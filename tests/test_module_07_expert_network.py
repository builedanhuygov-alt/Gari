"""
GARI Module 07 — Expert Network & Consultation Workflow Test Suite
Verifies:
1. Expert application submission with qualifications, crops, institution.
2. Host Admin review & approval with strict privilege separation (Expert != Host Admin).
3. Host Admin suspend and reactivate expert lifecycle with audit logging.
4. Farmer creates consultation case from AI Leaf Diagnosis with symptoms & urgency.
5. Farm data privacy consent enforcement (masking farm name and phone when consent is withheld).
6. Expert claims open case and transitions status to in_review.
7. Expert requests additional agronomic info (status -> waiting_user_info).
8. Farmer provides additional info (status -> in_review).
9. Expert resolves case with IPM prescription and farmer closes case with 5-star rating.
10. Strict expert isolation boundary (Expert B cannot access or mutate Expert A's claimed cases).
"""

import unittest
import sys
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi.testclient import TestClient
import sqlite3
import uuid
from datetime import datetime, timezone

from api_server import app
import gari_experts
from gari_database import get_connection

client = TestClient(app)


def _create_user(name_prefix="User", account_type="farmer"):
    unique_id = uuid.uuid4().hex[:8]
    email = f"{name_prefix.lower()}_{unique_id}@example.com"
    pwd = "Password123!"
    resp = client.post("/api/auth/register", json={
        "email": email,
        "password": pwd,
        "confirm_password": pwd,
        "full_name": f"{name_prefix} {unique_id}",
        "account_type": account_type
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    user = data.get("user", {})
    return user, token, {"Authorization": f"Bearer {token}"}


def _create_host_admin():
    user, token, headers = _create_user("HostAdmin", account_type="admin")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_host_admin = 1, is_admin = 1 WHERE id = ?", (user["id"],))
        conn.commit()
    return user, token, headers


def _create_verified_expert(name_prefix="Agronomist"):
    user, token, headers = _create_user(name_prefix, account_type="expert")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_expert = 1, is_host_admin = 0 WHERE id = ?", (user["id"],))
        cursor.execute("""
            INSERT OR REPLACE INTO expert_profiles (
                user_id, full_name, display_title, institution, degree, specialization,
                primary_crops_json, farming_regions_json, status, is_active, rating, cases_resolved_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', 1, 5.0, 0)
        """, (
            user["id"],
            user["full_name"],
            "Kỹ sư Bảo vệ Thực vật",
            "Viện BVTV Quốc Gia",
            "Thạc sĩ",
            "Bệnh học cây trồng nhiệt đới",
            '["Tomato", "Coffee", "Rice"]',
            '["Toàn quốc"]'
        ))
        conn.commit()
    return user, token, headers


class TestModule07ExpertNetwork(unittest.TestCase):

    def test_01_expert_application_submission(self):
        """1. Regular user submits expert application with degrees, crops, institution."""
        user, token, headers = _create_user("Applicant")
        payload = {
            "full_name": user["full_name"],
            "phone": "0987654321",
            "title": "Thạc sĩ BVTV",
            "organization": "Viện KHKT Nông Lâm Nghiệp Tây Nguyên",
            "specialties": ["Coffee", "Pepper", "Durian"],
            "years_experience": 8,
            "license_number": "BVTV-TN-2024",
            "degree_details": "Thạc sĩ Nông nghiệp - ĐH Nông Lâm Huế",
            "bio": "Hơn 8 năm công tác thực địa chẩn đoán sâu bệnh cây công nghiệp."
        }
        resp = client.post("/api/expert/apply", json=payload, headers=headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertTrue(data.get("success"))
        app_id = data.get("application_id")
        self.assertIsNotNone(app_id)

        # Verify application in database
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM expert_applications WHERE id = ?", (app_id,))
            app_record = cursor.fetchone()
            self.assertIsNotNone(app_record)
            self.assertIn(app_record["status"], ("pending", "submitted"))
            self.assertEqual(app_record["user_id"], user["id"])
            self.assertEqual(app_record["institution"], "Viện KHKT Nông Lâm Nghiệp Tây Nguyên")

    def test_02_host_admin_review_approval_privilege_separation(self):
        """2. Host Admin approves expert application. Verify privilege separation (is_expert != is_host_admin)."""
        applicant, _, app_headers = _create_user("Candidate")
        apply_resp = client.post("/api/expert/apply", json={
            "full_name": applicant["full_name"],
            "phone": "0911223344",
            "organization": "Đại học Cần Thơ",
            "specialties": ["Rice", "Durian"],
            "years_experience": 10,
            "title": "TS Nông học"
        }, headers=app_headers)
        self.assertEqual(apply_resp.status_code, 200)
        app_id = apply_resp.json()["application_id"]

        # Host admin approves
        host_user, host_token, host_headers = _create_host_admin()
        review_resp = client.post(f"/api/host/experts/applications/{app_id}/review", json={
            "action": "approve",
            "admin_notes": "Bằng cấp và kinh nghiệm 10 năm phù hợp tiêu chuẩn GARI",
            "commission_rate": 0.15
        }, headers=host_headers)
        self.assertEqual(review_resp.status_code, 200, review_resp.text)
        review_data = review_resp.json()
        self.assertTrue(review_data.get("success"))

        # Check candidate user in database
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_expert, is_host_admin, account_type FROM users WHERE id = ?", (applicant["id"],))
            user_row = cursor.fetchone()
            self.assertEqual(user_row["is_expert"], 1)
            self.assertEqual(user_row["account_type"], "expert")
            # CRITICAL PRIVILEGE SEPARATION: Expert status must NOT grant Host Admin rights!
            self.assertEqual(user_row["is_host_admin"], 0)

            # Check audit log
            cursor.execute("SELECT * FROM host_audit_logs WHERE action_type = 'expert_application_approved' ORDER BY id DESC LIMIT 1")
            audit = cursor.fetchone()
            self.assertIsNotNone(audit)
            self.assertEqual(audit["host_admin_id"], host_user["id"])

        # Verify candidate cannot access host endpoints
        app_forbidden = client.get("/api/host/experts", headers=app_headers)
        self.assertEqual(app_forbidden.status_code, 403)

    def test_03_host_admin_suspend_and_reactivate_expert(self):
        """3. Host Admin suspends expert, revoking portal access; then reactivates."""
        expert, expert_token, expert_headers = _create_verified_expert("DrKhoa")
        host, host_token, host_headers = _create_host_admin()

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM expert_profiles WHERE user_id = ?", (expert["id"],))
            prof = cursor.fetchone()
            expert_prof_id = prof["id"]

        # Suspend expert
        sus_resp = client.patch(f"/api/host/experts/{expert_prof_id}/status", json={
            "is_active": False,
            "status": "suspended"
        }, headers=host_headers)
        self.assertEqual(sus_resp.status_code, 200, sus_resp.text)

        # Verify user is_expert is revoked to 0
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_expert FROM users WHERE id = ?", (expert["id"],))
            self.assertEqual(cursor.fetchone()["is_expert"], 0)

        # Suspended expert cannot access expert portal queue
        forbidden_resp = client.get("/api/expert/portal/cases", headers=expert_headers)
        self.assertEqual(forbidden_resp.status_code, 403)

        # Reactivate expert
        act_resp = client.patch(f"/api/host/experts/{expert_prof_id}/status", json={
            "is_active": True,
            "status": "active"
        }, headers=host_headers)
        self.assertEqual(act_resp.status_code, 200)

        # Verify user is_expert restored to 1
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_expert FROM users WHERE id = ?", (expert["id"],))
            self.assertEqual(cursor.fetchone()["is_expert"], 1)

        # Can access portal again
        allowed_resp = client.get("/api/expert/portal/cases", headers=expert_headers)
        self.assertEqual(allowed_resp.status_code, 200)

    def test_04_farmer_creates_case_from_leaf_diagnosis(self):
        """4. Farmer creates consultation case linked to AI diagnosis with urgency and symptoms."""
        farmer, farmer_token, farmer_headers = _create_user("FarmerNam")

        # Create diagnosis record in DB
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO diagnoses (
                    user_id, crop_id, crop_name, predicted_disease, disease_name_vi,
                    confidence, severity, diagnosis_status, created_at
                ) VALUES (?, 'tomato', 'Cà chua', 'Tomato Late Blight', 'Bệnh mốc sương cà chua', 0.94, 'HIGH', 'diagnosed', CURRENT_TIMESTAMP)
            """, (farmer["id"],))
            conn.commit()
            diag_id = cursor.lastrowid

        payload = {
            "diagnosis_id": diag_id,
            "symptoms_description": "Vết cháy sũng nước lan từ chóp lá, có lớp mốc trắng mỏng",
            "urgency": "high",
            "farm_name": "Nông trại Nam Cà Mau",
            "phone": "0909123456",
            "consent_share_farm_data": 1
        }
        resp = client.post("/api/expert/cases", json=payload, headers=farmer_headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        case_data = resp.json()["case"]
        case_id = case_data["id"]

        self.assertEqual(case_data["crop_name"], "Cà chua")
        self.assertEqual(case_data["suspected_disease"], "Bệnh mốc sương cà chua")
        self.assertEqual(case_data["status"], "submitted")
        self.assertEqual(case_data["urgency"], "high")
        self.assertEqual(case_data["consent_share_farm_data"], 1)

        # Verify activity history has 'created'
        act_resp = client.get(f"/api/expert/cases/{case_id}/activities", headers=farmer_headers)
        self.assertEqual(act_resp.status_code, 200)
        activities = act_resp.json()["activities"]
        self.assertTrue(any(a["action"] == "created" for a in activities))

    def test_05_farm_privacy_consent_masking(self):
        """5. Verify data masking when farmer unchecks consent_share_farm_data (consent=0)."""
        farmer, farmer_token, farmer_headers = _create_user("PrivateFarmer")
        expert, expert_token, expert_headers = _create_verified_expert("DrPrivacy")

        # Farmer creates case with consent_share_farm_data = 0
        create_resp = client.post("/api/expert/cases", json={
            "symptoms_description": "Lá cà chua có đốm nâu tròn đồng tâm",
            "farm_name": "Khu Nông Nghiệp Công Nghệ Cao Củ Chi",
            "farmer_name": "Nguyễn Văn Bảo Mật",
            "phone": "0988776655",
            "urgency": "medium",
            "consent_share_farm_data": 0
        }, headers=farmer_headers)
        self.assertEqual(create_resp.status_code, 200)
        case_id = create_resp.json()["case"]["id"]

        # 1) When Farmer (Owner) views case -> sees unmasked original data
        farmer_view = client.get(f"/api/expert/cases/{case_id}", headers=farmer_headers)
        self.assertEqual(farmer_view.status_code, 200)
        f_case = farmer_view.json()["case"]
        self.assertEqual(f_case["farm_name"], "Khu Nông Nghiệp Công Nghệ Cao Củ Chi")
        self.assertEqual(f_case["phone"], "0988776655")

        # 2) When Expert views case -> sees masked farm name and phone!
        expert_view = client.get(f"/api/expert/cases/{case_id}", headers=expert_headers)
        self.assertEqual(expert_view.status_code, 200)
        e_case = expert_view.json()["case"]
        self.assertEqual(e_case["farm_id"], None)
        self.assertIn("BẢO MẬT", e_case["farm_name"])
        self.assertIn("ẨN SỐ ĐIỆN THOẠI", e_case["phone"])

    def test_06_expert_claim_case(self):
        """6. Verified Expert claims open case: status transitions to in_review and logs activity."""
        farmer, _, f_headers = _create_user("FarmerA")
        expert, _, exp_headers = _create_verified_expert("DrClaim")

        c_resp = client.post("/api/expert/cases", json={
            "symptoms_description": "Vàng lá gân xanh trên cây cam sành",
            "urgency": "medium"
        }, headers=f_headers)
        case_id = c_resp.json()["case"]["id"]

        # Expert claims case
        claim_resp = client.post(f"/api/expert/cases/{case_id}/claim", headers=exp_headers)
        self.assertEqual(claim_resp.status_code, 200, claim_resp.text)
        claimed_case = claim_resp.json()["case"]
        self.assertEqual(claimed_case["status"], "in_review")
        self.assertEqual(claimed_case["assigned_expert_id"], expert["id"])

        # Cannot be claimed again by another expert
        other_exp, _, other_exp_headers = _create_verified_expert("DrOther")
        double_claim = client.post(f"/api/expert/cases/{case_id}/claim", headers=other_exp_headers)
        self.assertIn(double_claim.status_code, (400, 403))

        # Verify activity history has 'claimed'
        act_resp = client.get(f"/api/expert/cases/{case_id}/activities", headers=exp_headers)
        self.assertEqual(act_resp.status_code, 200)
        acts = act_resp.json()["activities"]
        self.assertTrue(any(a["action"] == "claimed" and a["new_value"] == "in_review" for a in acts))

    def test_07_expert_requests_additional_info(self):
        """7. Claimed Expert requests additional field info: status transitions to waiting_user_info."""
        farmer, _, f_headers = _create_user("FarmerB")
        expert, _, exp_headers = _create_verified_expert("DrInfo")

        c_resp = client.post("/api/expert/cases", json={
            "symptoms_description": "Đốm rỉ sắt trên lá cà phê",
            "urgency": "medium"
        }, headers=f_headers)
        case_id = c_resp.json()["case"]["id"]
        client.post(f"/api/expert/cases/{case_id}/claim", headers=exp_headers)

        # Expert requests info
        req_resp = client.post(f"/api/expert/cases/{case_id}/request-info", json={
            "question": "Bà con chụp thêm ảnh mặt dưới lá và cho biết tuổi vườn cà phê?"
        }, headers=exp_headers)
        self.assertEqual(req_resp.status_code, 200, req_resp.text)
        res_data = req_resp.json()["case"]
        self.assertEqual(res_data["status"], "waiting_user_info")

        # Verify message added to case messages
        msg_resp = client.get(f"/api/expert/cases/{case_id}/messages", headers=exp_headers)
        self.assertEqual(msg_resp.status_code, 200)
        messages = msg_resp.json()["messages"]
        self.assertTrue(any(m["sender_role"] == "expert" and "mặt dưới lá" in m["message"] for m in messages))

    def test_08_farmer_provides_additional_info(self):
        """8. Farmer replies to expert request: status transitions back to in_review."""
        farmer, _, f_headers = _create_user("FarmerC")
        expert, _, exp_headers = _create_verified_expert("DrReply")

        c_resp = client.post("/api/expert/cases", json={
            "symptoms_description": "Lá lúa có sọc vàng",
            "urgency": "high"
        }, headers=f_headers)
        case_id = c_resp.json()["case"]["id"]
        client.post(f"/api/expert/cases/{case_id}/claim", headers=exp_headers)
        client.post(f"/api/expert/cases/{case_id}/request-info", json={
            "question": "Lúa giai đoạn nào và đã bón đạm bao nhiêu kg/sào?"
        }, headers=exp_headers)

        # Farmer provides follow-up info
        prov_resp = client.post(f"/api/expert/cases/{case_id}/provide-info", json={
            "info": "Lúa đẻ nhánh rộ được 35 ngày, đã bón 8kg urê/sào 500m2 tuần trước."
        }, headers=f_headers)
        self.assertEqual(prov_resp.status_code, 200, prov_resp.text)
        case_data = prov_resp.json()["case"]
        self.assertEqual(case_data["status"], "in_review")

        # Verify message added
        msg_resp = client.get(f"/api/expert/cases/{case_id}/messages", headers=f_headers)
        messages = msg_resp.json()["messages"]
        self.assertTrue(any(m["sender_role"] == "farmer" and "35 ngày" in m["message"] for m in messages))

    def test_09_expert_resolves_case_with_ipm_prescription_and_farmer_closes(self):
        """9. Expert resolves case with IPM prescription and farmer closes case with 5-star rating."""
        farmer, _, f_headers = _create_user("FarmerD")
        expert, _, exp_headers = _create_verified_expert("DrResolve")

        c_resp = client.post("/api/expert/cases", json={
            "symptoms_description": "Thối nhũn bắp cải sau mưa",
            "urgency": "urgent"
        }, headers=f_headers)
        case_id = c_resp.json()["case"]["id"]
        client.post(f"/api/expert/cases/{case_id}/claim", headers=exp_headers)

        # Expert resolves case
        res_payload = {
            "resolution_notes": "Xác định bệnh Thối nhũn do vi khuẩn Pectobacterium carotovorum.",
            "diagnosis_correction": "Bacterial Soft Rot",
            "prescription_data": {
                "active_ingredient": "Kasugamycin hoặc Oxytetracycline",
                "dosage": "20ml/bình 16L",
                "ipm_measures": [
                    "Thu gom tiêu hủy cây bệnh",
                    "Rút cạn nước mương rãnh",
                    "Không bón thêm phân đạm hóa học"
                ]
            }
        }
        res_resp = client.post(f"/api/expert/cases/{case_id}/resolve", json=res_payload, headers=exp_headers)
        self.assertEqual(res_resp.status_code, 200, res_resp.text)
        res_case = res_resp.json()["case"]
        self.assertEqual(res_case["status"], "resolved")
        self.assertIn("Kasugamycin", res_case["expert_notes"])

        # Verify expert's cases_resolved_count incremented
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT cases_resolved_count FROM expert_profiles WHERE user_id = ?", (expert["id"],))
            self.assertGreaterEqual(cursor.fetchone()["cases_resolved_count"], 1)

        # Farmer closes case and gives 5 stars
        close_resp = client.post(f"/api/expert/cases/{case_id}/close", json={
            "rating": 5,
            "feedback_notes": "Phác đồ rất hiệu quả, sau 3 ngày ruộng đã ngưng thối!"
        }, headers=f_headers)
        self.assertEqual(close_resp.status_code, 200, close_resp.text)
        closed_case = close_resp.json()["case"]
        self.assertEqual(closed_case["status"], "closed")
        self.assertEqual(closed_case["rating"], 5)
        self.assertIsNotNone(closed_case["closed_at"])

    def test_10_expert_isolation_boundary(self):
        """10. Expert B cannot view or modify a case claimed by Expert A (HTTP 403 Forbidden)."""
        farmer, _, f_headers = _create_user("FarmerBoundary")
        expert_a, _, exp_a_headers = _create_verified_expert("ExpertAlpha")
        expert_b, _, exp_b_headers = _create_verified_expert("ExpertBeta")

        # Create and claim case by Expert A
        c_resp = client.post("/api/expert/cases", json={
            "symptoms_description": "Vết chấm kim trên lá ớt",
            "urgency": "medium"
        }, headers=f_headers)
        case_id = c_resp.json()["case"]["id"]
        client.post(f"/api/expert/cases/{case_id}/claim", headers=exp_a_headers)

        # Expert B attempts to view Case A -> 403 Forbidden
        view_b = client.get(f"/api/expert/cases/{case_id}", headers=exp_b_headers)
        self.assertEqual(view_b.status_code, 403)

        # Expert B attempts to request info on Case A -> 403 Forbidden
        req_b = client.post(f"/api/expert/cases/{case_id}/request-info", json={
            "question": "Can thiệp trái phép"
        }, headers=exp_b_headers)
        self.assertEqual(req_b.status_code, 403)

        # Expert B attempts to resolve Case A -> 403 Forbidden
        res_b = client.post(f"/api/expert/cases/{case_id}/resolve", json={
            "resolution_notes": "Can thiệp trái phép"
        }, headers=exp_b_headers)
        self.assertEqual(res_b.status_code, 403)


if __name__ == "__main__":
    unittest.main()
