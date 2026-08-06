# 部署

## 要求

- Python **3.9+**（或 Docker）
- 对每个受监控主机的 SSH 密钥访问
- **nginx** 以 combined 或自定义格式写入访问日志
- 若使用云端 LLM 提供商（OpenRouter、OpenAI 等），需出站 HTTPS

## 裸机 / 虚拟机

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

打开 `http://localhost:8501`。

## Docker Compose

```bash
docker compose up -d --build
```

通过 compose 卷挂载 `servers.yaml`、`agent.yaml` 和 SSH 密钥（参见 `docker-compose.yml`）。

### PostgreSQL（生产环境）

生产环境请使用 PostgreSQL 替代 SQLite 文件：

```bash
# .env
SKOPOS_POSTGRES_USER=skopos
SKOPOS_POSTGRES_PASSWORD=change-me
SKOPOS_DATABASE_URL=postgresql://skopos:change-me@postgres:5432/skopos

docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

优先级：**`SKOPOS_DATABASE_URL`** 环境变量 → `servers.yaml` 中的 `database_url` → `db_path`（SQLite 开发）。

## 生产检查清单

1. 设置 **`SKOPOS_DASHBOARD_PASSWORD`**
2. 多用户/持久化生产存储使用 **PostgreSQL**（`SKOPOS_DATABASE_URL`）
3. 启用 **`SKOPOS_SSH_STRICT_HOST_KEYS=1`**
4. 将端口 **8501** 限制为 VPN 或带 TLS 的反向代理
5. 通过 cron 或 systemd 定时器调度 **`skoposctl.py collect`**
6. 在 **设置** 中启用自动扫描（默认每 60 分钟）

## 架构（概览）

```mermaid
flowchart LR
  nginx[nginx access.log] -->|SSH tail| collector[skopos collector]
  collector --> db[(SQLite or PostgreSQL)]
  db --> ui[Streamlit UI]
  ui --> agent[AI agent]
  collector --> security[Security probes]
  security --> db
```

![空白页眉区域在 SKOPOS 中变为顶部导航](../../screenshots/topbar-area.png)
