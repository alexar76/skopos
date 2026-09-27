from __future__ import annotations

from skopos.security.probe import _parse_ports, _split_sections


def test_split_sections():
    text = "===META===\nhost1\n===PORTS===\ntcp LISTEN 0 128 0.0.0.0:443"
    sec = _split_sections(text)
    assert sec.get("meta") == "host1"
    assert "443" in sec.get("ports", "")


def test_parse_ports_ss_format():
    section = """
State  Recv-Q Send-Q Local Address:Port Peer Address:PortProcess
tcp   LISTEN 0      128          0.0.0.0:443       0.0.0.0:*    users:(("nginx",pid=1,fd=3))
tcp   LISTEN 0      128        127.0.0.1:8080      0.0.0.0:*
"""
    ports = _parse_ports(section)
    assert any(p.port == 443 and p.bind_scope == "public" for p in ports)
    assert any(p.port == 8080 and p.bind_scope == "localhost" for p in ports)
