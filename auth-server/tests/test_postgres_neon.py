"""
GARI Auth Server 1.0 — PostgreSQL / Neon Serverless Integration Tests
"""
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from app.config import Settings
from app.services.registration import register_user, RegistrationCapacityError
from app.models.user import User


def test_database_url_normalization_neon():
    """Verifies that postgres:// URI from Render/Neon is converted to postgresql:// for SQLAlchemy 2.0."""
    neon_url = "postgres://neondb_owner:npg_secret123@ep-lively-star-123456-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
    s = Settings(DATABASE_URL=neon_url)
    assert s.database_url.startswith("postgresql://")
    assert "neondb_owner" in s.database_url
    assert "sslmode=require" in s.database_url


def test_cors_origins_comma_separated_parsing():
    """Verifies that Render environment string for CORS origins is correctly parsed into a list."""
    s = Settings(CORS_ALLOWED_ORIGINS="https://gari-team.vercel.app, https://preview.vercel.app,http://localhost:3000")
    assert isinstance(s.CORS_ALLOWED_ORIGINS, list)
    assert len(s.CORS_ALLOWED_ORIGINS) == 3
    assert "https://gari-team.vercel.app" in s.CORS_ALLOWED_ORIGINS
    assert "https://preview.vercel.app" in s.CORS_ALLOWED_ORIGINS
    assert "http://localhost:3000" in s.CORS_ALLOWED_ORIGINS


def test_cors_origins_json_parsing():
    """Verifies that JSON string format for CORS origins is also parsed correctly."""
    s = Settings(CORS_ALLOWED_ORIGINS='["https://gari-team.vercel.app", "http://localhost:3000"]')
    assert isinstance(s.CORS_ALLOWED_ORIGINS, list)
    assert len(s.CORS_ALLOWED_ORIGINS) == 2


def test_health_endpoints_multi_path(client):
    """Verifies that all standard health check paths return 200 OK for Render and Edge Gateway."""
    paths = ["/health", "/healthz", "/api/health", "/api/v1/health"]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, f"Path {path} failed: {response.text}"
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


def test_readiness_probe_success(client):
    """Verifies readiness probe returns 200 with database connectivity."""
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert data["registration_capacity_max"] == 10


def test_postgres_dialect_advisory_lock_invocation():
    """
    Verifies that on a PostgreSQL database connection,
    the registration service invokes pg_advisory_xact_lock(424242) for race-free serialization.
    """
    mock_db = MagicMock()
    mock_bind = MagicMock()
    mock_bind.dialect.name = "postgresql"
    mock_db.get_bind.return_value = mock_bind
    mock_db.query.return_value.filter.return_value.count.return_value = 0
    mock_db.query.return_value.filter.return_value.first.return_value = None

    user = register_user(
        db=mock_db,
        email="pg_farmer@test.gari.vn",
        password="SecurePassword123!",
        full_name="Postgres Test Farmer"
    )
    assert user.email == "pg_farmer@test.gari.vn"
    assert user.account_type == "farmer"

    # Verify pg_advisory_xact_lock was executed
    executed_sqls = [call[0][0].text for call in mock_db.connection().execute.call_args_list]
    assert any("pg_advisory_xact_lock" in sql for sql in executed_sqls)
