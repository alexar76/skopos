"""The pull-based deploy path: a push-only node agent claims a signed order and executes it.

The property under test throughout: authority is SPLIT. The conductor can publish but not execute;
the agent can execute but not invent, widen, or forge. Neither side alone can ship code.
"""

from __future__ import annotations

import pytest
# Module level: this file uses `from __future__ import annotations`, so FastAPI resolves handler
# annotations against module globals — a Request imported inside a function is invisible there.
from fastapi import FastAPI, Request
import httpx

from oracle_core.signing import Signer

from skopos.remediation.node_agent import NodeAgentConfig, NodeAgentDeployHand
from skopos.remediation.order_queue import OrderQueue


def _signed_order(conductor: Signer, momus: Signer, *, service="oracle-family",
                  finding_id="mom-1", fixed=True, order_id="deploy-1", host="h"):
    import json
    from skopos.remediation.deploy_order import DeployOrder, sign_deploy_order
    v = {"finding_id": finding_id, "target": "oracles", "probe": "p", "fixed": fixed,
         "outcome": "no_finding" if fixed else "finding", "detail": "x",
         "checked_at": "2026-01-01T00:00:00Z", "verifier_pubkey": momus.public_key_b64}
    v["signature"] = momus.sign_payload(json.dumps(v, sort_keys=True, separators=(",", ":"),
                                                   ensure_ascii=False))
    o = DeployOrder(finding_id=finding_id, service=service, host=host, momus_verdict=v)
    o.order_id = order_id
    sign_deploy_order(o, conductor)
    return o.to_dict()


def test_from_env_ships_canary_and_hub_live(monkeypatch):
    """Live deploy is the default for the two services with recipes. Park with an empty allowlist."""
    for key in ("SKOPOS_AGENT_SERVICE_ALLOWLIST", "SKOPOS_AGENT_DRY_RUN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SKOPOS_CONDUCTOR_URL", "http://conductor.local")
    monkeypatch.setenv("SKOPOS_AGENT_HOST", "h")
    cfg = NodeAgentConfig.from_env()
    assert cfg.dry_run is False
    assert "canary" in cfg.service_allowlist and "hub" in cfg.service_allowlist
    assert "momus" not in cfg.service_allowlist and "treasury" not in cfg.service_allowlist


def test_from_env_empty_allowlist_parks(monkeypatch):
    monkeypatch.setenv("SKOPOS_AGENT_SERVICE_ALLOWLIST", "")
    monkeypatch.delenv("SKOPOS_AGENT_DRY_RUN", raising=False)
    cfg = NodeAgentConfig.from_env()
    assert cfg.service_allowlist == ()
    assert cfg.dry_run is False


def test_order_is_single_use(tmp_path):
    """A claimed order is never handed out again, so a replayed poll cannot re-run a deploy."""
    q = OrderQueue(str(tmp_path / "orders.jsonl"))
    q.publish(host="h1", service="svc", finding_id="f1", order={"order_id": "o1"})
    assert q.claim_for("h1").order_id == "o1"
    assert q.claim_for("h1") is None


def test_order_is_addressed_to_one_host(tmp_path):
    q = OrderQueue(str(tmp_path / "orders.jsonl"))
    q.publish(host="h1", service="svc", finding_id="f1", order={"order_id": "o1"})
    assert q.claim_for("h2") is None          # a different host must not pick it up
    assert q.claim_for("h1") is not None


def test_expired_order_is_not_served(tmp_path):
    """A stale redeploy instruction must not execute against a host whose state has moved on."""
    q = OrderQueue(str(tmp_path / "orders.jsonl"), ttl_s=0)
    q.publish(host="h1", service="svc", finding_id="f1", order={"order_id": "o1"})
    import time
    time.sleep(0.01)
    assert q.claim_for("h1") is None


def test_result_requires_a_claim(tmp_path):
    q = OrderQueue(str(tmp_path / "orders.jsonl"))
    q.publish(host="h1", service="svc", finding_id="f1", order={"order_id": "o1"})
    assert q.report("o1", {"deployed": True}) is False     # never claimed
    q.claim_for("h1")
    assert q.report("o1", {"deployed": True}) is True
    assert q.get("o1").state == "reported"


def test_queue_survives_restart(tmp_path):
    p = str(tmp_path / "orders.jsonl")
    q = OrderQueue(p)
    q.publish(host="h1", service="svc", finding_id="f1", order={"order_id": "o1"})
    q.claim_for("h1")
    q.report("o1", {"deployed": True})
    again = OrderQueue(p)
    assert again.get("o1").state == "reported" and again.stats()["deployed"] == 1


