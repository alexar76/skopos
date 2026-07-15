#!/bin/sh
set -eu
python /app/api_server.py &
BASE="${STREAMLIT_SERVER_BASE_URL_PATH:-}"
if [ -n "${BASE}" ]; then
  exec streamlit run dashboard.py --server.address=0.0.0.0 --server.port=8501 --server.baseUrlPath="${BASE}"
fi
exec streamlit run dashboard.py --server.address=0.0.0.0 --server.port=8501
