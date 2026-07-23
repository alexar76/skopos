from __future__ import annotations

import hashlib
import json
import threading

import pandas as pd
import streamlit as st

from skopos.config import load_app_env, load_config

load_app_env()

from skopos.app_shell import T, bootstrap_app, finalize_page, stop_page, prime_theme
from skopos.i18n import t
from skopos.backfill import backfill_all
from skopos.charts import (
    chart_countries_bar,
    chart_countries_by_host,
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
    fetch_countries_by_host,
    fetch_country_hourly,
    fetch_country_stats,
    fetch_filter_options,
    fetch_first_ts,
    fetch_has_traffic,
    fetch_heatmap,
    fetch_journal,
    fetch_kpis,
    fetch_source_stats,
    fetch_status_classes,
    fetch_timeline,
    fetch_top_dimension,
    fetch_traffic_snapshot,
    fetch_treemap,
    fetch_verified_visitors,
)
from skopos.period_picker import ensure_period_state, get_active_period, render_period_toolbar
from skopos.log_sources import resolve_log_sources
from skopos.traffic import client_label
from skopos.ui import hero, plot, plot_fullscreen, section_head
from skopos.ui_briefing import render_ecosystem_briefing_card
from skopos.ui_onboarding import render_analytics_onboarding
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


@st.cache_data(ttl=30)
def _cached_filter_options(
    db_target: str,
    since_utc_iso: str,
    until_utc_iso: str,
    known_servers: tuple[str, ...],
) -> tuple[list[str], list[str]]:
    con = connect(db_target)
    try:
        return fetch_filter_options(con, known_servers, since_utc_iso, until_utc_iso)
    finally:
        con.close()


@st.cache_data(ttl=30)
def _cached_kpis(
    db_target: str,
    since_utc_iso: str,
    until_utc_iso: str,
    known_servers: tuple[str, ...],
    filters_key: str,
    filters: AnalyticsFilterState,
):
    _ = filters_key
    con = connect(db_target)
    try:
        return fetch_kpis(con, known_servers, since_utc_iso, until_utc_iso, filters)
    finally:
        con.close()


@st.cache_data(ttl=30)
def _cached_verified_visitors(
    db_target: str,
    since_utc_iso: str,
    until_utc_iso: str,
    known_servers: tuple[str, ...],
    filters_key: str,
    filters: AnalyticsFilterState,
) -> int:
    _ = filters_key
    con = connect(db_target)
    try:
        return fetch_verified_visitors(con, known_servers, since_utc_iso, until_utc_iso, filters)
    finally:
        con.close()


@st.cache_data(ttl=300)
def _cached_first_ts(
    db_target: str,
    since_utc_iso: str,
    until_utc_iso: str,
    known_servers: tuple[str, ...],
    filters_key: str,
    filters: AnalyticsFilterState,
) -> str | None:
    _ = filters_key
    con = connect(db_target)
    try:
        return fetch_first_ts(con, known_servers, since_utc_iso, until_utc_iso, filters)
    finally:
        con.close()


@st.cache_data(ttl=30)
def _cached_country_stats(
    db_target: str,
    since_utc_iso: str,
    until_utc_iso: str,
    known_servers: tuple[str, ...],
    filters_key: str,
    filters: AnalyticsFilterState,
) -> pd.DataFrame:
    _ = filters_key
    con = connect(db_target)
    try:
        return fetch_country_stats(con, known_servers, since_utc_iso, until_utc_iso, filters)
    finally:
        con.close()


