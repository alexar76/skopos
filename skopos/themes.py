"""Dashboard theme system — light, dark, premium, midnight."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ThemeId = Literal[
    "light",
    "dark",
    "premium",
    "midnight",
    "ocean",
    "forest",
    "slate",
    "rose",
    "aurora",
]

LIGHT_THEME_IDS: frozenset[str] = frozenset({"light", "premium", "slate"})
DARK_THEME_IDS: frozenset[str] = frozenset({"dark", "midnight", "ocean", "forest", "rose", "aurora"})
COSMIC_THEME_IDS: frozenset[str] = frozenset({"midnight", "aurora"})


@dataclass(frozen=True)
class Theme:
    id: ThemeId
    label_key: str
    icon: str
    # Shell
    app_bg: str
    sidebar_bg: str
    text: str
    text_muted: str
    accent: str
    accent2: str
    border: str
    # Cards & metrics
    card_bg: str
    card_border: str
    card_shadow: str
    card_hover_shadow: str
    metric_bg: str
    metric_border: str
    metric_label: str
    metric_value: str
    # Typography accents
    hero_gradient: str
    section_border: str
    tab_active_bg: str
    divider: str
    # Plotly
    plotly_template: str
    chart_paper_bg: str
    chart_plot_bg: str
    chart_font: str
    chart_grid: str
    chart_title: str
    # Globe
    globe_scene_bg: str
    globe_paper_bg: str
    globe_title: str
    # Security widgets
    sec_ring_bg: str
    sec_ring_border: str
    sec_ring_label: str
    sec_crit_bg: str
    sec_crit_border: str
    sec_crit_text: str
    sec_high_bg: str
    sec_high_border: str
    sec_high_text: str
    sec_alert_crit_bg: str
    sec_alert_high_bg: str
    sec_alert_med_bg: str
    sec_remark: str
    progress_track: str


THEMES: dict[ThemeId, Theme] = {
    "light": Theme(
        id="light",
        label_key="theme.light",
        icon="☀️",
        app_bg="linear-gradient(160deg, #f4f7fb 0%, #eef2f7 45%, #f8fafc 100%)",
        sidebar_bg="linear-gradient(180deg, #ffffff 0%, #f8faff 100%)",
        text="#202124",
        text_muted="#5f6368",
        accent="#4285F4",
        accent2="#34A853",
        border="rgba(66,133,244,0.12)",
        card_bg="#ffffff",
        card_border="rgba(0,0,0,0.06)",
        card_shadow="0 4px 24px rgba(60,64,67,0.06)",
        card_hover_shadow="0 10px 36px rgba(66,133,244,0.12)",
        metric_bg="linear-gradient(145deg, #ffffff 0%, #f8faff 100%)",
        metric_border="rgba(66,133,244,0.12)",
        metric_label="#5f6368",
        metric_value="#202124",
        hero_gradient="linear-gradient(135deg, #1a1a2e 0%, #4285F4 50%, #34A853 100%)",
        section_border="linear-gradient(90deg, #4285F4, #34A853)",
        tab_active_bg="linear-gradient(180deg, rgba(66,133,244,0.10) 0%, transparent 100%)",
        divider="linear-gradient(90deg, transparent, #dadce0, transparent)",
        plotly_template="plotly_white",
        chart_paper_bg="rgba(0,0,0,0)",
        chart_plot_bg="rgba(0,0,0,0)",
        chart_font="#202124",
        chart_grid="#eef0f2",
        chart_title="#202124",
        globe_scene_bg="rgba(4,8,20,1)",
        globe_paper_bg="rgba(4,8,20,0.95)",
        globe_title="#e8eaed",
        sec_ring_bg="linear-gradient(145deg, #f8faff 0%, #fff 100%)",
        sec_ring_border="rgba(66,133,244,0.15)",
        sec_ring_label="#5f6368",
        sec_crit_bg="#fce8e6",
        sec_crit_border="#f5c6c2",
        sec_crit_text="#c5221f",
        sec_high_bg="#fff3e0",
        sec_high_border="#ffe0b2",
        sec_high_text="#e65100",
        sec_alert_crit_bg="#fce8e6",
        sec_alert_high_bg="#fff3e0",
        sec_alert_med_bg="#fef7e0",
        sec_remark="#5f6368",
        progress_track="#e8eaed",
    ),
    "dark": Theme(
        id="dark",
        label_key="theme.dark",
        icon="🌙",
        app_bg="linear-gradient(165deg, #0d1117 0%, #121820 50%, #0f1419 100%)",
        sidebar_bg="linear-gradient(180deg, #161b22 0%, #0d1117 100%)",
        text="#e6edf3",
        text_muted="#9aa4b2",
        accent="#58a6ff",
        accent2="#3fb950",
        border="rgba(88,166,255,0.18)",
        card_bg="#161b22",
        card_border="rgba(48,54,61,0.9)",
        card_shadow="0 8px 32px rgba(0,0,0,0.35)",
        card_hover_shadow="0 12px 40px rgba(88,166,255,0.15)",
        metric_bg="linear-gradient(145deg, #1c2128 0%, #161b22 100%)",
        metric_border="rgba(88,166,255,0.2)",
        metric_label="#8b949e",
        metric_value="#f0f6fc",
        hero_gradient="linear-gradient(135deg, #58a6ff 0%, #79c0ff 45%, #3fb950 100%)",
        section_border="linear-gradient(90deg, #58a6ff, #3fb950)",
        tab_active_bg="linear-gradient(180deg, rgba(88,166,255,0.14) 0%, transparent 100%)",
        divider="linear-gradient(90deg, transparent, #30363d, transparent)",
        plotly_template="plotly_dark",
        chart_paper_bg="rgba(0,0,0,0)",
        chart_plot_bg="rgba(0,0,0,0)",
        chart_font="#e6edf3",
        chart_grid="#21262d",
        chart_title="#f0f6fc",
        globe_scene_bg="rgba(2,4,12,1)",
        globe_paper_bg="rgba(2,4,12,0.98)",
        globe_title="#e6edf3",
        sec_ring_bg="#161b22",
        sec_ring_border="rgba(88,166,255,0.22)",
        sec_ring_label="#9aa4b2",
        sec_crit_bg="rgba(248,81,73,0.15)",
        sec_crit_border="rgba(248,81,73,0.35)",
        sec_crit_text="#ff7b72",
        sec_high_bg="rgba(210,153,34,0.15)",
        sec_high_border="rgba(210,153,34,0.35)",
        sec_high_text="#e3b341",
        sec_alert_crit_bg="#2a1215",
        sec_alert_high_bg="#2a1f0e",
        sec_alert_med_bg="#252115",
        sec_remark="#9aa4b2",
        progress_track="#30363d",
    ),
    "premium": Theme(
        id="premium",
        label_key="theme.premium",
        icon="✨",
        app_bg="linear-gradient(155deg, #faf6ef 0%, #f3ebe0 40%, #efe4d4 100%)",
        sidebar_bg="linear-gradient(180deg, #fffdf8 0%, #f7f0e6 100%)",
        text="#2c2416",
        text_muted="#3d3528",
        accent="#b8860b",
        accent2="#1a6b4a",
        border="rgba(184,134,11,0.22)",
        card_bg="#fffef9",
        card_border="rgba(184,134,11,0.18)",
        card_shadow="0 10px 40px rgba(44,36,22,0.08), inset 0 1px 0 rgba(255,255,255,0.8)",
        card_hover_shadow="0 16px 48px rgba(184,134,11,0.16)",
        metric_bg="linear-gradient(145deg, #fffef9 0%, #f5efe3 100%)",
        metric_border="rgba(184,134,11,0.25)",
        metric_label="#3d3528",
        metric_value="#1a1408",
        hero_gradient="linear-gradient(135deg, #2c2416 0%, #b8860b 40%, #1a6b4a 100%)",
        section_border="linear-gradient(90deg, #b8860b, #1a6b4a)",
        tab_active_bg="linear-gradient(180deg, rgba(184,134,11,0.12) 0%, transparent 100%)",
        divider="linear-gradient(90deg, transparent, rgba(184,134,11,0.35), transparent)",
        plotly_template="plotly_white",
        chart_paper_bg="rgba(0,0,0,0)",
        chart_plot_bg="rgba(0,0,0,0)",
        chart_font="#1a1408",
        chart_grid="#b8a890",
        chart_title="#1a1408",
        globe_scene_bg="rgba(12,10,8,1)",
        globe_paper_bg="rgba(12,10,8,0.96)",
        globe_title="#f5efe3",
        sec_ring_bg="linear-gradient(145deg, #fffef9 0%, #f5efe3 100%)",
        sec_ring_border="rgba(184,134,11,0.28)",
        sec_ring_label="#3d3528",
        sec_crit_bg="rgba(183,28,28,0.1)",
        sec_crit_border="rgba(183,28,28,0.28)",
        sec_crit_text="#b71c1c",
        sec_high_bg="rgba(230,126,34,0.12)",
        sec_high_border="rgba(230,126,34,0.3)",
        sec_high_text="#c45c00",
        sec_alert_crit_bg="#fce8e6",
        sec_alert_high_bg="#fff3e0",
        sec_alert_med_bg="#fef7e0",
        sec_remark="#3d3528",
        progress_track="#ebe4d8",
    ),
    "midnight": Theme(
        id="midnight",
        label_key="theme.midnight",
        icon="🌌",
        app_bg="#060508",
        sidebar_bg="linear-gradient(180deg, rgba(14,10,18,0.96) 0%, rgba(6,5,8,0.98) 100%)",
        text="#fff4e8",
        text_muted="#c4a88a",
        accent="#ff8c2a",
        accent2="#ffd56a",
        border="rgba(255,160,80,0.22)",
        card_bg="rgba(18,12,22,0.78)",
        card_border="rgba(255,160,80,0.22)",
        card_shadow="0 12px 40px rgba(0,0,0,0.45), 0 0 0 1px rgba(255,160,80,0.08), inset 0 1px 0 rgba(255,244,232,0.05)",
        card_hover_shadow="0 18px 52px rgba(0,0,0,0.55), 0 0 32px rgba(255,140,42,0.18), inset 0 1px 0 rgba(255,244,232,0.08)",
        metric_bg="linear-gradient(145deg, rgba(26,18,24,0.92) 0%, rgba(14,10,18,0.96) 100%)",
        metric_border="rgba(255,160,80,0.28)",
        metric_label="#c4a88a",
        metric_value="#fff4e8",
        hero_gradient="linear-gradient(95deg, #ffb347 0%, #ffd56a 45%, #fff4e8 100%)",
        section_border="linear-gradient(90deg, #ff8c2a, #ffd56a)",
        tab_active_bg="linear-gradient(180deg, rgba(255,140,42,0.16) 0%, transparent 100%)",
        divider="linear-gradient(90deg, transparent, rgba(255,160,80,0.35), transparent)",
        plotly_template="plotly_dark",
        chart_paper_bg="rgba(0,0,0,0)",
        chart_plot_bg="rgba(0,0,0,0)",
        chart_font="#fff4e8",
        chart_grid="#1a1218",
        chart_title="#ffd56a",
        globe_scene_bg="rgba(6,5,8,1)",
        globe_paper_bg="rgba(6,5,8,0.98)",
        globe_title="#fff4e8",
        sec_ring_bg="linear-gradient(145deg, rgba(26,18,24,0.95) 0%, rgba(14,10,18,0.98) 100%)",
        sec_ring_border="rgba(255,160,80,0.32)",
        sec_ring_label="#c4a88a",
        sec_crit_bg="rgba(232,74,26,0.16)",
        sec_crit_border="rgba(232,74,26,0.38)",
        sec_crit_text="#ffb4a0",
        sec_high_bg="rgba(255,140,42,0.14)",
        sec_high_border="rgba(255,140,42,0.35)",
        sec_high_text="#ffcc80",
        sec_alert_crit_bg="#2a1210",
        sec_alert_high_bg="#2a1a0e",
        sec_alert_med_bg="#1a1410",
        sec_remark="#c4a88a",
        progress_track="#1a1218",
    ),
    "ocean": Theme(
        id="ocean",
        label_key="theme.ocean",
        icon="🌊",
        app_bg="linear-gradient(165deg, #041018 0%, #061820 50%, #030c12 100%)",
        sidebar_bg="linear-gradient(180deg, #0a1c28 0%, #041018 100%)",
        text="#e0f7fa",
        text_muted="#80cbc4",
        accent="#26c6da",
        accent2="#4dd0e1",
        border="rgba(38,198,218,0.22)",
        card_bg="#0a1c28",
        card_border="rgba(38,198,218,0.18)",
        card_shadow="0 8px 32px rgba(0,0,0,0.4)",
        card_hover_shadow="0 12px 40px rgba(38,198,218,0.18)",
        metric_bg="linear-gradient(145deg, #0d2430 0%, #0a1c28 100%)",
        metric_border="rgba(38,198,218,0.24)",
        metric_label="#80cbc4",
        metric_value="#e0f7fa",
        hero_gradient="linear-gradient(135deg, #006064 0%, #26c6da 50%, #4dd0e1 100%)",
        section_border="linear-gradient(90deg, #00838f, #26c6da)",
        tab_active_bg="linear-gradient(180deg, rgba(38,198,218,0.14) 0%, transparent 100%)",
        divider="linear-gradient(90deg, transparent, #1a3a44, transparent)",
        plotly_template="plotly_dark",
        chart_paper_bg="rgba(0,0,0,0)",
        chart_plot_bg="rgba(0,0,0,0)",
        chart_font="#e0f7fa",
        chart_grid="#123040",
        chart_title="#b2ebf2",
        globe_scene_bg="rgba(2,8,16,1)",
        globe_paper_bg="rgba(2,8,16,0.98)",
        globe_title="#e0f7fa",
        sec_ring_bg="#0a1c28",
        sec_ring_border="rgba(38,198,218,0.28)",
        sec_ring_label="#80cbc4",
        sec_crit_bg="rgba(239,83,80,0.16)",
        sec_crit_border="rgba(239,83,80,0.38)",
        sec_crit_text="#ff8a80",
        sec_high_bg="rgba(255,183,77,0.14)",
        sec_high_border="rgba(255,183,77,0.35)",
        sec_high_text="#ffcc80",
        sec_alert_crit_bg="#1a1010",
        sec_alert_high_bg="#1a160e",
        sec_alert_med_bg="#101820",
        sec_remark="#80cbc4",
        progress_track="#123040",
    ),
    "forest": Theme(
        id="forest",
        label_key="theme.forest",
        icon="🌲",
        app_bg="linear-gradient(165deg, #0a120c 0%, #0e1810 50%, #081008 100%)",
        sidebar_bg="linear-gradient(180deg, #142018 0%, #0a120c 100%)",
        text="#e8f5e9",
        text_muted="#a5d6a7",
        accent="#66bb6a",
        accent2="#81c784",
        border="rgba(102,187,106,0.22)",
        card_bg="#142018",
        card_border="rgba(102,187,106,0.18)",
        card_shadow="0 8px 32px rgba(0,0,0,0.38)",
        card_hover_shadow="0 12px 40px rgba(102,187,106,0.16)",
        metric_bg="linear-gradient(145deg, #182820 0%, #142018 100%)",
        metric_border="rgba(102,187,106,0.24)",
        metric_label="#a5d6a7",
        metric_value="#e8f5e9",
        hero_gradient="linear-gradient(135deg, #1b5e20 0%, #66bb6a 50%, #a5d6a7 100%)",
        section_border="linear-gradient(90deg, #2e7d32, #66bb6a)",
        tab_active_bg="linear-gradient(180deg, rgba(102,187,106,0.14) 0%, transparent 100%)",
        divider="linear-gradient(90deg, transparent, #2a4030, transparent)",
        plotly_template="plotly_dark",
        chart_paper_bg="rgba(0,0,0,0)",
        chart_plot_bg="rgba(0,0,0,0)",
        chart_font="#e8f5e9",
        chart_grid="#1a3020",
        chart_title="#c8e6c9",
        globe_scene_bg="rgba(4,10,6,1)",
        globe_paper_bg="rgba(4,10,6,0.98)",
        globe_title="#e8f5e9",
        sec_ring_bg="#142018",
        sec_ring_border="rgba(102,187,106,0.28)",
        sec_ring_label="#a5d6a7",
        sec_crit_bg="rgba(239,83,80,0.16)",
        sec_crit_border="rgba(239,83,80,0.38)",
        sec_crit_text="#ff8a80",
        sec_high_bg="rgba(255,183,77,0.14)",
        sec_high_border="rgba(255,183,77,0.35)",
        sec_high_text="#ffcc80",
        sec_alert_crit_bg="#1a1010",
        sec_alert_high_bg="#1a160e",
        sec_alert_med_bg="#121810",
        sec_remark="#a5d6a7",
        progress_track="#1a3020",
    ),
    "slate": Theme(
        id="slate",
        label_key="theme.slate",
        icon="🪨",
        app_bg="linear-gradient(160deg, #eef1f5 0%, #e4e8ee 45%, #f0f2f5 100%)",
        sidebar_bg="linear-gradient(180deg, #f8f9fb 0%, #eef1f5 100%)",
        text="#1c2333",
        text_muted="#5c6578",
        accent="#546e7a",
        accent2="#78909c",
        border="rgba(84,110,122,0.18)",
        card_bg="#ffffff",
        card_border="rgba(28,35,51,0.08)",
        card_shadow="0 4px 20px rgba(28,35,51,0.06)",
        card_hover_shadow="0 10px 32px rgba(84,110,122,0.12)",
        metric_bg="linear-gradient(145deg, #ffffff 0%, #f4f6f8 100%)",
        metric_border="rgba(84,110,122,0.16)",
        metric_label="#5c6578",
        metric_value="#1c2333",
        hero_gradient="linear-gradient(135deg, #263238 0%, #546e7a 50%, #78909c 100%)",
        section_border="linear-gradient(90deg, #455a64, #78909c)",
        tab_active_bg="linear-gradient(180deg, rgba(84,110,122,0.10) 0%, transparent 100%)",
        divider="linear-gradient(90deg, transparent, #cfd8dc, transparent)",
        plotly_template="plotly_white",
        chart_paper_bg="rgba(0,0,0,0)",
        chart_plot_bg="rgba(0,0,0,0)",
        chart_font="#1c2333",
        chart_grid="#dfe3e8",
        chart_title="#1c2333",
        globe_scene_bg="rgba(18,24,32,1)",
        globe_paper_bg="rgba(18,24,32,0.96)",
        globe_title="#eceff1",
        sec_ring_bg="linear-gradient(145deg, #f8f9fb 0%, #fff 100%)",
        sec_ring_border="rgba(84,110,122,0.20)",
        sec_ring_label="#5c6578",
        sec_crit_bg="#ffebee",
        sec_crit_border="#ffcdd2",
        sec_crit_text="#c62828",
        sec_high_bg="#fff8e1",
        sec_high_border="#ffe082",
        sec_high_text="#ef6c00",
        sec_alert_crit_bg="#ffebee",
        sec_alert_high_bg="#fff8e1",
        sec_alert_med_bg="#f5f5f5",
        sec_remark="#5c6578",
        progress_track="#dfe3e8",
    ),
    "rose": Theme(
        id="rose",
        label_key="theme.rose",
        icon="🌹",
        app_bg="linear-gradient(165deg, #140810 0%, #1a0c14 50%, #100610 100%)",
        sidebar_bg="linear-gradient(180deg, #1e1018 0%, #140810 100%)",
        text="#fce4ec",
        text_muted="#f48fb1",
        accent="#ec407a",
        accent2="#f06292",
        border="rgba(236,64,122,0.24)",
        card_bg="#1e1018",
        card_border="rgba(236,64,122,0.20)",
        card_shadow="0 8px 32px rgba(0,0,0,0.42)",
        card_hover_shadow="0 12px 40px rgba(236,64,122,0.18)",
        metric_bg="linear-gradient(145deg, #241420 0%, #1e1018 100%)",
        metric_border="rgba(236,64,122,0.26)",
        metric_label="#f48fb1",
        metric_value="#fce4ec",
        hero_gradient="linear-gradient(135deg, #880e4f 0%, #ec407a 50%, #f8bbd0 100%)",
        section_border="linear-gradient(90deg, #ad1457, #ec407a)",
        tab_active_bg="linear-gradient(180deg, rgba(236,64,122,0.14) 0%, transparent 100%)",
        divider="linear-gradient(90deg, transparent, #3a2030, transparent)",
        plotly_template="plotly_dark",
        chart_paper_bg="rgba(0,0,0,0)",
        chart_plot_bg="rgba(0,0,0,0)",
        chart_font="#fce4ec",
        chart_grid="#281820",
        chart_title="#f8bbd0",
        globe_scene_bg="rgba(12,4,8,1)",
        globe_paper_bg="rgba(12,4,8,0.98)",
        globe_title="#fce4ec",
        sec_ring_bg="#1e1018",
        sec_ring_border="rgba(236,64,122,0.30)",
        sec_ring_label="#f48fb1",
        sec_crit_bg="rgba(239,83,80,0.16)",
        sec_crit_border="rgba(239,83,80,0.38)",
        sec_crit_text="#ff8a80",
        sec_high_bg="rgba(255,183,77,0.14)",
        sec_high_border="rgba(255,183,77,0.35)",
        sec_high_text="#ffcc80",
        sec_alert_crit_bg="#2a1018",
        sec_alert_high_bg="#2a1810",
        sec_alert_med_bg="#1a1018",
        sec_remark="#f48fb1",
        progress_track="#281820",
    ),
    "aurora": Theme(
        id="aurora",
        label_key="theme.aurora",
        icon="🌈",
        app_bg="#080612",
        sidebar_bg="linear-gradient(180deg, rgba(16,10,28,0.96) 0%, rgba(8,6,18,0.98) 100%)",
        text="#ede7f6",
        text_muted="#b39ddb",
        accent="#7c4dff",
        accent2="#69f0ae",
        border="rgba(124,77,255,0.24)",
        card_bg="rgba(16,10,28,0.82)",
        card_border="rgba(124,77,255,0.22)",
        card_shadow="0 12px 40px rgba(0,0,0,0.45), 0 0 0 1px rgba(124,77,255,0.08)",
        card_hover_shadow="0 18px 52px rgba(0,0,0,0.55), 0 0 32px rgba(124,77,255,0.18)",
        metric_bg="linear-gradient(145deg, rgba(22,14,36,0.92) 0%, rgba(12,8,22,0.96) 100%)",
        metric_border="rgba(124,77,255,0.28)",
        metric_label="#b39ddb",
        metric_value="#ede7f6",
        hero_gradient="linear-gradient(95deg, #7c4dff 0%, #69f0ae 50%, #ede7f6 100%)",
        section_border="linear-gradient(90deg, #7c4dff, #69f0ae)",
        tab_active_bg="linear-gradient(180deg, rgba(124,77,255,0.16) 0%, transparent 100%)",
        divider="linear-gradient(90deg, transparent, rgba(124,77,255,0.35), transparent)",
        plotly_template="plotly_dark",
        chart_paper_bg="rgba(0,0,0,0)",
        chart_plot_bg="rgba(0,0,0,0)",
        chart_font="#ede7f6",
        chart_grid="#1a1028",
        chart_title="#b388ff",
        globe_scene_bg="rgba(8,6,18,1)",
        globe_paper_bg="rgba(8,6,18,0.98)",
        globe_title="#ede7f6",
        sec_ring_bg="linear-gradient(145deg, rgba(22,14,36,0.95) 0%, rgba(12,8,22,0.98) 100%)",
        sec_ring_border="rgba(124,77,255,0.32)",
        sec_ring_label="#b39ddb",
        sec_crit_bg="rgba(239,83,80,0.16)",
        sec_crit_border="rgba(239,83,80,0.38)",
        sec_crit_text="#ff8a80",
        sec_high_bg="rgba(255,183,77,0.14)",
        sec_high_border="rgba(255,183,77,0.35)",
        sec_high_text="#ffcc80",
        sec_alert_crit_bg="#1a1020",
        sec_alert_high_bg="#1a1820",
        sec_alert_med_bg="#121018",
        sec_remark="#b39ddb",
        progress_track="#1a1028",
    ),
}

THEME_ORDER: tuple[ThemeId, ...] = (
    "light",
    "slate",
    "premium",
    "dark",
    "ocean",
    "forest",
    "rose",
    "aurora",
    "midnight",
)
DEFAULT_THEME: ThemeId = "midnight"


def is_light_theme(theme_id: str) -> bool:
    return theme_id in LIGHT_THEME_IDS


def is_dark_theme(theme_id: str) -> bool:
    return theme_id in DARK_THEME_IDS


def is_cosmic_theme(theme_id: str) -> bool:
    return theme_id in COSMIC_THEME_IDS


def get_active_theme() -> Theme:
    try:
        import streamlit as st

        from skopos.theme_prefs import SKOPOS_THEME_KEY, SKOPOS_THEME_WIDGET

        theme_id = st.session_state.get(SKOPOS_THEME_KEY)
        if not theme_id or theme_id not in THEMES:
            theme_id = st.session_state.get(SKOPOS_THEME_WIDGET, DEFAULT_THEME)
        if theme_id not in THEMES and "app_theme_selector" in st.session_state:
            theme_id = st.session_state.app_theme_selector
        return THEMES.get(theme_id, THEMES[DEFAULT_THEME])
    except Exception:
        return THEMES[DEFAULT_THEME]


def theme_surface_bg(theme: Theme) -> str:
    """Solid surface color for contrast checks (card backgrounds)."""
    return {
        "light": "#ffffff",
        "dark": "#161b22",
        "premium": "#fffef9",
        "midnight": "#120c16",
        "ocean": "#0a1c28",
        "forest": "#142018",
        "slate": "#ffffff",
        "rose": "#1e1018",
        "aurora": "#100a1c",
    }[theme.id]


def theme_shell_bg(theme: Theme) -> str:
    """Solid app background for first paint (avoids flash on navigation)."""
    return {
        "light": "#f4f7fb",
        "dark": "#0d1117",
        "premium": "#faf8f3",
        "midnight": "#060508",
        "ocean": "#041018",
        "forest": "#0a120c",
        "slate": "#eef1f5",
        "rose": "#140810",
        "aurora": "#080612",
    }[theme.id]


def _theme_shell_colors() -> dict[str, str]:
    return {tid: theme_shell_bg(th) for tid, th in THEMES.items()}


def _theme_ids_json() -> str:
    import json

    return json.dumps(list(THEMES.keys()))


def _agent_widget_selector() -> str:
    """Target only the innermost Streamlit block that hosts the floating agent."""
    return (
        'section.main div[data-testid="stVerticalBlock"]'
        ":has(> div.element-container:has(.stats-agent-anchor))"
        ':not(:has(> div.element-container > div[data-testid="stVerticalBlock"]'
        ":has(> div.element-container:has(.stats-agent-anchor))))"
    )


def _status_bar_palette() -> dict[ThemeId, dict[str, str]]:
    """Header + Running… bar colors keyed by data-skopos-theme (survives rerun flash)."""
    return {
        "light": {
            "header_bg": "rgba(255,255,255,0.92)",
            "status_bg": "rgba(255,255,255,0.96)",
            "text": "#202124",
            "muted": "#5f6368",
            "border": "rgba(0,0,0,0.10)",
        },
        "dark": {
            "header_bg": "rgba(13,17,23,0.96)",
            "status_bg": "rgba(22,27,34,0.98)",
            "text": "#e6edf3",
            "muted": "#8b949e",
            "border": "rgba(88,166,255,0.28)",
        },
        "premium": {
            "header_bg": "rgba(255,254,249,0.92)",
            "status_bg": "rgba(255,254,249,0.96)",
            "text": "#1a1408",
            "muted": "#3d3528",
            "border": "rgba(184,134,11,0.28)",
        },
        "midnight": {
            "header_bg": "transparent",
            "status_bg": "rgba(18,12,22,0.88)",
            "text": "#fff4e8",
            "muted": "#c4a88a",
            "border": "rgba(255,160,80,0.28)",
        },
        "ocean": {
            "header_bg": "rgba(4,16,24,0.96)",
            "status_bg": "rgba(10,28,40,0.98)",
            "text": "#e0f7fa",
            "muted": "#80cbc4",
            "border": "rgba(38,198,218,0.28)",
        },
        "forest": {
            "header_bg": "rgba(10,18,12,0.96)",
            "status_bg": "rgba(20,32,24,0.98)",
            "text": "#e8f5e9",
            "muted": "#a5d6a7",
            "border": "rgba(102,187,106,0.28)",
        },
        "slate": {
            "header_bg": "rgba(238,241,245,0.92)",
            "status_bg": "rgba(248,249,251,0.96)",
            "text": "#1c2333",
            "muted": "#5c6578",
            "border": "rgba(84,110,122,0.28)",
        },
        "rose": {
            "header_bg": "rgba(20,8,16,0.96)",
            "status_bg": "rgba(30,16,24,0.98)",
            "text": "#fce4ec",
            "muted": "#f48fb1",
            "border": "rgba(236,64,122,0.28)",
        },
        "aurora": {
            "header_bg": "transparent",
            "status_bg": "rgba(16,10,28,0.88)",
            "text": "#ede7f6",
            "muted": "#b39ddb",
            "border": "rgba(124,77,255,0.28)",
        },
    }


def build_status_bar_css() -> str:
    """Theme-aware Running… / stStatusWidget chrome — uses html[data-skopos-theme] for first paint."""
    blocks: list[str] = [
        """
  /* Streamlit header strip — hidden; SKOPOS topbar + floating Running… pill replace it. */
  header[data-testid="stHeader"] {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    max-height: 0 !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    overflow: hidden !important;
  }
