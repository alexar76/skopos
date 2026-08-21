from __future__ import annotations

from skopos.config import AppConfig, SSHConfig, ServerConfig, NginxConfig
from skopos.db import connect, init_db, insert_requests, ParsedRequest, now_utc_iso
from skopos.db_dialect import adapt_sql, backend_for_target, resolve_db_target


def _cfg(db_path: str = "./test.sqlite3", database_url: str | None = None) -> AppConfig:
    return AppConfig(
        db_path=db_path,
        database_url=database_url,
        servers=[
            ServerConfig(
                name="web-1",
                source="ssh_nginx_access_log",
                ssh=SSHConfig(host="10.0.0.1", port=22, user="stats"),
                nginx=NginxConfig(),
            )
        ],
    )


def test_resolve_db_target_uses_cfg_database_url():
    cfg = _cfg(database_url="postgresql://yaml/db")
    assert resolve_db_target(cfg) == "postgresql://yaml/db"


def test_resolve_db_target_sqlite_fallback():
    cfg = _cfg(db_path="./local.sqlite3")
    assert resolve_db_target(cfg) == "./local.sqlite3"


def test_sqlite_connect_init_insert(tmp_path):
    db = str(tmp_path / "t.sqlite3")
    con = connect(db)
    assert con.backend == "sqlite"
    init_db(con)
    n = insert_requests(
        con,
        "web-1",
        [
            ParsedRequest(
                log_source="file:/var/log/nginx/access.log",
                ecosystem_segment=None,
                server_ip="10.0.0.1",
                ts_utc=now_utc_iso(),
                remote_addr="203.0.113.1",
                host="example.com",
                country_code=None,
                country_name=None,
                ua_browser=None,
                ua_os=None,
                ua_device=None,
                ua_is_bot=None,
                referer_domain=None,
                method="GET",
                path="/",
                status=200,
                bytes_sent=123,
                referer=None,
                user_agent="curl",
                request_raw="GET / HTTP/1.1",
                line_raw='203.0.113.1 - - [01/Jan/2026:00:00:00 +0000] "GET / HTTP/1.1" 200 123',
            )
        ],
    )
    assert n == 1
    row = con.execute("SELECT COUNT(*) AS c FROM http_requests").fetchone()
    assert int(row["c"] if isinstance(row, dict) else row[0]) == 1
    con.close()


def test_backend_detection():
    assert backend_for_target("./x.sqlite3") == "sqlite"
    assert backend_for_target("postgresql://localhost/db") == "postgresql"


def test_adapt_sql_escapes_literal_percent_in_like():
    sql = "SELECT 1 FROM http_requests WHERE log_source LIKE 'file:%' AND id = ?"
    assert adapt_sql(sql, "postgresql") == (
        "SELECT 1 FROM http_requests WHERE log_source LIKE 'file:%%' AND id = %s"
    )


def test_connect_memory_does_not_create_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    con = connect(":memory:")
    init_db(con)
    con.close()
    assert not (tmp_path / ":memory:").exists()
    assert not (tmp_path / ":memory:-wal").exists()
    assert not (tmp_path / ":memory:-shm").exists()
