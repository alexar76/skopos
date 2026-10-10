"""The finger on the trigger. Every test here is a way it must NOT fire.

This is the component that gives the loop initiative — the point where the system starts
changing production without being asked. So the tests are written from the refusals inward: what
it will not dispatch, how many times it will not dispatch, and what it does when the evidence is
merely an observation rather than a reproduction.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from skopos.remediation import autopilot as ap  # noqa: E402


@pytest.fixture(autouse=True)
def _enabled(monkeypatch):
    monkeypatch.setenv(ap.ENABLED_ENV, "1")
    monkeypatch.delenv("AUTOPILOT_POLICY", raising=False)


def _finding(**over):
    base = {"finding_id": "mom-1", "target": "canary", "severity": "high", "seen_count": 5,
            "probe": "free_tier_ceiling_bypass", "status": "raw"}
    base.update(over)
    return base


def _pilot(tmp_path, **env):
    import os

    for k, v in env.items():
        os.environ[k] = str(v)
    pilot = ap.Autopilot(momus_url="http://momus.test",
                         operator_token="t",
                         state_path=str(tmp_path / "dispatched.jsonl"))
    return pilot


class TestItIsOffUntilSomebodySaysOtherwise:
    def test_merging_the_file_does_not_give_the_loop_initiative(self, monkeypatch, tmp_path):
        monkeypatch.delenv(ap.ENABLED_ENV, raising=False)
        out = _pilot(tmp_path).tick()
        assert out["enabled"] is False
        assert "dispatched" not in out

    def test_it_does_not_even_scan_while_disabled(self, monkeypatch, tmp_path):
        """A scanner that runs while dispatch is off still costs the fleet probe traffic, and
        would fill the corpus with findings nothing is going to act on."""
        monkeypatch.delenv(ap.ENABLED_ENV, raising=False)
        pilot = _pilot(tmp_path)
        called = []
        monkeypatch.setattr(pilot, "scan", lambda t: called.append(t))
        pilot.tick()
        assert called == []


class TestWhatItRefusesToTouch:
    @pytest.mark.parametrize("component", ["momus", "momus-backend", "treasury",
                                           "momus-treasury", "skopos", "skopos-remediation",
                                           "remediation-fixer", "self"])
    def test_the_auditor_the_payer_and_the_conductor(self, tmp_path, component):
        """Refused here as well as in the Factory's patch gate, because this is the component
        that would otherwise ASK for it."""
        d = _pilot(tmp_path).decide(_finding(target=component), history=[], now=time.time())
        assert not d.dispatch
        assert "auditor" in d.reason or "payer" in d.reason or "conductor" in d.reason

    def test_a_component_with_no_policy_entry(self, tmp_path):
        d = _pilot(tmp_path).decide(_finding(target="oracles"), history=[], now=time.time())
        assert not d.dispatch and "no dispatch policy" in d.reason

    def test_a_severity_below_the_policy(self, tmp_path):
        for severity in ("medium", "low", "info"):
            d = _pilot(tmp_path).decide(_finding(severity=severity), history=[], now=time.time())
            assert not d.dispatch, severity
            assert "below the policy" in d.reason

    def test_a_denied_component_cannot_be_added_by_policy(self, tmp_path, monkeypatch):
        """Omission is a default, and a default is what someone widening a config overrides
        without noticing."""
        monkeypatch.setenv("AUTOPILOT_POLICY", json.dumps({
            "momus": {"severities": ["high"], "min_sightings": 1},
            "canary": {"severities": ["high"], "min_sightings": 1},
        }))
        assert "momus" not in ap.policy()
        assert "canary" in ap.policy()


class TestEvidence:
    def test_one_sighting_is_an_observation_not_a_finding(self, tmp_path):
        d = _pilot(tmp_path).decide(_finding(seen_count=1), history=[], now=time.time())
        assert not d.dispatch and "needs 2" in d.reason

    def test_reproduction_across_scans_is_the_evidence(self, tmp_path):
        d = _pilot(tmp_path).decide(_finding(seen_count=2), history=[], now=time.time())
        assert d.dispatch and "reproduced 2x" in d.reason

    def test_the_hub_waits_longer_than_the_canary(self, tmp_path):
        """The canary exists to be broken and fixed; the hub is a revenue path."""
        now = time.time()
        pilot = _pilot(tmp_path)
        assert not pilot.decide(_finding(target="hub", seen_count=2), history=[], now=now).dispatch
        assert pilot.decide(_finding(target="hub", seen_count=3), history=[], now=now).dispatch

    def test_an_independent_verdict_lowers_the_sighting_bar_but_does_not_remove_it(self, tmp_path):
        """Changed deliberately, and worth saying why.

        This branch asserted that a verdict short-circuits the count entirely — a hub finding
        seen ONCE would dispatch. It was never exercised: nothing in production wrote a
        verdict, so the branch was dead the whole time it was asserted.

        Now that MOMUS has an independent verifier, the day a verdict arrives is the day that
        assertion becomes real, and it would let a single model answer overrule the hub's
        three-sighting conservatism on a revenue path — a loosening that would have arrived as
        a side effect of fixing something else, chosen by nobody.

        A verdict is a second opinion. One opinion plus one sighting is two independent
        reasons to believe the finding, which is what the default asks for. So the floor is
        two, and it is a floor, not a bypass.
        """
        verdict = {"verdict": "confirmed", "verifier_id": "metis",
                   "score": 0.9, "verifier_pubkey": "pk-verifier"}
        pilot = _pilot(tmp_path)

        once = pilot.decide(_finding(target="hub", seen_count=1, verdicts=[verdict]),
                            history=[], now=time.time())
        assert not once.dispatch, "one sighting plus one opinion is not enough on the hub"
        assert "needs 2" in once.reason

        twice = pilot.decide(_finding(target="hub", seen_count=2, verdicts=[verdict]),
                             history=[], now=time.time())
        assert twice.dispatch, "the verdict must still buy something — 2 instead of 3"

    def test_a_verdict_the_verifier_is_unsure_of_buys_nothing(self, tmp_path):
        """A low-confidence "confirmed" is more dangerous than an "inconclusive": it reads as
        evidence and is not."""
        unsure = {"verdict": "confirmed", "verifier_id": "metis", "score": 0.4}
        d = _pilot(tmp_path).decide(
            _finding(target="hub", seen_count=2, verdicts=[unsure]),
            history=[], now=time.time())
        assert not d.dispatch

    def test_a_verdict_signed_by_the_scanner_itself_buys_nothing(self, tmp_path):
        """MOMUS refuses to build a verifier whose key is the scanner's. This is the second
        place that cannot be talked out of it — the two run on different hosts."""
        self_signed = {"verdict": "confirmed", "verifier_id": "momus", "score": 0.95,
                       "verifier_pubkey": "pk-scanner"}
        d = _pilot(tmp_path).decide(
            _finding(target="hub", seen_count=2, verdicts=[self_signed],
                     scanner_pubkey="pk-scanner"),
            history=[], now=time.time())
        assert not d.dispatch

    def test_a_refuting_verdict_does_not_count_as_one(self, tmp_path):
        d = _pilot(tmp_path).decide(
            _finding(seen_count=1, verdicts=[{"verdict": "refuted"}]),
            history=[], now=time.time())
        assert not d.dispatch

    def test_the_status_field_is_not_consulted(self, tmp_path):
        """Nothing in production ever writes "confirmed" to it — Status.CONFIRMED appears in the
        momus tree only in tests. A dispatcher gated on it would never fire once."""
        d = _pilot(tmp_path).decide(_finding(status="raw"), history=[], now=time.time())
        assert d.dispatch, "a raw finding with enough sightings must still dispatch"


class TestItDoesNotSpendTwiceForOneBug:
    def test_the_same_finding_is_not_redispatched_while_cooling_down(self, tmp_path):
        now = time.time()
        history = [{"at": now - 3600, "finding_id": "mom-1", "component": "canary",
                    "dispatched": True}]
        d = _pilot(tmp_path).decide(_finding(), history=history, now=now)
        assert not d.dispatch and "cooling down" in d.reason

    def test_after_the_cooldown_it_may_go_again(self, tmp_path):
        now = time.time()
        history = [{"at": now - 7 * 3600, "finding_id": "mom-1", "component": "canary",
                    "dispatched": True}]
        assert _pilot(tmp_path).decide(_finding(), history=history, now=now).dispatch

    def test_a_global_daily_cap(self, tmp_path):
        now = time.time()
        history = [{"at": now - 100, "finding_id": f"other-{i}", "component": "gaia",
                    "dispatched": True} for i in range(4)]
        d = _pilot(tmp_path).decide(_finding(), history=history, now=now)
        assert not d.dispatch and "daily cap reached" in d.reason

    def test_a_per_component_daily_cap(self, tmp_path):
        now = time.time()
        history = [{"at": now - 100, "finding_id": f"c-{i}", "component": "canary",
                    "dispatched": True} for i in range(2)]
        d = _pilot(tmp_path).decide(_finding(), history=history, now=now)
        assert not d.dispatch and "daily cap for canary" in d.reason

    def test_yesterdays_dispatches_do_not_count_against_today(self, tmp_path):
        now = time.time()
        history = [{"at": now - 90000, "finding_id": f"old-{i}", "component": "canary",
                    "dispatched": True} for i in range(9)]
        assert _pilot(tmp_path).decide(_finding(), history=history, now=now).dispatch

    def test_a_refused_dispatch_does_not_consume_the_cap(self, tmp_path):
        """Otherwise a run of MOMUS 403s would silently use up the day's budget."""
        now = time.time()
        history = [{"at": now - 100, "finding_id": f"f-{i}", "component": "canary",
                    "dispatched": False} for i in range(9)]
        assert _pilot(tmp_path).decide(_finding(), history=history, now=now).dispatch


