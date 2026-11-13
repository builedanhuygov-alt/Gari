"""
GARI Auth Server 1.0 — FastAPI Application Entry Point
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.config import settings
from app.database import init_db
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.csrf import CSRFProtectionMiddleware
from app.routes.health import router as health_router
from app.routes.auth import router as auth_router
from app.routes.profile import router as profile_router
from app.routes.admin import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize isolated database schema
    init_db()
    yield
    # Shutdown logic if needed


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Independent Authentication Service for GARI AgriTech AI Platform",
    lifespan=lifespan,
    docs_url="/docs" if settings.AUTH_ENV != "production" else None,
    redoc_url="/redoc" if settings.AUTH_ENV != "production" else None
)

# 1. Security Headers Middleware
app.add_middleware(SecurityHeadersMiddleware)

# 2. CSRF Protection Middleware
app.add_middleware(CSRFProtectionMiddleware)

# 3. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "X-Requested-With"],
    expose_headers=["Retry-After"]
)

# 4. Global sanitized 500 error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "code": "INTERNAL_SERVER_ERROR",
            "detail": "Đã xảy ra lỗi nội bộ máy chủ xác thực. Vui lòng thử lại sau."
        }
    )

# 5. Include API Routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(admin_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.AUTH_HOST,
        port=settings.AUTH_PORT,
        reload=(settings.AUTH_ENV == "development")
    )
