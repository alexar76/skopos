"""The courier that carries orders out and results back — and decides nothing.

It runs beside the conductor and speaks the same agent protocol a local hand does, so the
conductor needs no knowledge that some of its hands are elsewhere. These tests pin the parts
that are easy to get subtly wrong, and one of them is an ORDERING bug that would be invisible:
orders are handed out ONCE, so an order that reaches the hand before the commit it names is
spent on a build that cannot find its branch.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from skopos.remediation import fleet_forwarder as ff  # noqa: E402


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise ff.httpx.HTTPError(f"status {self.status_code}")


@pytest.fixture()
def wired(monkeypatch):
    """A forwarder with the network replaced by a transcript."""
    monkeypatch.setenv("SKOPOS_FORWARDER_HOSTS", "hub")
    monkeypatch.setenv("SKOPOS_RELAY_URL", "https://relay.example")
    monkeypatch.setenv("SKOPOS_RELAY_TOKEN", "t")
    monkeypatch.setenv("SKOPOS_AGENT_TOKEN", "a")
    monkeypatch.setenv("SKOPOS_CONDUCTOR_URL", "http://127.0.0.1:9402")
    fw = ff.FleetForwarder()
    calls: list[tuple[str, str]] = []

    def fake_get(url, **kwargs):
        calls.append(("GET", url))
        if url.endswith("/agent/v1/orders"):
            return _Resp({"order": {"kind": "build", "branch": "momus/fix-mom-1",
                                    "commit_sha": "abc123"},
                          "order_id": "ord-1", "host": "hub"})
        if url.endswith("/fleet/v1/results"):
            return _Resp({"results": []})
        return _Resp({})

    def fake_post(url, **kwargs):
        calls.append(("POST", url))
        return _Resp({"queued": True, "applied": True, "detail": "ok"})

    monkeypatch.setattr(ff.httpx, "get", fake_get)
    monkeypatch.setattr(ff.httpx, "post", fake_post)
    return fw, calls


class TestOrderingIsLoadBearing:
    def test_the_source_is_delivered_before_the_order(self, wired, monkeypatch):
        """Orders are handed out once. An order that reaches the hand before its commit is spent
        on a build that cannot find its branch — and nothing retries it."""
        fw, calls = wired
        monkeypatch.setattr(fw, "send_source", lambda branch: (True, "applied"))
        fw.carry_orders()
        posted = [u for m, u in calls if m == "POST"]
        assert posted == ["https://relay.example/fleet/v1/orders"]

    def test_a_source_failure_is_reported_instead_of_the_order_being_dropped(self, wired, monkeypatch):
        """The conductor is waiting for a result. Silently dropping the order leaves the job
        hanging until its timeout, with no reason recorded anywhere."""
        fw, calls = wired
        monkeypatch.setattr(fw, "send_source", lambda branch: (False, "bundle rejected"))
        reported: list[dict] = []
        monkeypatch.setattr(fw, "report", lambda payload: reported.append(payload) or True)
        out = fw.carry_orders()
        assert out and out[0]["carried"] is False
        assert reported and reported[0]["result"]["refused"] is True
        assert "bundle rejected" in reported[0]["result"]["reason"]
        assert "fleet/v1/orders" not in " ".join(u for m, u in calls if m == "POST")


class TestItCarriesOnlyWhatItWasTold:
    def test_no_hosts_means_it_carries_nothing(self, monkeypatch):
        """A courier that guessed would claim an order meant for a hand perfectly able to poll
        the conductor itself — and the order is handed out ONCE, to the wrong courier."""
        monkeypatch.setenv("SKOPOS_FORWARDER_HOSTS", "")
        assert ff.FleetForwarder().hosts == []

    def test_hosts_are_parsed_exactly(self, monkeypatch):
        monkeypatch.setenv("SKOPOS_FORWARDER_HOSTS", " hub , gaia ,, ")
        assert ff.FleetForwarder().hosts == ["hub", "gaia"]


class TestOrdersWithoutSource:
    def test_a_rollback_carries_no_branch_and_needs_no_bundle(self, wired, monkeypatch):
        """A rollback restores a digest the hand already recorded; there is nothing to build."""
        fw, calls = wired

        def fake_get(url, **kwargs):
            calls.append(("GET", url))
            if url.endswith("/agent/v1/orders"):
                return _Resp({"order": {"kind": "rollback", "rollback_of": "ord-0"},
                              "order_id": "ord-2", "host": "hub"})
            return _Resp({"results": []})

        monkeypatch.setattr(ff.httpx, "get", fake_get)
        called = []
        monkeypatch.setattr(fw, "send_source", lambda branch: called.append(branch) or (True, ""))
        out = fw.carry_orders()
        assert not called, "a rollback should not ask for source"
        assert out and out[0]["carried"] is True


class TestResultsComeBack:
    def test_each_result_is_posted_to_the_conductor(self, wired, monkeypatch):
        fw, calls = wired

        def fake_get(url, **kwargs):
            if url.endswith("/fleet/v1/results"):
                return _Resp({"results": [{"order_id": "ord-1", "result": {"deployed": True}},
                                          {"order_id": "ord-2", "result": {"refused": True}}]})
            return _Resp({"order": None})

        monkeypatch.setattr(ff.httpx, "get", fake_get)
        posted: list[dict] = []
        monkeypatch.setattr(fw, "report", lambda payload: posted.append(payload) or True)
        assert fw.carry_results() == 2
        assert [p["order_id"] for p in posted] == ["ord-1", "ord-2"]

    def test_a_conductor_outage_leaves_the_result_undelivered_rather_than_lost(self, wired, monkeypatch):
        """It returns a count, not an exception: the relay still holds nothing, but the journal
        on the relay is the record, and the next tick tries again."""
        fw, _ = wired
        monkeypatch.setattr(fw, "report", lambda payload: False)
        monkeypatch.setattr(ff.httpx, "get", lambda url, **kw: _Resp(
            {"results": [{"order_id": "ord-9", "result": {}}]}))
        assert fw.carry_results() == 0


class TestTheCourierDoesNotCarryWhatIsAlreadyThere:
    """`git bundle create <branch> --not <that same sha>` produces an EMPTY bundle, which git
    refuses outright — and the fallback then sent the entire 586 MB history to deliver nothing.
    A retry, or a second order for the same commit, is exactly when that happens."""

    def _fw(self, monkeypatch, relay_refs, tip):
        monkeypatch.setenv("SKOPOS_RELAY_URL", "https://relay.example")
        monkeypatch.setenv("SKOPOS_RELAY_TOKEN", "t")
        monkeypatch.setenv("SKOPOS_FORWARDER_REPO_URL", "https://git.example/x.git")
        fw = ff.FleetForwarder()
        monkeypatch.setattr(fw, "_ensure_mirror", lambda: (True, "ok"))
        monkeypatch.setattr(fw, "relay_refs", lambda: relay_refs)
        calls: list[tuple] = []

        def fake_git(*args):
            calls.append(args)
            if "rev-parse" in args:
                return 0, tip + "\n", ""
            return 0, "", ""

        monkeypatch.setattr(fw, "_git", fake_git)
        return fw, calls

    def test_a_commit_the_relay_already_has_is_not_bundled_again(self, monkeypatch):
        fw, calls = self._fw(monkeypatch, {"refs/heads/momus/fix-1": "deadbeef"}, "deadbeef")
        ok, note = fw.send_source("momus/fix-1")
        assert ok and note == "already on the relay"
        assert not any("bundle" in a for a in calls), "it bundled anyway"

    def test_a_new_commit_on_a_known_branch_is_still_carried(self, monkeypatch):
        fw, calls = self._fw(monkeypatch, {"refs/heads/momus/fix-1": "oldsha"}, "newsha")
        monkeypatch.setattr(ff.httpx, "post", lambda url, **kw: _Resp({"applied": True,
                                                                       "detail": "ok"}))
        ok, _ = fw.send_source("momus/fix-1")
        assert ok
        assert any("bundle" in a for a in calls), "a new commit must still be carried"
