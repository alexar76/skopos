"""Section refresh nonce — load once, bump only when asked."""

from __future__ import annotations

from skopos.i18n import t
from skopos.ui_refresh import (
    bump_refresh,
    consume_refresh_request,
    refresh_key,
    refresh_nonce,
    refresh_request_key,
)


def test_refresh_nonce_starts_at_zero():
    store: dict = {}
    assert refresh_nonce("analytics", store) == 0
    assert refresh_key("analytics") == "_skopos_refresh_analytics"


def test_bump_refresh_is_per_section():
    store: dict = {}
    assert bump_refresh("geo", store) == 1
    assert consume_refresh_request("geo", store) is True
    assert consume_refresh_request("geo", store) is False
    assert bump_refresh("geo", store) == 2
    assert refresh_nonce("overview", store) == 0
    assert refresh_nonce("geo", store) == 2
    assert refresh_request_key("geo") == "_skopos_refresh_requested_geo"


def test_saved_nonce_does_not_trigger_analytics_refresh_in_a_new_session():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "dashboard.py").read_text(
        encoding="utf-8"
    )
    assert "should_refresh_snapshot(" in src
    assert 'get("_section_nonce", -1)) != dashboard_refresh_nonce' not in src


def test_refresh_hint_exists_in_every_locale():
    for loc in ("en", "ru", "es", "fr", "zh"):
        assert t("common.refresh", loc) != "common.refresh"
        assert t("common.refresh_hint", loc) != "common.refresh_hint"
    assert t("common.refresh", "ru") == "Обновить"


def test_dashboard_loading_copy_exists_in_every_locale():
    for loc in ("en", "ru", "es", "fr", "zh"):
        assert t("analytics.loading", loc) != "analytics.loading"
        assert t("analytics.updating", loc) != "analytics.updating"
        assert t("common.loading_section", loc) != "common.loading_section"
        assert t("common.section_ready", loc) != "common.section_ready"
        assert t("common.cached_snapshot", loc) != "common.cached_snapshot"
        assert t("common.cached_snapshot_refreshing", loc) != "common.cached_snapshot_refreshing"
        assert t("common.first_dashboard_load", loc) != "common.first_dashboard_load"
    assert t("analytics.loading", "ru") == "Загружаем аналитику…"


def test_data_dashboards_are_server_side_lazy_and_show_progress():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    paths = [
        root / "dashboard.py",
        root / "pages" / "1_Security.py",
        root / "pages" / "3_Scan_History.py",
        root / "pages" / "6_Observability.py",
    ]
    for path in paths:
        src = path.read_text(encoding="utf-8")
        assert "render_lazy_tabs(" in src, path.name
        assert "section_loading(" in src, path.name
        assert "st.tabs(" not in src, path.name


def test_analytics_cache_survives_process_reruns():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "dashboard.py").read_text(encoding="utf-8")
    assert 'persist="disk"' in src
    assert "fetch_summary_metrics" in src
    # definition + one live paint. A second call stacks duplicate KPI tiles
    # after Refresh (Streamlit 1.37 empty().container() appends).
    assert src.count("_render_summary_strip(") == 2


def test_remediation_keeps_its_last_snapshot_while_refreshing():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "pages" / "7_Remediation.py").read_text(
        encoding="utf-8"
    )
    assert "section_loading(" in src
    assert 'persist="disk"' in src