# ── the agent hand ───────────────────────────────────────────────────────────
def _conductor_app(queue: OrderQueue, reports: list):
    app = FastAPI()

    @app.get("/agent/v1/orders")
    async def orders(host: str, request: Request):
        q = queue.claim_for(host, agent_id=host)
        return {"order": q.order if q else None, "host": host}

    @app.post("/agent/v1/result")
    async def result(body: dict, request: Request):
        reports.append(body)
        queue.report(str(body.get("order_id")), body.get("result") or {})
        return {"recorded": True}

    return app


@pytest.mark.asyncio
async def test_agent_claims_verifies_and_reports(tmp_path):
    conductor, momus = Signer(str(tmp_path / "c.key")), Signer(str(tmp_path / "m.key"))
    queue = OrderQueue(str(tmp_path / "orders.jsonl"))
    reports: list = []
    queue.publish(host="oracle-host", service="oracle-family", finding_id="f1",
                  order=_signed_order(conductor, momus, host="oracle-host"))
    hand = NodeAgentDeployHand(NodeAgentConfig(
        conductor_url="http://conductor.local", host="oracle-host",
        conductor_pubkey=conductor.public_key_b64, momus_pubkey=momus.public_key_b64,
        service_allowlist=("oracle-family",), compose_file="/srv/dc.yml", dry_run=True),
        transport=httpx.ASGITransport(app=_conductor_app(queue, reports)))
    out = await hand.poll_once()
    assert out["polled"] and out["result"]["dry_run"] is True
    assert "oracle-family" in out["result"]["would_run"]
    assert reports and reports[0]["result"]["host"] == "oracle-host"


@pytest.mark.asyncio
async def test_agent_refuses_a_service_outside_its_own_allowlist(tmp_path):
    """The allowlist is LOCAL: even a compromised conductor cannot widen what a host will touch."""
    conductor, momus = Signer(str(tmp_path / "c.key")), Signer(str(tmp_path / "m.key"))
    queue = OrderQueue(str(tmp_path / "orders.jsonl"))
    reports: list = []
    queue.publish(host="oracle-host", service="hub", finding_id="f1",
                  order=_signed_order(conductor, momus, service="hub", host="oracle-host"))
    hand = NodeAgentDeployHand(NodeAgentConfig(
        conductor_url="http://conductor.local", host="oracle-host",
        conductor_pubkey=conductor.public_key_b64, momus_pubkey=momus.public_key_b64,
        service_allowlist=("oracle-family",), dry_run=True),   # 'hub' is NOT allowed here
        transport=httpx.ASGITransport(app=_conductor_app(queue, reports)))
    out = await hand.poll_once()
    assert out["result"]["refused"] is True and "allowlist" in out["result"]["reason"]


@pytest.mark.asyncio
async def test_agent_refuses_a_forged_momus_verdict(tmp_path):
    """A queue compromise cannot fabricate 'fixed': the agent checks it under MOMUS's known key."""
    conductor, momus = Signer(str(tmp_path / "c.key")), Signer(str(tmp_path / "m.key"))
    attacker = Signer(str(tmp_path / "a.key"))
    queue = OrderQueue(str(tmp_path / "orders.jsonl"))
    queue.publish(host="h", service="oracle-family", finding_id="f1",
                  order=_signed_order(conductor, attacker))     # verdict signed by the wrong key
    hand = NodeAgentDeployHand(NodeAgentConfig(
        conductor_url="http://conductor.local", host="h",
        conductor_pubkey=conductor.public_key_b64, momus_pubkey=momus.public_key_b64,
        service_allowlist=("oracle-family",), dry_run=True),
        transport=httpx.ASGITransport(app=_conductor_app(queue, [])))
    out = await hand.poll_once()
    assert out["result"]["refused"] is True and "verdict signature" in out["result"]["reason"]


@pytest.mark.asyncio
async def test_agent_refuses_a_not_fixed_verdict(tmp_path):
    conductor, momus = Signer(str(tmp_path / "c.key")), Signer(str(tmp_path / "m.key"))
    queue = OrderQueue(str(tmp_path / "orders.jsonl"))
    queue.publish(host="h", service="oracle-family", finding_id="f1",
                  order=_signed_order(conductor, momus, fixed=False))
    hand = NodeAgentDeployHand(NodeAgentConfig(
        conductor_url="http://conductor.local", host="h",
        conductor_pubkey=conductor.public_key_b64, momus_pubkey=momus.public_key_b64,
        service_allowlist=("oracle-family",), dry_run=True),
        transport=httpx.ASGITransport(app=_conductor_app(queue, [])))
    out = await hand.poll_once()
    assert out["result"]["refused"] is True and "not 'fixed'" in out["result"]["reason"]


