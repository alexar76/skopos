# Konfiguration

## `servers.yaml`

Jeder Server-Eintrag beschreibt SSH-Zugang und **nginx-Log-Pfade**:

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

| Feld | Zweck |
|------|--------|
| `name` | Bezeichnung in Dashboards und Filtern |
| `source` | `ssh_nginx_access_log` (nur nginx) oder `ssh_http_access_log` (nginx + optional Apache) |
| `nginx.access_log_path` | Primäre Access-Log-Datei |
| `nginx.access_log_paths` | Zusätzliche Log-Dateien (Multi-Site) |
| `nginx.auto_discover_logs` | nginx-Configs auf dem Host nach weiteren Pfaden parsen |
| `nginx.auto_discover_docker_logs` | Optional: auch öffentliche Docker-HTTP-Container tailen |

### Berechtigungen

Der SSH-Benutzer muss **nginx-Log-Dateien lesen** können (oft Gruppe `adm` unter Debian/Ubuntu).

## `agent.yaml`

LLM-Anbieter für Security Report und schwebenden Agenten. Standard: **OpenRouter** via `OPENROUTER_API_KEY`.

## Umgebungsvariablen

| Feld | Zweck |
|------|--------|
| `SKOPOS_DASHBOARD_PASSWORD` | Gemeinsames Dashboard-Passwort (Login-Formular); in **Einstellungen** oder `.env` |
| `SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH` | Mindestlänge neuer Passwörter (Standard **12**) |
| `SKOPOS_DASHBOARD_SESSION_HOURS` | Auto-Abmeldung nach N Stunden (Standard **12**) |
| `OPENROUTER_API_KEY` | Standard-LLM-Anbieter |
| `SKOPOS_SSH_KEY_PASSPHRASE` | Passphrase für verschlüsselte SSH-Schlüssel |
| `SKOPOS_SSH_STRICT_HOST_KEYS` | `1` zur Host-Key-Prüfung |

## Wo in der UI ändern

| Feld | Zweck |
|------|--------|
| Sprache & Theme | Unten in der Seitenleiste |
| Sammlung / Backfill | Seitenleiste bei **Analytik** |
| Auto-Scan-Intervall | **Einstellungen** |
| Telegram-Alerts | **Einstellungen** |
| Security-Agent-Anbieter | **Sicherheit** → Tab AI Agent |

## Settings sections (detail)

| Feld | Zweck |
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

![Einstellungen und Seitenleisten-Steuerung](../../screenshots/settings-fleet.png)

![Sidebar](../../screenshots/sidebar-nav.png)
