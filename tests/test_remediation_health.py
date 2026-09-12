"""Loop health and the circuit breaker — the part that makes "it does not degrade" enforceable.

A dashboard is not a safeguard. These tests pin the properties that make the breaker one: it sits in
the deploy path, it counts the right thing (undos per shipped patch, not failures), it survives the
restart a crash-looping deploy tends to cause, and only a human re-arms it.
"""

from __future__ import annotations

import json
from dataclasses import asdict

import pytest
from fastapi.testclient import TestClient

from oracle_core.signing import Signer

from skopos.remediation.conductor import Conductor, RemediationConfig
from skopos.remediation.health import (
    FLAG_BREAKER_OPEN,
    FLAG_DEPLOYED,
    FLAG_GATE_INCONCLUSIVE,
    FLAG_ROLLED_BACK,
    BreakerThresholds,
    CircuitBreaker,
    LoopHealth,
)
from skopos.remediation.jobs import Job, JobState, JobStore
from skopos.remediation.order_queue import OrderQueue


def _store_with(tmp_path, jobs: list[Job]) -> JobStore:
    store = JobStore(str(tmp_path / "jobs.jsonl"))
    for job in jobs:
        store.upsert(job)
    return store


def _job(finding_id: str, component: str, state: JobState, flags: list[str] | None = None) -> Job:
    job = Job(finding_id=finding_id, component=component, probe="p", severity="high", route="auto")
    job.transition(state, "test")
    job.flags = list(flags or [])
    return job


def _queue_with_deploys(tmp_path, n: int, *, service="svc", reverted=0) -> OrderQueue:
    q = OrderQueue(str(tmp_path / "orders.jsonl"))
    for i in range(n):
        order = {"order_id": f"deploy-{i}", "kind": "deploy", "service": service}
        q.publish(host=service, service=service, finding_id=f"f{i}", order=order)
        q.claim_for(service, agent_id=service)
        result = ({"deployed": False, "health_gate_failed": True} if i < reverted
                  else {"deployed": True})
        q.report(f"deploy-{i}", result)
    return q


# ── what the numbers say ──────────────────────────────────────────────────────
def test_rollback_rate_is_undos_per_shipped_patch(tmp_path):
    """The headline signal. A patch refused by the gate costs nothing; a patch that shipped and had
    to be undone means the gate and reality disagreed."""
    store = _store_with(tmp_path, [
        _job("f1", "svc", JobState.DONE, [FLAG_DEPLOYED]),
        _job("f2", "svc", JobState.ESCALATED, [FLAG_DEPLOYED, FLAG_ROLLED_BACK]),
        # A gate-refused job: it never shipped, so it must NOT drag the rate around.
        _job("f3", "svc", JobState.FAILED, []),
    ])
    health = LoopHealth(store, OrderQueue(str(tmp_path / "orders.jsonl")))
    snap = health.snapshot()
    assert snap["deployed"] == 2 and snap["rolled_back"] == 1
    assert snap["rollback_rate"] == 0.5
    assert snap["win_rate"] == round(1 / 3, 3)


def test_rollback_rate_is_none_rather_than_zero_when_nothing_shipped(tmp_path):
    """An absent rate is not a healthy rate. Reporting 0.0 for "no data" is how a dead signal looks
    exactly like a good one."""
    store = _store_with(tmp_path, [_job("f1", "svc", JobState.FAILED, [])])
    snap = LoopHealth(store, OrderQueue(str(tmp_path / "orders.jsonl"))).snapshot()
    assert snap["rollback_rate"] is None and snap["deployed"] == 0


def test_reverted_deploys_still_count_against_the_daily_cap(tmp_path):
    """A loop that breaks and reverts a service all day touched the host every time. Counting only
    successful deploys let it sit at zero and never hit its own throttle."""
    q = _queue_with_deploys(tmp_path, 3, reverted=2)
    total, per = LoopHealth(_store_with(tmp_path, []), q).deploys_today()
    assert total == 3 and per["svc"] == 3


def test_dry_run_jobs_do_not_count_as_deploys(tmp_path):
    """A DONE job in dry-run deployed nothing; throttling on those would strangle a loop that never
    touched a host."""
    store = _store_with(tmp_path, [_job(f"f{i}", "svc", JobState.DONE, []) for i in range(9)])
    total, _ = LoopHealth(store, OrderQueue(str(tmp_path / "orders.jsonl"))).deploys_today()
    assert total == 0


