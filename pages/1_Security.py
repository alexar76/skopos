"""Security Center — monitoring, audit, 3D threats, AI agent."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from skopos.config import load_app_env

load_app_env()

from skopos.agent import LLMProviderError, load_agent_config, run_security_analysis
from skopos.agent.config import get_provider
from skopos.app_shell import T, bootstrap_app, finalize_page, stop_page, prime_theme
from skopos.db import connect, connect_for_config, init_db
from skopos.db_dialect import resolve_db_target
from skopos.security.charts import (
    chart_disk_usage,
    chart_findings_bar,
    chart_multi_server_overview,
    chart_network_io,
    chart_port_matrix,
    chart_threat_3d,
)
from skopos.security.knock_charts import (
    chart_knocks_actor_types,
    chart_knocks_actors,
    chart_knocks_by_port,
    chart_knocks_countries,
    chart_knocks_heatmap,
    chart_knocks_timeline,
)
from skopos.security.collector import scan_all_servers
from skopos.security.store import (
    knock_summary_by_actor,
    latest_findings_by_server,
    latest_snapshots,
    load_knock_events,
    load_snapshot_payload,
    scan_history_summary,
)
from skopos.ui import display_dataframe, display_labeled_df, hero, plot, plot_fullscreen, section_head
from skopos.ui_onboarding import render_security_onboarding
from skopos.ui_security import plot_resource_gauges, render_posture_panel
from skopos.ui_security_report import render_security_report_section

from skopos.i18n import browser_page_title

st.set_page_config(
    page_title=browser_page_title("security.title"),
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="auto",
)
prime_theme()

if "agent_report" not in st.session_state:
    st.session_state.agent_report = ""

@st.cache_data(ttl=15)
def _load_security(db_target: str, server_names: tuple[str, ...]) -> tuple[list[dict], dict[str, list[dict]]]:
    con = connect(db_target)
    init_db(con)
    snaps = latest_snapshots(con, list(server_names))
    findings_map: dict[str, list[dict]] = {}
    enriched: list[dict] = []
    for row in snaps:
        payload = load_snapshot_payload(row).to_dict()
        name = row["server_name"]
        findings = latest_findings_by_server(con, name)
        findings_map[name] = findings
        enriched.append(
            {
                "server_name": name,
                "host": row["host"],
                "scanned_at_utc": row["scanned_at_utc"],
                "snapshot_id": row["id"],
                "payload": payload,
            }
        )
    con.close()
    return enriched, findings_map


@st.cache_data(ttl=15)
def _load_knocks(db_target: str, server_names: tuple[str, ...], hours: int = 168) -> tuple[pd.DataFrame, pd.DataFrame]:
    con = connect(db_target)
    init_db(con)
    names = list(server_names) if server_names else None
    events = load_knock_events(con, names, hours=hours)
    summary = knock_summary_by_actor(con, names, hours=hours)
    con.close()
    return pd.DataFrame(events), pd.DataFrame(summary)


# ── Sidebar ──────────────────────────────────────────────────────────────────

from skopos.i18n import active_locale, ensure_locale_state, t as translate

ensure_locale_state()

try:
    ctx = bootstrap_app("./servers.yaml", st.session_state.get("security_agent_path", "./agent.yaml"))
    cfg = ctx.cfg
    agent_path = st.sidebar.text_input(
        translate("security.agent_config_path", active_locale()),
        value=st.session_state.get("security_agent_path", "./agent.yaml"),
        label_visibility="collapsed",
    )
    st.session_state["security_agent_path"] = agent_path
    agent_cfg = load_agent_config(agent_path)
except Exception as e:
    st.exception(e)
    st.stop()

known = tuple(s.name for s in cfg.servers)
server_labels = {s.name: f"{s.name} ({s.ssh.host})" for s in cfg.servers}

sel_server = st.sidebar.selectbox(
    T(ctx, "common.all_servers"),
    ["__all__"] + list(known),
    format_func=lambda x: T(ctx, "common.all_servers") if x == "__all__" else server_labels.get(x, x),
    key="security_sel_server",
)

_agent_server = None if sel_server == "__all__" else sel_server
st.session_state._skopos_agent_server_name = _agent_server

if st.sidebar.button(T(ctx, "security.scan_all"), use_container_width=True, type="primary"):
    with st.spinner(T(ctx, "common.scanning")):
        results = scan_all_servers(cfg)
    for r in results:
        if r.ok:
            st.sidebar.success(f"{r.server_name}: {r.findings_count} {T(ctx, 'security.findings').lower()}")
        else:
            st.sidebar.error(f"{r.server_name}: {r.error}")
    st.cache_data.clear()
    st.rerun()

# ── Header ───────────────────────────────────────────────────────────────────

hero(T(ctx,"security.title"), T(ctx,"security.subtitle"))

_db = resolve_db_target(cfg)
snapshots, findings_map = _load_security(_db, known)

if sel_server != "__all__":
    snapshots = [s for s in snapshots if s["server_name"] == sel_server]
    findings_map = {k: v for k, v in findings_map.items() if k == sel_server}

if not snapshots:
    render_security_onboarding(
        locale=ctx.locale,
        has_scan=False,
        server_count=len(cfg.servers),
    )
    stop_page(ctx, server_name=_agent_server)

# KPI row
total_crit = sum(1 for fs in findings_map.values() for f in fs if f.get("severity") == "critical")
total_high = sum(1 for fs in findings_map.values() for f in fs if f.get("severity") == "high")
total_public = sum(
    len([p for p in s["payload"].get("ports", []) if p.get("bind_scope") == "public"]) for s in snapshots
)
m1, m2, m3, m4 = st.columns(4)
m1.metric(T(ctx,"security.findings"), sum(len(v) for v in findings_map.values()))
m2.metric(T(ctx,"security.severity_critical"), total_crit)
m3.metric(T(ctx,"security.severity_high"), total_high)
m4.metric(T(ctx,"security.public_ports"), total_public)

st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

tab_score, tab_report, tab_ov, tab_ports, tab_knocks, tab_res, tab_audit, tab_3d, tab_agent = st.tabs(
    [
        T(ctx, "security.tab_score"),
        T(ctx, "security.tab_report"),
        T(ctx, "security.tab_overview"),
        T(ctx, "security.tab_ports"),
        T(ctx, "security.tab_knocks"),
        T(ctx, "security.tab_resources"),
        T(ctx, "security.tab_audit"),
        T(ctx, "security.tab_3d"),
        T(ctx, "security.tab_agent"),
    ]
)

with tab_score:
    render_posture_panel(ctx.posture, locale=ctx.locale)

with tab_report:
    target = None if sel_server == "__all__" else sel_server
    knock_names = list(known) if sel_server == "__all__" else [sel_server]
    con = connect_for_config(cfg)
    init_db(con)
    hist_summary = scan_history_summary(con, knock_names)
    knock_sum = knock_summary_by_actor(con, knock_names, hours=168)
    con.close()
    render_security_report_section(
        cfg=cfg,
        agent_path=agent_path,
        agent_cfg=agent_cfg,
        posture=ctx.posture,
        findings_map=findings_map,
        snapshots=snapshots,
        knocks_summary=knock_sum,
        scan_history_summary=hist_summary,
        locale=ctx.locale,
        server_filter=target,
    )

with tab_ov:
    with st.container(border=True):
        plot(chart_multi_server_overview(snapshots, findings_map), key="sec_fleet")
    for snap in snapshots:
        p = snap["payload"]
        with st.expander(f"{snap['server_name']} ({snap['host']}) — {snap['scanned_at_utc']}", expanded=len(snapshots) == 1):
            plot_resource_gauges(p, key_prefix=f"sec_gauge_{snap['server_name']}", locale=ctx.locale)
            plot(chart_findings_bar(findings_map.get(snap["server_name"], [])), key=f"sec_fbar_{snap['server_name']}")
            st.caption(p.get("uptime") or "")
            st.code((p.get("kernel") or "")[:200])

with tab_ports:
    for snap in snapshots:
        p = snap["payload"]
        section_head(f"{T(ctx,'security.port_map')} — {snap['server_name']}")
        with st.container(border=True):
            plot(chart_port_matrix(p.get("ports") or []), key=f"sec_ports_{snap['server_name']}")
        ports_df = pd.DataFrame(p.get("ports") or [])
        if not ports_df.empty:
            ports_df["exposure"] = ports_df["bind_scope"].map(
                {
                    "public": T(ctx, "security.exposure_open"),
                    "localhost": T(ctx, "security.exposure_localhost"),
                    "other": T(ctx, "security.exposure_other"),
                }
            )
            display_dataframe(
                ports_df[["proto", "port", "address", "bind_scope", "exposure", "process"]],
                use_container_width=True,
                hide_index=True,
            )
        fw = p.get("firewall_status")
        if fw:
            section_head(T(ctx,"security.firewall"))
            st.code(fw[:1500])

with tab_knocks:
    section_head(T(ctx,"security.knocks_title"))
    st.caption(T(ctx,"security.knocks_subtitle"))
    knock_servers = list(known) if sel_server == "__all__" else [sel_server]
    knock_df, actor_df = _load_knocks(_db, tuple(knock_servers))

    if knock_df.empty:
        st.info(T(ctx,"security.knocks_no_data"))
    else:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(T(ctx,"security.knocks_events"), f"{len(knock_df):,}")
        k2.metric(T(ctx,"security.knocks_unique_ips"), f"{knock_df['remote_addr'].nunique():,}")
        top_port = (
            knock_df["dest_port"].mode().iloc[0]
            if knock_df["dest_port"].notna().any()
            else "—"
        )
        k3.metric(T(ctx,"security.knocks_top_port"), str(top_port))
        high_threat = len(actor_df[actor_df["threat_score"] >= 70]) if not actor_df.empty else 0
        k4.metric(T(ctx,"security.knocks_threat") + " ≥70", high_threat)

        c1, c2 = st.columns(2, gap="large")
        with c1:
            with st.container(border=True):
                plot(chart_knocks_actors(actor_df), key="knock_actors")
        with c2:
            with st.container(border=True):
                plot(chart_knocks_actor_types(actor_df), key="knock_types")

        c3, c4 = st.columns(2, gap="large")
        with c3:
            with st.container(border=True):
                plot(chart_knocks_by_port(knock_df), key="knock_ports")
        with c4:
            with st.container(border=True):
                plot(chart_knocks_countries(actor_df), key="knock_countries")

        with st.container(border=True):
            plot(chart_knocks_timeline(knock_df), key="knock_tl")
        with st.container(border=True):
            plot(chart_knocks_heatmap(knock_df), key="knock_heat")

        section_head(T(ctx,"security.knocks_actor_table"))
        if not actor_df.empty:
            show = actor_df.copy()
            show["country"] = show.apply(
                lambda r: f"{r.get('country_name') or '—'} ({r.get('country_code') or '—'})", axis=1
            )
            display_labeled_df(
                show,
                [
                    ("remote_addr", "security.knock_col_ip", "text"),
                    ("country", "analytics.col_country", "text"),
                    ("actor_class", "security.knocks_classification", "text"),
                    ("actor_label", "security.knock_profile", "text"),
                    ("threat_score", "security.knocks_threat", "number"),
                    ("hits", "security.knocks_events", "number"),
                    ("ports_targeted", "security.knocks_ports_hit", "number"),
                    ("port_list", "security.knock_ports_col", "text"),
                    ("servers", "security.knock_servers_col", "text"),
                ],
                ctx,
                use_container_width=True,
                hide_index=True,
                height=420,
            )

        section_head(T(ctx,"security.knocks_event_log"))
        log = knock_df.head(300).copy()
        log["country"] = log.apply(
            lambda r: f"{r.get('country_name') or '—'} ({r.get('country_code') or '—'})", axis=1
        )
        display_labeled_df(
            log,
            [
                ("ts_utc", "security.knock_col_time", "datetime"),
                ("server_name", "security.knock_servers_col", "text"),
                ("remote_addr", "security.knock_col_ip", "text"),
                ("country", "analytics.col_country", "text"),
                ("dest_port", "security.knock_col_port", "number"),
                ("event_type", "security.knock_col_type", "text"),
                ("actor_class", "security.knocks_classification", "text"),
                ("actor_label", "security.knock_profile", "text"),
                ("source_log", "security.knock_col_source", "text"),
            ],
            ctx,
            use_container_width=True,
            hide_index=True,
            height=400,
        )

with tab_res:
    for snap in snapshots:
        p = snap["payload"]
        section_head(f"{snap['server_name']} — {T(ctx,'security.tab_resources')}")
        plot_resource_gauges(p, key_prefix=f"sec_rg_{snap['server_name']}", locale=ctx.locale)
        with st.container(border=True):
            plot(chart_network_io(p), key=f"sec_net_{snap['server_name']}")
        with st.container(border=True):
            plot(chart_disk_usage(p.get("disks") or []), key=f"sec_disk_{snap['server_name']}")

with tab_audit:
    for snap in snapshots:
        findings = findings_map.get(snap["server_name"], [])
        section_head(f"{snap['server_name']} — {T(ctx,'security.tab_audit')}")
        if not findings:
            st.success(T(ctx, "security.audit_clean"))
            continue
        for f in findings:
            sev = f.get("severity", "info")
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "🟢"}.get(sev, "⚪")
            with st.container(border=True):
                st.markdown(f"**{icon} [{sev.upper()}] {f.get('title')}**")
                st.caption(f.get("detail"))
                if f.get("recommendation"):
                    st.info(f"**{T(ctx,'security.recommendation')}:** {f['recommendation']}")
        if snap["payload"].get("failed_logins"):
            section_head(T(ctx, "security.auth_log_sample"))
            st.code("\n".join(snap["payload"]["failed_logins"]))

with tab_3d:
    for snap in snapshots:
        section_head(f"🌐 3D — {snap['server_name']}")
        with st.container(border=True):
            plot_fullscreen(
                chart_threat_3d(
                    snap["payload"],
                    findings_map.get(snap["server_name"], []),
                    title=T(ctx,"security.tab_3d"),
                ),
                key=f"sec_3d_{snap['server_name']}",
                locale=ctx.locale,
                caption=T(ctx, "security.threat_3d_caption"),
                expanded_height=940,
            )

with tab_agent:
    st.info(T(ctx, "security.agent_tab_hint"))
    prov_ids = list(agent_cfg.providers.keys())
    prov_id = st.selectbox(T(ctx, "security.agent_provider"), prov_ids, index=prov_ids.index(agent_cfg.default_provider))
    prov = get_provider(agent_cfg, prov_id)
    if prov.kind in ("openai_compatible", "anthropic_compatible") and not prov.api_key:
        env = prov.api_key_env or "API_KEY"
        st.warning(T(ctx, "security.agent_no_key", env=env))

    target = None if sel_server == "__all__" else sel_server

    if st.button(T(ctx, "security.agent_analyze"), type="primary", use_container_width=True):
        with st.spinner(T(ctx, "security.agent_analyzing", provider=prov_id)):
            try:
                result = run_security_analysis(cfg, agent_cfg, server_name=target, provider_id=prov_id)
                st.session_state.agent_report = result.report
            except LLMProviderError as e:
                st.error(str(e))

    if st.session_state.agent_report:
        section_head(T(ctx, "security.agent_report"))
        st.markdown(st.session_state.agent_report)

finalize_page(ctx, server_name=_agent_server)
