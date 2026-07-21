# التكوين

## `servers.yaml`

كل إدخال خادم يصف الوصول عبر SSH و**مسارات سجلات nginx**:

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

| الحقل | الغرض |
|------|--------|
| `name` | تسمية في اللوحات والمرشّحات |
| `source` | `ssh_nginx_access_log` (nginx فقط) أو `ssh_http_access_log` (nginx + Apache اختياري) |
| `nginx.access_log_path` | ملف سجل الوصول الرئيسي |
| `nginx.access_log_paths` | ملفات سجلات إضافية (مواقع متعددة) |
| `nginx.auto_discover_logs` | تحليل إعدادات nginx على المضيف لاكتشاف مسارات إضافية |
| `nginx.auto_discover_docker_logs` | اختياري: تتبّع حاويات Docker HTTP العامة أيضًا |

### الصلاحيات

يجب أن يستطيع مستخدم SSH **قراءة ملفات سجلات nginx** (غالبًا العضوية في مجموعة `adm` على Debian/Ubuntu).

## `agent.yaml`

مزوّدو LLM لتقرير الأمان والوكيل العائم. الافتراضي: **OpenRouter** عبر `OPENROUTER_API_KEY`.

## متغيّرات البيئة

| الحقل | الغرض |
|------|--------|
| `SKOPOS_DASHBOARD_PASSWORD` | كلمة مرور لوحة التحكم المشتركة (نموذج تسجيل الدخول)； في **الإعدادات** أو `.env` |
| `SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH` | الحد الأدنى لطول كلمات المرور الجديدة (افتراضي **12**) |
| `SKOPOS_DASHBOARD_SESSION_HOURS` | تسجيل خروج تلقائي بعد N ساعة (افتراضي **12**) |
| `OPENROUTER_API_KEY` | مزوّد LLM الافتراضي |
| `SKOPOS_SSH_KEY_PASSPHRASE` | عبارة مرور لمفاتيح SSH المشفّرة |
| `SKOPOS_SSH_STRICT_HOST_KEYS` | `1` للتحقق من مفاتيح المضيف |

## أين تغيّر الإعدادات في الواجهة

| الحقل | الغرض |
|------|--------|
| اللغة والسمة | أسفل الشريط الجانبي |
| الجمع / backfill | الشريط الجانبي في **التحليلات** |
| فترة الفحص التلقائي | **الإعدادات** |
| تنبيهات Telegram | **الإعدادات** |
| مزوّد وكيل الأمان | **الأمان** → تبويب AI Agent |

## Settings sections (detail)

| الحقل | الغرض |
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

![الإعدادات وعناصر الشريط الجانبي](screenshots/settings-fleet.png)

![Sidebar](screenshots/sidebar-nav.png)
