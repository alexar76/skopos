"""A2A ingress for SKOPOS's remediation conductor.

A small FastAPI app that lets MOMUS delegate a ``remediate`` task to SKOPOS. It can run as a
sidecar next to the Streamlit dashboard, or be mounted into SKOPOS's existing API server. It
advertises an A2A Agent Card so MOMUS (or any peer) can discover the ``remediate`` skill, and it
exposes the job board for the dashboard.

The conductor's work is I/O-bound and may take a while (Factory patch + retests + deploy), so a
posted task starts the job in the background and returns immediately with the job handle; the
peer/dashboard polls ``/remediation/jobs`` for progress.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from skopos.remediation.conductor import Conductor, RemediationConfig


def agent_card(public_url: str, conductor_pubkey: str) -> dict[str, Any]:
    base = public_url.rstrip("/")
    return {
        "protocolVersion": "0.2",
        "name": "SKOPOS",
        "description": "The watcher — conducts remediation: receives a signed finding from MOMUS, "
                       "drives the AI-Factory to patch it, gates the redeploy on a MOMUS re-test, "
                       "and dispatches a signed deploy order to the installed node agent.",
        "url": base,
        "version": "0.1.0",
        "capabilities": {"streaming": False, "pushNotifications": True, "stateTransitionHistory": True},
        "conductorPublicKey": conductor_pubkey,
        "skills": [{
            "id": "remediate",
            "name": "Remediation conductor",
            "description": "Accept a confirmed MOMUS finding and drive fix → re-test → deploy to "
                           "closure, escalating security-core findings to a human.",
            "tags": ["security", "remediation", "orchestration", "ci", "deploy"],
        }],
        "endpoints": {"tasks": f"{base}/a2a/tasks"},
    }


def build_app(conductor: Conductor | None = None) -> FastAPI:
    conductor = conductor or Conductor(RemediationConfig.from_env())
    app = FastAPI(title="SKOPOS remediation conductor", version="0.1.0")
    origins = [o.strip() for o in os.environ.get("SKOPOS_A2A_CORS", "*").split(",") if o.strip()] or ["*"]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])
    app.state.conductor = conductor

    # ── Peer authentication ────────────────────────────────────────────────────
    # A2A is agent-to-AGENT, not a public inbox. This endpoint can start a Factory patch and end in
    # a signed DeployOrder, so an unauthenticated caller must not be able to open a job. The token is
    # shared with MOMUS (SKOPOS_A2A_TOKEN on both sides); fail-closed outside dry-run.
    a2a_token = os.environ.get("SKOPOS_A2A_TOKEN", "").strip()

    def _require_peer(request: Request) -> None:
        if not a2a_token:
            if not conductor.cfg.dry_run:
                raise HTTPException(
                    status_code=503,
                    detail="SKOPOS_A2A_TOKEN is unset — refusing A2A tasks outside dry-run "
                           "(fail-closed). Configure the same token on MOMUS.")
            return  # dry-run convenience only
        supplied = (request.headers.get("x-a2a-token") or "").strip()
        if supplied != a2a_token:
            raise HTTPException(status_code=403, detail="A2A peer token required")

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "service": "skopos-remediation", "version": "0.1.0",
                "conductor_pubkey": conductor.conductor_pubkey, "dry_run": conductor.cfg.dry_run,
                "a2a_gated": bool(a2a_token) or not conductor.cfg.dry_run,
                "momus_pubkey_configured": bool(conductor.cfg.momus_pubkey)}

    @app.get("/.well-known/agent-card.json")
    async def card() -> dict[str, Any]:
        public = os.environ.get("SKOPOS_PUBLIC_URL", "https://skopos.modelmarket.dev")
        return agent_card(public, conductor.conductor_pubkey)

    @app.post("/a2a/tasks")
    async def a2a_tasks(body: dict, request: Request) -> dict[str, Any]:
        _require_peer(request)
        skill = str((body or {}).get("skill") or "").strip()
        if skill != "remediate":
            conductor.observer.record_inbound(body, state="rejected",
                                              note=f"unsupported skill '{skill}'")
            return {"state": "rejected",
                    "message": f"SKOPOS conductor accepts skill 'remediate', not '{skill}'"}
        ticket = ((body or {}).get("input") or {}).get("ticket") or {}
        if not ticket.get("finding_id"):
            conductor.observer.record_inbound(body, state="rejected", note="missing ticket.finding_id")
            return {"state": "rejected", "message": "missing ticket.finding_id"}
        conductor.observer.record_inbound(body, state="working")
        # Start the (long-running) job in the background; return the handle immediately.
        asyncio.create_task(conductor.handle_ticket(ticket))
        return {"state": "working", "finding_id": ticket["finding_id"],
                "message": "remediation job started", "poll": "/remediation/jobs"}

    # ── A2A observability: SKOPOS watching the agents talk ────────────────────
    @app.get("/a2a/events")
    async def a2a_events(limit: int = 100, peer: str | None = None,
                         skill: str | None = None) -> dict[str, Any]:
        return {"events": conductor.observer.recent(limit, peer=peer, skill=skill),
                "stats": conductor.observer.stats()}

    @app.get("/a2a/stats")
    async def a2a_stats() -> dict[str, Any]:
        return conductor.observer.stats()

    # ── Deploy-order pickup for PUSH-ONLY node agents ─────────────────────────
    # The fleet agents have no HTTP server, so they poll here. Authority stays split: the conductor
    # publishes a signed order but cannot execute it; the agent executes but cannot invent one.
    agent_token = os.environ.get("SKOPOS_AGENT_TOKEN", "").strip()

    def _require_agent(request: Request) -> None:
        if not agent_token:
            if not conductor.cfg.dry_run:
                raise HTTPException(status_code=503,
                                    detail="SKOPOS_AGENT_TOKEN is unset — refusing to hand out "
                                           "deploy orders outside dry-run (fail-closed)")
            return
        if (request.headers.get("x-agent-token") or "").strip() != agent_token:
            raise HTTPException(status_code=403, detail="agent token required")

    @app.get("/agent/v1/orders")
    async def agent_orders(host: str, request: Request) -> dict[str, Any]:
        """Hand this host its next signed order, ONCE. A claimed order is never re-served, so a
        replayed poll cannot re-run a deploy; an expired one is skipped rather than executed late."""
        _require_agent(request)
        q = conductor.orders.claim_for(host, agent_id=host)
        if q is None:
            return {"order": None, "host": host}
        conductor.observer.record_outbound(
            peer=f"agent:{host}", skill="deploy-order", finding_id=q.finding_id,
            state="completed", summary=f"order {q.order_id} claimed for {q.service}",
            artifacts=["deploy-order"])
        return {"order": q.order, "host": host, "order_id": q.order_id, "service": q.service}

    @app.post("/agent/v1/result")
    async def agent_result(body: dict, request: Request) -> dict[str, Any]:
        """The agent reports what it did — including a REFUSAL, which is the interesting case."""
        _require_agent(request)
        oid = str((body or {}).get("order_id") or "")
        result = (body or {}).get("result") or {}
        ok = conductor.orders.report(oid, result)
        conductor.observer.record_inbound(
            {"skill": "deploy-result", "from_agent": f"agent:{result.get('host', '?')}",
             "input": {"finding_id": oid}},
            state="completed" if ok else "rejected",
            note=("deployed" if result.get("deployed") else
                  f"refused: {str(result.get('reason'))[:80]}" if result.get("refused") else
                  "dry-run"))
        return {"recorded": ok, "order_id": oid}

    @app.get("/agent/v1/queue")
    async def agent_queue(limit: int = 20) -> dict[str, Any]:
        """Read-only view of published orders and what the agents did with them."""
        return {"orders": conductor.orders.all(limit), "stats": conductor.orders.stats()}

    @app.get("/remediation/jobs")
    async def jobs() -> dict[str, Any]:
        return {"jobs": [j.to_dict() for j in conductor.store.all()]}

    @app.get("/remediation/jobs/{finding_id}")
    async def job(finding_id: str) -> dict[str, Any]:
        j = conductor.store.get(finding_id)
        return j.to_dict() if j else {"error": "unknown_job", "finding_id": finding_id}

    return app
