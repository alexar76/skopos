"""Security report builder tests."""

from skopos.security.posture import SecurityPosture, ServerScore
from skopos.security.report_builder import build_fallback_security_report


def _posture(**kwargs) -> SecurityPosture:
    defaults = dict(
        fleet_score=62,
        grade="C",
        server_scores=[ServerScore("srv1", 62, "C")],
        alerts=[],
        remarks=["Test remark"],
        computed_at_utc="2026-07-01T00:00:00+00:00",
    )
    defaults.update(kwargs)
    return SecurityPosture(**defaults)


def test_fallback_report_includes_remediation():
    bundle = build_fallback_security_report(
        posture=_posture(),
        findings_map={
            "srv1": [
                {
                    "severity": "medium",
                    "title": "Disk usage high (/var)",
                    "detail": "90%",
                    "recommendation": "Free disk space",
                }
            ]
        },
        snapshots=[{"server_name": "srv1", "host": "1.2.3.4", "payload": {}}],
        knocks_summary=None,
        locale="en",
    )
    assert bundle.source == "rules"
    assert "Remediation" in bundle.markdown or "remediation" in bundle.markdown.lower()
    assert "Free disk space" in bundle.markdown
