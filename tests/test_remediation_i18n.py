"""The `remediation:` block must be complete in all five catalogues.

``t`` renders a miss as the dotted key itself and the en fallback is a shallow top-level
``dict.update``, so a block that exists with holes does not fall back to English at all — a single
missing key would put "remediation.section_board" in front of an operator. ``t_or`` keeps that in
English rather than raw, which makes a hole silent instead of loud; these tests are what notices.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from skopos.i18n import SUPPORTED_LOCALES, t

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"
SECTION = "remediation"

#: Keys built by f-string rather than written literally, so a grep of the call sites misses them.
JOB_STATES = ("received", "fixing", "retesting", "deploying", "verifying", "done", "failed",
              "escalated")
QUEUE_STATES = ("pending", "claimed", "reported")
A2A_DIRECTIONS = ("in", "out")
A2A_STATES = ("completed", "working", "submitted", "rejected", "failed")


def _catalog(locale: str) -> dict:
    return yaml.safe_load((LOCALES_DIR / f"{locale}.yaml").read_text(encoding="utf-8"))


def _called_keys() -> set[str]:
    """Every literal ``remediation.*`` key in the page and the two section modules."""
    root = LOCALES_DIR.parent
    sources = [root / "pages" / "7_Remediation.py",
               root / "skopos" / "ui_remediation.py",
               root / "skopos" / "ui_a2a.py"]
    found: set[str] = set()
    for src in sources:
        # the closing quote is what makes it a whole key: an f-string prefix such as
        # "remediation.state_{key}" stops at a brace and is covered by the enum test below.
        found |= set(re.findall(r"""remediation\.([a-z0-9_]+)(?=["'])""",
                                src.read_text(encoding="utf-8")))
    return found


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_remediation_block_present(locale):
    assert SECTION in _catalog(locale), f"{locale}.yaml has no {SECTION}: block"


@pytest.mark.parametrize("locale", [loc for loc in SUPPORTED_LOCALES if loc != "en"])
def test_remediation_key_set_matches_english(locale):
    """Identical key sets — partial coverage is worse than none, since it cannot fall back."""
    base = set(_catalog("en")[SECTION])
    other = set(_catalog(locale)[SECTION])
    assert not base - other, f"{locale}.yaml missing: {sorted(base - other)}"
    assert not other - base, f"{locale}.yaml has extra: {sorted(other - base)}"


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_yes_no_keys_survive_yaml_booleans(locale):
    """`yes:`/`no:` unquoted are YAML 1.1 booleans, and t() would never find them again."""
    block = _catalog(locale)[SECTION]
    assert not [k for k in block if not isinstance(k, str)], "boolean-coerced key"
    for key in ("yes", "no", "unknown"):
        assert t(f"{SECTION}.{key}", locale) != f"{SECTION}.{key}"


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_every_called_key_resolves(locale):
    for name in sorted(_called_keys()):
        key = f"{SECTION}.{name}"
        assert t(key, locale) != key, f"{locale}: {key} unresolved"


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_enum_label_keys_resolve(locale):
    """The f-string keys: one label per JobState, queue state, A2A direction and A2A task state."""
    names = ([f"state_{s}" for s in JOB_STATES]
             + [f"queue_{s}" for s in QUEUE_STATES]
             + [f"a2a_dir_{d}" for d in A2A_DIRECTIONS]
             + [f"a2a_state_{s}" for s in A2A_STATES])
    for name in names:
        key = f"{SECTION}.{name}"
        assert t(key, locale) != key, f"{locale}: {key} unresolved"


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_nav_label_present(locale):
    assert t("app.remediation", locale) != "app.remediation"
    # the sidebar and the hero must not disagree about the page's name
    assert t("app.remediation", locale) == t(f"{SECTION}.title", locale)


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_placeholders_preserved(locale):
    """A dropped placeholder silently loses the only number in the sentence."""
    assert "X" in t(f"{SECTION}.store_unreachable", locale, error="X")
    assert "7" in t(f"{SECTION}.rows_unreadable", locale, n=7)
    assert "why" in t(f"{SECTION}.agent_refused", locale, reason="why")
    assert "TS" in t(f"{SECTION}.last_update", locale, ts="TS")
    window = t(f"{SECTION}.window_truncated", locale, shown=12, total=99)
    assert "12" in window and "99" in window


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_empty_states_stay_honest(locale):
    """The empty state says nothing happened; it must not read as a clean bill of health."""
    for key in ("empty_no_channel", "empty_nothing_pushed", "a2a_empty", "a2a_empty_no_channel",
                "a2a_empty_no_contract"):
        text = t(f"{SECTION}.{key}", locale)
        assert text != f"{SECTION}.{key}"
        assert "✅" not in text and "fixed" not in text.lower()


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_identifiers_are_not_translated(locale):
    """Product names, the A2A protocol tokens and the JobState vocabulary stay verbatim."""
    assert "MOMUS" in t(f"{SECTION}.col_gate", locale)
    assert "MOMUS" in t(f"{SECTION}.detail_gate", locale)
    assert "A2A" in t(f"{SECTION}.section_a2a", locale)
    assert "SKOPOS" in t(f"{SECTION}.source_note", locale)
    for state in JOB_STATES:
        # the enum token is the anchor; anything localized rides in parentheses next to it
        assert state in t(f"{SECTION}.state_{state}", locale).replace("re-testing", "retesting")
    for state in A2A_STATES:
        assert t(f"{SECTION}.a2a_state_{state}", locale) == state


@pytest.mark.parametrize("locale", [loc for loc in SUPPORTED_LOCALES if loc != "en"])
def test_short_labels_do_not_blow_up_the_layout(locale):
    """Column headers and the monospace field labels sit in fixed-width furniture."""
    en = _catalog("en")[SECTION]
    other = _catalog(locale)[SECTION]
    for name, text in other.items():
        if not isinstance(name, str) or not name.startswith(("col_", "f_", "kpi_")):
            continue
        if name.endswith("_hint"):
            continue
        budget = max(len(en[name]) * 3, 24)
        assert len(text) <= budget, f"{locale}.{name} is {len(text)} chars (budget {budget})"
