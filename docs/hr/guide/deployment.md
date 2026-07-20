# Implementacija

## Zahtjevi

- Python **3.9+** (ili Docker)
- SSH pristup ključem na svaki nadgledani host
- **nginx** piše access logove u combined ili prilagođenom formatu
- Odlazni HTTPS ako koristite cloud LLM (OpenRouter, OpenAI itd.)

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

Otvorite `http://localhost:8501`.

## Docker Compose

```bash
docker compose up -d --build
```

Mountajte `servers.yaml`, `agent.yaml` i SSH ključeve putem compose volumena (vidi `docker-compose.yml`).

### PostgreSQL (produkcija)

U produkciji koristite PostgreSQL umjesto SQLite datoteke:

```bash
# .env
SKOPOS_POSTGRES_USER=skopos
SKOPOS_POSTGRES_PASSWORD=change-me
SKOPOS_DATABASE_URL=postgresql://skopos:change-me@postgres:5432/skopos

docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

Prioritet: env **`SKOPOS_DATABASE_URL`** → `database_url` u `servers.yaml` → `db_path` (SQLite dev).

## Produkcijski checklist

1. Postavite **`SKOPOS_DASHBOARD_PASSWORD`**
2. Koristite **PostgreSQL** (`SKOPOS_DATABASE_URL`) za trajno multi-user prod pohranu
3. Uključite **`SKOPOS_SSH_STRICT_HOST_KEYS=1`**
4. Ograničite port **8501** na VPN ili reverse proxy s TLS-om
5. Zakažite **`skoposctl.py collect`** putem cron-a ili systemd timera
6. Uključite auto-scan u **Postavkama** (zadano: svakih 60 minuta)

## Arhitektura (pregled)

```mermaid
flowchart LR
  nginx[nginx access.log] -->|SSH tail| collector[skopos collector]
  collector --> db[(SQLite or PostgreSQL)]
  db --> ui[Streamlit UI]
  ui --> agent[AI agent]
  collector --> security[Security probes]
  security --> db
```

![Prazno područje zaglavlja postaje gornja navigacija u SKOPOS-u](screenshots/topbar-area.png)
