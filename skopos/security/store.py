from __future__ import annotations

import json

from ..db import DbConnection, now_utc_iso, sha1_hex
from ..db_dialect import cutoff_iso, group_concat_distinct, is_integrity_error, normalize_row, scan_day_expr
from .audit import SecurityFinding
from .knock_analyzer import EnrichedKnock
from .probe import ServerSnapshot

SECURITY_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS security_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  server_name TEXT NOT NULL,
  host TEXT,
  scanned_at_utc TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_security_snapshots_server_ts
  ON security_snapshots(server_name, scanned_at_utc DESC);

CREATE TABLE IF NOT EXISTS security_findings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id INTEGER NOT NULL,
  server_name TEXT NOT NULL,
  severity TEXT NOT NULL,
  category TEXT NOT NULL,
  title TEXT NOT NULL,
  detail TEXT NOT NULL,
  recommendation TEXT,
  FOREIGN KEY (snapshot_id) REFERENCES security_snapshots(id)
);
CREATE INDEX IF NOT EXISTS idx_security_findings_server
  ON security_findings(server_name, severity);

CREATE TABLE IF NOT EXISTS port_knock_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  server_name TEXT NOT NULL,
  server_ip TEXT,
  remote_addr TEXT NOT NULL,
  dest_port INTEGER,
  src_port INTEGER,
  event_type TEXT NOT NULL,
  source_log TEXT,
  username TEXT,
  ts_utc TEXT,
  country_code TEXT,
  country_name TEXT,
  actor_class TEXT,
  actor_label TEXT,
  threat_score INTEGER DEFAULT 0,
  line_raw TEXT NOT NULL,
  line_sha1 TEXT NOT NULL,
  ingested_at_utc TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_port_knock_dedup
  ON port_knock_events(server_name, line_sha1);
CREATE INDEX IF NOT EXISTS idx_port_knock_server_ts
  ON port_knock_events(server_name, ts_utc DESC);
CREATE INDEX IF NOT EXISTS idx_port_knock_remote
  ON port_knock_events(remote_addr, server_name);
CREATE INDEX IF NOT EXISTS idx_port_knock_port
  ON port_knock_events(dest_port, server_name);

CREATE TABLE IF NOT EXISTS tls_certificates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  server_name TEXT,
  domain TEXT NOT NULL,
  port INTEGER NOT NULL DEFAULT 443,
  issuer TEXT,
  subject TEXT,
  sans TEXT,
  not_before_utc TEXT,
  not_after_utc TEXT,
  days_remaining INTEGER,
  status TEXT NOT NULL,
  error TEXT,
  source TEXT,
  checked_at_utc TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tls_certificates_domain_port
  ON tls_certificates(domain, port);
CREATE INDEX IF NOT EXISTS idx_tls_certificates_server
  ON tls_certificates(server_name, checked_at_utc DESC);
"""

SECURITY_SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS security_snapshots (
  id BIGSERIAL PRIMARY KEY,
  server_name TEXT NOT NULL,
  host TEXT,
  scanned_at_utc TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_security_snapshots_server_ts
  ON security_snapshots(server_name, scanned_at_utc DESC);

CREATE TABLE IF NOT EXISTS security_findings (
  id BIGSERIAL PRIMARY KEY,
  snapshot_id BIGINT NOT NULL,
  server_name TEXT NOT NULL,
  severity TEXT NOT NULL,
  category TEXT NOT NULL,
  title TEXT NOT NULL,
  detail TEXT NOT NULL,
  recommendation TEXT,
  FOREIGN KEY (snapshot_id) REFERENCES security_snapshots(id)
);
CREATE INDEX IF NOT EXISTS idx_security_findings_server
  ON security_findings(server_name, severity);

CREATE TABLE IF NOT EXISTS port_knock_events (
  id BIGSERIAL PRIMARY KEY,
  server_name TEXT NOT NULL,
  server_ip TEXT,
  remote_addr TEXT NOT NULL,
  dest_port INTEGER,
  src_port INTEGER,
  event_type TEXT NOT NULL,
  source_log TEXT,
  username TEXT,
  ts_utc TEXT,
  country_code TEXT,
  country_name TEXT,
  actor_class TEXT,
  actor_label TEXT,
  threat_score INTEGER DEFAULT 0,
  line_raw TEXT NOT NULL,
  line_sha1 TEXT NOT NULL,
  ingested_at_utc TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_port_knock_dedup
  ON port_knock_events(server_name, line_sha1);
CREATE INDEX IF NOT EXISTS idx_port_knock_server_ts
  ON port_knock_events(server_name, ts_utc DESC);
CREATE INDEX IF NOT EXISTS idx_port_knock_remote
  ON port_knock_events(remote_addr, server_name);
CREATE INDEX IF NOT EXISTS idx_port_knock_port
  ON port_knock_events(dest_port, server_name);

CREATE TABLE IF NOT EXISTS tls_certificates (
  id BIGSERIAL PRIMARY KEY,
  server_name TEXT,
  domain TEXT NOT NULL,
  port INTEGER NOT NULL DEFAULT 443,
  issuer TEXT,
  subject TEXT,
  sans TEXT,
  not_before_utc TEXT,
  not_after_utc TEXT,
  days_remaining INTEGER,
  status TEXT NOT NULL,
  error TEXT,
  source TEXT,
  checked_at_utc TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tls_certificates_domain_port
  ON tls_certificates(domain, port);
CREATE INDEX IF NOT EXISTS idx_tls_certificates_server
  ON tls_certificates(server_name, checked_at_utc DESC);
"""


