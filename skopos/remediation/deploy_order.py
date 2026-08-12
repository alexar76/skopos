"""The signed DeployOrder — the authorization a node agent needs before it will redeploy anything.

The order chains two signatures so no single party can make a deploy happen on its own:

  1. MOMUS signs a ``fixed`` retest verdict (finding no longer reproduces on the patched build).
  2. SKOPOS's conductor signs a DeployOrder that EMBEDS that verdict and names the exact service +
     host + image to ship.

A node agent runs ``verify_deploy_chain`` before touching anything: it checks the conductor's
signature under the SKOPOS pubkey it learned at enrollment, checks the embedded verdict's signature
under MOMUS's known pubkey, checks the verdict is actually ``fixed`` and bound to this finding, and
checks the service is on its OWN local allowlist. Any failure → refuse. This is the whole reason a
compromised conductor still cannot ship arbitrary code to a host: it cannot forge MOMUS's verdict,
and the agent will not deploy a service it was not pre-authorized to touch.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any

try:
    from oracle_core.signing import Signer
except Exception:  # pragma: no cover - oracle-core always present in the ecosystem venv
    Signer = None  # type: ignore


def _canon(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass
class DeployOrder:
    """A conductor-signed instruction to redeploy ONE service, gated on a MOMUS fixed-verdict."""

    finding_id: str
    service: str              # the container/service to redeploy (must be on the agent's allowlist)
    host: str                 # which fleet host / which node agent
    image: str = ""           # image ref / tag to promote (empty → rebuild from source)
    momus_verdict: dict[str, Any] = field(default_factory=dict)  # the signed FixVerdict from MOMUS
    order_id: str = ""
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    conductor_pubkey: str = ""
    signature: dict[str, Any] = field(default_factory=dict)

    def canonical(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("signature", None)
        return d

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sign_deploy_order(order: DeployOrder, conductor_signer: "Signer") -> DeployOrder:
    if not order.order_id:
        order.order_id = f"deploy-{order.finding_id}-{int(time.time())}"
    order.conductor_pubkey = conductor_signer.public_key_b64
    order.signature = conductor_signer.sign_payload(_canon(order.canonical()))
    return order


def verify_deploy_chain(order: dict[str, Any], *, conductor_pubkey: str, momus_pubkey: str,
                        service_allowlist: list[str]) -> tuple[bool, str]:
    """Run ON the node agent before deploying. Returns (ok, reason). Fails closed on anything odd."""
    if Signer is None:
        return False, "no signing backend available"
    # 1. The order must be signed by the conductor key the agent trusts (from enrollment).
    sig = order.get("signature") or {}
    body = {k: v for k, v in order.items() if k != "signature"}
    if not sig.get("value"):
        return False, "deploy order is unsigned"
    if order.get("conductor_pubkey") != conductor_pubkey:
        return False, "deploy order not signed by the enrolled conductor key"
    if not Signer.verify_signature_object(_canon(body), sig, conductor_pubkey):
        return False, "conductor signature does not verify"
    # 2. The embedded MOMUS verdict must verify under MOMUS's known key, and say fixed for THIS finding.
    verdict = order.get("momus_verdict") or {}
    vsig = verdict.get("signature") or {}
    vbody = {k: v for k, v in verdict.items() if k != "signature"}
    if not vsig.get("value"):
        return False, "no MOMUS retest verdict embedded"
    if not Signer.verify_signature_object(_canon(vbody), vsig, momus_pubkey):
        return False, "MOMUS verdict signature does not verify (forged fixed-verdict?)"
    if not verdict.get("fixed"):
        return False, "MOMUS verdict is not 'fixed' — deploy refused"
    if verdict.get("finding_id") != order.get("finding_id"):
        return False, "MOMUS verdict is for a different finding (transplanted)"
    # 3. The agent only ships services it was pre-authorized to touch.
    if order.get("service") not in service_allowlist:
        return False, f"service '{order.get('service')}' not on this agent's deploy allowlist"
    return True, "chain verified: MOMUS-fixed + conductor-signed + service allowlisted"
