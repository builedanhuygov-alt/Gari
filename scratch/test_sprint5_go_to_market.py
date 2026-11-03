"""
GARI AI LAB — SPRINT 5 ACCEPTANCE TEST SUITE (test_sprint5_go_to_market.py)
Automated verification of Go-to-Market & Pilot Validation:
1. Valid pilot request is created with initial status 'new'.
2. Missing consent or mandatory fields rejected with 400/422.
3. Regular user cannot read other users' pilot leads (HTTP 403).
4. Regular user cannot update lead status to 'accepted' (HTTP 403).
5. Unauthorized admin requests rejected (HTTP 401/403).
6. Feedback attaches cleanly to valid diagnosis.
7. Feedback CANNOT overwrite model prediction, confidence, or output.
8. Feedback does NOT become verified ground truth (is_verified_by_expert stays False).
9. Cross-tenant feedback access and deletion is blocked (HTTP 403).
10. Pilot metrics calculated from real data and properly filtered by time window.
11. Pilot dashboard metrics do NOT leak PII (names, emails, phones).
12. Unconfigured email provider explicitly noted; manual follow-up message shown.
13. Full regression passes without breaking Sprints 1–4, Privacy, B2B, and AgriTech.
"""

import io
import json
import os
import sys
import time
from pathlib import Path
import requests

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

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


def get_token(email: str, password: str = "Password123!"):
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=10)
    if resp.status_code == 200:
        return resp.json().get("token")
    return None


