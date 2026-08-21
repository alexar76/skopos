"""Redaction must remove secrets and cost the dashboard nothing.

Both halves are load-bearing. A control that leaks is useless; a control that
breaks the analytics an operator relies on gets switched off, and then it is also
useless. So these tests assert the removal *and* assert that everything the
dashboard groups by still arrives intact.
"""

from __future__ import annotations

import pytest

from skopos.redact import REDACTED, redact_path, redact_query, redact_referer


# --- What must be removed ---------------------------------------------------

@pytest.mark.parametrize("path", [
    "/reset?token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcdefghij",  # JWT
    "/w?api_key=" + "AKIA" + "IOSFODNN7EXAMPLE",  # named (AWS-docs shape, split for secret scanners)
    "/t?visitor_id=a3f9c2e1b7d4e5f60718",                            # tracking id
    "/u?email=someone@example.com",                                  # personal
    "/x?session=9f8e7d6c5b4a39281706",                               # session
    "/x?sig=a3f9c2e1b7d4e5f6a3f9c2e1b7d4e5f6",                       # signature
    "/s?q=eyJhbGciOiJIUzI1NiJ9aaaaaaaa",                             # pasted into search
    "/o?url=https%3A%2F%2Fa.example%3Ftoken%3DeyJhbGciOiJIUzI1NiJ9",  # nested
])
def test_secrets_do_not_survive(path):
    out = redact_path(path)
    assert REDACTED in out, f"{path} kept its secret"


def test_credentials_in_a_get_login_form_do_not_survive():
    """Measured on the live database: 14 rows carried exactly this shape.

    Short values, so only the *name* rule can catch them. The path is what the
    abuse detector reads, and it is untouched.
    """
    out = redact_path("/boaform/admin/formLogin?username=admin&psd=admin")
    assert out == f"/boaform/admin/formLogin?username={REDACTED}&psd={REDACTED}"


def test_a_traversal_probe_is_not_mistaken_for_a_credential():
    """``/etc/passwd`` is an attack signature, not anyone's password."""
    for probe in ("/..%2F..%2F..%2Fetc%2Fpasswd", "/.git-secret", "/config/secrets.yml"):
        assert redact_path(probe) == probe


def test_the_secret_itself_is_gone_not_just_marked():
    out = redact_path("/reset?token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcdefghij")
    assert "eyJhbGci" not in out


def test_a_referer_cannot_carry_a_reset_link():
    # The classic leak: the next request after a password reset carries the
    # whole reset URL in its Referer header.
    out = redact_referer("https://site.example/reset?token=abc123def456ghi789")
    assert out == "https://site.example"
    assert "token" not in out


# --- What must survive ------------------------------------------------------

@pytest.mark.parametrize("path", [
    "/api/v2/stats/live?mode=live&limit=80",   # measured: the two commonest params
    "/x?west=1953&service=metis&step=2",       # app-specific, non-identifying
    "/p?page=3&sort=desc&order=asc&lang=en",   # pagination and locale
    "/o?url=https%3A%2F%2Fa.example&lang=ru",  # a plain redirect target
    "/s?q=hello+world",                        # a real search term
    "/feed?_rsc=1a2b3",                        # framework marker
    "/l?utm_source=news&utm_campaign=spring",  # campaign attribution
])
def test_ordinary_analytics_parameters_are_untouched(path):
    assert redact_path(path) == path, "a dimension the dashboard groups by was destroyed"


@pytest.mark.parametrize("path", [
    "/wp-admin/setup-config.php",
    "/.env",
    "/phpmyadmin/index.php",
    "/admin/login",
])
def test_scan_paths_survive_for_bot_detection(path):
    # These drive an actual security feature; redacting them would blind it.
    assert redact_path(path) == path


def test_parameter_names_survive_even_when_values_do_not():
    # "which endpoints are being hit with a token" stays answerable.
    out = redact_path("/reset?token=eyJhbGciOiJIUzI1NiJ9aaaa&lang=ru")
    assert out == f"/reset?token={REDACTED}&lang=ru"


def test_a_path_without_a_query_is_returned_unchanged():
    assert redact_path("/a/b/c") == "/a/b/c"


@pytest.mark.parametrize("value", [None, "", 123])
def test_odd_inputs_do_not_raise(value):
    redact_path(value)
    redact_referer(value)


def test_malformed_query_fragments_pass_through():
    # A log line is not obliged to contain a well-formed query.
    assert redact_query("a&&b=") == "a&&b="
    assert redact_query("noequalshere") == "noequalshere"


# --- The end-to-end shape ---------------------------------------------------

def _row(con, sql, params=()):
    r = con.execute(sql, params).fetchone()
    return dict(r) if r is not None else None


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.delenv("SKOPOS_DATABASE_URL", raising=False)
    monkeypatch.delenv("SKOPOS_STORE_RAW_LINES", raising=False)
    from skopos.db import connect, init_db

    con = connect(str(tmp_path / "t.sqlite3"))
    init_db(con)
    return con


