"""The build step — the missing arm, and the promotion it makes possible.

Before this existed the loop could not heal anything even in principle. `DeployOrder.image` was
carried and read by NOTHING: the agent ran one fixed `docker compose up --force-recreate`, so a "fix
deploy" recreated the container from the image already on the host. The gate then examined that same
unpatched service and legitimately said "still reproduces", and the escalation blamed the patch.

These tests pin the four properties that make the arm safe:

1. source arrives as a COMMIT REFERENCE on a branch prefix the HOST allows, never inline;
2. the agent promotes only images IT BUILT, for the service it built them for;
3. a promotion needs a PRE-promotion (candidate) verdict — a verdict about the live service says
   nothing about the image being shipped;
4. "deployed" means the running container really is that digest.
"""

from __future__ import annotations

import json

import pytest

from oracle_core.signing import Signer

from skopos.remediation.agent_executor import NodeDeployExecutor
from skopos.remediation.agent_state import AgentStateStore, BuildRecord
from skopos.remediation.deploy_order import (
    BuildOrder,
    DeployOrder,
    sign_build_order,
    sign_deploy_order,
    verify_build_chain,
    verify_deploy_chain,
)

COMMIT = "c" * 40
DIGEST = "sha256:" + "ab" * 32


def _verdict(momus: Signer, finding_id="mom-1", fixed=True, gated="candidate"):
    v = {"finding_id": finding_id, "target": "svc", "probe": "p", "fixed": fixed,
         "outcome": "no_finding" if fixed else "finding", "detail": "d", "gated": gated,
         "checked_at": "2026-01-01T00:00:00Z", "verifier_pubkey": momus.public_key_b64}
    canon = json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    v["signature"] = momus.sign_payload(canon)
    return v


def _build_order(cond: Signer, *, service="svc", sha=COMMIT, branch="momus/fix-mom-1"):
    order = BuildOrder(finding_id="mom-1", service=service, host="svc",
                       commit_sha=sha, branch=branch)
    sign_build_order(order, cond)
    return order


# ── 1. the build order: a reference, on an allowed branch ─────────────────────
def test_build_order_accepts_a_signed_order_on_an_allowed_branch(tmp_path):
    cond = Signer(str(tmp_path / "c"))
    ok, why = verify_build_chain(_build_order(cond).to_dict(),
                                 conductor_pubkey=cond.public_key_b64,
                                 service_allowlist=["svc"],
                                 allowed_branch_prefixes=["momus/fix-"])
    assert ok, why


def test_build_from_an_unprotected_branch_is_refused(tmp_path):
    """A build from `main` would be a build of whatever anyone last merged. The prefix rule is what
    keeps machine-authored source in a namespace a human can protect and grep for."""
    cond = Signer(str(tmp_path / "c"))
    for branch in ("main", "master", "feature/sneaky", "momus/other-"):
        order = _build_order(cond, branch=branch)
        ok, why = verify_build_chain(order.to_dict(), conductor_pubkey=cond.public_key_b64,
                                     service_allowlist=["svc"],
                                     allowed_branch_prefixes=["momus/fix-"])
        assert not ok and "not under an allowed prefix" in why, branch


def test_build_order_refuses_anything_that_is_not_a_commit_id(tmp_path):
    """The agent resolves the id itself, so a ref name, a range or an option has no business here."""
    cond = Signer(str(tmp_path / "c"))
    for sha in ("HEAD", "main", "../../etc/passwd", "c" * 41, "--upload-pack=evil", ""):
        order = _build_order(cond, sha=sha)
        ok, why = verify_build_chain(order.to_dict(), conductor_pubkey=cond.public_key_b64,
                                     service_allowlist=["svc"],
                                     allowed_branch_prefixes=["momus/fix-"])
        assert not ok and "not a hex commit id" in why, sha


def test_build_order_refuses_a_service_the_host_never_allowlisted(tmp_path):
    cond = Signer(str(tmp_path / "c"))
    ok, why = verify_build_chain(_build_order(cond, service="hub").to_dict(),
                                 conductor_pubkey=cond.public_key_b64,
                                 service_allowlist=["svc"],
                                 allowed_branch_prefixes=["momus/fix-"])
    assert not ok and "allowlist" in why


def test_a_build_order_is_not_a_deploy_order(tmp_path):
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    ok, why = verify_deploy_chain(_build_order(cond).to_dict(),
                                  conductor_pubkey=cond.public_key_b64,
                                  momus_pubkey=momus.public_key_b64, service_allowlist=["svc"])
    assert not ok and "not a deploy order" in why


