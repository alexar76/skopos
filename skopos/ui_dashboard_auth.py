"""Dashboard password settings UI (Settings + wizard)."""

from __future__ import annotations

import os

import streamlit as st

from skopos.app_auth import clear_dashboard_auth, dashboard_password_set
from skopos.config import load_app_env
from skopos.env_io import upsert_env_var
from skopos.i18n import t
from skopos.password_policy import (
    configured_password_meets_policy,
    min_password_length,
    password_rules,
    validate_dashboard_password,
)


def _rule_caption(locale: str, key: str) -> str:
    if key == "auth.policy.min_length":
        return t("auth.policy.min_length", locale, min=min_password_length())
    return t(key, locale)


def render_password_requirements(locale: str, password: str = "") -> None:
    rules = password_rules(password)
    for rule in rules:
        icon = "✅" if rule.passed else "⬜"
        st.caption(f"{icon} {_rule_caption(locale, rule.key)}")


def save_dashboard_password(
    new_password: str,
    *,
    session_hours: float | None = None,
    clear: bool = False,
) -> tuple[bool, str]:
    if clear:
        upsert_env_var("SKOPOS_DASHBOARD_PASSWORD", "")
        load_app_env()
        clear_dashboard_auth()
        return True, "auth.password_cleared"

    ok, failed = validate_dashboard_password(new_password)
    if not ok:
        return False, failed[0]

    upsert_env_var("SKOPOS_DASHBOARD_PASSWORD", new_password)
    if session_hours is not None:
        hours = max(0.25, min(168.0, float(session_hours)))
        upsert_env_var("SKOPOS_DASHBOARD_SESSION_HOURS", str(hours))
    load_app_env()
    clear_dashboard_auth()
    return True, "auth.password_saved"


def render_dashboard_auth_settings(locale: str, *, key_prefix: str = "settings") -> None:
    """Password set/change block for Settings and wizard."""
    configured = dashboard_password_set()
    policy_ok, _ = configured_password_meets_policy()

    if configured and not policy_ok:
        st.warning(t("auth.weak_current_password", locale))

    try:
        session_hours = float(os.environ.get("SKOPOS_DASHBOARD_SESSION_HOURS", "12"))
    except ValueError:
        session_hours = 12.0

    status_col, session_col = st.columns(2)
    with status_col:
        if configured:
            label = t("auth.status_protected", locale)
            if policy_ok:
                st.success(label)
            else:
                st.warning(label)
        else:
            st.error(t("auth.status_open", locale))
    with session_col:
        new_session_hours = st.number_input(
            t("auth.session_hours", locale),
            min_value=0.25,
            max_value=168.0,
            value=float(session_hours),
            step=0.5,
            help=t("auth.session_hours_help", locale),
            key=f"{key_prefix}_dashboard_session_hours",
        )

    st.caption(t("auth.password_requirements_intro", locale))
    render_password_requirements(locale)

    with st.form(f"{key_prefix}_dashboard_password_form", clear_on_submit=False):
        pwd1 = st.text_input(t("auth.new_password", locale), type="password")
        pwd2 = st.text_input(t("auth.confirm_password", locale), type="password")
        if pwd1:
            render_password_requirements(locale, pwd1)

        c1, c2 = st.columns(2)
        with c1:
            save_btn = st.form_submit_button(t("auth.save_password", locale), type="primary", use_container_width=True)
        with c2:
            clear_btn = st.form_submit_button(t("auth.clear_password", locale), use_container_width=True)

        if save_btn:
            if not pwd1:
                st.error(t("auth.password_empty", locale))
            elif pwd1 != pwd2:
                st.error(t("auth.password_mismatch", locale))
            else:
                ok, msg_key = save_dashboard_password(pwd1, session_hours=new_session_hours)
                if ok:
                    st.success(t(msg_key, locale))
                    st.rerun()
                else:
                    st.error(_rule_caption(locale, msg_key))

        if clear_btn:
            if configured:
                ok, msg_key = save_dashboard_password("", clear=True)
                if ok:
                    st.success(t(msg_key, locale))
                    st.rerun()
                else:
                    st.error(t(msg_key, locale))
            else:
                st.info(t("auth.already_open", locale))
