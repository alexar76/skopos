from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .db_connection import DbConnection, connect, connect_for_config, is_integrity_error
from .db_dialect import adapt_sql, backend_for_target

SQLITE_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS collector_status (
  server_name TEXT PRIMARY KEY,
  last_ok_at_utc TEXT,
  last_error_at_utc TEXT,
  last_error TEXT,
  last_fetched_lines INTEGER,
  last_inserted_rows INTEGER,
  updated_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingested_lines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  server_name TEXT NOT NULL,
  line_sha1 TEXT NOT NULL,
  ingested_at_utc TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ingested_lines_unique
  ON ingested_lines(server_name, line_sha1);

CREATE TABLE IF NOT EXISTS http_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  server_name TEXT NOT NULL,
  server_ip TEXT,
  log_source TEXT,
  ecosystem_segment TEXT,
  ts_utc TEXT,
  remote_addr TEXT,
  host TEXT,
  country_code TEXT,
  country_name TEXT,
  ua_browser TEXT,
  ua_os TEXT,
  ua_device TEXT,
  ua_is_bot INTEGER,
  referer_domain TEXT,
  method TEXT,
  path TEXT,
  status INTEGER,
  bytes_sent INTEGER,
  referer TEXT,
  user_agent TEXT,
  request_raw TEXT,
  line_raw TEXT NOT NULL,
  ingested_at_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_http_requests_ts ON http_requests(ts_utc);
CREATE INDEX IF NOT EXISTS idx_http_requests_server_ts ON http_requests(server_name, ts_utc);
CREATE INDEX IF NOT EXISTS idx_http_requests_host_ts ON http_requests(host, ts_utc);
CREATE INDEX IF NOT EXISTS idx_http_requests_path_ts ON http_requests(path, ts_utc);
CREATE INDEX IF NOT EXISTS idx_http_requests_status_ts ON http_requests(status, ts_utc);
CREATE INDEX IF NOT EXISTS idx_http_requests_file_server_ts
  ON http_requests(server_name, ts_utc)
  WHERE log_source LIKE 'file:%' AND ts_utc IS NOT NULL;
"""

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS collector_status (
  server_name TEXT PRIMARY KEY,
  last_ok_at_utc TEXT,
  last_error_at_utc TEXT,
  last_error TEXT,
  last_fetched_lines INTEGER,
  last_inserted_rows INTEGER,
  last_log_paths TEXT,
  updated_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingested_lines (
  id BIGSERIAL PRIMARY KEY,
  server_name TEXT NOT NULL,
  line_sha1 TEXT NOT NULL,
  ingested_at_utc TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ingested_lines_unique
  ON ingested_lines(server_name, line_sha1);

CREATE TABLE IF NOT EXISTS http_requests (
  id BIGSERIAL PRIMARY KEY,
  server_name TEXT NOT NULL,
  server_ip TEXT,
  log_source TEXT,
  ecosystem_segment TEXT,
  ts_utc TEXT,
  remote_addr TEXT,
  host TEXT,
  country_code TEXT,
  country_name TEXT,
  ua_browser TEXT,
  ua_os TEXT,
  ua_device TEXT,
  ua_is_bot INTEGER,
  referer_domain TEXT,
  method TEXT,
  path TEXT,
  status INTEGER,
  bytes_sent INTEGER,
  referer TEXT,
  user_agent TEXT,
  request_raw TEXT,
  line_raw TEXT NOT NULL,
  ingested_at_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_http_requests_ts ON http_requests(ts_utc);
CREATE INDEX IF NOT EXISTS idx_http_requests_server_ts ON http_requests(server_name, ts_utc);
CREATE INDEX IF NOT EXISTS idx_http_requests_host_ts ON http_requests(host, ts_utc);
CREATE INDEX IF NOT EXISTS idx_http_requests_path_ts ON http_requests(path, ts_utc);
CREATE INDEX IF NOT EXISTS idx_http_requests_status_ts ON http_requests(status, ts_utc);
CREATE INDEX IF NOT EXISTS idx_http_requests_ecosystem ON http_requests(ecosystem_segment, ts_utc);
CREATE INDEX IF NOT EXISTS idx_http_requests_file_server_ts
  ON http_requests(server_name, ts_utc)
  WHERE log_source LIKE 'file:%' AND ts_utc IS NOT NULL;
"""

_POST_MIGRATION_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_http_requests_ecosystem ON http_requests(ecosystem_segment, ts_utc);
CREATE INDEX IF NOT EXISTS idx_http_requests_file_server_ts
  ON http_requests(server_name, ts_utc)
  WHERE log_source LIKE 'file:%' AND ts_utc IS NOT NULL;
"""


@dataclass(frozen=True)
class ParsedRequest:
    log_source: str | None
    ecosystem_segment: str | None
    server_ip: str | None
    ts_utc: str | None
    remote_addr: str | None
    host: str | None
    country_code: str | None
    country_name: str | None
    ua_browser: str | None
    ua_os: str | None
    ua_device: str | None
    ua_is_bot: int | None
    referer_domain: str | None
    method: str | None
    path: str | None
    status: int | None
    bytes_sent: int | None
    referer: str | None
    user_agent: str | None
    request_raw: str | None
    line_raw: str


def _sqlite_columns(con: DbConnection, table: str) -> set[str]:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _pg_columns(con: DbConnection, table: str) -> set[str]:
    rows = con.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = ?
        """,
        (table,),
    ).fetchall()
    return {row["column_name"] for row in rows}


