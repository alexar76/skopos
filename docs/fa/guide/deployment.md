# استقرار

## الزامات

- Python **3.9+** (یا Docker)
- دسترسی کلید SSH به هر میزبان پایش‌شده
- **nginx** در حال نوشتن access log با فرمت combined یا سفارشی
- HTTPS خروجی در صورت استفاده از ارائه‌دهندگان LLM ابری (OpenRouter، OpenAI و غیره)

## Bare-metal / VM

```bash
cd skopos
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp servers.example.yaml servers.yaml
cp agent.example.yaml agent.yaml
export SKOPOS_DASHBOARD_PASSWORD='strong-secret'
python skoposctl.py collect
python skoposctl.py security-scan
streamlit run dashboard.py
```

`http://localhost:8501` را باز کنید.

## Docker Compose

```bash
docker compose up -d --build
```

`servers.yaml`، `agent.yaml` و کلیدهای SSH را از طریق volumeهای compose mount کنید (نگاه کنید به `docker-compose.yml`).

### PostgreSQL (تولید)

در تولید به‌جای فایل SQLite از PostgreSQL استفاده کنید:

```bash
# .env
SKOPOS_POSTGRES_USER=skopos
SKOPOS_POSTGRES_PASSWORD=change-me
SKOPOS_DATABASE_URL=postgresql://skopos:change-me@postgres:5432/skopos

docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

اولویت: env **`SKOPOS_DATABASE_URL`** → `database_url` در `servers.yaml` → `db_path` (SQLite dev).

## چک‌لیست تولید

1. **`SKOPOS_DASHBOARD_PASSWORD`** را تنظیم کنید
2. برای ذخیره‌سازی prod چندکاربره از **PostgreSQL** (`SKOPOS_DATABASE_URL`) استفاده کنید
3. **`SKOPOS_SSH_STRICT_HOST_KEYS=1`** را فعال کنید
4. پورت **8501** را به VPN یا reverse proxy با TLS محدود کنید
5. **`skoposctl.py collect`** را با cron یا systemd timer زمان‌بندی کنید
6. اسکن خودکار را در **تنظیمات** فعال کنید (پیش‌فرض: هر ۶۰ دقیقه)

## معماری (سطح بالا)

```mermaid
flowchart LR
  nginx[nginx access.log] -->|SSH tail| collector[skopos collector]
  collector --> db[(SQLite or PostgreSQL)]
  db --> ui[Streamlit UI]
  ui --> agent[AI agent]
  collector --> security[Security probes]
  security --> db
```

![ناحیه خالی سربرگ در SKOPOS به ناوبری بالا تبدیل می‌شود](screenshots/topbar-area.png)
