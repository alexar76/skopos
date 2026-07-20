from __future__ import annotations

import pytest

from skopos.i18n import (
    NAV_PAGES,
    _locale_from_accept_language,
    _locale_from_system,
    active_locale,
    browser_page_title,
    detect_initial_locale,
    ensure_locale_state,
    t,
    t_list,
)


def test_i18n_english_default():
    assert t("security.title", "en") == "Security Center"
    assert t("security.title", "ru") == "Центр безопасности"
    assert t("security.title", "es") == "Centro de seguridad"


def test_i18n_analytics_english():
    assert t("analytics.globe_hint", "en").startswith("🖱️")
    assert "Вращайте" in t("analytics.globe_hint", "ru")


def test_locale_from_accept_language():
    assert _locale_from_accept_language("en-US,en;q=0.9") == "en"
    assert _locale_from_accept_language("ru-RU,ru;q=0.9,en;q=0.8") == "ru"
    assert _locale_from_accept_language("de-DE,de;q=0.9") is None


def test_detect_initial_locale_fallback(monkeypatch):
    monkeypatch.delenv("LANG", raising=False)
    monkeypatch.setenv("LANG", "ru_RU.UTF-8")
    assert detect_initial_locale() == "ru"


def test_i18n_fallback_unknown_key():
    assert t("missing.key", "en") == "missing.key"


def test_i18n_format():
    assert "24" in t("common.last_hours", "en", h=24)


def test_i18n_nav_menu_keys():
    for loc in ("en", "ru", "es"):
        for _path, key, _icon in NAV_PAGES:
            assert t(key, loc) != key


def test_render_sidebar_nav_imports_streamlit():
    import skopos.i18n as i18n_mod

    assert hasattr(i18n_mod, "st")
    src = __import__("inspect").getsource(i18n_mod.render_sidebar_nav)
    assert "import streamlit as st" not in src  # module-level import, not function-local


def test_resolve_page_link_path_returns_input_when_no_runtime():
    from skopos.i18n import _resolve_page_link_path

    assert _resolve_page_link_path("pages/1_Security.py") == "pages/1_Security.py"


def test_browser_page_title_ru():
    title = browser_page_title("analytics.title", locale="ru")
    assert "SKOPOS" in title
    assert "аналитика" in title.lower()


def test_i18n_agent_suggestions():
    for loc in ("en", "ru", "es"):
        items = t_list("agent.suggestions", loc)
        assert len(items) >= 4
        assert t("agent.suggestions_title", loc) != "agent.suggestions_title"


def test_i18n_onboarding_and_marketing_keys():
    for loc in ("en", "ru", "es"):
        assert t("app.tagline", loc) != "app.tagline"
        assert t("onboarding.title", loc) != "onboarding.title"
        assert t("security.agent_tab_hint", loc) != "security.agent_tab_hint"
        assert t("auth.no_password_warn", loc) != "auth.no_password_warn"
        assert t("auth.logout", loc) != "auth.logout"
        assert t("app.quick_start", loc) != "app.quick_start"
        assert t("wizard.title", loc) != "wizard.title"
        assert t("common.language", loc) != "common.language"
        assert t("security.resource_utilization", loc) != "security.resource_utilization"
        assert t("security.alerts_more", loc, n=3) != "security.alerts_more"


def test_active_locale_uses_canonical_key():
    import streamlit as st

    st.session_state.clear()
    st.session_state["skopos_locale"] = "en"
    st.session_state["skopos_locale_widget"] = "ru"
    assert active_locale() == "en"


def test_active_locale_migrates_legacy_locale_key():
    import streamlit as st

    st.session_state.clear()
    st.session_state["locale"] = "es"
    ensure_locale_state()
    assert st.session_state["skopos_locale"] == "es"
    assert active_locale() == "es"


def test_nav_labels_match_locale():
    assert t("app.analytics", "en") == "Analytics"
    assert t("app.analytics", "ru") == "Аналитика"
    assert t("common.theme", "en") == "Theme"
    assert t("common.theme", "ru") == "Тема"


def test_resource_gauge_metrics_localized():
    from skopos.security.charts import resource_gauge_metrics

    en = [m[1] for m in resource_gauge_metrics({}, locale="en")]
    ru = [m[1] for m in resource_gauge_metrics({}, locale="ru")]
    assert en != ru
    assert "CPU" in en[0]
    assert "CPU" in ru[0] or "Память" in ru[1]