def _row_dict(row) -> dict:
    if isinstance(row, dict):
        return row
    return dict(row)


def init_security_db(con: DbConnection) -> None:
    script = SECURITY_SCHEMA_POSTGRES if con.backend == "postgresql" else SECURITY_SCHEMA_SQLITE
    con.executescript(script)
    con.commit()


def save_scan(
    con: DbConnection,
    snap: ServerSnapshot,
    findings: list[SecurityFinding],
) -> int:
    init_security_db(con)
    payload = json.dumps(snap.to_dict(), ensure_ascii=False)
    if con.backend == "postgresql":
        cur = con.execute(
            """
            INSERT INTO security_snapshots(server_name, host, scanned_at_utc, payload_json)
            VALUES (?, ?, ?, ?) RETURNING id
            """,
            (snap.server_name, snap.host, snap.scanned_at_utc, payload),
        )
        row = cur.fetchone()
        snapshot_id = int(row["id"])
    else:
        cur = con.execute(
            """
            INSERT INTO security_snapshots(server_name, host, scanned_at_utc, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (snap.server_name, snap.host, snap.scanned_at_utc, payload),
        )
        snapshot_id = int(cur.lastrowid or 0)

    for f in findings:
        con.execute(
            """
            INSERT INTO security_findings(
              snapshot_id, server_name, severity, category, title, detail, recommendation
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                snap.server_name,
                f.severity,
                f.category,
                f.title,
                f.detail,
                f.recommendation,
            ),
        )
    con.commit()
    return snapshot_id


def latest_snapshots(con: DbConnection, server_names: list[str] | None = None) -> list[dict]:
    init_security_db(con)
    if server_names:
        placeholders = ",".join("?" * len(server_names))
        q = f"""
          SELECT s.* FROM security_snapshots s
          INNER JOIN (
            SELECT server_name, MAX(scanned_at_utc) AS max_ts
            FROM security_snapshots
            WHERE server_name IN ({placeholders})
            GROUP BY server_name
          ) t ON s.server_name = t.server_name AND s.scanned_at_utc = t.max_ts
        """
        rows = con.execute(q, server_names).fetchall()
    else:
        rows = con.execute(
            """
            SELECT s.* FROM security_snapshots s
            INNER JOIN (
              SELECT server_name, MAX(scanned_at_utc) AS max_ts
              FROM security_snapshots GROUP BY server_name
            ) t ON s.server_name = t.server_name AND s.scanned_at_utc = t.max_ts
            """
        ).fetchall()
    return [_row_dict(r) for r in rows]


def findings_for_snapshot(con: DbConnection, snapshot_id: int) -> list[dict]:
    init_security_db(con)
    rows = con.execute(
        "SELECT * FROM security_findings WHERE snapshot_id = ? ORDER BY id",
        (snapshot_id,),
    ).fetchall()
    return [_row_dict(r) for r in rows]


def latest_findings_by_server(con: DbConnection, server_name: str) -> list[dict]:
    init_security_db(con)
    row = con.execute(
        """
        SELECT id FROM security_snapshots
        WHERE server_name = ? ORDER BY scanned_at_utc DESC LIMIT 1
        """,
        (server_name,),
    ).fetchone()
    if not row:
        return []
    rid = row["id"] if isinstance(row, dict) else row[0]
    return findings_for_snapshot(con, int(rid))


