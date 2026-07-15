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
    page.wait_for_timeout(6500)


def _login(page, base_url: str, password: str) -> None:
    page.goto(base_url.rstrip("/") + "/", wait_until="domcontentloaded", timeout=120_000)
    _wait_app(page)
    pwd = page.locator('input[type="password"]')
    if pwd.count():
        pwd.fill(password)
        for label in ("Sign in", "Login", "Войти", "Entrar"):
            btn = page.get_by_role("button", name=label)
            if btn.count():
                btn.first.click()
                break
        else:
            page.get_by_role("button").first.click()
        _wait_app(page)


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


def capture(base_url: str, password: str) -> None:
    _ensure_playwright()
    from playwright.sync_api import sync_playwright

    README_OUT.mkdir(parents=True, exist_ok=True)
    THEMES_OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
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

        # Theme gallery on Analytics
        _nav(page, "Analytics", "Аналитика")
        for theme_id, theme_label in THEME_SHOTS:
            _pick_theme(page, theme_label)
            _shot(page, THEMES_OUT / f"analytics-{theme_id}.png")

        browser.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("SKOPOS_CAPTURE_URL", "http://127.0.0.1:8501"))
    args = ap.parse_args()
    password = os.environ.get("SKOPOS_DASHBOARD_PASSWORD", "").strip()
    if not password:
        print("Set SKOPOS_DASHBOARD_PASSWORD", file=sys.stderr)
        return 1
    capture(args.base_url, password)
    print(f"OK → {README_OUT} and {THEMES_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
