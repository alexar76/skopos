from __future__ import annotations

import hashlib
import json
import threading

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from skopos.config import load_app_env, load_config

load_app_env()

from skopos.app_shell import T, bootstrap_app, finalize_page, stop_page, prime_theme
from skopos.i18n import t
from skopos.backfill import backfill_all
from dataclasses import replace

from skopos.charts import (
    chart_countries_bar,
    chart_countries_by_category,
    chart_countries_donut,
    chart_countries_map,
    chart_countries_map_2d,
    chart_countries_timeline,
    chart_donut_dimension,
    chart_ecosystem,
    chart_heatmap_hourly,
    chart_status_codes,
    chart_top_dimension,
    chart_traffic_timeline,
    chart_treemap_pages,
)
from skopos.collector import collect_once, run_forever
from skopos.config_paths import resolve_config_path
from skopos.db import connect, connect_for_config, init_db, read_sql_query
from skopos.db_dialect import resolve_db_target
from skopos.analytics_filters import AnalyticsFilterState, read_analytics_filters, render_analytics_filters
from skopos.analytics_queries import (
    fetch_countries_by_dimension,
    fetch_country_hourly,
    fetch_country_stats,
    fetch_filter_options,
    fetch_first_ts,
    fetch_has_traffic,
    fetch_heatmap,
    fetch_journal,
    fetch_kpis,
    fetch_source_stats,
    fetch_summary_metrics,
    fetch_status_classes,
    fetch_timeline,
    fetch_top_dimension,
    fetch_traffic_snapshot,
    fetch_treemap,
    fetch_verified_visitors,
)
from skopos.period_picker import (
    SESSION_CUSTOM_KEY,
    ensure_period_state,
    get_active_period,
    render_period_toolbar,
)
from skopos.log_sources import resolve_log_sources
from skopos.traffic import client_label
from skopos.ui import hero, plot, plot_fullscreen, section_head, section_loading
from skopos.ui_briefing import render_ecosystem_briefing_card
from skopos.ui_refresh import (
    consume_refresh_request,
    refresh_nonce,
    render_section_refresh,
)
from skopos.ui_onboarding import render_analytics_onboarding
from skopos.ui_lazy_tabs import render_lazy_tabs
from skopos.dashboard_snapshots import (
    load_dashboard_snapshot,
    save_dashboard_snapshot,
    should_refresh_snapshot,
)
from skopos.agent.ecosystem_briefing import TrafficSnapshot

from skopos.i18n import browser_page_title

st.set_page_config(
    page_title=browser_page_title("analytics.title"),
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="auto",
)
prime_theme()

_COLLECTOR_CACHE_VERSION = 7

ctx = bootstrap_app("./servers.yaml", "./agent.yaml")
cfg = ctx.cfg


@st.cache_resource
def _start_collector_thread(config_path: str, _cache_version: int):
    cfg = load_config(config_path)
    con = connect_for_config(cfg)
    init_db(con)
    con.close()
    t = threading.Thread(target=run_forever, args=(config_path,), daemon=True)
    t.start()
    return t


def _filters_key(filters: AnalyticsFilterState) -> str:
    payload = {
        "hide_bots": filters.hide_bots,
        "hide_service": filters.hide_service,
        "visitors_only": filters.visitors_only,
        "hide_datacenter": filters.hide_datacenter,
        "sel_servers": list(filters.sel_servers),
        "sel_hosts": list(filters.sel_hosts),
        "sel_countries": list(filters.sel_countries),
        "path_contains": filters.path_contains,
    }
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


@st.cache_data(show_spinner=False, persist="disk", max_entries=128)
def _cached_filter_options(
    db_target: str,
    period_cache_key: str,
    known_servers: tuple[str, ...],
    refresh_nonce: int = 0,
    *,
    _since_utc_iso: str,
    _until_utc_iso: str,
) -> tuple[list[str], list[str]]:
    _ = period_cache_key
    _ = refresh_nonce
    con = connect(db_target)
    try:
        return fetch_filter_options(
            con, known_servers, _since_utc_iso, _until_utc_iso
        )
    finally:
        con.close()


@st.cache_data(show_spinner=False, persist="disk", max_entries=128)
def _cached_kpis(
    db_target: str,
    since_utc_iso: str,
    until_utc_iso: str,
    known_servers: tuple[str, ...],
    filters_key: str,
    filters: AnalyticsFilterState,
    refresh_nonce: int = 0,
):
    _ = filters_key
    _ = refresh_nonce
    con = connect(db_target)
    try:
        return fetch_kpis(con, known_servers, since_utc_iso, until_utc_iso, filters)
    finally:
        con.close()


@st.cache_data(show_spinner=False, persist="disk", max_entries=128)
def _cached_summary_metrics(
    db_target: str,
    since_utc_iso: str,
    until_utc_iso: str,
    known_servers: tuple[str, ...],
    filters_key: str,
    filters: AnalyticsFilterState,
    refresh_nonce: int = 0,
):
    _ = filters_key
    _ = refresh_nonce
    con = connect(db_target)
    try:
        return fetch_summary_metrics(con, known_servers, since_utc_iso, until_utc_iso, filters)
    finally:
        con.close()


@st.cache_data(show_spinner=False, persist="disk", max_entries=128)
def _cached_verified_visitors(
    db_target: str,
    since_utc_iso: str,
    until_utc_iso: str,
    known_servers: tuple[str, ...],
    filters_key: str,
    filters: AnalyticsFilterState,
    refresh_nonce: int = 0,
) -> int:
    _ = filters_key
    _ = refresh_nonce
    con = connect(db_target)
    try:
        return fetch_verified_visitors(con, known_servers, since_utc_iso, until_utc_iso, filters)
    finally:
        con.close()


@st.cache_data(show_spinner=False, persist="disk", max_entries=128)
def _cached_first_ts(
    db_target: str,
    since_utc_iso: str,
    until_utc_iso: str,
    known_servers: tuple[str, ...],
    filters_key: str,
    filters: AnalyticsFilterState,
    refresh_nonce: int = 0,
) -> str | None:
    _ = filters_key
    _ = refresh_nonce
    con = connect(db_target)
    try:
        return fetch_first_ts(con, known_servers, since_utc_iso, until_utc_iso, filters)
    finally:
        con.close()


@st.cache_data(show_spinner=False, persist="disk", max_entries=128)
def _cached_country_stats(
    db_target: str,
    since_utc_iso: str,
    until_utc_iso: str,
    known_servers: tuple[str, ...],
    filters_key: str,
    filters: AnalyticsFilterState,
    refresh_nonce: int = 0,
) -> pd.DataFrame:
    _ = filters_key
    _ = refresh_nonce
    con = connect(db_target)
    try:
        return fetch_country_stats(con, known_servers, since_utc_iso, until_utc_iso, filters)
    finally:
        con.close()


