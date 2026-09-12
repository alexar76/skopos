# SKOPOS — satellite d’observabilité de flotte de l’écosystème AICOM

> 🌐 [English](../README.md) · [Русский](README.ru.md) · [Español](README.es.md) · **Français** · [中文](README.zh.md) · [Glossaire](https://github.com/alexar76/aicom/blob/main/docs/localization-glossary.md)


> **Analytique nginx/Apache auto-hébergée et sécurité IA pour votre flotte de serveurs** — tableaux de bord HTTP type GA, Security Center avec carte 3D des menaces, Prometheus Observability (KPI APM + graphe 3D de services), historique des scans et agent IA avec entrée vocale. Pas de trackers tiers ; les données restent sur votre infrastructure.

<p align="center">
  <strong><a href="https://skopos.modelmarket.dev">Démo live</a></strong>
  ·
  <strong><a href="https://alexar76.github.io/skopos/">Landing</a></strong>
  ·
  neuf thèmes intégrés
</p>

En grec, **skopos** (σκοπός) signifie *veilleur* ou *éclaireur*. **SKOPOS** est le satellite d’observabilité de flotte de l’[écosystème AICOM / AIMarket](https://magic-ai-factory.com) : trafic nginx via SSH, posture de sécurité sur les hôtes factory / metis / oracle, et analyste LLM dans la barre latérale.

| | |
|---|---|
| **Rôle** | Collecte de logs SSH → analytique SQLite/PostgreSQL → Security Center + agent IA |
| **Démo live** | [skopos.modelmarket.dev](https://skopos.modelmarket.dev) |
| **Landing** | [alexar76.github.io/skopos](https://alexar76.github.io/skopos/) |
| **Surveille** | logs d’accès **nginx** (principal), **Apache** combined, CPU/RAM/disque, ports, fail2ban |
| **Charte** | Sondes SSH en lecture seule · données auto-hébergées · mot de passe optionnel du tableau de bord |

### Fonctionnalités

- **Analytics** — logs nginx via SSH, SQLite, graphiques Streamlit, globe de trafic
- **Security** — CPU/RAM/disque/réseau, audit de ports, pare-feu, carte 3D des menaces, **Security Report**
- **Scan History** — timeline de score, tendances des findings, comparaison de snapshots
- **Auto-scan** — scans de sécurité en arrière-plan (défaut : toutes les 60 min)
- **AI Agent** — OpenRouter (défaut), DeepSeek, OpenAI, Anthropic, Ollama, LM Studio ; chat latéral avec voix
- **i18n** — English (défaut), Russian, Spanish (`locales/`)

### Démarrage rapide

Voir [docs/quickstart.md](quickstart.md).

```bash
cp servers.example.yaml servers.yaml
cp agent.example.yaml agent.yaml
export OPENROUTER_API_KEY=sk-or-...
python skoposctl.py collect
python skoposctl.py security-scan
streamlit run dashboard.py
```

### Sécurité

- **Security Score** (0–100, note A–F) dans la barre latérale
- Bannière **Threat alerts** en cas de critical/high
- **Mot de passe du tableau de bord** — seul un **hash** PBKDF2 salé est stocké (`SKOPOS_DASHBOARD_PASSWORD` pour le bootstrap)
- **SKOPOS_SSH_STRICT_HOST_KEYS=1** — vérifier les host keys SSH
- Voir [docs/audit-findings.md](audit-findings.md)

### Documentation

| Doc | Description |
|-----|-------------|
| [Quick Start](quickstart.md) | Setup en 5 minutes |
| [User Guide](user-guide.md) | Référence UI |
| [Use Cases](use-cases.md) | Workflows courants |
| [Security Module](security.md) | Architecture |
| [nginx scope](en/guide/nginx.md) | Analytique **nginx** par défaut |
| [CHANGELOG](../CHANGELOG.md) | Notes de version |

> **Périmètre analytique :** les tableaux de trafic parsont les **nginx access logs** par défaut. **Apache combined** si `apache.enabled: true`. Les sondes de sécurité sont indépendantes de la stack.

### Agent IA

Fournisseur par défaut : **OpenRouter** via `OPENROUTER_API_KEY`. Éditez `agent.yaml` pour DeepSeek, OpenAI, Anthropic, Ollama ou LM Studio.

### Docker

```bash
docker compose up -d --build
```

Ouvrez `http://localhost:8501`

### Licence

MIT — voir [LICENSE](../LICENSE).

### Tests et couverture

```bash
pip install -r requirements.txt pytest pytest-cov
bash scripts/ci_coverage_badge.sh -- tests/ -q --cov=skopos
```

**227** cas pytest · couverture dans [`docs/badges/coverage.svg`](badges/coverage.svg).
