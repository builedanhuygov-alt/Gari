"""
GARI AI LAB — SPRINT 1/6 ACCEPTANCE TEST SUITE (test_sprint1_core.py)
Automated verification of Startup Core & Productization:
1. Product Architecture & 5 Unified Tiers (No fake prices, clean unlimited quota)
2. Security & RBAC: Admin routes return 403 for regular users, 200 for Platform Admin
3. Prevention of Self-Elevation: Tampering with registration cannot grant Pro/VIP
4. Onboarding Workflow: Persistence of persona, crops, region and entitlement return
5. Usage Metering & Clean Quota: No magic 999999, atomic tracking
6. Leaf Gate Rejection: Zero quota deduction on invalid image
7. Multi-Tenant B2B Isolation: Org A cannot read or modify Org B
8. Frontend pages accessible (onboarding.html, pricing.html, admin.html, index.html)
"""

import io
import json
import os
import sys
import time
from pathlib import Path
from PIL import Image
import requests

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8000"

def test_log(name: str, passed: bool, detail: str = ""):
    mark = "PASS" if passed else "FAIL"
    print(f"[{mark}] {name} {detail}")
    if not passed:
        sys.exit(1)


def test_1_plan_catalog_integrity():
    print("\n--- 1. Testing Centralized Plan Catalog (/api/plans) ---")
    resp = requests.get(f"{BASE_URL}/api/plans", timeout=10)
    test_log("GET /api/plans status", resp.status_code == 200, f"HTTP {resp.status_code}")
    data = resp.json()
    plans = data.get("plans", [])
    test_log("Plans list present", len(plans) >= 5, f"Total plans: {len(plans)}")

    plan_ids = [p["plan_id"] for p in plans]
    for required_id in ["guest", "free", "pro", "team", "enterprise"]:
        test_log(f"Plan tier '{required_id}' present", required_id in plan_ids)

    # Check required fields
    req_fields = [
        "plan_id", "display_name", "description", "billing_interval",
        "price", "currency", "quota_limit", "allowed_features",
        "allowed_models", "max_members", "is_active"
    ]
    catalog = data.get("catalog", {})
    for p in plans:
        for f in req_fields:
            assert f in p, f"Plan {p.get('plan_id')} missing required attribute: {f}"

    # Verify no fake prices: Pro, Team, Enterprise must NOT have fake VND prices
    pro_plan = catalog.get("pro", {})
    team_plan = catalog.get("team", {})
    ent_plan = catalog.get("enterprise", {})
    free_plan = catalog.get("free", {})

    test_log("Pro tier has unconfirmed price in Pilot Beta", pro_plan.get("price") is None and pro_plan.get("price_status") == "pilot_beta")
    test_log("Team tier has unconfirmed price in Pilot Beta", team_plan.get("price") is None and team_plan.get("price_status") == "pilot_beta")
    test_log("Enterprise tier has custom contract pricing", ent_plan.get("price") is None and ent_plan.get("price_status") == "custom_contract")
    test_log("Free tier is 0 VND", free_plan.get("price") == 0 and free_plan.get("price_status") == "free")

    # Verify safe unlimited quota representation (NO 999999)
    test_log("Enterprise quota_limit is None (Safe Unlimited, No 999999)", ent_plan.get("quota_limit") is None and ent_plan.get("is_unlimited_quota") is True)


