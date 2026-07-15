# Konfigurácia

## `servers.yaml`

Každý záznam servera popisuje SSH prístup a **nginx cesty logov**:

```yaml
servers:
  - name: factory
    source: ssh_nginx_access_log
    ssh:
      host: 203.0.113.10
      port: 22
      user: deploy
      key_path: ~/.ssh/id_rsa
    nginx:
      access_log_path: /var/log/nginx/access.log
      auto_discover_logs: true
      auto_discover_docker_logs: false
```

| Pole | Účel |
|------|--------|
| `name` | Štítok v dashboardoch a filtroch |
| `source` | `ssh_nginx_access_log` (len nginx) alebo `ssh_http_access_log` (nginx + voliteľný Apache) |
| `nginx.access_log_path` | Primárny access log súbor |
| `nginx.access_log_paths` | Extra log súbory (multi-site) |
| `nginx.auto_discover_logs` | Parsovať nginx config na hoste pre ďalšie cesty |
| `nginx.auto_discover_docker_logs` | Voliteľne: tail aj verejné Docker HTTP kontajnery |

### Oprávnenia

SSH používateľ musí vedieť **čítať nginx log súbory** (často skupina `adm` na Debian/Ubuntu).

## `agent.yaml`

LLM poskytovatelia pre Security Report a plávajúci agent. Predvolene: **OpenRouter** cez `OPENROUTER_API_KEY`.

## Premenné prostredia

| Pole | Účel |
|------|--------|
| `SKOPOS_DASHBOARD_PASSWORD` | Zdieľané heslo dashboardu (login formulár); v **Nastaveniach** alebo `.env` |
| `SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH` | Minimálna dĺžka nových hesiel (predvolene **12**) |
| `SKOPOS_DASHBOARD_SESSION_HOURS` | Auto odhlásenie po N hodinách (predvolene **12**) |
| `OPENROUTER_API_KEY` | Predvolený LLM poskytovateľ |
| `SKOPOS_SSH_KEY_PASSPHRASE` | Passphrase pre šifrované SSH kľúče |
| `SKOPOS_SSH_STRICT_HOST_KEYS` | `1` na overenie host keys |

## Kde meniť v UI

| Pole | Účel |
|------|--------|
| Jazyk a téma | Spodok bočného panelu |
| Zber / backfill | Bočný panel na **Analytike** |
| Interval auto-scanu | **Nastavenia** |
| Telegram alerty | **Nastavenia** |
| Poskytovateľ bezpečnostného agenta | **Bezpečnosť** → karta AI Agent |

## Settings sections (detail)

| Pole | Účel |
|------|--------|
| Dashboard access | `SKOPOS_DASHBOARD_PASSWORD`, session hours, min length policy |
| Database | `SKOPOS_DATABASE_URL` or SQLite `db_path`; test + migrate in UI |
| Auto-scan | Background security scan interval (minutes) |
| Telegram | `SKOPOS_TELEGRAM_*` env vars; notify on new critical findings |
| SSH keys | Generate Ed25519; keys stored under `.skopos/ssh/` |
| Fleet servers | Visual editor for `servers.yaml` — nginx, Apache, docker logs |

## `agent.yaml` providers

Each provider block needs an API key env var. Default stack uses **OpenRouter** (`OPENROUTER_API_KEY`). Providers appear in Summary Report, floating agent, and Security → AI Agent tab.

| Provider | API key |
|------|--------|
| `openrouter` | `OPENROUTER_API_KEY` — default; many models via one key |
| `openai` | `OPENAI_API_KEY` |
| `anthropic` | `ANTHROPIC_API_KEY` |
| `deepseek` | `DEEPSEEK_API_KEY` |

![Nastavenia a ovládanie bočného panelu](screenshots/settings-fleet.png)

![Sidebar](screenshots/sidebar-nav.png)
