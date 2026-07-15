# Configuration

## `servers.yaml`

Each server entry describes SSH access and **nginx log paths**:

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

| Field | Purpose |
|------|--------|
| `name` | Label in dashboards and filters |
| `source` | `ssh_nginx_access_log` (nginx only) or `ssh_http_access_log` (nginx + optional Apache) |
| `nginx.access_log_path` | Primary access log file |
| `nginx.access_log_paths` | Extra log files (multi-site) |
| `nginx.auto_discover_logs` | Parse nginx configs on the host for more paths |
| `nginx.auto_discover_docker_logs` | Optional: also tail public Docker HTTP containers |

### Permissions

The SSH user must be able to **read nginx log files** (often membership in the `adm` group on Debian/Ubuntu).

## `agent.yaml`

LLM providers for the Security Report and floating agent. Default: **OpenRouter** via `OPENROUTER_API_KEY`.

## Environment variables

| Field | Purpose |
|------|--------|
| `SKOPOS_DASHBOARD_PASSWORD` | Shared dashboard password (login form); set via Settings or `.env` |
| `SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH` | Minimum length for new passwords (default **12**) |
| `SKOPOS_DASHBOARD_SESSION_HOURS` | Auto sign-out after N hours (default **12**) |
| `OPENROUTER_API_KEY` | Default LLM provider |
| `SKOPOS_SSH_KEY_PASSPHRASE` | Passphrase for encrypted SSH keys |
| `SKOPOS_SSH_STRICT_HOST_KEYS` | `1` to verify host keys |

## Where to change things in the UI

| Field | Purpose |
|------|--------|
| Language & theme | Sidebar bottom |
| Collection / backfill | Sidebar on **Analytics** |
| Auto-scan interval | **Settings** |
| Telegram alerts | **Settings** |
| Security agent provider | **Security** → AI Agent tab |

## Settings sections (detail)

| Field | Purpose |
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

![Settings and sidebar controls](screenshots/settings-fleet.png)

![Sidebar](screenshots/sidebar-nav.png)
