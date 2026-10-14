from __future__ import annotations

import time

import pandas as pd
import plotly.graph_objects as go
from streamlit.testing.v1 import AppTest

from skopos.dashboard_snapshots import (
    load_dashboard_snapshot,
    save_dashboard_snapshot,
    should_refresh_snapshot,
)


def test_snapshot_round_trip_is_atomic_and_keeps_dataframes(tmp_path):
    payload = {"metrics": [["Requests", "42"]], "table": pd.DataFrame({"x": [1, 2]})}
    save_dashboard_snapshot("analytics", "overview", payload, cache_dir=tmp_path)

    loaded = load_dashboard_snapshot("analytics", "overview", cache_dir=tmp_path)

    assert loaded is not None
    assert loaded["metrics"] == [["Requests", "42"]]
    pd.testing.assert_frame_equal(loaded["table"], payload["table"])


def test_snapshot_is_shared_through_database_when_local_cache_is_empty(tmp_path):
    db_target = str(tmp_path / "shared.sqlite3")
    figure = go.Figure(go.Bar(x=pd.Series(["RU", "DE"]), y=pd.Series([7, 3])))
    payload = {
        "metrics": [["Requests", "73"]],
        "chart_rows": [[figure.to_dict()]],
        "table": pd.DataFrame({"country": ["RU", "DE"], "requests": [7, 3]}),
    }
    save_dashboard_snapshot(
        "analytics",
        "overview",
        payload,
        cache_dir=tmp_path / "worker-a",
        db_target=db_target,
    )

    loaded = load_dashboard_snapshot(
        "analytics",
        "overview",
        cache_dir=tmp_path / "worker-b",
        db_target=db_target,
    )

    assert loaded is not None
    assert loaded["metrics"] == payload["metrics"]
    restored_figure = go.Figure(loaded["chart_rows"][0][0])
    assert list(restored_figure.data[0].x) == ["RU", "DE"]
    assert list(restored_figure.data[0].y) == [7, 3]
    pd.testing.assert_frame_equal(loaded["table"], payload["table"])


def test_cached_snapshot_never_refreshes_without_an_explicit_request():
    cached_from_another_session = {"_section_nonce": 99, "chart_rows": []}

    assert should_refresh_snapshot(cached_from_another_session, False) is False
    assert should_refresh_snapshot(cached_from_another_session, True) is True
    assert should_refresh_snapshot(None, False) is True


def test_all_analytics_dashboards_render_and_cached_revisit_is_fast(tmp_path, monkeypatch):
    monkeypatch.setenv("SKOPOS_REQUIRE_DASHBOARD_AUTH", "0")
    monkeypatch.setenv("SKOPOS_DASHBOARD_CACHE_DIR", str(tmp_path))
    app = AppTest.from_file("dashboard.py", default_timeout=30).run()
    assert not app.exception

    minimums = {
        "overview": (7, 0),
        "geo": (6, 0),
        "audience": (5, 0),
        "content": (4, 0),
        "sources": (1, 0),
        "journal": (0, 1),
        "system": (0, 0),
    }
    for dashboard, (minimum_charts, minimum_tables) in minimums.items():
        started = time.monotonic()
        app.radio[0].set_value(dashboard).run(timeout=30)
        elapsed = time.monotonic() - started
        assert not app.exception, dashboard
        assert len(app.get("plotly_chart")) >= minimum_charts, dashboard
        assert len(app.dataframe) >= minimum_tables, dashboard
        assert elapsed < 15, f"{dashboard} took {elapsed:.1f}s"

    # The second visit must use the persisted last-good presentation snapshot;
    # it must not repeat the database work that built the first one.
    started = time.monotonic()
    app.radio[0].set_value("overview").run(timeout=10)
    elapsed = time.monotonic() - started
    assert not app.exception
    assert len(app.get("plotly_chart")) >= 7
    assert elapsed < 5, f"cached overview took {elapsed:.1f}s"
