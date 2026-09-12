# Logs HTTP — alcance y límites

> **Principal:** analítica SKOPOS para **logs nginx**. **Apache combined** con `apache.enabled: true`.

## Soportado

| Fuente | Cómo |
|------|--------|
| Archivos access.log nginx en el host | `ssh_nginx_access_log` o `ssh_http_access_log` |
| Logs Apache (combined) | `ssh_http_access_log` + `apache.enabled: true` |
| Logs nginx adicionales | `access_log_paths`, `auto_discover_logs` |
| Logs Apache adicionales | `apache.access_log_paths`, `apache.auto_discover_logs` |
| stdout Docker (opcional) | `auto_discover_docker_logs: true` |

## No soportado como fuente principal

- Caddy / Traefik como fuentes independientes
- Logs CDN sin formato combined
- Logs de aplicación sin líneas HTTP access

Si termina TLS en nginx y hace proxy a Node/Python, **mantenga access logging en nginx**.

## Apache (prueba / secundario)

Apache debe usar formato **combined**. Ejemplo:

```apache
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
CustomLog /var/log/apache2/access.log combined
```

En metis, httpd de prueba en **8088** junto a nginx — ver `metis/deploy/apache-test/`.

### Prueba del panel admin

1. Despliegue: `./metis/deploy/apache-test/deploy.sh` en metis.
2. Generar tráfico:
   ```bash
curl -sS http://127.0.0.1:8088/
curl -sS http://127.0.0.1:8088/admin/
curl -sS "http://127.0.0.1:8088/admin/?page=settings"
tail -n 5 /opt/metis/deploy/apache-test/logs/access_log
```
3. En `servers.yaml`: `source: ssh_http_access_log`, `apache.enabled: true`, ruta a `access_log`.
4. En SKOPOS **Analítica**, filtrar `/admin` — líneas tras collect.

Rutas admin Apache son **fixture de prueba**; en prod use logs nginx.

## `log_format` nginx recomendado

Incluya `$remote_addr`, `$time_local`, `$request`, `$status`, `$body_bytes_sent`, referer, user-agent. Para vhost añada **`$host`**:

```nginx
log_format skopos '$remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent '
                  '"$http_referer" "$http_user_agent" "$host"';
access_log /var/log/nginx/access.log skopos;
```

## ¿Por qué nginx primero?

- Formato combined predecible
- SSH tail sin agente en cada caja
- Apache opcional en stacks mixtos
- Módulo Security independiente del web stack
