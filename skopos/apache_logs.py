"""Discover Apache access logs on remote hosts (Debian/Ubuntu + RHEL paths)."""

from __future__ import annotations

import re

from .config import ServerConfig
from .ssh import SSHConnInfo, run_command


def _apache_get(server: ServerConfig, key: str, default=None):
    apache = getattr(server, "apache", None)
    if apache is None:
        return default
    return getattr(apache, key, default)


_DISCOVER_SCRIPT = r"""
set -euo pipefail
paths=()

for d in /etc/apache2 /etc/httpd /etc/apache2/sites-enabled /etc/apache2/sites-available; do
  [ -d "$d" ] || continue
  while IFS= read -r line; do
    tok=$(echo "$line" | awk '{print $NF}' | tr -d '"')
    [ -n "$tok" ] || continue
    case "$tok" in
      off|syslog:*|/dev/*|stderr|combined|common) continue ;;
    esac
    paths+=("$tok")
  done < <(grep -RhE '^\s*(CustomLog|TransferLog)\s+' "$d" 2>/dev/null || true)
done

for g in \
  /var/log/apache2/access.log \
  /var/log/apache2/*access*.log \
  /var/log/httpd/access_log \
  /var/log/httpd/*access* \
  /usr/local/apache2/logs/access_log \
  /opt/metis/deploy/apache-test/logs/access_log; do
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
    if not bool(_apache_get(server, "enabled", False)):
        return []

    explicit = list(_apache_get(server, "access_log_paths") or [])
    auto_discover = bool(_apache_get(server, "auto_discover_logs", True))
    if explicit and not auto_discover:
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

    default_path = _apache_get(server, "access_log_path", "/var/log/apache2/access.log")
    if not merged and default_path:
        merged = [default_path]

    out: list[str] = []
    for p in merged:
        low = p.lower()
        if "access" not in low and "access_log" not in low:
            continue
        if p.endswith(".gz"):
            continue
        out.append(p)
    return out or ([default_path] if default_path else [])


def host_from_log_path(log_path: str) -> str | None:
    m = re.search(r"/([^/]+)[_-]access\.log$", log_path)
    if m:
        name = m.group(1)
        if name not in ("access", "apache2", "httpd"):
            return name.replace("_", ".")
    m = re.search(r"/([^/]+)_access_log$", log_path)
    if m:
        return m.group(1).replace("_", ".")
    return None
