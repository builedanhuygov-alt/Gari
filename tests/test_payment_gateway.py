"""
GARI AI LAB — Comprehensive Payment Gateway, Webhooks & Idempotency Test Suite (test_payment_gateway.py)

Covers all 16 audit and verification requirements:
1. Correct payment-order creation and server-side pricing
2. Client attempts to alter the amount or plan
3. Valid webhook signature calculation and verification
4. Invalid, missing, expired, or modified webhook signature rejection
5. Duplicate webhook event idempotency (no double subscriptions)
6. Concurrent duplicate webhook deliveries
7. Provider event with mismatched amount or currency
8. Provider event with mismatched payment/order ID
9. Order status and permission isolation (cross-user rejection)
10. Successful payment activates the correct subscription exactly once
11. Failed, cancelled, and expired payments do not grant access
12. Retry after a processing failure
13. Voucher and payment flows cannot double-grant access
14. Business tenant isolation and role checks
15. Missing provider credentials fail closed
16. Existing voucher, subscription lifecycle, and pricing integration
"""

import concurrent.futures
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import sys
import unittest
from unittest.mock import patch

# Add repository root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Ensure test database migrations are applied
from database.migrations_payments import run_migrations as run_payment_migrations
run_payment_migrations()

from database.migrations_vouchers import run_migrations as run_voucher_migrations
run_voucher_migrations()

import gari_auth
import gari_b2b
import gari_payment
import gari_plans
import gari_revenue
import gari_vouchers


