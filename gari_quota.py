"""
GARI AI LAB — Centralized Quota & Usage Management System (gari_quota.py)
Sprint 1: Productization & Core Architecture Refactor

Enforces:
- Single Source of Truth via gari_plans.PRODUCT_PLANS
- Atomic SQLite + threading.Lock deduction (no race conditions)
- Clean unlimited representation (is_unlimited: True, quota_limit: None, NO magic 999999)
- Non-deduction on validation rejection or inference failure
- Human-friendly Vietnamese time formatting and status messages
- Entitlement resolution supporting User, Org, and Subscription tiers
"""

import logging
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import gari_plans

logger = logging.getLogger("gari_quota")

# -----------------------------------------------------------------------------
# SINGLE SOURCE OF TRUTH CONFIGURATION (Synced with gari_plans)
# -----------------------------------------------------------------------------
QUOTA_CONFIG = {
    # Free tier: 5 classifications per 24-hour cycle
    "free_tier_quota": gari_plans.PRODUCT_PLANS["free"]["quota_limit"],
    # Refresh period: 24 hours
    "refresh_period_hours": 24,
    # Guest / unauthenticated tier (tracked per IP): 3 turns per 24 hours
    "guest_tier_quota": gari_plans.PRODUCT_PLANS["guest"]["quota_limit"],
    # Personal tier: 150 turns per 24 hours
    "personal_tier_quota": gari_plans.PRODUCT_PLANS["personal"]["quota_limit"],
    # Business tier: 800 turns per 24 hours
    "business_tier_quota": gari_plans.PRODUCT_PLANS["business"]["quota_limit"],
    # Legacy aliases for compatibility
    "pro_tier_quota": gari_plans.PRODUCT_PLANS["pro"]["quota_limit"],
    "team_tier_quota": gari_plans.PRODUCT_PLANS["team"]["quota_limit"],
}

DB_PATH = Path(__file__).resolve().parent / "database" / "disease_detector.db"
_QUOTA_LOCK = threading.RLock()


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_quota_database() -> None:
    """Ensure user_quotas table exists with proper indexes."""
    with _QUOTA_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_quotas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_identifier TEXT UNIQUE NOT NULL,
                user_id INTEGER,
                quota_limit INTEGER NOT NULL,
                used_count INTEGER DEFAULT 0,
                cycle_start DATETIME NOT NULL,
                cycle_end DATETIME NOT NULL,
                last_used_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_quotas_client ON user_quotas(client_identifier);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_quotas_user ON user_quotas(user_id);")
            conn.commit()


# Initialize table on module import
init_quota_database()


def is_vip_account(
    user: Optional[Dict[str, Any]], 
    dev_pro_header: bool = False,
    org_id: Optional[int] = None
) -> bool:
    """
    Authoritative VIP verification using unified product entitlement engine.
    Checks user personal subscription, org plan, and legacy VIP markers.
    """
    entitlement = gari_plans.resolve_user_entitlement(
        user, 
        org_id=org_id, 
        allow_dev_header=dev_pro_header
    )
    return bool(entitlement.get("has_vip_models", False))


def format_vietnamese_relative_time(target_dt: datetime) -> str:
    """Formats human-friendly Vietnamese time string for quota refresh."""
    now = datetime.now(timezone.utc)
    diff = target_dt - now
    total_seconds = int(diff.total_seconds())
    if total_seconds <= 0:
        return "ngay bây giờ"

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    if hours > 0:
        return f"{hours} giờ {minutes} phút"
    elif minutes > 0:
        return f"{minutes} phút"
    else:
        return f"{total_seconds} giây"


def format_vietnamese_datetime(dt: datetime) -> str:
    """Format datetime into standard Vietnamese readable format."""
    vn_dt = dt.astimezone(timezone(timedelta(hours=7)))
    return vn_dt.strftime("%H:%M ngày %d/%m/%Y")


def get_client_identifier(
    user: Optional[Dict[str, Any]], 
    ip_address: Optional[str] = None,
    client_override: Optional[str] = None
) -> Tuple[str, Optional[int]]:
    """Generates unique client identifier for quota tracking."""
    if user and user.get("id"):
        return f"user_{user['id']}", user["id"]
    if client_override:
        return f"client_{client_override.strip()}", None
    clean_ip = (ip_address or "127.0.0.1").strip()
    return f"guest_{clean_ip}", None


