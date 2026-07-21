#!/usr/bin/env python3
"""Capture README hero + per-theme gallery from a running SKOPOS instance.

Usage:
  export SKOPOS_DASHBOARD_PASSWORD=...
  pip install playwright pillow && playwright install chromium
  python scripts/capture_readme_screenshots.py --base-url https://skopos.modelmarket.dev/app/
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
README_OUT = OUT / "readme"
THEMES_OUT = OUT / "themes"

# (theme_id, label in Theme selectbox — English UI on prod)
THEME_SHOTS: tuple[tuple[str, str], ...] = (
    ("light", "Light"),
    ("premium", "Premium"),
    ("midnight", "Cosmos"),
    ("ocean", "Ocean"),
    ("aurora", "Aurora"),
    ("slate", "Slate"),
)


def _ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright", "pillow", "-q"])
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])


def _wait_app(page) -> None:
    page.wait_for_selector('[data-testid="stApp"]', timeout=120_000)
    page.wait_for_timeout(5000)


def _is_logged_in(page) -> bool:
    if page.locator('input[type="password"]').count():
        return False
    return page.locator('section[data-testid="stSidebar"]').count() > 0


def _submit_login(page) -> None:
    submit = page.locator('[data-testid="stFormSubmitButton"] button')
    if submit.count():
        submit.first.click()
        return
    for label in ("Sign in", "Login", "Войти", "Entrar"):
        btn = page.get_by_role("button", name=label)
        if btn.count():
            btn.first.click()
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
        "() => !document.querySelector('input[type=\"password\"]')",
        timeout=60_000,
    )
    page.wait_for_selector('section[data-testid="stSidebar"]', timeout=60_000)
    _wait_app(page)
    if not _is_logged_in(page):
        err = page.locator('[data-testid="stAlert"]').first
        detail = err.inner_text() if err.count() else "unknown login failure"
        raise RuntimeError(f"login failed: {detail}")


def _scroll_sidebar(page) -> None:
    sidebar = page.locator('section[data-testid="stSidebar"]').first
    if sidebar.count():
        sidebar.evaluate("el => { el.scrollTop = el.scrollHeight; }")
        page.wait_for_timeout(600)


def _theme_selectbox(page):
    _scroll_sidebar(page)
    sidebar = page.locator('section[data-testid="stSidebar"]').first
    return sidebar.locator('[data-testid="stSelectbox"]').nth(1)


def _pick_theme(page, label: str) -> None:
    box = _theme_selectbox(page)
    box.locator('[data-baseweb="select"]').click()
    page.locator('[data-baseweb="popover"] [role="option"]').filter(has_text=label).first.click()
    page.wait_for_timeout(3200)


def _scroll_to_charts(page) -> None:
    """Scroll the main container so the first traffic chart sits near the top.

    The Analytics gallery must showcase the dashboards (traffic timeline +
    country donuts), not the page header. Streamlit scrolls an inner
    ``section.main`` container (not the window), so window.scrollTo / full_page
    do nothing here — we must move that element and anchor on the first
    Plotly chart, which renders asynchronously after a theme switch.

    Async fragments (e.g. the AI ecosystem-health card) can rerun *after* we
    scroll and reset scrollTop to 0, so we scroll → wait → verify → repeat
    until the first chart actually settles near the viewport top.
    """
    anchor = 90
    for _ in range(10):
        top = page.evaluate(
            """(anchor) => {
          const main = document.querySelector('section.main')
            || document.querySelector('[data-testid="stMain"]')
            || document.scrollingElement;
          const chart = document.querySelector(
            '[data-testid="stPlotlyChart"], .js-plotly-plot');
          if (!main || !chart) return null;
          const mTop = main.getBoundingClientRect().top;
          const cTop = chart.getBoundingClientRect().top;
          main.scrollTop += (cTop - mTop) - anchor;
          return chart.getBoundingClientRect().top - main.getBoundingClientRect().top;
        }""",
            anchor,
        )
        page.wait_for_timeout(1400)
        # verify it stuck (guards against a late rerun snapping back to top)
        settled = page.evaluate(
            """(anchor) => {
          const main = document.querySelector('section.main')
            || document.querySelector('[data-testid="stMain"]')
            || document.scrollingElement;
          const chart = document.querySelector(
            '[data-testid="stPlotlyChart"], .js-plotly-plot');
          if (!main || !chart) return false;
          const rel = chart.getBoundingClientRect().top - main.getBoundingClientRect().top;
          return Math.abs(rel - anchor) < 60;
        }""",
            anchor,
        )
        if settled:
            break
    page.wait_for_timeout(800)


def _shot(page, path: Path, *, full_page: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=full_page)
    if path.stat().st_size < 8000:
        raise RuntimeError(f"screenshot too small: {path} ({path.stat().st_size} bytes)")


def _make_hero_banner(analytics: Path, security: Path, out: Path) -> None:
    from PIL import Image

    a = Image.open(analytics).convert("RGB")
    s = Image.open(security).convert("RGB")
    target_h = 720
    a = _fit_height(a, target_h)
    s = _fit_height(s, target_h)
    gap = 12
    canvas = Image.new("RGB", (a.width + gap + s.width, target_h), (8, 6, 12))
    canvas.paste(a, (0, 0))
    canvas.paste(s, (a.width + gap, 0))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, format="PNG", optimize=True)


def _fit_height(img, h: int):
    from PIL import Image

    if img.height == h:
        return img
    w = max(1, int(img.width * h / img.height))
    return img.resize((w, h), Image.Resampling.LANCZOS)


def _nav(page, *names: str) -> None:
    for name in names:
        link = page.locator('section[data-testid="stSidebar"] [data-testid="stPageLink"] a').filter(
            has_text=name
        )
        if link.count():
            link.first.click()
            _wait_app(page)
            return
    raise RuntimeError(f"sidebar nav not found: {names}")


def _capture_login_gate(page, base_url: str, out_dir: Path) -> None:
    page.goto(base_url.rstrip("/") + "/", wait_until="domcontentloaded", timeout=120_000)
    _wait_app(page)
    pwd = page.locator('input[type="password"]')
    if not pwd.count():
        return
    for path in (out_dir / "login-gate.png", out_dir / "en" / "login-gate.png"):
        _shot(page, path)


def _wait_agent_fab(page) -> None:
    page.wait_for_function(
        "() => document.querySelector('.stats-agent-anchor')",
        timeout=120_000,
    )
    page.wait_for_timeout(2000)


def _click_agent_fab(page) -> None:
    _wait_agent_fab(page)
    buttons = page.locator('button').filter(has_text="chat")
    for i in range(buttons.count()):
        btn = buttons.nth(i)
        box = btn.bounding_box()
        if box and box["width"] > 10:
            btn.click()
            break
    else:
        raise RuntimeError("floating agent FAB not found")
    page.wait_for_function(
        "() => !!document.querySelector('.stats-agent-root--open')",
        timeout=30_000,
    )
    page.wait_for_timeout(2500)


def _shot_agent_panel(page, path: Path) -> None:
    """Capture the opened floating panel (portaled to body)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    portal = page.locator(".skopos-agent-portal--open").first
    if portal.count():
        portal.screenshot(path=str(path))
        if path.stat().st_size >= 8000:
            return
    host = page.locator('[data-testid="stFragment"]:has(.stats-agent-root--open)').first
    if host.count():
        host.screenshot(path=str(path))
        if path.stat().st_size >= 8000:
            return
    _shot(page, path, full_page=False)


