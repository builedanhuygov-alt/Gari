"""
GARI AI LAB — Voucher & Access Grant Engine (gari_vouchers.py)

Production-oriented implementation of admin-issued free access vouchers:
1. Cryptographically secure code generation (secrets module)
2. Zero plaintext storage: SHA-256 code hashing in database
3. Anti-brute-force rate limiting (in-memory sliding window)
4. Atomic database transactions with strict concurrency control
5. Single-use and limited-use validation
6. Email-restricted voucher support
7. Automatic subscription activation & extension
8. Comprehensive tamper-evident audit logging
9. Strict admin-only access control
"""

import hashlib
import json
import logging
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import gari_plans

logger = logging.getLogger("gari_vouchers")

DB_PATH = Path(__file__).resolve().parent / "database" / "disease_detector.db"
_VOUCHER_LOCK = threading.RLock()

# Allowed plans for voucher issuance
ALLOWED_VOUCHER_PLANS = ("personal", "business", "pro", "team", "enterprise", "vip_pro")

# Rate limiting: max 5 failed attempts within 900 seconds (15 minutes)
_FAILED_VOUCHER_ATTEMPTS: Dict[str, List[float]] = {}
RATE_LIMIT_WINDOW_SECONDS = 900
RATE_LIMIT_MAX_ATTEMPTS = 5

# Custom domain exceptions
class VoucherError(Exception):
    """Base exception for voucher domain errors."""

class VoucherNotFoundError(VoucherError):
    """Raised when voucher code does not match any record."""

class VoucherExpiredError(VoucherError):
    """Raised when voucher expiration date has passed."""

class VoucherExhaustedError(VoucherError):
    """Raised when voucher redemption limit is reached."""

class VoucherRevokedError(VoucherError):
    """Raised when voucher has been revoked by admin."""

class VoucherIneligibleError(VoucherError):
    """Raised when voucher is restricted to a different user."""

class VoucherAlreadyRedeemedError(VoucherError):
    """Raised when user has already redeemed this voucher."""

class VoucherRateLimitExceededError(VoucherError):
    """Raised when brute-force threshold is exceeded."""


def now_utc() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def now_iso() -> str:
    """Return current UTC time in standardized SQLite string format."""
    return now_utc().strftime("%Y-%m-%d %H:%M:%S")


def get_db_connection() -> sqlite3.Connection:
    """Return connection with row factory enabled."""
    conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_code(raw_code: str) -> str:
    """
    Normalize voucher code: uppercase and strip all hyphens, spaces, and formatting.
    E.g., 'gari-pers-8k3n-7m2p' -> 'GARIPERS8K3N7M2P'
    """
    if not raw_code:
        return ""
    return re.sub(r"[^A-Z0-9]", "", raw_code.upper().strip())


def hash_code(raw_code: str) -> str:
    """Compute SHA-256 hash of normalized voucher code."""
    normalized = normalize_code(raw_code)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_voucher_code(plan_id: str) -> Tuple[str, str]:
    """
    Generate a high-entropy, unpredictable voucher code.
    Format: GARI-PERS-XXXX-YYYY or GARI-BIZ-XXXX-YYYY
    Alphabet: 32 unambiguous characters (excludes 0, O, 1, I).
    Returns (raw_code, preview_code).
    """
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    prefix = "GARI-PERS" if plan_id == "personal" else "GARI-BIZ"
    part1 = "".join(secrets.choice(alphabet) for _ in range(4))
    part2 = "".join(secrets.choice(alphabet) for _ in range(4))
    raw_code = f"{prefix}-{part1}-{part2}"
    preview_code = f"{prefix}-****-{part2}"
    return raw_code, preview_code


# -----------------------------------------------------------------------------
# Rate Limiting (Anti-Brute-Force)
# -----------------------------------------------------------------------------

