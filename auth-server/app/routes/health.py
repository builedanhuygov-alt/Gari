"""
GARI Auth Server 1.0 — Health & Readiness Probes
"""
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.config import settings

router = APIRouter(prefix="/api/v1", tags=["Monitoring"])


@router.get("/health")
def health_check():
    """Liveness probe: verifies service process is running."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.AUTH_ENV
    }


@router.get("/ready")
def readiness_check(response: Response, db: Session = Depends(get_db)):
    """Readiness probe: verifies database connectivity and WAL mode operation."""
    try:
        result = db.execute(text("SELECT 1")).scalar()
        if result != 1:
            raise Exception("Database returned unexpected result")
        return {
            "status": "ready",
            "database": "connected",
            "registration_capacity_max": settings.MAX_REGISTRATION_ACCOUNTS,
            "registration_open": settings.REGISTRATION_OPEN
        }
    except Exception as e:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "error": str(e)
        }
