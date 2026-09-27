# डिप्लॉयमेंट

## आवश्यकताएँ

- Python **3.9+** (या Docker)
- प्रत्येक मॉनिटर किए गए होस्ट पर SSH कुंजी पहुँच
- **nginx** combined या कस्टम प्रारूप में एक्सेस लॉग लिख रहा हो
- क्लाउड LLM प्रदाताओं (OpenRouter, OpenAI आदि) के लिए आउटबाउंड HTTPS

## बेयर-मेटल / VM

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

`http://localhost:8501` खोलें।

## Docker Compose

```bash
docker compose up -d --build
```

compose volumes के माध्यम से `servers.yaml`, `agent.yaml` और SSH कुंजियाँ माउंट करें (`docker-compose.yml` देखें)।

### PostgreSQL (प्रोडक्शन)

प्रोडक्शन के लिए SQLite फ़ाइल के बजाय PostgreSQL का उपयोग करें:

```bash
# .env
SKOPOS_POSTGRES_USER=skopos
SKOPOS_POSTGRES_PASSWORD=change-me
SKOPOS_DATABASE_URL=postgresql://skopos:change-me@postgres:5432/skopos

docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

प्राथमिकता: **`SKOPOS_DATABASE_URL`** env → `servers.yaml` में `database_url` → `db_path` (SQLite dev)।

## प्रोडक्शन चेकलिस्ट

1. **`SKOPOS_DASHBOARD_PASSWORD`** सेट करें
2. मल्टी-यूज़र / टिकाऊ प्रोड स्टोरेज के लिए **PostgreSQL** (`SKOPOS_DATABASE_URL`)
3. **`SKOPOS_SSH_STRICT_HOST_KEYS=1`** सक्षम करें
4. पोर्ट **8501** को VPN या TLS वाले reverse proxy तक सीमित करें
5. cron या systemd timer के माध्यम से **`skoposctl.py collect`** शेड्यूल करें
6. **सेटिंग्स** में ऑटो-स्कैन सक्षम करें (डिफ़ॉल्ट: हर 60 मिनट)

## आर्किटेक्चर (उच्च स्तर)

```mermaid
flowchart LR
  nginx[nginx access.log] -->|SSH tail| collector[skopos collector]
  collector --> db[(SQLite or PostgreSQL)]
  db --> ui[Streamlit UI]
  ui --> agent[AI agent]
  collector --> security[Security probes]
  security --> db
```

![खाली हेडर क्षेत्र SKOPOS में टॉप नेविगेशन बन जाता है](../../screenshots/topbar-area.png)