@st.cache_data(ttl=30)
def _cached_query_df(
    kind: str,
    db_target: str,
    since_utc_iso: str,
    until_utc_iso: str,
    known_servers: tuple[str, ...],
    filters_key: str,
    filters: AnalyticsFilterState,
    **kwargs,
) -> pd.DataFrame:
    _ = filters_key
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
            return fetch_countries_by_host(
                con, known_servers, since_utc_iso, until_utc_iso, filters,
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


@st.cache_data(ttl=30)
def _cached_source_stats(
    db_target: str,
    since_utc_iso: str,
    until_utc_iso: str,
    known_servers: tuple[str, ...],
    filters_key: str,
    filters: AnalyticsFilterState,
) -> tuple[int, int]:
    _ = filters_key
    con = connect(db_target)
    try:
        return fetch_source_stats(con, known_servers, since_utc_iso, until_utc_iso, filters)
    finally:
        con.close()


@st.cache_data(ttl=30)
def _cached_traffic_snapshot(
    db_target: str,
    since_utc_iso: str,
    until_utc_iso: str,
    known_servers: tuple[str, ...],
    filters_key: str,
    filters: AnalyticsFilterState,
) -> dict:
    _ = filters_key
    con = connect(db_target)
    try:
        return fetch_traffic_snapshot(con, known_servers, since_utc_iso, until_utc_iso, filters)
    finally:
        con.close()


@st.cache_data(ttl=30)
def _cached_has_traffic(
    db_target: str,
    since_utc_iso: str,
    until_utc_iso: str,
    known_servers: tuple[str, ...],
) -> bool:
    con = connect(db_target)
    try:
        return fetch_has_traffic(con, known_servers, since_utc_iso, until_utc_iso)
    finally:
        con.close()


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

host_opts, country_opts = _cached_filter_options(db_target, since_iso, until_iso, known_servers)
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

has_traffic = _cached_has_traffic(db_target, since_iso, until_iso, known_servers)
kpis = _cached_kpis(db_target, since_iso, until_iso, known_servers, fk, filters)
countries_df = _cached_country_stats(db_target, since_iso, until_iso, known_servers, fk, filters)
snap = _cached_traffic_snapshot(db_target, since_iso, until_iso, known_servers, fk, filters)
traffic = TrafficSnapshot(
    requests=int(snap["requests"]),
    unique_ips=int(snap["unique_ips"]),
    top_segment=snap.get("top_segment"),
    top_segment_share_pct=float(snap.get("top_segment_share_pct") or 0),
    error_rate_pct=float(snap.get("error_rate_pct") or 0),
    active_hosts=int(snap.get("active_hosts") or 0),
)

render_ecosystem_briefing_card(
    config_path=config_path,
    agent_path="./agent.yaml",
    posture=ctx.posture,
    period=period,
    traffic_df=None,
    locale=ctx.locale,
    traffic_snapshot=traffic,
)

if kpis.requests == 0:
    render_analytics_onboarding(
        locale=ctx.locale,
        has_traffic=has_traffic,
        server_count=len(cfg.servers),
    )
    stop_page(ctx)

verified_people = _cached_verified_visitors(db_target, since_iso, until_iso, known_servers, fk, filters)

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric(T(ctx, "analytics.requests"), f"{kpis.requests:,}")
m2.metric(T(ctx, "analytics.unique_ip"), f"{kpis.unique_ips:,}")
m3.metric(
    T(ctx, "analytics.verified_visitors"),
    f"{verified_people:,}",
    help=T(ctx, "analytics.verified_visitors_help"),
)
m4.metric(T(ctx, "analytics.countries"), f"{kpis.countries:,}")
m5.metric(T(ctx, "analytics.pages"), f"{kpis.pages:,}")
m6.metric(T(ctx, "analytics.hosts"), f"{kpis.hosts:,}")

# Honest coverage: a 30d picker over 6 days of ingested logs is not 30 days.
first_ts = _cached_first_ts(db_target, since_iso, until_iso, known_servers, fk, filters)
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

st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

# ── Tabs ─────────────────────────────────────────────────────────────────────

tab_overview, tab_geo, tab_audience, tab_content, tab_sources, tab_visitors, tab_system = st.tabs(
    [
        f"📊 {T(ctx, 'analytics.tab_overview')}",
        f"🌍 {T(ctx, 'analytics.tab_geo')}",
        f"👥 {T(ctx, 'analytics.tab_audience')}",
        f"📄 {T(ctx, 'analytics.tab_content')}",
        f"🔗 {T(ctx, 'analytics.tab_sources')}",
        f"📋 {T(ctx, 'analytics.tab_journal')}",
        f"⚙️ {T(ctx, 'analytics.tab_system')}",
    ]
)

loc = ctx.locale


def _q(kind: str, **kwargs) -> pd.DataFrame:
    return _cached_query_df(
        kind, db_target, since_iso, until_iso, known_servers, fk, filters, **kwargs
    )


with tab_overview:
    with st.container(border=True):
        gran = st.radio(
            T(ctx, "analytics.granularity"),
            ["hour", "day"],
            horizontal=True,
            format_func=lambda x: T(ctx, "analytics.by_hour") if x == "hour" else T(ctx, "analytics.by_day"),
        )
        plot(chart_traffic_timeline(_q("timeline", granularity=gran), granularity=gran, locale=loc), key="ov_timeline")

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
            plot(chart_top_dimension(_q("top", column="path", top_n=12), "path", T(ctx, "analytics.chart_top_pages"), top_n=12), key="ov_paths")
    with c4:
        with st.container(border=True):
            plot(chart_top_dimension(_q("top", column="host", top_n=12), "host", T(ctx, "analytics.chart_top_addresses"), top_n=12), key="ov_hosts")

    c5, c6 = st.columns(2, gap="large")
    with c5:
        with st.container(border=True):
            plot(chart_heatmap_hourly(_q("heatmap"), locale=loc), key="ov_heat")
    with c6:
        with st.container(border=True):
            plot(chart_status_codes(_q("status"), locale=loc), key="ov_status")

with tab_geo:
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
            geo_fig = chart_countries_map(countries_df, metric=geo_map_metric, locale=loc)
            geo_caption = T(ctx, "analytics.globe_hint")
        else:
            geo_fig = chart_countries_map_2d(countries_df, metric=geo_map_metric, locale=loc)
            geo_caption = T(ctx, "analytics.map_2d_hint")
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
            plot(chart_countries_bar(countries_df, top_n=15, metric="requests", locale=loc), key="geo_bar_req")
    with g2:
        with st.container(border=True):
            plot(chart_countries_donut(countries_df, top_n=8, metric="requests", locale=loc), key="geo_donut_req")
    with st.container(border=True):
        plot(chart_countries_timeline(_q("country_hourly", metric="requests", top_n=6), metric="requests", locale=loc), key="geo_tl_req")

    section_head(T(ctx, "analytics.section_visitors_by_country"))
    g3, g4 = st.columns([3, 2], gap="large")
    with g3:
        with st.container(border=True):
            plot(chart_countries_bar(countries_df, top_n=15, metric="visitors", locale=loc), key="geo_bar_vis")
    with g4:
        with st.container(border=True):
            plot(chart_countries_donut(countries_df, top_n=8, metric="visitors", locale=loc), key="geo_donut_vis")
    with st.container(border=True):
        plot(chart_countries_timeline(_q("country_hourly", metric="visitors", top_n=6), metric="visitors", locale=loc), key="geo_tl_vis")

    with st.container(border=True):
        plot(chart_countries_by_host(_q("host_country", metric="requests"), metric="requests", locale=loc), key="geo_host")

    section_head(T(ctx, "analytics.section_summary_table"))
    ct = _country_table(countries_df, loc)
    if not ct.empty:
        st.dataframe(ct, use_container_width=True, hide_index=True, height=400)
    else:
        st.info(T(ctx, "analytics.no_geo_data"))

with tab_audience:
    section_head(T(ctx, "analytics.section_browsers"))
    browsers = _q("top", column="ua_browser", top_n=20)
    with st.container(border=True):
        plot(chart_donut_dimension(browsers, "ua_browser", T(ctx, "analytics.chart_browsers"), top_n=8, locale=loc), key="aud_browser")
    with st.container(border=True):
        plot(chart_top_dimension(browsers, "ua_browser", T(ctx, "analytics.chart_top_clients"), top_n=12), key="aud_browser_bar")

    section_head(T(ctx, "analytics.section_os"))
    with st.container(border=True):
        plot(chart_donut_dimension(_q("top", column="ua_os", top_n=20), "ua_os", T(ctx, "analytics.chart_os"), top_n=8, locale=loc), key="aud_os")

    section_head(T(ctx, "analytics.section_devices"))
    with st.container(border=True):
        plot(chart_donut_dimension(_q("top", column="ua_device", top_n=20), "ua_device", T(ctx, "analytics.chart_devices"), top_n=6, locale=loc), key="aud_device")

    section_head(T(ctx, "analytics.section_ips"))
    with st.container(border=True):
        plot(chart_top_dimension(_q("top", column="remote_addr", top_n=15), "remote_addr", T(ctx, "analytics.chart_top_ips"), top_n=15), key="aud_ip")

with tab_content:
    with st.container(border=True):
        plot(chart_treemap_pages(_q("treemap"), locale=loc), key="cnt_tree")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        with st.container(border=True):
            plot(chart_top_dimension(_q("top", column="path", top_n=15), "path", T(ctx, "analytics.chart_popular_paths"), top_n=15), key="cnt_paths")
    with c2:
        with st.container(border=True):
            plot(chart_top_dimension(_q("top", column="host", top_n=12), "host", T(ctx, "analytics.chart_popular_hosts"), top_n=12), key="cnt_hosts")
    with st.container(border=True):
        plot(chart_ecosystem(_q("top", column="ecosystem_segment", top_n=30), locale=loc), key="cnt_eco")

with tab_sources:
    with st.container(border=True):
        plot(chart_top_dimension(_q("top", column="referer_domain", top_n=15), "referer_domain", T(ctx, "analytics.chart_referers"), top_n=15), key="src_ref")
    direct, with_ref = _cached_source_stats(db_target, since_iso, until_iso, known_servers, fk, filters)
    s1, s2 = st.columns(2)
    s1.metric(T(ctx, "analytics.direct_visits"), f"{direct:,}")
    s2.metric(T(ctx, "analytics.with_referer"), f"{with_ref:,}")

with tab_visitors:
    section_head(T(ctx, "analytics.section_visit_log"))
    journal = _q("journal", limit=1000)
    if not journal.empty and "server_ip" in journal.columns:
        journal = journal.copy()
        journal["server_ip"] = journal["server_ip"].fillna(
            journal.get("server_name", pd.Series(index=journal.index)).map(server_ip_map)
        )
    st.dataframe(_visitors_table(journal, loc, limit=1000), use_container_width=True, hide_index=True, height=560)

with tab_system:
    con = connect_for_config(cfg)
    known = {s.name for s in cfg.servers}
    status_df = read_sql_query(
        """
        SELECT server_name, last_ok_at_utc, last_error_at_utc, last_error,
               last_inserted_rows, last_fetched_lines
        FROM collector_status ORDER BY server_name
        """,
        con,
    )
    con.close()
    if not status_df.empty:
        df = status_df[status_df["server_name"].isin(known)].copy()
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

finalize_page(ctx)