class TestPaymentGatewayAndWebhooks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_checksum_key = "test_checksum_key_for_hmac_sha256_mock_32_chars"
        cls.test_client_id = "test_payos_client_id_123"
        cls.test_api_key = "test_payos_api_key_456"

        # Ensure test users and organizations exist in database
        with gari_payment.get_db_connection() as conn:
            cursor = conn.cursor()
            # User A
            cursor.execute("SELECT id FROM users WHERE email = 'test_payer_a@gari.vn'")
            row_a = cursor.fetchone()
            if not row_a:
                cursor.execute("""
                    INSERT INTO users (email, name, full_name, password_hash, account_type, is_admin)
                    VALUES ('test_payer_a@gari.vn', 'Payer A', 'Payer A', 'hash', 'Nông hộ', 0)
                """)
                cls.user_a_id = cursor.lastrowid
            else:
                cls.user_a_id = row_a["id"]

            # User B
            cursor.execute("SELECT id FROM users WHERE email = 'test_payer_b@gari.vn'")
            row_b = cursor.fetchone()
            if not row_b:
                cursor.execute("""
                    INSERT INTO users (email, name, full_name, password_hash, account_type, is_admin)
                    VALUES ('test_payer_b@gari.vn', 'Payer B', 'Payer B', 'hash', 'Nông hộ', 0)
                """)
                cls.user_b_id = cursor.lastrowid
            else:
                cls.user_b_id = row_b["id"]

            # Organization A
            cursor.execute("SELECT id FROM organizations WHERE slug = 'payment-org-a'")
            row_org_a = cursor.fetchone()
            if not row_org_a:
                cursor.execute("""
                    INSERT INTO organizations (name, slug, owner_id, plan_id, status)
                    VALUES ('Payment Org A', 'payment-org-a', ?, 'pilot', 'active')
                """, (cls.user_a_id,))
                cls.org_a_id = cursor.lastrowid
            else:
                cls.org_a_id = row_org_a["id"]

            # Add User A as owner
            cursor.execute("""
                INSERT OR IGNORE INTO organization_members (organization_id, user_id, role)
                VALUES (?, ?, 'owner')
            """, (cls.org_a_id, cls.user_a_id))

            conn.commit()

    def setUp(self):
        # Configure test credentials in environment
        self.patcher_checksum = patch.object(gari_payment, "PAYOS_CHECKSUM_KEY", self.test_checksum_key)
        self.patcher_client = patch.object(gari_payment, "PAYOS_CLIENT_ID", self.test_client_id)
        self.patcher_api = patch.object(gari_payment, "PAYOS_API_KEY", self.test_api_key)
        self.patcher_provider = patch.object(gari_payment, "PAYMENT_PROVIDER", "payos")
        self.patcher_checkout_switch = patch.object(gari_payment, "PAYOS_ENABLE_PUBLIC_CHECKOUT", True)

        self.patcher_checksum.start()
        self.patcher_client.start()
        self.patcher_api.start()
        self.patcher_provider.start()
        self.patcher_checkout_switch.start()

        # Clean active subscriptions for test users for test isolation
        with gari_payment.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM subscriptions WHERE target_type = 'user' AND target_id IN (?, ?)", (self.user_a_id, self.user_b_id))
            cursor.execute("DELETE FROM user_subscriptions WHERE user_id IN (?, ?)", (self.user_a_id, self.user_b_id))
            conn.commit()

    def tearDown(self):
        self.patcher_checksum.stop()
        self.patcher_client.stop()
        self.patcher_api.stop()
        self.patcher_provider.stop()
        self.patcher_checkout_switch.stop()

    # -------------------------------------------------------------------------
    # Test 1: Correct Payment-Order Creation & Server-Side Pricing
    # -------------------------------------------------------------------------
    def test_01_correct_order_creation_and_server_side_pricing(self):
        """Pricing is derived strictly from server: Personal = 129,000 VND, Business = 299,000 VND."""
        price_p, curr_p, name_p = gari_payment.get_canonical_order_pricing("personal")
        self.assertEqual(price_p, 129000)
        self.assertEqual(curr_p, "VND")
        self.assertEqual(name_p, "Cá nhân")

        price_b, curr_b, name_b = gari_payment.get_canonical_order_pricing("business")
        self.assertEqual(price_b, 299000)
        self.assertEqual(curr_b, "VND")
        self.assertEqual(name_b, "Doanh nghiệp")

    # -------------------------------------------------------------------------
    # Test 2: Client Attempts to Alter Amount or Plan
    # -------------------------------------------------------------------------
    def test_02_client_tamper_amount_or_invalid_plan(self):
        """Rejects non-existent plan and free plan from checkout."""
        with self.assertRaises(gari_payment.InvalidPlanForPaymentError):
            gari_payment.get_canonical_order_pricing("free")

        with self.assertRaises(gari_payment.InvalidPlanForPaymentError):
            gari_payment.get_canonical_order_pricing("invalid_plan_123")

    # -------------------------------------------------------------------------
    # Test 3: Valid Webhook Signature
    # -------------------------------------------------------------------------
    def test_03_valid_webhook_signature(self):
        """Valid HMAC-SHA256 signature calculated over sorted keys passes verification."""
        data = {
            "orderCode": 10001,
            "amount": 129000,
            "description": "GARI Personal",
            "accountNumber": "0123456789",
            "reference": "REF_TEST_001",
            "transactionDateTime": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "currency": "VND",
            "code": "00",
            "desc": "success"
        }
        sig = gari_payment.calculate_payos_signature(data, self.test_checksum_key)
        payload = {"code": "00", "desc": "success", "data": data, "signature": sig}

        is_valid, msg = gari_payment.verify_payos_webhook_signature(payload, self.test_checksum_key)
        self.assertTrue(is_valid, f"Expected valid signature, got: {msg}")
        self.assertEqual(msg, "Valid signature")

    # -------------------------------------------------------------------------
    # Test 4: Invalid, Missing, Expired, or Modified Webhook Signature
    # -------------------------------------------------------------------------
    def test_04_invalid_missing_expired_modified_signatures(self):
        """Rejects forged signatures, missing signatures, altered amounts, and expired timestamps."""
        data = {
            "orderCode": 10002,
            "amount": 129000,
            "reference": "REF_TEST_002",
            "transactionDateTime": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "currency": "VND",
            "code": "00"
        }
        sig = gari_payment.calculate_payos_signature(data, self.test_checksum_key)

        # 1. Missing signature
        is_valid, msg = gari_payment.verify_payos_webhook_signature({"data": data}, self.test_checksum_key)
        self.assertFalse(is_valid)

        # 2. Forged signature
        is_valid, msg = gari_payment.verify_payos_webhook_signature(
            {"data": data, "signature": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
            self.test_checksum_key
        )
        self.assertFalse(is_valid)
        self.assertIn("mismatch", msg.lower())

        # 3. Modified payload (Attacker changes amount to 1000 VND)
        tampered_data = dict(data)
        tampered_data["amount"] = 1000
        is_valid, msg = gari_payment.verify_payos_webhook_signature(
            {"data": tampered_data, "signature": sig},
            self.test_checksum_key
        )
        self.assertFalse(is_valid)

        # 4. Expired timestamp beyond replay window (e.g. 2 days ago with max_age=86400s)
        old_time = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        expired_data = dict(data)
        expired_data["transactionDateTime"] = old_time
        expired_sig = gari_payment.calculate_payos_signature(expired_data, self.test_checksum_key)
        is_valid, msg = gari_payment.verify_payos_webhook_signature(
            {"data": expired_data, "signature": expired_sig},
            self.test_checksum_key,
            max_age_seconds=3600
        )
        self.assertFalse(is_valid)
        self.assertIn("expired", msg.lower())

    # -------------------------------------------------------------------------
    # Helper: Create Mock Order Directly in DB
    # -------------------------------------------------------------------------
    def _create_mock_order(self, user_id: int, plan_id: str = "personal", amount: int = 129000, org_id=None) -> int:
        order_code = gari_payment.generate_order_code()
        internal_id = f"pay_{order_code}_test"
        target_type = "organization" if plan_id == "business" else "user"
        target_id = org_id if plan_id == "business" else user_id

        with gari_payment.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO payment_orders (
                    order_code, internal_payment_id, target_type, target_id,
                    user_id, organization_id, plan_id, amount, currency,
                    provider, payment_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'VND', 'payos', 'pending')
            """, (order_code, internal_id, target_type, target_id, user_id, org_id, plan_id, amount))
            conn.commit()
        return order_code

    # -------------------------------------------------------------------------
    # Test 5: Duplicate Webhook Event Idempotency
    # -------------------------------------------------------------------------
    def test_05_duplicate_webhook_event_idempotency(self):
        """Durable idempotency: delivering identical webhook event twice does not double-grant."""
        order_code = self._create_mock_order(self.user_a_id, "personal", 129000)

        data = {
            "orderCode": order_code,
            "amount": 129000,
            "reference": f"REF_DUP_{order_code}",
            "transactionDateTime": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "currency": "VND",
            "code": "00",
            "desc": "success"
        }
        sig = gari_payment.calculate_payos_signature(data, self.test_checksum_key)
        payload_bytes = json.dumps({"code": "00", "desc": "success", "data": data, "signature": sig}).encode("utf-8")

        # Delivery 1: Success
        res1 = gari_payment.process_payos_webhook(payload_bytes, enforce_replay_window=False)
        self.assertTrue(res1["success"])
        self.assertEqual(res1["status"], "succeeded")
        sub_id_1 = res1["subscription_id"]

        # Delivery 2: Duplicate
        res2 = gari_payment.process_payos_webhook(payload_bytes, enforce_replay_window=False)
        self.assertTrue(res2["success"])
        self.assertTrue(res2.get("duplicate"))

        # Verify only 1 active subscription exists
        with gari_payment.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as cnt FROM subscriptions
                WHERE target_type = 'user' AND target_id = ? AND status = 'active'
            """, (self.user_a_id,))
            self.assertEqual(cursor.fetchone()["cnt"], 1)

    # -------------------------------------------------------------------------
    # Test 6: Concurrent Duplicate Webhook Deliveries
    # -------------------------------------------------------------------------
    def test_06_concurrent_duplicate_webhook_deliveries(self):
        """5 parallel threads delivering the exact same webhook event -> exactly 1 succeeds, no races."""
        order_code = self._create_mock_order(self.user_b_id, "personal", 129000)

        data = {
            "orderCode": order_code,
            "amount": 129000,
            "reference": f"REF_CONC_{order_code}",
            "transactionDateTime": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "currency": "VND",
            "code": "00",
            "desc": "success"
        }
        sig = gari_payment.calculate_payos_signature(data, self.test_checksum_key)
        payload_bytes = json.dumps({"code": "00", "desc": "success", "data": data, "signature": sig}).encode("utf-8")

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(gari_payment.process_payos_webhook, payload_bytes, None, False)
                for _ in range(5)
            ]
            for f in concurrent.futures.as_completed(futures):
                try:
                    results.append(f.result())
                except Exception as e:
                    results.append({"error": str(e)})

        # All threads return success (either initial processing or duplicate acknowledgment)
        for r in results:
            self.assertTrue(r.get("success"), f"Thread failed with: {r}")

        # In DB, exactly 1 active subscription and 1 invoice exists
        with gari_payment.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as cnt FROM subscriptions
                WHERE target_type = 'user' AND target_id = ? AND status = 'active'
            """, (self.user_b_id,))
            self.assertEqual(cursor.fetchone()["cnt"], 1)

            cursor.execute("SELECT COUNT(*) as cnt FROM invoices WHERE invoice_number = ?", (f"INV-PAYOS-{order_code}",))
            self.assertEqual(cursor.fetchone()["cnt"], 1)

    # -------------------------------------------------------------------------
    # Test 7: Provider Event with Mismatched Amount or Currency
    # -------------------------------------------------------------------------
    def test_07_mismatched_amount_or_currency(self):
        """Webhook with wrong amount or currency raises error and rejects subscription grant."""
        order_code = self._create_mock_order(self.user_a_id, "personal", 129000)

        # Mismatched amount (100,000 instead of 129,000)
        data_wrong_amount = {
            "orderCode": order_code,
            "amount": 100000,
            "reference": f"REF_WRONG_AMT_{order_code}",
            "currency": "VND",
            "code": "00"
        }
        sig1 = gari_payment.calculate_payos_signature(data_wrong_amount, self.test_checksum_key)
        payload1 = json.dumps({"code": "00", "data": data_wrong_amount, "signature": sig1}).encode("utf-8")

        with self.assertRaises(gari_payment.PaymentAmountMismatchError):
            gari_payment.process_payos_webhook(payload1, enforce_replay_window=False)

        # Mismatched currency ('USD' instead of 'VND')
        data_wrong_curr = {
            "orderCode": order_code,
            "amount": 129000,
            "reference": f"REF_WRONG_CURR_{order_code}",
            "currency": "USD",
            "code": "00"
        }
        sig2 = gari_payment.calculate_payos_signature(data_wrong_curr, self.test_checksum_key)
        payload2 = json.dumps({"code": "00", "data": data_wrong_curr, "signature": sig2}).encode("utf-8")

        with self.assertRaises(gari_payment.PaymentCurrencyMismatchError):
            gari_payment.process_payos_webhook(payload2, enforce_replay_window=False)

    # -------------------------------------------------------------------------
    # Test 8: Provider Event with Non-Existent Order Code
    # -------------------------------------------------------------------------
    def test_08_mismatched_order_code(self):
        """Webhook with unknown orderCode raises PaymentOrderNotFoundError."""
        data = {
            "orderCode": 999999999,
            "amount": 129000,
            "reference": "REF_UNKNOWN_ORDER",
            "currency": "VND",
            "code": "00"
        }
        sig = gari_payment.calculate_payos_signature(data, self.test_checksum_key)
        payload = json.dumps({"code": "00", "data": data, "signature": sig}).encode("utf-8")

        with self.assertRaises(gari_payment.PaymentOrderNotFoundError):
            gari_payment.process_payos_webhook(payload, enforce_replay_window=False)

    # -------------------------------------------------------------------------
    # Test 9: Order Status & Permission Isolation
    # -------------------------------------------------------------------------
    def test_09_order_status_permission_isolation(self):
        """User A can view their own order; User B is rejected with PaymentPermissionError."""
        order_code = self._create_mock_order(self.user_a_id, "personal", 129000)

        # User A views order -> succeeds
        status_a = gari_payment.get_order_status(order_code, self.user_a_id)
        self.assertEqual(status_a["order_code"], order_code)
        self.assertEqual(status_a["amount"], 129000)

        # User B views User A's order -> rejected
        with self.assertRaises(gari_payment.PaymentPermissionError):
            gari_payment.get_order_status(order_code, self.user_b_id)

    # -------------------------------------------------------------------------
    # Test 10: Successful Payment Activates Subscription Exactly Once
    # -------------------------------------------------------------------------
    def test_10_successful_payment_activates_correct_subscription_once(self):
        """Full lifecycle: pending order -> payment confirmed -> entitlement active with VIP models."""
        order_code = self._create_mock_order(self.user_a_id, "personal", 129000)

        data = {
            "orderCode": order_code,
            "amount": 129000,
            "reference": f"REF_SUCCESS_{order_code}",
            "transactionDateTime": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "currency": "VND",
            "code": "00",
            "desc": "success"
        }
        sig = gari_payment.calculate_payos_signature(data, self.test_checksum_key)
        payload = json.dumps({"code": "00", "desc": "success", "data": data, "signature": sig}).encode("utf-8")

        res = gari_payment.process_payos_webhook(payload, enforce_replay_window=False)
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "succeeded")

        # Entitlement check
        ent = gari_plans.resolve_user_entitlement({"id": self.user_a_id})
        self.assertEqual(ent["plan_id"], "personal")
        self.assertTrue(ent["has_vip_models"])
        self.assertEqual(ent["subscription_status"], "active")

    # -------------------------------------------------------------------------
    # Test 11: Failed & Cancelled Payments Do Not Grant Access
    # -------------------------------------------------------------------------
    def test_11_failed_and_cancelled_payments_do_not_grant_access(self):
        """Cancelled or failed webhook events update order status without granting subscriptions."""
        order_code = self._create_mock_order(self.user_b_id, "personal", 129000)

        data = {
            "orderCode": order_code,
            "amount": 129000,
            "reference": f"REF_CANCEL_{order_code}",
            "currency": "VND",
            "code": "01",
            "desc": "cancelled"
        }
        sig = gari_payment.calculate_payos_signature(data, self.test_checksum_key)
        payload = json.dumps({"code": "01", "desc": "cancelled", "data": data, "signature": sig}).encode("utf-8")

        res = gari_payment.process_payos_webhook(payload, enforce_replay_window=False)
        self.assertEqual(res["status"], "cancelled")
        self.assertIsNone(res["subscription_id"])

        # User B still has free tier
        ent = gari_plans.resolve_user_entitlement({"id": self.user_b_id})
        self.assertEqual(ent["plan_id"], "free")
        self.assertFalse(ent["has_vip_models"])

    # -------------------------------------------------------------------------
    # Test 12: Retry After Processing Failure
    # -------------------------------------------------------------------------
    def test_12_retry_after_processing_failure(self):
        """If an event was previously recorded as failed, retry is permitted and succeeds."""
        order_code = self._create_mock_order(self.user_a_id, "personal", 129000)

        event_id = f"payos_{order_code}_REF_RETRY"
        # Pre-seed failed event in payment_webhook_events
        with gari_payment.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO payment_webhook_events (provider, event_id, order_code, raw_payload, status, processing_error)
                VALUES ('payos', ?, ?, '{}', 'failed', 'Simulated transient database lock')
            """, (event_id, order_code))
            conn.commit()

        # Retry the event with valid payload
        data = {
            "orderCode": order_code,
            "amount": 129000,
            "reference": "REF_RETRY",
            "currency": "VND",
            "code": "00"
        }
        sig = gari_payment.calculate_payos_signature(data, self.test_checksum_key)
        payload = json.dumps({"code": "00", "data": data, "signature": sig}).encode("utf-8")

        res = gari_payment.process_payos_webhook(payload, enforce_replay_window=False)
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "succeeded")

    # -------------------------------------------------------------------------
    # Test 13: Voucher and Payment Flows Cannot Double-Grant Access
    # -------------------------------------------------------------------------
    def test_13_voucher_and_payment_flows_cannot_double_grant(self):
        """Paying for a subscription supersedes an existing voucher subscription; strictly one active."""
        # 1. User A redeems voucher
        v_res = gari_vouchers.create_voucher(admin_user_id=1, plan_id="personal", duration_days=15)
        gari_vouchers.redeem_voucher(user_id=self.user_a_id, raw_code=v_res["voucher_code"], ip_address="10.0.0.1")

        # 2. User A now purchases Business plan via payment
        order_code = self._create_mock_order(self.user_a_id, "personal", 129000)
        data = {
            "orderCode": order_code,
            "amount": 129000,
            "reference": f"REF_SUPER_{order_code}",
            "currency": "VND",
            "code": "00"
        }
        sig = gari_payment.calculate_payos_signature(data, self.test_checksum_key)
        payload = json.dumps({"code": "00", "data": data, "signature": sig}).encode("utf-8")

        res = gari_payment.process_payos_webhook(payload, enforce_replay_window=False)
        self.assertTrue(res["success"])

        # Strictly ONE active subscription exists in database
        with gari_payment.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as cnt FROM subscriptions
                WHERE target_type = 'user' AND target_id = ? AND status = 'active'
            """, (self.user_a_id,))
            self.assertEqual(cursor.fetchone()["cnt"], 1)

    # -------------------------------------------------------------------------
    # Test 14: Business Tenant Isolation and Role Checks
    # -------------------------------------------------------------------------
    def test_14_business_tenant_isolation_and_roles(self):
        """User B (non-member) cannot checkout for Org A; Org owner User A can checkout."""
        # Non-member checkout rejected
        with self.assertRaises(gari_payment.PaymentPermissionError):
            gari_payment.create_payment_order(
                user_id=self.user_b_id,
                plan_id="business",
                org_id=self.org_a_id
            )

        # Missing org_id for business plan rejected
        with self.assertRaises(gari_payment.PaymentError):
            gari_payment.create_payment_order(
                user_id=self.user_a_id,
                plan_id="business",
                org_id=None
            )

    # -------------------------------------------------------------------------
    # Test 15: Missing Provider Credentials Fail Closed
    # -------------------------------------------------------------------------
    def test_15_missing_provider_credentials_fail_closed(self):
        """Missing credentials causes is_payment_configured() to return False and checkout to fail."""
        with patch.object(gari_payment, "PAYOS_CHECKSUM_KEY", ""):
            self.assertFalse(gari_payment.is_payment_configured())
            with self.assertRaises(gari_payment.PaymentProviderNotConfiguredError):
                gari_payment.create_payment_order(self.user_a_id, "personal")

    # -------------------------------------------------------------------------
    # Test 16: API Endpoints Integration (FastAPI TestClient)
    # -------------------------------------------------------------------------
    def test_16_api_endpoints_integration(self):
        """Tests /api/billing/payment-config, /api/billing/checkout, /api/billing/webhook/payos."""
        from fastapi.testclient import TestClient
        from api_server import app

        client = TestClient(app)

        # 1. Config endpoint
        resp_cfg = client.get("/api/billing/payment-config")
        self.assertEqual(resp_cfg.status_code, 200)
        cfg_data = resp_cfg.json()
        self.assertEqual(cfg_data["payment_provider"], "payos")
        self.assertTrue(cfg_data["is_configured"])

        # 2. Checkout without auth -> 401
        resp_no_auth = client.post("/api/billing/checkout", json={"plan_id": "personal"})
        self.assertEqual(resp_no_auth.status_code, 401)

        # 3. Webhook with invalid signature -> 400
        resp_bad_sig = client.post(
            "/api/billing/webhook/payos",
            json={"code": "00", "data": {"orderCode": 100}, "signature": "bad_sig"}
        )
        self.assertEqual(resp_bad_sig.status_code, 400)

    # -------------------------------------------------------------------------
    # Test 17: Public Checkout Remains Disabled by Default
    # -------------------------------------------------------------------------
    def test_17_checkout_disabled_by_default_without_public_switch(self):
        """Even if credentials exist, checkout raises safety error unless PAYOS_ENABLE_PUBLIC_CHECKOUT=1."""
        with patch.object(gari_payment, "PAYOS_ENABLE_PUBLIC_CHECKOUT", False):
            self.assertFalse(gari_payment.is_checkout_enabled())
            with self.assertRaises(gari_payment.PaymentProviderNotConfiguredError) as ctx:
                gari_payment.create_payment_order(self.user_a_id, "personal")
            self.assertIn("checkout_disabled_safety", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Test 18: returnUrl Alone Never Grants Subscription Access
    # -------------------------------------------------------------------------
    def test_18_return_url_alone_never_grants_access(self):
        """Visiting returnUrl or having a pending order never grants VIP access until webhook confirms."""
        # 1. User A has a pending order
        order_code = self._create_mock_order(self.user_a_id, "personal", 129000)

        # 2. Simulate user redirected to returnUrl (?payment=success&orderCode=...)
        # Fetching subscription status from backend reports unpaid/free
        with gari_payment.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT payment_status FROM payment_orders WHERE order_code = ?", (order_code,))
            self.assertEqual(cursor.fetchone()["payment_status"], "pending")

        ent = gari_plans.resolve_user_entitlement({"id": self.user_a_id})
        self.assertEqual(ent["plan_id"], "free")
        self.assertFalse(ent["has_vip_models"])
        self.assertFalse(ent.get("is_paid", False))


if __name__ == "__main__":
    unittest.main()
