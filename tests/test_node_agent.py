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
                  finding_id="mom-1", fixed=True, order_id="deploy-1"):
    import json
    from skopos.remediation.deploy_order import DeployOrder, sign_deploy_order
    v = {"finding_id": finding_id, "target": "oracles", "probe": "p", "fixed": fixed,
         "outcome": "no_finding" if fixed else "finding", "detail": "x",
         "checked_at": "2026-01-01T00:00:00Z", "verifier_pubkey": momus.public_key_b64}
    v["signature"] = momus.sign_payload(json.dumps(v, sort_keys=True, separators=(",", ":"),
                                                   ensure_ascii=False))
    o = DeployOrder(finding_id=finding_id, service=service, host="h", momus_verdict=v)
    o.order_id = order_id
    sign_deploy_order(o, conductor)
    return o.to_dict()


# ── the queue ────────────────────────────────────────────────────────────────
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
                  order=_signed_order(conductor, momus))
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
                  order=_signed_order(conductor, momus, service="hub"))
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
