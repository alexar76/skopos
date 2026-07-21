# Log akses HTTP — cakupan & batasan

> **Utama:** analitik SKOPOS dibangun untuk **log akses nginx**. Format **Apache combined** juga didukung jika diaktifkan (`apache.enabled: true`).

## Didukung

| Sumber | Cara |
|------|--------|
| File access log nginx di host | `ssh_nginx_access_log` atau `ssh_http_access_log` + `nginx.access_log_path` |
| File access log Apache (combined) | `ssh_http_access_log` + `apache.enabled: true` |
| Log nginx tambahan | `access_log_paths` atau `auto_discover_logs` |
| Log Apache tambahan | `apache.access_log_paths` atau `apache.auto_discover_logs` |
| stdout container Docker (opsional) | Hanya jika `auto_discover_docker_logs: true`; parser coba **combined** lalu **uvicorn** |

## Tidak didukung sebagai analitik utama

- Caddy / Traefik sebagai sumber log mandiri
- Log CDN cloud (Cloudflare, Fastly) tanpa baris format combined
- Log aplikasi yang bukan baris akses HTTP

Jika TLS di nginx dan proxy ke Node/Python, **pertahankan access logging nginx** — tetap catatan lalu lintas kanonik di produksi.

## Apache (uji / sekunder)

Apache harus format log **combined** (field sama nginx combined). Contoh:

```apache
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
CustomLog /var/log/apache2/access.log combined
```

Di metis, container httpd uji bisa jalan di **8088** berdampingan nginx 80/443 — lihat `metis/deploy/apache-test/`.

### Smoke test panel admin

1. Deploy: `./metis/deploy/apache-test/deploy.sh` di host metis.
2. Hasilkan lalu lintas:
   ```bash
curl -sS http://127.0.0.1:8088/
curl -sS http://127.0.0.1:8088/admin/
curl -sS "http://127.0.0.1:8088/admin/?page=settings"
tail -n 5 /opt/metis/deploy/apache-test/logs/access_log
```
3. Di `servers.yaml`: `source: ssh_http_access_log`, `apache.enabled: true`, path ke `access_log`.
4. Di SKOPOS **Analitik**, filter path berisi `/admin` — baris muncul setelah collect.

Rute admin Apache adalah **fixture uji** validasi parser/filter; prod tetap gunakan log nginx kanonik.

## `log_format` nginx yang disarankan

Sertakan minimal: `$remote_addr`, `$time_local`, `$request`, `$status`, `$body_bytes_sent`, `$http_referer`, `$http_user_agent`. Untuk analitik vhost tambahkan **`$host`**:

```nginx
log_format skopos '$remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent '
                  '"$http_referer" "$http_user_agent" "$host"';
access_log /var/log/nginx/access.log skopos;
```

## Mengapa nginx dulu?

- Format combined prediktif di armada
- SSH tail `/var/log/nginx/` tanpa agent di setiap box
- Apache opsional untuk stack campuran atau node uji
- Modul keamanan tetap probe metrik OS terpisah dari web stack
