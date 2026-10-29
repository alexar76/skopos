"""Exercise dashboard IP trust through real Uvicorn WebSocket connections.

Streamlit's client context takes its IP from the ASGI scope. Uvicorn can already
rewrite that scope from X-Forwarded-For before SKOPOS sees it. The socket peer
must therefore come from the transport, and an unavailable transport must never
enable the header fallback.
"""

from __future__ import annotations

import asyncio
import json
import socket
from types import SimpleNamespace

import pytest
import streamlit.runtime as st_runtime
import streamlit.runtime.scriptrunner as scriptrunner
import uvicorn
from starlette.applications import Starlette
from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket
from streamlit.runtime.context import StreamlitHeaders
from streamlit.web.server.starlette.starlette_websocket import StarletteSessionClient
from websockets.asyncio.client import connect

from skopos import app_auth


@pytest.mark.parametrize("protocol", ["websockets", "websockets-sansio"])
@pytest.mark.parametrize(
    ("trusted_proxies", "proxy_hops", "wrap_receive", "expected_key"),
    [
        ("", "1", False, "127.0.0.1"),
        ("127.0.0.1", "0", False, "127.0.0.1"),
        ("127.0.0.1", "1", False, "198.51.100.9"),
        ("127.0.0.1", "1", True, "unknown"),
    ],
    ids=["no-trusted-proxies", "header-trust-disabled", "trusted-proxy", "unknown-transport"],
)
def test_dashboard_uses_transport_peer_after_uvicorn_rewrites_client(
    monkeypatch, protocol, trusted_proxies, proxy_hops, wrap_receive, expected_key
):
    monkeypatch.setenv("SKOPOS_TRUSTED_PROXIES", trusted_proxies)
    monkeypatch.setenv("SKOPOS_TRUSTED_PROXY_HOPS", proxy_hops)

    async def run():
        async def endpoint(websocket: WebSocket):
            await websocket.accept()
            client = StarletteSessionClient(websocket)
            try:
                with monkeypatch.context() as patch:
                    patch.setattr(st_runtime, "exists", lambda: True)
                    patch.setattr(
                        st_runtime,
                        "get_instance",
                        lambda: SimpleNamespace(get_client=lambda session_id: client),
                    )
                    patch.setattr(
                        scriptrunner,
                        "get_script_run_ctx",
                        lambda: SimpleNamespace(session_id="transport-test"),
                    )
                    patch.setattr(
                        app_auth,
                        "st",
                        SimpleNamespace(context=SimpleNamespace(
                            headers=StreamlitHeaders(client.client_context.headers)
                        )),
                    )
                    result = {
                        "scope_ip": client.client_context.remote_ip,
                        "transport_peer": app_auth._websocket_peer(),
                        "lockout_key": app_auth._client_ip(),
                    }
                await websocket.send_text(json.dumps(result))
                await websocket.close()
            finally:
                await client.aclose()

        app = Starlette(routes=[WebSocketRoute("/peer", endpoint)])

        async def wrapped_app(scope, receive, send):
            # A future ASGI middleware may wrap receive and hide the protocol.
            # Losing that implementation detail must fail closed, rather than
            # trusting Streamlit's already rewritten context IP or headers.
            async def wrapped_receive():
                return await receive()

            await app(scope, wrapped_receive if wrap_receive else receive, send)

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.bind(("127.0.0.1", 0))
        except OSError:
            listener.close()
            raise
        listener.listen()
        listener.setblocking(False)
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(
            wrapped_app,
            host="127.0.0.1",
            port=port,
            ws=protocol,
            proxy_headers=True,
            forwarded_allow_ips="*",
            lifespan="off",
            log_config=None,
            log_level="error",
        ))
        task = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            async def wait_until_started():
                while not server.started:
                    if task.done():
                        await task
                    await asyncio.sleep(0.01)

            await asyncio.wait_for(wait_until_started(), timeout=5)
            async with connect(
                f"ws://127.0.0.1:{port}/peer",
                additional_headers={
                    "X-Forwarded-For": "198.51.100.99",
                    "X-Real-IP": "198.51.100.9",
                },
                proxy=None,
            ) as websocket:
                result = json.loads(await asyncio.wait_for(websocket.recv(), timeout=5))
            # Prove that the actual middleware rewrote the connection context.
            assert result["scope_ip"] == "198.51.100.99"
            assert result["transport_peer"] == (None if wrap_receive else "127.0.0.1")
            assert result["lockout_key"] == expected_key
        finally:
            server.should_exit = True
            try:
                await asyncio.wait_for(task, timeout=5)
            finally:
                if not task.done():
                    task.cancel()
                listener.close()

    asyncio.run(run())
