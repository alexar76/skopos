from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

_env_loaded = False
_env_mtime: float = 0.0

_PROXY_VARS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "NO_PROXY",
    "no_proxy",
)


def _strip_proxy_env() -> None:
    for name in _PROXY_VARS:
        os.environ.pop(name, None)


def _alias_legacy_env(old_prefix: str, new_prefix: str) -> None:
    """Map STATS_* → SKOPOS_* when the new name is unset (migration from standalone Stats)."""
    for key, val in list(os.environ.items()):
        if not key.startswith(old_prefix):
            continue
        alias = new_prefix + key[len(old_prefix) :]
        if alias not in os.environ:
            os.environ[alias] = val


def load_app_env() -> None:
    """Load project .env (reloads when .env changes). Never use IDE proxy."""
    global _env_loaded, _env_mtime
    _strip_proxy_env()
    root = Path(__file__).resolve().parents[1]
    env_path = root / ".env"
    mtime = env_path.stat().st_mtime if env_path.exists() else 0.0
    if _env_loaded and mtime == _env_mtime:
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        _env_loaded = True
        _env_mtime = mtime
        return
    load_dotenv(env_path, override=True)
    _alias_legacy_env("STATS_", "SKOPOS_")
    _strip_proxy_env()
    _env_loaded = True
    _env_mtime = mtime


SourceType = Literal["ssh_nginx_access_log", "ssh_http_access_log"]


@dataclass(frozen=True)
class SSHConfig:
    host: str
    port: int
    user: str
    key_path: str | None = None
    key_passphrase_env: str | None = None


@dataclass(frozen=True)
class ApacheConfig:
    enabled: bool = False
    access_log_path: str = "/var/log/apache2/access.log"
    access_log_paths: list[str] | None = None
    auto_discover_logs: bool = True


@dataclass(frozen=True)
class NginxConfig:
    access_log_path: str = "/var/log/nginx/access.log"
    access_log_paths: list[str] | None = None
    auto_discover_logs: bool = True
    auto_discover_docker_logs: bool = False
    docker_log_containers: list[str] | None = None


@dataclass(frozen=True)
class ServerConfig:
    name: str
    source: SourceType
    ssh: SSHConfig
    nginx: NginxConfig
    apache: ApacheConfig | None = None


DEFAULT_SECURITY_SCAN_INTERVAL_MINUTES = 60
DEFAULT_TELEGRAM_BOT_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
DEFAULT_TELEGRAM_NOTIFY_INTERVAL_MINUTES = 60


@dataclass(frozen=True)
class AppConfig:
    db_path: str
    database_url: str | None = None
    geoip_mmdb_path: str | None = None
    poll_interval_seconds: int = 5
    batch_lines_per_server: int = 4000
    security_auto_scan: bool = True
    security_scan_interval_minutes: int = DEFAULT_SECURITY_SCAN_INTERVAL_MINUTES
    telegram_enabled: bool = False
    telegram_bot_token_env: str = DEFAULT_TELEGRAM_BOT_TOKEN_ENV
    telegram_chat_id: str | None = None
    telegram_notify_interval_minutes: int = DEFAULT_TELEGRAM_NOTIFY_INTERVAL_MINUTES
    servers: list[ServerConfig] = None  # type: ignore[assignment]


def _require(d: dict[str, Any], key: str) -> Any:
    if key not in d:
        raise ValueError(f"Missing required config key: {key}")
    return d[key]


