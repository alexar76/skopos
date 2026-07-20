# Changelog

All notable changes to SKOPOS (self-hosted nginx analytics & AI security) are documented here.

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
