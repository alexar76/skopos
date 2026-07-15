# User Guide

> **HTTP logs:** analytics read **nginx access logs** by default; **Apache combined** is optional. See [HTTP log scope](en/guide/nginx.md).

## Navigation

| Page | Purpose |
|------|---------|
| **Analytics** (main) | HTTP traffic dashboards, geography, audience, journal |
| **Security** | Server monitoring, port audit, 3D threats, Security Report, AI agent |
| **Scan History** | Score timeline, findings trends, snapshot comparison |
| **Settings** | SSH fleet, keys, auto-scan interval, custom commands |

Language selector is in the sidebar (English default). UI strings live in `locales/*.yaml`.

---

## Analytics

### Filters (sidebar)

- **Hide bots** — scanner paths, bot user-agents
- **Hide service traffic** — health checks, internal monitors
- **External IPs only** — exclude private ranges
- **Servers / Addresses / Countries / Path** — narrow scope

### Tabs

| Tab | Content |
|-----|---------|
| Overview | Timeline, countries, top paths/hosts, heatmap |
| Geography | World map, country bars, tables |
| Audience | Browsers, OS, devices, top IPs |
| Content | Page treemap, ecosystem segments |
| Sources | Referrers |
| Journal | Raw visit log with server IP |
| System | Collector status, log sources |

### Data collection

- Background thread polls every 5s (configurable in `servers.yaml`)
- **Collect now** — manual one-shot
- **Backfill all** — re-infer hosts, countries, UA

When no traffic data exists yet, a getting-started checklist appears on the main page.

---

## Security

### Scan

**Scan all servers** runs over SSH:

- CPU, memory, load, disk
- Network counters
- Listening ports (`ss` / `netstat`)
- Firewall status (ufw/iptables)
- Auth log samples (failed SSH)
- Docker containers
- SSHd config hints

Results stored in SQLite (`security_snapshots`, `security_findings`).

### Auto-scan

In **Settings**, enable **Auto security scan** and set the interval (default 60 minutes). Scans run in the background while the dashboard is open.

### Tabs

| Tab | Content |
|-----|---------|
| Overview | Fleet scatter, per-server gauges |
| Ports | Exposure map, table (open/closed) |
| Resources | Gauges, network, disk |
| Audit | Rule-based findings with severity |
| 3D Threat Map | Cyberpunk topology — server rack, globe, aggregated alerts; fullscreen toggle |
| Security Report | Consolidated AI remediation report with Markdown export |
| AI Agent | Quick analysis + legacy export (see Security Report for full report) |

### Severity levels

| Level | Meaning |
|-------|---------|
| Critical | Immediate risk (DB exposed, disk full) |
| High | Serious (brute force, password auth) |
| Medium | Needs attention (high memory, no firewall) |
| Low | Review recommended |
| Info | Informational |

---

## Scan History

Open **Scan History** from the sidebar after at least one security scan.

| Section | Content |
|---------|---------|
| Summary | Total scans, latest score, trend direction |
| Score timeline | Fleet score over time |
| Findings trend | New/resolved findings by severity |
| Compare | Diff two snapshots side by side |
| Calendar | Scan activity heatmap |

The AI agent in the sidebar can reference scan history when answering questions.

---

## AI Agent

### Sidebar agent (all pages)

Chat with context from security snapshots, HTTP traffic, and scan history. Supports **voice input** (Web Speech API in supported browsers).

### Default: OpenRouter

Set environment variable:

```bash
export OPENROUTER_API_KEY=sk-or-...
```

Config: `agent.yaml` → `default_provider: openrouter`

### Security Report vs AI Agent tab

- **Security Report** tab — full consolidated report with prioritized remediation steps and export
- **AI Agent** tab on Security — quick one-shot analysis; sidebar agent for follow-up chat

### Providers

| Provider | Kind | API key env |
|----------|------|-------------|
| OpenRouter | openai_compatible | `OPENROUTER_API_KEY` |
| DeepSeek | openai_compatible | `DEEPSEEK_API_KEY` |
| OpenAI | openai_compatible | `OPENAI_API_KEY` |
| Anthropic | anthropic_compatible | `ANTHROPIC_API_KEY` |
| Ollama | ollama | none |
| LM Studio | lmstudio | none |

---

## Settings

- **Servers** — add/edit SSH targets and nginx log paths
- **SSH keys** — generate keys, copy-id helpers, connection test
- **Auto security scan** — enable and set interval
- **Custom commands** — remote shell shortcuts

---

## CLI reference

```bash
python skoposctl.py discover          # list log sources
python skoposctl.py collect           # fetch nginx logs
python skoposctl.py security-scan     # probe + audit all servers
```

---

## Localization

Files: `locales/en.yaml`, `locales/ru.yaml`, `locales/es.yaml`

Keys use dot notation: `security.title`, `common.run_scan`

Add a language:

1. Create `locales/xx.yaml`
2. Add code to `SUPPORTED_LOCALES` in `skopos/i18n.py`
3. Add label in `locale_label()`

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Empty map (countries) | Run backfill; ensure ISO-2 → ISO-3 conversion |
| Security scan fails | Check SSH key, passphrase env, firewall |
| AI agent no key | Export `OPENROUTER_API_KEY` (or provider key from `agent.yaml`) |
| Dashboard publicly exposed | Set `SKOPOS_DASHBOARD_PASSWORD` |
| metis no file logs | Uses docker `metis-nginx` — see `servers.yaml` |
