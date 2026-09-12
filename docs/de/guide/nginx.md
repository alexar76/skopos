# HTTP-Access-Logs — Umfang & Grenzen

> **Primär:** SKOPOS-Analytik ist für **nginx-Access-Logs** gebaut. **Apache combined** wird bei expliziter Aktivierung (`apache.enabled: true`) ebenfalls unterstützt.

## Unterstützt

| Quelle | Wie |
|------|--------|
| nginx-Access-Log-Dateien auf dem Host | `ssh_nginx_access_log` oder `ssh_http_access_log` + `nginx.access_log_path` |
| Apache-Access-Log-Dateien (combined) | `ssh_http_access_log` + `apache.enabled: true` |
| Zusätzliche nginx-Logs | `access_log_paths` oder `auto_discover_logs` |
| Zusätzliche Apache-Logs | `apache.access_log_paths` oder `apache.auto_discover_logs` |
| Docker-Container-stdout (optional) | Nur bei `auto_discover_docker_logs: true`; Parser versucht **combined**, dann **uvicorn** |

## Nicht als primäre Analytik unterstützt

- Caddy / Traefik als eigenständige Log-Quellen
- Cloud-CDN-Logs (Cloudflare, Fastly) ohne combined-formatierte Zeilen
- Anwendungslogs ohne HTTP-Access-Zeilen

Bei TLS-Terminierung auf nginx und Proxy zu Node/Python: **nginx-Access-Logging aktiv lassen** — das bleibt der kanonische Traffic-Datensatz in Produktion.

## Apache (Test / sekundär)

Apache muss **combined**-Logformat nutzen (gleiche Felder wie nginx combined). Beispiel:

```apache
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
CustomLog /var/log/apache2/access.log combined
```

Auf metis kann ein Test-httpd-Container auf **8088** parallel zu nginx 80/443 laufen — siehe `metis/deploy/apache-test/`.

### Admin-Panel-Smoke-Test

1. Deploy: `./metis/deploy/apache-test/deploy.sh` auf metis-Host.
2. Traffic erzeugen:
   ```bash
curl -sS http://127.0.0.1:8088/
curl -sS http://127.0.0.1:8088/admin/
curl -sS "http://127.0.0.1:8088/admin/?page=settings"
tail -n 5 /opt/metis/deploy/apache-test/logs/access_log
```
3. In `servers.yaml`: `source: ssh_http_access_log`, `apache.enabled: true`, Pfad zu `access_log`.
4. In SKOPOS **Analytik** Pfade mit `/admin` filtern — Zeilen nach collect sichtbar.

Apache-Admin-Routen sind **Test-Fixture** für Parser/Filter-Validierung; in Prod nginx-Access-Logs als kanonisch behandeln.

## Empfohlenes nginx-`log_format`

Mindestens: `$remote_addr`, `$time_local`, `$request`, `$status`, `$body_bytes_sent`, `$http_referer`, `$http_user_agent`. Für vhost-Analytik **`$host`** hinzufügen:

```nginx
log_format skopos '$remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent '
                  '"$http_referer" "$http_user_agent" "$host"';
access_log /var/log/nginx/access.log skopos;
```

## Warum nginx zuerst?

- Vorhersagbares combined-Format in der Flotte
- SSH tail von `/var/log/nginx/` ohne Agent auf jeder Box
- Apache optional für gemischte Stacks oder Test-Knoten
- Security-Modul prüft OS-Metriken unabhängig vom Web-Stack
