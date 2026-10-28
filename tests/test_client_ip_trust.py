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


# --- GCVE-110-PYPI-2026-021896: X-Real-IP was taken from anyone who reached Streamlit ----

def test_a_direct_peer_cannot_name_its_own_lockout_address(monkeypatch):
    from skopos import app_auth

    # A public address: Python's ipaddress counts the documentation ranges (203.0.113.0/24 …)
    # as private, and client_ip treats a private peer as our own proxy.
    monkeypatch.setattr(app_auth, "_websocket_peer", lambda: "93.184.216.34")
    keys = {_client_ip_with(monkeypatch, {"X-Real-IP": f"198.51.100.{n}"}) for n in range(1, 20)}
    assert keys == {"93.184.216.34"}, f"a direct caller partitioned the lockout into {keys}"


def test_behind_our_proxy_the_real_ip_header_still_counts(monkeypatch):
    from skopos import app_auth

    monkeypatch.setattr(app_auth, "_websocket_peer", lambda: "127.0.0.1")
    assert _client_ip_with(monkeypatch, {"X-Real-IP": "198.51.100.7"}) == "198.51.100.7"


def test_the_websocket_peer_comes_from_the_streamlit_session(monkeypatch):
    """Streamlit 1.37 has no public API for it: runtime -> session manager -> session info ->
    the tornado websocket handler's request.remote_ip. Pinned with stand-ins of those names."""
    from types import SimpleNamespace

    import streamlit.runtime as st_runtime
    import streamlit.runtime.scriptrunner as scriptrunner

    from skopos import app_auth

    handler = SimpleNamespace(request=SimpleNamespace(remote_ip="203.0.113.51"))
    mgr = SimpleNamespace(get_session_info=lambda sid: SimpleNamespace(client=handler)
                          if sid == "s1" else None)
    monkeypatch.setattr(st_runtime, "exists", lambda: True)
    monkeypatch.setattr(st_runtime, "get_instance", lambda: SimpleNamespace(_session_mgr=mgr))
    monkeypatch.setattr(scriptrunner, "get_script_run_ctx",
                        lambda *a, **k: SimpleNamespace(session_id="s1"))
    assert app_auth._websocket_peer() == "203.0.113.51"
    monkeypatch.setattr(st_runtime, "get_instance", lambda: SimpleNamespace())
    assert app_auth._websocket_peer() is None          # internals changed: header fallback


def test_failures_from_many_addresses_slow_logins_down_and_lock_no_one(tmp_path, monkeypatch):
    """Whatever the key, guessing is bounded: every failure also counts against all addresses. Over
    that budget a new address waits a little before its next try, at most a minute; the budget used
    to lock every address out, the operator's too (Vulnetix GCVE-110-VULN-PYPI-2026-000644)."""
    from skopos import auth_store

    db = str(tmp_path / "auth.sqlite")
    monkeypatch.setenv("SKOPOS_LOGIN_GLOBAL_MAX_ATTEMPTS", "12")
    locked = [auth_store.register_failed_login(f"198.51.100.{n}", db_target=db) for n in range(12)]
    assert locked == [0] * 12
    assert auth_store.login_lockout_remaining_seconds("192.0.2.200", db_target=db) == 0
    assert auth_store.login_pace_seconds("192.0.2.200", db_target=db) == 0  # within the budget
    auth_store.register_failed_login("198.51.100.99", db_target=db)
    assert 0 < auth_store.login_pace_seconds("192.0.2.200", db_target=db) <= 2
    for n in range(30):
        auth_store.register_failed_login(f"198.51.101.{n}", db_target=db)
    assert 30 < auth_store.login_pace_seconds("192.0.2.200", db_target=db) <= 60
    assert auth_store.login_lockout_remaining_seconds("192.0.2.200", db_target=db) == 0


def test_an_address_that_logged_in_is_never_held_up(tmp_path, monkeypatch):
    from skopos import auth_store

    db = str(tmp_path / "auth.sqlite")
    auth_store.clear_login_lockout("192.0.2.1", db_target=db)  # the operator logged in from here
    monkeypatch.setenv("SKOPOS_LOGIN_GLOBAL_MAX_ATTEMPTS", "12")
    for n in range(40):
        auth_store.register_failed_login(f"198.51.100.{n}", db_target=db)
    assert auth_store.login_pace_seconds("192.0.2.1", db_target=db) == 0
    assert auth_store.login_pace_seconds("192.0.2.200", db_target=db) > 0
    monkeypatch.setenv("SKOPOS_LOGIN_KNOWN_DAYS", "0")  # remembered for no time at all
    assert auth_store.login_pace_seconds("192.0.2.1", db_target=db) > 0


def test_one_address_still_locks_after_its_own_five(tmp_path):
    from skopos import auth_store

    db = str(tmp_path / "auth.sqlite")
    got = [auth_store.register_failed_login("192.0.2.9", db_target=db) for _ in range(5)]
    assert got[-1] > 0 and auth_store.login_lockout_remaining_seconds("192.0.2.9", db_target=db) > 0
    assert auth_store.login_lockout_remaining_seconds("192.0.2.10", db_target=db) == 0


def test_trusted_proxies_are_loopback_unless_named(monkeypatch, tmp_path):
    # the class of Vulnetix GCVE-110-VULN-PYPI-2026-000636: X-Real-IP / X-Forwarded-For were taken from any
    # private peer, so a neighbour on the same docker network or LAN named its own address.
    import ipaddress
    import sys
    import skopos.client_ip as trust

    monkeypatch.delenv("SKOPOS_TRUSTED_PROXIES", raising=False)
    assert trust._peer_is_trusted_proxy("127.0.0.1") and trust._peer_is_trusted_proxy("::1")
    for neighbour in ("172.18.0.7", "10.0.0.5", "192.168.1.20", "fe80::1", "not-an-address", ""):
        assert not trust._peer_is_trusted_proxy(neighbour), neighbour
    monkeypatch.setenv("SKOPOS_TRUSTED_PROXIES", "10.1.0.0/16, 172.18.0.9")
    assert trust._peer_is_trusted_proxy("10.1.2.3") and trust._peer_is_trusted_proxy("172.18.0.9")
    assert not trust._peer_is_trusted_proxy("127.0.0.1")  # the list replaces the default
    route = tmp_path / "route"
    gateway_hex = "010012AC" if sys.byteorder == "little" else "AC120001"  # 172.18.0.1
    route.write_text("Iface\tDestination\tGateway\tFlags\n"
                     "eth0\t00000000\t" + gateway_hex + "\t0003\n")
    monkeypatch.setattr(trust, "_PROC_NET_ROUTE", str(route))
    monkeypatch.setenv("SKOPOS_TRUSTED_PROXIES", "gateway")
    assert trust._peer_is_trusted_proxy("172.18.0.1") and not trust._peer_is_trusted_proxy("172.18.0.2")
    named = {"frontend": (ipaddress.ip_address("172.18.0.5"),)}
    monkeypatch.setattr(trust, "_proxy_name_addresses", lambda name: named.get(name, ()))
    monkeypatch.setenv("SKOPOS_TRUSTED_PROXIES", "127.0.0.1, frontend")
    assert trust._peer_is_trusted_proxy("172.18.0.5") and not trust._peer_is_trusted_proxy("172.18.0.6")
