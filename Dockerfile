# NiveshRakshak backend — arm64/amd64 compatible.
# Deployed on an Oracle Always Free A1 (aarch64, Ubuntu 24.04) alongside another
# project, so resource caps live in docker-compose.yml, not here.

FROM python:3.11-slim

# CLI tools server/ocr.py shells out to.
# NOTE: tesseract-ocr-eng / tesseract-ocr-hin are deliberately NOT installed —
# the repo ships its own traineddata in server/tessdata/ and ocr.py points
# TESSDATA_PREFIX at it. That keeps the image smaller and the language set
# under version control.
# tzdata is required for the TZ=Asia/Kolkata env in docker-compose.yml; slim
# images do not ship it, and without it TZ is silently ignored (stays UTC).
# curl is only for the container HEALTHCHECK.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        zbar-tools \
        tzdata \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first so this layer caches across code-only changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ server/
COPY tools/  tools/
COPY web/    web/

# Run as non-root. /app/data is the mounted volume (registry mirror + audit log
# + SEBI result cache); compose chowns it via the volume mount.
RUN useradd -m -u 10001 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

ENV HOST=0.0.0.0 \
    PORT=8300 \
    PYTHONUNBUFFERED=1 \
    TESSDATA_PREFIX=/app/server/tessdata

EXPOSE 8300

# start-period is generous: first boot downloads ~23.5k registry rows from
# sebi.gov.in in a background thread (the API serves before that finishes).
HEALTHCHECK --interval=60s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8300/api/health >/dev/null || exit 1

# --proxy-headers is LOAD-BEARING. Behind the reverse proxy / tunnel,
# request.client.host would otherwise be the proxy's address, and the per-IP
# token bucket in app.py (NR_RATE_LIMIT checks per NR_RATE_WINDOW) would
# collapse into ONE GLOBAL bucket — locking out every tester after 30 checks.
# Safe to trust unconditionally here because compose binds the published port
# to 127.0.0.1 only, so the proxy is the only thing that can reach us.
CMD ["sh", "-c", "exec uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-8300} --proxy-headers --forwarded-allow-ips='*'"]
