# پیکربندی

## `servers.yaml`

هر ورودی سرور دسترسی SSH و **مسیرهای لاگ nginx** را توصیف می‌کند:

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

| فیلد | هدف |
|------|--------|
| `name` | برچسب در داشبوردها و فیلترها |
| `source` | `ssh_nginx_access_log` (فقط nginx) یا `ssh_http_access_log` (nginx + Apache اختیاری) |
| `nginx.access_log_path` | فایل access log اصلی |
| `nginx.access_log_paths` | فایل‌های لاگ اضافی (چندسایته) |
| `nginx.auto_discover_logs` | پیکربندی nginx روی میزبان را برای مسیرهای بیشتر parse کنید |
| `nginx.auto_discover_docker_logs` | اختیاری: کانتینرهای Docker HTTP عمومی را هم tail کنید |

### مجوزها

کاربر SSH باید بتواند **فایل‌های لاگ nginx را بخواند** (اغلب عضویت در گروه `adm` در Debian/Ubuntu).

## `agent.yaml`

ارائه‌دهندگان LLM برای Security Report و عامل شناور. پیش‌فرض: **OpenRouter** از طریق `OPENROUTER_API_KEY`.

## متغیرهای محیطی

| فیلد | هدف |
|------|--------|
| `SKOPOS_DASHBOARD_PASSWORD` | رمز عبور مشترک داشبورد (فرم ورود)； در **تنظیمات** یا `.env` |
| `SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH` | حداقل طول رمزهای جدید (پیش‌فرض **12**) |
| `SKOPOS_DASHBOARD_SESSION_HOURS` | خروج خودکار پس از N ساعت (پیش‌فرض **12**) |
| `OPENROUTER_API_KEY` | ارائه‌دهنده LLM پیش‌فرض |
| `SKOPOS_SSH_KEY_PASSPHRASE` | Passphrase برای کلیدهای SSH رمزنگاری‌شده |
| `SKOPOS_SSH_STRICT_HOST_KEYS` | `1` برای تأیید host key |

## کجا در رابط کاربری تغییر دهید

| فیلد | هدف |
|------|--------|
| زبان و تم | پایین نوار کناری |
| جمع‌آوری / backfill | نوار کناری در **تحلیل‌ها** |
| فاصله اسکن خودکار | **تنظیمات** |
| هشدارهای Telegram | **تنظیمات** |
| ارائه‌دهنده عامل امنیت | **امنیت** → تب AI Agent |

## Settings sections (detail)

| فیلد | هدف |
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

![تنظیمات و کنترل‌های نوار کناری](screenshots/settings-fleet.png)

![Sidebar](screenshots/sidebar-nav.png)
