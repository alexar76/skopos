"""The conductor's terminal-state push.

Two things are being defended here, and they pull in opposite directions: the summary must be
accepted by the REAL ingest (same headers, same signature, same seq discipline as any monitored
host), and the push must be so inconsequential that a dead dashboard cannot turn a successful
remediation into a failed one. So the happy path runs the actual server code, and every unhappy path
asserts that nothing escaped.
"""

from __future__ import annotations

import base64
import email.message
import io
import json
import textwrap
import time
import urllib.error

import pytest

from skopos.node_protocol import HDR_NODE, HDR_SEQ, HDR_SIGNATURE, HDR_TIMESTAMP, verify
from skopos.remediation.conductor import Conductor, RemediationConfig
from skopos.remediation.jobs import Job, JobState
from skopos.remediation.report_push import PushConfig, ReportPusher, job_summary

# The ingest half of the channel pulls in the dashboard's runtime (log parsing, UA and GeoIP
# enrichment), which the ecosystem's test interpreter does not carry. The signing half is stdlib only,
# so the wire contract is asserted against node_protocol.verify — the very function the server calls —
# and the tests that want a real credential row and a real stored board skip where the deps are absent.
SECRET = b"k" * 32

OPERATOR_TOKEN = "s3cr3t-operator-token-value"
PRIVATE_IP = "192.0.2.55"  # TEST-NET-1 — not a fleet host; mirror secret-gate safe
PRIVATE_URL = "https://skopos.internal:9402/hooks"
GATE_SIG = "Zm9yZ2Vkc2lnbmF0dXJlYmxvYg" * 4          # a full signature blob, ~104 chars
BLAME_SIG = "YmxhbWVzaWduYXR1cmU" * 6

#: The order-queue record for a published deploy order, as the conductor joins it in.
QUEUED = {
    "order_id": "deploy-mom-42-1754650000", "host": "oracle-family", "service": "oracle-family",
    "finding_id": "mom-42", "state": "reported", "claimed_by": "oracle-family",
    "claimed_at": "2026-08-08T12:00:45Z",
    "order": {"order_id": "deploy-mom-42-1754650000", "service": "oracle-family",
              "host": "oracle-family", "image": "oracle-family:patched-mom-42",
              "created_at": "2026-08-08T12:00:40Z", "conductor_pubkey": "Y29uZHVjdG9ycHVia2V5",
              "signature": {"value": "b3JkZXJzaWduYXR1cmU" * 5}},
    "result": {"deployed": True, "refused": False, "reason": "", "host": "oracle-family",
               "executed_at": "2026-08-08T12:01:00Z"},
}


# --- fixtures and stand-ins -------------------------------------------------

def _job(state: str = JobState.DONE.value, **overrides) -> Job:
    job = Job(finding_id="mom-42", component="oracle-family", probe="free_tier_ceiling_bypass",
              severity="high", route="auto", state=state, attempts=2,
              ticket={"finding_id": "mom-42", "component": "oracle-family", "target": "oracles",
                      "target_kind": "service", "operator_token": OPERATOR_TOKEN,
                      "blame": {"signature": {"value": BLAME_SIG}}},
              history=[{"ts": "2026-08-08T12:00:00Z", "state": "fixing", "note": "attempt 1"},
                       {"ts": "2026-08-08T12:01:00Z", "state": "done", "note": "verified in place"}],
              result={"deploy_order_id": "deploy-mom-42-1754650000",
                      "fix": {"ok": True, "patch": {"summary": "bounded the free tier",
                                                    "image": "oracle-family:patched-mom-42"}},
                      "gate_verdict": {"finding_id": "mom-42", "target": "oracles", "fixed": True,
                                       "outcome": "no_finding", "detail": "probe no longer reproduces",
                                       "checked_at": "2026-08-08T12:00:30Z",
                                       "verifier_pubkey": "bW9tdXNwdWJsaWNrZXk=",
                                       "signature": {"value": GATE_SIG}}})
    for key, value in overrides.items():
        setattr(job, key, value)
    return job


