#!/usr/bin/env bash
# Download the free iptoasn.com IP→ASN dump for offline ASN/datacenter detection.
# No account or license key required.
#
# Usage:
#   ./scripts/install_iptoasn.sh [output-path]
#
# Default output: ./ip2asn-combined.tsv (put it in ./geoip/ for the docker deploy —
# the deploy mounts ./geoip read-only at /app/geoip).
#
# Idempotent: skips download when the file exists and is fresh
# (IPTOASN_MAX_AGE_DAYS, default 14).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TARGET="${1:-${SKOPOS_ASN_TSV_PATH:-./ip2asn-combined.tsv}}"
MAX_AGE_DAYS="${IPTOASN_MAX_AGE_DAYS:-14}"
URL="https://iptoasn.com/data/ip2asn-combined.tsv.gz"

log() { echo "[iptoasn] $*"; }

file_is_fresh() {
  local f="$1"
  [[ -f "$f" ]] || return 1
  local age_days
  if stat --version >/dev/null 2>&1; then
    age_days=$(( ( $(date +%s) - $(stat -c %Y "$f") ) / 86400 ))
  else
    age_days=$(( ( $(date +%s) - $(stat -f %m "$f") ) / 86400 ))
  fi
  [[ "$age_days" -lt "$MAX_AGE_DAYS" ]]
}

mkdir -p "$(dirname "$TARGET")"

if file_is_fresh "$TARGET"; then
  size="$(wc -c < "$TARGET" | tr -d ' ')"
  log "OK — $(basename "$TARGET") already present (${size} bytes, younger than ${MAX_AGE_DAYS}d)"
  exit 0
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "[iptoasn] error: curl required" >&2
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

ARCHIVE="${TMP}/ip2asn-combined.tsv.gz"
log "Downloading ${URL}…"
curl -fsSL "$URL" -o "$ARCHIVE"

if [[ ! -s "$ARCHIVE" ]] || ! gzip -t "$ARCHIVE" >/dev/null 2>&1; then
  echo "[iptoasn] error: download failed or archive corrupt" >&2
  exit 1
fi

# Atomic replace: unpack next to the target and rename, so a collector that
# lazily opens the file mid-install never sees a half-written TSV.
STAGING="$(dirname "$TARGET")/.ip2asn-combined.tsv.tmp.$$"
gunzip -c "$ARCHIVE" > "$STAGING"
chmod 0644 "$STAGING"
mv -f "$STAGING" "$TARGET"
size="$(wc -c < "$TARGET" | tr -d ' ')"
log "Installed $(realpath "$TARGET" 2>/dev/null || echo "$TARGET") (${size} bytes)"
