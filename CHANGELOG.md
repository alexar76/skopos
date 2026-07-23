# Changelog

All notable changes to SKOPOS (self-hosted nginx analytics & AI security) are documented here.

## [0.1.4] — 2026-07-20

### Added
- **People (est.) KPI** — GA-comparable visitor estimate: unique IPs that fetched a page document AND its assets from a non-datacenter network. Replay fleets (identical-UA proxy botnets requesting only APIs/RSC payloads) and scanners (pages without assets) are excluded — UA filters alone cannot catch bots with perfect browser UAs
- **Hide datacenter IPs** filter (4th checkbox) — offline IP→ASN enrichment via the free iptoasn.com dump (`scripts/install_iptoasn.sh`, no license key); new `asn`/`asn_org` columns, `skoposctl backfill-asn` for existing rows
- **Data coverage notice** — when the selected period extends beyond ingested logs (e.g. 30d picker over 6 days of logs), the Analytics header now says where data actually starts; explains most "Skopos vs GA" mismatch

### Fixed
- Hide bots left ~90% non-human traffic in "unique IPs": a 72-IP residential-proxy fleet with identical `X11 Chrome/149` UA and Tencent-cloud fake-iPhone probes passed all UA heuristics

## [Unreleased]

### Added
- **Security Report** tab — consolidated AI remediation report with Markdown export
- **Scan History** page — score timeline, trends, scan comparison
- **Auto security scan** — configurable interval in Settings (default 60 min)
- **Voice input** for sidebar AI agent (Web Speech API)
- **Fullscreen mode** for 3D threat map and traffic globe
- Cyberpunk 3D threat map — server rack, textured globe, aggregated alerts
- Getting-started onboarding checklists (Analytics & Security)
- **Quick Start wizard** — guided setup page (server, SSH, collect, scan)
- Sidebar product tagline and password-protected dashboard warning
- MIT LICENSE, updated docs and README for discoverability

### Changed
- Streamlit page URLs without emoji in filenames (`pages/1_Security.py`, etc.)
- Browser tab titles: `SKOPOS — …` on all pages
- README aligned with OpenRouter default in `agent.yaml`
- RU/ES locale fixes for Settings strings

### Fixed
- Duplicate docker disk findings on 3D map and in audit
- Fullscreen chart CSS (`Theme.app_bg`)
- Scan history query layer for AI agent context
- Security hardening: SSH log fetch quoting, auto-scan import bug, auth lockout/session TTL, LLM auth-log redaction, custom SSH commands gated, config path traversal guard, alert XSS escape, GeoIP HTTPS, DB permissions, CDN-free voice component

## [0.1.3] — 2026-07-20

### Fixed
- **Hide bots / Hide service** still left mass scanner + ecosystem noise in KPIs (websiphon, libredtail, l9explore, empty UA, AIMarketHub, python-requests, …)
- Expanded bot/scanner heuristics and service UA/path lists; empty `-` UA treated as bot

## [0.1.2] — 2026-07-20

### Fixed
- **Hide bots** left crawlers visible when `user_agents` set `is_bot=False` (Applebot, 360Spider, OAI-SearchBot, …)
- Analytics SQL filter now drops heuristic bot UA/browser matches, not only `ua_is_bot=1`
- UA ingest + backfill re-flag false-negative bot rows

## [0.1.1] — 2026-07-20

### Changed
- Analytics KPIs/charts computed via SQL aggregates over the full period (no row sampling / newest-N cap)
- Period filter uses `ts_utc` + partial file-log index; journal still ORDER BY + LIMIT
- Running status pill cleared below the Filters card border

### Fixed
- 24h vs 7d geo charts identical under high traffic
- Duplicate «Unique IPs» column crashing the country summary table

## [0.1.0] — 2026-07

- Initial release: nginx SSH analytics, Security Center, AI agent, i18n (EN/RU/ES)
