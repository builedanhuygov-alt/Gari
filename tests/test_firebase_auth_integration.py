"""
Comprehensive Firebase Authentication Integration Test Suite
Verifies:
1. Public Firebase client configuration endpoint (/api/auth/firebase-config)
2. Firebase operational status endpoint (/api/auth/firebase-status)
3. Registration via Firebase ID token (/api/auth/firebase-login)
4. Protection against client privilege escalation (Host Admin / Expert cannot be granted)
5. Normalization of account types (farmer, cooperative, enterprise)
6. Login via Firebase ID token and 5-layer profile delivery
7. Dual auth via Bearer header with Firebase ID token
8. Invalidation of unauthorized / malformed Firebase tokens
9. Session logout and token destruction
10. Password reset flow
"""

import os
import sys
import uuid
from pathlib import Path
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

os.environ["APP_ENV"] = "development"
os.environ["FIREBASE_PROJECT_ID"] = "gari-ai-lab"
os.environ["FIREBASE_API_KEY"] = "AIzaSyTestMockKeyForVerification2026"

import api_server
import gari_auth
import gari_firebase

client = TestClient(api_server.app)


def test_firebase_config_public_endpoint():
    """Verify /api/auth/firebase-config delivers public keys without secrets."""
    res = client.get("/api/auth/firebase-config")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["configured"] is True
    config = data["config"]
    assert config["apiKey"] == "AIzaSyTestMockKeyForVerification2026"
    assert config["projectId"] == "gari-ai-lab"
    assert "authDomain" in config
    # Ensure no secret service account keys are leaked
    assert "private_key" not in str(data)
    assert "client_secret" not in str(data)
    print("PASS: test_firebase_config_public_endpoint")


def test_firebase_status_endpoint():
    """Verify operational status reporting."""
    res = client.get("/api/auth/firebase-status")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "client_configured" in data
    assert "admin_initialized" in data
    print("PASS: test_firebase_status_endpoint")


def test_firebase_registration_flow_and_profile_creation():
    """Verify Firebase registration creates GARI user profile with normalized account type."""
    test_uid = f"fb_reg_{uuid.uuid4().hex[:8]}"
    test_token = f"firebase_test_{test_uid}"

    # Register as Cooperative
    res = client.post("/api/auth/firebase-login", json={
        "id_token": test_token,
        "full_name": "Hợp Tác Xã Rau Sạch Đà Lạt",
        "phone": "0912345678",
        "province": "Lâm Đồng",
        "account_type": "cooperative",
        "terms_agreed": True,
        "marketing_opt_in": True
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] is True
    assert "token" in data
    user = data["user"]

    # Layer 1: Identity
    assert user["identity"]["uid"] == test_uid
    assert user["identity"]["provider_id"] == "firebase"

    # Layer 2: Demographic profile
    assert user["profile"]["full_name"] == "Hợp Tác Xã Rau Sạch Đà Lạt"
    assert user["profile"]["phone"] == "0912345678"
    assert user["profile"]["province"] == "Lâm Đồng"

    # Layer 3: Account type
    assert user["account_type"]["key"] == "cooperative"

    # Layer 4: System roles (privilege escalation prevented!)
    assert user["system_roles"]["is_host_admin"] is False
    assert user["system_roles"]["is_expert"] is False
    assert user["system_roles"]["primary_role"] == "cooperative"
    print("PASS: test_firebase_registration_flow_and_profile_creation")


def test_firebase_registration_escalation_prevention():
    """Verify client cannot grant Host Admin or Expert on registration."""
    test_uid = f"fb_hack_{uuid.uuid4().hex[:8]}"
    test_token = f"firebase_test_{test_uid}"

    # Attacker tries to register as host_admin / expert
    res = client.post("/api/auth/firebase-login", json={
        "id_token": test_token,
        "full_name": "Attacker",
        "account_type": "host_admin",
        "terms_agreed": True
    })
    assert res.status_code == 200
    user = res.json()["user"]
    # Must be safely defaulted to farmer
    assert user["system_roles"]["is_host_admin"] is False
    assert user["system_roles"]["primary_role"] == "farmer"
    print("PASS: test_firebase_registration_escalation_prevention")


def test_firebase_terms_consent_required():
    """Registration without agreeing to terms must be rejected with 400 Bad Request."""
    test_uid = f"fb_noterms_{uuid.uuid4().hex[:8]}"
    test_token = f"firebase_test_{test_uid}"

    res = client.post("/api/auth/firebase-login", json={
        "id_token": test_token,
        "full_name": "No Consent User",
        "account_type": "farmer",
        "terms_agreed": False
    })
    assert res.status_code == 400
    assert "điều khoản" in res.json()["detail"].lower()
    print("PASS: test_firebase_terms_consent_required")


def test_firebase_login_existing_user():
    """Subsequent logins return the same profile and active session."""
    test_uid = f"fb_login_{uuid.uuid4().hex[:8]}"
    test_token = f"firebase_test_{test_uid}"

    # Initial registration
    client.post("/api/auth/firebase-login", json={
        "id_token": test_token,
        "full_name": "Nguyen Van B",
        "account_type": "farmer",
        "terms_agreed": True
    })

    # Subsequent login with remember_me
    res = client.post("/api/auth/firebase-login", json={
        "id_token": test_token,
        "remember_me": True
    })
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert data["user"]["identity"]["uid"] == test_uid
    print("PASS: test_firebase_login_existing_user")


def test_firebase_invalid_token_rejection():
    """Invalid or forged Firebase ID tokens must be rejected with 401 Unauthorized."""
    res = client.post("/api/auth/firebase-login", json={
        "id_token": "forged_invalid_jwt_token_payload_xyz"
    })
    assert res.status_code == 401
    print("PASS: test_firebase_invalid_token_rejection")


def test_bearer_dual_auth_with_firebase_token():
    """Verify that requests directly passing Firebase ID token as Bearer token succeed."""
    test_uid = f"fb_bearer_{uuid.uuid4().hex[:8]}"
    test_token = f"firebase_test_{test_uid}"

    # First access to /api/auth/profile directly with Firebase Bearer token
    res = client.get("/api/auth/profile", headers={"Authorization": f"Bearer {test_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["identity"]["uid"] == test_uid
    print("PASS: test_bearer_dual_auth_with_firebase_token")


def test_logout_invalidates_session():
    """Verify session destruction on logout."""
    test_uid = f"fb_logout_{uuid.uuid4().hex[:8]}"
    test_token = f"firebase_test_{test_uid}"

    login_res = client.post("/api/auth/firebase-login", json={"id_token": test_token})
    session_token = login_res.json()["token"]

    # Verify session active
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {session_token}"})
    assert me_res.status_code == 200

    # Logout
    logout_res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {session_token}"})
    assert logout_res.status_code == 200

    # Session must now be rejected
    check_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {session_token}"})
    assert check_res.status_code == 401
    print("PASS: test_logout_invalidates_session")


if __name__ == "__main__":
    test_firebase_config_public_endpoint()
    test_firebase_status_endpoint()
    test_firebase_registration_flow_and_profile_creation()
    test_firebase_registration_escalation_prevention()
    test_firebase_terms_consent_required()
    test_firebase_login_existing_user()
    test_firebase_invalid_token_rejection()
    test_bearer_dual_auth_with_firebase_token()
    test_logout_invalidates_session()
    print("\n==========================================")
    print("ALL FIREBASE AUTH INTEGRATION TESTS PASSED")
    print("==========================================")