def _line(token, referer="https://news.example.com/reset?token=SECRETVALUE123456"):
    return (
        f'203.0.113.9 - - [31/Jul/2026:10:00:00 +0000] '
        f'"GET /reset?token={token}&lang=ru HTTP/1.1" 200 12 "{referer}" "curl/8"'
    )


def test_ingest_stores_no_secret_but_keeps_every_analytic(db):
    from skopos.collector import ingest_lines
    from skopos.log_sources import LogSource

    src = LogSource(id="file:/var/log/nginx/access.log", kind="file", parser="nginx")
    fetched, inserted = ingest_lines(
        db, server_name="s", server_ip="10.0.0.1",
        lines=[(src, _line("eyJhbGciOiJIUzI1NiJ9aaaaaaaaaaaa"))],
    )
    assert (fetched, inserted) == (1, 1)

    row = _row(db, "SELECT path, referer, referer_domain, request_raw, line_raw, "
                   "remote_addr, status, method, ua_browser FROM http_requests")

    # Gone.
    assert "eyJhbGci" not in (row["path"] or "")
    assert "SECRETVALUE" not in (row["referer"] or "")
    assert not row["line_raw"], "the verbatim line kept an unredacted copy"
    assert row["request_raw"] is None

    # Kept — every one of these is something the dashboard groups by.
    assert row["path"] == f"/reset?token={REDACTED}&lang=ru"
    assert row["referer_domain"] == "example.com", "referrer analysis broke"
    assert row["remote_addr"] == "203.0.113.9", "per-IP analytics broke"
    assert row["status"] == 200
    assert row["method"] == "GET"
    assert row["ua_browser"], "user-agent parsing broke"


def test_two_requests_differing_only_in_their_token_are_still_two_requests(db):
    """Redaction must not make distinct requests collide in deduplication.

    The hash is taken from the original line for exactly this reason: both lines
    redact to the same stored path, and hashing the stored form would silently
    drop the second request.
    """
    from skopos.collector import ingest_lines
    from skopos.log_sources import LogSource

    src = LogSource(id="file:/var/log/nginx/access.log", kind="file", parser="nginx")
    lines = [
        (src, _line("eyJhbGciOiJIUzI1NiJ9aaaaaaaaaaaa")),
        (src, _line("eyJhbGciOiJIUzI1NiJ9bbbbbbbbbbbb")),
    ]
    fetched, inserted = ingest_lines(db, server_name="s", server_ip="10.0.0.1", lines=lines)
    assert (fetched, inserted) == (2, 2), "distinct requests collapsed into one"

    # ...and a genuine repeat is still deduplicated.
    _f, again = ingest_lines(db, server_name="s", server_ip="10.0.0.1", lines=lines[:1])
    assert again == 0


def test_the_user_agent_length_clamp_actually_reaches_storage(db):
    """The clamp is a CPU guard on the UA regex corpus, and it once went dead.

    It was computed into a local and then left out of the merge dict, so
    ``pr.__dict__`` put the original unbounded string back. Nothing failed —
    the guard simply stopped guarding. This asserts the stored value, not the
    local.
    """
    from skopos.collector import ingest_lines
    from skopos.log_sources import LogSource

    huge = "Mozilla/5.0 " + "A" * 5000
    line = (
        '203.0.113.9 - - [31/Jul/2026:10:00:00 +0000] '
        f'"GET /ua HTTP/1.1" 200 12 "-" "{huge}"'
    )
    src = LogSource(id="file:/var/log/nginx/access.log", kind="file", parser="nginx")
    ingest_lines(db, server_name="ua", server_ip="10.0.0.1", lines=[(src, line)])

    row = _row(db, "SELECT user_agent FROM http_requests WHERE server_name = 'ua'")
    assert row is not None and row["user_agent"]
    assert len(row["user_agent"]) <= 512, "the clamp is not reaching storage"


def test_dropping_the_raw_line_does_not_collapse_repeated_probes(db):
    """Emptying line_raw promoted the summary line from fallback to normal case.

    The summary is the identity of a derived knock event — in the in-batch
    ``seen`` set and in the ``line_sha1`` dedup behind it. Without a timestamp,
    fifty scans from one address to one path produce fifty identical strings and
    collapse to a single event, so the actor's hit count on the Security page —
    which is what it ranks by — reads 1 instead of 50.
    """
    import datetime

    from skopos.collector import ingest_lines
    from skopos.log_sources import LogSource
    from skopos.security.knock_analyzer import http_probes_from_db

    src = LogSource(id="file:/var/log/nginx/access.log", kind="file", parser="nginx")
    now = datetime.datetime.now(datetime.timezone.utc)
    lines = []
    for i in range(50):
        stamp = (now - datetime.timedelta(minutes=i)).strftime("%d/%b/%Y:%H:%M:%S +0000")
        lines.append((src, (
            f'45.33.32.156 - - [{stamp}] '
            f'"GET /wp-admin/setup-config.php HTTP/1.1" 404 12 "-" "scanner"'
        )))

    ingest_lines(db, server_name="probe", server_ip="10.0.0.1", lines=lines)
    events = http_probes_from_db(db, "probe", hours=168)
    assert len(events) == 50, f"{len(events)} of 50 probes survived deduplication"
