"""End-to-end tests for the push transport.

These drive the real ingest path — credential store, signature check, replay
guard, document validator and the shared enrich/dedup code — because the value
of the design is in how those fit together, not in any one of them.
"""

from __future__ import annotations

import base64
import json
import textwrap
import time

import pytest

from skopos import node_store
from skopos.config import load_config
from skopos.db import connect, init_db
from skopos.node_ingest import AuthError, IngestError, SeqConflict, handle_enroll, handle_report
from skopos.node_protocol import (
    HDR_NODE,
    HDR_SEQ,
    HDR_SIGNATURE,
    HDR_TIMESTAMP,
    PROTOCOL_VERSION,
    ProtocolError,
    compress,
    sign,
)
from skopos.node_report import parse_report

LINE = '203.0.113.9 - - [31/Jul/2026:10:00:00 +0000] "GET /a HTTP/1.1" 200 12 "-" "curl/8"'


@pytest.fixture
def fleet(tmp_path, monkeypatch):
    """Two configured servers — one push, one legacy — and an empty database."""
    monkeypatch.delenv("SKOPOS_NODE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SKOPOS_DATABASE_URL", raising=False)
    db = tmp_path / "t.sqlite3"
    cfg_path = tmp_path / "servers.yaml"
    cfg_path.write_text(textwrap.dedent(f"""
        db_path: "{db}"
        servers:
          - name: pushed
            source: ssh_nginx_access_log
            transport: agent-push
            address: 203.0.113.50
            nginx: {{access_log_path: /var/log/nginx/access.log}}
          - name: pulled
            source: ssh_nginx_access_log
            ssh: {{host: 203.0.113.10, user: skopos, key_path: /k/pulled}}
            nginx: {{access_log_path: /var/log/nginx/access.log}}
    """))
    cfg = load_config(str(cfg_path))
    con = connect(str(db))
    init_db(con)
    node_store.init_node_db(con)
    return type("Fleet", (), {"cfg": cfg, "db": str(db), "con": con})


def document(lines=(LINE,), **overrides):
    doc = {
        "protocol": PROTOCOL_VERSION,
        "agent_version": "1.0.0",
        "generated_at": int(time.time()),
        "sources": [{
            "id": "file:/var/log/nginx/access.log",
            "kind": "file",
            "parser": "nginx",
            "lines": list(lines),
        }],
    }
    doc.update(overrides)
    return doc


def signed(key_id, secret, doc, *, seq=1, timestamp=None, gzip_it=False):
    body = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
    headers = {}
    if gzip_it:
        body = compress(body)
        headers["Content-Encoding"] = "gzip"
    ts = int(time.time()) if timestamp is None else timestamp
    headers.update({
        HDR_NODE: key_id,
        HDR_TIMESTAMP: str(ts),
        HDR_SEQ: str(seq),
        HDR_SIGNATURE: sign(secret, key_id=key_id, timestamp=ts, seq=seq, body=body),
    })
    return headers, body


@pytest.fixture
def enrolled(fleet):
    ticket = node_store.create_ticket(fleet.con, "pushed")
    out = handle_enroll(fleet.cfg, {"ticket": ticket, "hostname": "web-1"})
    return out["key_id"], base64.b64decode(out["secret_b64"])


# --- Enrollment -------------------------------------------------------------

def test_a_ticket_can_only_be_used_once(fleet):
    ticket = node_store.create_ticket(fleet.con, "pushed")
    first = handle_enroll(fleet.cfg, {"ticket": ticket})
    assert first["server_name"] == "pushed"
    with pytest.raises(AuthError):
        handle_enroll(fleet.cfg, {"ticket": ticket})


def test_an_expired_ticket_is_refused(fleet):
    ticket = node_store.create_ticket(fleet.con, "pushed", ttl_minutes=-1)
    with pytest.raises(AuthError):
        handle_enroll(fleet.cfg, {"ticket": ticket})


def test_an_invented_ticket_is_refused(fleet):
    with pytest.raises(AuthError):
        handle_enroll(fleet.cfg, {"ticket": "et_not_a_real_ticket"})


def test_the_secret_is_never_stored_in_the_clear_when_a_key_is_configured(fleet, monkeypatch):
    monkeypatch.setenv("SKOPOS_NODE_SECRET_KEY", base64.b64encode(b"k" * 32).decode())
    ticket = node_store.create_ticket(fleet.con, "pushed")
    out = handle_enroll(fleet.cfg, {"ticket": ticket})
    row = fleet.con.execute(
        "SELECT secret_sealed FROM node_credentials WHERE key_id = ?", (out["key_id"],)
    ).fetchone()
    sealed = row["secret_sealed"] if isinstance(row, dict) else row[0]
    assert sealed.startswith("gcm:")
    assert out["secret_b64"] not in sealed
    # ...and it still round-trips.
    assert node_store.get_credential(fleet.con, out["key_id"]).secret == base64.b64decode(
        out["secret_b64"]
    )


