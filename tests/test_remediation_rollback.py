"""Rollback, and the ordering bug that made the loop unshippable.

Two defects are pinned here, both invisible in dry-run and both fatal the moment an operator turns
it off:

1. **The conductor re-tested before the agent had deployed.** It published an order and immediately
   asked MOMUS to verify "the live container". Agents poll on an interval, so that verdict described
   the OLD build: every job would read as a post-deploy regression, burn its attempts and escalate,
   while the patch it was judging had not been applied.
2. **There was no way back.** Nothing recorded what had been running, so a patch that came up broken
   stayed live through three more attempts and then through the escalation.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from oracle_core.signing import Signer

from skopos.remediation.agent_executor import NodeDeployExecutor
from skopos.remediation.agent_state import AgentStateStore
from skopos.remediation.conductor import Conductor, RemediationConfig
from skopos.remediation.deploy_order import (
    DeployOrder,
    RollbackOrder,
    sign_deploy_order,
    sign_rollback_order,
    verify_deploy_chain,
    verify_rollback_chain,
)
from skopos.remediation.health import (
    FLAG_AGENT_NEVER_CLAIMED,
    FLAG_AGENT_REFUSED,
    FLAG_HEALTH_GATE_FAILED,
    FLAG_LIVE_REGRESSION,
    FLAG_ROLLBACK_FAILED,
    FLAG_ROLLED_BACK,
)
from skopos.remediation.jobs import JobState


def _signed_ticket(key_path: str, finding_id: str, component: str = "svc") -> dict:
    """A ticket with a Blame attestation signed by the key the conductor trusts.

    Outside dry-run the conductor refuses tickets it cannot verify, so every live-mode test has to
    produce a real one — which is the guard working, not a test inconvenience."""
    from dataclasses import asdict

    from momus.findings import Blame, FindingSigner
    blame = FindingSigner(key_path).sign_blame(Blame(
        finding_id=finding_id, component=component, severity="high", hop="probe",
        summary="test finding"))
    return {"finding_id": finding_id, "component": component, "target": component,
            "probe": "p", "severity": "high", "blame": asdict(blame)}


def _verdict(momus: Signer, finding_id="mom-1", fixed=True):
    v = {"finding_id": finding_id, "target": "oracles", "probe": "p", "fixed": fixed,
         "outcome": "no_finding" if fixed else "finding", "detail": "d",
         "checked_at": "2026-01-01T00:00:00Z", "verifier_pubkey": momus.public_key_b64}
    canon = json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    v["signature"] = momus.sign_payload(canon)
    return v


# ── a fake docker, so the health gate and the undo can be exercised ────────────
class FakeDocker:
    """Records argv and answers the three questions the executor asks docker.

    ``restarts`` drives the health gate: a freshly recreated container with a restart count is a
    crash loop, which is precisely the failure `docker compose up` exits 0 on."""

    def __init__(self, *, running_image="sha256:OLD", compose_ref="svc:latest",
                 new_image="sha256:NEW", restarts=0, status="running", tag_fails=False):
        self.calls: list[list[str]] = []
        self.running_image = running_image
        self.compose_ref = compose_ref
        self.new_image = new_image
        self.restarts = restarts
        self.status = status
        self.tag_fails = tag_fails
        self.deploys = 0
        self.tags: list[tuple[str, str]] = []

    def __call__(self, argv: list[str], timeout: int):
        self.calls.append(list(argv))
        if argv[:2] == ["docker", "compose"] and "ps" in argv:
            return 0, "container-id\n", ""
        if argv[:2] == ["docker", "inspect"] and "{{.Image}}|{{.Config.Image}}" in argv:
            img = self.new_image if self.deploys else self.running_image
            return 0, f"{img}|{self.compose_ref}\n", ""
        if argv[:2] == ["docker", "inspect"]:
            return 0, f"{self.status}|false|{self.restarts}|none\n", ""
        if argv[:2] == ["docker", "tag"]:
            if self.tag_fails:
                return 1, "", "No such image"
            self.tags.append((argv[2], argv[3]))
            self.running_image = argv[2]
            self.restarts = 0            # the restored image behaves
            return 0, "", ""
        if argv[:2] == ["docker", "compose"] and "up" in argv:
            self.deploys += 1
            return 0, "recreated\n", ""
        return 0, "", ""


def _executor(tmp_path, cond: Signer, momus: Signer, docker: FakeDocker, **kw):
    return NodeDeployExecutor(
        conductor_pubkey=cond.public_key_b64, momus_pubkey=momus.public_key_b64,
        service_allowlist=["svc"], compose_file="dc.yml", dry_run=False,
        state=AgentStateStore(str(tmp_path / "agent" / "deploys.jsonl")),
        runner=docker, sleeper=lambda _s: None, **kw)


def _deploy_order(cond: Signer, momus: Signer, service="svc", finding_id="mom-1"):
    order = DeployOrder(finding_id=finding_id, service=service, host="svc",
                        momus_verdict=_verdict(momus, finding_id))
    sign_deploy_order(order, cond)
    return order


# ── the executor: remember, gate, undo ────────────────────────────────────────
def test_executor_records_the_previous_image_before_deploying(tmp_path):
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    docker = FakeDocker()
    ex = _executor(tmp_path, cond, momus, docker)
    out = ex.execute(_deploy_order(cond, momus).to_dict())
    assert out["deployed"] and out["previous_image"] == "sha256:OLD"
    assert out["compose_image_ref"] == "svc:latest" and out["rollback_available"]
    # The record has to exist on the agent's own disk, or there is nothing to roll back to later.
    record = ex.state.all()[0]
    assert record["previous_image"] == "sha256:OLD" and record["can_roll_back"]


def test_executor_rolls_back_when_the_container_crash_loops(tmp_path):
    """`docker compose up` exits 0 for a container that then dies. The gate must catch that."""
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    docker = FakeDocker(restarts=3)
    ex = _executor(tmp_path, cond, momus, docker)
    out = ex.execute(_deploy_order(cond, momus).to_dict())
    assert out["deployed"] is False and out["health_gate_failed"]
    assert out["rolled_back"] and "crash loop" in out["reason"]
    # It restored the digest it recorded, by re-pointing the tag compose resolves.
    assert docker.tags == [("sha256:OLD", "svc:latest")]
    assert out["rollback"]["restored_image"] == "sha256:OLD"
    assert out["rollback"]["needs_human"] is False


def test_executor_reports_needs_human_when_the_old_image_is_also_broken(tmp_path):
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))

    class StillBroken(FakeDocker):
        def __call__(self, argv, timeout):
            rc, out, err = super().__call__(argv, timeout)
            if argv[:2] == ["docker", "tag"]:
                self.restarts = 9      # the rollback target is unhealthy too
            return rc, out, err

    docker = StillBroken(restarts=2)
    ex = _executor(tmp_path, cond, momus, docker)
    out = ex.execute(_deploy_order(cond, momus).to_dict())
    # Reverted, but the host is NOT fine. That must not read as a clean recovery.
    assert out["rolled_back"] and out["rollback"]["needs_human"] is True


def test_executor_says_so_when_the_old_image_was_pruned(tmp_path):
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    docker = FakeDocker(restarts=1, tag_fails=True)
    ex = _executor(tmp_path, cond, momus, docker)
    out = ex.execute(_deploy_order(cond, momus).to_dict())
    assert out["health_gate_failed"] and out["rolled_back"] is False
    assert "pruned" in out["rollback"]["reason"]


# ── the rollback order: no image, and it cannot be forged into a deploy ───────
def test_rollback_order_carries_no_image_field(tmp_path):
    """The safety property, asserted structurally: there is no field to smuggle an image in."""
    cond = Signer(str(tmp_path / "c"))
    undo = RollbackOrder(finding_id="mom-1", service="svc", host="svc", rollback_of="deploy-1")
    sign_rollback_order(undo, cond)
    assert "image" not in undo.to_dict()


def test_rollback_chain_accepts_a_valid_order(tmp_path):
    cond = Signer(str(tmp_path / "c"))
    undo = RollbackOrder(finding_id="mom-1", service="svc", host="svc", rollback_of="deploy-1")
    sign_rollback_order(undo, cond)
    ok, why = verify_rollback_chain(undo.to_dict(), conductor_pubkey=cond.public_key_b64,
                                    service_allowlist=["svc"])
    assert ok, why


def test_a_deploy_order_cannot_be_replayed_as_a_rollback(tmp_path):
    """Relabelling `kind` on the wire breaks the signature; and each verifier rejects the other kind
    outright, so a missing MOMUS verdict never reads as a broken chain."""
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    order = _deploy_order(cond, momus).to_dict()
    relabelled = {**order, "kind": "rollback"}
    ok, why = verify_rollback_chain(relabelled, conductor_pubkey=cond.public_key_b64,
                                    service_allowlist=["svc"])
    assert not ok and "signature does not verify" in why

    undo = RollbackOrder(finding_id="mom-1", service="svc", host="svc", rollback_of="deploy-1")
    sign_rollback_order(undo, cond)
    ok, why = verify_deploy_chain(undo.to_dict(), conductor_pubkey=cond.public_key_b64,
                                  momus_pubkey=momus.public_key_b64, service_allowlist=["svc"])
    assert not ok and "not a deploy order" in why


def test_rollback_is_refused_for_an_order_this_agent_never_executed(tmp_path):
    """The whole reason a rollback needs no MOMUS verdict: the target is resolved from the agent's
    own journal, so an order naming someone else's deploy resolves to nothing."""
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    ex = _executor(tmp_path, cond, momus, FakeDocker())
    undo = RollbackOrder(finding_id="mom-1", service="svc", host="svc",
                         rollback_of="deploy-that-never-happened")
    sign_rollback_order(undo, cond)
    out = ex.execute_rollback(undo.to_dict())
    assert out["refused"] and "never executed it" in out["reason"]


