# Yapılandırma

## `servers.yaml`

Her sunucu girişi SSH erişimi ve **nginx günlük yollarını** tanımlar:

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

| Alan | Amaç |
|------|--------|
| `name` | Panolarda ve filtrelerde etiket |
| `source` | `ssh_nginx_access_log` (yalnızca nginx) veya `ssh_http_access_log` (nginx + isteğe bağlı Apache) |
| `nginx.access_log_path` | Birincil erişim günlüğü dosyası |
| `nginx.access_log_paths` | Ek günlük dosyaları (çoklu site) |
| `nginx.auto_discover_logs` | Daha fazla yol için ana bilgisayardaki nginx yapılandırmalarını ayrıştır |
| `nginx.auto_discover_docker_logs` | İsteğe bağlı: genel Docker HTTP konteynerlerini de izle |

### İzinler

SSH kullanıcısı **nginx günlük dosyalarını okuyabilmeli** (Debian/Ubuntu'da genelde `adm` grubu).

## `agent.yaml`

Security Report ve yüzen aracı için LLM sağlayıcıları. Varsayılan: `OPENROUTER_API_KEY` ile **OpenRouter**.

## Ortam değişkenleri

| Alan | Amaç |
|------|--------|
| `SKOPOS_DASHBOARD_PASSWORD` | Paylaşılan pano parolası (giriş formu); **Ayarlar** veya `.env` |
| `SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH` | Yeni parolalar için minimum uzunluk (varsayılan **12**) |
| `SKOPOS_DASHBOARD_SESSION_HOURS` | N saat sonra otomatik çıkış (varsayılan **12**) |
| `OPENROUTER_API_KEY` | Varsayılan LLM sağlayıcısı |
| `SKOPOS_SSH_KEY_PASSPHRASE` | Şifreli SSH anahtarları için passphrase |
| `SKOPOS_SSH_STRICT_HOST_KEYS` | Host key doğrulama için `1` |

## Arayüzde nerede değiştirilir

| Alan | Amaç |
|------|--------|
| Dil ve tema | Kenar çubuğu altı |
| Toplama / backfill | **Analitik** kenar çubuğu |
| Otomatik tarama aralığı | **Ayarlar** |
| Telegram uyarıları | **Ayarlar** |
| Güvenlik aracısı sağlayıcısı | **Güvenlik** → AI Agent sekmesi |

## Settings sections (detail)

| Alan | Amaç |
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

![Ayarlar ve kenar çubuğu denetimleri](../../screenshots/settings-fleet.png)

![Sidebar](../../screenshots/sidebar-nav.png)
