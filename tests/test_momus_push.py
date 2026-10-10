"""SKOPOS hands its findings to MOMUS — and the ways it must not.

The bridge on the MOMUS side was written, tested and reachable while nothing here ever called
it. So these tests are mostly about the calling: that it is configured rather than assumed, that
a dead MOMUS loses nothing, and above all that one observation is reported once.

That last one is not tidiness. MOMUS counts how many separate scans rediscovered a defect and
the autopilot will not dispatch a fix until that count passes a threshold. A pusher that re-sent
the same snapshot on a timer would manufacture that evidence out of thin air, and the loop would
redeploy production on the strength of a single sighting counted three times.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from skopos.db_connection import connect_sqlite  # noqa: E402
from skopos.security.audit import SecurityFinding  # noqa: E402
from skopos.security.momus_push import (  # noqa: E402
    MomusPusher,
    build_document,
    last_pushed_snapshot,
    push_latest,
)
from skopos.security.probe import ServerSnapshot  # noqa: E402
from skopos.security.store import save_scan  # noqa: E402


class FakeMomus:
    """Stands in for MOMUS. Records what it was told, answers how it was asked to."""

    def __init__(self, *, status: int = 200, error: str = "", imported: int = 1):
        self.status, self.error, self.imported = status, error, imported
        self.documents: list[dict] = []

    def configured(self):
        return True, ""

    def post(self, document):
        self.documents.append(document)
        if self.error:
            return None, {}, self.error
        return self.status, {"imported": self.imported, "new": self.imported}, ""


@pytest.fixture
def con(tmp_path):
    c = connect_sqlite(str(tmp_path / "skopos.db"))
    yield c
    c.close()


def _scan(con, server: str = "oracle-host", *, at: str = "2026-09-14T10:00:00Z",
          title: str = "PostgreSQL reachable from the internet") -> int:
    snap = ServerSnapshot(server_name=server, host="10.0.0.2", scanned_at_utc=at)
    finding = SecurityFinding(severity="high", category="ports", title=title,
                              detail="tcp/5432 on 0.0.0.0", recommendation="Bind to localhost.")
    return save_scan(con, snap, [finding])


def test_the_export_is_the_shape_momus_reads(con):
    """Built here, parsed there. The contract is `momus.intel.skopos_bridge.import_findings`."""
    sid = _scan(con)
    from skopos.security.store import latest_snapshots

    [snap] = latest_snapshots(con, ["oracle-host"])
    doc = build_document(con, snap)
    assert doc["server"] == "oracle-host"
    assert doc["observed_at"] == "2026-09-14T10:00:00Z"
    [f] = doc["findings"]
    assert (f["severity"], f["category"]) == ("high", "ports")
    assert f["title"] and f["detail"] and f["recommendation"]
    assert sid


def test_one_snapshot_is_reported_once(con):
    """The sighting count is dispatch evidence; it must come from scans, not from timer ticks."""
    _scan(con)
    momus = FakeMomus()
    [first] = push_latest(con, pusher=momus)
    assert first.pushed and first.findings_sent == 1
    [second] = push_latest(con, pusher=momus)
    assert not second.pushed
    assert "already sent" in second.reason
    assert len(momus.documents) == 1


def test_a_new_scan_is_reported_again(con):
    """A defect that survives the next scan is a rediscovery, and MOMUS must hear about it."""
    _scan(con)
    momus = FakeMomus()
    push_latest(con, pusher=momus)
    _scan(con, at="2026-09-14T10:15:00Z")
    [again] = push_latest(con, pusher=momus)
    assert again.pushed
    assert len(momus.documents) == 2


def test_a_refused_push_is_not_remembered_as_sent(con):
    """Marking a failed push as delivered would skip that snapshot for ever."""
    _scan(con)
    dead = FakeMomus(error="MOMUS unreachable: ConnectError")
    [result] = push_latest(con, pusher=dead)
    assert not result.pushed and "unreachable" in result.reason
    assert last_pushed_snapshot(con, "oracle-host") is None
    # The next pass retries it rather than silently dropping the fleet's first report.
    live = FakeMomus()
    [retry] = push_latest(con, pusher=live)
    assert retry.pushed


def test_resend_overrides_the_memory(con):
    """For re-importing into a MOMUS whose corpus was lost — an explicit act, never the default."""
    _scan(con)
    momus = FakeMomus()
    push_latest(con, pusher=momus)
    [forced] = push_latest(con, pusher=momus, resend=True)
    assert forced.pushed
    assert len(momus.documents) == 2


def test_it_is_silent_and_explicit_when_unconfigured(con, monkeypatch):
    """No address or no token sends nothing — and says so, rather than looking like a clean fleet."""
    _scan(con)
    for var in ("SKOPOS_MOMUS_URL", "AUTOPILOT_MOMUS_URL", "MOMUS_OPERATOR_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    [result] = push_latest(con, pusher=MomusPusher())
    assert not result.pushed and "SKOPOS_MOMUS_URL" in result.reason
    assert last_pushed_snapshot(con, "oracle-host") is None

    monkeypatch.setenv("SKOPOS_MOMUS_URL", "http://127.0.0.1:9410")
    [result] = push_latest(con, pusher=MomusPusher())
    assert not result.pushed and "MOMUS_OPERATOR_TOKEN" in result.reason


def test_only_the_named_servers_are_reported(con):
    _scan(con, "oracle-host")
    _scan(con, "hub-host")
    momus = FakeMomus()
    results = push_latest(con, server_names=["hub-host"], pusher=momus)
    assert [r.server_name for r in results] == ["hub-host"]
    assert momus.documents[0]["server"] == "hub-host"


def test_the_operator_token_travels_in_the_header_momus_reads():
    """Named here because a wrong header name fails as a 403 that looks like a bad token."""
    from skopos.security import momus_push

    assert momus_push.OPERATOR_HEADER == "x-momus-operator"


def test_the_autopilot_does_not_report_unless_asked(monkeypatch):
    """Reporting is not dispatching, so it has its own switch — and that switch defaults to off."""
    from skopos.remediation import autopilot as ap

    monkeypatch.delenv("SKOPOS_MOMUS_PUSH", raising=False)
    assert ap.Autopilot().report_skopos_findings() == []


def test_a_broken_push_never_stops_the_loop(monkeypatch):
    """SKOPOS's own database being unreadable must not stop MOMUS's findings being dispatched."""
    from skopos.remediation import autopilot as ap
    from skopos.security import momus_push

    monkeypatch.setenv("SKOPOS_MOMUS_PUSH", "1")
    monkeypatch.setattr(momus_push, "push_now",
                        lambda **_: (_ for _ in ()).throw(RuntimeError("no database")))
    [entry] = ap.Autopilot().report_skopos_findings()
    assert entry["pushed"] is False and "RuntimeError" in entry["reason"]


# ── the cross-host path ─────────────────────────────────────────────────────────
# MOMUS is on another machine, binds to loopback, and its public edge answers 404 for
# every route that makes it act — /skopos/report among them. So SKOPOS publishes and
# the MOMUS host pulls. These tests are about that inversion: what the export will and
# will not hand out, and that the puller still sends one push per scan without a
# database of its own to remember in.
def test_the_export_is_off_until_it_has_a_token(monkeypatch):
    from skopos.security import export

    monkeypatch.delenv(export.TOKEN_ENV, raising=False)
    assert not export.export_enabled()
    assert not export.token_ok("")
    assert not export.token_ok("anything")


def test_the_export_refuses_a_wrong_token(monkeypatch):
    from skopos.security import export

    monkeypatch.setenv(export.TOKEN_ENV, "s3cret")
    assert export.export_enabled()
    assert export.token_ok("s3cret")
    assert not export.token_ok("s3cre")
    assert not export.token_ok("")
    assert not export.token_ok(None)


def test_the_export_carries_the_snapshot_id(con):
    """Without it the puller cannot tell a re-scan from a repeat of the same scan."""
    from skopos.security.export import build_export

    _scan(con)
    body = build_export(con)
    assert body["count"] == 1
    [doc] = body["documents"]
    assert isinstance(doc["snapshot_id"], int)
    assert doc["server"] == "oracle-host" and doc["findings"]


def test_the_puller_sends_one_push_per_scan(tmp_path, monkeypatch):
    from skopos.security import momus_push

    documents = [{"server": "oracle-host", "snapshot_id": 7, "observed_at": "t",
                  "findings": [{"severity": "high", "category": "ports", "title": "x",
                                "detail": "d", "recommendation": "r"}]}]
    monkeypatch.setattr(momus_push, "fetch_export", lambda url, token, **kw: documents)
    state = str(tmp_path / "seen.json")
    momus = FakeMomus()

    [first] = momus_push.push_remote(export_url="http://skopos/e", export_token="t",
                                     seen_path=state, pusher=momus)
    assert first.pushed and first.snapshot_id == 7
    [second] = momus_push.push_remote(export_url="http://skopos/e", export_token="t",
                                      seen_path=state, pusher=momus)
    assert not second.pushed and "already sent" in second.reason
    documents[0]["snapshot_id"] = 8
    [third] = momus_push.push_remote(export_url="http://skopos/e", export_token="t",
                                     seen_path=state, pusher=momus)
    assert third.pushed
    assert len(momus.documents) == 2


def test_a_refused_remote_push_is_not_remembered(tmp_path, monkeypatch):
    from skopos.security import momus_push

    documents = [{"server": "oracle-host", "snapshot_id": 7, "observed_at": "t", "findings": []}]
    monkeypatch.setattr(momus_push, "fetch_export", lambda url, token, **kw: documents)
    state = str(tmp_path / "seen.json")
    [dead] = momus_push.push_remote(export_url="http://skopos/e", export_token="t",
                                    seen_path=state, pusher=FakeMomus(error="boom"))
    assert not dead.pushed
    [retry] = momus_push.push_remote(export_url="http://skopos/e", export_token="t",
                                     seen_path=state, pusher=FakeMomus())
    assert retry.pushed


def test_the_puller_is_explicit_when_unconfigured(tmp_path):
    from skopos.security import momus_push

    [r] = momus_push.push_remote(export_url="", export_token="t",
                                 seen_path=str(tmp_path / "s.json"), pusher=FakeMomus())
    assert not r.pushed and momus_push.EXPORT_URL_ENV in r.reason
    [r] = momus_push.push_remote(export_url="http://skopos/e", export_token="",
                                 seen_path=str(tmp_path / "s.json"), pusher=FakeMomus())
    assert not r.pushed and momus_push.EXPORT_TOKEN_ENV in r.reason


def test_reporting_cannot_kill_the_tick(monkeypatch):
    """The import lives inside the try, and this is why.

    `skopos.security` used to drag in the SSH probe stack, which a conductor-only host
    does not install. With the import one line higher it raised before the guard and took
    the whole tick with it — and `run_forever` swallows that, so the loop went on sleeping
    and dispatching nothing, with nothing in the journal to say why.
    """
    import builtins

    from skopos.remediation import autopilot as ap

    monkeypatch.setenv("SKOPOS_MOMUS_PUSH", "1")
    real_import = builtins.__import__

    def refuse(name, *args, **kwargs):
        if name == "skopos.security.momus_push":
            raise ModuleNotFoundError("No module named 'paramiko'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", refuse)
    [entry] = ap.Autopilot().report_skopos_findings()
    assert entry["pushed"] is False and "ModuleNotFoundError" in entry["reason"]


def test_the_findings_pusher_needs_no_ssh_stack():
    """It reads a table and posts JSON; requiring paramiko to do that is the bug above."""
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.modules['paramiko'] = None;"
         " import skopos.security.momus_push as m; print(m.OPERATOR_HEADER)"],
        cwd=str(root), capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "x-momus-operator" in proc.stdout
