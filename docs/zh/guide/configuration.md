# 配置

## `servers.yaml`

每个服务器条目描述 SSH 访问和 **nginx 日志路径**：

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

| 字段 | 用途 |
|------|--------|
| `name` | 仪表板和过滤器中的标签 |
| `source` | `ssh_nginx_access_log`（仅 nginx）或 `ssh_http_access_log`（nginx + 可选 Apache） |
| `nginx.access_log_path` | 主访问日志文件 |
| `nginx.access_log_paths` | 额外日志文件（多站点） |
| `nginx.auto_discover_logs` | 解析主机上的 nginx 配置以发现更多路径 |
| `nginx.auto_discover_docker_logs` | 可选：同时跟踪公开 Docker HTTP 容器 |

### 权限

SSH 用户必须能够 **读取 nginx 日志文件**（在 Debian/Ubuntu 上通常需加入 `adm` 组）。

## `agent.yaml`

安全报告和浮动代理的 LLM 提供商。默认通过 `OPENROUTER_API_KEY` 使用 **OpenRouter**。

## 环境变量

| 字段 | 用途 |
|------|--------|
| `SKOPOS_DASHBOARD_PASSWORD` | 共享仪表板密码（登录表单）；在 **设置** 或 `.env` 中设置 |
| `SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH` | 新密码最小长度（默认 **12**） |
| `SKOPOS_DASHBOARD_SESSION_HOURS` | N 小时后自动登出（默认 **12**） |
| `OPENROUTER_API_KEY` | 默认 LLM 提供商 |
| `SKOPOS_SSH_KEY_PASSPHRASE` | 加密 SSH 密钥的口令 |
| `SKOPOS_SSH_STRICT_HOST_KEYS` | `1` 表示验证主机密钥 |

## 在界面中修改设置的位置

| 字段 | 用途 |
|------|--------|
| 语言与主题 | 侧边栏底部 |
| 收集 / 回填 | **分析** 页面的侧边栏 |
| 自动扫描间隔 | **设置** |
| Telegram 告警 | **设置** |
| 安全代理提供商 | **安全** → AI Agent 标签页 |

## Settings sections (detail)

| 字段 | 用途 |
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

![设置与侧边栏控件](screenshots/settings-fleet.png)

![Sidebar](screenshots/sidebar-nav.png)
