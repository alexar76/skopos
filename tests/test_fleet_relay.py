"""The remediation front door, so a hand on another machine needs no hole opened for it.

The loop is single-host by construction — the conductor and Gitea are bound to loopback on
purpose — so a deploy hand on another server has nothing to talk to. Publishing those two would
expose the most sensitive services in the loop. The relay is the other way round: both sides
speak outbound to a host that is already public and already the fleet agents' front door.

The relay is trusted with NOTHING. It never signs, never decides, never holds a key. These tests
pin that: what it refuses to carry, that an order is handed out once, and that tampering is
something the hand catches rather than something the relay is trusted not to do.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from skopos.remediation.fleet_relay import (  # noqa: E402
    BRANCH_PREFIX, RelayStore, _branch_is_acceptable, apply_bundle,
)


class TestWhatTheRelayWillCarry:
    @pytest.mark.parametrize("branch", ["momus/fix-mom-a1b2", "momus/fix-x", BRANCH_PREFIX + "1"])
    def test_a_machine_authored_branch_is_accepted(self, branch):
        assert _branch_is_acceptable(branch)

    @pytest.mark.parametrize("branch", [
        # `main` is NOT here: the trunk is carried once so every fix branch after it is
        # incremental. Holding it is not permission to build it — see TestTheBaseBranchIsCarriedOnce.
        "master", "momus/canary", "", "refs/heads/momus/fix-a",
        "momus/fix-../../etc/passwd", "momus/fix-a//b", "momus/fix-" + "x" * 300,
        "momus/fix-a b", "momus/fix-a;rm -rf /", "momus/fix-a\nb",
    ])
    def test_anything_else_is_refused(self, branch):
        """A courier that will carry anything is a courier worth attacking. The prefix is checked
        here as well as on the hand — the two protect different things: the hand protects the host
        it deploys to, the relay protects what it is willing to store and serve at all."""
        assert not _branch_is_acceptable(branch)


class TestAnOrderIsHandedOutOnce:
    def test_a_second_poll_gets_nothing(self):
        """A replayed poll must not re-run a deploy."""
        store = RelayStore()
        store.put_order("hub", "ord-1", {"kind": "build"})
        assert store.claim("hub")["order_id"] == "ord-1"
        assert store.claim("hub") is None

    def test_the_forwarder_may_retry_without_queueing_twice(self):
        """The courier retries on a network wobble; the hand must not then deploy twice."""
        store = RelayStore()
        store.put_order("hub", "ord-1", {"kind": "build"})
        store.put_order("hub", "ord-1", {"kind": "build"})
        assert store.claim("hub") is not None
        assert store.claim("hub") is None

    def test_hosts_do_not_see_each_others_orders(self):
        store = RelayStore()
        store.put_order("hub", "ord-hub", {"kind": "build"})
        store.put_order("gaia", "ord-gaia", {"kind": "build"})
        assert store.claim("gaia")["order_id"] == "ord-gaia"
        assert store.claim("hub")["order_id"] == "ord-hub"

    def test_a_stale_order_is_dropped_rather_than_executed_late(self, monkeypatch):
        import skopos.remediation.fleet_relay as relay

        store = relay.RelayStore()
        store.put_order("hub", "old", {"kind": "build"})
        # Far enough ahead that the TTL has certainly passed. 10**9 is the year 2001 —
        # earlier than now, so the age came out negative and the order looked fresh.
        monkeypatch.setattr(relay.time, "time", lambda: 10**12)
        assert store.claim("hub") is None


class TestACapturedOrderCannotBeReplayed:
    """`claim()`'s docstring said "a claimed order is never re-served, so a replayed poll
    cannot re-run a deploy". That was only true INSIDE the live queue: `put_order`
    de-duplicated against the current queue only, so once an order was popped the same
    order_id could be pushed back and served again.

    The relay's token is fleet-wide — every remote deploy hand holds it (it is accepted as
    `x-agent-token`) — and `host` is a plain query parameter bound to nothing. So a token
    holder could claim another host's pending order (silently denying that host its repair),
    keep the genuine conductor-signed order with its embedded MOMUS `fixed` verdict, and
    re-inject it later, at any host, as often as it liked.
    """

    def test_a_claimed_order_id_cannot_be_queued_again(self):
        store = RelayStore()
        store.put_order("hub", "ord-1", {"kind": "build", "host": "hub"})
        assert store.claim("hub")["order_id"] == "ord-1"
        store.put_order("hub", "ord-1", {"kind": "build", "host": "hub"})
        assert store.claim("hub") is None, "a spent order was re-served"

    def test_a_captured_order_cannot_be_re_aimed_at_another_host(self):
        """The order carries its target host INSIDE the conductor's signature; honour it."""
        store = RelayStore()
        store.put_order("victim", "ord-x", {"kind": "deploy", "host": "victim"})
        assert store.claim("victim") is not None
        # Same signed order, pointed somewhere else.
        store.put_order("attacker-host", "ord-x", {"kind": "deploy", "host": "victim"})
        assert store.claim("attacker-host") is None

    def test_a_queue_host_that_disagrees_with_the_signed_host_is_refused(self):
        store = RelayStore()
        store.put_order("gaia", "ord-y", {"kind": "deploy", "host": "hub"})
        assert store.claim("gaia") is None, "queued under a host the order does not name"

    def test_an_order_older_than_the_freshness_window_is_never_queued(self, monkeypatch):
        """Capture now, replay next month: bound it with the order's own signed created_at."""
        import skopos.remediation.fleet_relay as relay

        store = relay.RelayStore()
        store.put_order("hub", "ord-old", {
            "kind": "deploy", "host": "hub", "created_at": "2020-01-01T00:00:00Z",
        })
        assert store.claim("hub") is None

    def test_a_fresh_order_with_a_created_at_still_goes_through(self):
        import time as _t

        import skopos.remediation.fleet_relay as relay

        store = relay.RelayStore()
        store.put_order("hub", "ord-new", {
            "kind": "deploy", "host": "hub",
            "created_at": _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime()),
        })
        assert store.claim("hub") is not None

    def test_an_order_with_no_host_field_is_still_carried(self):
        """Build orders in the existing tests carry no host; do not break them."""
        store = RelayStore()
        store.put_order("hub", "ord-b", {"kind": "build"})
        assert store.claim("hub") is not None


