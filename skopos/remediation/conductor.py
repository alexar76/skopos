"""The conductor — SKOPOS's orchestration of one remediation job.

It runs the state machine for a single MOMUS ticket: drive the Factory to patch, ask MOMUS to
re-test the patch (the gate), sign a DeployOrder embedding MOMUS's fixed-verdict, dispatch it to
the node agent on the target host, then ask MOMUS to re-test once more IN PLACE to confirm the live
container is clean. Bounded retries; anything touching the security core, or a job that can't be
fixed, escalates to a human.

The conductor signs DeployOrders with its OWN key and never redeploys anything itself — the
installed node agent does, and only after verifying the full chain. SKOPOS conducts; it does not
wield deploy authority directly.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any

from skopos.remediation.clients import FactoryClient, MomusClient
from skopos.remediation.deploy_order import DeployOrder, sign_deploy_order
from skopos.remediation.jobs import Job, JobState, JobStore

try:
    from oracle_core.signing import Signer
except Exception:  # pragma: no cover
    Signer = None  # type: ignore


@dataclass
class RemediationConfig:
    data_dir: str = "data/remediation"
    conductor_key_path: str = "data/remediation/conductor_key"
    momus_url: str = ""
    momus_pubkey: str = ""            # MOMUS's known scanner/verifier pubkey (for the agent's checks)
    # MOMUS's /retest is operator-gated in prod; the conductor must hold that token to use the gate.
    momus_operator_token: str = ""
    factory_url: str = ""
    dry_run: bool = True
    max_attempts: int = 3
    # Map a component/target → (node-agent url, host label). In dry-run the url may be blank.
    agent_hosts: dict[str, str] | None = None

    @classmethod
    def from_env(cls) -> "RemediationConfig":
        import json
        hosts_raw = os.environ.get("SKOPOS_AGENT_HOSTS", "").strip()
        agent_hosts = {}
        if hosts_raw:
            try:
                agent_hosts = json.loads(hosts_raw)
            except json.JSONDecodeError:
                agent_hosts = {}
        return cls(
            data_dir=os.environ.get("SKOPOS_REMEDIATION_DIR", "data/remediation"),
            conductor_key_path=os.environ.get("SKOPOS_CONDUCTOR_KEY_PATH", "data/remediation/conductor_key"),
            momus_url=os.environ.get("SKOPOS_MOMUS_URL", ""),
            momus_pubkey=os.environ.get("SKOPOS_MOMUS_PUBKEY", ""),
            momus_operator_token=os.environ.get("MOMUS_OPERATOR_TOKEN", ""),
            factory_url=os.environ.get("SKOPOS_FACTORY_URL", ""),
            dry_run=(os.environ.get("SKOPOS_REMEDIATION_DRY_RUN", "1").strip().lower() not in ("0", "false", "no")),
            max_attempts=int(os.environ.get("SKOPOS_REMEDIATION_MAX_ATTEMPTS", "3")),
            agent_hosts=agent_hosts,
        )


class Conductor:
    def __init__(self, config: RemediationConfig | None = None):
        self.cfg = config or RemediationConfig.from_env()
        os.makedirs(self.cfg.data_dir, exist_ok=True)
        self.store = JobStore(os.path.join(self.cfg.data_dir, "jobs.jsonl"))
        self._signer = Signer(self.cfg.conductor_key_path) if Signer else None
        self.momus = MomusClient(self.cfg.momus_url, operator_token=self.cfg.momus_operator_token)
        self.factory = FactoryClient(self.cfg.factory_url, dry_run=self.cfg.dry_run)
        # A2A wire observer — SKOPOS is the fleet's observability satellite, so agent↔agent
        # delegations are recorded here and surfaced in the dashboard.
        from skopos.remediation.a2a_observer import A2AObserver
        self.observer = A2AObserver(self.cfg.data_dir)
        self._locks: dict[str, asyncio.Lock] = {}   # one live remediation per finding
        # Published deploy orders. The fleet agents are PUSH-ONLY (no inbound port), so they poll
        # this queue instead of being called — see order_queue.py for why pull is the right shape.
        from skopos.remediation.order_queue import OrderQueue
        self.orders = OrderQueue(os.path.join(self.cfg.data_dir, "deploy_orders.jsonl"))
        # How a terminal outcome reaches the dashboard: a summary pushed over the fleet's existing
        # signed node-report channel. Opt-in, best-effort, and never able to change a job's outcome.
        from skopos.remediation.report_push import ReportPusher
        self.reporter = ReportPusher(data_dir=self.cfg.data_dir)

    @property
    def conductor_pubkey(self) -> str:
        return self._signer.public_key_b64 if self._signer else ""

    def _agent_url_for(self, component: str) -> str:
        return (self.cfg.agent_hosts or {}).get(component, "")

    async def _retest_observed(self, finding_id: str, phase: str) -> dict[str, Any]:
        """Ask MOMUS to re-test, and record the A2A round trip so an operator can watch it."""
        import time as _t
        t0 = _t.monotonic()
        verdict = await self.momus.retest(finding_id)
        elapsed = int((_t.monotonic() - t0) * 1000)
        fixed = bool(verdict.get("fixed"))
        self.observer.record_outbound(
            peer="momus", skill="retest", finding_id=finding_id,
            state="completed" if verdict.get("outcome") != "inconclusive" else "failed",
            ok=verdict.get("outcome") != "inconclusive", latency_ms=elapsed,
            summary=f"{phase}: fixed={fixed} outcome={verdict.get('outcome')}",
            artifacts=["fix-verdict"] if verdict.get("signature") else [])
        return verdict

    def _verify_ticket(self, ticket: dict[str, Any]) -> tuple[bool, str]:
        """Check the ticket's Blame attestation against MOMUS's KNOWN key.

        Without this the conductor believed whatever a caller posted. A peer could claim any
        finding_id and component and get a fix + redeploy driven on its behalf."""
        pub = (self.cfg.momus_pubkey or "").strip()
        blame = ticket.get("blame") or {}
        if not pub:
            # Fail closed in prod: no key to check against means the ticket is unverifiable.
            if not self.cfg.dry_run:
                return False, ("SKOPOS_MOMUS_PUBKEY is unset — cannot verify the ticket's Blame "
                               "attestation; refusing to remediate on an unverified claim")
            return True, "dry-run: ticket signature not verified (no SKOPOS_MOMUS_PUBKEY)"
        sig = blame.get("signature") or {}
        if not sig.get("value"):
            return False, "ticket carries no signed Blame attestation"
        body = {k: v for k, v in blame.items() if k != "signature"}
        try:
            from momus.findings import verify_document_signature
            if not verify_document_signature(body, sig, pub):
                return False, "Blame signature does not verify under the known MOMUS key"
        except Exception as exc:  # noqa: BLE001
            return False, f"Blame verification error: {type(exc).__name__}"
        # The Blame must be about the SAME finding and component the ticket claims.
        if blame.get("finding_id") != ticket.get("finding_id"):
            return False, "Blame finding_id disagrees with the ticket"
        if blame.get("component") != ticket.get("component"):
            return False, "Blame component disagrees with the ticket"
        return True, "Blame verified under the known MOMUS key"

    async def handle_ticket(self, ticket: dict[str, Any]) -> Job:  # type: ignore[name-defined]
        """Entry point: an A2A 'remediate' task from MOMUS arrives here."""
        fid = ticket.get("finding_id", "")
        component = ticket.get("component", "")
        # Re-DERIVE the escalation route from the component, server-side. Reading `route` off the
        # ticket let a caller label a security-core finding as ordinary and walk it straight into
        # the automated fix→deploy path — the exact lever the escalation rule exists to remove.
        from momus.engine.remediation import escalation_for
        route = escalation_for(component, ticket.get("target_kind", ""))
        job = self.store.get(fid) or Job(
            finding_id=fid, component=component, probe=ticket.get("probe", ""),
            severity=ticket.get("severity", ""), route=route, ticket=ticket)
        job.route = route  # never let a stored/claimed value override the derived one

        ok, why = self._verify_ticket(ticket)
        if not ok:
            return await self._finish(job, JobState.ESCALATED, f"unverified ticket: {why}")

        # Security core → never auto-remediate; hand to a human.
        if route == "human-governance":
            return await self._finish(job, JobState.ESCALATED,
                                      f"security-core finding ({component}): routed to human "
                                      f"governance + external verifier, never auto-remediated")
        # One live job per finding: N concurrent posts used to spawn N loops mutating one Job, each
        # able to reach DEPLOYING and get an order signed while `attempts` was incremented by all.
        if job.state in (JobState.FIXING.value, JobState.RETESTING.value,
                         JobState.DEPLOYING.value, JobState.VERIFYING.value):
            return job
        # A NEW ticket for a job that already reached a terminal state re-opens it with a fresh
        # attempt budget. Without this a single transient failure (a patch that had not landed yet,
        # an unauthorised gate call) left the job ESCALATED for ever and the finding could never be
        # remediated even after the fix shipped — the same "temporary problem, permanent damage"
        # shape as consuming a dedup identity on an unsettled HELD payout. DONE is left alone: a
        # finished remediation should not be redone by a duplicate ticket.
        if job.state in (JobState.FAILED.value, JobState.ESCALATED.value):
            job.attempts = 0
            job.transition(JobState.RECEIVED,
                           "re-opened by a new remediation ticket — the world may have changed "
                           "(e.g. the patch has since landed); attempt budget reset")
        elif job.state == JobState.DONE.value:
            return job
        async with self._lock_for(fid):
            return await self._run(job)

    def _lock_for(self, finding_id: str):
        lock = self._locks.get(finding_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[finding_id] = lock
        return lock

    async def _finish(self, job: Job, state: JobState, note: str) -> Job:
        """Reach a terminal state: record it, persist it, then tell the dashboard about it.

        The push is deliberately the LAST thing that happens and cannot change the outcome — a
        SKOPOS outage, a 401 or a seq conflict is logged and swallowed, so a remediation that worked
        is never recorded as failed because a dashboard was down."""
        job.transition(state, note)
        self.store.upsert(job)
        await self.reporter.push_job_async(job, conductor_pubkey=self.conductor_pubkey,
                                           queued=self._queued_order_for(job))
        return job

    def _queued_order_for(self, job: Job) -> dict[str, Any] | None:
        """The signed order, its claim, and what the node agent reported back.

        None of that is on the Job — the Job keeps only the order id — so the summary would otherwise
        stop at 'MOMUS says fixed' and never say whether the deploy actually happened."""
        order_id = str((job.result or {}).get("deploy_order_id") or "")
        queued = self.orders.get(order_id) if order_id else None
        return queued.to_dict() if queued else None

    async def _run(self, job: Job) -> Job:  # type: ignore[name-defined]
        while job.attempts < self.cfg.max_attempts:
            job.attempts += 1

            # 1. FIXING — the AI-Factory writes a patch.
            job.transition(JobState.FIXING, f"attempt {job.attempts}: requesting fix from AI-Factory")
            self.store.upsert(job)
            fix = await self.factory.request_fix(job.ticket)
            if not fix.get("ok"):
                job.transition(JobState.FAILED, f"factory error: {fix.get('error')}")
                self.store.upsert(job)
                continue
            image = (fix.get("patch") or {}).get("image", "")

            # 2. RETESTING — MOMUS re-runs the exact probe on the patched build (the gate).
            job.transition(JobState.RETESTING, "asking MOMUS to re-test the patched build")
            self.store.upsert(job)
            verdict = await self._retest_observed(job.finding_id, "gate")
            # An INCONCLUSIVE gate is not a verdict on the patch — MOMUS is unreachable, refusing, or
            # cannot resolve the finding. Another Factory attempt cannot fix a gate that will not
            # run, and looping would burn the budget and then escalate blaming the patch. So stop
            # here and escalate naming the real cause, which is an operator's to clear.
            if str(verdict.get("outcome") or "") == "inconclusive":
                return await self._finish(job, JobState.ESCALATED,
                                          f"deploy gate could not run — not a verdict on the fix: "
                                          f"{verdict.get('detail', '')}")
            if not verdict.get("fixed"):
                job.transition(JobState.FAILED,
                               f"retest not fixed ({verdict.get('outcome')}): {verdict.get('detail','')}")
                self.store.upsert(job)
                continue  # loop back to FIXING for another attempt

            # 3. DEPLOYING — sign a DeployOrder embedding MOMUS's fixed-verdict; the node agent ships it.
            job.transition(JobState.DEPLOYING, "MOMUS confirms fixed; signing deploy order for the node agent")
            self.store.upsert(job)
            order = DeployOrder(finding_id=job.finding_id, service=job.component,
                                host=job.component, image=image, momus_verdict=verdict)
            if self._signer:
                sign_deploy_order(order, self._signer)
            # PUBLISH the order; the addressed agent claims it on its next poll and verifies the
            # chain locally before touching anything. The conductor never executes a deploy itself.
            # Publishing cannot be "rejected" — the agent's verdict arrives later, on
            # /agent/v1/result. The old `if not dispatch["accepted"]` here tested a literal
            # True and could never fire; the real rejection path is the agent's result.
            queued = self.orders.publish(host=job.component, service=job.component,
                                         finding_id=job.finding_id, order=order.to_dict())
            dispatch = {"accepted": True, "order_id": queued.order_id, "queued": True,
                        "note": f"signed order published for host '{job.component}'; the node agent "
                                f"will claim it on its next poll and verify the chain locally"}

            # 4. VERIFYING — a final IN-PLACE MOMUS retest confirms the live container is clean.
            job.transition(JobState.VERIFYING, "deploy accepted; final in-place MOMUS retest")
            self.store.upsert(job)
            post = await self._retest_observed(job.finding_id, "post-deploy")
            job.result = {"fix": fix, "gate_verdict": verdict, "deploy": dispatch, "post_deploy_verdict": post,
                          "deploy_order_id": order.order_id}
            if post.get("fixed") or self.cfg.dry_run:
                return await self._finish(job, JobState.DONE, "fixed, deployed and verified in place")
            job.transition(JobState.FAILED, "regressed after deploy — will retry")
            self.store.upsert(job)

        # Retries exhausted.
        return await self._finish(job, JobState.ESCALATED,
                                  f"{job.attempts} attempts exhausted — escalated to a human")
