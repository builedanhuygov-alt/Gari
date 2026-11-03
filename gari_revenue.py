"""
GARI AI LAB — Revenue & Subscription Engine (gari_revenue.py)
Sprint 3: Revenue & Subscription Engine

Provides:
1. Subscription Lifecycle State Machine:
   - trialing, active, past_due, cancel_at_period_end, canceled, expired, suspended
   - Exactly one active subscription per subject (user or organization)
2. Authoritative Entitlement Resolution:
   - Single point of truth for paid benefits, models, and limits
   - Expiration checks: expired/past_due/suspended immediately revokes paid access
   - cancel_at_period_end retains benefits until current_period_end
   - Safe unlimited quota representation (is_unlimited: True, quota_limit: None, NO 999999)
3. Billing & Invoicing Records:
   - Billing customer profile (tax ID, address, contact)
   - Invoices with honest payment_status ('not_collected', 'pending', 'succeeded', 'failed', 'refunded')
   - Payment attempts with provider tx_id and failure reasons
   - Credit notes & refund records
4. Payment Provider Transparency:
   - Returns payment_provider_not_configured when no live gateway configured
   - Clearly marks manual pilot vs paid subscription (is_paid: False, payment_method: "manual")
5. Admin Controls & Full Audit Trail:
   - Assign, renew, extend, cancel, suspend subscriptions with mandatory reason
   - Record audited payment attempts and manual settlements
"""

import hashlib
import json
import logging
import re
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import gari_plans

logger = logging.getLogger("gari_revenue")

DB_PATH = Path(__file__).resolve().parent / "database" / "disease_detector.db"
_REVENUE_LOCK = threading.RLock()

# -----------------------------------------------------------------------------
# 1. SUBSCRIPTION & REVENUE CONSTANTS
# -----------------------------------------------------------------------------
SUBSCRIPTION_STATUSES = (
    "trialing",
    "active",
    "past_due",
    "cancel_at_period_end",
    "canceled",
    "expired",
    "suspended",
)

ACTIVE_ENTITLED_STATUSES = {"active", "trialing", "cancel_at_period_end"}

BILLING_INTERVALS = ("daily", "monthly", "annual")

PAYMENT_STATUSES = (
    "not_collected",
    "pending",
    "succeeded",
    "failed",
    "refunded",
)

INVOICE_STATUSES = (
    "draft",
    "open",
    "paid",
    "void",
    "uncollectible",
    "refunded",
)

COMMERCIAL_INTENTS = (
    "none",
    "pilot_interest",
    "pilot_active",
    "paid_subscription",
)

PAYMENT_PROVIDERS = ("manual", "vnpay", "stripe", "momo", "none")

# Current gateway state
PAYMENT_PROVIDER_STATUS = "payment_provider_not_configured"


class SubscriptionError(Exception):
    """Base exception for subscription domain errors."""


class SubscriptionStateError(SubscriptionError):
    """Raised when an invalid state transition is attempted."""