# ── the fake docker for build/promote ─────────────────────────────────────────
class FakeBuildDocker:
    def __init__(self, *, tip=COMMIT, digest=DIGEST, build_rc=0, candidate_status="running",
                 running_image="sha256:OLD", compose_ref="svc:latest"):
        self.calls: list[list[str]] = []
        self.tip = tip
        self.digest = digest
        self.build_rc = build_rc
        self.candidate_status = candidate_status
        self.live_status = "running"
        self.running_image = running_image
        self.compose_ref = compose_ref
        self.promoted_to: str | None = None

    def __call__(self, argv, timeout, *rest):
        self.calls.append(list(argv))
        j = " ".join(argv)
        if argv[:1] == ["git"]:
            if "rev-parse" in argv:
                return 0, self.tip + "\n", ""
            return 0, "", ""
        if argv[:2] == ["docker", "build"]:
            return self.build_rc, "built\n", ("" if self.build_rc == 0 else "build blew up")
        if argv[:3] == ["docker", "image", "inspect"]:
            return (0, self.digest + "\n", "") if self.digest else (1, "", "no such image")
        if argv[:2] == ["docker", "run"]:
            return 0, "candidate-id\n", ""
        if argv[:2] == ["docker", "rm"]:
            return 0, "", ""
        if argv[:2] == ["docker", "tag"]:
            self.promoted_to = argv[3]
            self.running_image = argv[2]
            return 0, "", ""
        if argv[:2] == ["docker", "compose"] and "ps" in argv:
            return 0, "container-id\n", ""
        if argv[:2] == ["docker", "compose"] and "up" in argv:
            return 0, "recreated\n", ""
        if argv[:2] == ["docker", "inspect"] and "{{.State.Restarting}}" in j:
            return 0, f"{self.live_status}|false|0|none\n", ""      # the health gate
        if argv[:2] == ["docker", "inspect"] and "{{.Image}}|{{.Config.Image}}" in j:
            return 0, f"{self.running_image}|{self.compose_ref}\n", ""
        if argv[:2] == ["docker", "inspect"] and "NetworkSettings" in j:
            return 0, "momus-net\n", ""
        if argv[:2] == ["docker", "inspect"] and "{{.State.Status}}" in j:
            return 0, self.candidate_status + "\n", ""              # the candidate liveness check
        if argv[:2] == ["docker", "inspect"]:
            return 0, "running|false|0|none\n", ""
        return 0, "", ""


def _executor(tmp_path, cond, momus, docker, **kw):
    return NodeDeployExecutor(
        conductor_pubkey=cond.public_key_b64, momus_pubkey=momus.public_key_b64,
        service_allowlist=["svc"], compose_file="dc.yml", dry_run=False,
        state=AgentStateStore(str(tmp_path / "agent" / "deploys.jsonl")),
        repo_url="http://127.0.0.1:3000/alexar76/aicom.git",
        repo_dir=str(tmp_path / "agent" / "repo.git"),
        work_dir=str(tmp_path / "agent" / "wt"),
        build_map={"svc": {"dockerfile": "svc/Dockerfile", "context": ".",
                           "image_ref": "svc:latest", "network": "momus-net"}},
        runner=docker, sleeper=lambda _s: None, **kw)


# ── 2. building ───────────────────────────────────────────────────────────────
def test_build_produces_a_digest_and_a_probeable_candidate(tmp_path):
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    docker = FakeBuildDocker()
    ex = _executor(tmp_path, cond, momus, docker)
    out = ex.execute_build(_build_order(cond).to_dict())
    assert out["built"] and out["image_digest"] == DIGEST
    assert out["candidate_running"] is True
    # An image nobody can reach cannot be gated, so the build also starts the candidate.
    assert any(a[:2] == ["docker", "run"] for a in docker.calls)
    assert ex.state.built_image(DIGEST).service == "svc"


def test_build_refuses_a_commit_that_is_not_the_branch_tip(tmp_path):
    """Without this the prefix check is decorative: an order could name any commit in the repo and
    label it with an allowed branch that had nothing to do with that code."""
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    docker = FakeBuildDocker(tip="d" * 40)
    ex = _executor(tmp_path, cond, momus, docker)
    out = ex.execute_build(_build_order(cond).to_dict())
    assert not out["built"] and "not the tip" in out["reason"]
    assert not any(a[:2] == ["docker", "build"] for a in docker.calls)


