# Dağıtım

## Gereksinimler

- Python **3.9+** (veya Docker)
- Her izlenen ana bilgisayara SSH anahtar erişimi
- **nginx** combined veya özel formatta erişim günlüğü yazıyor olmalı
- Bulut LLM sağlayıcıları (OpenRouter, OpenAI vb.) için giden HTTPS

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

`http://localhost:8501` adresini açın.

## Docker Compose

```bash
docker compose up -d --build
```

compose volume'ları ile `servers.yaml`, `agent.yaml` ve SSH anahtarlarını bağlayın (`docker-compose.yml` bakın).

### PostgreSQL (üretim)

Üretimde SQLite dosyası yerine PostgreSQL kullanın:

```bash
# .env
SKOPOS_POSTGRES_USER=skopos
SKOPOS_POSTGRES_PASSWORD=change-me
SKOPOS_DATABASE_URL=postgresql://skopos:change-me@postgres:5432/skopos

docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

Öncelik: env **`SKOPOS_DATABASE_URL`** → `servers.yaml` içinde `database_url` → `db_path` (SQLite dev).

## Üretim kontrol listesi

1. **`SKOPOS_DASHBOARD_PASSWORD`** ayarlayın
2. Çok kullanıcılı kalıcı prod depolama için **PostgreSQL** (`SKOPOS_DATABASE_URL`)
3. **`SKOPOS_SSH_STRICT_HOST_KEYS=1`** etkinleştirin
4. Port **8501**'i VPN veya TLS'li reverse proxy ile sınırlayın
5. cron veya systemd timer ile **`skoposctl.py collect`** zamanlayın
6. **Ayarlar**'da otomatik taramayı etkinleştirin (varsayılan: 60 dakikada bir)

## Mimari (genel)

```mermaid
flowchart LR
  nginx[nginx access.log] -->|SSH tail| collector[skopos collector]
  collector --> db[(SQLite or PostgreSQL)]
  db --> ui[Streamlit UI]
  ui --> agent[AI agent]
  collector --> security[Security probes]
  security --> db
```

![Boş başlık alanı SKOPOS'ta üst gezinme olur](screenshots/topbar-area.png)
