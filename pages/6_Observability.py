"""Observability — Prometheus APM, Hub/Factory/Metis KPIs, 3D service graph."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from skopos.config import load_app_env

load_app_env()

from skopos.app_shell import T, bootstrap_app, finalize_page, prime_theme
from skopos.i18n import browser_page_title
from skopos.observability.charts import (
    chart_heatmap_by_capability,
    chart_kpi_gauges,
    chart_timeseries_matrix,
    targets_table_rows,
)
from skopos.observability.graph3d import chart_service_graph_3d
from skopos.observability.prom import (
    collect_overview_kpis,
    parse_instant_vector,
    parse_range_matrix,
    prometheus_base_url,
    query_instant,
    query_range,
)
from skopos.ui import display_dataframe, hero, plot, section_head
from skopos.ui_refresh import refresh_nonce, render_section_refresh


@st.cache_data(show_spinner=False)
def _cached_obs_kpis(refresh_nonce: int) -> tuple[dict, bool]:
    _ = refresh_nonce
    return collect_overview_kpis()


@st.cache_data(show_spinner=False)
def _cached_range(expr: str, hours: float, step: str, refresh_nonce: int):
    _ = refresh_nonce
    return parse_range_matrix(query_range(expr, hours=hours, step=step))


@st.cache_data(show_spinner=False)
def _cached_instant(expr: str, refresh_nonce: int):
    _ = refresh_nonce
    return parse_instant_vector(query_instant(expr))


st.set_page_config(
    page_title=browser_page_title("observability.title"),
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="auto",
)
prime_theme()

ctx = bootstrap_app(show_alerts=False)
locale = ctx.locale

hero(T(ctx, "observability.title"), T(ctx, "observability.subtitle"))
render_section_refresh("observability", locale)

kpis, live = _cached_obs_kpis(refresh_nonce("observability"))
prom_url = prometheus_base_url()
source_label = T(ctx, "observability.source_live") if live else T(ctx, "observability.source_demo")
st.caption(f"{T(ctx, 'observability.prometheus_url')}: `{prom_url}` · {source_label}")

if not live:
    st.warning(
        f"**{T(ctx, 'observability.prom_offline_title')}**\n\n"
        + T(ctx, "observability.prom_offline_body", url=prom_url.rstrip("/")),
        icon="⚠️",
    )


def _kpi_up(val: float | None) -> str:
    if not live:
        return "—"
    if val is None:
        return "—"
    return "UP" if val >= 0.5 else "DOWN"


def _kpi_num(val: float | None) -> str:
    if not live or val is None:
        return "—"
    try:
        f = float(val)
    except (TypeError, ValueError):
        return "—"
    if f != f:  # NaN
        return "—"
    return f"{f:.3g}"


c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric(T(ctx, "observability.kpi_hub"), _kpi_up(kpis.get("hub_up")))
c2.metric(T(ctx, "observability.kpi_factory"), _kpi_up(kpis.get("factory_up")))
c3.metric(T(ctx, "observability.kpi_metis"), _kpi_up(kpis.get("metis_up")))
c4.metric(T(ctx, "observability.kpi_rps"), _kpi_num(kpis.get("invoke_rps")))
c5.metric(T(ctx, "observability.kpi_402"), _kpi_num(kpis.get("payment_required_rps")))
c6.metric(T(ctx, "observability.kpi_p99"), _kpi_num(kpis.get("p99_s")))

tab_ov, tab_hub, tab_factory, tab_mesh, tab_graph = st.tabs(
    [
        T(ctx, "observability.tab_overview"),
        T(ctx, "observability.tab_hub"),
        T(ctx, "observability.tab_factory"),
        T(ctx, "observability.tab_mesh"),
        T(ctx, "observability.tab_graph"),
    ]
)
from skopos.ui_tab_deeplink import inject_tab_deeplink

inject_tab_deeplink(["overview", "hub", "factory", "mesh", "graph"])

with tab_ov:
    render_section_refresh("observability_overview", locale)
    if not live:
        st.caption(T(ctx, "observability.prom_offline_charts_note"))
    section_head(T(ctx, "observability.section_kpis"))
    st.caption(T(ctx, "observability.section_kpis_hint"))
    plot(chart_kpi_gauges(kpis), key="obs_kpi")
    section_head(T(ctx, "observability.section_targets"))
    st.caption(T(ctx, "observability.section_targets_hint"))
    display_dataframe(pd.DataFrame(targets_table_rows(live, kpis)), key="obs_targets")

with tab_hub:
    hub_n = render_section_refresh("observability_hub", locale)
    section_head(T(ctx, "observability.section_hub_rate"))
    st.caption(T(ctx, "observability.section_hub_rate_hint"))
    hub_rate = _cached_range(
        "sum by (capability) (rate(aimarket_hub_invokes_total[5m]))", 1.0, "30s", hub_n
    )
    if not hub_rate and not live:
        # Demo series so the tab is never blank offline.
        import time as _time

        now = _time.time()
        hub_rate = [
            {
                "metric": {"capability": "platon.oracle@v1"},
                "timestamps": [now - 3600 + i * 60 for i in range(60)],
                "values": [0.2 + (i % 7) * 0.03 for i in range(60)],
            },
            {
                "metric": {"capability": "sandbox.demo@v1"},
                "timestamps": [now - 3600 + i * 60 for i in range(60)],
                "values": [0.5 + (i % 5) * 0.02 for i in range(60)],
            },
        ]
    plot(chart_timeseries_matrix(hub_rate, T(ctx, "observability.chart_hub_rate")), key="obs_hub_rate")

    section_head(T(ctx, "observability.section_hub_heat"))
    st.caption(T(ctx, "observability.section_hub_heat_hint"))
    heat_rows = _cached_instant(
        "sum by (capability, result) (rate(aimarket_hub_invokes_total[15m]))", hub_n
    )
    if not heat_rows and not live:
        heat_rows = [
            {"metric": {"capability": "platon.oracle@v1", "result": "payment_required"}, "value": 0.12},
            {"metric": {"capability": "platon.oracle@v1", "result": "ok"}, "value": 0.01},
            {"metric": {"capability": "sandbox.demo@v1", "result": "ok"}, "value": 0.4},
        ]
    plot(chart_heatmap_by_capability(heat_rows, T(ctx, "observability.chart_hub_heat")), key="obs_hub_heat")

with tab_factory:
    fac_n = render_section_refresh("observability_factory", locale)
    section_head(T(ctx, "observability.section_factory"))
    st.caption(T(ctx, "observability.section_factory_hint"))
    factory_series = _cached_range('up{job="aicom"}', 6.0, "1m", fac_n)
    if not factory_series and not live:
        import time as _time

        now = _time.time()
        factory_series = [
            {
                "metric": {"job": "aicom"},
                "timestamps": [now - 6 * 3600 + i * 60 for i in range(360)],
                "values": [1.0] * 360,
            }
        ]
    plot(chart_timeseries_matrix(factory_series, T(ctx, "observability.chart_factory_up")), key="obs_factory")

with tab_mesh:
    mesh_n = render_section_refresh("observability_mesh", locale)
    section_head(T(ctx, "observability.section_mesh"))
    st.caption(T(ctx, "observability.section_mesh_hint"))
    metis_series = _cached_range('up{job="metis"} or on() vector(0)', 6.0, "1m", mesh_n)
    if not metis_series:
        metis_series = _cached_range("metis_up", 6.0, "1m", mesh_n)
    if not metis_series and not live:
        import time as _time

        now = _time.time()
        metis_series = [
            {
                "metric": {"job": "metis"},
                "timestamps": [now - 6 * 3600 + i * 60 for i in range(360)],
                "values": [1.0] * 360,
            }
        ]
    plot(chart_timeseries_matrix(metis_series, T(ctx, "observability.chart_metis_up")), key="obs_metis")

with tab_graph:
    render_section_refresh("observability_graph", locale)
    section_head(T(ctx, "observability.section_graph"))
    st.caption(T(ctx, "observability.section_graph_hint"))
    plot(chart_service_graph_3d(kpis), key="obs_graph3d")

finalize_page(ctx)
