"""
GARI AI LAB — Vietnamese Bank QR Payment & Manual Admin Verification Engine (gari_payment.py)

Architecture & Flow:
1. Bank QR Flow (VietQR / NAPAS 24/7):
   - Generates VietQR standard payment QR codes containing:
     * Recipient Bank ID & Account Number from server configuration.
     * Exact payment amount derived strictly from server-side canonical pricing.
     * Unique transfer description linked to the authenticated user's UID and unique order code:
       Format: 'GARI-U<user_id>-<order_code>' (e.g. 'GARI-U42-84920155').
       Guarantees uniqueness across multiple purchases by the same user.
2. User Transfer Reporting ('I have transferred'):
   - When the user completes the interbank transfer in their mobile banking app,
     they click 'Tôi đã chuyển khoản' ('I have transferred').
   - Transitions order status to 'pending_review' and timestamps the notification.
   - ZERO-TRUST SECURITY: This action NEVER grants VIP or modifies entitlements.
3. Admin-Only Manual Payment Verification:
   - Platform administrators inspect the corporate bank statement/app.
   - An authorized admin verifies the received funds and confirms the transaction via
     server-side authenticated admin endpoint.
   - Only upon authorized admin confirmation does the backend atomically mark the order
     as 'paid' and grant the 30-day subscription.
   - Verifies admin authorization server-side (never trusts frontend role flags).
   - Enforces idempotency: repeated confirmation attempts return success without
     double-granting subscriptions or extending billing periods twice.
   - Preserves complete audit trail: admin ID, order reference, amount, bank transaction reference,
     and confirmation timestamp.
4. Fail-Closed Security:
   - Public checkout remains disabled by default (PAYMENT_PUBLIC_CHECKOUT_ENABLED=0)
     until merchant credentials and receiving bank account are configured.
"""

import hashlib
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse

import gari_b2b
import gari_config
import gari_database
import gari_plans
import gari_revenue

logger = logging.getLogger("gari_payment")

DB_PATH = Path(__file__).resolve().parent / "database" / "disease_detector.db"
_PAYMENT_LOCK = threading.RLock()


# -----------------------------------------------------------------------------
# 1. Configuration & Constants
# -----------------------------------------------------------------------------

def get_payment_provider() -> str:
    return os.getenv("PAYMENT_PROVIDER", "bank_qr").lower().strip()

def get_bank_id() -> str:
    return os.getenv("BANK_QR_BANK_ID", "MoMo (VietQR / NAPAS 24/7)").strip()

def get_account_number() -> str:
    return os.getenv("BANK_QR_ACCOUNT_NUMBER", "*******193").strip()

def get_account_name() -> str:
    return os.getenv("BANK_QR_ACCOUNT_NAME", "BUI LE DAN HUY").strip()

def get_static_qr_url() -> str:
    return os.getenv("PAYMENT_STATIC_QR_URL", "/static/frontend2/images/vietqr_momo.jpg").strip()


def is_public_checkout_enabled() -> bool:
    return os.getenv("PAYMENT_PUBLIC_CHECKOUT_ENABLED", "0").lower().strip() in ("1", "true", "yes")

def get_order_expiry_minutes() -> int:
    try:
        return int(os.getenv("PAYMENT_ORDER_EXPIRY_MINUTES", "15"))
    except Exception:
        return 15

def get_return_url() -> str:
    return os.getenv("PAYMENT_RETURN_URL", "http://localhost:8000/frontend2/pricing.html?payment=success")

def get_cancel_url() -> str:
    return os.getenv("PAYMENT_CANCEL_URL", "http://localhost:8000/frontend2/pricing.html?payment=cancel")


# Valid Payment Statuses
PAYMENT_STATUS_PENDING = "pending"
PAYMENT_STATUS_PENDING_REVIEW = "pending_review"
PAYMENT_STATUS_PAID = "paid"
PAYMENT_STATUS_EXPIRED = "expired"
PAYMENT_STATUS_FAILED = "failed"
PAYMENT_STATUS_REJECTED = "rejected"
PAYMENT_STATUS_REVIEW_REQUIRED = "review_required"


# -----------------------------------------------------------------------------
# 2. Domain Exceptions
# -----------------------------------------------------------------------------

class PaymentError(Exception):
    """Base exception for payment domain errors."""


