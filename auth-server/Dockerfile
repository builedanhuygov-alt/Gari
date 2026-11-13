# GARI Auth Server 1.0 — Production Dockerfile
FROM python:3.11-slim as base

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (build-essential needed for compiling cffi/argon2 if binary wheels unavailable)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create dedicated non-root application user and persistent data directory
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/false -m appuser && \
    mkdir -p /var/lib/gari-auth/data && \
    mkdir -p /var/lib/gari-auth/backups && \
    chown -R appuser:appgroup /var/lib/gari-auth

# Copy application source
COPY --chown=appuser:appgroup app/ ./app
COPY --chown=appuser:appgroup scripts/ ./scripts

USER appuser

EXPOSE 8001

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8001/api/v1/health || exit 1

ENV AUTH_HOST=0.0.0.0 \
    AUTH_PORT=8001 \
    AUTH_ENV=production \
    AUTH_DATA_DIR=/var/lib/gari-auth/data

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