"""
    ]
    for tid, pal in _status_bar_palette().items():
        blocks.append(
            f"""
  html[data-skopos-theme="{tid}"] header[data-testid="stHeader"] {{
    display: none !important;
    background: transparent !important;
    border: none !important;
  }}
"""
        )
    return f"""
<style id="skopos-status-bar">
{"".join(blocks)}
</style>
"""



def _build_theme_boot_script() -> str:
    return f"""
<script id="skopos-theme-boot">
(function() {{
  var valid = {_theme_ids_json()};
  try {{
    var stored = localStorage.getItem("skopos-theme-id");
    if (stored && valid.indexOf(stored) >= 0) {{
      document.documentElement.setAttribute("data-skopos-theme", stored);
    }} else {{
      document.documentElement.setAttribute("data-skopos-theme", "{DEFAULT_THEME}");
    }}
  }} catch (e) {{}}
}})();
</script>
"""


def build_critical_shell_css(theme: Theme, *, collapsed: bool = False) -> str:
    """First-paint shell: full background + text before Streamlit widgets render."""
    th = theme
    shell = theme_shell_bg(th)
    scheme = "dark" if is_dark_theme(theme.id) else "light"
    shells_json = __import__("json").dumps(_theme_shell_colors())
    _ = collapsed  # sidebar is always expanded; kept for call-site compatibility
    return (
        _build_theme_boot_script()
        + build_status_bar_css()
        + f"""