def test_build_refuses_a_service_with_no_local_recipe(tmp_path):
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    ex = _executor(tmp_path, cond, momus, FakeBuildDocker())
    ex.build_map = {}                                  # a host that never described this service
    out = ex.execute_build(_build_order(cond).to_dict())
    assert out["refused"] and "no local build recipe" in out["reason"]


def test_agent_refuses_a_signed_build_order_for_another_host(tmp_path):
    """A shared queue credential must not turn an order for host A into authority on host B."""
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    docker = FakeBuildDocker()
    ex = _executor(tmp_path, cond, momus, docker)
    ex.host = "node-b"

    out = ex.execute_build(_build_order(cond).to_dict())

    assert out["refused"] and "not this agent 'node-b'" in out["reason"]
    assert docker.calls == []


def test_build_without_a_digest_is_not_a_build(tmp_path):
    """A tag is mutable. Without a digest there is nothing for the gate to bind to and nothing the
    deploy step could check against the build journal."""
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    ex = _executor(tmp_path, cond, momus, FakeBuildDocker(digest=""))
    out = ex.execute_build(_build_order(cond).to_dict())
    assert not out["built"] and "image digest" in out["reason"]


def test_a_failed_build_reports_the_failure(tmp_path):
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    ex = _executor(tmp_path, cond, momus, FakeBuildDocker(build_rc=1))
    out = ex.execute_build(_build_order(cond).to_dict())
    assert not out["built"] and "docker build failed" in out["reason"]


def test_a_candidate_that_will_not_start_is_reported_not_hidden(tmp_path):
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    ex = _executor(tmp_path, cond, momus, FakeBuildDocker(candidate_status="exited"))
    out = ex.execute_build(_build_order(cond).to_dict())
    assert out["built"] and out["candidate_running"] is False
    assert "not running" in out["candidate"]


# ── 3. promoting: only what this agent built, only on a candidate verdict ─────
def _deploy_order(cond, momus, *, image=DIGEST, gated="candidate", service="svc"):
    order = DeployOrder(finding_id="mom-1", service=service, host="svc", image=image,
                        momus_verdict=_verdict(momus, gated=gated))
    sign_deploy_order(order, cond)
    return order


def test_promoting_an_image_needs_a_pre_promotion_verdict(tmp_path):
    """THE gate's teeth. A verdict that examined the live service says nothing about the image being
    shipped — which is how the old loop could call a deploy 'verified' having examined the build it
    was replacing."""
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    ok, why = verify_deploy_chain(_deploy_order(cond, momus, gated="live").to_dict(),
                                  conductor_pubkey=cond.public_key_b64,
                                  momus_pubkey=momus.public_key_b64, service_allowlist=["svc"])
    assert not ok and "never looked at" in why

    ok, why = verify_deploy_chain(_deploy_order(cond, momus, gated="candidate").to_dict(),
                                  conductor_pubkey=cond.public_key_b64,
                                  momus_pubkey=momus.public_key_b64, service_allowlist=["svc"])
    assert ok, why


def test_gated_cannot_be_relabelled_on_the_wire(tmp_path):
    """`gated` sits inside the signed FixVerdict, and that verdict sits inside the signed order — so
    flipping it breaks the conductor's signature before the verdict's own is even reached. Two
    independent signatures cover it; if it were an unsigned field, neither would."""
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    order = _deploy_order(cond, momus, gated="candidate").to_dict()
    order["momus_verdict"]["gated"] = "live"        # tamper
    ok, why = verify_deploy_chain(order, conductor_pubkey=cond.public_key_b64,
                                  momus_pubkey=momus.public_key_b64, service_allowlist=["svc"])
    assert not ok and "signature does not verify" in why

    # And the reverse: a verdict MOMUS signed for the live service cannot be re-signed by the
    # conductor into a promotion, because the promotion check reads the signed value.
    live = _deploy_order(cond, momus, gated="live").to_dict()
    ok, why = verify_deploy_chain(live, conductor_pubkey=cond.public_key_b64,
                                  momus_pubkey=momus.public_key_b64, service_allowlist=["svc"])
    assert not ok and "never looked at" in why


def test_the_agent_refuses_an_image_it_did_not_build(tmp_path):
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    ex = _executor(tmp_path, cond, momus, FakeBuildDocker())
    out = ex.execute(_deploy_order(cond, momus, image="sha256:" + "ff" * 32).to_dict())
    assert out["refused"] and "not built by this agent" in out["reason"]


