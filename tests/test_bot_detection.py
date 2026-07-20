"""Bot detection: user_agents miss + Hide bots SQL heuristic."""

from __future__ import annotations

from skopos.analytics_filters import AnalyticsFilterState
from skopos.analytics_queries import filters_sql
from skopos.enrich import parse_user_agent
from skopos.traffic import looks_like_bot


def _filters(**kwargs) -> AnalyticsFilterState:
    base = dict(
        hide_bots=True,
        hide_service=False,
        visitors_only=False,
        sel_servers=[],
        sel_hosts=[],
        sel_countries=[],
        path_contains="",
    )
    base.update(kwargs)
    return AnalyticsFilterState(**base)


def test_looks_like_bot_catches_applebot_family():
    assert looks_like_bot(ua_browser="Applebot")
    assert looks_like_bot(ua_browser="360Spider")
    assert looks_like_bot(ua_browser="OAI-SearchBot")
    assert not looks_like_bot(ua_browser="Chrome")


def test_parse_user_agent_flags_missed_crawlers():
    apple = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.4 Safari/605.1.15 "
        "(Applebot/0.1; +http://www.apple.com/go/applebot)"
    )
    spider = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36 360Spider"
    )
    chrome = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    assert parse_user_agent(apple).is_bot is True
    assert parse_user_agent(spider).is_bot is True
    assert parse_user_agent(chrome).is_bot is False


def test_hide_bots_sql_excludes_heuristic_ua():
    sql, params = filters_sql(_filters(hide_bots=True), backend="postgresql")
    assert "ua_is_bot = 1" in sql
    assert "LOWER(COALESCE(user_agent, '')) LIKE ?" in sql
    assert "%applebot%" in params or "%bot%" in params
    assert "NOT (" in sql
