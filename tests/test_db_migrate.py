from __future__ import annotations

from skopos.db import connect, init_db, insert_requests, ParsedRequest, now_utc_iso
from skopos.db_migrate import migrate_database, source_row_total, check_database_connection
from skopos.db_settings import build_postgres_url, db_settings_from_config, parse_postgres_url
from skopos.config import AppConfig, SSHConfig, ServerConfig, NginxConfig


def _sample_request() -> ParsedRequest:
    return ParsedRequest(
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
        bytes_sent=100,
        referer=None,
        user_agent="curl",
        request_raw="GET /",
        line_raw='203.0.113.1 - - [01/Jan/2026:00:00:00 +0000] "GET / HTTP/1.1" 200 100',
    )


def test_build_and_parse_postgres_url():
    url = build_postgres_url("localhost", 5432, "skopos", "p@ss", "skopos")
    parsed = parse_postgres_url(url)
    assert parsed is not None
    assert parsed["pg_host"] == "localhost"
    assert parsed["pg_user"] == "skopos"
    assert parsed["pg_password"] == "p@ss"


def test_db_settings_from_config_sqlite():
    cfg = AppConfig(
        db_path="./local.sqlite3",
        servers=[
            ServerConfig(
                name="x",
                source="ssh_nginx_access_log",
                ssh=SSHConfig(host="h", port=22, user="u"),
                nginx=NginxConfig(),
            )
        ],
    )
    s = db_settings_from_config(cfg)
    assert s.mode == "sqlite"
    assert s.db_path == "./local.sqlite3"


def test_migrate_sqlite_to_sqlite_copy(tmp_path):
    src = str(tmp_path / "src.sqlite3")
    dst = str(tmp_path / "dst.sqlite3")
    con = connect(src)
    init_db(con)
    insert_requests(con, "web-1", [_sample_request()])
    con.close()
    assert source_row_total(src) > 0

    result = migrate_database(src, dst, replace_dest=True)
    assert result.ok is True
    assert result.rows_copied.get("http_requests", 0) == 1
    assert source_row_total(dst) > 0


def test_check_database_connection_sqlite(tmp_path):
    db = str(tmp_path / "t.sqlite3")
    ok, msg = check_database_connection(db)
    assert ok is True
    assert "SQLite" in msg
