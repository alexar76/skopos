"""Tests for scan history store and charts."""

from __future__ import annotations

from skopos.db import connect, init_db
from skopos.security.audit import SecurityFinding
from skopos.security.history_charts import chart_score_timeline, chart_diff_summary
from skopos.security.probe import ServerSnapshot
from skopos.security.store import (
    compare_snapshots,
    fleet_score_history,
    list_scan_history,
    save_scan,
    scan_history_summary,
    snapshot_score,
)


def _minimal_snap(name: str = "srv1") -> ServerSnapshot:
    return ServerSnapshot.from_dict(
        {
            "server_name": name,
            "host": "10.0.0.1",
            "scanned_at_utc": "2026-07-01T12:00:00+00:00",
            "cpu_idle_pct": 90.0,
            "mem_used_pct": 40.0,
            "load_1": 0.5,
            "disks": [],
            "ports": [],
            "docker_containers": [],
        }
    )


def test_scan_history_roundtrip(tmp_path):
    db = str(tmp_path / "t.sqlite3")
    con = connect(db)
    init_db(con)

    f1 = SecurityFinding(
        severity="high",
        category="ssh",
        title="Password auth enabled",
        detail="PermitRootLogin yes",
        recommendation="Disable",
    )
    snap1 = _minimal_snap()
    id1 = save_scan(con, snap1, [f1])

    snap2 = _minimal_snap()
    snap2_dict = snap2.to_dict()
    snap2_dict["scanned_at_utc"] = "2026-07-02T12:00:00+00:00"
    snap2 = ServerSnapshot.from_dict(snap2_dict)
    f2 = SecurityFinding(
        severity="critical",
        category="ports",
        title="Open Redis",
        detail="6379 public",
        recommendation="Bind localhost",
    )
    id2 = save_scan(con, snap2, [f2])

    summary = scan_history_summary(con, ["srv1"])
    assert summary["total_scans"] == 2

    history = list_scan_history(con, ["srv1"], limit=10)
    assert len(history) == 2
    assert history[0]["findings_total"] >= 1

    scores = fleet_score_history(con, ["srv1"], days=30)
    assert len(scores) == 2
    assert scores[-1]["score"] < scores[0]["score"]  # critical worse than high only

    diff = compare_snapshots(con, id1, id2)
    assert len(diff["new_issues"]) >= 1
    assert diff["unchanged_count"] >= 0

    fig = chart_score_timeline(scores)
    assert fig.layout.height == 400

    fig2 = chart_diff_summary(diff)
    assert fig2.data[0].y[0] >= 1

    con.close()


def test_snapshot_score_empty():
    assert snapshot_score([]) == 100