def load_snapshot_payload(row: dict) -> ServerSnapshot:
    data = json.loads(row["payload_json"])
    return ServerSnapshot.from_dict(data)


def insert_knock_events(
    con: DbConnection,
    server_name: str,
    server_ip: str,
    events: list[EnrichedKnock],
) -> int:
    init_security_db(con)
    inserted = 0
    now = now_utc_iso()
    for e in events:
        h = sha1_hex(e.line_raw)
        try:
            cur = con.execute(
                """
                INSERT INTO port_knock_events(
                  server_name, server_ip, remote_addr, dest_port, src_port,
                  event_type, source_log, username, ts_utc,
                  country_code, country_name, actor_class, actor_label,
                  threat_score, line_raw, line_sha1, ingested_at_utc
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT DO NOTHING
                """,
                (
                    server_name,
                    server_ip,
                    e.remote_addr,
                    e.dest_port,
                    e.src_port,
                    e.event_type,
                    e.source_log,
                    e.username,
                    e.ts_utc,
                    e.country_code,
                    e.country_name,
                    e.actor_class,
                    e.actor_label,
                    e.threat_score,
                    e.line_raw,
                    h,
                    now,
                ),
            )
            if con.backend == "postgresql":
                if getattr(cur._cursor, "rowcount", 0) == 0:
                    continue
            inserted += 1
        except Exception as exc:
            if is_integrity_error(exc):
                if con.backend == "postgresql":
                    con.connection.rollback()
                continue
            raise
    con.commit()
    return inserted


def load_knock_events(
    con: DbConnection,
    server_names: list[str] | None = None,
    *,
    hours: int = 168,
    limit: int = 50000,
) -> list[dict]:
    init_security_db(con)
    since = cutoff_iso(hours=hours)
    params: list = [since, limit]
    if server_names:
        ph = ",".join("?" * len(server_names))
        q = f"""
          SELECT * FROM port_knock_events
          WHERE server_name IN ({ph})
            AND (ts_utc IS NULL OR ts_utc >= ?)
          ORDER BY COALESCE(ts_utc, ingested_at_utc) DESC
          LIMIT ?
        """
        params = list(server_names) + params
    else:
        q = """
          SELECT * FROM port_knock_events
          WHERE ts_utc IS NULL OR ts_utc >= ?
          ORDER BY COALESCE(ts_utc, ingested_at_utc) DESC
          LIMIT ?
        """
    rows = con.execute(q, params).fetchall()
    return [_row_dict(r) for r in rows]


def knock_summary_by_actor(con: DbConnection, server_names: list[str] | None, hours: int = 168) -> list[dict]:
    init_security_db(con)
    since = cutoff_iso(hours=hours)
    params: list = [since]
    filter_sql = ""
    if server_names:
        ph = ",".join("?" * len(server_names))
        filter_sql = f"AND server_name IN ({ph})"
        params = list(server_names) + params
    ports = group_concat_distinct("dest_port", con.backend)
    servers = group_concat_distinct("server_name", con.backend)
    q = f"""
      SELECT
        remote_addr,
        MAX(country_code) AS country_code,
        MAX(country_name) AS country_name,
        MAX(actor_class) AS actor_class,
        MAX(actor_label) AS actor_label,
        MAX(threat_score) AS threat_score,
        COUNT(*) AS hits,
        COUNT(DISTINCT dest_port) AS ports_targeted,
        {ports} AS port_list,
        {servers} AS servers,
        MAX(event_type) AS last_event_type
      FROM port_knock_events
      WHERE (ts_utc IS NULL OR ts_utc >= ?)
        {filter_sql}
      GROUP BY remote_addr
      ORDER BY threat_score DESC, hits DESC
      LIMIT 200
    """
    rows = con.execute(q, params).fetchall()
    return [_row_dict(r) for r in rows]


