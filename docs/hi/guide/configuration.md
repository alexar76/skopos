# कॉन्फ़िगरेशन

## `servers.yaml`

प्रत्येक सर्वर प्रविष्टि SSH पहुँच और **nginx लॉग पथ** वर्णन करती है:

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

| फ़ील्ड | उद्देश्य |
|------|--------|
| `name` | डैशबोर्ड और फ़िल्टर में लेबल |
| `source` | `ssh_nginx_access_log` (केवल nginx) या `ssh_http_access_log` (nginx + वैकल्पिक Apache) |
| `nginx.access_log_path` | प्राथमिक एक्सेस लॉग फ़ाइल |
| `nginx.access_log_paths` | अतिरिक्त लॉग फ़ाइलें (मल्टी-साइट) |
| `nginx.auto_discover_logs` | अधिक पथों के लिए होस्ट पर nginx कॉन्फ़िग पार्स करें |
| `nginx.auto_discover_docker_logs` | वैकल्पिक: सार्वजनिक Docker HTTP कंटेनर भी टेल करें |

### अनुमतियाँ

SSH उपयोगकर्ता **nginx लॉग फ़ाइलें पढ़** सके (Debian/Ubuntu पर अक्सर `adm` समूह की सदस्यता)।

## `agent.yaml`

Security Report और फ़्लोटिंग एजेंट के लिए LLM प्रदाता। डिफ़ॉल्ट: `OPENROUTER_API_KEY` के माध्यम से **OpenRouter**।

## पर्यावरण चर

| फ़ील्ड | उद्देश्य |
|------|--------|
| `SKOPOS_DASHBOARD_PASSWORD` | साझा डैशबोर्ड पासवर्ड (लॉगिन फ़ॉर्म); **सेटिंग्स** या `.env` में सेट करें |
| `SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH` | नए पासवर्ड की न्यूनतम लंबाई (डिफ़ॉल्ट **12**) |
| `SKOPOS_DASHBOARD_SESSION_HOURS` | N घंटे बाद स्वतः साइन-आउट (डिफ़ॉल्ट **12**) |
| `OPENROUTER_API_KEY` | डिफ़ॉल्ट LLM प्रदाता |
| `SKOPOS_SSH_KEY_PASSPHRASE` | एन्क्रिप्टेड SSH कुंजियों के लिए passphrase |
| `SKOPOS_SSH_STRICT_HOST_KEYS` | होस्ट कुंजियाँ सत्यापित करने के लिए `1` |

## UI में बदलाव कहाँ करें

| फ़ील्ड | उद्देश्य |
|------|--------|
| भाषा और थीम | साइडबार नीचे |
| संग्रह / बैकफ़िल | **एनालिटिक्स** पर साइडबार |
| ऑटो-स्कैन अंतराल | **सेटिंग्स** |
| Telegram अलर्ट | **सेटिंग्स** |
| सुरक्षा एजेंट प्रदाता | **सुरक्षा** → AI Agent टैब |

## Settings sections (detail)

| फ़ील्ड | उद्देश्य |
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

![सेटिंग्स और साइडबार नियंत्रण](screenshots/settings-fleet.png)

![Sidebar](screenshots/sidebar-nav.png)