# --- The happy path ---------------------------------------------------------

def test_a_signed_report_lands_as_rows(fleet, enrolled):
    key_id, secret = enrolled
    headers, body = signed(key_id, secret, document())
    result = handle_report(fleet.cfg, headers, body)

    assert result.server_name == "pushed"
    assert result.accepted == 1
    rows = fleet.con.execute(
        "SELECT server_name, remote_addr, status, log_source FROM http_requests"
    ).fetchall()
    assert len(rows) == 1
    row = dict(rows[0]) if isinstance(rows[0], dict) else {
        "server_name": rows[0][0], "remote_addr": rows[0][1],
        "status": rows[0][2], "log_source": rows[0][3],
    }
    # Re-parsed by SKOPOS from the raw line, not taken from the node.
    assert row["server_name"] == "pushed"
    assert row["remote_addr"] == "203.0.113.9"
    assert row["status"] == 200


def test_gzip_bodies_are_accepted(fleet, enrolled):
    key_id, secret = enrolled
    headers, body = signed(key_id, secret, document(), gzip_it=True)
    assert handle_report(fleet.cfg, headers, body).accepted == 1


def test_resending_the_same_lines_deduplicates(fleet, enrolled):
    key_id, secret = enrolled
    handle_report(fleet.cfg, *signed(key_id, secret, document(), seq=1))
    second = handle_report(fleet.cfg, *signed(key_id, secret, document(), seq=2))
    assert second.accepted == 0
    assert second.duplicates == 1


# --- Identity ---------------------------------------------------------------

def test_a_node_cannot_report_as_another_server(fleet, enrolled):
    key_id, secret = enrolled
    # The document has no field for this, so even naming it is a hard error.
    headers, body = signed(key_id, secret, document(server_name="pulled"))
    with pytest.raises(ProtocolError) as exc:
        handle_report(fleet.cfg, headers, body)
    assert "server_name" in str(exc.value)


def test_a_push_credential_cannot_write_into_a_pull_server(fleet):
    ticket = node_store.create_ticket(fleet.con, "pulled")
    out = handle_enroll(fleet.cfg, {"ticket": ticket})
    headers, body = signed(out["key_id"], base64.b64decode(out["secret_b64"]), document())
    with pytest.raises(IngestError) as exc:
        handle_report(fleet.cfg, headers, body)
    assert "not agent-push" in str(exc.value)


def test_the_node_cannot_supply_parsed_fields(fleet, enrolled):
    key_id, secret = enrolled
    doc = document()
    doc["sources"][0]["remote_addr"] = "10.0.0.1"
    headers, body = signed(key_id, secret, doc)
    with pytest.raises(ProtocolError):
        handle_report(fleet.cfg, headers, body)


# --- Authentication ---------------------------------------------------------

def test_a_tampered_body_is_refused(fleet, enrolled):
    key_id, secret = enrolled
    headers, body = signed(key_id, secret, document())
    tampered = body.replace(b"200", b"404")
    assert tampered != body
    with pytest.raises(AuthError):
        handle_report(fleet.cfg, headers, tampered)


def test_a_wrong_secret_is_refused(fleet, enrolled):
    key_id, _secret = enrolled
    headers, body = signed(key_id, b"z" * 32, document())
    with pytest.raises(AuthError):
        handle_report(fleet.cfg, headers, body)


def test_an_unknown_key_is_refused(fleet):
    headers, body = signed("nk_nope", b"z" * 32, document())
    with pytest.raises(AuthError):
        handle_report(fleet.cfg, headers, body)


def test_a_revoked_key_stops_working(fleet, enrolled):
    key_id, secret = enrolled
    assert node_store.revoke_credential(fleet.con, key_id) is True
    headers, body = signed(key_id, secret, document(), seq=5)
    with pytest.raises(AuthError):
        handle_report(fleet.cfg, headers, body)


@pytest.mark.parametrize("skew", [-4000, 4000])
def test_a_badly_skewed_clock_is_refused(fleet, enrolled, skew):
    key_id, secret = enrolled
    headers, body = signed(key_id, secret, document(), timestamp=int(time.time()) + skew)
    with pytest.raises(AuthError):
        handle_report(fleet.cfg, headers, body)


# --- Replay -----------------------------------------------------------------

def test_replaying_a_report_verbatim_is_refused(fleet, enrolled):
    key_id, secret = enrolled
    headers, body = signed(key_id, secret, document(), seq=1)
    handle_report(fleet.cfg, headers, body)
    with pytest.raises(SeqConflict) as exc:
        handle_report(fleet.cfg, headers, body)
    # The signature verified, so naming the next number tells this caller
    # nothing it could not compute — and lets it recover on its own.
    assert exc.value.next_seq == 2