def list_scan_history(
    con: DbConnection,
    server_names: list[str] | None = None,
    *,
    limit: int = 100,
    days: int | None = None,
) -> list[dict]:
    init_security_db(con)
    params: list = []
    filters: list[str] = []
    if server_names:
        ph = ",".join("?" * len(server_names))
        filters.append(f"s.server_name IN ({ph})")
        params.extend(server_names)
    if days is not None:
        filters.append("s.scanned_at_utc >= ?")
        params.append(cutoff_iso(days=days))
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    q = f"""
      SELECT
        s.id AS snapshot_id,
        s.server_name,
        s.host,
        s.scanned_at_utc,
        COUNT(f.id) AS findings_total,
        SUM(CASE WHEN f.severity = 'critical' THEN 1 ELSE 0 END) AS critical,
        SUM(CASE WHEN f.severity = 'high' THEN 1 ELSE 0 END) AS high,
        SUM(CASE WHEN f.severity = 'medium' THEN 1 ELSE 0 END) AS medium,
        SUM(CASE WHEN f.severity = 'low' THEN 1 ELSE 0 END) AS low
      FROM security_snapshots s
      LEFT JOIN security_findings f ON f.snapshot_id = s.id
      {where}
      GROUP BY s.id
      ORDER BY s.scanned_at_utc DESC
      LIMIT ?
    """
    params.append(limit)
    rows = con.execute(q, params).fetchall()
    return [_row_dict(r) for r in rows]


def findings_for_snapshots(con: DbConnection, snapshot_ids: list[int]) -> dict[int, list[dict]]:
    init_security_db(con)
    if not snapshot_ids:
        return {}
    ph = ",".join("?" * len(snapshot_ids))
    rows = con.execute(
        f"SELECT * FROM security_findings WHERE snapshot_id IN ({ph}) ORDER BY snapshot_id, id",
        snapshot_ids,
    ).fetchall()
    out: dict[int, list[dict]] = {sid: [] for sid in snapshot_ids}
    for r in rows:
        row = _row_dict(r)
        out[int(row["snapshot_id"])].append(row)
    return out


def snapshot_score(findings: list[dict]) -> int:
    from .posture import _SEV_PENALTY

    score = 100
    for f in findings:
        score -= _SEV_PENALTY.get(str(f.get("severity", "")), 0)
    return max(0, min(100, score))


def fleet_score_history(
    con: DbConnection,
    server_names: list[str],
    *,
    days: int = 30,
) -> list[dict]:
    history = list_scan_history(con, server_names, limit=500, days=days)
    if not history:
        return []
    ids = [int(r["snapshot_id"]) for r in history]
    findings_map = findings_for_snapshots(con, ids)
    points: list[dict] = []
    for row in history:
        sid = int(row["snapshot_id"])
        findings = findings_map.get(sid, [])
        score = snapshot_score(findings)
        points.append(
            {
                "snapshot_id": sid,
                "server_name": row["server_name"],
                "scanned_at_utc": row["scanned_at_utc"],
                "score": score,
                "findings_total": int(row.get("findings_total") or 0),
                "critical": int(row.get("critical") or 0),
                "high": int(row.get("high") or 0),
            }
        )
    points.sort(key=lambda x: x["scanned_at_utc"])
    return points


def findings_trend(
    con: DbConnection,
    server_names: list[str] | None,
    *,
    days: int = 30,
) -> list[dict]:
    init_security_db(con)
    since = cutoff_iso(days=days)
    params: list = [since]
    filter_sql = ""
    if server_names:
        ph = ",".join("?" * len(server_names))
        filter_sql = f"AND s.server_name IN ({ph})"
        params = list(server_names) + params
    day_expr = scan_day_expr("s.scanned_at_utc", con.backend)
    q = f"""
      SELECT
        {day_expr} AS scan_day,
        f.severity,
        COUNT(*) AS cnt
      FROM security_snapshots s
      JOIN security_findings f ON f.snapshot_id = s.id
      WHERE s.scanned_at_utc >= ?
        {filter_sql}
      GROUP BY scan_day, f.severity
      ORDER BY scan_day
    """
    rows = con.execute(q, params).fetchall()
    return [_row_dict(r) for r in rows]


def compare_snapshots(con: DbConnection, snapshot_id_a: int, snapshot_id_b: int) -> dict:
    init_security_db(con)
    fa = findings_for_snapshot(con, snapshot_id_a)
    fb = findings_for_snapshot(con, snapshot_id_b)

    def _key(f: dict) -> str:
        return f"{f.get('category')}:{f.get('title')}"

    set_a = {_key(f) for f in fa}
    set_b = {_key(f) for f in fb}
    new_issues = [f for f in fb if _key(f) not in set_a]
    resolved = [f for f in fa if _key(f) not in set_b]
    return {
        "new_issues": new_issues,
        "resolved": resolved,
        "unchanged_count": len(set_a & set_b),
    }


