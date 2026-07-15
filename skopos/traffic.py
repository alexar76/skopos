from __future__ import annotations

import re

# Healthchecks / internal polling — hide by default in visitor views.
SERVICE_UA_PATTERN = re.compile(
    r"(?i)^(alien-monitor|node|dioscuri|python-httpx|TLM-Audit|AlienMonitor|Go-http-client|curl|wget|okhttp)",
)
SERVICE_PATH_PATTERN = re.compile(
    r"(?i)(/api/health$|/monitor/api/state|/monitor/api/argus/run|/monitor/api/chain/status|/monitor/api/health$)",
)


def is_service_traffic(*, user_agent: str | None, path: str | None) -> bool:
    ua = (user_agent or "").strip()
    p = path or ""
    if ua and SERVICE_UA_PATTERN.search(ua):
        return True
    if p and SERVICE_PATH_PATTERN.search(p):
        return True
    return False


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
