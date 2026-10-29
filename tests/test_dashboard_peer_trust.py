"""Dashboard login budgets must use the connection, not caller-chosen headers.

Exercise Streamlit's real Starlette session client: the former Tornado-shaped
test double hid the missing ``client.request`` on supported Streamlit versions.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
import streamlit.runtime as runtime
import streamlit.runtime.scriptrunner as scriptrunner
from starlette.websockets import WebSocket
from streamlit.runtime.context import StreamlitHeaders
from streamlit.web.server.starlette.starlette_websocket import StarletteSessionClient

from skopos import app_auth, auth_store


@pytest.fixture(autouse=True)
def proxy_defaults(monkeypatch):
    monkeypatch.delenv("SKOPOS_TRUSTED_PROXIES", raising=False)
    monkeypatch.delenv("SKOPOS_TRUSTED_PROXY_HOPS", raising=False)


def _connection_key(monkeypatch, peer, headers, *, expose_headers=True,
                    transport_available=True, peername_override=...,
                    bound_receive=True, transport_error=False):
    """Exercise the Streamlit adapter with a raw transport and rewritten ASGI IP.

    The bound receive method models Uvicorn's protocol/transport boundary. ASGI's
    client address is deliberately different: middleware may have rewritten it
    from a caller-controlled forwarded header before Streamlit sees the scope.
    """
    async def run():
        class Transport:
            def get_extra_info(self, name):
                assert name == "peername"
                if transport_error:
                    raise RuntimeError("transport unavailable")
                if peername_override is not ...:
                    return peername_override
                return (peer, 12345) if peer is not None else None

        class Protocol:
            def __init__(self):
                if transport_available:
                    self.transport = Transport()

            async def receive(self):
                return {"type": "websocket.disconnect"}

        async def send(message):
            pass

        async def unbound_receive():
            return {"type": "websocket.disconnect"}

        websocket = WebSocket(
            {
                "type": "websocket",
                "client": ("198.18.0.250", 12345),
                "headers": [(key.lower().encode(), value.encode())
                            for key, value in headers.items()],
            },
            Protocol().receive if bound_receive else unbound_receive,
            send,
        )
        client = StarletteSessionClient(websocket)
        monkeypatch.setattr(runtime, "exists", lambda: True)
        monkeypatch.setattr(runtime, "get_instance", lambda: SimpleNamespace(
            get_client=lambda session_id: client
        ))
        monkeypatch.setattr(scriptrunner, "get_script_run_ctx",
                            lambda *args, **kwargs: SimpleNamespace(session_id="test-session"))
        context = SimpleNamespace(
            headers=StreamlitHeaders(client.client_context.headers) if expose_headers else None
        )
        monkeypatch.setattr(app_auth, "st", SimpleNamespace(context=context))
        try:
            return app_auth._websocket_peer(), app_auth._client_ip()
        finally:
            await client.aclose()

    return asyncio.run(run())


@pytest.mark.parametrize("peer", ["93.184.216.34", "172.18.0.7", "2606:4700:4700::1111"])
def test_real_streamlit_client_keeps_direct_callers_in_their_own_bucket(monkeypatch, peer):
    results = {
        _connection_key(monkeypatch, peer, {
            "X-Real-IP": f"198.51.100.{number}",
            "X-Forwarded-For": f"192.0.2.{number}",
        })
        for number in range(1, 4)
    }
    assert results == {(peer, peer)}


@pytest.mark.parametrize("peer", ["127.0.0.1", "::1"])
def test_real_streamlit_loopback_proxy_uses_forwarded_address(monkeypatch, peer):
    assert _connection_key(monkeypatch, peer, {
        "X-Real-IP": "198.51.100.8",
        "X-Forwarded-For": "192.0.2.9, 198.51.100.8",
    }) == (peer, "198.51.100.8")


def test_real_streamlit_client_respects_explicit_proxy_allowlist(monkeypatch):
    monkeypatch.setenv("SKOPOS_TRUSTED_PROXIES", "172.18.0.5")
    assert _connection_key(monkeypatch, "172.18.0.5", {
        "X-Forwarded-For": "192.0.2.1, 198.51.100.8",
    }) == ("172.18.0.5", "198.51.100.8")
    assert _connection_key(monkeypatch, "127.0.0.1", {
        "X-Real-IP": "198.51.100.8",
    }) == ("127.0.0.1", "127.0.0.1")


def test_disabled_header_trust_keeps_proxy_connection_address(monkeypatch):
    monkeypatch.setenv("SKOPOS_TRUSTED_PROXY_HOPS", "0")
    assert _connection_key(monkeypatch, "127.0.0.1", {
        "X-Real-IP": "198.51.100.8",
    }) == ("127.0.0.1", "127.0.0.1")


def test_ipv6_transport_peername_uses_address_without_port_or_scope_fields(monkeypatch):
    assert _connection_key(monkeypatch, None, {"X-Real-IP": "198.51.100.8"},
                           peername_override=("2606:4700:4700::1111", 12345, 0, 0)) == (
        "2606:4700:4700::1111", "2606:4700:4700::1111"
    )


def test_ipv4_mapped_loopback_retains_trusted_proxy_behavior(monkeypatch):
    peer, key = _connection_key(monkeypatch, None, {"X-Real-IP": "198.51.100.8"},
                                peername_override=("::ffff:127.0.0.1", 12345, 0, 0))
    # Python versions render mapped IPv4 addresses in dotted or hexadecimal form.
    assert peer in {"::ffff:127.0.0.1", "::ffff:7f00:1"}
    assert key == "198.51.100.8"


@pytest.mark.parametrize("peer", [None, "", "not-an-ip", "127.0.0.1,93.184.216.34"])
def test_unknown_or_invalid_connection_never_adopts_address_headers(monkeypatch, peer):
    assert _connection_key(monkeypatch, peer, {
        "X-Real-IP": "198.51.100.8",
        "X-Forwarded-For": "198.51.100.9",
    }) == (None, "unknown")


@pytest.mark.parametrize("peer", ["93.184.216.34", "127.0.0.1"])
def test_connection_address_survives_missing_header_view(monkeypatch, peer):
    assert _connection_key(monkeypatch, peer, {}, expose_headers=False) == (peer, peer)


def test_missing_transport_does_not_adopt_scope_or_address_headers(monkeypatch):
    assert _connection_key(monkeypatch, "93.184.216.34", {
        "X-Real-IP": "198.51.100.8", "X-Forwarded-For": "198.51.100.9",
    }, transport_available=False) == (None, "unknown")


@pytest.mark.parametrize("options", [{"bound_receive": False}, {"transport_error": True}])
def test_unavailable_transport_adapter_never_uses_scope_or_headers(monkeypatch, options):
    assert _connection_key(monkeypatch, "93.184.216.34", {
        "X-Real-IP": "198.51.100.8",
    }, **options) == (None, "unknown")


@pytest.mark.parametrize("peername", [None, (), "127.0.0.1", (None, 12345), (12345, 12345)])
def test_malformed_transport_peer_does_not_adopt_scope_or_headers(monkeypatch, peername):
    assert _connection_key(monkeypatch, "93.184.216.34", {
        "X-Real-IP": "198.51.100.8",
    }, peername_override=peername) == (None, "unknown")


@pytest.mark.parametrize("failure", ["no-runtime", "no-script-context", "runtime-error"])
def test_unavailable_session_does_not_fall_back_to_headers(monkeypatch, failure):
    monkeypatch.setattr(app_auth, "st", SimpleNamespace(context=SimpleNamespace(headers={
        "X-Real-IP": "198.51.100.8", "X-Forwarded-For": "198.51.100.9",
    })))
    monkeypatch.setattr(runtime, "exists", lambda: failure != "no-runtime")
    monkeypatch.setattr(scriptrunner, "get_script_run_ctx", lambda *args, **kwargs: (
        None if failure == "no-script-context" else SimpleNamespace(session_id="test-session")
    ))

    def broken_runtime():
        raise RuntimeError("session lookup unavailable")

    monkeypatch.setattr(runtime, "get_instance", broken_runtime)
    assert app_auth._websocket_peer() is None
    assert app_auth._client_ip() == "unknown"


@pytest.mark.parametrize("peer", ["93.184.216.34", "127.0.0.1"])
@pytest.mark.parametrize("failure", ["header-access", "header-lookup"])
def test_header_errors_preserve_the_verified_connection_key(monkeypatch, peer, failure):
    class BrokenHeaders:
        def get(self, name):
            raise RuntimeError("header lookup unavailable")

    class Context:
        @property
        def headers(self):
            if failure == "header-access":
                raise RuntimeError("context headers unavailable")
            return BrokenHeaders()

    monkeypatch.setattr(app_auth, "_websocket_peer", lambda: peer)
    monkeypatch.setattr(app_auth, "st", SimpleNamespace(context=Context()))
    assert app_auth._client_ip() == peer


def test_spoofed_known_ip_cannot_avoid_pacing_or_switch_lockout_bucket(monkeypatch, tmp_path):
    database = str(tmp_path / "auth.sqlite")
    monkeypatch.setenv("SKOPOS_LOGIN_GLOBAL_MAX_ATTEMPTS", "12")
    monkeypatch.setenv("SKOPOS_LOGIN_MAX_ATTEMPTS", "5")
    monkeypatch.setenv("SKOPOS_LOGIN_LOCKOUT_SECONDS", "300")
    monkeypatch.setenv("SKOPOS_LOGIN_KNOWN_DAYS", "30")
    known_ip = "198.51.100.8"
    peer = "93.184.216.34"
    auth_store.clear_login_lockout(known_ip, db_target=database)
    for number in range(45):
        auth_store.register_failed_login(f"192.0.2.{number + 1}", db_target=database)

    _, key = _connection_key(monkeypatch, peer, {"X-Real-IP": known_ip})
    assert auth_store.login_pace_seconds(known_ip, db_target=database) == 0
    assert auth_store.login_pace_seconds(key, db_target=database) > 0

    for number in range(5):
        _, key = _connection_key(monkeypatch, peer, {"X-Real-IP": f"198.51.100.{number + 10}"})
        auth_store.register_failed_login(key, db_target=database)
    assert auth_store.login_lockout_remaining_seconds(peer, db_target=database) > 0