def test_consecutive_failures_stop_at_the_last_success(tmp_path):
    store = JobStore(str(tmp_path / "jobs.jsonl"))
    for fid, state in [("a", JobState.ESCALATED), ("b", JobState.DONE),
                       ("c", JobState.FAILED), ("d", JobState.FAILED)]:
        store.upsert(_job(fid, "svc", state, []))
    health = LoopHealth(store, OrderQueue(str(tmp_path / "orders.jsonl")))
    # newest first: d, c, b(DONE → stop), a
    assert health.consecutive_failures("svc") == 2
    assert health.consecutive_failures("other") == 0


# ── the breaker ───────────────────────────────────────────────────────────────
def _breaker(tmp_path, store, queue, **kw) -> CircuitBreaker:
    thresholds = BreakerThresholds(**{**{"max_deploys_per_day": 100,
                                         "max_deploys_per_component_per_day": 100,
                                         "max_rollbacks_in_window": 2,
                                         "max_consecutive_component_failures": 3}, **kw})
    return CircuitBreaker(LoopHealth(store, queue), thresholds=thresholds,
                          state_path=str(tmp_path / "breaker.json"))


def test_breaker_trips_on_repeated_rollbacks(tmp_path):
    store = _store_with(tmp_path, [
        _job("f1", "svc", JobState.ESCALATED, [FLAG_DEPLOYED, FLAG_ROLLED_BACK]),
        _job("f2", "svc", JobState.ESCALATED, [FLAG_DEPLOYED, FLAG_ROLLED_BACK]),
    ])
    breaker = _breaker(tmp_path, store, OrderQueue(str(tmp_path / "orders.jsonl")))
    ok, why = breaker.check("svc")
    assert not ok and "2 rollbacks" in why and "not matching reality" in why
    assert breaker.state.tripped


def test_a_tripped_breaker_survives_a_restart(tmp_path):
    """The property that matters: a breaker that reset on restart would be defeated by the very
    crash-loop it exists to interrupt."""
    store = _store_with(tmp_path, [
        _job(f"f{i}", "svc", JobState.ESCALATED, [FLAG_DEPLOYED, FLAG_ROLLED_BACK])
        for i in range(2)])
    queue = OrderQueue(str(tmp_path / "orders.jsonl"))
    first = _breaker(tmp_path, store, queue)
    assert not first.check("svc")[0]

    # A fresh process, an empty job store — the trip must still hold.
    reborn = _breaker(tmp_path, _store_with(tmp_path / "fresh", []), queue)
    ok, why = reborn.check("svc")
    assert not ok and "circuit breaker is OPEN" in why and "operator must clear it" in why


def test_only_an_operator_clears_a_trip(tmp_path):
    store = _store_with(tmp_path, [
        _job(f"f{i}", "svc", JobState.ESCALATED, [FLAG_DEPLOYED, FLAG_ROLLED_BACK])
        for i in range(2)])
    breaker = _breaker(tmp_path, store, OrderQueue(str(tmp_path / "orders.jsonl")))
    breaker.check("svc")
    assert breaker.state.tripped
    breaker.clear(by="operator")
    # The rollbacks are still in the store; clearing is a deliberate override, and the next check
    # re-evaluates and trips again rather than staying quietly closed.
    assert not breaker.state.tripped
    assert not breaker.check("svc")[0]
    assert breaker.state.trips_total == 2


def test_an_unreadable_breaker_file_fails_closed(tmp_path):
    """Deleting or corrupting one file must not be enough to re-arm a quarantined loop."""
    (tmp_path / "breaker.json").write_text("{ this is not json", encoding="utf-8")
    breaker = _breaker(tmp_path, _store_with(tmp_path, []), OrderQueue(str(tmp_path / "o.jsonl")))
    ok, why = breaker.check("svc")
    assert not ok and "unreadable" in why


def test_daily_cap_throttles_without_tripping(tmp_path):
    """A cap is a throttle, not a fault: it must not quarantine the loop, because tomorrow is fine."""
    queue = _queue_with_deploys(tmp_path, 6)
    breaker = _breaker(tmp_path, _store_with(tmp_path, []), queue, max_deploys_per_day=6)
    ok, why = breaker.check("svc")
    assert not ok and "daily deploy cap" in why
    assert breaker.state.tripped is False


def test_per_component_cap_calls_out_thrashing(tmp_path):
    queue = _queue_with_deploys(tmp_path, 2, service="svc")
    breaker = _breaker(tmp_path, _store_with(tmp_path, []), queue,
                       max_deploys_per_component_per_day=2)
    ok, why = breaker.check("svc")
    assert not ok and "thrashing" in why
    # Another component is unaffected — the cap is per service, not a global freeze.
    assert breaker.check("other")[0]


