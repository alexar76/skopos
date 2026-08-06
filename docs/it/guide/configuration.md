# Configurazione

## `servers.yaml`

Ogni voce server descrive accesso SSH e **percorsi log nginx**:

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

| Campo | Scopo |
|------|--------|
| `name` | Etichetta in dashboard e filtri |
| `source` | `ssh_nginx_access_log` (solo nginx) o `ssh_http_access_log` (nginx + Apache opzionale) |
| `nginx.access_log_path` | File access log principale |
| `nginx.access_log_paths` | File log aggiuntivi (multi-sito) |
| `nginx.auto_discover_logs` | Analizza config nginx sull'host per altri percorsi |
| `nginx.auto_discover_docker_logs` | Opzionale: tail anche container Docker HTTP pubblici |

### Permessi

L'utente SSH deve poter **leggere i file log nginx** (spesso gruppo `adm` su Debian/Ubuntu).

## `agent.yaml`

Provider LLM per Security Report e agente flottante. Default: **OpenRouter** via `OPENROUTER_API_KEY`.

## Variabili d'ambiente

| Campo | Scopo |
|------|--------|
| `SKOPOS_DASHBOARD_PASSWORD` | Password condivisa dashboard (form login); in **Impostazioni** o `.env` |
| `SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH` | Lunghezza minima nuove password (default **12**) |
| `SKOPOS_DASHBOARD_SESSION_HOURS` | Logout auto dopo N ore (default **12**) |
| `OPENROUTER_API_KEY` | Provider LLM predefinito |
| `SKOPOS_SSH_KEY_PASSPHRASE` | Passphrase per chiavi SSH cifrate |
| `SKOPOS_SSH_STRICT_HOST_KEYS` | `1` per verificare host keys |

## Dove modificare nell'UI

| Campo | Scopo |
|------|--------|
| Lingua e tema | In fondo alla barra laterale |
| Raccolta / backfill | Barra laterale in **Analitiche** |
| Intervallo auto-scan | **Impostazioni** |
| Avvisi Telegram | **Impostazioni** |
| Provider agente sicurezza | **Sicurezza** → scheda AI Agent |

## Settings sections (detail)

| Campo | Scopo |
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

![Impostazioni e controlli barra laterale](../../screenshots/settings-fleet.png)

![Sidebar](../../screenshots/sidebar-nav.png)
