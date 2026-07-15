from __future__ import annotations

import threading

import pandas as pd
import streamlit as st

from skopos.config import load_app_env, load_config

load_app_env()

from skopos.app_shell import T, bootstrap_app, finalize_page, prime_theme
from skopos.i18n import t
from skopos.backfill import backfill_all, backfill_countries
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
from skopos.analytics_filters import read_analytics_filters, render_analytics_filters
from skopos.period_picker import ensure_period_state, get_active_period, render_period_toolbar
from skopos.geoip import is_private_ip
from skopos.log_sources import resolve_log_sources
from skopos.traffic import client_label, is_service_traffic
from skopos.ui import hero, plot, plot_fullscreen, section_head
from skopos.ui_briefing import render_ecosystem_briefing_card
from skopos.ui_onboarding import render_analytics_onboarding

from skopos.i18n import browser_page_title

st.set_page_config(
    page_title=browser_page_title("analytics.title"),
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="auto",
)
prime_theme()

BOT_SCAN_PATTERN = r"(?i)(/wp-|/wordpress|/xmlrpc\.php|/wp-admin|/wp-login\.php|\.php$|/phpmyadmin|/pma/|/cgi-bin/|/\.env$|/\.git/|/vendor/phpunit)"
_COLLECTOR_CACHE_VERSION = 6

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


@st.cache_data(ttl=30)
def _load_df(
    db_target: str,
    since_utc_iso: str,
    until_utc_iso: str,
    known_servers: tuple[str, ...],
) -> pd.DataFrame:
    con = connect(db_target)
    placeholders = ",".join("?" * len(known_servers)) if known_servers else "''"
    q = f"""
      SELECT
        server_name, server_ip, log_source, ecosystem_segment,
        ts_utc, remote_addr, host,
        country_code, country_name,
        ua_browser, ua_os, ua_device, ua_is_bot,
        referer_domain,
        method, path, status, bytes_sent, referer, user_agent
      FROM http_requests
      WHERE log_source LIKE 'file:%'
        AND server_name IN ({placeholders})
        AND (ts_utc IS NULL OR (ts_utc >= ? AND ts_utc <= ?))
      ORDER BY COALESCE(ts_utc, ingested_at_utc) DESC
      LIMIT 200000
    """
    params = list(known_servers) + [since_utc_iso, until_utc_iso]
    df = read_sql_query(q, con, params=params)
    con.close()
    if "ts_utc" in df.columns:
        df["ts_utc"] = pd.to_datetime(df["ts_utc"], errors="coerce", utc=True)
    return df


def _apply_filters(df, *, hide_bots, hide_service, visitors_only, sel_servers, sel_hosts, sel_countries, path_contains):
    fdf = df.copy()
    if fdf.empty or "path" not in fdf.columns:
        return fdf
    if visitors_only:
        fdf = fdf[~fdf["remote_addr"].fillna("").map(lambda ip: is_private_ip(str(ip)) if ip else True)]
    if hide_bots:
        fdf = fdf[~fdf["path"].fillna("").str.contains(BOT_SCAN_PATTERN, regex=True)]
        fdf = fdf[fdf["ua_is_bot"].fillna(0) != 1]
    if hide_service:
        mask = fdf.apply(
            lambda r: is_service_traffic(user_agent=r.get("user_agent"), path=r.get("path")), axis=1
        )
        fdf = fdf[~mask]
    if sel_servers:
        fdf = fdf[fdf["server_name"].isin(sel_servers)]
    if sel_hosts:
        fdf = fdf[fdf["host"].fillna("").isin(sel_hosts)]
    if sel_countries:
        fdf = fdf[fdf["country_code"].isin(sel_countries)]
    if path_contains.strip():
        fdf = fdf[fdf["path"].fillna("").str.contains(path_contains.strip(), case=False, regex=False)]
    return fdf


def _country_table(df: pd.DataFrame, locale: str) -> pd.DataFrame:
    base = df[df["country_code"].notna() & (df["country_code"] != "INT")].copy()
    if base.empty:
        return base
    g = (
        base.groupby("country_code", dropna=True)
        .agg(
            country_name=("country_name", lambda s: next((x for x in s if x), None)),
            requests=("remote_addr", "count"),
            unique_ips=("remote_addr", "nunique"),
        )
        .reset_index()
        .sort_values("requests", ascending=False)
    )
    if g.empty:
        return g
    total_req, total_vis = g["requests"].sum(), g["unique_ips"].sum()
    g["share_requests_pct"] = (g["requests"] / total_req * 100).round(1)
    g["share_users_pct"] = (g["unique_ips"] / total_vis * 100).round(1)
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
    out["client"] = out.apply(lambda r: client_label(r.get("user_agent"), r.get("ua_browser")), axis=1)
    out["country"] = out.apply(
        lambda r: f"{r['country_name'] or '—'} ({r['country_code'] or '—'})", axis=1
    )
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