def test_repeated_component_failures_hand_over_to_a_human(tmp_path):
    store = JobStore(str(tmp_path / "jobs.jsonl"))
    for i in range(3):
        store.upsert(_job(f"f{i}", "svc", JobState.FAILED, []))
    breaker = _breaker(tmp_path, store, OrderQueue(str(tmp_path / "o.jsonl")),
                       max_consecutive_component_failures=3)
    ok, why = breaker.check("svc")
    assert not ok and "3 times in a row" in why


def test_master_switch_refuses_without_reading_as_a_fault(tmp_path):
    breaker = CircuitBreaker(LoopHealth(_store_with(tmp_path, []),
                                        OrderQueue(str(tmp_path / "o.jsonl"))),
                             state_path=str(tmp_path / "b.json"), enabled=False)
    ok, why = breaker.check("svc")
    assert not ok and "switched off" in why and not breaker.state.tripped


def test_rate_needs_a_sample_before_it_can_trip(tmp_path):
    """1-of-1 is not a 100% failure rate worth quarantining a loop over."""
    store = _store_with(tmp_path, [_job("f1", "svc", JobState.ESCALATED,
                                        [FLAG_DEPLOYED, FLAG_ROLLED_BACK])])
    breaker = _breaker(tmp_path, store, OrderQueue(str(tmp_path / "o.jsonl")),
                       max_rollbacks_in_window=5, min_sample_for_rate=5)
    assert breaker.check("svc")[0], "one rollback out of one deploy must not trip the breaker"


