"""
Tests for Registration Capacity Limit (10 Accounts) & Concurrency Race Resistance
"""
import pytest
from concurrent.futures import ThreadPoolExecutor
from app.models.user import User
from app.config import settings
from starlette.testclient import TestClient
from app.main import app


def test_registration_limit_at_10(client, db_session):
    """Test 2: Exactly 10 accounts can be registered; 11th is rejected."""
    # Register exactly 10 users
    for i in range(1, 11):
        res = client.post("/api/v1/auth/register", json={
            "email": f"farmer_{i}@gari.vn",
            "password": "Password123!",
            "full_name": f"Nông Dân Số {i}"
        })
        assert res.status_code == 201, f"User {i} failed: {res.text}"

    # Verify database count is 10
    count = db_session.query(User).filter(User.account_type != "admin").count()
    assert count == 10

    # Attempt 11th registration -> must be rejected
    res_11 = client.post("/api/v1/auth/register", json={
        "email": "farmer_11@gari.vn",
        "password": "Password123!",
        "full_name": "Nông Dân Số 11"
    })
    assert res_11.status_code == 403
    assert "đã đạt giới hạn thử nghiệm (10 tài khoản)" in res_11.json()["detail"]

    # Verify count remains 10
    assert db_session.query(User).filter(User.account_type != "admin").count() == 10


def test_concurrent_registration_race(db_session):
    """Test 3: 15 concurrent registration requests cannot exceed the 10-account limit."""
    results = []

    def register_worker(index: int):
        with TestClient(app, base_url="http://testserver") as c:
            r = c.post("/api/v1/auth/register", json={
                "email": f"race_farmer_{index}@gari.vn",
                "password": "Password123!",
                "full_name": f"Nông Dân Concurrency {index}"
            })
            return r.status_code

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(register_worker, i) for i in range(1, 16)]
        for f in futures:
            results.append(f.result())

    success_count = sum(1 for code in results if code == 201)
    rejected_count = sum(1 for code in results if code == 403)

    # In database, exactly 10 non-admin accounts must exist
    db_count = db_session.query(User).filter(User.account_type != "admin").count()
    assert db_count == 10, f"Expected exactly 10 users in DB, got {db_count}"
    assert success_count == 10, f"Expected 10 successes, got {success_count}"
    assert rejected_count == 5, f"Expected 5 rejected, got {rejected_count}"
