"""
GARI AI LAB — API Integration Tests for Vouchers & Entitlements (test_voucher_api.py)

Tests HTTP endpoints:
- POST /api/vouchers/redeem (401 unauthenticated, 400 invalid, 200 success)
- POST /api/admin/vouchers (403 non-admin, 200 admin)
- GET /api/admin/vouchers (403 non-admin, 200 admin)
- POST /api/admin/vouchers/{id}/revoke (403 non-admin, 200 admin)
- GET /api/billing/subscription (entitlement source, honest gateway)
- POST /api/billing/checkout (honest 400, no demo fake checkout)
"""

import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
import gari_auth
import gari_vouchers
from api_server import app


class TestVoucherAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

        # Create test users and tokens
        with gari_vouchers.get_db_connection() as conn:
            cursor = conn.cursor()
            # 1. Platform Admin
            cursor.execute("SELECT id FROM users WHERE email = 'api_admin_test@gari.vn'")
            row = cursor.fetchone()
            if not row:
                cursor.execute("""
                    INSERT INTO users (email, name, full_name, password_hash, account_type, is_admin)
                    VALUES ('api_admin_test@gari.vn', 'Admin API', 'Admin API', 'hash', 'Platform Admin', 1)
                """)
                cls.admin_id = cursor.lastrowid
            else:
                cls.admin_id = row["id"]

            # 2. Regular User
            cursor.execute("SELECT id FROM users WHERE email = 'api_user_test@gari.vn'")
            row2 = cursor.fetchone()
            if not row2:
                cursor.execute("""
                    INSERT INTO users (email, name, full_name, password_hash, account_type, is_admin)
                    VALUES ('api_user_test@gari.vn', 'Regular User', 'Regular User', 'hash', 'Nông hộ', 0)
                """)
                cls.user_id = cursor.lastrowid
            else:
                cls.user_id = row2["id"]
            conn.commit()

        # Generate auth sessions
        cls.admin_token = gari_auth.create_session(cls.admin_id)
        cls.user_token = gari_auth.create_session(cls.user_id)

    def test_01_unauthenticated_redeem_rejected(self):
        """Unauthenticated caller cannot redeem vouchers (401)."""
        res = self.client.post("/api/vouchers/redeem", json={"code": "GARI-PERS-FAKE-CODE"})
        self.assertEqual(res.status_code, 401)

    def test_02_non_admin_cannot_access_admin_vouchers(self):
        """Normal authenticated user is rejected from admin voucher routes (403)."""
        headers = {"Authorization": f"Bearer {self.user_token}"}
        
        # Create
        res = self.client.post("/api/admin/vouchers", headers=headers, json={"plan_id": "personal"})
        self.assertEqual(res.status_code, 403)

        # List
        res = self.client.get("/api/admin/vouchers", headers=headers)
        self.assertEqual(res.status_code, 403)

        # Revoke
        res = self.client.post("/api/admin/vouchers/1/revoke", headers=headers, json={"reason": "test"})
        self.assertEqual(res.status_code, 403)

        # Audit
        res = self.client.get("/api/admin/vouchers/audit", headers=headers)
        self.assertEqual(res.status_code, 403)

    def test_03_admin_create_voucher_and_user_redeem(self):
        """Admin creates voucher; user redeems it; subscription is activated."""
        admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        user_headers = {"Authorization": f"Bearer {self.user_token}"}

        # 1. Admin creates voucher
        create_res = self.client.post(
            "/api/admin/vouchers",
            headers=admin_headers,
            json={
                "plan_id": "personal",
                "duration_days": 60,
                "max_redemptions": 1,
                "notes": "API Integration Test"
            }
        )
        self.assertEqual(create_res.status_code, 200)
        data = create_res.json()
        self.assertTrue(data["success"])
        voucher_code = data["voucher_code"]
        voucher_id = data["voucher"]["id"]
        self.assertTrue(voucher_code.startswith("GARI-PERS-"))

        # 2. User redeems voucher
        redeem_res = self.client.post(
            "/api/vouchers/redeem",
            headers=user_headers,
            json={"code": voucher_code}
        )
        self.assertEqual(redeem_res.status_code, 200)
        r_data = redeem_res.json()
        self.assertTrue(r_data["success"])
        self.assertEqual(r_data["redemption"]["plan_id"], "personal")
        self.assertEqual(r_data["redemption"]["duration_days"], 60)

        # 3. Check billing subscription endpoint
        sub_res = self.client.get("/api/billing/subscription", headers=user_headers)
        self.assertEqual(sub_res.status_code, 200)
        sub_data = sub_res.json()
        self.assertTrue(sub_data["success"])
        self.assertEqual(sub_data["entitlement"]["plan_id"], "personal")
        self.assertEqual(sub_data["entitlement"]["access_source"], "voucher")
        self.assertEqual(sub_data["entitlement"]["subscription_status"], "active")
        self.assertEqual(sub_data["payment_gateway"]["status"], "payment_provider_not_configured")

    def test_04_admin_list_and_revoke_voucher(self):
        """Admin lists vouchers (preview only) and revokes an active voucher."""
        admin_headers = {"Authorization": f"Bearer {self.admin_token}"}

        # Create voucher
        c_res = self.client.post(
            "/api/admin/vouchers",
            headers=admin_headers,
            json={"plan_id": "business", "duration_days": 30}
        )
        v_id = c_res.json()["voucher"]["id"]

        # List vouchers
        l_res = self.client.get("/api/admin/vouchers", headers=admin_headers)
        self.assertEqual(l_res.status_code, 200)
        vouchers = l_res.json()["vouchers"]
        found = [v for v in vouchers if v["id"] == v_id]
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0]["code_preview"].startswith("GARI-BIZ-****-"))
        self.assertEqual(found[0]["status"], "active")

        # Revoke voucher
        r_res = self.client.post(
            f"/api/admin/vouchers/{v_id}/revoke",
            headers=admin_headers,
            json={"reason": "Revoked for test"}
        )
        self.assertEqual(r_res.status_code, 200)
        self.assertEqual(r_res.json()["voucher"]["status"], "revoked")

    def test_05_no_demo_mode_honest_checkout(self):
        """Payment checkout returns honest 400 when gateway is not configured (no fake checkout)."""
        user_headers = {"Authorization": f"Bearer {self.user_token}"}
        res = self.client.post("/api/billing/checkout", headers=user_headers, json={"plan_id": "personal"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("payment_provider_not_configured", res.json()["detail"])


if __name__ == "__main__":
    unittest.main()