def test_an_old_sequence_number_is_refused(fleet, enrolled):
    key_id, secret = enrolled
    handle_report(fleet.cfg, *signed(key_id, secret, document(), seq=10))
    headers, body = signed(key_id, secret, document(lines=("other",)), seq=9)
    with pytest.raises(SeqConflict) as exc:
        handle_report(fleet.cfg, headers, body)
    assert exc.value.next_seq == 11


def test_an_implausible_sequence_jump_is_refused(fleet, enrolled):
    key_id, secret = enrolled
    headers, body = signed(key_id, secret, document(), seq=999_999)
    with pytest.raises(AuthError) as exc:
        handle_report(fleet.cfg, headers, body)
    assert "jumped" in str(exc.value)


# --- Input bounds -----------------------------------------------------------

def test_a_line_with_a_nul_byte_is_dropped_not_fatal(fleet, enrolled):
    key_id, secret = enrolled
    headers, body = signed(key_id, secret, document(lines=(LINE, "bad\x00line")))
    result = handle_report(fleet.cfg, headers, body)
    assert result.accepted == 1
    assert result.rejected == 1


def test_an_absurd_byte_count_does_not_abort_the_batch(fleet, enrolled):
    key_id, secret = enrolled
    huge = '203.0.113.9 - - [31/Jul/2026:10:00:00 +0000] "GET /b HTTP/1.1" 200 99999999999999 "-" "x"'
    headers, body = signed(key_id, secret, document(lines=(LINE, huge)))
    assert handle_report(fleet.cfg, headers, body).accepted == 2
    stored = fleet.con.execute(
        "SELECT bytes_sent FROM http_requests WHERE path = '/b'"
    ).fetchone()
    value = stored["bytes_sent"] if isinstance(stored, dict) else stored[0]
    assert value is None, "an int4 overflow must be nulled, not stored"


def test_a_timestamp_from_the_future_is_not_believed(fleet, enrolled):
    key_id, secret = enrolled
    future = '203.0.113.9 - - [01/Jan/2099:00:00:00 +0000] "GET /c HTTP/1.1" 200 1 "-" "x"'
    headers, body = signed(key_id, secret, document(lines=(future,)))
    handle_report(fleet.cfg, headers, body)
    row = fleet.con.execute("SELECT ts_utc FROM http_requests WHERE path = '/c'").fetchone()
    value = row["ts_utc"] if isinstance(row, dict) else row[0]
    assert value is None, "a 2099 line would otherwise match every time window forever"


@pytest.mark.parametrize("bad_source", [
    "file:../../etc/shadow",
    "file:relative.log",
    "file:/etc/passwd; id",
    "docker:../evil",
    "nonsense:/var/log/x",
])
def test_source_ids_are_validated(fleet, enrolled, bad_source):
    key_id, secret = enrolled
    doc = document()
    doc["sources"][0]["id"] = bad_source
    headers, body = signed(key_id, secret, doc)
    with pytest.raises(ProtocolError):
        handle_report(fleet.cfg, headers, body)


def test_too_many_lines_is_refused():
    doc = document(lines=tuple("line %d" % i for i in range(20_001)))
    with pytest.raises(ProtocolError):
        parse_report(doc)


def test_an_unknown_protocol_version_is_refused():
    with pytest.raises(ProtocolError):
        parse_report(document(protocol=99))


def test_overlong_lines_are_truncated_not_rejected():
    report = parse_report(document(lines=("x" * 20_000,)))
    assert len(report.sources[0].lines[0].encode()) == 8 * 1024


def test_the_agents_own_gzip_is_what_the_server_inflates():
    """The agent uses gzip.compress; the server must speak the same framing.

    Bare zlib and gzip differ only in the header, so a mismatch survives every
    unit test that compresses and decompresses with the same helper — and then
    fails on the first real report with an opaque 500.
    """
    import gzip as _gzip

    from skopos.node_protocol import compress, decompress

    payload = b'{"protocol":1,"sources":[]}'
    # What the agent actually emits.
    assert decompress(_gzip.compress(payload, 6)) == payload
    # ...and our own helper agrees with it byte-for-byte in framing.
    assert _gzip.decompress(compress(payload)) == payload


def test_a_body_that_is_not_gzip_is_a_clean_rejection():
    from skopos.node_protocol import ProtocolError, decompress

    with pytest.raises(ProtocolError):
        decompress(b"this is not compressed at all")


def test_a_decompression_bomb_is_refused():
    import gzip as _gzip

    from skopos.node_protocol import ProtocolError, decompress

    bomb = _gzip.compress(b"\x00" * (64 * 1024 * 1024))
    with pytest.raises(ProtocolError):
        decompress(bomb)


