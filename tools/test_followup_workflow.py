import urllib.request
import urllib.error
import json

BASE = "http://127.0.0.1:8000"

print("=== TESTING P1.5 TREATMENT & FOLLOW-UP WORKFLOW ===")

# 1. Login user A
login_data = json.dumps({"email": "prod_audit_test@gari.vn", "password": "SecTest#2026_Prod"}).encode()
req = urllib.request.Request(f"{BASE}/api/auth/login", data=login_data, headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req) as r:
    token_a = json.loads(r.read().decode())["token"]

# 2. Get user A's diagnoses list
req = urllib.request.Request(f"{BASE}/api/diagnoses", headers={"Authorization": f"Bearer {token_a}"})
with urllib.request.urlopen(req) as r:
    diags = json.loads(r.read().decode())["diagnoses"]
    assert len(diags) > 0, "No diagnoses found for user A"
    diag_id = diags[0]["id"]
    print(f"Target Diagnosis ID: {diag_id} (Crop: {diags[0]['crop_name']}, Disease: {diags[0]['predicted_disease']})")

# 3. Test: Recovery claim without observation notes MUST be rejected
bad_payload = json.dumps({"monitoring_status": "recovered"}).encode()
req = urllib.request.Request(f"{BASE}/api/diagnoses/{diag_id}/follow-up", data=bad_payload, headers={"Content-Type": "application/json", "Authorization": f"Bearer {token_a}"}, method="PATCH")
try:
    with urllib.request.urlopen(req) as r:
        print("[FAIL] Unfounded recovery claim should have been rejected!")
except urllib.error.HTTPError as e:
    res = json.loads(e.read().decode())
    print("[PASS] Unfounded recovery rejected -> HTTP", e.code, "| Detail:", res.get("detail"))
    assert e.code == 400

# 4. Test: Record valid treatment action and observation
valid_treated = json.dumps({
    "monitoring_status": "treated",
    "observation_notes": "Đã tiến hành cắt tỉa các lá có vết đốm bệnh và phun dung dịch Booc-đô 1% bảo vệ phiến lá.",
    "treatment_action": "Cắt tỉa & Phun Booc-đô 1%"
}).encode()
req = urllib.request.Request(f"{BASE}/api/diagnoses/{diag_id}/follow-up", data=valid_treated, headers={"Content-Type": "application/json", "Authorization": f"Bearer {token_a}"}, method="PATCH")
with urllib.request.urlopen(req) as r:
    data = json.loads(r.read().decode())
    updated = data["diagnosis"]
    print("[PASS] Follow-up status updated to 'treated' -> HTTP 200")
    print("  Monitoring status:", updated["monitoring_status"])
    print("  Treatment status:", updated["treatment_status"])
    assert updated["monitoring_status"] == "treated"
    assert updated["treatment_status"] == "in_progress"

# 5. Test: Valid recovery update with field observation evidence
valid_recovered = json.dumps({
    "monitoring_status": "recovered",
    "observation_notes": "Kiểm tra thực địa ngày thứ 7: Vết đốm đã khô đen hoàn toàn, viền lá non phát triển bình thường, không có dấu hiệu lây lan mới.",
    "treatment_action": "Kiểm tra nghiệm thu sau điều trị"
}).encode()
req = urllib.request.Request(f"{BASE}/api/diagnoses/{diag_id}/follow-up", data=valid_recovered, headers={"Content-Type": "application/json", "Authorization": f"Bearer {token_a}"}, method="PATCH")
with urllib.request.urlopen(req) as r:
    data = json.loads(r.read().decode())
    updated = data["diagnosis"]
    print("[PASS] Follow-up status updated to 'recovered' with evidence -> HTTP 200")
    print("  Monitoring status:", updated["monitoring_status"])
    print("  Treatment status:", updated["treatment_status"])
    assert updated["monitoring_status"] == "recovered"
    assert updated["treatment_status"] == "completed"

# 6. Test: Cross-user authorization check (User B cannot modify User A's diagnosis follow-up)
reg_b = json.dumps({"email": "user_b_unauthorized@gari.vn", "password": "SecTest#2026_Prod", "full_name": "Người Dùng B"}).encode()
try:
    req = urllib.request.Request(f"{BASE}/api/auth/register", data=reg_b, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as r:
        token_b = json.loads(r.read().decode())["token"]
except:
    log_b = json.dumps({"email": "user_b_unauthorized@gari.vn", "password": "SecTest#2026_Prod"}).encode()
    req = urllib.request.Request(f"{BASE}/api/auth/login", data=log_b, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as r:
        token_b = json.loads(r.read().decode())["token"]

req = urllib.request.Request(f"{BASE}/api/diagnoses/{diag_id}/follow-up", data=valid_treated, headers={"Content-Type": "application/json", "Authorization": f"Bearer {token_b}"}, method="PATCH")
try:
    with urllib.request.urlopen(req) as r:
        print("[FAIL] Unauthorized user should not modify another user's diagnosis!")
except urllib.error.HTTPError as e:
    print("[PASS] Cross-user follow-up update rejected -> HTTP", e.code)
    assert e.code == 403

print("=== ALL P1.5 FOLLOW-UP WORKFLOW TESTS PASSED ===")

