#!/usr/bin/env bash
# ==============================================================================
# GARI AgriTech AI Lab — Oracle Cloud VM System Metrics & Cron Monitor
# Path: deploy/oracle/system_metrics.sh
# Can be executed via cron every 5 minutes: */5 * * * * bash /app/deploy/oracle/system_metrics.sh
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

# Ensure logs directory exists
mkdir -p logs

# Run Python monitor
if [ -f .venv/bin/python ]; then
    PYTHON_BIN=".venv/bin/python"
elif command -v python3 &> /dev/null; then
    PYTHON_BIN="python3"
else
    echo "[-] Python 3 not found."
    exit 1
fi

$PYTHON_BIN deploy/oracle/monitor.py --url "${GARI_INTERNAL_URL:-http://127.0.0.1:8000}" --log-file logs/monitoring.jsonl

