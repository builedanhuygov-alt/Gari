import sys
import io
import time
import uuid
import requests
import concurrent.futures
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import internal helpers for setting up test sessions
import gari_auth
import gari_quota

BASE_URL = "http://localhost:8000"

def get_sample_leaf():
    test_imgs = list(Path("test-images").glob("*.jpg")) + list(Path("test-images").glob("*.png"))
    if test_imgs:
        return test_imgs[0]
    imgs = list(Path(".").glob("*.jpg"))
    if imgs:
        return imgs[0]
    raise RuntimeError("No image found for testing")

def run_tests():
    print("=" * 70)
    print(" GARI AI LAB - QUOTA & VIP VERIFICATION TEST SUITE ")
    print("=" * 70)
    
    leaf_path = get_sample_leaf()
    print(f"[*] Using sample leaf image: {leaf_path}")
    leaf_bytes = leaf_path.read_bytes()
    
    # -----------------------------------------------------------------
    # Test 1: New Account / Default Quota Initialization
    # -----------------------------------------------------------------
    print("\n--- Test 1: Default Quota Initialization ---")
    # Standard User: User 4 (nongdan.viet@test.vn, Nông hộ)
    std_token = gari_auth.create_session(4, remember_me=False)
    std_headers = {"Authorization": f"Bearer {std_token}"}
    
    res = requests.get(f"{BASE_URL}/api/user/quota", headers=std_headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    user_info = res.json().get("user")
    q_std = res.json()["quota"]
    print(f"Standard user ({user_info['email']} - {user_info['account_type']}):")
    print(f"  Quota: {q_std['remaining']}/{q_std['quota_limit']} turns. is_vip={q_std['is_vip']}. can_classify={q_std['can_classify']}")
    assert q_std['quota_limit'] == 5, f"Expected 5 total turns, got {q_std['quota_limit']}"
    assert not q_std['is_vip'], "Expected standard user to not be VIP"
    
    # VIP User: User 1 (danhuynh@gari.vn - Đơn vị dịch vụ nông nghiệp)
    vip_token = gari_auth.create_session(1, remember_me=False)
    vip_headers = {"Authorization": f"Bearer {vip_token}"}
    
    res = requests.get(f"{BASE_URL}/api/user/quota", headers=vip_headers)
    assert res.status_code == 200
    user_vip = res.json().get("user")
    q_vip = res.json()["quota"]
    print(f"VIP user ({user_vip['email']} - {user_vip['account_type']}):")
    print(f"  Quota: {q_vip['remaining']}/{q_vip['quota_limit']} turns. is_vip={q_vip['is_vip']}. can_classify={q_vip['can_classify']}")
    assert q_vip['is_vip'], "Expected VIP user to have is_vip=True"
    assert q_vip['remaining'] >= 999999, "Expected VIP quota to be unlimited"
    print("  -> PASS: Default quota and VIP status correctly initialized.")

    # -----------------------------------------------------------------
    # Test 2: Valid Leaf Diagnosis Deducts Exactly 1 Turn
    # -----------------------------------------------------------------
    print("\n--- Test 2: Valid Diagnosis Deducts Exactly 1 Turn ---")
    test_client_id = f"tester_{uuid.uuid4().hex[:8]}"
    test_headers = {"X-Client-Id": test_client_id}
    
    # Check initial quota
    res = requests.get(f"{BASE_URL}/api/user/quota", headers=test_headers)
    init_quota = res.json()["quota"]
    init_remaining = init_quota["remaining"]
    init_limit = init_quota["quota_limit"]
    print(f"Initial guest/client quota: {init_remaining}/{init_limit}")
    
    files = {"file": ("leaf.jpg", leaf_bytes, "image/jpeg")}
    data = {"mode": "auto_crop"}
    res = requests.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=data, headers=test_headers)
    assert res.status_code == 200, f"Diagnose failed: {res.text}"
    diag_res = res.json()
    quota_res = diag_res.get("quota", {})
    print(f"Diagnosis completed: status={diag_res.get('status')}, quota_deducted={diag_res.get('quota_deducted')}")
    print(f"Quota after diagnosis: {quota_res.get('remaining')}/{quota_res.get('quota_limit')}")
    assert diag_res.get("quota_deducted") is True, "Expected quota_deducted to be True"
    assert quota_res.get("remaining") == init_remaining - 1, f"Expected {init_remaining - 1}, got {quota_res.get('remaining')}"
    print("  -> PASS: Valid diagnosis correctly deducted exactly 1 turn.")

    # -----------------------------------------------------------------
    # Test 3: Invalid Leaf / Validation Failure Does NOT Deduct Turn
    # -----------------------------------------------------------------
    print("\n--- Test 3: Invalid Image Validation Failure Does NOT Deduct Quota ---")
    quota_before = quota_res.get("remaining")
    
    # Synthetic non-leaf image (pure black image)
    from PIL import Image
    black_img = Image.new("RGB", (256, 256), color=(0, 0, 0))
    buf = io.BytesIO()
    black_img.save(buf, format="JPEG")
    buf.seek(0)
    
    files = {"file": ("non_leaf.jpg", buf.getvalue(), "image/jpeg")}
    data = {"mode": "auto_crop"}
    res = requests.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=data, headers=test_headers)
    assert res.status_code == 200
    non_leaf_res = res.json()
    print(f"Non-leaf response: status={non_leaf_res.get('status')}, val_status={non_leaf_res.get('leaf_validation', {}).get('status')}")
    print(f"quota_deducted: {non_leaf_res.get('quota_deducted')}")
    print(f"Message Vi: {non_leaf_res.get('leaf_validation', {}).get('message_vi')}")
    assert non_leaf_res.get("quota_deducted") is False, "Quota must NOT be deducted for invalid leaf!"
    
    # Check quota remains untouched
    res = requests.get(f"{BASE_URL}/api/user/quota", headers=test_headers)
    quota_after = res.json()["quota"]["remaining"]
    print(f"Quota before: {quota_before}, Quota after: {quota_after}")
    assert quota_before == quota_after, f"Quota changed! Before: {quota_before}, After: {quota_after}"
    print("  -> PASS: Quota remained completely untouched upon leaf validation failure.")

    # -----------------------------------------------------------------
    # Test 4: Exhaustion Blocks Inference & Returns Vietnamese Message
    # -----------------------------------------------------------------
    print("\n--- Test 4: Quota Exhaustion & 429 Rejection ---")
    # Consume remaining turns
    remaining = quota_after
    print(f"Consuming remaining {remaining} turns for client {test_client_id}...")
    for i in range(remaining):
        f = {"file": ("leaf.jpg", leaf_bytes, "image/jpeg")}
        d = {"mode": "auto_crop"}
        r = requests.post(f"{BASE_URL}/api/plant/diagnose", files=f, data=d, headers=test_headers)
        assert r.status_code == 200, f"Turn {i+1} failed: {r.text}"
    
    # Verify remaining is now 0
    res = requests.get(f"{BASE_URL}/api/user/quota", headers=test_headers)
    zero_quota = res.json()["quota"]
    print(f"Quota state: {zero_quota['remaining']}/{zero_quota['quota_limit']} remaining. can_classify={zero_quota['can_classify']}")
    assert zero_quota['remaining'] == 0, f"Expected 0 remaining, got {zero_quota['remaining']}"
    assert not zero_quota['can_classify']
    
    # Next diagnosis attempt must be rejected with HTTP 429
    f = {"file": ("leaf.jpg", leaf_bytes, "image/jpeg")}
    d = {"mode": "auto_crop"}
    res = requests.post(f"{BASE_URL}/api/plant/diagnose", files=f, data=d, headers=test_headers)
    print(f"Exhausted attempt HTTP status: {res.status_code}")
    assert res.status_code == 429, f"Expected HTTP 429, got {res.status_code}"
    err_body = res.json()
    print(f"Vietnamese rejection detail: {err_body.get('detail')}")
    assert "Bạn đã dùng hết lượt phân loại miễn phí" in err_body.get("detail", ""), "Vietnamese notice missing!"
    print("  -> PASS: Blocked with HTTP 429 and correct Vietnamese message when quota exhausted.")

    # -----------------------------------------------------------------
    # Test 5: Standard User Cannot Access VIP Models (Backend Enforcement)
    # -----------------------------------------------------------------
    print("\n--- Test 5: VIP Model Access Enforcement ---")
    # Reset standard user quota if needed to ensure they have turns
    with gari_quota._QUOTA_LOCK:
        with gari_quota.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE user_quotas SET used_count = 0 WHERE client_identifier = 'user_4'")
            conn.commit()
            
    # Try calling auto_pro (Model tong 2 vip) as standard user
    f = {"file": ("leaf.jpg", leaf_bytes, "image/jpeg")}
    d = {"mode": "auto_pro"}
    res = requests.post(f"{BASE_URL}/api/plant/diagnose", files=f, data=d, headers=std_headers)
    print(f"Standard user calling auto_pro HTTP status: {res.status_code}")
    assert res.status_code == 403, f"Expected HTTP 403, got {res.status_code}: {res.text}"
    print(f"Rejection detail: {res.json().get('detail')}")
    assert "VIP" in res.json().get("detail", "")
    
    # Try calling model tong 4 (vip) specifically as standard user
    f = {"file": ("leaf.jpg", leaf_bytes, "image/jpeg")}
    d = {"mode": "crop_model", "crop_name": "model tong 4 (vip)"}
    res = requests.post(f"{BASE_URL}/api/plant/diagnose", files=f, data=d, headers=std_headers)
    print(f"Standard user calling model tong 4 (vip) HTTP status: {res.status_code}")
    assert res.status_code == 403, f"Expected HTTP 403, got {res.status_code}"
    
    # Now verify VIP user CAN call auto_pro
    f = {"file": ("leaf.jpg", leaf_bytes, "image/jpeg")}
    d = {"mode": "auto_pro"}
    res = requests.post(f"{BASE_URL}/api/plant/diagnose", files=f, data=d, headers=vip_headers)
    print(f"VIP user calling auto_pro HTTP status: {res.status_code}")
    assert res.status_code == 200, f"Expected 200 for VIP user, got {res.status_code}: {res.text}"
    vip_diag = res.json()
    print(f"VIP Model used: {vip_diag.get('model_used')}, VIP Quota remaining: {vip_diag.get('quota', {}).get('remaining')}")
    print("  -> PASS: Backend strictly blocked non-VIP user and permitted VIP user.")

    # -----------------------------------------------------------------
    # Test 6: Quota Refresh Cycle
    # -----------------------------------------------------------------
    print("\n--- Test 6: Quota Cycle Refresh ---")
    # Manually backdate cycle_end for exhausted client by 1 hour ago
    with gari_quota._QUOTA_LOCK:
        with gari_quota.get_db_connection() as conn:
            cursor = conn.cursor()
            one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "UPDATE user_quotas SET cycle_end = ?, cycle_start = ? WHERE client_identifier = ?", 
                (one_hour_ago, two_days_ago, f"client_{test_client_id}")
            )
            conn.commit()
    
    res = requests.get(f"{BASE_URL}/api/user/quota", headers=test_headers)
    refreshed_quota = res.json()["quota"]
    print(f"Quota after expired cycle pass: {refreshed_quota['remaining']}/{refreshed_quota['quota_limit']} (can_classify={refreshed_quota['can_classify']})")
    assert refreshed_quota['remaining'] == refreshed_quota['quota_limit'], f"Expected turns restored after refresh, got {refreshed_quota['remaining']}"
    print("  -> PASS: Quota automatically restored after refresh period expired.")

    # -----------------------------------------------------------------
    # Test 7: Race Condition / Concurrent Requests
    # -----------------------------------------------------------------
    print("\n--- Test 7: Atomic Concurrency & Negative Quota Prevention ---")
    race_id = f"race_{uuid.uuid4().hex[:8]}"
    race_headers = {"X-Client-Id": race_id}
    
    # Initialize quota and set used_count so exactly 1 turn remains
    requests.get(f"{BASE_URL}/api/user/quota", headers=race_headers)
    with gari_quota._QUOTA_LOCK:
        with gari_quota.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT quota_limit FROM user_quotas WHERE client_identifier = ?", (f"client_{race_id}",))
            q_lim = cursor.fetchone()["quota_limit"]
            cursor.execute(
                "UPDATE user_quotas SET used_count = ? WHERE client_identifier = ?", 
                (q_lim - 1, f"client_{race_id}")
            )
            conn.commit()
        
    res = requests.get(f"{BASE_URL}/api/user/quota", headers=race_headers)
    assert res.json()["quota"]["remaining"] == 1, f"Failed to prep exactly 1 remaining turn: {res.json()['quota']}"
    print("Starting state: Exactly 1 turn remaining.")
    
    print("Blasting 8 concurrent classification requests simultaneously...")
    def send_req(req_idx):
        f = {"file": (f"leaf_{req_idx}.jpg", leaf_bytes, "image/jpeg")}
        d = {"mode": "auto_crop"}
        try:
            return requests.post(f"{BASE_URL}/api/plant/diagnose", files=f, data=d, headers=race_headers, timeout=30)
        except Exception as e:
            return e

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(send_req, i) for i in range(8)]
        results = [f.result() for f in futures]
    
    status_codes = [r.status_code if hasattr(r, 'status_code') else str(r) for r in results]
    print(f"Response status codes: {status_codes}")
    
    success_count = sum(1 for sc in status_codes if sc == 200)
    rejected_count = sum(1 for sc in status_codes if sc == 429)
    print(f"Success (200): {success_count}, Quota Exhausted (429): {rejected_count}")
    
    # Verify database final state
    res = requests.get(f"{BASE_URL}/api/user/quota", headers=race_headers)
    final_quota = res.json()["quota"]
    print(f"Final quota: remaining={final_quota['remaining']}, used_count={final_quota['used_count']}")
    assert final_quota['remaining'] == 0, f"Remaining quota should be exactly 0, got {final_quota['remaining']}"
    assert final_quota['remaining'] >= 0, "Remaining quota must NEVER be negative!"
    assert success_count == 1, f"Expected exactly 1 request to succeed, got {success_count}"
    assert rejected_count == 7, f"Expected 7 requests to be 429 rejected, got {rejected_count}"
    print("  -> PASS: Atomic reservation prevented race condition. Quota never became negative.")
    
    print("\n" + "=" * 70)
    print(" ALL 7 TEST CASES PASSED PERFECTLY! ")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