<style id="stats-critical-shell">
  :root {{
    --skopos-sidebar-expanded-width: 17rem;
    --skopos-sidebar-collapsed-width: 4rem;
    --skopos-sidebar-collapsed: var(--skopos-sidebar-collapsed-width);
    --skopos-sidebar-expanded: var(--skopos-sidebar-expanded-width);
    --sidebar-width: var(--skopos-sidebar-expanded-width);
  }}
  html.skopos-sidebar-expanded {{
    --sidebar-width: var(--skopos-sidebar-expanded-width) !important;
  }}
  html.skopos-sidebar-collapsed {{
    --sidebar-width: var(--skopos-sidebar-collapsed-width) !important;
  }}
  html {{
    color-scheme: {scheme};
    background-color: {shell} !important;
  }}
  body,
  [data-testid="stAppViewContainer"],
  [data-testid="stApp"],
  .stApp,
  [data-testid="stMain"],
  section.main {{
    background-color: {shell} !important;
    background-image: {th.app_bg} !important;
    color: {th.text} !important;
    transition: none !important;
  }}
  section[data-testid="stSidebar"],
  section[data-testid="stSidebar"] > div,
  [data-testid="stSidebarUserContent"] {{
    background: {th.sidebar_bg} !important;
    transition:
      width 0.28s cubic-bezier(0.4, 0, 0.2, 1),
      min-width 0.28s cubic-bezier(0.4, 0, 0.2, 1),
      max-width 0.28s cubic-bezier(0.4, 0, 0.2, 1),
      flex-basis 0.28s cubic-bezier(0.4, 0, 0.2, 1),
      padding 0.28s cubic-bezier(0.4, 0, 0.2, 1) !important;
  }}
  section[data-testid="stSidebar"] .stMarkdown,
  section[data-testid="stSidebar"] label,
  section[data-testid="stSidebar"] p,
  section[data-testid="stSidebar"] span,
  section[data-testid="stSidebar"] small {{
    color: {th.text} !important;
  }}
</style>
<script>
(function() {{
  var id = "{theme.id}";
  var collapsed = false;
  var valid = {_theme_ids_json()};
  var shells = {shells_json};
  var expandedW = "17rem";
  function applySidebarWidth() {{
    document.documentElement.style.setProperty("--sidebar-width", expandedW);
    var sb = document.querySelector('section[data-testid="stSidebar"]');
    if (sb) {{
      sb.style.setProperty("width", expandedW, "important");
      sb.style.setProperty("min-width", expandedW, "important");
      sb.style.setProperty("max-width", expandedW, "important");
      var measured = sb.getBoundingClientRect().width;
      if (measured > 32) {{
        document.documentElement.style.setProperty("--sidebar-width", measured + "px");
      }}
    }}
  }}
  try {{
    if (valid.indexOf(id) < 0) {{
      id = "{DEFAULT_THEME}";
    }}
    document.documentElement.setAttribute("data-skopos-theme", id);
    document.documentElement.classList.remove("skopos-sidebar-collapsed");
    document.documentElement.classList.add("skopos-sidebar-expanded");
    applySidebarWidth();
    if (shells[id]) {{
      document.documentElement.style.backgroundColor = shells[id];
    }}
    localStorage.setItem("skopos-theme-id", id);
    localStorage.setItem("skopos-sidebar-collapsed", "0");
    if (window.__skoposSidebarObs) {{
      window.__skoposSidebarObs.disconnect();
    }}
    var pending = null;
    window.__skoposSidebarObs = new MutationObserver(function() {{
      if (pending) return;
      pending = requestAnimationFrame(function() {{
        pending = null;
        applySidebarWidth();
      }});
    }});
    window.__skoposSidebarObs.observe(document.documentElement, {{ childList: true, subtree: true }});
  }} catch (e) {{}}
}})();
</script>
"""
    )


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """WCAG relative luminance contrast ratio."""

    def _lum(hex_color: str) -> float:
        h = hex_color.lstrip("#")
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))

        def lin(c: float) -> float:
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        r, g, b = lin(r), lin(g), lin(b)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    l1, l2 = _lum(fg_hex), _lum(bg_hex)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def theme_label(theme: Theme, locale: str) -> str:
    from skopos.i18n import t

    return t(theme.label_key, locale)


def _widget_palette(theme: Theme) -> dict[str, str]:
    """Shared input/dropdown/alert colors for app shell and portaled overlays."""
    light_ui = is_light_theme(theme.id)
    th = theme
    if theme.id == "premium":
        chip_bg = "rgba(184,134,11,0.14)"
        chip_text = "#8a6914"
    elif theme.id == "midnight":
        chip_bg = "rgba(255,140,42,0.16)"
        chip_text = "#ffd56a"
    elif theme.id == "aurora":
        chip_bg = "rgba(124,77,255,0.18)"
        chip_text = "#b388ff"
    elif theme.id == "ocean":
        chip_bg = "rgba(38,198,218,0.16)"
        chip_text = "#4dd0e1"
    elif theme.id == "forest":
        chip_bg = "rgba(102,187,106,0.16)"
        chip_text = "#81c784"
    elif theme.id == "rose":
        chip_bg = "rgba(236,64,122,0.16)"
        chip_text = "#f48fb1"
    elif light_ui:
        chip_bg = "#e8f0fe" if theme.id == "light" else "rgba(84,110,122,0.12)"
        chip_text = "#1967d2" if theme.id == "light" else "#455a64"
    else:
        chip_bg = "rgba(88,166,255,0.18)"
        chip_text = "#58a6ff"

    if light_ui:
        widget_bg = "#ffffff"
        input_inset_bg = "#ffffff"
        input_inset_border = "rgba(0,0,0,0.22)"
    elif theme.id == "midnight":
        widget_bg = "rgba(18,12,22,0.92)"
        input_inset_bg = "rgba(255,244,232,0.10)"
        input_inset_border = "rgba(255,160,80,0.55)"
    elif theme.id == "aurora":
        widget_bg = "rgba(16,10,28,0.92)"
        input_inset_bg = "rgba(237,231,246,0.10)"
        input_inset_border = "rgba(124,77,255,0.55)"
    else:
        widget_bg = "#1c2128"
        input_inset_bg = "rgba(255,255,255,0.08)"
        input_inset_border = th.border if th.border else "rgba(88,166,255,0.45)"
    return {
        "widget_bg": widget_bg,
        "input_inset_bg": input_inset_bg,
        "input_inset_border": input_inset_border,
        "widget_text": th.text,
        "widget_border": "rgba(0,0,0,0.10)" if light_ui else th.border,
        "widget_muted": th.text_muted,
        "chip_bg": chip_bg,
        "chip_text": chip_text,
        "menu_shadow": "0 4px 16px rgba(60,64,67,0.16)" if light_ui else "0 8px 24px rgba(0,0,0,0.45)",
        "alert_info_bg": chip_bg if light_ui else "rgba(88,166,255,0.12)",
        "alert_info_text": chip_text if light_ui else th.accent,
        "alert_success_bg": "#e6f4ea" if light_ui else "rgba(63,185,80,0.14)",
        "alert_success_text": "#137333" if light_ui else th.accent2,
        "alert_warning_bg": th.sec_high_bg,
        "alert_warning_text": th.sec_high_text,
        "alert_error_bg": th.sec_crit_bg,
        "alert_error_text": th.sec_crit_text,
        "table_header_bg": th.metric_bg,
        "table_row_hover": chip_bg,
    }


def build_portal_overlay_css(theme: Theme) -> str:
    """Selectbox/multiselect menus render in a body portal — outside .stApp."""
    th = theme
    pal = _widget_palette(theme)
    menu_bg = pal["widget_bg"]
    menu_text = pal["widget_text"]
    menu_border = pal["widget_border"]
    hover_bg = pal["chip_bg"]
    hover_text = pal["chip_text"]
    selected_bg = th.accent
    selected_text = "#ffffff"
    return f"""
