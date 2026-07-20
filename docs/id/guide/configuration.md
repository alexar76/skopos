# Konfigurasi

## `servers.yaml`

Setiap entri server menjelaskan akses SSH dan **path log nginx**:

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

| Field | Tujuan |
|------|--------|
| `name` | Label di dasbor dan filter |
| `source` | `ssh_nginx_access_log` (hanya nginx) atau `ssh_http_access_log` (nginx + Apache opsional) |
| `nginx.access_log_path` | File access log utama |
| `nginx.access_log_paths` | File log tambahan (multi-site) |
| `nginx.auto_discover_logs` | Parse config nginx di host untuk path lain |
| `nginx.auto_discover_docker_logs` | Opsional: juga tail container Docker HTTP publik |

### Izin

Pengguna SSH harus bisa **membaca file log nginx** (sering grup `adm` di Debian/Ubuntu).

## `agent.yaml`

Penyedia LLM untuk Security Report dan agen mengambang. Default: **OpenRouter** via `OPENROUTER_API_KEY`.

## Variabel lingkungan

| Field | Tujuan |
|------|--------|
| `SKOPOS_DASHBOARD_PASSWORD` | Password dasbor bersama (form login); di **Pengaturan** atau `.env` |
| `SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH` | Panjang minimum password baru (default **12**) |
| `SKOPOS_DASHBOARD_SESSION_HOURS` | Logout otomatis setelah N jam (default **12**) |
| `OPENROUTER_API_KEY` | Penyedia LLM default |
| `SKOPOS_SSH_KEY_PASSPHRASE` | Passphrase untuk kunci SSH terenkripsi |
| `SKOPOS_SSH_STRICT_HOST_KEYS` | `1` untuk verifikasi host key |

## Di mana mengubah di UI

| Field | Tujuan |
|------|--------|
| Bahasa & tema | Bawah sidebar |
| Koleksi / backfill | Sidebar di **Analitik** |
| Interval auto-scan | **Pengaturan** |
| Alert Telegram | **Pengaturan** |
| Penyedia agen keamanan | **Keamanan** → tab AI Agent |

## Settings sections (detail)

| Field | Tujuan |
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

![Pengaturan dan kontrol sidebar](screenshots/settings-fleet.png)

![Sidebar](screenshots/sidebar-nav.png)