def test_rollback_is_refused_when_the_service_is_not_allowlisted(tmp_path):
    cond = Signer(str(tmp_path / "c"))
    undo = RollbackOrder(finding_id="mom-1", service="hub", host="h", rollback_of="deploy-1")
    sign_rollback_order(undo, cond)
    ok, why = verify_rollback_chain(undo.to_dict(), conductor_pubkey=cond.public_key_b64,
                                    service_allowlist=["svc"])
    assert not ok and "allowlist" in why


def test_conductor_ordered_rollback_restores_the_recorded_image(tmp_path):
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    docker = FakeDocker()
    ex = _executor(tmp_path, cond, momus, docker)
    deploy = _deploy_order(cond, momus)
    ex.execute(deploy.to_dict())          # healthy: nothing rolled back locally

    undo = RollbackOrder(finding_id="mom-1", service="svc", host="svc",
                         rollback_of=deploy.order_id, reason="live regression")
    sign_rollback_order(undo, cond)
    out = ex.execute_rollback(undo.to_dict())
    assert out["rolled_back"] and out["restored_image"] == "sha256:OLD"
    assert ex.state.get(deploy.order_id).rolled_back_at is not None


# ── the conductor: wait for the hand, then verify ─────────────────────────────
#: What a healthy build reports back. A digest, and a candidate container the gate can probe.
BUILT_DIGEST = "sha256:" + "ab" * 32
BUILD_OK = {"built": True, "image_digest": BUILT_DIGEST, "image_tag": "svc:momus-abcdef",
            "commit_sha": "c" * 40, "candidate_running": True, "candidate": "svc-candidate on net"}


