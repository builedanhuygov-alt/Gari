import sys
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import gari_auth
import gari_b2b
import gari_database
import gari_plans
import gari_quota
import gari_revenue
import gari_vouchers


class TestAuditComprehensive(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.now_str = self.now.strftime("%Y-%m-%d %H:%M:%S")

    def test_01_voucher_expiration_permanent_removal(self):
        """Audit Item 3: Voucher expiration permanently removes access on all subsequent calls."""
        with gari_vouchers.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email = 'audit_exp_p1@gari.vn'")
            row = cursor.fetchone()
            if not row:
                cursor.execute("""
                    INSERT INTO users (email, name, full_name, password_hash, account_type)
                    VALUES ('audit_exp_p1@gari.vn', 'Exp User', 'Exp User', 'hash', 'Nông hộ')
                """)
                user_id = cursor.lastrowid
            else:
                user_id = row["id"]
            conn.commit()

        user = {"id": user_id, "email": "audit_exp_p1@gari.vn", "account_type": "Nông hộ"}

        # Redeem voucher
        res = gari_vouchers.create_voucher(admin_user_id=1, plan_id="personal", duration_days=30)
        gari_vouchers.redeem_voucher(user_id=user_id, raw_code=res["voucher_code"])

        # Check active
        ent_active = gari_plans.resolve_user_entitlement(user)
        self.assertEqual(ent_active["plan_id"], "personal")
        self.assertTrue(ent_active["has_vip_models"])

        # Simulate expiration
        yesterday_str = (self.now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        with gari_vouchers.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE subscriptions SET current_period_end = ? WHERE user_id = ?", (yesterday_str, user_id))
            cursor.execute("UPDATE user_subscriptions SET end_date = ? WHERE user_id = ?", (yesterday_str, user_id))
            conn.commit()

        # Call 1: Drops to free
        ent_call1 = gari_plans.resolve_user_entitlement(user)
        self.assertEqual(ent_call1["plan_id"], "free")
        self.assertFalse(ent_call1["has_vip_models"])

        # Call 2: MUST stay on free (no resurrection from legacy table!)
        ent_call2 = gari_plans.resolve_user_entitlement(user)
        self.assertEqual(ent_call2["plan_id"], "free")
        self.assertFalse(ent_call2["has_vip_models"])

        # Quota check: limit must be 5 (free tier), not 150
        quota = gari_quota.get_or_create_quota_record(f"user_{user_id}", user_id=user_id, user=user)
        self.assertEqual(quota["quota_limit"], 5)

    def test_02_voucher_revocation_immediate_access_removal(self):
        """Audit Item 4: Voucher revocation immediately revokes granted access."""
        with gari_vouchers.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email = 'audit_revoke_p2@gari.vn'")
            row = cursor.fetchone()
            if not row:
                cursor.execute("""
                    INSERT INTO users (email, name, full_name, password_hash, account_type)
                    VALUES ('audit_revoke_p2@gari.vn', 'Revoke User', 'Revoke User', 'hash', 'Nông hộ')
                """)
                user_id = cursor.lastrowid
            else:
                user_id = row["id"]
            conn.commit()

        user = {"id": user_id, "email": "audit_revoke_p2@gari.vn", "account_type": "Nông hộ"}

        res = gari_vouchers.create_voucher(admin_user_id=1, plan_id="business", duration_days=30)
        v_id = res["voucher"]["id"]
        gari_vouchers.redeem_voucher(user_id=user_id, raw_code=res["voucher_code"])

        # Confirm active
        self.assertEqual(gari_plans.resolve_user_entitlement(user)["plan_id"], "business")

        # Admin revokes voucher
        gari_vouchers.revoke_voucher(voucher_id=v_id, admin_user_id=1, reason="Revoking compromised voucher")

        # Confirm user access is IMMEDIATELY revoked
        ent_after = gari_plans.resolve_user_entitlement(user)
        self.assertEqual(ent_after["plan_id"], "free")
        self.assertFalse(ent_after["has_vip_models"])

    def test_03_previous_subscription_cannot_accidentally_resurface(self):
        """Audit Item 4: Previous trial/subscription is canceled and cannot resurface after voucher expires."""
        with gari_vouchers.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email = 'audit_supersede_p3@gari.vn'")
            row = cursor.fetchone()
            if not row:
                cursor.execute("""
                    INSERT INTO users (email, name, full_name, password_hash, account_type)
                    VALUES ('audit_supersede_p3@gari.vn', 'Supersede User', 'Supersede User', 'hash', 'Nông hộ')
                """)
                user_id = cursor.lastrowid
            else:
                user_id = row["id"]

            # Give user an old active subscription row in subscriptions table
            cursor.execute("""
                INSERT INTO subscriptions (target_type, target_id, user_id, plan_id, status, billing_interval, current_period_start, is_paid)
                VALUES ('user', ?, ?, 'personal', 'active', 'monthly', CURRENT_TIMESTAMP, 0)
            """, (user_id, user_id))
            conn.commit()

        user = {"id": user_id, "email": "audit_supersede_p3@gari.vn", "account_type": "Nông hộ"}

        # User redeems a business voucher
        res = gari_vouchers.create_voucher(admin_user_id=1, plan_id="business", duration_days=30)
        gari_vouchers.redeem_voucher(user_id=user_id, raw_code=res["voucher_code"])

        # Check that previous subscription was superseded
        with gari_vouchers.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT status FROM subscriptions
                WHERE target_type = 'user' AND target_id = ? AND plan_id = 'personal'
            """, (user_id,))
            old_statuses = [r["status"] for r in cursor.fetchall()]
            for st in old_statuses:
                self.assertIn(st, ("canceled", "superseded", "expired"))

        # Now simulate expiration of the business voucher
        yesterday_str = (self.now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        with gari_vouchers.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE subscriptions SET current_period_end = ? WHERE user_id = ? AND plan_id = 'business'", (yesterday_str, user_id))
            cursor.execute("UPDATE user_subscriptions SET end_date = ? WHERE user_id = ?", (yesterday_str, user_id))
            conn.commit()

        # The user MUST NOT revert back to active personal plan!
        ent = gari_plans.resolve_user_entitlement(user)
        self.assertEqual(ent["plan_id"], "free")
        self.assertFalse(ent["has_vip_models"])

    def tearDown(self):
        gari_vouchers._FAILED_VOUCHER_ATTEMPTS.clear()

    def test_04_dual_rate_limiting_ip_and_user(self):
        """Audit Item 6: Brute force attempts locked per-IP and per-user independently."""
        test_ip = "10.254.254.99"
        user_a = 901
        user_b = 902

        # 5 failed attempts from user_a on test_ip
        for _ in range(5):
            try:
                gari_vouchers.redeem_voucher(user_id=user_a, raw_code="GARI-INVALID-CODE", ip_address=test_ip)
            except gari_vouchers.VoucherError:
                pass

        # 6th attempt from user_a on test_ip should be rate limited
        with self.assertRaises(gari_vouchers.VoucherRateLimitExceededError):
            gari_vouchers.redeem_voucher(user_id=user_a, raw_code="GARI-INVALID-CODE", ip_address=test_ip)

        # 6th attempt from DIFFERENT user_b on the SAME test_ip should ALSO be rate limited (per-IP enforcement!)
        with self.assertRaises(gari_vouchers.VoucherRateLimitExceededError):
            gari_vouchers.redeem_voucher(user_id=user_b, raw_code="GARI-INVALID-CODE", ip_address=test_ip)

    def test_05_concurrent_redemption_race_safety(self):
        """Audit Item 7: Database-level atomicity and unique constraint under concurrency."""
        # Create a single-use voucher (max_redemptions = 1)
        res = gari_vouchers.create_voucher(admin_user_id=1, plan_id="personal", max_redemptions=1, duration_days=30)
        raw_code = res["voucher_code"]
        v_id = res["voucher"]["id"]

        successes = []
        errors = []

        def attempt_redeem(uid):
            try:
                r = gari_vouchers.redeem_voucher(user_id=uid, raw_code=raw_code, ip_address=f"10.0.0.{uid}")
                if r.get("success"):
                    successes.append(uid)
            except Exception as e:
                errors.append((uid, type(e).__name__))

        # Launch 8 simultaneous threads trying to redeem the same single-use voucher
        threads = [threading.Thread(target=attempt_redeem, args=(800 + i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(successes), 1, f"Exactly 1 thread must succeed. Succeeded: {successes}")
        self.assertEqual(len(errors), 7, f"Exactly 7 threads must fail. Failed: {len(errors)}")

        # Verify DB state
        with gari_vouchers.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT redemption_count, status FROM vouchers WHERE id = ?", (v_id,))
            v_row = cursor.fetchone()
            self.assertEqual(v_row["redemption_count"], 1)
            self.assertEqual(v_row["status"], "exhausted")

    def test_06_organization_tenant_isolation(self):
        """Audit Item 8: Verify a user in Org A cannot access Org B's data or shared quota."""
        with gari_b2b.get_db_connection() as conn:
            cursor = conn.cursor()
            # Ensure two test organizations exist
            cursor.execute("SELECT id FROM organizations WHERE slug = 'audit-org-a'")
            row_a = cursor.fetchone()
            if not row_a:
                cursor.execute("""
                    INSERT INTO organizations (name, slug, owner_id, plan_id, status)
                    VALUES ('Audit Org A', 'audit-org-a', 1, 'team', 'active')
                """)
                org_a_id = cursor.lastrowid
            else:
                org_a_id = row_a["id"]

            cursor.execute("SELECT id FROM organizations WHERE slug = 'audit-org-b'")
            row_b = cursor.fetchone()
            if not row_b:
                cursor.execute("""
                    INSERT INTO organizations (name, slug, owner_id, plan_id, status)
                    VALUES ('Audit Org B', 'audit-org-b', 1, 'team', 'active')
                """)
                org_b_id = cursor.lastrowid
            else:
                org_b_id = row_b["id"]

            # Add User 501 only to Org A
            cursor.execute("INSERT OR IGNORE INTO organization_members (organization_id, user_id, role) VALUES (?, 501, 'member')", (org_a_id,))
            # Ensure User 501 is NOT in Org B
            cursor.execute("DELETE FROM organization_members WHERE organization_id = ? AND user_id = 501", (org_b_id,))
            conn.commit()

        # Check membership
        self.assertIsNotNone(gari_b2b.get_member_role(org_a_id, 501))
        self.assertIsNone(gari_b2b.get_member_role(org_b_id, 501))

        # Check permission check raises exception for Org B
        with self.assertRaises(gari_b2b.OrganizationPermissionError):
            gari_b2b.require_permission(org_b_id, 501, "diagnosis.use")

    def test_07_b2b_canonical_business_plan_configured(self):
        """Audit Item 8: Verify 'business' and 'personal' are configured in gari_b2b."""
        self.assertIn("business", gari_b2b.PLANS_CONFIG)
        self.assertIn("personal", gari_b2b.PLANS_CONFIG)
        self.assertEqual(gari_b2b.PLANS_CONFIG["business"]["price_vnd_month"], 299000)
        self.assertEqual(gari_b2b.PLANS_CONFIG["personal"]["price_vnd_month"], 129000)
        self.assertIn("business", gari_b2b.PAID_ORG_PLANS)


if __name__ == "__main__":
    unittest.main()