<style id="stats-portal-overlays">
  /* Streamlit virtual dropdowns (portal to body, not inside .stApp) */
  [data-testid="stSelectboxVirtualDropdown"],
  [data-testid="stVirtualDropdown"],
  [data-testid="stMultiSelectVirtualDropdown"],
  [data-testid="stSelectboxVirtualDropdown"] > div,
  [data-testid="stVirtualDropdown"] > div,
  [data-testid="stMultiSelectVirtualDropdown"] > div,
  [data-testid="stSelectboxVirtualDropdown"] [role="listbox"],
  [data-testid="stVirtualDropdown"] [role="listbox"],
  [data-testid="stMultiSelectVirtualDropdown"] [role="listbox"],
  div[data-baseweb="popover"] [data-baseweb="menu"],
  div[data-baseweb="popover"] [data-baseweb="menu"] ul {{
    background-color: {menu_bg} !important;
    color: {menu_text} !important;
    border-color: {menu_border} !important;
  }}

  [data-testid="stSelectboxVirtualDropdown"],
  [data-testid="stVirtualDropdown"],
  [data-testid="stMultiSelectVirtualDropdown"] {{
    border: 1px solid {menu_border} !important;
    box-shadow: {pal["menu_shadow"]} !important;
    border-radius: 8px !important;
  }}

  [data-testid="stSelectboxVirtualDropdown"] li[role="option"],
  [data-testid="stVirtualDropdown"] li[role="option"],
  [data-testid="stMultiSelectVirtualDropdown"] li[role="option"],
  div[data-baseweb="menu"] li,
  div[data-baseweb="menu"] li[role="option"],
  div[role="listbox"] [role="option"] {{
    background-color: transparent !important;
    color: {menu_text} !important;
  }}

  [data-testid="stSelectboxVirtualDropdown"] li[role="option"]:hover,
  [data-testid="stVirtualDropdown"] li[role="option"]:hover,
  [data-testid="stMultiSelectVirtualDropdown"] li[role="option"]:hover,
  div[data-baseweb="menu"] li:hover,
  div[role="listbox"] [role="option"]:hover {{
    background-color: {hover_bg} !important;
    color: {hover_text} !important;
  }}

  [data-testid="stSelectboxVirtualDropdown"] li[role="option"][aria-selected="true"],
  [data-testid="stVirtualDropdown"] li[role="option"][aria-selected="true"],
  [data-testid="stMultiSelectVirtualDropdown"] li[role="option"][aria-selected="true"],
  div[data-baseweb="menu"] li[aria-selected="true"],
  div[role="listbox"] [role="option"][aria-selected="true"] {{
    background-color: {selected_bg} !important;
    color: {selected_text} !important;
  }}

  /* Date/time pickers, tooltips, popovers — also portaled to body */
  [data-testid="stDateInputPopover"],
  [data-testid="stDateInputCalendar"],
  [data-testid="stTimeInputPopover"],
  [data-testid="stTooltip"],
  [data-testid="stTooltipIcon"],
  [data-baseweb="tooltip"],
  div[data-baseweb="calendar"],
  div[data-baseweb="calendar"] header,
  div[data-baseweb="calendar"] div {{
    background-color: {menu_bg} !important;
    color: {menu_text} !important;
    border-color: {menu_border} !important;
  }}

  div[data-baseweb="calendar"] abbr,
  div[data-baseweb="calendar"] span,
  div[data-baseweb="calendar"] button {{
    color: {menu_text} !important;
  }}

  div[data-baseweb="calendar"] [aria-selected="true"],
  div[data-baseweb="calendar"] [data-baseweb="calendar-day"]:hover {{
    background-color: {hover_bg} !important;
    color: {hover_text} !important;
  }}

  [data-baseweb="tooltip"] > div,
  [data-baseweb="tooltip"] div,
  [data-testid="stTooltip"] > div,
  [data-testid="stTooltip"] p {{
    background-color: transparent !important;
    color: inherit !important;
    border: none !important;
    box-shadow: none !important;
  }}
</style>
"""


def build_widget_css(theme: Theme) -> str:
    """Native Streamlit widgets not fully covered by shell/portal CSS."""
    th = theme
    pal = _widget_palette(theme)
    widget_bg = pal["widget_bg"]
    widget_text = pal["widget_text"]
    widget_border = pal["widget_border"]
    widget_muted = pal["widget_muted"]
    chip_bg = pal["chip_bg"]
    chip_text = pal["chip_text"]
    toggle_on = th.accent
    slider_fill = th.accent
    return f"""
<style id="stats-widget-theme">
  /* Radio & checkbox */
  .stApp [data-testid="stRadio"] label,
  .stApp [data-testid="stRadio"] [role="radiogroup"] label,
  .stApp [data-testid="stCheckbox"] label,
  .stApp [data-testid="stCheckbox"] span,
  .stApp [data-testid="stToggle"] label,
  .stApp [data-testid="stToggle"] span,
  .stApp [data-testid="stToggle"] p {{
    color: {widget_text} !important;
  }}

  .stApp [data-testid="stRadio"] [data-baseweb="radio"] svg,
  .stApp [data-testid="stCheckbox"] [data-baseweb="checkbox"] svg {{
    fill: {toggle_on} !important;
  }}

  /* Toggle track */
  .stApp [data-testid="stToggle"] [data-baseweb="toggle"] > div {{
    background-color: {th.progress_track} !important;
  }}
  .stApp [data-testid="stToggle"] [data-baseweb="toggle"][aria-checked="true"] > div {{
    background-color: {toggle_on} !important;
  }}

  /* Slider */
  .stApp [data-testid="stSlider"] label,
  .stApp [data-testid="stSlider"] [data-testid="stTickBarMin"],
  .stApp [data-testid="stSlider"] [data-testid="stTickBarMax"] {{
    color: {widget_muted} !important;
  }}
  .stApp [data-testid="stSlider"] [data-baseweb="slider"] div[data-testid="stThumbValue"] {{
    color: {widget_text} !important;
    background-color: {widget_bg} !important;
    border: 1px solid {widget_border} !important;
  }}
  .stApp [data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {{
    background: {slider_fill} !important;
  }}
  .stApp [data-testid="stSlider"] [data-baseweb="slider"] > div > div {{
    background: {th.progress_track} !important;
  }}

  /* Number input steppers */
  .stApp [data-testid="stNumberInput"] label {{
    color: {widget_text} !important;
  }}
  .stApp [data-testid="stNumberInput"] input {{
    color: {widget_text} !important;
    background-color: {widget_bg} !important;
  }}
  .stApp [data-testid="stNumberInput"] button {{
    background-color: {widget_bg} !important;
    color: {widget_text} !important;
    border-color: {widget_border} !important;
  }}

  /* Date / time triggers */
  .stApp [data-testid="stDateInput"] label,
  .stApp [data-testid="stTimeInput"] label {{
    color: {widget_text} !important;
  }}
  .stApp [data-testid="stDateInput"] input,
  .stApp [data-testid="stTimeInput"] input {{
    color: {widget_text} !important;
    background-color: {widget_bg} !important;
  }}

  /* Alerts — base card surface */
  .stApp [data-testid="stAlert"],
  section[data-testid="stSidebar"] [data-testid="stAlert"] {{
    background-color: {th.card_bg} !important;
    color: {widget_text} !important;
    border: 1px solid {th.card_border} !important;
    border-radius: 10px !important;
  }}
  .stApp [data-testid="stAlert"] [data-testid="stMarkdownContainer"] p,
  .stApp [data-testid="stAlert"] [data-testid="stMarkdownContainer"] span,
  section[data-testid="stSidebar"] [data-testid="stAlert"] p {{
    color: inherit !important;
  }}

  /* Alert variants (override base) */
  .stApp [data-testid="stAlert"]:has(svg[aria-label="Info"]) {{
    background-color: {pal["alert_info_bg"]} !important;
    color: {pal["alert_info_text"]} !important;
  }}
  .stApp [data-testid="stAlert"]:has(svg[aria-label="Success"]) {{
    background-color: {pal["alert_success_bg"]} !important;
    color: {pal["alert_success_text"]} !important;
  }}
  .stApp [data-testid="stAlert"]:has(svg[aria-label="Warning"]) {{
    background-color: {pal["alert_warning_bg"]} !important;
    color: {pal["alert_warning_text"]} !important;
  }}
  .stApp [data-testid="stAlert"]:has(svg[aria-label="Error"]) {{
    background-color: {pal["alert_error_bg"]} !important;
    color: {pal["alert_error_text"]} !important;
  }}

  /* Dataframes */
  .stApp [data-testid="stDataFrame"],
  .stApp [data-testid="stDataFrame"] [data-testid="stTable"] {{
    background-color: {th.card_bg} !important;
    border: 1px solid {th.card_border} !important;
  }}
  .stApp [data-testid="stDataFrame"] table {{
    color: {widget_text} !important;
  }}
  .stApp [data-testid="stDataFrame"] th {{
    background-color: {pal["table_header_bg"]} !important;
    color: {widget_text} !important;
    border-color: {widget_border} !important;
  }}
  .stApp [data-testid="stDataFrame"] td {{
    color: {widget_text} !important;
    border-color: {widget_border} !important;
    background-color: {th.card_bg} !important;
  }}
  .stApp [data-testid="stDataFrame"] tr:hover td {{
    background-color: {pal["table_row_hover"]} !important;
  }}

  /* Chat messages (agent widget) */
  .stApp [data-testid="stChatMessage"],
  .stApp [data-testid="stChatMessageContent"] {{
    background-color: {th.card_bg} !important;
    color: {widget_text} !important;
    border: 1px solid {th.card_border} !important;
  }}

  /* Spinner / progress */
  .stApp [data-testid="stSpinner"] {{
    color: {th.accent} !important;
  }}
  .stApp [data-testid="stProgress"] > div > div {{
    background-color: {th.accent} !important;
  }}
  .stApp [data-testid="stProgress"] > div {{
    background-color: {th.progress_track} !important;
  }}

  /* Page links in sidebar nav */
  .stApp [data-testid="stPageLink"] a,
  section[data-testid="stSidebar"] [data-testid="stPageLink"] a {{
    color: {widget_text} !important;
  }}
  .stApp [data-testid="stPageLink"] a:hover,
  section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {{
    color: {th.accent} !important;
    background-color: {chip_bg} !important;
  }}

  /* Form submit area */
  .stApp [data-testid="stForm"] {{
    border-color: {th.card_border} !important;
  }}

  /* Text inputs — visible inset field (especially inside glass forms / login gate) */
  .stApp [data-testid="stTextInput"] [data-baseweb="input"],
  .stApp [data-testid="stTextInput"] [data-baseweb="input"] > div,
  .stApp [data-testid="stForm"] [data-testid="stTextInput"] [data-baseweb="input"] > div {{
    background-color: {pal["input_inset_bg"]} !important;
    border: 1.5px solid {pal["input_inset_border"]} !important;
    min-height: 2.85rem !important;
    border-radius: 10px !important;
    box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.12) !important;
  }}
  .stApp [data-testid="stTextInput"] input,
  .stApp [data-testid="stForm"] [data-testid="stTextInput"] input {{
    color: {widget_text} !important;
    -webkit-text-fill-color: {widget_text} !important;
    caret-color: {widget_text} !important;
    background-color: transparent !important;
    min-height: 2.5rem !important;
    font-size: 1rem !important;
  }}
  .stApp [data-testid="stTextInput"] input::placeholder {{
    color: {widget_muted} !important;
    opacity: 1 !important;
  }}
  .skopos-login-gate [data-testid="stForm"] {{
    padding: 1.25rem 1.35rem 1.1rem !important;
    max-width: 28rem !important;
    margin: 0 auto !important;
  }}

  /* File uploader */
  .stApp [data-testid="stFileUploader"] section {{
    background-color: {widget_bg} !important;
    border-color: {widget_border} !important;
  }}
  .stApp [data-testid="stFileUploader"] label,
  .stApp [data-testid="stFileUploader"] small {{
    color: {widget_muted} !important;
  }}
