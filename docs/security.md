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


## What happens to a finding

Until 2026-09-13 the answer was: nothing. The audit rules ran, `save_scan` stored the
findings, and `skopos/ui_security.py` drew a gauge, an alert banner and a sidebar badge.
Nothing else read them. A database bound to `0.0.0.0` sat in the dashboard until a person
happened to look. The "remediation board" on the Remediation page does not contradict
this — it *displays* jobs the conductor pushes in through `ingest_remediation`; SKOPOS
has never created one.

Findings now leave the dashboard. `skopos/security/momus_push.py` posts the newest
snapshot of each server to `POST /skopos/report` on MOMUS, which converts them
(`momus/momus/intel/skopos_bridge.py`) into its own findings, records them in its corpus,
and puts them through the machinery it already had for its own probes: sign, blame,
route, fix, and re-probe before the fix is accepted.

```bash
# by hand, or from cron right after the scan
python skoposctl.py momus-push
python skoposctl.py momus-push --server oracle-host --resend
```

| Variable | Meaning |
|---|---|
| `SKOPOS_MOMUS_PUSH` | `1` turns reporting on. Off by default, and **not** inferred from the URL being set. |
| `SKOPOS_MOMUS_URL` | Where MOMUS listens (falls back to `AUTOPILOT_MOMUS_URL`). |
| `MOMUS_OPERATOR_TOKEN` | Sent as `x-momus-operator`. Without it MOMUS refuses the report. |
| `SKOPOS_MOMUS_PUSH_INTERVAL_S` | Only for the standalone daemon (`python -m skopos.security.momus_push`); default 900. |

### When SKOPOS and MOMUS are on different machines

Which is the production case, and the direction is **inverted** there — SKOPOS does not post.

MOMUS binds to loopback, and its public edge answers `404` for every route that makes it
act (`/scan`, `/retest`, `/remediate`, `/a2a/tasks`, and `/skopos/report` with them). That
is a deliberate second layer behind the operator token, stated in its own config. So
carrying the operator token to the SKOPOS host would not help: the door is shut in front
of the token, not behind it.

Instead SKOPOS **publishes** and the MOMUS host **pulls**:

```
skopos.modelmarket.dev            MOMUS host
GET /security/export   ◀──pull──  autopilot ──POST /skopos/report──▶ 127.0.0.1:9410
(read-only, own token)                        (loopback, operator token)
```

| Variable | Where | Meaning |
|---|---|---|
| `SKOPOS_EXPORT_TOKEN` | SKOPOS | Turns `GET /security/export` on. Unset ⇒ the route is `404` and publishes nothing. Its OWN token: a leak discloses posture, it does not grant the ability to file findings against any host MOMUS knows. |
| `SKOPOS_EXPORT_URL` | MOMUS host | Where to pull from. Set ⇒ the pull path is used instead of a local database. |
| `SKOPOS_EXPORT_TOKEN` | MOMUS host | The same value, sent as `X-Skopos-Export-Token`. |
| `SKOPOS_MOMUS_PUSH_STATE` | MOMUS host | Where the puller remembers the last snapshot id per server, since it has no database of its own. Default `/var/lib/skopos-autopilot/momus-push.json`. |

Reads leave SKOPOS; writes stay inside MOMUS. Neither machine gains a shell or a
credential on the other, and nothing that changes MOMUS becomes reachable from the
internet.

The autopilot (`skopos/remediation/autopilot.py`) also reports once per tick, **before**
its own dispatch gate and under `SKOPOS_MOMUS_PUSH` rather than `AUTOPILOT_ENABLED`.
Handing MOMUS an observation is not the same act as letting the loop change production,
and the evidence a dispatch needs — see the sighting count below — can only accumulate
over time, so it has to start before anyone arms the loop.

* **Severity and category** map across directly; `info` is dropped unless explicitly
  requested, because one fix round costs an agent run.
* **Deduplication** is stable across re-scans. An hourly scan that keeps seeing the same
  open port produces one finding, not one per hour — so the loop does not open a ticket,
  or pay a bounty, twenty-four times for it.
* **One push per snapshot.** MOMUS counts how many *separate scans* rediscovered a defect
  (`seen_count`), and the autopilot will not dispatch until that count passes a threshold.
  Re-posting an unchanged snapshot on a timer would manufacture that evidence out of a
  single observation, so the id of the last snapshot sent is remembered per server
  (`momus_pushes`) and an unchanged one is skipped. A failed push is never recorded as
  sent — otherwise that snapshot would be skipped for ever.
* **Routing is not ours to choose.** `escalation_for` decides `auto` (fix → retest →
  redeploy) or `human-governance`, exactly as it does for a MOMUS-discovered finding. A
  SKOPOS finding about a security-core host escalates to a person; importing a finding is
  not a way to get an automated patch onto an infrastructure box.
* **Most host findings escalate, and that is the honest answer.** The fix loop edits a
  component's repository and redeploys its container. "Postgres is bound to `0.0.0.0` on
  this machine", "fail2ban is not running", "this certificate expires in six days" are
  properties of the *machine*: no patch to any repo closes them, so dispatching one buys a
  rejected patch and a spent agent run while the port stays open. They become signed,
  blamed, routed tickets for an operator with shell access instead. The exception is
  **supply-chain** (`packages`, `project`) — a vulnerable dependency *is* a line in a
  lockfile, and fix → retest → redeploy is exactly what that needs.
* **Operator token required.** The endpoint writes into the queue that opens remediation
  tickets, so an unauthenticated caller could otherwise invent findings against any host
  MOMUS knows about.

The operator-facing runbook for the loop itself — including what redeploys and what does
not — is `momus/docs/self-healing-operations.md`, section "Findings that come from
SKOPOS", which exists in all five of that document's locales.

## Security notes

- SSH uses `AutoAddPolicy` (same as traffic collector)
- API keys via environment variables only
- Agent context may include auth log excerpts — protect `skopos.sqlite3`