class TestTheCapBindsWithinASinglePass:
    def test_three_eligible_findings_do_not_all_go_out_under_a_cap_of_two(self, tmp_path,
                                                                          monkeypatch):
        """The bug this exists to prevent: reading the journal once at the top of the tick and
        then dispatching everything eligible, because nothing written during the pass is seen."""
        pilot = _pilot(tmp_path)
        monkeypatch.setattr(pilot, "scan", lambda t: {"target": t, "status": 200})
        monkeypatch.setattr(pilot, "findings", lambda limit=50: [
            _finding(finding_id=f"mom-{i}") for i in range(3)])
        sent: list[str] = []
        monkeypatch.setattr(pilot, "dispatch",
                            lambda fid: sent.append(fid) or {"status": 200, "body": {}})
        out = pilot.tick()
        assert len(sent) == 2, f"cap did not bind within the pass: {sent}"
        assert len(out["held"]) == 1


class TestTheJournalIsTheRecord:
    def test_every_decision_that_fired_is_written_down(self, tmp_path, monkeypatch):
        pilot = _pilot(tmp_path)
        monkeypatch.setattr(pilot, "scan", lambda t: {"target": t, "status": 200})
        monkeypatch.setattr(pilot, "findings", lambda limit=50: [_finding()])
        monkeypatch.setattr(pilot, "dispatch", lambda fid: {"status": 200, "body": {}})
        pilot.tick()
        written = [json.loads(line) for line in
                   Path(pilot.state_path).read_text().splitlines() if line.strip()]
        assert written and written[0]["finding_id"] == "mom-1"
        assert written[0]["dispatched"] is True
        assert "reproduced" in written[0]["reason"]

    def test_a_failed_dispatch_is_recorded_as_not_dispatched(self, tmp_path, monkeypatch):
        pilot = _pilot(tmp_path)
        monkeypatch.setattr(pilot, "scan", lambda t: {"target": t, "status": 200})
        monkeypatch.setattr(pilot, "findings", lambda limit=50: [_finding()])
        monkeypatch.setattr(pilot, "dispatch", lambda fid: {"status": 403, "body": {}})
        pilot.tick()
        written = [json.loads(line) for line in
                   Path(pilot.state_path).read_text().splitlines() if line.strip()]
        assert written[0]["dispatched"] is False and written[0]["http"] == 403


