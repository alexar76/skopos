# 設定

## `servers.yaml`

各サーバー項目は SSH アクセスと **nginx ログパス** を記述:

```yaml
servers:
  - name: factory
    source: ssh_nginx_access_log
    ssh:
      host: 203.0.113.10
      port: 22
      user: deploy
      key_path: ~/.ssh/id_rsa
    nginx:
      access_log_path: /var/log/nginx/access.log
      auto_discover_logs: true
      auto_discover_docker_logs: false
```

| フィールド | 目的 |
|------|--------|
| `name` | ダッシュボードとフィルターのラベル |
| `source` | `ssh_nginx_access_log`（nginx のみ）または `ssh_http_access_log`（nginx + 任意 Apache） |
| `nginx.access_log_path` | 主アクセスログファイル |
| `nginx.access_log_paths` | 追加ログファイル（マルチサイト） |
| `nginx.auto_discover_logs` | ホスト上の nginx 設定を解析してパスを追加発見 |
| `nginx.auto_discover_docker_logs` | 任意: 公開 Docker HTTP コンテナも tail |

### 権限

SSH ユーザーは **nginx ログファイルを読み取れる** 必要があります（Debian/Ubuntu では多くの場合 `adm` グループ）。

## `agent.yaml`

Security Report とフローティングエージェント用 LLM プロバイダー。デフォルト: `OPENROUTER_API_KEY` 経由の **OpenRouter**。

## 環境変数

| フィールド | 目的 |
|------|--------|
| `SKOPOS_DASHBOARD_PASSWORD` | 共有ダッシュボードパスワード（ログインフォーム）；**設定** または `.env` で設定 |
| `SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH` | 新パスワードの最小長（デフォルト **12**） |
| `SKOPOS_DASHBOARD_SESSION_HOURS` | N 時間後に自動サインアウト（デフォルト **12**） |
| `OPENROUTER_API_KEY` | デフォルト LLM プロバイダー |
| `SKOPOS_SSH_KEY_PASSPHRASE` | 暗号化 SSH キーのパスフレーズ |
| `SKOPOS_SSH_STRICT_HOST_KEYS` | ホスト鍵検証は `1` |

## UI で変更する場所

| フィールド | 目的 |
|------|--------|
| 言語とテーマ | サイドバー下部 |
| 収集 / backfill | **分析** のサイドバー |
| 自動スキャン間隔 | **設定** |
| Telegram アラート | **設定** |
| セキュリティエージェントプロバイダー | **セキュリティ** → AI Agent タブ |

## Settings sections (detail)

| フィールド | 目的 |
|------|--------|
| Dashboard access | `SKOPOS_DASHBOARD_PASSWORD`, session hours, min length policy |
| Database | `SKOPOS_DATABASE_URL` or SQLite `db_path`; test + migrate in UI |
| Auto-scan | Background security scan interval (minutes) |
| Telegram | `SKOPOS_TELEGRAM_*` env vars; notify on new critical findings |
| SSH keys | Generate Ed25519; keys stored under `.skopos/ssh/` |
| Fleet servers | Visual editor for `servers.yaml` — nginx, Apache, docker logs |

## `agent.yaml` providers

Each provider block needs an API key env var. Default stack uses **OpenRouter** (`OPENROUTER_API_KEY`). Providers appear in Summary Report, floating agent, and Security → AI Agent tab.

| Provider | API key |
|------|--------|
| `openrouter` | `OPENROUTER_API_KEY` — default; many models via one key |
| `openai` | `OPENAI_API_KEY` |
| `anthropic` | `ANTHROPIC_API_KEY` |
| `deepseek` | `DEEPSEEK_API_KEY` |

![設定とサイドバーコントロール](../../screenshots/settings-fleet.png)

![Sidebar](../../screenshots/sidebar-nav.png)
