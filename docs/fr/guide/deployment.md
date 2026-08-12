# Déploiement

## Prérequis

- Python **3.9+** (ou Docker)
- Accès SSH par clé à chaque hôte surveillé
- **nginx** écrivant des access logs au format combined ou personnalisé
- HTTPS sortant si vous utilisez des LLM cloud (OpenRouter, OpenAI, etc.)

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

Ouvrez `http://localhost:8501`.

## Docker Compose

```bash
docker compose up -d --build
```

Montez `servers.yaml`, `agent.yaml` et clés SSH via volumes compose (voir `docker-compose.yml`).

### PostgreSQL (production)

En production, utilisez PostgreSQL plutôt que le fichier SQLite :

```bash
# .env
SKOPOS_POSTGRES_USER=skopos
SKOPOS_POSTGRES_PASSWORD=change-me
SKOPOS_DATABASE_URL=postgresql://skopos:change-me@postgres:5432/skopos

docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

Priorité : env **`SKOPOS_DATABASE_URL`** → `database_url` dans `servers.yaml` → `db_path` (SQLite dev).

## Checklist production

1. Définissez **`SKOPOS_DASHBOARD_PASSWORD`**
2. Utilisez **PostgreSQL** (`SKOPOS_DATABASE_URL`) pour un stockage prod durable multi-utilisateur
3. Activez **`SKOPOS_SSH_STRICT_HOST_KEYS=1`**
4. Restreignez le port **8501** au VPN ou reverse proxy avec TLS
5. Planifiez **`skoposctl.py collect`** via cron ou systemd timer
6. Activez l'analyse auto dans **Paramètres** (par défaut : toutes les 60 minutes)

## Architecture (vue d'ensemble)

```mermaid
flowchart LR
  nginx[nginx access.log] -->|SSH tail| collector[skopos collector]
  collector --> db[(SQLite or PostgreSQL)]
  db --> ui[Streamlit UI]
  ui --> agent[AI agent]
  collector --> security[Security probes]
  security --> db
```

![La zone d'en-tête vide devient la navigation supérieure dans SKOPOS](../../screenshots/topbar-area.png)