class TestTheBodyReaderDoesNotBelieveTheHeaders:
    """`int(Content-Length)` accepts "-1", and `rfile.read(-1)` reads to EOF.

    The sibling reader in api_server.py already documents this exact trap and validates the
    header; the relay's did not, so MAX_BODY_BYTES (1 GiB) was not enforced at all and a
    non-numeric value raised ValueError out of the handler. Post-auth, but the relay's token
    is held by every deploy hand — and this is the fleet's healing front door.
    """

    @staticmethod
    def _reader(content_length, body=b""):
        import io

        from skopos.remediation.fleet_relay import RelayStore, make_handler

        handler_cls = make_handler(RelayStore())
        sent = []

        class Fake(handler_cls):
            def __init__(self):  # bypass BaseHTTPRequestHandler's socket setup
                self.headers = {"content-length": content_length}
                self.rfile = io.BytesIO(body)

            def _send(self, code, payload):
                sent.append((code, payload))

        return Fake(), sent

    def test_a_negative_content_length_is_refused_not_read_to_eof(self):
        handler, sent = self._reader("-1", b"x" * 5000)
        out = handler._body(1024)
        assert out in (None, b""), "read past the cap on a negative Content-Length"
        assert sent and sent[0][0] == 400, sent

    def test_a_non_numeric_content_length_is_answered_not_raised(self):
        handler, sent = self._reader("abc", b"x")
        out = handler._body(1024)
        assert out in (None, b"")
        assert sent and sent[0][0] == 400, sent

    def test_an_oversized_body_is_refused_once(self):
        handler, sent = self._reader("5000", b"x" * 5000)
        out = handler._body(1024)
        assert out is None, "413 must signal the caller to stop, not look like an empty body"
        assert sent == [(413, {"error": "payload too large"})], sent

    def test_a_body_longer_than_it_claims_is_truncated_at_the_cap(self):
        handler, sent = self._reader("10", b"y" * 10_000)
        out = handler._body(1024)
        assert out == b"y" * 10, out

    def test_a_normal_body_still_reads(self):
        handler, sent = self._reader("5", b"hello world")
        assert handler._body(1024) == b"hello"
        assert sent == []


class TestResultsSurviveTheCourier:
    def test_a_result_is_drained_once(self, tmp_path):
        store = RelayStore(str(tmp_path / "results.jsonl"))
        store.put_result("ord-1", {"deployed": True})
        assert len(store.drain_results()) == 1
        assert store.drain_results() == []

    def test_a_result_is_journalled_because_losing_it_loses_the_only_record(self, tmp_path):
        """Losing an ORDER is safe — the conductor republishes. Losing a RESULT loses the only
        record that a deploy happened at all."""
        journal = tmp_path / "results.jsonl"
        store = RelayStore(str(journal))
        store.put_result("ord-1", {"deployed": True, "host": "hub"})
        store.drain_results()
        written = [json.loads(line) for line in journal.read_text().splitlines()]
        assert written and written[0]["order_id"] == "ord-1"


def _git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