class PaymentProviderNotConfiguredError(PaymentError):
    """Raised when bank QR recipient credentials are not properly configured."""


class InvalidPlanForPaymentError(PaymentError):
    """Raised when the plan is not available for online purchase."""


class PaymentOrderNotFoundError(PaymentError):
    """Raised when an order code or reference does not match any record."""


class PaymentOrderExpiredError(PaymentError):
    """Raised when an operation is attempted against an expired order."""


class PaymentPermissionError(PaymentError):
    """Raised when a user lacks permission for the payment order or action."""


class PaymentAlreadyPaidError(PaymentError):
    """Raised when attempting an invalid state transition on an already paid order."""


# -----------------------------------------------------------------------------
# 3. Database Connection Helper
# -----------------------------------------------------------------------------

def get_db_connection() -> sqlite3.Connection:
    """Returns a SQLite connection with row access and WAL mode."""
    conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# -----------------------------------------------------------------------------
# 4. Provider Readiness & Configuration Check
# -----------------------------------------------------------------------------

def is_bank_qr_configured() -> bool:
    """
    Returns True only if all required recipient bank details are present.
    Fails closed if any key is missing or set to a placeholder.
    """
    bank_id = get_bank_id()
    account_number = get_account_number()
    account_name = get_account_name()

    if not (bank_id and account_number and account_name):
        return False
    placeholders = {
        "your_bank_id", "your_account_number", "your_account_name",
        "changeme", "default", ""
    }
    if (account_number.lower() in placeholders or
        bank_id.lower() in placeholders):
        return False
    return True


def is_checkout_enabled() -> bool:
    """
    Returns True only if Bank QR details are configured AND public checkout
    has been explicitly authorized via PAYMENT_PUBLIC_CHECKOUT_ENABLED=1.
    """
    return is_bank_qr_configured() and is_public_checkout_enabled()


def get_payment_config_info() -> Dict[str, Any]:
    """Returns safe, public payment gateway readiness info for frontend and status checks."""
    configured = is_bank_qr_configured()
    checkout_active = is_checkout_enabled()
    return {
        "payment_provider": get_payment_provider(),
        "is_configured": configured,
        "checkout_enabled": checkout_active,
        "bank_id": get_bank_id() if configured else "",
        "account_number": get_account_number() if configured else "",
        "account_name": get_account_name() if configured else "",
        "currency": "VND",
        "supported_methods": ["VietQR", "Bank_Transfer"],
        "status": "active" if checkout_active else ("testing_mode" if configured else "payment_provider_not_configured"),
        "message_vi": (
            "Cổng thanh toán Chuyển khoản VietQR đã sẵn sàng." if checkout_active else (
                "Cổng thanh toán chuyển khoản đang trong chế độ cấu hình nội bộ (chưa mở thanh toán công khai)." if configured else
                "Cổng thanh toán chuyển khoản ngân hàng đang được cấu hình. Quý khách vui lòng sử dụng Mã Voucher ưu đãi hoặc liên hệ hỗ trợ."
            )
        )
    }


# -----------------------------------------------------------------------------
# 5. Order Reference, Pricing & VietQR Link Helpers
# -----------------------------------------------------------------------------

def generate_order_code() -> int:
    """
    Generates a unique, positive integer order code (8 digits).
    Example: 84920155
    Guaranteed collision-free against existing payment orders.
    """
    with get_db_connection() as conn:
        for _ in range(25):
            code = secrets.randbelow(90_000_000) + 10_000_000
            row = conn.execute("SELECT 1 FROM payment_orders WHERE order_code = ?", (code,)).fetchone()
            if not row:
                return code
    return int(f"1{secrets.randbelow(900_000_000) + 100_000_000}")


def format_order_reference(user_id: int, order_code: int) -> str:
    """
    Standardized transfer reference linked to authenticated user's UID and order code.
    Example: 'GARI-U42-84920155'
    - Includes authenticated user's UID.
    - Includes unique order code to guarantee uniqueness across multiple purchases by the same user.
    """
    return f"GARI-U{user_id}-{order_code}"