def test_the_agent_refuses_to_cross_deploy_another_services_image(tmp_path):
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    ex = _executor(tmp_path, cond, momus, FakeBuildDocker())
    ex.state.record_build(BuildRecord(order_id="b1", service="other", commit_sha=COMMIT,
                                      image_tag="other:momus", image_digest=DIGEST))
    out = ex.execute(_deploy_order(cond, momus).to_dict())
    assert out["refused"] and "built for 'other'" in out["reason"]


def test_promotion_moves_the_compose_tag_onto_the_built_digest(tmp_path):
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    docker = FakeBuildDocker()
    ex = _executor(tmp_path, cond, momus, docker)
    ex.execute_build(_build_order(cond).to_dict())
    docker.running_image = "sha256:OLD"            # the live container, pre-promotion

    out = ex.execute(_deploy_order(cond, momus).to_dict())
    # `compose up` resolves a TAG, so promoting means moving the tag onto the digest — the same
    # mechanism rollback uses, in the other direction.
    assert docker.promoted_to == "svc:latest"
    assert out["promoted_image"] == DIGEST and out["deployed"] is True
    assert out["previous_image"] == "sha256:OLD", "the rollback target must still be recorded"


# ── 4. "deployed" has to mean the patch is actually running ───────────────────
def test_a_deploy_that_did_not_actually_apply_the_image_is_a_failure(tmp_path):
    """`compose up` reports success for recreating a container from whatever the tag resolved to. So
    'deployed: true' alone never proved the patch had been applied."""
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))

    class TagIgnored(FakeBuildDocker):
        def __call__(self, argv, timeout, *rest):
            rc, out, err = super().__call__(argv, timeout, *rest)
            if argv[:2] == ["docker", "tag"]:
                self.running_image = "sha256:STALE"   # the promotion silently did not take
            return rc, out, err

    docker = TagIgnored()
    ex = _executor(tmp_path, cond, momus, docker)
    ex.execute_build(_build_order(cond).to_dict())
    out = ex.execute(_deploy_order(cond, momus).to_dict())
    assert out["deployed"] is False and out["image_mismatch"] is True
    assert "did NOT take effect" in out["reason"]


def test_a_plain_restart_with_no_image_still_works(tmp_path):
    """Not every order is a fix. An order with no image is a restart of the current build, and must
    not be dragged through the build-journal check."""
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    docker = FakeBuildDocker()
    ex = _executor(tmp_path, cond, momus, docker)
    order = DeployOrder(finding_id="mom-1", service="svc", host="svc",
                        momus_verdict=_verdict(momus, gated="live"))
    sign_deploy_order(order, cond)
    out = ex.execute(order.to_dict())
    assert out["deployed"] is True and out["promoted_image"] == ""
    assert docker.promoted_to is None, "a restart must not re-tag anything"


# ── the conductor must actually authenticate to the fix route ─────────────────
def test_factory_client_sends_the_shared_secret(monkeypatch):
    """The fix route is shared-secret gated and fail-closed in production. A client that does not
    send the header gets 401 on every call, and the job escalates blaming a patch that was never
    authored — the same omission a live run already found once with MOMUS's operator token."""
    from skopos.remediation.clients import FactoryClient

    monkeypatch.setenv("AIFACTORY_REMEDIATION_KEY", "sh4red")
    client = FactoryClient("http://fixer:9086", dry_run=False)
    assert client._api_key == "sh4red"

    monkeypatch.delenv("AIFACTORY_REMEDIATION_KEY", raising=False)
    assert FactoryClient("http://fixer:9086", dry_run=False)._api_key == ""
    assert FactoryClient("http://fixer:9086", dry_run=False, api_key="explicit")._api_key == "explicit"


@pytest.mark.asyncio
async def test_a_refused_fix_route_is_a_config_error_not_a_bad_patch(monkeypatch):
    """401/403/404/503 mean an operator has to fix something. Retrying them three times and then
    blaming the fix is the mistake the gate and unset-URL paths already corrected."""
    import httpx

    from skopos.remediation.clients import FactoryClient

    for code, needle in ((401, "AIFACTORY_REMEDIATION_KEY"), (503, "unauthenticated caller"),
                         (404, "not enabled on this Factory build")):
        client = FactoryClient("http://fixer:9086", dry_run=False)

        async def fake_post(*a, code=code, **kw):
            raise httpx.HTTPStatusError("refused", request=httpx.Request("POST", "http://x"),
                                        response=httpx.Response(code))

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
        out = await client.request_fix({"finding_id": "x"})
        assert out["ok"] is False and out["config_error"] is True, code
        assert needle in out["error"], (code, out["error"])


