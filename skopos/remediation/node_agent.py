"""The deploy hand that runs ON a node agent — a constrained executor, not a fixer.

This is what the installed SKOPOS agent gains: the ability to *carry out* one redeploy that somebody
else authorised. It deliberately cannot do more than that.

Why the agent is a hand and not a brain — an agent that could AUTHOR fixes would need write access to
code and the ability to run arbitrary changes, replicated on every fleet host. That is the most
dangerous privilege in the system, and it buys nothing: a patch written in place on a host leaves no
reviewable artifact (no diff, no signature, nothing MOMUS can gate), and N agents fixing locally
produce N divergent fixes with no single verified result. So the division of labour is:

    AI-Factory authors  →  MOMUS verifies  →  SKOPOS orders  →  the agent executes ONE command

The agent's whole job is therefore: poll, verify the signed chain, run one allowlisted service
redeploy, report. It cannot invent work, cannot choose a different service, and cannot deploy without
a MOMUS-signed `fixed` verdict it has no key to forge. A fully compromised agent can redeploy its own
allowlisted services and nothing else.

Outbound only: the agent polls the conductor. Nothing here opens a port on a fleet host — the
existing agents are push-only and that property is preserved on purpose.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

from skopos.remediation.agent_executor import NodeDeployExecutor


@dataclass
class NodeAgentConfig:
    """Everything the hand needs. The allowlist is LOCAL: the host decides what may be touched,
    never the caller — so even a compromised conductor cannot widen it."""

    conductor_url: str
    host: str                        # this agent's host label, as the conductor addresses it
    agent_token: str = ""            # the agent's enrolment credential
    conductor_pubkey: str = ""       # learned at enrolment; orders must be signed by it
    momus_pubkey: str = ""           # orders must embed a verdict signed by THIS key
    service_allowlist: tuple[str, ...] = ()
    compose_file: str = ""
    dry_run: bool = True             # NOTHING ships until an operator turns this off
    poll_interval_s: float = 30.0

    @classmethod
    def from_env(cls) -> "NodeAgentConfig":
        raw = os.environ.get("SKOPOS_AGENT_SERVICE_ALLOWLIST", "")
        return cls(
            conductor_url=os.environ.get("SKOPOS_CONDUCTOR_URL", "").strip().rstrip("/"),
            host=os.environ.get("SKOPOS_AGENT_HOST", "").strip(),
            agent_token=os.environ.get("SKOPOS_AGENT_TOKEN", "").strip(),
            conductor_pubkey=os.environ.get("SKOPOS_CONDUCTOR_PUBKEY", "").strip(),
            momus_pubkey=os.environ.get("SKOPOS_MOMUS_PUBKEY", "").strip(),
            service_allowlist=tuple(s.strip() for s in raw.split(",") if s.strip()),
            compose_file=os.environ.get("SKOPOS_AGENT_COMPOSE_FILE", "").strip(),
            dry_run=(os.environ.get("SKOPOS_AGENT_DRY_RUN", "1").strip().lower()
                     not in ("0", "false", "no", "off")),
            poll_interval_s=float(os.environ.get("SKOPOS_AGENT_POLL_S", "30") or 30),
        )


class NodeAgentDeployHand:
    def __init__(self, config: NodeAgentConfig | None = None, *, transport: Any = None):
        self.cfg = config or NodeAgentConfig.from_env()
        self._transport = transport   # test hook (httpx.ASGITransport)
        self._executor = NodeDeployExecutor(
            conductor_pubkey=self.cfg.conductor_pubkey,
            momus_pubkey=self.cfg.momus_pubkey,
            service_allowlist=list(self.cfg.service_allowlist),
            compose_file=self.cfg.compose_file,
            dry_run=self.cfg.dry_run,
        )

    def _client(self) -> httpx.AsyncClient:
        headers = {"x-agent-token": self.cfg.agent_token} if self.cfg.agent_token else {}
        kwargs: dict[str, Any] = {"base_url": self.cfg.conductor_url, "timeout": 30.0,
                                  "headers": headers}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    async def poll_once(self) -> dict[str, Any]:
        """Claim at most one order, verify it locally, execute it, report the outcome.

        Never raises: a conductor outage leaves the host untouched, which is the safe direction."""
        if not self.cfg.conductor_url or not self.cfg.host:
            return {"polled": False, "reason": "agent not configured (conductor url / host missing)"}
        try:
            async with self._client() as c:
                r = await c.get("/agent/v1/orders", params={"host": self.cfg.host})
                r.raise_for_status()
                body = r.json()
        except (httpx.HTTPError, ValueError) as exc:
            return {"polled": False, "reason": f"conductor unreachable: {type(exc).__name__}"}

        order = (body or {}).get("order")
        if not order:
            return {"polled": True, "order": None, "reason": "no order for this host"}

        # LOCAL verification, then one fixed-shape command. This is the only place a deploy happens.
        result = self._executor.execute(order)
        result["host"] = self.cfg.host
        result["executed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        try:
            async with self._client() as c:
                await c.post("/agent/v1/result",
                             json={"order_id": order.get("order_id"), "result": result})
        except (httpx.HTTPError, ValueError):
            pass  # the deploy already happened (or was refused); a lost report must not retry it
        return {"polled": True, "order_id": order.get("order_id"), "result": result}

    async def run_forever(self) -> None:  # pragma: no cover - long-running loop
        import asyncio
        while True:
            await self.poll_once()
            await asyncio.sleep(self.cfg.poll_interval_s)
