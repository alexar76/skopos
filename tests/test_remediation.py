"""SKOPOS remediation conductor — the full find → fix → verify → deploy loop, with the signed
deploy chain the node agent enforces."""

from __future__ import annotations

import pytest

from oracle_core.signing import Signer

from skopos.remediation.agent_executor import NodeDeployExecutor
from skopos.remediation.clients import MomusClient
from skopos.remediation.conductor import Conductor, RemediationConfig
from skopos.remediation.deploy_order import DeployOrder, sign_deploy_order, verify_deploy_chain
from skopos.remediation.jobs import JobState


def _momus_fixed_verdict(momus: Signer, finding_id="mom-1", fixed=True):
    import json
    v = {"finding_id": finding_id, "target": "oracles", "probe": "free_tier_ceiling_bypass",
         "fixed": fixed, "outcome": "no_finding" if fixed else "finding", "detail": "x",
         "checked_at": "2026-01-01T00:00:00Z", "verifier_pubkey": momus.public_key_b64}
    canon = json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    v["signature"] = momus.sign_payload(canon)
    return v


def test_deploy_chain_accepts_valid(tmp_path):
    conductor = Signer(str(tmp_path / "cond.key"))
    momus = Signer(str(tmp_path / "momus.key"))
    order = DeployOrder(finding_id="mom-1", service="oracle-family", host="h",
                        momus_verdict=_momus_fixed_verdict(momus))
    sign_deploy_order(order, conductor)
    ok, reason = verify_deploy_chain(order.to_dict(), conductor_pubkey=conductor.public_key_b64,
                                     momus_pubkey=momus.public_key_b64,
                                     service_allowlist=["oracle-family"])
    assert ok, reason


def test_deploy_chain_rejects_forged_momus_verdict(tmp_path):
    conductor = Signer(str(tmp_path / "cond.key"))
    momus = Signer(str(tmp_path / "momus.key"))
    attacker = Signer(str(tmp_path / "attacker.key"))
    # verdict signed by an attacker, not MOMUS
    order = DeployOrder(finding_id="mom-1", service="oracle-family", host="h",
                        momus_verdict=_momus_fixed_verdict(attacker))
    sign_deploy_order(order, conductor)
    ok, reason = verify_deploy_chain(order.to_dict(), conductor_pubkey=conductor.public_key_b64,
                                     momus_pubkey=momus.public_key_b64,
                                     service_allowlist=["oracle-family"])
    assert not ok and "verdict signature" in reason


def test_deploy_chain_rejects_not_fixed(tmp_path):
    conductor = Signer(str(tmp_path / "cond.key"))
    momus = Signer(str(tmp_path / "momus.key"))
    order = DeployOrder(finding_id="mom-1", service="oracle-family", host="h",
                        momus_verdict=_momus_fixed_verdict(momus, fixed=False))
    sign_deploy_order(order, conductor)
    ok, reason = verify_deploy_chain(order.to_dict(), conductor_pubkey=conductor.public_key_b64,
                                     momus_pubkey=momus.public_key_b64, service_allowlist=["oracle-family"])
    assert not ok and "not 'fixed'" in reason


def test_deploy_chain_rejects_service_not_allowlisted(tmp_path):
    conductor = Signer(str(tmp_path / "cond.key"))
    momus = Signer(str(tmp_path / "momus.key"))
    order = DeployOrder(finding_id="mom-1", service="hub", host="h",
                        momus_verdict=_momus_fixed_verdict(momus))
    sign_deploy_order(order, conductor)
    ok, reason = verify_deploy_chain(order.to_dict(), conductor_pubkey=conductor.public_key_b64,
                                     momus_pubkey=momus.public_key_b64, service_allowlist=["oracle-family"])
    assert not ok and "allowlist" in reason


def test_agent_executor_dry_run_validates_then_would_run(tmp_path):
    conductor = Signer(str(tmp_path / "cond.key"))
    momus = Signer(str(tmp_path / "momus.key"))
    order = DeployOrder(finding_id="mom-1", service="oracle-family", host="h",
                        momus_verdict=_momus_fixed_verdict(momus))
    sign_deploy_order(order, conductor)
    ex = NodeDeployExecutor(conductor_pubkey=conductor.public_key_b64, momus_pubkey=momus.public_key_b64,
                            service_allowlist=["oracle-family"], compose_file="dc.yml", dry_run=True)
    out = ex.execute(order.to_dict())
    assert out["dry_run"] and "oracle-family" in out["would_run"] and "docker compose" in out["would_run"]


