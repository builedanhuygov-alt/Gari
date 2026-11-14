"""
GARI AgriTech AI Platform — Vercel Python Serverless Function Entrypoint
Provides native FastAPI ASGI handling directly on Vercel's Fluid Compute runtime.
"""
import sys
import os
from pathlib import Path

# Add auth-server directory to Python search path so all modules (app.*) resolve
_auth_server_dir = str(Path(__file__).resolve().parent.parent / "auth-server")
if _auth_server_dir in sys.path:
    sys.path.remove(_auth_server_dir)
sys.path.insert(0, _auth_server_dir)

# Ensure app package from auth-server is imported
from app.main import app  # noqa: E402, F401