def _live_conductor(tmp_path, monkeypatch, momus: Signer, *, gate_fixed=True, post_fixed=True,
                    max_attempts=2):
    """A conductor in live mode, with the Factory and git stubbed but the real state machine.

    The Factory returns a DIFF (it authors patches, not images); git accepts the branch; everything
    from the build order onwards is the code under test."""
    from skopos.remediation.git_push import PushResult

    cfg = RemediationConfig(data_dir=str(tmp_path / "rem"),
                            conductor_key_path=str(tmp_path / "rem" / "cond.key"),
                            dry_run=False, max_attempts=max_attempts,
                            momus_pubkey=momus.public_key_b64,
                            factory_url="http://factory.test",
                            deploy_result_timeout_s=3.0)
    conductor = Conductor(cfg)
    calls: list[str] = []

    async def retest(finding_id, *, candidate=False, **_):
        calls.append("gate" if candidate else "post")
        fixed = gate_fixed if candidate else post_fixed
        return _verdict(momus, finding_id=finding_id, fixed=fixed)

    async def fix(ticket, previous_failure="", attempt=1):
        return {"ok": True, "patch": {"component": ticket.get("component"),
                                      "summary": "enforce the ceiling",
                                      "diff": "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n"}}

    monkeypatch.setattr(conductor.momus, "retest", retest)
    monkeypatch.setattr(conductor.factory, "request_fix", fix)
    monkeypatch.setattr(conductor.git, "push_patch",
                        lambda **kw: PushResult(True, branch="momus/fix-" + kw["finding_id"],
                                                commit_sha="c" * 40))
    monkeypatch.setattr(conductor.git, "push_provenance", lambda **kw: PushResult(True))
    return conductor, calls


async def _claim_one(conductor, host, expected_kind, *, tries=200):
    """Wait for the next order for this host and assert what kind it is."""
    for _ in range(tries):
        await asyncio.sleep(0.02)
        q = conductor.orders.claim_for(host, agent_id=host)
        if q is not None:
            assert q.kind == expected_kind, f"expected a {expected_kind} order, got {q.kind}"
            return q
    raise AssertionError(f"no {expected_kind} order was published")


async def _act_as_agent(conductor, host, result, *, build=BUILD_OK):
    """Act as the node agent for a whole run: build first, then deploy.

    The build step is not optional any more — it is what turns the patch into an image, and without
    it there would be nothing to promote."""
    b = await _claim_one(conductor, host, "build")
    conductor.orders.report(b.order_id, build)
    d = await _claim_one(conductor, host, "deploy")
    conductor.orders.report(d.order_id, result)
    return d


@pytest.mark.asyncio
async def test_post_deploy_retest_waits_for_the_agent(tmp_path, monkeypatch):
    """THE ordering bug. The in-place verdict must be asked for AFTER the agent reports, not before:
    a re-test that races the poll interval describes the build we were trying to replace."""
    momus = Signer(str(tmp_path / "m"))
    conductor, calls = _live_conductor(tmp_path, monkeypatch, momus)
    order_seen: list[str] = []

    async def agent():
        b = await _claim_one(conductor, "svc", "build")
        conductor.orders.report(b.order_id, BUILD_OK)
        d = await _claim_one(conductor, "svc", "deploy")
        # At the moment the agent picks the DEPLOY order up, the conductor must have asked for the
        # pre-promotion (candidate) verdict and NOT yet for the post-deploy one. Before the fix,
        # "post" was already in `calls` here — it had re-tested the container it was replacing.
        order_seen.extend(calls)
        conductor.orders.report(d.order_id, {"deployed": True, "health": "running",
                                             "deployed_image": BUILT_DIGEST})

    ticket = _signed_ticket(str(tmp_path / "m"), "mom-77")
    job, _ = await asyncio.gather(conductor.handle_ticket(ticket), agent())
    assert order_seen == ["gate"], f"post-deploy retest ran before the deploy: {order_seen}"
    assert calls == ["gate", "post"]
    assert job.state == JobState.DONE.value