@st.cache_data(show_spinner=False, persist="disk", max_entries=256)
def _cached_query_df(
    kind: str,
    db_target: str,
    since_utc_iso: str,
    until_utc_iso: str,
    known_servers: tuple[str, ...],
    filters_key: str,
    filters: AnalyticsFilterState,
    refresh_nonce: int = 0,
    **kwargs,
) -> pd.DataFrame:
    _ = filters_key
    _ = refresh_nonce
    con = connect(db_target)
    try:
        if kind == "timeline":
            return fetch_timeline(
                con, known_servers, since_utc_iso, until_utc_iso, filters,
                granularity=kwargs.get("granularity", "hour"),
            )
        if kind == "heatmap":
            return fetch_heatmap(con, known_servers, since_utc_iso, until_utc_iso, filters)
        if kind == "status":
            return fetch_status_classes(con, known_servers, since_utc_iso, until_utc_iso, filters)
        if kind == "top":
            return fetch_top_dimension(
                con, known_servers, since_utc_iso, until_utc_iso, filters,
                kwargs["column"], top_n=int(kwargs.get("top_n", 15)),
            )
        if kind == "country_hourly":
            return fetch_country_hourly(
                con, known_servers, since_utc_iso, until_utc_iso, filters,
                metric=kwargs.get("metric", "requests"),
                top_n=int(kwargs.get("top_n", 6)),
            )
        if kind == "host_country":
            return fetch_countries_by_dimension(
                con, known_servers, since_utc_iso, until_utc_iso, filters,
                dimension="host",
                metric=kwargs.get("metric", "requests"),
            )
        if kind == "server_country":
            return fetch_countries_by_dimension(
                con, known_servers, since_utc_iso, until_utc_iso, filters,
                dimension="server",
                metric=kwargs.get("metric", "requests"),
            )
        if kind == "treemap":
            return fetch_treemap(con, known_servers, since_utc_iso, until_utc_iso, filters)
        if kind == "journal":
            return fetch_journal(
                con, known_servers, since_utc_iso, until_utc_iso, filters,
                limit=int(kwargs.get("limit", 1000)),
            )
        raise ValueError(kind)
    finally:
        con.close()


@st.cache_data(show_spinner=False, persist="disk", max_entries=128)
def _cached_source_stats(
    db_target: str,
    since_utc_iso: str,
    until_utc_iso: str,
    known_servers: tuple[str, ...],
    filters_key: str,
    filters: AnalyticsFilterState,
    refresh_nonce: int = 0,
) -> tuple[int, int]:
    _ = filters_key
    _ = refresh_nonce
    con = connect(db_target)
    try:
        return fetch_source_stats(con, known_servers, since_utc_iso, until_utc_iso, filters)
    finally:
        con.close()


@st.cache_data(show_spinner=False, persist="disk", max_entries=128)
def _cached_traffic_snapshot(
    db_target: str,
    since_utc_iso: str,
    until_utc_iso: str,
    known_servers: tuple[str, ...],
    filters_key: str,
    filters: AnalyticsFilterState,
    refresh_nonce: int = 0,
) -> dict:
    _ = filters_key
    _ = refresh_nonce
    con = connect(db_target)
    try:
        return fetch_traffic_snapshot(con, known_servers, since_utc_iso, until_utc_iso, filters)
    finally:
        con.close()


@st.cache_data(show_spinner=False, persist="disk", max_entries=128)
def _cached_has_traffic(
    db_target: str,
    since_utc_iso: str,
    until_utc_iso: str,
    known_servers: tuple[str, ...],
    refresh_nonce: int = 0,
) -> bool:
    _ = refresh_nonce
    con = connect(db_target)
    try:
        return fetch_has_traffic(con, known_servers, since_utc_iso, until_utc_iso)
    finally:
        con.close()


@st.cache_data(show_spinner=False, persist="disk", max_entries=64)
def _cached_collector_status(
    db_target: str,
    known_servers: tuple[str, ...],
    refresh_nonce: int = 0,
) -> pd.DataFrame:
    _ = refresh_nonce
    con = connect(db_target)
    try:
        status_df = read_sql_query(
            """
            SELECT server_name, last_ok_at_utc, last_error_at_utc, last_error,
                   last_inserted_rows, last_fetched_lines
            FROM collector_status ORDER BY server_name
            """,
            con,
        )
    finally:
        con.close()
    if status_df.empty:
        return status_df
    return status_df[status_df["server_name"].isin(set(known_servers))].copy()


_GEO_ALL = "__all__"


def _country_table(df: pd.DataFrame, locale: str) -> pd.DataFrame:
    if df.empty:
        return df
    g = df.copy()
    if "visitors" in g.columns:
        if "unique_ips" not in g.columns:
            g["unique_ips"] = g["visitors"]
        g = g.drop(columns=["visitors"])
    total_req, total_vis = g["requests"].sum(), g["unique_ips"].sum()
    g["share_requests_pct"] = (g["requests"] / total_req * 100).round(1) if total_req else 0
    g["share_users_pct"] = (g["unique_ips"] / total_vis * 100).round(1) if total_vis else 0
    cols = [
        "country_code",
        "country_name",
        "requests",
        "unique_ips",
        "share_requests_pct",
        "share_users_pct",
    ]
    g = g[[c for c in cols if c in g.columns]]
    return g.rename(
        columns={
            "country_code": t("analytics.col_code", locale),
            "country_name": t("analytics.col_country", locale),
            "requests": t("analytics.col_requests", locale),
            "unique_ips": t("analytics.col_unique_ip", locale),
            "share_requests_pct": t("analytics.col_share_requests", locale),
            "share_users_pct": t("analytics.col_share_users", locale),
        }
    )


def _crosstab_table(df: pd.DataFrame, locale: str, *, entity_key: str) -> pd.DataFrame:
    if df.empty:
        return df
    g = df.copy()
    if "entity" not in g.columns:
        return pd.DataFrame()
    g["country_label"] = [
        f"{(n or c or '—')}" + (f" ({c})" if c and n and n != c else "")
        for n, c in zip(g.get("country"), g.get("country_code"))
    ]
    cols = ["entity", "country_label", "requests", "visitors"]
    g = g[[c for c in cols if c in g.columns]]
    return g.rename(
        columns={
            "entity": t(entity_key, locale),
            "country_label": t("analytics.col_country", locale),
            "requests": t("analytics.col_requests", locale),
            "visitors": t("analytics.col_unique_ip", locale),
        }
    )


