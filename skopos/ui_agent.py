"""Global floating security agent — bottom-right chat widget (SupportWidget-style)."""

from __future__ import annotations

import html

import streamlit as st

from skopos.agent import ChatMessage, LLMProviderError, build_agent_context, chat_with_agent, load_agent_config
from skopos.agent.config import get_provider
from skopos.app_auth import is_dashboard_authenticated
from skopos.config import AppConfig, load_app_env
from skopos.db import connect_for_config, init_db
from skopos.i18n import t, t_list
from skopos.security.posture import SecurityPosture


def _init_agent_state() -> None:
    if "agent_history" not in st.session_state:
        st.session_state.agent_history: list[ChatMessage] = []
    if "agent_open" not in st.session_state:
        st.session_state.agent_open = False


def _submit_agent_prompt(
    cfg: AppConfig,
    agent_cfg,
    ctx: str,
    prov_id: str,
    prompt: str,
) -> None:
    try:
        reply = chat_with_agent(
            agent_cfg,
            st.session_state.agent_history,
            prompt,
            context=ctx,
            provider_id=prov_id,
        )
        st.session_state.agent_history.append(ChatMessage(role="user", content=prompt))
        st.session_state.agent_history.append(ChatMessage(role="assistant", content=reply))
        st.session_state.agent_open = True
        st.rerun()
    except LLMProviderError as e:
        st.error(str(e))


def _render_agent_messages(history: list[ChatMessage]) -> None:
    if not history:
        return
    rows: list[str] = ['<div class="stats-agent-messages" role="log">']
    for msg in history[-12:]:
        role = msg.role
        row_cls = "stats-agent-row stats-agent-row--user" if role == "user" else "stats-agent-row stats-agent-row--assistant"
        bubble_cls = "stats-agent-bubble stats-agent-bubble--user" if role == "user" else "stats-agent-bubble stats-agent-bubble--assistant"
        body = html.escape(msg.content).replace("\n", "<br>")
        rows.append(f'<div class="{row_cls}"><div class="{bubble_cls}">{body}</div></div>')
    rows.append("</div>")
    st.markdown("".join(rows), unsafe_allow_html=True)


def _render_panel_header(*, locale: str, is_open: bool) -> None:
    state = "open" if is_open else "closed"
    st.markdown(
        f'<span class="stats-agent-root stats-agent-root--{state}" aria-hidden="true"></span>'
        f'<span class="stats-agent-anchor" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )
    if is_open:
        st.markdown('<div class="stats-agent-panel" aria-hidden="true"></div>', unsafe_allow_html=True)


@st.fragment
def _agent_widget(
    cfg: AppConfig,
    agent_cfg,
    posture: SecurityPosture | None,
    *,
    locale: str,
    server_name: str | None,
) -> None:
    is_open = bool(st.session_state.agent_open)

    if not is_open:
        _render_panel_header(locale=locale, is_open=False)
        st.markdown('<span class="stats-agent-fab-slot" aria-hidden="true"></span>', unsafe_allow_html=True)
        if st.button("chat", key="stats_agent_fab", help=t("agent.open", locale)):
            st.session_state.agent_open = True
            st.rerun()
        return

    _render_panel_header(locale=locale, is_open=True)

    head_l, head_r = st.columns([9, 1])
    with head_l:
        title = html.escape(t("agent.panel_title", locale))
        subtitle = html.escape(t("agent.panel_subtitle", locale))
        st.markdown(
            f'<div class="stats-agent-head">'
            f'<div class="stats-agent-head-title">{title}</div>'
            f'<div class="stats-agent-head-sub">{subtitle}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
    with head_r:
        if st.button("✕", key="stats_agent_close", help=t("agent.close", locale)):
            st.session_state.agent_open = False
            st.rerun()

    prov_ids = list(agent_cfg.providers.keys())
    default_idx = prov_ids.index(agent_cfg.default_provider) if agent_cfg.default_provider in prov_ids else 0
    if "global_agent_provider" not in st.session_state:
        st.session_state.global_agent_provider = prov_ids[default_idx]
    with st.expander(t("security.agent_provider", locale), expanded=False):
        st.selectbox(
            t("security.agent_provider", locale),
            prov_ids,
            index=prov_ids.index(st.session_state.global_agent_provider)
            if st.session_state.global_agent_provider in prov_ids
            else default_idx,
            key="global_agent_provider",
            label_visibility="collapsed",
        )
    prov_id = str(st.session_state.global_agent_provider)
    prov = get_provider(agent_cfg, prov_id)
    if prov.kind in ("openai_compatible", "anthropic_compatible") and not prov.api_key:
        env = prov.api_key_env or "API_KEY"
        st.caption(t("security.agent_no_key", locale, env=env))

    con = connect_for_config(cfg)
    init_db(con)
    ctx = build_agent_context(cfg, con, server_name=server_name, posture=posture)
    con.close()

    history = st.session_state.agent_history

    if not history:
        st.markdown(
            f'<p class="stats-agent-intro">{html.escape(t("agent.panel_intro", locale))}</p>',
            unsafe_allow_html=True,
        )

    _render_agent_messages(history)

    suggestions = t_list("agent.suggestions", locale)
    if suggestions:
        st.markdown(
            f'<div class="stats-agent-suggestions-label">{html.escape(t("agent.suggestions_title", locale))}</div>',
            unsafe_allow_html=True,
        )
        for idx, label in enumerate(suggestions[:4]):
            if st.button(label, key=f"agent_suggestion_{idx}", use_container_width=True):
                _submit_agent_prompt(cfg, agent_cfg, ctx, prov_id, label)

    st.markdown('<div class="stats-agent-footer" aria-hidden="true"></div>', unsafe_allow_html=True)
    draft = st.text_area(
        t("agent.placeholder", locale),
        key="global_agent_draft",
        label_visibility="collapsed",
        height=88,
    )
    foot_l, foot_r = st.columns([2, 1])
    with foot_l:
        st.markdown(
            f'<p class="stats-agent-footnote">{html.escape(t("agent.footer_status", locale))}</p>',
            unsafe_allow_html=True,
        )
    with foot_r:
        send = st.button(
            t("agent.send", locale),
            key="global_agent_send",
            type="primary",
            use_container_width=True,
        )

    if send and draft.strip():
        _submit_agent_prompt(cfg, agent_cfg, ctx, prov_id, draft.strip())
        st.session_state.global_agent_draft = ""

    if history:
        if st.button(t("agent.clear", locale), key="global_agent_clear", type="secondary", use_container_width=True):
            st.session_state.agent_history = []
            st.rerun()


def render_global_agent(
    cfg: AppConfig,
    agent_path: str,
    *,
    locale: str = "en",
    server_name: str | None = None,
    posture: SecurityPosture | None = None,
) -> None:
    """Floating AI agent — bottom-right on every authenticated page."""
    if not is_dashboard_authenticated():
        return

    _init_agent_state()
    load_app_env()
    try:
        agent_cfg = load_agent_config(agent_path)
    except Exception:
        return

    _agent_widget(cfg, agent_cfg, posture, locale=locale, server_name=server_name)
