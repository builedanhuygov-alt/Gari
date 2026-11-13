# ==============================================================================
# GARI AgriTech AI Lab — Production Dockerfile
# Multi-Architecture Support: linux/amd64, linux/arm64 (Oracle Cloud Ampere A1)
# ==============================================================================

FROM python:3.11-slim AS base

# Install essential native libraries for OpenCV and system healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Optimize Python execution environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    APP_ENV=production \
    DEVICE=cpu

WORKDIR /app

# Install production Python dependencies
COPY requirements-production.txt requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    if [ -f requirements-production.txt ]; then \
        pip install --no-cache-dir -r requirements-production.txt; \
    else \
        pip install --no-cache-dir -r requirements.txt; \
    fi

# Create non-root application user for container isolation
RUN useradd -m -u 1000 gari && \
    mkdir -p /app/database /app/database/uploads /app/models /app/logs && \
    chown -R gari:gari /app

# Copy application source code (excluding files listed in .dockerignore)
COPY --chown=gari:gari . .

# Switch to non-root user
USER gari

EXPOSE 8000

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Launch FastAPI via Uvicorn
CMD ["sh", "-c", "uvicorn api_server:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --timeout-keep-alive 65"]
