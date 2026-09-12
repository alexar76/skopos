# Triển khai

## Yêu cầu

- Python **3.9+** (hoặc Docker)
- Truy cập khóa SSH tới mỗi host được giám sát
- **nginx** ghi access log định dạng combined hoặc tùy chỉnh
- HTTPS ra ngoài nếu dùng nhà cung cấp LLM đám mây (OpenRouter, OpenAI, v.v.)

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

Mở `http://localhost:8501`.

## Docker Compose

```bash
docker compose up -d --build
```

Mount `servers.yaml`, `agent.yaml` và khóa SSH qua volume compose (xem `docker-compose.yml`).

### PostgreSQL (sản xuất)

Trong sản xuất, dùng PostgreSQL thay cho file SQLite:

```bash
# .env
SKOPOS_POSTGRES_USER=skopos
SKOPOS_POSTGRES_PASSWORD=change-me
SKOPOS_DATABASE_URL=postgresql://skopos:change-me@postgres:5432/skopos

docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

Ưu tiên: env **`SKOPOS_DATABASE_URL`** → `database_url` trong `servers.yaml` → `db_path` (SQLite dev).

## Checklist sản xuất

1. Đặt **`SKOPOS_DASHBOARD_PASSWORD`**
2. Dùng **PostgreSQL** (`SKOPOS_DATABASE_URL`) cho lưu trữ prod đa người dùng
3. Bật **`SKOPOS_SSH_STRICT_HOST_KEYS=1`**
4. Giới hạn cổng **8501** qua VPN hoặc reverse proxy TLS
5. Lên lịch **`skoposctl.py collect`** qua cron hoặc systemd timer
6. Bật quét tự động trong **Cài đặt** (mặc định: 60 phút)

## Kiến trúc (tổng quan)

```mermaid
flowchart LR
  nginx[nginx access.log] -->|SSH tail| collector[skopos collector]
  collector --> db[(SQLite or PostgreSQL)]
  db --> ui[Streamlit UI]
  ui --> agent[AI agent]
  collector --> security[Security probes]
  security --> db
```

![Vùng header trống trở thành điều hướng trên trong SKOPOS](../../screenshots/topbar-area.png)
