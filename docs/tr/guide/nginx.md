# HTTP erişim günlükleri — kapsam ve sınırlamalar

> **Birincil:** SKOPOS analitiği **nginx erişim günlükleri** için tasarlanmıştır. **Apache combined** açıkça etkinleştirildiğinde (`apache.enabled: true`) de desteklenir.

## Desteklenen

| Kaynak | Nasıl |
|------|--------|
| Ana bilgisayardaki nginx erişim günlüğü dosyaları | `ssh_nginx_access_log` veya `ssh_http_access_log` + `nginx.access_log_path` |
| Apache erişim günlüğü dosyaları (combined) | `ssh_http_access_log` + `apache.enabled: true` |
| Ek nginx günlükleri | `access_log_paths` veya `auto_discover_logs` |
| Ek Apache günlükleri | `apache.access_log_paths` veya `apache.auto_discover_logs` |
| Docker konteyner stdout (isteğe bağlı) | Yalnızca `auto_discover_docker_logs: true`; ayrıştırıcı önce **combined**, sonra **uvicorn** dener |

## Birincil analitik olarak desteklenmeyen

- Bağımsız günlük kaynağı olarak Caddy / Traefik
- combined biçimli satırlar olmayan bulut CDN günlükleri (Cloudflare, Fastly)
- HTTP erişim satırı olmayan uygulama günlükleri

TLS'yi nginx'te sonlandırıp Node/Python'a proxy yapıyorsanız, **nginx erişim günlüğünü etkin tutun** — üretim filosunda kanonik trafik kaydı budur.

## Apache (test / ikincil)

Apache **combined** günlük formatı kullanmalı (nginx combined ile aynı alanlar). Örnek:

```apache
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
CustomLog /var/log/apache2/access.log combined
```

metis'te test httpd konteyneri nginx 80/443 yanında **8088**'de çalışabilir — `metis/deploy/apache-test/` bakın.

### Yönetici paneli duman testi

1. Dağıt: metis ana bilgisayarında `./metis/deploy/apache-test/deploy.sh`.
2. Trafik oluştur:
   ```bash
curl -sS http://127.0.0.1:8088/
curl -sS http://127.0.0.1:8088/admin/
curl -sS "http://127.0.0.1:8088/admin/?page=settings"
tail -n 5 /opt/metis/deploy/apache-test/logs/access_log
```
3. `servers.yaml` içinde: `source: ssh_http_access_log`, `apache.enabled: true`, `access_log` yolu.
4. SKOPOS **Analitik**'te `/admin` içeren yolları filtrele — collect sonrası satırlar görünmeli.

Apache admin rotaları ayrıştırıcı/filtre doğrulama **test fixture**'ıdır; üretimde nginx erişim günlükleri kanonik kalmalı.

## Önerilen nginx `log_format`

En az şunları ekleyin: `$remote_addr`, `$time_local`, `$request`, `$status`, `$body_bytes_sent`, `$http_referer`, `$http_user_agent`. vhost analitiği için **`$host`** ekleyin:

```nginx
log_format skopos '$remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent '
                  '"$http_referer" "$http_user_agent" "$host"';
access_log /var/log/nginx/access.log skopos;
```

## Neden önce nginx?

- Filo genelinde öngörülebilir combined günlük formatı
- Her kutuda aracı olmadan `/var/log/nginx/` SSH tail
- Apache karışık yığınlar veya test düğümleri için isteğe bağlı
- Güvenlik modülü web yığınından bağımsız OS metriklerini inceler
