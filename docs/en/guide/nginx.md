# HTTP access logs — scope & limitations

> **Primary:** SKOPOS analytics are built for **nginx access logs**. **Apache combined** format is also supported when explicitly enabled (`apache.enabled: true`).

## Supported

| Source | How |
|------|--------|
| nginx access log files on the host | `ssh_nginx_access_log` or `ssh_http_access_log` + `nginx.access_log_path` |
| Apache access log files (combined) | `ssh_http_access_log` + `apache.enabled: true` |
| Additional nginx logs | `access_log_paths` or `auto_discover_logs` |
| Additional Apache logs (multi-vhost) | `apache.access_log_paths` or `apache.auto_discover_logs` |
| Docker container stdout (optional) | `nginx.auto_discover_docker_logs` **or** `apache.auto_discover_docker_logs`; parser tries **combined** first, then **uvicorn** |

## Not supported as primary analytics

- Caddy / Traefik as standalone log sources
- Cloud CDN logs (Cloudflare, Fastly) without combined-shaped lines
- Application logs that are not HTTP access lines

If you terminate TLS on nginx and proxy to Node/Python, **keep nginx access logging enabled** — that remains the canonical traffic record for production fleets.

## Apache (test / secondary)

Apache must use **combined** log format (same fields as nginx combined). Example:

```apache
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
CustomLog /var/log/apache2/access.log combined
```

On metis, a test httpd container can run on **port 8088** alongside nginx on 80/443 — see `metis/deploy/apache-test/`.

### Apache auto-discovery (parity with nginx)

With `apache.auto_discover_logs: true` SKOPOS reads the host's Apache config the
same way it reads nginx configs:

- Scans **`CustomLog`** and **`TransferLog`** directives across
  `sites-enabled`, `sites-available`, `conf-enabled`, and `conf.d` — covering both
  Debian (`/etc/apache2`) and RHEL (`/etc/httpd`) layouts.
- **Every discovered path is kept**, even when the filename has no `access` token
  (e.g. `api.example.com.log`) — because `CustomLog`/`TransferLog` are, by
  definition, access logs (`ErrorLog` is never picked up).
- Expands the `${APACHE_LOG_DIR}` placeholder to `/var/log/apache2`.
- Skips piped loggers (`CustomLog "|/usr/bin/rotatelogs …"`) — those are not
  tailable files.
- Falls back to common locations (`/var/log/apache2/*access*.log`,
  `/var/log/httpd/access_log`, …) and finally `apache.access_log_path`.

Per-vhost host names are inferred from filenames such as `example.com.access.log`,
`example.com-access.log`, `example.com_access.log`, and the RHEL-style
`example.com-access_log`, so multi-site Apache hosts split cleanly by vhost — just
like nginx.

Docker HTTP containers can also be discovered/tailed for Apache-only servers via
`apache.auto_discover_docker_logs` / `apache.docker_log_containers` (equivalent to
the nginx options; container traffic is host-level, not tied to either server).

### Admin panel smoke test

1. Deploy: `./metis/deploy/apache-test/deploy.sh` on the metis host.
2. Generate traffic:
   ```bash
curl -sS http://127.0.0.1:8088/
curl -sS http://127.0.0.1:8088/admin/
curl -sS "http://127.0.0.1:8088/admin/?page=settings"
tail -n 5 /opt/metis/deploy/apache-test/logs/access_log
```
3. In `servers.yaml`: `source: ssh_http_access_log`, `apache.enabled: true`, path to `access_log`.
4. In SKOPOS **Analytics**, filter paths containing `/admin` — lines should appear after collect.

The Apache admin routes are a **test fixture** for parser/filter validation; production fleets should still treat nginx access logs as canonical.

## Recommended nginx `log_format`

Include at least: `$remote_addr`, `$time_local`, `$request`, `$status`, `$body_bytes_sent`, `$http_referer`, `$http_user_agent`. For per-vhost analytics add **`$host`**:

```nginx
log_format skopos '$remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent '
                  '"$http_referer" "$http_user_agent" "$host"';
access_log /var/log/nginx/access.log skopos;
```

## Why nginx-first?

- Predictable combined log format across fleets
- SSH tail of `/var/log/nginx/` without agent install on every box
- Apache is optional for mixed stacks or test nodes
- Security module still probes OS metrics independently of the web stack