</style>
"""


def build_sidebar_layout_css(theme: Theme, *, collapsed: bool = False) -> str:
    """Sidebar layout — always expanded full panel."""
    th = theme
    pal = _widget_palette(theme)
    _ = collapsed
    return f"""
<style id="stats-sidebar-layout">
  [data-testid="stSidebarCollapseButton"],
  [data-testid="collapsedControl"] {{
    display: none !important;
  }}

  section[data-testid="stSidebar"] {{
    overflow-x: hidden !important;
    overflow-y: auto !important;
  }}

  section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{
    display: flex !important;
    flex-direction: column !important;
    min-height: calc(100vh - 1rem) !important;
    padding-top: 0.65rem !important;
    padding-bottom: 1rem !important;
  }}
  .skopos-sidebar-bottom-start {{
    margin-top: auto !important;
    padding-top: 1rem !important;
    border-top: 1px solid {th.border} !important;
    width: 100% !important;
  }}

  .skopos-hidden-page-links {{
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    padding: 0 !important;
    margin: -1px !important;
    overflow: hidden !important;
    clip: rect(0, 0, 0, 0) !important;
    white-space: nowrap !important;
    border: 0 !important;
  }}

  /* GA-style nav links */
  section[data-testid="stSidebar"] [data-testid="stPageLink"] a {{
    display: flex !important;
    align-items: center !important;
    gap: 0.65rem !important;
    border-radius: 0 999px 999px 0 !important;
    padding: 0.5rem 0.85rem 0.5rem 0.65rem !important;
    margin-right: 0.25rem !important;
    text-decoration: none !important;
    font-family: 'Outfit', system-ui, sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.88rem !important;
    min-height: 2.5rem !important;
    transition: background-color 0.18s ease, color 0.18s ease, box-shadow 0.18s ease !important;
  }}
  section[data-testid="stSidebar"] [data-testid="stPageLink"] a.skopos-nav-active {{
    background: color-mix(in srgb, {th.accent} 14%, transparent) !important;
    color: {th.accent} !important;
    font-weight: 600 !important;
  }}
  section[data-testid="stSidebar"] [data-testid="stPageLink"] a.skopos-nav-active [data-testid="stIconMaterial"],
  section[data-testid="stSidebar"] [data-testid="stPageLink"] a.skopos-nav-active svg {{
    color: {th.accent} !important;
    fill: {th.accent} !important;
  }}

  section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {{
    background-color: {pal["chip_bg"]} !important;
    color: {pal["chip_text"]} !important;
  }}

  .skopos-sidebar-brand {{
    margin: 0 0 1rem !important;
    padding: 0 0.15rem !important;
  }}
  section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:has(.skopos-sidebar-brand),
  section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:has(.skopos-sidebar-brand) p,
  section[data-testid="stSidebar"] [data-testid="stHtml"] .skopos-sidebar-brand,
  section[data-testid="stSidebar"] [data-testid="stHtml"] .skopos-sidebar-brand p {{
    margin: 0 !important;
    padding: 0 !important;
  }}
  .skopos-brand-row {{
    display: flex !important;
    flex-direction: row !important;
    align-items: flex-start !important;
    gap: 0.75rem !important;
    width: 100% !important;
  }}
  .skopos-logo-mark {{
    flex: 0 0 auto !important;
    width: 2.25rem !important;
    height: 2.25rem !important;
    display: block !important;
  }}
  .skopos-brand-text {{
    display: flex !important;
    flex-direction: column !important;
    gap: 0.28rem !important;
    min-width: 0 !important;
    flex: 1 1 auto !important;
    overflow: hidden !important;
  }}
  .skopos-sidebar-title {{
    display: block !important;
    font-family: 'Sora', 'Outfit', system-ui, sans-serif !important;
    font-size: 0.98rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.14em !important;
    text-transform: uppercase !important;
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1.2 !important;
    color: {th.text} !important;
    white-space: nowrap !important;
  }}
  .skopos-sidebar-tagline {{
    display: block !important;
    font-family: 'Outfit', system-ui, sans-serif !important;
    font-size: 0.72rem !important;
    font-weight: 400 !important;
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1.45 !important;
    color: {th.text_muted} !important;
    opacity: 1 !important;
    overflow-wrap: anywhere !important;
    word-break: break-word !important;
    hyphens: auto !important;
  }}
  html.skopos-sidebar-collapsed .skopos-brand-text,
  html.skopos-sidebar-collapsed .skopos-sidebar-title,
  html.skopos-sidebar-collapsed .skopos-sidebar-tagline {{
    display: none !important;
  }}
  html.skopos-sidebar-collapsed .skopos-brand-row {{
    justify-content: center !important;
  }}
  html.skopos-sidebar-collapsed .skopos-logo-mark {{
    width: 2rem !important;
    height: 2rem !important;
  }}
  .skopos-sidebar-divider {{
    height: 1px;
    margin: 0.65rem 0 0.85rem;
    background: {th.border};
  }}

  html.skopos-sidebar-expanded section[data-testid="stSidebar"],
  html.skopos-sidebar-expanded section[data-testid="stSidebar"] > div {{
    min-width: var(--skopos-sidebar-expanded-width) !important;
  }}

  html.skopos-sidebar-collapsed .skopos-sidebar-divider {{
    display: none !important;
  }}

  /* Collapsed: narrow icon rail */
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"],
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] > div {{
    width: var(--skopos-sidebar-collapsed) !important;
    min-width: var(--skopos-sidebar-collapsed) !important;
    max-width: var(--skopos-sidebar-collapsed) !important;
    padding-left: 0.35rem !important;
    padding-right: 0.35rem !important;
  }}

  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="stPageLink"] a {{
    justify-content: center !important;
    padding-left: 0.35rem !important;
    padding-right: 0.35rem !important;
  }}

  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="stPageLink"] p,
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="stPageLink"] a > span:not(:has(svg)) {{
    display: none !important;
  }}

  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="stPageLink"] a.skopos-nav-active {{
    background: {th.accent} !important;
    color: #ffffff !important;
    border-radius: 50% !important;
    width: 2.5rem !important;
    height: 2.5rem !important;
    min-height: 2.5rem !important;
    padding: 0 !important;
    margin: 0.2rem auto !important;
    box-shadow: 0 4px 14px color-mix(in srgb, {th.accent} 40%, transparent) !important;
  }}
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="stPageLink"] a.skopos-nav-active [data-testid="stIconMaterial"],
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="stPageLink"] a.skopos-nav-active svg {{
    color: #ffffff !important;
    fill: #ffffff !important;
  }}
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="stPageLink"] [data-testid="stIconMaterial"],
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="stPageLink"] svg {{
    display: inline-flex !important;
    font-size: 1.15rem !important;
    width: 1.15rem !important;
    height: 1.15rem !important;
    margin: 0 !important;
    flex-shrink: 0 !important;
  }}

  /* Hide page-specific sidebar widgets in icon-rail mode */
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="element-container"]:has([data-testid="stSelectbox"]),
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="element-container"]:has([data-testid="stMultiSelect"]),
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="element-container"]:has([data-testid="stSlider"]),
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="element-container"]:has([data-testid="stCheckbox"]),
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="element-container"]:has([data-testid="stToggle"]),
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="element-container"]:has([data-testid="stTextInput"]),
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="element-container"]:has([data-testid="stNumberInput"]),
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="element-container"]:has([data-testid="stExpander"]),
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="element-container"]:has([data-testid="stAlert"]),
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="element-container"]:has([data-testid="stRadio"]),
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="element-container"]:has(.sec-score-ring),
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="element-container"]:has([data-testid="stCaptionContainer"]),
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="element-container"]:has([data-testid="stMarkdownContainer"] h3),
  html.skopos-sidebar-collapsed section[data-testid="stSidebar"] [data-testid="element-container"]:has(hr) {{
    display: none !important;
  }}