@pytest.mark.asyncio
async def test_unclaimed_build_order_escalates_instead_of_blaming_the_patch(tmp_path, monkeypatch):
    """No agent picked the BUILD up. That is a host/enrolment problem; re-patching cannot address it,
    and the loop must not spend its attempts pretending otherwise — nor ask MOMUS to gate a candidate
    that was never built."""
    momus = Signer(str(tmp_path / "m"))
    conductor, calls = _live_conductor(tmp_path, monkeypatch, momus)
    job = await conductor.handle_ticket(_signed_ticket(str(tmp_path / "m"), "mom-78"))
    assert job.state == JobState.ESCALATED.value
    assert "never claimed the build order" in job.history[-1]["note"]
    assert calls == [], "nothing should be gated when nothing was built"
    assert job.attempts == 1, "an absent agent must not burn the attempt budget"


@pytest.mark.asyncio
async def test_unclaimed_deploy_order_escalates(tmp_path, monkeypatch):
    """The agent built the image and then went away before the deploy. Still not the patch's fault."""
    momus = Signer(str(tmp_path / "m"))
    conductor, calls = _live_conductor(tmp_path, monkeypatch, momus)

    async def agent_builds_only():
        b = await _claim_one(conductor, "svc", "build")
        conductor.orders.report(b.order_id, BUILD_OK)

    job, _ = await asyncio.gather(
        conductor.handle_ticket(_signed_ticket(str(tmp_path / "m"), "mom-78b")),
        agent_builds_only())
    assert job.state == JobState.ESCALATED.value
    assert FLAG_AGENT_NEVER_CLAIMED in job.flags
    assert calls == ["gate"], "the candidate was gated, but nothing was deployed to re-verify"


@pytest.mark.asyncio
async def test_agent_refusal_escalates(tmp_path, monkeypatch):
    momus = Signer(str(tmp_path / "m"))
    conductor, _ = _live_conductor(tmp_path, monkeypatch, momus)
    ticket = _signed_ticket(str(tmp_path / "m"), "mom-79")
    job, _ = await asyncio.gather(
        conductor.handle_ticket(ticket),
        _act_as_agent(conductor, "svc",
                      {"refused": True, "deployed": False,
                       "reason": "service 'svc' not on this agent's deploy allowlist"}))
    assert job.state == JobState.ESCALATED.value and FLAG_AGENT_REFUSED in job.flags


@pytest.mark.asyncio
async def test_self_rolled_back_deploy_escalates_and_is_counted(tmp_path, monkeypatch):
    momus = Signer(str(tmp_path / "m"))
    conductor, _ = _live_conductor(tmp_path, monkeypatch, momus)
    ticket = _signed_ticket(str(tmp_path / "m"), "mom-80")
    job, _ = await asyncio.gather(
        conductor.handle_ticket(ticket),
        _act_as_agent(conductor, "svc",
                      {"deployed": False, "health_gate_failed": True,
                       "health": "container already restarted 3x since deploy (crash loop)",
                       "rollback": {"rolled_back": True, "restored_image": "sha256:OLDDIGEST",
                                    "needs_human": False}}))
    assert job.state == JobState.ESCALATED.value
    assert FLAG_HEALTH_GATE_FAILED in job.flags and FLAG_ROLLED_BACK in job.flags
    assert FLAG_ROLLBACK_FAILED not in job.flags


@pytest.mark.asyncio
async def test_failed_self_rollback_is_flagged_as_needing_a_human(tmp_path, monkeypatch):
    momus = Signer(str(tmp_path / "m"))
    conductor, _ = _live_conductor(tmp_path, monkeypatch, momus)
    ticket = _signed_ticket(str(tmp_path / "m"), "mom-81")
    job, _ = await asyncio.gather(
        conductor.handle_ticket(ticket),
        _act_as_agent(conductor, "svc",
                      {"deployed": False, "health_gate_failed": True, "health": "exited",
                       "rollback": {"rolled_back": False, "reason": "image pruned"}}))
    assert job.state == JobState.ESCALATED.value
    assert FLAG_ROLLBACK_FAILED in job.flags
    assert "needs a human NOW" in job.history[-1]["note"]


@pytest.mark.asyncio
async def test_live_regression_triggers_a_conductor_rollback(tmp_path, monkeypatch):
    """Gate said fixed, container is healthy, the finding still reproduces live. Undo it — and do
    NOT re-attempt: the same gate that was just wrong would judge the next patch."""
    momus = Signer(str(tmp_path / "m"))
    conductor, calls = _live_conductor(tmp_path, monkeypatch, momus, post_fixed=False)

    async def agent():
        deploy = await _act_as_agent(conductor, "svc",
                                     {"deployed": True, "health": "running",
                                      "deployed_image": BUILT_DIGEST})
        # Now the rollback order should appear, and it must jump the queue.
        claimed = await _claim_one(conductor, "svc", "rollback")
        assert claimed.order["rollback_of"] == deploy.order_id
        assert "image" not in claimed.order
        conductor.orders.report(claimed.order_id,
                                {"rolled_back": True, "restored_image": "sha256:OLD",
                                 "needs_human": False})

    ticket = _signed_ticket(str(tmp_path / "m"), "mom-82")
    job, _ = await asyncio.gather(conductor.handle_ticket(ticket), agent())
    assert job.state == JobState.ESCALATED.value
    assert FLAG_LIVE_REGRESSION in job.flags and FLAG_ROLLED_BACK in job.flags
    assert job.result["rollback_result"]["rolled_back"] is True
    assert calls == ["gate", "post"], "it must not loop back for another patch"


