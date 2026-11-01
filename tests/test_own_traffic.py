"""The fleet's own requests are counted, not stored, when the operator says so.

On 2026-11-01 ~93% of the requests one SKOPOS stored came from the fleet's own servers
(monitors, health checks, hubs polling each other), and they were filling its disk.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from skopos.collector import ingest_lines
from skopos.config import load_config
from skopos.db import connect, init_db, prune_dedup
from skopos.log_sources import LogSource
from skopos.own_traffic import is_own, own_addresses

SRC = LogSource(id="file:/var/log/nginx/access.log", kind="file", parser="nginx")
FLEET = "9.9.9.9"
STRANGER = "8.8.8.8"


def _line(ip, path="/a", stamp="31/Oct/2026:10:00:00 +0000"):
    return f'{ip} - - [{stamp}] "GET {path} HTTP/1.1" 200 12 "-" "curl/8"'


@pytest.fixture
def db(tmp_path, monkeypatch):
    for name in ("SKOPOS_DATABASE_URL", "SKOPOS_IP_ANONYMIZE", "SKOPOS_STORE_RAW_LINES"):
        monkeypatch.delenv(name, raising=False)
    con = connect(str(tmp_path / "t.sqlite3"))
    init_db(con)
    return con


def _cfg(*, store=False, servers=(FLEET,), extra=()):
    return SimpleNamespace(
        store_own_traffic=store,
        own_addresses=tuple(extra),
        servers=[SimpleNamespace(ssh=SimpleNamespace(host=h)) for h in servers],
    )


def _count(con, sql):
    return con.execute(sql).fetchone()[0]


def test_own_lines_are_counted_once_and_strangers_are_stored(db):
    own = own_addresses(_cfg())
    lines = [(SRC, _line(FLEET, "/health")), (SRC, _line(STRANGER, "/pricing")), (SRC, _line(FLEET, "/.well-known/x"))]
    ingest_lines(db, server_name="factory", server_ip=FLEET, lines=lines, own=own)
    # The next report overlaps the last window: nothing may be counted twice.
    ingest_lines(db, server_name="factory", server_ip=FLEET, lines=lines, own=own)
    assert _count(db, "SELECT count(*) FROM http_requests") == 1
    assert db.execute("SELECT path FROM http_requests").fetchone()[0] == "/pricing"
    row = db.execute("SELECT day, server_name, requests FROM own_traffic_daily").fetchone()
    assert tuple(row) == ("2026-10-31", "factory", 2)


def test_storing_own_traffic_stays_the_default(db, monkeypatch):
    for name in ("SKOPOS_STORE_OWN_TRAFFIC", "SKOPOS_OWN_ADDRESSES", "SKOPOS_DEDUP_RETENTION_DAYS"):
        monkeypatch.delenv(name, raising=False)
    assert own_addresses(_cfg(store=True)) is None
    ingest_lines(db, server_name="s", server_ip=FLEET, lines=[(SRC, _line(FLEET))], own=own_addresses(_cfg(store=True)))
    assert _count(db, "SELECT count(*) FROM http_requests") == 1
    assert _count(db, "SELECT count(*) FROM own_traffic_daily") == 0


def test_private_addresses_are_never_the_fleets(db):
    # A docker gateway can stand in front of every real visitor of a service.
    own = own_addresses(_cfg(servers=(FLEET, "172.17.0.1"), extra=("10.0.0.5",)))
    assert own == frozenset({FLEET})
    assert not is_own("172.17.0.1", own)
    ingest_lines(db, server_name="s", server_ip=FLEET, lines=[(SRC, _line("172.17.0.4"))], own=own)
    assert _count(db, "SELECT count(*) FROM http_requests") == 1


def test_extra_addresses_count_and_host_names_do_not(db):
    # A name is not resolved: behind a CDN its addresses would be every visitor's.
    own = own_addresses(_cfg(servers=("-", "shop.example.org", "localhost"), extra=("1.1.1.1", " ", "example.com")))
    assert own == frozenset({"1.1.1.1"})
    assert is_own("1.1.1.1", own) and not is_own("1.1.1.2", own) and not is_own(None, own)


def test_config_reads_the_switches_from_the_environment(tmp_path, monkeypatch):
    path = tmp_path / "skopos.yml"
    path.write_text(
        "db_path: ./x.sqlite3\nservers:\n"
        "  - name: pushed\n    source: ssh_nginx_access_log\n    transport: agent-push\n"
        "    address: 9.9.9.9\n    nginx: {access_log_path: /var/log/nginx/access.log}\n"
    )
    monkeypatch.setenv("SKOPOS_STORE_OWN_TRAFFIC", "0")
    monkeypatch.setenv("SKOPOS_OWN_ADDRESSES", "1.1.1.1, 1.2.3.4")
    monkeypatch.setenv("SKOPOS_DEDUP_RETENTION_DAYS", "7")
    cfg = load_config(str(path))
    assert cfg.store_own_traffic is False
    assert cfg.own_addresses == ("1.1.1.1", "1.2.3.4")
    assert cfg.dedup_retention_days == 7
    assert own_addresses(cfg) == frozenset({"9.9.9.9", "1.1.1.1", "1.2.3.4"})


def test_pruning_finds_the_boundary_across_gaps(db):
    now = datetime.now(timezone.utc)
    for i in range(40):
        stamp = (now - timedelta(days=20 - i * 0.5)).isoformat()
        db.execute("INSERT INTO ingested_lines(server_name, line_sha1, ingested_at_utc) VALUES('s',?,?)", (f"h{i}", stamp))
    db.execute("DELETE FROM ingested_lines WHERE line_sha1 IN ('h3','h7','h20','h25')")
    db.commit()
    prune_dedup(db, 7)
    left = db.execute("SELECT min(ingested_at_utc) FROM ingested_lines").fetchone()[0]
    older = db.execute("SELECT count(*) FROM ingested_lines WHERE ingested_at_utc < ?",
                       ((now - timedelta(days=7)).isoformat(),)).fetchone()[0]
    assert older == 0 and left >= (now - timedelta(days=7, minutes=1)).isoformat()
    assert db.execute("SELECT count(*) FROM ingested_lines").fetchone()[0] == 13  # ages 6.5 .. 0.5 days


def test_line_hashes_older_than_the_window_are_pruned(db):
    old = (datetime.now(timezone.utc) - timedelta(days=9)).isoformat()
    new = datetime.now(timezone.utc).isoformat()
    db.execute("INSERT INTO ingested_lines(server_name, line_sha1, ingested_at_utc) VALUES('s','a',?)", (old,))
    db.execute("INSERT INTO ingested_lines(server_name, line_sha1, ingested_at_utc) VALUES('s','b',?)", (new,))
    db.commit()
    assert prune_dedup(db, 0) == 0
    assert prune_dedup(db, 7) == 1
    assert [r[0] for r in db.execute("SELECT line_sha1 FROM ingested_lines").fetchall()] == ["b"]


def test_the_postgres_schema_creates_the_totals_table():
    # SQLite runs the schema as one script; PostgreSQL runs it statement by statement, and a
    # statement with a comment above it was dropped there (own_traffic_daily, 2026-11-01).
    from skopos.db import POSTGRES_SCHEMA
    from skopos.db_dialect import split_sql_script

    statements = split_sql_script(POSTGRES_SCHEMA)
    assert any(s.startswith("CREATE TABLE IF NOT EXISTS own_traffic_daily") for s in statements)
    assert split_sql_script("-- only a comment\n;\n-- a note\nSELECT 1;") == ["SELECT 1"]
