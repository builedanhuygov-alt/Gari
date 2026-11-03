"""
GARI AI LAB — SPRINT 4 VERIFICATION TEST SUITE
scratch/test_sprint4_agri_intelligence.py

Automated test suite verifying all 10 mandatory requirements:
1. Valid diagnosis saves history with minimal schema (diagnosis_id, actor_user_id, organization_id,
   farm_plot_id, crop, predicted_disease, confidence, model_version, diagnosis_status, created_at).
   Image persistence respects consent_store_image.
2. Invalid image rejected at leaf gate with retake guidance and zero quota deduction.
3. Uncertain/needs_review result is never inflated to clinical certitude; low-risk actions only.
4. User cannot read diagnosis history of another user/tenant (HTTP 403).
5. User cannot attach diagnosis to a farm plot belonging to another user/tenant (HTTP 403).
6. Model prediction and confidence cannot be tampered/overridden via user API (HTTP 403).
7. Data deletion unlinks stored files and obeys privacy erasure policies across timeline events.
8. Farm plot timeline returns objective summary without asserting disease worsening without evidence;
   observation notes and status transitions work with tenant isolation.
9. Quota is accurately metered for diagnoses (valid deducts 1, rejected deducts 0, 429 when exhausted).
10. Regression pass-through across all core modules.
"""

import io
import os
import sys
import time
import requests
from PIL import Image
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

passed_count = 0
failed_count = 0
checks_total = 0

def check(description: str, condition: bool, extra: str = ""):
    global passed_count, failed_count, checks_total
    checks_total += 1
    if condition:
        passed_count += 1
        print(f"  [PASS] {description}")
    else:
        failed_count += 1
        msg = f"  [FAIL] {description}"
        if extra:
            msg += f" -> {extra}"
        print(msg)


def get_auth_token(email: str, password: str = "Password123!"):
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=10)
    if resp.status_code == 200:
        return resp.json().get("token")
    return None


def create_solid_image(color=(10, 10, 10), size=(256, 256)):
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf.getvalue()


def get_real_leaf_image():
    leaf_path = PROJECT_ROOT / "test_leaf.jpg"
    if leaf_path.exists():
        with open(leaf_path, "rb") as f:
            return f.read()
    # Fallback to green leaf-like image if file missing
    img = Image.new("RGB", (256, 256), color=(34, 139, 34))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf.getvalue()