def _table_columns(con: DbConnection, table: str) -> set[str]:
    if con.backend == "postgresql":
        return _pg_columns(con, table)
    return _sqlite_columns(con, table)


def init_db(con: DbConnection) -> None:
    if con.backend == "postgresql":
        con.executescript(POSTGRES_SCHEMA)
    else:
        con.executescript(SQLITE_SCHEMA)

    try:
        cols = _table_columns(con, "collector_status")
        if "last_fetched_lines" not in cols:
            con.execute("ALTER TABLE collector_status ADD COLUMN last_fetched_lines INTEGER")
        if "last_inserted_rows" not in cols:
            con.execute("ALTER TABLE collector_status ADD COLUMN last_inserted_rows INTEGER")
        if "updated_at_utc" not in cols:
            con.execute("ALTER TABLE collector_status ADD COLUMN updated_at_utc TEXT")
        if "last_log_paths" not in cols:
            con.execute("ALTER TABLE collector_status ADD COLUMN last_log_paths TEXT")
    except Exception:
        pass

    try:
        cols = _table_columns(con, "http_requests")
        for col, typ in (
            ("country_code", "TEXT"),
            ("country_name", "TEXT"),
            ("ua_browser", "TEXT"),
            ("ua_os", "TEXT"),
            ("ua_device", "TEXT"),
            ("ua_is_bot", "INTEGER"),
            ("referer_domain", "TEXT"),
            ("log_source", "TEXT"),
            ("ecosystem_segment", "TEXT"),
            ("server_ip", "TEXT"),
        ):
            if col not in cols:
                con.execute(f"ALTER TABLE http_requests ADD COLUMN {col} {typ}")
    except Exception:
        pass

    if con.backend == "sqlite":
        try:
            con.executescript(_POST_MIGRATION_INDEXES)
        except Exception:
            pass
    else:
        try:
            for stmt in (
                "CREATE INDEX IF NOT EXISTS idx_http_requests_ecosystem ON http_requests(ecosystem_segment, ts_utc)",
                """CREATE INDEX IF NOT EXISTS idx_http_requests_file_server_ts
                     ON http_requests(server_name, ts_utc)
                     WHERE log_source LIKE 'file:%' AND ts_utc IS NOT NULL""",
            ):
                con.execute(stmt)
        except Exception:
            pass
    con.commit()


