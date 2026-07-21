#!/usr/bin/env python3
"""Public API: healthz + optional AIMarket economy endpoints."""

from __future__ import annotations

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("skopos.api")

_MAX_BODY = 256_000


def _economy_cfg():
    from skopos.economy.config import load_economy_config

    return load_economy_config()


def _check_api_key(handler: BaseHTTPRequestHandler, cfg) -> bool:
    if not cfg.api_key:
        return True
    auth = handler.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and auth[7:].strip() == cfg.api_key:
        return True
    if handler.headers.get("X-API-Key", "").strip() == cfg.api_key:
        return True
    return False


def _agent_authorized(handler: BaseHTTPRequestHandler) -> bool:
    from skopos.agent_token import verify_token

    auth = handler.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.startswith("Bearer ") else ""
    if not token:
        token = handler.headers.get("X-Skopos-Agent-Token", "").strip()
    return verify_token(token)


class Handler(BaseHTTPRequestHandler):
    def _send_cors(self) -> None:
        # Auth is a bearer token (no cookies), so a wildcard origin is safe and
        # lets the widget work from a dev origin too. Same-origin in prod.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Skopos-Agent-Token")
        self.send_header("Access-Control-Max-Age", "600")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._send_cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._send_cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > _MAX_BODY:
            raise ValueError("body too large")
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw.decode("utf-8") or "{}")
        return data if isinstance(data, dict) else {}

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        cfg = _economy_cfg()

        if path in ("/healthz", "/healthz/"):
            from skopos.public_status import build_status

            self._send_json(200, build_status(config_path=cfg.config_path))
            return

        if path in ("/agent/ping", "/agent/ping/"):
            # Cheap availability probe for the floating widget (no secrets).
            self._send_json(200, {"ok": True, "agent": True})
            return

        if not cfg.enabled:
            self.send_response(404)
            self.end_headers()
            return

        if path == "/.well-known/ai-market.json":
            from skopos.economy.manifest import build_well_known

            self._send_json(200, build_well_known(cfg))
            return

        if path == "/ai-market/v2/manifest":
            from skopos.economy.manifest import build_v2_manifest

            self._send_json(200, build_v2_manifest(cfg))
            return

        if path == "/ai-market/v2/prices":
            from skopos.economy.manifest import build_prices

            self._send_json(200, build_prices(cfg))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if path in ("/agent/chat", "/agent/chat/"):
            self._handle_agent_chat()
            return

        cfg = _economy_cfg()

        if not cfg.enabled or path not in ("/aimarket/invoke", "/aimarket/invoke/"):
            self.send_response(404)
            self.end_headers()
            return

        if not _check_api_key(self, cfg):
            self._send_json(401, {"error": "unauthorized"})
            return

        try:
            body = self._read_json()
            from skopos.economy.invoke import InvokeError, dispatch_invoke

            payload = dispatch_invoke(body, cfg=cfg)
            self._send_json(200, payload)
        except InvokeError as exc:
            self._send_json(exc.status, {"error": str(exc)})
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid json"})
        except Exception:
            logger.exception("invoke failed")
            self._send_json(500, {"error": "internal error"})

    def _handle_agent_chat(self) -> None:
        if not _agent_authorized(self):
            self._send_json(401, {"error": "unauthorized"})
            return
        try:
            body = self._read_json()
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid json"})
            return

        messages = body.get("messages")
        if not isinstance(messages, list):
            self._send_json(400, {"error": "messages must be a list"})
            return
        page = body.get("page") if isinstance(body.get("page"), str) else None
        server_name = body.get("server_name") if isinstance(body.get("server_name"), str) else None

        try:
            from skopos.agent.providers import LLMProviderError
            from skopos.agent.service import answer_agent_message

            result = answer_agent_message(messages, server_name=server_name, page=page)
            self._send_json(200, {"reply": result.reply, "provider": result.provider, "model": result.model})
        except LLMProviderError as exc:
            logger.warning("agent chat unavailable: %s", exc)
            self._send_json(503, {"error": "assistant temporarily unavailable", "detail": str(exc)})
        except Exception:
            logger.exception("agent chat failed")
            self._send_json(500, {"error": "internal error"})

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main() -> None:
    cfg = _economy_cfg()
    if cfg.enabled and cfg.auto_register:
        from skopos.economy.consumer import try_auto_register

        try_auto_register(cfg)

    port = int(os.environ.get("SKOPOS_HEALTHZ_PORT", "8502"))
    logger.info(
        "SKOPOS API on :%s (healthz + agent chat%s)",
        port,
        " + AIMarket economy" if cfg.enabled else "",
    )
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
