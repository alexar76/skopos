"""Remediation jobs — the tracked state machine behind each MOMUS ticket.

    RECEIVED ─▶ FIXING ─▶ RETESTING ─▶ DEPLOYING ─▶ VERIFYING ─▶ DONE
                   │           │            │            │
                   └─ FAILED ◀─┴────────────┴────────────┘   (bounded retries loop back to FIXING)
    ESCALATED  (security-core findings, or retries exhausted → human)

Persisted as JSONL so the SKOPOS dashboard can render a live board and a restart loses nothing.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class JobState(str, Enum):
    RECEIVED = "received"
    FIXING = "fixing"          # AI-Factory is producing a patch
    RETESTING = "retesting"    # MOMUS is re-running the probe on the patched build
    DEPLOYING = "deploying"    # a node agent is redeploying the service
    VERIFYING = "verifying"    # final in-place MOMUS retest after deploy
    DONE = "done"              # fixed + deployed + verified
    FAILED = "failed"          # gave up (bounded retries exhausted)
    ESCALATED = "escalated"    # routed to a human (security core, or repeated failure)


@dataclass
class Job:
    finding_id: str
    component: str
    probe: str
    severity: str
    route: str                 # "auto" | "human-governance"
    state: str = JobState.RECEIVED.value
    attempts: int = 0
    ticket: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    updated_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def transition(self, state: JobState, note: str = "") -> None:
        self.state = state.value
        self.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.history.append({"ts": self.updated_at, "state": state.value, "note": note})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class JobStore:
    def __init__(self, path: str):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, Job] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                self._jobs[d["finding_id"]] = Job(**d)
            except (json.JSONDecodeError, KeyError, TypeError):
                continue

    def _persist(self) -> None:
        # Rewrite the whole file (job count is small; keeps one line per current job state).
        with self._path.open("w", encoding="utf-8") as fh:
            for job in self._jobs.values():
                fh.write(json.dumps(job.to_dict(), ensure_ascii=False) + "\n")

    def get(self, finding_id: str) -> Job | None:
        return self._jobs.get(finding_id)

    def upsert(self, job: Job) -> Job:
        self._jobs[job.finding_id] = job
        self._persist()
        return job

    def all(self) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda j: j.updated_at, reverse=True)
