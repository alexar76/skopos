from __future__ import annotations

import argparse

from skopos.config import load_app_env

load_app_env()

from skopos.collector import collect_once
from skopos.config import load_config
from skopos.log_sources import resolve_log_sources
from skopos.security.collector import scan_all_servers


def main() -> int:
    ap = argparse.ArgumentParser(prog="skoposctl", description="SKOPOS collector control")
    ap.add_argument("--config", default="./servers.yaml", help="Path to servers.yaml")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("collect", help="Collect once from all servers")
    sub.add_parser("discover", help="List HTTP log sources discovered on servers")
    sub.add_parser("security-scan", help="Run security probe + audit on all servers")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.cmd == "collect":
        res = collect_once(cfg)
        for r in res:
            print(f"{r.server_name}: fetched={r.fetched_lines} inserted={r.inserted_rows} sources={len(r.log_paths)}")
            for p in r.log_paths:
                print(f"  - {p}")
        return 0

    if args.cmd == "discover":
        for s in cfg.servers:
            sources = resolve_log_sources(s)
            print(f"{s.name} ({s.ssh.host}:{s.ssh.port}) — {len(sources)} source(s)")
            for src in sources:
                print(f"  [{src.kind}/{src.parser}] {src.id}")
        return 0

    if args.cmd == "security-scan":
        results = scan_all_servers(cfg)
        for r in results:
            if r.ok:
                print(
                    f"{r.server_name}: ok findings={r.findings_count} "
                    f"knocks_inserted={r.knocks_inserted} snapshot_id={r.snapshot_id}"
                )
            else:
                print(f"{r.server_name}: ERROR {r.error}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
