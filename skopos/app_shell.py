"""Shared app bootstrap: auth, locale, security posture, global agent."""

from __future__ import annotations

import html
from dataclasses import dataclass

import streamlit as st

from skopos.agent import load_agent_config
from skopos.app_auth import render_logout_button, require_dashboard_auth
from skopos.config import AppConfig, load_app_env, load_config
from skopos.i18n import (
    SKOPOS_LOCALE_WIDGET,
    SUPPORTED_LOCALES,
    _commit_locale_widget,
    _resolve_page_link_path,
    _sync_locale_widget,
    active_locale,
    ensure_locale_state,
    locale_label,
    render_sidebar_nav,
    safe_page_link,
    t,
)
from skopos.security.auto_scan import get_auto_scan_status, start_auto_scan_thread
from skopos.telegram_notify import get_telegram_notify_status
from skopos.security.posture import SecurityPosture
from skopos.security.posture_loader import load_security_posture
from skopos.db_dialect import resolve_db_target
from skopos.setup_state import evaluate_setup, try_load_config
from skopos.themes import DEFAULT_THEME, THEME_ORDER, THEMES, get_active_theme, theme_label
from skopos.theme_prefs import (
    SKOPOS_THEME_KEY,
    SKOPOS_THEME_WIDGET,
    apply_theme_state,
    save_theme_pref,
    sync_theme_widget,
)
from skopos.brand import render_sidebar_brand
from skopos.ui import clear_fullscreen_state, inject_all_theme_css
from skopos.ui_agent import render_global_agent
from skopos.ui_topbar import render_topbar
from skopos.ui_security import render_alert_banner, render_sidebar_score
from skopos.ui_onboarding import render_password_warning


@dataclass(frozen=True)
class AppContext:
    cfg: AppConfig
    agent_path: str
    locale: str
    posture: SecurityPosture
    theme_id: str


@st.cache_resource(ttl=30)
def _cached_posture(db_path: str, server_tuple: tuple[str, ...], agent_path: str) -> SecurityPosture:
    cfg = load_config("./servers.yaml")
    return load_security_posture(db_path, cfg, agent_yaml_path=agent_path)


def ensure_theme_state() -> None:
    """Load canonical theme id from disk or session (survives page navigation)."""
    apply_theme_state(st.session_state, valid_ids=set(THEMES), default=DEFAULT_THEME)


def _sync_theme_widget() -> None:
    """Keep the theme selectbox aligned with the canonical id (no mid-run drift)."""
    sync_theme_widget(st.session_state, valid_ids=set(THEMES), default=DEFAULT_THEME)


def _init_theme_state() -> None:
    ensure_theme_state()
    _sync_theme_widget()


def _commit_theme() -> None:
    picked = str(st.session_state.get(SKOPOS_THEME_WIDGET, DEFAULT_THEME))
    if picked in THEMES:
        st.session_state[SKOPOS_THEME_KEY] = picked
        save_theme_pref(picked)


def _current_topbar_slug() -> str | None:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        ctx = get_script_run_ctx()
        if ctx is None:
            return None
        main = str(getattr(ctx, "main_script_path", "") or "").replace("\\", "/")
        if main.endswith("dashboard.py") or main.endswith("/dashboard.py"):
            return "home"
        if "4_Documentation" in main or "Documentation.py" in main:
            return "documentation"
        if "0_Quick_Start" in main or "Quick_Start" in main:
            return "quick_start"
        if "2_Settings" in main or "Settings.py" in main:
            return "settings"
    except Exception:
        return None
    return None


def _render_hidden_topbar_page_links(locale: str) -> None:
    """Hidden sidebar anchors so the fixed top bar can SPA-navigate (incl. Documentation)."""
    st.sidebar.markdown(
        '<div class="skopos-hidden-page-links" aria-hidden="true">',
        unsafe_allow_html=True,
    )
    for path in ("pages/4_Documentation.py",):
        try:
            st.sidebar.page_link(path, label=t("app.documentation", locale))
        except Exception:
            pass
    st.sidebar.markdown("</div>", unsafe_allow_html=True)


def _render_nav_menu() -> None:
    render_sidebar_brand(
        title=t("app.title", active_locale()),
        tagline=t("app.tagline", active_locale()),
    )
    render_sidebar_nav(locale=active_locale(), collapsed=False)
    _render_hidden_topbar_page_links(active_locale())


def _render_wizard_sidebar_prompt(locale: str, *, config_path: str = "./servers.yaml") -> None:
    status = evaluate_setup(config_path)
    if status.needs_wizard:
        st.sidebar.info(t("wizard.sidebar_prompt", locale))


def prime_theme() -> None:
    """Apply theme CSS before any widgets — call right after st.set_page_config."""
    clear_fullscreen_state()
    _init_theme_state()
    st.session_state["_skopos_prime_theme_this_run"] = True
    inject_all_theme_css(get_active_theme())