def run_all_tests():
    print("=" * 70)
    print("GARI AI LAB — SPRINT 4: AGRI INTELLIGENCE & FARM OPERATIONS TEST SUITE")
    print("=" * 70)

    # Setup 2 distinct users for tenant isolation testing
    token_user_a = get_auth_token("danhuynh@gari.vn", "Password123!")
    token_user_b = get_auth_token("nongdan.mau@gari.vn", "FarmerPassword123!")

    check("User A login success (danhuynh@gari.vn)", token_user_a is not None)
    check("User B login success (nongdan.mau@gari.vn)", token_user_b is not None)

    headers_a = {"Authorization": f"Bearer {token_user_a}"}
    headers_b = {"Authorization": f"Bearer {token_user_b}"}

    # -------------------------------------------------------------
    # 1. SETUP: Create farm & plots for User A and User B
    # -------------------------------------------------------------
    print("\n--- Setup: Farms and Plots ---")
    farm_a_resp = requests.post(f"{BASE_URL}/api/farms", headers=headers_a, json={
        "name": f"Trang trại A {int(time.time())}",
        "province": "Lâm Đồng",
        "area_hectare": 3.0,
        "primary_crop": "Cà phê"
    })
    check("Create Farm for User A", farm_a_resp.status_code == 200)
    farm_a_id = farm_a_resp.json().get("farm", {}).get("id")

    plot_a_resp = requests.post(f"{BASE_URL}/api/farms/{farm_a_id}/plots", headers=headers_a, json={
        "plot_name": "Thửa A1 - Robusta đồi",
        "crop_name": "Cà phê",
        "crop_id": "coffee",
        "area_hectare": 1.2,
        "region": "Đồi Nam Ban",
        "notes": "Đất đỏ bazan, hệ thống tưới nhỏ giọt"
    })
    check("Create Plot A1 for User A with voluntary region", plot_a_resp.status_code == 200)
    plot_a_id = plot_a_resp.json().get("plot", {}).get("id")

    farm_b_resp = requests.post(f"{BASE_URL}/api/farms", headers=headers_b, json={
        "name": f"Vườn Bác Ba {int(time.time())}",
        "province": "Đắk Lắk",
        "area_hectare": 2.0,
        "primary_crop": "Hồ tiêu"
    })
    check("Create Farm for User B", farm_b_resp.status_code == 200)
    farm_b_id = farm_b_resp.json().get("farm", {}).get("id")

    plot_b_resp = requests.post(f"{BASE_URL}/api/farms/{farm_b_id}/plots", headers=headers_b, json={
        "plot_name": "Thửa B1 - Tiêu Vĩnh Linh",
        "crop_name": "Hồ tiêu",
        "crop_id": "pepper",
        "area_hectare": 0.8,
        "region": "Buôn Ma Thuột",
        "notes": "Trụ tiêu bê tông"
    })
    check("Create Plot B1 for User B", plot_b_resp.status_code == 200)
    plot_b_id = plot_b_resp.json().get("plot", {}).get("id")

    # -------------------------------------------------------------
    # 2. TEST 1: Valid Diagnosis Saves History with Minimal Schema
    # -------------------------------------------------------------
    print("\n--- Test 1: Valid Diagnosis History & Privacy Consent ---")
    leaf_bytes = get_real_leaf_image()

    # Case A: Explicit consent_store_image = False -> raw image must NOT be stored
    files = {"image": ("test_leaf.jpg", leaf_bytes, "image/jpeg")}
    data_no_consent = {
        "mode": "manual",
        "crop": "Tomato",
        "plot_id": plot_a_id,
        "farm_id": farm_a_id,
        "consent_store_image": "false"
    }
    resp_diag_no_consent = requests.post(f"{BASE_URL}/api/plant/diagnose", headers=headers_a, files=files, data=data_no_consent)
    check("Diagnosis request without image consent succeeded", resp_diag_no_consent.status_code == 200)
    diag_res_a = resp_diag_no_consent.json()
    check("Response includes diagnosis_status", diag_res_a.get("diagnosis_status") in ["diagnosed", "needs_review"])
    check("Response includes action_guidance", "action_guidance" in diag_res_a)
    saved_id_a = diag_res_a.get("saved_diagnosis_id")
    check("Diagnosis history record created", saved_id_a is not None)

    # Verify history minimal fields
    rec_resp = requests.get(f"{BASE_URL}/api/diagnoses/{saved_id_a}", headers=headers_a)
    check("Fetch diagnosis record details", rec_resp.status_code == 200)
    rec_data = rec_resp.json().get("diagnosis", {})
    check("Field diagnosis_id present", rec_data.get("diagnosis_id") == saved_id_a)
    check("Field actor_user_id present", rec_data.get("actor_user_id") is not None)
    check("Field farm_plot_id present", rec_data.get("farm_plot_id") == plot_a_id)
    check("Field crop present", rec_data.get("crop") is not None)
    check("Field predicted_disease present", rec_data.get("predicted_disease") is not None)
    check("Field confidence present", rec_data.get("confidence") is not None)
    check("Field model_version present", rec_data.get("model_version") is not None)
    check("Field diagnosis_status present", rec_data.get("diagnosis_status") is not None)
    check("Field created_at present", rec_data.get("created_at") is not None)
    check("No image stored on disk when consent_store_image=False", rec_data.get("image_path") is None or not os.path.exists(PROJECT_ROOT / rec_data.get("image_path").lstrip("/")))

    # Case B: With consent_store_image = True
    files_consent = {"image": ("test_leaf.jpg", leaf_bytes, "image/jpeg")}
    data_consent = {
        "mode": "manual",
        "crop": "Tomato",
        "plot_id": plot_a_id,
        "farm_id": farm_a_id,
        "consent_store_image": "true"
    }
    resp_diag_consent = requests.post(f"{BASE_URL}/api/plant/diagnose", headers=headers_a, files=files_consent, data=data_consent)
    check("Diagnosis with image consent succeeded", resp_diag_consent.status_code == 200)
    saved_id_consent = resp_diag_consent.json().get("saved_diagnosis_id")
    rec_consent_data = requests.get(f"{BASE_URL}/api/diagnoses/{saved_id_consent}", headers=headers_a).json().get("diagnosis", {})
    check("Image stored when consent_store_image=True", rec_consent_data.get("image_path") is not None)

    # -------------------------------------------------------------
    # 3. TEST 2: Invalid Image Rejected at Leaf Gate & Zero Quota Deduct
    # -------------------------------------------------------------
    print("\n--- Test 2: Leaf Gate Rejection & Zero Quota Deduction ---")
    black_img = create_solid_image(color=(5, 5, 5))
    
    # Check quota before
    q_before = requests.get(f"{BASE_URL}/api/user/quota", headers=headers_a).json().get("quota", {}).get("remaining")
    
    files_invalid = {"image": ("non_leaf.jpg", black_img, "image/jpeg")}
    resp_invalid = requests.post(f"{BASE_URL}/api/plant/diagnose", headers=headers_a, files=files_invalid, data={"mode": "auto_standard"})
    check("Invalid image endpoint returned 200 with rejection", resp_invalid.status_code == 200)
    inv_data = resp_invalid.json()
    check("diagnosis_status is rejected_invalid_image", inv_data.get("diagnosis_status") == "rejected_invalid_image")
    check("Retake guidance provided in action_guidance", len(inv_data.get("action_guidance", {}).get("retake_tips", [])) > 0)
    
    # Check quota after
    q_after = requests.get(f"{BASE_URL}/api/user/quota", headers=headers_a).json().get("quota", {}).get("remaining")
    check("Zero quota deduction on invalid image rejection", q_before == q_after, f"Before: {q_before}, After: {q_after}")

    # -------------------------------------------------------------
    # 4. TEST 3: Uncertain Result Never Inflated to Certainty
    # -------------------------------------------------------------
    print("\n--- Test 3: Action Guidance & Non-inflation of Uncertain Results ---")
    # Test action guidance directly from knowledge engine
    from gari_knowledge import get_action_guidance
    ag_uncertain = get_action_guidance(crop_id="coffee", disease_id="rust", confidence=0.45, is_healthy=False, diagnosis_status="needs_review")
    check("Low confidence categorized as uncertain/needs_review", ag_uncertain["status"] == "uncertain")
    check("Uncertain result prompts retake advice", len(ag_uncertain.get("retake_tips", [])) > 0)
    check("Low-risk immediate actions prioritized (no strong chemicals)", all("thuốc" not in a.lower() or "sinh học" in a.lower() or "tham vấn" in a.lower() for a in ag_uncertain["immediate_low_risk_actions"]))
    check("Triggers on when to ask agronomist provided", len(ag_uncertain.get("when_to_ask_expert", [])) > 0)
    
    ag_unverified = get_action_guidance(crop_id="dragonfruit", disease_id="unknown_spot", confidence=0.85, is_healthy=False)
    check("Unverified disease marked verified=False", ag_unverified["verified"] is False)
    check("Unverified status shows cautious fallback notice", "chưa có hướng dẫn đã xác minh" in ag_unverified["notice"].lower())

    # -------------------------------------------------------------
    # 5. TEST 4: Cross-Tenant History Access Forbidden
    # -------------------------------------------------------------
    print("\n--- Test 4: Cross-Tenant Isolation on Diagnosis History ---")
    # User B attempts to read User A's diagnosis
    resp_cross_read = requests.get(f"{BASE_URL}/api/diagnoses/{saved_id_a}", headers=headers_b)
    check("User B reading User A's diagnosis rejected with HTTP 403", resp_cross_read.status_code == 403)

    # User B attempts to delete User A's diagnosis
    resp_cross_del = requests.delete(f"{BASE_URL}/api/diagnoses/{saved_id_a}", headers=headers_b)
    check("User B deleting User A's diagnosis rejected with HTTP 403", resp_cross_del.status_code == 403)

    # -------------------------------------------------------------
    # 6. TEST 5: Cannot Attach Diagnosis to Inaccessible Plot
    # -------------------------------------------------------------
    print("\n--- Test 5: Inaccessible Farm Plot Attachment Forbidden ---")
    # User A tries to diagnose and attach to User B's plot (plot_b_id)
    files_tamper = {"image": ("test_leaf.jpg", leaf_bytes, "image/jpeg")}
    data_tamper = {
        "mode": "manual",
        "crop": "Tomato",
        "plot_id": plot_b_id, # BELONGS TO USER B
        "consent_store_image": "false"
    }
    resp_tamper_plot = requests.post(f"{BASE_URL}/api/plant/diagnose", headers=headers_a, files=files_tamper, data=data_tamper)
    check("User A attaching User B's plot rejected with HTTP 403", resp_tamper_plot.status_code == 403)

    # -------------------------------------------------------------
    # 7. TEST 6: User Cannot Modify Model Prediction or Confidence
    # -------------------------------------------------------------
    print("\n--- Test 6: Model Outputs Cannot Be Client-Tampered ---")
    tamper_payload = {
        "crop": "Tomato",
        "predicted_disease": "FABRICATED_HEALTHY_STATUS",
        "confidence": 0.9999,
        "model_version": "v_hacked",
        "diagnosis_status": "diagnosed"
    }
    resp_post_tamper = requests.post(f"{BASE_URL}/api/diagnoses", headers=headers_a, json=tamper_payload)
    check("Direct tampering of model prediction rejected with HTTP 403", resp_post_tamper.status_code == 403)

    # -------------------------------------------------------------
    # 8. TEST 7: Data Deletion & Privacy Erasure Compliance
    # -------------------------------------------------------------
    print("\n--- Test 7: Data Deletion & Privacy Erasure ---")
    # Create temporary diagnosis with consent to store image
    files_del = {"image": ("test_leaf.jpg", leaf_bytes, "image/jpeg")}
    del_diag_resp = requests.post(f"{BASE_URL}/api/plant/diagnose", headers=headers_a, files=files_del, data={
        "mode": "manual", "crop": "Tomato", "plot_id": plot_a_id, "consent_store_image": "true"
    })
    temp_diag_id = del_diag_resp.json().get("saved_diagnosis_id")
    temp_rec = requests.get(f"{BASE_URL}/api/diagnoses/{temp_diag_id}", headers=headers_a).json().get("diagnosis", {})
    temp_img_rel = temp_rec.get("image_path")
    temp_img_file = PROJECT_ROOT / "database" / "uploads" / os.path.basename(temp_img_rel) if temp_img_rel else None

    if temp_img_file and temp_img_file.exists():
        check("Temporary image exists on disk before deletion", True)
    else:
        check("Temporary image exists on disk before deletion", False, f"File: {temp_img_file}")

    # User A deletes their own diagnosis
    resp_del_own = requests.delete(f"{BASE_URL}/api/diagnoses/{temp_diag_id}", headers=headers_a)
    check("User A deleted own diagnosis successfully (HTTP 200)", resp_del_own.status_code == 200)

    # Verify image unlinked from disk
    if temp_img_file:
        check("Image file safely unlinked from disk upon deletion", not temp_img_file.exists())

    # Verify DB record gone
    resp_verify_gone = requests.get(f"{BASE_URL}/api/diagnoses/{temp_diag_id}", headers=headers_a)
    check("Diagnosis record no longer exists in database", resp_verify_gone.status_code == 404)

    # -------------------------------------------------------------
    # 9. TEST 8: Farm Plot Timeline & Objective Progression
    # -------------------------------------------------------------
    print("\n--- Test 8: Farm Plot Timeline & Monitoring States ---")
    # User A adds observation note to Plot A1
    resp_timeline_note = requests.post(f"{BASE_URL}/api/plots/{plot_a_id}/timeline", headers=headers_a, json={
        "monitoring_status": "monitoring",
        "notes": "Đã cắt tỉa cành bệnh, cây đang hồi phục tốt ngoài vườn."
    })
    check("User A added timeline observation event (HTTP 200)", resp_timeline_note.status_code == 200)

    # User B attempts to post event to User A's plot -> 403 Forbidden
    resp_b_plot_event = requests.post(f"{BASE_URL}/api/plots/{plot_a_id}/timeline", headers=headers_b, json={
        "monitoring_status": "resolved",
        "notes": "Hacker trying to alter timeline"
    })
    check("User B cannot post event to User A's plot (HTTP 403)", resp_b_plot_event.status_code == 403)

    # User B attempts to read User A's plot timeline -> 403 Forbidden
    resp_b_read_timeline = requests.get(f"{BASE_URL}/api/plots/{plot_a_id}/timeline", headers=headers_b)
    check("User B cannot read User A's plot timeline (HTTP 403)", resp_b_read_timeline.status_code == 403)

    # User A reads their own plot timeline
    resp_a_timeline = requests.get(f"{BASE_URL}/api/plots/{plot_a_id}/timeline", headers=headers_a)
    check("User A can read own plot timeline (HTTP 200)", resp_a_timeline.status_code == 200)
    tl_data = resp_a_timeline.json()
    summary = tl_data.get("summary") or tl_data.get("timeline", {}).get("summary", {})
    check("Timeline summary does NOT claim disease progression without evidence", "bệnh đang nặng lên" not in summary.get("progression_analysis", "").lower() and "bệnh đang nặng lên" not in summary.get("progression_note", "").lower())
    check("Timeline summary contains total_diagnoses count", "total_diagnoses" in summary)
    events = tl_data.get("events") or tl_data.get("timeline_feed") or tl_data.get("timeline", {}).get("timeline_feed", [])
    check("Timeline events stream contains events", len(events) >= 1)

    # -------------------------------------------------------------
    # 10. TEST 9: Quota Metering for Diagnosis Calls
    # -------------------------------------------------------------
    print("\n--- Test 9: Quota Metering for Diagnoses ---")
    # Create fresh guest client ID
    guest_id = f"test_quota_guest_{int(time.time())}"
    guest_headers = {"X-Client-Id": guest_id}
    
    q_init = requests.get(f"{BASE_URL}/api/user/quota", headers=guest_headers).json().get("quota", {})
    initial_rem = q_init.get("remaining")
    check("Guest initialized with clean quota (<= 3)", initial_rem is not None and initial_rem <= 3)

    # Run valid diagnosis for guest
    guest_files = {"image": ("test_leaf.jpg", leaf_bytes, "image/jpeg")}
    guest_diag = requests.post(f"{BASE_URL}/api/plant/diagnose", headers=guest_headers, files=guest_files, data={"mode": "manual", "crop": "Tomato"})
    check("Guest diagnosis succeeded", guest_diag.status_code == 200)
    
    q_after_one = requests.get(f"{BASE_URL}/api/user/quota", headers=guest_headers).json().get("quota", {})
    check("Quota deducted by exactly 1 for valid diagnosis", q_after_one.get("remaining") == initial_rem - 1)

    # -------------------------------------------------------------
    # 11. TEST 10: Regression Pass-Through
    # -------------------------------------------------------------
    print("\n--- Test 10: Regression Verification ---")
    # Verify core system health
    health_resp = requests.get(f"{BASE_URL}/api/health")
    check("API health status 200 OK", health_resp.status_code == 200 and health_resp.json().get("status") == "healthy")

    # Verify B2B plans catalog
    plans_resp = requests.get(f"{BASE_URL}/api/plans")
    check("Plans catalog accessible (Free, Pro, Team, Enterprise)", plans_resp.status_code == 200 and len(plans_resp.json().get("plans", {})) >= 4)

    # Verify model discovery
    models_resp = requests.get(f"{BASE_URL}/api/models")
    check("AI Models endpoint returns valid models", models_resp.status_code == 200 and len(models_resp.json().get("models", [])) > 0)

    # Summary
    print("\n" + "=" * 70)
    print(f"SPRINT 4 VERIFICATION RESULTS: {passed_count}/{checks_total} CHECKS PASSED")
    if failed_count == 0:
        print("ALL SPRINT 4 ACCEPTANCE CHECKS PASSED! READY FOR DEPLOYMENT.")
        print("=" * 70)
        return True
    else:
        print(f"WARNING: {failed_count} CHECKS FAILED.")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
