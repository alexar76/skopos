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

    async def fake_retest(finding_id, **_):
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
async def test_conductor_rejects_unsafe_finding_id_before_git_work(tmp_path):
    cfg = RemediationConfig(data_dir=str(tmp_path / "rem"),
                            conductor_key_path=str(tmp_path / "rem" / "cond.key"), dry_run=True)
    conductor = Conductor(cfg)
    job = await conductor.handle_ticket({
        "finding_id": "../../outside",
        "component": "oracle-family",
        "probe": "p",
        "severity": "high",
    })
    assert job.state == JobState.ESCALATED.value
    assert any("unsafe path" in h["note"] for h in job.history)


@pytest.mark.asyncio
async def test_conductor_retries_then_escalates_when_never_fixed(tmp_path, monkeypatch):
    cfg = RemediationConfig(data_dir=str(tmp_path / "rem"),
                            conductor_key_path=str(tmp_path / "rem" / "cond.key"), dry_run=True, max_attempts=2)
    conductor = Conductor(cfg)
    momus = Signer(str(tmp_path / "momus.key"))

    async def never_fixed(finding_id, **_):
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
    async def not_fixed(finding_id, **_):
        return _momus_fixed_verdict(momus, finding_id=finding_id, fixed=False)
    monkeypatch.setattr(conductor.momus, "retest", not_fixed)
    first = await conductor.handle_ticket(ticket)
    assert first.state == JobState.ESCALATED.value

    # The patch lands. A new ticket must RE-OPEN the job and drive it to closure.
    async def now_fixed(finding_id, **_):
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

    async def fixed(finding_id, **_):
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

    async def gate_cannot_run(finding_id, **_):
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


# ── 2026-08 audit: A2A ingress hardening ─────────────────────────────────────


def _ingress(tmp_path, monkeypatch, *, a2a_token="", dry_run="1", max_inflight="2"):
    monkeypatch.setenv("SKOPOS_REMEDIATION_DIR", str(tmp_path / "rem"))
    monkeypatch.setenv("SKOPOS_CONDUCTOR_KEY_PATH", str(tmp_path / "cond.key"))
    monkeypatch.setenv("SKOPOS_A2A_TOKEN", a2a_token)
    monkeypatch.setenv("SKOPOS_REMEDIATION_DRY_RUN", dry_run)
    monkeypatch.setenv("SKOPOS_MAX_INFLIGHT_JOBS", max_inflight)
    import importlib

    from skopos.remediation import a2a_ingress as mod

    importlib.reload(mod)
    mod._inflight.clear()
    return mod


def test_a2a_peer_token_is_compared_in_constant_time(tmp_path, monkeypatch):
    """Every other secret comparison in this package uses compare_digest; these two used
    `!=`, which leaks the shared token's prefix through response timing."""
    mod = _ingress(tmp_path, monkeypatch, a2a_token="s3cret", dry_run="0")
    src = __import__("inspect").getsource(mod.build_app)
    assert "compare_digest" in src
    assert "!= a2a_token" not in src and "!= agent_token" not in src


def test_a2a_tasks_bound_the_number_of_in_flight_jobs(tmp_path, monkeypatch):
    """Each accepted ticket spawns a long-running background job. Nothing counted them, so
    a caller could open jobs faster than they finish — and in dry-run
    the peer check deliberately lets an unauthenticated caller in."""
    from fastapi.testclient import TestClient

    mod = _ingress(tmp_path, monkeypatch, a2a_token="", dry_run="1", max_inflight="2")

    started: list[str] = []

    class _Slow:
        """A conductor whose jobs never finish, so the cap is what has to stop them."""

        def __init__(self, real):
            self._real = real
            self.observer = real.observer
            self.orders = real.orders
            self.cfg = real.cfg
            self.conductor_pubkey = real.conductor_pubkey
            self.store = real.store

        async def handle_ticket(self, ticket):
            import asyncio

            started.append(ticket["finding_id"])
            await asyncio.sleep(30)

    real = mod.Conductor(mod.RemediationConfig.from_env())
    app = mod.build_app(_Slow(real))
    with TestClient(app) as client:
        codes = [
            client.post(
                "/a2a/tasks",
                json={"skill": "remediate", "input": {"ticket": {"finding_id": f"m-{i}"}}},
            ).status_code
            for i in range(5)
        ]

    assert codes.count(200) == 2, f"expected the cap to hold at 2 in flight: {codes}"
    assert codes[-1] == 429
    mod._inflight.clear()


