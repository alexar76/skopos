# Nasadenie

## Požiadavky

- Python **3.9+** (alebo Docker)
- SSH prístup kľúčom ku každému monitorovanému hostu
- **nginx** zapisuje access logy vo formáte combined alebo vlastnom
- Odchádzajúce HTTPS pri cloud LLM (OpenRouter, OpenAI atď.)

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

Otvorte `http://localhost:8501`.

## Docker Compose

```bash
docker compose up -d --build
```

Namontujte `servers.yaml`, `agent.yaml` a SSH kľúče cez compose volumes (pozri `docker-compose.yml`).

### PostgreSQL (produkcia)

V produkcii použite PostgreSQL namiesto SQLite súboru:

```bash
# .env
SKOPOS_POSTGRES_USER=skopos
SKOPOS_POSTGRES_PASSWORD=change-me
SKOPOS_DATABASE_URL=postgresql://skopos:change-me@postgres:5432/skopos

docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

Priorita: env **`SKOPOS_DATABASE_URL`** → `database_url` v `servers.yaml` → `db_path` (SQLite dev).

## Produkčný checklist

1. Nastavte **`SKOPOS_DASHBOARD_PASSWORD`**
2. Použite **PostgreSQL** (`SKOPOS_DATABASE_URL`) pre multi-user prod úložisko
3. Zapnite **`SKOPOS_SSH_STRICT_HOST_KEYS=1`**
4. Obmedzte port **8501** na VPN alebo reverse proxy s TLS
5. Naplánujte **`skoposctl.py collect`** cez cron alebo systemd timer
6. Zapnite auto-scan v **Nastaveniach** (predvolene: každých 60 minút)

## Architektúra (prehľad)

```mermaid
flowchart LR
  nginx[nginx access.log] -->|SSH tail| collector[skopos collector]
  collector --> db[(SQLite or PostgreSQL)]
  db --> ui[Streamlit UI]
  ui --> agent[AI agent]
  collector --> security[Security probes]
  security --> db
```

![Prázdna oblasť hlavičky sa stane hornou navigáciou v SKOPOS](../../screenshots/topbar-area.png)
