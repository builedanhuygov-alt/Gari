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

from app.main import app as _fastapi_app  # noqa: E402


class VercelASGIAdapter:
    """
    ASGI middleware wrapper that ensures the original request path is preserved
    when Vercel rewrites requests to the /api function.
    """
    def __init__(self, fastapi_app):
        self._app = fastapi_app

    def __getattr__(self, name):
        return getattr(self._app, name)

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            headers = dict(scope.get("headers", []))
            # Vercel sets x-matched-path or x-forwarded-uri on rewritten requests
            matched_path = headers.get(b"x-matched-path", b"").decode("latin1")
            if matched_path and matched_path != "/api":
                scope["path"] = matched_path
        await self._app(scope, receive, send)


app = VercelASGIAdapter(_fastapi_app)