class TestATwoHundredIsNotADispatch:
    """MOMUS answers 200 with dispatched=false when a ticket routes to human governance — the
    security core never auto-remediates. Reading the status code alone records that as a success
    and spends one of the day's slots on a ticket nobody picked up."""

    def test_a_human_governance_answer_is_not_counted(self, tmp_path, monkeypatch):
        pilot = _pilot(tmp_path)
        monkeypatch.setattr(pilot, "scan", lambda t: {"target": t, "status": 200})
        monkeypatch.setattr(pilot, "findings", lambda limit=50: [_finding()])
        monkeypatch.setattr(pilot, "dispatch", lambda fid: {
            "status": 200,
            "body": {"dispatched": False,
                     "note": "security-core finding — escalated to human governance"},
        })
        pilot.tick()
        written = [json.loads(line) for line in
                   Path(pilot.state_path).read_text().splitlines() if line.strip()]
        assert written[0]["dispatched"] is False
        assert "human governance" in (written[0]["error"] or "")

    def test_and_it_does_not_consume_the_daily_cap(self, tmp_path, monkeypatch):
        pilot = _pilot(tmp_path)
        monkeypatch.setattr(pilot, "scan", lambda t: {"target": t, "status": 200})
        monkeypatch.setattr(pilot, "findings", lambda limit=50: [
            _finding(finding_id=f"mom-{i}") for i in range(3)])
        seen: list[str] = []
        monkeypatch.setattr(pilot, "dispatch", lambda fid: seen.append(fid) or {
            "status": 200, "body": {"dispatched": False, "note": "escalated"}})
        pilot.tick()
        # All three were offered, because none of them counted against the cap of two.
        assert len(seen) == 3

    def test_a_real_dispatch_still_counts(self, tmp_path, monkeypatch):
        pilot = _pilot(tmp_path)
        monkeypatch.setattr(pilot, "scan", lambda t: {"target": t, "status": 200})
        monkeypatch.setattr(pilot, "findings", lambda limit=50: [_finding()])
        monkeypatch.setattr(pilot, "dispatch", lambda fid: {
            "status": 200, "body": {"ticket": {}, "a2a_task": {}, "delivery": {"state": "working"}}})
        pilot.tick()
        written = [json.loads(line) for line in
                   Path(pilot.state_path).read_text().splitlines() if line.strip()]
        assert written[0]["dispatched"] is True


