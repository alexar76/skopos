#!/bin/sh
set -eu
python /app/api_server.py &

GEOIP_DIR="/app/geoip"
GEOIP_FILE="${GEOIP_DIR}/GeoLite2-Country.mmdb"
if [ -n "${MAXMIND_LICENSE_KEY:-}" ] && [ ! -f "${GEOIP_FILE}" ]; then
  mkdir -p "${GEOIP_DIR}"
  bash /app/scripts/install_geolite2_country.sh "${GEOIP_FILE}" || true
fi

BASE="${STREAMLIT_SERVER_BASE_URL_PATH:-}"
if [ -n "${BASE}" ]; then
  exec streamlit run dashboard.py --server.address=0.0.0.0 --server.port=8501 --server.baseUrlPath="${BASE}"
fi
exec streamlit run dashboard.py --server.address=0.0.0.0 --server.port=8501