def _visitors_table(df: pd.DataFrame, locale: str, limit: int = 500) -> pd.DataFrame:
    out = df.head(limit).copy()
    if "user_agent" not in out.columns:
        out["user_agent"] = None
    out["client"] = [
        client_label(ua, br) for ua, br in zip(out.get("user_agent"), out.get("ua_browser"))
    ]
    out["country"] = [
        f"{(n or '—')} ({(c or '—')})"
        for n, c in zip(out.get("country_name"), out.get("country_code"))
    ]
    return out.rename(
        columns={
            "ts_utc": t("analytics.col_time", locale),
            "host": t("analytics.col_host", locale),
            "server_ip": t("analytics.col_server_ip", locale),
            "remote_addr": t("analytics.col_visitor_ip", locale),
            "country": t("analytics.col_country", locale),
            "client": t("analytics.col_client", locale),
            "ua_os": t("analytics.col_os", locale),
            "ua_device": t("analytics.col_device", locale),
            "method": t("analytics.col_method", locale),
            "path": t("analytics.col_path", locale),
            "status": t("analytics.col_status", locale),
            "referer_domain": t("analytics.col_referer", locale),
        }
    )[
        [
            t("analytics.col_time", locale),
            t("analytics.col_host", locale),
            t("analytics.col_server_ip", locale),
            t("analytics.col_visitor_ip", locale),
            t("analytics.col_country", locale),
            t("analytics.col_client", locale),
            t("analytics.col_os", locale),
            t("analytics.col_device", locale),
            t("analytics.col_method", locale),
            t("analytics.col_path", locale),
            t("analytics.col_status", locale),
            t("analytics.col_referer", locale),
        ]
    ]


def _period_snapshot_key(period) -> str:
    """Stable semantic period key: relative ranges do not change every minute."""
    from skopos.period_picker import SESSION_CUSTOM_KEY, SESSION_PRESET_KEY

    if st.session_state.get(SESSION_CUSTOM_KEY):
        return f"custom:{period.since_iso()}:{period.until_iso()}"
    return f"preset:{st.session_state.get(SESSION_PRESET_KEY, '1d')}"


def _snapshot_signature(
    *, db_target: str, filters_key: str, period, dashboard: str
) -> str:
    return f"{db_target}|{filters_key}|{_period_snapshot_key(period)}|{dashboard}"


def _figure_payload(fig: go.Figure) -> dict:
    """Keep snapshot files independent from a live Plotly Figure instance."""
    return fig.to_dict()


def _render_summary_strip(ctx, payload: dict | None, *, cached: bool) -> None:
    if cached:
        st.caption(f"🗄️ {T(ctx, 'common.cached_snapshot')}")
    values = (payload or {}).get("kpis", {})
    verified = (payload or {}).get("verified_people")
    cols = st.columns(6)
    labels = (
        T(ctx, "analytics.requests"),
        T(ctx, "analytics.unique_ip"),
        T(ctx, "analytics.verified_visitors"),
        T(ctx, "analytics.countries"),
        T(ctx, "analytics.pages"),
        T(ctx, "analytics.hosts"),
    )
    raw_values = (
        values.get("requests"),
        values.get("unique_ips"),
        verified,
        values.get("countries"),
        values.get("pages"),
        values.get("hosts"),
    )
    for col, label, value in zip(cols, labels, raw_values):
        col.metric(label, "—" if value is None else f"{int(value):,}")


def _render_dashboard_preview(
    ctx,
    dashboard: str,
    payload: dict | None,
    *,
    server_ip_map: dict[str, str],
    refreshing: bool,
) -> None:
    """Paint cached charts or a full card skeleton before any fresh query."""
    if payload is None:
        card_count = {
            "overview": 7,
            "geo": 6,
            "audience": 5,
            "content": 4,
            "sources": 3,
            "journal": 1,
            "system": 1,
        }.get(dashboard, 4)
        cards = "".join(
            '<div class="skopos-dashboard-skeleton-card"><span></span><i></i><i></i></div>'
            for _ in range(card_count)
        )
        st.markdown(
            f'<div class="skopos-cache-note skopos-cache-note--loading">'
            f'⏳ {T(ctx, "common.first_dashboard_load")}</div>'
            f'<div class="skopos-dashboard-skeleton">{cards}</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f'<div class="skopos-cache-note">🗄️ '
        f'{T(ctx, "common.cached_snapshot_refreshing" if refreshing else "common.cached_snapshot")}'
        f'</div>',
        unsafe_allow_html=True,
    )
    metrics = list(payload.get("metrics") or [])
    if metrics:
        cols = st.columns(len(metrics))
        for col, item in zip(cols, metrics):
            label, value = item
            col.metric(str(label), str(value))
    for row_index, row in enumerate(payload.get("chart_rows") or []):
        figures = list(row or [])
        if len(figures) == 1:
            with st.container(border=True):
                plot(go.Figure(figures[0]), key=f"cached_{dashboard}_{row_index}_0")
            continue
        columns = st.columns(len(figures), gap="large")
        for column_index, (column, figure) in enumerate(zip(columns, figures)):
            with column:
                with st.container(border=True):
                    plot(
                        go.Figure(figure),
                        key=f"cached_{dashboard}_{row_index}_{column_index}",
                    )
    table = payload.get("table")
    if isinstance(table, pd.DataFrame):
        if dashboard == "journal" and not table.empty and "server_ip" in table.columns:
            table = table.copy()
            table["server_ip"] = table["server_ip"].fillna(
                table.get("server_name", pd.Series(index=table.index)).map(server_ip_map)
            )
            table = _visitors_table(table, ctx.locale, limit=1000)
        st.dataframe(table, use_container_width=True, hide_index=True, height=560)


_CONFIG_PATH_KEY = "analytics_config_path"


# ── Sidebar ──────────────────────────────────────────────────────────────────

config_path_input = st.sidebar.text_input(
    T(ctx, "settings.config_path"),
    value=st.session_state.get(_CONFIG_PATH_KEY, "./servers.yaml"),
    label_visibility="collapsed",
)
try:
    config_path = str(resolve_config_path(config_path_input))
except ValueError as exc:
    st.sidebar.error(str(exc))
    config_path = st.session_state.get(_CONFIG_PATH_KEY, "./servers.yaml")
st.session_state[_CONFIG_PATH_KEY] = config_path
if config_path != "./servers.yaml":
    cfg = load_config(config_path)
