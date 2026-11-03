"""
GARI AI LAB — Single Active Account Type & Role Selection Tests (test_account_type_selection.py)

Validates:
1. Exactly one active account type per authenticated UID (no multiple simultaneous roles).
2. Existing users retain their current active type.
3. Users cannot modify their type by submitting arbitrary API requests (no silent changes, no UID spoofing).
4. Account type is persisted, loaded, and audited correctly.
5. Account-type changes strictly preserve payment, subscription, and VIP status.
6. Backend authorization dependencies enforce account-type restrictions.
"""

import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys
import uuid

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import gari_auth
import gari_database
import gari_plans
from fastapi import HTTPException
from starlette.testclient import TestClient
from api_server import app


class TestAccountTypeSelection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gari_database.init_database()
        cls.client = TestClient(app)

    def setUp(self):
        self.test_suffix = uuid.uuid4().hex[:8]

    def _create_test_user(self, account_type="farmer", email_prefix="acc_test"):
        email = f"{email_prefix}_{self.test_suffix}@gari.vn"
        password = "Password123!"
        user = gari_auth.register_user(
            full_name=f"User {self.test_suffix}",
            email=email,
            password=password,
            confirm_password=password,
            account_type=account_type
        )
        token = gari_auth.create_session(user["id"])
        return user, token

    def test_01_one_account_type_per_uid(self):
        """Requirement 2 & 10: Enforce exactly ONE active account type per authenticated UID."""
        user, token = self._create_test_user(account_type="farmer")
        uid = user["id"]

        info = gari_auth.get_user_account_type_info(uid)
        self.assertEqual(info["account_type"], "farmer")
        self.assertTrue(info["is_locked"])
        self.assertIsInstance(info["account_type"], str)

        # Setting initial account type on a user who already has one must be rejected
        with self.assertRaises(HTTPException) as cm:
            gari_auth.set_initial_account_type(uid, "cooperative")
        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("đang kích hoạt", cm.exception.detail)

        # Verify type is still 'farmer' (single active type preserved)
        info_after = gari_auth.get_user_account_type_info(uid)
        self.assertEqual(info_after["account_type"], "farmer")

    def test_02_existing_users_retain_current_type(self):
        """Requirement 10: Existing users retain their current active type."""
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            # Dan Huynh (seed user 1) was mapped from agronomist to 'expert'
            cursor.execute("SELECT id, email, account_type FROM users WHERE id = 1")
            dan = cursor.fetchone()
            if dan:
                self.assertEqual(dan["account_type"], "expert")

            # Check all existing users have valid single account type
            cursor.execute("SELECT account_type FROM users")
            all_types = [r[0] for r in cursor.fetchall() if r[0]]
            for t in all_types:
                self.assertIn(t, gari_auth.VALID_ACCOUNT_TYPES)

    def test_03_users_cannot_modify_type_with_arbitrary_requests(self):
        """Requirement 5, 7 & 10: Reject arbitrary modifications, enforce confirm=True, prevent UID spoofing."""
        victim_user, victim_token = self._create_test_user(account_type="farmer", email_prefix="victim")
        attacker_user, attacker_token = self._create_test_user(account_type="farmer", email_prefix="attacker")

        # 1. Arbitrary initial POST when type already exists is rejected
        res = self.client.post(
            "/api/user/account-type",
            json={"account_type": "enterprise"},
            headers={"Authorization": f"Bearer {victim_token}"}
        )
        self.assertEqual(res.status_code, 400)

        # 2. Change request without confirm: true is rejected (no silent change)
        res_no_confirm = self.client.post(
            "/api/user/account-type/change",
            json={"account_type": "expert", "confirm": False},
            headers={"Authorization": f"Bearer {victim_token}"}
        )
        self.assertEqual(res_no_confirm.status_code, 400)
        self.assertIn("confirm", res_no_confirm.json()["detail"].lower())

        # 3. Invalid account type string is rejected
        res_invalid = self.client.post(
            "/api/user/account-type/change",
            json={"account_type": "super_admin_bypass", "confirm": True},
            headers={"Authorization": f"Bearer {victim_token}"}
        )
        self.assertEqual(res_invalid.status_code, 400)

        # 4. Attacker passes victim's user_id in payload: backend must ignore client-sent UID
        # and strictly apply change to attacker's own session UID
        res_spoof = self.client.post(
            "/api/user/account-type/change",
            json={
                "account_type": "cooperative",
                "confirm": True,
                "user_id": victim_user["id"],  # Maliciously targeting victim
                "uid": victim_user["id"]
            },
            headers={"Authorization": f"Bearer {attacker_token}"}
        )
        self.assertEqual(res_spoof.status_code, 200)

        # Victim's account type MUST NOT be changed
        victim_info = gari_auth.get_user_account_type_info(victim_user["id"])
        self.assertEqual(victim_info["account_type"], "farmer")

        # Attacker's own account type changed
        attacker_info = gari_auth.get_user_account_type_info(attacker_user["id"])
        self.assertEqual(attacker_info["account_type"], "cooperative")

    def test_04_account_type_persisted_loaded_and_audited(self):
        """Requirement 4, 7 & 10: Account type is persisted, loaded and audited correctly."""
        user, token = self._create_test_user(account_type="cooperative", email_prefix="audit_user")
        uid = user["id"]

        # GET /api/user/account-type
        res = self.client.get(
            "/api/user/account-type",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["account_type"], "cooperative")
        self.assertEqual(data["display_name"], "Hợp Tác Xã")
        self.assertTrue(data["is_locked"])
        self.assertEqual(len(data["available_types"]), 4)

        # Change account type with explicit confirmation
        res_change = self.client.post(
            "/api/user/account-type/change",
            json={
                "account_type": "expert",
                "confirm": True,
                "reason": "Chuyển sang chuyên gia khuyến nông"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(res_change.status_code, 200)
        change_data = res_change.json()
        self.assertEqual(change_data["account_type"], "expert")
        self.assertEqual(change_data["previous_type"], "cooperative")

        # Verify persistence in database
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT account_type FROM users WHERE id = ?", (uid,))
            self.assertEqual(cursor.fetchone()[0], "expert")

            # Verify audit trail
            cursor.execute("""
                SELECT previous_type, new_type, reason, changed_by_user_id
                FROM user_account_type_audit
                WHERE user_id = ?
                ORDER BY id DESC LIMIT 1
            """, (uid,))
            audit_row = cursor.fetchone()
            self.assertEqual(audit_row[0], "cooperative")
            self.assertEqual(audit_row[1], "expert")
            self.assertEqual(audit_row[2], "Chuyển sang chuyên gia khuyến nông")
            self.assertEqual(audit_row[3], uid)

    def test_05_account_type_changes_preserve_payment_and_vip_status(self):
        """Requirement 8 & 10: Changing account type preserves VIP subscription status intact."""
        user, token = self._create_test_user(account_type="farmer", email_prefix="vip_payer")
        uid = user["id"]

        # Assign an active Personal VIP subscription (Model 2 & 4 VIP access)
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO user_subscriptions (user_id, plan_id, status, billing_interval, start_date)
                VALUES (?, 'personal', 'active', 'monthly', ?)
            """, (uid, now_iso))
            conn.commit()

        # Check entitlement before change
        ent_before = gari_plans.resolve_user_entitlement(user)
        self.assertEqual(ent_before["plan_id"], "personal")
        self.assertTrue(ent_before["has_vip_models"])

        # Change account type from 'farmer' to 'enterprise'
        res = self.client.post(
            "/api/user/account-type/change",
            json={
                "account_type": "enterprise",
                "confirm": True,
                "reason": "Mở rộng liên kết doanh nghiệp"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(res.status_code, 200)

        # Refresh user dict
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (uid,))
            updated_user = dict(cursor.fetchone())

        self.assertEqual(updated_user["account_type"], "enterprise")

        # Check entitlement after change: VIP models MUST remain True, plan must remain 'personal'
        ent_after = gari_plans.resolve_user_entitlement(updated_user)
        self.assertEqual(ent_after["plan_id"], "personal")
        self.assertTrue(ent_after["has_vip_models"])

        # Verify user_subscriptions record was not touched or canceled
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT plan_id, status FROM user_subscriptions WHERE user_id = ?", (uid,))
            sub_row = cursor.fetchone()
            self.assertEqual(sub_row["plan_id"], "personal")
            self.assertEqual(sub_row["status"], "active")

    def test_06_backend_permission_enforcement(self):
        """Requirement 6: Enforce account-type permissions on backend."""
        farmer_user, farmer_token = self._create_test_user(account_type="farmer", email_prefix="perm_farmer")
        expert_user, expert_token = self._create_test_user(account_type="expert", email_prefix="perm_expert")

        # 1. Expert dashboard restricted to 'expert'
        # Farmer gets 403 Forbidden
        res_farmer = self.client.get(
            "/api/expert/dashboard",
            headers={"Authorization": f"Bearer {farmer_token}"}
        )
        self.assertEqual(res_farmer.status_code, 403)
        self.assertIn("Chuyên Gia BVTV", res_farmer.json()["detail"])

        # Expert succeeds with 200 OK
        res_expert = self.client.get(
            "/api/expert/dashboard",
            headers={"Authorization": f"Bearer {expert_token}"}
        )
        self.assertEqual(res_expert.status_code, 200)

        # 2. Updating an expert case via PATCH is restricted to 'expert'
        # Create a test case first
        case_res = self.client.post(
            "/api/expert/cases",
            json={"symptoms_description": "Lá lúa bị cháy đầu lá", "farmer_name": "Test Farmer"},
            headers={"Authorization": f"Bearer {farmer_token}"}
        )
        self.assertEqual(case_res.status_code, 200)
        case_id = case_res.json()["case"]["id"]

        # Farmer tries to update case status -> 403 Forbidden
        patch_farmer = self.client.patch(
            f"/api/expert/cases/{case_id}",
            json={"status": "Answered", "expert_notes": "Bệnh đạo ôn lá"},
            headers={"Authorization": f"Bearer {farmer_token}"}
        )
        self.assertEqual(patch_farmer.status_code, 403)

        # Expert updates case status -> 200 OK
        patch_expert = self.client.patch(
            f"/api/expert/cases/{case_id}",
            json={"status": "Answered", "expert_notes": "Bệnh đạo ôn lá - Khuyến nghị phun Tricyclazole"},
            headers={"Authorization": f"Bearer {expert_token}"}
        )
        self.assertEqual(patch_expert.status_code, 200)


if __name__ == "__main__":
    unittest.main()