@pytest.fixture()
def source_repo(tmp_path):
    """A repo with one machine-authored branch, bundled the way the forwarder bundles it."""
    if subprocess.run(["git", "--version"], capture_output=True).returncode != 0:
        pytest.skip("git unavailable")
    work = tmp_path / "work"
    work.mkdir()
    _git("init", "-q", "-b", "main", str(work))
    _git("config", "user.email", "t@example.test", cwd=work)
    _git("config", "user.name", "t", cwd=work)
    (work / "f.txt").write_text("one\n")
    _git("add", "-A", cwd=work)
    _git("commit", "-qm", "one", cwd=work)
    _git("checkout", "-qb", "momus/fix-mom-1", cwd=work)
    (work / "f.txt").write_text("two\n")
    _git("commit", "-aqm", "fix", cwd=work)
    sha = _git("rev-parse", "HEAD", cwd=work).stdout.strip()
    bundle = tmp_path / "b.bundle"
    _git("bundle", "create", str(bundle), "refs/heads/momus/fix-mom-1", cwd=work)
    return {"bundle": str(bundle), "sha": sha, "work": work}


class TestTheSourceItServes:
    def test_a_bundle_becomes_a_repository_a_hand_can_fetch(self, source_repo, tmp_path):
        """The hand fetches with stock git and must stay unchanged — the code that decides
        whether a commit may be built is the last place to introduce a special case."""
        repo = str(tmp_path / "relay.git")
        ok, note = apply_bundle(source_repo["bundle"], "momus/fix-mom-1", repo)
        assert ok, note
        mirror = tmp_path / "hand.git"
        assert _git("clone", "--bare", "-q", repo, str(mirror)).returncode == 0
        tip = _git("-C", str(mirror), "rev-parse", "refs/heads/momus/fix-mom-1").stdout.strip()
        assert tip == source_repo["sha"]

    def test_dumb_http_metadata_is_written(self, source_repo, tmp_path):
        """Without `update-server-info` a fetch over plain HTTP sees a repository frozen at the
        last time somebody remembered to run it."""
        repo = Path(tmp_path / "relay.git")
        assert apply_bundle(source_repo["bundle"], "momus/fix-mom-1", str(repo))[0]
        assert (repo / "info" / "refs").is_file()

    def test_a_branch_outside_the_prefix_is_refused_before_anything_is_unpacked(
            self, source_repo, tmp_path):
        ok, note = apply_bundle(source_repo["bundle"], "master", str(tmp_path / "relay.git"))
        assert not ok and "branch name" in note

    def test_a_corrupt_bundle_is_refused_by_git_itself(self, tmp_path):
        bad = tmp_path / "bad.bundle"
        bad.write_bytes(b"not a bundle")
        ok, note = apply_bundle(str(bad), "momus/fix-x", str(tmp_path / "relay.git"))
        assert not ok and "verification" in note


class TestTheGitDoorIsReadOnlyAndBounded:
    """The hand fetches with stock git, so the relay serves a plain repository over dumb HTTP.

    That door is the one thing on the relay that touches the filesystem, so it gets the same
    treatment as any other path-from-a-caller: resolved and compared, never inspected as a string.
    """

    def _handler(self, tmp_path, monkeypatch, token="t"):
        import skopos.remediation.fleet_relay as relay

        monkeypatch.setenv("SKOPOS_RELAY_TOKEN", token)
        monkeypatch.setenv("SKOPOS_RELAY_REPO", str(tmp_path / "aicom.git"))
        handler_cls = relay.make_handler(relay.RelayStore())

        class Probe(handler_cls):  # type: ignore[misc,valid-type]
            def __init__(self):  # noqa: D107 - no socket; we only exercise the helpers
                self.sent: list = []
                self.headers = {}

            def send_response(self, code, *a):
                self.sent.append(("status", code))

            def send_header(self, *a):
                pass

            def end_headers(self):
                pass

            @property
            def wfile(self):
                outer = self

                class _W:
                    def write(self, data):
                        outer.sent.append(("body", data))

                return _W()

        return Probe

    def test_a_traversal_out_of_the_repo_is_a_404(self, tmp_path, monkeypatch):
        repo = tmp_path / "aicom.git"
        (repo / "info").mkdir(parents=True)
        (repo / "info" / "refs").write_text("ref\n")
        secret = tmp_path / "secret.txt"
        secret.write_text("do not serve me")

        probe = self._handler(tmp_path, monkeypatch)()
        probe.headers = {"x-relay-token": "t"}
        probe._serve_git("aicom.git/../secret.txt")
        assert ("status", 404) in probe.sent
        assert not any(kind == "body" for kind, _ in probe.sent)

    def test_a_real_file_inside_the_repo_is_served(self, tmp_path, monkeypatch):
        repo = tmp_path / "aicom.git"
        (repo / "info").mkdir(parents=True)
        (repo / "info" / "refs").write_text("abc refs/heads/momus/fix-1\n")

        probe = self._handler(tmp_path, monkeypatch)()
        probe.headers = {"x-relay-token": "t"}
        probe._serve_git("aicom.git/info/refs")
        assert ("status", 200) in probe.sent
        assert any(b"refs/heads/momus/fix-1" in data for kind, data in probe.sent if kind == "body")

    def test_without_a_token_git_is_asked_to_authenticate(self, tmp_path, monkeypatch):
        probe = self._handler(tmp_path, monkeypatch)()
        probe.headers = {}
        probe._serve_git("aicom.git/info/refs")
        assert ("status", 401) in probe.sent

    def test_basic_auth_is_accepted_because_git_cannot_send_a_custom_header(self, tmp_path,
                                                                            monkeypatch):
        import base64

        repo = tmp_path / "aicom.git"
        (repo / "info").mkdir(parents=True)
        (repo / "info" / "refs").write_text("x\n")
        probe = self._handler(tmp_path, monkeypatch)()
        creds = base64.b64encode(b"hand:t").decode()
        probe.headers = {"authorization": f"Basic {creds}"}
        probe._serve_git("aicom.git/info/refs")
        assert ("status", 200) in probe.sent

    def test_a_wrong_basic_password_is_refused(self, tmp_path, monkeypatch):
        import base64

        probe = self._handler(tmp_path, monkeypatch)()
        probe.headers = {"authorization": "Basic " + base64.b64encode(b"hand:wrong").decode()}
        probe._serve_git("aicom.git/info/refs")
        assert ("status", 401) in probe.sent


