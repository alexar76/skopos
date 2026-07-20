from __future__ import annotations

from dataclasses import dataclass

from .apache import parse_access_line as parse_apache_line
from .config import ServerConfig
from .nginx import parse_access_line
from .nginx_logs import host_from_log_path as nginx_host_from_log_path
from .shell_safe import quote_shell, validate_docker_name, validate_log_path
from .ssh import SSHConnInfo, run_command
from .uvicorn_log import parse_uvicorn_line


@dataclass(frozen=True)
class LogSource:
    """A remote HTTP access log we can tail over SSH."""

    id: str
    kind: str  # "file" | "docker"
    parser: str  # "nginx" | "apache" | "uvicorn" | "auto"


_DISCOVER_DOCKER_SCRIPT = r"""
set -euo pipefail
docker ps --format '{{.Names}}|{{.Ports}}' 2>/dev/null | while IFS='|' read -r name ports; do
  [ -n "$name" ] || continue
  [ -n "$ports" ] || continue
  case "$ports" in
    *"0.0.0.0:"*|*"[::]:"*) ;;
    *) continue ;;
  esac
  # Skip obvious non-HTTP services (DB, cache, raw TCP).
  case "$ports" in
    *":5432->"*|*":6379->"*|*":16380->"*|*":15433->"*|*":3306->"*|*":27017->"*) continue ;;
  esac
  # Require a typical HTTP(S) host port binding.
  if echo "$ports" | grep -qE '0\.0\.0\.0:(80|443|3000|8000|8080|8081|8787|8788|9080|9081|9082|9090|9195|18001)->|\[::\]:(80|443|3000|8000|8080|8081|8787|8788|9080|9081|9082|9090|9195|18001)->'; then
    echo "docker:$name"
  fi
done | sort -u
"""


def _ssh_info(server: ServerConfig) -> SSHConnInfo:
    return SSHConnInfo(
        host=server.ssh.host,
        port=server.ssh.port,
        user=server.ssh.user,
        key_path=server.ssh.key_path,
        key_passphrase_env=server.ssh.key_passphrase_env,
    )


def discover_docker_http_containers(server: ServerConfig) -> list[str]:
    out = run_command(_ssh_info(server), _DISCOVER_DOCKER_SCRIPT, timeout_s=30)
    names: list[str] = []
    for ln in out.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("# STDERR:"):
            continue
        if ln.startswith("docker:"):
            ln = ln[len("docker:") :]
        if ln and ln not in names:
            names.append(ln)
    return names


def resolve_log_sources(server: ServerConfig) -> list[LogSource]:
    """HTTP access logs: nginx files, optional Apache files, public docker containers."""
    from .apache_logs import resolve_log_paths as resolve_apache_paths
    from .nginx_logs import resolve_log_paths as resolve_nginx_paths

    sources: list[LogSource] = []
    seen: set[str] = set()

    for path in resolve_nginx_paths(server):
        sid = f"file:{path}"
        if sid not in seen:
            seen.add(sid)
            sources.append(LogSource(id=sid, kind="file", parser="nginx"))

    if getattr(server, "apache", None) and server.apache.enabled:
        for path in resolve_apache_paths(server):
            sid = f"file:{path}"
            if sid not in seen:
                seen.add(sid)
                sources.append(LogSource(id=sid, kind="file", parser="apache"))

    # Docker HTTP containers are host-level (serve traffic regardless of nginx/apache).
    # Honor explicit lists and auto-discover toggles from EITHER block for symmetry.
    apache_cfg = getattr(server, "apache", None)
    extra_docker = list(getattr(server.nginx, "docker_log_containers", None) or [])
    if apache_cfg is not None and getattr(apache_cfg, "enabled", False):
        for name in getattr(apache_cfg, "docker_log_containers", None) or []:
            if name not in extra_docker:
                extra_docker.append(name)

    auto_docker = bool(getattr(server.nginx, "auto_discover_docker_logs", True))
    if apache_cfg is not None and getattr(apache_cfg, "enabled", False):
        auto_docker = auto_docker or bool(getattr(apache_cfg, "auto_discover_docker_logs", False))

    discovered_docker: list[str] = []
    if auto_docker:
        try:
            discovered_docker = discover_docker_http_containers(server)
        except Exception:
            discovered_docker = []

    for name in extra_docker + discovered_docker:
        sid = f"docker:{name}"
        if sid not in seen:
            seen.add(sid)
            sources.append(LogSource(id=sid, kind="docker", parser="auto"))

    return sources


def fetch_lines(server: ServerConfig, source: LogSource, batch_lines: int) -> list[str]:
    n = max(100, int(batch_lines))
    try:
        if source.kind == "file":
            path = validate_log_path(source.id[len("file:") :])
            cmd = f"set -euo pipefail; tail -n {n} {quote_shell(path)} 2>/dev/null || true"
        elif source.kind == "docker":
            name = validate_docker_name(source.id[len("docker:") :])
            cmd = f"set -euo pipefail; docker logs --tail {n} {quote_shell(name)} 2>&1 || true"
        else:
            return []
    except ValueError:
        return []

    out = run_command(_ssh_info(server), cmd, timeout_s=60)
    return [ln for ln in out.splitlines() if ln and not ln.startswith("# STDERR:")]


def parse_line(source: LogSource, line: str):
    if source.parser == "nginx":
        return parse_access_line(line)
    if source.parser == "apache":
        return parse_apache_line(line)
    if source.parser == "uvicorn":
        return parse_uvicorn_line(line)

    # auto: try nginx/apache combined first, then uvicorn.
    pr = parse_access_line(line)
    if pr and pr.remote_addr and pr.method:
        return pr
    uv = parse_uvicorn_line(line)
    if uv:
        return uv
    if pr and pr.remote_addr:
        return pr
    return None


def host_hint(source: LogSource) -> str | None:
    if source.kind == "file" and source.id.startswith("file:"):
        path = source.id[len("file:") :]
        if source.parser == "apache":
            from .apache_logs import host_from_log_path as apache_host

            return apache_host(path) or nginx_host_from_log_path(path)
        return nginx_host_from_log_path(path)
    return None