def test_2_admin_rbac_and_protection():
    print("\n--- 2. Testing Platform Admin RBAC & Route Security ---")
    # 2.1 Unauthenticated requests to admin routes must be rejected (401 or 403)
    resp_unauth = requests.get(f"{BASE_URL}/api/admin/overview", timeout=10)
    test_log("Unauthenticated /api/admin/overview rejected", resp_unauth.status_code in (401, 403), f"HTTP {resp_unauth.status_code}")

    # 2.2 Login as regular user (nongdan.mau@gari.vn)
    login_free = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "nongdan.mau@gari.vn", "password": "FarmerPassword123!"})
    token_free = login_free.json().get("token")
    headers_free = {"Authorization": f"Bearer {token_free}"}

    # Regular user attempting admin routes -> MUST RECEIVE 403 FORBIDDEN
    resp_user_ov = requests.get(f"{BASE_URL}/api/admin/overview", headers=headers_free)
    test_log("Regular user calling /api/admin/overview rejected with 403", resp_user_ov.status_code == 403, f"HTTP {resp_user_ov.status_code}")

    resp_user_met = requests.get(f"{BASE_URL}/api/admin/metrics", headers=headers_free)
    test_log("Regular user calling /api/admin/metrics rejected with 403", resp_user_met.status_code == 403, f"HTTP {resp_user_met.status_code}")

    resp_user_assign = requests.post(
        f"{BASE_URL}/api/admin/plans/assign",
        headers=headers_free,
        json={"user_id": 1, "plan_id": "enterprise"}
    )
    test_log("Regular user calling /api/admin/plans/assign rejected with 403", resp_user_assign.status_code == 403, f"HTTP {resp_user_assign.status_code}")

    # 2.3 Login as Platform Admin (danhuynh@gari.vn)
    login_admin = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "danhuynh@gari.vn", "password": "Password123!"})
    test_log("Platform Admin login", login_admin.status_code == 200)
    token_admin = login_admin.json().get("token")
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    # Admin calls /api/admin/overview -> MUST RETURN 200 OK with real DB metrics
    resp_admin_ov = requests.get(f"{BASE_URL}/api/admin/overview", headers=headers_admin)
    test_log("Admin calling /api/admin/overview authorized", resp_admin_ov.status_code == 200, f"HTTP {resp_admin_ov.status_code}")
    ov_data = resp_admin_ov.json().get("overview", {})
    assert "total_users" in ov_data and ov_data["total_users"] > 0
    assert "total_diagnoses" in ov_data
    assert "total_organizations" in ov_data
    test_log("Admin overview data integrity", True, f"Users: {ov_data['total_users']}, Orgs: {ov_data['total_organizations']}, Diags: {ov_data['total_diagnoses']}")

    # Admin calls /api/admin/metrics -> MUST RETURN 200 OK
    resp_admin_met = requests.get(f"{BASE_URL}/api/admin/metrics", headers=headers_admin)
    test_log("Admin calling /api/admin/metrics authorized", resp_admin_met.status_code == 200)
    met_data = resp_admin_met.json()
    assert "plan_usage" in met_data
    assert "diagnosis_telemetry" in met_data

    # Admin assigns plan to user with Audit Trail
    resp_assign = requests.post(
        f"{BASE_URL}/api/admin/plans/assign",
        headers=headers_admin,
        json={
            "user_id": 7, # nongdan.mau@gari.vn
            "plan_id": "pro",
            "status": "pilot_active",
            "notes": "Cấp quyền thử nghiệm Kỹ sư Pro trong Sprint 1"
        }
    )
    test_log("Admin assigns Pro plan to User #7", resp_assign.status_code == 200, f"HTTP {resp_assign.status_code}")

    # Check Audit Logs
    resp_audit = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=headers_admin)
    test_log("Admin fetches /api/admin/audit-logs", resp_audit.status_code == 200)
    audit_logs = resp_audit.json().get("audit_logs", [])
    test_log("Audit logs recorded event", len(audit_logs) > 0, f"Total logs: {len(audit_logs)}")

    # Reset User #7 back to 'free' plan to preserve clean baseline for other test suites
    requests.post(
        f"{BASE_URL}/api/admin/plans/assign",
        headers=headers_admin,
        json={"user_id": 7, "plan_id": "free", "status": "active", "notes": "Hoàn nguyên về Free sau kiểm thử"}
    )


def test_3_prevention_of_self_elevation():
    print("\n--- 3. Testing Prevention of Self-Elevation via Tampering ---")
    # Attacker tries to register and pass 'VIP' or 'Đơn vị dịch vụ nông nghiệp'
    fake_email = f"attacker_{int(time.time())}@test.vn"
    resp_reg = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={
            "full_name": "Kẻ Tấn Công Thử Nâng Quyền",
            "email": fake_email,
            "password": "AttackerPass123!",
            "confirm_password": "AttackerPass123!",
            "account_type": "Đơn vị dịch vụ nông nghiệp", # Trying to self-elevate
            "terms_agreed": True
        }
    )
    test_log("Registration succeeds", resp_reg.status_code == 200)
    token_attacker = resp_reg.json().get("token")
    headers_attacker = {"Authorization": f"Bearer {token_attacker}"}

    # Fetch quota: MUST be free tier (5 turns, is_vip=False), NOT Pro or VIP!
    resp_q = requests.get(f"{BASE_URL}/api/user/quota", headers=headers_attacker)
    q_data = resp_q.json().get("quota", {})
    test_log("User cannot self-elevate to VIP via registration", q_data.get("is_vip") is False, f"is_vip={q_data.get('is_vip')}")
    test_log("Quota limit remains free tier (5 turns)", q_data.get("quota_limit") == 5, f"limit={q_data.get('quota_limit')}")


def test_4_user_onboarding_workflow():
    print("\n--- 4. Testing Business Onboarding Workflow ---")
    # Login farmer
    login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "nongdan.mau@gari.vn", "password": "FarmerPassword123!"})
    token = login_resp.json().get("token")
    headers = {"Authorization": f"Bearer {token}"}

    # Submit onboarding profile
    payload = {
        "persona_type": "smallholder",
        "primary_crops": ["Rice", "Tomato", "Pepper"],
        "farming_region": "Đồng bằng sông Cửu Long",
        "farming_scale": "1 - 5 ha"
    }
    resp_post = requests.post(f"{BASE_URL}/api/user/onboarding", headers=headers, json=payload)
    test_log("POST /api/user/onboarding status", resp_post.status_code == 200, f"HTTP {resp_post.status_code}")
    res = resp_post.json()
    assert res.get("profile") is not None
    assert "entitlement" in res

    # Retrieve onboarding profile
    resp_get = requests.get(f"{BASE_URL}/api/user/onboarding", headers=headers)
    test_log("GET /api/user/onboarding status", resp_get.status_code == 200)
    profile = resp_get.json().get("profile", {})
    test_log("Persona preserved", profile.get("persona_type") == "smallholder")
    test_log("Crops preserved", "Rice" in profile.get("primary_crops", []))
    test_log("Region preserved", profile.get("farming_region") == "Đồng bằng sông Cửu Long")