@pytest.mark.asyncio
async def test_rollback_jumps_the_queue_ahead_of_pending_deploys(tmp_path, monkeypatch):
    """A pending undo means a host is serving something we already decided is wrong. It must not
    wait behind unclaimed forward orders."""
    cfg = RemediationConfig(data_dir=str(tmp_path / "rem"),
                            conductor_key_path=str(tmp_path / "rem" / "cond.key"), dry_run=False)
    conductor = Conductor(cfg)
    momus = Signer(str(tmp_path / "m"))
    stale = DeployOrder(finding_id="mom-a", service="svc", host="svc",
                        momus_verdict=_verdict(momus, "mom-a"))
    sign_deploy_order(stale, conductor._signer)
    conductor.orders.publish(host="svc", service="svc", finding_id="mom-a", order=stale.to_dict())
    undo = RollbackOrder(finding_id="mom-b", service="svc", host="svc", rollback_of=stale.order_id)
    sign_rollback_order(undo, conductor._signer)
    conductor.orders.publish(host="svc", service="svc", finding_id="mom-b", order=undo.to_dict())

    first = conductor.orders.claim_for("svc", agent_id="svc")
    assert first.kind == "rollback", "the undo waited behind an unclaimed deploy"


@pytest.mark.asyncio
async def test_dry_run_no_longer_claims_a_live_verification(tmp_path, monkeypatch):
    """In dry-run nothing is applied, so there is nothing to verify in place. The old code ran the
    post-deploy retest anyway and closed the job as 'verified in place' — the exact overstatement
    that made the loop look further along than it was."""
    cfg = RemediationConfig(data_dir=str(tmp_path / "rem"),
                            conductor_key_path=str(tmp_path / "rem" / "cond.key"), dry_run=True)
    conductor = Conductor(cfg)
    momus = Signer(str(tmp_path / "m"))
    calls: list[str] = []

    async def retest(finding_id, **_):
        calls.append("retest")
        return _verdict(momus, finding_id=finding_id, fixed=True)
    monkeypatch.setattr(conductor.momus, "retest", retest)

    job = await conductor.handle_ticket({"finding_id": "mom-83", "component": "svc",
                                         "target": "svc", "probe": "p", "severity": "low"})
    assert job.state == JobState.DONE.value
    assert calls == ["retest"], "dry-run must not pretend to verify a live container"
    assert "nothing was deployed" in job.history[-1]["note"]


@pytest.mark.asyncio
async def test_live_conductor_with_no_factory_url_fails_closed(tmp_path):
    """Outside dry-run an unconfigured Factory used to fall back to SYNTHESIS: a made-up patch, a
    real signed order, and a container recreated from the same image — a fix that fixed nothing."""
    cfg = RemediationConfig(data_dir=str(tmp_path / "rem"),
                            conductor_key_path=str(tmp_path / "rem" / "cond.key"),
                            dry_run=False, factory_url="",
                            momus_pubkey=Signer(str(tmp_path / "m")).public_key_b64)
    conductor = Conductor(cfg)
    job = await conductor.handle_ticket(_signed_ticket(str(tmp_path / "m"), "mom-84"))
    assert job.state == JobState.ESCALATED.value
    assert "SKOPOS_FACTORY_URL is unset" in job.history[-1]["note"]
    assert conductor.orders.stats()["total"] == 0, "nothing should have been signed"


@pytest.mark.asyncio
async def test_a_dry_run_completion_does_not_block_the_first_live_ticket(tmp_path, monkeypatch):
    """Found the hard way: the FIRST live ticket after dry-run was switched off was swallowed.

    The conductor accepted the A2A task, found a job already in DONE — reached in dry-run, where
    nothing was deployed and nothing verified — and returned it without a single outbound call. The
    duplicate-ticket guard is right in general; it just could not tell a completion that shipped
    something from one that only proved the plumbing."""
    from skopos.remediation.health import FLAG_DRY_RUN

    momus = Signer(str(tmp_path / "m"))
    ticket = _signed_ticket(str(tmp_path / "m"), "mom-90")

    # 1. A dry-run conductor closes the job as DONE, flagged.
    dry_cfg = RemediationConfig(data_dir=str(tmp_path / "rem"),
                                conductor_key_path=str(tmp_path / "rem" / "cond.key"),
                                dry_run=True, momus_pubkey=momus.public_key_b64)
    dry = Conductor(dry_cfg)

    async def fixed(finding_id, **_):
        return _verdict(momus, finding_id=finding_id, fixed=True)
    monkeypatch.setattr(dry.momus, "retest", fixed)

    job = await dry.handle_ticket(ticket)
    assert job.state == JobState.DONE.value and FLAG_DRY_RUN in job.flags
    assert "nothing was deployed" in job.history[-1]["note"]

    # 2. A duplicate ticket to a still-dry conductor is correctly ignored.
    again = await dry.handle_ticket(ticket)
    assert again.history[-1]["note"] == job.history[-1]["note"], "dry-run duplicate should no-op"

    # 3. The same job, same store, now a LIVE conductor: it must re-open and do the work.
    live, calls = _live_conductor(tmp_path, monkeypatch, momus)
    live.store._load()                       # same jobs.jsonl on disk

    # The dry run also PUBLISHED a deploy order, and it is still pending in the shared queue. In
    # production the 900s TTL expires those; here it is fresh, so drain it — and check on the way out
    # that a live agent would have REFUSED it anyway, because it carries an image with a verdict that
    # never examined a candidate. That is the pre-promotion check earning its keep.
    stale = live.orders.claim_for("svc", agent_id="svc")
    if stale is not None:
        from skopos.remediation.deploy_order import verify_deploy_chain
        ok, why = verify_deploy_chain(stale.order, conductor_pubkey=live.conductor_pubkey,
                                      momus_pubkey=momus.public_key_b64, service_allowlist=["svc"])
        assert not ok and "never looked at" in why, why
        live.orders.report(stale.order_id, {"refused": True, "reason": why})

    reopened, _ = await asyncio.gather(
        live.handle_ticket(ticket),
        _act_as_agent(live, "svc", {"deployed": True, "health": "running",
                                    "deployed_image": BUILT_DIGEST}))
    assert FLAG_DRY_RUN not in reopened.flags, "the stale dry-run flag must be cleared"
    assert any("never deployed anything" in h["note"] for h in reopened.history)
    assert calls == ["gate", "post"], "the live run must actually call the gate and verify in place"
    assert reopened.state == JobState.DONE.value


