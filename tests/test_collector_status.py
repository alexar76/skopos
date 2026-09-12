"""Collector status persistence."""

from __future__ import annotations

from skopos.db import connect, init_db, upsert_collector_status


def test_success_clears_previous_error():
    con = connect(":memory:")
    init_db(con)
    upsert_collector_status(con, server_name="factory", ok=False, error="PermissionError(1, 'Operation not permitted')")
    upsert_collector_status(con, server_name="factory", ok=True, fetched_lines=10, inserted_rows=3, log_paths='["file:/var/log/nginx/access.log"]')

    row = con.execute(
        "SELECT last_ok_at_utc, last_error_at_utc, last_error, last_inserted_rows FROM collector_status WHERE server_name='factory'"
    ).fetchone()
    assert row[0] is not None
    assert row[1] is None
    assert row[2] is None
    assert row[3] == 3
    con.close()
