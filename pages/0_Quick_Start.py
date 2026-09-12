"""Quick Start — guided setup wizard."""

from __future__ import annotations

import streamlit as st

from skopos.config import load_app_env

load_app_env()

from skopos.app_shell import bootstrap_shell, prime_theme
from skopos.config_paths import resolve_config_path
from skopos.ui_wizard import render_quick_start_wizard

from skopos.i18n import browser_page_title

st.set_page_config(
    page_title=browser_page_title("wizard.title"),
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="auto",
)
prime_theme()

locale = bootstrap_shell(show_wizard_prompt=False)

try:
    config_path = str(resolve_config_path("./servers.yaml"))
except ValueError as exc:
    st.error(str(exc))
    st.stop()

render_quick_start_wizard(
    locale=locale,
    config_path=config_path,
    agent_path="./agent.yaml",
)
