"""Remediation — what MOMUS made us fix: the gate verdict, the signed order, the agent's answer."""

from __future__ import annotations

import streamlit as st

from skopos.config import load_app_env

load_app_env()

from skopos.app_shell import bootstrap_app, finalize_page, prime_theme, stop_page
from skopos.db_connection import DbConnection, connect
from skopos.db_dialect import normalize_row, resolve_db_target
from skopos.i18n import active_locale, browser_page_title, t_or
from skopos.node_remediation import recent_jobs, stats
from skopos.node_store import list_credentials
from skopos.ui import hero, section_head
from skopos.ui_a2a import a2a_rows, render_a2a_empty, render_a2a_strip
from skopos.ui_remediation import (
    job_rows,
    render_remediation_board,
    render_remediation_empty,
    render_remediation_headline,
)

st.set_page_config(
    page_title=browser_page_title("remediation.title"),
    page_icon="🩹",
    layout="wide",
    initial_sidebar_state="auto",
)
prime_theme()

ctx = bootstrap_app(show_alerts=False)
locale = ctx.locale


def L(key: str, default: str, **kw) -> str:
    """Localized string with an English default at the call site — mirrors app_shell.T.

    Re-reads active_locale() rather than closing over ctx.locale, so the page stays correct when
    the language changes mid-run.
    """
    return t_or(key, active_locale(), default, **kw)


# ── the store ────────────────────────────────────────────────────────────────
# The conductor lives on another host and its control API is loopback-only, so this page never
# calls it: it reads only what the conductor PUSHED into the SKOPOS store, through that store's own
# reader (skopos/node_remediation.py). Read-only in the sense that matters — the page writes no row
# and has no path back to the conductor; the reader's idempotent CREATE TABLE IF NOT EXISTS is its
# own bootstrap, and lets the dashboard open the database before the first push ever lands.

#: recent_jobs caps itself at 500. Counting the headline over the same window keeps the four numbers
#: consistent with the board underneath them; a truncated window is called out in the caption.
_JOB_WINDOW = 500

#: Where the conductor's A2A wire lands IF it is ever pushed. It is not part of the push contract
#: today — a2a_events lives in its own SQLite on the conductor host — so this table normally does
#: not exist, and the strip says so instead of inventing envelopes.
_A2A_TABLE = "remediation_a2a_events"
_A2A_WINDOW = 200


def _read_a2a(con: DbConnection) -> list[dict] | None:
    """Pushed envelopes, or None when the table does not exist — a different message from empty.

    Deliberately unordered: no clock column is under contract yet, so the window is bounded here and
    sorted newest-first after flattening (a2a_rows).
    """
    try:
        if con.backend == "postgresql":
            probe = con.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = ?",
                (_A2A_TABLE,),
            ).fetchone()
        else:
            probe = con.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (_A2A_TABLE,),
            ).fetchone()
        if probe is None:
            return None
        rows = con.execute(f"SELECT * FROM {_A2A_TABLE} LIMIT ?", (_A2A_WINDOW,)).fetchall()
        return [normalize_row(r) for r in rows]
    except Exception:  # noqa: BLE001 - an unreadable wire table is reported, not raised
        return None


def _read_store(db_target: str) -> dict:
    con = connect(db_target)
    try:
        enrolled = sum(1 for c in list_credentials(con) if not c.get("revoked_at_utc"))
        jobs = recent_jobs(con, limit=_JOB_WINDOW)
        totals = stats(con)
        events = _read_a2a(con)
    finally:
        con.close()
    # Why enrollment decides the wording: a push needs a credential minted here, so zero of them is
    # the one thing the store can prove about the channel itself. Real rows always win — a
    # credential revoked after a push must not hide what it delivered.
    if jobs:
        status = "ok"
    elif enrolled == 0:
        status = "no_channel"
    else:
        status = "nothing_pushed"
    if events:
        a2a_status = "ok"
    elif events is None:
        a2a_status = "no_contract"
    else:
        a2a_status = status if status != "ok" else "nothing_pushed"
    return {
        "status": status,
        "a2a_status": a2a_status,
        "jobs": jobs,
        "events": events or [],
        "enrolled": enrolled,
        "total": int(totals.get("total") or 0),
        "last_update": str(totals.get("last_update_utc") or ""),
        "error": "",
    }