@pytest.mark.asyncio
async def test_a_real_completion_is_still_not_redone(tmp_path, monkeypatch):
    """The other half: a DONE that genuinely shipped must stay closed, or a duplicate ticket
    redeploys a service for no reason."""
    momus = Signer(str(tmp_path / "m"))
    conductor, calls = _live_conductor(tmp_path, monkeypatch, momus)
    ticket = _signed_ticket(str(tmp_path / "m"), "mom-91")
    first, _ = await asyncio.gather(
        conductor.handle_ticket(ticket),
        _act_as_agent(conductor, "svc", {"deployed": True, "health": "running",
                                         "deployed_image": BUILT_DIGEST}))
    assert first.state == JobState.DONE.value
    before = len(calls)
    again = await conductor.handle_ticket(ticket)
    assert again.state == JobState.DONE.value
    assert len(calls) == before, "a real completion must not be redone by a duplicate ticket"


@pytest.mark.asyncio
async def test_a_done_job_from_before_flags_existed_still_reopens(tmp_path, monkeypatch):
    """The second miss on the same bug. Keying the re-open on FLAG_DRY_RUN helped only jobs closed by
    the NEW build; the one job that had actually swallowed a live ticket was closed by an older one
    that never set that flag, so it stayed stuck. The test has to be structural: did this job ever
    deploy anything? `FLAG_DEPLOYED` is set only when an agent reports a real deploy."""
    from skopos.remediation.health import FLAG_DEPLOYED
    from skopos.remediation.jobs import Job, JobStore

    momus = Signer(str(tmp_path / "m"))
    store = JobStore(str(tmp_path / "rem" / "jobs.jsonl"))
    stale = Job(finding_id="mom-92", component="svc", probe="p", severity="high", route="auto")
    stale.transition(JobState.DONE, "dry run: chain complete; nothing was deployed")
    stale.flags = ["reopened"]                 # exactly what the real stuck job carried: no flags
    store.upsert(stale)

    live, calls = _live_conductor(tmp_path, monkeypatch, momus)
    live.store._load()
    ticket = _signed_ticket(str(tmp_path / "m"), "mom-92")
    job, _ = await asyncio.gather(
        live.handle_ticket(ticket),
        _act_as_agent(live, "svc", {"deployed": True, "health": "running",
                                    "deployed_image": BUILT_DIGEST}))
    assert any("never deployed anything" in h["note"] for h in job.history), job.history[-3:]
    assert calls == ["gate", "post"], "the live run must actually do the work"
    assert FLAG_DEPLOYED in job.flags and job.state == JobState.DONE.value


@pytest.mark.asyncio
async def test_a_job_that_really_deployed_is_not_reopened(tmp_path, monkeypatch):
    """The guard still has to hold for real completions, or a duplicate ticket redeploys for nothing."""
    from skopos.remediation.health import FLAG_DEPLOYED
    from skopos.remediation.jobs import Job, JobStore

    momus = Signer(str(tmp_path / "m"))
    store = JobStore(str(tmp_path / "rem" / "jobs.jsonl"))
    shipped = Job(finding_id="mom-93", component="svc", probe="p", severity="high", route="auto")
    shipped.transition(JobState.DONE, "fixed, deployed and verified in place")
    shipped.flags = [FLAG_DEPLOYED]
    store.upsert(shipped)

    live, calls = _live_conductor(tmp_path, monkeypatch, momus)
    live.store._load()
    job = await live.handle_ticket(_signed_ticket(str(tmp_path / "m"), "mom-93"))
    assert job.state == JobState.DONE.value
    assert calls == [], "a completion that really shipped must not be redone"


