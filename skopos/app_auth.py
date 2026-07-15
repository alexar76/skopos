from __future__ import annotations

import os
import secrets
import time

import streamlit as st

from skopos.i18n import t
from skopos.password_policy import configured_password_meets_policy, min_password_length

_MAX_LOGIN_ATTEMPTS = 5
_LOCKOUT_SECONDS = 300


def _session_ttl_seconds() -> float:
    try:
        hours = float(os.environ.get("SKOPOS_DASHBOARD_SESSION_HOURS", "12"))
    except ValueError:
        hours = 12.0
    return max(0.25, hours) * 3600


def dashboard_password_set() -> bool:
    return bool(os.environ.get("SKOPOS_DASHBOARD_PASSWORD", "").strip())


def is_dashboard_authenticated() -> bool:
    """True when the user passed the login gate (or auth is disabled)."""
    if not dashboard_password_set():
        return True
    if not st.session_state.get("_skopos_auth_ok"):
        return False
    if _session_expired():
        clear_dashboard_auth()
        return False
    return True


def clear_dashboard_auth() -> None:
    for key in (
        "_skopos_auth_ok",
        "_skopos_auth_at",
        "_skopos_auth_attempts",
        "_skopos_auth_lock_until",
    ):
        st.session_state.pop(key, None)


def _session_expired() -> bool:
    auth_at = st.session_state.get("_skopos_auth_at")
    if auth_at is None:
        return False
    return (time.time() - float(auth_at)) > _session_ttl_seconds()


def _check_login_lockout(locale: str) -> None:
    lock_until = float(st.session_state.get("_skopos_auth_lock_until") or 0)
    if time.time() < lock_until:
        remaining = max(1, int(lock_until - time.time()))
        st.error(t("auth.lockout", locale, seconds=remaining))
        st.stop()


def _register_failed_login(locale: str) -> None:
    attempts = int(st.session_state.get("_skopos_auth_attempts") or 0) + 1
    st.session_state._skopos_auth_attempts = attempts
    if attempts >= _MAX_LOGIN_ATTEMPTS:
        st.session_state._skopos_auth_lock_until = time.time() + _LOCKOUT_SECONDS
        st.session_state._skopos_auth_attempts = 0
        st.warning(t("auth.lockout_started", locale, seconds=_LOCKOUT_SECONDS))


def require_dashboard_auth(locale: str = "en") -> bool:
    """Gate dashboard when SKOPOS_DASHBOARD_PASSWORD is set."""
    expected = os.environ.get("SKOPOS_DASHBOARD_PASSWORD", "").strip()
    if not expected:
        return True

    if st.session_state.get("_skopos_auth_ok"):
        if _session_expired():
            clear_dashboard_auth()
            st.info(t("auth.session_expired", locale))
        else:
            return True

    _check_login_lockout(locale)

    policy_ok, _ = configured_password_meets_policy()
    if not policy_ok:
        st.warning(t("auth.weak_current_password", locale))

    _left, center, _right = st.columns([1, 1.35, 1])
    with center:
        st.markdown('<div class="skopos-login-gate">', unsafe_allow_html=True)
        st.markdown(f"### 🔐 {t('auth.title', locale)}")
        st.caption(t("auth.subtitle", locale))

        with st.expander(t("auth.password_requirements_intro", locale), expanded=False):
            st.caption(t("auth.policy.min_length", locale, min=min_password_length()))
            st.caption(t("auth.policy.has_letter", locale))
            st.caption(t("auth.policy.has_digit", locale))
            st.caption(t("auth.policy.not_weak", locale))

        with st.form("stats_login", clear_on_submit=False):
            pwd = st.text_input(
                t("auth.password", locale),
                type="password",
                autocomplete="current-password",
                placeholder=t("auth.password_placeholder", locale),
            )
            submitted = st.form_submit_button(t("auth.login", locale), type="primary", use_container_width=True)
            if submitted:
                if secrets.compare_digest(pwd, expected):
                    st.session_state._skopos_auth_ok = True
                    st.session_state._skopos_auth_at = time.time()
                    st.session_state._skopos_auth_attempts = 0
                    st.session_state.pop("_skopos_auth_lock_until", None)
                    st.rerun()
                _register_failed_login(locale)
                st.error(t("auth.invalid", locale))
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()
    return False


def render_logout_button(*, locale: str) -> None:
    if not dashboard_password_set():
        return
    if not st.session_state.get("_skopos_auth_ok"):
        return
    ttl = _session_ttl_seconds()
    auth_at = st.session_state.get("_skopos_auth_at")
    if auth_at is not None:
        remaining_h = max(0.0, (float(auth_at) + ttl - time.time()) / 3600)
        st.sidebar.caption(t("auth.session_remaining", locale, hours=f"{remaining_h:.1f}"))
    if st.sidebar.button(t("auth.logout", locale), use_container_width=True):
        clear_dashboard_auth()
        st.rerun()
