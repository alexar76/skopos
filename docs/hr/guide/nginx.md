# HTTP access logovi — opseg i ograničenja

> **Primarno:** SKOPOS analitika je za **nginx access logove**. **Apache combined** podržan i uz `apache.enabled: true`.

## Podržano

| Izvor | Kako |
|------|--------|
| nginx access log datoteke na hostu | `ssh_nginx_access_log` ili `ssh_http_access_log` + `nginx.access_log_path` |
| Apache access log datoteke (combined) | `ssh_http_access_log` + `apache.enabled: true` |
| Dodatni nginx logovi | `access_log_paths` ili `auto_discover_logs` |
| Dodatni Apache logovi | `apache.access_log_paths` ili `apache.auto_discover_logs` |
| Docker kontejner stdout (opcionalno) | Samo uz `auto_discover_docker_logs: true`; parser prvo **combined**, zatim **uvicorn** |

## Nije podržano kao primarna analitika

- Caddy / Traefik kao samostalni izvori logova
- Cloud CDN logovi (Cloudflare, Fastly) bez combined linija
- Aplikacijski logovi koji nisu HTTP access linije

Ako TLS završavate na nginx-u i proxyjate na Node/Python, **zadržite nginx access logging** — to ostaje kanonski zapis prometa u produkciji.

## Apache (test / sekundarno)

Apache mora koristiti **combined** log format (ista polja kao nginx combined). Primjer:

```apache
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
CustomLog /var/log/apache2/access.log combined
```

Na metis-u test httpd kontejner može raditi na **8088** uz nginx 80/443 — vidi `metis/deploy/apache-test/`.

### Smoke test admin panela

1. Deploy: `./metis/deploy/apache-test/deploy.sh` na metis hostu.
2. Generiraj promet:
   ```bash
curl -sS http://127.0.0.1:8088/
curl -sS http://127.0.0.1:8088/admin/
curl -sS "http://127.0.0.1:8088/admin/?page=settings"
tail -n 5 /opt/metis/deploy/apache-test/logs/access_log
```
3. U `servers.yaml`: `source: ssh_http_access_log`, `apache.enabled: true`, put do `access_log`.
4. U SKOPOS **Analitici** filtriraj putanje s `/admin` — linije nakon collect.

Apache admin rute su **test fixture** za validaciju parsera/filtra; u produkciji nginx access logovi ostaju kanonski.

## Preporučeni nginx `log_format`

Uključite barem: `$remote_addr`, `$time_local`, `$request`, `$status`, `$body_bytes_sent`, `$http_referer`, `$http_user_agent`. Za vhost analitiku dodajte **`$host`**:

```nginx
log_format skopos '$remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent '
                  '"$http_referer" "$http_user_agent" "$host"';
access_log /var/log/nginx/access.log skopos;
```

## Zašto nginx prvo?

- Predvidiv combined format u floti
- SSH tail `/var/log/nginx/` bez agenta na svakom boxu
- Apache opcionalan za miješane stackove ili test čvorove
- Sigurnosni modul i dalje sondira OS metrike neovisno o web stacku
