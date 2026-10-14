FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
COPY requirements-postgres.txt /app/requirements-postgres.txt
RUN pip install --no-cache-dir -r /app/requirements.txt -r /app/requirements-postgres.txt \
    && python -c "from dilithium_py.ml_dsa import ML_DSA_65"

COPY . /app

RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8501 8502

# Not root: the SKOPOS dashboard and API. uid 10001 owns only what it writes (/app/.skopos).
RUN mkdir -p /app/.skopos && chown 10001:10001 /app && chown -R 10001:10001 /app/.skopos
ENV HOME=/tmp
USER 10001:10001

ENTRYPOINT ["/app/docker-entrypoint.sh"]