</style>
<script>
(function() {{
  try {{
    document.documentElement.classList.remove("skopos-sidebar-collapsed");
    document.documentElement.classList.add("skopos-sidebar-expanded");
    localStorage.setItem("skopos-sidebar-collapsed", "0");
  }} catch (e) {{}}
}})();
</script>
"""


def build_app_css(theme: Theme) -> str:
    th = theme
    light_ui = is_light_theme(theme.id)
    pal = _widget_palette(theme)
    widget_bg = pal["widget_bg"]
    widget_text = pal["widget_text"]
    widget_border = pal["widget_border"]
    widget_muted = pal["widget_muted"]
    button_bg = "#ffffff" if light_ui else "#21262d"
    button_text = th.text
    button_border = widget_border
    header_bg = "rgba(255,255,255,0.85)" if light_ui else "rgba(13,17,23,0.92)"
    chip_bg = pal["chip_bg"]
    chip_text = pal["chip_text"]
    code_bg = "#0f1419"
    code_text = "#e6edf3"
    if theme.id == "premium":
        inline_code_bg = "#f5efe3"
        inline_code_text = "#5c4a1f"
        inline_code_border = "rgba(184,134,11,0.28)"
    elif light_ui:
        inline_code_bg = "#e8f0fe"
        inline_code_text = "#174ea6"
        inline_code_border = "rgba(66,133,244,0.22)"
    else:
        inline_code_bg = "#21262d"
        inline_code_text = "#79c0ff"
        inline_code_border = th.border

    return f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Sora:wght@500;600;700;800&display=swap');

  .stApp,
  [data-testid="stAppViewContainer"],
  [data-testid="stMain"],
  section.main {{
    font-family: 'Outfit', system-ui, -apple-system, sans-serif;
    color: {th.text} !important;
    background-color: {theme_shell_bg(th)} !important;
    background-image: {th.app_bg} !important;
    transition: none !important;
  }}

  /* Legacy selector kept for older Streamlit builds */
  .stApp {{
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    color: {th.text};
    background-color: {theme_shell_bg(th)};
    background-image: {th.app_bg};
  }}

  header[data-testid="stHeader"] {{
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
  }}

  section[data-testid="stSidebar"] {{
    background: {th.sidebar_bg} !important;
    border-right: 1px solid {th.border};
  }}
  section[data-testid="stSidebar"] .stMarkdown,
  section[data-testid="stSidebar"] label,
  section[data-testid="stSidebar"] p,
  section[data-testid="stSidebar"] span,
  section[data-testid="stSidebar"] small {{
    color: {th.text} !important;
  }}

  /* Hide Streamlit auto page list (English filenames); we render translated nav. */
  [data-testid="stSidebarNav"],
  [data-testid="stSidebarNav"] + div {{
    display: none !important;
  }}

  /* Streamlit deploy / ⋮ menu — SKOPOS uses sidebar + top bar */
  [data-testid="stToolbarActions"],
  [data-testid="stMainMenu"],
  #MainMenu {{
    display: none !important;
  }}

  /* Streamlit markdown / captions / labels */
  .stApp [data-testid="stMarkdownContainer"],
  .stApp [data-testid="stMarkdownContainer"] p,
  .stApp [data-testid="stMarkdownContainer"] li,
  .stApp [data-testid="stMarkdownContainer"] span,
  .stApp [data-testid="stMarkdownContainer"] h1,
  .stApp [data-testid="stMarkdownContainer"] h2,
  .stApp [data-testid="stMarkdownContainer"] h3,
  .stApp [data-testid="stMarkdownContainer"] h4,
  .stApp [data-testid="stMarkdownContainer"] h5,
  .stApp [data-testid="stMarkdownContainer"] h6,
  .stApp [data-testid="stCaptionContainer"],
  .stApp [data-testid="stCaptionContainer"] p,
  .stApp label[data-testid="stWidgetLabel"],
  .stApp label[data-testid="stWidgetLabel"] p {{
    color: {th.text} !important;
  }}

  .stApp [data-testid="stCaptionContainer"] p {{
    color: {th.text_muted} !important;
  }}

  /* Inputs, selects, multiselects */
  .stApp [data-baseweb="input"] > div,
  .stApp [data-baseweb="select"] > div,
  .stApp [data-baseweb="select"] div[data-baseweb="select"] > div,
  .stApp [data-baseweb="textarea"] > div,
  .stApp [data-baseweb="popover"] [data-baseweb="input"] > div,
  .stApp [data-baseweb="popover"] [data-baseweb="select"] > div {{
    background-color: {widget_bg} !important;
    color: {widget_text} !important;
    border-color: {widget_border} !important;
  }}

  /* Selectbox selected value (BaseWeb + React Aria combobox) */
  .stApp [data-testid="stSelectbox"] [data-baseweb="select"] > div,
  .stApp [data-testid="stSelectbox"] [data-baseweb="select"] span,
  .stApp [data-testid="stSelectbox"] input,
  .stApp [data-testid="stSelectbox"] [role="combobox"],
  section[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] > div,
  section[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] span,
  section[data-testid="stSidebar"] [data-testid="stSelectbox"] input,
  section[data-testid="stSidebar"] [data-testid="stSelectbox"] [role="combobox"] {{
    color: {widget_text} !important;
    -webkit-text-fill-color: {widget_text} !important;
    caret-color: {widget_text} !important;
    background-color: {widget_bg} !important;
    opacity: 1 !important;
  }}

  .stApp [data-baseweb="select"] span {{
    color: {widget_text} !important;
    -webkit-text-fill-color: {widget_text} !important;
  }}
  .stApp input, .stApp textarea {{
    color: {widget_text} !important;
    background-color: {widget_bg} !important;
  }}
  .stApp [data-testid="stTextInput"] input {{
    background-color: transparent !important;
  }}
  .stApp [data-baseweb="select"] svg {{
    fill: {widget_muted} !important;
  }}

  /* Multiselect chips */
  .stApp [data-baseweb="tag"] {{
    background-color: {chip_bg} !important;
    color: {chip_text} !important;
  }}

  /* Buttons */
  .stApp button[kind="secondary"],
  .stApp button[data-testid="baseButton-secondary"],
  .stApp .stButton > button {{
    background-color: {button_bg} !important;
    color: {button_text} !important;
    border: 1px solid {button_border} !important;
  }}
  .stApp button[kind="primary"],
  .stApp button[data-testid="baseButton-primary"] {{
    background-color: {th.accent} !important;
    color: #ffffff !important;
    border: none !important;
  }}

  /* Expanders */
  .stApp [data-testid="stExpander"] details {{
    background: {th.card_bg} !important;
    border: 1px solid {th.card_border} !important;
    border-radius: 12px !important;
  }}

  .block-container {{
    padding-top: 1rem !important;
    padding-bottom: 3rem !important;
    max-width: 1400px !important;
    margin-left: 0 !important;
    margin-right: auto !important;
  }}

  /* Quick Start — centered step rail */
  .skopos-wizard-steps {{
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    align-items: center;
    gap: 0.4rem 0.75rem;
    margin: 0.5rem 0 1rem;
    text-align: center;
  }}
  .skopos-wizard-step {{
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.82rem;
    font-weight: 500;
    color: {th.text_muted};
    padding: 0.28rem 0.65rem;
    border-radius: 999px;
    border: 1px solid transparent;
    background: transparent;
    white-space: nowrap;
  }}
  .skopos-wizard-step.is-done {{
    color: {th.accent2};
    border-color: color-mix(in srgb, {th.accent2} 35%, transparent);
    background: color-mix(in srgb, {th.accent2} 10%, transparent);
  }}
  .skopos-wizard-step.is-current {{
    color: {th.accent};
    font-weight: 700;
    border-color: color-mix(in srgb, {th.accent} 45%, transparent);
    background: color-mix(in srgb, {th.accent} 14%, transparent);
    box-shadow: 0 4px 16px color-mix(in srgb, {th.accent} 22%, transparent);
  }}
  .skopos-wizard-step.is-todo {{
    opacity: 0.72;
  }}

  @keyframes fadeUp {{
    from {{ opacity: 0; transform: translateY(18px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  @keyframes fadeIn {{
    from {{ opacity: 0; }}
    to   {{ opacity: 1; }}
  }}
  @keyframes glowPulse {{
    0%, 100% {{ opacity: 0.55; }}
    50%      {{ opacity: 1; }}
  }}

  .hero-title {{
    font-size: 2.1rem;
    font-weight: 700;
    font-family: 'Sora', 'Outfit', system-ui, sans-serif;
    letter-spacing: -0.02em;
    background: {th.hero_gradient};
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.25rem;
  }}
  .hero-sub {{
    color: {th.text_muted};
    font-size: 0.95rem;
    margin-bottom: 1.5rem;
  }}

  .theme-badge {{
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: {th.text_muted};
    padding: 0.35rem 0.65rem;
    border-radius: 999px;
    border: 1px solid {th.border};
    background: {th.card_bg};
    margin-bottom: 0.75rem;
  }}

  div[data-testid="stMetric"] {{
    background: {th.metric_bg};
    border: 1px solid {th.metric_border};
    border-radius: 16px;
    padding: 1.25rem 1.5rem !important;
    box-shadow: {th.card_shadow};
    transition: transform 0.25s ease, box-shadow 0.25s ease;
    backdrop-filter: blur(8px);
  }}
  div[data-testid="stMetric"]:hover {{
    transform: translateY(-3px);
    box-shadow: {th.card_hover_shadow};
  }}
  div[data-testid="stMetric"] label {{
    color: {th.metric_label} !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }}
  div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
    color: {th.metric_value} !important;
    font-size: 1.75rem !important;
    font-weight: 700 !important;
  }}

  div[data-testid="stTabs"] [data-baseweb="tab-list"] {{
    gap: 0.5rem;
    background: transparent;
    border-bottom: 2px solid {th.border};
    padding-bottom: 0;
  }}
  div[data-testid="stTabs"] [data-baseweb="tab"] {{
    padding: 0.75rem 1.25rem;
    font-weight: 500;
    border-radius: 8px 8px 0 0;
    color: {th.text_muted};
  }}
  div[data-testid="stTabs"] [aria-selected="true"] {{
    background: {th.tab_active_bg};
    color: {th.text} !important;
  }}

  .section-head {{
    font-size: 1.15rem;
    font-weight: 600;
    color: {th.text};
    margin: 2rem 0 1rem 0;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid transparent;
    border-image: {th.section_border} 1;
  }}

  div[data-testid="stVerticalBlockBorderWrapper"] {{
    border-radius: 16px !important;
    border: 1px solid {th.card_border} !important;
    box-shadow: {th.card_shadow} !important;
    padding: 1.5rem !important;
    margin-bottom: 1.5rem !important;
    background: {th.card_bg} !important;
    transition: box-shadow 0.3s ease, transform 0.25s ease;
    backdrop-filter: blur(10px);
  }}
  div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
    box-shadow: {th.card_hover_shadow} !important;
  }}

  .stPlotlyChart {{
    margin-top: 0.5rem;
    margin-bottom: 0.5rem;
    min-height: 220px;
  }}
  div[data-testid="column"] .stPlotlyChart {{
    min-width: 160px;
  }}

  h1, h2, h3, h4, h5, h6, p, label {{
    color: {th.text} !important;
  }}

  /* Do not let global span styling break st.code / syntax highlighting */
  .stApp span {{
    color: inherit;
  }}
  .stApp [data-testid="stSelectbox"] span,
  section[data-testid="stSidebar"] [data-testid="stSelectbox"] span {{
    color: {widget_text} !important;
    -webkit-text-fill-color: {widget_text} !important;
  }}

  .stApp [data-testid="stCode"],
  .stApp [data-testid="stCodeBlock"],
  .stApp .stCode {{
    border-radius: 10px !important;
  }}
  .stApp [data-testid="stCode"] pre,
  .stApp [data-testid="stCode"] code,
  .stApp [data-testid="stCodeBlock"] pre,
  .stApp [data-testid="stCodeBlock"] code,
  .stApp .stCode pre,
  .stApp .stCode code {{
    background-color: {code_bg} !important;
    color: {code_text} !important;
    border: 1px solid {th.border} !important;
    font-size: 0.82rem !important;
    line-height: 1.45 !important;
  }}
  .stApp [data-testid="stCode"] pre *,
  .stApp [data-testid="stCode"] code *,
  .stApp [data-testid="stCodeBlock"] pre *,
  .stApp [data-testid="stCodeBlock"] code *,
  .stApp .stCode pre *,
  .stApp .stCode code * {{
    color: {code_text} !important;
  }}

  /* Inline `code` in markdown / expander labels (SSH host badges) */
  .stApp [data-testid="stMarkdownContainer"] :not(pre) > code,
  .stApp [data-testid="stExpander"] summary code,
  .stApp details[data-testid="stExpander"] summary code,
  .stApp [data-baseweb="accordion"] summary code {{
    background-color: {inline_code_bg} !important;
    color: {inline_code_text} !important;
    border: 1px solid {inline_code_border} !important;
    border-radius: 6px !important;
    padding: 0.12rem 0.45rem !important;
    font-size: 0.82em !important;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
  }}

  .stApp [data-testid="stException"],
  .stApp [data-testid="stException"] pre,
  .stApp [data-testid="stException"] code,
  .stApp [data-testid="stException"] p,
  .stApp [data-testid="stException"] span {{
    color: #3b1219 !important;
  }}

  .hero-sub, .sec-remark {{
    color: {th.text_muted} !important;
  }}

  .stDataFrame, [data-testid="stDataFrame"] {{
    border-radius: 12px;
    overflow: hidden;
  }}

  hr.section-divider {{
    border: none;
    height: 1px;
    background: {th.divider};
    margin: 2.5rem 0;
  }}

  /* Mobile-first responsive layout */
  @media (max-width: 768px) {{
    .hero-title {{ font-size: 1.55rem !important; }}
    .hero-sub {{ font-size: 0.92rem !important; }}
    div[data-testid="column"] {{
      min-width: 100% !important;
      flex: 1 1 100% !important;
    }}
    div[data-testid="stHorizontalBlock"] {{
      flex-wrap: wrap !important;
      gap: 0.5rem !important;
    }}
    div[data-testid="stTabs"] [data-baseweb="tab"] {{
      padding: 0.5rem 0.65rem !important;
      font-size: 0.82rem !important;
    }}
    .stPlotlyChart {{
      min-height: 280px !important;
    }}
    .sec-score-value {{ font-size: 2rem !important; }}
    .sec-alert-counts {{
      flex-wrap: wrap;
    }}
    .sec-count-pill {{
      flex: 1 1 45%;
    }}
    section[data-testid="stSidebar"] {{
      min-width: 280px;
    }}
    html.skopos-sidebar-collapsed section[data-testid="stSidebar"] {{
      min-width: var(--skopos-sidebar-collapsed) !important;
      max-width: var(--skopos-sidebar-collapsed) !important;
      width: var(--skopos-sidebar-collapsed) !important;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"] {{
      padding: 1rem !important;
    }}
    div[data-testid="stSidebar"] .stButton > button,
    div[data-testid="stSidebar"] [data-testid="stPageLink"] a {{
      min-height: 44px;
    }}
    .main .block-container {{
      padding-left: 1rem !important;
      padding-right: 1rem !important;
      max-width: 100% !important;
    }}
    div[data-testid="stForm"] button {{
      min-height: 44px;
    }}
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input {{
      font-size: 16px !important;
    }}
  }}
  @media (max-width: 480px) {{
    .hero-title {{ font-size: 1.35rem !important; }}
    div[data-testid="stMetric"] {{
      padding: 0.35rem 0 !important;
    }}
    .sec-count-pill {{
      flex: 1 1 100%;
    }}
    section[data-testid="stSidebar"] {{
      min-width: 0 !important;
    }}
    .stButton > button {{
      min-height: 44px;
      width: 100%;
    }}
  }}
</style>
"""


