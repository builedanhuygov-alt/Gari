"""
GARI AI LAB — PayOS Synthetic Webhook Fixture & Verification Suite (test_payos_synthetic_webhooks.py)

Tests PayOS production-readiness using synthetic JSON fixtures strictly in-memory
without making any live external API calls or initiating real payments.

Covers:
1. Valid PayOS webhook synthetic fixture -> Successful processing & subscription activation
2. Missing webhook signature -> Rejected (HTTP 400 / WebhookSignatureVerificationError)
3. Forged or invalid signature -> Rejected
4. Modified payload (signature mismatch on tampered amount) -> Rejected
5. Duplicate event delivery -> Acknowledged as duplicate without double grant
6. Wrong order code -> Rejected with PaymentOrderNotFoundError
7. Wrong amount -> Rejected with PaymentAmountMismatchError
8. Wrong currency -> Rejected with PaymentCurrencyMismatchError
9. Retry after transient database failure -> Successfully recovered
10. returnUrl redirection alone -> Never grants VIP entitlement
11. Public checkout safety switch -> Disabled by default (PAYOS_ENABLE_PUBLIC_CHECKOUT=0)
"""

import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
import unittest
from unittest.mock import patch

# Add repository root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import gari_payment
import gari_plans

# Test Secret Key (Mocked for test fixtures, never live credentials)
MOCK_CHECKSUM_KEY = "synthetic_checksum_key_64_hex_chars_mock_test_2026_payos_gari"


