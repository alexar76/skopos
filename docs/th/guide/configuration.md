# การกำหนดค่า

## `servers.yaml`

แต่ละรายการเซิร์ฟเวอร์อธิบายการเข้าถึง SSH และ **เส้นทาง log nginx**:

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

| ฟิลด์ | วัตถุประสงค์ |
|------|--------|
| `name` | ป้ายกำกับในแดชบอร์ดและตัวกรอง |
| `source` | `ssh_nginx_access_log` (nginx เท่านั้น) หรือ `ssh_http_access_log` (nginx + Apache ทางเลือก) |
| `nginx.access_log_path` | ไฟล์ access log หลัก |
| `nginx.access_log_paths` | ไฟล์ log เพิ่มเติม (หลายไซต์) |
| `nginx.auto_discover_logs` | แยก config nginx บนโฮสต์เพื่อหาเส้นทางเพิ่ม |
| `nginx.auto_discover_docker_logs` | ทางเลือก: tail คอนเทนเนอร์ Docker HTTP สาธารณะด้วย |

### สิทธิ์

ผู้ใช้ SSH ต้อง **อ่านไฟล์ log nginx** ได้ (มักเป็นกลุ่ม `adm` บน Debian/Ubuntu)

## `agent.yaml`

ผู้ให้บริการ LLM สำหรับ Security Report และเอเจนต์ลอย ค่าเริ่มต้น: **OpenRouter** ผ่าน `OPENROUTER_API_KEY`

## ตัวแปรสภาพแวดล้อม

| ฟิลด์ | วัตถุประสงค์ |
|------|--------|
| `SKOPOS_DASHBOARD_PASSWORD` | รหัสผ่านแดชบอร์ดร่วม (ฟอร์มล็อกอิน); ใน **การตั้งค่า** หรือ `.env` |
| `SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH` | ความยาวขั้นต่ำรหัสผ่านใหม่ (ค่าเริ่มต้น **12**) |
| `SKOPOS_DASHBOARD_SESSION_HOURS` | ออกจากระบบอัตโนมัติหลัง N ชั่วโมง (ค่าเริ่มต้น **12**) |
| `OPENROUTER_API_KEY` | ผู้ให้บริการ LLM เริ่มต้น |
| `SKOPOS_SSH_KEY_PASSPHRASE` | Passphrase สำหรับ SSH key ที่เข้ารหัส |
| `SKOPOS_SSH_STRICT_HOST_KEYS` | `1` เพื่อตรวจสอบ host key |

## เปลี่ยนใน UI ที่ไหน

| ฟิลด์ | วัตถุประสงค์ |
|------|--------|
| ภาษาและธีม | ด้านล่างแถบข้าง |
| การรวบรวม / backfill | แถบด้านข้างใน **การวิเคราะห์** |
| ช่วง auto-scan | **การตั้งค่า** |
| การแจ้งเตือน Telegram | **การตั้งค่า** |
| ผู้ให้บริการเอเจนต์ความปลอดภัย | **ความปลอดภัย** → แท็บ AI Agent |

## Settings sections (detail)

| ฟิลด์ | วัตถุประสงค์ |
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

![การตั้งค่าและควบคุมแถบด้านข้าง](screenshots/settings-fleet.png)

![Sidebar](screenshots/sidebar-nav.png)