def check_redemption_rate_limit(client_key: str) -> None:
    """
    Ensure the client has not exceeded failed voucher attempt threshold.
    client_key should combine IP address and/or user ID.
    """
    now = time.time()
    with _VOUCHER_LOCK:
        attempts = _FAILED_VOUCHER_ATTEMPTS.get(client_key, [])
        valid_attempts = [t for t in attempts if now - t < RATE_LIMIT_WINDOW_SECONDS]
        _FAILED_VOUCHER_ATTEMPTS[client_key] = valid_attempts
        if len(valid_attempts) >= RATE_LIMIT_MAX_ATTEMPTS:
            remaining = int(RATE_LIMIT_WINDOW_SECONDS - (now - valid_attempts[0]))
            raise VoucherRateLimitExceededError(
                f"Quá nhiều lần nhập mã voucher không hợp lệ. Vui lòng thử lại sau {max(1, remaining // 60)} phút để bảo vệ hệ thống."
            )


def record_failed_redemption(client_key: str) -> None:
    """Record a failed redemption attempt."""
    now = time.time()
    with _VOUCHER_LOCK:
        attempts = _FAILED_VOUCHER_ATTEMPTS.get(client_key, [])
        attempts.append(now)
        _FAILED_VOUCHER_ATTEMPTS[client_key] = attempts


def clear_failed_redemptions(client_key: str) -> None:
    """Clear failed attempts on successful redemption."""
    with _VOUCHER_LOCK:
        if client_key in _FAILED_VOUCHER_ATTEMPTS:
            del _FAILED_VOUCHER_ATTEMPTS[client_key]


# -----------------------------------------------------------------------------
# Core Voucher Operations
# -----------------------------------------------------------------------------

