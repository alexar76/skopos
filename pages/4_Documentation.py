"""SKOPOS — in-app documentation."""

from __future__ import annotations

import streamlit as st

from skopos.app_shell import bootstrap_shell, prime_theme
from skopos.docs_viewer import render_docs_page

prime_theme()
locale = bootstrap_shell(require_auth=False, show_wizard_prompt=False)
render_docs_page(locale=locale)
