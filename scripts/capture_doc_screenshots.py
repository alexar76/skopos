#!/usr/bin/env python3
"""Capture the in-app documentation screenshot sets, one per UI language.

The docs viewer resolves screenshots by *documentation* language → ``en``,
``ru`` or ``es`` folders (see ``skopos/doc_i18n.py``). Each folder MUST contain
screenshots captured with the matching UI language — otherwise an English guide
shows a Russian dashboard. This script switches the dashboard language and
recaptures the full referenced set into ``docs/screenshots/<loc>/``.

Usage:
  export SKOPOS_DASHBOARD_PASSWORD=...
  pip install playwright && playwright install chromium
  python scripts/capture_doc_screenshots.py \
      --base-url https://skopos.modelmarket.dev/app/ --locales en es ru

Structural targeting (language-independent) — see the app source:
  * sidebar selectboxes: nth(0)=Language, nth(1)=Theme
  * language option order: en=0, ru=1, es=2 (SUPPORTED_LOCALES)
  * theme option order: premium=2 (THEME_ORDER)
  * nav page links: 0 Quick Start, 2 Analytics, 3 Security, 5 Fleet
  * Security tabs: 1 Security Report, 7 3D Threat Map
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "docs" / "screenshots"

SIDEBAR = 'section[data-testid="stSidebar"]'

# Language selectbox option index per target locale (SUPPORTED_LOCALES order).
LOCALE_OPTION_INDEX = {"en": 0, "ru": 1, "es": 2}
PREMIUM_THEME_INDEX = 2  # THEME_ORDER: light,slate,premium,...
DEFAULT_THEME_INDEX = 8  # midnight/Cosmos — restore prod default after the run


def _ensure_playwright() -> None:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright", "-q"])
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])


def _wait_app(page) -> None:
    page.wait_for_selector('[data-testid="stApp"]', timeout=120_000)
    page.wait_for_timeout(3500)


def _is_logged_in(page) -> bool:
    if page.locator('input[type="password"]').count():
        return False
    return page.locator(SIDEBAR).count() > 0


def _submit_login(page) -> None:
    submit = page.locator('[data-testid="stFormSubmitButton"] button')
    if submit.count():
        submit.first.click()
        return
    page.keyboard.press("Enter")


def _login(page, base_url: str, password: str) -> None:
    page.goto(base_url.rstrip("/") + "/", wait_until="domcontentloaded", timeout=120_000)
    _wait_app(page)
    if _is_logged_in(page):
        return
    pwd = page.locator('input[type="password"]')
    if not pwd.count():
        raise RuntimeError("login gate not found and not authenticated")
    pwd.first.fill(password)
    _submit_login(page)
    page.wait_for_function(
        "() => !document.querySelector('input[type=\"password\"]')", timeout=60_000
    )
    page.wait_for_selector(SIDEBAR, timeout=60_000)
    _wait_app(page)


def _scroll_sidebar(page, *, bottom: bool) -> None:
    sb = page.locator(SIDEBAR).first
    if sb.count():
        sb.evaluate("(el, toBottom) => { el.scrollTop = toBottom ? el.scrollHeight : 0; }", bottom)
        page.wait_for_timeout(500)


def _pick_selectbox_option(page, box_index: int, option_index: int) -> None:
    _scroll_sidebar(page, bottom=True)
    box = page.locator(f'{SIDEBAR} [data-testid="stSelectbox"]').nth(box_index)
    box.locator('[data-baseweb="select"]').click()
    page.wait_for_selector('[data-baseweb="popover"] [role="option"]', timeout=15_000)
    page.locator('[data-baseweb="popover"] [role="option"]').nth(option_index).click()
    page.wait_for_timeout(3200)


def _set_language(page, locale: str) -> None:
    _pick_selectbox_option(page, 0, LOCALE_OPTION_INDEX[locale])


def _set_theme(page, theme_index: int) -> None:
    _pick_selectbox_option(page, 1, theme_index)


def _nav(page, index: int) -> None:
    links = page.locator(
        f'{SIDEBAR} [data-testid="stPageLink"] a:visible'
    )
    links.nth(index).click()
    _wait_app(page)


def _tab(page, index: int) -> None:
    tabs = page.locator('[data-testid="stTabs"] [role="tab"]')
    tabs.nth(index).click()
    page.wait_for_timeout(3500)


def _shot(page, loc: str, name: str, *, full_page: bool = False) -> None:
    out = SHOTS / loc / name
    out.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out), full_page=full_page)
    _assert_size(out)


def _shot_element(page, selector: str, loc: str, name: str) -> None:
    out = SHOTS / loc / name
    out.parent.mkdir(parents=True, exist_ok=True)
    el = page.locator(selector).first
    el.scroll_into_view_if_needed(timeout=15_000)
    page.wait_for_timeout(600)
    el.screenshot(path=str(out))
    _assert_size(out)


def _assert_size(path: Path) -> None:
    if path.stat().st_size < 6000:
        raise RuntimeError(f"screenshot too small: {path} ({path.stat().st_size} bytes)")


def _safe(label: str, fn) -> bool:
    try:
        fn()
        print(f"    ✓ {label}")
        return True
    except Exception as exc:  # keep going; one missing shot must not abort the set
        print(f"    ⚠️  {label}: {exc}")
        return False


def _open_agent(page) -> None:
    page.wait_for_selector("#skopos-agent-root button.skopos-agent-fab", timeout=60_000)
    page.wait_for_timeout(1500)
    page.locator("#skopos-agent-root button.skopos-agent-fab").first.click()
    page.wait_for_timeout(500)
    # The FAB click handler lives on the top-document button; when Playwright's
    # synthetic click doesn't toggle it, force the open state so CSS reveals the
    # panel (opacity/visibility/transform driven by the `is-open` class).
    if not page.locator("#skopos-agent-root.is-open").count():
        page.evaluate(
            "() => { var el = document.querySelector('#skopos-agent-root'); if (el) el.classList.add('is-open'); }"
        )
    page.wait_for_selector("#skopos-agent-root.is-open .skopos-agent-panel", timeout=15_000)
    page.wait_for_timeout(1800)


def _close_agent(page) -> None:
    page.evaluate(
        "() => { var el = document.querySelector('#skopos-agent-root'); if (el) el.classList.remove('is-open'); }"
    )
    page.wait_for_timeout(500)


def capture_locale(page, base_url: str, loc: str) -> None:
    print(f"\n=== locale: {loc} ===")
    _set_language(page, loc)
    _set_theme(page, PREMIUM_THEME_INDEX)

    # Analytics (home) — sidebar, briefing card, overview
    _safe("nav → Analytics", lambda: _nav(page, 2))
    _scroll_sidebar(page, bottom=False)
    _safe("sidebar-nav.png", lambda: _shot_element(page, SIDEBAR, loc, "sidebar-nav.png"))
    _safe("topbar-area.png", lambda: _shot_element(page, '[data-testid="stMain"] [data-testid="stHeader"], .skopos-topbar', loc, "topbar-area.png"))
    _safe("ai-briefing-card.png", lambda: _shot_element(page, ".ai-briefing-card", loc, "ai-briefing-card.png"))
    _safe("analytics-premium.png", lambda: (_tab(page, 0), _shot(page, loc, "analytics-premium.png")))

    # Security — Summary Report (tab 1) and 3D Threat Map (tab 7)
    _safe("nav → Security", lambda: _nav(page, 3))
    _safe("security-summary-report.png", lambda: (_tab(page, 1), _shot(page, loc, "security-summary-report.png")))
    _safe("security-3d-map.png", lambda: (_tab(page, 7), _shot(page, loc, "security-3d-map.png")))

    # Fleet / settings servers
    _safe("settings-fleet.png", lambda: (_nav(page, 5), _shot(page, loc, "settings-fleet.png")))

    # Quick Start (best-effort: capture current wizard step)
    _safe("quick-start.png", lambda: (_nav(page, 0), page.wait_for_timeout(1500), _shot(page, loc, "quick-start.png")))

    # Floating agent — FAB + open panel (theme-following gamma)
    _safe("nav → Analytics (agent)", lambda: _nav(page, 2))
    _safe("floating-agent-fab.png", lambda: _shot_element(page, "#skopos-agent-root", loc, "floating-agent-fab.png"))
    _safe("floating-agent.png", lambda: (_open_agent(page), _shot_element(page, "#skopos-agent-root.is-open .skopos-agent-panel", loc, "floating-agent.png"), _close_agent(page)))


def capture(base_url: str, password: str, locales: list[str]) -> None:
    _ensure_playwright()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        _login(page, base_url, password)
        for loc in locales:
            capture_locale(page, base_url, loc)
        # Restore prod defaults: English UI, Cosmos (midnight) theme.
        _safe("restore language → en", lambda: _set_language(page, "en"))
        _safe("restore theme → midnight", lambda: _set_theme(page, DEFAULT_THEME_INDEX))
        browser.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("SKOPOS_CAPTURE_URL", "https://skopos.modelmarket.dev/app/"))
    ap.add_argument("--locales", nargs="+", default=["en", "es", "ru"], choices=["en", "es", "ru"])
    args = ap.parse_args()
    password = os.environ.get("SKOPOS_DASHBOARD_PASSWORD", "").strip()
    if not password:
        print("Set SKOPOS_DASHBOARD_PASSWORD", file=sys.stderr)
        return 1
    try:
        capture(args.base_url, password, args.locales)
    except Exception as exc:
        print(f"capture failed: {exc}", file=sys.stderr)
        return 1
    print(f"OK → {SHOTS}/<locale>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
