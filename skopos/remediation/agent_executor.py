"""The deploy executor that runs ON a SKOPOS node agent — the constrained deployer.

This is the *only* code path by which a redeploy happens, and it is deliberately small and
paranoid. Before it does anything it runs ``verify_deploy_chain`` (MOMUS-fixed verdict +
conductor signature + local service allowlist). Only then does it run a single, fixed-shape
redeploy command for that one allowlisted service. It never accepts an arbitrary command; the
DeployOrder carries a service name, not a shell string, so there is nothing to inject.

Default is DRY-RUN: it validates and reports the command it *would* run, executing nothing. A real
node agent flips ``dry_run=False`` and provides the compose file for its host.
"""

from __future__ import annotations

import shlex
import subprocess
from typing import Any

from skopos.remediation.deploy_order import verify_deploy_chain


class NodeDeployExecutor:
    def __init__(self, *, conductor_pubkey: str, momus_pubkey: str,
                 service_allowlist: list[str], compose_file: str = "",
                 dry_run: bool = True):
        self.conductor_pubkey = conductor_pubkey
        self.momus_pubkey = momus_pubkey
        self.service_allowlist = list(service_allowlist)
        self.compose_file = compose_file
        self.dry_run = dry_run

    def execute(self, order: dict[str, Any]) -> dict[str, Any]:
        ok, reason = verify_deploy_chain(
            order, conductor_pubkey=self.conductor_pubkey, momus_pubkey=self.momus_pubkey,
            service_allowlist=self.service_allowlist)
        if not ok:
            return {"deployed": False, "refused": True, "reason": reason}

        service = order["service"]
        # A single, fixed-shape command. The service name is allowlisted and passed as an argv
        # element (never interpolated into a shell string), so there is no command-injection surface.
        argv = ["docker", "compose"]
        if self.compose_file:
            argv += ["-f", self.compose_file]
        argv += ["up", "-d", "--no-deps", "--force-recreate", service]

        if self.dry_run:
            return {"deployed": False, "dry_run": True, "reason": reason,
                    "would_run": " ".join(shlex.quote(a) for a in argv)}
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=300, check=False)
            return {"deployed": proc.returncode == 0, "returncode": proc.returncode,
                    "reason": reason, "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]}
        except (subprocess.SubprocessError, OSError) as exc:
            return {"deployed": False, "reason": reason, "error": f"{type(exc).__name__}: {exc}"}