def test_conductor_from_env_is_live_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("SKOPOS_REMEDIATION_DRY_RUN", raising=False)
    monkeypatch.setenv("SKOPOS_REMEDIATION_DIR", str(tmp_path / "rem"))
    from skopos.remediation.conductor import RemediationConfig
    assert RemediationConfig.from_env().dry_run is False


class TestTheTimeoutChainHasHeadroom:
    """Measured on the live deployment: the model answers the patch prompt in 79-119 seconds. A
    240s budget was therefore marginal, and marginal means it fails during an incident — which is
    exactly when the first real autonomous dispatch hit it, twice in a row.

    Whatever the budget is, the conductor's client must outlast it: otherwise the client gives up
    first and the job escalates blaming a patch that was still being written.
    """

    def test_the_factory_client_timeout_is_configurable(self, monkeypatch):
        from skopos.remediation.clients import FactoryClient

        monkeypatch.setenv("SKOPOS_FACTORY_TIMEOUT_S", "900")
        assert FactoryClient("http://f.test", dry_run=True)._timeout == 900.0

    def test_it_falls_back_to_a_sane_default(self, monkeypatch):
        from skopos.remediation.clients import FactoryClient

        monkeypatch.delenv("SKOPOS_FACTORY_TIMEOUT_S", raising=False)
        assert FactoryClient("http://f.test", dry_run=True)._timeout == 300.0

    def test_a_malformed_value_does_not_make_it_zero(self, monkeypatch):
        """A zero timeout would abort every request instantly and read as the Factory being down."""
        from skopos.remediation.clients import FactoryClient

        monkeypatch.setenv("SKOPOS_FACTORY_TIMEOUT_S", "not-a-number")
        assert FactoryClient("http://f.test", dry_run=True)._timeout == 300.0

    def test_an_explicit_argument_still_wins(self, monkeypatch):
        from skopos.remediation.clients import FactoryClient

        monkeypatch.setenv("SKOPOS_FACTORY_TIMEOUT_S", "900")
        assert FactoryClient("http://f.test", dry_run=True, timeout_s=42.0)._timeout == 42.0


class TestARegressionReopensAShippedRemediation:
    """A shipped remediation must not be redone by a DUPLICATE ticket — and must be redone by a
    REGRESSION. From the conductor the two look identical unless something dates them.

    Measured: the canary's fix shipped, the canary was later rebuilt from unpatched source, the
    finding came back, and every new ticket was answered with the old DONE job — the loop could
    not re-heal its own regression.
    """

    def _seen_after(self, ticket, when):
        from skopos.remediation.conductor import _seen_after

        return _seen_after(ticket, when)

    def test_a_finding_seen_after_the_job_finished_is_a_regression(self):
        assert self._seen_after({"last_seen_at": "2026-08-29T10:00:00Z"}, "2026-08-27T11:27:23Z")

    def test_a_stale_duplicate_ticket_is_not(self):
        assert not self._seen_after({"last_seen_at": "2026-08-27T09:00:00Z"},
                                    "2026-08-27T11:27:23Z")

    def test_the_same_instant_is_not_a_regression(self):
        assert not self._seen_after({"last_seen_at": "2026-08-27T11:27:23Z"},
                                    "2026-08-27T11:27:23Z")

    def test_an_unknown_age_never_reads_as_a_regression(self):
        """The consequence of guessing wrong here is re-running a paid pipeline against something
        that was already fixed, so absence must fail toward doing nothing."""
        for ticket, when in (
            ({}, "2026-08-27T11:27:23Z"),
            ({"last_seen_at": ""}, "2026-08-27T11:27:23Z"),
            ({"last_seen_at": "2026-08-29T10:00:00Z"}, ""),
            ({"last_seen_at": "yesterday"}, "2026-08-27T11:27:23Z"),
            ({"last_seen_at": "2026-08-29 10:00:00"}, "2026-08-27T11:27:23Z"),
        ):
            assert not self._seen_after(ticket, when), (ticket, when)

    def test_the_ticket_carries_the_field_at_all(self):
        """MOMUS fills it from the corpus row; a ticket without it silently disables the rule."""
        import dataclasses

        import pytest

        from momus.engine.remediation import RemediationTicket

        names = [f.name for f in dataclasses.fields(RemediationTicket)]
        if "last_seen_at" not in names:
            pytest.skip(
                "installed aimarket-momus lacks RemediationTicket.last_seen_at "
                "(publish/bump momus; monorepo already has the field)"
            )
        assert "last_seen_at" in names