_start_collector_thread(config_path, _COLLECTOR_CACHE_VERSION)
known_servers = tuple(s.name for s in cfg.servers)
server_labels = {s.name: f"{s.name} ({s.ssh.host})" for s in cfg.servers}
server_ip_map = {s.name: s.ssh.host for s in cfg.servers}
db_target = resolve_db_target(cfg)

ensure_period_state()
period = get_active_period()
since_iso, until_iso = period.since_iso(), period.until_iso()

analytics_nonce = refresh_nonce("analytics")
analytics_refresh_requested = consume_refresh_request("analytics")
filter_period_key = (
    f"custom:{since_iso}:{until_iso}"
    if st.session_state.get(SESSION_CUSTOM_KEY)
    else f"relative:{int(period.duration.total_seconds())}"
)
filter_options_signature = (
    f"{db_target}|{filter_period_key}|{json.dumps(known_servers)}"
)
filter_options_snapshot = load_dashboard_snapshot(
    "analytics_filter_options",
    filter_options_signature,
    db_target=db_target,
)
if filter_options_snapshot is not None and not analytics_refresh_requested:
    host_opts = list(filter_options_snapshot.get("hosts") or [])
    country_opts = list(filter_options_snapshot.get("countries") or [])
else:
    host_opts, country_opts = _cached_filter_options(
        db_target,
        filter_period_key,
        known_servers,
        analytics_nonce,
        _since_utc_iso=since_iso,
        _until_utc_iso=until_iso,
    )
    save_dashboard_snapshot(
        "analytics_filter_options",
        filter_options_signature,
        {
            "hosts": host_opts,
            "countries": country_opts,
            "_analytics_nonce": analytics_nonce,
        },
        db_target=db_target,
    )
server_opts = sorted(known_servers)

with st.sidebar.expander(T(ctx, "analytics.collection")):
    if st.button(T(ctx, "settings.collect_now"), use_container_width=True):
        for r in collect_once(cfg):
            st.caption(f"{r.server_name}: +{r.inserted_rows}")
        st.cache_data.clear()
        st.rerun()
    if st.button(T(ctx, "settings.backfill"), use_container_width=True):
        with st.spinner(T(ctx, "analytics.updating")):
            st.success(backfill_all(db_target, mmdb_path=cfg.geoip_mmdb_path, asn_tsv_path=cfg.asn_tsv_path))
        st.cache_data.clear()
        st.rerun()

# ── Header + primary toolbar ─────────────────────────────────────────────────

hero(T(ctx, "analytics.title"), T(ctx, "analytics.subtitle"))
render_section_refresh("analytics", ctx.locale)

with st.container(border=True):
    render_period_toolbar(st, ctx.locale, key_suffix="_main", show_custom=True)
    st.markdown("---")
    render_analytics_filters(
        st,
        ctx.locale,
        key_suffix="_main",
        server_opts=server_opts,
        host_opts=host_opts,
        country_opts=country_opts,
        server_labels=server_labels,
        compact=False,
    )

# Spacer so the Running… status never sits on the Filters card border.
st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)

period = get_active_period()
since_iso, until_iso = period.since_iso(), period.until_iso()
filters = read_analytics_filters()
fk = _filters_key(filters)

dashboard_tabs = [
    ("overview", f"📊 {T(ctx, 'analytics.tab_overview')}"),
    ("geo", f"🌍 {T(ctx, 'analytics.tab_geo')}"),
    ("audience", f"👥 {T(ctx, 'analytics.tab_audience')}"),
    ("content", f"📄 {T(ctx, 'analytics.tab_content')}"),
    ("sources", f"🔗 {T(ctx, 'analytics.tab_sources')}"),
    ("journal", f"📋 {T(ctx, 'analytics.tab_journal')}"),
    ("system", f"⚙️ {T(ctx, 'analytics.tab_system')}"),
]
active_dashboard = render_lazy_tabs("analytics", dashboard_tabs)
dashboard_loading_message = (
    f"{T(ctx, 'common.loading_section')} · {dict(dashboard_tabs)[active_dashboard]}"
)

loc = ctx.locale
dashboard_refresh_nonce = render_section_refresh(
    f"analytics_{active_dashboard}", loc
)
dashboard_refresh_requested = consume_refresh_request(
    f"analytics_{active_dashboard}"
)
dashboard_signature = _snapshot_signature(
    db_target=db_target, filters_key=fk, period=period, dashboard=active_dashboard
)
summary_signature = _snapshot_signature(
    db_target=db_target, filters_key=fk, period=period, dashboard="summary"
)

# These placeholders are emitted before every query.  A last-good disk
# snapshot (or, on the very first visit, the complete card skeleton) is sent to
# the browser immediately.  Slow refresh work can no longer leave a blank well.
dashboard_loading_slot = st.empty()
summary_slot = st.empty()
dashboard_preview_slot = st.empty()
cached_summary = load_dashboard_snapshot(
    "analytics", summary_signature, db_target=db_target
)
cached_dashboard = load_dashboard_snapshot(
    "analytics", dashboard_signature, db_target=db_target
)
dashboard_needs_refresh = should_refresh_snapshot(
    cached_dashboard, dashboard_refresh_requested
)
summary_needs_refresh = should_refresh_snapshot(
    cached_summary, analytics_refresh_requested
)
# Never paint the KPI strip here. Streamlit 1.37 `empty().container()`
# appends on Refresh instead of replacing, so a cached strip plus the live
# strip below becomes two identical rows. Charts still come from the
# preview slot while queries run; KPIs are written once at the end.
with dashboard_preview_slot.container():
    _render_dashboard_preview(
        ctx,
        active_dashboard,
        cached_dashboard,
        server_ip_map=server_ip_map,
        refreshing=dashboard_needs_refresh,
    )


def _q(kind: str, nonce: int = 0, **kwargs) -> pd.DataFrame:
    return _cached_query_df(
        kind, db_target, since_iso, until_iso, known_servers, fk, filters, nonce, **kwargs
    )


def _commit_dashboard_snapshot(payload: dict) -> None:
    """Publish only a complete dashboard; a failed refresh keeps the old one."""
    payload["_analytics_nonce"] = analytics_nonce
    payload["_section_nonce"] = dashboard_refresh_nonce
    save_dashboard_snapshot(
        "analytics", dashboard_signature, payload, db_target=db_target
    )
    dashboard_preview_slot.empty()


