# Use Cases

## 1. Production traffic overview

**Goal:** See all HTTP requests across your server fleet.

1. Configure `servers.yaml` with SSH + nginx logs
2. Run collector (`skoposctl collect` or dashboard auto-collect)
3. Open **Analytics → Overview**
4. Filter by server, host, country, path

**Value:** GA-like view without installing trackers on sites.

---

## 2. Geographic audience analysis

**Goal:** Understand where visitors come from.

1. Ensure GeoIP works (MaxMind MMDB or ip-api fallback)
2. Open **Analytics → Geography**
3. Toggle map between requests and unique users

**Value:** Country-level marketing and CDN decisions.

---

## 3. Security posture audit

**Goal:** Know what's exposed on each server.

1. Run `python skoposctl.py security-scan`
2. Open **Security → Ports**
3. Review public vs localhost bindings
4. Check **Audit** tab for rule-based findings
5. Open **3D Threat Map** for visual topology (use fullscreen for presentations)

**Value:** Quick answer to "what's open to the internet?"

---

## 4. Resource health monitoring

**Goal:** CPU, memory, disk before incidents.

1. Enable **Auto security scan** in Settings (default 60 min)
2. **Security → Resources** — gauges + disk charts
3. Or schedule via cron:

```bash
*/15 * * * * cd /path/skopos && .venv/bin/python skoposctl.py security-scan
```

---

## 5. AI-assisted incident response

**Goal:** Expert analysis without manual log diving.

1. Set `OPENROUTER_API_KEY` (default provider in `agent.yaml`)
2. Run security scan + traffic collect
3. **Security → Security Report** — full prioritized remediation report
4. Sidebar agent: "Which IPs are scanning us?" / "Should we close port 8443?" (voice input supported)

**Value:** Context-aware answers using live snapshot, HTTP logs, and scan history.

---

## 6. Track security improvements over time

**Goal:** Prove remediation worked after changes.

1. Run scans before and after fixes
2. Open **Scan History**
3. Compare two snapshots — see resolved vs new findings
4. Review score timeline for fleet-wide trend

**Value:** Audit trail for compliance and post-incident reviews.

---

## 7. Multi-language ops team

**Goal:** English, Russian, or Spanish UI.

1. Sidebar → **Language**
2. Add new locale: copy `locales/en.yaml` → `locales/de.yaml`, translate keys

---

## 8. Custom LLM provider

**Goal:** Use Ollama locally or OpenAI/Anthropic.

Edit `agent.yaml`:

```yaml
default_provider: ollama
providers:
  ollama:
    kind: ollama
    base_url: http://127.0.0.1:11434/v1
    model: llama3.2
```

Supported kinds: `openai_compatible`, `anthropic_compatible`, `ollama`, `lmstudio`.

---

## Recommended first-run path

1. **Settings** — add servers and test SSH
2. **Analytics** — collect traffic, explore Overview
3. **Security** — run first scan, read **Security Report**
4. Enable auto-scan in Settings
5. Return to **Scan History** after a few scans to see trends
