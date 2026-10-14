# Privacy & data handling

How SKOPOS treats the one field in an access log that is personal data — the
visitor's IP address — and how that maps to the GDPR and to US state privacy law.

> This is an engineering description of the controls the software ships with, not
> legal advice. Which law applies to *your* deployment depends on who your
> visitors are and how much traffic you handle; see [Jurisdiction](#jurisdiction).

---

## What SKOPOS stores, and what it does not

SKOPOS parses **nginx / Apache access logs** into the `http_requests` table. Per
request it keeps: timestamp, host, request path, method, status, bytes, referer
domain, parsed user-agent (browser / OS / device / bot flag), the derived country
and ASN, and the visitor's IP address (`remote_addr`).

It deliberately does **not**:

- **Load any third-party tracker.** No Google Analytics, no ad networks, no
  cross-site cookies. Everything is first-party server logs on a host you run.
- **Keep the verbatim log line.** `line_raw` is dropped at the storage boundary
  (stored empty) unless `SKOPOS_STORE_RAW_LINES=1` is set for parser debugging.
- **Keep secrets from URLs.** Session tokens, reset links, e-mails and tracking
  IDs in query strings and referers are stripped at ingest — see
  [`skopos/redact.py`](../skopos/redact.py).

The remaining sensitive field is the IP address, which this document is about.

## The IP address is personal data

An IP address identifies (or helps identify) a person, so both regimes treat it
as protected:

- **GDPR** — the CJEU held a dynamic IP address is *personal data* in the hands
  of an operator who has lawful means to identify the user (C-582/14, *Breyer*,
  2016). Recital 30 lists online identifiers explicitly.
- **US state laws** — the CCPA/CPRA name IP address as an example of *personal
  information*, and the newer state acts (see below) use the same definition.

Storing every visitor's full address indefinitely, indexed and charted as "top
visitors", is therefore processing that would need a lawful basis, a retention
limit and a notice. SKOPOS avoids most of that by **not keeping the full address
in the first place**, while still answering the questions the dashboard exists
for (which countries, which networks, how many distinct people, which scanners).

## What SKOPOS does about it

The full address is used for enrichment **first** — country, ASN, the bot flag —
and only then reduced before it is written. See
[`skopos/anonymize.py`](../skopos/anonymize.py). Three modes:

| `SKOPOS_IP_ANONYMIZE` | Stored form | Use it when |
|---|---|---|
| `truncate` *(default)* | IPv4 → `a.b.c.0` (/24), IPv6 → `/48` | You want privacy-by-default. "Top IPs" becomes "top /24s" — still a real, blockable network, but no single machine is singled out. |
| `hash` | salted SHA-256, first 12 hex, `h:` prefix | You need **exact** distinct-visitor counts. The address is unrecoverable without the salt (`SKOPOS_IP_HASH_SALT`). |
| `off` | full address | You have your own lawful basis + retention and need the exact value. |

Internal traffic (private, loopback, link-local ranges) is left whole under every
mode: no data subject sits between your own hosts, and the exact value is what
makes an internal log debuggable.

**Reduction happens after enrichment**, so accuracy is preserved:

```
parse → clamp → redact URL secrets → geo + ASN lookup (full IP) → reduce IP → store
```

### Retention

`http_retention_days` (config key, or `SKOPOS_HTTP_RETENTION_DAYS`) deletes rows
older than N days, once per collect cycle — no separate cron. The default is
**90 days**; set it to `0` to keep everything. Ninety days is long enough for
security investigation and month-over-month trends, and short enough to satisfy
storage-limitation expectations even before anonymisation is counted.

### Existing rows

Anonymisation protects rows written from now on. To bring history to the same
standard once:

```bash
python -m skopos.anonymize --config config.yaml --backfill
```

## Does this still let us filter bots and traffic? — Yes

This was a design constraint, not an afterthought. Everything the dashboard
filters on is derived from the **full** IP or the user-agent **before** the
address is reduced, and stored in its own column:

- **Bot filtering** (`hide_bots`) reads `ua_is_bot`, empty-UA and UA/browser
  patterns, and path shape — none of which touch `remote_addr`. Unaffected.
- **Datacenter / service / relay filtering** reads `asn` / `asn_org`, resolved on
  the full IP at ingest. Unaffected.
- **Private-range exclusion** (`visitors_only`) matches prefixes like `10.%`,
  which still work because internal addresses are kept whole.
- **Scan / probe detection** groups by address; under `truncate` a scanner still
  appears as its /24 — which is what you would firewall anyway.

The one thing that changes: **unique-visitor counts** under `truncate` are counted
per /24, so several people behind one NAT/ISP block count as one. If you need
exact unique counts, use `hash` mode — it keeps per-visitor distinctness while
still storing no readable address. (For blocking a specific attacker, `truncate`
is usually better: a /24 is routable and blockable; a hash is not.)

---

## Jurisdiction

**Where you incorporate does not decide which privacy law applies.** A Delaware
LLC is still under the GDPR for its EU visitors, under the CCPA for its California
visitors, and so on. Applicability follows **where your users are** and **how
much data you handle** — not the flag on the company. The good news is that the
same technical controls satisfy all of them, because they all reward the same
thing: collect less, keep it shorter, don't sell it, secure it.

### GDPR (EU / UK / EEA visitors)

| Control in SKOPOS | GDPR hook |
|---|---|
| Reduce the IP; drop `line_raw`; strip URL secrets | **Art. 5(1)(c)** data minimisation; **Art. 25** privacy by design & *by default* |
| `http_retention_days` | **Art. 5(1)(e)** storage limitation |
| Logging for security/abuse at all | **Recital 49** — network & information security is a recognised legitimate interest (**Art. 6(1)(f)**) |
| No third-party trackers / no cookies for analytics | avoids **ePrivacy** consent-banner obligations for tracking |
| Self-hosted: the operator is the controller | **Art. 4(7)**; erasure / access requests handled by the operator (**Art. 15–17**) |

A note on the modes: salted **hashing is pseudonymisation** (Art. 4(5)) — still
personal data while the salt exists, so pair it with access control and retention.
**Truncation** to /24 removes the host identifier and is the approach regulators
accepted for analytics (it is what Google Analytics' IP-anonymisation did);
whether the result is "anonymous" or merely "pseudonymous" is a judgement call,
but either way it materially lowers risk versus the full address.

### United States

There is no single federal law; a growing set of **state** laws use materially
similar definitions and defences. IP address is "personal information"; **data
that is truncated/hashed can qualify as "deidentified"** and fall outside most
obligations if you (a) can't reasonably re-identify it, (b) commit not to, and
(c) keep the controls in place — which is exactly what `truncate` / `hash` plus
retention give you.

| Law | Applies roughly when | What SKOPOS covers |
|---|---|---|
| **CCPA / CPRA** (California) | >$25M revenue, **or** PI of 100k+ consumers/households, **or** ≥50% revenue from selling PI | No selling / sharing (no third-party trackers) sidesteps the "sale/share" duties; deidentification + retention cover minimisation & security |
| **Delaware DPDPA** | Effective **Jan 1, 2025**; target DE residents **and** process 35k+ consumers, **or** 10k+ **and** >20% revenue from data sale | Same controls; lower thresholds than California, so easier to fall under |
| **VCDPA / CPA / CTDPA / UCPA / TDPSA / …** (VA, CO, CT, UT, TX, OR, MT, and more) | Vary by state; most turn on 100k consumers, or 25k + a data-sale share | All share the minimise / limit-retention / don't-sell / reasonable-security duties these controls address |

So: incorporating in Delaware is fine, but it is the **residency of your
visitors** and your **traffic volume** that pull you under DPDPA, CCPA or the
GDPR. The controls here are written to hold up under whichever one lands.

---

## Configuration quick reference

```bash
# Anonymisation (default: truncate)
SKOPOS_IP_ANONYMIZE=truncate     # truncate | hash | off
SKOPOS_IP_HASH_SALT=<random>     # required for hash mode to be meaningful

# Retention (default: 90 days)
SKOPOS_HTTP_RETENTION_DAYS=90    # 0 keeps everything; also settable as http_retention_days in config

# Raw log lines (default: off)
SKOPOS_STORE_RAW_LINES=0         # 1 keeps line_raw for parser debugging (IPs still reduced)
```

One-off history rewrite: `python -m skopos.anonymize --config config.yaml --backfill`.

Related code: [`anonymize.py`](../skopos/anonymize.py) ·
[`redact.py`](../skopos/redact.py) · retention in
[`db.py`](../skopos/db.py) (`prune_old_requests`) · wiring in
[`collector.py`](../skopos/collector.py).