if dashboard_needs_refresh and active_dashboard == "overview":
    ov_n = dashboard_refresh_nonce
    with st.container(border=True):
        gran = st.radio(
            T(ctx, "analytics.granularity"),
            ["hour", "day"],
            horizontal=True,
            format_func=lambda x: T(ctx, "analytics.by_hour") if x == "hour" else T(ctx, "analytics.by_day"),
        )
        with section_loading(
            dashboard_loading_message,
            6,
            complete_message=T(ctx, "common.section_ready"),
            slot=dashboard_loading_slot,
        ) as loading:
            timeline_df = _q("timeline", ov_n, granularity=gran)
            loading.advance(T(ctx, "analytics.granularity"))
            paths_df = _q("top", ov_n, column="path", top_n=12)
            loading.advance(T(ctx, "analytics.chart_top_pages"))
            hosts_df = _q("top", ov_n, column="host", top_n=12)
            loading.advance(T(ctx, "analytics.chart_top_addresses"))
            heat_df = _q("heatmap", ov_n)
            loading.advance(T(ctx, "analytics.requests"))
            status_df = _q("status", ov_n)
            loading.advance(T(ctx, "analytics.col_status"))
            countries_df = _cached_country_stats(
                db_target, since_iso, until_iso, known_servers, fk, filters, ov_n
            )
            loading.advance(T(ctx, "analytics.countries"))
        _commit_dashboard_snapshot(
            {
                "chart_rows": [
                    [_figure_payload(chart_traffic_timeline(timeline_df, granularity=gran, locale=loc))],
                    [
                        _figure_payload(chart_countries_donut(countries_df, metric="requests", locale=loc)),
                        _figure_payload(chart_countries_donut(countries_df, metric="visitors", locale=loc)),
                    ],
                    [
                        _figure_payload(chart_top_dimension(paths_df, "path", T(ctx, "analytics.chart_top_pages"), top_n=12)),
                        _figure_payload(chart_top_dimension(hosts_df, "host", T(ctx, "analytics.chart_top_addresses"), top_n=12)),
                    ],
                    [
                        _figure_payload(chart_heatmap_hourly(heat_df, locale=loc)),
                        _figure_payload(chart_status_codes(status_df, locale=loc)),
                    ],
                ]
            }
        )
        plot(chart_traffic_timeline(timeline_df, granularity=gran, locale=loc), key="ov_timeline")

    c1, c2 = st.columns(2, gap="large")
    with c1:
        with st.container(border=True):
            plot(chart_countries_donut(countries_df, metric="requests", locale=loc), key="ov_donut_req")
    with c2:
        with st.container(border=True):
            plot(chart_countries_donut(countries_df, metric="visitors", locale=loc), key="ov_donut_vis")

    c3, c4 = st.columns(2, gap="large")
    with c3:
        with st.container(border=True):
            plot(chart_top_dimension(paths_df, "path", T(ctx, "analytics.chart_top_pages"), top_n=12), key="ov_paths")
    with c4:
        with st.container(border=True):
            plot(chart_top_dimension(hosts_df, "host", T(ctx, "analytics.chart_top_addresses"), top_n=12), key="ov_hosts")

    c5, c6 = st.columns(2, gap="large")
    with c5:
        with st.container(border=True):
            plot(chart_heatmap_hourly(heat_df, locale=loc), key="ov_heat")
    with c6:
        with st.container(border=True):
            plot(chart_status_codes(status_df, locale=loc), key="ov_status")