def test_the_component_name_is_translated_to_the_compose_service(tmp_path):
    """Found by running the real chain: MOMUS names its canary target `canary`, but the compose
    service is `momus-canary`. The conductor sets `service = job.component`, so without a host-side
    mapping every deploy would target a service that does not exist. The order carries the component
    — that is what the finding is about — and the HOST translates it, like the allowlist."""
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    docker = FakeBuildDocker()
    ex = NodeDeployExecutor(
        conductor_pubkey=cond.public_key_b64, momus_pubkey=momus.public_key_b64,
        service_allowlist=["canary"], compose_file="dc.yml", dry_run=False,
        state=AgentStateStore(str(tmp_path / "agent" / "deploys.jsonl")),
        build_map={"canary": {"dockerfile": "momus/Dockerfile", "context": ".",
                              "image_ref": "momus-canary:latest", "network": "momus-net",
                              "compose_service": "momus-canary"}},
        runner=docker, sleeper=lambda _s: None)

    assert ex._compose_service("canary") == "momus-canary"
    # No mapping declared → falls back to the component name, the common case.
    assert ex._compose_service("something-else") == "something-else"

    order = DeployOrder(finding_id="mom-1", service="canary", host="canary",
                        momus_verdict=_verdict(momus, gated="live"))
    sign_deploy_order(order, cond)
    ex.execute(order.to_dict())
    ups = [a for a in docker.calls if a[:2] == ["docker", "compose"] and "up" in a]
    assert ups and ups[0][-1] == "momus-canary", ups
    # And MOMUS probes `<compose-host>-candidate`, so the candidate must be named after the compose
    # service too, or the pre-promotion gate looks for a container nobody created.
    assert ex._candidate_name("canary") == "momus-canary-candidate"


# ── the git credential ────────────────────────────────────────────────────────
def test_an_ssh_deploy_key_is_supplied_out_of_band(tmp_path):
    """A credential in a URL lands in git's logs, in reflogs and in the process list. And the key
    style matters: Gitea ACCESS TOKENS are user-scoped (`write:repository` covers every repo that
    user owns), while a deploy key is per-repository — and `push_whitelist_deploy_keys` is false on
    this repo's `main` protection, so a deploy key cannot reach `main` while the owner's account can.
    That is the second, independent policy."""
    from skopos.remediation.git_push import GitPushConfig, GitPusher

    seen: list[list[str]] = []
    pusher = GitPusher(GitPushConfig(repo_url="ssh://git@gitea:2222/alexar76/aicom.git",
                                     ssh_key_path="/keys/conductor_ed25519"),
                       runner=lambda argv, cwd=None, stdin=None: (seen.append(argv), (0, "", ""))[1])
    pusher._git("ls-remote", "origin")
    argv = seen[0]
    joined = " ".join(argv)
    assert "core.sshCommand=" in joined and "/keys/conductor_ed25519" in joined
    assert "IdentitiesOnly=yes" in joined and "BatchMode=yes" in joined
    assert "ssh://git@gitea" not in joined or "@" not in argv[-1].split("//")[-1].split("/")[0].replace("git@", "")

    # An HTTP token still travels as a header, never in the URL — and never in argv
    # (/proc/cmdline is world-readable). git reads GIT_CONFIG_* from the environment.
    seen.clear()
    env_seen: list[dict[str, str]] = []

    def _record(argv, cwd=None, stdin=None):
        import os as _os
        seen.append(argv)
        env_seen.append({k: v for k, v in _os.environ.items() if k.startswith("GIT_CONFIG")})
        return 0, "", ""

    http = GitPusher(GitPushConfig(repo_url="http://127.0.0.1:3000/alexar76/aicom.git", token="tok"),
                     runner=_record)
    http._git("ls-remote", "origin")
    assert not any("http.extraHeader=Authorization: token tok" in a for a in seen[0])
    assert env_seen and env_seen[0].get("GIT_CONFIG_VALUE_0") == "Authorization: token tok"


def test_the_pusher_refuses_a_branch_outside_its_prefix(tmp_path):
    """Belt and braces on top of server-side protection: a bug that computed the wrong branch name
    must not be able to reach a protected one."""
    from skopos.remediation.git_push import GitPushConfig, GitPusher

    pusher = GitPusher(GitPushConfig(repo_url="ssh://git@gitea:2222/x/y.git",
                                     branch_prefix="momus/fix-"))
    for branch in ("main", "master", "release", "momus/other"):
        ok, why = pusher._push("/tmp/nonexistent", branch)
        assert not ok and "refusing to push" in why, branch


