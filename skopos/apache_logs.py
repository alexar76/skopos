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


# Apache access logs come only from CustomLog/TransferLog directives (ErrorLog is
# separate), so every discovered path is authoritative — no filename heuristics
# needed. We scan Debian (apache2) and RHEL (httpd) layouts incl. conf.d/conf-enabled.
_DISCOVER_SCRIPT = r"""
set -euo pipefail
paths=()

for d in \
  /etc/apache2 \
  /etc/apache2/sites-enabled \
  /etc/apache2/sites-available \
  /etc/apache2/conf-enabled \
  /etc/apache2/conf-available \
  /etc/httpd \
  /etc/httpd/conf \
  /etc/httpd/conf.d \
  /etc/httpd/conf.modules.d; do
  [ -d "$d" ] || continue
  while IFS= read -r line; do
    # CustomLog "<path>" <format>  |  TransferLog "<path>"
    tok=$(echo "$line" | sed -E 's/^\s*(CustomLog|TransferLog)\s+//I' | awk '{print $1}' | tr -d '"')
    [ -n "$tok" ] || continue
    case "$tok" in
      off|syslog:*|/dev/*|stderr|combined|common|"|"*|"${APACHE_LOG_DIR}"*) ;;
    esac
    case "$tok" in
      off|syslog:*|/dev/*|stderr|combined|common) continue ;;
      "|"*) continue ;;                 # piped logger — cannot tail a file
    esac
    # Expand the common ${APACHE_LOG_DIR} placeholder (Debian default).
    tok=${tok//\$\{APACHE_LOG_DIR\}//var/log/apache2}
    case "$tok" in
      /*) paths+=("$tok") ;;            # absolute only (skip relative ServerRoot paths)
    esac
  done < <(grep -RhE '^\s*(CustomLog|TransferLog)\s+' "$d" 2>/dev/null || true)
done

for g in \
  /var/log/apache2/access.log \
  /var/log/apache2/other_vhosts_access.log \
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

    # Every path here is authoritative (explicit config, default, or a CustomLog/
    # TransferLog directive — never an ErrorLog), so we do NOT drop by filename:
    # Apache vhosts routinely log to files without "access" in the name. Only skip
    # rotated .gz archives.
    out: list[str] = []
    for p in merged:
        if p.endswith(".gz"):
            continue
        out.append(p)
    return out or ([default_path] if default_path else [])


_GENERIC_LOG_NAMES = {"access", "apache2", "httpd", "other_vhosts", "ssl", "vhost"}


def host_from_log_path(log_path: str) -> str | None:
    """Infer a vhost host from an Apache access-log filename.

    Handles the common vhost naming conventions:
      example.com.access.log · example.com-access.log · example.com_access.log
      example.com_access_log · example.com-access_log (RHEL-style)
    """
    for pat in (
        r"/([^/]+)[._-]access\.log$",   # <host>{.,-,_}access.log
        r"/([^/]+)[._-]access_log$",    # <host>{.,-,_}access_log (RHEL)
    ):
        m = re.search(pat, log_path)
        if m:
            name = m.group(1)
            if name.lower() not in _GENERIC_LOG_NAMES:
                return name.replace("_", ".")
    return None
