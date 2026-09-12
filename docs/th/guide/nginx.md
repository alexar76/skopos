# HTTP access log — ขอบเขตและข้อจำกัด

> **หลัก:** การวิเคราะห์ SKOPOS สำหรับ **nginx access log** รองรับ **Apache combined** เมื่อเปิดใช้ (`apache.enabled: true`)

## รองรับ

| แหล่ง | วิธี |
|------|--------|
| ไฟล์ nginx access log บนโฮสต์ | `ssh_nginx_access_log` หรือ `ssh_http_access_log` + `nginx.access_log_path` |
| ไฟล์ Apache access log (combined) | `ssh_http_access_log` + `apache.enabled: true` |
| log nginx เพิ่มเติม | `access_log_paths` หรือ `auto_discover_logs` |
| log Apache เพิ่มเติม | `apache.access_log_paths` หรือ `apache.auto_discover_logs` |
| stdout คอนเทนเนอร์ Docker (ทางเลือก) | เมื่อ `auto_discover_docker_logs: true` เท่านั้น; parser ลอง **combined** ก่อน **uvicorn** |

## ไม่รองรับเป็นการวิเคราะห์หลัก

- Caddy / Traefik เป็นแหล่ง log แยก
- log CDN คลาวด์ (Cloudflare, Fastly) ที่ไม่มีบรรทัดรูป combined
- log แอปที่ไม่ใช่บรรทัด HTTP access

หาก terminate TLS ที่ nginx และ proxy ไป Node/Python **ให้เปิด nginx access logging** — ยังเป็นบันทึกทราฟฟิกมาตรฐานใน production

## Apache (ทดสอบ / รอง)

Apache ต้องใช้รูปแบบ log **combined** (ฟิลด์เดียวกับ nginx combined) ตัวอย่าง:

```apache
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
CustomLog /var/log/apache2/access.log combined
```

บน metis คอนเทนเนอร์ httpd ทดสอบรันที่ **8088** คู่กับ nginx 80/443 — ดู `metis/deploy/apache-test/`

### Smoke test แผง admin

1. Deploy: `./metis/deploy/apache-test/deploy.sh` บนโฮสต์ metis
2. สร้างทราฟฟิก:
   ```bash
curl -sS http://127.0.0.1:8088/
curl -sS http://127.0.0.1:8088/admin/
curl -sS "http://127.0.0.1:8088/admin/?page=settings"
tail -n 5 /opt/metis/deploy/apache-test/logs/access_log
```
3. ใน `servers.yaml`: `source: ssh_http_access_log`, `apache.enabled: true`, path ไป `access_log`
4. ใน SKOPOS **การวิเคราะห์** กรอง path ที่มี `/admin` — บรรทัดควรปรากฏหลัง collect

เส้นทาง admin Apache เป็น **fixture ทดสอบ** สำหรับตรวจ parser/filter; production ยังใช้ nginx access log เป็นมาตรฐาน

## `log_format` nginx ที่แนะนำ

รวมอย่างน้อย: `$remote_addr`, `$time_local`, `$request`, `$status`, `$body_bytes_sent`, `$http_referer`, `$http_user_agent` สำหรับ vhost เพิ่ม **`$host`**:

```nginx
log_format skopos '$remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent '
                  '"$http_referer" "$http_user_agent" "$host"';
access_log /var/log/nginx/access.log skopos;
```

## ทำไม nginx ก่อน?

- รูปแบบ combined คาดเดาได้ทั้ง fleet
- SSH tail `/var/log/nginx/` โดยไม่ติด agent ทุกเครื่อง
- Apache เป็นทางเลือกสำหรับ stack ผสมหรือโหนดทดสอบ
- โมดูลความปลอดภัยยัง probe metric OS แยกจาก web stack