def test_a_cold_mirror_still_fetches_the_tracking_refs(tmp_path):
    """The bug a live run found and no test could: a `--bare` clone puts upstream heads in
    `refs/heads/*`, while worktrees here are based on `refs/remotes/origin/*`, which only the fetch
    refspec creates. Cloning and returning left the FIRST job with `fatal: invalid reference`."""
    from skopos.remediation.git_push import GitPushConfig, GitPusher

    calls: list[list[str]] = []

    def runner(argv, cwd=None, stdin=None):
        calls.append(argv)
        return 0, "", ""

    cfg = GitPushConfig(repo_url="ssh://git@gitea:2222/x/y.git", work_root=str(tmp_path / "git"))
    pusher = GitPusher(cfg, runner=runner)
    ok, why = pusher._ensure_mirror()          # mirror dir does not exist yet → cold path
    assert ok, why
    joined = [" ".join(a) for a in calls]
    assert any("clone --bare" in j for j in joined), joined
    assert any("+refs/heads/*:refs/remotes/origin/*" in j for j in joined), \
        "a cold clone must be followed by the fetch that creates the tracking refs"


def test_the_base_ref_falls_back_until_one_resolves(tmp_path):
    """`--verify` each candidate rather than assuming: a mirror without remote-tracking refs used to
    produce an unusable base ref instead of a usable fallback."""
    from skopos.remediation.git_push import GitPushConfig, GitPusher

    resolvable = {"refs/heads/main"}

    def runner(argv, cwd=None, stdin=None):
        if "symbolic-ref" in argv:
            return 1, "", "no HEAD"
        if "rev-parse" in argv:
            return (0, "", "") if argv[-1] in resolvable else (1, "", "bad ref")
        return 0, "", ""

    pusher = GitPusher(GitPushConfig(repo_url="ssh://git@gitea:2222/x/y.git",
                                     work_root=str(tmp_path)), runner=runner)
    assert pusher._base_ref() == "refs/heads/main"


def test_a_cold_clone_gets_a_longer_timeout():
    """A ~1GB bare clone at 300s is not a margin worth betting a cold start on."""
    from skopos.remediation import git_push

    assert git_push._CLONE_TIMEOUT_S >= 1200 > git_push._GIT_TIMEOUT_S


@pytest.mark.parametrize("finding_id", ("../../tmp/owned", "mom/other", "-option", "", "x" * 97))
def test_git_pusher_refuses_unsafe_finding_ids_before_touching_disk(tmp_path, finding_id):
    """The signed finding id is also used in worktree paths and ref names; it is data, not a path."""
    from skopos.remediation.git_push import GitPushConfig, GitPusher

    calls: list[list[str]] = []
    pusher = GitPusher(
        GitPushConfig(repo_url="ssh://git@gitea:2222/x/y.git", work_root=str(tmp_path / "git")),
        runner=lambda argv, cwd=None, stdin=None: (calls.append(argv), (0, "", ""))[1],
    )

    out = pusher.push_patch(
        finding_id=finding_id,
        component="svc",
        diff="diff --git a/a b/a\n",
        summary="test",
    )

    assert out.ok is False and "unsafe" in out.error
    assert calls == []


def test_the_candidate_can_be_given_env_from_the_host(tmp_path):
    """A candidate that starts on the wrong port is unreachable, and the gate reports that as
    'inconclusive' — blocking the deploy for a reason that has nothing to do with the patch. The env
    comes from the host's build map, never from an order."""
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    docker = FakeBuildDocker()
    ex = _executor(tmp_path, cond, momus, docker)
    ex.build_map["svc"]["env"] = {"PORT": "9450", "MODE": "probe"}
    ex.execute_build(_build_order(cond).to_dict())
    run = [a for a in docker.calls if a[:2] == ["docker", "run"]][0]
    assert "-e" in run and "PORT=9450" in run and "MODE=probe" in run
    assert ["--cap-drop", "ALL"] == run[run.index("--cap-drop"):run.index("--cap-drop") + 2]
    assert "no-new-privileges:true" in run
    # The image must remain the LAST argument, or docker parses it as part of the env list.
    assert run[-1].startswith("svc:momus-")