def _inject_theme_early() -> None:
    """Bootstrap hook; skip duplicate injection when the page already called prime_theme()."""
    if st.session_state.pop("_skopos_prime_theme_this_run", False):
        _init_theme_state()
        return
    _init_theme_state()
    inject_all_theme_css(get_active_theme())


def _render_locale_and_theme_pickers() -> str:
    """Language + theme controls. Canonical locale lives in skopos_locale, not the widget key."""
    ensure_locale_state()
    _sync_locale_widget()
    loc = active_locale()
    st.sidebar.selectbox(
        t("common.language", loc),
        SUPPORTED_LOCALES,
        format_func=locale_label,
        key=SKOPOS_LOCALE_WIDGET,
        on_change=_commit_locale_widget,
    )
    loc = active_locale()
    ensure_theme_state()
    _sync_theme_widget()
    st.sidebar.selectbox(
        t("common.theme", loc),
        THEME_ORDER,
        format_func=lambda tid: theme_label(THEMES[tid], loc),
        key=SKOPOS_THEME_WIDGET,
        on_change=_commit_theme,
    )
    return active_locale()


def _render_sidebar_bottom(*, config_path: str, show_wizard_prompt: bool) -> None:
    """Locale, theme, logout — pinned to sidebar bottom (GA-style)."""
    st.sidebar.markdown('<div class="skopos-sidebar-bottom-start"></div>', unsafe_allow_html=True)
    locale = _render_locale_and_theme_pickers()
    if show_wizard_prompt:
        _render_wizard_sidebar_prompt(locale, config_path=config_path)
    render_password_warning(locale=locale)
    render_logout_button(locale=locale)


def bootstrap_shell(*, config_path: str = "./servers.yaml", show_wizard_prompt: bool = True) -> str:
    """Auth, navigation, theme, and locale without requiring a valid servers.yaml."""
    load_app_env()
    _inject_theme_early()
    ensure_locale_state()
    require_dashboard_auth(active_locale())

    locale = active_locale()
    render_topbar(locale=locale, active=_current_topbar_slug())
    _render_nav_menu()
    _render_sidebar_bottom(config_path=config_path, show_wizard_prompt=show_wizard_prompt)
    return active_locale()


def finalize_page(ctx: AppContext, *, server_name: str | None = None) -> None:
    """Render floating agent widget at page bottom (call once per page)."""
    render_global_agent(
        ctx.cfg,
        ctx.agent_path,
        locale=active_locale(),
        server_name=server_name,
        posture=ctx.posture,
    )


@st.cache_resource
def _ensure_auto_scan(config_path: str, interval_minutes: int, enabled: bool):
    if not enabled:
        return None
    return start_auto_scan_thread(config_path)


def bootstrap_app(
    config_path: str = "./servers.yaml",
    agent_path: str = "./agent.yaml",
    *,
    show_alerts: bool = True,
    server_filter: str | None = None,
) -> AppContext:
    load_app_env()
    _inject_theme_early()
    ensure_locale_state()
    require_dashboard_auth(active_locale())

    cfg = try_load_config(config_path)
    if cfg is None:
        bootstrap_shell(config_path=config_path, show_wizard_prompt=False)
        locale = active_locale()
        st.error(t("wizard.config_invalid", locale))
        resolved = _resolve_page_link_path("pages/0_Quick_Start.py")
        if not safe_page_link(
            resolved,
            label=t("app.quick_start", locale),
            icon=":material/rocket_launch:",
        ):
            st.info(t("app.quick_start", locale))
        st.stop()

    posture = _cached_posture(resolve_db_target(cfg), tuple(s.name for s in cfg.servers), agent_path)

    locale = active_locale()
    render_topbar(locale=locale, active=_current_topbar_slug())
    _render_nav_menu()
    _render_sidebar_bottom(config_path=config_path, show_wizard_prompt=True)

    locale = active_locale()
    if cfg.security_auto_scan:
        _ensure_auto_scan(config_path, cfg.security_scan_interval_minutes, True)
        scan_status = get_auto_scan_status()
        if scan_status.get("last_run_utc"):
            st.sidebar.caption(
                f"🔄 {t('settings.auto_scan_last', locale)}: {scan_status['last_run_utc'][:19]}"
            )

    if cfg.telegram_enabled:
        tg_status = get_telegram_notify_status()
        if tg_status.get("last_notify_utc"):
            st.sidebar.caption(
                f"📨 {t('settings.telegram_last_notify', locale)}: {tg_status['last_notify_utc'][:19]}"
            )

    render_sidebar_score(posture, locale=locale)

    if show_alerts:
        render_alert_banner(posture, locale=active_locale())

    theme = get_active_theme()
    locale = active_locale()
    return AppContext(
        cfg=cfg,
        agent_path=agent_path,
        locale=locale,
        posture=posture,
        theme_id=theme.id,
    )


def T(ctx: AppContext, key: str, **kw) -> str:
    return t(key, active_locale(), **kw)
