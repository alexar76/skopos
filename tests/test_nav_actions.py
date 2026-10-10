"""Tests for allowlisted agent navigation tags."""

from __future__ import annotations

from skopos.agent.nav_actions import extract_nav_actions, normalize_page_key


def test_extract_nav_observability_hub():
    clean, actions = extract_nav_actions(
        "Hub looks healthy. Open the Hub dashboard.\n\n[[nav:observability/hub]]"
    )
    assert "[[nav:" not in clean
    assert "Hub looks healthy" in clean
    assert len(actions) == 1
    assert actions[0].page == "observability"
    assert actions[0].tab == "hub"
    assert actions[0].to_dict() == {"type": "navigate", "page": "observability", "tab": "hub"}


def test_extract_nav_rejects_unknown_page_and_tab():
    clean, actions = extract_nav_actions("Nope [[nav:evil/xss]] [[nav:security/notabs]]")
    assert actions == [] or all(a.page != "evil" for a in actions)
    # unknown page stripped; unknown tab → page-only if page known
    clean2, actions2 = extract_nav_actions("See ports [[nav:security/notabs]]")
    assert len(actions2) == 1
    assert actions2[0].page == "security"
    assert actions2[0].tab is None
    assert "[[nav:" not in clean2


def test_extract_nav_max_two_actions():
    _, actions = extract_nav_actions(
        "[[nav:security/ports]] [[nav:observability/hub]] [[nav:analytics/geo]]"
    )
    assert len(actions) == 2


def test_normalize_page_aliases():
    assert normalize_page_key("dashboard") == "analytics"
    assert normalize_page_key("scan_history") == "history"
    assert normalize_page_key("Observability") == "observability"
    assert normalize_page_key("nope") is None
