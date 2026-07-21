"""Scan History — trends, comparisons, threat evolution."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from skopos.config import load_app_env

load_app_env()

from skopos.i18n import browser_page_title
from skopos.app_shell import T, bootstrap_app, finalize_page, stop_page, prime_theme
from skopos.db import connect, connect_for_config, init_db
from skopos.db_dialect import resolve_db_target
from skopos.security.history_charts import (
    chart_diff_summary,
    chart_findings_trend,
    chart_fleet_radar,
    chart_scan_calendar,
    chart_score_timeline,
)
from skopos.security.store import (
    compare_snapshots,
    findings_trend,
    fleet_score_history,
    list_scan_history,
    scan_history_summary,
    snapshot_score,
    findings_for_snapshot,
)
from skopos.ui import hero, plot, section_head

st.set_page_config(
    page_title=browser_page_title("history.title"),
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="auto",
)
prime_theme()

ctx = bootstrap_app("./servers.yaml", "./agent.yaml")
cfg = ctx.cfg
locale = ctx.locale
known = tuple(s.name for s in cfg.servers)
server_labels = {s.name: f"{s.name} ({s.ssh.host})" for s in cfg.servers}

hero(T(ctx, "history.title"), T(ctx, "history.subtitle"))

days = st.sidebar.slider(T(ctx, "history.days"), 7, 90, 30, key="history_days")
server_filter = st.sidebar.selectbox(
    T(ctx, "common.all_servers"),
    [None] + list(known),
    format_func=lambda x: T(ctx, "common.all_servers") if x is None else server_labels.get(x, x),
    key="history_server",
)
names = [server_filter] if server_filter else list(known)

@st.cache_data(ttl=20)
def _load_history(db_target: str, names: tuple[str, ...], days: int):
    con = connect(db_target)
    init_db(con)
    history = list_scan_history(con, list(names) if names else None, limit=200, days=days)
    scores = fleet_score_history(con, list(names), days=days)
    trend = findings_trend(con, list(names) if names else None, days=days)
    summary = scan_history_summary(con, list(names) if names else None)
    con.close()
    return history, scores, trend, summary


history, scores, trend, summary = _load_history(resolve_db_target(cfg), tuple(names), days)

if not history:
    st.info(T(ctx, "history.no_data"))
    stop_page(ctx)

c1, c2, c3, c4 = st.columns(4)
c1.metric(T(ctx, "history.total_scans"), summary.get("total_scans", 0))
c2.metric(T(ctx, "history.last_scan"), (summary.get("last_scan_utc") or "—")[:19])
c3.metric(T(ctx, "history.servers"), len(names))
latest_score = scores[-1]["score"] if scores else "—"
c4.metric(T(ctx, "history.latest_score"), latest_score)

tab_timeline, tab_trend, tab_compare, tab_log = st.tabs(
    [
        T(ctx, "history.tab_timeline"),
        T(ctx, "history.tab_trend"),
        T(ctx, "history.tab_compare"),
        T(ctx, "history.tab_log"),
    ]
)

with tab_timeline:
    section_head(T(ctx, "history.score_timeline"))
    plot(chart_score_timeline(scores, title=T(ctx, "history.score_timeline")))
    col_a, col_b = st.columns(2)
    with col_a:
        section_head(T(ctx, "history.scan_activity"))
        plot(chart_scan_calendar(history, title=T(ctx, "history.scan_activity")))
    with col_b:
        section_head(T(ctx, "history.fleet_radar"))
        con = connect_for_config(cfg)
        init_db(con)
        latest_by_server: dict[str, int] = {}
        for row in history:
            sn = row["server_name"]
            if sn not in latest_by_server:
                findings = findings_for_snapshot(con, int(row["snapshot_id"]))
                latest_by_server[sn] = snapshot_score(findings)
        con.close()
        plot(chart_fleet_radar(latest_by_server, title=T(ctx, "history.fleet_radar")))

with tab_trend:
    section_head(T(ctx, "history.findings_trend"))
    plot(chart_findings_trend(trend, title=T(ctx, "history.findings_trend")))

with tab_compare:
    section_head(T(ctx, "history.compare"))
    ids = [int(r["snapshot_id"]) for r in history[:30]]
    labels = {
        int(r["snapshot_id"]): f"{r['server_name']} · {r['scanned_at_utc'][:16]}"
        for r in history[:30]
    }
    if len(ids) >= 2:
        ca, cb = st.columns(2)
        with ca:
            id_a = st.selectbox(T(ctx, "history.scan_a"), ids, format_func=lambda i: labels[i], key="cmp_a")
        with cb:
            id_b = st.selectbox(T(ctx, "history.scan_b"), ids, format_func=lambda i: labels[i], index=1, key="cmp_b")
        if id_a != id_b:
            con = connect_for_config(cfg)
            init_db(con)
            diff = compare_snapshots(con, id_a, id_b)
            con.close()
            plot(chart_diff_summary(diff, title=T(ctx, "history.compare_chart")))
            nc1, nc2 = st.columns(2)
            with nc1:
                st.markdown(f"**{T(ctx, 'history.new_issues')}** ({len(diff['new_issues'])})")
                for f in diff["new_issues"][:15]:
                    st.markdown(f"- [{f['severity'].upper()}] {f['title']}")
            with nc2:
                st.markdown(f"**{T(ctx, 'history.resolved')}** ({len(diff['resolved'])})")
                for f in diff["resolved"][:15]:
                    st.markdown(f"- [{f['severity'].upper()}] {f['title']}")
        else:
            st.warning(T(ctx, "history.pick_two"))
    else:
        st.info(T(ctx, "history.need_two_scans"))

with tab_log:
    section_head(T(ctx, "history.scan_log"))
    df = pd.DataFrame(history)
    df = df.rename(
        columns={
            "scanned_at_utc": T(ctx, "history.col_time"),
            "server_name": T(ctx, "history.col_server"),
            "findings_total": T(ctx, "history.col_findings"),
            "critical": T(ctx, "security.severity_critical"),
            "high": T(ctx, "security.severity_high"),
        }
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

finalize_page(ctx)
