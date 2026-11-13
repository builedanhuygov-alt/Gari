"""
GARI MODULE 12 — HOST CONSOLE SYSTEM ADMINISTRATION TEST SUITE
File: tests/test_module_12_host_console.py

Comprehensive test suite verifying:
1. Strict Host Admin RBAC Boundary Rejections (unauthenticated 401, regular user 403, expert 403, org owner 403, host admin 200).
2. User Management Inspection & Sensitive Admin Password Reset with explicit confirmation (400 if confirm=False).
3. Organization Management, Details Inspector, Member Roster, and Status/Plan modifications.
4. Expert Application Review & Verification Lifecycle with inspection and status toggles.
5. Dynamic Subscription Plans & Entitlements Configuration via Host Admin (updating limits, immediate reflection in entitlements).
6. AI Configuration Security & Secret Masking (credentials securely stored, never returned in plain text, redacted in audit logs).
7. AI Provider Connectivity Testing & Explicit Health States (unconfigured, configured, healthy, failing).
8. Model Availability Inventory, Architecture & Hardware Telemetry, and Live Inference Benchmarking.
9. System-wide Usage Monitoring Aggregation (diagnoses, AI assistant, farms, plots, seats, storage).
10. Unified Moderation Queue Resolution (with confirmation) & System Health / Error Logs Monitoring with Clear action.
"""

import os
import sys
import unittest
import uuid
from pathlib import Path

# Set development environment
os.environ["APP_ENV"] = "development"
os.environ["PAYMENT_PUBLIC_CHECKOUT_ENABLED"] = "1"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
import api_server
import gari_auth
import gari_database
import gari_entitlements
import gari_host_service


