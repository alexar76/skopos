# Configuration

## `servers.yaml`

Chaque entrée serveur décrit l'accès SSH et les **chemins de logs nginx** :

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

| Champ | Rôle |
|------|--------|
| `name` | Libellé dans tableaux et filtres |
| `source` | `ssh_nginx_access_log` (nginx seul) ou `ssh_http_access_log` (nginx + Apache optionnel) |
| `nginx.access_log_path` | Fichier access log principal |
| `nginx.access_log_paths` | Fichiers de logs supplémentaires (multi-site) |
| `nginx.auto_discover_logs` | Analyser les configs nginx sur l'hôte pour plus de chemins |
| `nginx.auto_discover_docker_logs` | Optionnel : suivre aussi les conteneurs Docker HTTP publics |

### Permissions

L'utilisateur SSH doit pouvoir **lire les fichiers de logs nginx** (souvent membre du groupe `adm` sur Debian/Ubuntu).

## `agent.yaml`

Fournisseurs LLM pour Security Report et agent flottant. Par défaut : **OpenRouter** via `OPENROUTER_API_KEY`.

## Variables d'environnement

| Champ | Rôle |
|------|--------|
| `SKOPOS_DASHBOARD_PASSWORD` | Mot de passe partagé du tableau (formulaire de connexion) ; dans **Paramètres** ou `.env` |
| `SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH` | Longueur minimale des nouveaux mots de passe (défaut **12**) |
| `SKOPOS_DASHBOARD_SESSION_HOURS` | Déconnexion auto après N heures (défaut **12**) |
| `OPENROUTER_API_KEY` | Fournisseur LLM par défaut |
| `SKOPOS_SSH_KEY_PASSPHRASE` | Passphrase pour clés SSH chiffrées |
| `SKOPOS_SSH_STRICT_HOST_KEYS` | `1` pour vérifier les host keys |

## Où modifier dans l'interface

| Champ | Rôle |
|------|--------|
| Langue et thème | Bas de la barre latérale |
| Collecte / backfill | Barre latérale sur **Analytique** |
| Intervalle d'analyse auto | **Paramètres** |
| Alertes Telegram | **Paramètres** |
| Fournisseur agent sécurité | **Sécurité** → onglet AI Agent |

## Settings sections (detail)

| Champ | Rôle |
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

![Paramètres et contrôles de la barre latérale](../../screenshots/settings-fleet.png)

![Sidebar](../../screenshots/sidebar-nav.png)
