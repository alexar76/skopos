# سجلات وصول HTTP — النطاق والقيود

> **الأساسي:** تحليلات SKOPOS مبنية لـ **سجلات وصول nginx**. صيغة **Apache combined** مدعومة أيضًا عند التفعيل صراحة (`apache.enabled: true`).

## مدعوم

| المصدر | كيف |
|------|--------|
| ملفات سجل وصول nginx على المضيف | `ssh_nginx_access_log` أو `ssh_http_access_log` + `nginx.access_log_path` |
| ملفات سجل وصول Apache (combined) | `ssh_http_access_log` + `apache.enabled: true` |
| سجلات nginx إضافية | `access_log_paths` أو `auto_discover_logs` |
| سجلات Apache إضافية | `apache.access_log_paths` أو `apache.auto_discover_logs` |
| stdout حاوية Docker (اختياري) | فقط عند `auto_discover_docker_logs: true`؛ المحلّل يجرب **combined** أولًا ثم **uvicorn** |

## غير مدعوم كتحليلات أساسية

- Caddy / Traefik كمصادر سجلات مستقلة
- سجلات CDN السحابية (Cloudflare, Fastly) بدون أسطر بصيغة combined
- سجلات التطبيقات التي ليست أسطر وصول HTTP

إذا أنهيت TLS على nginx ووجّهت إلى Node/Python، **أبقِ تسجيل وصول nginx مفعّلًا** — يظل السجل المرجعي لحركة المرور في الإنتاج.

## Apache (اختبار / ثانوي)

يجب أن يستخدم Apache صيغة **combined** (نفس حقول nginx combined). مثال:

```apache
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
CustomLog /var/log/apache2/access.log combined
```

على metis، يمكن تشغيل حاوية httpd اختبارية على **8088** بجانب nginx على 80/443 — راجع `metis/deploy/apache-test/`.

### اختبار دخان لوحة الإدارة

1. النشر: `./metis/deploy/apache-test/deploy.sh` على مضيف metis.
2. توليد حركة مرور:
   ```bash
curl -sS http://127.0.0.1:8088/
curl -sS http://127.0.0.1:8088/admin/
curl -sS "http://127.0.0.1:8088/admin/?page=settings"
tail -n 5 /opt/metis/deploy/apache-test/logs/access_log
```
3. في `servers.yaml`: `source: ssh_http_access_log`، `apache.enabled: true`، مسار `access_log`.
4. في SKOPOS **التحليلات**، رشّح المسارات التي تحتوي `/admin` — يجب أن تظهر الأسطر بعد collect.

مسارات إدارة Apache هي **fixture اختبار** للتحقق من المحلّل/المرشّح؛ في الإنتاج يجب الاعتماد على سجلات وصول nginx.

## `log_format` nginx الموصى به

ضمّن على الأقل: `$remote_addr`، `$time_local`، `$request`، `$status`، `$body_bytes_sent`، `$http_referer`، `$http_user_agent`. للتحليل لكل vhost أضف **`$host`**:

```nginx
log_format skopos '$remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent '
                  '"$http_referer" "$http_user_agent" "$host"';
access_log /var/log/nginx/access.log skopos;
```

## لماذا nginx أولًا؟

- صيغة combined متوقّعة عبر الأسطول
- SSH tail لـ `/var/log/nginx/` دون تثبيت وكيل على كل صندوق
- Apache اختياري للمكدسات المختلطة أو عقد الاختبار
- وحدة الأمان تفحص مقاييس OS باستقلال عن مكدس الويب
