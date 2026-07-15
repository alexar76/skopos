# Configuración

## `servers.yaml`

Cada servidor describe SSH y **rutas de logs nginx**:

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

| Campo | Propósito |
|------|--------|
| `name` | Etiqueta en paneles y filtros |
| `source` | `ssh_nginx_access_log` (solo nginx) o `ssh_http_access_log` (nginx + Apache) |
| `nginx.access_log_path` | Archivo access log principal |
| `nginx.access_log_paths` | Logs extra (multi-sitio) |
| `nginx.auto_discover_logs` | Buscar más rutas en configs nginx |
| `nginx.auto_discover_docker_logs` | Opcional: logs Docker HTTP |

### Permisos

El usuario SSH debe **leer logs nginx** (a menudo grupo `adm`).

## `agent.yaml`

Proveedores LLM para Security Report y agente flotante. Por defecto **OpenRouter** vía `OPENROUTER_API_KEY`.

## Variables de entorno

| Campo | Propósito |
|------|--------|
| `SKOPOS_DASHBOARD_PASSWORD` | Contraseña del panel; en **Ajustes** o `.env` |
| `SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH` | Longitud mínima (por defecto **12**) |
| `SKOPOS_DASHBOARD_SESSION_HOURS` | Cierre de sesión tras N horas (por defecto **12**) |
| `OPENROUTER_API_KEY` | Proveedor LLM por defecto |
| `SKOPOS_SSH_KEY_PASSPHRASE` | Passphrase de clave SSH |
| `SKOPOS_SSH_STRICT_HOST_KEYS` | `1` para verificar host keys |

## Dónde cambiar en la UI

| Campo | Propósito |
|------|--------|
| Idioma y tema | Parte inferior de la barra lateral |
| Recolección / backfill | Barra lateral en **Analítica** |
| Intervalo auto-scan | **Ajustes** |
| Alertas Telegram | **Ajustes** |
| Proveedor AI | **Seguridad** → pestaña AI Agent |

## Settings sections (detail)

| Campo | Propósito |
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

![Barra lateral y ajustes](screenshots/settings-fleet.png)

![Sidebar](screenshots/sidebar-nav.png)