ensure_period_state()
period = get_active_period()

df_raw = _load_df(resolve_db_target(cfg), period.since_iso(), period.until_iso(), known_servers)
if "server_ip" in df_raw.columns:
    df_raw["server_ip"] = df_raw["server_ip"].fillna(df_raw["server_name"].map(server_ip_map))

server_opts = sorted(known_servers)
host_opts = sorted([h for h in df_raw["host"].dropna().unique().tolist() if h])
country_opts = sorted([c for c in df_raw["country_code"].dropna().unique().tolist() if c and c != "INT"])

# Sidebar: data collection only (period + filters live in main toolbar)
with st.sidebar.expander(T(ctx, "analytics.collection")):
    if st.button(T(ctx, "settings.collect_now"), use_container_width=True):
        for r in collect_once(cfg):
            st.caption(f"{r.server_name}: +{r.inserted_rows}")
        st.cache_data.clear()
        st.rerun()
    if st.button(T(ctx, "settings.backfill"), use_container_width=True):
        with st.spinner(T(ctx, "analytics.updating")):
            st.success(backfill_all(resolve_db_target(cfg), mmdb_path=cfg.geoip_mmdb_path))
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

period = get_active_period()
df_raw = _load_df(resolve_db_target(cfg), period.since_iso(), period.until_iso(), known_servers)
if "server_ip" in df_raw.columns:
    df_raw["server_ip"] = df_raw["server_ip"].fillna(df_raw["server_name"].map(server_ip_map))

filters = read_analytics_filters()
fdf = _apply_filters(
    df_raw,
    hide_bots=filters.hide_bots,
    hide_service=filters.hide_service,
    visitors_only=filters.visitors_only,
    sel_servers=filters.sel_servers,
    sel_hosts=filters.sel_hosts,
    sel_countries=filters.sel_countries,
    path_contains=filters.path_contains,
)

render_ecosystem_briefing_card(
    config_path=config_path,
    agent_path="./agent.yaml",
    posture=ctx.posture,
    period=period,
    traffic_df=df_raw,
    locale=ctx.locale,
)

if fdf.empty:
    render_analytics_onboarding(
        locale=ctx.locale,
        has_traffic=not df_raw.empty,
        server_count=len(cfg.servers),
    )
    st.stop()

n_countries = fdf[fdf["country_code"].notna() & (fdf["country_code"] != "INT")]["country_code"].nunique()
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric(T(ctx, "analytics.requests"), f"{len(fdf):,}")
m2.metric(T(ctx, "analytics.unique_ip"), f"{fdf['remote_addr'].nunique():,}")
m3.metric(T(ctx, "analytics.countries"), f"{n_countries:,}")
m4.metric(T(ctx, "analytics.pages"), f"{fdf['path'].nunique():,}")
m5.metric(T(ctx, "analytics.hosts"), f"{fdf['host'].nunique():,}")

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

with tab_overview:
    with st.container(border=True):
        gran = st.radio(
            T(ctx, "analytics.granularity"),
            ["hour", "day"],
            horizontal=True,
            format_func=lambda x: T(ctx, "analytics.by_hour") if x == "hour" else T(ctx, "analytics.by_day"),
        )
        plot(chart_traffic_timeline(fdf, granularity=gran, locale=loc), key="ov_timeline")

    c1, c2 = st.columns(2, gap="large")
    with c1:
        with st.container(border=True):
            plot(chart_countries_donut(fdf, metric="requests", locale=loc), key="ov_donut_req")
    with c2:
        with st.container(border=True):
            plot(chart_countries_donut(fdf, metric="visitors", locale=loc), key="ov_donut_vis")

    c3, c4 = st.columns(2, gap="large")
    with c3:
        with st.container(border=True):
            plot(chart_top_dimension(fdf, "path", T(ctx, "analytics.chart_top_pages"), top_n=12), key="ov_paths")
    with c4:
        with st.container(border=True):
            plot(chart_top_dimension(fdf, "host", T(ctx, "analytics.chart_top_addresses"), top_n=12), key="ov_hosts")

    c5, c6 = st.columns(2, gap="large")
    with c5:
        with st.container(border=True):
            plot(chart_heatmap_hourly(fdf, locale=loc), key="ov_heat")
    with c6:
        with st.container(border=True):
            plot(chart_status_codes(fdf, locale=loc), key="ov_status")

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
            geo_fig = chart_countries_map(fdf, metric=geo_map_metric, locale=loc)
            geo_caption = T(ctx, "analytics.globe_hint")
        else:
            geo_fig = chart_countries_map_2d(fdf, metric=geo_map_metric, locale=loc)
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
            plot(chart_countries_bar(fdf, top_n=15, metric="requests", locale=loc), key="geo_bar_req")
    with g2:
        with st.container(border=True):
            plot(chart_countries_donut(fdf, top_n=8, metric="requests", locale=loc), key="geo_donut_req")
    with st.container(border=True):
        plot(chart_countries_timeline(fdf, metric="requests", locale=loc), key="geo_tl_req")

    section_head(T(ctx, "analytics.section_visitors_by_country"))
    g3, g4 = st.columns([3, 2], gap="large")
    with g3:
        with st.container(border=True):
            plot(chart_countries_bar(fdf, top_n=15, metric="visitors", locale=loc), key="geo_bar_vis")
    with g4:
        with st.container(border=True):
            plot(chart_countries_donut(fdf, top_n=8, metric="visitors", locale=loc), key="geo_donut_vis")
    with st.container(border=True):
        plot(chart_countries_timeline(fdf, metric="visitors", locale=loc), key="geo_tl_vis")

    with st.container(border=True):
        plot(chart_countries_by_host(fdf, metric="requests", locale=loc), key="geo_host")

    section_head(T(ctx, "analytics.section_summary_table"))
    ct = _country_table(fdf, loc)
    if not ct.empty:
        st.dataframe(ct, use_container_width=True, hide_index=True, height=400)
    else:
        st.info(T(ctx, "analytics.no_geo_data"))

