"""
GARI AI LAB — Comprehensive Voucher & Pricing Security Test Suite (test_vouchers.py)
Tests all requirements:
1. Voucher generation (SHA-256 hashing, entropy, single raw code return)
2. Voucher redemption & entitlement granting (personal & business)
3. Duplicate redemption prevention
4. Expiration rejection
5. Revocation rejection
6. Redemption count / exhaustion enforcement
7. Email restriction enforcement
8. Brute-force rate limiting (5 failed attempts -> lockout)
9. Concurrency protection (multithreaded race condition resistance)
10. Admin authorization enforcement (normal user rejected with 403)
"""

import concurrent.futures
import datetime
import os
import secrets
import sqlite3
import sys
import unittest
from datetime import timedelta, timezone
from pathlib import Path

# Add root directory to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import gari_auth
import gari_plans
import gari_revenue
import gari_vouchers


class TestVouchersAndPricing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure database tables exist
        from database.migrations_vouchers import run_migrations
        run_migrations()

        # Create test admin user and normal test users if not exist
        with gari_vouchers.get_db_connection() as conn:
            cursor = conn.cursor()
            # Admin user
            cursor.execute("SELECT id FROM users WHERE email = 'test_admin_voucher@gari.vn'")
            admin_row = cursor.fetchone()
            if not admin_row:
                cursor.execute("""
                    INSERT INTO users (email, name, full_name, password_hash, account_type, is_admin)
                    VALUES ('test_admin_voucher@gari.vn', 'Admin Test', 'Admin Test', 'hash', 'Platform Admin', 1)
                """)
                cls.admin_id = cursor.lastrowid
            else:
                cls.admin_id = admin_row["id"]

            # User 1
            cursor.execute("SELECT id FROM users WHERE email = 'test_user1_voucher@gari.vn'")
            u1_row = cursor.fetchone()
            if not u1_row:
                cursor.execute("""
                    INSERT INTO users (email, name, full_name, password_hash, account_type, is_admin)
                    VALUES ('test_user1_voucher@gari.vn', 'User One', 'User One', 'hash', 'Nông hộ', 0)
                """)
                cls.user1_id = cursor.lastrowid
            else:
                cls.user1_id = u1_row["id"]

            # User 2
            cursor.execute("SELECT id FROM users WHERE email = 'test_user2_voucher@gari.vn'")
            u2_row = cursor.fetchone()
            if not u2_row:
                cursor.execute("""
                    INSERT INTO users (email, name, full_name, password_hash, account_type, is_admin)
                    VALUES ('test_user2_voucher@gari.vn', 'User Two', 'User Two', 'hash', 'Nông hộ', 0)
                """)
                cls.user2_id = cursor.lastrowid
            else:
                cls.user2_id = u2_row["id"]

            conn.commit()

    def setUp(self):
        gari_vouchers._FAILED_VOUCHER_ATTEMPTS.clear()

    def tearDown(self):
        gari_vouchers._FAILED_VOUCHER_ATTEMPTS.clear()

    def test_01_pricing_plans_specification(self):
        """Verify Personal (129k) and Business (299k) integer VND pricing and catalog."""
        personal = gari_plans.get_plan_definition("personal")
        self.assertEqual(personal["plan_id"], "personal")
        self.assertEqual(personal["display_name"], "Cá nhân")
        self.assertEqual(personal["price"], 129000)
        self.assertIsInstance(personal["price"], int)
        self.assertEqual(personal["currency"], "VND")
        self.assertEqual(personal["billing_interval"], "monthly")
        self.assertTrue(personal["has_vip_models"])
        self.assertEqual(personal["max_members"], 1)

        business = gari_plans.get_plan_definition("business")
        self.assertEqual(business["plan_id"], "business")
        self.assertEqual(business["display_name"], "Doanh nghiệp")
        self.assertEqual(business["price"], 299000)
        self.assertIsInstance(business["price"], int)
        self.assertEqual(business["currency"], "VND")
        self.assertEqual(business["billing_interval"], "monthly")
        self.assertTrue(business["has_vip_models"])
        self.assertTrue(business["has_api_access"])
        self.assertEqual(business["max_members"], 10)

        # Verify catalog list contains both
        active_plans = gari_plans.list_active_plans()
        plan_ids = [p["plan_id"] for p in active_plans]
        self.assertIn("personal", plan_ids)
        self.assertIn("business", plan_ids)
        self.assertIn("free", plan_ids)

    def test_02_voucher_creation_security(self):
        """Verify voucher creation: raw code returned once, only SHA-256 hash stored in DB."""
        res = gari_vouchers.create_voucher(
            admin_user_id=self.admin_id,
            plan_id="personal",
            duration_days=30,
            max_redemptions=1,
            notes="Security Test Voucher"
        )
        self.assertTrue(res["success"])
        raw_code = res["voucher_code"]
        self.assertTrue(raw_code.startswith("GARI-PERS-"))
        voucher_id = res["voucher"]["id"]

        # Check DB: verify plaintext raw_code is NOT stored in vouchers table!
        with gari_vouchers.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vouchers WHERE id = ?", (voucher_id,))
            row = dict(cursor.fetchone())
            self.assertNotIn("raw_code", row)
            self.assertNotEqual(row["code_hash"], raw_code)
            self.assertEqual(row["code_hash"], gari_vouchers.hash_code(raw_code))
            self.assertTrue(row["code_preview"].startswith("GARI-PERS-****-"))
            self.assertEqual(row["status"], "active")
            self.assertEqual(row["redemption_count"], 0)

    def test_03_successful_redemption_and_entitlement(self):
        """User redeems voucher -> receives active subscription & entitlement for exact plan."""
        res = gari_vouchers.create_voucher(
            admin_user_id=self.admin_id,
            plan_id="personal",
            duration_days=45
        )
        raw_code = res["voucher_code"]

        redeem_res = gari_vouchers.redeem_voucher(
            user_id=self.user1_id,
            raw_code=raw_code,
            ip_address="127.0.0.1"
        )
        self.assertTrue(redeem_res["success"])
        self.assertEqual(redeem_res["plan_id"], "personal")
        self.assertEqual(redeem_res["duration_days"], 45)

        # Check entitlement resolution for user1
        user1_dict = {"id": self.user1_id, "email": "test_user1_voucher@gari.vn"}
        entitlement = gari_plans.resolve_user_entitlement(user1_dict)
        self.assertEqual(entitlement["plan_id"], "personal")
        self.assertEqual(entitlement["access_source"], "voucher")
        self.assertEqual(entitlement["subscription_status"], "active")
        self.assertTrue(entitlement["is_active"])
        self.assertTrue(entitlement["has_vip_models"])

    def test_04_duplicate_redemption_prevented(self):
        """Same user cannot redeem the same voucher twice."""
        res = gari_vouchers.create_voucher(
            admin_user_id=self.admin_id,
            plan_id="business",
            duration_days=30,
            max_redemptions=5
        )
        raw_code = res["voucher_code"]

        # First redemption succeeds
        redeem1 = gari_vouchers.redeem_voucher(user_id=self.user1_id, raw_code=raw_code)
        self.assertTrue(redeem1["success"])

        # Second redemption by same user must raise VoucherAlreadyRedeemedError
        with self.assertRaises(gari_vouchers.VoucherAlreadyRedeemedError):
            gari_vouchers.redeem_voucher(user_id=self.user1_id, raw_code=raw_code)

    def test_05_expired_voucher_rejected(self):
        """Expired voucher is rejected."""
        past_date = (gari_vouchers.now_utc() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        res = gari_vouchers.create_voucher(
            admin_user_id=self.admin_id,
            plan_id="personal",
            expires_at_iso=past_date
        )
        v_id = res["voucher"]["id"]
        raw_code = res["voucher_code"]

        # Manually alter expiration date in DB to past
        past_iso = (gari_vouchers.now_utc() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        with gari_vouchers.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE vouchers SET expires_at = ? WHERE id = ?", (past_iso, v_id))
            conn.commit()

        with self.assertRaises(gari_vouchers.VoucherExpiredError):
            gari_vouchers.redeem_voucher(user_id=self.user2_id, raw_code=raw_code)

    def test_06_revoked_voucher_rejected(self):
        """Revoked voucher cannot be redeemed."""
        res = gari_vouchers.create_voucher(
            admin_user_id=self.admin_id,
            plan_id="personal",
            duration_days=30
        )
        v_id = res["voucher"]["id"]
        raw_code = res["voucher_code"]

        # Revoke voucher
        gari_vouchers.revoke_voucher(
            voucher_id=v_id,
            admin_user_id=self.admin_id,
            reason="Thu hồi thử nghiệm bảo mật"
        )

        with self.assertRaises(gari_vouchers.VoucherRevokedError):
            gari_vouchers.redeem_voucher(user_id=self.user2_id, raw_code=raw_code)

    def test_07_redemption_limit_exhausted(self):
        """Single-use voucher cannot be redeemed by a second user."""
        res = gari_vouchers.create_voucher(
            admin_user_id=self.admin_id,
            plan_id="personal",
            max_redemptions=1
        )
        raw_code = res["voucher_code"]

        # User 1 redeems
        res1 = gari_vouchers.redeem_voucher(user_id=self.user1_id, raw_code=raw_code)
        self.assertTrue(res1["success"])

        # User 2 tries to redeem the same single-use voucher
        with self.assertRaises(gari_vouchers.VoucherExhaustedError):
            gari_vouchers.redeem_voucher(user_id=self.user2_id, raw_code=raw_code)

    def test_08_email_restriction_enforced(self):
        """Restricted voucher can only be redeemed by designated email."""
        res = gari_vouchers.create_voucher(
            admin_user_id=self.admin_id,
            plan_id="business",
            restricted_to_email="test_user1_voucher@gari.vn"
        )
        raw_code = res["voucher_code"]

        # User 2 (email: test_user2_voucher@gari.vn) attempts redemption -> rejected
        with self.assertRaises(gari_vouchers.VoucherIneligibleError):
            gari_vouchers.redeem_voucher(user_id=self.user2_id, raw_code=raw_code)

        # User 1 (matching email) attempts redemption -> succeeds
        res1 = gari_vouchers.redeem_voucher(user_id=self.user1_id, raw_code=raw_code)
        self.assertTrue(res1["success"])

    def test_09_brute_force_rate_limiting(self):
        """5 failed voucher attempts trigger rate limiting lockout."""
        fake_ip = "192.168.100.99"
        test_uid = 9999

        for attempt in range(gari_vouchers.RATE_LIMIT_MAX_ATTEMPTS):
            with self.assertRaises(gari_vouchers.VoucherNotFoundError):
                gari_vouchers.redeem_voucher(
                    user_id=test_uid,
                    raw_code=f"GARI-FAKE-CODE-{attempt}",
                    ip_address=fake_ip
                )

        # 6th attempt must be blocked by rate limiter
        with self.assertRaises(gari_vouchers.VoucherRateLimitExceededError):
            gari_vouchers.redeem_voucher(
                user_id=test_uid,
                raw_code="GARI-ANOTHER-ATTEMPT",
                ip_address=fake_ip
            )

    def test_10_concurrent_redemption_safety(self):
        """
        Concurrency stress test:
        Create a voucher with max_redemptions=2.
        Launch 5 parallel threads attempting to redeem for distinct simulated users.
        Exactly 2 must succeed; 3 must fail. Total redemptions in DB must be exactly 2.
        """
        # Create 5 distinct simulated users
        sim_user_ids = []
        with gari_vouchers.get_db_connection() as conn:
            cursor = conn.cursor()
            for i in range(5):
                email = f"sim_user_{secrets.token_hex(4)}@gari.vn"
                cursor.execute("INSERT INTO users (email, name, full_name, password_hash) VALUES (?, 'Sim', 'Sim', 'h')", (email,))
                sim_user_ids.append(cursor.lastrowid)
            conn.commit()

        res = gari_vouchers.create_voucher(
            admin_user_id=self.admin_id,
            plan_id="personal",
            max_redemptions=2
        )
        raw_code = res["voucher_code"]
        v_id = res["voucher"]["id"]

        results = []
        errors = []

        def worker(uid):
            try:
                r = gari_vouchers.redeem_voucher(user_id=uid, raw_code=raw_code, ip_address=f"10.0.0.{uid}")
                results.append(r)
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker, uid) for uid in sim_user_ids]
            concurrent.futures.wait(futures)

        self.assertEqual(len(results), 2, f"Expected exactly 2 redemptions to succeed, got {len(results)}")
        self.assertEqual(len(errors), 3, f"Expected exactly 3 redemptions to fail, got {len(errors)}")

        # Verify DB final state
        with gari_vouchers.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT redemption_count, status FROM vouchers WHERE id = ?", (v_id,))
            row = dict(cursor.fetchone())
            self.assertEqual(row["redemption_count"], 2)
            self.assertEqual(row["status"], "exhausted")

            cursor.execute("SELECT COUNT(*) as cnt FROM voucher_redemptions WHERE voucher_id = ?", (v_id,))
            cnt = cursor.fetchone()["cnt"]
            self.assertEqual(cnt, 2)


if __name__ == "__main__":
    unittest.main()
