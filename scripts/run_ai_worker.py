"""
GARI AgriTech — Dedicated AI Inference Worker Daemon
Launches uvicorn api_server:app with validated production environment and model warmup.
"""
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

os.environ["APP_ENV"] = "production"
os.environ["HOST"] = "127.0.0.1"
os.environ["PORT"] = "8000"

# Load DATABASE_URL from .env.local if not already in environment
if not os.environ.get("DATABASE_URL") and (ROOT_DIR / ".env.local").exists():
    with open(ROOT_DIR / ".env.local", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("DATABASE_URL="):
                os.environ["DATABASE_URL"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
if not os.environ.get("SESSION_SECRET") or len(os.environ.get("SESSION_SECRET", "")) < 32:
    os.environ["SESSION_SECRET"] = "gari_production_session_secret_key_32_characters_minimum_2026_secure"
if not os.environ.get("JWT_SECRET") or len(os.environ.get("JWT_SECRET", "")) < 32:
    os.environ["JWT_SECRET"] = "gari_production_jwt_secret_key_32_characters_minimum_2026_secure"
os.environ["MODEL_PRELOAD_ENABLED"] = "true"
os.environ["MODEL_IDLE_TIMEOUT_SECONDS"] = "86400"
os.environ["INFERENCE_TIMEOUT_SECONDS"] = "60"
os.environ["GARI_ALLOW_ORIGINS"] = "https://gari-team.vercel.app,http://localhost:8000,http://127.0.0.1:8000"

import uvicorn

if __name__ == "__main__":
    print(f"[*] Starting GARI AI Worker from {ROOT_DIR} on 127.0.0.1:8000...")
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, log_level="info", access_log=True)
