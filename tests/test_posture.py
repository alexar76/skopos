from __future__ import annotations

from skopos.security.audit import SecurityFinding
from skopos.security.fail2ban_status import Fail2banStatus
from skopos.security.posture import build_posture, score_to_grade
from skopos.security.project_audit import ProjectSecurityIssue


def test_fleet_score_penalizes_critical():
    findings = {
        "factory": [
            SecurityFinding("critical", "ports", "MySQL exposed", "3306 open", "close it"),
        ]
    }
    posture = build_posture(
        server_findings=findings,
        knock_summary=[],
        project_issues=[],
    )
    assert posture.fleet_score < 90
    assert posture.critical_count >= 1


def test_project_issues_create_alerts():
    issues = [
        ProjectSecurityIssue(
            severity="high",
            category="project",
            title="No auth",
            detail="open dashboard",
            recommendation="set password",
        )
    ]
    posture = build_posture(
        server_findings={"s1": []},
        knock_summary=[],
        project_issues=issues,
    )
    assert any(a.category == "project" for a in posture.alerts)


def test_grade_mapping():
    assert score_to_grade(95) == "A"
    assert score_to_grade(40) == "F"


def test_fail2ban_remark_when_all_servers_protected():
    fb = Fail2banStatus(
        service_active=True,
        jails=("sshd",),
        currently_banned=2,
        recent_ban_ips=("1.2.3.4",),
        sshd_jail=True,
        summary="service active; jails: sshd",
    )
    posture = build_posture(
        server_findings={"metis": [], "factory": []},
        knock_summary=[{"threat_score": 90, "actor_ip": "9.9.9.9"}],
        project_issues=[],
        fail2ban_by_server={"metis": fb, "factory": fb},
    )
    assert any("fail2ban active on all" in r for r in posture.remarks)
