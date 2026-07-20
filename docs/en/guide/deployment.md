# Deployment

## Requirements

- Python **3.9+** (or Docker)
- SSH key access to each monitored host
- **nginx** writing access logs in combined or custom format
- Outbound HTTPS if you use cloud LLM providers (OpenRouter, OpenAI, etc.)

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

Open `http://localhost:8501`.

## Docker Compose

```bash
docker compose up -d --build
```

Mount `servers.yaml`, `agent.yaml`, and SSH keys via compose volumes (see `docker-compose.yml`).

### PostgreSQL (production)

For production, use PostgreSQL instead of the SQLite file:

```bash
# .env
SKOPOS_POSTGRES_USER=skopos
SKOPOS_POSTGRES_PASSWORD=change-me
SKOPOS_DATABASE_URL=postgresql://skopos:change-me@postgres:5432/skopos

docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

Priority: **`SKOPOS_DATABASE_URL`** env → `database_url` in `servers.yaml` → `db_path` (SQLite dev).

## Production checklist

1. Set **`SKOPOS_DASHBOARD_PASSWORD`**
2. Use **PostgreSQL** (`SKOPOS_DATABASE_URL`) for multi-user / durable prod storage
3. Enable **`SKOPOS_SSH_STRICT_HOST_KEYS=1`**
4. Restrict port **8501** to VPN or reverse proxy with TLS
5. Schedule **`skoposctl.py collect`** via cron or systemd timer
6. Enable auto-scan in **Settings** (default: every 60 minutes)

## Architecture (high level)

```mermaid
flowchart LR
  nginx[nginx access.log] -->|SSH tail| collector[skopos collector]
  collector --> db[(SQLite or PostgreSQL)]
  db --> ui[Streamlit UI]
  ui --> agent[AI agent]
  collector --> security[Security probes]
  security --> db
```

![Empty header area becomes top navigation in SKOPOS](screenshots/topbar-area.png)
