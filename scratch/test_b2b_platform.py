"""
Acceptance Test Suite for Gari AgriTech B2B SaaS, Multi-Tenant & API-as-a-Service Platform.
Verifies all items in G. ACCEPTANCE TESTS:
1. Multi-tenant isolation (Unauthorized user blocked from other organization).
2. RBAC enforcement (Member cannot promote themselves or delete admin/owner).
3. Concurrency-safe quota metering (Parallel requests cannot drive quota negative).
4. VIP Model routing (Organization with Team plan can call VIP models; Free blocked).
5. API Key lifecycle & Revocation (Active key works, revoked key returns 401).
6. Usage metering audit (Records reflect model, crop, latency, quota deducted).
7. Zero quota deduction on rejected photos.
8. Frontend B2B routes accessibility (Organization, Pricing, API Docs, Plans catalog).
"""

import concurrent.futures
import io
import json
import sys
from pathlib import Path
from PIL import Image
import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8000"

def log_test(name, success, detail=""):
    mark = "PASS" if success else "FAIL"
    print(f"[{mark}] {name} {detail}")
    if not success:
        sys.exit(1)

def get_auth_token(email, password):
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    return resp.json()["token"]

def test_frontend_b2b_routes():
    print("\n--- 1. Testing B2B Frontend Routes & Plan Catalog ---")
    routes = [
        "/frontend2/organization.html",
        "/frontend2/pricing.html",
        "/frontend2/api-docs.html",
        "/api/plans"
    ]
    for r in routes:
        resp = requests.get(f"{BASE_URL}{r}", timeout=10)
        log_test(f"Route GET {r}", resp.status_code == 200, f"HTTP {resp.status_code}")

    resp_plans = requests.get(f"{BASE_URL}/api/plans").json()
    plans = resp_plans.get("plans", [])
    plan_ids = [p.get("id") or p.get("plan_id") for p in plans]
    log_test("Plan Catalog 4 Tiers Check", {"free", "pro", "team", "enterprise"}.issubset(set(plan_ids)), f"Tiers={plan_ids}")

def test_multi_tenant_isolation_and_rbac():
    print("\n--- 2. Testing Multi-Tenant Isolation & RBAC ---")
    token_owner = get_auth_token("danhuynh@gari.vn", "Password123!") # User 1 (Owner of Org 1)
    token_farmer = get_auth_token("nongdan.mau@gari.vn", "FarmerPassword123!") # User 7 (Member of Org 1)
    
    # Create an isolated organization for User 7
    hdr_farmer = {"Authorization": f"Bearer {token_farmer}"}
    resp_create = requests.post(
        f"{BASE_URL}/api/organizations",
        json={"name": "Trang Trại Rau Sạch Nông Dân 7", "plan_id": "team"},
        headers=hdr_farmer
    )
    log_test("Farmer creates Org 2", resp_create.status_code == 200)
    farmer_org_id = resp_create.json()["organization"]["id"]

    # 1. Isolation check: User 1 (danhuynh) attempts to access Farmer's Org 2 without membership -> Blocked 403
    hdr_owner = {"Authorization": f"Bearer {token_owner}"}
    resp_unauthorized = requests.get(f"{BASE_URL}/api/organizations/{farmer_org_id}", headers=hdr_owner)
    log_test("Cross-Tenant Access Blocked (403)", resp_unauthorized.status_code == 403, f"HTTP {resp_unauthorized.status_code}")

    # 2. RBAC check: Farmer (User 7 is only a 'member' in Org 1) attempts to add a member or change role in Org 1 -> Blocked 403
    resp_unauth_add = requests.post(
        f"{BASE_URL}/api/organizations/1/members",
        json={"email": "hacker@test.vn", "role": "admin"},
        headers=hdr_farmer
    )
    log_test("Member cannot add members to Org (403)", resp_unauth_add.status_code == 403, f"HTTP {resp_unauth_add.status_code}")

    # 3. RBAC check: Farmer attempts to delete Owner (User 1) from Org 1 -> Blocked 403
    resp_unauth_del = requests.delete(f"{BASE_URL}/api/organizations/1/members/1", headers=hdr_farmer)
    log_test("Member cannot remove Owner from Org (403)", resp_unauth_del.status_code == 403, f"HTTP {resp_unauth_del.status_code}")

