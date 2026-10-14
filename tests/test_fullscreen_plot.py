"""Fullscreen plot helper."""

from skopos.themes import THEMES, build_fullscreen_chart_css
from skopos.ui import _fullscreen_state_key, clear_fullscreen_state


def test_fullscreen_state_key():
    assert _fullscreen_state_key("geo_map") == "stats_fs_geo_map"


def test_clear_fullscreen_state_keeps_other_session_keys():
    session = {
        "stats_fs_geo_map": True,
        "stats_fs_sec_3d_metis": True,
        "skopos_theme": "light",
        "theme": "light",
    }
    clear_fullscreen_state(session)
    assert "stats_fs_geo_map" not in session
    assert "stats_fs_sec_3d_metis" not in session
    assert session["skopos_theme"] == "light"


def test_fullscreen_css_uses_theme_fields():
    for theme in THEMES.values():
        css = build_fullscreen_chart_css(theme)
        assert theme.app_bg in css
        assert theme.globe_scene_bg in css
        assert "stSidebar" in css
        assert "skopos-fs-marker" in css
        assert "position: fixed" in css
        assert "z-index: 9010" in css
