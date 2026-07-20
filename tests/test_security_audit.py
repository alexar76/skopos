from __future__ import annotations

from skopos.security.audit import audit_snapshot
from skopos.security.probe import PortInfo, ServerSnapshot


def _snap(**kwargs) -> ServerSnapshot:
    base = dict(
        server_name="test",
        host="1.2.3.4",
        scanned_at_utc="2026-01-01T00:00:00+00:00",
    )
    base.update(kwargs)
    return ServerSnapshot(**base)


def test_audit_critical_disk():
    snap = _snap(
        disks=[{"mount": "/", "use_pct": 96.0, "filesystem": "/dev/sda1"}],
    )
    findings = audit_snapshot(snap)
    assert any(f.severity == "critical" and "Disk" in f.title for f in findings)


def test_audit_public_mysql():
    snap = _snap(
        ports=[
            PortInfo(proto="tcp", address="0.0.0.0", port=3306, bind_scope="public"),
        ]
    )
    findings = audit_snapshot(snap)
    assert any("MySQL" in f.title for f in findings)


def test_audit_failed_logins():
    snap = _snap(failed_logins=["Failed password for root"] * 5)
    findings = audit_snapshot(snap)
    assert any(f.category == "auth" for f in findings)
