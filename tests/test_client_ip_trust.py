"""The budget/lockout key must be the caller, never a value the caller can choose.

The nginx in front of SKOPOS sets BOTH headers:

    proxy_set_header X-Real-IP $remote_addr;                      # overwritten by nginx
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;  # APPENDS to the client's

`$proxy_add_x_forwarded_for` appends the real peer to the RIGHT of whatever the client sent,
so the LEFT-most hop is fully attacker-chosen. Both readers took the left-most hop first:

* `skopos.app_auth._client_ip` keys the DB-persisted login lockout
  (`register_failed_login` / `login_lockout_remaining_seconds`, 5 attempts -> 300s). A fresh
  spoofed value per attempt puts every guess in a new bucket, so the lockout never fires and
  the operator dashboard password — which gates server inventory, SSH config, enrolment
  tickets and the remediation board — is open to unmetered online guessing.
* `api_server._peer_ip` keys the `/agent/chat` LLM-spend limiter, which exists so a stolen
  agent token cannot burn unbounded paid LLM calls. A new header value per request means a
  fresh empty bucket every time.

ATLAS already had the right shape (`atlas/atlas/main.py:_client_ip`): trust proxy headers
only when the direct peer IS the local proxy, prefer X-Real-IP, and count XFF from the
RIGHT. These tests pin that shape here.
"""

from __future__ import annotations

import pytest


class _Ctx:
    def __init__(self, headers):
        self.headers = headers


# --- the Streamlit dashboard login lockout key ---------------------------------------

def _client_ip_with(monkeypatch, headers):
    from skopos import app_auth

    monkeypatch.setattr(app_auth.st, "context", _Ctx(headers), raising=False)
    return app_auth._client_ip()


def test_login_lockout_key_ignores_a_client_supplied_left_hop(monkeypatch):
    """nginx appended the truth on the right; the left value is the attacker's."""
    got = _client_ip_with(monkeypatch, {
        "X-Forwarded-For": "1.2.3.4, 203.0.113.9",
        "X-Real-IP": "203.0.113.9",
    })
    assert got == "203.0.113.9", (
        f"lockout keyed on {got!r}; an attacker rotating that header gets unlimited guesses"
    )


def test_login_lockout_key_is_stable_across_rotated_spoofs(monkeypatch):
    """The property that actually matters: the key must not move when the header does."""
    keys = {
        _client_ip_with(monkeypatch, {
            "X-Forwarded-For": f"10.0.0.{n}, 203.0.113.9",
            "X-Real-IP": "203.0.113.9",
        })
        for n in range(1, 30)
    }
    assert keys == {"203.0.113.9"}, f"attacker partitioned the lockout budget into {keys}"


def test_x_real_ip_alone_is_still_honoured(monkeypatch):
    assert _client_ip_with(monkeypatch, {"X-Real-IP": "198.18.7.7"}) == "198.18.7.7"


def test_xff_is_read_from_the_right_when_there_is_no_real_ip(monkeypatch):
    """Fallback: the right-most hop is the one our own proxy appended."""
    got = _client_ip_with(monkeypatch, {"X-Forwarded-For": "1.2.3.4, 9.9.9.9, 203.0.113.9"})
    assert got == "203.0.113.9"


# --- the /agent/chat LLM-spend limiter key --------------------------------------------

class _Handler:
    """Just enough of BaseHTTPRequestHandler for _peer_ip."""

    def __init__(self, headers, peer="127.0.0.1"):
        self.headers = headers
        self.client_address = (peer, 12345)


def _peer_ip_with(headers, peer="127.0.0.1"):
    import api_server

    return api_server.Handler._peer_ip(_Handler(headers, peer))


def test_agent_budget_key_ignores_a_client_supplied_left_hop():
    got = _peer_ip_with({"X-Forwarded-For": "1.2.3.4, 203.0.113.9", "X-Real-IP": "203.0.113.9"})
    assert got == "203.0.113.9", (
        f"LLM-spend limiter keyed on {got!r}; a stolen token then has no ceiling"
    )


def test_agent_budget_key_is_stable_across_rotated_spoofs():
    keys = {
        _peer_ip_with({"X-Forwarded-For": f"10.0.0.{n}, 203.0.113.9", "X-Real-IP": "203.0.113.9"})
        for n in range(1, 30)
    }
    assert keys == {"203.0.113.9"}, f"attacker partitioned the LLM budget into {keys}"


def test_agent_budget_falls_back_to_the_tcp_peer_when_no_proxy_header():
    assert _peer_ip_with({}, peer="203.0.113.50") == "203.0.113.50"


def test_a_direct_caller_cannot_forge_headers_when_it_is_not_the_local_proxy():
    """Exposed without nginx, the headers are somebody's claim, not evidence.

    The peer here has to be GENUINELY public: Python reports the documentation ranges
    (198.51.100.0/24, 203.0.113.0/24) as ``is_private``, so using one as the "outside"
    address makes it count as the local proxy and the test proves nothing. That confusion
    is the same one that had a hub test fixture calling TEST-NET-3 "public".
    """
    got = _peer_ip_with(
        {"X-Real-IP": "1.1.1.1", "X-Forwarded-For": "1.1.1.1"}, peer="93.184.216.34"
    )
    assert got == "93.184.216.34", f"trusted a header from a non-proxy peer: {got!r}"
