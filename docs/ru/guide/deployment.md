# Развёртывание

## Требования

- Python **3.9+** (или Docker)
- SSH-ключ до каждого хоста
- **nginx** с access-логами (combined или свой формат)
- HTTPS наружу — если используете облачные LLM (OpenRouter и т.д.)

## Установка на сервер

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

Откройте `http://localhost:8501`.

## Docker Compose

```bash
docker compose up -d --build
```

Подключите `servers.yaml`, `agent.yaml` и SSH-ключи через volumes (см. `docker-compose.yml`).

### PostgreSQL (prod)

Для production используйте PostgreSQL вместо SQLite:

```bash
# .env
SKOPOS_POSTGRES_USER=skopos
SKOPOS_POSTGRES_PASSWORD=change-me
SKOPOS_DATABASE_URL=postgresql://skopos:change-me@postgres:5432/skopos

docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

Приоритет: env **`SKOPOS_DATABASE_URL`** → `database_url` в `servers.yaml` → `db_path` (SQLite для dev).

## Продакшен

1. Задайте **`SKOPOS_DASHBOARD_PASSWORD`**
2. Используйте **PostgreSQL** (`SKOPOS_DATABASE_URL`) для prod
3. Включите **`SKOPOS_SSH_STRICT_HOST_KEYS=1`**
4. Закройте порт **8501** (VPN / reverse proxy + TLS)
5. Cron для **`skoposctl.py collect`**
6. Авто-скан в **Настройках** (по умолчанию каждые 60 мин)

## Архитектура (кратко)

```mermaid
flowchart LR
  nginx[nginx access.log] -->|SSH tail| collector[skopos collector]
  collector --> db[(SQLite or PostgreSQL)]
  db --> ui[Streamlit UI]
  ui --> agent[AI agent]
  collector --> security[Security probes]
  security --> db
```

![Верхняя панель с меню](../../screenshots/topbar-area.png)
