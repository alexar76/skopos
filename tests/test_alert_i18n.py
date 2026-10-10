from skopos.security.alert_i18n import localize_alert
from skopos.security.posture import SecurityAlert


def test_localize_active_threat_ru():
    alert = SecurityAlert(
        id="knock:1.2.3.4",
        severity="high",
        category="perimeter",
        title="Active threat: 1.2.3.4",
        message="SSH brute force",
        server_name="metis",
        action="Block IP in firewall / ensure fail2ban is active; verify SSH key-only auth.",
    )
    loc = localize_alert(alert, "ru")
    assert loc.title == "Активная угроза: 1.2.3.4"
    assert "firewall" in loc.action or "fail2ban" in loc.action
