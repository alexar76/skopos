# Cấu hình

## `servers.yaml`

Mỗi mục máy chủ mô tả truy cập SSH và **đường dẫn log nginx**:

```yaml
servers:
  - name: factory
    source: ssh_nginx_access_log
    ssh:
      host: 203.0.113.10
      port: 22
      user: deploy
      key_path: ~/.ssh/id_rsa
    nginx:
      access_log_path: /var/log/nginx/access.log
      auto_discover_logs: true
      auto_discover_docker_logs: false
```

| Trường | Mục đích |
|------|--------|
| `name` | Nhãn trên bảng và bộ lọc |
| `source` | `ssh_nginx_access_log` (chỉ nginx) hoặc `ssh_http_access_log` (nginx + Apache tùy chọn) |
| `nginx.access_log_path` | File access log chính |
| `nginx.access_log_paths` | File log bổ sung (đa site) |
| `nginx.auto_discover_logs` | Phân tích cấu hình nginx trên host để tìm thêm đường dẫn |
| `nginx.auto_discover_docker_logs` | Tùy chọn: tail container Docker HTTP công khai |

### Quyền

Người dùng SSH phải **đọc được file log nginx** (thường là nhóm `adm` trên Debian/Ubuntu).

## `agent.yaml`

Nhà cung cấp LLM cho Security Report và tác tử nổi. Mặc định: **OpenRouter** qua `OPENROUTER_API_KEY`.

## Biến môi trường

| Trường | Mục đích |
|------|--------|
| `SKOPOS_DASHBOARD_PASSWORD` | Mật khẩu bảng chia sẻ (form đăng nhập); trong **Cài đặt** hoặc `.env` |
| `SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH` | Độ dài tối thiểu mật khẩu mới (mặc định **12**) |
| `SKOPOS_DASHBOARD_SESSION_HOURS` | Tự đăng xuất sau N giờ (mặc định **12**) |
| `OPENROUTER_API_KEY` | Nhà cung cấp LLM mặc định |
| `SKOPOS_SSH_KEY_PASSPHRASE` | Passphrase cho khóa SSH mã hóa |
| `SKOPOS_SSH_STRICT_HOST_KEYS` | `1` để xác minh host key |

## Thay đổi ở đâu trong UI

| Trường | Mục đích |
|------|--------|
| Ngôn ngữ & giao diện | Cuối thanh bên |
| Thu thập / backfill | Thanh bên **Phân tích** |
| Khoảng quét tự động | **Cài đặt** |
| Cảnh báo Telegram | **Cài đặt** |
| Nhà cung cấp tác tử bảo mật | **Bảo mật** → tab AI Agent |

## Settings sections (detail)

| Trường | Mục đích |
|------|--------|
| Dashboard access | `SKOPOS_DASHBOARD_PASSWORD`, session hours, min length policy |
| Database | `SKOPOS_DATABASE_URL` or SQLite `db_path`; test + migrate in UI |
| Auto-scan | Background security scan interval (minutes) |
| Telegram | `SKOPOS_TELEGRAM_*` env vars; notify on new critical findings |
| SSH keys | Generate Ed25519; keys stored under `.skopos/ssh/` |
| Fleet servers | Visual editor for `servers.yaml` — nginx, Apache, docker logs |

## `agent.yaml` providers

Each provider block needs an API key env var. Default stack uses **OpenRouter** (`OPENROUTER_API_KEY`). Providers appear in Summary Report, floating agent, and Security → AI Agent tab.

| Provider | API key |
|------|--------|
| `openrouter` | `OPENROUTER_API_KEY` — default; many models via one key |
| `openai` | `OPENAI_API_KEY` |
| `anthropic` | `ANTHROPIC_API_KEY` |
| `deepseek` | `DEEPSEEK_API_KEY` |

![Cài đặt và điều khiển thanh bên](screenshots/settings-fleet.png)

![Sidebar](screenshots/sidebar-nav.png)
