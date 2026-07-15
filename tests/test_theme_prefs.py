"""Theme preference persistence."""

from __future__ import annotations

from skopos.theme_prefs import load_saved_theme, save_theme_pref


def test_theme_pref_roundtrip(tmp_path, monkeypatch):
    prefs = tmp_path / "ui_prefs.json"
    monkeypatch.setenv("SKOPOS_UI_PREFS_PATH", str(prefs))
    save_theme_pref("ocean")
    assert load_saved_theme() == "ocean"
    save_theme_pref("slate")
    assert load_saved_theme() == "slate"