def test_5_quota_metering_and_no_999999():
    print("\n--- 5. Testing Metering & Safe Unlimited Quota (No 999999) ---")
    resp = requests.get(f"{BASE_URL}/api/user/quota")
    q = resp.json().get("quota", {})
    # Check that remaining is not 999999
    assert q.get("remaining") != 999999, f"Quota must not use 999999! Value={q.get('remaining')}"
    test_log("Guest quota representation is clean", q.get("quota_limit") == 3 and q.get("remaining") <= 3)


def test_6_leaf_gate_rejection_zero_quota_deduct():
    print("\n--- 6. Testing Leaf Gate Rejection: Zero Quota Deduction ---")
    # Solid black image (clearly not a leaf)
    img = Image.new("RGB", (256, 256), color=(10, 10, 10))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    test_client = f"gate_test_{int(time.time())}"
    headers = {"X-Client-Id": test_client}

    # Quota before
    s = requests.Session()
    q_before = s.get(f"{BASE_URL}/api/user/quota", headers=headers).json()["quota"]["remaining"]

    # Submit non-leaf image
    files = {"image": ("non_leaf.jpg", buf, "image/jpeg")}
    data = {"mode": "auto_standard"}
    resp = s.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=data, headers=headers)
    test_log("Diagnose non-leaf image status", resp.status_code == 200)
    res = resp.json()
    val = res.get("validation", {})
    test_log("Leaf Gate rejection status", val.get("status") in ["NOT_A_LEAF", "UNCERTAIN", "IMAGE_QUALITY_LOW"])

    # Quota after
    q_after = s.get(f"{BASE_URL}/api/user/quota", headers=headers).json()["quota"]["remaining"]
    test_log("Zero Quota Deduction on Rejection", q_before == q_after, f"Before={q_before}, After={q_after}")


def test_7_multi_tenant_isolation():
    print("\n--- 7. Testing Multi-Tenant B2B Isolation ---")
    # Login user 1 (owner of org 1)
    login1 = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "danhuynh@gari.vn", "password": "Password123!"})
    token1 = login1.json().get("token")
    headers1 = {"Authorization": f"Bearer {token1}"}

    # Create Org A
    org_a = requests.post(
        f"{BASE_URL}/api/organizations",
        headers=headers1,
        json={"name": f"Hợp Tác Xã Cô Đơn {int(time.time())}", "plan_id": "team"}
    ).json().get("organization")
    org_a_id = org_a["id"]

    # Login user 2 (nongdan.mau@gari.vn)
    login2 = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "nongdan.mau@gari.vn", "password": "FarmerPassword123!"})
    token2 = login2.json().get("token")
    headers2 = {"Authorization": f"Bearer {token2}"}

    # User 2 tries to read Org A details -> MUST BE 403 Forbidden!
    resp_read = requests.get(f"{BASE_URL}/api/organizations/{org_a_id}", headers=headers2)
    test_log("Tenant Isolation: User 2 cannot access Org A details", resp_read.status_code == 403, f"HTTP {resp_read.status_code}")

    # User 2 tries to add member to Org A -> MUST BE 403 Forbidden!
    resp_invite = requests.post(
        f"{BASE_URL}/api/organizations/{org_a_id}/members",
        headers=headers2,
        json={"email": "intruder@test.vn", "role": "member"}
    )
    test_log("Tenant Isolation: User 2 cannot modify Org A membership", resp_invite.status_code == 403, f"HTTP {resp_invite.status_code}")


def test_8_frontend_routes_accessibility():
    print("\n--- 8. Testing Frontend Pages Accessibility ---")
    routes = [
        "/frontend2/onboarding.html",
        "/frontend2/pricing.html",
        "/frontend2/admin.html",
        "/frontend2/index.html",
        "/frontend2/predict.html"
    ]
    for r in routes:
        resp = requests.get(f"{BASE_URL}{r}", timeout=10)
        test_log(f"Page GET {r}", resp.status_code == 200, f"HTTP {resp.status_code}")


if __name__ == "__main__":
    print("=============================================================")
    print("   GARI AI LAB — SPRINT 1/6 ACCEPTANCE TEST SUITE           ")
    print("=============================================================")
    test_1_plan_catalog_integrity()
    test_2_admin_rbac_and_protection()
    test_3_prevention_of_self_elevation()
    test_4_user_onboarding_workflow()
    test_5_quota_metering_and_no_999999()
    test_6_leaf_gate_rejection_zero_quota_deduct()
    test_7_multi_tenant_isolation()
    test_8_frontend_routes_accessibility()
    print("\n=============================================================")
    print("   ALL SPRINT 1 ACCEPTANCE TESTS PASSED SUCCESSFULLY!       ")
    print("=============================================================\n")
