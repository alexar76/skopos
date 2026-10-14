"""Settings — AI Security Agent (provider, API keys)."""

from __future__ import annotations

import streamlit as st

from skopos.app_shell import T, bootstrap_app, finalize_page, prime_theme
from skopos.config import load_app_env
from skopos.i18n import active_locale, browser_page_title
from skopos.ui_agent_settings import render_agent_settings

load_app_env()

st.set_page_config(
    page_title=browser_page_title("agent_settings.title"),
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="auto",
)
prime_theme()

ctx = bootstrap_app(show_alerts=False)
locale = ctx.locale

if "agent_settings_path" not in st.session_state:
    st.session_state.agent_settings_path = ctx.agent_path

agent_path = st.sidebar.text_input(
    T(ctx, "agent_settings.config_path"),
    value=st.session_state.agent_settings_path,
    key="settings_agent_path_sidebar",
)
st.session_state.agent_settings_path = agent_path

render_agent_settings(locale=locale, agent_path=agent_path)

finalize_page(ctx)
