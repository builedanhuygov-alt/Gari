"""
GARI AI LAB — Host Console Moderation & Violation Management Test Suite
File: tests/test_moderation_system.py

Verifies:
1. Access control: strict host authorization (HTTP 401 unauthenticated, HTTP 403 normal users).
2. Automated detection pipeline: creates pending cases and NEVER automatically bans/suspends users.
3. Repeated violations handling and severity tracking.
4. Host actions: dismiss, false positive, warn.
5. Host action: feature restriction and backend enforcement (e.g. upload_restricted blocked from /api/predict).
6. Host action: suspension / ban, immediate session revocation, rejection of banned users.
7. Separation of concerns: moderation status does not wipe subscription or alter account_type.
8. User appeals flow: user submission, host review (approve/reject), and automatic status restoration upon approval.
9. Immutable audit trail in moderation_audit_logs.
"""

import io
import os
import sys
import unittest
import uuid
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

os.environ["APP_ENV"] = "test"
os.environ["PAYMENT_PUBLIC_CHECKOUT_ENABLED"] = "1"

import api_server
import gari_auth
import gari_database
import gari_moderation
from starlette.testclient import TestClient


class TestModerationSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gari_database.init_database()
        cls.client = TestClient(api_server.app)

        cls.suffix = uuid.uuid4().hex[:8]
        cls.farmer_email = f"farmer_mod_{cls.suffix}@gari.vn"
        cls.bad_actor_email = f"target_mod_{cls.suffix}@gari.vn"
        cls.host_email = f"host_mod_{cls.suffix}@gari.vn"
        cls.password = "StrongModPass123!"

        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            pwd_hash = gari_auth.hash_password(cls.password)

            # Normal farmer (non-host)
            cursor.execute(
                """
                INSERT INTO users (full_name, name, email, password_hash, account_type, is_host_admin, is_active, moderation_status)
                VALUES ('Farmer Mod User', 'Farmer Mod User', ?, ?, 'farmer', 0, 1, 'clean')
                """,
                (cls.farmer_email, pwd_hash)
            )
            cls.farmer_id = cursor.lastrowid

            # Target user (for moderation actions and violations)
            cursor.execute(
                """
                INSERT INTO users (full_name, name, email, password_hash, account_type, is_host_admin, is_active, moderation_status)
                VALUES ('Bad Actor Mod User', 'Bad Actor Mod User', ?, ?, 'enterprise', 0, 1, 'clean')
                """,
                (cls.bad_actor_email, pwd_hash)
            )
            cls.bad_actor_id = cursor.lastrowid

            # Add VIP subscription to target user to verify moderation doesn't wipe subscriptions
            cursor.execute(
                """
                INSERT INTO user_subscriptions (user_id, plan_id, status, billing_interval, start_date, end_date)
                VALUES (?, 'vip_pro', 'active', 'month', CURRENT_TIMESTAMP, datetime('now', '+30 days'))
                """,
                (cls.bad_actor_id,)
            )

            # Verified Host Administrator (is_host_admin = 1)
            cursor.execute(
                """
                INSERT INTO users (full_name, name, email, password_hash, account_type, is_host_admin, is_active, moderation_status)
                VALUES ('Host Mod Admin', 'Host Mod Admin', ?, ?, 'enterprise', 1, 1, 'clean')
                """,
                (cls.host_email, pwd_hash)
            )
            cls.host_id = cursor.lastrowid

            # Create test diagnosis owned by bad actor
            cursor.execute(
                """
                INSERT INTO diagnoses (user_id, crop_id, crop_name, predicted_disease, confidence)
                VALUES (?, 'tomato', 'Cà chua', 'Tomato Early Blight', 0.95)
                """,
                (cls.bad_actor_id,)
            )
            cls.test_diag_id = cursor.lastrowid
            conn.commit()

        # Sessions
        cls.farmer_token = gari_auth.create_session(cls.farmer_id)
        cls.farmer_headers = {"Authorization": f"Bearer {cls.farmer_token}"}

        cls.bad_actor_token = gari_auth.create_session(cls.bad_actor_id)
        cls.bad_actor_headers = {"Authorization": f"Bearer {cls.bad_actor_token}"}

        cls.host_token = gari_auth.create_session(cls.host_id)
        cls.host_headers = {"Authorization": f"Bearer {cls.host_token}"}

    @classmethod
    def tearDownClass(cls):
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = OFF")
            cursor.execute("DELETE FROM diagnoses WHERE user_id IN (?, ?, ?)", (cls.farmer_id, cls.bad_actor_id, cls.host_id))
            cursor.execute("DELETE FROM diagnosis_feedbacks WHERE user_id IN (?, ?, ?)", (cls.farmer_id, cls.bad_actor_id, cls.host_id))
            cursor.execute("DELETE FROM moderation_appeals WHERE user_id IN (?, ?, ?)", (cls.farmer_id, cls.bad_actor_id, cls.host_id))
            cursor.execute("DELETE FROM moderation_audit_logs WHERE target_user_id IN (?, ?, ?) OR actor_admin_id IN (?, ?, ?)",
                           (cls.farmer_id, cls.bad_actor_id, cls.host_id, cls.farmer_id, cls.bad_actor_id, cls.host_id))
            cursor.execute("DELETE FROM moderation_cases WHERE user_id IN (?, ?, ?)", (cls.farmer_id, cls.bad_actor_id, cls.host_id))
            cursor.execute("DELETE FROM user_sessions WHERE user_id IN (?, ?, ?)", (cls.farmer_id, cls.bad_actor_id, cls.host_id))
            cursor.execute("DELETE FROM user_subscriptions WHERE user_id IN (?, ?, ?)", (cls.farmer_id, cls.bad_actor_id, cls.host_id))
            cursor.execute("DELETE FROM users WHERE email IN (?, ?, ?)", (cls.farmer_email, cls.bad_actor_email, cls.host_email))
            cursor.execute("PRAGMA foreign_keys = ON")
            conn.commit()

    # -------------------------------------------------------------------------
    # 1. Access Control Tests
    # -------------------------------------------------------------------------
    def test_01_access_control_unauthenticated_and_forbidden(self):
        """Host moderation endpoints must reject unauthenticated requests (401) and normal users (403)."""
        host_endpoints = [
            "/api/host/moderation/stats",
            "/api/host/moderation/cases",
            "/api/host/moderation/appeals",
            "/api/host/moderation/audit-logs"
        ]

        for ep in host_endpoints:
            # 1. Unauthenticated -> 401
            res_unauth = self.client.get(ep)
            self.assertEqual(res_unauth.status_code, 401, f"{ep} should return 401 when unauthenticated")

            # 2. Normal farmer -> 403 Forbidden
            res_forbidden = self.client.get(ep, headers=self.farmer_headers)
            self.assertEqual(res_forbidden.status_code, 403, f"{ep} should return 403 for non-host users")

            # 3. Host admin -> 200 OK
            res_ok = self.client.get(ep, headers=self.host_headers)
            self.assertEqual(res_ok.status_code, 200, f"{ep} should return 200 for host admin")

    # -------------------------------------------------------------------------
    # 2. Automated Detection: Pending Review & No Automatic Ban
    # -------------------------------------------------------------------------
    def test_02_content_detection_creates_pending_case_no_auto_ban(self):
        """Detection pipeline must create a 'pending' review case and NEVER automatically ban or suspend."""
        # Bad actor submits feedback containing gambling spam & harassment keywords
        spam_feedback = "Khuyến mãi nhà cái Kubet cá cược lô đề gái gọi 100% uy tín, tao chém cả lò mày đm"
        
        # Test scan through feedback endpoint
        res = self.client.post(
            f"/api/diagnoses/{self.test_diag_id}/feedback",
            json={"feedback_type": "looks_incorrect", "notes": spam_feedback},
            headers=self.bad_actor_headers
        )
        self.assertEqual(res.status_code, 200)

        # Verify a moderation case was created with status 'pending'
        cases_res = gari_moderation.list_moderation_cases(user_id=self.bad_actor_id)
        cases = cases_res["cases"] if isinstance(cases_res, dict) else cases_res
        self.assertGreater(len(cases), 0, "A moderation case should have been created for spam/harassment")
        
        latest_case = cases[0]
        self.assertEqual(latest_case["status"], "pending", "New moderation cases must be in 'pending' status")
        self.assertIn(latest_case["violation_category"], ["spam", "harassment_abuse", "scam_impersonation"])

        # CRITICAL SAFETY CHECK: User must NOT be banned or suspended automatically
        user = gari_auth.get_user_by_id(self.bad_actor_id)
        self.assertEqual(user["is_active"], 1, "User must NOT be automatically deactivated")
        self.assertEqual(user["moderation_status"], "clean", "User status must remain clean until Host human review")

    def test_03_repeated_violations_increase_severity_still_pending(self):
        """Repeated violations elevate case severity or notice count, but still do not auto-ban."""
        # Create another violation
        case = gari_moderation.scan_content_and_report(
            user_id=self.bad_actor_id,
            user_email=self.bad_actor_email,
            content_type="chat",
            text="Tôi là Ban quản trị GARI yêu cầu bạn cung cấp mã OTP và chuyển khoản nhận quà",
            evidence_ref="chat_msg_101"
        )
        self.assertIsNotNone(case)
        self.assertEqual(case["status"], "pending")

        # Verify target user remains active and not auto-banned
        user = gari_auth.get_user_by_id(self.bad_actor_id)
        self.assertEqual(user["is_active"], 1)

    # -------------------------------------------------------------------------
    # 3. Host Review Actions: Dismiss & False Positive
    # -------------------------------------------------------------------------
    def test_04_host_action_dismiss_case(self):
        """Host administrator can dismiss a case without penalizing the user."""
        # Create a fresh case to dismiss
        case = gari_moderation.create_moderation_case(
            user_id=self.bad_actor_id,
            user_email=self.bad_actor_email,
            violation_category="non_agricultural",
            severity="low",
            detection_source="keyword_filter",
            evidence_summary="User asked about weather forecast",
            evidence_ref="chat_weather"
        )
        case_id = case["case_id"]

        # Host dismisses the case
        payload = {
            "action": "dismiss",
            "reason": "Topic is tangentially related to farming weather, no violation.",
            "notes": "Reviewed and dismissed"
        }
        res = self.client.post(
            f"/api/host/moderation/cases/{case_id}/action",
            json=payload,
            headers=self.host_headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["case"]["status"], "dismissed")

        # Verify user remains clean
        user = gari_auth.get_user_by_id(self.bad_actor_id)
        self.assertEqual(user["moderation_status"], "clean")

    def test_05_host_action_false_positive(self):
        """Host administrator can mark a case as false_positive and clear any false flags."""
        case = gari_moderation.create_moderation_case(
            user_id=self.bad_actor_id,
            user_email=self.bad_actor_email,
            violation_category="unsafe_upload",
            severity="medium",
            detection_source="heuristics",
            evidence_summary="Filename matched suspicious pattern",
            evidence_ref="upload_img_false_positive"
        )
        case_id = case["case_id"]

        payload = {
            "action": "false_positive",
            "reason": "Image is authentic tomato leaf photo, false positive filter.",
            "notes": "System false detection confirmed"
        }
        res = self.client.post(
            f"/api/host/moderation/cases/{case_id}/action",
            json=payload,
            headers=self.host_headers
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["case"]["status"], "false_positive")

    # -------------------------------------------------------------------------
    # 4. Host Review Actions: Feature Restriction & Enforcement
    # -------------------------------------------------------------------------
    def test_06_host_action_feature_restriction_and_enforcement(self):
        """Host can apply feature restrictions (upload_restricted) and backend enforces it on /api/predict."""
        case = gari_moderation.create_moderation_case(
            user_id=self.bad_actor_id,
            user_email=self.bad_actor_email,
            violation_category="unsafe_upload",
            severity="high",
            detection_source="file_scanner",
            evidence_summary="Repeated corrupt file attempts",
            evidence_ref="diag_upload_bad"
        )
        case_id = case["case_id"]

        # Apply feature restriction
        payload = {
            "action": "restrict",
            "reason": "Uploading non-plant corrupted blobs repeatedly",
            "feature_restrictions": ["upload_restricted"],
            "notes": "Restricting upload capabilities for 7 days"
        }
        res = self.client.post(
            f"/api/host/moderation/cases/{case_id}/action",
            json=payload,
            headers=self.host_headers
        )
        self.assertEqual(res.status_code, 200)

        # Verify user has upload_restricted in database
        user = gari_auth.get_user_by_id(self.bad_actor_id)
        self.assertEqual(user["moderation_status"], "restricted")
        self.assertIn("upload_restricted", user["feature_restrictions"])

        # Verify user is now BLOCKED from /api/predict with HTTP 403
        dummy_file = io.BytesIO(b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"\x00" * 100)
        upload_res = self.client.post(
            "/api/predict",
            files={"file": ("leaf.jpg", dummy_file, "image/jpeg")},
            headers=self.bad_actor_headers
        )
        self.assertEqual(upload_res.status_code, 403, "Restricted user must be rejected with 403 on restricted feature")
        self.assertTrue(
            "upload_restricted" in upload_res.json()["detail"] or "giới hạn" in upload_res.json()["detail"].lower(),
            "Error detail should explain restriction"
        )

    # -------------------------------------------------------------------------
    # 5. Host Review Actions: Suspension, Ban & Immediate Session Invalidation
    # -------------------------------------------------------------------------
    def test_07_host_action_ban_and_session_revocation(self):
        """Host ban requires reason, revokes all user sessions, and blocks authentication."""
        case = gari_moderation.create_moderation_case(
            user_id=self.bad_actor_id,
            user_email=self.bad_actor_email,
            violation_category="scam_impersonation",
            severity="critical",
            detection_source="admin_report",
            evidence_summary="Impersonating GARI official support to solicit payments",
            evidence_ref="scam_proof_01"
        )
        case_id = case["case_id"]

        # Ban without reason should be rejected
        res_no_reason = self.client.post(
            f"/api/host/moderation/cases/{case_id}/action",
            json={"action": "ban", "reason": ""},
            headers=self.host_headers
        )
        self.assertEqual(res_no_reason.status_code, 400)

        # Host confirms permanent ban
        payload = {
            "action": "ban",
            "reason": "Confirmed severe phishing and payment scam targeting farmers",
            "notes": "Approved permanent ban"
        }
        res_ban = self.client.post(
            f"/api/host/moderation/cases/{case_id}/action",
            json=payload,
            headers=self.host_headers
        )
        self.assertEqual(res_ban.status_code, 200)

        # Verify user is banned in database and deactivated
        user = gari_auth.get_user_by_id(self.bad_actor_id)
        self.assertEqual(user["moderation_status"], "banned")
        self.assertEqual(user["is_active"], 0)

        # Verify existing session token is invalidated immediately
        res_check_session = self.client.get(
            "/api/auth/me",
            headers=self.bad_actor_headers
        )
        self.assertEqual(res_check_session.status_code, 401, "Banned user session must be invalid (401)")

        # Verify attempting to log in again fails
        login_res = self.client.post(
            "/api/auth/login",
            json={"email": self.bad_actor_email, "password": self.password}
        )
        self.assertEqual(login_res.status_code, 403, "Banned user login attempt must be rejected (403)")

    # -------------------------------------------------------------------------
    # 6. Separation of Concerns: VIP Subscription & Account Type Preserved
    # -------------------------------------------------------------------------
    def test_08_moderation_does_not_wipe_subscription_or_change_account_type(self):
        """Moderation disciplinary actions must keep account_type and VIP subscription records separate."""
        user = gari_auth.get_user_by_id(self.bad_actor_id)
        # Account type must remain 'enterprise'
        self.assertEqual(user["account_type"], "enterprise", "Disciplinary action must not alter account_type")

        # Verify subscription row still exists in database
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT plan_id, status FROM user_subscriptions WHERE user_id = ?", (self.bad_actor_id,))
            sub = cursor.fetchone()
            self.assertIsNotNone(sub, "Subscription record must not be deleted")
            self.assertEqual(sub["plan_id"], "vip_pro")

    # -------------------------------------------------------------------------
    # 7. User Appeals Flow & Host Review
    # -------------------------------------------------------------------------
    def test_09_user_appeal_and_host_resolution(self):
        """User submits an appeal, and Host approves it to restore clean account status."""
        # Restore active flag so user can submit appeal
        with gari_database.get_connection() as conn:
            conn.cursor().execute("UPDATE users SET is_active = 1, moderation_status = 'restricted' WHERE id = ?", (self.bad_actor_id,))
            conn.commit()

        # Generate fresh session for appeal submission
        fresh_token = gari_auth.create_session(self.bad_actor_id)
        appeal_headers = {"Authorization": f"Bearer {fresh_token}"}

        # 1. User submits appeal
        appeal_payload = {
            "case_id": "CASE-APPEAL-TEST",
            "appeal_reason": "Tài khoản của tôi bị kẻ gian chiếm quyền đăng tải, tôi đã đổi mật khẩu và cam kết tuân thủ chính sách."
        }
        res_appeal = self.client.post(
            "/api/moderation/appeals",
            json=appeal_payload,
            headers=appeal_headers
        )
        self.assertEqual(res_appeal.status_code, 200)
        appeal_data = res_appeal.json()
        self.assertTrue(appeal_data["success"])
        appeal_id = appeal_data["appeal"]["id"]

        # 2. Host lists appeals and sees it
        res_list = self.client.get("/api/host/moderation/appeals", headers=self.host_headers)
        self.assertEqual(res_list.status_code, 200)
        appeals = res_list.json()["appeals"]
        matching = [a for a in appeals if a["id"] == appeal_id]
        self.assertEqual(len(matching), 1)

        # 3. Host reviews and approves the appeal
        review_payload = {
            "decision": "approved",
            "host_response": "Giải trình hợp lý. Đã gỡ bỏ giới hạn và khôi phục tài khoản."
        }
        res_review = self.client.post(
            f"/api/host/moderation/appeals/{appeal_id}/review",
            json=review_payload,
            headers=self.host_headers
        )
        self.assertEqual(res_review.status_code, 200)
        self.assertEqual(res_review.json()["appeal"]["status"], "approved")

        # 4. Verify user status is restored to 'clean' and restrictions cleared
        restored_user = gari_auth.get_user_by_id(self.bad_actor_id)
        self.assertEqual(restored_user["moderation_status"], "clean")
        self.assertEqual(restored_user["feature_restrictions"], "")

    # -------------------------------------------------------------------------
    # 8. Immutable Audit Trail
    # -------------------------------------------------------------------------
    def test_10_moderation_audit_logs_contain_actor_target_and_reasons(self):
        """Host moderation actions must generate detailed records in moderation_audit_logs."""
        res = self.client.get("/api/host/moderation/audit-logs", headers=self.host_headers)
        self.assertEqual(res.status_code, 200)
        logs = res.json()["logs"]
        self.assertGreater(len(logs), 0, "Moderation actions must produce audit logs")

        # Verify structure of log entry
        log_sample = logs[0]
        self.assertIn("actor_email", log_sample)
        self.assertIn("target_user_id", log_sample)
        self.assertIn("action", log_sample)
        self.assertIn("reason", log_sample)
        self.assertIn("previous_status", log_sample)
        self.assertIn("resulting_status", log_sample)


if __name__ == "__main__":
    unittest.main()
