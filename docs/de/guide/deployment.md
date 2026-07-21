# Deployment

## Anforderungen

- Python **3.9+** (oder Docker)
- SSH-Schlüsselzugriff auf jeden überwachten Host
- **nginx** schreibt Access-Logs im combined- oder Custom-Format
- Ausgehendes HTTPS bei Cloud-LLM-Anbietern (OpenRouter, OpenAI usw.)

## Bare-Metal / VM

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

Öffnen Sie `http://localhost:8501`.

## Docker Compose

```bash
docker compose up -d --build
```

Mounten Sie `servers.yaml`, `agent.yaml` und SSH-Schlüssel per Compose-Volumes (siehe `docker-compose.yml`).

### PostgreSQL (Produktion)

In Produktion PostgreSQL statt SQLite-Datei verwenden:

```bash
# .env
SKOPOS_POSTGRES_USER=skopos
SKOPOS_POSTGRES_PASSWORD=change-me
SKOPOS_DATABASE_URL=postgresql://skopos:change-me@postgres:5432/skopos

docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

Priorität: Env **`SKOPOS_DATABASE_URL`** → `database_url` in `servers.yaml` → `db_path` (SQLite dev).

## Produktions-Checkliste

1. **`SKOPOS_DASHBOARD_PASSWORD`** setzen
2. **PostgreSQL** (`SKOPOS_DATABASE_URL`) für dauerhaften Multi-User-Prod-Speicher
3. **`SKOPOS_SSH_STRICT_HOST_KEYS=1`** aktivieren
4. Port **8501** auf VPN oder Reverse Proxy mit TLS beschränken
5. **`skoposctl.py collect`** per cron oder systemd timer planen
6. Auto-Scan in **Einstellungen** aktivieren (Standard: alle 60 Minuten)

## Architektur (Überblick)

```mermaid
flowchart LR
  nginx[nginx access.log] -->|SSH tail| collector[skopos collector]
  collector --> db[(SQLite or PostgreSQL)]
  db --> ui[Streamlit UI]
  ui --> agent[AI agent]
  collector --> security[Security probes]
  security --> db
```

![Leerer Header-Bereich wird zur Top-Navigation in SKOPOS](screenshots/topbar-area.png)
