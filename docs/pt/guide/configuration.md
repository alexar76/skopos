# Configuração

## `servers.yaml`

Cada entrada de servidor descreve acesso SSH e **caminhos de log nginx**:

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

| Campo | Finalidade |
|------|--------|
| `name` | Rótulo em painéis e filtros |
| `source` | `ssh_nginx_access_log` (somente nginx) ou `ssh_http_access_log` (nginx + Apache opcional) |
| `nginx.access_log_path` | Arquivo principal de access log |
| `nginx.access_log_paths` | Arquivos de log extras (multi-site) |
| `nginx.auto_discover_logs` | Analisar configs nginx no host para mais caminhos |
| `nginx.auto_discover_docker_logs` | Opcional: também acompanhar containers Docker HTTP públicos |

### Permissões

O usuário SSH deve poder **ler arquivos de log nginx** (muitas vezes membro do grupo `adm` no Debian/Ubuntu).

## `agent.yaml`

Provedores LLM para o Security Report e agente flutuante. Padrão: **OpenRouter** via `OPENROUTER_API_KEY`.

## Variáveis de ambiente

| Campo | Finalidade |
|------|--------|
| `SKOPOS_DASHBOARD_PASSWORD` | Senha compartilhada do painel (formulário de login); em **Configurações** ou `.env` |
| `SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH` | Comprimento mínimo de novas senhas (padrão **12**) |
| `SKOPOS_DASHBOARD_SESSION_HOURS` | Encerrar sessão após N horas (padrão **12**) |
| `OPENROUTER_API_KEY` | Provedor LLM padrão |
| `SKOPOS_SSH_KEY_PASSPHRASE` | Passphrase para chaves SSH criptografadas |
| `SKOPOS_SSH_STRICT_HOST_KEYS` | `1` para verificar host keys |

## Onde alterar na interface

| Campo | Finalidade |
|------|--------|
| Idioma e tema | Parte inferior da barra lateral |
| Coleta / backfill | Barra lateral em **Análises** |
| Intervalo de varredura automática | **Configurações** |
| Alertas Telegram | **Configurações** |
| Provedor do agente de segurança | **Segurança** → aba AI Agent |

## Settings sections (detail)

| Campo | Finalidade |
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

![Configurações e controles da barra lateral](screenshots/settings-fleet.png)

![Sidebar](screenshots/sidebar-nav.png)