class TestOneSecretThreeSpellings:
    """The forwarder sends `X-Relay-Token`; the hand — the same program that talks to the
    conductor — sends `X-Agent-Token`; git can send neither and sends HTTP Basic. One secret."""

    def _probe(self, tmp_path, monkeypatch, headers):
        import skopos.remediation.fleet_relay as relay

        monkeypatch.setenv("SKOPOS_RELAY_TOKEN", "t")
        handler_cls = relay.make_handler(relay.RelayStore())

        class Probe(handler_cls):  # type: ignore[misc,valid-type]
            def __init__(self):
                self.headers = headers

        return Probe()

    def test_the_couriers_header(self, tmp_path, monkeypatch):
        assert self._probe(tmp_path, monkeypatch, {"x-relay-token": "t"})._supplied_token() == "t"

    def test_the_hands_header(self, tmp_path, monkeypatch):
        assert self._probe(tmp_path, monkeypatch, {"x-agent-token": "t"})._supplied_token() == "t"

    def test_gits_basic_auth(self, tmp_path, monkeypatch):
        import base64

        creds = base64.b64encode(b"hand:t").decode()
        probe = self._probe(tmp_path, monkeypatch, {"authorization": f"Basic {creds}"})
        assert probe._supplied_token() == "t"

    def test_nothing_at_all(self, tmp_path, monkeypatch):
        assert self._probe(tmp_path, monkeypatch, {})._supplied_token() == ""


class TestTheBaseBranchIsCarriedOnce:
    """Without a trunk on the relay, the FIRST remediation pays for the whole history — and it
    pays during an incident, which is the worst possible moment."""

    def test_the_trunk_is_accepted(self, monkeypatch):
        monkeypatch.delenv("SKOPOS_RELAY_BASE_BRANCH", raising=False)
        assert _branch_is_acceptable("main")

    def test_it_is_configurable(self, monkeypatch):
        monkeypatch.setenv("SKOPOS_RELAY_BASE_BRANCH", "trunk")
        assert _branch_is_acceptable("trunk")
        assert not _branch_is_acceptable("main")

    def test_nothing_else_slips_in_alongside_it(self, monkeypatch):
        monkeypatch.delenv("SKOPOS_RELAY_BASE_BRANCH", raising=False)
        for branch in ("master", "develop", "momus/canary", "main-ish", "release/1"):
            assert not _branch_is_acceptable(branch), branch

    def test_holding_the_trunk_is_not_permission_to_build_it(self, monkeypatch):
        """The relay stores it; the hand builds the commit an ORDER names, and an order names a
        machine-authored branch. Storage and buildability are different questions."""
        from skopos.remediation.recipes import DEFAULT_BUILD_RECIPES  # noqa: F401
        import skopos.remediation.node_agent as na

        monkeypatch.delenv("SKOPOS_AGENT_BRANCH_PREFIXES", raising=False)
        assert na.NodeAgentConfig.from_env().branch_prefixes == ("momus/fix-",)