elif dashboard_needs_refresh and active_dashboard == "geo":
    geo_n = dashboard_refresh_nonce
    with section_loading(
        dashboard_loading_message, 1,
        complete_message=T(ctx, "common.section_ready"), slot=dashboard_loading_slot
    ) as loading:
        geo_countries = _cached_country_stats(
            db_target, since_iso, until_iso, known_servers, fk, filters, geo_n
        )
        loading.advance(T(ctx, "analytics.countries"))
    geo_view_labels = {
        "overall": T(ctx, "analytics.geo_view_overall"),
        "servers": T(ctx, "analytics.geo_view_servers"),
        "sites": T(ctx, "analytics.geo_view_sites"),
    }
    with st.container(border=True):
        geo_view = st.radio(
            T(ctx, "analytics.geo_view"),
            ["overall", "servers", "sites"],
            horizontal=True,
            format_func=lambda v: geo_view_labels[v],
            key="geo_view_mode",
        )

    def _q_f(kind: str, nonce: int, flt: AnalyticsFilterState, **kwargs) -> pd.DataFrame:
        return _cached_query_df(
            kind, db_target, since_iso, until_iso, known_servers, _filters_key(flt), flt, nonce, **kwargs
        )

    if geo_view == "overall":
        with section_loading(
            dashboard_loading_message, 2,
            complete_message=T(ctx, "common.section_ready"), slot=dashboard_loading_slot
        ) as loading:
            geo_requests_timeline = _q("country_hourly", geo_n, metric="requests", top_n=6)
            loading.advance(T(ctx, "analytics.requests"))
            geo_visitors_timeline = _q("country_hourly", geo_n, metric="visitors", top_n=6)
            loading.advance(T(ctx, "analytics.unique_ip"))
        with st.container(border=True):
            geo_ctrl_left, geo_ctrl_right = st.columns([3, 1])
            with geo_ctrl_left:
                geo_map_metric = st.radio(
                    T(ctx, "analytics.on_map"),
                    ["requests", "visitors"],
                    horizontal=True,
                    format_func=lambda m: T(ctx, "analytics.map_requests") if m == "requests" else T(ctx, "analytics.map_visitors"),
                )
            with geo_ctrl_right:
                use_globe_3d = st.toggle(T(ctx, "analytics.map_view_3d"), value=False, key="geo_map_3d")
            if use_globe_3d:
                geo_fig = chart_countries_map(geo_countries, metric=geo_map_metric, locale=loc)
                geo_caption = T(ctx, "analytics.globe_hint")
            else:
                geo_fig = chart_countries_map_2d(geo_countries, metric=geo_map_metric, locale=loc)
                geo_caption = T(ctx, "analytics.map_2d_hint")
            _commit_dashboard_snapshot(
                {
                    "chart_rows": [
                        [_figure_payload(geo_fig)],
                        [
                            _figure_payload(chart_countries_bar(geo_countries, top_n=15, metric="requests", locale=loc)),
                            _figure_payload(chart_countries_donut(geo_countries, top_n=8, metric="requests", locale=loc)),
                        ],
                        [_figure_payload(chart_countries_timeline(geo_requests_timeline, metric="requests", locale=loc))],
                        [
                            _figure_payload(chart_countries_bar(geo_countries, top_n=15, metric="visitors", locale=loc)),
                            _figure_payload(chart_countries_donut(geo_countries, top_n=8, metric="visitors", locale=loc)),
                        ],
                        [_figure_payload(chart_countries_timeline(geo_visitors_timeline, metric="visitors", locale=loc))],
                    ],
                    "table": _country_table(geo_countries, loc),
                }
            )
            plot_fullscreen(
                geo_fig,
                key="geo_map",
                locale=loc,
                caption=geo_caption,
                expanded_height=960,
            )

        section_head(T(ctx, "analytics.section_requests_by_country"))
        g1, g2 = st.columns([3, 2], gap="large")
        with g1:
            with st.container(border=True):
                plot(chart_countries_bar(geo_countries, top_n=15, metric="requests", locale=loc), key="geo_bar_req")
        with g2:
            with st.container(border=True):
                plot(chart_countries_donut(geo_countries, top_n=8, metric="requests", locale=loc), key="geo_donut_req")
        with st.container(border=True):
            plot(chart_countries_timeline(geo_requests_timeline, metric="requests", locale=loc), key="geo_tl_req")

        section_head(T(ctx, "analytics.section_visitors_by_country"))
        g3, g4 = st.columns([3, 2], gap="large")
        with g3:
            with st.container(border=True):
                plot(chart_countries_bar(geo_countries, top_n=15, metric="visitors", locale=loc), key="geo_bar_vis")
        with g4:
            with st.container(border=True):
                plot(chart_countries_donut(geo_countries, top_n=8, metric="visitors", locale=loc), key="geo_donut_vis")
        with st.container(border=True):
            plot(chart_countries_timeline(geo_visitors_timeline, metric="visitors", locale=loc), key="geo_tl_vis")

        section_head(T(ctx, "analytics.section_summary_table"))
        ct = _country_table(geo_countries, loc)
        if not ct.empty:
            st.dataframe(ct, use_container_width=True, hide_index=True, height=400)
        else:
            st.info(T(ctx, "analytics.no_geo_data"))

    else:
        by_server = geo_view == "servers"
        dim = "server" if by_server else "host"
        title_key = "countries_by_server" if by_server else "countries_by_site"
        entity_i18n = "analytics.col_server" if by_server else "analytics.col_site"
        pick_label = T(ctx, "analytics.geo_pick_server" if by_server else "analytics.geo_pick_site")
        section_head(T(ctx, "analytics.section_by_server" if by_server else "analytics.section_by_site"))
        if by_server:
            entity_opts = list(filters.sel_servers) if filters.sel_servers else list(server_opts)
        else:
            entity_opts = list(filters.sel_hosts) if filters.sel_hosts else list(host_opts)
        pick_opts = [_GEO_ALL] + entity_opts
        ctrl_a, ctrl_b = st.columns([2, 3])
        with ctrl_a:
            geo_metric = st.radio(
                T(ctx, "analytics.on_map"),
                ["requests", "visitors"],
                horizontal=True,
                format_func=lambda m: T(ctx, "analytics.map_requests") if m == "requests" else T(ctx, "analytics.map_visitors"),
                key=f"geo_dim_metric_{dim}",
            )
        with ctrl_b:
            picked = st.selectbox(
                pick_label,
                pick_opts,
                format_func=lambda v: T(ctx, "analytics.geo_pick_all") if v == _GEO_ALL else v,
                key=f"geo_pick_{dim}",
            )

        if picked != _GEO_ALL:
            scoped = replace(
                filters,
                sel_servers=[picked] if by_server else filters.sel_servers,
                sel_hosts=[picked] if not by_server else filters.sel_hosts,
            )
            with section_loading(
                dashboard_loading_message, 2,
                complete_message=T(ctx, "common.section_ready"), slot=dashboard_loading_slot
            ) as loading:
                scoped_countries = _cached_country_stats(
                    db_target, since_iso, until_iso, known_servers, _filters_key(scoped), scoped, geo_n
                )
                loading.advance(T(ctx, "analytics.countries"))
                scoped_timeline = _q_f(
                    "country_hourly", geo_n, scoped, metric=geo_metric, top_n=6
                )
                loading.advance(T(ctx, "analytics.granularity"))
            scoped_requests = int(scoped_countries["requests"].sum()) if not scoped_countries.empty else 0
            scoped_visitors = int(scoped_countries["visitors"].sum()) if not scoped_countries.empty else 0
            scoped_country_count = 0 if scoped_countries.empty else len(scoped_countries)
            _commit_dashboard_snapshot(
                {
                    "metrics": [
                        [T(ctx, "analytics.requests"), f"{scoped_requests:,}"],
                        [T(ctx, "analytics.unique_ip"), f"{scoped_visitors:,}"],
                        [T(ctx, "analytics.countries"), f"{scoped_country_count:,}"],
                    ],
                    "chart_rows": [
                        [
                            _figure_payload(chart_countries_bar(scoped_countries, top_n=15, metric=geo_metric, locale=loc)),
                            _figure_payload(chart_countries_donut(scoped_countries, top_n=8, metric=geo_metric, locale=loc)),
                        ],
                        [_figure_payload(chart_countries_timeline(scoped_timeline, metric=geo_metric, locale=loc))],
                    ],
                    "table": _country_table(scoped_countries, loc),
                }
            )
            k1, k2, k3 = st.columns(3)
            k1.metric(T(ctx, "analytics.requests"), f"{int(scoped_countries['requests'].sum()) if not scoped_countries.empty else 0:,}")
            k2.metric(
                T(ctx, "analytics.unique_ip"),
                f"{int(scoped_countries['visitors'].sum()) if not scoped_countries.empty else 0:,}",
            )
            k3.metric(T(ctx, "analytics.countries"), f"{0 if scoped_countries.empty else len(scoped_countries):,}")
            b1, g2 = st.columns([3, 2], gap="large")
            with b1:
                with st.container(border=True):
                    plot(chart_countries_bar(scoped_countries, top_n=15, metric=geo_metric, locale=loc), key=f"geo_{dim}_bar")
            with g2:
                with st.container(border=True):
                    plot(chart_countries_donut(scoped_countries, top_n=8, metric=geo_metric, locale=loc), key=f"geo_{dim}_donut")
            with st.container(border=True):
                plot(
                    chart_countries_timeline(
                        scoped_timeline,
                        metric=geo_metric,
                        locale=loc,
                    ),
                    key=f"geo_{dim}_tl",
                )
            section_head(T(ctx, "analytics.section_summary_table"))
            ct = _country_table(scoped_countries, loc)
            if not ct.empty:
                st.dataframe(ct, use_container_width=True, hide_index=True, height=400)
            else:
                st.info(T(ctx, "analytics.no_geo_data"))
        else:
            with section_loading(
                dashboard_loading_message, 1,
                complete_message=T(ctx, "common.section_ready"), slot=dashboard_loading_slot
            ) as loading:
                stacked = _q(
                    f"{dim}_country" if dim == "host" else "server_country",
                    geo_n,
                    metric=geo_metric,
                )
                loading.advance(T(ctx, "analytics.countries"))
            _commit_dashboard_snapshot(
                {
                    "chart_rows": [[_figure_payload(chart_countries_by_category(
                        stacked,
                        metric=geo_metric,
                        locale=loc,
                        title_key=title_key,
                    ))]],
                    "table": _crosstab_table(stacked, loc, entity_key=entity_i18n),
                }
            )
            with st.container(border=True):
                plot(
                    chart_countries_by_category(
                        stacked,
                        metric=geo_metric,
                        locale=loc,
                        title_key=title_key,
                    ),
                    key=f"geo_{dim}_stack",
                )
            xt = _crosstab_table(stacked, loc, entity_key=entity_i18n)
            if not xt.empty:
                st.dataframe(xt, use_container_width=True, hide_index=True, height=420)
            else:
                st.info(T(ctx, "analytics.no_geo_data"))

