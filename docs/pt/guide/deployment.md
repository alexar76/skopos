# Implantação

## Requisitos

- Python **3.9+** (ou Docker)
- Acesso SSH com chave a cada host monitorado
- **nginx** gravando logs de acesso em formato combined ou personalizado
- HTTPS de saída se usar provedores LLM na nuvem (OpenRouter, OpenAI etc.)

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

Monte `servers.yaml`, `agent.yaml` e chaves SSH via volumes do compose (veja `docker-compose.yml`).

### PostgreSQL (produção)

Em produção, use PostgreSQL em vez do arquivo SQLite:

```bash
# .env
SKOPOS_POSTGRES_USER=skopos
SKOPOS_POSTGRES_PASSWORD=change-me
SKOPOS_DATABASE_URL=postgresql://skopos:change-me@postgres:5432/skopos

docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

Prioridade: env **`SKOPOS_DATABASE_URL`** → `database_url` em `servers.yaml` → `db_path` (SQLite dev).

## Checklist de produção

1. Defina **`SKOPOS_DASHBOARD_PASSWORD`**
2. Use **PostgreSQL** (`SKOPOS_DATABASE_URL`) para armazenamento durável multiusuário
3. Ative **`SKOPOS_SSH_STRICT_HOST_KEYS=1`**
4. Restrinja a porta **8501** a VPN ou proxy reverso com TLS
5. Agende **`skoposctl.py collect`** via cron ou systemd timer
6. Ative varredura automática em **Configurações** (padrão: a cada 60 minutos)

## Arquitetura (visão geral)

```mermaid
flowchart LR
  nginx[nginx access.log] -->|SSH tail| collector[skopos collector]
  collector --> db[(SQLite or PostgreSQL)]
  db --> ui[Streamlit UI]
  ui --> agent[AI agent]
  collector --> security[Security probes]
  security --> db
```

![A área vazia do cabeçalho vira navegação superior no SKOPOS](screenshots/topbar-area.png)
