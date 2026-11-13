"""
Security & Compliance Tests (CSRF, CORS, Rate Limiting, Security Headers)
"""
import pytest
from app.config import settings
from app.middleware.rate_limit import rate_limiter


def test_csrf_protection(client):
    """Test 11: CSRF validation blocks authenticated POST without CSRF token."""
    # 1. Register user
    reg = client.post("/api/v1/auth/register", json={
        "email": "csrf_test@gari.vn",
        "password": "Password123!",
        "full_name": "Người Dùng CSRF"
    })
    assert reg.status_code == 201

    # 2. Attempt profile update without X-CSRF-Token header -> must be blocked
    update_res = client.put("/api/v1/profile", json={"full_name": "Tên Đổi Mới"})
    assert update_res.status_code == 403
    assert update_res.json()["code"] == "CSRF_VERIFICATION_FAILED"

    # 3. Retrieve valid CSRF token and retry with X-CSRF-Token header -> succeeds
    csrf_token = client.cookies.get(settings.CSRF_COOKIE_NAME)
    assert csrf_token is not None

    update_success = client.put(
        "/api/v1/profile",
        json={"full_name": "Tên Đổi Mới Hợp Lệ"},
        headers={"X-CSRF-Token": csrf_token}
    )
    assert update_success.status_code == 200
    assert update_success.json()["full_name"] == "Tên Đổi Mới Hợp Lệ"


def test_cors_restrictions(client):
    """Test 12: CORS allowlists allowed origins and restricts malicious origins."""
    # Allowed origin
    res_allowed = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://gari-team.vercel.app",
            "Access-Control-Request-Method": "POST"
        }
    )
    assert res_allowed.headers.get("access-control-allow-origin") == "https://gari-team.vercel.app"
    assert res_allowed.headers.get("access-control-allow-credentials") == "true"

    # Disallowed origin
    res_blocked = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://malicious-attacker-site.com",
            "Access-Control-Request-Method": "POST"
        }
    )
    assert res_blocked.headers.get("access-control-allow-origin") is None


def test_rate_limiting(client):
    """Test 13: Rapid failed attempts trigger 429 Too Many Requests."""
    settings.RATE_LIMIT_LOGIN_MAX_ATTEMPTS = 5
    rate_limiter._history.clear()
    email = "rate_limit_target@gari.vn"

    # Attempt 5 failed logins
    for i in range(5):
        client.post("/api/v1/auth/login", json={"email": email, "password": f"wrong_{i}"})

    # 6th attempt must be rejected with 429
    blocked = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong_final"})
    assert blocked.status_code == 429
    assert "Quá nhiều lần thử" in blocked.json()["detail"]
    assert "Retry-After" in blocked.headers


def test_security_headers(client):
    """Verifies baseline HTTP security headers."""
    res = client.get("/api/v1/health")
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "DENY"
    assert res.headers.get("x-xss-protection") == "1; mode=block"
    assert res.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_malformed_session_token_handling(client):
    """Verifies malformed or SQL-injection session tokens return 401 without server error."""
    client.cookies.set(settings.COOKIE_NAME, "'; DROP TABLE users; --", domain="testserver", path="/")
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert "Yêu cầu đăng nhập" in res.json()["detail"] or "hết hạn" in res.json()["detail"]


def test_email_whitespace_and_case_normalization(client):
    """Verifies leading/trailing whitespace and uppercase characters are normalized consistently."""
    reg = client.post("/api/v1/auth/register", json={
        "email": "   Farmer.Normalize@Gari.VN   ",
        "password": "Password123!",
        "full_name": "  Nông Dân Chuẩn Hóa  "
    })
    assert reg.status_code == 201
    assert reg.json()["user"]["email"] == "farmer.normalize@gari.vn"
    assert reg.json()["user"]["full_name"] == "Nông Dân Chuẩn Hóa"

    # Login using different casing & whitespace
    client.cookies.clear()
    login = client.post("/api/v1/auth/login", json={
        "email": "FARMER.NORMALIZE@GARI.VN",
        "password": "Password123!"
    })
    assert login.status_code == 200

