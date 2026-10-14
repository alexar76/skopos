# Quick Start

> **Scope:** SKOPOS analytics are built for **nginx access logs** collected over SSH. **Apache combined** logs are supported when `apache.enabled: true`. Caddy, Traefik, and raw application logs are not primary sources. Optional Docker log discovery still expects nginx combined or uvicorn-shaped HTTP lines.

Get the SKOPOS dashboard running in under 5 minutes.

## 1. Prerequisites

- Python 3.9+
- SSH key access to your servers (`~/.ssh/id_rsa`)
- Optional: `OPENROUTER_API_KEY` for AI security analysis (default in `agent.yaml`)

## 2. Install

```bash
cd skopos
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp servers.example.yaml servers.yaml
cp agent.example.yaml agent.yaml
export SKOPOS_SSH_KEY_PASSPHRASE='your-key-passphrase'   # if needed
export OPENROUTER_API_KEY='sk-or-...'                   # for AI agent
export SKOPOS_DASHBOARD_PASSWORD='your-secret'           # recommended if exposed
```

## 3. Configure servers

Edit `servers.yaml` — set SSH host, port, user, nginx log paths. Or use **Settings** in the UI after launch.

## 4. Collect traffic

```bash
python skoposctl.py discover
python skoposctl.py collect
```

## 5. Security scan

```bash
python skoposctl.py security-scan
```

## 6. Launch dashboard

```bash
streamlit run dashboard.py
```

Open **Quick Start** in the sidebar (`🚀 Quick Start`) — the guided wizard helps you add a server, test SSH, collect traffic, and run your first security scan.

Other pages:

- **Analytics** — `http://localhost:8501` (main page)
- **Security** — sidebar → Security
- **Scan History** — sidebar → Scan History
- **Settings** — sidebar → Settings (auto-scan, SSH keys)

## Docker

```bash
docker compose up -d --build
```

Mount `~/.ssh`, set env vars in `docker-compose.yml`.