@pytest.mark.asyncio
async def test_unconfigured_agent_does_nothing(tmp_path):
    hand = NodeAgentDeployHand(NodeAgentConfig(conductor_url="", host=""))
    out = await hand.poll_once()
    assert out["polled"] is False and "not configured" in out["reason"]


@pytest.mark.asyncio
async def test_conductor_outage_leaves_the_host_untouched(tmp_path):
    """A conductor outage must fail in the safe direction: no order, no deploy."""
    hand = NodeAgentDeployHand(NodeAgentConfig(
        conductor_url="http://127.0.0.1:1", host="h", dry_run=True))
    out = await hand.poll_once()
    assert out["polled"] is False and "unreachable" in out["reason"]


# ── each service lives in its own compose project ─────────────────────────────


class TestPerServiceComposeFile:
    """One agent, one compose file was enough while the loop only touched the canary.

    The services MOMUS probes are in three different compose projects on the same host — the
    canary in `momus-deploy`, the oracle family in `oracles`, GAIA in `gaia`. With a single
    global file `compose ps` returns nothing for the other two, and the deploy step reads as
    "service not running" rather than "misconfigured", which is the kind of wrong that looks
    like a service being down.
    """

    def _executor(self, build_map, compose_file=""):
        from skopos.remediation.agent_executor import NodeDeployExecutor

        return NodeDeployExecutor(
            conductor_pubkey="", momus_pubkey="", service_allowlist=list(build_map),
            compose_file=compose_file, dry_run=True, state=None, build_map=build_map,
        )

    def test_a_service_uses_its_own_compose_file(self):
        ex = self._executor({"gaia": {"compose_file": "/root/aicom/gaia/docker-compose.yml",
                                      "compose_service": "gaia-backend"}},
                            compose_file="/root/momus-deploy/docker-compose.prod.yml")
        argv = ex._compose("ps", service="gaia")
        assert argv[:4] == ["docker", "compose", "-f", "/root/aicom/gaia/docker-compose.yml"]

    def test_a_service_without_one_falls_back_to_the_agents_file(self):
        ex = self._executor({"canary": {"compose_service": "momus-canary"}},
                            compose_file="/root/momus-deploy/docker-compose.prod.yml")
        argv = ex._compose("ps", service="canary")
        assert argv[3] == "/root/momus-deploy/docker-compose.prod.yml"

    def test_several_files_for_one_service_are_all_passed(self):
        """GAIA is three overlaid compose files on the live host; dropping the overlays would
        resolve a different image than the one actually running."""
        ex = self._executor({"gaia": {"compose_file": "a.yml,b.yml,c.yml"}})
        argv = ex._compose("ps", service="gaia")
        assert argv.count("-f") == 3
        assert [argv[i + 1] for i, a in enumerate(argv) if a == "-f"] == ["a.yml", "b.yml", "c.yml"]

    def test_no_file_anywhere_means_plain_compose(self):
        ex = self._executor({"svc": {}})
        assert ex._compose("ps", service="svc") == ["docker", "compose", "ps"]