elif dashboard_needs_refresh and active_dashboard == "audience":
    aud_n = dashboard_refresh_nonce
    with section_loading(
        dashboard_loading_message, 4,
        complete_message=T(ctx, "common.section_ready"), slot=dashboard_loading_slot
    ) as loading:
        browsers = _q("top", aud_n, column="ua_browser", top_n=20)
        loading.advance(T(ctx, "analytics.section_browsers"))
        operating_systems = _q("top", aud_n, column="ua_os", top_n=20)
        loading.advance(T(ctx, "analytics.section_os"))
        devices = _q("top", aud_n, column="ua_device", top_n=20)
        loading.advance(T(ctx, "analytics.section_devices"))
        ips = _q("top", aud_n, column="remote_addr", top_n=15)
        loading.advance(T(ctx, "analytics.section_ips"))
    _commit_dashboard_snapshot(
        {
            "chart_rows": [
                [_figure_payload(chart_donut_dimension(browsers, "ua_browser", T(ctx, "analytics.chart_browsers"), top_n=8, locale=loc))],
                [_figure_payload(chart_top_dimension(browsers, "ua_browser", T(ctx, "analytics.chart_top_clients"), top_n=12))],
                [_figure_payload(chart_donut_dimension(operating_systems, "ua_os", T(ctx, "analytics.chart_os"), top_n=8, locale=loc))],
                [_figure_payload(chart_donut_dimension(devices, "ua_device", T(ctx, "analytics.chart_devices"), top_n=6, locale=loc))],
                [_figure_payload(chart_top_dimension(ips, "remote_addr", T(ctx, "analytics.chart_top_ips"), top_n=15))],
            ]
        }
    )
    section_head(T(ctx, "analytics.section_browsers"))
    with st.container(border=True):
        plot(chart_donut_dimension(browsers, "ua_browser", T(ctx, "analytics.chart_browsers"), top_n=8, locale=loc), key="aud_browser")
    with st.container(border=True):
        plot(chart_top_dimension(browsers, "ua_browser", T(ctx, "analytics.chart_top_clients"), top_n=12), key="aud_browser_bar")

    section_head(T(ctx, "analytics.section_os"))
    with st.container(border=True):
        plot(chart_donut_dimension(operating_systems, "ua_os", T(ctx, "analytics.chart_os"), top_n=8, locale=loc), key="aud_os")

    section_head(T(ctx, "analytics.section_devices"))
    with st.container(border=True):
        plot(chart_donut_dimension(devices, "ua_device", T(ctx, "analytics.chart_devices"), top_n=6, locale=loc), key="aud_device")

    section_head(T(ctx, "analytics.section_ips"))
    with st.container(border=True):
        plot(chart_top_dimension(ips, "remote_addr", T(ctx, "analytics.chart_top_ips"), top_n=15), key="aud_ip")

elif dashboard_needs_refresh and active_dashboard == "content":
    cnt_n = dashboard_refresh_nonce
    with section_loading(
        dashboard_loading_message, 4,
        complete_message=T(ctx, "common.section_ready"), slot=dashboard_loading_slot
    ) as loading:
        content_tree = _q("treemap", cnt_n)
        loading.advance(T(ctx, "analytics.tab_content"))
        popular_paths = _q("top", cnt_n, column="path", top_n=15)
        loading.advance(T(ctx, "analytics.chart_popular_paths"))
        popular_hosts = _q("top", cnt_n, column="host", top_n=12)
        loading.advance(T(ctx, "analytics.chart_popular_hosts"))
        ecosystem = _q("top", cnt_n, column="ecosystem_segment", top_n=30)
        loading.advance(T(ctx, "analytics.hosts"))
    _commit_dashboard_snapshot(
        {
            "chart_rows": [
                [_figure_payload(chart_treemap_pages(content_tree, locale=loc))],
                [
                    _figure_payload(chart_top_dimension(popular_paths, "path", T(ctx, "analytics.chart_popular_paths"), top_n=15)),
                    _figure_payload(chart_top_dimension(popular_hosts, "host", T(ctx, "analytics.chart_popular_hosts"), top_n=12)),
                ],
                [_figure_payload(chart_ecosystem(ecosystem, locale=loc))],
            ]
        }
    )
    with st.container(border=True):
        plot(chart_treemap_pages(content_tree, locale=loc), key="cnt_tree")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        with st.container(border=True):
            plot(chart_top_dimension(popular_paths, "path", T(ctx, "analytics.chart_popular_paths"), top_n=15), key="cnt_paths")
    with c2:
        with st.container(border=True):
            plot(chart_top_dimension(popular_hosts, "host", T(ctx, "analytics.chart_popular_hosts"), top_n=12), key="cnt_hosts")
    with st.container(border=True):
        plot(chart_ecosystem(ecosystem, locale=loc), key="cnt_eco")

elif dashboard_needs_refresh and active_dashboard == "sources":
    src_n = dashboard_refresh_nonce
    with section_loading(
        dashboard_loading_message, 2,
        complete_message=T(ctx, "common.section_ready"), slot=dashboard_loading_slot
    ) as loading:
        referers = _q("top", src_n, column="referer_domain", top_n=15)
        loading.advance(T(ctx, "analytics.chart_referers"))
        direct, with_ref = _cached_source_stats(
            db_target, since_iso, until_iso, known_servers, fk, filters, src_n
        )
        loading.advance(T(ctx, "analytics.tab_sources"))
    _commit_dashboard_snapshot(
        {
            "metrics": [
                [T(ctx, "analytics.direct_visits"), f"{direct:,}"],
                [T(ctx, "analytics.with_referer"), f"{with_ref:,}"],
            ],
            "chart_rows": [[_figure_payload(chart_top_dimension(
                referers,
                "referer_domain",
                T(ctx, "analytics.chart_referers"),
                top_n=15,
            ))]],
        }
    )
    with st.container(border=True):
        plot(chart_top_dimension(referers, "referer_domain", T(ctx, "analytics.chart_referers"), top_n=15), key="src_ref")
    s1, s2 = st.columns(2)
    s1.metric(T(ctx, "analytics.direct_visits"), f"{direct:,}")
    s2.metric(T(ctx, "analytics.with_referer"), f"{with_ref:,}")

