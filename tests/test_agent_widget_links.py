"""The assistant widget renders model replies with innerHTML; a quote must not end an attribute.

The model's context includes request paths any internet client chooses (SKOPOS reads the
monitored hosts' access logs), so a reply can carry a crafted markdown link.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

from pathlib import Path

import pytest

# Read as text: importing the module pulls in streamlit, which the widget does not need.
_SRC = (Path(__file__).resolve().parents[1] / "skopos" / "agent_widget.py").read_text(encoding="utf-8")
_WIDGET_JS = _SRC.split('_WIDGET_JS = r"""', 1)[1].split('"""', 1)[0]

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _render(text: str) -> str:
    esc = re.search(r"function esc\(s\) \{.*?\}\n", _WIDGET_JS, re.S).group(0)
    fmt = re.search(r"function fmt\(s\) \{.*?\n  \}\n", _WIDGET_JS, re.S).group(0)
    program = esc + fmt + f"process.stdout.write(fmt({json.dumps(text)}));"
    return subprocess.run([shutil.which("node"), "-e", program], capture_output=True, text=True,
                          check=True, timeout=30).stdout


def test_a_quote_in_a_link_cannot_add_attributes():
    out = _render("see [docs](https://x.example/a'onmouseover='alert(1))")
    assert "onmouseover='" not in out
    assert "&#39;" in out


def test_ordinary_links_still_render():
    out = _render("see [docs](https://skopos.modelmarket.dev/help)")
    assert "<a href='https://skopos.modelmarket.dev/help'" in out
