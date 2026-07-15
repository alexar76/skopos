from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from dateutil import parser as date_parser

from ..config import ServerConfig
from ..ssh import SSHConnInfo, run_command

_KNOCK_SCRIPT = r"""
set +e
echo '===AUTH==='
for f in /var/log/auth.log /var/log/secure; do
  [ -r "$f" ] && grep -hE "Failed password|Invalid user|Connection closed by|Disconnected from authenticating user|Did not receive identification" "$f" 2>/dev/null
done | tail -1000
echo '===UFW==='
for f in /var/log/ufw.log /var/log/kern.log /var/log/syslog; do
  [ -r "$f" ] && grep -h "UFW BLOCK" "$f" 2>/dev/null
done | tail -600
echo '===KERNEL==='
for f in /var/log/kern.log /var/log/syslog /var/log/messages; do
  [ -r "$f" ] && grep -hE "SRC=[0-9]" "$f" 2>/dev/null | grep -iE "DROP|REJECT|BLOCK|DENIED" | grep "DPT="
done | tail -500
echo '===FAIL2BAN==='
for f in /var/log/fail2ban.log /var/log/fail2ban/fail2ban.log; do
  [ -r "$f" ] && grep -hE "Ban |Unban " "$f" 2>/dev/null
done | tail -300
"""

_RE_SYSLOG_TS = re.compile(
    r"^(?P<ts>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+\S+\s+"
)
_RE_SSH_FAILED = re.compile(
    r"Failed password for (?:invalid user )?(?P<user>\S+).* from (?P<ip>\d{1,3}(?:\.\d{1,3}){3}) port (?P<src_port>\d+)",
    re.I,
)
_RE_SSH_INVALID = re.compile(
    r"Invalid user (?P<user>\S+) from (?P<ip>\d{1,3}(?:\.\d{1,3}){3}) port (?P<src_port>\d+)",
    re.I,
)
_RE_SSH_PREAUTH = re.compile(
    r"Connection (?:closed|reset) by (?P<ip>\d{1,3}(?:\.\d{1,3}){3}) port (?P<src_port>\d+)",
    re.I,
)
_RE_UFW = re.compile(
    r"SRC=(?P<ip>\d{1,3}(?:\.\d{1,3}){3}).*?DPT=(?P<dpt>\d+)",
    re.I,
)
_RE_KERNEL = re.compile(
    r"SRC=(?P<ip>\d{1,3}(?:\.\d{1,3}){3}).*?DPT=(?P<dpt>\d+)",
    re.I,
)
_RE_FAIL2BAN_BAN = re.compile(
    r"Ban (?P<ip>\d{1,3}(?:\.\d{1,3}){3})",
    re.I,
)


@dataclass(frozen=True)
class PortKnockEvent:
    remote_addr: str
    dest_port: int | None
    src_port: int | None
    event_type: str
    source_log: str
    username: str | None
    ts_utc: str | None
    line_raw: str


def _ssh_info(server: ServerConfig) -> SSHConnInfo:
    return SSHConnInfo(
        host=server.ssh.host,
        port=server.ssh.port,
        user=server.ssh.user,
        key_path=server.ssh.key_path,
        key_passphrase_env=server.ssh.key_passphrase_env,
    )


def _split_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current = "_head"
    buf: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("===") and stripped.endswith("==="):
            sections[current] = "\n".join(buf).strip()
            current = stripped.strip("=").strip().lower()
            buf = []
        elif line.startswith("# STDERR:"):
            continue
        else:
            buf.append(line)
    sections[current] = "\n".join(buf).strip()
    return sections


def _parse_syslog_ts(line: str) -> str | None:
    m = _RE_SYSLOG_TS.match(line)
    if not m:
        return None
    try:
        # Syslog without year — assume current year
        raw = f"{m.group('ts')} {datetime.now(tz=timezone.utc).year}"
        dt = date_parser.parse(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def _parse_auth_line(line: str) -> PortKnockEvent | None:
    ip = port = user = etype = None
    src_port = None
    if m := _RE_SSH_FAILED.search(line):
        user, ip, src_port = m.group("user"), m.group("ip"), int(m.group("src_port"))
        etype = "ssh_failed_password"
        port = 22
    elif m := _RE_SSH_INVALID.search(line):
        user, ip, src_port = m.group("user"), m.group("ip"), int(m.group("src_port"))
        etype = "ssh_invalid_user"
        port = 22
    elif m := _RE_SSH_PREAUTH.search(line):
        ip, src_port = m.group("ip"), int(m.group("src_port"))
        etype = "ssh_preauth_drop"
        port = 22
    else:
        return None
    return PortKnockEvent(
        remote_addr=ip,
        dest_port=port,
        src_port=src_port,
        event_type=etype,
        source_log="auth",
        username=user,
        ts_utc=_parse_syslog_ts(line),
        line_raw=line.strip(),
    )


def _parse_firewall_line(line: str, source: str, etype: str) -> PortKnockEvent | None:
    m = _RE_UFW.search(line) if source == "ufw" else _RE_KERNEL.search(line)
    if not m:
        return None
    return PortKnockEvent(
        remote_addr=m.group("ip"),
        dest_port=int(m.group("dpt")),
        src_port=None,
        event_type=etype,
        source_log=source,
        username=None,
        ts_utc=_parse_syslog_ts(line),
        line_raw=line.strip(),
    )


def _parse_fail2ban_line(line: str) -> PortKnockEvent | None:
    m = _RE_FAIL2BAN_BAN.search(line)
    if not m:
        return None
    return PortKnockEvent(
        remote_addr=m.group("ip"),
        dest_port=None,
        src_port=None,
        event_type="fail2ban_ban",
        source_log="fail2ban",
        username=None,
        ts_utc=_parse_syslog_ts(line),
        line_raw=line.strip(),
    )


def parse_knock_line(line: str, section: str) -> PortKnockEvent | None:
    line = line.strip()
    if not line:
        return None
    if section == "auth":
        return _parse_auth_line(line)
    if section == "ufw":
        return _parse_firewall_line(line, "ufw", "firewall_block")
    if section == "kernel":
        return _parse_firewall_line(line, "kernel", "kernel_drop")
    if section == "fail2ban":
        return _parse_fail2ban_line(line)
    return None


def fetch_port_knocks(server: ServerConfig) -> list[PortKnockEvent]:
    raw = run_command(_ssh_info(server), _KNOCK_SCRIPT, timeout_s=90)
    sections = _split_sections(raw)
    events: list[PortKnockEvent] = []
    seen: set[str] = set()
    for sec in ("auth", "ufw", "kernel", "fail2ban"):
        for line in sections.get(sec, "").splitlines():
            ev = parse_knock_line(line, sec)
            if not ev or ev.line_raw in seen:
                continue
            seen.add(ev.line_raw)
            events.append(ev)
    return events