class _Response:
    """What the ingest answers with: counts and a server clock, nothing the pusher acts on."""

    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self, _n: int = -1) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> bool:
        return False


def _conflict(next_seq: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://skopos.test/node/v1/report", 409, "conflict", {},
        io.BytesIO(json.dumps({"error": "seq", "next_seq": next_seq}).encode("utf-8")))


class _FakeOpener:
    """Answers each call with the next scripted outcome: an exception is raised, a dict is a 200."""

    def __init__(self, *outcomes):
        self._outcomes = list(outcomes) or [{"ok": True}]
        self.calls: list = []

    def open(self, request, timeout=None):
        self.calls.append(request)
        outcome = self._outcomes[min(len(self.calls) - 1, len(self._outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return _Response(outcome)


def _server_headers(request) -> email.message.Message:
    """The request's headers as the real server sees them.

    urllib normalises names to ``X-skopos-node`` on the way out and ``http.server`` parses them into
    a case-insensitive ``email.Message`` on the way in, which is why the ingest's exact-case lookups
    work over a socket. Reproduce that rather than handing the ingest urllib's own dict.
    """
    message = email.message.Message()
    for name, value in request.header_items():
        message[name] = value
    return message


@pytest.fixture
def fleet(tmp_path, monkeypatch):
    """A real dashboard database with the conductor provisioned as an agent-push server."""
    pytest.importorskip("tldextract", reason="needs the dashboard's ingest dependencies")
    from skopos import node_store
    from skopos.config import load_config
    from skopos.db import connect, init_db
    from skopos.node_ingest import handle_enroll, handle_report

    monkeypatch.delenv("SKOPOS_NODE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SKOPOS_DATABASE_URL", raising=False)
    db = tmp_path / "t.sqlite3"
    cfg_path = tmp_path / "servers.yaml"
    cfg_path.write_text(textwrap.dedent(f"""
        db_path: "{db}"
        servers:
          - name: conductor
            source: ssh_nginx_access_log
            transport: agent-push
            address: 203.0.113.50
            nginx: {{access_log_path: /var/log/nginx/access.log}}
    """))
    cfg = load_config(str(cfg_path))
    con = connect(str(db))
    init_db(con)
    node_store.init_node_db(con)
    enrolled = handle_enroll(cfg, {"ticket": node_store.create_ticket(con, "conductor"),
                                   "hostname": "conductor"})

    class _SkoposIngest:
        """A stand-in for SKOPOS running the real authenticate + ingest over the pusher's bytes."""

        def __init__(self):
            self.calls: list = []

        def open(self, request, timeout=None):
            self.calls.append(request)
            result = handle_report(cfg, _server_headers(request), request.data)
            return _Response({"ok": True, "accepted": result.accepted,
                              "duplicate": result.duplicates, "rejected": result.rejected,
                              "server_time": int(time.time())})

    return type("Fleet", (), {"cfg": cfg, "con": con, "store": node_store,
                              "key_id": enrolled["key_id"], "secret_b64": enrolled["secret_b64"],
                              "ingest": _SkoposIngest()})


def _pusher(tmp_path, *, opener, key_id="nk_test", secret_b64=None, **overrides) -> ReportPusher:
    cfg = PushConfig(base_url="http://skopos.test", key_id=key_id,
                     secret_b64=secret_b64 or base64.b64encode(SECRET).decode(),
                     state_path=str(tmp_path / "push_state.json"), allow_plaintext=True,
                     **overrides)
    return ReportPusher(cfg, opener=opener)


def _pushed_summary(request) -> dict:
    doc = json.loads(request.data)
    assert doc["kind"] == "remediation" and len(doc["jobs"]) == 1
    return doc["jobs"][0]


# --- the happy path ---------------------------------------------------------

def test_a_terminal_job_pushes_a_signed_summary(tmp_path):
    opener = _FakeOpener({"ok": True, "accepted": 1, "server_time": int(time.time())})
    pusher = _pusher(tmp_path, opener=opener)

    out = pusher.push_job(_job(), conductor_pubkey="Y29uZHVjdG9ycHVia2V5", queued=QUEUED)

    assert out["pushed"] is True, out
    assert len(opener.calls) == 1
    request = opener.calls[0]
    assert request.full_url == "http://skopos.test/node/v1/report" and request.method == "POST"

    headers = {name.lower(): value for name, value in request.header_items()}
    # The four protocol headers, and a signature the SERVER's own verifier accepts over the exact
    # bytes on the wire. Identity is in the header and nowhere in the document.
    assert headers[HDR_NODE.lower()] == "nk_test" and headers[HDR_SEQ.lower()] == "1"
    assert verify(SECRET, headers[HDR_SIGNATURE.lower()], key_id="nk_test",
                  timestamp=int(headers[HDR_TIMESTAMP.lower()]), seq=1, body=request.data)
    assert headers["content-type"] == "application/json"
    assert "content-encoding" not in headers          # small summary: nothing to gain from gzip

    document = json.loads(request.data)
    assert document["agent_version"] == "skopos-conductor/1"
    # No server_name and no protocol/sources: identity comes from the credential, and this document
    # deliberately is not a log report, so PROTOCOL_VERSION and the deployed agents stay untouched.
    assert "server_name" not in document and "sources" not in document

    summary = _pushed_summary(request)
    assert summary["state"] == "done" and summary["attempts"] == 2
    assert summary["component"] == "oracle-family" and summary["target"] == "oracles"
    assert summary["probe"] == "free_tier_ceiling_bypass" and summary["severity"] == "high"
    assert summary["route"] == "auto" and summary["finding_id"] == "mom-42"
    assert [(h["ts"], h["state"], h["note"]) for h in summary["history"]] == [
        ("2026-08-08T12:00:00Z", "fixing", "attempt 1"),
        ("2026-08-08T12:01:00Z", "done", "verified in place")]
    gate = summary["gate_verdict"]
    assert gate["fixed"] is True and gate["outcome"] == "no_finding"
    assert gate["checked_at"] == "2026-08-08T12:00:30Z"
    assert gate["verifier_pubkey"] == "bW9tdXNwdWJsaWNrZXk="
    assert summary["deploy"]["order_id"] == "deploy-mom-42-1754650000"
    assert summary["deploy"]["conductor_pubkey"] == "Y29uZHVjdG9ycHVia2V5"
    assert summary["queue"]["state"] == "reported"
    assert summary["agent_result"]["deployed"] is True


def test_the_conductor_pubkey_travels_even_with_nothing_deployed(tmp_path):
    """An escalation never signs an order, and the board still has to say which conductor spoke."""
    summary = job_summary(_job(state=JobState.ESCALATED.value, result={}),
                          conductor_pubkey="Y29uZHVjdG9ycHVia2V5")
    assert summary["deploy"] == {"conductor_pubkey": "Y29uZHVjdG9ycHVia2V5"}
    assert "gate_verdict" not in summary and "queue" not in summary


def test_the_real_ingest_accepts_the_push_and_stores_the_board(fleet, tmp_path):
    """End to end against the actual server code: credential lookup, HMAC, replay guard, storage."""
    from skopos.node_remediation import recent_jobs

    pusher = _pusher(tmp_path, opener=fleet.ingest, key_id=fleet.key_id,
                     secret_b64=fleet.secret_b64)

    first = pusher.push_job(_job(), conductor_pubkey="Y29uZHVjdG9ycHVia2V5", queued=QUEUED)
    second = pusher.push_job(_job(state=JobState.ESCALATED.value))

    assert (first["pushed"], second["pushed"]) == (True, True), (first, second)
    assert (first["seq"], second["seq"]) == (1, 2)
    assert first["server"]["accepted"] == 1            # the receiver stored it, not just accepted it
    credential = fleet.store.get_credential(fleet.con, fleet.key_id)
    assert credential.last_seq == 2 and credential.server_name == "conductor"
    # Telemetry says which agent reported, so an operator can tell the conductor's pushes apart from a
    # monitored host's.
    row = fleet.con.execute(
        "SELECT agent_version, reports_total FROM node_credentials WHERE key_id = ?",
        (fleet.key_id,)).fetchone()
    assert (row["agent_version"], row["reports_total"]) == ("skopos-conductor/1", 2)

    board = recent_jobs(fleet.con)
    assert len(board) == 1                             # one row per finding, updated in place
    assert board[0]["finding_id"] == "mom-42" and board[0]["state"] == "escalated"
    assert board[0]["server_name"] == "conductor"      # from the credential, not the document
    assert board[0]["summary"]["history"][-1]["note"] == "verified in place"


# --- best-effort: nothing here may reach the caller -------------------------

def test_a_skopos_outage_is_logged_and_swallowed(tmp_path, caplog):
    opener = _FakeOpener(urllib.error.URLError("connection refused"))
    pusher = _pusher(tmp_path, opener=opener)
    out = pusher.push_job(_job())
    assert out["pushed"] is False and "URLError" in out["reason"]
    assert len(opener.calls) == 1                       # not retried: only a seq conflict is
    assert any("the job outcome stands" in r.message for r in caplog.records)


def test_a_401_is_swallowed_even_though_it_says_nothing(tmp_path):
    unauthorized = urllib.error.HTTPError(
        "https://skopos.test/node/v1/report", 401, "unauthorized", {},
        io.BytesIO(b'{"error":"unauthorized"}'))
    pusher = _pusher(tmp_path, opener=_FakeOpener(unauthorized))
    assert pusher.push_job(_job())["pushed"] is False


def test_an_unconfigured_pusher_is_a_silent_no_op(tmp_path):
    opener = _FakeOpener()
    pusher = ReportPusher(PushConfig(state_path=str(tmp_path / "s.json")), opener=opener)
    out = pusher.push_job(_job())
    assert out == {"pushed": False, "reason": "not configured"}
    assert not opener.calls and not (tmp_path / "s.json").exists()   # no seq burnt either


def test_a_non_terminal_job_is_not_pushed(tmp_path):
    opener = _FakeOpener()
    pusher = _pusher(tmp_path, opener=opener)
    out = pusher.push_job(_job(state=JobState.DEPLOYING.value))
    assert out["pushed"] is False and "not a terminal state" in out["reason"]
    assert not opener.calls


def test_a_plaintext_url_is_refused_rather_than_pushed_in_the_clear(tmp_path):
    opener = _FakeOpener()
    pusher = _pusher(tmp_path, opener=opener)
    pusher.cfg.allow_plaintext = False
    out = pusher.push_job(_job())
    assert out["pushed"] is False and "https" in out["reason"]
    assert not opener.calls


# --- seq conflicts ----------------------------------------------------------

def test_a_seq_conflict_is_retried_once_with_the_number_skopos_handed_back(tmp_path):
    opener = _FakeOpener(_conflict(7), {"ok": True})
    pusher = _pusher(tmp_path, opener=opener)

    out = pusher.push_job(_job())

    assert out["pushed"] is True and out["seq"] == 7
    assert len(opener.calls) == 2
    assert dict(opener.calls[1].header_items())["X-skopos-seq"] == "7"
    # Persisted before the retry went out, so a crash cannot re-spend the number.
    assert json.loads((tmp_path / "push_state.json").read_text())["seq"] == 7


def test_a_second_seq_conflict_gives_up_instead_of_looping(tmp_path):
    opener = _FakeOpener(_conflict(7), _conflict(8))
    pusher = _pusher(tmp_path, opener=opener)
    out = pusher.push_job(_job())
    assert out["pushed"] is False and out["reason"] == "seq conflict"
    assert len(opener.calls) == 2
    # The number is still taken: giving up on this summary must not leave the next one stuck behind
    # the same conflict.
    assert json.loads((tmp_path / "push_state.json").read_text())["seq"] == 8


def test_an_insane_next_seq_is_not_adopted(tmp_path):
    opener = _FakeOpener(_conflict(10**9), {"ok": True})
    pusher = _pusher(tmp_path, opener=opener)
    out = pusher.push_job(_job())
    assert out["pushed"] is False
    assert len(opener.calls) == 1
    assert json.loads((tmp_path / "push_state.json").read_text())["seq"] == 1


# --- redaction --------------------------------------------------------------

def test_redaction_removes_every_forbidden_field(tmp_path):
    opener = _FakeOpener({"ok": True})
    pusher = _pusher(tmp_path, opener=opener)
    job = _job(history=[
        {"ts": "2026-08-08T12:00:00Z", "state": "failed",
         "note": f"factory error: {PRIVATE_URL} refused; MOMUS_OPERATOR_TOKEN={OPERATOR_TOKEN}"},
        {"ts": "2026-08-08T12:01:00Z", "state": "deploying",
         "note": f"deploy rejected: the agent at {PRIVATE_IP}:9402 is unreachable"},
        {"ts": "2026-08-08T12:02:00Z", "state": "escalated",
         "note": f"MOMUS refused the re-test: Authorization: Bearer {OPERATOR_TOKEN}"},
    ])
    # A private registry in the image, an address in the agent's result, and the agent's own "host".
    queued = json.loads(json.dumps(QUEUED))
    queued["order"]["image"] = "registry.internal:5000/oracle-family:patched-mom-42"
    queued["host"] = queued["claimed_by"] = PRIVATE_IP
    queued["result"] = {"deployed": False, "refused": True, "host": PRIVATE_IP,
                        "reason": f"could not reach {PRIVATE_IP}"}

    out = pusher.push_job(job, conductor_pubkey="Y29uZHVjdG9ycHVia2V5", queued=queued)
    assert out["pushed"] is True
    body = opener.calls[0].data.decode("utf-8")

    assert OPERATOR_TOKEN not in body                  # the operator token, quoted in a note
    assert PRIVATE_IP not in body                      # a bare address, in a note and in the result
    assert "skopos.internal" not in body               # a private host, inside a url
    assert "registry.internal" not in body             # a private host, inside an image ref
    assert GATE_SIG not in body and BLAME_SIG not in body      # full signature blobs
    assert QUEUED["order"]["signature"]["value"] not in body   # including the conductor's own
    # And the raw MOMUS ticket is not there at all — not its keys, not its blame attestation.
    assert "operator_token" not in body and "target_kind" not in body and "blame" not in body

    summary = _pushed_summary(opener.calls[0])
    # What survives is what a human needs to correlate: a signature PREFIX, both public keys, and the
    # repository and tag with the registry host taken off.
    assert summary["gate_verdict"]["signature"] == GATE_SIG[:20]
    assert summary["gate_verdict"]["verifier_pubkey"] == "bW9tdXNwdWJsaWNrZXk="
    assert summary["deploy"]["conductor_pubkey"] == "Y29uZHVjdG9ycHVia2V5"
    assert summary["deploy"]["signature"] == QUEUED["order"]["signature"]["value"][:20]
    assert summary["deploy"]["image"] == "<registry>/oracle-family:patched-mom-42"
    assert "<url>" in summary["history"][0]["note"] and "<ip>" in summary["history"][1]["note"]
    assert summary["queue"]["claimed_by"] == "<ip>"
    assert "host" not in summary["deploy"] and "host" not in summary["agent_result"]


def test_only_the_newest_slice_of_a_long_history_is_sent(tmp_path):
    """The conductor's jobs.jsonl stays the authority; the pushed copy is a bounded mirror."""
    job = _job(history=[{"ts": f"2026-08-08T12:{n:02d}:00Z", "state": "fixing", "note": f"n={n}"}
                        for n in range(30)])
    history = job_summary(job)["history"]
    assert len(history) == 20 and history[0]["note"] == "n=10" and history[-1]["note"] == "n=29"


def test_a_timestamp_is_not_mistaken_for_an_address(tmp_path):
    """The IPv6 filter has to leave ``12:00:00`` alone, or every ts and checked_at is mangled."""
    summary = job_summary(_job())
    assert summary["history"][0]["ts"] == "2026-08-08T12:00:00Z"
    assert summary["gate_verdict"]["checked_at"] == "2026-08-08T12:00:30Z"


# --- the wiring -------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_conductor_pushes_once_when_a_job_reaches_done(tmp_path, monkeypatch):
    from oracle_core.signing import Signer
    from tests.test_remediation import _momus_fixed_verdict

    conductor = Conductor(RemediationConfig(data_dir=str(tmp_path / "rem"),
                                            conductor_key_path=str(tmp_path / "rem" / "cond.key"),
                                            dry_run=True, max_attempts=3))
    momus = Signer(str(tmp_path / "momus.key"))

    async def fixed(finding_id):
        return _momus_fixed_verdict(momus, finding_id=finding_id, fixed=True)
    monkeypatch.setattr(conductor.momus, "retest", fixed)

    pushes: list[tuple] = []
    conductor.reporter.cfg.base_url = "https://skopos.test"
    monkeypatch.setattr(conductor.reporter, "push_job",
                        lambda job, **kw: pushes.append((job.state, kw)) or {"pushed": True})

    job = await conductor.handle_ticket({"finding_id": "mom-42", "component": "oracle-family",
                                         "probe": "p", "severity": "high", "route": "auto"})
    assert job.state == JobState.DONE.value
    assert [state for state, _ in pushes] == ["done"]          # once, at the terminal transition
    assert pushes[0][1]["conductor_pubkey"] == conductor.conductor_pubkey
    # The signed order, joined from the queue: without it the summary would stop at "MOMUS says fixed".
    queued = pushes[0][1]["queued"]
    assert queued["order_id"] == job.result["deploy_order_id"] and queued["state"] == "pending"


@pytest.mark.asyncio
async def test_the_conductor_pushes_an_escalation_too(tmp_path, monkeypatch):
    conductor = Conductor(RemediationConfig(data_dir=str(tmp_path / "rem"),
                                            conductor_key_path=str(tmp_path / "rem" / "cond.key"),
                                            dry_run=True))
    pushes: list[str] = []
    conductor.reporter.cfg.base_url = "https://skopos.test"
    monkeypatch.setattr(conductor.reporter, "push_job",
                        lambda job, **kw: pushes.append(job.state) or {"pushed": True})

    job = await conductor.handle_ticket({"finding_id": "mom-9", "component": "momus", "probe": "x",
                                         "severity": "critical", "route": "auto"})
    assert job.state == JobState.ESCALATED.value and pushes == ["escalated"]


@pytest.mark.asyncio
async def test_a_terminal_job_still_reports_done_when_the_push_fails(tmp_path, monkeypatch):
    """The whole point of the feature being best-effort: a dashboard outage is not a failed fix."""
    from oracle_core.signing import Signer
    from tests.test_remediation import _momus_fixed_verdict

    conductor = Conductor(RemediationConfig(data_dir=str(tmp_path / "rem"),
                                            conductor_key_path=str(tmp_path / "rem" / "cond.key"),
                                            dry_run=True))
    momus = Signer(str(tmp_path / "momus.key"))

    async def fixed(finding_id):
        return _momus_fixed_verdict(momus, finding_id=finding_id, fixed=True)
    monkeypatch.setattr(conductor.momus, "retest", fixed)

    attempted: list[str] = []

    def exploding_push(job, **_kw):
        attempted.append(job.state)
        raise RuntimeError("SKOPOS is down and the pusher itself is broken")
    conductor.reporter.cfg.base_url = "https://skopos.test"
    monkeypatch.setattr(conductor.reporter, "push_job", exploding_push)

    job = await conductor.handle_ticket({"finding_id": "mom-77", "component": "oracle-family",
                                         "probe": "p", "severity": "high", "route": "auto"})
    assert attempted == ["done"]                       # it really did try
    assert job.state == JobState.DONE.value            # and the outcome stands
    assert job.result["gate_verdict"]["fixed"] is True
