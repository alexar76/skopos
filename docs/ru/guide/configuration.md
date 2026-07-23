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

### Домены и поддомены (авто-обнаружение)

Домены нигде не перечисляются — SKOPOS сам группирует каждый запрос по **домену** (`host`), поэтому каждый сайт и поддомен появляется отдельно в Аналитике (фильтр **host**) и в оповещениях. Единственное требование: nginx на хосте должен **писать домен (vhost)** в лог. Стандартный *combined*-формат его не пишет — добавьте `$host` в `log_format` один раз и перезагрузите nginx, никакой пер-доменной настройки:

```nginx
# /etc/nginx/nginx.conf — внутри блока http { }
log_format skopos '$host $remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"';

access_log /var/log/nginx/access.log skopos;
```

Затем `sudo nginx -t && sudo nginx -s reload`. Парсер SKOPOS понимает **оба** формата — стандартный combined и этот с префиксом `$host`, поэтому старые строки лога продолжают разбираться при переходе. Добавили новый поддомен? Здесь делать ничего не нужно — как только он начнёт отдавать трафик через тот же nginx, он появится сам. (Пер-vhost `access_log`-файлы тоже подходят: укажите их в `nginx.access_log_paths` или оставьте `auto_discover_logs: true`.)

### Apache (опционально)

Access-логи Apache используют тот же формат **combined/common**, что и nginx,
поэтому SKOPOS разбирает их тем же движком. Добавьте блок `apache:` и укажите
`source: ssh_http_access_log`:

```yaml
servers:
  - name: metis
    source: ssh_http_access_log
    ssh:
      host: 203.0.113.20
      port: 22
      user: stats
      key_path: ~/.ssh/id_ed25519
    nginx:
      access_log_path: /var/log/nginx/access.log
      auto_discover_logs: true
    apache:
      enabled: true
      access_log_path: /var/log/apache2/access.log
      access_log_paths:                 # доп. vhost-логи (мульти-сайт)
        - /var/log/apache2/api.example.com-access.log
      auto_discover_logs: true          # сканировать CustomLog/TransferLog
      auto_discover_docker_logs: false  # опционально: docker HTTP-контейнеры
      docker_log_containers: []         # опционально: явные имена контейнеров
```

| Поле | Назначение |
|------|--------|
| `apache.enabled` | Включить сбор логов Apache для сервера |
| `apache.access_log_path` | Основной access.log (fallback, если ничего не найдено) |
| `apache.access_log_paths` | Доп. vhost-логи (мульти-сайт) |
| `apache.auto_discover_logs` | Сканировать `CustomLog`/`TransferLog` в `sites-enabled`, `sites-available`, `conf-enabled`, `conf.d` (Debian **и** RHEL) |
| `apache.auto_discover_docker_logs` | Опционально: docker logs HTTP-контейнеров |
| `apache.docker_log_containers` | Опционально: явные имена контейнеров |

Авто-поиск для Apache **авторитетен**: логи доступа берутся только из директив
`CustomLog`/`TransferLog` (никогда из `ErrorLog`), поэтому сохраняются все
найденные пути — включая vhost-логи, в имени которых нет слова `access`
(например `api.example.com.log`). Плейсхолдер `${APACHE_LOG_DIR}` раскрывается в
`/var/log/apache2`, а pipe-логгеры (`|/usr/bin/rotatelogs …`) пропускаются (это не
файлы для tail). Имя хоста берётся из имён вроде `example.com.access.log`,
`example.com-access.log`, `example.com_access.log` и RHEL-стиля
`example.com-access_log`.

### Права

SSH-пользователь должен **читать логи веб-сервера** — логи nginx обычно доступны
через группу `adm` (Debian/Ubuntu); логи Apache лежат в `/var/log/apache2`
(Debian) или `/var/log/httpd` (RHEL), обычно группа `adm` или `root` — добавьте
SSH-пользователя соответственно.

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

![Сайдбар: навигация, язык и тема](../../screenshots/settings-fleet.png)

![Sidebar](../../screenshots/sidebar-nav.png)
