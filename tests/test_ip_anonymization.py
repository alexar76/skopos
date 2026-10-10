"""IP anonymisation must protect the visitor and cost the dashboard nothing.

Same contract as the redaction tests: the address is reduced to something that is
no longer personal data, while country, ASN and distinct-visitor counts — the
things the dashboard is actually built on — survive. And the reduction must
happen *after* the geo/ASN lookup, or it would trade the whole point of the
dashboard for the privacy win.
"""

from __future__ import annotations

import datetime
from types import SimpleNamespace

import pytest

from skopos.anonymize import anonymize_ip, backfill_existing, scrub_ips_in_text


# --- The address is reduced --------------------------------------------------

def test_ipv4_truncates_to_its_network():
    assert anonymize_ip("8.8.8.8", mode="truncate") == "8.8.8.0"
    assert anonymize_ip("45.33.32.156", mode="truncate") == "45.33.32.0"


def test_ipv6_truncates_to_a_48():
    assert anonymize_ip("2001:4860:4860::8888", mode="truncate") == "2001:4860:4860::"


def test_hash_is_deterministic_opaque_and_salted():
    a = anonymize_ip("8.8.8.8", mode="hash", salt="s1")
    b = anonymize_ip("8.8.8.8", mode="hash", salt="s1")
    assert a == b, "the same address must count as the same visitor"
    assert a.startswith("h:") and "8.8.8.8" not in a, "the address itself leaked"
    assert anonymize_ip("8.8.8.8", mode="hash", salt="s2") != a, "the salt does nothing"


def test_distinct_public_addresses_stay_distinct_under_hash():
    # Distinct-visitor counts depend on this: two people must not collapse to one.
    assert anonymize_ip("8.8.8.8", mode="hash", salt="s") != anonymize_ip(
        "8.8.4.4", mode="hash", salt="s"
    )


# --- What must be left alone -------------------------------------------------

def test_off_keeps_the_full_address():
    assert anonymize_ip("8.8.8.8", mode="off") == "8.8.8.8"


@pytest.mark.parametrize("ip", ["10.0.0.5", "192.168.1.1", "127.0.0.1", "169.254.1.1"])
def test_internal_addresses_are_kept_whole(ip):
    # No data subject sits between our own hosts, and the exact value is what
    # makes an internal log debuggable.
    assert anonymize_ip(ip, mode="truncate") == ip
    assert anonymize_ip(ip, mode="hash", salt="s") == ip


@pytest.mark.parametrize("value", [None, "", "not-an-ip", "HTTP/1.1"])
def test_non_addresses_pass_through(value):
    assert anonymize_ip(value, mode="truncate") == value


# --- scrub_ips_in_text (the verbatim line) -----------------------------------

def test_scrub_reduces_addresses_but_not_lookalikes():
    line = '8.8.8.8 - - [x] "GET /a HTTP/1.1" 200 4096 "-" "curl/8.8.8"'
    out = scrub_ips_in_text(line, mode="truncate")
    assert "8.8.8.8 - -" not in out and "8.8.8.0 - -" in out, "the client IP was not reduced"
    assert "HTTP/1.1" in out, "a version string was mistaken for an address"
    assert "200 4096" in out, "a byte count was mistaken for an address"
    assert "curl/8.8.8" in out, "a UA token was mistaken for an address"


def test_scrub_off_is_a_noop():
    line = "8.8.8.8 GET /a"
    assert scrub_ips_in_text(line, mode="off") == line


# --- End to end through the one ingest path ----------------------------------

class _StubGeo:
    """Records which address it was asked about, so the test can prove the lookup
    saw the real value and not the reduced one."""

    def __init__(self):
        self.asked: list[str] = []

    def prefetch_map(self, ips):
        self.asked = list(ips)
        return {ip: SimpleNamespace(iso_code="US", name="United States") for ip in ips}

    def country_for_ip(self, ip):  # pragma: no cover - prefetch path is used
        return SimpleNamespace(iso_code="US", name="United States")

    def close(self):
        pass


def _line(ip, path="/a", stamp="31/Jul/2026:10:00:00 +0000"):
    return f'{ip} - - [{stamp}] "GET {path} HTTP/1.1" 200 12 "-" "curl/8"'


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.delenv("SKOPOS_DATABASE_URL", raising=False)
    monkeypatch.delenv("SKOPOS_STORE_RAW_LINES", raising=False)
    monkeypatch.delenv("SKOPOS_IP_ANONYMIZE", raising=False)
    monkeypatch.delenv("SKOPOS_IP_HASH_SALT", raising=False)
    from skopos.db import connect, init_db

    con = connect(str(tmp_path / "t.sqlite3"))
    init_db(con)
    return con


def _one(con, sql, params=()):
    r = con.execute(sql, params).fetchone()
    return dict(r) if r is not None else None


def test_geo_is_resolved_on_the_full_address_then_the_row_is_reduced(db):
    from skopos.collector import ingest_lines
    from skopos.log_sources import LogSource

    geo = _StubGeo()
    src = LogSource(id="file:/var/log/nginx/access.log", kind="file", parser="nginx")
    ingest_lines(db, server_name="s", server_ip="10.0.0.1", lines=[(src, _line("8.8.8.8"))], geo=geo)

    assert "8.8.8.8" in geo.asked, "the geo lookup was handed a reduced address"
    row = _one(db, "SELECT remote_addr, country_code FROM http_requests")
    assert row["remote_addr"] == "8.8.8.0", "the stored address was not reduced"
    assert row["country_code"] == "US", "reducing the address broke the country lookup"


