# HTTP 액세스 로그 — 범위 및 제한

> **주요:** SKOPOS 분석은 **nginx 액세스 로그**용입니다. **Apache combined** 형식도 명시적 활성화(`apache.enabled: true`) 시 지원.

## 지원

| 소스 | 방법 |
|------|--------|
| 호스트의 nginx 액세스 로그 파일 | `ssh_nginx_access_log` 또는 `ssh_http_access_log` + `nginx.access_log_path` |
| Apache 액세스 로그 파일 (combined) | `ssh_http_access_log` + `apache.enabled: true` |
| 추가 nginx 로그 | `access_log_paths` 또는 `auto_discover_logs` |
| 추가 Apache 로그 | `apache.access_log_paths` 또는 `apache.auto_discover_logs` |
| Docker 컨테이너 stdout (선택) | `auto_discover_docker_logs: true`일 때만; 파서는 **combined** 후 **uvicorn** 시도 |

## 주요 분석 소스로 미지원

- Caddy / Traefik 독립 로그 소스
- combined 형식이 아닌 CDN 로그 (Cloudflare, Fastly)
- HTTP 액세스 줄이 아닌 애플리케이션 로그

nginx에서 TLS 종료 후 Node/Python 프록시 시 **nginx 액세스 로깅 유지** — 프로덕션 플릿의 정식 트래픽 기록.

## Apache (테스트 / 보조)

Apache는 **combined** 로그 형식(nginx combined와 동일 필드) 필요. 예:

```apache
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
CustomLog /var/log/apache2/access.log combined
```

metis에서 테스트 httpd 컨테이너를 nginx 80/443과 병행 **8088**에서 실행 — `metis/deploy/apache-test/` 참조.

### 관리 패널 스모크 테스트

1. 배포: metis 호스트에서 `./metis/deploy/apache-test/deploy.sh`.
2. 트래픽 생성:
   ```bash
curl -sS http://127.0.0.1:8088/
curl -sS http://127.0.0.1:8088/admin/
curl -sS "http://127.0.0.1:8088/admin/?page=settings"
tail -n 5 /opt/metis/deploy/apache-test/logs/access_log
```
3. `servers.yaml`에서: `source: ssh_http_access_log`, `apache.enabled: true`, `access_log` 경로.
4. SKOPOS **분석**에서 `/admin` 포함 경로 필터 — collect 후 줄 표시.

Apache admin 경로는 파서/필터 검증용 **테스트 fixture**; 프로덕션은 nginx 액세스 로그가 정식.

## 권장 nginx `log_format`

최소 포함: `$remote_addr`, `$time_local`, `$request`, `$status`, `$body_bytes_sent`, `$http_referer`, `$http_user_agent`. vhost 분석에 **`$host`** 추가:

```nginx
log_format skopos '$remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent '
                  '"$http_referer" "$http_user_agent" "$host"';
access_log /var/log/nginx/access.log skopos;
```

## 왜 nginx 우선?

- 플릿 전반 예측 가능한 combined 로그 형식
- 각 박스에 에이전트 없이 `/var/log/nginx/` SSH tail
- Apache는 혼합 스택 또는 테스트 노드용 선택
- 보안 모듈은 웹 스택과 독립적으로 OS 메트릭 프로브
