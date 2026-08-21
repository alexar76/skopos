# Despliegue

## Requisitos

- Python **3.9+** (o Docker)
- Acceso SSH con clave a cada host
- **nginx** escribiendo access logs (combined u otro formato)
- HTTPS saliente si usa LLM en la nube (OpenRouter, etc.)

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

Abra `http://localhost:8501`.

## Docker Compose

```bash
docker compose up -d --build
```

Monte `servers.yaml`, `agent.yaml` y claves SSH en volumes (ver `docker-compose.yml`).

### PostgreSQL (producción)

En producción use PostgreSQL en lugar del archivo SQLite:

```bash
# .env
SKOPOS_POSTGRES_USER=skopos
SKOPOS_POSTGRES_PASSWORD=change-me
SKOPOS_DATABASE_URL=postgresql://skopos:change-me@postgres:5432/skopos

docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

Prioridad: env **`SKOPOS_DATABASE_URL`** → `database_url` en `servers.yaml` → `db_path` (SQLite dev).

## Lista de producción

1. Defina **`SKOPOS_DASHBOARD_PASSWORD`**
2. Use **PostgreSQL** (`SKOPOS_DATABASE_URL`) en prod
3. Active **`SKOPOS_SSH_STRICT_HOST_KEYS=1`**
4. Restrinja el puerto **8501** (VPN / reverse proxy + TLS)
5. Programe **`skoposctl.py collect`** (cron/systemd)
6. Auto-scan en **Ajustes** (cada 60 min por defecto)

## Arquitectura (resumen)

```mermaid
flowchart LR
  nginx[nginx access.log] -->|SSH tail| collector[skopos collector]
  collector --> db[(SQLite or PostgreSQL)]
  db --> ui[Streamlit UI]
  ui --> agent[AI agent]
  collector --> security[Security probes]
  security --> db
```

![La cabecera superior con menú de navegación](../../screenshots/topbar-area.png)
