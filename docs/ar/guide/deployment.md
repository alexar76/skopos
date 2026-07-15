# النشر

## المتطلبات

- Python **3.9+** (أو Docker)
- وصول SSH بمفتاح إلى كل مضيف مراقَب
- **nginx** يكتب سجلات الوصول بصيغة combined أو مخصّصة
- HTTPS صادر إذا كنت تستخدم مزوّدي LLM السحابيين (OpenRouter وOpenAI وغيرها)

## خادم فعلي / VM

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

افتح `http://localhost:8501`.

## Docker Compose

```bash
docker compose up -d --build
```

اربط `servers.yaml` و`agent.yaml` ومفاتيح SSH عبر volumes في compose (راجع `docker-compose.yml`).

### PostgreSQL (الإنتاج)

للإنتاج، استخدم PostgreSQL بدل ملف SQLite:

```bash
# .env
SKOPOS_POSTGRES_USER=skopos
SKOPOS_POSTGRES_PASSWORD=change-me
SKOPOS_DATABASE_URL=postgresql://skopos:change-me@postgres:5432/skopos

docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

الأولوية: متغيّر **`SKOPOS_DATABASE_URL`** → `database_url` في `servers.yaml` → `db_path` (SQLite للتطوير).

## قائمة التحقق للإنتاج

1. عيّن **`SKOPOS_DASHBOARD_PASSWORD`**
2. استخدم **PostgreSQL** (`SKOPOS_DATABASE_URL`) للتخزين الدائم متعدد المستخدمين
3. فعّل **`SKOPOS_SSH_STRICT_HOST_KEYS=1`**
4. قيّد المنفذ **8501** على VPN أو وكيل عكسي مع TLS
5. جدولة **`skoposctl.py collect`** عبر cron أو systemd timer
6. فعّل الفحص التلقائي في **الإعدادات** (افتراضيًا كل 60 دقيقة)

## البنية (مختصر)

```mermaid
flowchart LR
  nginx[nginx access.log] -->|SSH tail| collector[skopos collector]
  collector --> db[(SQLite or PostgreSQL)]
  db --> ui[Streamlit UI]
  ui --> agent[AI agent]
  collector --> security[Security probes]
  security --> db
```

![منطقة الرأس الفارغة تصبح تنقلًا علويًا في SKOPOS](screenshots/topbar-area.png)
