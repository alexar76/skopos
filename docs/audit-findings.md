# Security Audit — Findings & Remediation

Expert review of the SKOPOS platform and monitored fleet (July 2026).

## Fleet perimeter (factory, oracle, metis)

| Finding | Severity | Status |
|---------|----------|--------|
| Active SSH brute-force from dozens of IPs | **Critical** | Monitored in Port Knocks tab; block via fail2ban |
| Firewall inactive / not reported on hosts | **High** | Alert + audit finding; enable `ufw default deny` |
| SSH password auth may be enabled | **High** | Audit checks `sshd_config`; disable passwords |
| Public ports 22, 25, 80, 443, 8443 | **Info–Medium** | Expected for web; review SMTP 25 |
| fail2ban not confirmed under attack | **High** | New audit rule when brute-force without fail2ban |

## SKOPOS application (this project)

| Finding | Severity | Remediation implemented |
|---------|----------|-------------------------|
| Dashboard open without password | **Critical** | `SKOPOS_DASHBOARD_PASSWORD` + login gate |
| SSH MITM (AutoAddPolicy) | **Medium** | `SKOPOS_SSH_STRICT_HOST_KEYS=1` + RejectPolicy |
| API keys in process env | **Medium** | Documented; requires dashboard auth |
| SQLite / config world-readable | **Low–Medium** | `project_audit` detects; chmod 600 |
| Plaintext keys in agent.yaml | **Critical** | Audit warns; use `api_key_env` only |
| Bound to 0.0.0.0 without auth | **Critical** | Password gate + docker env documented |

## Implemented monitoring

- **Security Score** 0–100 (fleet + per-server) with grade A–F
- **Active threat alerts** banner on all pages
- **Expert remarks** in Score & Alerts tab
- **Global Security Agent** in sidebar (Analytics + Security)
- **Port knock classification** with threat score
- **Project self-audit** on every posture computation

## Recommended next steps (ops)

1. `export SKOPOS_DASHBOARD_PASSWORD='…'` before exposing port 8501
2. `export SKOPOS_SSH_STRICT_HOST_KEYS=1` and populate `known_hosts`
3. On each server: `ufw enable`, `fail2ban`, `PasswordAuthentication no`
4. Cron: `*/15 * * * * skoposctl.py security-scan`
5. Block top threat IPs at perimeter firewall