class TestTheAllowlistCoversWhatMomusProbesAndNothingElse:
    def test_every_recipe_names_a_dockerfile_that_exists_in_this_repo(self):
        """A recipe is a promise the build step has to keep. The oracle family is probed by
        MOMUS and is NOT here on purpose: on the live host it is built from a separate
        checkout, so an agent that clones this repo cannot produce its image — and the failure
        would arrive mid-remediation as "dockerfile not found", not at configuration time."""
        from pathlib import Path as _Path

        import pytest

        from skopos.remediation.recipes import DEFAULT_BUILD_RECIPES

        # Monorepo: skopos/tests → aicom/. Satellite GitHub checkout has no sibling
        # praxis/gaia/momus trees — recipes still name those Dockerfiles for the live
        # fleet host that clones the full tree.
        here = _Path(__file__).resolve()
        mono_root = here.parents[2]
        if not (mono_root / "praxis").is_dir() and not (mono_root / "momus").is_dir():
            pytest.skip("recipe Dockerfiles live in monorepo siblings, not the skopos satellite")
        root = mono_root
        for service, recipe in DEFAULT_BUILD_RECIPES.items():
            dockerfile = recipe.get("dockerfile")
            assert dockerfile, f"{service} has no dockerfile"
            assert (root / dockerfile).is_file(), f"{service}: {dockerfile} does not exist"

    def test_the_services_it_claims_are_the_ones_it_can_build(self):
        from skopos.remediation.recipes import DEFAULT_BUILD_RECIPES, DEFAULT_SERVICE_ALLOWLIST

        assert set(DEFAULT_SERVICE_ALLOWLIST) == set(DEFAULT_BUILD_RECIPES)
        assert {"canary", "hub", "gaia"} <= set(DEFAULT_BUILD_RECIPES)

    def test_the_auditor_the_payer_and_the_conductor_are_absent(self):
        """An agent that could rebuild the auditor could rebuild the thing that decides whether
        its own deploy was any good. Same exclusions as the Factory's patch scope, one layer up."""
        from skopos.remediation.recipes import DEFAULT_BUILD_RECIPES, DEFAULT_SERVICE_ALLOWLIST

        for forbidden in ("momus", "momus-backend", "treasury", "momus-treasury",
                          "skopos", "skopos-remediation", "remediation-fixer"):
            assert forbidden not in DEFAULT_BUILD_RECIPES
            assert forbidden not in DEFAULT_SERVICE_ALLOWLIST

    def test_no_recipe_builds_from_a_dockerfile_belonging_to_an_excluded_component(self):
        from skopos.remediation.recipes import DEFAULT_BUILD_RECIPES

        for service, recipe in DEFAULT_BUILD_RECIPES.items():
            dockerfile = str(recipe.get("dockerfile") or "")
            assert not dockerfile.startswith(("momus/momus", "treasury/", "skopos/")), \
                f"{service} builds from {dockerfile}, which is an excluded component"


class TestTheHandDoesNotCareWhoItPolls:
    """A hand on another host reaches the fleet relay, not the conductor.

    The path differs — `/agent/` on the relay's vhost was already the AI assistant's — but the
    hand's behaviour must not: the order is signed by the conductor and gated by a MOMUS verdict
    either way, so this is a path, not a mode. Anything that made the hand treat "remote" as a
    different case would be a second code path through the only place a deploy happens.
    """

    def _cfg(self, monkeypatch, **env):
        from skopos.remediation.node_agent import NodeAgentConfig

        for k, v in env.items():
            monkeypatch.setenv(k, v)
        return NodeAgentConfig.from_env()

    def test_it_polls_the_conductor_by_default(self, monkeypatch):
        monkeypatch.delenv("SKOPOS_AGENT_API_PREFIX", raising=False)
        assert self._cfg(monkeypatch).api_prefix == "/agent/v1"

    def test_it_can_be_pointed_at_the_relay(self, monkeypatch):
        assert self._cfg(monkeypatch, SKOPOS_AGENT_API_PREFIX="/fleet/v1").api_prefix == "/fleet/v1"

    @pytest.mark.parametrize("given", ["fleet/v1", "/fleet/v1/", "  /fleet/v1  "])
    def test_the_spelling_is_normalised(self, monkeypatch, given):
        """A trailing slash would produce `//orders`, which some proxies rewrite and others 404."""
        assert self._cfg(monkeypatch, SKOPOS_AGENT_API_PREFIX=given).api_prefix == "/fleet/v1"


class TestTheHandSaysWhenItCannotVerify:
    """Without a signing backend the hand looks perfectly healthy — it polls, it claims, it
    reports — and refuses every order with "no signing backend available": a message that
    describes the symptom and names nothing an operator can act on.

    Measured: the first real autonomous cycle died exactly there, after the model had been paid
    and the image built.
    """

    def test_the_refusal_names_a_cause(self, monkeypatch):
        import skopos.remediation.deploy_order as do

        monkeypatch.setattr(do, "Signer", None)
        ok, reason = do.verify_deploy_chain({"kind": "deploy"}, conductor_pubkey="x",
                                            momus_pubkey="y", service_allowlist=["canary"])
        assert not ok and "signing backend" in reason

    def test_the_startup_banner_reports_the_backend(self):
        """The check has to be in main(), where an operator reads it, not only at refusal time."""
        from pathlib import Path as _Path

        source = (_Path(__file__).resolve().parents[1] / "skopos" / "remediation"
                  / "node_agent.py").read_text()
        assert "NO SIGNING BACKEND" in source
        assert "aimarket-oracle-core" in source, "the banner must name the fix, not just the fault"
