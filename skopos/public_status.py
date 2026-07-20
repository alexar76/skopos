"""Public non-secret SKOPOS status (healthz + economy)."""

from __future__ import annotations

import os


def build_status(*, config_path: str | None = None) -> dict:
    db_url = os.environ.get("SKOPOS_DATABASE_URL", "")
    db = "postgresql" if db_url.startswith("postgresql") else "sqlite"
    cfg_path = config_path or os.environ.get("SKOPOS_CONFIG_PATH", "/app/servers.yaml")
    out: dict = {
        "ok": True,
        "service": "skopos",
        "version": os.environ.get("SKOPOS_VERSION", "0.1.1"),
        "database": db,
        "log_parsers": ["nginx", "apache"],
        "servers_monitored": 0,
        "requests_total": 0,
        "economy_enabled": os.environ.get("SKOPOS_AIMARKET_ENABLED", "0").strip().lower()
        in ("1", "true", "yes", "on"),
    }
    try:
        from skopos.config import load_app_env, load_config
        from skopos.db import connect_for_config, init_db

        load_app_env()
        cfg = load_config(cfg_path)
        out["servers_monitored"] = len(cfg.servers or [])
        con = connect_for_config(cfg)
        init_db(con)
        row = con.execute("SELECT COUNT(*) AS c FROM http_requests").fetchone()
        if isinstance(row, dict):
            out["requests_total"] = int(row.get("c") or 0)
        else:
            out["requests_total"] = int(row[0] if row else 0)
        snap = con.execute(
            "SELECT id FROM security_snapshots ORDER BY scanned_at_utc DESC LIMIT 1"
        ).fetchone()
        snap_id = (snap.get("id") if isinstance(snap, dict) else snap[0]) if snap else None
        if snap_id is not None:
            from skopos.security.store import findings_for_snapshot, snapshot_score

            findings = findings_for_snapshot(con, int(snap_id))
            out["security_score"] = snapshot_score(findings)
        con.close()
    except Exception:
        pass
    return out
