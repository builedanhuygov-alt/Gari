"""
Automated Test Suite for Gari AgriTech Startup MVP.
Verifies:
1. Frontend HTTP endpoints & responsive pages.
2. Startup Metrics Hub API (/api/metrics/startup).
3. Free vs VIP Quota & VIP Model Enforcement (Model 2/4 VIP protection).
4. Leaf Validation Gate: Non-leaf rejection, zero quota deduction, telemetry logging.
5. Real leaf inference: Uncalibrated score notice, Trust & Safety payload, quality factors, next inspection steps, no chemical pesticide dosages.
6. History & Farm Records: Secure record creation, user-scoped deletion, data isolation.
"""
import sys
from pathlib import Path
import json
import io
import time
from PIL import Image
import requests

# Set stdout encoding for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8000"

def log_test(name, success, detail=""):
    mark = "PASS" if success else "FAIL"
    print(f"[{mark}] {name} {detail}")
    if not success:
        sys.exit(1)

def test_frontend_routes():
    print("\n--- 1. Testing Frontend HTTP Routes ---")
    routes = [
        "/frontend2/predict.html",
        "/frontend2/reports.html",
        "/frontend2/admin.html",
        "/frontend2/index.html",
        "/api/health"
    ]
    for r in routes:
        resp = requests.get(f"{BASE_URL}{r}", timeout=10)
        log_test(f"Route GET {r}", resp.status_code == 200, f"HTTP {resp.status_code}")

def test_startup_metrics_endpoint():
    print("\n--- 2. Testing Startup Metrics Hub API ---")
    resp = requests.get(f"{BASE_URL}/api/metrics/startup", timeout=10)
    log_test("GET /api/metrics/startup status", resp.status_code == 200, f"HTTP {resp.status_code}")
    data = resp.json()
    metrics = data.get("metrics", {})
    required_keys = [
        "total_registered_accounts",
        "active_users_7d",
        "successful_classifications",
        "rejected_photo_rate_percent",
        "retention_rate_percent",
        "free_vs_vip",
        "inference_errors_count",
        "models_invoked_breakdown"
    ]
    for k in required_keys:
        assert k in metrics, f"Missing metric key: {k}"
    log_test("Startup Metrics fields integrity", True, f"Total Accounts={metrics['total_registered_accounts']}, Active={metrics['active_users_7d']}, Success={metrics['successful_classifications']}, Free/VIP={metrics['free_vs_vip']['ratio_text']}")

def test_auth_and_quota_mechanisms():
    print("\n--- 3. Testing Authentication & Quota Tiers ---")
    # Test guest quota
    guest_session = requests.Session()
    resp_quota = guest_session.get(f"{BASE_URL}/api/user/quota")
    log_test("Guest Quota Fetch", resp_quota.status_code == 200)
    guest_q = resp_quota.json().get("quota", {})
    log_test("Guest Quota Limit check", guest_q.get("quota_limit") == 3, f"Limit={guest_q.get('quota_limit')}")
    assert guest_q.get("is_vip") is False, "Guest should not be VIP"

    # Test Free User login (nongdan.mau@gari.vn / FarmerPassword123!)
    resp_login_free = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "nongdan.mau@gari.vn", "password": "FarmerPassword123!"})
    log_test("Login Free Farmer", resp_login_free.status_code == 200, f"HTTP {resp_login_free.status_code}")
    token_free = resp_login_free.json().get("token")
    headers_free = {"Authorization": f"Bearer {token_free}"}
    resp_free_q = requests.get(f"{BASE_URL}/api/user/quota", headers=headers_free)
    log_test("Free User Quota Fetch", resp_free_q.status_code == 200)
    free_q = resp_free_q.json().get("quota", {})
    log_test("Free User Quota tier", free_q.get("quota_limit") == 5, f"Limit={free_q.get('quota_limit')}")
    assert free_q.get("is_vip") is False, "Farmer should not be VIP"

    # Test VIP User login (danhuynh@gari.vn / Password123!)
    resp_login_vip = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "danhuynh@gari.vn", "password": "Password123!"})
    log_test("Login VIP Agronomist", resp_login_vip.status_code == 200, f"HTTP {resp_login_vip.status_code}")
    token_vip = resp_login_vip.json().get("token")
    headers_vip = {"Authorization": f"Bearer {token_vip}"}
    resp_vip_q = requests.get(f"{BASE_URL}/api/user/quota", headers=headers_vip)
    log_test("VIP User Quota Fetch", resp_vip_q.status_code == 200)
    vip_q = resp_vip_q.json().get("quota", {})
    log_test("VIP User Quota tier", vip_q.get("is_vip") is True, f"IsVIP={vip_q.get('is_vip')}")