def test_a_candidate_without_declared_env_is_still_started(tmp_path):
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    docker = FakeBuildDocker()
    ex = _executor(tmp_path, cond, momus, docker)
    out = ex.execute_build(_build_order(cond).to_dict())
    assert out["candidate_running"] is True
    run = [a for a in docker.calls if a[:2] == ["docker", "run"]][0]
    assert "-e" not in run and run[-1].startswith("svc:momus-")


def test_default_recipes_map_hub_and_canary_to_compose_services():
    """Widening the loop to hub is a recipe + allowlist, not a new executor. MOMUS names
    the target `hub`; compose on the fleet is also `hub`. Canary still needs the rename."""
    from skopos.remediation.recipes import DEFAULT_BUILD_RECIPES, merge_build_map

    assert DEFAULT_BUILD_RECIPES["hub"]["compose_service"] == "hub"
    assert DEFAULT_BUILD_RECIPES["hub"]["dockerfile"] == "aimarket-hub/Dockerfile"
    assert DEFAULT_BUILD_RECIPES["canary"]["compose_service"] == "momus-canary"
    assert "momus" not in DEFAULT_BUILD_RECIPES
    assert "treasury" not in DEFAULT_BUILD_RECIPES
    from skopos.remediation.recipes import DEFAULT_SERVICE_ALLOWLIST
    assert "hub" in DEFAULT_SERVICE_ALLOWLIST and "canary" in DEFAULT_SERVICE_ALLOWLIST
    assert "momus" not in DEFAULT_SERVICE_ALLOWLIST
    merged = merge_build_map({"hub": {"compose_service": "aimarket-hub"}})
    assert merged["hub"]["compose_service"] == "aimarket-hub"
    assert merged["canary"]["compose_service"] == "momus-canary"


class TestARetryGetsItsOwnBranch:
    """Measured on the first real autonomous run: a re-opened job authored a second patch, tried
    to push it to the branch the first attempt already occupied, and was refused as a
    non-fast-forward — "a human must reconcile it". Forcing is correctly refused, so every retry
    after the first could never land.
    """

    def _pusher(self):
        from skopos.remediation.git_push import GitPushConfig, GitPusher

        return GitPusher(GitPushConfig(repo_url="http://git.test/x.git"))

    def test_the_first_attempt_keeps_the_original_name(self):
        """So existing branches, published orders and every prior test are unaffected."""
        assert self._pusher().branch_for("mom-abc") == "momus/fix-mom-abc"
        assert self._pusher().branch_for("mom-abc", 0) == "momus/fix-mom-abc"

    def test_each_retry_gets_a_branch_of_its_own(self):
        pusher = self._pusher()
        assert pusher.branch_for("mom-abc", 1) == "momus/fix-mom-abc-1"
        assert pusher.branch_for("mom-abc", 2) == "momus/fix-mom-abc-2"

    def test_the_attempts_are_distinct_so_a_push_always_fast_forwards(self):
        pusher = self._pusher()
        names = {pusher.branch_for("mom-abc", n) for n in range(4)}
        assert len(names) == 4

    def test_a_retry_branch_still_matches_the_machine_authored_prefix(self):
        """The relay refuses anything outside momus/fix-, and the hand checks the same prefix."""
        assert self._pusher().branch_for("mom-abc", 3).startswith("momus/fix-")

    def test_an_unsafe_finding_id_is_still_refused(self):
        import pytest as _pytest

        with _pytest.raises(ValueError):
            self._pusher().branch_for("../../etc/passwd", 1)


