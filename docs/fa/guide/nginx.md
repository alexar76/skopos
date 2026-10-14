# لاگ‌های دسترسی HTTP — دامنه و محدودیت‌ها

> **اصلی:** تحلیل SKOPOS برای **لاگ‌های دسترسی nginx** ساخته شده. فرمت **Apache combined** نیز با فعال‌سازی صریح (`apache.enabled: true`) پشتیبانی می‌شود.

## پشتیبانی‌شده

| منبع | چگونه |
|------|--------|
| فایل‌های access log nginx روی میزبان | `ssh_nginx_access_log` یا `ssh_http_access_log` + `nginx.access_log_path` |
| فایل‌های access log Apache (combined) | `ssh_http_access_log` + `apache.enabled: true` |
| لاگ‌های nginx اضافی | `access_log_paths` یا `auto_discover_logs` |
| لاگ‌های Apache اضافی | `apache.access_log_paths` یا `apache.auto_discover_logs` |
| stdout کانتینر Docker (اختیاری) | فقط با `auto_discover_docker_logs: true`؛ parser ابتدا **combined** سپس **uvicorn** |

## به‌عنوان تحلیل اصلی پشتیبانی نمی‌شود

- Caddy / Traefik به‌عنوان منبع لاگ مستقل
- لاگ‌های CDN ابری (Cloudflare، Fastly) بدون خطوط combined
- لاگ‌های برنامه که خط دسترسی HTTP نیستند

اگر TLS را روی nginx خاتمه می‌دهید و به Node/Python proxy می‌کنید، **access logging nginx را فعال نگه دارید** — همچنان س record مرجع ترافیک در تولید است.

## Apache (آزمون / ثانویه)

Apache باید از فرمت لاگ **combined** (همان فیلدهای nginx combined) استفاده کند. مثال:

```apache
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
CustomLog /var/log/apache2/access.log combined
```

روی metis، کانتینر httpd آزمایشی می‌تواند روی **8088** کنار nginx 80/443 اجرا شود — `metis/deploy/apache-test/` را ببینید.

### Smoke test پنل admin

1. استقرار: `./metis/deploy/apache-test/deploy.sh` روی میزبان metis.
2. ترافیک تولید کنید:
   ```bash
curl -sS http://127.0.0.1:8088/
curl -sS http://127.0.0.1:8088/admin/
curl -sS "http://127.0.0.1:8088/admin/?page=settings"
tail -n 5 /opt/metis/deploy/apache-test/logs/access_log
```
3. در `servers.yaml`: `source: ssh_http_access_log`، `apache.enabled: true`، مسیر `access_log`.
4. در SKOPOS **تحلیل‌ها**، مسیرهای حاوی `/admin` را فیلتر کنید — پس از collect خطوط باید ظاهر شوند.

مسیرهای admin Apache **fixture آزمون** برای اعتبارسنجی parser/فیلتر هستند؛ در prod همچنان لاگ nginx مرجع است.

## `log_format` nginx توصیه‌شده

حداقل شامل: `$remote_addr`، `$time_local`، `$request`، `$status`، `$body_bytes_sent`، `$http_referer`، `$http_user_agent`. برای تحلیل vhost **`$host`** اضافه کنید:

```nginx
log_format skopos '$remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent '
                  '"$http_referer" "$http_user_agent" "$host"';
access_log /var/log/nginx/access.log skopos;
```

## چرا nginx اول؟

- فرمت combined قابل پیش‌بینی در ناوگان
- SSH tail از `/var/log/nginx/` بدون نصب agent روی هر box
- Apache اختیاری برای stackهای مختلط یا گره‌های آزمون
- ماژول امنیت همچنان متریک‌های OS را مستقل از web stack probe می‌کند
