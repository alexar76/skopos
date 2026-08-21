# SKOPOS — satélite de observabilidad de flota del ecosistema AICOM

> 🌐 [English](../README.md) · [Русский](README.ru.md) · **Español** · [Français](README.fr.md) · [中文](README.zh.md) · [Glosario](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md)


> **Analítica nginx/Apache autoalojada y seguridad con IA para tu flota de servidores** — paneles HTTP tipo GA, Security Center con mapa 3D de amenazas, Prometheus Observability (KPI APM + grafo 3D de servicios), historial de escaneos y un agente de IA con entrada de voz. Sin trackers de terceros; los datos permanecen en tu infraestructura.

<p align="center">
  <strong><a href="https://skopos.modelmarket.dev">Demo en vivo</a></strong>
  ·
  <strong><a href="https://alexar76.github.io/skopos/">Landing</a></strong>
  ·
  nueve temas integrados
</p>

En griego, **skopos** (σκοπός) significa *vigilante* o *explorador*. **SKOPOS** es el satélite de observabilidad de flota del [ecosistema AICOM / AIMarket](https://magic-ai-factory.com): tráfico nginx por SSH, postura de seguridad en hosts factory / metis / oracle, y un analista LLM en la barra lateral.

| | |
|---|---|
| **Rol** | Recolección de logs por SSH → analítica SQLite/PostgreSQL → Security Center + agente IA |
| **Demo en vivo** | [skopos.modelmarket.dev](https://skopos.modelmarket.dev) |
| **Landing** | [alexar76.github.io/skopos](https://alexar76.github.io/skopos/) |
| **Supervisa** | logs de acceso **nginx** (principal), **Apache** combined, CPU/RAM/disco, puertos, fail2ban |
| **Carta** | Sondas SSH de solo lectura · datos autoalojados · contraseña opcional del panel |

### Funciones

- **Analytics** — logs nginx por SSH, SQLite, gráficos Streamlit, globo de tráfico
- **Security** — CPU/RAM/disco/red, auditoría de puertos, firewall / cortafuegos, mapa 3D de amenazas, **Security Report**
- **Scan History** — línea temporal de score, tendencias de findings, comparación de snapshots
- **Auto-scan** — escaneos de seguridad en segundo plano (por defecto cada 60 min)
- **AI Agent** — OpenRouter (por defecto), DeepSeek, OpenAI, Anthropic, Ollama, LM Studio; chat lateral con voz
- **i18n** — English (default), Russian, Spanish (`locales/`)

### Inicio rápido

Ver [docs/quickstart.md](quickstart.md).

```bash
cp servers.example.yaml servers.yaml
cp agent.example.yaml agent.yaml
export OPENROUTER_API_KEY=sk-or-...
python skoposctl.py collect
python skoposctl.py security-scan
streamlit run dashboard.py
```

### Seguridad

- **Security Score** (0–100, grado A–F) en la barra lateral
- Banner de **Threat alerts** ante critical/high
- **Contraseña del panel** — solo hash PBKDF2 con sal en la BD (`SKOPOS_DASHBOARD_PASSWORD` para bootstrap)
- **SKOPOS_SSH_STRICT_HOST_KEYS=1** — verificar host keys SSH
- Ver [docs/audit-findings.md](audit-findings.md)

### Documentación

| Doc | Descripción |
|-----|-------------|
| [Quick Start](quickstart.md) | Setup en 5 minutos |
| [User Guide](user-guide.md) | Referencia UI |
| [Use Cases](use-cases.md) | Flujos habituales |
| [Security Module](security.md) | Arquitectura |
| [nginx scope](en/guide/nginx.md) | Analítica **nginx** por defecto |
| [CHANGELOG](../CHANGELOG.md) | Notas de versión |

> **Alcance de analítica:** los paneles de tráfico parsean **nginx access logs** por defecto. **Apache combined** con `apache.enabled: true`. Las sondas de seguridad son agnósticas al stack.

### Agente IA

Proveedor por defecto: **OpenRouter** vía `OPENROUTER_API_KEY`. Edita `agent.yaml` para DeepSeek, OpenAI, Anthropic, Ollama o LM Studio.

### Docker

```bash
docker compose up -d --build
```

Abre `http://localhost:8501`

### Licencia

MIT — ver [LICENSE](../LICENSE).

### Pruebas y cobertura

```bash
pip install -r requirements.txt pytest pytest-cov
bash scripts/ci_coverage_badge.sh -- tests/ -q --cov=skopos
```

**227** casos pytest · cobertura en [`docs/badges/coverage.svg`](badges/coverage.svg).