class TestPayOSSyntheticWebhooks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create test user
        with gari_payment.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email = 'synthetic_test_user@gari.vn'")
            row = cursor.fetchone()
            if not row:
                cursor.execute("""
                    INSERT INTO users (email, name, full_name, password_hash, account_type, is_admin)
                    VALUES ('synthetic_test_user@gari.vn', 'Synthetic Tester', 'Synthetic Tester', 'hash', 'Nông hộ', 0)
                """)
                cls.test_user_id = cursor.lastrowid
            else:
                cls.test_user_id = row["id"]
            conn.commit()

    def setUp(self):
        # Patch checksum key so tests run securely in isolated environment
        self.patcher_checksum = patch.object(gari_payment, "PAYOS_CHECKSUM_KEY", MOCK_CHECKSUM_KEY)
        self.patcher_provider = patch.object(gari_payment, "PAYMENT_PROVIDER", "payos")
        self.patcher_checksum.start()
        self.patcher_provider.start()

        # Clean prior test subscriptions for test user
        with gari_payment.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM subscriptions WHERE target_type = 'user' AND target_id = ?", (self.test_user_id,))
            cursor.execute("DELETE FROM user_subscriptions WHERE user_id = ?", (self.test_user_id,))
            conn.commit()

    def tearDown(self):
        self.patcher_checksum.stop()
        self.patcher_provider.stop()

    def _create_pending_order(self, plan_id="personal", amount=129000) -> int:
        order_code = gari_payment.generate_order_code()
        internal_id = f"pay_{order_code}_synthetic"
        with gari_payment.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO payment_orders (
                    order_code, internal_payment_id, target_type, target_id,
                    user_id, plan_id, amount, currency, provider, payment_status
                ) VALUES (?, ?, 'user', ?, ?, ?, ?, 'VND', 'payos', 'pending')
            """, (order_code, internal_id, self.test_user_id, self.test_user_id, plan_id, amount))
            conn.commit()
        return order_code

    def _build_synthetic_fixture(self, order_code: int, amount: int = 129000, currency: str = "VND", reference: str = None) -> dict:
        """Constructs an authentic PayOS webhook payload structure."""
        ref = reference or f"FT26{order_code}MOCK"
        data = {
            "orderCode": order_code,
            "amount": amount,
            "description": "GARI Personal",
            "accountNumber": "0987654321",
            "reference": ref,
            "transactionDateTime": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "currency": currency,
            "paymentLinkId": f"pl_{order_code}_mock",
            "code": "00",
            "desc": "success",
            "counterAccountBankId": "970415",
            "counterAccountBankName": "VietinBank",
            "counterAccountName": "NGUYEN VAN A",
            "counterAccountNumber": "101867890123",
            "virtualAccountName": "GARI AI LAB",
            "virtualAccountNumber": "9999888877"
        }
        signature = gari_payment.calculate_payos_signature(data, MOCK_CHECKSUM_KEY)
        return {
            "code": "00",
            "desc": "success",
            "data": data,
            "signature": signature
        }

    # 1. Valid signature synthetic fixture
    def test_01_valid_synthetic_webhook_fixture(self):
        """Authentic synthetic PayOS webhook fixture successfully confirms payment and grants VIP entitlement."""
        order_code = self._create_pending_order("personal", 129000)
        fixture = self._build_synthetic_fixture(order_code, 129000, "VND")
        raw_body = json.dumps(fixture).encode("utf-8")

        result = gari_payment.process_payos_webhook(raw_body, enforce_replay_window=False)
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "succeeded")
        self.assertIsNotNone(result["subscription_id"])

        # Confirm entitlement
        ent = gari_plans.resolve_user_entitlement({"id": self.test_user_id})
        self.assertEqual(ent["plan_id"], "personal")
        self.assertTrue(ent["has_vip_models"])
        self.assertEqual(ent["subscription_status"], "active")

    # 2. Missing or invalid signature
    def test_02_missing_and_invalid_signature(self):
        """Rejects webhook payload when signature is missing or altered."""
        order_code = self._create_pending_order("personal", 129000)
        fixture = self._build_synthetic_fixture(order_code, 129000, "VND")

        # Missing signature
        bad_fixture_1 = copy.deepcopy(fixture)
        bad_fixture_1.pop("signature")
        with self.assertRaises(gari_payment.WebhookSignatureVerificationError):
            gari_payment.process_payos_webhook(json.dumps(bad_fixture_1).encode("utf-8"), enforce_replay_window=False)

        # Invalid/forged signature
        bad_fixture_2 = copy.deepcopy(fixture)
        bad_fixture_2["signature"] = "deadbeef1234567890deadbeef1234567890deadbeef1234567890deadbeef1234"
        with self.assertRaises(gari_payment.WebhookSignatureVerificationError):
            gari_payment.process_payos_webhook(json.dumps(bad_fixture_2).encode("utf-8"), enforce_replay_window=False)

    # 3. Modified payload (tampered after signing)
    def test_03_modified_payload_rejected(self):
        """Attacker modifies amount in body after signature was generated -> rejected."""
        order_code = self._create_pending_order("personal", 129000)
        fixture = self._build_synthetic_fixture(order_code, 129000, "VND")

        # Attacker tampers data.amount to 1,000 VND
        tampered = copy.deepcopy(fixture)
        tampered["data"]["amount"] = 1000

        with self.assertRaises(gari_payment.WebhookSignatureVerificationError):
            gari_payment.process_payos_webhook(json.dumps(tampered).encode("utf-8"), enforce_replay_window=False)

    # 4. Duplicate event delivery
    def test_04_duplicate_event_safe_acknowledgment(self):
        """Delivering the exact same synthetic webhook twice acknowledges duplicate without re-granting."""
        order_code = self._create_pending_order("personal", 129000)
        fixture = self._build_synthetic_fixture(order_code, 129000, "VND")
        raw_body = json.dumps(fixture).encode("utf-8")

        # Delivery 1
        res1 = gari_payment.process_payos_webhook(raw_body, enforce_replay_window=False)
        self.assertTrue(res1["success"])
        self.assertEqual(res1["status"], "succeeded")

        # Delivery 2 (Duplicate)
        res2 = gari_payment.process_payos_webhook(raw_body, enforce_replay_window=False)
        self.assertTrue(res2["success"])
        self.assertTrue(res2.get("duplicate"))
        self.assertIn("already processed", res2.get("message", "").lower())

        # Subscriptions table has strictly 1 active subscription
        with gari_payment.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM subscriptions WHERE target_type = 'user' AND target_id = ? AND status = 'active'", (self.test_user_id,))
            self.assertEqual(cursor.fetchone()["cnt"], 1)

    # 5. Wrong order code
    def test_05_wrong_order_code_rejected(self):
        """Webhook with an orderCode that does not exist raises PaymentOrderNotFoundError."""
        fixture = self._build_synthetic_fixture(order_code=888888888, amount=129000, currency="VND")
        raw_body = json.dumps(fixture).encode("utf-8")

        with self.assertRaises(gari_payment.PaymentOrderNotFoundError):
            gari_payment.process_payos_webhook(raw_body, enforce_replay_window=False)

    # 6. Wrong amount
    def test_06_wrong_amount_rejected(self):
        """Webhook with valid signature but amount mismatching internal order is rejected."""
        order_code = self._create_pending_order("personal", 129000)
        # Webhook payload has 100,000 VND instead of 129,000 VND
        fixture = self._build_synthetic_fixture(order_code=order_code, amount=100000, currency="VND")
        raw_body = json.dumps(fixture).encode("utf-8")

        with self.assertRaises(gari_payment.PaymentAmountMismatchError):
            gari_payment.process_payos_webhook(raw_body, enforce_replay_window=False)

    # 7. Wrong currency
    def test_07_wrong_currency_rejected(self):
        """Webhook claiming 'USD' instead of canonical 'VND' is rejected."""
        order_code = self._create_pending_order("personal", 129000)
        fixture = self._build_synthetic_fixture(order_code=order_code, amount=129000, currency="USD")
        raw_body = json.dumps(fixture).encode("utf-8")

        with self.assertRaises(gari_payment.PaymentCurrencyMismatchError):
            gari_payment.process_payos_webhook(raw_body, enforce_replay_window=False)

    # 8. Retry after processing failure
    def test_08_retry_after_transient_failure(self):
        """Transient failed event can be retried and successfully processed."""
        order_code = self._create_pending_order("personal", 129000)
        fixture = self._build_synthetic_fixture(order_code=order_code, amount=129000, reference="REF_RETRY_SYN")
        raw_body = json.dumps(fixture).encode("utf-8")

        event_id = f"payos_{order_code}_REF_RETRY_SYN"
        # Seed pre-existing failed event in database
        with gari_payment.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO payment_webhook_events (provider, event_id, order_code, raw_payload, status, processing_error)
                VALUES ('payos', ?, ?, '{}', 'failed', 'Temporary connection timeout')
            """, (event_id, order_code))
            conn.commit()

        # Retry processing
        res = gari_payment.process_payos_webhook(raw_body, enforce_replay_window=False)
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "succeeded")

    # 9. returnUrl alone never grants subscription access
    def test_09_return_url_alone_never_grants_access(self):
        """User visiting returnUrl without a verified webhook event remains on unpaid free tier."""
        order_code = self._create_pending_order("personal", 129000)

        # Confirm order is still pending in database
        status_info = gari_payment.get_order_status(order_code, self.test_user_id)
        self.assertEqual(status_info["payment_status"], "pending")

        # Entitlement check: User MUST still be free
        ent = gari_plans.resolve_user_entitlement({"id": self.test_user_id})
        self.assertEqual(ent["plan_id"], "free")
        self.assertFalse(ent["has_vip_models"])
        self.assertFalse(ent.get("is_paid", False))

    # 10. Public checkout disabled by default
    def test_10_public_checkout_safety_switch(self):
        """Public checkout cannot create live orders unless PAYOS_ENABLE_PUBLIC_CHECKOUT=1."""
        # A) Credentials missing -> payment_provider_not_configured
        with self.assertRaises(gari_payment.PaymentProviderNotConfiguredError) as ctx_missing:
            gari_payment.create_payment_order(self.test_user_id, "personal")
        self.assertIn("payment_provider_not_configured", str(ctx_missing.exception))

        # B) Credentials present, but PAYOS_ENABLE_PUBLIC_CHECKOUT is False -> checkout_disabled_safety
        with patch.object(gari_payment, "PAYOS_CLIENT_ID", "mock_client_id_123"), \
             patch.object(gari_payment, "PAYOS_API_KEY", "mock_api_key_456"), \
             patch.object(gari_payment, "PAYOS_ENABLE_PUBLIC_CHECKOUT", False):
            self.assertTrue(gari_payment.is_payment_configured())
            self.assertFalse(gari_payment.is_checkout_enabled())
            with self.assertRaises(gari_payment.PaymentProviderNotConfiguredError) as ctx_disabled:
                gari_payment.create_payment_order(self.test_user_id, "personal")
            self.assertIn("checkout_disabled_safety", str(ctx_disabled.exception))


if __name__ == "__main__":
    unittest.main()
