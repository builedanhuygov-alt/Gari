"""
GARI AI LAB — Vietnamese Bank QR Payment & Manual Admin Verification Tests (test_bank_qr_sepay.py)

Comprehensive synthetic test suite covering:
1. Public checkout disabled by default (fail-closed security)
2. Valid checkout creates pending order with UID-linked unique order reference (e.g. GARI-U<uid>-<order_code>)
3. Multiple purchases by same user have distinct unique references (UID alone is never the reference)
4. User clicks 'Tôi đã chuyển khoản' ('I have transferred') -> transitions to 'pending_review'
   CRITICAL TEST: User-submitted confirmation NEVER grants VIP or modifies entitlements!
5. Unauthenticated / unauthorized user cannot report transfer on another user's order (401 / 403)
6. Non-admin caller CANNOT confirm payment (403 Forbidden; server-side verified, never trusts frontend flags)
7. Authorized admin confirms payment with bank transaction reference:
   - Order marked 'paid'
   - Atomically grants 30-day VIP subscription & creates paid invoice
   - User entitlement upgraded to Pro/VIP
8. Duplicate admin confirmation is idempotent (no duplicate grants, no end-date extensions)
9. Complete audit trail verification (admin ID, order reference, amount, bank tx ref, timestamp)
10. Admin can reject payment order (status becomes 'rejected', no VIP)
11. Admin can list and filter payment orders for review
12. Database atomicity: subscription grant failure rolls back payment order

Note: Synthetic test payloads ONLY. Never initiates real transfers or claims live payment.
"""

import json
import os
import sqlite3
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
import gari_auth
import gari_database
import gari_payment
import gari_plans
import gari_vouchers
from api_server import app


TEST_BANK_CONFIG = {
    "PAYMENT_PROVIDER": "bank_qr",
    "BANK_QR_BANK_ID": "MoMo (VietQR / NAPAS 24/7)",
    "BANK_QR_ACCOUNT_NUMBER": "*******193",
    "BANK_QR_ACCOUNT_NAME": "BUI LE DAN HUY",
    "PAYMENT_STATIC_QR_URL": "/static/frontend2/images/vietqr_momo.jpg",
    "PAYMENT_PUBLIC_CHECKOUT_ENABLED": "1",
    "PAYMENT_ORDER_EXPIRY_MINUTES": "15",
}



