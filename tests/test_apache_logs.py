from __future__ import annotations

import tempfile
from pathlib import Path

import yaml

from skopos.apache_logs import host_from_log_path, resolve_log_paths
from skopos.config import ApacheConfig, NginxConfig, SSHConfig, ServerConfig, load_config
from skopos.config_io import save_config
from skopos.config import AppConfig
from skopos.log_sources import LogSource, host_hint, parse_line, resolve_log_sources


def _server(*, apache_enabled: bool = False, apache_paths: list[str] | None = None) -> ServerConfig:
    apache = None
    if apache_enabled:
        apache = ApacheConfig(
            enabled=True,
            access_log_path="/opt/metis/deploy/apache-test/logs/access_log",
            access_log_paths=apache_paths,
            auto_discover_logs=False,
        )
    return ServerConfig(
        name="metis",
        source="ssh_http_access_log" if apache_enabled else "ssh_nginx_access_log",
        ssh=SSHConfig(host="10.0.0.1", port=22, user="stats"),
        nginx=NginxConfig(access_log_path="/var/log/nginx/access.log", auto_discover_logs=False),
        apache=apache,
    )


def test_host_from_log_path_apache():
    assert host_from_log_path("/var/log/apache2/example.com_access.log") == "example.com"
    assert host_from_log_path("/opt/metis/deploy/apache-test/logs/access_log") is None
    # Dot / dash / RHEL underscore vhost naming conventions all resolve.
    assert host_from_log_path("/var/log/apache2/example.com.access.log") == "example.com"
    assert host_from_log_path("/var/log/apache2/example.com-access.log") == "example.com"
    assert host_from_log_path("/var/log/httpd/example.com-access_log") == "example.com"
    # Generic names never look like a host.
    assert host_from_log_path("/var/log/apache2/other_vhosts_access.log") is None
    assert host_from_log_path("/var/log/apache2/ssl.access.log") is None


def test_resolve_log_paths_keeps_customlog_without_access_in_name(monkeypatch):
    """Discovered CustomLog paths are authoritative — never dropped by filename."""
    monkeypatch.setattr(
        "skopos.apache_logs.discover_access_logs",
        lambda _s: ["/var/log/apache2/mysite.log", "/var/log/apache2/old.log.gz"],
    )
    srv = _server(apache_enabled=True)
    srv = ServerConfig(
        name=srv.name,
        source=srv.source,
        ssh=srv.ssh,
        nginx=srv.nginx,
        apache=ApacheConfig(enabled=True, auto_discover_logs=True),
    )
    paths = resolve_log_paths(srv)
    assert "/var/log/apache2/mysite.log" in paths
    assert all(not p.endswith(".gz") for p in paths)


def test_resolve_log_paths_explicit_apache():
    paths = resolve_log_paths(
        _server(
            apache_enabled=True,
            apache_paths=["/opt/metis/deploy/apache-test/logs/access_log"],
        )
    )
    assert paths == ["/opt/metis/deploy/apache-test/logs/access_log"]


def test_parse_line_apache_combined():
    line = (
        '203.0.113.5 - - [13/Jul/2026:10:00:00 +0000] '
        '"GET /v1/models HTTP/1.1" 200 1234 "-" "curl/8.0"'
    )
    src = LogSource(id="file:/var/log/apache2/access.log", kind="file", parser="apache")
    pr = parse_line(src, line)
    assert pr is not None
    assert pr.remote_addr == "203.0.113.5"
    assert pr.method == "GET"
    assert pr.path == "/v1/models"
    assert pr.status == 200


def test_resolve_log_sources_includes_apache(monkeypatch):
    monkeypatch.setattr(
        "skopos.nginx_logs.resolve_log_paths",
        lambda _s: ["/var/log/nginx/access.log"],
    )
    monkeypatch.setattr(
        "skopos.apache_logs.resolve_log_paths",
        lambda _s: ["/opt/metis/deploy/apache-test/logs/access_log"],
    )
    sources = resolve_log_sources(_server(apache_enabled=True))
    parsers = {s.parser for s in sources}
    assert parsers == {"nginx", "apache"}


def test_resolve_log_sources_merges_apache_docker(monkeypatch):
    monkeypatch.setattr("skopos.nginx_logs.resolve_log_paths", lambda _s: [])
    monkeypatch.setattr("skopos.apache_logs.resolve_log_paths", lambda _s: [])
    monkeypatch.setattr(
        "skopos.log_sources.discover_docker_http_containers",
        lambda _s: [],
    )
    srv = ServerConfig(
        name="metis",
        source="ssh_http_access_log",
        ssh=SSHConfig(host="10.0.0.1", port=22, user="stats"),
        nginx=NginxConfig(auto_discover_logs=False, auto_discover_docker_logs=False),
        apache=ApacheConfig(
            enabled=True,
            auto_discover_logs=False,
            docker_log_containers=["apache-app"],
        ),
    )
    sources = resolve_log_sources(srv)
    docker_ids = {s.id for s in sources if s.kind == "docker"}
    assert "docker:apache-app" in docker_ids


def test_apache_docker_config_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "servers.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "db_path": "./skopos.sqlite3",
                    "servers": [
                        {
                            "name": "metis",
                            "source": "ssh_http_access_log",
                            "ssh": {"host": "10.0.0.1", "port": 22, "user": "stats"},
                            "nginx": {"access_log_path": "/var/log/nginx/access.log"},
                            "apache": {
                                "enabled": True,
                                "auto_discover_docker_logs": True,
                                "docker_log_containers": ["httpd-app"],
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        cfg = load_config(str(path))
        ap = cfg.servers[0].apache
        assert ap is not None
        assert ap.auto_discover_docker_logs is True
        assert ap.docker_log_containers == ["httpd-app"]

        save_config(str(path), AppConfig(db_path=cfg.db_path, servers=cfg.servers))
        reloaded = load_config(str(path))
        assert reloaded.servers[0].apache.docker_log_containers == ["httpd-app"]


def test_host_hint_apache():
    src = LogSource(
        id="file:/var/log/apache2/demo_access.log",
        kind="file",
        parser="apache",
    )
    assert host_hint(src) == "demo"


def test_load_and_save_apache_config():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "servers.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "db_path": "./skopos.sqlite3",
                    "servers": [
                        {
                            "name": "metis",
                            "source": "ssh_http_access_log",
                            "ssh": {"host": "10.0.0.1", "port": 22, "user": "stats"},
                            "nginx": {"access_log_path": "/var/log/nginx/access.log"},
                            "apache": {
                                "enabled": True,
                                "access_log_path": "/opt/metis/deploy/apache-test/logs/access_log",
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        cfg = load_config(str(path))
        assert cfg.servers[0].apache is not None
        assert cfg.servers[0].apache.enabled is True

        save_config(str(path), AppConfig(db_path=cfg.db_path, servers=cfg.servers))
        reloaded = load_config(str(path))
        assert reloaded.servers[0].apache is not None
        assert reloaded.servers[0].apache.access_log_path.endswith("access_log")
