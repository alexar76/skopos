from __future__ import annotations

import re

# Healthchecks / internal polling — hide by default in visitor views.
SERVICE_UA_PATTERN = re.compile(
    r"(?i)^(?:alien-monitor|node|dioscuri|python-httpx|TLM-Audit|AlienMonitor|Go-http-client|curl|wget|okhttp)",
)
SERVICE_PATH_PATTERN = re.compile(
    r"(?i)(?:/api/health$|/monitor/api/state|/monitor/api/argus/run|/monitor/api/chain/status|/monitor/api/health$)",
)

# user_agents.is_bot misses common crawlers (Applebot, 360Spider, OAI-SearchBot, …).
# Used at ingest + as a SQL safety net for Hide bots.
BOT_UA_HINT = re.compile(
    r"(?i)(?:"
    r"\bbot\b|crawl|spider|slurp|scrapy|httpclient|wget|curl|"
    r"facebookexternalhit|bytespider|semrush|ahrefs|petal|yandex|"
    r"duckduck|baidu|sogou|seznam|applebot|bingpreview|gptbot|"
    r"claudebot|oai-search|360spider|trendiction|dotbot|mj12bot|"
    r"rogerbot|linkedinbot|twitterbot|slackbot|discordbot|telegrambot"
    r")"
)

# LIKE fragments for SQL hide_bots (lowercase; match LOWER(user_agent/ua_browser)).
BOT_UA_SQL_LIKES = (
    "%bot%",
    "%crawl%",
    "%spider%",
    "%slurp%",
    "%facebookexternalhit%",
    "%bytespider%",
    "%semrush%",
    "%ahrefs%",
    "%petalbot%",
    "%yandex%",
    "%duckduck%",
    "%baidu%",
    "%sogou%",
    "%applebot%",
    "%bingpreview%",
    "%gptbot%",
    "%claudebot%",
    "%oai-search%",
    "%360spider%",
    "%trendiction%",
    "%mj12bot%",
    "%dotbot%",
)


def looks_like_bot(*, user_agent: str | None = None, ua_browser: str | None = None) -> bool:
    """Heuristic bot flag beyond user_agents.parse().is_bot."""
    for part in (user_agent, ua_browser):
        raw = (part or "").strip()
        if raw and raw != "-" and BOT_UA_HINT.search(raw):
            return True
    return False


def is_service_traffic(*, user_agent: str | None, path: str | None) -> bool:
    ua = (user_agent or "").strip()
    p = path or ""
    if ua and SERVICE_UA_PATTERN.search(ua):
        return True
    if p and SERVICE_PATH_PATTERN.search(p):
        return True
    return False


def service_traffic_mask(user_agents, paths) -> "pd.Series":
    """Vectorized hide-service mask (True = service traffic)."""
    import pandas as pd

    ua = pd.Series(user_agents, dtype="object").fillna("").astype(str).str.strip()
    path = pd.Series(paths, dtype="object").fillna("").astype(str)
    return ua.str.contains(SERVICE_UA_PATTERN) | path.str.contains(SERVICE_PATH_PATTERN)


def client_label(user_agent: str | None, ua_browser: str | None) -> str:
    ua = (user_agent or "").strip()
    if ua_browser and ua_browser not in ("Other", "None"):
        return ua_browser
    if not ua or ua == "-":
        return "—"
    if ua.startswith("Mozilla/"):
        return ua_browser or "Browser"
    # Service / bot client id: "TLM-Audit-Scanner/1.0" -> TLM-Audit-Scanner
    return ua.split("/")[0][:48] or ua[:48]
