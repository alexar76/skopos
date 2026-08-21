"""Manual section refresh — load once, stay put, pull again only when asked.

Streamlit reruns the whole script on every widget click. Combined with 15–30s
``ttl=`` on ``st.cache_data``, that made SKOPOS feel busy even after the first
paint: caches expired, Prometheus was hit again, Plotly charts were rebuilt.

Caches that take ``refresh_nonce(section)`` as an argument stay until the
operator clicks **Refresh** in that section.
"""

from __future__ import annotations

from typing import Any, MutableMapping

import streamlit as st

from skopos.i18n import t

PREFIX = "_skopos_refresh_"


def _store(store: MutableMapping[str, Any] | None) -> MutableMapping[str, Any]:
    return store if store is not None else st.session_state


def refresh_key(section: str) -> str:
    return f"{PREFIX}{section}"


def refresh_nonce(section: str, store: MutableMapping[str, Any] | None = None) -> int:
    """How many times this section has been asked to reload. Starts at 0."""
    try:
        return int(_store(store).get(refresh_key(section), 0) or 0)
    except (TypeError, ValueError):
        return 0


def bump_refresh(section: str, store: MutableMapping[str, Any] | None = None) -> int:
    """Increment the section nonce. Safe as a Streamlit ``on_click`` callback."""
    s = _store(store)
    nxt = refresh_nonce(section, s) + 1
    s[refresh_key(section)] = nxt
    return nxt


def render_section_refresh(
    section: str,
    locale: str,
    *,
    store: MutableMapping[str, Any] | None = None,
) -> int:
    """Render **Refresh** for ``section`` and return the nonce to pass into caches.

    Uses ``on_click`` so the nonce is already bumped when the rest of this run
    reads it. Does not ``st.cache_data.clear()`` — other sections keep their last
    load.
    """
    loc = locale or "en"
    btn, _rest = st.columns([1.2, 6.8])
    with btn:
        st.button(
            t("common.refresh", loc),
            key=f"refresh_btn_{section}",
            help=t("common.refresh_hint", loc),
            on_click=bump_refresh,
            args=(section,),
            use_container_width=True,
        )
    return refresh_nonce(section, store)
