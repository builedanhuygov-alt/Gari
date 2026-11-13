"""
Tests for Admin Bootstrap & Privilege Escalation Prevention
"""
import pytest
from app.models.user import User


def test_admin_bootstrap_one_time(client, db_session):
    """Verifies one-time initial admin bootstrap."""
    # 1. Invalid bootstrap token
    bad_res = client.post("/api/v1/admin/bootstrap", json={
        "bootstrap_token": "wrong_token_12345",
        "email": "admin@gari.vn",
        "password": "AdminPassword123!",
        "full_name": "Quản Trị Viên Gari"
    })
    assert bad_res.status_code == 403

    # 2. Valid bootstrap
    good_res = client.post("/api/v1/admin/bootstrap", json={
        "bootstrap_token": "super_secure_bootstrap_secret_token_12345",
        "email": "admin@gari.vn",
        "password": "AdminPassword123!",
        "full_name": "Quản Trị Viên Gari"
    })
    assert good_res.status_code == 201
    assert good_res.json()["account_type"] == "admin"

    # 3. Second bootstrap attempt must be rejected
    repeat_res = client.post("/api/v1/admin/bootstrap", json={
        "bootstrap_token": "super_secure_bootstrap_secret_token_12345",
        "email": "admin2@gari.vn",
        "password": "AdminPassword123!",
        "full_name": "Quản Trị Viên 2"
    })
    assert repeat_res.status_code == 409
    assert "bị khóa vĩnh viễn" in repeat_res.json()["detail"]


def test_admin_privilege_escalation_prevention(client):
    """Test 14: Non-admin users cannot access admin endpoints or elevate roles."""
    # 1. Register ordinary farmer
    client.post("/api/v1/auth/register", json={
        "email": "farmer_victim@gari.vn",
        "password": "Password123!",
        "full_name": "Nông Dân Thường"
    })

    # 2. Attempt to list users via admin endpoint -> 403 Forbidden
    res_list = client.get("/api/v1/admin/users")
    assert res_list.status_code == 403
    assert "Yêu cầu quyền quản trị viên" in res_list.json()["detail"]

    # 3. Attempt to change status of another user -> 403
    res_status = client.post("/api/v1/admin/users/1/status", json={"is_active": False})
    assert res_status.status_code == 403


def test_admin_user_management(client):
    """Admin can list users, view stats, and toggle registration."""
    # 1. Bootstrap admin
    client.post("/api/v1/admin/bootstrap", json={
        "bootstrap_token": "super_secure_bootstrap_secret_token_12345",
        "email": "superadmin@gari.vn",
        "password": "AdminPassword123!",
        "full_name": "Super Admin"
    })

    # 2. Login as admin
    client.cookies.clear()
    login_admin = client.post("/api/v1/auth/login", json={
        "email": "superadmin@gari.vn",
        "password": "AdminPassword123!"
    })
    assert login_admin.status_code == 200

    # 3. View stats
    stats_res = client.get("/api/v1/admin/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["capacity_limit"] == 10
    assert stats["registered_farmers"] == 0
    assert stats["capacity_remaining"] == 10
    assert stats["registration_open"] is True

    # 4. Toggle registration
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    toggle_res = client.post("/api/v1/admin/registration/toggle", headers={"X-CSRF-Token": csrf})
    assert toggle_res.status_code == 200

    # Verify registration is now closed
    client.cookies.clear()
    blocked_reg = client.post("/api/v1/auth/register", json={
        "email": "new_farmer@gari.vn",
        "password": "Password123!",
        "full_name": "Nông Dân Mới"
    })
    assert blocked_reg.status_code == 403
    assert "tạm đóng" in blocked_reg.json()["detail"]
