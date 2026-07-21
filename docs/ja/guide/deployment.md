# デプロイ

## 要件

- Python **3.9+**（または Docker）
- 監視対象ホストごとの SSH キーアクセス
- **nginx** が combined またはカスタム形式でアクセスログを出力
- クラウド LLM プロバイダー（OpenRouter、OpenAI など）利用時は外向き HTTPS

## ベアメタル / VM

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

`http://localhost:8501` を開きます。

## Docker Compose

```bash
docker compose up -d --build
```

compose ボリュームで `servers.yaml`、`agent.yaml`、SSH キーをマウント（`docker-compose.yml` 参照）。

### PostgreSQL（本番）

本番では SQLite ファイルの代わりに PostgreSQL を使用:

```bash
# .env
SKOPOS_POSTGRES_USER=skopos
SKOPOS_POSTGRES_PASSWORD=change-me
SKOPOS_DATABASE_URL=postgresql://skopos:change-me@postgres:5432/skopos

docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

優先順位: 環境変数 **`SKOPOS_DATABASE_URL`** → `servers.yaml` の `database_url` → `db_path`（SQLite 開発）。

## 本番チェックリスト

1. **`SKOPOS_DASHBOARD_PASSWORD`** を設定
2. マルチユーザー/永続本番ストレージに **PostgreSQL**（`SKOPOS_DATABASE_URL`）
3. **`SKOPOS_SSH_STRICT_HOST_KEYS=1`** を有効化
4. ポート **8501** を VPN または TLS 付きリバースプロキシに制限
5. cron または systemd timer で **`skoposctl.py collect`** をスケジュール
6. **設定** で自動スキャンを有効化（デフォルト: 60 分ごと）

## アーキテクチャ（概要）

```mermaid
flowchart LR
  nginx[nginx access.log] -->|SSH tail| collector[skopos collector]
  collector --> db[(SQLite or PostgreSQL)]
  db --> ui[Streamlit UI]
  ui --> agent[AI agent]
  collector --> security[Security probes]
  security --> db
```

![空のヘッダー領域が SKOPOS のトップナビゲーションになる](screenshots/topbar-area.png)
