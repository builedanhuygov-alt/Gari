"""
Test Vercel Python Function Entrypoint & Serverless Engine Lifecycle
"""
import os
import pytest
from fastapi.testclient import TestClient
from app.config import settings

def test_vercel_entrypoint_import():
    """Verifies that api.index exports a valid FastAPI ASGI app without importing ML modules."""
    from api.index import app
    assert app is not None
    assert app.title == "GARI Independent Auth Server"
    paths = list(app.openapi()["paths"].keys())
    assert "/api/v1/health" in paths
    assert "/api/v1/ready" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/auth/register" in paths
    assert "/api/auth/login" in paths
    assert "/api/auth/register" in paths

def test_vercel_serverless_nullpool():
    """Verifies that NullPool is configured when VERCEL=1 is present in the environment."""
    os.environ["VERCEL"] = "1"
    try:
        from app.database import get_engine
        from sqlalchemy.pool import NullPool
        test_engine = get_engine("postgresql+psycopg2://test:test@localhost:5432/test")
        assert isinstance(test_engine.pool, NullPool)
    finally:
        del os.environ["VERCEL"]

def test_vercel_health_and_ready_endpoints():
    """Verifies the health and ready endpoints via the Vercel ASGI entrypoint."""
    from api.index import app
    client = TestClient(app)
    
    res_health = client.get("/api/v1/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"
    
    res_ready = client.get("/api/v1/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"

def test_vercel_auth_lifecycle():
    """Verifies complete register -> login -> me -> logout flow via TestClient on api.index."""
    from api.index import app
    client = TestClient(app)
    
    # 1. CSRF
    res_csrf = client.get("/api/v1/auth/csrf")
    assert res_csrf.status_code == 200
    csrf_token = res_csrf.json()["csrf_token"]
    assert csrf_token
    client.cookies.set("gari_csrf_token", csrf_token)
    
    # 2. Register
    test_email = "vercel_test_user@gari.vn"
    res_reg = client.post(
        "/api/v1/auth/register",
        json={"email": test_email, "password": "SecurePassword123!", "full_name": "Vercel Tester"},
        headers={"X-CSRF-Token": csrf_token}
    )
    # Could be 201 or 409 if already registered
    assert res_reg.status_code in [201, 409]
    
    # 3. Login
    res_login = client.post(
        "/api/v1/auth/login",
        json={"email": test_email, "password": "SecurePassword123!"},
        headers={"X-CSRF-Token": csrf_token}
    )
    assert res_login.status_code == 200
    assert settings.COOKIE_NAME in res_login.cookies
    session_cookie = res_login.cookies[settings.COOKIE_NAME]
    client.cookies.set(settings.COOKIE_NAME, session_cookie)
    
    # 4. Check Me
    res_me = client.get("/api/v1/auth/me")
    assert res_me.status_code == 200
    assert res_me.json()["email"] == test_email
    
    # 5. Logout
    res_logout = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_token}
    )
    assert res_logout.status_code == 200