def get_or_create_quota_record(
    client_id: str,
    user_id: Optional[int] = None,
    is_vip: bool = False,
    user: Optional[Dict[str, Any]] = None,
    org_id: Optional[int] = None,
    dev_pro_header: bool = False
) -> Dict[str, Any]:
    """
    Retrieve or initialize user quota record with auto-refresh if cycle has expired.
    Uses -1 in SQLite to denote true unlimited quota (avoiding magic numbers like 999999).
    """
    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.strftime("%Y-%m-%d %H:%M:%S")

    # Fetch user if not provided but user_id is known
    if not user and user_id:
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, email, name, account_type FROM users WHERE id = ?", (user_id,))
                row = cursor.fetchone()
                if row:
                    user = dict(row)
        except Exception:
            pass

    # Resolve entitlement to get exact plan quota limit
    entitlement = gari_plans.resolve_user_entitlement(
        user, 
        org_id=org_id, 
        allow_dev_header=dev_pro_header
    )
    is_unlimited = entitlement.get("is_unlimited_quota", False)
    plan_limit = entitlement.get("quota_limit")

    if is_unlimited:
        limit = -1
    elif plan_limit is not None:
        limit = plan_limit
    elif is_vip:
        limit = QUOTA_CONFIG["pro_tier_quota"]
    elif user_id is not None:
        limit = QUOTA_CONFIG["free_tier_quota"]
    else:
        limit = QUOTA_CONFIG["guest_tier_quota"]

    with _QUOTA_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM user_quotas WHERE client_identifier = ?",
                (client_id,)
            )
            row = cursor.fetchone()

            if not row:
                cycle_end = now_utc + timedelta(hours=QUOTA_CONFIG["refresh_period_hours"])
                cycle_end_iso = cycle_end.strftime("%Y-%m-%d %H:%M:%S")

                cursor.execute("""
                INSERT INTO user_quotas (client_identifier, user_id, quota_limit, used_count, cycle_start, cycle_end)
                VALUES (?, ?, ?, 0, ?, ?)
                """, (client_id, user_id, limit, now_iso, cycle_end_iso))
                conn.commit()

                cursor.execute("SELECT * FROM user_quotas WHERE client_identifier = ?", (client_id,))
                row = cursor.fetchone()

            record = dict(row)

            # Check if cycle expired -> refresh quota
            try:
                cycle_end_dt = datetime.strptime(record["cycle_end"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except Exception:
                cycle_end_dt = now_utc + timedelta(hours=24)

            if now_utc >= cycle_end_dt:
                new_cycle_end = now_utc + timedelta(hours=QUOTA_CONFIG["refresh_period_hours"])
                new_cycle_end_iso = new_cycle_end.strftime("%Y-%m-%d %H:%M:%S")

                cursor.execute("""
                UPDATE user_quotas
                SET used_count = 0,
                    quota_limit = ?,
                    cycle_start = ?,
                    cycle_end = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """, (limit, now_iso, new_cycle_end_iso, record["id"]))
                conn.commit()

                record["used_count"] = 0
                record["quota_limit"] = limit
                record["cycle_start"] = now_iso
                record["cycle_end"] = new_cycle_end_iso

            # Update limit if tier changed (e.g. upgraded to Pro/VIP/Enterprise)
            if record["quota_limit"] != limit:
                cursor.execute(
                    "UPDATE user_quotas SET quota_limit = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (limit, record["id"])
                )
                conn.commit()
                record["quota_limit"] = limit

            record["_entitlement"] = entitlement
            return record


def get_quota_status(
    client_id: str,
    user_id: Optional[int] = None,
    is_vip: bool = False,
    user: Optional[Dict[str, Any]] = None,
    org_id: Optional[int] = None,
    dev_pro_header: bool = False
) -> Dict[str, Any]:
    """
    Calculate remaining quota and return structured metadata.
    Does NOT use 999999:
    - If unlimited (enterprise): remaining is None, is_unlimited is True
    - If VIP with limit (pro: 150, team: 800): displays remaining accurately
    """
    record = get_or_create_quota_record(
        client_id, 
        user_id=user_id, 
        is_vip=is_vip, 
        user=user, 
        org_id=org_id, 
        dev_pro_header=dev_pro_header
    )
    entitlement = record.get("_entitlement") or gari_plans.resolve_user_entitlement(user, org_id=org_id, allow_dev_header=dev_pro_header)
    
    used = record["used_count"]
    limit = record["quota_limit"]

    is_unlimited = (limit == -1) or entitlement.get("is_unlimited_quota", False)
    has_vip_models = entitlement.get("has_vip_models", False) or is_vip

    try:
        cycle_end_dt = datetime.strptime(record["cycle_end"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception:
        cycle_end_dt = datetime.now(timezone.utc) + timedelta(hours=24)

    relative_time = format_vietnamese_relative_time(cycle_end_dt)
    formatted_end = format_vietnamese_datetime(cycle_end_dt)

    if is_unlimited:
        remaining = None
        remaining_display = "Không giới hạn"
        limit_val = None
        limit_display = "Không giới hạn"
        can_classify = True
        msg = f"{entitlement.get('plan_name', 'Gói Nâng Cao')} — Không giới hạn lượt phân loại."
        exhausted_msg = None
    elif has_vip_models:
        limit_val = limit
        limit_display = str(limit)
        remaining = max(0, limit - used)
        remaining_display = str(remaining)
        can_classify = True  # VIP users are never blocked from classification
        if remaining > 0:
            msg = f"{entitlement.get('plan_name', 'Tài khoản VIP')} — Bạn còn {remaining}/{limit} lượt phân loại hôm nay. Làm mới sau {relative_time} ({formatted_end})."
            exhausted_msg = None
        else:
            msg = f"Tài khoản của bạn đã dùng hết hạn ngạch {limit} lượt trong ngày. Lượt tiếp theo sẽ được cấp lại vào {formatted_end}."
            exhausted_msg = f"Tài khoản của bạn đã dùng hết {limit} lượt phân loại. Lượt tiếp theo sẽ được cấp lại vào {formatted_end}."
    else:
        limit_val = limit
        limit_display = str(limit)
        remaining = max(0, limit - used)
        remaining_display = str(remaining)
        can_classify = remaining > 0
        if remaining > 0:
            msg = f"Bạn còn {remaining}/{limit} lượt phân loại miễn phí. Làm mới sau {relative_time} ({formatted_end})."
            exhausted_msg = None
        else:
            msg = f"Bạn đã dùng hết {limit} lượt phân loại miễn phí. Lượt tiếp theo sẽ được cấp lại vào {formatted_end} (sau {relative_time})."
            exhausted_msg = f"Bạn đã dùng hết lượt phân loại miễn phí. Lượt tiếp theo sẽ được cấp lại vào {formatted_end}."

    return {
        "is_vip": has_vip_models,
        "is_unlimited": is_unlimited,
        "plan_id": entitlement.get("plan_id", "free" if user_id else "guest"),
        "plan_name": entitlement.get("plan_name", "Miễn phí"),
        "quota_limit": limit_val,
        "quota_limit_display": limit_display,
        "used_count": used,
        "remaining": remaining,
        "remaining_display": remaining_display,
        "cycle_end": record["cycle_end"],
        "cycle_end_formatted": formatted_end,
        "resets_in_human": relative_time,
        "message_vi": msg,
        "exhausted_message_vi": exhausted_msg,
        "can_classify": can_classify,
        "entitlement": {
            "source": entitlement.get("source"),
            "allowed_models": entitlement.get("allowed_models", []),
            "has_vip_models": has_vip_models,
            "has_api_access": entitlement.get("has_api_access", False),
            "subscription_status": entitlement.get("subscription_status", "active")
        },
        "config": {
            "free_tier_quota": QUOTA_CONFIG["free_tier_quota"],
            "refresh_period_hours": QUOTA_CONFIG["refresh_period_hours"]
        }
    }


def check_quota_pre_flight(
    client_id: str,
    user_id: Optional[int] = None,
    is_vip: bool = False,
    user: Optional[Dict[str, Any]] = None,
    org_id: Optional[int] = None,
    dev_pro_header: bool = False
) -> Tuple[bool, Dict[str, Any]]:
    """
    Check if user has quota before running inference.
    Does NOT deduct turns. Returns (can_proceed, quota_info).
    """
    status = get_quota_status(
        client_id, 
        user_id=user_id, 
        is_vip=is_vip, 
        user=user, 
        org_id=org_id, 
        dev_pro_header=dev_pro_header
    )
    return status["can_classify"], status


def deduct_quota_atomic(
    client_id: str,
    user_id: Optional[int] = None,
    is_vip: bool = False,
    user: Optional[Dict[str, Any]] = None,
    org_id: Optional[int] = None,
    dev_pro_header: bool = False
) -> Dict[str, Any]:
    """
    Atomically deduct exactly 1 turn upon successful classification.
    Protected by threading.Lock and SQLite constraints.
    Does NOT deduct when unlimited or when limit is reached.
    """
    record = get_or_create_quota_record(
        client_id, 
        user_id=user_id, 
        is_vip=is_vip, 
        user=user, 
        org_id=org_id, 
        dev_pro_header=dev_pro_header
    )
    limit = record["quota_limit"]

    with _QUOTA_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if limit == -1:
                # Unlimited tier: simply increment usage counter for analytics
                cursor.execute("""
                UPDATE user_quotas
                SET used_count = used_count + 1,
                    last_used_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE client_identifier = ?
                """, (client_id,))
                conn.commit()
            else:
                # Metered tier: only increment if used_count < quota_limit
                cursor.execute("""
                UPDATE user_quotas
                SET used_count = used_count + 1,
                    last_used_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE client_identifier = ? AND used_count < quota_limit
                """, (client_id,))
                conn.commit()

                if cursor.rowcount == 0:
                    logger.warning("Quota deduction rejected: limit already reached for client %s", client_id)

    return get_quota_status(
        client_id, 
        user_id=user_id, 
        is_vip=is_vip, 
        user=user, 
        org_id=org_id, 
        dev_pro_header=dev_pro_header
    )


def reset_quota_for_test(client_id: str, custom_used: int = 0) -> Dict[str, Any]:
    """Test helper to reset or configure a specific quota level for automated tests."""
    with _QUOTA_LOCK:
        get_or_create_quota_record(client_id)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE user_quotas
            SET used_count = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE client_identifier = ?
            """, (custom_used, client_id))
            conn.commit()
    return get_or_create_quota_record(client_id)
