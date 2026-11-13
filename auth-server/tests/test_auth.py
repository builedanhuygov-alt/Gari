"""
Unit & Integration Tests for Authentication Flow
"""
import pytest
from datetime import datetime, timedelta, timezone
from app.models.user import User
from app.models.session import SessionModel
from app.config import settings


def test_registration_success(client, db_session):
    """Test 1: Registration succeeds with Argon2id hash and farmer role."""
    payload = {
        "email": "farmer_nam@gari.vn",
        "password": "StrongPassword123!",
        "full_name": "Nguyễn Văn Nam"
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["success"] is True
    assert data["user"]["email"] == "farmer_nam@gari.vn"
    assert data["user"]["account_type"] == "farmer"

    # Verify session cookie was set
    assert settings.COOKIE_NAME in res.cookies

    # Verify database state
    user = db_session.query(User).filter(User.email == "farmer_nam@gari.vn").first()
    assert user is not None
    assert user.password_hash.startswith("$argon2id$")
    assert user.password_hash != "StrongPassword123!"


def test_duplicate_email(client):
    """Test 4: Duplicate email rejected with 409 Conflict."""
    payload = {
        "email": "farmer_duplicate@gari.vn",
        "password": "StrongPassword123!",
        "full_name": "Nông Dân A"
    }
    r1 = client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201

    r2 = client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409
    assert "đã được sử dụng" in r2.json()["detail"]


def test_login_success(client):
    """Test 5: Login succeeds and sets HttpOnly cookie."""
    reg = client.post("/api/v1/auth/register", json={
        "email": "login_test@gari.vn",
        "password": "ValidPassword123!",
        "full_name": "Lê Văn Test"
    })
    assert reg.status_code == 201

    # Log in with fresh client (no prior cookies)
    client.cookies.clear()
    login_res = client.post("/api/v1/auth/login", json={
        "email": "login_test@gari.vn",
        "password": "ValidPassword123!"
    })
    assert login_res.status_code == 200
    assert settings.COOKIE_NAME in login_res.cookies


def test_incorrect_password(client):
    """Test 6: Incorrect password returns uniform 401 error."""
    client.post("/api/v1/auth/register", json={
        "email": "wrong_pass@gari.vn",
        "password": "CorrectPassword123!",
        "full_name": "Trần Thị B"
    })

    client.cookies.clear()
    res = client.post("/api/v1/auth/login", json={
        "email": "wrong_pass@gari.vn",
        "password": "WrongPassword999!"
    })
    assert res.status_code == 401
    assert "không chính xác" in res.json()["detail"]


def test_session_persistence(client):
    """Test 7: Authenticated session persists and returns user profile."""
    client.post("/api/v1/auth/register", json={
        "email": "persist@gari.vn",
        "password": "Password123!",
        "full_name": "Phạm Văn C"
    })

    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "persist@gari.vn"


def test_session_expiry(client, db_session):
    """Test 8: Expired session is rejected with 401."""
    client.post("/api/v1/auth/register", json={
        "email": "expire_test@gari.vn",
        "password": "Password123!",
        "full_name": "Vũ Văn D"
    })

    # Fast-forward session expiration in DB
    user = db_session.query(User).filter(User.email == "expire_test@gari.vn").first()
    session_rec = db_session.query(SessionModel).filter(SessionModel.user_id == user.id).first()
    session_rec.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.commit()

    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert "hết hạn" in res.json()["detail"]


def test_logout(client, db_session):
    """Test 9: Logout revokes session in DB and deletes cookie."""
    client.post("/api/v1/auth/register", json={
        "email": "logout_test@gari.vn",
        "password": "Password123!",
        "full_name": "Hoàng Văn E"
    })

    logout_res = client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200

    # Verify session revoked in DB
    user = db_session.query(User).filter(User.email == "logout_test@gari.vn").first()
    session_rec = db_session.query(SessionModel).filter(SessionModel.user_id == user.id).first()
    assert session_rec.revoked_at is not None

    # Subsequent request fails
    assert client.get("/api/v1/auth/me").status_code == 401


def test_session_revocation(client, db_session):
    """Test 10: Revoke other sessions keeps current session active."""
    # Register user (Session 1)
    client.post("/api/v1/auth/register", json={
        "email": "multi_session@gari.vn",
        "password": "Password123!",
        "full_name": "Đỗ Văn F"
    })
    token1 = client.cookies.get(settings.COOKIE_NAME)

    # Login on second device (Session 2)
    client.cookies.clear()
    login2 = client.post("/api/v1/auth/login", json={
        "email": "multi_session@gari.vn",
        "password": "Password123!"
    })
    assert login2.status_code == 200
    token2 = client.cookies.get(settings.COOKIE_NAME)

    # From Session 2, revoke other sessions
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    revoke_res = client.post("/api/v1/auth/revoke-sessions", headers={"X-CSRF-Token": csrf})
    assert revoke_res.status_code == 200

    # Session 2 is still valid
    assert client.get("/api/v1/auth/me").status_code == 200

    # Session 1 is now revoked
    client.cookies.clear()
    client.cookies.set(settings.COOKIE_NAME, token1, domain="testserver", path="/")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_inactive_account_login(client, db_session):
    """Test 15: Deactivated accounts cannot log in."""
    client.post("/api/v1/auth/register", json={
        "email": "banned@gari.vn",
        "password": "Password123!",
        "full_name": "Tài Khoản Khóa"
    })

    user = db_session.query(User).filter(User.email == "banned@gari.vn").first()
    user.is_active = False
    db_session.commit()

    client.cookies.clear()
    res = client.post("/api/v1/auth/login", json={
        "email": "banned@gari.vn",
        "password": "Password123!"
    })
    assert res.status_code == 403
    assert "tạm khóa" in res.json()["detail"]