def _capture_floating_agent(page, out_dir: Path) -> None:
    _nav(page, "Security", "Безопасность")
    page.wait_for_timeout(4000)
    _wait_agent_fab(page)
    for sub in ("", "en", "ru"):
        target = out_dir / sub / "floating-agent-fab.png" if sub else out_dir / "floating-agent-fab.png"
        _shot(page, target)
    _click_agent_fab(page)
    page.wait_for_selector("textarea", timeout=30_000)
    page.wait_for_timeout(1500)
    for sub, name in (("", "floating-agent.png"), ("en", "floating-agent.png"), ("ru", "floating-agent.png")):
        target = out_dir / sub / name if sub else out_dir / name
        _shot_agent_panel(page, target)


def _capture_theme_gallery(page) -> None:
    """Analytics dashboards (traffic timeline + country donuts) per theme."""
    _nav(page, "Analytics", "Аналитика")
    for theme_id, theme_label in THEME_SHOTS:
        _pick_theme(page, theme_label)
        _scroll_to_charts(page)
        _shot(page, THEMES_OUT / f"analytics-{theme_id}.png")


def capture(base_url: str, password: str, *, gallery_only: bool = False) -> None:
    _ensure_playwright()
    from playwright.sync_api import sync_playwright

    README_OUT.mkdir(parents=True, exist_ok=True)
    THEMES_OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)

        if gallery_only:
            _login(page, base_url, password)
            _capture_theme_gallery(page)
            browser.close()
            return

        _capture_login_gate(page, base_url, OUT)
        _login(page, base_url, password)

        # Analytics — Cosmos (midnight) for hero
        _pick_theme(page, "Cosmos")
        analytics_path = README_OUT / "hero-analytics-midnight.png"
        _shot(page, analytics_path)

        # Security → 3D Threat Map
        _nav(page, "Security", "Безопасность")
        for tab_name in ("3D Threat Map", "3D-карта", "3D"):
            tab = page.get_by_role("tab", name=tab_name)
            if tab.count():
                tab.first.click()
                break
        page.wait_for_timeout(4000)
        security_path = README_OUT / "hero-security-3d.png"
        _shot(page, security_path)

        # Production may show onboarding instead of tabs — reuse bundled 3D capture.
        fallback_3d = OUT / "en" / "security-3d-map.png"
        if fallback_3d.is_file() and "3D Threat" not in page.inner_text("body"):
            import shutil

            shutil.copy2(fallback_3d, security_path)

        _make_hero_banner(analytics_path, security_path, README_OUT / "hero-banner.png")

        _capture_floating_agent(page, OUT)

        # Theme gallery on Analytics — dashboards with charts
        _capture_theme_gallery(page)

        browser.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("SKOPOS_CAPTURE_URL", "http://127.0.0.1:8501"))
    ap.add_argument(
        "--gallery-only",
        action="store_true",
        help="Only regenerate the per-theme Analytics dashboard gallery",
    )
    args = ap.parse_args()
    password = os.environ.get("SKOPOS_DASHBOARD_PASSWORD", "").strip()
    if not password:
        print("Set SKOPOS_DASHBOARD_PASSWORD", file=sys.stderr)
        return 1
    try:
        capture(args.base_url, password, gallery_only=args.gallery_only)
    except Exception as exc:
        print(f"capture failed: {exc}", file=sys.stderr)
        return 1
    print(f"OK → {README_OUT} and {THEMES_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
