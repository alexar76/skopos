from __future__ import annotations

from skopos.security.knock_analyzer import classify_actor
from skopos.security.port_knocks import PortKnockEvent, parse_knock_line


def test_parse_ssh_failed():
    line = "Jul 14 08:00:00 host sshd[1]: Failed password for root from 203.0.113.50 port 49822 ssh2"
    ev = parse_knock_line(line, "auth")
    assert ev is not None
    assert ev.remote_addr == "203.0.113.50"
    assert ev.dest_port == 22
    assert ev.event_type == "ssh_failed_password"


def test_parse_invalid_user():
    line = "Jul 14 08:01:00 host sshd[2]: Invalid user admin from 198.51.100.10 port 55123 ssh2"
    ev = parse_knock_line(line, "auth")
    assert ev is not None
    assert ev.event_type == "ssh_invalid_user"
    assert ev.username == "admin"


def test_parse_ufw_block():
    line = "Jul 14 08:02:00 host kernel: [UFW BLOCK] IN=eth0 OUT= SRC=192.0.2.1 DST=1.2.3.4 LEN=60 PROTO=TCP DPT=22"
    ev = parse_knock_line(line, "ufw")
    assert ev is not None
    assert ev.remote_addr == "192.0.2.1"
    assert ev.dest_port == 22
    assert ev.event_type == "firewall_block"


def test_classify_ssh_bruteforcer():
    events = [
        PortKnockEvent("1.2.3.4", 22, 1000 + i, "ssh_failed_password", "auth", "root", None, f"line{i}")
        for i in range(6)
    ]
    acl, label, score = classify_actor("1.2.3.4", events)
    assert acl == "ssh_bruteforcer"
    assert score >= 75


def test_classify_port_scanner():
    events = [
        PortKnockEvent("5.6.7.8", port, None, "firewall_block", "ufw", None, None, f"p{port}")
        for port in (22, 80, 443, 3306, 8080)
    ]
    acl, label, score = classify_actor("5.6.7.8", events)
    assert acl == "port_scanner"