with tab_audience:
    section_head(T(ctx, "analytics.section_browsers"))
    with st.container(border=True):
        plot(chart_donut_dimension(fdf, "ua_browser", T(ctx, "analytics.chart_browsers"), top_n=8, locale=loc), key="aud_browser")
    with st.container(border=True):
        plot(chart_top_dimension(fdf, "ua_browser", T(ctx, "analytics.chart_top_clients"), top_n=12), key="aud_browser_bar")

    section_head(T(ctx, "analytics.section_os"))
    with st.container(border=True):
        plot(chart_donut_dimension(fdf, "ua_os", T(ctx, "analytics.chart_os"), top_n=8, locale=loc), key="aud_os")

    section_head(T(ctx, "analytics.section_devices"))
    with st.container(border=True):
        plot(chart_donut_dimension(fdf, "ua_device", T(ctx, "analytics.chart_devices"), top_n=6, locale=loc), key="aud_device")

    section_head(T(ctx, "analytics.section_ips"))
    with st.container(border=True):
        plot(chart_top_dimension(fdf, "remote_addr", T(ctx, "analytics.chart_top_ips"), top_n=15), key="aud_ip")

with tab_content:
    with st.container(border=True):
        plot(chart_treemap_pages(fdf, locale=loc), key="cnt_tree")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        with st.container(border=True):
            plot(chart_top_dimension(fdf, "path", T(ctx, "analytics.chart_popular_paths"), top_n=15), key="cnt_paths")
    with c2:
        with st.container(border=True):
            plot(chart_top_dimension(fdf, "host", T(ctx, "analytics.chart_popular_hosts"), top_n=12), key="cnt_hosts")
    with st.container(border=True):
        plot(chart_ecosystem(fdf, locale=loc), key="cnt_eco")

with tab_sources:
    with st.container(border=True):
        plot(chart_top_dimension(fdf, "referer_domain", T(ctx, "analytics.chart_referers"), top_n=15), key="src_ref")
    ref_df = fdf[fdf["referer_domain"].notna()]
    s1, s2 = st.columns(2)
    s1.metric(T(ctx, "analytics.direct_visits"), f"{len(fdf) - len(ref_df):,}")
    s2.metric(T(ctx, "analytics.with_referer"), f"{len(ref_df):,}")

with tab_visitors:
    section_head(T(ctx, "analytics.section_visit_log"))
    st.dataframe(_visitors_table(fdf, loc, limit=1000), use_container_width=True, hide_index=True, height=560)

with tab_system:
    con = connect_for_config(cfg)
    known = {s.name for s in cfg.servers}
    status_df = pd.read_sql_query(
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
        recovered = df["last_ok_at_utc"].notna() & (
            df["last_error_at_utc"].isna()
            | (df["last_ok_at_utc"] >= df["last_error_at_utc"])
        )
        df.loc[recovered, "last_error"] = None
        st.dataframe(df, use_container_width=True, hide_index=True)
    for s in cfg.servers:
        try:
            sources = resolve_log_sources(s)
            st.code(f"{s.name}: " + ", ".join(x.id for x in sources))
        except Exception as e:
            st.error(f"{s.name}: {e}")

finalize_page(ctx)
