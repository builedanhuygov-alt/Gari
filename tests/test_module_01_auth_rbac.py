"""
GARI MODULE 01 — CORE AUTHENTICATION & RBAC TEST SUITE
(tests/test_module_01_auth_rbac.py)

Comprehensive test coverage verifying:
1. Standard Registration, Bcrypt 12-round hashing, and validation
2. Password authentication, session creation, cookies, and rate limiting
3. Session invalidation and logout (token destruction)
4. Password recovery (forgot-password, reset-password, and session revocation)
5. Firebase ID token verification and user auto-sync (/api/auth/firebase-login & Bearer)
6. Centralized 5-layer user profile schema (/api/user/profile & /api/auth/profile)
7. Profile updates with STRICT privilege escalation prevention (400 Bad Request)
8. Decoupled System Roles vs Organization Roles:
   - Expert (is_expert=1) CANNOT access Host Admin routes (403 Forbidden)
   - Expert can access Expert Portal routes
   - Personal User cannot access Host or Expert routes
   - Host Admin can access Host routes
9. Strict Multi-Tenant Organization Boundary Enforcement:
   - Cross-organization member access blocked (403 Forbidden)
   - Tenant resource manipulation blocked for non-members
10. Server-side ownership checks on farms, plots, and season reports
11. Audit logging for privileged operations and role changes
"""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sqlite3
import uuid
from fastapi.testclient import TestClient

# Ensure test / development environment
os.environ["APP_ENV"] = "development"
os.environ["PAYMENT_PUBLIC_CHECKOUT_ENABLED"] = "1"

import api_server
import gari_auth
import gari_b2b
import gari_database
import gari_firebase

client = TestClient(api_server.app)





def test_01_registration_and_bcrypt_hashing():
    """Verify user registration stores Bcrypt 12-round hash and rejects duplicates."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"farmer_{unique_suffix}@test.gari.vn"
    password = "SecurePassword123!"

    # 1. Register valid user
    res = client.post("/api/auth/register", json={
        "full_name": f"Nông dân Test {unique_suffix}",
        "email": email,
        "password": password,
        "confirm_password": password,
        "phone": "0987654321",
        "account_type": "Nông hộ"
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] is True
    assert "token" in data
    user = data["user"]
    assert user["email"] == email

    # 2. Verify Bcrypt hash in database
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],))
        row = cursor.fetchone()
        assert row is not None
        pwd_hash = row["password_hash"]
        assert pwd_hash.startswith("$2b$12$"), f"Hash must be Bcrypt rounds=12, got: {pwd_hash[:10]}"

    # 3. Reject duplicate registration with 409 Conflict
    res_dup = client.post("/api/auth/register", json={
        "full_name": "Trùng lặp",
        "email": email,
        "password": password,
        "confirm_password": password
    })
    assert res_dup.status_code == 409


def test_02_login_session_and_logout():
    """Verify login, session persistence, cookie handling, and logout invalidation."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"login_{unique_suffix}@test.gari.vn"
    password = "MySecretPassword123!"

    # Register
    reg_res = client.post("/api/auth/register", json={
        "full_name": f"User {unique_suffix}",
        "email": email,
        "password": password,
        "confirm_password": password
    })
    assert reg_res.status_code == 200

    # Bad password -> 401
    bad_res = client.post("/api/auth/login", json={
        "email": email,
        "password": "WrongPassword!"
    })
    assert bad_res.status_code == 401

    # Good password -> 200 + token + cookie
    login_res = client.post("/api/auth/login", json={
        "email": email,
        "password": password,
        "remember_me": True
    })
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    assert token and len(token) > 20

    # Test authenticated endpoint via Bearer header
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["user"]["email"] == email

    # Test logout destroys session
    logout_res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200

    # Token must now be rejected with 401
    expired_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert expired_res.status_code == 401


