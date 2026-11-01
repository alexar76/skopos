"""The fleet's own requests to itself: monitors, health checks, hubs polling each other.

On a fleet that watches itself these are most of the log. On 2026-11-01 one SKOPOS stored
~988k requests a day, ~93% of them from the fleet's own servers (discovery monitors, health
checks, federation polling), and its database grew ~0.85 GB a day toward a 90-day window
larger than its disk. They also inflate every request count on the dashboard.

With ``store_own_traffic`` off, a request whose client address is one of the fleet's own
servers is not stored as a row; it is counted per day and server in ``own_traffic_daily``
(once per log line, through the same deduplication as every row). The fleet's addresses are
the configured servers' addresses written as IPs, plus ``own_addresses``. Only exact public
addresses count: a private address can be a docker gateway standing in front of real visitors,
and a host name is not resolved, because the day it points at a CDN its addresses would be
every visitor's.
"""

from __future__ import annotations

import ipaddress

from .geoip import is_private_ip


def _literal(host: str) -> frozenset[str]:
    try:
        return frozenset({str(ipaddress.ip_address((host or "").strip().strip("[]")))})
    except ValueError:
        return frozenset()


def own_addresses(cfg) -> frozenset[str] | None:
    """The fleet's public client addresses, or None when own traffic is stored like any other."""
    if getattr(cfg, "store_own_traffic", True):
        return None
    found: set[str] = set()
    for server in getattr(cfg, "servers", None) or []:
        found |= _literal(server.ssh.host)
    for extra in getattr(cfg, "own_addresses", ()) or ():
        found |= _literal(extra)
    return frozenset(a for a in found if not is_private_ip(a))


def is_own(remote_addr: str | None, own: frozenset[str] | None) -> bool:
    if not own or not remote_addr:
        return False
    try:
        return str(ipaddress.ip_address(remote_addr.strip())) in own
    except ValueError:
        return False


__all__ = ["is_own", "own_addresses"]
