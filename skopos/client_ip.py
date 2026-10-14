"""Resolve the CALLER's address — never a value the caller chose.

Both of SKOPOS's per-address budgets were keyed on an attacker-controlled string. The nginx
in front of the service sets both headers:

    proxy_set_header X-Real-IP $remote_addr;                      # nginx overwrites this
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;  # APPENDS to the client's

``$proxy_add_x_forwarded_for`` appends the real peer to the RIGHT of whatever arrived, so the
LEFT-most hop is whatever the client typed. Reading it left-first meant:

* the DB-persisted login lockout (5 attempts / 300 s) could be given a fresh bucket per
  guess, leaving the operator dashboard password open to unmetered online guessing;
* the ``/agent/chat`` LLM-spend limiter — which exists so a stolen agent token cannot burn
  unbounded paid calls — got a fresh empty bucket per request.

The shape here is the one ATLAS already uses (``atlas/atlas/main.py:_client_ip``): proxy
headers are evidence only when the direct peer IS our own proxy; otherwise they are a
stranger's claim. Then prefer ``X-Real-IP``, and fall back to counting ``X-Forwarded-For``
from the RIGHT, because our hop is the one on the right.
"""

from __future__ import annotations

import ipaddress
import os

#: How many proxies sit in front of us. 1 = the local nginx. 0 disables header trust.
def trusted_proxy_hops() -> int:
    try:
        return max(0, int(os.environ.get("SKOPOS_TRUSTED_PROXY_HOPS", "1")))
    except (TypeError, ValueError):
        return 1


def peer_is_local_proxy(peer: str) -> bool:
    """Is the direct TCP peer plausibly our own reverse proxy?

    SKOPOS runs on loopback behind nginx on the same host, so anything else is a direct
    caller whose headers carry no authority.
    """
    peer = (peer or "").strip()
    if not peer:
        return False
    try:
        addr = ipaddress.ip_address(peer.split("%")[0])
    except ValueError:
        return False
    return addr.is_loopback or addr.is_private or addr.is_link_local


def resolve(peer: str, get_header) -> str:
    """The address to key a budget on.

    ``get_header`` is a callable taking a header name (case-insensitive lookup is the
    caller's job — both Streamlit's header map and http.client's are case-insensitive).
    """
    if trusted_proxy_hops() > 0 and peer_is_local_proxy(peer):
        real = str(get_header("X-Real-IP") or "").strip()
        if real:
            return real[:64]
        forwarded = str(get_header("X-Forwarded-For") or "").strip()
        if forwarded:
            hops = [h.strip() for h in forwarded.split(",") if h.strip()]
            if hops:
                want = trusted_proxy_hops()
                return (hops[-want] if len(hops) >= want else hops[-1])[:64]
    return (peer or "unknown")[:64]
