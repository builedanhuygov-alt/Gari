"""
Unit tests for GARI VIP Voucher Activation & Status Endpoints
"""
import pytest
from app.routes.voucher import AUTHORIZED_VOUCHER_CODE, VOUCHER_DURATION_DAYS, VOUCHER_DAILY_QUOTA


def test_activate_voucher_unauthenticated(client):
    """Anonymous user must receive 401 when attempting to activate voucher."""
    res = client.post("/api/v1/voucher/activate", json={"code": AUTHORIZED_VOUCHER_CODE})
    assert res.status_code == 401


def test_activate_voucher_invalid_code(client):
    """Authenticated user with invalid voucher code receives 400 Bad Request."""
    client.post("/api/v1/auth/register", json={
        "email": "student_invalid@gari.vn",
        "password": "Password123!",
        "full_name": "Học sinh 1"
    })
    res = client.post("/api/v1/voucher/activate", json={"code": "INVALID-CODE-999"})
    assert res.status_code == 400
    assert "không hợp lệ" in res.json()["detail"]


def test_activate_voucher_success(client):
    """Valid code activation succeeds, sets 7-day expiration, and updates /me."""
    client.post("/api/v1/auth/register", json={
        "email": "student_nhd@gari.vn",
        "password": "Password123!",
        "full_name": "Học sinh THPT NHD"
    })

    # Check initial status
    status_res = client.get("/api/v1/voucher/status")
    assert status_res.status_code == 200
    assert status_res.json()["is_activated"] is False

    # Activate
    res = client.post("/api/v1/voucher/activate", json={"code": AUTHORIZED_VOUCHER_CODE})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    voucher = data["voucher"]
    assert voucher["code"] == AUTHORIZED_VOUCHER_CODE
    assert voucher["tier"] == "vip_trial"
    assert voucher["daily_quota"] == VOUCHER_DAILY_QUOTA
    assert voucher["days_left"] == VOUCHER_DURATION_DAYS

    # Check status after activation
    status_res2 = client.get("/api/v1/voucher/status")
    assert status_res2.status_code == 200
    s_data = status_res2.json()
    assert s_data["is_activated"] is True
    assert s_data["is_expired"] is False
    assert s_data["code"] == AUTHORIZED_VOUCHER_CODE

    # Check /api/v1/auth/me reflects active VIP trial
    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["subscription"]["is_vip"] is True
    assert me_data["subscription"]["plan_id"] == "vip_trial"
    assert "VIP" in me_data["subscription"]["plan_name"]


def test_activate_voucher_duplicate_rejected(client):
    """Subsequent activation attempt by the same account must be rejected with 409 Conflict."""
    client.post("/api/v1/auth/register", json={
        "email": "student_dup@gari.vn",
        "password": "Password123!",
        "full_name": "Học sinh Dup"
    })

    # First activation: OK
    r1 = client.post("/api/v1/voucher/activate", json={"code": AUTHORIZED_VOUCHER_CODE})
    assert r1.status_code == 200

    # Second activation: 409 Conflict
    r2 = client.post("/api/v1/voucher/activate", json={"code": AUTHORIZED_VOUCHER_CODE})
    assert r2.status_code == 409
    assert "đã từng kích hoạt" in r2.json()["detail"]
