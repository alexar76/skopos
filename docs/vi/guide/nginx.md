# Nhật ký truy cập HTTP — phạm vi & giới hạn

> **Chính:** phân tích SKOPOS xây cho **nhật ký truy cập nginx**. **Apache combined** cũng hỗ trợ khi bật rõ (`apache.enabled: true`).

## Hỗ trợ

| Nguồn | Cách |
|------|--------|
| File access log nginx trên host | `ssh_nginx_access_log` hoặc `ssh_http_access_log` + `nginx.access_log_path` |
| File access log Apache (combined) | `ssh_http_access_log` + `apache.enabled: true` |
| Log nginx bổ sung | `access_log_paths` hoặc `auto_discover_logs` |
| Log Apache bổ sung | `apache.access_log_paths` hoặc `apache.auto_discover_logs` |
| stdout container Docker (tùy chọn) | Chỉ khi `auto_discover_docker_logs: true`; parser thử **combined** rồi **uvicorn** |

## Không hỗ trợ làm phân tích chính

- Caddy / Traefik làm nguồn log độc lập
- Log CDN đám mây (Cloudflare, Fastly) không có dòng dạng combined
- Log ứng dụng không phải dòng truy cập HTTP

Nếu kết thúc TLS trên nginx và proxy tới Node/Python, **giữ access logging nginx** — vẫn là bản ghi lưu lượng chuẩn trong prod.

## Apache (thử nghiệm / phụ)

Apache phải dùng định dạng log **combined** (cùng trường nginx combined). Ví dụ:

```apache
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
CustomLog /var/log/apache2/access.log combined
```

Trên metis, container httpd thử có thể chạy **8088** song song nginx 80/443 — xem `metis/deploy/apache-test/`.

### Smoke test bảng admin

1. Triển khai: `./metis/deploy/apache-test/deploy.sh` trên host metis.
2. Tạo lưu lượng:
   ```bash
curl -sS http://127.0.0.1:8088/
curl -sS http://127.0.0.1:8088/admin/
curl -sS "http://127.0.0.1:8088/admin/?page=settings"
tail -n 5 /opt/metis/deploy/apache-test/logs/access_log
```
3. Trong `servers.yaml`: `source: ssh_http_access_log`, `apache.enabled: true`, đường dẫn `access_log`.
4. Trong SKOPOS **Phân tích**, lọc đường dẫn chứa `/admin` — dòng xuất hiện sau collect.

Route admin Apache là **fixture thử nghiệm** xác thực parser/filter; prod vẫn coi log nginx là chuẩn.

## `log_format` nginx khuyến nghị

Gồm tối thiểu: `$remote_addr`, `$time_local`, `$request`, `$status`, `$body_bytes_sent`, `$http_referer`, `$http_user_agent`. Phân tích vhost thêm **`$host`**:

```nginx
log_format skopos '$remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent '
                  '"$http_referer" "$http_user_agent" "$host"';
access_log /var/log/nginx/access.log skopos;
```

## Vì sao ưu tiên nginx?

- Định dạng combined dự đoán được trên fleet
- SSH tail `/var/log/nginx/` không cần agent trên mỗi máy
- Apache tùy chọn cho stack hỗn hợp hoặc node thử
- Module bảo mật vẫn thăm dò metric OS độc lập web stack