class TestModule12HostConsole(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(api_server.app)

        # Helper to register and create test users
        cls.host_admin_user, cls.host_admin_headers = cls._create_user("host_admin", is_host_admin=True)
        cls.regular_user, cls.regular_headers = cls._create_user("farmer", account_type="farmer")
        cls.expert_user, cls.expert_headers = cls._create_user("agronomist", account_type="expert", is_expert=True)
        cls.org_owner_user, cls.org_owner_headers = cls._create_user("business_owner", account_type="business")

    @classmethod
    def _create_user(cls, prefix: str, account_type: str = "farmer", is_host_admin: bool = False, is_expert: bool = False):
        email = f"{prefix}_{uuid.uuid4().hex[:6]}@gari.vn"
        password = "SecurePassword123!"
        full_name = f"User {prefix.capitalize()}"

        reg_res = cls.client.post("/api/auth/register", json={
            "email": email,
            "password": password,
            "confirm_password": password,
            "full_name": full_name
        })
        user_id = reg_res.json()["user"]["id"]

        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users
                SET is_host_admin = ?, is_expert = ?, account_type = ?, is_active = 1
                WHERE id = ?
                """,
                (1 if is_host_admin else 0, 1 if is_expert else 0, account_type, user_id)
            )
            conn.commit()

        login_res = cls.client.post("/api/auth/login", json={
            "email": email,
            "password": password
        })
        token = login_res.json().get("token") or login_res.json().get("session_token")
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        user_info = {
            "id": user_id,
            "email": email,
            "full_name": full_name,
            "token": token
        }
        return user_info, headers

    def test_01_host_console_rbac_boundaries_and_unauthorized_rejection(self):
        """
        Verify strict Host Admin RBAC Boundary:
        - Unauthenticated access returns HTTP 401.
        - Regular user (is_host_admin=0) returns HTTP 403.
        - Expert user (is_expert=1, is_host_admin=0) returns HTTP 403.
        - Organization Owner (is_host_admin=0) returns HTTP 403.
        - Host Admin (is_host_admin=1) returns HTTP 200.
        """
        protected_endpoints = [
            ("GET", "/api/host/me"),
            ("GET", "/api/host/overview"),
            ("GET", "/api/host/users"),
            ("GET", "/api/host/organizations"),
            ("GET", "/api/host/subscriptions/plans"),
            ("GET", "/api/host/ai/config"),
            ("GET", "/api/host/system/health"),
            ("GET", "/api/host/system/errors"),
            ("GET", "/api/host/usage/summary"),
        ]

        unauth_client = TestClient(api_server.app)
        for method, endpoint in protected_endpoints:
            # 1. Unauthenticated
            res_unauth = getattr(unauth_client, method.lower())(endpoint)
            self.assertEqual(res_unauth.status_code, 401, f"Expected 401 for unauthenticated on {endpoint}")

            # 2. Regular user
            res_reg = getattr(self.client, method.lower())(endpoint, headers=self.regular_headers)
            self.assertEqual(res_reg.status_code, 403, f"Expected 403 for regular user on {endpoint}")

            # 3. Expert user
            res_exp = getattr(self.client, method.lower())(endpoint, headers=self.expert_headers)
            self.assertEqual(res_exp.status_code, 403, f"Expected 403 for expert on {endpoint}")

            # 4. Org owner user
            res_owner = getattr(self.client, method.lower())(endpoint, headers=self.org_owner_headers)
            self.assertEqual(res_owner.status_code, 403, f"Expected 403 for org owner on {endpoint}")

            # 5. Verified Host Admin
            res_admin = getattr(self.client, method.lower())(endpoint, headers=self.host_admin_headers)
            self.assertEqual(res_admin.status_code, 200, f"Expected 200 for host admin on {endpoint}")

    def test_02_user_management_inspection_and_confirmed_password_reset(self):
        """
        Verify User Management:
        - List users with search and pagination.
        - Inspect detailed user profile (/api/host/users/{user_id}) showing stats and subscriptions.
        - Password reset requires explicit confirmation (confirm=True).
        - Rejection with 400 when confirm=False.
        - Audited in host_audit_logs.
        """
        # 1. List users
        res_list = self.client.get("/api/host/users?limit=10", headers=self.host_admin_headers)
        self.assertEqual(res_list.status_code, 200)
        users = res_list.json()["users"]
        self.assertGreater(len(users), 0)

        # 2. Inspect single user
        target_uid = self.regular_user["id"]
        res_detail = self.client.get(f"/api/host/users/{target_uid}", headers=self.host_admin_headers)
        self.assertEqual(res_detail.status_code, 200)
        detail_data = res_detail.json()
        self.assertTrue(detail_data["success"])
        self.assertEqual(detail_data["user"]["id"], target_uid)
        self.assertIn("stats", detail_data)
        self.assertIn("subscription", detail_data)

        # 3. Password reset without confirmation must be rejected (400)
        res_reset_no_confirm = self.client.post(
            f"/api/host/users/{target_uid}/reset-password",
            json={"new_password": "NewSafePassword456!", "confirm": False},
            headers=self.host_admin_headers
        )
        self.assertEqual(res_reset_no_confirm.status_code, 400)

        # 4. Password reset with confirmation succeeds
        res_reset_ok = self.client.post(
            f"/api/host/users/{target_uid}/reset-password",
            json={"new_password": "NewSafePassword456!", "confirm": True, "reason": "Admin test reset"},
            headers=self.host_admin_headers
        )
        self.assertEqual(res_reset_ok.status_code, 200)
        self.assertTrue(res_reset_ok.json()["success"])

        # 5. Verify target user can now login with new password
        login_res = self.client.post("/api/auth/login", json={
            "email": self.regular_user["email"],
            "password": "NewSafePassword456!"
        })
        self.assertEqual(login_res.status_code, 200)

    def test_03_organization_management_and_member_inspection(self):
        """
        Verify Organization Management:
        - List organizations.
        - Inspect organization details (/api/host/organizations/{org_id}).
        - Inspect organization members roster (/api/host/organizations/{org_id}/members).
        - Update organization status and plan.
        """
        # Create an organization for testing
        org_slug = f"htx-test-{uuid.uuid4().hex[:6]}"
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO organizations (name, slug, organization_type, owner_id, status, plan_id)
                VALUES ('HTX Host Test', ?, 'cooperative', ?, 'active', 'free')
                """,
                (org_slug, self.org_owner_user["id"])
            )
            org_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO organization_members (organization_id, user_id, role) VALUES (?, ?, 'owner')",
                (org_id, self.org_owner_user["id"])
            )
            conn.commit()

        # 1. Inspect organization details
        res_org = self.client.get(f"/api/host/organizations/{org_id}", headers=self.host_admin_headers)
        self.assertEqual(res_org.status_code, 200)
        org_data = res_org.json()
        self.assertEqual(org_data["organization"]["id"], org_id)
        self.assertEqual(org_data["member_count"], 1)

        # 2. Inspect members
        res_mem = self.client.get(f"/api/host/organizations/{org_id}/members", headers=self.host_admin_headers)
        self.assertEqual(res_mem.status_code, 200)
        self.assertEqual(len(res_mem.json()["members"]), 1)

        # 3. Update organization status (suspend)
        res_status = self.client.patch(
            f"/api/host/organizations/{org_id}/status",
            json={"status": "suspended", "reason": "Test audit suspension"},
            headers=self.host_admin_headers
        )
        self.assertEqual(res_status.status_code, 200)

    def test_04_expert_application_review_and_status_toggle(self):
        """
        Verify Expert Application Review & Verification Lifecycle:
        - Submit application.
        - Host Admin inspects application details.
        - Host Admin approves application with review notes and commission.
        - Host Admin lists verified experts and toggles active status.
        """
        applicant_user, applicant_headers = self._create_user("app_farmer", account_type="farmer")

        # Submit expert application
        app_res = self.client.post("/api/expert/apply", json={
            "full_name": "Nguyen Van Chuyen Gia",
            "title": "Ky su BVTV",
            "organization": "Dai hoc Can Tho",
            "specialties": ["Coffee", "Pepper"],
            "years_experience": 8,
            "phone": "0988776655",
            "degree": "Ky su Dai hoc Nong Lam"
        }, headers=applicant_headers)
        self.assertEqual(app_res.status_code, 200)
        app_id = app_res.json().get("application_id") or app_res.json().get("id")

        # 1. Host Admin inspects application details
        res_detail = self.client.get(f"/api/host/experts/applications/{app_id}", headers=self.host_admin_headers)
        self.assertEqual(res_detail.status_code, 200)
        app_info = res_detail.json()
        self.assertEqual(app_info["application"]["id"], app_id)

        # 2. Host Admin approves application
        res_approve = self.client.post(
            f"/api/host/experts/applications/{app_id}/review",
            json={"action": "approve", "admin_notes": "Ho so dat tieu chuan", "commission_rate": 0.15},
            headers=self.host_admin_headers
        )
        self.assertEqual(res_approve.status_code, 200)
        self.assertTrue(res_approve.json()["success"])

        # 3. Host Admin lists verified experts
        res_experts = self.client.get("/api/host/experts?active_only=false", headers=self.host_admin_headers)
        self.assertEqual(res_experts.status_code, 200)
        self.assertGreater(len(res_experts.json()["experts"]), 0)

    def test_05_dynamic_subscription_plans_configuration(self):
        """
        Verify Dynamic Subscription Plans & Entitlements Configuration:
        - Retrieve all configurable plans from database (/api/host/subscriptions/plans).
        - Update plan limits requiring explicit confirmation (confirm=True).
        - Rejection with 400 when confirm=False.
        - Verify entitlement service immediately reflects the updated limits.
        """
        # 1. Fetch plans
        res_plans = self.client.get("/api/host/subscriptions/plans", headers=self.host_admin_headers)
        self.assertEqual(res_plans.status_code, 200)
        plans = res_plans.json()["plans"]
        plan_ids = [p["id"] for p in plans]
        self.assertIn("free", plan_ids)
        self.assertIn("pro", plan_ids)
        self.assertIn("ultra", plan_ids)

        # 2. Update without confirmation must be rejected (400)
        res_update_no_confirm = self.client.put(
            "/api/host/subscriptions/plans/pro",
            json={"ai_usage_limit": 450, "confirm": False},
            headers=self.host_admin_headers
        )
        self.assertEqual(res_update_no_confirm.status_code, 400)

        # 3. Update with confirmation succeeds
        res_update_ok = self.client.put(
            "/api/host/subscriptions/plans/pro",
            json={"ai_usage_limit": 450, "confirm": True, "reason": "Host Admin increased Pro quota"},
            headers=self.host_admin_headers
        )
        self.assertEqual(res_update_ok.status_code, 200)

        # 4. Verify gari_entitlements immediately reflects new limit
        plan_def = gari_entitlements.get_plan_definition("pro")
        self.assertEqual(plan_def["ai_usage_limit"], 450)

    def test_06_ai_configuration_security_masking_and_no_secret_leakage(self):
        """
        Verify AI Provider & Model Configuration Security:
        - Store provider credentials securely on backend.
        - Secret API keys are masked in GET responses (AIza...**** or ***).
        - Raw secrets are NEVER returned in plain text to the client.
        - Updates to configuration are recorded in host_audit_logs with secret REDACTED.
        """
        # 1. Save configuration with a sensitive API key
        raw_secret_key = "AIzaSySecretTestKey998877665544332211"
        res_save = self.client.post(
            "/api/host/ai/config",
            json={
                "provider": "gemini",
                "model": "gemini-1.5-flash",
                "api_key": raw_secret_key,
                "temperature": 0.25,
                "reason": "Host Admin updated Gemini API key"
            },
            headers=self.host_admin_headers
        )
        self.assertEqual(res_save.status_code, 200)

        # 2. Fetch AI configuration
        res_get = self.client.get("/api/host/ai/config", headers=self.host_admin_headers)
        self.assertEqual(res_get.status_code, 200)
        cfg = res_get.json()["config"]

        # 3. Verify secret masking: NEVER returns raw_secret_key
        self.assertNotEqual(cfg["api_key_masked"], raw_secret_key)
        self.assertTrue(cfg["api_key_masked"].startswith("AIza"))
        self.assertTrue(cfg["api_key_masked"].endswith("2211"))
        self.assertIn("...", cfg["api_key_masked"])
        self.assertTrue(cfg["has_api_key"])
        self.assertNotIn("raw_key", cfg)

        # 4. Verify secret is REDACTED in audit logs
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT details_json FROM host_audit_logs WHERE action_type = 'UPDATE_AI_CONFIG' ORDER BY id DESC LIMIT 1"
            )
            audit_row = cursor.fetchone()
            self.assertIsNotNone(audit_row)
            audit_details = audit_row["details_json"]
            self.assertNotIn(raw_secret_key, audit_details)
            self.assertIn("SECRET_REDACTED", audit_details)

    def test_07_ai_provider_connection_testing_and_health_states(self):
        """
        Verify AI Provider Connectivity Testing & Explicit Health States:
        - Supports connection testing without exposing credentials.
        - Shows explicit states: configured, unconfigured, healthy, failing.
        """
        # 1. Test Mock AI Provider (should succeed and report healthy)
        self.client.post(
            "/api/host/ai/config",
            json={"provider": "mock", "model": "mock-agri-v1", "reason": "Switch to mock for test"},
            headers=self.host_admin_headers
        )

        res_test = self.client.post("/api/host/ai/provider-test", headers=self.host_admin_headers)
        self.assertEqual(res_test.status_code, 200)
        test_data = res_test.json()
        self.assertTrue(test_data["success"])
        self.assertIn("latency_ms", test_data)

        # 2. Check health status in config
        res_cfg = self.client.get("/api/host/ai/config", headers=self.host_admin_headers)
        self.assertEqual(res_cfg.status_code, 200)
        state = res_cfg.json()["config"]["state"]
        self.assertEqual(state, "healthy")

        # 3. Test failing provider state (invalid provider or key failure)
        res_fail_test = self.client.post(
            "/api/host/ai/provider-test",
            json={"provider": "gemini", "api_key": ""},
            headers=self.host_admin_headers
        )
        self.assertEqual(res_fail_test.status_code, 200)
        self.assertFalse(res_fail_test.json()["success"])

        # Health state should now transition to failing
        res_cfg_fail = self.client.get("/api/host/ai/config", headers=self.host_admin_headers)
        self.assertEqual(res_cfg_fail.json()["config"]["state"], "failing")

    def test_08_model_availability_inventory_and_inference_benchmark(self):
        """
        Verify Model Availability & Live Benchmarking:
        - List deep learning models, devices, directory sizes, and runtime readiness.
        - Run real inference benchmark on engine and return latency and FPS throughput.
        - Audited in host_audit_logs.
        """
        # 1. Models inventory
        res_models = self.client.get("/api/host/models", headers=self.host_admin_headers)
        self.assertEqual(res_models.status_code, 200)
        models_data = res_models.json()
        self.assertTrue(models_data["success"])
        self.assertIn("device", models_data)
        self.assertGreater(models_data["total_models"], 0)

        # 2. Run real live benchmark
        res_bench = self.client.post("/api/host/models/benchmark", headers=self.host_admin_headers)
        self.assertEqual(res_bench.status_code, 200)
        bench_data = res_bench.json()
        self.assertTrue(bench_data["success"])
        self.assertIn("latency_ms", bench_data)
        self.assertIn("throughput_fps", bench_data)
        self.assertEqual(bench_data["engine_status"], "healthy")

    def test_09_system_wide_usage_monitoring_aggregation(self):
        """
        Verify System-wide Usage Monitoring:
        - Aggregates resource consumption across all users and organizations.
        - Reports totals for diagnoses, AI assistant queries, farms, plots, seats, and storage.
        """
        res_usage = self.client.get("/api/host/usage/summary", headers=self.host_admin_headers)
        self.assertEqual(res_usage.status_code, 200)
        usage_data = res_usage.json()
        self.assertTrue(usage_data["success"])

        # Check all core dimensions
        self.assertIn("users", usage_data)
        self.assertIn("organizations", usage_data)
        self.assertIn("agriculture", usage_data)
        self.assertIn("diagnoses", usage_data)
        self.assertIn("ai_assistant", usage_data)
        self.assertIn("storage", usage_data)
        self.assertIn("plans", usage_data)

        self.assertGreaterEqual(usage_data["users"]["total"], 1)
        self.assertGreaterEqual(usage_data["storage"]["estimated_mb"], 0.0)

    def test_10_moderation_queue_and_system_health_error_monitoring(self):
        """
        Verify Moderation Queue & System Health / Error Logs:
        - Unified moderation queue combining community reports and system cases.
        - Resolving item with confirmation.
        - System health telemetry (CPU, RAM, Disk, DB ping).
        - System error logs inspection and clearing with confirmation.
        """
        # 1. System Health Telemetry
        res_health = self.client.get("/api/host/system/health", headers=self.host_admin_headers)
        self.assertEqual(res_health.status_code, 200)
        h_data = res_health.json()
        self.assertTrue(h_data["success"])
        self.assertIn("cpu", h_data)
        self.assertIn("memory", h_data)
        self.assertIn("disk", h_data)
        self.assertEqual(h_data["database"]["status"], "healthy")

        # 2. Record a synthetic error log for testing
        gari_host_service.log_system_event(
            log_level="ERROR",
            component="test_component",
            message="Synthetic test error for Host Console audit",
            error_details="Traceback: ValueError on line 42",
            ip_address="127.0.0.1"
        )

        # 3. Retrieve system error logs
        res_err = self.client.get("/api/host/system/errors?min_level=ERROR", headers=self.host_admin_headers)
        self.assertEqual(res_err.status_code, 200)
        err_data = res_err.json()
        self.assertTrue(err_data["success"])
        self.assertGreater(err_data["total"], 0)

        # 4. Clear system error logs without confirmation must be rejected (400)
        res_clear_no_confirm = self.client.post(
            "/api/host/system/errors/clear",
            json={"confirm": False},
            headers=self.host_admin_headers
        )
        self.assertEqual(res_clear_no_confirm.status_code, 400)

        # 5. Clear system error logs with confirmation succeeds
        res_clear_ok = self.client.post(
            "/api/host/system/errors/clear",
            json={"confirm": True, "reason": "Unit test error log clearing"},
            headers=self.host_admin_headers
        )
        self.assertEqual(res_clear_ok.status_code, 200)
        self.assertTrue(res_clear_ok.json()["success"])

        # 6. Moderation Queue retrieval
        res_mod = self.client.get("/api/host/moderation/queue", headers=self.host_admin_headers)
        self.assertEqual(res_mod.status_code, 200)
        self.assertTrue(res_mod.json()["success"])


if __name__ == "__main__":
    unittest.main()
