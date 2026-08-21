# Deployment

## Persyaratan

- Python **3.9+** (atau Docker)
- Akses kunci SSH ke setiap host yang dimonitor
- **nginx** menulis access log format combined atau kustom
- HTTPS keluar jika menggunakan penyedia LLM cloud (OpenRouter, OpenAI, dll.)

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

Buka `http://localhost:8501`.

## Docker Compose

```bash
docker compose up -d --build
```

Mount `servers.yaml`, `agent.yaml`, dan kunci SSH via volume compose (lihat `docker-compose.yml`).

### PostgreSQL (produksi)

Untuk produksi, gunakan PostgreSQL alih-alih file SQLite:

```bash
# .env
SKOPOS_POSTGRES_USER=skopos
SKOPOS_POSTGRES_PASSWORD=change-me
SKOPOS_DATABASE_URL=postgresql://skopos:change-me@postgres:5432/skopos

docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

Prioritas: env **`SKOPOS_DATABASE_URL`** → `database_url` di `servers.yaml` → `db_path` (SQLite dev).

## Checklist produksi

1. Set **`SKOPOS_DASHBOARD_PASSWORD`**
2. Gunakan **PostgreSQL** (`SKOPOS_DATABASE_URL`) untuk penyimpanan prod multi-pengguna
3. Aktifkan **`SKOPOS_SSH_STRICT_HOST_KEYS=1`**
4. Batasi port **8501** ke VPN atau reverse proxy dengan TLS
5. Jadwalkan **`skoposctl.py collect`** via cron atau systemd timer
6. Aktifkan auto-scan di **Pengaturan** (default: setiap 60 menit)

## Arsitektur (ringkas)

```mermaid
flowchart LR
  nginx[nginx access.log] -->|SSH tail| collector[skopos collector]
  collector --> db[(SQLite or PostgreSQL)]
  db --> ui[Streamlit UI]
  ui --> agent[AI agent]
  collector --> security[Security probes]
  security --> db
```

![Area header kosong menjadi navigasi atas di SKOPOS](../../screenshots/topbar-area.png)
