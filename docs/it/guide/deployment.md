# Deployment

## Requisiti

- Python **3.9+** (o Docker)
- Accesso SSH con chiave a ogni host monitorato
- **nginx** che scrive access log in formato combined o personalizzato
- HTTPS in uscita se usi LLM cloud (OpenRouter, OpenAI, ecc.)

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

Apri `http://localhost:8501`.

## Docker Compose

```bash
docker compose up -d --build
```

Monta `servers.yaml`, `agent.yaml` e chiavi SSH via volumi compose (vedi `docker-compose.yml`).

### PostgreSQL (produzione)

In produzione usa PostgreSQL invece del file SQLite:

```bash
# .env
SKOPOS_POSTGRES_USER=skopos
SKOPOS_POSTGRES_PASSWORD=change-me
SKOPOS_DATABASE_URL=postgresql://skopos:change-me@postgres:5432/skopos

docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

Priorità: env **`SKOPOS_DATABASE_URL`** → `database_url` in `servers.yaml` → `db_path` (SQLite dev).

## Checklist produzione

1. Imposta **`SKOPOS_DASHBOARD_PASSWORD`**
2. Usa **PostgreSQL** (`SKOPOS_DATABASE_URL`) per storage prod multi-utente
3. Abilita **`SKOPOS_SSH_STRICT_HOST_KEYS=1`**
4. Limita la porta **8501** a VPN o reverse proxy con TLS
5. Pianifica **`skoposctl.py collect`** via cron o systemd timer
6. Abilita auto-scan in **Impostazioni** (default: ogni 60 minuti)

## Architettura (panoramica)

```mermaid
flowchart LR
  nginx[nginx access.log] -->|SSH tail| collector[skopos collector]
  collector --> db[(SQLite or PostgreSQL)]
  db --> ui[Streamlit UI]
  ui --> agent[AI agent]
  collector --> security[Security probes]
  security --> db
```

![L'area header vuota diventa navigazione superiore in SKOPOS](screenshots/topbar-area.png)