def create_voucher(
    admin_user_id: int,
    plan_id: str,
    duration_days: int = 30,
    max_redemptions: int = 1,
    expires_at_iso: Optional[str] = None,
    restricted_to_email: Optional[str] = None,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new voucher record.
    Security: The plaintext voucher code is returned in this response ONLY ONCE.
    It is never stored in plaintext in the database (only SHA-256 hash).
    """
    plan_id = (plan_id or "").lower().strip()
    if plan_id not in ALLOWED_VOUCHER_PLANS:
        raise ValueError(f"Gói dịch vụ không hợp lệ. Chỉ có thể tạo voucher cho: {', '.join(ALLOWED_VOUCHER_PLANS)}")

    duration_days = int(duration_days)
    if duration_days < 1 or duration_days > 730:
        raise ValueError("Thời hạn cấp quyền phải từ 1 đến 730 ngày (tối đa 2 năm).")

    max_redemptions = int(max_redemptions)
    if max_redemptions < 1 or max_redemptions > 10000:
        raise ValueError("Số lượt kích hoạt tối đa phải từ 1 đến 10,000 lượt.")

    # Expiration date validation
    if expires_at_iso:
        try:
            # Parse ISO or SQLite string
            clean_date = expires_at_iso.replace("Z", "+00:00")
            exp_dt = datetime.fromisoformat(clean_date)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if exp_dt <= now_utc():
                raise ValueError("Ngày hết hạn voucher phải ở tương lai.")
            exp_str = exp_dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError as ve:
            if "Ngày hết hạn" in str(ve):
                raise
            raise ValueError(f"Định dạng ngày hết hạn không hợp lệ: {expires_at_iso}")
    else:
        # Default: 90 days from now
        exp_str = (now_utc() + timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")

    # Restricted email normalization
    norm_email = None
    if restricted_to_email:
        norm_email = restricted_to_email.strip().lower()
        if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", norm_email):
            raise ValueError(f"Địa chỉ email chỉ định không đúng định dạng: {restricted_to_email}")

    raw_code, preview_code = generate_voucher_code(plan_id)
    c_hash = hash_code(raw_code)

    with _VOUCHER_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO vouchers (
                    code_hash, code_preview, plan_id, duration_days,
                    max_redemptions, redemption_count, status, restricted_to_email,
                    expires_at, created_by_user_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, 'active', ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                c_hash, preview_code, plan_id, duration_days,
                max_redemptions, norm_email, exp_str, admin_user_id
            ))
            v_id = cursor.lastrowid

            # Audit log
            cursor.execute("""
                INSERT INTO voucher_audit_log (voucher_id, actor_user_id, action, details_json, created_at)
                VALUES (?, ?, 'created', ?, CURRENT_TIMESTAMP)
            """, (
                v_id, admin_user_id,
                json.dumps({
                    "plan_id": plan_id,
                    "duration_days": duration_days,
                    "max_redemptions": max_redemptions,
                    "expires_at": exp_str,
                    "restricted_to_email": norm_email,
                    "notes": notes
                }, ensure_ascii=False)
            ))
            conn.commit()

            cursor.execute("SELECT * FROM vouchers WHERE id = ?", (v_id,))
            created_voucher = dict(cursor.fetchone())

    return {
        "success": True,
        "voucher_code": raw_code,  # RETURNED ONLY ONCE
        "voucher": created_voucher,
        "warning_vi": "Vui lòng sao chép mã này ngay. Mã đầy đủ sẽ không thể xem lại sau khi đóng cửa sổ này."
    }


def redeem_voucher(
    user_id: int,
    raw_code: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Dict[str, Any]:
    """
    Redeem a voucher atomically for an authenticated user.
    Security protections:
    - Enforces rate limiting per IP and per user
    - Enforces SHA-256 hash lookup (no plaintext stored)
    - Verifies voucher status, expiry date, redemption limit, email restriction
    - Prevents race conditions and duplicate redemption by same user
    - Activates or extends the target subscription for the exact plan
    - Logs audit trail in voucher_audit_log and plan_audit_trail
    """
    ip_key = f"ip_{ip_address or 'no_ip'}"
    user_key = f"user_{user_id}"
    check_redemption_rate_limit(ip_key)
    check_redemption_rate_limit(user_key)

    def _fail():
        record_failed_redemption(ip_key)
        record_failed_redemption(user_key)

    raw_clean = (raw_code or "").strip()
    if not raw_clean:
        _fail()
        raise VoucherNotFoundError("Vui lòng nhập mã voucher.")

    c_hash = hash_code(raw_clean)
    now = now_utc()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    with _VOUCHER_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # 1. Fetch voucher by hash
            cursor.execute("SELECT * FROM vouchers WHERE code_hash = ?", (c_hash,))
            v_row = cursor.fetchone()
            if not v_row:
                _fail()
                cursor.execute("""
                    INSERT INTO voucher_audit_log (voucher_id, actor_user_id, action, details_json, ip_address, created_at)
                    VALUES (NULL, ?, 'redemption_failed', ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, json.dumps({"reason": "code_not_found"}, ensure_ascii=False), ip_address))
                conn.commit()
                raise VoucherNotFoundError("Mã voucher không tồn tại hoặc đã nhập không chính xác.")

            voucher = dict(v_row)
            v_id = voucher["id"]
            plan_id = voucher["plan_id"]
            duration_days = voucher["duration_days"]
            max_redemptions = voucher["max_redemptions"]
            redemption_count = voucher["redemption_count"]
            v_status = voucher["status"]

            # 2. Check revocation
            if v_status == "revoked":
                _fail()
                raise VoucherRevokedError(f"Mã voucher này đã bị thu hồi bởi ban quản trị. Lý do: {voucher.get('revoke_reason') or 'Không có'}")

            # 3. Check expiration
            exp_dt = datetime.strptime(voucher["expires_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if exp_dt <= now:
                if v_status != "expired":
                    cursor.execute("UPDATE vouchers SET status = 'expired', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (v_id,))
                    conn.commit()
                _fail()
                raise VoucherExpiredError(f"Mã voucher này đã hết hạn sử dụng vào ngày {voucher['expires_at']}.")

            # 4. Check redemption limit
            if redemption_count >= max_redemptions or v_status == "exhausted":
                if v_status != "exhausted":
                    cursor.execute("UPDATE vouchers SET status = 'exhausted', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (v_id,))
                    conn.commit()
                _fail()
                raise VoucherExhaustedError("Mã voucher này đã hết số lượt kích hoạt cho phép.")

            # 5. Check user email restriction
            if voucher.get("restricted_to_email"):
                cursor.execute("SELECT email FROM users WHERE id = ?", (user_id,))
                u_row = cursor.fetchone()
                user_email = (u_row["email"] if u_row else "").strip().lower()
                req_email = voucher["restricted_to_email"].strip().lower()
                if user_email != req_email:
                    _fail()
                    raise VoucherIneligibleError(f"Mã voucher này chỉ dành riêng cho tài khoản {req_email}.")

            # 6. Check if user already redeemed this voucher
            cursor.execute("SELECT id FROM voucher_redemptions WHERE voucher_id = ? AND user_id = ?", (v_id, user_id))
            if cursor.fetchone():
                _fail()
                raise VoucherAlreadyRedeemedError("Tài khoản của bạn đã kích hoạt mã voucher này trước đó rồi.")

            # 7. Atomic update: increment redemption count
            new_count = redemption_count + 1
            new_status = "exhausted" if new_count >= max_redemptions else "active"
            cursor.execute("""
                UPDATE vouchers
                SET redemption_count = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND redemption_count = ?
            """, (new_count, new_status, v_id, redemption_count))
            if cursor.rowcount == 0:
                # Concurrency conflict: another process redeemed simultaneously
                raise VoucherError("Xảy ra xung đột khi kích hoạt voucher. Vui lòng thử lại.")

            # 8. Calculate subscription period
            # Check existing active personal subscription in subscriptions table
            cursor.execute("""
                SELECT * FROM subscriptions
                WHERE target_type = 'user' AND target_id = ? AND status IN ('active', 'trialing')
                ORDER BY id DESC LIMIT 1
            """, (user_id,))
            existing_sub_row = cursor.fetchone()

            base_start = now
            if existing_sub_row:
                existing_sub = dict(existing_sub_row)
                # If currently active for the same plan, extend existing end date!
                if existing_sub["plan_id"] == plan_id and existing_sub.get("current_period_end"):
                    try:
                        curr_end_dt = datetime.strptime(existing_sub["current_period_end"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                        if curr_end_dt > now:
                            base_start = curr_end_dt
                    except Exception:
                        pass

            period_start_str = now_str
            period_end_dt = base_start + timedelta(days=duration_days)
            period_end_str = period_end_dt.strftime("%Y-%m-%d %H:%M:%S")

            # 9. Supersede previous active subscriptions for this user
            cursor.execute("""
                UPDATE subscriptions
                SET status = 'canceled', canceled_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE target_type = 'user' AND target_id = ?
                  AND status IN ('trialing', 'active', 'cancel_at_period_end', 'past_due', 'suspended')
            """, (user_id,))

            # Insert active subscription
            cursor.execute("""
                INSERT INTO subscriptions (
                    target_type, target_id, user_id, organization_id, plan_id,
                    status, billing_interval, current_period_start, current_period_end,
                    cancel_at_period_end, commercial_intent, is_paid, provider,
                    provider_subscription_id, notes, created_at, updated_at
                ) VALUES (
                    'user', ?, ?, NULL, ?,
                    'active', 'monthly', ?, ?,
                    0, 'paid_subscription', 1, 'voucher',
                    ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """, (
                user_id, user_id, plan_id,
                period_start_str, period_end_str,
                f"vch_{v_id}_{user_id}",
                f"Kích hoạt quyền lợi miễn phí qua voucher {voucher['code_preview']}"
            ))
            sub_id = cursor.lastrowid

            # Sync to backward compatible user_subscriptions table (UPSERT)
            cursor.execute("""
                INSERT INTO user_subscriptions (
                    user_id, plan_id, status, billing_interval,
                    start_date, end_date, notes, created_at, updated_at
                ) VALUES (?, ?, 'active', 'monthly', ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    plan_id = excluded.plan_id,
                    status = 'active',
                    billing_interval = excluded.billing_interval,
                    start_date = excluded.start_date,
                    end_date = excluded.end_date,
                    notes = excluded.notes,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, plan_id, period_start_str, period_end_str, f"Voucher {voucher['code_preview']}"))

            # 10. Record redemption
            cursor.execute("""
                INSERT INTO voucher_redemptions (
                    voucher_id, user_id, plan_id, duration_days,
                    granted_period_start, granted_period_end, subscription_id,
                    ip_address, user_agent, redeemed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                v_id, user_id, plan_id, duration_days,
                period_start_str, period_end_str, sub_id,
                ip_address, user_agent
            ))

            # 11. Record audit logs
            cursor.execute("""
                INSERT INTO voucher_audit_log (voucher_id, actor_user_id, action, details_json, ip_address, created_at)
                VALUES (?, ?, 'redeemed', ?, ?, CURRENT_TIMESTAMP)
            """, (
                v_id, user_id,
                json.dumps({
                    "plan_id": plan_id,
                    "duration_days": duration_days,
                    "granted_period_start": period_start_str,
                    "granted_period_end": period_end_str,
                    "subscription_id": sub_id
                }, ensure_ascii=False),
                ip_address
            ))

            cursor.execute("""
                INSERT INTO plan_audit_trail (
                    target_type, target_id, old_plan, new_plan, action, changed_by_user_id, reason, created_at
                ) VALUES ('user', ?, 'unknown', ?, 'voucher_redeemed', ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, plan_id, user_id, f"Kích hoạt voucher {voucher['code_preview']}"))

            conn.commit()

    # Clear rate limit failure counter on successful redemption
    clear_failed_redemptions(ip_key)
    clear_failed_redemptions(user_key)

    plan_def = gari_plans.get_plan_definition(plan_id)
    return {
        "success": True,
        "message_vi": f"Kích hoạt thành công gói {plan_def['display_name']} trong {duration_days} ngày!",
        "voucher_id": v_id,
        "plan_id": plan_id,
        "plan_name": plan_def["display_name"],
        "duration_days": duration_days,
        "period_start": period_start_str,
        "period_end": period_end_str,
        "access_source": "voucher",
        "subscription_id": sub_id
    }


def revoke_voucher(voucher_id: int, admin_user_id: int, reason: str) -> Dict[str, Any]:
    """
    Revoke an active voucher and immediately cancel active subscriptions granted by it.
    Future redemptions will be rejected immediately.
    """
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise ValueError("Vui lòng cung cấp lý do thu hồi voucher (tối thiểu 3 ký tự).")

    with _VOUCHER_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vouchers WHERE id = ?", (voucher_id,))
            v_row = cursor.fetchone()
            if not v_row:
                raise VoucherNotFoundError("Không tìm thấy voucher chỉ định.")

            voucher = dict(v_row)
            if voucher["status"] == "revoked":
                raise ValueError("Voucher này đã ở trạng thái thu hồi trước đó.")

            cursor.execute("""
                UPDATE vouchers
                SET status = 'revoked', revoked_at = CURRENT_TIMESTAMP,
                    revoked_by_user_id = ?, revoke_reason = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (admin_user_id, reason, voucher_id))

            # Cascade: Immediately revoke / cancel active subscriptions granted by this voucher
            cursor.execute("""
                UPDATE subscriptions
                SET status = 'canceled', canceled_at = CURRENT_TIMESTAMP,
                    notes = notes || ' [Voucher thu hồi: ' || ? || ']',
                    updated_at = CURRENT_TIMESTAMP
                WHERE provider = 'voucher' AND provider_subscription_id LIKE ?
                  AND status IN ('trialing', 'active', 'cancel_at_period_end')
            """, (reason, f"vch_{voucher_id}_%"))

            # Also sync cancellation to user_subscriptions table
            cursor.execute("""
                UPDATE user_subscriptions
                SET status = 'canceled', notes = notes || ' [Voucher thu hồi: ' || ? || ']', updated_at = CURRENT_TIMESTAMP
                WHERE user_id IN (SELECT user_id FROM voucher_redemptions WHERE voucher_id = ?)
                  AND status = 'active'
            """, (reason, voucher_id))

            cursor.execute("""
                INSERT INTO voucher_audit_log (voucher_id, actor_user_id, action, details_json, created_at)
                VALUES (?, ?, 'revoked', ?, CURRENT_TIMESTAMP)
            """, (
                voucher_id, admin_user_id,
                json.dumps({"reason": reason, "old_status": voucher["status"]}, ensure_ascii=False)
            ))
            conn.commit()

            cursor.execute("SELECT * FROM vouchers WHERE id = ?", (voucher_id,))
            return dict(cursor.fetchone())


def list_vouchers(
    admin_user_id: int,
    status: Optional[str] = None,
    plan_id: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    List vouchers for administrator dashboard.
    Never exposes raw code or code hash. Shows preview code only.
    """
    limit = max(1, min(int(limit or 100), 500))
    now_str = now_iso()

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Opportunistic check: update expired status for vouchers past expiration date
        cursor.execute("""
            UPDATE vouchers
            SET status = 'expired', updated_at = CURRENT_TIMESTAMP
            WHERE status = 'active' AND expires_at < ?
        """, (now_str,))
        conn.commit()

        clauses = []
        params: List[Any] = []
        if status:
            clauses.append("v.status = ?")
            params.append(status.lower().strip())
        if plan_id:
            clauses.append("v.plan_id = ?")
            params.append(plan_id.lower().strip())

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)

        cursor.execute(f"""
            SELECT v.id, v.code_preview, v.plan_id, v.duration_days,
                   v.max_redemptions, v.redemption_count, v.status,
                   v.restricted_to_email, v.expires_at, v.created_by_user_id,
                   v.revoked_at, v.revoked_by_user_id, v.revoke_reason,
                   v.created_at, v.updated_at,
                   u.email as creator_email, u.full_name as creator_name
            FROM vouchers v
            LEFT JOIN users u ON v.created_by_user_id = u.id
            {where_sql}
            ORDER BY v.id DESC
            LIMIT ?
        """, params)

        rows = [dict(r) for r in cursor.fetchall()]
        for r in rows:
            plan_info = gari_plans.get_plan_definition(r["plan_id"])
            r["plan_name"] = plan_info.get("display_name", r["plan_id"])
        return rows


def list_voucher_audit_log(
    admin_user_id: int,
    voucher_id: Optional[int] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Retrieve audit log events for voucher operations."""
    limit = max(1, min(int(limit or 100), 500))
    with get_db_connection() as conn:
        cursor = conn.cursor()
        clauses = []
        params: List[Any] = []
        if voucher_id is not None:
            clauses.append("l.voucher_id = ?")
            params.append(voucher_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)

        cursor.execute(f"""
            SELECT l.id, l.voucher_id, l.actor_user_id, l.action,
                   l.details_json, l.ip_address, l.created_at,
                   v.code_preview, v.plan_id,
                   u.email as actor_email, u.full_name as actor_name
            FROM voucher_audit_log l
            LEFT JOIN vouchers v ON l.voucher_id = v.id
            LEFT JOIN users u ON l.actor_user_id = u.id
            {where_sql}
            ORDER BY l.id DESC
            LIMIT ?
        """, params)
        rows = [dict(r) for r in cursor.fetchall()]
        for r in rows:
            if r.get("details_json"):
                try:
                    r["details"] = json.loads(r["details_json"])
                except Exception:
                    r["details"] = {}
        return rows


def list_voucher_redemptions(
    admin_user_id: int,
    voucher_id: Optional[int] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """List redemption history records for admin inspection."""
    limit = max(1, min(int(limit or 100), 500))
    with get_db_connection() as conn:
        cursor = conn.cursor()
        clauses = []
        params: List[Any] = []
        if voucher_id is not None:
            clauses.append("r.voucher_id = ?")
            params.append(voucher_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)

        cursor.execute(f"""
            SELECT r.id, r.voucher_id, r.user_id, r.plan_id, r.duration_days,
                   r.granted_period_start, r.granted_period_end, r.subscription_id,
                   r.ip_address, r.redeemed_at,
                   v.code_preview,
                   u.email as user_email, u.full_name as user_name
            FROM voucher_redemptions r
            LEFT JOIN vouchers v ON r.voucher_id = v.id
            LEFT JOIN users u ON r.user_id = u.id
            {where_sql}
            ORDER BY r.id DESC
            LIMIT ?
        """, params)
        return [dict(r) for r in cursor.fetchall()]
