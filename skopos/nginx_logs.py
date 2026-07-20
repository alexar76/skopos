from __future__ import annotations

import re

from .config import ServerConfig
from .ssh import SSHConnInfo, run_command


def _nginx_get(server: ServerConfig, key: str, default=None):
    """Read nginx config fields safely (handles cached dataclass instances from older runs)."""
    return getattr(server.nginx, key, default)


_DISCOVER_SCRIPT = r"""
set -euo pipefail
paths=()

# 1) Parse nginx configs (active + available).
for d in /etc/nginx /etc/nginx/sites-enabled /etc/nginx/sites-available /etc/nginx/conf.d; do
  [ -d "$d" ] || continue
  while IFS= read -r line; do
    tok=$(echo "$line" | awk '{print $2}' | tr -d ';')
    [ -n "$tok" ] || continue
    case "$tok" in
      off|syslog:*|/dev/*|stderr) continue ;;
    esac
    paths+=("$tok")
  done < <(grep -RhE '^\s*access_log\s+' "$d" 2>/dev/null || true)
done

# 2) Common log locations.
for g in /var/log/nginx/access.log /var/log/nginx/*access*.log; do
  [ -r "$g" ] && paths+=("$g")
done

printf '%s\n' "${paths[@]}" | sort -u
"""


def discover_access_logs(server: ServerConfig) -> list[str]:
    out = run_command(
        SSHConnInfo(
            host=server.ssh.host,
            port=server.ssh.port,
            user=server.ssh.user,
            key_path=server.ssh.key_path,
            key_passphrase_env=server.ssh.key_passphrase_env,
        ),
        _DISCOVER_SCRIPT,
        timeout_s=30,
    )
    paths: list[str] = []
    for ln in out.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("# STDERR:"):
            continue
        if ln in paths:
            continue
        paths.append(ln)
    return paths


def resolve_log_paths(server: ServerConfig) -> list[str]:
    explicit = list(_nginx_get(server, "access_log_paths") or [])
    auto_discover = bool(_nginx_get(server, "auto_discover_logs", True))
    if not auto_discover:
        return explicit

    discovered: list[str] = []
    if auto_discover:
        try:
            discovered = discover_access_logs(server)
        except Exception:
            discovered = []

    merged: list[str] = []
    for p in explicit + discovered:
        if p and p not in merged:
            merged.append(p)

    default_path = _nginx_get(server, "access_log_path", "/var/log/nginx/access.log")
    if not merged and default_path:
        merged = [default_path]

    # Keep only plausible nginx access logs.
    out: list[str] = []
    for p in merged:
        if "access" not in p.lower():
            continue
        if p.endswith(".gz"):
            continue
        out.append(p)
    return out or ([default_path] if default_path else [])


def host_from_log_path(log_path: str) -> str | None:
    # /var/log/nginx/lottery.modelmarket.dev.access.log -> lottery.modelmarket.dev
    m = re.search(r"/([^/]+)\.access\.log$", log_path)
    if not m:
        return None
    name = m.group(1)
    if name in ("access", "nginx"):
        return None
    return name.replace("_", ".")