def sha1_hex(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", errors="replace")).hexdigest()


def now_utc_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def insert_requests(
    con: DbConnection,
    server_name: str,
    parsed: Iterable[ParsedRequest],
) -> int:
    inserted = 0
    for r in parsed:
        dedup_key = f"{r.log_source or ''}\n{r.line_raw}"
        h = sha1_hex(dedup_key)
        try:
            cur = con.execute(
                "INSERT INTO ingested_lines(server_name, line_sha1, ingested_at_utc) "
                "VALUES(?,?,?) ON CONFLICT DO NOTHING",
                (server_name, h, now_utc_iso()),
            )
        except Exception as exc:
            if is_integrity_error(exc):
                if con.backend == "postgresql":
                    con.connection.rollback()
                continue
            raise

        skipped = False
        if con.backend == "postgresql":
            skipped = getattr(cur._cursor, "rowcount", 1) == 0
        elif not (cur.lastrowid or 0):
            skipped = True
        if skipped:
            continue

        con.execute(
            """
            INSERT INTO http_requests(
              server_name, server_ip, log_source, ecosystem_segment,
              ts_utc, remote_addr, host, country_code, country_name,
              ua_browser, ua_os, ua_device, ua_is_bot, referer_domain,
              method, path, status, bytes_sent,
              referer, user_agent, request_raw, line_raw, ingested_at_utc
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                server_name,
                r.server_ip,
                r.log_source,
                r.ecosystem_segment,
                r.ts_utc,
                r.remote_addr,
                r.host,
                r.country_code,
                r.country_name,
                r.ua_browser,
                r.ua_os,
                r.ua_device,
                r.ua_is_bot,
                r.referer_domain,
                r.method,
                r.path,
                r.status,
                r.bytes_sent,
                r.referer,
                r.user_agent,
                r.request_raw,
                r.line_raw,
                now_utc_iso(),
            ),
        )
        inserted += 1

    con.commit()
    return inserted


def upsert_collector_status(
    con: DbConnection,
    *,
    server_name: str,
    ok: bool,
    fetched_lines: int | None = None,
    inserted_rows: int | None = None,
    error: str | None = None,
    log_paths: str | None = None,
) -> None:
    now = now_utc_iso()
    if ok:
        con.execute(
            """
            INSERT INTO collector_status(
              server_name, last_ok_at_utc, last_error_at_utc, last_error,
              last_fetched_lines, last_inserted_rows, last_log_paths, updated_at_utc
            ) VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(server_name) DO UPDATE SET
              last_ok_at_utc=excluded.last_ok_at_utc,
              last_error_at_utc=NULL,
              last_error=NULL,
              last_fetched_lines=excluded.last_fetched_lines,
              last_inserted_rows=excluded.last_inserted_rows,
              last_log_paths=excluded.last_log_paths,
              updated_at_utc=excluded.updated_at_utc
            """,
            (server_name, now, None, None, fetched_lines, inserted_rows, log_paths, now),
        )
    else:
        con.execute(
            """
            INSERT INTO collector_status(
              server_name, last_ok_at_utc, last_error_at_utc, last_error,
              last_fetched_lines, last_inserted_rows, updated_at_utc
            ) VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(server_name) DO UPDATE SET
              last_error_at_utc=excluded.last_error_at_utc,
              last_error=excluded.last_error,
              updated_at_utc=excluded.updated_at_utc
            """,
            (server_name, None, now, (error or "")[:4000], fetched_lines, inserted_rows, now),
        )
    con.commit()


def read_sql_query(sql: str, con: DbConnection, params: list | tuple = ()) -> "pd.DataFrame":
    import pandas as pd

    if con.backend == "postgresql":
        # psycopg connection uses dict_row; pandas.read_sql_query would iterate
        # each dict row as its keys and fill the frame with column-name strings.
        cur = con.execute(sql, tuple(params))
        rows = cur.fetchall()
        description = getattr(cur._cursor, "description", None) or []
        columns = [d[0] for d in description]
        if not rows:
            return pd.DataFrame(columns=columns)
        return pd.DataFrame.from_records(rows, columns=columns or None)
    return pd.read_sql_query(adapt_sql(sql, con.backend), con.connection, params=params)


__all__ = [
    "ParsedRequest",
    "connect",
    "connect_for_config",
    "init_db",
    "insert_requests",
    "upsert_collector_status",
    "sha1_hex",
    "now_utc_iso",
    "read_sql_query",
    "DbConnection",
]