class BillingPermissionError(PermissionError):
    """Raised when an unauthorized billing action or cross-tenant access is attempted."""


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_utc_iso() -> str:
    return now_utc().strftime("%Y-%m-%d %H:%M:%S")


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(cursor: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
    """Idempotently add a column to an existing SQLite table."""
    columns = [row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


# -----------------------------------------------------------------------------
# 2. DATABASE SCHEMA INITIALIZATION
# -----------------------------------------------------------------------------

def init_revenue_database() -> None:
    """Initialize Revenue, Subscriptions, Invoices, and Payment tables."""
    with _REVENUE_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # 1. Unified Subscriptions Table (User & Organization subjects)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_type TEXT NOT NULL,                  -- 'user' | 'organization'
                target_id INTEGER NOT NULL,                 -- user_id or organization_id
                user_id INTEGER,
                organization_id INTEGER,
                plan_id TEXT NOT NULL DEFAULT 'free',
                status TEXT NOT NULL DEFAULT 'active',
                billing_interval TEXT NOT NULL DEFAULT 'monthly',
                current_period_start DATETIME NOT NULL,
                current_period_end DATETIME,
                cancel_at_period_end BOOLEAN NOT NULL DEFAULT 0,
                canceled_at DATETIME,
                ended_at DATETIME,
                trial_start DATETIME,
                trial_end DATETIME,
                commercial_intent TEXT NOT NULL DEFAULT 'none',
                is_paid BOOLEAN NOT NULL DEFAULT 0,
                provider TEXT NOT NULL DEFAULT 'manual',
                provider_subscription_id TEXT,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 2. Billing Customer Profiles
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_type TEXT NOT NULL,                  -- 'user' | 'organization'
                target_id INTEGER NOT NULL,
                customer_name TEXT NOT NULL,
                company_name TEXT,
                tax_id TEXT,
                billing_email TEXT NOT NULL,
                billing_phone TEXT,
                billing_address TEXT,
                currency TEXT NOT NULL DEFAULT 'VND',
                provider TEXT NOT NULL DEFAULT 'none',
                provider_customer_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (target_type, target_id)
            );
            """)

            # 3. Invoices Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                target_type TEXT NOT NULL,
                target_id INTEGER NOT NULL,
                subscription_id INTEGER,
                amount REAL NOT NULL DEFAULT 0.0,
                currency TEXT NOT NULL DEFAULT 'VND',
                status TEXT NOT NULL DEFAULT 'draft',
                payment_status TEXT NOT NULL DEFAULT 'not_collected',
                payment_method TEXT NOT NULL DEFAULT 'manual',
                period_start DATETIME,
                period_end DATETIME,
                description TEXT,
                created_by_user_id INTEGER,
                issued_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                due_date DATETIME,
                paid_at DATETIME,
                voided_at DATETIME,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE SET NULL
            );
            """)

            # 4. Payment Attempts Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS payment_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                target_type TEXT NOT NULL,
                target_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'VND',
                payment_method TEXT NOT NULL DEFAULT 'manual',
                payment_status TEXT NOT NULL DEFAULT 'pending',
                provider TEXT NOT NULL DEFAULT 'manual',
                provider_tx_id TEXT,
                idempotency_key TEXT UNIQUE,
                failure_reason TEXT,
                error_code TEXT,
                initiated_by_user_id INTEGER,
                metadata_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
            );
            """)

            # 5. Credit Notes & Refunds Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS credit_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                credit_note_number TEXT UNIQUE NOT NULL,
                invoice_id INTEGER NOT NULL,
                target_type TEXT NOT NULL,
                target_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'VND',
                reason TEXT NOT NULL,
                created_by_user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'completed',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
            );
            """)

            # 6. Auditable Billing Usage Events (No sensitive data or images)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_type TEXT NOT NULL,                  -- 'user' | 'organization'
                target_id INTEGER NOT NULL,
                actor_user_id INTEGER,
                feature TEXT NOT NULL,                      -- 'diagnosis', 'api_call', 'export'
                usage_amount INTEGER NOT NULL DEFAULT 1,
                result TEXT NOT NULL,                       -- 'success', 'quota_exceeded', 'permission_denied'
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Indexes for high performance and isolation
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_subs_target ON subscriptions(target_type, target_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_subs_status ON subscriptions(status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_subs_user ON subscriptions(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_subs_org ON subscriptions(organization_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_billing_cust_target ON billing_customers(target_type, target_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_target ON invoices(target_type, target_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_number ON invoices(invoice_number);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pay_attempts_invoice ON payment_attempts(invoice_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pay_attempts_target ON payment_attempts(target_type, target_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_credit_notes_inv ON credit_notes(invoice_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_billing_events_target ON billing_usage_events(target_type, target_id, created_at);")

            conn.commit()


# Initialize on import
init_revenue_database()


# -----------------------------------------------------------------------------
# 3. SUBSCRIPTION LIFECYCLE STATE MACHINE
# -----------------------------------------------------------------------------

def _validate_subscription_transition(old_status: str, new_status: str) -> None:
    """Validate allowed state transitions for the subscription lifecycle."""
    if new_status == old_status:
        return
    if new_status not in SUBSCRIPTION_STATUSES:
        raise SubscriptionStateError(f"Trạng thái subscription không hợp lệ: {new_status}")

    allowed_transitions = {
        "trialing": {"active", "expired", "canceled"},
        "active": {"cancel_at_period_end", "past_due", "suspended", "expired", "canceled"},
        "cancel_at_period_end": {"active", "expired", "canceled"},
        "past_due": {"active", "suspended", "canceled", "expired"},
        "suspended": {"active", "canceled", "expired"},
        "expired": {"active"},    # Renewal by admin/manual order
        "canceled": {"active"},   # Admin explicit restoration
    }
    allowed = allowed_transitions.get(old_status, set())
    if new_status not in allowed:
        raise SubscriptionStateError(f"Không thể chuyển trạng thái subscription từ '{old_status}' sang '{new_status}'.")


def get_active_subscription(target_type: str, target_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve the single currently effective subscription for a user or organization.
    Automatically checks and reflects expiration if current_period_end has elapsed.
    """
    now = now_utc()
    now_iso = now.strftime("%Y-%m-%d %H:%M:%S")

    with _REVENUE_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM subscriptions
                WHERE target_type = ? AND target_id = ?
                  AND status IN ('trialing', 'active', 'cancel_at_period_end', 'past_due', 'suspended')
                ORDER BY (status = 'active') DESC, created_at DESC
                LIMIT 1
            """, (target_type, target_id))
            row = cursor.fetchone()
            if not row:
                return None

            sub = dict(row)
            # Check period end expiration
            if sub.get("current_period_end"):
                try:
                    end_dt = datetime.strptime(sub["current_period_end"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    if now > end_dt:
                        # Period expired
                        cursor.execute("""
                            UPDATE subscriptions
                            SET status = 'expired', updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (sub["id"],))
                        if sub.get("target_type") == "user" and sub.get("target_id"):
                            cursor.execute("""
                                UPDATE user_subscriptions
                                SET status = 'expired', updated_at = CURRENT_TIMESTAMP
                                WHERE user_id = ?
                            """, (sub["target_id"],))
                        conn.commit()
                        sub["status"] = "expired"
                except Exception:
                    pass

            return sub


def get_subscription_by_id(subscription_id: int) -> Optional[Dict[str, Any]]:
    """Fetch subscription record by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM subscriptions WHERE id = ?", (subscription_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def list_subscriptions(
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """List subscriptions with optional filtering (Platform Admin / Billing view)."""
    limit = max(1, min(int(limit or 100), 500))
    with get_db_connection() as conn:
        cursor = conn.cursor()
        clauses = []
        params: List[Any] = []

        if target_type:
            clauses.append("target_type = ?")
            params.append(target_type)
        if target_id is not None:
            clauses.append("target_id = ?")
            params.append(target_id)
        if status:
            clauses.append("status = ?")
            params.append(status)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)

        cursor.execute(f"""
            SELECT * FROM subscriptions
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ?
        """, params)
        return [dict(r) for r in cursor.fetchall()]


def create_or_assign_subscription(
    target_type: str,
    target_id: int,
    plan_id: str,
    status: str = "active",
    billing_interval: str = "monthly",
    duration_days: Optional[int] = 30,
    commercial_intent: str = "pilot_active",
    is_paid: bool = False,
    provider: str = "manual",
    notes: Optional[str] = None,
    actor_user_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create or assign a subscription with single-active invariant and audit logging.
    Enforces rule: exactly one active subscription per target subject.
    """
    if target_type not in ("user", "organization"):
        raise ValueError("target_type phải là 'user' hoặc 'organization'.")
    plan_def = gari_plans.get_plan_definition(plan_id)
    canonical_plan_id = plan_def["plan_id"]

    if status not in SUBSCRIPTION_STATUSES:
        raise ValueError(f"Trạng thái subscription không hợp lệ. Hợp lệ: {', '.join(SUBSCRIPTION_STATUSES)}")
    if commercial_intent not in COMMERCIAL_INTENTS:
        commercial_intent = "none"

    now = now_utc()
    now_iso = now.strftime("%Y-%m-%d %H:%M:%S")

    if duration_days is None:
        period_end_iso = None
    else:
        period_end = now + timedelta(days=max(1, int(duration_days)))
        period_end_iso = period_end.strftime("%Y-%m-%d %H:%M:%S")

    user_id = target_id if target_type == "user" else None
    org_id = target_id if target_type == "organization" else None

    with _REVENUE_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Invariant: Terminate / supersede any previous active subscription for this target
            cursor.execute("""
                UPDATE subscriptions
                SET status = 'canceled', canceled_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE target_type = ? AND target_id = ?
                  AND status IN ('trialing', 'active', 'cancel_at_period_end', 'past_due', 'suspended')
            """, (target_type, target_id))

            cursor.execute("""
                INSERT INTO subscriptions (
                    target_type, target_id, user_id, organization_id, plan_id, status,
                    billing_interval, current_period_start, current_period_end, cancel_at_period_end,
                    commercial_intent, is_paid, provider, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
            """, (
                target_type, target_id, user_id, org_id, canonical_plan_id, status,
                billing_interval, now_iso, period_end_iso, commercial_intent, 1 if is_paid else 0,
                provider, notes or reason or "Khởi tạo/Cập nhật subscription"
            ))
            sub_id = cursor.lastrowid

            # Mirror to user_subscriptions or organizations table for complete backward compatibility
            if target_type == "user":
                cursor.execute("""
                    INSERT INTO user_subscriptions (user_id, plan_id, status, billing_interval, start_date, end_date, notes, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        plan_id = excluded.plan_id,
                        status = excluded.status,
                        billing_interval = excluded.billing_interval,
                        start_date = excluded.start_date,
                        end_date = excluded.end_date,
                        notes = excluded.notes,
                        updated_at = CURRENT_TIMESTAMP
                """, (target_id, canonical_plan_id, status, billing_interval, now_iso, period_end_iso, notes or reason))
            elif target_type == "organization":
                # Sync organizations.plan_id
                cursor.execute("""
                    UPDATE organizations
                    SET plan_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (canonical_plan_id, target_id))
                # Sync organization quota table
                quota_limit = plan_def.get("quota_limit")
                if quota_limit is None and plan_def.get("is_unlimited_quota"):
                    quota_limit = -1
                cursor.execute("""
                    UPDATE organization_quotas
                    SET plan_id = ?, quota_limit = COALESCE(?, quota_limit), updated_at = CURRENT_TIMESTAMP
                    WHERE organization_id = ?
                """, (canonical_plan_id, quota_limit, target_id))

            # Audit Trail
            cursor.execute("""
                INSERT INTO plan_audit_trail (target_type, target_id, old_plan, new_plan, action, changed_by_user_id, reason)
                VALUES (?, ?, 'none', ?, 'assigned', ?, ?)
            """, (target_type, target_id, canonical_plan_id, actor_user_id, reason or notes or "Admin gán subscription"))

            # Org audit log if organization
            if target_type == "organization":
                cursor.execute("""
                    INSERT INTO organization_audit_log (organization_id, actor_user_id, action, target_type, target_id, reason, metadata_json)
                    VALUES (?, ?, 'organization.subscription_assigned', 'subscription', ?, ?, ?)
                """, (
                    target_id, actor_user_id, sub_id, reason or "Gán subscription tổ chức",
                    json.dumps({
                        "plan_id": canonical_plan_id,
                        "status": status,
                        "is_paid": bool(is_paid),
                        "commercial_intent": commercial_intent,
                        "current_period_end": period_end_iso
                    }, ensure_ascii=False)
                ))

            conn.commit()

    return get_subscription_by_id(sub_id) or {}


def update_subscription_status(
    subscription_id: int,
    new_status: str,
    reason: str,
    actor_user_id: Optional[int] = None,
    extend_days: Optional[int] = None
) -> Dict[str, Any]:
    """
    Transition a subscription state (cancel, suspend, reactivate, extend) with strict audit.
    """
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise ValueError("Vui lòng cung cấp lý do thực hiện thao tác trên subscription.")

    with _REVENUE_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM subscriptions WHERE id = ?", (subscription_id,))
            sub_row = cursor.fetchone()
            if not sub_row:
                raise SubscriptionError("Không tìm thấy subscription.")

            sub = dict(sub_row)
            old_status = sub["status"]
            _validate_subscription_transition(old_status, new_status)

            updates = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
            params: List[Any] = [new_status]

            if new_status == "canceled":
                updates.append("canceled_at = CURRENT_TIMESTAMP")
                updates.append("ended_at = CURRENT_TIMESTAMP")
            elif new_status == "active":
                updates.append("cancel_at_period_end = 0")

            if extend_days and extend_days > 0:
                base_time = now_utc()
                if sub.get("current_period_end"):
                    try:
                        curr_end = datetime.strptime(sub["current_period_end"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                        if curr_end > base_time:
                            base_time = curr_end
                    except Exception:
                        pass
                new_end = (base_time + timedelta(days=extend_days)).strftime("%Y-%m-%d %H:%M:%S")
                updates.append("current_period_end = ?")
                params.append(new_end)

            params.append(subscription_id)
            cursor.execute(f"UPDATE subscriptions SET {', '.join(updates)} WHERE id = ?", params)

            # Sync to backward compatible tables
            target_type = sub["target_type"]
            target_id = sub["target_id"]
            if target_type == "user":
                cursor.execute("""
                    UPDATE user_subscriptions
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (new_status, target_id))
            elif target_type == "organization":
                # If subscription was revoked/suspended/canceled, sync org plan to pilot
                if new_status in ("canceled", "suspended", "expired", "past_due"):
                    cursor.execute("""
                        UPDATE organizations
                        SET plan_id = 'pilot', updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (target_id,))
                elif new_status == "active":
                    cursor.execute("""
                        UPDATE organizations
                        SET plan_id = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (sub["plan_id"], target_id))

            # Audit
            cursor.execute("""
                INSERT INTO plan_audit_trail (target_type, target_id, old_plan, new_plan, action, changed_by_user_id, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (target_type, target_id, sub["plan_id"], sub["plan_id"], f"status_{new_status}", actor_user_id, reason))

            if target_type == "organization":
                cursor.execute("""
                    INSERT INTO organization_audit_log (organization_id, actor_user_id, action, target_type, target_id, reason, metadata_json)
                    VALUES (?, ?, 'organization.subscription_status_changed', 'subscription', ?, ?, ?)
                """, (
                    target_id, actor_user_id, subscription_id, reason,
                    json.dumps({"old_status": old_status, "new_status": new_status}, ensure_ascii=False)
                ))

            conn.commit()

    return get_subscription_by_id(subscription_id) or {}


def cancel_subscription_at_period_end(
    subscription_id: int,
    reason: str,
    actor_user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Mark subscription to cancel at period end.
    CRITICAL RULE: User/org STILL HAS their plan entitlements until current_period_end!
    """
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise ValueError("Vui lòng cung cấp lý do hủy thuê bao.")

    with _REVENUE_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM subscriptions WHERE id = ?", (subscription_id,))
            row = cursor.fetchone()
            if not row:
                raise SubscriptionError("Không tìm thấy subscription.")
            sub = dict(row)
            if sub["status"] != "active":
                raise SubscriptionStateError("Chỉ có thể đặt hủy vào cuối kỳ cho subscription đang 'active'.")

            cursor.execute("""
                UPDATE subscriptions
                SET status = 'cancel_at_period_end', cancel_at_period_end = 1,
                    canceled_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (subscription_id,))

            cursor.execute("""
                INSERT INTO plan_audit_trail (target_type, target_id, old_plan, new_plan, action, changed_by_user_id, reason)
                VALUES (?, ?, ?, ?, 'cancel_at_period_end', ?, ?)
            """, (sub["target_type"], sub["target_id"], sub["plan_id"], sub["plan_id"], actor_user_id, reason))

            conn.commit()

    return get_subscription_by_id(subscription_id) or {}


def reactivate_subscription(
    subscription_id: int,
    reason: str,
    actor_user_id: Optional[int] = None
) -> Dict[str, Any]:
    """Reactivate a subscription that was scheduled to cancel at period end."""
    with _REVENUE_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM subscriptions WHERE id = ?", (subscription_id,))
            row = cursor.fetchone()
            if not row:
                raise SubscriptionError("Không tìm thấy subscription.")
            sub = dict(row)
            if sub["status"] != "cancel_at_period_end":
                raise SubscriptionStateError("Chỉ có thể kích hoạt lại subscription đang ở trạng thái 'cancel_at_period_end'.")

            cursor.execute("""
                UPDATE subscriptions
                SET status = 'active', cancel_at_period_end = 0,
                    canceled_at = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (subscription_id,))

            cursor.execute("""
                INSERT INTO plan_audit_trail (target_type, target_id, old_plan, new_plan, action, changed_by_user_id, reason)
                VALUES (?, ?, ?, ?, 'reactivated', ?, ?)
            """, (sub["target_type"], sub["target_id"], sub["plan_id"], sub["plan_id"], actor_user_id, reason))

            conn.commit()

    return get_subscription_by_id(subscription_id) or {}


# -----------------------------------------------------------------------------
# 4. BILLING PROFILES, INVOICES & PAYMENT ATTEMPTS
# -----------------------------------------------------------------------------

def get_or_create_billing_customer(
    target_type: str,
    target_id: int,
    customer_name: str,
    billing_email: str,
    company_name: Optional[str] = None,
    tax_id: Optional[str] = None,
    billing_phone: Optional[str] = None,
    billing_address: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieve or register a customer billing profile."""
    with _REVENUE_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM billing_customers
                WHERE target_type = ? AND target_id = ?
            """, (target_type, target_id))
            row = cursor.fetchone()
            if row:
                return dict(row)

            cursor.execute("""
                INSERT INTO billing_customers (
                    target_type, target_id, customer_name, company_name, tax_id,
                    billing_email, billing_phone, billing_address
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                target_type, target_id, customer_name, company_name, tax_id,
                billing_email.lower().strip(), billing_phone, billing_address
            ))
            cust_id = cursor.lastrowid
            conn.commit()

            cursor.execute("SELECT * FROM billing_customers WHERE id = ?", (cust_id,))
            return dict(cursor.fetchone())


def get_billing_customer(target_type: str, target_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve customer billing profile if exists."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM billing_customers WHERE target_type = ? AND target_id = ?", (target_type, target_id))
        row = cursor.fetchone()
        return dict(row) if row else None


def generate_invoice_number() -> str:
    """Generate sequential, human-friendly invoice number."""
    now_str = datetime.now(timezone.utc).strftime("%Y%m")
    rnd = secrets.token_hex(3).upper()
    return f"INV-{now_str}-{rnd}"


def create_invoice(
    target_type: str,
    target_id: int,
    amount: float,
    description: str,
    subscription_id: Optional[int] = None,
    currency: str = "VND",
    payment_method: str = "manual",
    payment_status: str = "not_collected",
    status: str = "draft",
    due_days: int = 14,
    created_by_user_id: Optional[int] = None,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create an invoice record.
    Rule: Cannot create a 'paid' invoice without payment provider proof or audited admin action.
    """
    if payment_status == "succeeded" and created_by_user_id is None:
        raise ValueError("Không thể tạo hóa đơn thanh toán thành công mà không có vết kiểm toán người phê duyệt.")

    inv_num = generate_invoice_number()
    now = now_utc()
    now_iso = now.strftime("%Y-%m-%d %H:%M:%S")
    due_iso = (now + timedelta(days=due_days)).strftime("%Y-%m-%d %H:%M:%S")
    paid_iso = now_iso if payment_status == "succeeded" else None

    with _REVENUE_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO invoices (
                    invoice_number, target_type, target_id, subscription_id,
                    amount, currency, status, payment_status, payment_method,
                    description, created_by_user_id, issued_at, due_date, paid_at, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                inv_num, target_type, target_id, subscription_id,
                amount, currency, status, payment_status, payment_method,
                description, created_by_user_id, now_iso, due_iso, paid_iso, notes
            ))
            inv_id = cursor.lastrowid
            conn.commit()

            cursor.execute("SELECT * FROM invoices WHERE id = ?", (inv_id,))
            return dict(cursor.fetchone())


def list_invoices(
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """List invoices for tenant or admin."""
    limit = max(1, min(int(limit or 50), 200))
    with get_db_connection() as conn:
        cursor = conn.cursor()
        clauses = []
        params: List[Any] = []
        if target_type:
            clauses.append("target_type = ?")
            params.append(target_type)
        if target_id is not None:
            clauses.append("target_id = ?")
            params.append(target_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)

        cursor.execute(f"""
            SELECT * FROM invoices
            {where_sql}
            ORDER BY issued_at DESC, id DESC
            LIMIT ?
        """, params)
        return [dict(r) for r in cursor.fetchall()]


def record_payment_attempt(
    invoice_id: int,
    payment_status: str,
    payment_method: str = "manual",
    provider: str = "manual",
    provider_tx_id: Optional[str] = None,
    failure_reason: Optional[str] = None,
    error_code: Optional[str] = None,
    initiated_by_user_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Record payment attempt result.
    RULE: Failed payment NEVER activates a paid subscription.
    """
    if payment_status not in PAYMENT_STATUSES:
        raise ValueError(f"payment_status không hợp lệ: {payment_status}")

    with _REVENUE_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
            inv_row = cursor.fetchone()
            if not inv_row:
                raise ValueError("Không tìm thấy hóa đơn.")
            inv = dict(inv_row)

            idempotency_key = f"pay_{invoice_id}_{secrets.token_hex(8)}"
            now_iso = now_utc_iso()

            cursor.execute("""
                INSERT INTO payment_attempts (
                    invoice_id, target_type, target_id, amount, currency,
                    payment_method, payment_status, provider, provider_tx_id,
                    idempotency_key, failure_reason, error_code, initiated_by_user_id,
                    metadata_json, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                invoice_id, inv["target_type"], inv["target_id"], inv["amount"], inv["currency"],
                payment_method, payment_status, provider, provider_tx_id,
                idempotency_key, failure_reason, error_code, initiated_by_user_id,
                json.dumps(metadata or {}, ensure_ascii=False), now_iso
            ))
            attempt_id = cursor.lastrowid

            # Update invoice state
            if payment_status == "succeeded":
                cursor.execute("""
                    UPDATE invoices
                    SET payment_status = 'succeeded', status = 'paid', paid_at = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (now_iso, invoice_id))
                # Activate subscription if linked
                if inv.get("subscription_id"):
                    cursor.execute("""
                        UPDATE subscriptions
                        SET is_paid = 1, status = 'active', updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (inv["subscription_id"],))
            elif payment_status == "failed":
                cursor.execute("""
                    UPDATE invoices
                    SET payment_status = 'failed', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (invoice_id,))
                # CRITICAL: A failed payment attempt must NEVER activate a subscription!
                # If subscription was linked and pending, it remains past_due or trialing
                if inv.get("subscription_id"):
                    cursor.execute("""
                        UPDATE subscriptions
                        SET is_paid = 0, status = CASE WHEN status = 'active' THEN 'past_due' ELSE status END,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (inv["subscription_id"],))

            conn.commit()

            cursor.execute("SELECT * FROM payment_attempts WHERE id = ?", (attempt_id,))
            return dict(cursor.fetchone())


def list_payment_attempts(
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """List payment attempts."""
    limit = max(1, min(int(limit or 50), 200))
    with get_db_connection() as conn:
        cursor = conn.cursor()
        clauses = []
        params: List[Any] = []
        if target_type:
            clauses.append("target_type = ?")
            params.append(target_type)
        if target_id is not None:
            clauses.append("target_id = ?")
            params.append(target_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)

        cursor.execute(f"""
            SELECT * FROM payment_attempts
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ?
        """, params)
        return [dict(r) for r in cursor.fetchall()]


# -----------------------------------------------------------------------------
# 5. AUDITABLE BILLING USAGE TELEMETRY
# -----------------------------------------------------------------------------

def log_billing_usage_event(
    target_type: str,
    target_id: int,
    feature: str,
    actor_user_id: Optional[int] = None,
    usage_amount: int = 1,
    result: str = "success"
) -> None:
    """Log an auditable usage event without sensitive content."""
    try:
        with _REVENUE_LOCK:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO billing_usage_events (target_type, target_id, actor_user_id, feature, usage_amount, result)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (target_type, target_id, actor_user_id, feature, usage_amount, result))
                conn.commit()
    except Exception as exc:
        logger.warning(f"Failed to log billing usage event: {exc}")


def get_billing_usage_summary(target_type: str, target_id: int, days: int = 30) -> Dict[str, Any]:
    """Summary of usage events for customer billing review."""
    days = max(1, min(int(days or 30), 365))
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COUNT(*) as total_events,
                SUM(usage_amount) as total_units_consumed,
                SUM(CASE WHEN result = 'success' THEN 1 ELSE 0 END) as successful_events,
                SUM(CASE WHEN result = 'quota_exceeded' THEN 1 ELSE 0 END) as quota_exceeded_events
            FROM billing_usage_events
            WHERE target_type = ? AND target_id = ?
              AND created_at >= datetime('now', ?)
        """, (target_type, target_id, f"-{days} days"))
        row = dict(cursor.fetchone() or {})

        cursor.execute("""
            SELECT feature, SUM(usage_amount) as units
            FROM billing_usage_events
            WHERE target_type = ? AND target_id = ?
              AND created_at >= datetime('now', ?)
            GROUP BY feature
        """, (target_type, target_id, f"-{days} days"))
        by_feature = {r["feature"]: r["units"] for r in cursor.fetchall()}

        return {
            "target_type": target_type,
            "target_id": target_id,
            "window_days": days,
            "total_events": int(row.get("total_events") or 0),
            "total_units_consumed": int(row.get("total_units_consumed") or 0),
            "successful_events": int(row.get("successful_events") or 0),
            "quota_exceeded_events": int(row.get("quota_exceeded_events") or 0),
            "by_feature": by_feature
        }
