"""SKOPOS ecosystem wiring — offline contracts for new modules and mechanics."""

from __future__ import annotations

from pathlib import Path

from skopos.agent_portal import _portal_script
from skopos.ecosystem import ecosystem_segment
from skopos.economy.capabilities import CAPABILITY_BY_ID
from skopos.economy.handlers import HANDLERS
from skopos.host_infer import infer_host
from skopos.security.posture import build_posture
from skopos.security.project_audit import ProjectSecurityIssue

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "pages"


def test_handlers_cover_all_capabilities():
    assert set(HANDLERS) == set(CAPABILITY_BY_ID)


def test_main_pages_mount_floating_agent_at_end():
    """Agent FAB must mount via finalize_page after page content (dashboard regression)."""
    expected = {
        "dashboard.py",
        "1_Security.py",
        "2_Settings.py",
        "3_Scan_History.py",
        "5_Fleet.py",
    }
    for name in expected:
        path = PAGES / name if name != "dashboard.py" else ROOT / name
        text = path.read_text(encoding="utf-8")
        assert "finalize_page(" in text, name
        assert text.rfind("finalize_page(") > text.rfind("bootstrap_app("), name


def test_posture_includes_project_audit_findings():
    issue = ProjectSecurityIssue(
        severity="medium",
        category="config",
        title="World-readable config",
        detail="chmod 600 recommended",
        recommendation="Run chmod 600 on config files",
    )
    posture = build_posture(
        server_findings={},
        knock_summary={},
        project_issues=[issue],
        stale_servers=[],
        fail2ban_by_server={},
    )
    assert any(a.category == "project" for a in posture.alerts)
    assert posture.fleet_score < 100


def test_host_infer_aligns_with_ecosystem_segments():
    host = infer_host("/platon/api", server_name="factory")
    assert host is not None
    assert ecosystem_segment("/platon/api", host=host) == "oracles"
    host2 = infer_host("/monitor/api/state", server_name="factory")
    assert host2 is not None
    assert ecosystem_segment("/monitor/api/state", host=host2) == "monitor"


def test_floating_widget_contract():
    """Self-contained factory-style widget: FAB + animated panel + backend call."""
    from skopos.agent_widget import _WIDGET_JS

    assert "skopos-agent-root" in _WIDGET_JS
    assert "skopos-agent-panel" in _WIDGET_JS
    assert "skopos-agent-fab" in _WIDGET_JS
    assert "is-open" in _WIDGET_JS  # open/close animation toggle
    assert "/agent/chat" in _WIDGET_JS  # talks to the SKOPOS backend
    assert "Bearer " in _WIDGET_JS  # HMAC session token
    # Surfaces are driven by CSS variables so the widget follows the active theme.
    assert "--sk-panel-bg" in _WIDGET_JS
    assert "var(--sk-text)" in _WIDGET_JS
    assert "applyPalette" in _WIDGET_JS


def test_floating_widget_config_carries_token_and_strings():
    from skopos.agent_widget import _build_config
    from skopos.themes import THEMES

    cfg = _build_config(
        locale="en",
        page="Security",
        server_name="factory",
        theme=THEMES["premium"],
    )
    assert cfg["token"] and "." in cfg["token"]
    assert cfg["strings"]["title"]
    assert cfg["page"] == "Security"
    assert cfg["theme"]["accent"] == THEMES["premium"].accent
    assert isinstance(cfg["suggestions"], list)


def test_floating_widget_palette_follows_theme():
    """The floating assistant gamma is derived from the selected dashboard theme."""
    from skopos.agent_widget import _build_config
    from skopos.themes import THEMES, theme_surface_bg

    for tid in ("light", "premium", "midnight", "ocean"):
        th = THEMES[tid]
        pal = _build_config(locale="en", page=None, server_name=None, theme=th)["palette"]
        assert pal["accent"] == th.accent
        assert pal["accent2"] == th.accent2
        assert pal["text"] == th.text
        assert pal["muted"] == th.text_muted
        # Panel surface tracks the theme's own surface color, not a fixed dark navy.
        assert theme_surface_bg(th) in pal["panelBg"]
        # FAB gradient follows the theme accents.
        assert th.accent in pal["fabBg"] and th.accent2 in pal["fabBg"]


def test_agent_portal_gated_behind_login():
    """Assistant must be torn down on the login screen (available only post-auth)."""
    script = _portal_script()
    assert "skopos-login-page-marker" in script
    assert "teardownLegacy" in script
    assert "stats-agent-panel" in script  # strip legacy Streamlit chat too


def test_mount_floating_agent_requires_auth():
    """Server-side guard: floating agent only mounts for authenticated sessions."""
    import inspect

    from skopos.app_shell import mount_floating_agent

    src = inspect.getsource(mount_floating_agent)
    assert "is_dashboard_authenticated()" in src


def test_agent_service_uses_injection_guard():
    """Floating assistant must sanitize user input and wrap fleet context."""
    import inspect

    from skopos.agent import service

    src = inspect.getsource(service.answer_agent_message)
    assert "sanitize_user_input" in src
    assert "wrap_untrusted" in src
    assert "build_system_prompt" in src
    assert "verify_canary_intact" in src
