"""SKOPOS — in-app documentation."""

from __future__ import annotations

import streamlit as st

from skopos.app_shell import bootstrap_app, finalize_page, prime_theme
from skopos.docs_viewer import render_docs_page

prime_theme()
ctx = bootstrap_app()
render_docs_page(locale=ctx.locale)
finalize_page(ctx)