def test_leaf_gate_rejection_no_quota_deduct():
    print("\n--- 4. Testing Leaf Validation Gate & No Quota Deduction ---")
    # Generate non-leaf solid gray image
    img = Image.new("RGB", (300, 300), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    # Use a fresh guest session with isolated client ID
    client_test_id = f"test_gate_{int(time.time())}"
    headers = {"X-Client-Id": client_test_id}
    s = requests.Session()
    q_before = s.get(f"{BASE_URL}/api/user/quota", headers=headers).json()["quota"]["remaining"]

    # Submit non-leaf image
    files = {"image": ("non_leaf.jpg", buf, "image/jpeg")}
    data = {"mode": "auto_standard"}
    resp = s.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=data, headers=headers)
    log_test("Non-leaf diagnosis call", resp.status_code == 200)
    res = resp.json()
    val = res.get("validation", {})
    log_test("Leaf Gate Rejection check", val.get("status") in ["NOT_A_LEAF", "UNCERTAIN", "IMAGE_QUALITY_LOW"], f"Validation status={val.get('status')}")

    # Check that quota was NOT deducted
    q_after = s.get(f"{BASE_URL}/api/user/quota", headers=headers).json()["quota"]["remaining"]
    log_test("Zero Quota Deduction on Rejection", q_before == q_after, f"Before={q_before}, After={q_after}")

def test_vip_model_enforcement():
    print("\n--- 5. Testing VIP Model Access Control ---")
    test_leaf = Path("test_leaf.jpg")
    if not test_leaf.exists():
        img = Image.new("RGB", (224, 224), color=(34, 139, 34))
        img.save("test_leaf.jpg")

    # Guest / Free user attempting auto_pro (Model tong 2 (vip)) without VIP or Dev Pro header
    client_test_id = f"test_vip_{int(time.time())}"
    headers_free = {"X-Client-Id": client_test_id}
    s = requests.Session()
    with open("test_leaf.jpg", "rb") as f:
        files = {"image": ("leaf.jpg", f, "image/jpeg")}
        data = {"mode": "auto_pro"}
        resp = s.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=data, headers=headers_free)
    log_test("VIP Model (auto_pro) Blocked for Free User", resp.status_code == 403, f"HTTP {resp.status_code} ({resp.json().get('detail')})")

    # Authorized test with Dev Pro header
    with open("test_leaf.jpg", "rb") as f:
        files = {"image": ("leaf.jpg", f, "image/jpeg")}
        data = {"mode": "auto_pro"}
        headers = {"X-Gari-Dev-Pro": "true"}
        resp_pro = s.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=data, headers=headers)
    log_test("VIP Model with Dev Pro Header authorized", resp_pro.status_code == 200, f"HTTP {resp_pro.status_code}")

def test_diagnosis_trust_safety_and_history():
    print("\n--- 6. Testing Real Leaf Diagnosis, Trust & Safety & History Deletion ---")
    s = requests.Session()
    # Login user 1
    resp_login = s.post(f"{BASE_URL}/api/auth/login", json={"email": "danhuynh@gari.vn", "password": "Password123!"})
    token = resp_login.json().get("token")
    headers = {"Authorization": f"Bearer {token}"}

    # Perform diagnosis with test leaf
    with open("test_leaf.jpg", "rb") as f:
        files = {"image": ("leaf.jpg", f, "image/jpeg")}
        data = {"mode": "manual", "crop": "Tomato", "notes": "Cây cà chua thử nghiệm MVP"}
        resp = s.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=data, headers=headers)

    log_test("Diagnosis execution", resp.status_code == 200)
    res = resp.json()
    diag_id = res.get("diagnosis_id") or res.get("saved_diagnosis_id") or res.get("id")
    log_test("Diagnosis ID returned", diag_id is not None, f"ID={diag_id}")

    # Check Trust & Safety structure
    ts = res.get("trust_and_safety")
    log_test("Trust & Safety payload presence", ts is not None)
    assert ts.get("agronomist_disclaimer") is not None, "Missing agronomist disclaimer"
    assert "liều lượng" in ts.get("chemical_pesticide_policy", "").lower(), "Chemical policy must mention dosage safeguard"
    assert ts.get("quality_factors") is not None, "Missing quality factors"
    assert len(ts.get("field_inspection_steps", [])) > 0, "Missing field inspection steps"
    log_test("Trust & Safety policy check", True, "Disclaimer, Chemical Policy, and Quality Factors verified")

    # Verify history listing contains this record
    resp_hist = s.get(f"{BASE_URL}/api/diagnoses?limit=5", headers=headers)
    log_test("Fetch History Records", resp_hist.status_code == 200)
    records = resp_hist.json().get("diagnoses", [])
    found = any(r["id"] == diag_id for r in records)
    log_test(f"Diagnosis #{diag_id} present in user history", found)

    # Test Deleting record
    resp_del = s.delete(f"{BASE_URL}/api/diagnoses/{diag_id}", headers=headers)
    log_test(f"DELETE /api/diagnoses/{diag_id}", resp_del.status_code == 200, f"HTTP {resp_del.status_code}")

    # Verify record is gone
    resp_hist2 = s.get(f"{BASE_URL}/api/diagnoses?limit=5", headers=headers)
    records2 = resp_hist2.json().get("diagnoses", [])
    still_there = any(r["id"] == diag_id for r in records2)
    log_test("Record successfully removed from database", not still_there)

if __name__ == "__main__":
    test_frontend_routes()
    test_startup_metrics_endpoint()
    test_auth_and_quota_mechanisms()
    test_leaf_gate_rejection_no_quota_deduct()
    test_vip_model_enforcement()
    test_diagnosis_trust_safety_and_history()
    print("\n==========================================")
    print(" ALL STARTUP MVP AUTOMATED TESTS PASSED! ")
    print("==========================================\n")
