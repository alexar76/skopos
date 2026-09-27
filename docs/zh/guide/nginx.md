# HTTP 访问日志 — 范围与限制

> **主要来源：** SKOPOS 分析面向 **nginx 访问日志** 构建。**Apache combined** 格式在显式启用时（`apache.enabled: true`）也受支持。

## 支持

| 来源 | 方式 |
|------|--------|
| 主机上的 nginx 访问日志文件 | `ssh_nginx_access_log` 或 `ssh_http_access_log` + `nginx.access_log_path` |
| Apache 访问日志文件（combined） | `ssh_http_access_log` + `apache.enabled: true` |
| 额外 nginx 日志 | `access_log_paths` 或 `auto_discover_logs` |
| 额外 Apache 日志 | `apache.access_log_paths` 或 `apache.auto_discover_logs` |
| Docker 容器 stdout（可选） | 仅当 `auto_discover_docker_logs: true`；解析器先尝试 **combined**，再尝试 **uvicorn** |

## 不作为主要分析来源

- Caddy / Traefik 作为独立日志来源
- 非 combined 格式的 CDN 日志（Cloudflare、Fastly）
- 非 HTTP 访问行的应用日志

若在 nginx 上终止 TLS 并代理到 Node/Python，**请保持 nginx 访问日志启用** — 这仍是生产集群的权威流量记录。

## Apache（测试 / 次要）

Apache 必须使用 **combined** 日志格式（与 nginx combined 字段相同）。示例：

```apache
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
CustomLog /var/log/apache2/access.log combined
```

在 metis 上，测试 httpd 容器可在 **8088** 端口与 nginx 80/443 并行运行 — 参见 `metis/deploy/apache-test/`。

### 管理面板冒烟测试

1. 部署：在 metis 主机上运行 `./metis/deploy/apache-test/deploy.sh`。
2. 生成流量：
   ```bash
curl -sS http://127.0.0.1:8088/
curl -sS http://127.0.0.1:8088/admin/
curl -sS "http://127.0.0.1:8088/admin/?page=settings"
tail -n 5 /opt/metis/deploy/apache-test/logs/access_log
```
3. 在 `servers.yaml` 中：`source: ssh_http_access_log`，`apache.enabled: true`，`access_log` 路径。
4. 在 SKOPOS **分析** 中，过滤包含 `/admin` 的路径 — collect 后应出现日志行。

Apache 管理路由是用于解析器/过滤器验证的 **测试装置**；生产集群仍应以 nginx 访问日志为权威来源。

## 推荐的 nginx `log_format`

至少包含：`$remote_addr`、`$time_local`、`$request`、`$status`、`$body_bytes_sent`、`$http_referer`、`$http_user_agent`。按虚拟主机分析请添加 **`$host`**：

```nginx
log_format skopos '$remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent '
                  '"$http_referer" "$http_user_agent" "$host"';
access_log /var/log/nginx/access.log skopos;
```

## 为何以 nginx 为先？

- 跨集群可预测的 combined 日志格式
- 无需在每个节点安装代理即可 SSH 跟踪 `/var/log/nginx/`
- Apache 对混合栈或测试节点为可选项
- 安全模块独立于 Web 栈探测 OS 指标
