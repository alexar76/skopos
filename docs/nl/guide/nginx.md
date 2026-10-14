# HTTP-accesslogs — scope en beperkingen

> **Primair:** SKOPOS-analyse is gebouwd voor **nginx-accesslogs**. **Apache combined** ook ondersteund bij expliciete activatie (`apache.enabled: true`).

## Ondersteund

| Bron | Hoe |
|------|--------|
| nginx-accesslogbestanden op host | `ssh_nginx_access_log` of `ssh_http_access_log` + `nginx.access_log_path` |
| Apache-accesslogbestanden (combined) | `ssh_http_access_log` + `apache.enabled: true` |
| Extra nginx-logs | `access_log_paths` of `auto_discover_logs` |
| Extra Apache-logs | `apache.access_log_paths` of `apache.auto_discover_logs` |
| Docker-container-stdout (optioneel) | Alleen bij `auto_discover_docker_logs: true`; parser probeert **combined**, dan **uvicorn** |

## Niet ondersteund als primaire analyse

- Caddy / Traefik als standalone logbronnen
- Cloud-CDN-logs (Cloudflare, Fastly) zonder combined-regels
- Applicatielogs die geen HTTP-accessregels zijn

Als u TLS op nginx beëindigt en proxiet naar Node/Python, **houd nginx-accesslogging aan** — dat blijft het canonieke trafficrecord in productie.

## Apache (test / secundair)

Apache moet **combined**-logformaat gebruiken (zelfde velden als nginx combined). Voorbeeld:

```apache
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
CustomLog /var/log/apache2/access.log combined
```

Op metis kan een test-httpd-container op **8088** naast nginx 80/443 draaien — zie `metis/deploy/apache-test/`.

### Adminpaneel smoke test

1. Deploy: `./metis/deploy/apache-test/deploy.sh` op metis-host.
2. Genereer traffic:
   ```bash
curl -sS http://127.0.0.1:8088/
curl -sS http://127.0.0.1:8088/admin/
curl -sS "http://127.0.0.1:8088/admin/?page=settings"
tail -n 5 /opt/metis/deploy/apache-test/logs/access_log
```
3. In `servers.yaml`: `source: ssh_http_access_log`, `apache.enabled: true`, pad naar `access_log`.
4. In SKOPOS **Analyse**, filter paden met `/admin` — regels na collect.

Apache-adminroutes zijn **testfixture** voor parser/filtervalidatie; in prod blijven nginx-accesslogs canoniek.

## Aanbevolen nginx-`log_format`

Minimaal: `$remote_addr`, `$time_local`, `$request`, `$status`, `$body_bytes_sent`, `$http_referer`, `$http_user_agent`. Voor vhost-analyse voeg **`$host`** toe:

```nginx
log_format skopos '$remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent '
                  '"$http_referer" "$http_user_agent" "$host"';
access_log /var/log/nginx/access.log skopos;
```

## Waarom nginx-first?

- Voorspelbaar combined-formaat over de fleet
- SSH tail van `/var/log/nginx/` zonder agent op elke box
- Apache optioneel voor gemengde stacks of testnodes
- Security-module peilt OS-metrics onafhankelijk van webstack