elif dashboard_needs_refresh and active_dashboard == "journal":
    vis_n = dashboard_refresh_nonce
    section_head(T(ctx, "analytics.section_visit_log"))
    with section_loading(
        dashboard_loading_message, 1,
        complete_message=T(ctx, "common.section_ready"), slot=dashboard_loading_slot
    ) as loading:
        journal = _q("journal", vis_n, limit=1000)
        loading.advance(T(ctx, "analytics.tab_journal"))
    _commit_dashboard_snapshot({"table": journal})
    if not journal.empty and "server_ip" in journal.columns:
        journal = journal.copy()
        journal["server_ip"] = journal["server_ip"].fillna(
            journal.get("server_name", pd.Series(index=journal.index)).map(server_ip_map)
        )
    st.dataframe(_visitors_table(journal, loc, limit=1000), use_container_width=True, hide_index=True, height=560)

elif dashboard_needs_refresh and active_dashboard == "system":
    sys_n = dashboard_refresh_nonce
    with section_loading(
        dashboard_loading_message, 1,
        complete_message=T(ctx, "common.section_ready"), slot=dashboard_loading_slot
    ) as loading:
        status_df = _cached_collector_status(db_target, known_servers, sys_n)
        loading.advance(T(ctx, "analytics.tab_system"))
    _commit_dashboard_snapshot({"table": status_df})
    if not status_df.empty:
        df = status_df.copy()
        ok_at = pd.to_datetime(df["last_ok_at_utc"], errors="coerce", utc=True)
        err_at = pd.to_datetime(df["last_error_at_utc"], errors="coerce", utc=True)
        recovered = ok_at.notna() & (err_at.isna() | (ok_at >= err_at))
        df.loc[recovered, "last_error"] = None
        st.dataframe(df, use_container_width=True, hide_index=True)
    for s in cfg.servers:
        try:
            sources = resolve_log_sources(s)
            st.code(f"{s.name}: " + ", ".join(x.id for x in sources))
        except Exception as e:
            st.error(f"{s.name}: {e}")

# Summary counters are deliberately resolved after the selected dashboard.
# They used to be the first blocking query, so one pathological aggregate left
# the entire analytics area blank.  A persisted summary paints above at once;
# only a missing snapshot or an explicit global refresh recomputes it here.
summary_payload = cached_summary
if summary_needs_refresh:
    with section_loading(
        dashboard_loading_message,
        4,
        complete_message=T(ctx, "common.section_ready"),
        slot=dashboard_loading_slot,
    ) as loading:
        kpis, snap = _cached_summary_metrics(
            db_target, since_iso, until_iso, known_servers, fk, filters, analytics_nonce
        )
        loading.advance(T(ctx, "analytics.requests"))
        verified_people = _cached_verified_visitors(
            db_target, since_iso, until_iso, known_servers, fk, filters, analytics_nonce
        )
        loading.advance(T(ctx, "analytics.verified_visitors"))
        first_ts = _cached_first_ts(
            db_target, since_iso, until_iso, known_servers, fk, filters, analytics_nonce
        )
        loading.advance(T(ctx, "common.period"))
        has_traffic = (
            True
            if kpis.requests
            else _cached_has_traffic(db_target, since_iso, until_iso, known_servers, analytics_nonce)
        )
        loading.advance(T(ctx, "analytics.collection"))
    summary_payload = {
        "kpis": {
            "requests": kpis.requests,
            "unique_ips": kpis.unique_ips,
            "countries": kpis.countries,
            "pages": kpis.pages,
            "hosts": kpis.hosts,
        },
        "verified_people": verified_people,
        "first_ts": first_ts,
        "has_traffic": has_traffic,
        "traffic": snap,
        "_analytics_nonce": analytics_nonce,
    }
    save_dashboard_snapshot(
        "analytics", summary_signature, summary_payload, db_target=db_target
    )

# One container() per run — do not empty()+container() here; that stacks
# a second identical KPI row after Refresh on Streamlit 1.37.
with summary_slot.container():
    _render_summary_strip(ctx, summary_payload, cached=False)
    first_ts = (summary_payload or {}).get("first_ts")
    if first_ts:
        try:
            _first_dt = pd.to_datetime(first_ts, utc=True)
            _since_dt = pd.to_datetime(since_iso, utc=True)
            _until_dt = pd.to_datetime(until_iso, utc=True)
            if _first_dt - _since_dt > pd.Timedelta(hours=12):
                _cov_days = max((_until_dt - _first_dt).days, 1)
                _sel_days = max((_until_dt - _since_dt).days, 1)
                st.caption(
                    "⚠️ "
                    + T(
                        ctx,
                        "analytics.data_coverage_notice",
                        date=_first_dt.strftime("%Y-%m-%d"),
                        covered=_cov_days,
                        selected=_sel_days,
                    )
                )
        except Exception:
            pass

summary_traffic = (summary_payload or {}).get("traffic") or {}
traffic = TrafficSnapshot(
    requests=int(summary_traffic.get("requests") or 0),
    unique_ips=int(summary_traffic.get("unique_ips") or 0),
    top_segment=summary_traffic.get("top_segment"),
    top_segment_share_pct=float(summary_traffic.get("top_segment_share_pct") or 0),
    error_rate_pct=float(summary_traffic.get("error_rate_pct") or 0),
    active_hosts=int(summary_traffic.get("active_hosts") or 0),
)

if summary_payload and int(summary_payload.get("kpis", {}).get("requests") or 0) == 0:
    render_analytics_onboarding(
        locale=ctx.locale,
        has_traffic=bool(summary_payload.get("has_traffic")),
        server_count=len(cfg.servers),
    )

# AI generation can involve a remote provider. It is deliberately below the
# selected dashboard so a slow provider never holds charts or navigation back.
render_ecosystem_briefing_card(
    config_path=config_path,
    agent_path="./agent.yaml",
    posture=ctx.posture,
    period=period,
    traffic_df=None,
    locale=ctx.locale,
    traffic_snapshot=traffic,
    lazy=True,
)

finalize_page(ctx)
