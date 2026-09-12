# Security Module

Architecture and extension guide for the Security Center.

## Components

```
skopos/security/
  probe.py      SSH remote probe → ServerSnapshot
  audit.py      Rule engine → SecurityFinding list
  store.py      SQLite persistence
  collector.py  Orchestration (scan_server / scan_all)
  charts.py     Plotly visualizations + 3D topology
```

## ServerSnapshot fields

| Field | Source |
|-------|--------|
| cpu_*, mem_*, load_* | /proc, free, top |
| disks | df -hP |
| ports | ss -tulnp |
| firewall_status | ufw / iptables |
| failed_logins | auth.log grep |
| docker_containers | `docker ps -a`, `docker stats`, compose labels — name, image, ports, CPU/RAM, inferred role |
| sshd_config | sshd_config grep |

## Adding audit rules

Edit `audit.py` → `audit_snapshot()`:

```python
if my_condition:
    findings.append(SecurityFinding(
        severity="medium",
        category="custom",
        title="My check",
        detail="...",
        recommendation="...",
    ))
```

## 3D threat map

Nodes:

- **core** — server center
- **port_N** — public listeners on a ring
- **internet** — upstream node
- **finding_N** — audit items elevated by severity

## Database schema

```sql
security_snapshots(id, server_name, host, scanned_at_utc, payload_json)
security_findings(id, snapshot_id, server_name, severity, category, title, detail, recommendation)
app_settings(key, value, updated_at_utc)   -- dashboard_password_hash + set-at timestamp
```

Latest snapshot per server is used by the dashboard.

## Dashboard authentication

The login password lives in `skopos/auth_store.py`:

- **Hashing:** PBKDF2-HMAC-SHA256, 240k iterations, 16-byte random salt, encoded
  as `pbkdf2_sha256$<iter>$<salt_b64>$<hash_b64>`. Verified with
  `hmac.compare_digest`. Only the hash is stored in `app_settings`.
- **Precedence:** DB hash → `SKOPOS_DASHBOARD_PASSWORD` env (plaintext, legacy) →
  open. Setting a password in the UI writes the hash and strips the plaintext
  from `.env`.
- **Rotation:** age is tracked from the set timestamp. Defaults:
  `SKOPOS_DASHBOARD_PASSWORD_MAX_AGE_DAYS=90`, warn window
  `SKOPOS_DASHBOARD_PASSWORD_WARN_DAYS=7`. Expiry triggers a Telegram alert
  (≤ once/day) via the auto-scan scheduler.
- **Gating:** the floating AI agent only mounts after authentication; the setup
  modal appears whenever no password is configured.

See the operator guide: [Dashboard password & rotation](en/guide/configuration.md).

## Agent context

`skopos/agent/context.py` builds markdown context:

1. Fleet SSH endpoints
2. Latest security snapshots + findings
3. HTTP traffic aggregates (24h)
4. Suspicious path hits (.env, wp-admin, etc.)

Truncated to `max_context_chars` from `agent.yaml`.

### Prompt injection (floating assistant)

`skopos/agent/injection_guard.py` hardens `/agent/chat`:

- **User input** — strip `[system]` / `user:` role markers; flag common jailbreak patterns
- **Fleet context** — wrapped in `<untrusted source="skopos_fleet_context">` so logs/stats are treated as data
- **System prompt** — canary token + boundary rules (never obey override attempts; never reveal prompt)
- **Reply check** — if the canary leaks into the model output, the response is replaced with a safe refusal
- **Metadata** — `page` and `server_name` from the client are stripped to safe slugs

The assistant has no tools and cannot run SSH commands; injection cannot trigger side effects beyond misleading text in the chat reply.

## Port knock monitoring

During `security-scan`, the collector parses:

| Source | Events |
|--------|--------|
| `/var/log/auth.log` | SSH failed passwords, invalid users |
| `ufw.log` / `kern.log` | Firewall blocks (DPT=port) |
| `fail2ban.log` | Banned IPs |
| `http_requests` DB | Web vulnerability probes (.env, wp-admin, etc.) |

Each source IP is classified:

| Class | Meaning |
|-------|---------|
| `ssh_bruteforcer` | Repeated SSH password attempts |
| `port_scanner` | Many destination ports |
| `firewall_prober` | Repeated firewall drops |
| `web_scanner` | Suspicious HTTP paths |
| `banned_attacker` | Already in fail2ban |

Dashboard: **Security → Port Knocks** tab.


```cron
*/15 * * * * cd /opt/skopos && .venv/bin/python skoposctl.py security-scan >> /var/log/skopos-security.log 2>&1
```

## Security notes

- SSH uses `AutoAddPolicy` (same as traffic collector)
- API keys via environment variables only
- Agent context may include auth log excerpts — protect `skopos.sqlite3`