def test_agent_executor_refuses_bad_chain(tmp_path):
    conductor = Signer(str(tmp_path / "cond.key"))
    momus = Signer(str(tmp_path / "momus.key"))
    order = DeployOrder(finding_id="mom-1", service="oracle-family", host="h",
                        momus_verdict=_momus_fixed_verdict(momus, fixed=False))
    sign_deploy_order(order, conductor)
    ex = NodeDeployExecutor(conductor_pubkey=conductor.public_key_b64, momus_pubkey=momus.public_key_b64,
                            service_allowlist=["oracle-family"], dry_run=True)
    out = ex.execute(order.to_dict())
    assert out["refused"] and not out["deployed"]


@pytest.mark.asyncio
async def test_conductor_full_loop_dry_run(tmp_path, monkeypatch):
    cfg = RemediationConfig(data_dir=str(tmp_path / "rem"),
                            conductor_key_path=str(tmp_path / "rem" / "cond.key"),
                            dry_run=True, max_attempts=3)
    conductor = Conductor(cfg)

    # Stub MOMUS retest to report 'fixed' (no live MOMUS in the test).
    momus = Signer(str(tmp_path / "momus.key"))

    async def fake_retest(finding_id):
        return _momus_fixed_verdict(momus, finding_id=finding_id, fixed=True)
    monkeypatch.setattr(conductor.momus, "retest", fake_retest)

    ticket = {"finding_id": "mom-42", "component": "oracle-family", "target": "oracle-family",
              "probe": "free_tier_ceiling_bypass", "severity": "high", "route": "auto"}
    job = await conductor.handle_ticket(ticket)
    assert job.state == JobState.DONE.value
    assert job.result["deploy_order_id"]
    assert job.result["gate_verdict"]["fixed"] is True


@pytest.mark.asyncio
async def test_conductor_escalates_security_core(tmp_path):
    cfg = RemediationConfig(data_dir=str(tmp_path / "rem"),
                            conductor_key_path=str(tmp_path / "rem" / "cond.key"), dry_run=True)
    conductor = Conductor(cfg)
    ticket = {"finding_id": "mom-9", "component": "momus", "probe": "x", "severity": "critical",
              "route": "human-governance"}
    job = await conductor.handle_ticket(ticket)
    assert job.state == JobState.ESCALATED.value


@pytest.mark.asyncio
async def test_conductor_retries_then_escalates_when_never_fixed(tmp_path, monkeypatch):
    cfg = RemediationConfig(data_dir=str(tmp_path / "rem"),
                            conductor_key_path=str(tmp_path / "rem" / "cond.key"), dry_run=True, max_attempts=2)
    conductor = Conductor(cfg)
    momus = Signer(str(tmp_path / "momus.key"))

    async def never_fixed(finding_id):
        return _momus_fixed_verdict(momus, finding_id=finding_id, fixed=False)
    monkeypatch.setattr(conductor.momus, "retest", never_fixed)
    ticket = {"finding_id": "mom-7", "component": "oracle-family", "probe": "p", "severity": "high", "route": "auto"}
    job = await conductor.handle_ticket(ticket)
    assert job.state == JobState.ESCALATED.value
    assert job.attempts == 2


@pytest.mark.asyncio
async def test_momus_client_offline_safe():
    c = MomusClient("")
    v = await c.retest("mom-1")
    assert v["fixed"] is False and "no MOMUS url" in v["detail"]


