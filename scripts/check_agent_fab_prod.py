#!/usr/bin/env python3
"""Headless check: floating agent FAB visible on prod Security page."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from capture_readme_screenshots import _login, _nav  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def main() -> int:
    url = os.environ.get("SKOPOS_URL", "https://skopos.modelmarket.dev/app/")
    pwd = os.environ.get("SKOPOS_DASHBOARD_PASSWORD", "").strip()
    if not pwd:
        print("SKOPOS_DASHBOARD_PASSWORD required", file=sys.stderr)
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        _login(page, url, pwd)
        _nav(page, "Security", "Безопасность")
        page.wait_for_timeout(20_000)
        info = page.evaluate(
            """() => ({
              url: location.href,
              loggedIn: !document.querySelector('input[type="password"]'),
              overlay: !!document.getElementById('skopos-agent-fab-overlay'),
              overlayRect: (() => {
                const el = document.getElementById('skopos-agent-fab-overlay');
                return el ? el.getBoundingClientRect() : null;
              })(),
              fabSlot: document.querySelectorAll('.stats-agent-fab-slot').length,
              closedRoot: document.querySelectorAll('.stats-agent-root--closed').length,
              vw: innerWidth,
              vh: innerHeight,
            })"""
        )
        print(json.dumps(info, indent=2))
        browser.close()

    ok = bool(info.get("loggedIn")) and bool(info.get("overlay"))
    rect = info.get("overlayRect") or {}
    ok = ok and (rect.get("width") or 0) >= 50 and (rect.get("height") or 0) >= 50
    ok = ok and rect.get("right", 0) > info.get("vw", 0) - 120
    ok = ok and rect.get("bottom", 0) > info.get("vh", 0) - 120
    ok = ok and (rect.get("top") or 0) >= 0 and (rect.get("top") or 0) < info.get("vh", 0)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
