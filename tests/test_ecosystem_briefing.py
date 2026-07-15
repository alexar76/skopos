from __future__ import annotations

import pandas as pd

from skopos.agent.ecosystem_briefing import (
    _briefing_looks_incomplete,
    _normalize_briefing_text,
    fallback_ecosystem_briefing,
    traffic_snapshot_from_df,
)
from skopos.security.posture import SecurityPosture, ServerScore

def test_traffic_snapshot():
    df = pd.DataFrame(
        {
            "remote_addr": ["1.1.1.1", "2.2.2.2", "1.1.1.1"],
            "host": ["a.example", "b.example", "a.example"],
            "status": [200, 500, 200],
            "ecosystem_segment": ["lottery", "oracles", "lottery"],
        }
    )
    snap = traffic_snapshot_from_df(df)
    assert snap is not None
    assert snap.requests == 3
    assert snap.unique_ips == 2
    assert snap.top_segment == "lottery"
    assert snap.error_rate_pct == 33.3


def test_fallback_briefing_russian():
    posture = SecurityPosture(
        fleet_score=38,
        grade="F",
        server_scores=[ServerScore("factory", 35, "F")],
        alerts=[],
        remarks=["SSH: PasswordAuthentication enabled on 2 server(s) — disable immediately."],
        computed_at_utc="2026-01-01T00:00:00+00:00",
    )
    snap = traffic_snapshot_from_df(
        pd.DataFrame(
            {
                "remote_addr": ["1.1.1.1"] * 10,
                "host": ["x"] * 10,
                "status": [200] * 10,
                "ecosystem_segment": ["lottery"] * 10,
            }
        )
    )
    b = fallback_ecosystem_briefing(posture, snap, locale="ru")
    assert b.source == "rules_no_key"
    assert b.mood == "urgent"
    assert "38" in b.text
    assert "запросов" in b.text.lower() or "За выбранный" in b.text


def test_fallback_briefing_english_good():
    posture = SecurityPosture(
        fleet_score=88,
        grade="B",
        server_scores=[],
        alerts=[],
        remarks=[],
        computed_at_utc="2026-01-01T00:00:00+00:00",
    )
    b = fallback_ecosystem_briefing(posture, None, locale="en")
    assert b.mood == "good"
    assert "calm" in b.text.lower() or "stable" in b.text.lower()


def test_briefing_incomplete_detects_truncated_tail():
    long_para = (
        "Доброе утро. Ситуация по флоту требует срочного внимания: общий балл безопасности "
        "38 из 100 (оценка F), и сейчас активно 80 критических алертов — оставлять это без реакции нельзя."
    )
    text = f"{long_para}\n\nЗдорового нем"
    assert _briefing_looks_incomplete(text) is True


def test_briefing_complete_fallback_russian():
    posture = SecurityPosture(
        fleet_score=38,
        grade="F",
        server_scores=[ServerScore("factory", 35, "F")],
        alerts=[],
        remarks=["SSH: PasswordAuthentication enabled on 2 server(s) — disable immediately."],
        computed_at_utc="2026-01-01T00:00:00+00:00",
    )
    snap = traffic_snapshot_from_df(
        pd.DataFrame(
            {
                "remote_addr": ["1.1.1.1"] * 10,
                "host": ["x"] * 10,
                "status": [200] * 10,
                "ecosystem_segment": ["lottery"] * 10,
            }
        )
    )
    b = fallback_ecosystem_briefing(posture, snap, locale="ru")
    assert _briefing_looks_incomplete(b.text) is False
    assert _normalize_briefing_text("**Hello**") == "Hello"