class TestBankQRPaymentManualAdmin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

        # Setup test users
        with gari_payment.get_db_connection() as conn:
            cursor = conn.cursor()
            # 1. Regular User A
            cursor.execute("SELECT id FROM users WHERE email = 'bankqr_user_a@gari.vn'")
            row = cursor.fetchone()
            if not row:
                cursor.execute("""
                    INSERT INTO users (email, name, full_name, password_hash, account_type, is_admin)
                    VALUES ('bankqr_user_a@gari.vn', 'User A', 'User A', 'hash', 'Nông hộ', 0)
                """)
                cls.user_a_id = cursor.lastrowid
            else:
                cls.user_a_id = row["id"]

            # 2. Regular User B (Attacker / Different User)
            cursor.execute("SELECT id FROM users WHERE email = 'bankqr_user_b@gari.vn'")
            row_b = cursor.fetchone()
            if not row_b:
                cursor.execute("""
                    INSERT INTO users (email, name, full_name, password_hash, account_type, is_admin)
                    VALUES ('bankqr_user_b@gari.vn', 'User B', 'User B', 'hash', 'Nông hộ', 0)
                """)
                cls.user_b_id = cursor.lastrowid
            else:
                cls.user_b_id = row_b["id"]

            # 3. Platform Admin
            cursor.execute("SELECT id FROM users WHERE email = 'bankqr_admin@gari.vn'")
            row_admin = cursor.fetchone()
            if not row_admin:
                cursor.execute("""
                    INSERT INTO users (email, name, full_name, password_hash, account_type, is_admin)
                    VALUES ('bankqr_admin@gari.vn', 'Payment Admin', 'Payment Admin', 'hash', 'Platform Admin', 1)
                """)
                cls.admin_id = cursor.lastrowid
            else:
                cls.admin_id = row_admin["id"]

            conn.commit()

        # Sessions
        cls.user_a_token = gari_auth.create_session(cls.user_a_id)
        cls.user_b_token = gari_auth.create_session(cls.user_b_id)
        cls.admin_token = gari_auth.create_session(cls.admin_id)

        cls.user_a_headers = {"Authorization": f"Bearer {cls.user_a_token}"}
        cls.user_b_headers = {"Authorization": f"Bearer {cls.user_b_token}"}
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

    def setUp(self):
        self.env_patcher = patch.dict(os.environ, TEST_BANK_CONFIG)
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_01_public_checkout_disabled_by_default(self):
        """When PAYMENT_PUBLIC_CHECKOUT_ENABLED is '0', checkout fails-closed."""
        with patch.dict(os.environ, {"PAYMENT_PUBLIC_CHECKOUT_ENABLED": "0"}):
            res = self.client.post("/api/billing/checkout", headers=self.user_a_headers, json={"plan_id": "personal"})
            self.assertEqual(res.status_code, 400)
            data = res.json()
            self.assertIn("mở công khai", data["detail"])

    def test_02_valid_checkout_creates_order_with_uid_linked_reference(self):
        """Checkout creates pending order with reference linked to user UID and unique order code."""
        res = self.client.post("/api/billing/checkout", headers=self.user_a_headers, json={
            "plan_id": "personal",
            "amount": 1000  # Untrusted client amount must be ignored
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertTrue(data["success"])
        self.assertEqual(data["amount"], 129000, "Server canonical pricing strictly enforced (129,000 VND)")
        self.assertEqual(data["currency"], "VND")
        self.assertEqual(data["payment_status"], "pending")

        # Check reference format: GARI-U<uid>-<order_code>
        order_ref = data["order_reference"]
        expected_prefix = f"GARI-U{self.user_a_id}-"
        self.assertTrue(order_ref.startswith(expected_prefix), f"Reference '{order_ref}' must start with '{expected_prefix}'")
        self.assertNotEqual(order_ref, f"GARI-{self.user_a_id}", "Reference must NOT be user UID alone")

        # Check Static QR Asset URL
        qr_url = data["qr_code_url"]
        self.assertEqual(qr_url, "/static/frontend2/images/vietqr_momo.jpg")

        # Verify static asset exists on disk and is non-empty
        asset_disk_path = ROOT_DIR / "frontend2" / "images" / "vietqr_momo.jpg"
        self.assertTrue(asset_disk_path.exists(), f"Static QR asset must exist at {asset_disk_path}")
        self.assertGreater(asset_disk_path.stat().st_size, 1000, "Static QR asset must be a valid image file")

        # Verify recipient details match uploaded QR asset
        self.assertEqual(data["bank_id"], "MoMo (VietQR / NAPAS 24/7)")
        self.assertEqual(data["account_number"], "*******193")
        self.assertEqual(data["account_name"], "BUI LE DAN HUY")


    def test_03_multiple_purchases_by_same_user_have_unique_references(self):
        """Users purchasing multiple times get distinct, unique order references despite having identical UID."""
        order1 = gari_payment.create_bank_qr_order(self.user_a_id, "personal")
        order2 = gari_payment.create_bank_qr_order(self.user_a_id, "personal")

        self.assertNotEqual(order1["order_code"], order2["order_code"])
        self.assertNotEqual(order1["order_reference"], order2["order_reference"])
        self.assertTrue(order1["order_reference"].startswith(f"GARI-U{self.user_a_id}-"))
        self.assertTrue(order2["order_reference"].startswith(f"GARI-U{self.user_a_id}-"))

    def test_04_user_reports_transfer_sets_pending_review_and_NEVER_grants_vip(self):
        """
        User clicking 'Tôi đã chuyển khoản' ('I have transferred') transitions order
        to 'pending_review'. CRITICAL REQUIREMENT: This action NEVER grants VIP!
        """
        # 1. Reset user A to free plan for clean test
        with gari_payment.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE subscriptions SET status = 'canceled' WHERE user_id = ?", (self.user_a_id,))
            cursor.execute("UPDATE user_subscriptions SET status = 'canceled' WHERE user_id = ?", (self.user_a_id,))
            conn.commit()

        initial_ent = gari_plans.resolve_user_entitlement({"id": self.user_a_id})
        self.assertEqual(initial_ent["plan_id"], "free")
        self.assertFalse(initial_ent["has_vip_models"])

        # 2. Create pending order
        order = gari_payment.create_bank_qr_order(self.user_a_id, "personal")
        order_code = order["order_code"]

        # 3. User reports transfer
        res = self.client.post(
            f"/api/billing/orders/{order_code}/transferred",
            headers=self.user_a_headers,
            json={"notes": "Đã chuyển khoản từ Techcombank lúc 14:30"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["payment_status"], "pending_review")
        self.assertIsNotNone(data.get("transfer_reported_at"))

        # 4. Check order status in DB
        st = gari_payment.get_order_status(order_code, user_id=self.user_a_id)
        self.assertEqual(st["payment_status"], "pending_review")
        self.assertIsNone(st["paid_at"])

        # 5. ABSOLUTE ZERO-TRUST CHECK: User MUST still be on Free plan! NO VIP!
        ent_after_report = gari_plans.resolve_user_entitlement({"id": self.user_a_id})
        self.assertEqual(ent_after_report["plan_id"], "free", "User-submitted report must NEVER grant VIP!")
        self.assertFalse(ent_after_report["has_vip_models"], "VIP models must remain locked until admin confirmation!")

    def test_05_unauthorized_user_cannot_report_transfer(self):
        """Caller cannot report transfer on another user's order (403), unauthenticated gets 401."""
        order = gari_payment.create_bank_qr_order(self.user_a_id, "personal")
        order_code = order["order_code"]

        # Unauthenticated
        res_unauth = self.client.post(f"/api/billing/orders/{order_code}/transferred", json={})
        self.assertEqual(res_unauth.status_code, 401)

        # User B attempts to report transfer for User A's order
        res_user_b = self.client.post(
            f"/api/billing/orders/{order_code}/transferred",
            headers=self.user_b_headers,
            json={}
        )
        self.assertEqual(res_user_b.status_code, 403)

    def test_06_non_admin_cannot_confirm_payment(self):
        """Regular user cannot access admin manual review confirmation (403 Forbidden)."""
        order = gari_payment.create_bank_qr_order(self.user_a_id, "personal")
        order_code = order["order_code"]

        # User reports transfer
        self.client.post(f"/api/billing/orders/{order_code}/transferred", headers=self.user_a_headers, json={})

        # Regular user A tries to confirm their own order
        res_confirm = self.client.post(
            f"/api/admin/billing/orders/{order_code}/confirm",
            headers=self.user_a_headers,
            json={"bank_tx_reference": "FAKE_REF"}
        )
        self.assertEqual(res_confirm.status_code, 403, "Non-admin must be rejected from manual confirmation endpoint")

        # Order must remain in pending_review
        st = gari_payment.get_order_status(order_code)
        self.assertEqual(st["payment_status"], "pending_review")

        # Entitlement remains free
        ent = gari_plans.resolve_user_entitlement({"id": self.user_a_id})
        self.assertEqual(ent["plan_id"], "free")

    def test_07_authorized_admin_confirms_payment_and_grants_vip_atomically(self):
        """Authorized admin confirms payment: order marked paid and 30-day subscription granted atomically."""
        order = gari_payment.create_bank_qr_order(self.user_a_id, "personal")
        order_code = order["order_code"]

        # User reports transfer
        self.client.post(f"/api/billing/orders/{order_code}/transferred", headers=self.user_a_headers, json={})

        # Admin reviews bank statement and confirms
        bank_tx_id = f"VCB_TX_{order_code}"
        res = self.client.post(
            f"/api/admin/billing/orders/{order_code}/confirm",
            headers=self.admin_headers,
            json={
                "bank_tx_reference": bank_tx_id,
                "admin_notes": "Xác nhận đã nhận đủ 129.000 đ vào tài khoản MB"
            }
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["payment_status"], "paid")
        self.assertEqual(data["bank_tx_reference"], bank_tx_id)
        self.assertEqual(data["confirmed_by_admin_id"], self.admin_id)

        # Verify DB state
        st = gari_payment.get_order_status(order_code)
        self.assertEqual(st["payment_status"], "paid")
        self.assertIsNotNone(st["paid_at"])
        self.assertEqual(st["confirmed_by_admin_id"], self.admin_id)
        self.assertEqual(st["bank_tx_reference"], bank_tx_id)

        # Verify paid invoice in DB
        with gari_payment.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM invoices WHERE invoice_number = ?", (f"INV-BANK-{order_code}",))
            inv = cursor.fetchone()
            self.assertIsNotNone(inv)
            self.assertEqual(inv["amount"], 129000)
            self.assertEqual(inv["payment_status"], "succeeded")

        # Verify User A now has active Personal VIP entitlement
        ent = gari_plans.resolve_user_entitlement({"id": self.user_a_id})
        self.assertEqual(ent["plan_id"], "personal")
        self.assertTrue(ent["has_vip_models"])

    def test_08_duplicate_admin_confirmation_is_idempotent(self):
        """Duplicate admin confirmation call does not double-grant subscription or extend end date."""
        order = gari_payment.create_bank_qr_order(self.user_a_id, "personal")
        order_code = order["order_code"]

        # 1. First confirmation
        res1 = self.client.post(
            f"/api/admin/billing/orders/{order_code}/confirm",
            headers=self.admin_headers,
            json={"bank_tx_reference": "TX_FIRST"}
        )
        self.assertEqual(res1.status_code, 200)
        self.assertFalse(res1.json().get("already_paid", False))

        with gari_payment.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT current_period_end FROM subscriptions WHERE user_id = ? AND status = 'active'", (self.user_a_id,))
            initial_end = cursor.fetchone()["current_period_end"]

        # 2. Second confirmation call
        res2 = self.client.post(
            f"/api/admin/billing/orders/{order_code}/confirm",
            headers=self.admin_headers,
            json={"bank_tx_reference": "TX_DUPLICATE_CALL"}
        )
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json().get("already_paid", True))

        # Check subscription end date was NOT extended twice
        with gari_payment.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT current_period_end FROM subscriptions WHERE user_id = ? AND status = 'active'", (self.user_a_id,))
            after_end = cursor.fetchone()["current_period_end"]
            self.assertEqual(after_end, initial_end)

    def test_09_audit_trail_preserved(self):
        """Audit trail preserves: admin ID, order reference, amount, bank tx reference, and timestamp."""
        order = gari_payment.create_bank_qr_order(self.user_a_id, "personal")
        order_code = order["order_code"]
        order_ref = order["order_reference"]

        # User report
        self.client.post(f"/api/billing/orders/{order_code}/transferred", headers=self.user_a_headers, json={})

        # Admin confirm
        bank_ref = f"AUDIT_TX_{order_code}"
        self.client.post(
            f"/api/admin/billing/orders/{order_code}/confirm",
            headers=self.admin_headers,
            json={"bank_tx_reference": bank_ref, "admin_notes": "Audit test check"}
        )

        with gari_payment.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM payment_audit_log
                WHERE order_code = ? AND action = 'admin_payment_confirmed'
            """, (order_code,))
            audit = cursor.fetchone()

            self.assertIsNotNone(audit, "Admin confirmation audit log must be recorded")
            self.assertEqual(audit["actor_type"], "admin")
            self.assertEqual(audit["actor_id"], str(self.admin_id))

            details = json.loads(audit["details_json"])
            self.assertEqual(details["admin_id"], self.admin_id)
            self.assertEqual(details["order_reference"], order_ref)
            self.assertEqual(details["amount"], 129000)
            self.assertEqual(details["bank_tx_reference"], bank_ref)
            self.assertIn("confirmed_at", details)

    def test_10_admin_can_reject_payment_order(self):
        """Admin can reject an invalid transfer order (status becomes rejected, no VIP)."""
        order = gari_payment.create_bank_qr_order(self.user_a_id, "personal")
        order_code = order["order_code"]

        # Admin rejects
        res = self.client.post(
            f"/api/admin/billing/orders/{order_code}/reject",
            headers=self.admin_headers,
            json={"reason": "Không tìm thấy giao dịch ngân hàng tương ứng sau 24h"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["payment_status"], "rejected")

        st = gari_payment.get_order_status(order_code)
        self.assertEqual(st["payment_status"], "rejected")
        self.assertIn("Không tìm thấy", st["failure_reason"])

    def test_11_admin_list_orders_filtering(self):
        """Admin can list and filter payment orders for review."""
        order = gari_payment.create_bank_qr_order(self.user_a_id, "personal")
        self.client.post(f"/api/billing/orders/{order['order_code']}/transferred", headers=self.user_a_headers, json={})

        res = self.client.get("/api/admin/billing/orders?status=pending_review", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        orders = res.json()["orders"]
        self.assertTrue(any(o["order_code"] == order["order_code"] for o in orders))

    def test_12_subscription_grant_failure_rolls_back_payment_order(self):
        """If database failure occurs during subscription insertion, order is safely rolled back."""
        order = gari_payment.create_bank_qr_order(self.user_a_id, "personal")
        order_code = order["order_code"]

        real_get_conn = gari_payment.get_db_connection

        class FaultyCursorWrapper:
            def __init__(self, real_cursor):
                self._cursor = real_cursor

            def execute(self, sql, *args, **kwargs):
                if "INSERT INTO subscriptions" in sql:
                    raise sqlite3.OperationalError("Simulated DB Disk Full during subscription grant")
                return self._cursor.execute(sql, *args, **kwargs)

            def __getattr__(self, name):
                return getattr(self._cursor, name)

        class FaultyConnWrapper:
            def __init__(self, real_conn):
                self._conn = real_conn

            def cursor(self):
                return FaultyCursorWrapper(self._conn.cursor())

            def __getattr__(self, name):
                return getattr(self._conn, name)

            def __enter__(self):
                self._conn.__enter__()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                return self._conn.__exit__(exc_type, exc_val, exc_tb)

        with patch("gari_payment.get_db_connection", side_effect=lambda: FaultyConnWrapper(real_get_conn())):
            res = self.client.post(
                f"/api/admin/billing/orders/{order_code}/confirm",
                headers=self.admin_headers,
                json={"bank_tx_reference": "TX_FAIL"}
            )
            self.assertEqual(res.status_code, 500)

        # Check DB: order must NOT be marked 'paid'
        st = gari_payment.get_order_status(order_code)
        self.assertNotEqual(st["payment_status"], "paid")
        self.assertIsNone(st["paid_at"])

    def test_13_invalid_amount_or_order_reference_cannot_grant_vip(self):
        """
        Tampered amount during checkout, non-existent order references, or invalid plans
        can never grant VIP entitlements.
        """
        # 1. Reset user A to free plan
        with gari_payment.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE subscriptions SET status = 'canceled' WHERE user_id = ?", (self.user_a_id,))
            cursor.execute("UPDATE user_subscriptions SET status = 'canceled' WHERE user_id = ?", (self.user_a_id,))
            conn.commit()

        initial_ent = gari_plans.resolve_user_entitlement({"id": self.user_a_id})
        self.assertEqual(initial_ent["plan_id"], "free")
        self.assertFalse(initial_ent["has_vip_models"])

        # 2. Checkout with negative, zero, or manipulated amount is ignored and forces server canonical price
        res_tampered = self.client.post("/api/billing/checkout", headers=self.user_a_headers, json={
            "plan_id": "personal",
            "amount": -50000
        })
        self.assertEqual(res_tampered.status_code, 200)
        self.assertEqual(res_tampered.json()["amount"], 129000, "Must ignore client-submitted tampered amount")

        # 3. Checkout with invalid plan code fails
        res_invalid_plan = self.client.post("/api/billing/checkout", headers=self.user_a_headers, json={
            "plan_id": "invalid_super_vip_plan"
        })
        self.assertEqual(res_invalid_plan.status_code, 400)

        # 4. Confirmation attempt with non-existent numeric order code returns 404
        res_fake_code = self.client.post(
            "/api/admin/billing/orders/99999999/confirm",
            headers=self.admin_headers,
            json={"bank_tx_reference": "TX_FAKE"}
        )
        self.assertEqual(res_fake_code.status_code, 404)

        # 5. Direct call to admin_confirm_payment with non-existent reference fails
        with self.assertRaises(gari_payment.PaymentOrderNotFoundError):
            gari_payment.admin_confirm_payment(
                order_code="GARI-U999-99999999",
                admin_user_id=self.admin_id,
                bank_tx_reference="TX_FAKE"
            )

        # 6. Verify User A remains on Free plan with zero VIP access
        final_ent = gari_plans.resolve_user_entitlement({"id": self.user_a_id})
        self.assertEqual(final_ent["plan_id"], "free")
        self.assertFalse(final_ent["has_vip_models"])

    def test_14_admin_confirm_by_order_reference_string(self):
        """Admin can confirm an order using the exact order reference string (e.g. GARI-U<uid>-<order_code>)."""
        order = gari_payment.create_bank_qr_order(self.user_a_id, "personal")
        order_ref = order["order_reference"]

        result = gari_payment.admin_confirm_payment(
            order_code=order_ref,
            admin_user_id=self.admin_id,
            bank_tx_reference="TX_BY_REF"
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["payment_status"], "paid")
        self.assertEqual(result["order_reference"], order_ref)


if __name__ == "__main__":
    unittest.main()