def upsert_tls_certificates(con: DbConnection, records) -> int:
    from .tls_certs import TlsCertRecord

    init_security_db(con)
    n = 0
    for rec in records:
        if not isinstance(rec, TlsCertRecord):
            continue
        sans = json.dumps(list(rec.sans), ensure_ascii=False) if rec.sans else None
        if con.backend == "postgresql":
            con.execute(
                """
                INSERT INTO tls_certificates(
                  server_name, domain, port, issuer, subject, sans,
                  not_before_utc, not_after_utc, days_remaining, status, error, source, checked_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (domain, port) DO UPDATE SET
                  server_name = EXCLUDED.server_name,
                  issuer = EXCLUDED.issuer,
                  subject = EXCLUDED.subject,
                  sans = EXCLUDED.sans,
                  not_before_utc = EXCLUDED.not_before_utc,
                  not_after_utc = EXCLUDED.not_after_utc,
                  days_remaining = EXCLUDED.days_remaining,
                  status = EXCLUDED.status,
                  error = EXCLUDED.error,
                  source = EXCLUDED.source,
                  checked_at_utc = EXCLUDED.checked_at_utc
                """,
                (
                    rec.server_name,
                    rec.domain,
                    rec.port,
                    rec.issuer,
                    rec.subject,
                    sans,
                    rec.not_before_utc,
                    rec.not_after_utc,
                    rec.days_remaining,
                    rec.status,
                    rec.error,
                    rec.source,
                    rec.checked_at_utc,
                ),
            )
        else:
            con.execute(
                """
                INSERT INTO tls_certificates(
                  server_name, domain, port, issuer, subject, sans,
                  not_before_utc, not_after_utc, days_remaining, status, error, source, checked_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(domain, port) DO UPDATE SET
                  server_name = excluded.server_name,
                  issuer = excluded.issuer,
                  subject = excluded.subject,
                  sans = excluded.sans,
                  not_before_utc = excluded.not_before_utc,
                  not_after_utc = excluded.not_after_utc,
                  days_remaining = excluded.days_remaining,
                  status = excluded.status,
                  error = excluded.error,
                  source = excluded.source,
                  checked_at_utc = excluded.checked_at_utc
                """,
                (
                    rec.server_name,
                    rec.domain,
                    rec.port,
                    rec.issuer,
                    rec.subject,
                    sans,
                    rec.not_before_utc,
                    rec.not_after_utc,
                    rec.days_remaining,
                    rec.status,
                    rec.error,
                    rec.source,
                    rec.checked_at_utc,
                ),
            )
        n += 1
    con.commit()
    return n


def latest_tls_certificates(con: DbConnection, server_names: list[str] | None = None) -> list[dict]:
    init_security_db(con)
    params: list = []
    filter_sql = ""
    if server_names:
        ph = ",".join("?" * len(server_names))
        filter_sql = f"WHERE server_name IN ({ph})"
        params = list(server_names)
    rows = con.execute(
        f"""
        SELECT * FROM tls_certificates
        {filter_sql}
        ORDER BY
          CASE status
            WHEN 'expired' THEN 0
            WHEN 'critical' THEN 1
            WHEN 'error' THEN 2
            WHEN 'warn' THEN 3
            ELSE 4
          END,
          days_remaining ASC NULLS LAST,
          domain ASC
        """,
        params,
    ).fetchall()
    return [_row_dict(r) for r in rows]


def scan_history_summary(con: DbConnection, server_names: list[str] | None = None) -> dict:
    init_security_db(con)
    params: list = []
    filter_sql = ""
    if server_names:
        ph = ",".join("?" * len(server_names))
        filter_sql = f"WHERE server_name IN ({ph})"
        params = list(server_names)
    total_row = con.execute(
        f"SELECT COUNT(*) AS total FROM security_snapshots {filter_sql}",
        params,
    ).fetchone()
    total_row = normalize_row(total_row)
    row = con.execute(
        f"""
        SELECT MIN(scanned_at_utc) AS first_scan, MAX(scanned_at_utc) AS last_scan
        FROM security_snapshots {filter_sql}
        """,
        params,
    ).fetchone()
    row = normalize_row(row)
    return {
        "total_scans": int(total_row.get("total") or 0),
        "first_scan_utc": row.get("first_scan"),
        "last_scan_utc": row.get("last_scan"),
    }