class TestTheBranchNameMustBeFreeNotMerelyNumbered:
    """A re-opened job resets its attempt budget to zero — by design, so a finding that came
    back gets a fresh ladder. That makes `attempt` useless as a unique name: the second
    re-open computes the same branch as the first and pushes a different commit to it.

    Measured on a live autonomous run: the autopilot dispatched by itself, the conductor
    recognised the regression, the Factory authored a patch in seven seconds — and the cycle
    died at `push rejected as non-fast-forward for 'momus/fix-...-1' — refusing to force`.
    Forcing stays refused; the name is chosen free instead.
    """

    def _pusher(self, taken):
        from skopos.remediation.git_push import GitPushConfig, GitPusher

        pusher = GitPusher(GitPushConfig(repo_url="http://git.test/x.git"))
        listing = "\n".join(f"origin/{name}" for name in taken)
        pusher._git = lambda *a, **kw: (0, listing, "")
        return pusher

    def test_an_unused_name_is_returned_unchanged(self):
        assert self._pusher([]).free_branch_for("mom-abc") == "momus/fix-mom-abc"

    def test_a_taken_name_is_stepped_over(self):
        pusher = self._pusher(["momus/fix-mom-abc"])
        assert pusher.free_branch_for("mom-abc") == "momus/fix-mom-abc-1"

    def test_it_walks_past_every_branch_a_previous_cycle_left(self):
        """The live shape: two earlier cycles, and the attempt counter back at 1."""
        pusher = self._pusher(["momus/fix-mom-abc", "momus/fix-mom-abc-1", "momus/fix-mom-abc-2"])
        assert pusher.free_branch_for("mom-abc", 1) == "momus/fix-mom-abc-3"

    def test_it_never_goes_backwards_below_the_attempt(self):
        """Attempt 3 with nothing taken still starts at 3 — the ladder stays legible."""
        assert self._pusher([]).free_branch_for("mom-abc", 3) == "momus/fix-mom-abc-3"

    def test_an_unreadable_ref_listing_falls_back_to_the_plain_name(self):
        from skopos.remediation.git_push import GitPushConfig, GitPusher

        pusher = GitPusher(GitPushConfig(repo_url="http://git.test/x.git"))
        pusher._git = lambda *a, **kw: (128, "", "not a git repository")
        # No worse off than before, and still never forcing.
        assert pusher.free_branch_for("mom-abc", 2) == "momus/fix-mom-abc-2"

    def test_a_free_name_still_matches_the_machine_authored_prefix(self):
        pusher = self._pusher(["momus/fix-mom-abc", "momus/fix-mom-abc-1"])
        assert pusher.free_branch_for("mom-abc").startswith("momus/fix-")

    def test_the_probe_is_bounded(self):
        from skopos.remediation.git_push import GitPusher

        taken = ["momus/fix-mom-abc"] + [f"momus/fix-mom-abc-{n}" for n in range(1, 400)]
        pusher = self._pusher(taken)
        name = pusher.free_branch_for("mom-abc")
        assert name == f"momus/fix-mom-abc-{GitPusher.MAX_BRANCH_PROBE + 1}"

    def test_the_ordinal_of_a_branch_round_trips(self):
        pusher = self._pusher([])
        assert pusher._ordinal_of("mom-abc", "momus/fix-mom-abc") == 0
        assert pusher._ordinal_of("mom-abc", "momus/fix-mom-abc-7") == 7


class TestADeadCandidateSaysWhyItDied:
    """"candidate container is 'exited'" is true and useless: the next attempt was told a
    container failed and not WHY. A real one read `ValueError: An Ed25519 private key is 32
    bytes long` — a fix in one line, thrown away because nobody carried it back."""

    def _executor(self, monkeypatch, logs_rc=0, logs_out="", status="exited"):
        from skopos.remediation.agent_executor import NodeDeployExecutor

        ex = NodeDeployExecutor.__new__(NodeDeployExecutor)
        ex.health_wait_s = 0
        ex.build_map = {}
        ex._sleep = lambda *a, **k: None

        def _run(argv, timeout=None):
            if argv[:2] == ["docker", "logs"]:
                return logs_rc, logs_out, ""
            if argv[:2] == ["docker", "inspect"]:
                return 0, status, ""
            return 0, "", ""

        ex._run = _run
        ex.remove_candidate = lambda service: None
        ex._network_of = lambda service: "net"
        ex._candidate_name = lambda service: "svc-candidate"
        return ex

    def test_the_traceback_is_carried_back(self, monkeypatch):
        err = "ValueError: An Ed25519 private key is 32 bytes long"
        ex = self._executor(monkeypatch, logs_out=f"Traceback (most recent call last):\n{err}\n")
        started, where = ex._start_candidate("svc", "img")
        assert started is False
        assert "exited" in where
        assert err in ex._last_candidate_error

    def test_a_running_candidate_carries_no_error(self, monkeypatch):
        ex = self._executor(monkeypatch, status="running")
        started, _ = ex._start_candidate("svc", "img")
        assert started is True
        assert ex._last_candidate_error == ""

    def test_unreadable_logs_are_not_fatal(self, monkeypatch):
        ex = self._executor(monkeypatch, logs_rc=1)
        started, _ = ex._start_candidate("svc", "img")
        assert started is False
        assert ex._last_candidate_error == ""

    def test_the_tail_is_bounded(self, monkeypatch):
        from skopos.remediation.agent_executor import NodeDeployExecutor

        ex = self._executor(monkeypatch, logs_out="x" * 50_000)
        ex._start_candidate("svc", "img")
        assert len(ex._last_candidate_error) <= NodeDeployExecutor.CANDIDATE_LOG_TAIL