def test_hash_mode_via_env_keeps_two_visitors_as_two(db, monkeypatch):
    monkeypatch.setenv("SKOPOS_IP_ANONYMIZE", "hash")
    monkeypatch.setenv("SKOPOS_IP_HASH_SALT", "pepper")
    from skopos.collector import ingest_lines
    from skopos.log_sources import LogSource

    src = LogSource(id="file:/var/log/nginx/access.log", kind="file", parser="nginx")
    ingest_lines(
        db,
        server_name="s",
        server_ip="10.0.0.1",
        lines=[(src, _line("8.8.8.8", path="/a")), (src, _line("8.8.4.4", path="/b"))],
    )
    rows = db.execute("SELECT DISTINCT remote_addr FROM http_requests").fetchall()
    stored = {(r["remote_addr"] if db.backend == "postgresql" else r[0]) for r in rows}
    assert len(stored) == 2, "two visitors collapsed to one"
    assert all(v.startswith("h:") for v in stored), "an address was stored in the clear"


def test_stored_raw_line_carries_no_full_address(db, monkeypatch):
    # STORE_RAW_LINES is read into a module constant at import, so flip the
    # constant rather than the env the fixture already cleared.
    monkeypatch.setattr("skopos.db.STORE_RAW_LINES", True)
    from skopos.collector import ingest_lines
    from skopos.log_sources import LogSource

    src = LogSource(id="file:/var/log/nginx/access.log", kind="file", parser="nginx")
    ingest_lines(db, server_name="s", server_ip="10.0.0.1", lines=[(src, _line("8.8.8.8"))])

    row = _one(db, "SELECT line_raw, remote_addr FROM http_requests")
    assert row["line_raw"], "the raw line should be kept when the flag is set"
    assert "8.8.8.8" not in row["line_raw"], "the raw line kept the full address"
    assert "8.8.8.0" in row["line_raw"]


def test_off_mode_via_env_stores_the_full_address(db, monkeypatch):
    monkeypatch.setenv("SKOPOS_IP_ANONYMIZE", "off")
    from skopos.collector import ingest_lines
    from skopos.log_sources import LogSource

    src = LogSource(id="file:/var/log/nginx/access.log", kind="file", parser="nginx")
    ingest_lines(db, server_name="s", server_ip="10.0.0.1", lines=[(src, _line("8.8.8.8"))])
    row = _one(db, "SELECT remote_addr FROM http_requests")
    assert row["remote_addr"] == "8.8.8.8"


# --- Retention ---------------------------------------------------------------

def _stamp(days_ago):
    dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_ago)
    return dt.strftime("%d/%b/%Y:%H:%M:%S +0000")


def test_prune_drops_old_rows_and_keeps_recent(db):
    from skopos.collector import ingest_lines
    from skopos.db import prune_old_requests
    from skopos.log_sources import LogSource

    src = LogSource(id="file:/var/log/nginx/access.log", kind="file", parser="nginx")
    ingest_lines(
        db,
        server_name="s",
        server_ip="10.0.0.1",
        lines=[
            (src, _line("8.8.8.8", path="/old", stamp=_stamp(60))),
            (src, _line("8.8.4.4", path="/new", stamp=_stamp(1))),
        ],
    )
    assert _one(db, "SELECT COUNT(*) AS n FROM http_requests")["n"] == 2

    removed = prune_old_requests(db, 30)
    assert removed == 1, "retention removed the wrong number of rows"
    rows = db.execute("SELECT path FROM http_requests").fetchall()
    paths = {(r["path"] if db.backend == "postgresql" else r[0]) for r in rows}
    assert paths == {"/new"}, "retention kept the wrong row"


def test_retention_defaults_to_ninety_days(monkeypatch):
    # A deliberate privacy-by-default choice: absent any override, history is kept
    # for 90 days, not forever. Guard it so a refactor cannot silently revert it.
    monkeypatch.delenv("SKOPOS_HTTP_RETENTION_DAYS", raising=False)
    from skopos.config import AppConfig

    assert AppConfig(db_path="x").http_retention_days == 90


def test_prune_with_zero_keeps_everything(db):
    from skopos.collector import ingest_lines
    from skopos.db import prune_old_requests
    from skopos.log_sources import LogSource

    src = LogSource(id="file:/var/log/nginx/access.log", kind="file", parser="nginx")
    ingest_lines(db, server_name="s", server_ip="10.0.0.1", lines=[(src, _line("8.8.8.8", stamp=_stamp(999)))])
    before = _one(db, "SELECT COUNT(*) AS n FROM http_requests")["n"]
    assert prune_old_requests(db, 0) == 0
    assert _one(db, "SELECT COUNT(*) AS n FROM http_requests")["n"] == before


# --- Backfill of history -----------------------------------------------------

def test_backfill_reduces_addresses_already_stored(db, monkeypatch):
    monkeypatch.setenv("SKOPOS_IP_ANONYMIZE", "off")  # store full addresses first
    from skopos.collector import ingest_lines
    from skopos.log_sources import LogSource

    src = LogSource(id="file:/var/log/nginx/access.log", kind="file", parser="nginx")
    ingest_lines(
        db,
        server_name="s",
        server_ip="10.0.0.1",
        lines=[(src, _line("8.8.8.8", path="/a")), (src, _line("8.8.8.8", path="/b"))],
    )
    assert _one(db, "SELECT remote_addr FROM http_requests")["remote_addr"] == "8.8.8.8"

    changed = backfill_existing(db, mode="truncate")
    assert changed == 1, "one distinct address should have been rewritten"
    rows = db.execute("SELECT DISTINCT remote_addr FROM http_requests").fetchall()
    stored = {(r["remote_addr"] if db.backend == "postgresql" else r[0]) for r in rows}
    assert stored == {"8.8.8.0"}, "history still carries the full address"