# ── the refund: a ticket nobody acted on cost nothing ────────────────────────────
# Found on the live deployment: the autopilot dispatched a real regression, the conductor
# absorbed it as a duplicate of a finished remediation and started nothing, and the day's
# budget was spent anyway. The next real dispatch was then refused by a cap that had been
# consumed by a ticket which produced no patch, no build and no deploy.


def _reconciling_pilot(tmp_path, monkeypatch, *, moved):
    """moved: finding_id -> True (work started) / False (nothing) / None (cannot tell)."""
    pilot = ap.Autopilot(state_path=str(tmp_path / "dispatched.jsonl"))
    monkeypatch.setattr(
        ap.Autopilot, "_job_moved_after",
        lambda self, fid, at: moved.get(fid) if isinstance(moved, dict) else moved,
    )
    return pilot


def test_an_absorbed_dispatch_is_refunded_and_stops_counting(tmp_path, monkeypatch):
    pilot = _reconciling_pilot(tmp_path, monkeypatch, moved={"mom-1": False})
    now = time.time()
    history = [{"at": now - 3600, "finding_id": "mom-1", "component": "canary",
                "severity": "high", "dispatched": True}]
    reconciled = pilot.reconcile(history, now=now)
    assert any(h.get("refund_of") for h in reconciled)
    # The cap and the cooldown must both stop seeing it.
    assert ap.Autopilot.effective(reconciled) == []