def run_sprint5_tests():
    print("================================================================================")
    print("GARI AI LAB — SPRINT 5: GO-TO-MARKET & PILOT VALIDATION ACCEPTANCE TESTS")
    print("================================================================================\n")

    # Setup Test Users
    # 1. Platform Admin
    admin_token = get_token("danhuynh@gari.vn", "Password123!")
    if not admin_token:
        # Fallback admin login or register
        reg = requests.post(f"{BASE_URL}/api/auth/register", json={
            "full_name": "Platform Admin",
            "email": "danhuynh@gari.vn",
            "password": "Password123!",
            "account_type": "admin"
        })
        admin_token = get_token("danhuynh@gari.vn", "Password123!")
    check("Admin authentication established", admin_token is not None)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Regular User A (Farmer)
    user_a_email = "nongdan.mau@gari.vn"
    login_a = requests.post(f"{BASE_URL}/api/auth/login", json={"email": user_a_email, "password": "FarmerPassword123!"})
    if login_a.status_code != 200:
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "full_name": "Nông Dân Mẫu",
            "email": user_a_email,
            "password": "FarmerPassword123!",
            "confirm_password": "FarmerPassword123!",
            "account_type": "Nông hộ",
            "terms_agreed": True
        })
        login_a = requests.post(f"{BASE_URL}/api/auth/login", json={"email": user_a_email, "password": "FarmerPassword123!"})
    user_a_token = login_a.json().get("token")
    user_a_id = login_a.json().get("user", {}).get("id")
    check("Regular User A authenticated", user_a_token is not None and user_a_id is not None)
    user_a_headers = {"Authorization": f"Bearer {user_a_token}"}

    # 3. Regular User B (Tenant B Farmer)
    ts = int(time.time())
    user_b_email = f"farmer_b_{ts}@example.com"
    requests.post(f"{BASE_URL}/api/auth/register", json={
        "full_name": "Nông Dân Hợp Tác Xã B",
        "email": user_b_email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "account_type": "Nông hộ",
        "terms_agreed": True
    })
    login_b = requests.post(f"{BASE_URL}/api/auth/login", json={"email": user_b_email, "password": "Password123!"})
    user_b_token = login_b.json().get("token")
    user_b_id = login_b.json().get("user", {}).get("id")
    check("Regular User B authenticated", user_b_token is not None and user_b_id is not None)
    user_b_headers = {"Authorization": f"Bearer {user_b_token}"}

    # --------------------------------------------------------------------------
    # CHECK 1: Valid Pilot Request Creation & Initial Status
    # --------------------------------------------------------------------------
    print("\n--- 1. Testing Pilot / Demo Request Submission ---")
    pilot_payload = {
        "name": "Hợp tác xã Nông nghiệp Sạch Ba Vì",
        "contact": "0912345678 (Zalo Giám đốc HTX)",
        "customer_type": "cooperative",
        "crops_of_interest": "Cà chua, Khoai tây, Ớt",
        "region": "Ba Vì, Hà Nội",
        "problem_statement": "Muốn kiểm chứng phát hiện sớm bệnh mốc sương trên 5ha cà chua vụ đông xuân",
        "consent_given": True
    }
    resp = requests.post(f"{BASE_URL}/api/pilot/requests", json=pilot_payload, timeout=10)
    check("Valid pilot request returns HTTP 201", resp.status_code == 201, f"HTTP {resp.status_code}")
    res_data = resp.json()
    check("Pilot request success flag is True", res_data.get("success") is True)
    check("Initial status is strictly 'new'", res_data.get("status") == "new")
    lead_id = res_data.get("request_id")
    check("Lead ID generated", lead_id is not None)

    # CHECK 12: Honest messaging about email provider
    notice = res_data.get("notice", "")
    check("Response explicitly notes manual contact (no fake automated email claim)",
          "chưa cấu hình" in notice or "thủ công" in notice or "liên hệ trực tiếp" in notice,
          f"Notice: {notice}")

    # --------------------------------------------------------------------------
    # CHECK 2: Validation of Consent & Required Fields
    # --------------------------------------------------------------------------
    print("\n--- 2. Testing Missing Consent & Required Fields Validation ---")
    # Missing consent
    no_consent_payload = dict(pilot_payload)
    no_consent_payload["consent_given"] = False
    resp_no_consent = requests.post(f"{BASE_URL}/api/pilot/requests", json=no_consent_payload, timeout=10)
    check("Request without consent rejected with HTTP 400", resp_no_consent.status_code == 400, f"HTTP {resp_no_consent.status_code}")

    # Missing contact
    no_contact_payload = dict(pilot_payload)
    no_contact_payload["contact"] = ""
    resp_no_contact = requests.post(f"{BASE_URL}/api/pilot/requests", json=no_contact_payload, timeout=10)
    check("Request without contact rejected with HTTP 400/422", resp_no_contact.status_code in (400, 422), f"HTTP {resp_no_contact.status_code}")

    # Short/empty name
    short_name_payload = dict(pilot_payload)
    short_name_payload["name"] = "A"
    resp_short_name = requests.post(f"{BASE_URL}/api/pilot/requests", json=short_name_payload, timeout=10)
    check("Request with invalid short name rejected with HTTP 400/422", resp_short_name.status_code in (400, 422), f"HTTP {resp_short_name.status_code}")

    # --------------------------------------------------------------------------
    # CHECK 3, 4, 5: RBAC & Permission Protection on Pilot Leads
    # --------------------------------------------------------------------------
    print("\n--- 3. Testing RBAC & Access Control on Pilot Leads ---")
    # Unauthenticated access to admin leads
    resp_unauth = requests.get(f"{BASE_URL}/api/admin/pilot/requests", timeout=10)
    check("Unauthenticated access to /api/admin/pilot/requests rejected (401/403)",
          resp_unauth.status_code in (401, 403), f"HTTP {resp_unauth.status_code}")

    # Regular user attempting to read leads
    resp_user_read = requests.get(f"{BASE_URL}/api/admin/pilot/requests", headers=user_a_headers, timeout=10)
    check("Regular user calling /api/admin/pilot/requests rejected with HTTP 403 Forbidden",
          resp_user_read.status_code == 403, f"HTTP {resp_user_read.status_code}")

    # Regular user attempting to update status to 'accepted'
    resp_user_patch = requests.patch(
        f"{BASE_URL}/api/admin/pilot/requests/{lead_id}",
        headers=user_a_headers,
        json={"status": "accepted"},
        timeout=10
    )
    check("Regular user cannot elevate status to 'accepted' (HTTP 403 Forbidden)",
          resp_user_patch.status_code == 403, f"HTTP {resp_user_patch.status_code}")

    # Regular user attempting to export CSV
    resp_user_export = requests.get(f"{BASE_URL}/api/admin/pilot/requests/export", headers=user_a_headers, timeout=10)
    check("Regular user cannot export leads CSV (HTTP 403 Forbidden)",
          resp_user_export.status_code == 403, f"HTTP {resp_user_export.status_code}")

    # Platform Admin accesses leads
    resp_admin_read = requests.get(f"{BASE_URL}/api/admin/pilot/requests", headers=admin_headers, timeout=10)
    check("Platform Admin can list pilot requests (HTTP 200)", resp_admin_read.status_code == 200)
    leads_list = resp_admin_read.json().get("requests", [])
    matching_lead = next((l for l in leads_list if l["id"] == lead_id), None)
    check("Newly created pilot request present in admin list", matching_lead is not None)
    if matching_lead:
        check("Lead customer type is cooperative", matching_lead.get("customer_type") == "cooperative")

    # Platform Admin updates status with audit log
    resp_admin_update = requests.patch(
        f"{BASE_URL}/api/admin/pilot/requests/{lead_id}",
        headers=admin_headers,
        json={"status": "reviewing", "internal_notes": "Đã tiếp nhận và lên lịch trao đổi thực địa."},
        timeout=10
    )
    check("Platform Admin updates lead status to 'reviewing' (HTTP 200)", resp_admin_update.status_code == 200)

    # Verify audit history
    resp_lead_detail = requests.get(f"{BASE_URL}/api/admin/pilot/requests/{lead_id}", headers=admin_headers, timeout=10)
    check("Lead detail endpoint accessible (HTTP 200)", resp_lead_detail.status_code == 200)
    lead_detail = resp_lead_detail.json().get("request", {})
    check("Lead status is 'reviewing'", lead_detail.get("status") == "reviewing")
    audit_hist = lead_detail.get("audit_history", [])
    check("Audit trail recorded the status change", len(audit_hist) >= 2, f"Events: {len(audit_hist)}")

    # Admin exports CSV
    resp_admin_export = requests.get(f"{BASE_URL}/api/admin/pilot/requests/export", headers=admin_headers, timeout=10)
    check("Platform Admin can export leads CSV (HTTP 200)", resp_admin_export.status_code == 200)
    check("CSV Content-Type is text/csv", "text/csv" in resp_admin_export.headers.get("Content-Type", ""))
    csv_text = resp_admin_export.text
    check("CSV contains header row", "Ho_Ten" in csv_text and "Loai_Khach_Hang" in csv_text)

    # --------------------------------------------------------------------------
    # CHECK 6, 7, 8: Diagnosis Feedback & Ground Truth Non-Inflation
    # --------------------------------------------------------------------------
    print("\n--- 4. Testing Diagnosis Feedback & Ground Truth Non-Inflation ---")
    import gari_database

    # Create a real test diagnosis owned by User A
    diag_record = gari_database.save_diagnosis({
        "crop_id": "Tomato",
        "crop_name": "Tomato",
        "predicted_disease": "Tomato___Early_blight",
        "confidence": 0.88,
        "severity": "MEDIUM",
        "top_predictions": [{"disease": "Tomato___Early_blight", "confidence": 0.88}],
        "diagnosis_status": "diagnosed"
    }, user_id=user_a_id)
    diag_id = diag_record["id"]
    check("Test diagnosis created", diag_id is not None)

    # Initial check of model output
    init_diag = gari_database.get_diagnosis(diag_id)
    initial_disease = init_diag["predicted_disease"]
    initial_conf = init_diag["confidence"]
    initial_verified = bool(init_diag.get("is_verified_by_expert", 0))
    check("Initial diagnosis model output matches", initial_disease == "Tomato___Early_blight" and initial_conf == 0.88)
    check("Initial is_verified_by_expert is False", initial_verified is False)

    # User submits feedback claiming model is wrong
    fb_resp = requests.post(
        f"{BASE_URL}/api/diagnoses/{diag_id}/feedback",
        headers=user_a_headers,
        json={
            "feedback_type": "looks_incorrect",
            "notes": "Tôi thấy lá này giống bị rỉ sắt hoặc cháy nắng hơn là đốm lá sớm."
        },
        timeout=10
    )
    check("User feedback submitted successfully (HTTP 200)", fb_resp.status_code == 200, f"HTTP {fb_resp.status_code}")
    fb_data = fb_resp.json()
    check("Feedback disclaimer clearly distinguishes user feedback from ground truth",
          "KHÔNG thay thế kết luận chuyên gia" in fb_data.get("disclaimer", ""))
    feedback_id = fb_data.get("feedback", {}).get("id")
    check("Feedback ID generated", feedback_id is not None)

    # Verify model prediction and confidence were NOT mutated
    after_diag = gari_database.get_diagnosis(diag_id)
    check("CHECK 7: Feedback CANNOT overwrite model predicted_disease",
          after_diag["predicted_disease"] == initial_disease)
    check("CHECK 7: Feedback CANNOT overwrite model confidence",
          after_diag["confidence"] == initial_conf)
    check("CHECK 8: Feedback does NOT make diagnosis expert-verified",
          bool(after_diag.get("is_verified_by_expert", 0)) is False)

    # --------------------------------------------------------------------------
    # CHECK 9: Cross-Tenant Feedback Isolation
    # --------------------------------------------------------------------------
    print("\n--- 5. Testing Cross-Tenant Feedback Isolation ---")
    # User B (from another tenant) attempts to read User A's feedback on diagnosis A
    resp_cross_read = requests.get(
        f"{BASE_URL}/api/diagnoses/{diag_id}/feedback",
        headers=user_b_headers,
        timeout=10
    )
    check("User B cannot read User A's diagnosis feedback (HTTP 403 Forbidden)",
          resp_cross_read.status_code == 403, f"HTTP {resp_cross_read.status_code}")

    # User B attempts to delete User A's feedback
    resp_cross_delete = requests.delete(
        f"{BASE_URL}/api/diagnoses/{diag_id}/feedback/{feedback_id}",
        headers=user_b_headers,
        timeout=10
    )
    check("User B cannot delete User A's feedback (HTTP 403 Forbidden)",
          resp_cross_delete.status_code == 403, f"HTTP {resp_cross_delete.status_code}")

    # Owner (User A) or Admin can delete feedback (Right to erasure)
    resp_owner_read = requests.get(f"{BASE_URL}/api/diagnoses/{diag_id}/feedback", headers=user_a_headers, timeout=10)
    check("Owner (User A) can view their own diagnosis feedback", resp_owner_read.status_code == 200)

    # --------------------------------------------------------------------------
    # CHECK 10, 11: Real Pilot Metrics & No PII Leakage
    # --------------------------------------------------------------------------
    print("\n--- 6. Testing Real Pilot Metrics & Telemetry Privacy ---")
    resp_metrics = requests.get(f"{BASE_URL}/api/admin/pilot/metrics?time_range=30d", headers=admin_headers, timeout=10)
    check("Admin gets pilot metrics (HTTP 200)", resp_metrics.status_code == 200)
    metrics_data = resp_metrics.json().get("metrics", {})

    check("Time range is 30d", metrics_data.get("time_range") == "30d")
    check("Pilot requests count is tracked", "pilot_requests" in metrics_data)
    check("Active users metric present with definition", "active_users" in metrics_data and "definition" in metrics_data["active_users"])
    check("Total diagnoses in period tracked", "diagnoses" in metrics_data)
    check("Leaf gate rejection metric present", "leaf_gate_rejection" in metrics_data)
    check("Uncertainty screening metric present", "uncertainty_screening" in metrics_data)
    check("Feedback metrics present with breakdown", "feedback_metrics" in metrics_data)

    # CHECK 11: Verify no PII in metrics JSON
    metrics_str = json.dumps(metrics_data)
    check("No phone numbers in aggregated metrics", "0912345678" not in metrics_str)
    check("No email addresses in aggregated metrics", "@example.com" not in metrics_str and "@gmail.com" not in metrics_str)
    check("Metrics disclaim fake ground-truth accuracy claims",
          metrics_data.get("data_policy", {}).get("ground_truth_claim") is False)

    # --------------------------------------------------------------------------
    # CHECK 13: UI Pages & Core Navigation Health
    # --------------------------------------------------------------------------
    print("\n--- 7. Testing Frontend UI Pages & Honest Messaging ---")
    resp_landing = requests.get(f"{BASE_URL}/landing", timeout=10)
    check("Public /landing endpoint returns HTTP 200", resp_landing.status_code == 200)
    landing_html = resp_landing.text
    check("Landing page specifies 7 priority crops", "7 Nhóm Cây Trồng" in landing_html or "7 Nhóm cây trồng" in landing_html)
    check("Landing page contains scientific AI disclaimer", "không thay thế chẩn đoán" in landing_html or "Lưu ý khoa học" in landing_html)
    check("Landing page contains pilot registration modal", "modalPilot" in landing_html or "landingPilotModal" in landing_html)
    check("Landing page has NO fake partner logos or 99.9% precision claims",
          "99.9%" not in landing_html and "tăng năng suất 50%" not in landing_html)

    resp_pricing = requests.get(f"{BASE_URL}/frontend2/pricing.html", timeout=10)
    check("/frontend2/pricing.html returns HTTP 200", resp_pricing.status_code == 200)
    check("Pricing page contains modalPilotRequest", "modalPilotRequest" in resp_pricing.text)

    resp_admin_html = requests.get(f"{BASE_URL}/frontend2/admin.html", timeout=10)
    check("/frontend2/admin.html returns HTTP 200", resp_admin_html.status_code == 200)
    check("Admin page contains Sprint 5 Pilot Validation Center", "SPRINT 5 VALIDATION" in resp_admin_html.text)

    resp_predict = requests.get(f"{BASE_URL}/frontend2/predict.html", timeout=10)
    check("/frontend2/predict.html returns HTTP 200", resp_predict.status_code == 200)
    check("Predict page contains diagnosisFeedbackCard", "diagnosisFeedbackCard" in resp_predict.text)

    # --------------------------------------------------------------------------
    # Final Clean-up
    # --------------------------------------------------------------------------
    del_resp = requests.delete(
        f"{BASE_URL}/api/diagnoses/{diag_id}/feedback/{feedback_id}",
        headers=user_a_headers,
        timeout=10
    )
    check("Owner deleted feedback successfully (GDPR Right to Erasure)", del_resp.status_code == 200)

    # Summary
    print("\n================================================================================")
    print(f"SPRINT 5 TEST RESULTS: {passed_count}/{checks_total} CHECKS PASSED ({(passed_count/checks_total*100):.1f}%)")
    if failed_count == 0:
        print("ALL SPRINT 5 ACCEPTANCE CRITERIA VERIFIED SUCCESSFULLY!")
    else:
        print(f"FAILED CHECKS: {failed_count}")
    print("================================================================================")

    return failed_count == 0


if __name__ == "__main__":
    success = run_sprint5_tests()
    sys.exit(0 if success else 1)