@pytest.mark.asyncio
async def test_the_push_and_build_record_survives_to_the_end_of_the_job(tmp_path, monkeypatch):
    """Found by checking the FIRST successful real heal instead of trusting it.

    The patch was correct, the branch was correct, the deploy was correct — and the signed provenance
    sidecar never landed, because `_run` assigned `job.result = {...}` wholesale after the build and
    wiped `fix_branch` / `fix_commit` / the build record. `_record_provenance` then found no branch
    and skipped silently. One `=` that should have been an update cost the entire audit artifact."""
    momus = Signer(str(tmp_path / "m"))
    conductor, _ = _live_conductor(tmp_path, monkeypatch, momus)
    recorded: list[dict] = []
    monkeypatch.setattr(conductor.git, "push_provenance",
                        lambda **kw: recorded.append(kw) or __import__(
                            "skopos.remediation.git_push", fromlist=["PushResult"]
                        ).PushResult(True))

    job, _ = await asyncio.gather(
        conductor.handle_ticket(_signed_ticket(str(tmp_path / "m"), "mom-94")),
        _act_as_agent(conductor, "svc", {"deployed": True, "health": "running",
                                         "deployed_image": BUILT_DIGEST}))
    assert job.state == JobState.DONE.value
    r = job.result
    for key in ("fix_branch", "fix_commit", "build_order_id", "build",
                "gate_verdict", "deploy_order_id", "agent_result"):
        assert r.get(key), f"job.result lost {key!r} — the audit trail is incomplete"

    # And the provenance push actually happened, with a record that names the chain.
    assert recorded, "no provenance was pushed"
    rec = recorded[0]["record"]
    assert rec["finding_id"] == "mom-94" and rec["component"] == "svc"
    assert rec["gate_verdict"]["fixed"] is True and rec["conductor_pubkey"]
    assert rec["history"], "the record must carry the job timeline"


def test_hub_is_on_the_rollback_path_once_allowlisted(tmp_path):
    """Same undo as canary: health-gate a crash loop and restore the recorded digest.
    Allowlisting hub must not invent a second rollback mechanism."""
    cond, momus = Signer(str(tmp_path / "c")), Signer(str(tmp_path / "m"))
    docker = FakeDocker(restarts=3, compose_ref="modelmarket-hub:latest")
    ex = NodeDeployExecutor(
        conductor_pubkey=cond.public_key_b64, momus_pubkey=momus.public_key_b64,
        service_allowlist=["hub"], compose_file="dc.yml", dry_run=False,
        state=AgentStateStore(str(tmp_path / "agent" / "deploys.jsonl")),
        runner=docker, sleeper=lambda _s: None,
        build_map={"hub": {"image_ref": "modelmarket-hub:latest", "compose_service": "hub"}},
    )
    out = ex.execute(_deploy_order(cond, momus, service="hub").to_dict())
    assert out["deployed"] is False and out["health_gate_failed"]
    assert out["rolled_back"] and "crash loop" in out["reason"]
    assert docker.tags == [("sha256:OLD", "modelmarket-hub:latest")]


@pytest.mark.asyncio
async def test_a_refused_attempt_tells_the_next_one_why(tmp_path, monkeypatch):
    """The retry ladder is only a ladder if each rung knows what the last one hit.

    Live: three attempts returned the identical rejected patch in eight seconds, each refused
    for the same reason, and the job escalated having learned nothing it was already told.
    """
    momus = Signer(str(tmp_path / "m"))
    conductor, _ = _live_conductor(tmp_path, monkeypatch, momus, max_attempts=3)
    seen: list[str] = []
    refusals = iter([
        {"ok": False, "error": "the patch adds 'cryptography' — the image does not have it"},
        {"ok": False, "error": "the patch adds 'cryptography' — the image does not have it"},
        {"ok": False, "error": "still adding it"},
    ])

    async def fix(ticket, previous_failure="", attempt=1):
        seen.append(previous_failure)
        return next(refusals)

    monkeypatch.setattr(conductor.factory, "request_fix", fix)
    await conductor.handle_ticket(_signed_ticket(str(tmp_path / "m"), "mom-99"))

    assert seen[0] == "", "the first attempt has nothing to learn from"
    assert "cryptography" in seen[1], "the second attempt must be told why the first was refused"
    assert "cryptography" in seen[2]


@pytest.mark.asyncio
async def test_a_candidate_that_is_still_waking_up_is_asked_again(tmp_path, monkeypatch):
    """RUNNING is not LISTENING. The agent reports the build the moment the container is up.

    Live: the gate asked a service 21 seconds into its own startup, got "target unreachable",
    and escalated a job whose patch had never been examined — the container answered 200 a
    minute later.
    """
    momus = Signer(str(tmp_path / "m"))
    conductor, _ = _live_conductor(tmp_path, monkeypatch, momus)
    conductor.gate_retry_delay_s = 0.01
    calls = {"n": 0}

    async def retest(finding_id, *, candidate=False, **_):
        calls["n"] += 1
        if candidate and calls["n"] <= 2:
            return {"outcome": "inconclusive", "detail": "target unreachable — cannot gate the deploy"}
        return _verdict(momus, finding_id=finding_id, fixed=True)

    monkeypatch.setattr(conductor.momus, "retest", retest)

    async def agent():
        b = await _claim_one(conductor, "svc", "build")
        conductor.orders.report(b.order_id, BUILD_OK)
        d = await _claim_one(conductor, "svc", "deploy")
        conductor.orders.report(d.order_id, {"deployed": True, "health": "running",
                                             "deployed_image": BUILT_DIGEST})

    job, _ = await asyncio.gather(
        conductor.handle_ticket(_signed_ticket(str(tmp_path / "m"), "mom-101")), agent())
    assert job.state == JobState.DONE.value, job.history[-1]
    assert calls["n"] >= 3, "the gate must have been re-asked, not escalated on the first miss"


