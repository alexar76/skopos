"""Smoke-test every Streamlit entrypoint with AppTest."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]

PAGES = [
    ROOT / "dashboard.py",
    ROOT / "pages" / "0_Quick_Start.py",
    ROOT / "pages" / "1_Security.py",
    ROOT / "pages" / "2_Settings.py",
    ROOT / "pages" / "5_Fleet.py",
    ROOT / "pages" / "3_Scan_History.py",
]


@pytest.mark.parametrize("script_path", PAGES, ids=[p.stem for p in PAGES])
def test_page_runs_without_exception(script_path: Path):
    at = AppTest.from_file(str(script_path), default_timeout=120)
    at.run()
    assert not at.exception, _format_exception(at, script_path)


def _format_exception(at: AppTest, script_path: Path) -> str:
    if at.exception is None:
        return ""
    exc = at.exception[0]
    stack = getattr(exc, "stacktrace", None) or getattr(exc, "stack_trace", None) or ""
    return f"{script_path.name}: {exc.type}: {exc.value}\n{stack}"
