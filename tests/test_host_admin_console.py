"""
GARI AI LAB — Host Server Admin Console Test Suite (tests/test_host_admin_console.py)
Tests:
1. Host Identity & Access Control (Strict Server-Side Verification)
2. Bootstrap Security & Duplicate Initial Host Prevention
3. Account Type Independence (Roles do not grant host privileges)
4. User Management (Suspend, Reactivate, Invalidate Sessions, Account Type change, VIP toggle)
5. Sensitive Data Redaction (No password hashes or tokens returned)
6. Voucher Issuance & Revocation
7. API & System Configuration Toggles
8. Immutable Audit Trail in host_audit_logs
"""

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
from starlette.testclient import TestClient


class TestHostAdminConsole(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gari_database.init_database()
        cls.client = TestClient(api_server.app)

        # Create isolated test entities
        cls.suffix = uuid.uuid4().hex[:8]
        cls.farmer_email = f"farmer_{cls.suffix}@gari.vn"
        cls.target_email = f"target_{cls.suffix}@gari.vn"
        cls.host_email = f"host_{cls.suffix}@gari.vn"
        cls.password = "StrongPass123!"

        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            # Normal farmer user (is_host_admin = 0)
            pwd_hash = gari_auth.hash_password(cls.password)
            cursor.execute(
                """
                INSERT INTO users (full_name, name, email, password_hash, account_type, is_host_admin, is_active)
                VALUES ('Farmer Test', 'Farmer Test', ?, ?, 'farmer', 0, 1)
                """,
                (cls.farmer_email, pwd_hash)
            )
            cls.farmer_id = cursor.lastrowid

            # Target user for testing admin actions
            cursor.execute(
                """
                INSERT INTO users (full_name, name, email, password_hash, account_type, is_host_admin, is_active)
                VALUES ('Target Test', 'Target Test', ?, ?, 'farmer', 0, 1)
                """,
                (cls.target_email, pwd_hash)
            )
            cls.target_id = cursor.lastrowid

            # Verified Host Administrator (is_host_admin = 1)
            cursor.execute(
                """
                INSERT INTO users (full_name, name, email, password_hash, account_type, is_host_admin, is_active)
                VALUES ('Gari Host Master', 'Gari Host Master', ?, ?, 'enterprise', 1, 1)
                """,
                (cls.host_email, pwd_hash)
            )
            cls.host_id = cursor.lastrowid
            conn.commit()

        # Generate sessions
        cls.farmer_token = gari_auth.create_session(cls.farmer_id)
        cls.farmer_headers = {"Authorization": f"Bearer {cls.farmer_token}"}

        cls.host_token = gari_auth.create_session(cls.host_id)
        cls.host_headers = {"Authorization": f"Bearer {cls.host_token}"}

    @classmethod
    def tearDownClass(cls):
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = OFF")
            cursor.execute("DELETE FROM user_sessions WHERE user_id IN (?, ?, ?)", (cls.farmer_id, cls.target_id, cls.host_id))
            cursor.execute("DELETE FROM user_subscriptions WHERE user_id IN (?, ?, ?)", (cls.farmer_id, cls.target_id, cls.host_id))
            cursor.execute("DELETE FROM user_account_type_audit WHERE user_id IN (?, ?, ?)", (cls.farmer_id, cls.target_id, cls.host_id))
            cursor.execute("DELETE FROM users WHERE email IN (?, ?, ?)", (cls.farmer_email, cls.target_email, cls.host_email))
            cursor.execute("DELETE FROM host_audit_logs WHERE host_email = ?", (cls.host_email,))
            cursor.execute("PRAGMA foreign_keys = ON")
            conn.commit()

    # -------------------------------------------------------------------------
    # 1. Access Control Tests
    # -------------------------------------------------------------------------
    def test_01_unauthenticated_requests_rejected(self):
        """Unauthenticated requests to host endpoints must return HTTP 401."""
        endpoints = [
            "/api/host/me",
            "/api/host/overview",
            "/api/host/users",
            "/api/host/vouchers",
            "/api/host/api-controls",
            "/api/host/audit-logs",
            "/api/host/models"
        ]
        for ep in endpoints:
            res = self.client.get(ep)
            self.assertEqual(res.status_code, 401, f"Endpoint {ep} should require auth (401)")

    def test_02_normal_user_forbidden_from_host_endpoints(self):
        """Authenticated normal users (farmer, expert, etc.) must receive HTTP 403 Forbidden."""
        endpoints = [
            "/api/host/me",
            "/api/host/overview",
            "/api/host/users",
            "/api/host/vouchers",
            "/api/host/api-controls",
            "/api/host/audit-logs",
            "/api/host/models"
        ]
        for ep in endpoints:
            res = self.client.get(ep, headers=self.farmer_headers)
            self.assertEqual(res.status_code, 403, f"Endpoint {ep} must return 403 for normal user")

    def test_03_normal_user_cannot_login_through_host_portal(self):
        """Normal users cannot use /api/auth/host-login and receive HTTP 403 Forbidden."""
        payload = {
            "email": self.farmer_email,
            "password": self.password,
            "remember_me": False
        }
        res = self.client.post("/api/auth/host-login", json=payload)
        self.assertEqual(res.status_code, 403)
        self.assertIn("không có đặc quyền Quản trị Máy chủ", res.json()["detail"])

    def test_04_host_admin_login_success(self):
        """Valid host admin credentials succeed and return token and profile."""
        payload = {
            "email": self.host_email,
            "password": self.password,
            "remember_me": True
        }
        res = self.client.post("/api/auth/host-login", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["user"]["is_host_admin"])
        self.assertIn("token", data)

    # -------------------------------------------------------------------------
    # 2. Host Telemetry & Privacy Redaction
    # -------------------------------------------------------------------------
    def test_05_host_me_returns_sanitized_profile(self):
        """Host profile endpoint returns identity without password hashes or tokens."""
        res = self.client.get("/api/host/me", headers=self.host_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        user = data["user"]
        self.assertEqual(user["email"], self.host_email)
        self.assertTrue(user["is_host_admin"])
        self.assertNotIn("password_hash", user)
        self.assertNotIn("token", user)

    def test_06_host_overview_returns_real_telemetry(self):
        """Overview endpoint returns real hardware and system metrics without fabrication."""
        res = self.client.get("/api/host/overview", headers=self.host_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        telemetry = data["telemetry"]
        self.assertIn("cpu_percent", telemetry)
        self.assertIn("ram", telemetry)
        self.assertIn("disk", telemetry)
        self.assertGreater(telemetry["ram"]["total_gb"], 0)
        self.assertGreater(telemetry["disk"]["total_gb"], 0)
        self.assertGreaterEqual(telemetry["uptime_seconds"], 0)

        ai = data["ai_models_summary"]
        self.assertGreaterEqual(ai["total_crop_models"], 0)

    def test_07_host_user_search_redacts_secrets(self):
        """User list endpoint supports search and redacts private hashes and tokens."""
        res = self.client.get(f"/api/host/users?search={self.target_email}", headers=self.host_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertGreaterEqual(data["total"], 1)
        found = data["users"][0]
        self.assertEqual(found["email"], self.target_email)
        self.assertNotIn("password_hash", found)
        self.assertNotIn("token", found)

    # -------------------------------------------------------------------------
    # 3. User Lifecycle & Status Management
    # -------------------------------------------------------------------------
    def test_08_host_can_suspend_and_reactivate_user_with_audit(self):
        """Host suspends user, invalidates active sessions, and audits action."""
        target_token = gari_auth.create_session(self.target_id)
        target_headers = {"Authorization": f"Bearer {target_token}"}
        # Session is valid initially
        self.assertEqual(self.client.get("/api/auth/me", headers=target_headers).status_code, 200)

        # Suspend target user
        res_suspend = self.client.patch(
            f"/api/host/users/{self.target_id}/status",
            json={"is_active": False, "reason": "Tạm khóa do phát hiện hoạt động bất thường."},
            headers=self.host_headers
        )
        self.assertEqual(res_suspend.status_code, 200)
        self.assertFalse(res_suspend.json()["is_active"])

        # Target session is immediately invalidated (401)
        self.assertEqual(self.client.get("/api/auth/me", headers=target_headers).status_code, 401)

        # Target cannot log in while suspended (403)
        res_login = self.client.post("/api/auth/login", json={"email": self.target_email, "password": self.password})
        self.assertEqual(res_login.status_code, 403)

        # Reactivate target user
        res_reactivate = self.client.patch(
            f"/api/host/users/{self.target_id}/status",
            json={"is_active": True, "reason": "Kích hoạt lại sau khi hoàn tất xác minh chủ tài khoản."},
            headers=self.host_headers
        )
        self.assertEqual(res_reactivate.status_code, 200)
        self.assertTrue(res_reactivate.json()["is_active"])

    def test_09_host_cannot_suspend_themselves(self):
        """Host admin is prevented from suspending their own account."""
        res = self.client.patch(
            f"/api/host/users/{self.host_id}/status",
            json={"is_active": False, "reason": "Tự khóa bản thân"},
            headers=self.host_headers
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Không thể tự đình chỉ", res.json()["detail"])

    def test_10_host_can_update_account_type(self):
        """Host admin updates user's single active account type with audit logging."""
        res = self.client.patch(
            f"/api/host/users/{self.target_id}/account-type",
            json={"account_type": "cooperative", "reason": "Chuyển đổi sang tài khoản Hợp tác xã."},
            headers=self.host_headers
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["account_type"], "cooperative")

    def test_11_host_can_grant_and_revoke_vip(self):
        """Host admin grants VIP and revokes VIP with audit trail."""
        res_grant = self.client.post(
            f"/api/host/users/{self.target_id}/vip",
            json={"action": "grant", "plan_id": "vip_pro", "duration_days": 30, "reason": "Tặng gói dùng thử VIP."},
            headers=self.host_headers
        )
        self.assertEqual(res_grant.status_code, 200)
        self.assertEqual(res_grant.json()["action"], "grant")

        res_revoke = self.client.post(
            f"/api/host/users/{self.target_id}/vip",
            json={"action": "revoke", "reason": "Hết thời gian dùng thử VIP."},
            headers=self.host_headers
        )
        self.assertEqual(res_revoke.status_code, 200)
        self.assertEqual(res_revoke.json()["action"], "revoke")

    # -------------------------------------------------------------------------
    # 4. Voucher & API Control Management
    # -------------------------------------------------------------------------
    def test_12_host_voucher_lifecycle(self):
        """Host creates voucher and revokes voucher with audit logging."""
        create_res = self.client.post(
            "/api/host/vouchers",
            json={"plan_id": "vip_pro", "max_redemptions": 5, "valid_days": 30, "note": "Voucher kiểm thử"},
            headers=self.host_headers
        )
        self.assertEqual(create_res.status_code, 200)
        v_data = create_res.json()["voucher"]
        voucher_id = v_data["voucher_id"]
        self.assertIn("raw_code", v_data)

        # List vouchers
        list_res = self.client.get("/api/host/vouchers", headers=self.host_headers)
        self.assertEqual(list_res.status_code, 200)
        self.assertTrue(any(v["id"] == voucher_id for v in list_res.json()["vouchers"]))

        # Revoke voucher
        revoke_res = self.client.post(
            f"/api/host/vouchers/{voucher_id}/revoke",
            json={"reason": "Thu hồi voucher kiểm thử."},
            headers=self.host_headers
        )
        self.assertEqual(revoke_res.status_code, 200)

    def test_13_host_api_controls_and_audit_trail(self):
        """Host updates API configuration setting and verifies audit logs."""
        update_res = self.client.patch(
            "/api/host/api-controls",
            json={"key": "rate_limit_per_minute", "value": "150", "reason": "Cập nhật rate limit cho kiểm thử."},
            headers=self.host_headers
        )
        self.assertEqual(update_res.status_code, 200)
        self.assertEqual(update_res.json()["value"], "150")

        # Verify audit logs
        audit_res = self.client.get("/api/host/audit-logs", headers=self.host_headers)
        self.assertEqual(audit_res.status_code, 200)
        logs = audit_res.json()["logs"]
        action_types = [l["action_type"] for l in logs]
        self.assertIn("update_api_config", action_types)
        self.assertIn("suspend_user", action_types)
        self.assertIn("reactivate_user", action_types)

    # -------------------------------------------------------------------------
    # 5. CLI Bootstrap & Recovery Verification
    # -------------------------------------------------------------------------
    def test_14_bootstrap_lock_prevents_duplicate_initial_creation(self):
        """CLI tool rejects creating duplicate host without --force-recovery."""
        import tools.create_host_admin as bootstrap_tool
        with self.assertRaises(PermissionError) as ctx:
            bootstrap_tool.bootstrap_host_admin(
                email=f"dup_{self.suffix}@gari.vn",
                password="NewPassword123!",
                confirm_password="NewPassword123!",
                force_recovery=False
            )
        self.assertIn("One-time initial bootstrap is locked", str(ctx.exception))

    def test_15_bootstrap_with_force_recovery_succeeds(self):
        """CLI tool allows credential reset or new host when --force-recovery is authorized."""
        import tools.create_host_admin as bootstrap_tool
        recovery_email = f"recovered_{self.suffix}@gari.vn"
        user_id = bootstrap_tool.bootstrap_host_admin(
            email=recovery_email,
            password="RecoveredPass123!",
            confirm_password="RecoveredPass123!",
            full_name="Recovered Host",
            force_recovery=True
        )
        self.assertGreater(user_id, 0)

        # Verify Bcrypt hash format
        with gari_database.get_connection() as conn:
            row = conn.execute("SELECT password_hash, is_host_admin FROM users WHERE id = ?", (user_id,)).fetchone()
            self.assertTrue(row["password_hash"].startswith("$2b$"))
            self.assertEqual(row["is_host_admin"], 1)

            # Cleanup recovered user
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()


if __name__ == "__main__":
    unittest.main()