@pytest.mark.asyncio
async def test_a_gate_that_refuses_is_not_re_asked(tmp_path, monkeypatch):
    """Only 'unreachable' is worth asking again — a refusal will refuse identically."""
    momus = Signer(str(tmp_path / "m"))
    conductor, _ = _live_conductor(tmp_path, monkeypatch, momus)
    conductor.gate_retry_delay_s = 0.01
    calls = {"n": 0}

    async def retest(finding_id, *, candidate=False, **_):
        calls["n"] += 1
        return {"outcome": "inconclusive", "detail": "operator token refused"}

    monkeypatch.setattr(conductor.momus, "retest", retest)

    async def agent():
        b = await _claim_one(conductor, "svc", "build")
        conductor.orders.report(b.order_id, BUILD_OK)

    job, _ = await asyncio.gather(
        conductor.handle_ticket(_signed_ticket(str(tmp_path / "m"), "mom-102")), agent())
    assert job.state == JobState.ESCALATED.value
    assert calls["n"] == 1, "a refusing gate must not be hammered"


@pytest.mark.asyncio
async def test_a_target_that_is_really_gone_still_escalates(tmp_path, monkeypatch):
    momus = Signer(str(tmp_path / "m"))
    conductor, _ = _live_conductor(tmp_path, monkeypatch, momus)
    conductor.gate_retries = 3
    conductor.gate_retry_delay_s = 0.01

    async def retest(finding_id, *, candidate=False, **_):
        return {"outcome": "inconclusive", "detail": "target unreachable — cannot gate the deploy"}

    monkeypatch.setattr(conductor.momus, "retest", retest)

    async def agent():
        b = await _claim_one(conductor, "svc", "build")
        conductor.orders.report(b.order_id, BUILD_OK)

    job, _ = await asyncio.gather(
        conductor.handle_ticket(_signed_ticket(str(tmp_path / "m"), "mom-103")), agent())
    assert job.state == JobState.ESCALATED.value
    assert "could not run" in job.history[-1]["note"]


@pytest.mark.asyncio
async def test_a_gate_rejection_reaches_the_next_attempt(tmp_path, monkeypatch):
    """The most informative failure was the one the retry never heard.

    `previous_failure` was set only when the FACTORY refused. A patch that applied, built,
    started and was then rejected by the probe fed nothing forward — so the next attempt got a
    byte-identical prompt and, at temperature 0 through a response cache, a byte-identical
    patch. Measured live: attempt 3 was published three seconds after attempt 2 failed.
    """
    momus = Signer(str(tmp_path / "m"))
    conductor, _ = _live_conductor(tmp_path, monkeypatch, momus, gate_fixed=False, max_attempts=3)
    seen: list[str] = []

    async def fix(ticket, previous_failure="", attempt=1):
        seen.append(previous_failure)
        return {"ok": True, "patch": {"component": ticket.get("component"), "summary": "s",
                                      "diff": "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n"}}

    monkeypatch.setattr(conductor.factory, "request_fix", fix)

    async def agent():
        for _ in range(3):
            b = await _claim_one(conductor, "svc", "build")
            conductor.orders.report(b.order_id, BUILD_OK)

    await asyncio.gather(
        conductor.handle_ticket(_signed_ticket(str(tmp_path / "m"), "mom-104")), agent())

    assert seen[0] == "", "the first attempt has nothing to learn from"
    assert "STILL reproduces" in seen[1], "the gate's rejection must reach attempt 2"
    assert "change your approach" in seen[1]
    assert seen[2], "and attempt 3 too"


@pytest.mark.asyncio
async def test_a_candidate_that_will_not_start_is_a_failed_attempt_not_the_end(tmp_path, monkeypatch):
    """It is a BAD PATCH — the one thing the next attempt exists to fix.

    Measured: a run died at attempt 2 on `ValueError: An Ed25519 private key is 32 bytes long`
    and ended there, so the stronger third rung was never asked at all.
    """
    momus = Signer(str(tmp_path / "m"))
    conductor, _ = _live_conductor(tmp_path, monkeypatch, momus, max_attempts=3)
    seen: list[str] = []
    attempts = {"n": 0}

    async def fix(ticket, previous_failure="", attempt=1):
        seen.append(previous_failure)
        attempts["n"] += 1
        return {"ok": True, "patch": {"component": ticket.get("component"), "summary": "s",
                                      "diff": "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n"}}

    monkeypatch.setattr(conductor.factory, "request_fix", fix)

    async def agent():
        for _ in range(3):
            b = await _claim_one(conductor, "svc", "build")
            conductor.orders.report(b.order_id, {
                "built": True, "image_digest": BUILT_DIGEST, "image_tag": "svc:x",
                "commit_sha": "c" * 40, "candidate_running": False,
                "candidate": "svc-candidate exited",
                "candidate_error": "ValueError: An Ed25519 private key is 32 bytes long"})

    job, _ = await asyncio.gather(
        conductor.handle_ticket(_signed_ticket(str(tmp_path / "m"), "mom-105")), agent())

    assert attempts["n"] == 3, "the ladder must run its full budget, not stop at the first crash"
    assert "did not start" in seen[1]
    assert "Ed25519 private key is 32 bytes" in seen[1], "the container's last words must travel"
    assert job.state == JobState.ESCALATED.value
