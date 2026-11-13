"""
GARI Auth Server 1.0 — CSRF Protection Middleware
"""
import secrets
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from app.config import settings

EXEMPT_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/logout",
    "/api/v1/auth/csrf",
    "/api/v1/admin/bootstrap",
    "/api/v1/health",
    "/api/v1/ready",
    "/docs",
    "/openapi.json",
    "/redoc"
}


def generate_csrf_token() -> str:
    """Generates a high-entropy CSRF protection token."""
    return secrets.token_urlsafe(32)


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/")
        method = request.method.upper()

        # 1. State-changing request validation
        if method in {"POST", "PUT", "PATCH", "DELETE"} and path not in EXEMPT_PATHS:
            session_cookie = request.cookies.get(settings.COOKIE_NAME)

            # If user has an active session cookie, enforce anti-CSRF
            if session_cookie:
                csrf_cookie = request.cookies.get(settings.CSRF_COOKIE_NAME)
                csrf_header = request.headers.get("X-CSRF-Token") or request.headers.get("x-csrf-token")

                if not csrf_cookie or not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
                    return JSONResponse(
                        status_code=403,
                        content={
                            "success": False,
                            "code": "CSRF_VERIFICATION_FAILED",
                            "detail": "Mã xác thực CSRF không hợp lệ hoặc đã hết hạn. Vui lòng làm mới trang."
                        }
                    )

        response: Response = await call_next(request)

        # 2. Ensure CSRF cookie is set for client if missing
        existing_csrf = request.cookies.get(settings.CSRF_COOKIE_NAME)
        if not existing_csrf:
            new_csrf = generate_csrf_token()
            response.set_cookie(
                key=settings.CSRF_COOKIE_NAME,
                value=new_csrf,
                httponly=False,  # JavaScript must be able to read CSRF token to send in X-CSRF-Token header
                secure=settings.COOKIE_SECURE,
                samesite=settings.COOKIE_SAMESITE,
                path="/"
            )

        return response
