# HTTP access logs — область и ограничения

> **Основной источник:** аналитика SKOPOS рассчитана на **nginx access logs**. **Apache combined** поддерживается при `apache.enabled: true`.

## Поддерживается

| Источник | Как |
|------|--------|
| Файлы access.log nginx на хосте | `ssh_nginx_access_log` или `ssh_http_access_log` |
| Apache access logs (combined) | `ssh_http_access_log` + `apache.enabled: true` |
| Доп. логи nginx | `access_log_paths`, `auto_discover_logs` |
| Доп. логи Apache (мульти-vhost) | `apache.access_log_paths`, `apache.auto_discover_logs` |
| Docker stdout (опционально) | `nginx.auto_discover_docker_logs` **или** `apache.auto_discover_docker_logs` |

## Не поддерживается

- Caddy / Traefik как отдельные источники
- CDN-логи без combined-формата
- Прикладные логи без HTTP access строк

Если TLS на nginx, а backend — Node/Python, **оставьте access logging на nginx** — это канонический источник трафика.

## Apache (тест / вторичный)

Нужен формат **combined**. Пример:

```apache
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
CustomLog /var/log/apache2/access.log combined
```

На metis тестовый httpd на **8088** параллельно nginx — см. `metis/deploy/apache-test/`.

### Авто-поиск Apache (parity с nginx)

При `apache.auto_discover_logs: true` SKOPOS читает конфиг Apache так же, как
конфиги nginx:

- Сканирует директивы **`CustomLog`** и **`TransferLog`** в `sites-enabled`,
  `sites-available`, `conf-enabled`, `conf.d` — покрывает Debian (`/etc/apache2`)
  и RHEL (`/etc/httpd`).
- **Сохраняет все найденные пути**, даже без слова `access` в имени
  (например `api.example.com.log`) — ведь `CustomLog`/`TransferLog` по определению
  access-логи (`ErrorLog` не берётся).
- Раскрывает плейсхолдер `${APACHE_LOG_DIR}` в `/var/log/apache2`.
- Пропускает pipe-логгеры (`CustomLog "|/usr/bin/rotatelogs …"`) — это не файлы.
- Фолбэк на типовые пути (`/var/log/apache2/*access*.log`,
  `/var/log/httpd/access_log`, …) и, наконец, `apache.access_log_path`.

Имя хоста для каждого vhost берётся из имён `example.com.access.log`,
`example.com-access.log`, `example.com_access.log` и RHEL-стиля
`example.com-access_log` — мульти-сайт Apache делится по vhost, как у nginx.

Docker HTTP-контейнеры тоже можно искать/тейлить для Apache-серверов через
`apache.auto_discover_docker_logs` / `apache.docker_log_containers` (аналогично
опциям nginx; трафик контейнеров — на уровне хоста, не привязан к серверу).

### Проверка с админкой

1. Поднять: `./metis/deploy/apache-test/deploy.sh` на хосте metis.
2. Сгенерировать трафик:
   ```bash
curl -sS http://127.0.0.1:8088/
curl -sS http://127.0.0.1:8088/admin/
curl -sS "http://127.0.0.1:8088/admin/?page=settings"
tail -n 5 /opt/metis/deploy/apache-test/logs/access_log
```
3. В `servers.yaml`: `source: ssh_http_access_log`, `apache.enabled: true`, путь к `access_log`.
4. В SKOPOS → **Аналитика**: фильтр path `/admin` — строки после collect.

Админка Apache — **тестовый стенд**; в проде опирайтесь на nginx access logs.

## Рекомендуемый `log_format` nginx

Минимум: `$remote_addr`, `$time_local`, `$request`, `$status`, `$body_bytes_sent`, referer, user-agent. Для vhost добавьте **`$host`**:

```nginx
log_format skopos '$remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent '
                  '"$http_referer" "$http_user_agent" "$host"';
access_log /var/log/nginx/access.log skopos;
```

## Почему nginx-first?

- Предсказуемый combined-формат
- SSH tail без агента на каждом хосте
- Apache опционален для смешанных стеков
- Security-модуль независим от web-стека
