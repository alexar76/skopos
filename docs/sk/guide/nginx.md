# HTTP access logy — rozsah a obmedzenia

> **Primárne:** SKOPOS analytika je pre **nginx access logy**. **Apache combined** tiež pri `apache.enabled: true`.

## Podporované

| Zdroj | Ako |
|------|--------|
| nginx access log súbory na hoste | `ssh_nginx_access_log` alebo `ssh_http_access_log` + `nginx.access_log_path` |
| Apache access log súbory (combined) | `ssh_http_access_log` + `apache.enabled: true` |
| Ďalšie nginx logy | `access_log_paths` alebo `auto_discover_logs` |
| Ďalšie Apache logy | `apache.access_log_paths` alebo `apache.auto_discover_logs` |
| Docker kontajner stdout (voliteľné) | Len pri `auto_discover_docker_logs: true`; parser skúsi **combined**, potom **uvicorn** |

## Nepodporované ako primárna analytika

- Caddy / Traefik ako samostatné zdroje logov
- Cloud CDN logy (Cloudflare, Fastly) bez combined riadkov
- Aplikačné logy, ktoré nie sú HTTP access riadky

Ak ukončujete TLS na nginx a proxyujete na Node/Python, **nechajte nginx access logging zapnutý** — zostáva kanonický záznam trafficu v produkcii.

## Apache (test / sekundárne)

Apache musí používať **combined** log formát (rovnaké polia ako nginx combined). Príklad:

```apache
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
CustomLog /var/log/apache2/access.log combined
```

Na metis môže test httpd kontajner bežať na **8088** popri nginx 80/443 — pozri `metis/deploy/apache-test/`.

### Smoke test admin panelu

1. Deploy: `./metis/deploy/apache-test/deploy.sh` na metis hoste.
2. Generuj traffic:
   ```bash
curl -sS http://127.0.0.1:8088/
curl -sS http://127.0.0.1:8088/admin/
curl -sS "http://127.0.0.1:8088/admin/?page=settings"
tail -n 5 /opt/metis/deploy/apache-test/logs/access_log
```
3. V `servers.yaml`: `source: ssh_http_access_log`, `apache.enabled: true`, cesta k `access_log`.
4. V SKOPOS **Analytike** filtruj cesty s `/admin` — riadky po collect.

Apache admin trasy sú **test fixture** pre validáciu parsera/filtra; v produkcii nginx access logy zostávajú kanonické.

## Odporúčaný nginx `log_format`

Zahrňte aspoň: `$remote_addr`, `$time_local`, `$request`, `$status`, `$body_bytes_sent`, `$http_referer`, `$http_user_agent`. Pre vhost analytiku pridajte **`$host`**:

```nginx
log_format skopos '$remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent '
                  '"$http_referer" "$http_user_agent" "$host"';
access_log /var/log/nginx/access.log skopos;
```

## Prečo nginx first?

- Predvídateľný combined formát vo flotile
- SSH tail `/var/log/nginx/` bez agenta na každom boxe
- Apache voliteľný pre zmiešané stacky alebo test uzly
- Bezpečnostný modul stále sonduje OS metriky nezávisle od web stacku