@st.cache_data(ttl=20, show_spinner=False)
def _load_store(db_target: str) -> dict:
    """Read with a hard timeout and no exceptions — an unreachable store must render a message.

    The exception text is deliberately dropped in favour of its type: a failing connect can echo
    the DSN back, and a Postgres URL carries credentials.
    """
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    unreachable = {"status": "unreachable", "a2a_status": "unreachable", "jobs": [], "events": [],
                   "enrolled": 0, "total": 0, "last_update": "", "error": ""}
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_read_store, db_target).result(timeout=6.0)
    except FuturesTimeout:
        return {**unreachable, "error": "timeout"}
    except Exception as exc:  # noqa: BLE001 - degrade, never crash the page
        return {**unreachable, "error": type(exc).__name__}


hero(
    L("remediation.title", "Remediation"),
    L("remediation.subtitle", "What MOMUS made us fix — finding, gate verdict, signed deploy order"),
)
st.caption(L(
    "remediation.source_note",
    "Read-only view of what the conductor pushed into the SKOPOS store. The conductor runs on "
    "another host and is never called from this page, and this copy is never the authority.",
))

data = _load_store(resolve_db_target(ctx.cfg))
status = str(data.get("status") or "")

if status == "unreachable":
    st.error(L(
        "remediation.store_unreachable",
        "The SKOPOS store could not be read ({error}), so nothing can be shown — this is a "
        "dashboard problem, not a statement about whether anything was fixed.",
        error=str(data.get("error") or "error"),
    ))
    stop_page(ctx)

raw_jobs = list(data.get("jobs") or [])
rows = job_rows(raw_jobs)
if len(rows) < len(raw_jobs):
    st.warning(L(
        "remediation.rows_unreadable",
        "{n} pushed record(s) could not be read and were left out of the board.",
        n=len(raw_jobs) - len(rows),
    ))

if rows:
    render_remediation_headline(rows, locale=locale)
    if data.get("last_update"):
        # The conductor's clock, not ours: the newest job update that was pushed, so the gap to
        # now is how stale this mirror is.
        st.caption(L("remediation.last_update", "Last pushed update: {ts}",
                     ts=str(data.get("last_update"))))

    section_head(L("remediation.section_board", "The board"))
    st.caption(L(
        "remediation.section_board_hint",
        "One row per finding: MOMUS found it, the AI-Factory patched it, MOMUS re-tested the patch "
        "as the deploy gate, and a node agent either redeployed the service or refused. Open a row "
        "for the full history and the raw pushed summary.",
    ))
    if int(data.get("total") or 0) > len(rows):
        # Say it rather than let the counters read as fleet-wide totals.
        st.caption(L("remediation.window_truncated",
                     "Showing the {shown} most recently updated of {total} findings — the counters "
                     "above cover this window.", shown=len(rows), total=int(data["total"])))
    render_remediation_board(rows, locale=locale)
else:
    render_remediation_empty(status, locale=locale)

section_head(L("remediation.section_a2a", "A2A wire"))
st.caption(L(
    "remediation.section_a2a_hint",
    "The delegations behind the board: MOMUS asking SKOPOS to remediate, SKOPOS asking MOMUS to "
    "re-test. Agent↔agent envelopes, not MCP tool calls.",
))
events = a2a_rows(data.get("events") or [])
if events:
    render_a2a_strip(events, locale=locale)
else:
    render_a2a_empty(str(data.get("a2a_status") or status), locale=locale)

finalize_page(ctx)