def load_config(path: str) -> AppConfig:
    p = Path(path).expanduser().resolve()
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Config must be a YAML mapping at the top-level.")

    servers_raw = _require(raw, "servers")
    if not isinstance(servers_raw, list) or not servers_raw:
        raise ValueError("Config 'servers' must be a non-empty list.")

    servers: list[ServerConfig] = []
    for item in servers_raw:
        if not isinstance(item, dict):
            raise ValueError("Each server entry must be a mapping.")
        name = str(_require(item, "name"))
        source = _require(item, "source")
        if source not in ("ssh_nginx_access_log", "ssh_http_access_log"):
            raise ValueError(
                f"Unsupported source '{source}' for server '{name}'. "
                "Use ssh_nginx_access_log or ssh_http_access_log."
            )

        ssh_raw = _require(item, "ssh")
        if not isinstance(ssh_raw, dict):
            raise ValueError(f"server '{name}': ssh must be a mapping")
        ssh = SSHConfig(
            host=str(_require(ssh_raw, "host")),
            port=int(ssh_raw.get("port", 22)),
            user=str(_require(ssh_raw, "user")),
            key_path=(str(ssh_raw["key_path"]) if "key_path" in ssh_raw else None),
            key_passphrase_env=(
                str(ssh_raw["key_passphrase_env"]) if "key_passphrase_env" in ssh_raw else None
            ),
        )

        nginx_raw = item.get("nginx") or {}
        if not isinstance(nginx_raw, dict):
            raise ValueError(f"server '{name}': nginx must be a mapping")
        extra_paths = nginx_raw.get("access_log_paths")
        if extra_paths is not None and not isinstance(extra_paths, list):
            raise ValueError(f"server '{name}': nginx.access_log_paths must be a list")
        docker_containers = nginx_raw.get("docker_log_containers")
        if docker_containers is not None and not isinstance(docker_containers, list):
            raise ValueError(f"server '{name}': nginx.docker_log_containers must be a list")
        nginx = NginxConfig(
            access_log_path=str(nginx_raw.get("access_log_path", "/var/log/nginx/access.log")),
            access_log_paths=[str(x) for x in extra_paths] if extra_paths else None,
            auto_discover_logs=bool(nginx_raw.get("auto_discover_logs", True)),
            auto_discover_docker_logs=bool(nginx_raw.get("auto_discover_docker_logs", False)),
            docker_log_containers=[str(x) for x in docker_containers] if docker_containers else None,
        )

        apache_raw = item.get("apache")
        apache: ApacheConfig | None = None
        if apache_raw is not None:
            if not isinstance(apache_raw, dict):
                raise ValueError(f"server '{name}': apache must be a mapping")
            ap_extra = apache_raw.get("access_log_paths")
            if ap_extra is not None and not isinstance(ap_extra, list):
                raise ValueError(f"server '{name}': apache.access_log_paths must be a list")
            apache = ApacheConfig(
                enabled=bool(apache_raw.get("enabled", True)),
                access_log_path=str(apache_raw.get("access_log_path", "/var/log/apache2/access.log")),
                access_log_paths=[str(x) for x in ap_extra] if ap_extra else None,
                auto_discover_logs=bool(apache_raw.get("auto_discover_logs", True)),
            )

        servers.append(ServerConfig(name=name, source=source, ssh=ssh, nginx=nginx, apache=apache))

    scan_interval = int(raw.get("security_scan_interval_minutes", DEFAULT_SECURITY_SCAN_INTERVAL_MINUTES))
    scan_interval = max(5, min(1440, scan_interval))

    notify_interval = int(
        raw.get("telegram_notify_interval_minutes", DEFAULT_TELEGRAM_NOTIFY_INTERVAL_MINUTES)
    )
    notify_interval = max(5, min(10080, notify_interval))

    chat_raw = raw.get("telegram_chat_id")
    chat_id = str(chat_raw).strip() if chat_raw not in (None, "") else None

    db_url_raw = raw.get("database_url")
    if db_url_raw in (None, ""):
        db_url_raw = os.environ.get("SKOPOS_DATABASE_URL")
    database_url = str(db_url_raw).strip() if db_url_raw not in (None, "") else None

    return AppConfig(
        db_path=str(raw.get("db_path", "./skopos.sqlite3")),
        database_url=database_url,
        geoip_mmdb_path=(str(raw["geoip_mmdb_path"]) if raw.get("geoip_mmdb_path") else None),
        poll_interval_seconds=int(raw.get("poll_interval_seconds", 5)),
        batch_lines_per_server=int(raw.get("batch_lines_per_server", 4000)),
        security_auto_scan=bool(raw.get("security_auto_scan", True)),
        security_scan_interval_minutes=scan_interval,
        telegram_enabled=bool(raw.get("telegram_enabled", False)),
        telegram_bot_token_env=str(
            raw.get("telegram_bot_token_env", DEFAULT_TELEGRAM_BOT_TOKEN_ENV)
        ),
        telegram_chat_id=chat_id,
        telegram_notify_interval_minutes=notify_interval,
        servers=servers,
    )
