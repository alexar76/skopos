"""SKOPOS-side storage for pushed remediation boards.

The point of interest is idempotency: the push channel is at-least-once, so the
same job arrives more than once and the same job also arrives *changed*. One row
per finding either way.
"""

from __future__ import annotations

import json

import pytest

from skopos.db import connect
from skopos.node_remediation import (
    init_remediation_db,
    record_remediation,
    recent_jobs,
    stats,
)


@pytest.fixture
def con(tmp_path, monkeypatch):
    monkeypatch.delenv("SKOPOS_DATABASE_URL", raising=False)
    connection = connect(str(tmp_path / "t.sqlite3"))
    init_remediation_db(connection)
    yield connection
    connection.close()


def job(
    finding_id="mom-1",
    *,
    state="escalated",
    attempts=1,
    updated_at="2026-08-08T10:00:00Z",
    **overrides,
):
    doc = {
        "finding_id": finding_id,
        "component": "oracle-family",
        "probe": "free_tier_ceiling_bypass",
        "severity": "high",
        "route": "auto",
        "state": state,
        "attempts": attempts,
        "created_at": "2026-08-08T09:00:00Z",
        "updated_at": updated_at,
        "history": [
            {"ts": "2026-08-08T09:00:00Z", "state": "received", "note": "ticket verified"},
            {"ts": updated_at, "state": state, "note": f"attempt {attempts}"},
        ],
    }
    doc.update(overrides)
    return doc


def _row(con, finding_id="mom-1"):
    return next(r for r in recent_jobs(con) if r["finding_id"] == finding_id)


def test_insert_stores_columns_and_raw_summary(con):
    counts = record_remediation(con, server_name="conductor", jobs=[job()])
    assert (counts.accepted, counts.duplicates, counts.rejected) == (1, 0, 0)

    row = _row(con)
    assert row["server_name"] == "conductor"
    assert row["state"] == "escalated"
    assert row["attempts"] == 1
    assert row["probe"] == "free_tier_ceiling_bypass"
    # A job that never reached the gate has no verdict — not a negative one, and
    # not the string "null".
    assert row["gate_fixed"] is None
    assert row["gate_outcome"] is None
    assert row["deploy_order_id"] is None
    # The detail the columns do not model is readable back off the JSON blob.
    assert [h["note"] for h in row["summary"]["history"]] == ["ticket verified", "attempt 1"]


def test_replay_updates_the_same_row(con):
    pushed = job()
    record_remediation(con, server_name="conductor", jobs=[pushed])
    counts = record_remediation(con, server_name="conductor", jobs=[pushed])

    # Same finding, same state, same attempts: the push carried nothing new, so
    # it is a duplicate — and there is still exactly one row.
    assert (counts.accepted, counts.duplicates, counts.rejected) == (0, 1, 0)
    assert len(recent_jobs(con)) == 1
    assert stats(con)["total"] == 1


def test_escalated_job_moves_to_done_on_a_later_push(con):
    record_remediation(con, server_name="conductor", jobs=[job()])
    counts = record_remediation(con, server_name="conductor", jobs=[
        job(
            state="done",
            attempts=2,
            updated_at="2026-08-08T11:00:00Z",
            gate_verdict={"fixed": True, "outcome": "no_finding", "detail": "clean"},
            deploy={"order_id": "deploy-mom-1-1000", "service": "oracle-family"},
            agent_result={"deployed": True},
        )
    ])

    assert (counts.accepted, counts.duplicates, counts.rejected) == (1, 0, 0)
    rows = recent_jobs(con)
    assert len(rows) == 1
    assert rows[0]["state"] == "done"
    assert rows[0]["attempts"] == 2
    assert rows[0]["gate_fixed"] is True
    assert rows[0]["gate_outcome"] == "no_finding"
    assert rows[0]["deploy_order_id"] == "deploy-mom-1-1000"
    assert rows[0]["deployed"] is True


def test_a_stale_push_cannot_walk_a_finished_job_backwards(con):
    record_remediation(con, server_name="conductor", jobs=[
        job(state="done", attempts=2, updated_at="2026-08-08T11:00:00Z")
    ])
    # A pusher that timed out re-sends an older window under a fresh sequence
    # number; the row it names is newer than the one it carries.
    counts = record_remediation(con, server_name="conductor", jobs=[
        job(state="fixing", attempts=1, updated_at="2026-08-08T10:00:00Z")
    ])

    assert (counts.accepted, counts.duplicates, counts.rejected) == (0, 1, 0)
    assert _row(con)["state"] == "done"


