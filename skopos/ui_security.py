"""Security score gauge, alert banners, sidebar badge."""

from __future__ import annotations

import html

import streamlit as st

from skopos.i18n import t
from skopos.security.charts import chart_resource_gauge, resource_gauge_metrics
from skopos.security.alert_i18n import localize_alert
from skopos.security.posture import SecurityPosture, grade_color
from skopos.themes import get_active_theme
from skopos.ui import plot


def render_sidebar_score(posture: SecurityPosture, *, locale: str = "en") -> None:
    color = grade_color(posture.grade)
    th = get_active_theme()
    crit = t("security.severity_critical", locale)
    high = t("security.severity_high", locale)
    st.sidebar.markdown(
        f"""
        <div class="sec-score-ring">
          <div style="font-size:0.75rem;text-transform:uppercase;letter-spacing:0.06em;color:{th.sec_ring_label};">
            {t('security.score_label', locale)}
          </div>
          <div class="sec-score-value" style="color:{color}">{posture.fleet_score}</div>
          <div class="sec-score-grade" style="color:{color}">{posture.grade}</div>
        </div>
        <div class="sec-alert-counts">
          <div class="sec-count-pill sec-count-critical">
            <span class="sec-count-num">{posture.critical_count}</span>
            <span class="sec-count-label">{crit}</span>
          </div>
          <div class="sec-count-pill sec-count-high">
            <span class="sec-count-num">{posture.high_count}</span>
            <span class="sec-count-label">{high}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _alert_class(severity: str) -> str:
    return {
        "critical": "sec-alert-critical",
        "high": "sec-alert-high",
        "medium": "sec-alert-medium",
    }.get(severity, "sec-alert-medium")


def render_alert_banner(posture: SecurityPosture, *, locale: str = "en", max_show: int = 5) -> None:
    critical_high = [a for a in posture.alerts if a.severity in ("critical", "high")]
    if not critical_high:
        return

    with st.container(border=True):
        st.markdown(f"#### ⚠️ {t('security.alerts_active', locale)}")
        for alert in critical_high[:max_show]:
            alert = localize_alert(alert, locale)
            icon = "🔴" if alert.severity == "critical" else "🟠"
            title = html.escape(alert.title or "")
            message = html.escape(alert.message or "")
            srv = f" · **{html.escape(alert.server_name)}**" if alert.server_name else ""
            st.markdown(
                f'<div class="{_alert_class(alert.severity)}">'
                f"<strong>{icon} {title}</strong>{srv}<br>"
                f"<span style='font-size:0.9rem'>{message}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        if len(critical_high) > max_show:
            st.caption(t("security.alerts_more", locale, n=len(critical_high) - max_show))


def plot_resource_gauges(snap: dict, *, key_prefix: str, locale: str = "en") -> None:
    """Render CPU / memory / load gauges in three equal-width columns."""
    st.markdown(f"##### {t('security.resource_utilization', locale)}")
    cols = st.columns(3, gap="medium")
    for col, (value, title, color) in zip(cols, resource_gauge_metrics(snap, locale=locale)):
        slug = title.lower().replace(" ", "_").replace("/", "_").replace("%", "pct")
        with col:
            with st.container(border=True):
                plot(chart_resource_gauge(value, title, color), key=f"{key_prefix}_{slug}")


def render_posture_panel(posture: SecurityPosture, *, locale: str = "en") -> None:
    color = grade_color(posture.grade)
    th = get_active_theme()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t("security.score_label", locale), f"{posture.fleet_score}/100")
    m2.metric(t("security.grade_label", locale), posture.grade)
    m3.metric(t("security.severity_critical", locale), posture.critical_count)
    m4.metric(t("security.alerts_total", locale), len(posture.alerts))

    st.markdown(
        f"<div style='height:8px;border-radius:4px;background:{th.progress_track};overflow:hidden'>"
        f"<div style='width:{posture.fleet_score}%;height:8px;background:{color};border-radius:4px'></div></div>",
        unsafe_allow_html=True,
    )

    if posture.server_scores:
        st.markdown(f"##### {t('security.per_server', locale)}")
        cols = st.columns(min(len(posture.server_scores), 4))
        for i, ss in enumerate(posture.server_scores):
            with cols[i % len(cols)]:
                st.metric(ss.server_name, f"{ss.score} ({ss.grade})")

    if posture.remarks:
        st.markdown(f"##### 📋 {t('security.audit_remarks', locale)}")
        for r in posture.remarks:
            st.markdown(f'<div class="sec-remark">• {html.escape(r)}</div>', unsafe_allow_html=True)

    if posture.alerts:
        st.markdown(f"##### 🚨 {t('security.all_alerts', locale)}")
        for a in posture.alerts:
            a = localize_alert(a, locale)
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}.get(a.severity, "⚪")
            with st.expander(f"{icon} [{a.severity.upper()}] {a.title}", expanded=a.severity == "critical"):
                st.write(a.message)
                if a.server_name:
                    st.caption(t("security.alert_server", locale, name=a.server_name))
                if a.action:
                    st.info(f"**{t('security.recommendation', locale)}:** {a.action}")
