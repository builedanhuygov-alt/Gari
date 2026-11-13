"""
GARI AI LAB — Centralized Billing Provider Adapter Architecture
(gari_billing_adapter.py)

Module 11: Subscription & Usage Management
Keeps all billing gateway integrations strictly behind an abstracted adapter layer:
- Bank QR Adapter (VietQR / NAPAS 24/7 with zero-trust manual/bank verification)
- PayOS Adapter (HMAC webhook signature validation)
- Mock Billing Adapter (For automated testing and simulation of payment lifecycles)

Zero-Trust Security Principle:
- Never claim payment success until verified and confirmed by the provider or bank reconciler.
- User reporting transfer only transitions status to 'pending_review' and NEVER grants subscription.
"""

from abc import ABC, abstractmethod
import hashlib
import hmac
import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import gari_entitlements

logger = logging.getLogger("gari_billing_adapter")
DB_PATH = Path(__file__).resolve().parent / "database" / "disease_detector.db"
_ADAPTER_LOCK = threading.RLock()


class BillingAdapterError(Exception):
    """Base exception for billing adapter errors."""


class PaymentVerificationError(BillingAdapterError):
    """Raised when webhook signature verification fails or payment is invalid."""


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
    conn.row_factory = sqlite3.Row
    return conn


class BillingAdapter(ABC):
    """Abstract base class for all billing providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g. 'bank_qr', 'payos', 'mock')."""
        pass

    @abstractmethod
    def create_checkout_order(
        self,
        user_id: int,
        plan_id: str,
        org_id: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Creates a pending payment order with the provider."""
        pass

    @abstractmethod
    def confirm_payment(
        self,
        order_code: int,
        provider_tx_id: Optional[str] = None,
        confirmed_by: Optional[int] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Confirms payment receipt and activates the subscription."""
        pass

    @abstractmethod
    def handle_failed_payment(
        self,
        order_code: int,
        reason: str
    ) -> Dict[str, Any]:
        """Marks order as failed or rejected and updates subscription state accordingly."""
        pass

    @abstractmethod
    def verify_webhook(
        self,
        payload: bytes,
        headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """Verifies incoming webhook signature and returns parsed event data."""
        pass


class BankQRBillingAdapter(BillingAdapter):
    """VietQR / NAPAS 24/7 interbank transfer billing adapter."""

    @property
    def provider_name(self) -> str:
        return "bank_qr"

    def create_checkout_order(
        self,
        user_id: int,
        plan_id: str,
        org_id: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        # Delegate to gari_payment
        import gari_payment
        return gari_payment.create_bank_qr_order(
            user_id=user_id,
            plan_id=plan_id,
            org_id=org_id,
            idempotency_key=idempotency_key
        )

    def report_transfer(self, order_code: int, user_id: int, notes: Optional[str] = None) -> Dict[str, Any]:
        """User reports they transferred money. Zero-Trust: only marks pending_review!"""
        import gari_payment
        return gari_payment.report_user_transfer(order_code=order_code, user_id=user_id, notes=notes)

    def confirm_payment(
        self,
        order_code: int,
        provider_tx_id: Optional[str] = None,
        confirmed_by: Optional[int] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Admin or reconciler confirms money has arrived in corporate bank account."""
        import gari_payment
        result = gari_payment.admin_confirm_payment(
            order_code=order_code,
            admin_id=confirmed_by or 1,
            bank_tx_reference=provider_tx_id or "BANK_CONFIRMED",
            admin_notes=notes or "Confirmed via BankQRBillingAdapter"
        )
        return result

    def handle_failed_payment(self, order_code: int, reason: str) -> Dict[str, Any]:
        import gari_payment
        return gari_payment.admin_reject_payment(
            order_code=order_code,
            admin_id=1,
            reason=reason
        )

    def verify_webhook(self, payload: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        # Bank QR typically uses polling/reconciler or custom bank webhook with secret
        secret = os.getenv("BANK_WEBHOOK_SECRET", "bank_dev_secret")
        signature = headers.get("X-Bank-Signature", "")
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise PaymentVerificationError("Chữ ký webhook ngân hàng không khớp.")
        return json.loads(payload.decode("utf-8"))


class PayOSBillingAdapter(BillingAdapter):
    """PayOS payment gateway integration adapter with HMAC signature verification."""

    @property
    def provider_name(self) -> str:
        return "payos"

    def create_checkout_order(
        self,
        user_id: int,
        plan_id: str,
        org_id: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        # Implementation creating order record in payment_orders
        plan = gari_entitlements.get_plan_definition(plan_id)
        amount = plan.get("price") or 0
        if amount <= 0:
            raise BillingAdapterError("Gói cước không yêu cầu thanh toán.")

        import random
        order_code = int(datetime.now().strftime("%y%m%d%H%M") + str(random.randint(10, 99)))
        target_type = "organization" if org_id else "user"
        target_id = org_id if org_id else user_id

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO payment_orders (
                    order_code, internal_payment_id, target_type, target_id, user_id, organization_id,
                    plan_id, amount, currency, provider, payment_status, idempotency_key, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'VND', 'payos', 'pending', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                order_code, f"PAYOS-{order_code}", target_type, target_id, user_id, org_id,
                plan_id, amount, idempotency_key
            ))
            conn.commit()

        return {
            "order_code": order_code,
            "internal_payment_id": f"PAYOS-{order_code}",
            "amount": amount,
            "currency": "VND",
            "provider": "payos",
            "checkout_url": f"https://pay.payos.vn/web/{order_code}",
            "payment_status": "pending"
        }

    def confirm_payment(
        self,
        order_code: int,
        provider_tx_id: Optional[str] = None,
        confirmed_by: Optional[int] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        with _ADAPTER_LOCK:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM payment_orders WHERE order_code = ?", (order_code,))
                order_row = cursor.fetchone()
                if not order_row:
                    raise BillingAdapterError(f"Không tìm thấy đơn hàng #{order_code}")

                order = dict(order_row)
                if order["payment_status"] == "paid":
                    return {"success": True, "already_paid": True, "order_code": order_code}

                # Update order
                cursor.execute("""
                    UPDATE payment_orders
                    SET payment_status = 'paid', paid_at = CURRENT_TIMESTAMP,
                        provider_tx_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE order_code = ?
                """, (provider_tx_id or "PAYOS_TX", order_code))
                conn.commit()

            # Activate subscription outside the previous connection
            target_type = order["target_type"]
            target_id = order["target_id"]
            plan_id = order["plan_id"]

            sub = gari_entitlements.assign_subscription(
                target_type=target_type,
                target_id=target_id,
                plan_id=plan_id,
                duration_days=30,
                notes=f"PayOS payment confirmed. Tx: {provider_tx_id}",
                is_paid=True,
                provider="payos"
            )

        return {"success": True, "order_code": order_code, "status": "paid", "subscription": sub}

    def handle_failed_payment(self, order_code: int, reason: str) -> Dict[str, Any]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE payment_orders
                SET payment_status = 'failed', failure_reason = ?, updated_at = CURRENT_TIMESTAMP
                WHERE order_code = ?
            """, (reason, order_code))
            conn.commit()
        return {"success": True, "order_code": order_code, "status": "failed", "reason": reason}

    def verify_webhook(self, payload: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        checksum_key = os.getenv("PAYOS_CHECKSUM_KEY", "payos_dev_checksum_key")
        signature = headers.get("x-payos-signature", "")
        expected = hmac.new(checksum_key.encode(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise PaymentVerificationError("Chữ ký PayOS không hợp lệ.")
        return json.loads(payload.decode("utf-8"))


class MockBillingAdapter(BillingAdapter):
    """Mock billing adapter for automated tests and edge-case simulation."""

    @property
    def provider_name(self) -> str:
        return "mock"

    def create_checkout_order(
        self,
        user_id: int,
        plan_id: str,
        org_id: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        plan = gari_entitlements.get_plan_definition(plan_id)
        amount = plan.get("price") or 0
        import random
        order_code = int(datetime.now().strftime("%y%m%d%H%M") + str(random.randint(100, 999)))
        target_type = "organization" if org_id else "user"
        target_id = org_id if org_id else user_id

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO payment_orders (
                    order_code, internal_payment_id, target_type, target_id, user_id, organization_id,
                    plan_id, amount, currency, provider, payment_status, idempotency_key, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'VND', 'mock', 'pending', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                order_code, f"MOCK-{order_code}", target_type, target_id, user_id, org_id,
                plan_id, amount, idempotency_key
            ))
            conn.commit()

        return {
            "order_code": order_code,
            "internal_payment_id": f"MOCK-{order_code}",
            "amount": amount,
            "currency": "VND",
            "provider": "mock",
            "checkout_url": f"https://mock-gateway.gari.vn/pay/{order_code}",
            "payment_status": "pending"
        }

    def confirm_payment(
        self,
        order_code: int,
        provider_tx_id: Optional[str] = None,
        confirmed_by: Optional[int] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        with _ADAPTER_LOCK:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM payment_orders WHERE order_code = ?", (order_code,))
                order_row = cursor.fetchone()
                if not order_row:
                    raise BillingAdapterError(f"Không tìm thấy đơn hàng #{order_code}")

                order = dict(order_row)
                cursor.execute("""
                    UPDATE payment_orders
                    SET payment_status = 'paid', paid_at = CURRENT_TIMESTAMP,
                        provider_tx_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE order_code = ?
                """, (provider_tx_id or "MOCK_TX_CONFIRMED", order_code))
                conn.commit()

            sub = gari_entitlements.assign_subscription(
                target_type=order["target_type"],
                target_id=order["target_id"],
                plan_id=order["plan_id"],
                duration_days=30,
                notes=f"Mock payment confirmed. Tx: {provider_tx_id}",
                is_paid=True,
                provider="mock"
            )

        return {"success": True, "order_code": order_code, "status": "paid", "subscription": sub}

    def handle_failed_payment(self, order_code: int, reason: str) -> Dict[str, Any]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE payment_orders
                SET payment_status = 'failed', failure_reason = ?, updated_at = CURRENT_TIMESTAMP
                WHERE order_code = ?
            """, (reason, order_code))
            conn.commit()
        return {"success": True, "order_code": order_code, "status": "failed", "reason": reason}

    def verify_webhook(self, payload: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        sig = headers.get("X-Mock-Signature", "")
        if sig != "valid_mock_signature":
            raise PaymentVerificationError("Mock webhook signature invalid.")
        return json.loads(payload.decode("utf-8"))


# Provider Registry
_ADAPTERS: Dict[str, BillingAdapter] = {
    "bank_qr": BankQRBillingAdapter(),
    "payos": PayOSBillingAdapter(),
    "mock": MockBillingAdapter()
}


def get_billing_adapter(provider_name: Optional[str] = None) -> BillingAdapter:
    """Returns the requested or default billing provider adapter."""
    p_name = (provider_name or os.getenv("BILLING_PROVIDER", "bank_qr")).strip().lower()
    if p_name in _ADAPTERS:
        return _ADAPTERS[p_name]
    return _ADAPTERS["bank_qr"]