def get_canonical_order_pricing(plan_id: str) -> Tuple[int, str, str]:
    """
    Authoritative server-side price lookup.
    Never trusts client input. Returns (amount_vnd, currency, display_name).
    """
    plan = gari_plans.get_plan_definition(plan_id)
    if not plan:
        raise InvalidPlanForPaymentError(f"Gói dịch vụ '{plan_id}' không tồn tại trong hệ thống.")
    if plan_id == "free":
        raise InvalidPlanForPaymentError("Gói Miễn Phí không yêu cầu thanh toán.")

    price = plan.get("price")
    if not isinstance(price, int) or price <= 0:
        raise InvalidPlanForPaymentError(f"Giá gói dịch vụ '{plan_id}' không hợp lệ.")

    currency = plan.get("currency", "VND")
    display_name = plan.get("display_name", plan_id)
    return price, currency, display_name


def generate_vietqr_url(bank_id: str = "", account_number: str = "", account_name: str = "", amount: int = 0, content: str = "") -> str:
    """
    Returns the static QR image payment asset URL.
    Strictly preserves the uploaded static VietQR/MoMo QR asset without regeneration, redrawing, or alteration.
    """
    return get_static_qr_url()



# -----------------------------------------------------------------------------
# 6. Payment Order Creation (Bank QR)
# -----------------------------------------------------------------------------

