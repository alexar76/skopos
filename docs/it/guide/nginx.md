# Log di accesso HTTP — ambito e limiti

> **Principale:** le analitiche SKOPOS sono per **log di accesso nginx**. Anche **Apache combined** se abilitato esplicitamente (`apache.enabled: true`).

## Supportato

| Fonte | Come |
|------|--------|
| File access log nginx sull'host | `ssh_nginx_access_log` o `ssh_http_access_log` + `nginx.access_log_path` |
| File access log Apache (combined) | `ssh_http_access_log` + `apache.enabled: true` |
| Log nginx aggiuntivi | `access_log_paths` o `auto_discover_logs` |
| Log Apache aggiuntivi | `apache.access_log_paths` o `apache.auto_discover_logs` |
| stdout container Docker (opzionale) | Solo con `auto_discover_docker_logs: true`; parser prova **combined** poi **uvicorn** |

## Non supportato come analitica principale

- Caddy / Traefik come sorgenti log autonome
- Log CDN cloud (Cloudflare, Fastly) senza righe in formato combined
- Log applicativi che non siano righe di accesso HTTP

Se termini TLS su nginx e fai proxy a Node/Python, **mantieni l'access logging nginx** — resta il record canonico del traffico in produzione.

## Apache (test / secondario)

Apache deve usare formato log **combined** (stessi campi di nginx combined). Esempio:

```apache
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
CustomLog /var/log/apache2/access.log combined
```

Su metis, un container httpd di test può girare sulla **porta 8088** accanto a nginx 80/443 — vedi `metis/deploy/apache-test/`.

### Smoke test pannello admin

1. Deploy: `./metis/deploy/apache-test/deploy.sh` sull'host metis.
2. Genera traffico:
   ```bash
curl -sS http://127.0.0.1:8088/
curl -sS http://127.0.0.1:8088/admin/
curl -sS "http://127.0.0.1:8088/admin/?page=settings"
tail -n 5 /opt/metis/deploy/apache-test/logs/access_log
```
3. In `servers.yaml`: `source: ssh_http_access_log`, `apache.enabled: true`, percorso a `access_log`.
4. In SKOPOS **Analitiche**, filtra percorsi con `/admin` — righe dopo collect.

Le route admin Apache sono **fixture di test** per validazione parser/filtro; in prod i log nginx restano canonici.

## `log_format` nginx consigliato

Includi almeno: `$remote_addr`, `$time_local`, `$request`, `$status`, `$body_bytes_sent`, `$http_referer`, `$http_user_agent`. Per analitica vhost aggiungi **`$host`**:

```nginx
log_format skopos '$remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent '
                  '"$http_referer" "$http_user_agent" "$host"';
access_log /var/log/nginx/access.log skopos;
```

## Perché nginx first?

- Formato combined prevedibile sulla flotta
- SSH tail di `/var/log/nginx/` senza agente su ogni box
- Apache opzionale per stack misti o nodi di test
- Il modulo security sonda metriche OS indipendentemente dallo stack web