def test_a_dispatch_that_started_work_is_never_refunded(tmp_path, monkeypatch):
    pilot = _reconciling_pilot(tmp_path, monkeypatch, moved={"mom-1": True})
    now = time.time()
    history = [{"at": now - 3600, "finding_id": "mom-1", "component": "canary",
                "severity": "high", "dispatched": True}]
    reconciled = pilot.reconcile(history, now=now)
    assert not any(h.get("refund_of") for h in reconciled)
    assert len(ap.Autopilot.effective(reconciled)) == 1


def test_an_unreachable_conductor_never_refunds(tmp_path, monkeypatch):
    """Over-refunding turns the daily cap into no cap. Unknown must read as spent."""
    pilot = _reconciling_pilot(tmp_path, monkeypatch, moved={"mom-1": None})
    now = time.time()
    history = [{"at": now - 3600, "finding_id": "mom-1", "component": "canary",
                "severity": "high", "dispatched": True}]
    reconciled = pilot.reconcile(history, now=now)
    assert not any(h.get("refund_of") for h in reconciled)
    assert len(ap.Autopilot.effective(reconciled)) == 1


def test_a_refund_is_written_once_not_on_every_tick(tmp_path, monkeypatch):
    pilot = _reconciling_pilot(tmp_path, monkeypatch, moved={"mom-1": False})
    now = time.time()
    history = [{"at": now - 3600, "finding_id": "mom-1", "component": "canary",
                "severity": "high", "dispatched": True}]
    first = pilot.reconcile(history, now=now)
    second = pilot.reconcile(first, now=now + 1)
    assert len([h for h in second if h.get("refund_of")]) == 1
    written = [json.loads(l) for l in open(pilot.state_path) if l.strip()]
    assert len(written) == 1


def test_refunding_frees_the_component_cap_for_a_real_regression(tmp_path, monkeypatch):
    """The exact live shape: two dispatches today, one of them absorbed."""
    pilot = _reconciling_pilot(tmp_path, monkeypatch, moved={"mom-absorbed": False, "mom-real": True})
    now = time.time()
    history = [
        {"at": now - 7200, "finding_id": "mom-real", "component": "canary",
         "severity": "high", "dispatched": True},
        {"at": now - 7100, "finding_id": "mom-absorbed", "component": "canary",
         "severity": "high", "dispatched": True},
    ]
    effective = ap.Autopilot.effective(pilot.reconcile(history, now=now))
    assert len(effective) == 1
    # With the cap at 2/component/day, a third finding is now dispatchable again.
    decision = pilot.decide(_finding(finding_id="mom-new", seen_count=4),
                            history=effective, now=now)
    assert decision.dispatch is True, decision.reason


def test_a_refunded_finding_is_no_longer_cooling_down(tmp_path, monkeypatch):
    """No work was started, so there is nothing to stay off — cooldown must lift with the slot."""
    pilot = _reconciling_pilot(tmp_path, monkeypatch, moved={"mom-1": False})
    now = time.time()
    history = [{"at": now - 3600, "finding_id": "mom-1", "component": "canary",
                "severity": "high", "dispatched": True}]
    effective = ap.Autopilot.effective(pilot.reconcile(history, now=now))
    decision = pilot.decide(_finding(finding_id="mom-1", seen_count=8),
                            history=effective, now=now)
    assert decision.dispatch is True, decision.reason


