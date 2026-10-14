# Configuratie

## `servers.yaml`

Elke serverentry beschrijft SSH-toegang en **nginx-logpaden**:

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

| Veld | Doel |
|------|--------|
| `name` | Label in dashboards en filters |
| `source` | `ssh_nginx_access_log` (alleen nginx) of `ssh_http_access_log` (nginx + optioneel Apache) |
| `nginx.access_log_path` | Primair accesslogbestand |
| `nginx.access_log_paths` | Extra logbestanden (multi-site) |
| `nginx.auto_discover_logs` | Parse nginx-configs op host voor meer paden |
| `nginx.auto_discover_docker_logs` | Optioneel: ook publieke Docker HTTP-containers tailen |

### Rechten

SSH-gebruiker moet **nginx-logbestanden kunnen lezen** (vaak groep `adm` op Debian/Ubuntu).

## `agent.yaml`

LLM-providers voor Security Report en zwevende agent. Standaard: **OpenRouter** via `OPENROUTER_API_KEY`.

## Omgevingsvariabelen

| Veld | Doel |
|------|--------|
| `SKOPOS_DASHBOARD_PASSWORD` | Gedeeld dashboardwachtwoord (loginformulier); in **Instellingen** of `.env` |
| `SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH` | Minimale lengte nieuwe wachtwoorden (standaard **12**) |
| `SKOPOS_DASHBOARD_SESSION_HOURS` | Auto uitloggen na N uur (standaard **12**) |
| `OPENROUTER_API_KEY` | Standaard LLM-provider |
| `SKOPOS_SSH_KEY_PASSPHRASE` | Passphrase voor versleutelde SSH-sleutels |
| `SKOPOS_SSH_STRICT_HOST_KEYS` | `1` om host keys te verifiëren |

## Waar wijzigen in de UI

| Veld | Doel |
|------|--------|
| Taal & thema | Onderkant zijbalk |
| Collectie / backfill | Zijbalk bij **Analyse** |
| Auto-scan-interval | **Instellingen** |
| Telegram-meldingen | **Instellingen** |
| Security-agentprovider | **Beveiliging** → tab AI Agent |

## Settings sections (detail)

| Veld | Doel |
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

![Instellingen en zijbalkbediening](../../screenshots/settings-fleet.png)

![Sidebar](../../screenshots/sidebar-nav.png)