def test_a_failed_ingest_burns_the_sequence_number(fleet, enrolled):
    """A server-side failure must not deadlock the node.

    The seq is claimed during authentication, so it is spent whatever happens
    afterwards. An agent that retried the same number would be told it was a
    replay — forever. This pins the server half of that contract: after a
    rejected ingest, seq N is gone and only N+1 works.
    """
    key_id, secret = enrolled

    # Authenticates, then fails validation: an unknown top-level field.
    bad = document()
    bad["totally_unexpected"] = 1
    with pytest.raises(ProtocolError):
        handle_report(fleet.cfg, *signed(key_id, secret, bad, seq=1))

    # Retrying with the same number is refused, with the number to use next...
    with pytest.raises(SeqConflict) as exc:
        handle_report(fleet.cfg, *signed(key_id, secret, document(), seq=1))
    assert exc.value.next_seq == 2

    # ...and moving on works, which is what the agent now does.
    assert handle_report(fleet.cfg, *signed(key_id, secret, document(), seq=2)).accepted == 1


def test_posture_ingest_is_rate_limited_not_run_every_report(fleet, enrolled):
    """Correlating knocks scans a week of history; hourly is enough.

    Doing it on every five-minute report turned a routine ingest into a gateway
    timeout on a host with millions of rows, for a reading nobody consumes more
    often than the scan interval.
    """
    key_id, secret = enrolled
    probe = "===META===\nhost-1\nLinux\nup 1 day\n===PORTS===\n===SSHD===\nPort 22\n"

    handle_report(fleet.cfg, *signed(key_id, secret, document(probe=probe), seq=1))
    first = fleet.con.execute("SELECT count(*) AS n FROM security_snapshots").fetchone()
    assert (first["n"] if isinstance(first, dict) else first[0]) == 1

    handle_report(fleet.cfg, *signed(key_id, secret, document(lines=("x",), probe=probe), seq=2))
    second = fleet.con.execute("SELECT count(*) AS n FROM security_snapshots").fetchone()
    assert (second["n"] if isinstance(second, dict) else second[0]) == 1, "a second snapshot was stored within the interval"


def test_a_pushed_snapshot_records_its_provenance(fleet, enrolled):
    key_id, secret = enrolled
    probe = "===META===\nhost-1\nLinux\nup 1 day\n===PORTS===\n"
    handle_report(fleet.cfg, *signed(key_id, secret, document(probe=probe), seq=1))
    row = fleet.con.execute("SELECT transport FROM security_snapshots").fetchone()
    value = row["transport"] if isinstance(row, dict) else row[0]
    # A host's word about its own health is worth less than a reading taken
    # independently, and the UI needs to be able to say which this was.
    assert value == "agent-push"


def test_a_flood_of_knock_events_is_bounded(fleet, enrolled, monkeypatch):
    """Enrichment resolves every distinct address in the knocks section.

    A node chooses that content outright, and 512 KiB of minimal "SRC=… DPT=…"
    lines is over twenty thousand addresses. Unbounded, one report becomes
    minutes of outbound lookups against a third-party service.
    """
    from skopos import node_ingest

    seen = []

    def counting_enrich(events, *, geo=None):
        seen.append(len(events))
        return []

    monkeypatch.setattr(node_ingest, "MAX_KNOCK_EVENTS_PER_REPORT", 50)
    import skopos.security.knock_analyzer as ka

    monkeypatch.setattr(ka, "enrich_knocks", counting_enrich)

    probe = "===META===\nhost-1\nLinux\nup 1 day\n===PORTS===\n"
    knocks = "===UFW===\n" + "\n".join(
        f"Jul 31 10:00:00 h kernel: [UFW BLOCK] SRC=203.0.113.{i % 254} DST=10.0.0.1 DPT={i}"
        for i in range(4000)
    )
    key_id, secret = enrolled
    handle_report(fleet.cfg, *signed(key_id, secret, document(probe=probe, knocks=knocks)))

    assert seen, "enrichment never ran"
    assert seen[0] <= 50 + 5, f"{seen[0]} events reached enrichment despite the cap"


def test_authentication_happens_before_work_is_admitted():
    """An unauthenticated peer must not be able to occupy an ingest slot.

    The expensive part of a report is admission-controlled by a two-slot
    semaphore. If that slot were taken before the signature was checked, anyone
    with a socket could hold both and stop the whole fleet reporting.
    """
    import inspect

    import api_server

    src = inspect.getsource(api_server.Handler._handle_node_report)
    auth_at = src.index("authenticate_request(")
    admit_at = src.index("_INGEST_SLOTS.acquire(")
    assert auth_at < admit_at, "the ingest slot is taken before the caller is known"


def test_the_ingest_entry_points_are_separable():
    """The split is what lets the caller authenticate first; keep it real."""
    from skopos.node_ingest import authenticate_request, ingest_authenticated

    assert callable(authenticate_request)
    assert callable(ingest_authenticated)