def test_job_moved_after_reads_history_timestamps(tmp_path, monkeypatch):
    """The real comparison, not the monkeypatched one."""
    pilot = ap.Autopilot(state_path=str(tmp_path / "d.jsonl"))
    at = time.time() - 7200
    after = ap._iso_utc(at + 60)
    before = ap._iso_utc(at - 600)

    class _Resp:
        status_code = 200

        def __init__(self, payload):
            self._p = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._p

    monkeypatch.setattr(ap.httpx, "get",
                        lambda url, **kw: _Resp({"job": {"history": [{"ts": before}]}}))
    assert pilot._job_moved_after("mom-1", at) is False

    monkeypatch.setattr(ap.httpx, "get",
                        lambda url, **kw: _Resp({"job": {"history": [{"ts": before}, {"ts": after}]}}))
    assert pilot._job_moved_after("mom-1", at) is True


def test_a_conductor_error_is_unknown_not_absent(tmp_path, monkeypatch):
    pilot = ap.Autopilot(state_path=str(tmp_path / "d.jsonl"))

    def _boom(url, **kw):
        raise ap.httpx.ConnectError("refused")

    monkeypatch.setattr(ap.httpx, "get", _boom)
    assert pilot._job_moved_after("mom-1", time.time()) is None


def test_a_later_ticket_does_not_retroactively_justify_a_dead_one(tmp_path, monkeypatch):
    """The live shape: dispatched 08:56, absorbed; a human re-dispatched at 10:51 and it ran.

    Asked open-endedly, the 10:51 work makes the 08:56 slot look well spent. It was not.
    """
    pilot = ap.Autopilot(state_path=str(tmp_path / "d.jsonl"))
    at = time.time() - 7 * 3600
    much_later = ap._iso_utc(at + 2 * 3600)

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"job": {"history": [{"ts": much_later}]}}

    monkeypatch.setattr(ap.httpx, "get", lambda url, **kw: _Resp())
    assert pilot._job_moved_after("mom-1", at) is False


def test_a_dispatch_inside_the_window_is_left_alone(tmp_path, monkeypatch):
    """Too soon to call it dead: the job may still be starting."""
    pilot = _reconciling_pilot(tmp_path, monkeypatch, moved={"mom-1": False})
    now = time.time()
    history = [{"at": now - 30, "finding_id": "mom-1", "component": "canary",
                "severity": "high", "dispatched": True}]
    assert not any(h.get("refund_of") for h in pilot.reconcile(history, now=now))


def test_refunding_one_dispatch_does_not_strike_out_its_tickmate(tmp_path, monkeypatch):
    """One tick stamps every dispatch with the same `now`; a refund must not free them both.

    Live regression: two findings went out at the same instant, one was absorbed, and
    refunding it also erased the other's cooldown and its slot in the day's budget.
    """
    pilot = _reconciling_pilot(tmp_path, monkeypatch,
                              moved={"mom-absorbed": False, "mom-working": True})
    now = time.time()
    stamp = now - 3600  # identical, as a single tick writes it
    history = [
        {"at": stamp, "finding_id": "mom-working", "component": "canary",
         "severity": "high", "dispatched": True},
        {"at": stamp, "finding_id": "mom-absorbed", "component": "canary",
         "severity": "high", "dispatched": True},
    ]
    effective = ap.Autopilot.effective(pilot.reconcile(history, now=now))
    assert [h["finding_id"] for h in effective] == ["mom-working"]

    # And the survivor is still cooling down: one hour into a six-hour cooldown.
    decision = pilot.decide(_finding(finding_id="mom-working", seen_count=9),
                            history=effective, now=now)
    assert decision.dispatch is False
    assert "cooling down" in decision.reason


# ── freshness: a finding nobody reproduces any more is not a live defect ──────────


def _iso_ago(seconds: float) -> str:
    return ap._iso_utc(time.time() - seconds)


def test_a_finding_the_latest_scans_no_longer_reproduce_is_not_dispatched(tmp_path):
    """seen_count never falls, so without this a fixed bug is dispatched for ever."""
    pilot = ap.Autopilot(state_path=str(tmp_path / "d.jsonl"))
    finding = _finding(seen_count=8, last_seen_at=_iso_ago(4 * 3600))
    decision = pilot.decide(finding, history=[], now=time.time())
    assert decision.dispatch is False
    assert "not a live defect" in decision.reason


