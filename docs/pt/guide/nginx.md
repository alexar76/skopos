# Logs de acesso HTTP — escopo e limitações

> **Principal:** as análises SKOPOS são feitas para **logs de acesso nginx**. O formato **Apache combined** também é suportado quando habilitado explicitamente (`apache.enabled: true`).

## Suportado

| Fonte | Como |
|------|--------|
| Arquivos de access log nginx no host | `ssh_nginx_access_log` ou `ssh_http_access_log` + `nginx.access_log_path` |
| Arquivos de access log Apache (combined) | `ssh_http_access_log` + `apache.enabled: true` |
| Logs nginx adicionais | `access_log_paths` ou `auto_discover_logs` |
| Logs Apache adicionais | `apache.access_log_paths` ou `apache.auto_discover_logs` |
| stdout de container Docker (opcional) | Somente com `auto_discover_docker_logs: true`; o parser tenta **combined** primeiro, depois **uvicorn** |

## Não suportado como análise principal

- Caddy / Traefik como fontes de log independentes
- Logs de CDN na nuvem (Cloudflare, Fastly) sem linhas no formato combined
- Logs de aplicação que não sejam linhas de acesso HTTP

Se você termina TLS no nginx e faz proxy para Node/Python, **mantenha o access logging do nginx ativo** — ele continua sendo o registro canônico de tráfego em produção.

## Apache (teste / secundário)

O Apache deve usar formato de log **combined** (mesmos campos do combined do nginx). Exemplo:

```apache
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
CustomLog /var/log/apache2/access.log combined
```

No metis, um container httpd de teste pode rodar na **porta 8088** junto ao nginx em 80/443 — veja `metis/deploy/apache-test/`.

### Teste de fumaça do painel admin

1. Implante: `./metis/deploy/apache-test/deploy.sh` no host metis.
2. Gere tráfego:
   ```bash
curl -sS http://127.0.0.1:8088/
curl -sS http://127.0.0.1:8088/admin/
curl -sS "http://127.0.0.1:8088/admin/?page=settings"
tail -n 5 /opt/metis/deploy/apache-test/logs/access_log
```
3. Em `servers.yaml`: `source: ssh_http_access_log`, `apache.enabled: true`, caminho para `access_log`.
4. No SKOPOS **Análises**, filtre caminhos com `/admin` — linhas devem aparecer após collect.

As rotas admin do Apache são um **fixture de teste** para validação de parser/filtro; frotas de produção ainda devem tratar logs nginx como canônicos.

## `log_format` nginx recomendado

Inclua ao menos: `$remote_addr`, `$time_local`, `$request`, `$status`, `$body_bytes_sent`, `$http_referer`, `$http_user_agent`. Para análise por vhost adicione **`$host`**:

```nginx
log_format skopos '$remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent '
                  '"$http_referer" "$http_user_agent" "$host"';
access_log /var/log/nginx/access.log skopos;
```

## Por que nginx primeiro?

- Formato combined previsível em toda a frota
- SSH tail de `/var/log/nginx/` sem instalar agente em cada máquina
- Apache é opcional para stacks mistos ou nós de teste
- O módulo de segurança ainda sonda métricas do SO independentemente da stack web
