# Collection transports

How a monitored host's data reaches SKOPOS is the biggest security decision in
this deployment, because it decides what SKOPOS is holding when someone breaks
into it. There are three answers.

| Transport | What SKOPOS holds | What a stolen SKOPOS gets |
|---|---|---|
| `agent-push` *(recommended)* | nothing | nothing on this host |
| `agent-ssh` | a key that can say two words | one `ping`, one `collect` |
| `direct-ssh` *(legacy)* | a full-shell key | everything that account can do |

Set it per server in `servers.yaml`, or in **Fleet → the server → How does this
host's data reach SKOPOS?**

---

## agent-push — the host reports in

A small agent runs on the monitored host and posts what it finds. SKOPOS never
connects outward and holds no credential for the host at all, so compromising
the dashboard gains an attacker no access to the fleet. That is the whole
argument, and it is why this is the default.

```yaml
servers:
  - name: web-1
    source: ssh_nginx_access_log
    transport: agent-push
    address: web-1.example.com     # labels the traffic; nothing dials it
    nginx:
      access_log_path: /var/log/nginx/access.log
```

Onboarding one host:

```bash
python skoposctl.py node-ticket --server web-1
python skoposctl.py node-installer --server web-1 \
    --base-url https://skopos.example.com --out install-web-1.sh
```

Copy the installer to the host and run it; it prompts for the ticket:

```bash
sudo bash install-web-1.sh
```

It prompts rather than taking the ticket as an argument because everything in
`argv` is readable in `/proc/<pid>/cmdline` by every local user, and lands in
shell history and sudo's log — and that includes the `printf` in a
`printf ... | bash` pipeline. For unattended installs it still accepts the
ticket on stdin. It is single-use and expires in 30 minutes; the
long-lived credential is minted server-side, returned once over TLS, and written
straight to a `0640` file.

### What gets installed

Two units, deliberately split:

- **`skopos-node-privdump.timer`** runs as root, takes *no arguments and no
  input*, and writes the probe output to `/run/skopos-node/`. Everything needing
  privilege lives here.
- **`skopos-node.timer`** runs as the unprivileged `skopos-node` user, reads the
  allowed log directories and those dumps, and posts them.

The split matters. Reading `auth.log`, listing sockets with process names,
querying `fail2ban` and talking to Docker all need root or something equivalent
to it. Granting those to the reporting agent — via the `docker` group, or a
`sudo` rule — would hand back exactly the privilege this design removes: a member
of the `docker` group can start a container that mounts `/`. So the privileged
half takes no input at all, and the unprivileged half cannot ask it for
anything.

Log access is granted by ACL on the configured directories. If the filesystem
cannot do ACLs the installer falls back to the `adm` group and says so loudly —
`adm` also reads syslog and every other `adm`-readable file, which is broader
than we want.

The installer grants **no sudo rules** and adds the agent to **no `docker`
group**. If you need container logs, list the containers explicitly; the root
timer reads those and only those.

### Managing agents

```bash
python skoposctl.py node-list                    # who is enrolled, last seen, agent version
python skoposctl.py node-revoke --key-id nk_...  # a decommissioned host
```

Set `SKOPOS_NODE_SECRET_KEY` to the base64 of 32 random bytes. Node secrets are
HMAC keys, so SKOPOS must be able to read them back — with this set they are
sealed with AES-GCM under a key held outside the database, so a leaked dump is
not a set of working fleet credentials. Without it they are stored in the clear
and `node-list` tells you so.

```bash
python -c "import base64,os; print(base64.b64encode(os.urandom(32)).decode())"
```

---

## agent-ssh — for hosts that cannot reach out

Same agent, same document; SKOPOS opens the connection instead. Use it when a
host has no outbound path to the dashboard.

```yaml
    transport: agent-ssh
    ssh:
      host: web-2.example.com
      user: skopos-node
      key_path: /root/.ssh/skopos-web-2   # one key per host, never shared
      mode: wrapper
```

The key is pinned by `authorized_keys` **and** by an sshd `Match` block:

```
command="/usr/local/bin/skopos-node ssh-op",restrict ssh-ed25519 AAAA...
```

The `authorized_keys` file lives in `/etc/ssh/authorized_keys.d/`, owned by root
— not in the agent user's home, where the agent user could edit it and drop the
forced command. The sshd `ForceCommand` is the belt to that braces: it outranks
anything the key or the client asks for, and the constrained account cannot
change it.

What crosses the wire is `v1 ping` or `v1 collect`. Nothing else. There is no
operation that takes a path, a container name or a count, so there is nothing to
inject into and no allow-list to walk out of — what the host is willing to read
is decided by a root-owned file on the host, never by the caller.

---

## direct-ssh — the legacy path

SKOPOS pipes shell scripts to the host, so the key it holds is a full shell.
It is kept only for hosts not yet migrated. `skoposctl doctor` lists them:

```bash
python skoposctl.py doctor
```

If it reports one key opening several hosts, that key costs you all of them at
once. If it reports a host collected as `root`, that key is a root shell sitting
on the SKOPOS box.

---

## Host key verification

Both SSH transports verify host keys by default. Record a host's key once, after
checking the fingerprint against the host itself:

```bash
python skoposctl.py trust-host --host web-2.example.com --port 22
```

The trust store is `~/.skopos/known_hosts` (override with `SKOPOS_KNOWN_HOSTS`).
`SKOPOS_SSH_STRICT_HOST_KEYS=0` turns verification off; the only thing it buys is
an unverified first connection, and the cost is that whoever answers on that
address gets the whole log stream and controls every response.

---

## What none of this fixes

Worth saying plainly, because a security page that only lists wins is not a
security page:

- **SKOPOS still accumulates the fleet's access logs.** Session tokens in query
  strings, password-reset links, the full IP and user-agent history of your
  sites' visitors. Whoever holds this database holds that, whatever transport
  brought it in.
- **A compromised host controls what it reports about itself.** It can look
  healthy while it is not. Snapshots record which transport produced them, and
  pushed ones deserve less belief than a reading taken independently — but that
  is provenance, not proof.
- **HMAC is symmetric.** Root on a monitored host means the ability to sign as
  that host. The agent is stdlib-only, and the standard library has no
  public-key signatures that would fix this.
