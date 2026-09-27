# SKOPOS — AICOM 生态的机队可观测性卫星

> 🌐 [English](../README.md) · [Русский](README.ru.md) · [Español](README.es.md) · [Français](README.fr.md) · **中文** · [术语表](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md)


> **自托管的 nginx/Apache 分析与面向服务器机队的 AI 安全** — 类 GA 的 HTTP 仪表盘、带 3D 威胁地图的 Security Center、Prometheus Observability（APM KPI + 3D 服务图）、扫描历史，以及带语音输入的 AI 智能体。无第三方追踪器；数据留在你自己的基础设施上。

<p align="center">
  <strong><a href="https://skopos.modelmarket.dev">在线演示</a></strong>
  ·
  <strong><a href="https://alexar76.github.io/skopos/">落地页</a></strong>
  ·
  九套内置主题
</p>

希腊语 **skopos**（σκοπός）意为*守望者*或*侦察兵*。**SKOPOS** 是 [AICOM / AIMarket 生态](https://magic-ai-factory.com) 的机队可观测性卫星：经 SSH 的 nginx 流量、factory / metis / oracle 主机上的安全态势，以及侧栏中的 LLM 分析师。

| | |
|---|---|
| **角色** | SSH 日志采集 → SQLite/PostgreSQL 分析 → Security Center + AI 智能体 |
| **在线演示** | [skopos.modelmarket.dev](https://skopos.modelmarket.dev) |
| **落地页** | [alexar76.github.io/skopos](https://alexar76.github.io/skopos/) |
| **监控** | **nginx** access 日志（主）、**Apache** combined、CPU/RAM/磁盘、端口、fail2ban |
| **章程** | 只读 SSH 探测 · 自托管数据 · 可选仪表盘密码 |

### 功能

- **Analytics** — 经 SSH 的 nginx 日志、SQLite、Streamlit 图表、流量地球仪
- **Security** — CPU/RAM/磁盘/网络、端口审计、防火墙、赛博朋克 3D 威胁地图、汇总 **Security Report**
- **Scan History** — 分数时间线、finding 趋势、快照对比
- **Auto-scan** — 后台安全扫描（默认每 60 分钟）
- **AI Agent** — OpenRouter（默认）、DeepSeek、OpenAI、Anthropic、Ollama、LM Studio；侧栏聊天含语音
- **i18n** — English（默认）、Russian、Spanish（`locales/`）

### 快速开始

见 [docs/quickstart.md](quickstart.md)。

```bash
cp servers.example.yaml servers.yaml
cp agent.example.yaml agent.yaml
export OPENROUTER_API_KEY=sk-or-...
python skoposctl.py collect
python skoposctl.py security-scan
streamlit run dashboard.py
```

### 安全

- 每页侧栏 **Security Score**（0–100，等级 A–F）
- 存在 critical/high 时显示 **Threat alerts**
- **仪表盘密码** — 仅在库中存储加盐 PBKDF2 **哈希**（bootstrap 可用 `SKOPOS_DASHBOARD_PASSWORD`）
- **SKOPOS_SSH_STRICT_HOST_KEYS=1** — 校验 SSH host keys（推荐）
- 见 [docs/audit-findings.md](audit-findings.md)

### 文档

| 文档 | 说明 |
|-----|-------------|
| [Quick Start](quickstart.md) | 5 分钟安装 |
| [User Guide](user-guide.md) | 完整 UI |
| [Use Cases](use-cases.md) | 常见流程 |
| [Security Module](security.md) | 架构 |
| [nginx scope](en/guide/nginx.md) | 默认仅 **nginx** 流量分析 |
| [CHANGELOG](../CHANGELOG.md) | 发行说明 |

> **分析范围：** 流量仪表盘默认解析 **nginx access logs**。开启 `apache.enabled: true` 时可解析 **Apache combined**。安全探测与栈无关。

### AI 智能体

默认提供方：**OpenRouter**（`OPENROUTER_API_KEY`）。编辑 `agent.yaml` 以使用 DeepSeek、OpenAI、Anthropic、Ollama 或 LM Studio。

### Docker

```bash
docker compose up -d --build
```

打开 `http://localhost:8501`

### 许可

MIT — 见 [LICENSE](../LICENSE)。

### 测试与覆盖率

```bash
pip install -r requirements.txt pytest pytest-cov
bash scripts/ci_coverage_badge.sh -- tests/ -q --cov=skopos
```

**227** 个 pytest · 覆盖率见 [`docs/badges/coverage.svg`](badges/coverage.svg)。
