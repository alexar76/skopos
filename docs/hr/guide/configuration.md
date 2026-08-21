# Konfiguracija

## `servers.yaml`

Svaki unos poslužitelja opisuje SSH pristup i **nginx putanje logova**:

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

| Polje | Svrha |
|------|--------|
| `name` | Oznaka u nadzornim pločama i filtrima |
| `source` | `ssh_nginx_access_log` (samo nginx) ili `ssh_http_access_log` (nginx + opcionalni Apache) |
| `nginx.access_log_path` | Primarna access log datoteka |
| `nginx.access_log_paths` | Dodatne log datoteke (multi-site) |
| `nginx.auto_discover_logs` | Parsiraj nginx config na hostu za više putanja |
| `nginx.auto_discover_docker_logs` | Opcionalno: prati i javne Docker HTTP kontejnere |

### Dozvole

SSH korisnik mora moći **čitati nginx log datoteke** (često grupa `adm` na Debian/Ubuntu).

## `agent.yaml`

LLM pružatelji za Security Report i plutajući agent. Zadano: **OpenRouter** preko `OPENROUTER_API_KEY`.

## Varijable okruženja

| Polje | Svrha |
|------|--------|
| `SKOPOS_DASHBOARD_PASSWORD` | Zajednička lozinka nadzorne ploče (login forma); u **Postavkama** ili `.env` |
| `SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH` | Minimalna duljina novih lozinki (zadano **12**) |
| `SKOPOS_DASHBOARD_SESSION_HOURS` | Automatska odjava nakon N sati (zadano **12**) |
| `OPENROUTER_API_KEY` | Zadani LLM pružatelj |
| `SKOPOS_SSH_KEY_PASSPHRASE` | Passphrase za šifrirane SSH ključeve |
| `SKOPOS_SSH_STRICT_HOST_KEYS` | `1` za provjeru host keys |

## Gdje mijenjati u sučelju

| Polje | Svrha |
|------|--------|
| Jezik i tema | Dno bočne trake |
| Prikupljanje / backfill | Bočna traka na **Analitici** |
| Interval auto-scana | **Postavke** |
| Telegram alerti | **Postavke** |
| Pružatelj sigurnosnog agenta | **Sigurnost** → kartica AI Agent |

## Settings sections (detail)

| Polje | Svrha |
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

![Postavke i kontrole bočne trake](../../screenshots/settings-fleet.png)

![Sidebar](../../screenshots/sidebar-nav.png)