def test_api_key_lifecycle_and_service():
    print("\n--- 3. Testing API-as-a-Service & API Key Lifecycle ---")
    token_owner = get_auth_token("danhuynh@gari.vn", "Password123!")
    hdr_owner = {"Authorization": f"Bearer {token_owner}"}

    # 1. Generate new API Key
    resp_gen = requests.post(
        f"{BASE_URL}/api/organizations/1/api-keys",
        json={"key_name": "Acceptance Test Key Drone v1", "rate_limit_rpm": 60},
        headers=hdr_owner
    )
    log_test("Generate API Key", resp_gen.status_code == 200)
    key_data = resp_gen.json()["api_key"]
    full_api_key = key_data["full_key"]
    key_id = key_data["id"]
    log_test("Full key format check", full_api_key.startswith("gari_live_"), f"Prefix={key_data['key_prefix']}")

    # 2. Call Standardized API Endpoint POST /api/v1/diagnose with the new key
    test_leaf = Path("test_leaf.jpg")
    if not test_leaf.exists():
        img = Image.new("RGB", (224, 224), color=(34, 139, 34))
        img.save("test_leaf.jpg")

    with open("test_leaf.jpg", "rb") as f:
        files = {"image": ("leaf.jpg", f, "image/jpeg")}
        data = {"mode": "auto_standard"}
        headers_api = {"X-Gari-API-Key": full_api_key}
        resp_api = requests.post(f"{BASE_URL}/api/v1/diagnose", headers=headers_api, files=files, data=data)

    log_test("POST /api/v1/diagnose with valid API Key", resp_api.status_code == 200, f"HTTP {resp_api.status_code}")
    res_json = resp_api.json()
    assert res_json.get("success") is True, "Inference success should be True"
    assert "diagnosis" in res_json, "Missing diagnosis in v1 response"
    assert "quota" in res_json, "Missing quota in v1 response"
    log_test("API Response Schema Verified", True, f"Disease={res_json['diagnosis']['name_vi']}, Remaining Quota={res_json['quota']['remaining']}")

    # 3. Revoke the API Key
    resp_revoke = requests.post(f"{BASE_URL}/api/organizations/1/api-keys/{key_id}/revoke", headers=hdr_owner)
    log_test("Revoke API Key", resp_revoke.status_code == 200)

    # 4. Call /api/v1/diagnose with the REVOKED key -> Must be rejected with 401
    with open("test_leaf.jpg", "rb") as f:
        files = {"image": ("leaf.jpg", f, "image/jpeg")}
        data = {"mode": "auto_standard"}
        resp_blocked = requests.post(f"{BASE_URL}/api/v1/diagnose", headers=headers_api, files=files, data=data)
    log_test("Revoked API Key Blocked with HTTP 401", resp_blocked.status_code == 401, f"HTTP {resp_blocked.status_code} ({resp_blocked.json().get('detail')})")

