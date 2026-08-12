"""Theme session state — canonical key vs widget sync."""

from __future__ import annotations

from skopos.theme_prefs import (
    SKOPOS_THEME_KEY,
    SKOPOS_THEME_WIDGET,
    apply_theme_state,
    save_theme_pref,
    sync_theme_widget,
)


def test_saved_theme_wins_over_default_midnight(tmp_path, monkeypatch):
    themes = {"light", "midnight", "ocean"}
    prefs = tmp_path / "ui_prefs.json"
    monkeypatch.setenv("SKOPOS_UI_PREFS_PATH", str(prefs))
    save_theme_pref("light")

    session: dict = {}
    apply_theme_state(session, valid_ids=themes, default="midnight")
    sync_theme_widget(session, valid_ids=themes, default="midnight")

    assert session[SKOPOS_THEME_KEY] == "light"
    assert session[SKOPOS_THEME_WIDGET] == "light"


def test_widget_choice_persists_in_canonical_key():
    themes = {"light", "midnight"}
    session = {SKOPOS_THEME_WIDGET: "light"}
    apply_theme_state(session, valid_ids=themes, default="midnight")
    sync_theme_widget(session, valid_ids=themes, default="midnight")
    assert session[SKOPOS_THEME_KEY] == "light"


def test_canonical_key_keeps_widget_on_navigation():
    themes = {"light", "midnight", "slate"}
    session = {SKOPOS_THEME_KEY: "slate", SKOPOS_THEME_WIDGET: "midnight"}
    sync_theme_widget(session, valid_ids=themes, default="midnight")
    assert session[SKOPOS_THEME_WIDGET] == "slate"