def test_stats_counts_open_and_terminal_states(con):
    record_remediation(con, server_name="conductor", jobs=[
        job("mom-1", state="done", attempts=2),
        job("mom-2", state="escalated", attempts=3),
        job("mom-3", state="fixing", attempts=1),
        job("mom-4", state="retesting", attempts=1),
    ])
    out = stats(con)

    assert out["total"] == 4
    assert out["by_state"] == {"done": 1, "escalated": 1, "fixing": 1, "retesting": 1}
    assert out["open"] == 2
    assert out["done"] == 1
    assert out["escalated"] == 1
    assert out["failed"] == 0
    assert out["last_update_utc"] == "2026-08-08T10:00:00Z"


def test_empty_store_reads_back_empty(con):
    assert recent_jobs(con) == []
    assert stats(con) == {
        "total": 0,
        "by_state": {},
        "open": 0,
        "done": 0,
        "failed": 0,
        "escalated": 0,
        "last_update_utc": None,
    }


def test_empty_store_reads_back_on_a_database_without_the_table(tmp_path):
    # The dashboard opens the same database as the ingest but may reach it first.
    fresh = connect(str(tmp_path / "fresh.sqlite3"))
    try:
        assert recent_jobs(fresh) == []
        assert stats(fresh)["total"] == 0
    finally:
        fresh.close()


def test_the_credential_decides_the_server_not_the_payload(con):
    record_remediation(
        con,
        server_name="conductor",
        jobs=[job(host="10.0.0.9", component="oracle-family")],
    )
    assert _row(con)["server_name"] == "conductor"
    # Two servers pushing the same finding id are two different rows, so one
    # node can never overwrite another's board.
    record_remediation(con, server_name="other-node", jobs=[job()])
    assert {r["server_name"] for r in recent_jobs(con)} == {"conductor", "other-node"}
    assert len(recent_jobs(con, server_name="conductor")) == 1


def test_unusable_and_unbounded_entries_are_rejected_not_stored(con):
    counts = record_remediation(con, server_name="conductor", jobs=[
        job(finding_id=""),            # no identity
        job(state="teleporting"),      # a state the board cannot label
        "not-a-job",
        job("mom-ok"),
    ])
    assert (counts.accepted, counts.rejected) == (1, 3)
    assert [r["finding_id"] for r in recent_jobs(con)] == ["mom-ok"]


def test_third_party_text_is_scrubbed_and_the_ticket_never_lands(con):
    record_remediation(con, server_name="conductor", jobs=[job(
        # The raw MOMUS ticket is unbounded and attacker-influenced; it is not on
        # the allowlist, so it cannot reach the row at all.
        ticket={"blame": {"signature": {"value": "x" * 5000}}},
        history=[{
            "ts": "2026-08-08T10:00:00Z",
            "state": "escalated",
            "note": "retest not fixed: \x1b[2Jsecret=hunter2 and a\x00null",
        }],
    )])
    row = _row(con)
    note = row["summary"]["history"][0]["note"]

    assert "ticket" not in row["summary"]
    assert "hunter2" not in note and "secret=<redacted>" in note
    assert "\x1b" not in note and "\x00" not in note
    assert "ticket" not in row["summary_json"]


def test_component_that_is_really_an_address_is_not_stored_as_a_label(con):
    record_remediation(con, server_name="conductor", jobs=[
        job("mom-ip", component="10.0.0.9"),
        job("mom-url", component="https://skopos.internal/deploy"),
    ])
    labels = {r["finding_id"]: r["component"] for r in recent_jobs(con)}
    assert labels == {"mom-ip": "<redacted>", "mom-url": "<redacted>"}


def test_summary_json_is_bounded(con):
    record_remediation(con, server_name="conductor", jobs=[job(history=[
        {"ts": "2026-08-08T10:00:00Z", "state": "fixing", "note": "n" * 4000}
        for _ in range(200)
    ])])
    row = _row(con)
    blob = row["summary_json"]

    assert len(blob) <= 16_384
    assert json.loads(blob)  # still valid JSON after the trimming
