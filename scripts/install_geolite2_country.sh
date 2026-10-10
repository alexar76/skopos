#!/usr/bin/env bash
# Download MaxMind GeoLite2-Country.mmdb for offline country lookup (no external GeoIP APIs).
#
# Requires a free MaxMind account + license key:
#   https://www.maxmind.com/en/geolite2/signup
#
# Usage:
#   export MAXMIND_LICENSE_KEY=your_key
#   ./scripts/install_geolite2_country.sh [output-path]
#
# Default output: ./GeoLite2-Country.mmdb (or ./geoip/GeoLite2-Country.mmdb when run from deploy dir)
#
# Idempotent: skips download when the file exists and is fresh (MAXMIND_GEOIP_MAX_AGE_DAYS, default 14).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TARGET="${1:-${SKOPOS_GEOIP_MMDB_PATH:-./GeoLite2-Country.mmdb}}"
MAX_AGE_DAYS="${MAXMIND_GEOIP_MAX_AGE_DAYS:-14}"

# Load project / deploy .env when present (never echo secrets).
for env_file in "${ROOT}/.env" "${ROOT}/../deploy/.env" "/opt/skopos-test/deploy/.env"; do
  if [[ -f "${env_file}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${env_file}"
    set +a
    break
  fi
done

LICENSE="${MAXMIND_LICENSE_KEY:-}"
ACCOUNT="${MAXMIND_ACCOUNT_ID:-}"

log() { echo "[geolite2] $*"; }

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

if [[ -z "$LICENSE" ]]; then
  log "skip — MAXMIND_LICENSE_KEY not set (free key: https://www.maxmind.com/en/geolite2/signup)"
  log "      country lookup will use external APIs unless you copy GeoLite2-Country.mmdb manually"
  exit 0
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "[geolite2] error: curl required" >&2
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

ARCHIVE="${TMP}/GeoLite2-Country.tar.gz"
log "Downloading GeoLite2-Country…"

download_ok=0
if [[ -n "$ACCOUNT" ]]; then
  if curl -fsSL -u "${ACCOUNT}:${LICENSE}" \
    "https://download.maxmind.com/geoip/databases/GeoLite2-Country/download?suffix=tar.gz" \
    -o "$ARCHIVE"; then
    download_ok=1
  fi
fi

if [[ "$download_ok" -eq 0 ]]; then
  curl -fsSL \
    "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-Country&license_key=${LICENSE}&suffix=tar.gz" \
    -o "$ARCHIVE"
fi

if [[ ! -s "$ARCHIVE" ]] || ! tar -tzf "$ARCHIVE" >/dev/null 2>&1; then
  echo "[geolite2] error: download failed — check MAXMIND_LICENSE_KEY / MAXMIND_ACCOUNT_ID" >&2
  exit 1
fi

tar -xzf "$ARCHIVE" -C "$TMP"
MMDB="$(find "$TMP" -name 'GeoLite2-Country.mmdb' -type f | head -1)"
if [[ -z "$MMDB" || ! -f "$MMDB" ]]; then
  echo "[geolite2] error: GeoLite2-Country.mmdb not found in archive" >&2
  exit 1
fi

install -m 0644 "$MMDB" "$TARGET"
size="$(wc -c < "$TARGET" | tr -d ' ')"
log "Installed $(realpath "$TARGET" 2>/dev/null || echo "$TARGET") (${size} bytes)"
