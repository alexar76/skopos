"""Offline-safe clients the conductor uses to reach the other agents.

Every client degrades gracefully: if an endpoint is unconfigured or unreachable it returns a
typed "not done" result rather than raising, so a demo runs end-to-end with nothing live and a
production outage never crashes the conductor mid-job.
"""

from __future__ import annotations

import os
from typing import Any

import httpx


class MomusClient:
    """Talk to MOMUS over its A2A / HTTP surface: re-test a finding (the deploy gate)."""

    def __init__(self, base_url: str, timeout_s: float = 30.0, operator_token: str | None = None,
                 *, transport: Any = None):
        self.base_url = (base_url or "").strip().rstrip("/")
        self._timeout = timeout_s
        self._transport = transport      # test hook (httpx.ASGITransport)
        # MOMUS's /retest is a CONTROL route: it makes MOMUS act, so it is operator-token gated in
        # production. The conductor must present that token or every gate call comes back 403 and
        # the job loops to "inconclusive" until its retries are exhausted — which is exactly what a
        # live run showed after the gate was added and this caller was not updated with it.
        self._token = (operator_token if operator_token is not None
                       else os.environ.get("MOMUS_OPERATOR_TOKEN", "")).strip()

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    async def retest(self, finding_id: str) -> dict[str, Any]:
        """Return MOMUS's signed FixVerdict dict, or a fail-closed stub. Never raises."""
        if not self.configured:
            return {"finding_id": finding_id, "fixed": False, "outcome": "inconclusive",
                    "detail": "no MOMUS url configured", "signature": {}}
        headers = {"x-momus-operator": self._token} if self._token else {}
        kwargs: dict[str, Any] = {"timeout": self._timeout, "headers": headers}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        try:
            async with httpx.AsyncClient(**kwargs) as c:
                r = await c.post(self.base_url + "/retest", json={"finding_id": finding_id})
                r.raise_for_status()
                body = r.json()
            # MOMUS answers 200 with an `error` body for a finding or target it cannot resolve. That
            # is NOT a verdict about the code — it is a plumbing failure, and reading it as
            # "still vulnerable" is the same dishonesty as calling an unreachable target a pass. The
            # conductor must escalate naming the real cause instead of blaming the patch.
            if not isinstance(body, dict) or not isinstance(body.get("fixed"), bool):
                err = (body or {}).get("error") if isinstance(body, dict) else None
                return {"finding_id": finding_id, "fixed": False, "outcome": "inconclusive",
                        "detail": f"MOMUS could not run the gate: {err or 'malformed verdict'}"
                                  + (" — the finding is not in MOMUS's corpus (wrong instance, or "
                                     "it was never recorded)" if err == "unknown_finding" else ""),
                        "signature": {}}
            return body
        except httpx.HTTPStatusError as exc:
            # Distinguish "refused" from "unreachable": a 403/503 here means the conductor is not
            # authorised, which an operator must fix — not something to retry into exhaustion.
            code = exc.response.status_code
            hint = (" — the conductor is missing MOMUS_OPERATOR_TOKEN (the /retest gate is "
                    "operator-only in production)") if code in (401, 403, 503) else ""
            return {"finding_id": finding_id, "fixed": False, "outcome": "inconclusive",
                    "detail": f"MOMUS refused the re-test: HTTP {code}{hint}", "signature": {}}
        except (httpx.HTTPError, ValueError) as exc:
            return {"finding_id": finding_id, "fixed": False, "outcome": "inconclusive",
                    "detail": f"MOMUS unreachable: {type(exc).__name__}", "signature": {}}


class FactoryClient:
    """Ask the AI-Factory to produce a patch for the at-fault component. In dry-run (default) it
    returns a synthetic 'patch produced' so the loop is testable without a live Factory."""

    def __init__(self, base_url: str, *, dry_run: bool = True, timeout_s: float = 120.0):
        self.base_url = (base_url or "").strip().rstrip("/")
        self.dry_run = dry_run or not self.base_url
        self._timeout = timeout_s

    async def request_fix(self, ticket: dict[str, Any]) -> dict[str, Any]:
        if self.dry_run:
            return {"ok": True, "dry_run": True,
                    "patch": {"component": ticket.get("component"), "summary": "dry-run: patch synthesized",
                              "image": f"{ticket.get('component')}:patched-{ticket.get('finding_id','')[:8]}"}}
        # NOTE: no Factory build serves /api/remediation/fix yet. Autonomous patch authoring is
        # designed but deliberately not enabled — see momus/docs/fix-provenance.md ("the fix step
        # stays a fixture flip"). Outside dry-run this call therefore 404s today, and it must say
        # so: reporting a 404 as "Factory unreachable" sent operators hunting a network fault.
        path = "/api/remediation/fix"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.post(self.base_url + path, json={"ticket": ticket})
                r.raise_for_status()
                return {"ok": True, **r.json()}
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            hint = (" — autonomous fix authoring is not enabled on this Factory build; "
                    "run the conductor in dry-run, or implement the route") if code == 404 else ""
            return {"ok": False, "http_status": code,
                    "error": f"Factory returned {code} for {path}{hint}"}
        except (httpx.HTTPError, ValueError) as exc:
            return {"ok": False, "error": f"Factory unreachable: {type(exc).__name__}"}
