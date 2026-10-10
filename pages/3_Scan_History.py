"""Scan History — trends, comparisons, threat evolution."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from skopos.config import load_app_env

load_app_env()

from skopos.i18n import browser_page_title
from skopos.app_shell import T, bootstrap_app, finalize_page, stop_page, prime_theme
from skopos.db import connect, init_db
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
from skopos.ui import hero, plot, section_head, section_loading
from skopos.ui_lazy_tabs import render_lazy_tabs
from skopos.ui_refresh import refresh_nonce, render_section_refresh

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
render_section_refresh("history", locale)

days = st.sidebar.slider(T(ctx, "history.days"), 7, 90, 30, key="history_days")
server_filter = st.sidebar.selectbox(
    T(ctx, "common.all_servers"),
    [None] + list(known),
    format_func=lambda x: T(ctx, "common.all_servers") if x is None else server_labels.get(x, x),
    key="history_server",
)
names = [server_filter] if server_filter else list(known)

@st.cache_data(show_spinner=False, persist="disk", max_entries=64)
def _load_history(db_target: str, names: tuple[str, ...], days: int, refresh_nonce: int = 0):
    _ = refresh_nonce
    con = connect(db_target)
    init_db(con)
    history = list_scan_history(con, list(names) if names else None, limit=200, days=days)
    scores = fleet_score_history(con, list(names), days=days)
    trend = findings_trend(con, list(names) if names else None, days=days)
    summary = scan_history_summary(con, list(names) if names else None)
    con.close()
    return history, scores, trend, summary


@st.cache_data(show_spinner=False, persist="disk", max_entries=64)
def _load_latest_scores(
    db_target: str, history_rows: tuple[tuple[int, str], ...], refresh_nonce: int = 0
) -> dict[str, int]:
    _ = refresh_nonce
    con = connect(db_target)
    init_db(con)
    latest: dict[str, int] = {}
    for snapshot_id, server_name in history_rows:
        if server_name not in latest:
            latest[server_name] = snapshot_score(findings_for_snapshot(con, snapshot_id))
    con.close()
    return latest


@st.cache_data(show_spinner=False, persist="disk", max_entries=64)
def _load_comparison(
    db_target: str, snapshot_a: int, snapshot_b: int, refresh_nonce: int = 0
):
    _ = refresh_nonce
    con = connect(db_target)
    init_db(con)
    diff = compare_snapshots(con, snapshot_a, snapshot_b)
    con.close()
    return diff


active_dashboard = render_lazy_tabs(
    "history",
    [
        ("timeline", T(ctx, "history.tab_timeline")),
        ("trend", T(ctx, "history.tab_trend")),
        ("compare", T(ctx, "history.tab_compare")),
        ("log", T(ctx, "history.tab_log")),
    ],
)

_db = resolve_db_target(cfg)
with section_loading(
    T(ctx, "common.loading_section"), 1, complete_message=T(ctx, "common.section_ready")
) as loading:
    history, scores, trend, summary = _load_history(
        _db, tuple(names), days, refresh_nonce("history")
    )
    loading.advance(T(ctx, "history.title"))

if not history:
    st.info(T(ctx, "history.no_data"))
    stop_page(ctx)

c1, c2, c3, c4 = st.columns(4)
c1.metric(T(ctx, "history.total_scans"), summary.get("total_scans", 0))
c2.metric(T(ctx, "history.last_scan"), (summary.get("last_scan_utc") or "—")[:19])
c3.metric(T(ctx, "history.servers"), len(names))
latest_score = scores[-1]["score"] if scores else "—"
c4.metric(T(ctx, "history.latest_score"), latest_score)

if active_dashboard == "timeline":
    render_section_refresh("history_timeline", locale)
    section_head(T(ctx, "history.score_timeline"))
    plot(chart_score_timeline(scores, title=T(ctx, "history.score_timeline")))
    col_a, col_b = st.columns(2)
    with col_a:
        section_head(T(ctx, "history.scan_activity"))
        plot(chart_scan_calendar(history, title=T(ctx, "history.scan_activity")))
    with col_b:
        section_head(T(ctx, "history.fleet_radar"))
        with section_loading(
            T(ctx, "common.loading_section"), 1, complete_message=T(ctx, "common.section_ready")
        ) as loading:
            score_rows = tuple(
                (int(row["snapshot_id"]), str(row["server_name"])) for row in history
            )
            latest_by_server = _load_latest_scores(
                _db, score_rows, refresh_nonce("history_timeline")
            )
            loading.advance(T(ctx, "history.fleet_radar"))
        plot(chart_fleet_radar(latest_by_server, title=T(ctx, "history.fleet_radar")))

elif active_dashboard == "trend":
    render_section_refresh("history_trend", locale)
    section_head(T(ctx, "history.findings_trend"))
    plot(chart_findings_trend(trend, title=T(ctx, "history.findings_trend")))

elif active_dashboard == "compare":
    render_section_refresh("history_compare", locale)
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
            with section_loading(
                T(ctx, "common.loading_section"),
                1,
                complete_message=T(ctx, "common.section_ready"),
            ) as loading:
                diff = _load_comparison(
                    _db, id_a, id_b, refresh_nonce("history_compare")
                )
                loading.advance(T(ctx, "history.compare"))
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

elif active_dashboard == "log":
    render_section_refresh("history_log", locale)
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
