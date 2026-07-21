# Journaux d'accès HTTP — périmètre et limites

> **Principal :** l'analytique SKOPOS est conçue pour les **journaux d'accès nginx**. Le format **Apache combined** est aussi pris en charge si activé explicitement (`apache.enabled: true`).

## Pris en charge

| Source | Comment |
|------|--------|
| Fichiers access log nginx sur l'hôte | `ssh_nginx_access_log` ou `ssh_http_access_log` + `nginx.access_log_path` |
| Fichiers access log Apache (combined) | `ssh_http_access_log` + `apache.enabled: true` |
| Logs nginx supplémentaires | `access_log_paths` ou `auto_discover_logs` |
| Logs Apache supplémentaires | `apache.access_log_paths` ou `apache.auto_discover_logs` |
| stdout conteneur Docker (optionnel) | Uniquement si `auto_discover_docker_logs: true` ; le parseur essaie **combined** puis **uvicorn** |

## Non pris en charge comme analytique principale

- Caddy / Traefik comme sources de logs autonomes
- Logs CDN cloud (Cloudflare, Fastly) sans lignes au format combined
- Logs applicatifs qui ne sont pas des lignes d'accès HTTP

Si vous terminez TLS sur nginx et proxiez vers Node/Python, **gardez l'access logging nginx activé** — c'est le registre canonique du trafic en production.

## Apache (test / secondaire)

Apache doit utiliser le format **combined** (mêmes champs que nginx combined). Exemple :

```apache
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
CustomLog /var/log/apache2/access.log combined
```

Sur metis, un conteneur httpd de test peut tourner sur le **port 8088** aux côtés de nginx 80/443 — voir `metis/deploy/apache-test/`.

### Test de fumée du panneau admin

1. Déployer : `./metis/deploy/apache-test/deploy.sh` sur l'hôte metis.
2. Générer du trafic :
   ```bash
curl -sS http://127.0.0.1:8088/
curl -sS http://127.0.0.1:8088/admin/
curl -sS "http://127.0.0.1:8088/admin/?page=settings"
tail -n 5 /opt/metis/deploy/apache-test/logs/access_log
```
3. Dans `servers.yaml` : `source: ssh_http_access_log`, `apache.enabled: true`, chemin vers `access_log`.
4. Dans SKOPOS **Analytique**, filtrer les chemins contenant `/admin` — lignes visibles après collect.

Les routes admin Apache sont un **fixture de test** pour validation parseur/filtre ; en prod, les logs nginx restent canoniques.

## `log_format` nginx recommandé

Incluez au minimum : `$remote_addr`, `$time_local`, `$request`, `$status`, `$body_bytes_sent`, `$http_referer`, `$http_user_agent`. Pour l'analytique par vhost ajoutez **`$host`**:

```nginx
log_format skopos '$remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent '
                  '"$http_referer" "$http_user_agent" "$host"';
access_log /var/log/nginx/access.log skopos;
```

## Pourquoi nginx en premier ?

- Format combined prévisible sur toute la flotte
- SSH tail de `/var/log/nginx/` sans agent sur chaque machine
- Apache optionnel pour stacks mixtes ou nœuds de test
- Le module sécurité sonde les métriques OS indépendamment de la stack web