def test_a_finding_seen_in_the_latest_scan_is_dispatched(tmp_path):
    pilot = ap.Autopilot(state_path=str(tmp_path / "d.jsonl"))
    finding = _finding(seen_count=8, last_seen_at=_iso_ago(30))
    assert pilot.decide(finding, history=[], now=time.time()).dispatch is True


def test_a_missing_last_seen_still_dispatches(tmp_path):
    """Unknown age must not mute a real defect; an over-dispatch is refunded, a miss is not."""
    pilot = ap.Autopilot(state_path=str(tmp_path / "d.jsonl"))
    finding = _finding(seen_count=8)
    finding.pop("last_seen_at", None)
    assert pilot.decide(finding, history=[], now=time.time()).dispatch is True


def test_the_freshness_gate_can_be_turned_off(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOPILOT_STALE_AFTER_S", "0")
    pilot = ap.Autopilot(state_path=str(tmp_path / "d.jsonl"))
    finding = _finding(seen_count=8, last_seen_at=_iso_ago(30 * 86400))
    assert pilot.decide(finding, history=[], now=time.time()).dispatch is True


# ── the cooldown must not outlive the work it protects ───────────────────────────
# Live: a cycle escalated on a branch-name collision at 12:33, and the finding — still
# reproducing — became undispatchable until 18:32. Nothing was in flight to protect.


def _cooling(tmp_path, seen=8):
    pilot = ap.Autopilot(state_path=str(tmp_path / "d.jsonl"))
    now = time.time()
    history = [{"at": now - 60, "finding_id": "mom-1", "component": "canary",
                "severity": "high", "dispatched": True}]
    finding = _finding(finding_id="mom-1", seen_count=seen, last_seen_at=ap._iso_utc(now - 30))
    return pilot, finding, history, now


def test_a_job_still_running_keeps_its_cooldown(tmp_path):
    pilot, finding, history, now = _cooling(tmp_path)
    d = pilot.decide(finding, history=history, now=now, job_state=lambda fid: "fixing")
    assert d.dispatch is False and "cooling down" in d.reason


def test_a_terminal_job_lifts_the_cooldown(tmp_path):
    pilot, finding, history, now = _cooling(tmp_path)
    for state in ("escalated", "failed", "done", "cancelled"):
        d = pilot.decide(finding, history=history, now=now, job_state=lambda fid, s=state: s)
        assert d.dispatch is True, f"{state}: {d.reason}"


def test_an_unreadable_job_state_keeps_the_cooldown(tmp_path):
    """Unknown must never read as permission — the same rule the refund follows."""
    pilot, finding, history, now = _cooling(tmp_path)
    d = pilot.decide(finding, history=history, now=now, job_state=lambda fid: None)
    assert d.dispatch is False and "cooling down" in d.reason


def test_without_a_job_state_lookup_the_cooldown_is_unchanged(tmp_path):
    pilot, finding, history, now = _cooling(tmp_path)
    d = pilot.decide(finding, history=history, now=now)
    assert d.dispatch is False and "cooling down" in d.reason


def test_a_lifted_cooldown_is_still_bounded_by_the_daily_cap(tmp_path, monkeypatch):
    """Repeats are the cap's job, not the cooldown's — so lifting it cannot run away."""
    monkeypatch.setenv("AUTOPILOT_MAX_PER_COMPONENT_PER_DAY", "2")
    pilot = ap.Autopilot(state_path=str(tmp_path / "d.jsonl"))
    now = time.time()
    history = [{"at": now - 300, "finding_id": "mom-1", "component": "canary",
                "severity": "high", "dispatched": True},
               {"at": now - 120, "finding_id": "mom-1", "component": "canary",
                "severity": "high", "dispatched": True}]
    finding = _finding(finding_id="mom-1", seen_count=9, last_seen_at=ap._iso_utc(now - 10))
    d = pilot.decide(finding, history=history, now=now, job_state=lambda fid: "escalated")
    assert d.dispatch is False
    assert "cap" in d.reason
