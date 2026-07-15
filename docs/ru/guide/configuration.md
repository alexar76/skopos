# Настройка

## `servers.yaml`

Каждый сервер: SSH и **пути к логам nginx**:

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

| Поле | Назначение |
|------|--------|
| `name` | Метка в дашбордах и фильтрах |
| `source` | `ssh_nginx_access_log` (только nginx) или `ssh_http_access_log` (nginx + Apache) |
| `nginx.access_log_path` | Основной access.log |
| `nginx.access_log_paths` | Дополнительные лог-файлы |
| `nginx.auto_discover_logs` | Искать логи в конфигах nginx |
| `nginx.auto_discover_docker_logs` | Опционально: docker logs HTTP-контейнеров |

### Права

SSH-пользователь должен **читать логи nginx** (часто группа `adm`).

## `agent.yaml`

LLM для Security Report и чат-агента. По умолчанию **OpenRouter** через `OPENROUTER_API_KEY`.

## Переменные окружения

| Поле | Назначение |
|------|--------|
| `SKOPOS_DASHBOARD_PASSWORD` | Пароль дашборда; в **Настройки** или `.env` |
| `SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH` | Мин. длина пароля (по умолчанию **12**) |
| `SKOPOS_DASHBOARD_SESSION_HOURS` | Автовыход через N часов (по умолчанию **12**) |
| `OPENROUTER_API_KEY` | LLM по умолчанию |
| `SKOPOS_SSH_KEY_PASSPHRASE` | Passphrase для SSH-ключа |
| `SKOPOS_SSH_STRICT_HOST_KEYS` | `1` — проверять host keys |

## Где менять в UI

| Поле | Назначение |
|------|--------|
| Язык и тема | Низ сайдбара |
| Сбор / backfill | Сайдбар **Аналитики** |
| Интервал авто-скана | **Настройки** |
| Telegram-алерты | **Настройки** |
| Провайдер AI | **Безопасность** → вкладка AI Agent |

## Разделы «Настройки» (подробно)

| Поле | Назначение |
|------|--------|
| Доступ к дашборду | `SKOPOS_DASHBOARD_PASSWORD`, время сессии, политика длины пароля |
| База данных | `SKOPOS_DATABASE_URL` или SQLite `db_path`; тест и миграция в UI |
| Авто-скан | Интервал фонового security-scan (минуты) |
| Telegram | env `SKOPOS_TELEGRAM_*`; уведомления о новых critical-находках |
| SSH-ключи | Генерация Ed25519; ключи в `.skopos/ssh/` |
| Серверы флота | Визуальный редактор `servers.yaml` — nginx, Apache, docker logs |

## Провайдеры в `agent.yaml`

Каждому провайдеру нужен API-ключ в env. По умолчанию **OpenRouter** (`OPENROUTER_API_KEY`). Провайдеры доступны в Сводном отчёте, плавающем агенте и вкладке AI Agent.

| Provider | API key |
|------|--------|
| `openrouter` | `OPENROUTER_API_KEY` — по умолчанию; много моделей через один ключ |
| `openai` | `OPENAI_API_KEY` |
| `anthropic` | `ANTHROPIC_API_KEY` |
| `deepseek` | `DEEPSEEK_API_KEY` |

![Сайдбар: навигация, язык и тема](screenshots/settings-fleet.png)

![Sidebar](screenshots/sidebar-nav.png)
