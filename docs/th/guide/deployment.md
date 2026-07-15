# การ deploy

## ข้อกำหนด

- Python **3.9+** (หรือ Docker)
- การเข้าถึง SSH key ไปยังแต่ละโฮสต์ที่ตรวจสอบ
- **nginx** เขียน access log รูปแบบ combined หรือกำหนดเอง
- HTTPS ขาออกหากใช้ผู้ให้บริการ LLM บนคลาวด์ (OpenRouter, OpenAI ฯลฯ)

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

เปิด `http://localhost:8501`

## Docker Compose

```bash
docker compose up -d --build
```

mount `servers.yaml`, `agent.yaml` และ SSH key ผ่าน compose volumes (ดู `docker-compose.yml`)

### PostgreSQL (production)

ใน production ใช้ PostgreSQL แทนไฟล์ SQLite:

```bash
# .env
SKOPOS_POSTGRES_USER=skopos
SKOPOS_POSTGRES_PASSWORD=change-me
SKOPOS_DATABASE_URL=postgresql://skopos:change-me@postgres:5432/skopos

docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

ลำดับความสำคัญ: env **`SKOPOS_DATABASE_URL`** → `database_url` ใน `servers.yaml` → `db_path` (SQLite dev)

## เช็กลิสต์ production

1. ตั้ง **`SKOPOS_DASHBOARD_PASSWORD`**
2. ใช้ **PostgreSQL** (`SKOPOS_DATABASE_URL`) สำหรับที่เก็บ prod หลายผู้ใช้
3. เปิด **`SKOPOS_SSH_STRICT_HOST_KEYS=1`**
4. จำกัดพอร์ต **8501** ให้ VPN หรือ reverse proxy พร้อม TLS
5. กำหนด **`skoposctl.py collect`** ผ่าน cron หรือ systemd timer
6. เปิด auto-scan ใน **การตั้งค่า** (ค่าเริ่มต้น: ทุก 60 นาที)

## สถาปัตยกรรม (ภาพรวม)

```mermaid
flowchart LR
  nginx[nginx access.log] -->|SSH tail| collector[skopos collector]
  collector --> db[(SQLite or PostgreSQL)]
  db --> ui[Streamlit UI]
  ui --> agent[AI agent]
  collector --> security[Security probes]
  security --> db
```

![พื้นที่ header ว่างกลายเป็นการนำทางด้านบนใน SKOPOS](screenshots/topbar-area.png)
