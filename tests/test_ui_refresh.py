"""Section refresh nonce — load once, bump only when asked."""

from __future__ import annotations

from skopos.i18n import t
from skopos.ui_refresh import bump_refresh, refresh_key, refresh_nonce


def test_refresh_nonce_starts_at_zero():
    store: dict = {}
    assert refresh_nonce("analytics", store) == 0
    assert refresh_key("analytics") == "_skopos_refresh_analytics"


def test_bump_refresh_is_per_section():
    store: dict = {}
    assert bump_refresh("geo", store) == 1
    assert bump_refresh("geo", store) == 2
    assert refresh_nonce("overview", store) == 0
    assert refresh_nonce("geo", store) == 2


def test_refresh_hint_exists_in_every_locale():
    for loc in ("en", "ru", "es", "fr", "zh"):
        assert t("common.refresh", loc) != "common.refresh"
        assert t("common.refresh_hint", loc) != "common.refresh_hint"
    assert t("common.refresh", "ru") == "Обновить"


def test_analytics_loading_copy_exists_in_every_locale():
    for loc in ("en", "ru", "es", "fr", "zh"):
        assert t("analytics.loading", loc) != "analytics.loading"
        assert t("analytics.updating", loc) != "analytics.updating"
    assert t("analytics.loading", "ru") == "Загружаем аналитику…"


def test_dashboard_shows_spinner_on_first_analytics_load():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "dashboard.py").read_text(encoding="utf-8")
    assert "page_loading(T(ctx, \"analytics.loading\"))" in src
    assert "show_spinner=False" in src