def build_agent_widget_css(theme: Theme) -> str:
    th = theme
    agent = _agent_widget_selector()
    fragment_root = (
        'section.main [data-testid="stFragment"]:has(.stats-agent-root), '
        'section.main div[data-testid="stVerticalBlock"]:has(.stats-agent-root)'
    )
    fab_host = (
        'section.main div.element-container:has(.stats-agent-fab-slot), '
        'section.main div.element-container:has(.stats-agent-fab-slot) + div.element-container, '
        'section.main [data-testid="stFragment"]:has(.stats-agent-fab-slot), '
        f'{fragment_root}:has(.stats-agent-root--closed)'
    )
    fab_btn = (
        'section.main div.element-container:has(.stats-agent-fab-slot) + div.element-container [data-testid="stButton"] > button, '
        'section.main [data-testid="stFragment"]:has(.stats-agent-fab-slot) [data-testid="stButton"] > button, '
        f'{fragment_root}:has(.stats-agent-root--closed) [data-testid="stButton"] > button'
    )
    panel_host = (
        f'{agent}:has(.stats-agent-panel), '
        f'{fragment_root}:has(.stats-agent-panel), '
        'section.main div[data-testid="stVerticalBlock"]:has(.stats-agent-panel), '
        'section.main [data-testid="stFragment"]:has(.stats-agent-panel)'
    )
    return f"""
<style>
  /* Agent must not push page layout — host column is zero-height, widget is fixed */
  section.main div[data-testid="stVerticalBlock"]:has(.stats-agent-root),
  section.main div[data-testid="stVerticalBlock"]:has(.stats-agent-anchor) {{
    height: 0 !important;
    min-height: 0 !important;
    max-height: 0 !important;
    overflow: visible !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
    background: transparent !important;
  }}

  {fragment_root} {{
    position: fixed !important;
    z-index: 999999 !important;
    margin: 0 !important;
    padding: 0 !important;
    background: transparent !important;
    border: none !important;
    overflow: visible !important;
  }}

  {fragment_root}:has(.stats-agent-root--closed) {{
    bottom: 2rem !important;
    right: 1.25rem !important;
    left: auto !important;
    top: auto !important;
    width: auto !important;
    max-height: none !important;
  }}

  {fragment_root}:has(.stats-agent-root--open) {{
    bottom: 1.25rem !important;
    right: 1.25rem !important;
    left: auto !important;
    top: auto !important;
    width: min(22rem, calc(100vw - 2.5rem)) !important;
    max-height: min(640px, calc(100vh - 2.5rem)) !important;
    overflow-x: hidden !important;
    overflow-y: auto !important;
    background: rgba(2, 6, 23, 0.95) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 1rem !important;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.55) !important;
    backdrop-filter: blur(16px) !important;
    -webkit-backdrop-filter: blur(16px) !important;
    animation: statsAgentIn 0.22s ease-out;
    color: #e2e8f0 !important;
  }}

  section.main div.element-container:has(.stats-agent-anchor),
  section.main div.element-container:has(.stats-agent-fab-slot),
  section.main div[data-testid="stVerticalBlockBorderWrapper"]:has(.stats-agent-anchor),
  section.main div[data-testid="stVerticalBlockBorderWrapper"]:has(.stats-agent-fab-slot) {{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
  }}
  section.main div[data-testid="stVerticalBlock"]:has(.stats-agent-anchor),
  section.main div[data-testid="stVerticalBlock"]:has(.stats-agent-fab-slot) {{
    min-height: 0 !important;
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
  }}

  /* Collapsed FAB — robust selectors (@st.fragment may skip innermost :has() chain) */
  {fab_host} {{
    position: fixed !important;
    bottom: 2rem !important;
    right: 1.25rem !important;
    left: auto !important;
    top: auto !important;
    z-index: 999999 !important;
    width: auto !important;
    max-height: none !important;
    overflow: visible !important;
    padding: 0 !important;
    margin: 0 !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    min-height: 0 !important;
  }}
  section.main div.element-container:has(.stats-agent-fab-slot) {{
    display: none !important;
  }}

  {fab_btn} {{
    width: 3.5rem !important;
    height: 3.5rem !important;
    min-width: 3.5rem !important;
    min-height: 3.5rem !important;
    border-radius: 999px !important;
    padding: 0 !important;
    font-size: 0 !important;
    line-height: 0 !important;
    color: transparent !important;
    background: linear-gradient(145deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 27, 75, 0.95) 100%) !important;
    border: 1px solid rgba(34, 211, 238, 0.4) !important;
    box-shadow: 0 10px 32px rgba(8, 47, 73, 0.45) !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease !important;
    position: relative !important;
  }}

  {fab_btn}::after {{
    content: "";
    position: absolute;
    inset: 0;
    margin: auto;
    width: 1.35rem;
    height: 1.35rem;
    background-repeat: no-repeat;
    background-position: center;
    background-size: contain;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%2367e8f9' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M7.9 20A9 9 0 1 0 4 16.1L2 22Z'/%3E%3C/svg%3E");
    pointer-events: none;
  }}

  {fab_btn}:hover {{
    transform: scale(1.05) !important;
    border-color: rgba(34, 211, 238, 0.65) !important;
    color: #fff !important;
    box-shadow: 0 14px 40px rgba(8, 47, 73, 0.55) !important;
  }}

  /* Floating security agent — factory SupportWidget-style dark glass panel */
  {panel_host} {{
    position: fixed !important;
    bottom: 1.25rem !important;
    right: 1.25rem !important;
    left: auto !important;
    top: auto !important;
    z-index: 999999 !important;
    width: min(22rem, calc(100vw - 2.5rem)) !important;
    max-height: min(640px, calc(100vh - 2.5rem)) !important;
    overflow-x: hidden !important;
    overflow-y: auto !important;
    margin: 0 !important;
    padding: 0 !important;
    background: rgba(2, 6, 23, 0.95) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 1rem !important;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.55) !important;
    backdrop-filter: blur(16px) !important;
    -webkit-backdrop-filter: blur(16px) !important;
    animation: statsAgentIn 0.22s ease-out;
    color: #e2e8f0 !important;
  }}

  @keyframes statsAgentIn {{
    from {{ opacity: 0; transform: translateY(12px) scale(0.96); }}
    to {{ opacity: 1; transform: translateY(0) scale(1); }}
  }}

  /* Legacy innermost-block FAB rules (open panel uses panel_host above) */
  {agent}:not(:has(.stats-agent-panel)) {{
    position: fixed !important;
    bottom: 2rem !important;
    right: 1.25rem !important;
    left: auto !important;
    top: auto !important;
    z-index: 999999 !important;
    width: auto !important;
    max-height: none !important;
    overflow: visible !important;
    padding: 0 !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    animation: none !important;
  }}

  {agent}:not(:has(.stats-agent-panel)) [data-testid="stButton"] > button {{
    width: 3.5rem !important;
    height: 3.5rem !important;
    min-width: 3.5rem !important;
    min-height: 3.5rem !important;
    border-radius: 999px !important;
    padding: 0 !important;
    font-size: 1.35rem !important;
    line-height: 1 !important;
    background: linear-gradient(145deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 27, 75, 0.95) 100%) !important;
    color: #67e8f9 !important;
    border: 1px solid rgba(34, 211, 238, 0.4) !important;
    box-shadow: 0 10px 32px rgba(8, 47, 73, 0.45) !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease !important;
  }}

  {agent}:not(:has(.stats-agent-panel)) [data-testid="stButton"] > button:hover {{
    transform: scale(1.05) !important;
    border-color: rgba(34, 211, 238, 0.65) !important;
    color: #fff !important;
    box-shadow: 0 14px 40px rgba(8, 47, 73, 0.55) !important;
  }}

  {agent}:has(.stats-agent-panel) > div.element-container:first-of-type {{
    display: none !important;
  }}

  {agent}:has(.stats-agent-panel) [data-testid="stHorizontalBlock"]:first-of-type {{
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    padding: 0.75rem 1rem 0.65rem;
    margin: 0 !important;
    align-items: center !important;
  }}

  {agent} .stats-agent-head-title {{
    font-size: 0.875rem;
    font-weight: 600;
    color: #fff;
    letter-spacing: -0.01em;
  }}

  {agent} .stats-agent-head-sub,
  {fragment_root} .stats-agent-head-sub {{
    font-size: 0.68rem;
    color: #94a3b8;
    margin-top: 0.15rem;
    line-height: 1.35;
  }}

  {agent} .stats-agent-intro,
  {fragment_root} .stats-agent-intro {{
    margin: 0 0.85rem 0.65rem;
    font-size: 0.75rem;
    line-height: 1.45;
    color: #64748b;
  }}

  {agent} .stats-agent-footnote,
  {fragment_root} .stats-agent-footnote {{
    margin: 0;
    font-size: 0.62rem;
    color: #64748b;
    line-height: 1.3;
  }}

  {fragment_root}:has(.stats-agent-root--open) [data-testid="stHorizontalBlock"]:first-of-type {{
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    padding: 0.65rem 0.75rem 0.5rem !important;
    margin: 0 !important;
    align-items: flex-start !important;
  }}

  {fragment_root}:has(.stats-agent-root--open) [data-testid="stExpander"],
  {fragment_root}:has(.stats-agent-root--open) [data-testid="stTextArea"],
  {fragment_root}:has(.stats-agent-root--open) [data-testid="stHorizontalBlock"] {{
    color: #e2e8f0 !important;
  }}

  {fragment_root}:has(.stats-agent-root--open) [data-testid="column"] {{
    padding: 0 0.15rem !important;
  }}

  {agent}:has(.stats-agent-panel) [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child [data-testid="stButton"] > button {{
    min-width: 2rem !important;
    width: 2rem !important;
    height: 2rem !important;
    min-height: 2rem !important;
    padding: 0 !important;
    border-radius: 0.5rem !important;
    background: transparent !important;
    color: #94a3b8 !important;
    border: none !important;
    font-size: 1rem !important;
    box-shadow: none !important;
  }}

  {agent}:has(.stats-agent-panel) [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child [data-testid="stButton"] > button:hover {{
    background: rgba(255, 255, 255, 0.08) !important;
    color: #fff !important;
  }}

  {agent}:has(.stats-agent-panel) [data-baseweb="select"] {{
    background: rgba(0, 0, 0, 0.25) !important;
    border-color: rgba(255, 255, 255, 0.12) !important;
    color: #cbd5e1 !important;
    font-size: 0.72rem !important;
    min-height: 2rem !important;
  }}

  {agent} .stats-agent-model {{
    margin: 0 1rem 0.35rem;
    font-size: 0.68rem;
    color: #64748b;
    line-height: 1.3;
  }}

  {agent}:has(.stats-agent-panel) [data-testid="stCaptionContainer"] {{
    padding: 0 1rem 0.35rem;
    color: #fbbf24 !important;
  }}

  {agent} .stats-agent-messages {{
    max-height: 18rem;
    overflow-y: auto;
    padding: 0.75rem 0.75rem 0.35rem;
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
  }}

  {agent} .stats-agent-row {{
    display: flex;
  }}

  {agent} .stats-agent-row--user {{
    justify-content: flex-end;
  }}

  {agent} .stats-agent-row--assistant {{
    justify-content: flex-start;
  }}

  {agent} .stats-agent-bubble {{
    max-width: 92%;
    border-radius: 0.75rem;
    padding: 0.5rem 0.75rem;
    font-size: 0.875rem;
    line-height: 1.45;
    word-break: break-word;
  }}

  {agent} .stats-agent-bubble--user {{
    background: rgba(8, 145, 178, 0.35);
    color: #ecfeff;
    border: 1px solid rgba(34, 211, 238, 0.25);
  }}

  {agent} .stats-agent-bubble--assistant {{
    background: rgba(255, 255, 255, 0.06);
    color: #e2e8f0;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }}

  {agent} .stats-agent-suggestions-label {{
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #64748b;
    margin: 0.15rem 0.75rem 0.45rem;
  }}

  {agent}:has(.stats-agent-panel) .stats-agent-suggestions-label ~ div [data-testid="stButton"] > button {{
    border-radius: 999px !important;
    font-size: 0.68rem !important;
    padding: 0.4rem 0.6rem !important;
    min-height: 2rem !important;
    height: auto !important;
    white-space: normal !important;
    line-height: 1.25 !important;
    text-align: left !important;
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(255, 255, 255, 0.14) !important;
    color: #cbd5e1 !important;
    box-shadow: none !important;
  }}

  {agent}:has(.stats-agent-panel) .stats-agent-suggestions-label ~ div [data-testid="stButton"] > button:hover {{
    background: rgba(255, 255, 255, 0.1) !important;
    color: #fff !important;
  }}

  {agent}:has(.stats-agent-footer) [data-testid="stTextArea"] {{
    border-top: 1px solid rgba(255, 255, 255, 0.1) !important;
    padding: 0.65rem 0.75rem 0.35rem !important;
    background: transparent !important;
  }}

  {agent}:has(.stats-agent-footer) [data-testid="stTextArea"] textarea {{
    background: rgba(0, 0, 0, 0.3) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 0.75rem !important;
    color: #fff !important;
    font-size: 0.875rem !important;
    min-height: 5.5rem !important;
    resize: none !important;
  }}

  {agent}:has(.stats-agent-footer) [data-testid="stTextArea"] textarea::placeholder {{
    color: #64748b !important;
  }}

  {agent}:has(.stats-agent-footer) [data-testid="stTextArea"] label {{
    display: none !important;
  }}

  {agent}:has(.stats-agent-panel) [data-testid="stButton"] > button[kind="primary"] {{
    margin: 0 0.75rem 0.5rem !important;
    border-radius: 0.5rem !important;
    background: rgba(8, 145, 178, 0.85) !important;
    border: none !important;
    color: #fff !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    min-height: 2.25rem !important;
    box-shadow: none !important;
  }}

  {agent}:has(.stats-agent-panel) [data-testid="stButton"] > button[kind="primary"]:hover {{
    background: rgba(34, 211, 238, 0.75) !important;
  }}

  {agent}:has(.stats-agent-panel) [data-testid="stButton"] > button[kind="secondary"] {{
    margin: 0 0.75rem 0.75rem !important;
    border-radius: 0.5rem !important;
    background: rgba(255, 255, 255, 0.06) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    color: #94a3b8 !important;
    font-size: 0.72rem !important;
    min-height: 2rem !important;
    box-shadow: none !important;
  }}

  @media (max-width: 768px) {{
    {panel_host} {{
      width: calc(100vw - 1rem) !important;
      right: 0.5rem !important;
      left: 0.5rem !important;
      bottom: 0.5rem !important;
      max-height: calc(100vh - 1rem) !important;
    }}
    {fab_host} {{
      right: 0.75rem !important;
      bottom: 0.75rem !important;
    }}
  }}
</style>
"""


