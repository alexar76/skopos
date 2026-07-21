from __future__ import annotations

from dataclasses import dataclass

from ..config import AppConfig, ServerConfig
from ..db_dialect import resolve_db_target
from ..db import connect, init_db, now_utc_iso
from ..geoip import GeoIPResolver
from .audit import SecurityFinding, audit_snapshot
from .knock_analyzer import enrich_knocks, http_probes_from_db
from .port_knocks import fetch_port_knocks
from .probe import ServerSnapshot, probe_server
from .store import insert_knock_events, save_scan


@dataclass(frozen=True)
class ScanResult:
    server_name: str
    ok: bool
    snapshot_id: int | None = None
    findings_count: int = 0
    knocks_inserted: int = 0
    error: str | None = None


def _make_geo(mmdb_path: str | None) -> GeoIPResolver:
    return GeoIPResolver(mmdb_path)


def scan_server(server: ServerConfig, db_target: str, *, mmdb_path: str | None = None) -> ScanResult:
    con = connect(db_target)
    init_db(con)
    geo = _make_geo(mmdb_path)
    try:
        scanned_at = now_utc_iso()
        snap = probe_server(server, scanned_at_utc=scanned_at)
        findings = audit_snapshot(snap)

        # Port knock collection + HTTP probe merge
        ssh_events = fetch_port_knocks(server)
        http_events = http_probes_from_db(con, server.name, hours=168)
        all_events = ssh_events + http_events
        enriched = enrich_knocks(all_events, geo=geo)
        knock_n = insert_knock_events(con, server.name, server.ssh.host, enriched)

        sid = save_scan(con, snap, findings)
        return ScanResult(
            server_name=server.name,
            ok=True,
            snapshot_id=sid,
            findings_count=len(findings),
            knocks_inserted=knock_n,
        )
    except Exception as e:
        return ScanResult(server_name=server.name, ok=False, error=repr(e))
    finally:
        geo.close()
        con.close()


def scan_all_servers(cfg: AppConfig) -> list[ScanResult]:
    mmdb = getattr(cfg, "geoip_mmdb_path", None)
    return [scan_server(s, resolve_db_target(cfg), mmdb_path=mmdb) for s in cfg.servers]