@pytest.mark.asyncio
async def test_terminal_job_reopens_on_a_new_ticket(tmp_path, monkeypatch):
    """A transient failure must not permanently block a finding from ever being remediated.

    Found by running the real A2A chain: the first delegation exhausted its attempts while the patch
    had not landed yet, the job went ESCALATED, and a later ticket — after the fix shipped — could
    never re-open it. Same "temporary problem, permanent damage" shape as burning a dedup identity
    on an unsettled payout."""
    cfg = RemediationConfig(data_dir=str(tmp_path / "rem"),
                            conductor_key_path=str(tmp_path / "rem" / "cond.key"),
                            dry_run=True, max_attempts=1)
    conductor = Conductor(cfg)
    momus = Signer(str(tmp_path / "momus.key"))
    ticket = {"finding_id": "mom-reopen", "component": "oracle-family", "probe": "p",
              "severity": "high", "route": "auto"}

    # First pass: the fix has not landed, so the gate refuses and the job escalates.
    async def not_fixed(finding_id):
        return _momus_fixed_verdict(momus, finding_id=finding_id, fixed=False)
    monkeypatch.setattr(conductor.momus, "retest", not_fixed)
    first = await conductor.handle_ticket(ticket)
    assert first.state == JobState.ESCALATED.value

    # The patch lands. A new ticket must RE-OPEN the job and drive it to closure.
    async def now_fixed(finding_id):
        return _momus_fixed_verdict(momus, finding_id=finding_id, fixed=True)
    monkeypatch.setattr(conductor.momus, "retest", now_fixed)
    second = await conductor.handle_ticket(ticket)
    assert second.state == JobState.DONE.value, [h["note"] for h in second.history]
    assert any("re-opened" in h["note"] for h in second.history)


@pytest.mark.asyncio
async def test_done_job_is_not_redone_by_a_duplicate_ticket(tmp_path, monkeypatch):
    cfg = RemediationConfig(data_dir=str(tmp_path / "rem"),
                            conductor_key_path=str(tmp_path / "rem" / "cond.key"), dry_run=True)
    conductor = Conductor(cfg)
    momus = Signer(str(tmp_path / "momus.key"))

    async def fixed(finding_id):
        return _momus_fixed_verdict(momus, finding_id=finding_id, fixed=True)
    monkeypatch.setattr(conductor.momus, "retest", fixed)
    ticket = {"finding_id": "mom-once", "component": "oracle-family", "probe": "p",
              "severity": "high", "route": "auto"}
    a = await conductor.handle_ticket(ticket)
    assert a.state == JobState.DONE.value
    attempts_after_first = a.attempts
    b = await conductor.handle_ticket(ticket)          # duplicate ticket
    assert b.state == JobState.DONE.value and b.attempts == attempts_after_first


@pytest.mark.asyncio
async def test_gate_error_body_is_inconclusive_not_a_verdict_on_the_fix(tmp_path):
    """MOMUS answers 200 {"error": ...} when it cannot resolve a finding. Reading that as
    "still vulnerable" blames the patch for a plumbing failure — the same dishonesty as calling an
    unreachable target a pass. Found by running the live chain on production."""
    import httpx
    from fastapi import FastAPI

    app = FastAPI()

    @app.post("/retest")
    async def retest(body: dict):
        return {"error": "unknown_finding", "finding_id": body.get("finding_id")}

    c = MomusClient("http://momus.local", transport=httpx.ASGITransport(app=app))
    v = await c.retest("mom-1")
    assert v["outcome"] == "inconclusive" and v["fixed"] is False
    assert "unknown_finding" in v["detail"] and "corpus" in v["detail"]


@pytest.mark.asyncio
async def test_inconclusive_gate_escalates_immediately_without_burning_attempts(tmp_path, monkeypatch):
    """A gate that cannot run is an operator problem. Retrying the Factory cannot fix it, and the
    escalation must name the real cause instead of blaming the patch."""
    cfg = RemediationConfig(data_dir=str(tmp_path / "rem"),
                            conductor_key_path=str(tmp_path / "rem" / "cond.key"),
                            dry_run=True, max_attempts=3)
    conductor = Conductor(cfg)
    calls = {"n": 0}

    async def gate_cannot_run(finding_id):
        calls["n"] += 1
        return {"finding_id": finding_id, "fixed": False, "outcome": "inconclusive",
                "detail": "MOMUS could not run the gate: unknown_finding", "signature": {}}
    monkeypatch.setattr(conductor.momus, "retest", gate_cannot_run)

    job = await conductor.handle_ticket({"finding_id": "mom-gate", "component": "oracle-family",
                                         "probe": "p", "severity": "high", "route": "auto"})
    assert job.state == JobState.ESCALATED.value
    assert job.attempts == 1 and calls["n"] == 1        # did not retry a gate that cannot run
    assert any("could not run" in h["note"] for h in job.history)
    assert not any("not fixed" in h["note"] for h in job.history)   # never blamed the patch
