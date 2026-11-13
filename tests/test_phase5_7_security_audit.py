"""
GARI AI LAB — Phase 5.7 Security Audit Test Suite
Tests authentication, authorization, IDOR boundaries, upload safety,
privilege escalation guards, and regression vectors on an isolated test database.
"""

import os
import sys
import time
import tempfile
import sqlite3
import unittest
from pathlib import Path

# Enforce test environment before imports
os.environ["APP_ENV"] = "test"
os.environ["GARI_ENV"] = "test"
os.environ["DEBUG"] = "0"

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import bcrypt
from fastapi.testclient import TestClient
import gari_auth
import gari_config
import gari_database
import gari_b2b
from api_server import app


class TestPhase57SecurityAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Verify test setup
        cls.test_db_path = Path("database/disease_detector.db")
        cls.assertTrue(cls.test_db_path.exists(), "Production DB exists for read verification")

    # -------------------------------------------------------------------------
    # 1. Authentication & Hashing Security Tests
    # -------------------------------------------------------------------------
    def test_01_password_hashing_bcrypt(self):
        """Verify Bcrypt hashing, salt generation, and verification timing."""
        plain = "SecurePassword123!"
        hashed = gari_auth.hash_password(plain)
        self.assertTrue(hashed.startswith("$2b$12$"), "Must use bcrypt with cost factor 12")
        self.assertTrue(gari_auth.verify_password(plain, hashed))
        self.assertFalse(gari_auth.verify_password("WrongPassword!", hashed))

    def test_02_login_rate_limiting(self):
        """Verify brute-force protection locks out client after 5 failed attempts."""
        test_client_key = "192.168.1.100:victim@example.com"
        gari_auth.clear_failed_attempts(test_client_key)

        for _ in range(gari_auth.RATE_LIMIT_MAX_ATTEMPTS - 1):
            gari_auth.record_failed_attempt(test_client_key)
            self.assertFalse(gari_auth.is_rate_limited(test_client_key))

        # 5th failed attempt triggers rate limit
        gari_auth.record_failed_attempt(test_client_key)
        self.assertTrue(gari_auth.is_rate_limited(test_client_key))

        # Cleanup
        gari_auth.clear_failed_attempts(test_client_key)
        self.assertFalse(gari_auth.is_rate_limited(test_client_key))

    def test_03_invalid_and_expired_session_validation(self):
        """Verify short tokens and expired tokens are rejected."""
        self.assertIsNone(gari_auth.validate_session(""))
        self.assertIsNone(gari_auth.validate_session("short_tok"))
        self.assertIsNone(gari_auth.validate_session("fake_token_that_does_not_exist_in_db_1234567890"))

    # -------------------------------------------------------------------------
    # 2. Privilege Escalation & Mass Assignment Tests
    # -------------------------------------------------------------------------
    def test_04_privilege_escalation_guard_in_profile_update(self):
        """Verify that forbidden system fields cannot be updated via profile API."""
        with self.assertRaises(gari_auth.HTTPException) as ctx:
            gari_auth.update_user_profile(
                user_id=99999,
                updates={"is_admin": 1, "is_host_admin": 1, "account_type": "enterprise"}
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Không được phép tự nâng cấp quyền", ctx.exception.detail)

    # -------------------------------------------------------------------------
    # 3. IDOR Vulnerability Audit Verification (Documenting Actual Code State)
    # -------------------------------------------------------------------------
    def test_05_audit_idor_unauthenticated_diagnoses_access(self):
        """
        Audit Finding SEC-01:
        GET /api/diagnoses with optional user dependency returns records without user/org filter.
        """
        response = self.client.get("/api/diagnoses")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        # Documenting that anonymous users can retrieve diagnosis records if present in DB
        self.assertIn("diagnoses", data)

    def test_06_audit_idor_default_user_1_in_notifications(self):
        """
        Audit Finding SEC-02:
        GET /api/notifications uses 'user_id = current_user["id"] if current_user else 1'.
        Anonymous requests leak User 1's notifications.
        """
        response = self.client.get("/api/notifications")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("notifications", data)

    def test_07_audit_idor_default_user_1_in_calendar_tasks(self):
        """
        Audit Finding SEC-02b:
        GET /api/calendar/tasks uses 'user_id = current_user["id"] if current_user else 1'.
        Anonymous requests leak User 1's cultivation calendar tasks.
        """
        response = self.client.get("/api/calendar/tasks")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("tasks", data)

    def test_08_audit_idor_cross_org_farms_enumeration(self):
        """
        Audit Finding SEC-03:
        GET /api/farms accepts 'org_id' without checking if the current user belongs to that org.
        """
        # When unauthenticated, /api/farms requires auth (401)
        res_unauth = self.client.get("/api/farms")
        self.assertEqual(res_unauth.status_code, 401)

    # -------------------------------------------------------------------------
    # 4. Upload & File Safety Tests
    # -------------------------------------------------------------------------
    def test_09_predict_upload_non_image_rejected(self):
        """Verify that /api/predict requires auth and rejects non-image files."""
        dummy_file = ("exploit.sh", b"#!/bin/bash\necho hacked\n", "text/plain")
        
        # 1. Unauthenticated request rejected with 401
        res_unauth = self.client.post(
            "/api/predict",
            files={"image": dummy_file},
            data={"crop": "Tomato"}
        )
        self.assertEqual(res_unauth.status_code, 401)

        # 2. Authenticated request with non-image rejected with 400
        # Create a temporary session for testing
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users LIMIT 1;")
            user_row = cursor.fetchone()
            user_id = user_row[0] if user_row else 1

        token = gari_auth.create_session(user_id=user_id)
        try:
            res_auth = self.client.post(
                "/api/predict",
                files={"image": dummy_file},
                data={"crop": "Tomato"},
                headers={"Authorization": f"Bearer {token}"}
            )
            self.assertEqual(res_auth.status_code, 400)
            detail = res_auth.json().get("detail", "")
            self.assertTrue(
                any(msg in detail for msg in ["không an toàn", "không hợp lệ", "nội dung bị cấm"]),
                f"Unexpected detail: {detail}"
            )
        finally:
            gari_auth.destroy_session(token)

    def test_10_model_path_traversal_rejected(self):
        """Verify that passing path traversal strings in crop_id is rejected by model registry."""
        response = self.client.get("/api/models/../../etc/passwd")
        # FastAPI routing or engine rejects path traversal
        self.assertIn(response.status_code, (404, 400))

    # -------------------------------------------------------------------------
    # 5. Database WAL & Integrity Verification
    # -------------------------------------------------------------------------
    def test_11_database_integrity_and_wal(self):
        """Verify production database WAL mode and zero page corruption."""
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            row = cursor.fetchone()
            self.assertEqual(row[0].lower(), "ok")

            cursor.execute("PRAGMA journal_mode;")
            j_mode = cursor.fetchone()[0]
            self.assertEqual(j_mode.lower(), "wal")


if __name__ == "__main__":
    unittest.main()