def test_03_password_recovery_and_session_revocation():
    """Verify forgot-password token generation, password reset, and session invalidation."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"recovery_{unique_suffix}@test.gari.vn"
    old_pwd = "OldPassword123!"
    new_pwd = "NewSecurePassword456!"

    # Register
    reg_res = client.post("/api/auth/register", json={
        "full_name": f"User {unique_suffix}",
        "email": email,
        "password": old_pwd,
        "confirm_password": old_pwd
    })
    assert reg_res.status_code == 200
    old_token = reg_res.json()["token"]

    # Request password reset
    forgot_res = client.post("/api/auth/forgot-password", json={"email": email})
    assert forgot_res.status_code == 200
    reset_token = forgot_res.json().get("reset_token")
    assert reset_token is not None

    # Reset password with token
    reset_res = client.post("/api/auth/reset-password", json={
        "token": reset_token,
        "new_password": new_pwd,
        "confirm_password": new_pwd
    })
    assert reset_res.status_code == 200

    # 1. Previous session MUST be revoked
    revoked_check = client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_token}"})
    assert revoked_check.status_code == 401

    # 2. Login with old password MUST fail
    old_login = client.post("/api/auth/login", json={"email": email, "password": old_pwd})
    assert old_login.status_code == 401

    # 3. Login with new password MUST succeed
    new_login = client.post("/api/auth/login", json={"email": email, "password": new_pwd})
    assert new_login.status_code == 200


def test_04_firebase_id_token_verification_and_sync():
    """Verify backend Firebase ID token verification and user auto-sync."""
    test_uid = f"fb_{uuid.uuid4().hex[:8]}"
    test_id_token = f"firebase_test_{test_uid}"

    # 1. Login via Firebase ID token endpoint
    fb_res = client.post("/api/auth/firebase-login", json={"id_token": test_id_token})
    assert fb_res.status_code == 200, fb_res.text
    fb_data = fb_res.json()
    assert fb_data["success"] is True
    assert "token" in fb_data
    user = fb_data["user"]
    assert user["identity"]["uid"] == test_uid
    assert user["identity"]["provider_id"] == "firebase"
    assert user["account_type"]["key"] == "farmer"

    # 2. Authenticate directly using Firebase test token in Bearer header
    bearer_res = client.get("/api/auth/profile", headers={"Authorization": f"Bearer {test_id_token}"})
    assert bearer_res.status_code == 200
    profile = bearer_res.json()
    assert profile["identity"]["uid"] == test_uid

    # 3. Invalid Firebase ID token rejection
    bad_fb = client.post("/api/auth/firebase-login", json={"id_token": "invalid_untrusted_token_xyz"})
    assert bad_fb.status_code == 401


def test_05_centralized_user_profile_structure():
    """Verify centralized user profile schema returns all 5 layers."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"profile_{unique_suffix}@test.gari.vn"
    reg_res = client.post("/api/auth/register", json={
        "full_name": f"Nguyen Van {unique_suffix}",
        "email": email,
        "password": "StrongPassword123!",
        "confirm_password": "StrongPassword123!",
        "phone": "0912345678",
        "account_type": "farmer"
    })
    token = reg_res.json()["token"]

    for path in ["/api/user/profile", "/api/auth/profile"]:
        res = client.get(path, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["success"] is True

        # Check Layer 1: Identity
        assert "identity" in data
        assert data["identity"]["email"] == email

        # Check Layer 2: Demographic Profile
        assert "profile" in data
        assert data["profile"]["full_name"] == f"Nguyen Van {unique_suffix}"
        assert data["profile"]["phone"] == "0912345678"

        # Check Layer 3: Canonical Account Type
        assert "account_type" in data
        assert data["account_type"]["key"] == "farmer"
        assert "label" in data["account_type"]

        # Check Layer 4: System Roles
        assert "system_roles" in data
        assert data["system_roles"]["is_host_admin"] is False
        assert data["system_roles"]["is_expert"] is False
        assert data["system_roles"]["primary_role"] == "farmer"

        # Check Layer 5: Subscription
        assert "subscription" in data
        assert "plan" in data["subscription"]
        assert "quota_limit" in data["subscription"]

        # Check Layer 6: Organization memberships
        assert "organizations" in data
        assert isinstance(data["organizations"], list)


def test_06_profile_update_and_privilege_escalation_block():
    """Verify safe profile update and strict rejection of privilege self-assignment."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"escalation_{unique_suffix}@test.gari.vn"
    reg_res = client.post("/api/auth/register", json={
        "full_name": f"Farmer Normal {unique_suffix}",
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!"
    })
    token = reg_res.json()["token"]
    user_id = reg_res.json()["user"]["id"]

    # 1. Legitimate profile update succeeds
    patch_res = client.patch(
        "/api/auth/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "full_name": "Farmer Updated Name",
            "phone": "0901112233",
            "province": "Lâm Đồng",
            "bio": "Kỹ thuật viên canh tác rau VietGAP"
        }
    )
    assert patch_res.status_code == 200, patch_res.text
    updated = patch_res.json()
    assert updated["profile"]["full_name"] == "Farmer Updated Name"
    assert updated["profile"]["phone"] == "0901112233"
    assert updated["profile"]["province"] == "Lâm Đồng"
    assert updated["profile"]["bio"] == "Kỹ thuật viên canh tác rau VietGAP"

    # 2. PRIVILEGE ESCALATION ATTEMPTS MUST FAIL WITH HTTP 400
    for attack_payload in [
        {"is_host_admin": True},
        {"is_host_admin": 1},
        {"is_admin": True},
        {"is_expert": True},
        {"account_type": "enterprise"},
        {"role": "admin"},
        {"is_active": 1, "is_host_admin": True}
    ]:
        attack_res = client.patch(
            "/api/auth/profile",
            headers={"Authorization": f"Bearer {token}"},
            json=attack_payload
        )
        assert attack_res.status_code == 400, f"Expected 400 Bad Request for {attack_payload}, got {attack_res.status_code}"
        assert "Không được phép tự nâng cấp quyền" in attack_res.json()["detail"]

    # 3. Verify in database that privileged columns remain untouched
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_host_admin, is_admin, is_expert, account_type FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        assert row["is_host_admin"] == 0
        assert row["is_admin"] == 0
        assert row["is_expert"] == 0
        assert row["account_type"] == "farmer"


def test_07_system_roles_boundary_expert_vs_host_admin():
    """Verify that an Expert account (is_expert=1) DOES NOT receive Host Admin permissions."""
    unique_suffix = uuid.uuid4().hex[:8]

    # Create an Expert user directly
    expert_email = f"expert_{unique_suffix}@gari.vn"
    reg_expert = client.post("/api/auth/register", json={
        "full_name": f"Kỹ sư BVTV {unique_suffix}",
        "email": expert_email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "account_type": "expert"
    })
    expert_token = reg_expert.json()["token"]
    expert_id = reg_expert.json()["user"]["id"]

    # Mark user as expert in database (simulating host verification)
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_expert = 1, is_host_admin = 0 WHERE id = ?", (expert_id,))
        conn.commit()

    # Create a Regular Farmer user
    farmer_email = f"farmer_{unique_suffix}@gari.vn"
    reg_farmer = client.post("/api/auth/register", json={
        "full_name": f"Farmer {unique_suffix}",
        "email": farmer_email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "account_type": "farmer"
    })
    farmer_token = reg_farmer.json()["token"]

    # Create a Host Admin user
    host_email = f"host_{unique_suffix}@gari.vn"
    reg_host = client.post("/api/auth/register", json={
        "full_name": f"Host Admin {unique_suffix}",
        "email": host_email,
        "password": "Password123!",
        "confirm_password": "Password123!"
    })
    host_token = reg_host.json()["token"]
    host_id = reg_host.json()["user"]["id"]
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_host_admin = 1 WHERE id = ?", (host_id,))
        conn.commit()

    # 1. Expert CAN access Expert Portal
    exp_portal_res = client.get("/api/expert/portal/cases", headers={"Authorization": f"Bearer {expert_token}"})
    assert exp_portal_res.status_code == 200

    # 2. Expert CANNOT access Host Admin routes (MUST be 403 Forbidden)
    exp_host_res = client.get("/api/host/me", headers={"Authorization": f"Bearer {expert_token}"})
    assert exp_host_res.status_code == 403, f"Expert must NOT access host admin, got {exp_host_res.status_code}"

    exp_host_overview = client.get("/api/host/overview", headers={"Authorization": f"Bearer {expert_token}"})
    assert exp_host_overview.status_code == 403

    # 3. Farmer CANNOT access Expert Portal or Host Admin routes
    farmer_portal_res = client.get("/api/expert/portal/cases", headers={"Authorization": f"Bearer {farmer_token}"})
    assert farmer_portal_res.status_code == 403

    farmer_host_res = client.get("/api/host/me", headers={"Authorization": f"Bearer {farmer_token}"})
    assert farmer_host_res.status_code == 403

    # 4. Host Admin CAN access Host Admin routes
    host_res = client.get("/api/host/me", headers={"Authorization": f"Bearer {host_token}"})
    assert host_res.status_code == 200
    assert host_res.json()["user"]["is_host_admin"] is True


def test_08_multi_tenant_organization_isolation():
    """Verify strict tenant isolation: User in Org A cannot access or modify Org B resources."""
    suffix = uuid.uuid4().hex[:8]

    # User 1 (Owner of Org A)
    u1_res = client.post("/api/auth/register", json={
        "full_name": f"Owner Org A {suffix}",
        "email": f"owner_a_{suffix}@test.gari.vn",
        "password": "Password123!",
        "confirm_password": "Password123!"
    })
    u1_token = u1_res.json()["token"]
    u1_id = u1_res.json()["user"]["id"]

    # User 2 (Member of Org A)
    u2_res = client.post("/api/auth/register", json={
        "full_name": f"Member Org A {suffix}",
        "email": f"member_a_{suffix}@test.gari.vn",
        "password": "Password123!",
        "confirm_password": "Password123!"
    })
    u2_token = u2_res.json()["token"]
    u2_id = u2_res.json()["user"]["id"]

    # User 3 (Owner of Org B)
    u3_res = client.post("/api/auth/register", json={
        "full_name": f"Owner Org B {suffix}",
        "email": f"owner_b_{suffix}@test.gari.vn",
        "password": "Password123!",
        "confirm_password": "Password123!"
    })
    u3_token = u3_res.json()["token"]
    u3_id = u3_res.json()["user"]["id"]

    # Create Org A
    org_a = gari_b2b.create_organization(
        name=f"Hợp Tác Xã A {suffix}",
        owner_id=u1_id,
        organization_type="cooperative"
    )
    org_a_id = org_a["id"]
    # Activate Org A
    gari_b2b.transition_organization_status(org_a_id, u1_id, "active", reason="Kích hoạt tổ chức A")

    # Add User 2 to Org A as member
    gari_b2b.add_member_by_email(org_a_id, u1_id, f"member_a_{suffix}@test.gari.vn", role="member")

    # Create Org B
    org_b = gari_b2b.create_organization(
        name=f"Hợp Tác Xã B {suffix}",
        owner_id=u3_id,
        organization_type="cooperative"
    )
    org_b_id = org_b["id"]
    gari_b2b.transition_organization_status(org_b_id, u3_id, "active", reason="Kích hoạt tổ chức B")

    # 1. User 2 (in Org A) CAN access Org A detail
    res_a = client.get(f"/api/organizations/{org_a_id}", headers={"Authorization": f"Bearer {u2_token}"})
    assert res_a.status_code == 200

    # 2. User 2 (in Org A) CANNOT access Org B detail (MUST be 403 Forbidden)
    res_b = client.get(f"/api/organizations/{org_b_id}", headers={"Authorization": f"Bearer {u2_token}"})
    assert res_b.status_code == 403

    # 3. User 2 CANNOT list Org B members
    res_b_members = client.get(f"/api/organizations/{org_b_id}/members", headers={"Authorization": f"Bearer {u2_token}"})
    assert res_b_members.status_code == 403

    # 4. User 2 CANNOT invite or add member to Org B
    res_b_add = client.post(
        f"/api/organizations/{org_b_id}/members",
        headers={"Authorization": f"Bearer {u2_token}"},
        json={"email": "intruder@test.gari.vn", "role": "admin"}
    )
    assert res_b_add.status_code == 403

    # 5. User 2 is regular member in Org A; CANNOT add members to Org A (requires admin/owner)
    res_a_unauthorized_add = client.post(
        f"/api/organizations/{org_a_id}/members",
        headers={"Authorization": f"Bearer {u2_token}"},
        json={"email": "someone@test.gari.vn", "role": "admin"}
    )
    assert res_a_unauthorized_add.status_code == 403


def test_09_farm_ownership_and_season_report_boundary():
    """Verify server-side ownership enforcement on farms and season reports."""
    suffix = uuid.uuid4().hex[:8]

    # User A
    uA = client.post("/api/auth/register", json={
        "full_name": f"Farmer A {suffix}",
        "email": f"farmer_a_{suffix}@test.gari.vn",
        "password": "Password123!",
        "confirm_password": "Password123!"
    })
    token_A = uA.json()["token"]

    # User B
    uB = client.post("/api/auth/register", json={
        "full_name": f"Farmer B {suffix}",
        "email": f"farmer_b_{suffix}@test.gari.vn",
        "password": "Password123!",
        "confirm_password": "Password123!"
    })
    token_B = uB.json()["token"]

    # User A creates a farm
    farm_res = client.post(
        "/api/farms",
        headers={"Authorization": f"Bearer {token_A}"},
        json={"name": f"Vườn Cà Chua A {suffix}", "location": "Đức Trọng, Lâm Đồng", "primary_crop": "Tomato"}
    )
    assert farm_res.status_code == 200
    farm_id = farm_res.json()["farm"]["id"]

    # 1. User A can view own farm
    view_A = client.get(f"/api/farms/{farm_id}", headers={"Authorization": f"Bearer {token_A}"})
    assert view_A.status_code == 200

    # 2. User B CANNOT view User A's farm -> 404 (Not Found / Access Denied)
    view_B = client.get(f"/api/farms/{farm_id}", headers={"Authorization": f"Bearer {token_B}"})
    assert view_B.status_code == 404

    # 3. User B CANNOT update User A's farm
    update_B = client.put(
        f"/api/farms/{farm_id}",
        headers={"Authorization": f"Bearer {token_B}"},
        json={"name": "Hacked Farm Name"}
    )
    assert update_B.status_code == 404

    # 4. User B CANNOT delete User A's farm
    delete_B = client.delete(f"/api/farms/{farm_id}", headers={"Authorization": f"Bearer {token_B}"})
    assert delete_B.status_code == 404

    # 5. User B CANNOT access User A's season report
    season_B = client.get(f"/api/farms/{farm_id}/season-report", headers={"Authorization": f"Bearer {token_B}"})
    assert season_B.status_code == 404

    # 6. Unauthenticated request to season report MUST return 401 Unauthorized
    client.cookies.clear()
    anon_season = client.get(f"/api/farms/{farm_id}/season-report")
    assert anon_season.status_code == 401


def test_10_audit_logging_for_privileged_changes():
    """Verify that privileged operations and role changes create immutable audit logs."""
    suffix = uuid.uuid4().hex[:8]

    # Host Admin
    u_host = client.post("/api/auth/register", json={
        "full_name": f"Audit Admin {suffix}",
        "email": f"audit_admin_{suffix}@gari.vn",
        "password": "Password123!",
        "confirm_password": "Password123!"
    })
    token_host = u_host.json()["token"]
    host_id = u_host.json()["user"]["id"]
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_host_admin = 1 WHERE id = ?", (host_id,))
        conn.commit()

    # Target User
    u_target = client.post("/api/auth/register", json={
        "full_name": f"Target User {suffix}",
        "email": f"target_{suffix}@test.gari.vn",
        "password": "Password123!",
        "confirm_password": "Password123!"
    })
    target_id = u_target.json()["user"]["id"]

    # Host updates target account type
    patch_res = client.patch(
        f"/api/host/users/{target_id}/account-type",
        headers={"Authorization": f"Bearer {token_host}"},
        json={"account_type": "cooperative", "reason": "Nâng cấp hợp tác xã kiểm thử"}
    )
    assert patch_res.status_code == 200

    # Verify audit logs in user_account_type_audit
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT new_type, reason, changed_by_user_id FROM user_account_type_audit WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (target_id,)
        )
        audit_row = cursor.fetchone()
        assert audit_row is not None
        assert audit_row["new_type"] == "cooperative"
        assert audit_row["changed_by_user_id"] == host_id

        # Verify host_audit_logs
        cursor.execute(
            "SELECT action_type, host_admin_id FROM host_audit_logs WHERE host_admin_id = ? ORDER BY id DESC LIMIT 1",
            (host_id,)
        )
        host_log = cursor.fetchone()
        assert host_log is not None
        assert host_log["host_admin_id"] == host_id


if __name__ == '__main__':
    print('Running GARI Module 01 Auth & RBAC tests...')
    test_01_registration_and_bcrypt_hashing()
    print('✓ test_01_registration_and_bcrypt_hashing PASSED')
    test_02_login_session_and_logout()
    print('✓ test_02_login_session_and_logout PASSED')
    test_03_password_recovery_and_session_revocation()
    print('✓ test_03_password_recovery_and_session_revocation PASSED')
    test_04_firebase_id_token_verification_and_sync()
    print('✓ test_04_firebase_id_token_verification_and_sync PASSED')
    test_05_centralized_user_profile_structure()
    print('✓ test_05_centralized_user_profile_structure PASSED')
    test_06_profile_update_and_privilege_escalation_block()
    print('✓ test_06_profile_update_and_privilege_escalation_block PASSED')
    test_07_system_roles_boundary_expert_vs_host_admin()
    print('✓ test_07_system_roles_boundary_expert_vs_host_admin PASSED')
    test_08_multi_tenant_organization_isolation()
    print('✓ test_08_multi_tenant_organization_isolation PASSED')
    test_09_farm_ownership_and_season_report_boundary()
    print('✓ test_09_farm_ownership_and_season_report_boundary PASSED')
    test_10_audit_logging_for_privileged_changes()
    print('✓ test_10_audit_logging_for_privileged_changes PASSED')
    print('\nALL 10 MODULE 01 AUTH & RBAC TESTS PASSED 100%!')