def build_security_css(theme: Theme) -> str:
    th = theme
    return f"""
<style>
  .sec-score-ring {{
    text-align: center;
    padding: 1rem 0.5rem;
    border-radius: 16px;
    background: {th.sec_ring_bg};
    border: 1px solid {th.sec_ring_border};
    margin-bottom: 0.75rem;
    box-shadow: {th.card_shadow};
  }}
  .sec-score-value {{
    font-size: 2.5rem;
    font-weight: 800;
    line-height: 1;
  }}
  .sec-score-grade {{
    font-size: 1.1rem;
    font-weight: 600;
    opacity: 0.85;
  }}
  .sec-alert-critical {{
    background: {th.sec_alert_crit_bg};
    border-left: 4px solid #EA4335;
    padding: 0.75rem 1rem;
    border-radius: 8px;
    margin-bottom: 0.5rem;
    color: {th.text};
  }}
  .sec-alert-high {{
    background: {th.sec_alert_high_bg};
    border-left: 4px solid #FF6D00;
    padding: 0.75rem 1rem;
    border-radius: 8px;
    margin-bottom: 0.5rem;
    color: {th.text};
  }}
  .sec-alert-medium {{
    background: {th.sec_alert_med_bg};
    border-left: 4px solid #FBBC04;
    padding: 0.75rem 1rem;
    border-radius: 8px;
    margin-bottom: 0.5rem;
    color: {th.text};
  }}
  .sec-remark {{
    font-size: 0.9rem;
    color: {th.sec_remark};
    padding: 0.5rem 0;
    border-bottom: 1px solid {th.border};
  }}
  .sec-alert-counts {{
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
  }}
  .sec-count-pill {{
    flex: 1;
    min-width: 0;
    text-align: center;
    padding: 0.55rem 0.35rem;
    border-radius: 10px;
    border: 1px solid transparent;
  }}
  .sec-count-num {{
    display: block;
    font-size: 1.35rem;
    font-weight: 700;
    line-height: 1.1;
  }}
  .sec-count-label {{
    display: block;
    margin-top: 0.15rem;
    font-size: 0.62rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    line-height: 1.2;
    opacity: 0.85;
  }}
  .sec-count-critical {{
    background: {th.sec_crit_bg};
    border-color: {th.sec_crit_border};
    color: {th.sec_crit_text};
  }}
  .sec-count-high {{
    background: {th.sec_high_bg};
    border-color: {th.sec_high_border};
    color: {th.sec_high_text};
  }}
</style>
"""


def build_fullscreen_chart_css(theme: Theme) -> str:
    """Hide app chrome and card frames so a 3D chart fills the viewport."""
    th = theme
    scene_bg = th.globe_scene_bg
    return f"""
<style>
  section[data-testid="stSidebar"] {{ display: none !important; }}
  header[data-testid="stHeader"] {{ display: none !important; }}
  [data-testid="stToolbar"] {{ display: none !important; }}
  [data-testid="stDecoration"] {{ display: none !important; }}
  .stApp {{
    background: {th.app_bg} !important;
  }}
  .stApp:has(.skopos-fs-marker) .main .block-container {{
    padding: 0 !important;
    max-width: 100% !important;
  }}
  .stApp:has(.skopos-fs-marker) .main [data-testid="stVerticalBlock"]:not(:has(.skopos-fs-marker)) {{
    display: none !important;
  }}
  .stApp:has(.skopos-fs-marker) .main [data-testid="stVerticalBlockBorderWrapper"]:has(.skopos-fs-marker) {{
    position: fixed !important;
    inset: 0 !important;
    z-index: 8000 !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
    border-radius: 0 !important;
    background: {th.app_bg} !important;
    box-shadow: none !important;
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
    transform: none !important;
    overflow: hidden !important;
    max-height: 100vh !important;
  }}
  .stApp:has(.skopos-fs-marker) .main [data-testid="stVerticalBlockBorderWrapper"]:has(.skopos-fs-marker):hover {{
    box-shadow: none !important;
    transform: none !important;
    border-color: transparent !important;
  }}
  .stApp:has(.skopos-fs-marker) .main [data-testid="stVerticalBlockBorderWrapper"]:has(.skopos-fs-marker) > div > [data-testid="stHorizontalBlock"]:first-child {{
    display: none !important;
  }}
  .stApp:has(.skopos-fs-marker) .main [data-testid="stVerticalBlockBorderWrapper"]:has(.skopos-fs-marker) [data-testid="stHorizontalBlock"]:has([data-testid="stButton"]) {{
    position: fixed !important;
    top: 0.75rem !important;
    right: 0.85rem !important;
    left: auto !important;
    width: auto !important;
    min-width: 11rem !important;
    z-index: 9010 !important;
    margin: 0 !important;
    padding: 0 !important;
    pointer-events: none !important;
  }}
  .stApp:has(.skopos-fs-marker) .main [data-testid="stVerticalBlockBorderWrapper"]:has(.skopos-fs-marker) [data-testid="stHorizontalBlock"]:has([data-testid="stButton"]) [data-testid="column"],
  .stApp:has(.skopos-fs-marker) .main [data-testid="stVerticalBlockBorderWrapper"]:has(.skopos-fs-marker) [data-testid="stHorizontalBlock"]:has([data-testid="stButton"]) [data-testid="stButton"],
  .stApp:has(.skopos-fs-marker) .main [data-testid="stVerticalBlockBorderWrapper"]:has(.skopos-fs-marker) [data-testid="stHorizontalBlock"]:has([data-testid="stButton"]) button {{
    pointer-events: auto !important;
  }}
  .stApp:has(.skopos-fs-marker) .main [data-testid="stVerticalBlockBorderWrapper"]:has(.skopos-fs-marker) .stPlotlyChart {{
    margin: 0 !important;
    min-height: 100vh !important;
    padding-top: 3.25rem !important;
  }}
  .stApp:has(.skopos-fs-marker) .main [data-testid="stVerticalBlockBorderWrapper"]:has(.skopos-fs-marker) .stPlotlyChart > div,
  .stApp:has(.skopos-fs-marker) .main [data-testid="stVerticalBlockBorderWrapper"]:has(.skopos-fs-marker) .stPlotlyChart iframe {{
    height: calc(100vh - 3.25rem) !important;
    min-height: calc(100vh - 3.25rem) !important;
    border: none !important;
    border-radius: 0 !important;
    background: {scene_bg} !important;
  }}
  .stApp:has(.skopos-fs-marker) .main [data-testid="stVerticalBlockBorderWrapper"]:has(.skopos-fs-marker) .js-plotly-plot,
  .stApp:has(.skopos-fs-marker) .main [data-testid="stVerticalBlockBorderWrapper"]:has(.skopos-fs-marker) .plotly,
  .stApp:has(.skopos-fs-marker) .main [data-testid="stVerticalBlockBorderWrapper"]:has(.skopos-fs-marker) .user-select-none {{
    background: {scene_bg} !important;
  }}
  @media (max-width: 768px) {{
    .stApp:has(.skopos-fs-marker) .main [data-testid="stVerticalBlockBorderWrapper"]:has(.skopos-fs-marker) [data-testid="stHorizontalBlock"]:has([data-testid="stButton"]) {{
      top: 0.55rem !important;
      right: 0.55rem !important;
      min-width: 9.5rem !important;
    }}
    .stApp:has(.skopos-fs-marker) .main [data-testid="stVerticalBlockBorderWrapper"]:has(.skopos-fs-marker) .stPlotlyChart {{
      padding-top: 3.75rem !important;
    }}
    .stApp:has(.skopos-fs-marker) .main [data-testid="stVerticalBlockBorderWrapper"]:has(.skopos-fs-marker) .stPlotlyChart > div,
    .stApp:has(.skopos-fs-marker) .main [data-testid="stVerticalBlockBorderWrapper"]:has(.skopos-fs-marker) .stPlotlyChart iframe {{
      height: calc(100vh - 3.75rem) !important;
      min-height: calc(100vh - 3.75rem) !important;
    }}
  }}
</style>
"""


def plotly_hover_bg(theme: Theme) -> str:
    """Plotly hoverlabel.bgcolor must be a solid color, not CSS gradients."""
    return _plotly_hover_bg(theme)


def _plotly_hover_bg(theme: Theme) -> str:
    """Plotly hoverlabel.bgcolor must be a solid color, not CSS gradients."""
    return {
        "light": "#ffffff",
        "premium": "#fffef9",
        "dark": "#161b22",
        "midnight": "#120c16",
    }.get(theme.id, "#ffffff")


def chart_layout_kwargs(theme: Theme | None = None) -> dict:
    th = theme or get_active_theme()
    return dict(
        template=th.plotly_template,
        paper_bgcolor=th.chart_paper_bg,
        plot_bgcolor=th.chart_plot_bg,
        font=dict(family="Inter, system-ui, sans-serif", size=14, color=th.chart_font),
        margin=dict(l=32, r=32, t=64, b=48),
        hoverlabel=dict(bgcolor=_plotly_hover_bg(th), font_size=13, font_family="Inter", font_color=th.chart_font),
        transition=dict(duration=600, easing="cubic-in-out"),
    )


def apply_chart_theme(fig, theme: Theme | None = None):
    """Force readable Plotly text — axes, legend, titles, trace labels."""
    th = theme or get_active_theme()
    color = th.chart_font
    grid = th.chart_grid
    axis_kw = dict(
        automargin=True,
        title_standoff=14,
        tickfont=dict(color=color, size=12),
        title=dict(font=dict(color=color, size=13)),
        linecolor=grid,
        tickcolor=color,
        gridcolor=grid,
        zerolinecolor=grid,
    )
    fig.update_xaxes(**axis_kw)
    fig.update_yaxes(**axis_kw)
    fig.update_coloraxes(
        colorbar=dict(
            tickfont=dict(color=color, size=12),
            title=dict(font=dict(color=color, size=13)),
            outlinecolor=grid,
        )
    )
    fig.update_layout(
        font=dict(family="Inter, system-ui, sans-serif", size=14, color=color),
        legend=dict(
            font=dict(color=color, size=12),
            title=dict(font=dict(color=color, size=12)),
        ),
    )
    fig.update_traces(
        textfont=dict(color=color, size=12),
        selector=dict(type="bar"),
    )
    fig.update_traces(
        textfont=dict(color=color, size=12),
        selector=dict(type="pie"),
    )
    fig.update_traces(
        outsidetextfont=dict(color=color, size=12),
        insidetextfont=dict(color=color, size=11),
        selector=dict(type="pie"),
    )
    fig.update_traces(
        textfont=dict(color=color, size=12),
        selector=dict(type="scatter"),
    )
    if fig.layout.scene:
        scene_font = dict(tickfont=dict(color=color, size=11), title=dict(font=dict(color=color, size=12)))
        fig.update_layout(scene=dict(xaxis=scene_font, yaxis=scene_font, zaxis=scene_font))
    return fig


# Backwards-compatible alias
apply_chart_axes = apply_chart_theme