# ── the breaker is in the DEPLOY PATH, not in a dashboard ─────────────────────
@pytest.mark.asyncio
async def test_conductor_signs_nothing_while_the_breaker_is_open(tmp_path, monkeypatch):
    momus = Signer(str(tmp_path / "m"))
    cfg = RemediationConfig(data_dir=str(tmp_path / "rem"),
                            conductor_key_path=str(tmp_path / "rem" / "cond.key"),
                            dry_run=True, momus_pubkey=momus.public_key_b64)
    conductor = Conductor(cfg)

    async def retest(finding_id, **_):
        v = {"finding_id": finding_id, "target": "svc", "probe": "p", "fixed": True,
             "outcome": "no_finding", "detail": "d", "checked_at": "2026-01-01T00:00:00Z",
             "verifier_pubkey": momus.public_key_b64}
        v["signature"] = momus.sign_payload(
            json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        return v
    monkeypatch.setattr(conductor.momus, "retest", retest)
    conductor.breaker.trip("two rollbacks in the window")

    from momus.findings import Blame, FindingSigner
    blame = FindingSigner(str(tmp_path / "m")).sign_blame(Blame(
        finding_id="mom-90", component="svc", severity="high", hop="probe", summary="s"))
    job = await conductor.handle_ticket({"finding_id": "mom-90", "component": "svc",
                                         "target": "svc", "probe": "p", "severity": "high",
                                         "blame": asdict(blame)})
    assert job.state == JobState.ESCALATED.value
    assert FLAG_BREAKER_OPEN in job.flags
    assert "circuit breaker" in job.history[-1]["note"]
    # The point of checking before signing: no instruction a host could act on was ever produced.
    assert conductor.orders.stats()["total"] == 0


# ── the surfaces an operator and a scraper read ───────────────────────────────
def _client(tmp_path, monkeypatch, **env):
    monkeypatch.setenv("SKOPOS_REMEDIATION_DIR", str(tmp_path / "rem"))
    monkeypatch.setenv("SKOPOS_CONDUCTOR_KEY_PATH", str(tmp_path / "cond.key"))
    monkeypatch.setenv("SKOPOS_REMEDIATION_DRY_RUN", "1")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import importlib

    import skopos.remediation.a2a_ingress as mod
    importlib.reload(mod)
    return TestClient(mod.build_app()), mod


def test_logos_keys_survive_alongside_the_new_ones(tmp_path, monkeypatch):
    """LOGOS has mapped these exact names since it shipped; renaming them here would zero its panel
    again, which is the bug that made this endpoint exist."""
    client, _ = _client(tmp_path, monkeypatch)
    body = client.get("/api/remediation/stats").json()
    for key in ("total", "closed", "confirmed_fixed", "escalated", "orders_signed", "by_state"):
        assert key in body, f"LOGOS reads {key}"
    for key in ("rolled_back", "rollback_rate", "win_rate", "breaker_open", "needs_attention"):
        assert key in body


def test_health_endpoint_reports_the_breaker(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    body = client.get("/remediation/health").json()
    assert body["dry_run"] is True
    assert body["breaker"]["enabled"] is True and body["breaker"]["tripped"] is False
    assert "rollback_rate" in body["health"] and "thresholds" in body["breaker"]


def test_metrics_exposes_the_degradation_signals(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    text = client.get("/metrics").text
    assert "skopos_remediation_breaker_open 0" in text
    assert "skopos_remediation_dry_run 1" in text
    assert "skopos_remediation_rollbacks 0" in text
    # An absent rate is omitted rather than published as 0 — see the health test above.
    assert "skopos_remediation_rollback_rate" not in text


def test_breaker_clear_requires_an_operator_token(tmp_path, monkeypatch):
    client, mod = _client(tmp_path, monkeypatch, SKOPOS_OPERATOR_TOKEN="s3cret")
    conductor = client.app.state.conductor
    conductor.breaker.trip("test trip")

    assert client.post("/remediation/breaker/clear").status_code == 403
    assert client.post("/remediation/breaker/clear",
                       headers={"x-skopos-operator": "wrong"}).status_code == 403
    assert conductor.breaker.state.tripped, "a rejected call must not clear anything"

    ok = client.post("/remediation/breaker/clear", headers={"x-skopos-operator": "s3cret"})
    assert ok.status_code == 200 and ok.json()["cleared"] is True
    assert not conductor.breaker.state.tripped


def test_breaker_clear_is_unavailable_without_operator_auth_configured(tmp_path, monkeypatch):
    """No token configured must not mean "anyone may clear it"."""
    client, _ = _client(tmp_path, monkeypatch, SKOPOS_OPERATOR_TOKEN="")
    client.app.state.conductor.breaker.trip("test trip")
    r = client.post("/remediation/breaker/clear")
    assert r.status_code == 503 and "OPERATOR_TOKEN" in r.json()["detail"]


# ── the introspection routes were written for loopback, and are not on one ────
def test_remediation_state_is_not_readable_without_a_control_token(tmp_path, monkeypatch):
    """These routes assumed `127.0.0.1:9402` meant "only this host". It does not: the publish
    binds the host side, while the CONTAINER port stays reachable across every docker network the
    conductor joins — and on the admin box that network also carries Gitea and its CI runner. A
    job container there read /remediation/jobs and /metrics with a 200."""
    client, _ = _client(tmp_path, monkeypatch, SKOPOS_OPERATOR_TOKEN="s3cret")
    for path in ("/remediation/jobs", "/remediation/jobs/mom-1", "/remediation/health",
                 "/metrics", "/agent/v1/queue", "/a2a/events", "/a2a/stats"):
        assert client.get(path).status_code == 403, f"{path} answered an unauthenticated reader"
        assert client.get(path, headers={"x-skopos-operator": "wrong"}).status_code == 403
        ok = client.get(path, headers={"x-skopos-operator": "s3cret"})
        assert ok.status_code == 200, f"{path} refused the operator"


def test_any_control_token_the_loop_already_holds_is_accepted(tmp_path, monkeypatch):
    """No new secret to distribute: the agent and the A2A peer hold tokens already, and a reader
    that has one of those has more authority than reading grants."""
    client, _ = _client(tmp_path, monkeypatch, SKOPOS_OPERATOR_TOKEN="op",
                        SKOPOS_AGENT_TOKEN="agent", SKOPOS_A2A_TOKEN="peer")
    for header, value in (("x-agent-token", "agent"), ("x-a2a-token", "peer"),
                          ("x-skopos-operator", "op")):
        assert client.get("/remediation/jobs", headers={header: value}).status_code == 200


def test_liveness_and_identity_stay_open(tmp_path, monkeypatch):
    """/health and the agent card are how a peer discovers us; gating them would break federation
    to hide nothing — they carry a public key and a boolean."""
    client, _ = _client(tmp_path, monkeypatch, SKOPOS_OPERATOR_TOKEN="s3cret")
    assert client.get("/health").status_code == 200
    assert client.get("/.well-known/agent-card.json").status_code == 200
    # Counts only, and LOGOS polls it with no header. See the route's docstring.
    assert client.get("/api/remediation/stats").status_code == 200


def test_a_conductor_with_no_tokens_at_all_still_serves_its_own_dashboard(tmp_path, monkeypatch):
    """A box with no control tokens is a dry-run box. Refusing there teaches nobody anything."""
    client, _ = _client(tmp_path, monkeypatch, SKOPOS_OPERATOR_TOKEN="",
                        SKOPOS_AGENT_TOKEN="", SKOPOS_A2A_TOKEN="")
    assert client.get("/remediation/jobs").status_code == 200
