# HTTP アクセスログ — スコープと制限

> **主要:** SKOPOS 分析は **nginx アクセスログ** 向けに構築。**Apache combined** 形式も明示的に有効化時（`apache.enabled: true`）サポート。

## サポート対象

| ソース | 方法 |
|------|--------|
| ホスト上の nginx アクセスログファイル | `ssh_nginx_access_log` または `ssh_http_access_log` + `nginx.access_log_path` |
| Apache アクセスログファイル（combined） | `ssh_http_access_log` + `apache.enabled: true` |
| 追加 nginx ログ | `access_log_paths` または `auto_discover_logs` |
| 追加 Apache ログ | `apache.access_log_paths` または `apache.auto_discover_logs` |
| Docker コンテナ stdout（任意） | `auto_discover_docker_logs: true` のみ；パーサーは **combined** を先に、次に **uvicorn** |

## 主要分析ソースとして非サポート

- Caddy / Traefik を独立ログソースとして
- combined 形式でない CDN ログ（Cloudflare、Fastly）
- HTTP アクセス行でないアプリケーションログ

nginx で TLS 終端し Node/Python にプロキシする場合、**nginx アクセスログを有効のまま** — 本番フリートの正規トラフィック記録です。

## Apache（テスト / 副次）

Apache は **combined** ログ形式（nginx combined と同フィールド）必須。例:

```apache
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
CustomLog /var/log/apache2/access.log combined
```

metis ではテスト httpd コンテナを nginx 80/443 と並行 **8088** で実行可能 — `metis/deploy/apache-test/` 参照。

### 管理パネルスモークテスト

1. デプロイ: metis ホストで `./metis/deploy/apache-test/deploy.sh`。
2. トラフィック生成:
   ```bash
curl -sS http://127.0.0.1:8088/
curl -sS http://127.0.0.1:8088/admin/
curl -sS "http://127.0.0.1:8088/admin/?page=settings"
tail -n 5 /opt/metis/deploy/apache-test/logs/access_log
```
3. `servers.yaml` で: `source: ssh_http_access_log`、`apache.enabled: true`、`access_log` パス。
4. SKOPOS **分析** で `/admin` を含むパスをフィルター — collect 後に行が表示されるはず。

Apache 管理ルートはパーサー/フィルター検証用 **テストフィクスチャ**；本番は nginx アクセスログを正とする。

## 推奨 nginx `log_format`

最低限: `$remote_addr`、`$time_local`、`$request`、`$status`、`$body_bytes_sent`、`$http_referer`、`$http_user_agent`。vhost 分析には **`$host`** を追加:

```nginx
log_format skopos '$remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent '
                  '"$http_referer" "$http_user_agent" "$host"';
access_log /var/log/nginx/access.log skopos;
```

## なぜ nginx ファースト？

- フリート全体で予測可能な combined ログ形式
- 各ボックスにエージェント不要で `/var/log/nginx/` を SSH tail
- Apache は混合スタックやテストノード向けオプション
- セキュリティモジュールは Web スタックと独立して OS メトリクスをプローブ
