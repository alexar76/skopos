from __future__ import annotations

from skopos.themes import THEMES, THEME_ORDER, apply_chart_axes, build_app_css, build_critical_shell_css, build_portal_overlay_css, build_security_css, build_sidebar_layout_css, build_status_bar_css, build_widget_css, chart_layout_kwargs, contrast_ratio, theme_shell_bg, theme_surface_bg, _widget_palette


def test_all_themes_defined():
    assert set(THEME_ORDER) == set(THEMES.keys())


def test_theme_css_generates():
    for tid in THEME_ORDER:
        css = build_app_css(THEMES[tid])
        assert ".stApp" in css
        assert THEMES[tid].accent in css


def test_security_css_generates():
    for tid in THEME_ORDER:
        css = build_security_css(THEMES[tid])
        assert ".sec-score-ring" in css


def test_chart_layout_hover_bg_is_solid():
    for tid in THEME_ORDER:
        layout = chart_layout_kwargs(THEMES[tid])
        bg = layout["hoverlabel"]["bgcolor"]
        assert "gradient" not in bg
        assert bg.startswith("#")


def test_apply_chart_axes_uses_theme_font():
    import plotly.graph_objects as go

    fig = go.Figure(data=[go.Bar(x=["a"], y=[1])])
    apply_chart_axes(fig, THEMES["light"])
    assert fig.layout.xaxis.tickfont.color == THEMES["light"].chart_font
    assert fig.layout.yaxis.title.font.color == THEMES["light"].chart_font


def test_theme_text_contrast_on_surface():
    """Body and chart text must stay readable on card surfaces."""
    for tid in THEME_ORDER:
        th = THEMES[tid]
        surface = theme_surface_bg(th)
        assert contrast_ratio(th.text, surface) >= 4.5, f"{tid}: text on surface"
        assert contrast_ratio(th.chart_font, surface) >= 4.5, f"{tid}: chart font on surface"
        assert contrast_ratio(th.text_muted, surface) >= 3.0, f"{tid}: muted on surface"


def test_dark_css_uses_dark_surfaces_not_light():
    css = build_app_css(THEMES["dark"])
    assert "#161b22" in css
    assert "#faf6ef" not in css
    assert THEMES["dark"].text in css


def test_code_blocks_use_light_text_on_dark_bg():
    css = build_app_css(THEMES["light"])
    assert "stCode" in css
    assert "#e6edf3" in css
    assert "#0f1419" in css
    assert "#174ea6" in css


def test_inline_code_badge_contrast_dark_theme():
    css = build_app_css(THEMES["dark"])
    assert "stExpander" in css
    assert "#79c0ff" in css


def test_critical_shell_css_matches_theme():
    for tid in THEME_ORDER:
        css = build_critical_shell_css(THEMES[tid])
        assert theme_shell_bg(THEMES[tid]) in css
        assert THEMES[tid].app_bg in css
        assert "skopos-theme-id" in css
        assert "skopos-theme-boot" in css
        assert "skopos-status-bar" in css
        assert "transition: none" in css
        assert "if (stored && shells[stored])" not in css
        assert 'localStorage.setItem("skopos-theme-id", id)' in css
        assert 'localStorage.getItem("skopos-theme-id")' in css


def test_status_bar_css_covers_all_themes():
    css = build_status_bar_css()
    assert "stHeader" in css
    assert "display: none" in css
    for tid in THEME_ORDER:
        assert f'data-skopos-theme="{tid}"' in css


def test_topbar_css_styles_running_widget():
    from skopos.ui_topbar import build_topbar_css

    css = build_topbar_css(THEMES["light"])
    assert "stStatusWidget" in css
    assert "stToolbar" in css
    assert "skopos-topbar" in css


def test_portal_overlay_css_matches_active_theme():
    for tid in THEME_ORDER:
        css = build_portal_overlay_css(THEMES[tid])
        assert "stSelectboxVirtualDropdown" in css
        assert "stDateInputPopover" in css
        assert "stTooltip" in css
        assert _widget_palette(THEMES[tid])["widget_bg"] in css
        assert THEMES[tid].text in css


def test_widget_css_covers_native_controls():
    for tid in THEME_ORDER:
        css = build_widget_css(THEMES[tid])
        assert "stRadio" in css
        assert "stToggle" in css
        assert "stSlider" in css
        assert "stAlert" in css
        assert "stDataFrame" in css


def test_app_css_styles_selectbox_value():
    css = build_app_css(THEMES["light"])
    assert "stSelectbox" in css
    assert "-webkit-text-fill-color" in css


def test_midnight_palette_uses_warm_chips():
    pal = _widget_palette(THEMES["midnight"])
    assert "#ffd56a" in pal["chip_text"]
    assert "255,140,42" in pal["chip_bg"]


def test_sidebar_layout_css_modes():
    css = build_sidebar_layout_css(THEMES["light"], collapsed=False)
    assert "skopos-sidebar-expanded" in css
    assert "skopos-sidebar-bottom-start" in css
    assert 'localStorage.setItem("skopos-sidebar-collapsed", "0")' in css
    assert "skopos-rail-toggle-marker" not in css


def test_agent_widget_css_targets_innermost_block_only():
    from skopos.themes import build_agent_widget_css

    agent_css = build_agent_widget_css(THEMES["light"])
    assert ':not(:has(> div.element-container > div[data-testid="stVerticalBlock"]' in agent_css
    assert "stats-agent-fab-slot" in agent_css
    assert "position: fixed" in agent_css
