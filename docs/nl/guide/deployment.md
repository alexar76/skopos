# Deployment

## Vereisten

- Python **3.9+** (of Docker)
- SSH-sleuteltoegang tot elke bewaakte host
- **nginx** schrijft accesslogs in combined- of aangepast formaat
- Uitgaand HTTPS bij cloud-LLM's (OpenRouter, OpenAI, enz.)

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

Mount `servers.yaml`, `agent.yaml` en SSH-sleutels via compose-volumes (zie `docker-compose.yml`).

### PostgreSQL (productie)

Gebruik in productie PostgreSQL in plaats van het SQLite-bestand:

```bash
# .env
SKOPOS_POSTGRES_USER=skopos
SKOPOS_POSTGRES_PASSWORD=change-me
SKOPOS_DATABASE_URL=postgresql://skopos:change-me@postgres:5432/skopos

docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

Prioriteit: env **`SKOPOS_DATABASE_URL`** → `database_url` in `servers.yaml` → `db_path` (SQLite dev).

## Productie-checklist

1. Stel **`SKOPOS_DASHBOARD_PASSWORD`** in
2. Gebruik **PostgreSQL** (`SKOPOS_DATABASE_URL`) voor duurzame multi-user prod-opslag
3. Schakel **`SKOPOS_SSH_STRICT_HOST_KEYS=1`** in
4. Beperk poort **8501** tot VPN of reverse proxy met TLS
5. Plan **`skoposctl.py collect`** via cron of systemd timer
6. Schakel auto-scan in bij **Instellingen** (standaard: elke 60 minuten)

## Architectuur (overzicht)

```mermaid
flowchart LR
  nginx[nginx access.log] -->|SSH tail| collector[skopos collector]
  collector --> db[(SQLite or PostgreSQL)]
  db --> ui[Streamlit UI]
  ui --> agent[AI agent]
  collector --> security[Security probes]
  security --> db
```

![Leeg headergebied wordt topnavigatie in SKOPOS](screenshots/topbar-area.png)