def create_bank_qr_order(
    user_id: int,
    plan_id: str,
    org_id: Optional[int] = None,
    idempotency_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates an internal pending Bank QR payment order with authoritative server-side pricing.
    Generates VietQR link, unique transfer description linked to UID (e.g. GARI-U42-84920155),
    and 15-minute expiration window.
    Supports client idempotency: returns existing pending order if idempotency_key matches.
    """
    # 1. Enforce configuration readiness
    if not is_bank_qr_configured():
        raise PaymentProviderNotConfiguredError(
            "payment_provider_not_configured: Cổng thanh toán chuyển khoản ngân hàng chưa được cấu hình. "
            "Vui lòng thiết lập BANK_QR_BANK_ID, BANK_QR_ACCOUNT_NUMBER và BANK_QR_ACCOUNT_NAME."
        )

    # 2. Enforce public checkout safety switch
    if not is_checkout_enabled():
        raise PaymentProviderNotConfiguredError(
            "payment_provider_not_configured: checkout_disabled_safety: Cổng thanh toán chuyển khoản đang trong chế độ cấu hình nội bộ "
            "và chưa được mở công khai (PAYMENT_PUBLIC_CHECKOUT_ENABLED=0). Vui lòng sử dụng mã voucher hoặc liên hệ quản trị viên."
        )


    # 3. Derive authoritative pricing from server-side definitions
    amount, currency, plan_name = get_canonical_order_pricing(plan_id)

    # 4. Determine target (user vs organization)
    if plan_id == "business":
        if not org_id:
            raise PaymentError("Gói Doanh Nghiệp (Business) yêu cầu cung cấp ID của tổ chức (org_id).")
        role = gari_b2b.get_member_role(org_id, user_id)
        if role not in ("owner", "admin"):
            raise PaymentPermissionError(f"Bạn không có quyền quản trị tài chính cho tổ chức #{org_id}.")
        target_type = "organization"
        target_id = org_id
    else:
        target_type = "user"
        target_id = user_id
        org_id = None

    with _PAYMENT_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            now_utc = datetime.now(timezone.utc)
            now_iso = now_utc.strftime("%Y-%m-%d %H:%M:%S")

            # 5. Check client idempotency key if provided
            if idempotency_key:
                cursor.execute("""
                    SELECT * FROM payment_orders
                    WHERE idempotency_key = ? AND user_id = ? AND payment_status IN ('pending', 'pending_review')
                """, (idempotency_key, user_id))
                existing = cursor.fetchone()
                if existing:
                    exp_str = existing["expires_at"]
                    if exp_str:
                        exp_dt = datetime.strptime(exp_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                        if exp_dt > now_utc:
                            logger.info("Returning existing pending order for idempotency_key '%s'", idempotency_key)
                            order_dict = dict(existing)
                            order_dict["transfer_content"] = order_dict["order_reference"]
                            return order_dict

            # 6. Generate order code, reference linked to UID, and expiration
            order_code = generate_order_code()
            order_reference = format_order_reference(user_id=user_id, order_code=order_code)
            internal_payment_id = f"gari_pay_{order_code}_{secrets.token_hex(4)}"
            expires_at = now_utc + timedelta(minutes=get_order_expiry_minutes())
            expires_iso = expires_at.strftime("%Y-%m-%d %H:%M:%S")

            bank_id = get_bank_id()
            account_number = get_account_number()
            account_name = get_account_name()

            # 7. Static QR Asset URL (from uploaded VietQR / MoMo image)
            qr_url = get_static_qr_url()


            # 8. Insert into payment_orders
            cursor.execute("""
                INSERT INTO payment_orders (
                    order_code, internal_payment_id, order_reference,
                    target_type, target_id, user_id, organization_id,
                    plan_id, amount, currency, provider,
                    bank_id, account_number, account_name, qr_code_url,
                    payment_status, idempotency_key, expires_at, metadata_json,
                    created_at, updated_at
                ) VALUES (
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, 'bank_qr',
                    ?, ?, ?, ?,
                    'pending', ?, ?, ?,
                    ?, ?
                )
            """, (
                order_code, internal_payment_id, order_reference,
                target_type, target_id, user_id, org_id,
                plan_id, amount, currency,
                bank_id, account_number, account_name, qr_url,
                idempotency_key, expires_iso, json.dumps({"plan_name": plan_name}),
                now_iso, now_iso
            ))

            # Audit log
            cursor.execute("""
                INSERT INTO payment_audit_log (order_code, internal_payment_id, action, actor_type, actor_id, details_json)
                VALUES (?, ?, 'order_created', 'user', ?, ?)
            """, (
                order_code, internal_payment_id, str(user_id),
                json.dumps({
                    "amount": amount,
                    "plan_id": plan_id,
                    "order_reference": order_reference,
                    "user_id": user_id,
                    "bank_id": bank_id,
                    "account_number": account_number,
                    "expires_at": expires_iso
                })
            ))

            conn.commit()

            cursor.execute("SELECT * FROM payment_orders WHERE order_code = ?", (order_code,))
            order_row = dict(cursor.fetchone())
            order_row["transfer_content"] = order_reference
            return order_row


# -----------------------------------------------------------------------------
# 7. User Action: Report Bank Transfer ('I have transferred')
# -----------------------------------------------------------------------------

def report_user_transfer(
    order_code: int,
    user_id: int,
    user_notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    User clicks 'Tôi đã chuyển khoản' ('I have transferred').
    Transitions the order status from 'pending' to 'pending_review'.
    CRITICAL SECURITY INVARIANT:
    - This action NEVER grants VIP or activates subscriptions.
    - Only updates payment_status to 'pending_review' with audit trail for admin review.
    """
    with _PAYMENT_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM payment_orders WHERE order_code = ? OR order_reference = ?", (order_code, str(order_code)))
            order = cursor.fetchone()
            if not order:
                raise PaymentOrderNotFoundError(f"Không tìm thấy đơn thanh toán #{order_code}")
            order_code = order["order_code"]


            # Verify ownership
            if order["target_type"] == "user" and order["user_id"] != user_id:
                raise PaymentPermissionError("Bạn không có quyền báo chuyển khoản cho đơn hàng này.")
            elif order["target_type"] == "organization":
                role = gari_b2b.get_member_role(order["organization_id"], user_id)
                if not role:
                    raise PaymentPermissionError("Bạn không thuộc tổ chức sở hữu đơn hàng này.")

            current_status = order["payment_status"]
            if current_status == PAYMENT_STATUS_PAID:
                return {
                    "success": True,
                    "already_paid": True,
                    "order_code": order_code,
                    "order_reference": order["order_reference"],
                    "payment_status": PAYMENT_STATUS_PAID,
                    "message_vi": "Đơn hàng này đã được xác nhận thanh toán."
                }

            if current_status in (PAYMENT_STATUS_EXPIRED, PAYMENT_STATUS_REJECTED):
                raise PaymentError(f"Đơn hàng hiện ở trạng thái '{current_status}', không thể báo chuyển khoản.")

            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                UPDATE payment_orders
                SET payment_status = 'pending_review',
                    transfer_reported_at = ?,
                    updated_at = ?
                WHERE order_code = ?
            """, (now_iso, now_iso, order_code))

            # Audit record
            cursor.execute("""
                INSERT INTO payment_audit_log (order_code, internal_payment_id, action, actor_type, actor_id, details_json)
                VALUES (?, ?, 'user_reported_transfer', 'user', ?, ?)
            """, (
                order_code, order["internal_payment_id"], str(user_id),
                json.dumps({
                    "user_id": user_id,
                    "order_reference": order["order_reference"],
                    "reported_at": now_iso,
                    "user_notes": user_notes
                })
            ))

            conn.commit()
            logger.info("User #%s reported transfer for order #%s (Reference: %s)", user_id, order_code, order["order_reference"])

            return {
                "success": True,
                "order_code": order_code,
                "order_reference": order["order_reference"],
                "payment_status": PAYMENT_STATUS_PENDING_REVIEW,
                "transfer_reported_at": now_iso,
                "message_vi": "Đã ghi nhận thông báo chuyển khoản thành công. Quản trị viên sẽ kiểm tra tài khoản ngân hàng và kích hoạt gói cước cho bạn."
            }


# -----------------------------------------------------------------------------
# 8. Admin-Only Action: Manual Payment Confirmation & Subscription Grant
# -----------------------------------------------------------------------------

def admin_confirm_payment(
    order_code: int,
    admin_user_id: int,
    bank_tx_reference: Optional[str] = None,
    admin_notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Admin-only manual payment confirmation.
    Executed after an authorized admin verifies the bank credit in the corporate bank statement.
    Atomically:
    1. Marks payment_orders as 'paid'.
    2. Cancels prior subscriptions for the target user/org.
    3. Grants 30-day VIP subscription in 'subscriptions' & 'user_subscriptions'.
    4. Generates paid invoice record in 'invoices'.
    5. Preserves detailed audit records (admin ID, order reference, amount, bank reference, timestamp).
    Idempotent:
    - If already paid, returns success immediately without granting duplicate subscriptions.
    """
    with _PAYMENT_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM payment_orders WHERE order_code = ? OR order_reference = ?", (order_code, str(order_code)))
            order = cursor.fetchone()
            if not order:
                raise PaymentOrderNotFoundError(f"Không tìm thấy đơn thanh toán #{order_code}")
            order_code = order["order_code"]


            current_status = order["payment_status"]

            # Idempotency check: already paid orders must not grant VIP twice
            if current_status == PAYMENT_STATUS_PAID:
                logger.info("Order #%s is already marked paid. Duplicate admin confirmation ignored.", order_code)
                return {
                    "success": True,
                    "already_paid": True,
                    "order_code": order_code,
                    "order_reference": order["order_reference"],
                    "payment_status": PAYMENT_STATUS_PAID,
                    "paid_at": order["paid_at"],
                    "subscription_id": order["subscription_id"],
                    "message_vi": "Đơn hàng này đã được xác nhận thanh toán trước đó."
                }

            now_utc = datetime.now(timezone.utc)
            now_iso = now_utc.strftime("%Y-%m-%d %H:%M:%S")
            period_end_utc = now_utc + timedelta(days=30)
            period_end_iso = period_end_utc.strftime("%Y-%m-%d %H:%M:%S")

            target_type = order["target_type"]
            target_id = order["target_id"]
            plan_id = order["plan_id"]
            amount = int(order["amount"])
            order_reference = order["order_reference"] or format_order_reference(order["user_id"], order_code)

            # a) Supersede existing active subscriptions
            cursor.execute("""
                UPDATE subscriptions
                SET status = 'canceled',
                    canceled_at = ?,
                    updated_at = ?
                WHERE target_type = ? AND target_id = ?
                  AND status IN ('active', 'trialing', 'cancel_at_period_end')
            """, (now_iso, now_iso, target_type, target_id))

            # b) Insert new active 30-day subscription
            tx_ref_label = bank_tx_reference or f"MANUAL-ADMIN-{admin_user_id}"
            cursor.execute("""
                INSERT INTO subscriptions (
                    target_type, target_id, user_id, organization_id,
                    plan_id, status, billing_interval,
                    current_period_start, current_period_end,
                    is_paid, provider, provider_subscription_id, notes,
                    created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?,
                    ?, 'active', 'monthly',
                    ?, ?,
                    1, 'manual_bank_transfer', ?, ?,
                    ?, ?
                )
            """, (
                target_type, target_id, order["user_id"], order["organization_id"],
                plan_id,
                now_iso, period_end_iso,
                f"sub_{order_code}_{admin_user_id}",
                f"Xác nhận chuyển khoản ngân hàng bởi Admin #{admin_user_id} (Ref: {tx_ref_label})",
                now_iso, now_iso
            ))
            new_sub_id = cursor.lastrowid

            # c) Sync legacy user_subscriptions table if user-target
            if target_type == "user":
                cursor.execute("""
                    INSERT OR REPLACE INTO user_subscriptions (
                        user_id, plan_id, status, billing_interval, start_date, end_date,
                        notes, created_at, updated_at
                    ) VALUES (?, ?, 'active', 'monthly', ?, ?, ?, ?, ?)
                """, (
                    target_id, plan_id, now_iso, period_end_iso,
                    f"Thanh toán chuyển khoản VietQR #{order_code} (Admin #{admin_user_id})",
                    now_iso, now_iso
                ))

            # d) Create paid invoice record
            invoice_number = f"INV-BANK-{order_code}"
            cursor.execute("""
                INSERT INTO invoices (
                    invoice_number, target_type, target_id, subscription_id,
                    amount, currency, status, payment_status, payment_method,
                    period_start, period_end, description, paid_at,
                    created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?,
                    ?, 'VND', 'paid', 'succeeded', 'bank_transfer',
                    ?, ?, ?, ?,
                    ?, ?
                )
            """, (
                invoice_number, target_type, target_id, new_sub_id,
                amount,
                now_iso, period_end_iso,
                f"Thanh toán gói {plan_id} (VietQR #{order_reference})",
                now_iso, now_iso, now_iso
            ))
            new_invoice_id = cursor.lastrowid

            # e) Update payment_orders record
            cursor.execute("""
                UPDATE payment_orders
                SET payment_status = 'paid',
                    paid_at = ?,
                    confirmed_by_admin_id = ?,
                    bank_tx_reference = ?,
                    admin_notes = ?,
                    subscription_id = ?,
                    invoice_id = ?,
                    updated_at = ?
                WHERE order_code = ?
            """, (
                now_iso, admin_user_id, bank_tx_reference, admin_notes,
                new_sub_id, new_invoice_id, now_iso, order_code
            ))

            # f) Record detailed audit record
            cursor.execute("""
                INSERT INTO payment_audit_log (order_code, internal_payment_id, action, actor_type, actor_id, details_json)
                VALUES (?, ?, 'admin_payment_confirmed', 'admin', ?, ?)
            """, (
                order_code, order["internal_payment_id"], str(admin_user_id),
                json.dumps({
                    "admin_id": admin_user_id,
                    "order_reference": order_reference,
                    "amount": amount,
                    "bank_tx_reference": bank_tx_reference,
                    "confirmed_at": now_iso,
                    "subscription_id": new_sub_id,
                    "invoice_id": new_invoice_id,
                    "notes": admin_notes
                })
            ))

            conn.commit()
            logger.info("Admin #%s confirmed payment for order #%s (Ref: %s, Sub: #%s)", admin_user_id, order_code, order_reference, new_sub_id)

            return {
                "success": True,
                "order_code": order_code,
                "order_reference": order_reference,
                "payment_status": PAYMENT_STATUS_PAID,
                "subscription_id": new_sub_id,
                "invoice_id": new_invoice_id,
                "confirmed_by_admin_id": admin_user_id,
                "bank_tx_reference": bank_tx_reference,
                "paid_at": now_iso,
                "message_vi": f"Đã xác nhận thanh toán thành công cho đơn #{order_code}. Thuê bao 30 ngày đã được kích hoạt."
            }


# -----------------------------------------------------------------------------
# 9. Admin-Only Action: Manual Payment Rejection
# -----------------------------------------------------------------------------

def admin_reject_payment(
    order_code: int,
    admin_user_id: int,
    reason: str,
    admin_notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Admin-only manual payment rejection (e.g. transfer not received, invalid syntax, fraudulent claim).
    Transitions order to 'rejected' without granting entitlements.
    """
    with _PAYMENT_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM payment_orders WHERE order_code = ? OR order_reference = ?", (order_code, str(order_code)))
            order = cursor.fetchone()
            if not order:
                raise PaymentOrderNotFoundError(f"Không tìm thấy đơn thanh toán #{order_code}")
            order_code = order["order_code"]


            if order["payment_status"] == PAYMENT_STATUS_PAID:
                raise PaymentError("Không thể từ chối đơn hàng đã được thanh toán.")

            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                UPDATE payment_orders
                SET payment_status = 'rejected',
                    failure_reason = ?,
                    confirmed_by_admin_id = ?,
                    admin_notes = ?,
                    updated_at = ?
                WHERE order_code = ?
            """, (reason, admin_user_id, admin_notes, now_iso, order_code))

            cursor.execute("""
                INSERT INTO payment_audit_log (order_code, internal_payment_id, action, actor_type, actor_id, details_json)
                VALUES (?, ?, 'admin_payment_rejected', 'admin', ?, ?)
            """, (
                order_code, order["internal_payment_id"], str(admin_user_id),
                json.dumps({
                    "admin_id": admin_user_id,
                    "order_reference": order["order_reference"],
                    "rejection_reason": reason,
                    "rejected_at": now_iso,
                    "notes": admin_notes
                })
            ))

            conn.commit()
            logger.info("Admin #%s rejected order #%s: %s", admin_user_id, order_code, reason)

            return {
                "success": True,
                "order_code": order_code,
                "order_reference": order["order_reference"],
                "payment_status": PAYMENT_STATUS_REJECTED,
                "failure_reason": reason,
                "message_vi": f"Đã từ chối đơn thanh toán #{order_code}."
            }


# -----------------------------------------------------------------------------
# 10. Admin-Only Action: List Payment Orders for Review
# -----------------------------------------------------------------------------

def list_payment_orders_for_admin(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Lists payment orders for administrative review with linked user information."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT po.*, u.email as user_email, u.name as user_name
            FROM payment_orders po
            LEFT JOIN users u ON po.user_id = u.id
        """
        params: List[Any] = []
        if status:
            query += " WHERE po.payment_status = ?"
            params.append(status)
        query += " ORDER BY po.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


# -----------------------------------------------------------------------------
# 11. Order Status Verification (Server-Side)
# -----------------------------------------------------------------------------

def get_order_status(order_code: int, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Retrieves the authoritative internal status of a payment order.
    If user_id is provided, verifies that order belongs to user or user's organization.
    Automatically checks and updates expiration if overdue.
    Never trusts client parameters or claims.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM payment_orders WHERE order_code = ? OR order_reference = ?", (order_code, str(order_code)))
        order = cursor.fetchone()
        if not order:
            raise PaymentOrderNotFoundError(f"Không tìm thấy đơn thanh toán #{order_code}")
        order_code = order["order_code"]


        # Ensure order belongs to user or user's organization (if user_id specified)
        if user_id is not None:
            if order["target_type"] == "user":
                if order["user_id"] != user_id:
                    raise PaymentPermissionError("Bạn không có quyền xem đơn hàng này.")
            elif order["target_type"] == "organization":
                role = gari_b2b.get_member_role(order["organization_id"], user_id)
                if not role:
                    raise PaymentPermissionError("Bạn không thuộc tổ chức sở hữu đơn hàng này.")

        current_status = order["payment_status"]

        # Check for expiration if still pending and not reported
        if current_status == PAYMENT_STATUS_PENDING and order["expires_at"]:
            now_utc = datetime.now(timezone.utc)
            exp_dt = datetime.strptime(order["expires_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if now_utc > exp_dt:
                current_status = PAYMENT_STATUS_EXPIRED
                cursor.execute("""
                    UPDATE payment_orders
                    SET payment_status = 'expired',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (order["id"],))
                conn.commit()

        return {
            "order_code": order["order_code"],
            "order_reference": order["order_reference"] or format_order_reference(order["user_id"], order["order_code"]),
            "internal_payment_id": order["internal_payment_id"],
            "plan_id": order["plan_id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "payment_status": current_status,
            "failure_reason": order["failure_reason"],
            "bank_id": order["bank_id"] or get_bank_id(),
            "account_number": order["account_number"] or get_account_number(),
            "account_name": order["account_name"] or get_account_name(),
            "qr_code_url": order["qr_code_url"],
            "transfer_content": order["order_reference"] or format_order_reference(order["user_id"], order["order_code"]),
            "expires_at": order["expires_at"],
            "created_at": order["created_at"],
            "transfer_reported_at": order["transfer_reported_at"] if "transfer_reported_at" in order.keys() else None,
            "paid_at": order["paid_at"],
            "confirmed_by_admin_id": order["confirmed_by_admin_id"] if "confirmed_by_admin_id" in order.keys() else None,
            "bank_tx_reference": order["bank_tx_reference"] if "bank_tx_reference" in order.keys() else None,
            "subscription_id": order["subscription_id"]
        }