def test_leaf_gate_rejection_no_org_quota_deduct():
    print("\n--- 4. Testing Zero Org Quota Deduction on Non-Leaf / Quality Failure ---")
    token_owner = get_auth_token("danhuynh@gari.vn", "Password123!")
    hdr_owner = {"Authorization": f"Bearer {token_owner}"}

    # Generate a fresh API key for Org 1
    resp_gen = requests.post(
        f"{BASE_URL}/api/organizations/1/api-keys",
        json={"key_name": "Gate Check Key", "rate_limit_rpm": 60},
        headers=hdr_owner
    )
    key_info = resp_gen.json()["api_key"]
    api_key = key_info["full_key"]
    headers_api = {"X-Gari-API-Key": api_key}

    # Check org quota before
    q_before = requests.get(f"{BASE_URL}/api/organizations/1", headers=hdr_owner).json()["organization"]["quota"]["remaining"]

    # Submit non-leaf solid gray image
    img = Image.new("RGB", (300, 300), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    files = {"image": ("non_leaf.jpg", buf, "image/jpeg")}
    resp_rej = requests.post(f"{BASE_URL}/api/v1/diagnose", headers=headers_api, files=files, data={"mode": "auto_standard"})
    log_test("Non-leaf submitted to /api/v1/diagnose", resp_rej.status_code == 422, f"HTTP {resp_rej.status_code}")
    assert resp_rej.json().get("quota_deducted") is False, "Quota must not be deducted on rejection"

    # Check org quota after
    q_after = requests.get(f"{BASE_URL}/api/organizations/1", headers=hdr_owner).json()["organization"]["quota"]["remaining"]
    log_test("Zero Org Quota Deduction on Rejection", q_before == q_after, f"Before={q_before}, After={q_after}")

    # Clean up key to keep slot available for future test runs
    requests.post(f"{BASE_URL}/api/organizations/1/api-keys/{key_info['id']}/revoke", headers=hdr_owner)

def test_usage_metering_audit_logging():
    print("\n--- 5. Testing Usage Metering Telemetry Audit ---")
    token_owner = get_auth_token("danhuynh@gari.vn", "Password123!")
    hdr_owner = {"Authorization": f"Bearer {token_owner}"}

    resp_usage = requests.get(f"{BASE_URL}/api/organizations/1/usage?limit=10", headers=hdr_owner)
    log_test("GET /api/organizations/1/usage", resp_usage.status_code == 200)
    logs = resp_usage.json().get("usage_logs", [])
    log_test("Usage logs recorded in database", len(logs) > 0, f"Total logs found={len(logs)}")
    recent = logs[0]
    log_test("Usage log structure verification", "model_name" in recent and "latency_ms" in recent and "quota_deducted" in recent, f"Model={recent.get('model_name')}, Latency={recent.get('latency_ms')}ms")

def test_concurrent_quota_atomic_safety():
    print("\n--- 6. Testing Concurrency-Safe Organization Quota (No Negative Quota) ---")
    import gari_b2b
    
    # We will test deduct_org_quota_atomic under 15 simultaneous threads
    # First, let's create a temporary test organization with a small quota (e.g. 5)
    test_org = gari_b2b.create_organization(
        name="Test Concurrent HTX",
        owner_id=1,
        plan_id="free" # Free plan has quota limit 5
    )
    test_org_id = test_org["id"]
    
    def try_deduct(thread_id):
        return gari_b2b.deduct_org_quota_atomic(
            org_id=test_org_id,
            user_id=1,
            caller_type="concurrent_test",
            model_name="Gari ConvNeXt Test",
            latency_ms=10.0
        )

    # Launch 15 simultaneous deductions when limit is only 5
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(try_deduct, i) for i in range(15)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    success_count = sum(1 for r in results if r is True)
    rejected_count = sum(1 for r in results if r is False)
    
    # Verify final quota
    final_q = gari_b2b.get_organization_quota_status(test_org_id)
    log_test("Concurrent Quota Deductions (Limit=5, Requests=15)", success_count == 5 and rejected_count == 10, f"Success={success_count}, Blocked={rejected_count}")
    log_test("Final Used Count equals Limit", final_q["used_count"] == 5, f"Used={final_q['used_count']}/{final_q['quota_limit']}")
    log_test("Remaining Quota is zero, NOT negative", final_q["remaining"] == 0, f"Remaining={final_q['remaining']}")

def test_vip_model_entitlement_by_org_plan():
    print("\n--- 7. Testing VIP Model Access via B2B Organization Plan ---")
    token_farmer = get_auth_token("nongdan.mau@gari.vn", "FarmerPassword123!") # Farmer is Free user individually
    
    # When farmer scans individually -> auto_pro (Model tong 2 VIP) is blocked (403)
    with open("test_leaf.jpg", "rb") as f:
        files = {"image": ("leaf.jpg", f, "image/jpeg")}
        data = {"mode": "auto_pro"}
        headers = {"Authorization": f"Bearer {token_farmer}"}
        resp_personal = requests.post(f"{BASE_URL}/api/plant/diagnose", headers=headers, files=files, data=data)
    log_test("Farmer alone blocked from VIP model", resp_personal.status_code == 403, f"HTTP {resp_personal.status_code}")

    # When farmer scans under Org 1 (HTX Ba Vì has 'team' plan with VIP models enabled) -> Allowed 200 OK!
    with open("test_leaf.jpg", "rb") as f:
        files = {"image": ("leaf.jpg", f, "image/jpeg")}
        data = {"mode": "auto_pro", "org_id": 1}
        headers = {"Authorization": f"Bearer {token_farmer}"}
        resp_org = requests.post(f"{BASE_URL}/api/plant/diagnose", headers=headers, files=files, data=data)
    log_test("Farmer under Team Org entitled to VIP model", resp_org.status_code == 200, f"HTTP {resp_org.status_code}")

if __name__ == "__main__":
    test_frontend_b2b_routes()
    test_multi_tenant_isolation_and_rbac()
    test_api_key_lifecycle_and_service()
    test_leaf_gate_rejection_no_org_quota_deduct()
    test_usage_metering_audit_logging()
    test_concurrent_quota_atomic_safety()
    test_vip_model_entitlement_by_org_plan()
    print("\n============================================================")
    print(" ALL B2B SAAS & API PLATFORM ACCEPTANCE TESTS PASSED (100%) ")
    print("============================================================\n")
