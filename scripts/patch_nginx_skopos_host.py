#!/usr/bin/env python3
"""Insert SKOPOS $host log_format into /etc/nginx/nginx.conf (idempotent)."""
from __future__ import annotations

from pathlib import Path

CONF = Path("/etc/nginx/nginx.conf")
BACKUP = Path("/etc/nginx/nginx.conf.bak-skopos-host")
OLD = "\taccess_log /var/log/nginx/access.log;"
NEW = (
    "\tlog_format skopos '$host $remote_addr - $remote_user [$time_local] '\n"
    "\t                  '\"$request\" $status $body_bytes_sent \"$http_referer\" \"$http_user_agent\"';\n"
    "\n"
    "\taccess_log /var/log/nginx/access.log skopos;"
)


def main() -> int:
    text = CONF.read_text()
    if "log_format skopos" in text and "access.log skopos" in text:
        print("ALREADY_SKOPOS_FORMAT")
        return 0
    if OLD not in text:
        print("access_log line not found", flush=True)
        return 1
    if not BACKUP.exists():
        BACKUP.write_text(text)
        print(f"backup {BACKUP}")
    CONF.write_text(text.replace(OLD, NEW, 1))
    print("PATCHED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
