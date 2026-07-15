"""Public non-secret SKOPOS status (healthz + economy)."""

from __future__ import annotations

import json
import os


def build_status(*, config_path: str | None = None) -> dict:
    db_url = os.environ.get("SKOPOS_DATABASE_URL", "")
    db = "postgresql" if db_url.startswith("postgresql") else "sqlite"
    cfg_path = config_path or os.environ.get("SKOPOS_CONFIG_PATH", "/app/servers.yaml")
    out: dict = {
        "ok": True,
        "service": "skopos",
        "version": os.environ.get("SKOPOS_VERSION", "0.1.0"),
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
        row = con.execute("SELECT COUNT(*) FROM http_requests").fetchone()
        out["requests_total"] = int(row[0] if row else 0)
        snap = con.execute(
            "SELECT payload_json FROM security_snapshots ORDER BY scanned_at_utc DESC LIMIT 1"
        ).fetchone()
        if snap and snap[0]:
            from skopos.security.store import snapshot_score

            payload = json.loads(snap[0]) if isinstance(snap[0], str) else snap[0]
            findings = payload.get("findings") if isinstance(payload, dict) else []
            if isinstance(findings, list):
                out["security_score"] = snapshot_score(findings)
        con.close()
    except Exception:
        pass
    return out
