# 배포

## 요구 사항

- Python **3.9+** (또는 Docker)
- 모니터링 호스트마다 SSH 키 접근
- **nginx**가 combined 또는 사용자 정의 형식으로 액세스 로그 기록
- 클라우드 LLM(OpenRouter, OpenAI 등) 사용 시 아웃바운드 HTTPS

## 베어메탈 / VM

```bash
cd skopos
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp servers.example.yaml servers.yaml
cp agent.example.yaml agent.yaml
export SKOPOS_DASHBOARD_PASSWORD='strong-secret'
python skoposctl.py collect
python skoposctl.py security-scan
streamlit run dashboard.py
```

`http://localhost:8501`을 여세요.

## Docker Compose

```bash
docker compose up -d --build
```

compose 볼륨으로 `servers.yaml`, `agent.yaml`, SSH 키 마운트 (`docker-compose.yml` 참조).

### PostgreSQL (프로덕션)

프로덕션에서는 SQLite 파일 대신 PostgreSQL 사용:

```bash
# .env
SKOPOS_POSTGRES_USER=skopos
SKOPOS_POSTGRES_PASSWORD=change-me
SKOPOS_DATABASE_URL=postgresql://skopos:change-me@postgres:5432/skopos

docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

우선순위: env **`SKOPOS_DATABASE_URL`** → `servers.yaml`의 `database_url` → `db_path` (SQLite dev).

## 프로덕션 체크리스트

1. **`SKOPOS_DASHBOARD_PASSWORD`** 설정
2. 다중 사용자/영구 prod 저장소에 **PostgreSQL** (`SKOPOS_DATABASE_URL`)
3. **`SKOPOS_SSH_STRICT_HOST_KEYS=1`** 활성화
4. 포트 **8501**을 VPN 또는 TLS 리버스 프록시로 제한
5. cron 또는 systemd timer로 **`skoposctl.py collect`** 예약
6. **설정**에서 자동 스캔 활성화 (기본: 60분마다)

## 아키텍처 (개요)

```mermaid
flowchart LR
  nginx[nginx access.log] -->|SSH tail| collector[skopos collector]
  collector --> db[(SQLite or PostgreSQL)]
  db --> ui[Streamlit UI]
  ui --> agent[AI agent]
  collector --> security[Security probes]
  security --> db
```

![빈 헤더 영역이 SKOPOS에서 상단 탐색이 됨](../../screenshots/topbar-area.png)
