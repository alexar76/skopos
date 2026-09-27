# 구성

## `servers.yaml`

각 서버 항목은 SSH 접근 및 **nginx 로그 경로**를 설명:

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

| 필드 | 용도 |
|------|--------|
| `name` | 대시보드 및 필터의 레이블 |
| `source` | `ssh_nginx_access_log` (nginx만) 또는 `ssh_http_access_log` (nginx + 선택 Apache) |
| `nginx.access_log_path` | 기본 액세스 로그 파일 |
| `nginx.access_log_paths` | 추가 로그 파일 (다중 사이트) |
| `nginx.auto_discover_logs` | 호스트 nginx 설정 파싱으로 경로 추가 발견 |
| `nginx.auto_discover_docker_logs` | 선택: 공개 Docker HTTP 컨테이너도 tail |

### 권한

SSH 사용자는 **nginx 로그 파일 읽기** 가능해야 함 (Debian/Ubuntu에서 종종 `adm` 그룹).

## `agent.yaml`

Security Report 및 플로팅 에이전트용 LLM 제공자. 기본: `OPENROUTER_API_KEY`를 통한 **OpenRouter**.

## 환경 변수

| 필드 | 용도 |
|------|--------|
| `SKOPOS_DASHBOARD_PASSWORD` | 공유 대시보드 비밀번호 (로그인 폼); **설정** 또는 `.env` |
| `SKOPOS_DASHBOARD_PASSWORD_MIN_LENGTH` | 새 비밀번호 최소 길이 (기본 **12**) |
| `SKOPOS_DASHBOARD_SESSION_HOURS` | N시간 후 자동 로그아웃 (기본 **12**) |
| `OPENROUTER_API_KEY` | 기본 LLM 제공자 |
| `SKOPOS_SSH_KEY_PASSPHRASE` | 암호화 SSH 키 passphrase |
| `SKOPOS_SSH_STRICT_HOST_KEYS` | 호스트 키 검증은 `1` |

## UI에서 변경 위치

| 필드 | 용도 |
|------|--------|
| 언어 및 테마 | 사이드바 하단 |
| 수집 / backfill | **분석** 사이드바 |
| 자동 스캔 간격 | **설정** |
| Telegram 알림 | **설정** |
| 보안 에이전트 제공자 | **보안** → AI Agent 탭 |

## Settings sections (detail)

| 필드 | 용도 |
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

![설정 및 사이드바 컨트롤](../../screenshots/settings-fleet.png)

![Sidebar](../../screenshots/sidebar-nav.png)
