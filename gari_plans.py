"""
GARI AI LAB — Centralized Product, Plans & Entitlements Engine (gari_plans.py)
Sprint 1: Startup Core & Productization
Single Source of Truth for:
- 5-Tier Product Architecture: Guest, Free, Pro, Team (Cooperative/Farm), Enterprise
- Plan Definitions & Feature Flags
- Entitlement Resolution (User & Organization)
- Subscription / Pilot Lifecycle States
- Safe Unlimited Quota representation (NO magic 999999)
- Audit Trail for Plan & Subscription modifications
"""

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("gari_plans")

DB_PATH = Path(__file__).resolve().parent / "database" / "disease_detector.db"
_PLANS_LOCK = threading.Lock()

import gari_config

# Production Security: All developer bypasses are permanently disabled.
ALLOW_DEV_PRO_BYPASS = False


# -----------------------------------------------------------------------------
# 1. UNIFIED PRODUCT & PLAN DEFINITIONS (Single Source of Truth)
# -----------------------------------------------------------------------------
# Price is None if unconfirmed or custom contract; price_status marks commercial readiness.
PRODUCT_PLANS: Dict[str, Dict[str, Any]] = {
    "guest": {
        "id": "guest",
        "plan_id": "guest",
        "display_name": "Dùng Thử Nhanh (Guest Trial)",
        "target_audience": "Người dùng vãng lai chưa tạo tài khoản",
        "description": "Trải nghiệm tức thì chẩn đoán bệnh lá cơ bản không cần đăng ký.",
        "billing_interval": "daily",
        "price": 0,
        "price_status": "free",
        "currency": "VND",
        "quota_limit": 3,
        "is_unlimited_quota": False,
        "refresh_hours": 24,
        "max_members": 1,
        "allowed_features": ["diagnosis_basic", "view_knowledge"],
        "allowed_models": ["standard_global", "crop_specific"],
        "has_vip_models": False,
        "has_api_access": False,
        "max_api_keys": 0,
        "can_export_data": False,
        "custom_branding": False,
        "is_active": True,
        "commercial_status": "Sẵn sàng sử dụng"
    },
    "free": {
        "id": "free",
        "plan_id": "free",
        "display_name": "Nông Hộ Cá Thể (Personal Free)",
        "target_audience": "Nông dân cá thể, người làm vườn gia đình",
        "description": "Theo dõi sức khỏe mùa vụ cơ bản và ghi nhật ký nông trại miễn phí.",
        "billing_interval": "daily",
        "price": 0,
        "price_status": "free",
        "currency": "VND",
        "quota_limit": 5,
        "is_unlimited_quota": False,
        "refresh_hours": 24,
        "max_members": 1,
        "allowed_features": ["diagnosis_basic", "farm_records", "data_export", "view_knowledge"],
        "allowed_models": ["standard_global", "crop_specific"],
        "has_vip_models": False,
        "has_api_access": False,
        "max_api_keys": 0,
        "can_export_data": True,
        "custom_branding": False,
        "is_active": True,
        "commercial_status": "Miễn phí trọn đời"
    },
    "personal": {
        "id": "personal",
        "plan_id": "personal",
        "display_name": "Cá nhân",
        "target_audience": "Kỹ sư nông học, khuyến nông cơ sở, chủ trang trại độc lập",
        "description": "Mở khóa toàn bộ mô hình VIP (Model 2 & Model 4) với hạn mức phân loại mở rộng dành cho cá nhân.",
        "billing_interval": "monthly",
        "price": 129000,
        "price_status": "active",
        "currency": "VND",
        "quota_limit": 150,
        "is_unlimited_quota": False,
        "refresh_hours": 24,
        "max_members": 1,
        "allowed_features": ["diagnosis_basic", "diagnosis_vip", "farm_records", "data_export", "view_knowledge", "priority_support"],
        "allowed_models": ["standard_global", "crop_specific", "pro_global", "vip_models"],
        "has_vip_models": True,
        "has_api_access": False,
        "max_api_keys": 0,
        "can_export_data": True,
        "custom_branding": False,
        "is_active": True,
        "commercial_status": "Sẵn sàng đăng ký"
    },
    "business": {
        "id": "business",
        "plan_id": "business",
        "display_name": "Doanh nghiệp",
        "target_audience": "Hợp tác xã nông nghiệp, trang trại vừa & nhỏ, đại lý vật tư BVTV, doanh nghiệp",
        "description": "Quản lý thành viên tập trung (tối đa 10 thành viên), phân quyền tổ chức, hạn ngạch chung và tích hợp API IoT.",
        "billing_interval": "monthly",
        "price": 299000,
        "price_status": "active",
        "currency": "VND",
        "quota_limit": 800,
        "is_unlimited_quota": False,
        "refresh_hours": 24,
        "max_members": 10,
        "allowed_features": ["diagnosis_basic", "diagnosis_vip", "farm_records", "data_export", "api_access", "team_management", "usage_metering", "priority_support"],
        "allowed_models": ["standard_global", "crop_specific", "pro_global", "vip_models"],
        "has_vip_models": True,
        "has_api_access": True,
        "max_api_keys": 5,
        "can_export_data": True,
        "custom_branding": False,
        "is_active": True,
        "commercial_status": "Sẵn sàng đăng ký"
    },
    "pro": {
        "id": "pro",
        "plan_id": "pro",
        "display_name": "Cá nhân (Pro)",
        "target_audience": "Kỹ sư nông học, khuyến nông cơ sở, chủ trang trại độc lập",
        "description": "Mở khóa toàn bộ mô hình VIP (Model 2 & Model 4) với hạn mức phân loại mở rộng.",
        "billing_interval": "monthly",
        "price": 129000,
        "price_status": "active",
        "currency": "VND",
        "quota_limit": 150,
        "is_unlimited_quota": False,
        "refresh_hours": 24,
        "max_members": 1,
        "allowed_features": ["diagnosis_basic", "diagnosis_vip", "farm_records", "data_export", "view_knowledge", "priority_support"],
        "allowed_models": ["standard_global", "crop_specific", "pro_global", "vip_models"],
        "has_vip_models": True,
        "has_api_access": False,
        "max_api_keys": 0,
        "can_export_data": True,
        "custom_branding": False,
        "is_active": True,
        "commercial_status": "Sẵn sàng đăng ký"
    },
    "team": {
        "id": "team",
        "plan_id": "team",
        "display_name": "Doanh nghiệp (Team)",
        "target_audience": "Hợp tác xã nông nghiệp, trang trại vừa & nhỏ, đại lý vật tư BVTV",
        "description": "Quản lý thành viên tập trung, phân quyền tổ chức, hạn ngạch chung và tích hợp API IoT.",
        "billing_interval": "monthly",
        "price": 299000,
        "price_status": "active",
        "currency": "VND",
        "quota_limit": 800,
        "is_unlimited_quota": False,
        "refresh_hours": 24,
        "max_members": 10,
        "allowed_features": ["diagnosis_basic", "diagnosis_vip", "farm_records", "data_export", "api_access", "team_management", "usage_metering", "priority_support"],
        "allowed_models": ["standard_global", "crop_specific", "pro_global", "vip_models"],
        "has_vip_models": True,
        "has_api_access": True,
        "max_api_keys": 5,
        "can_export_data": True,
        "custom_branding": False,
        "is_active": True,
        "commercial_status": "Sẵn sàng đăng ký"
    },
    "enterprise": {
        "id": "enterprise",
        "plan_id": "enterprise",
        "display_name": "Doanh Nghiệp & Đối Tác (Business / Enterprise)",
        "target_audience": "Tập đoàn nông nghiệp, đơn vị chế biến xuất khẩu, đối tác công nghệ",
        "description": "Hạn ngạch phân loại linh hoạt, không giới hạn thành viên, SLA cam kết 99.9%, hỗ trợ custom branding.",
        "billing_interval": "annual",
        "price": None,
        "price_status": "custom_contract",
        "price_display_note": "Liên hệ thỏa thuận hợp đồng giải pháp kỹ thuật riêng",
        "currency": "VND",
        "quota_limit": None, # None means true unlimited, NOT 999999
        "is_unlimited_quota": True,
        "refresh_hours": 24,
        "max_members": 1000,
        "allowed_features": ["diagnosis_basic", "diagnosis_vip", "farm_records", "data_export", "api_access", "team_management", "usage_metering", "custom_branding", "dedicated_weights"],
        "allowed_models": ["standard_global", "crop_specific", "pro_global", "vip_models", "custom_weights"],
        "has_vip_models": True,
        "has_api_access": True,
        "max_api_keys": 50,
        "can_export_data": True,
        "custom_branding": True,
        "is_active": True,
        "commercial_status": "Đàm phán theo hợp đồng B2B"
    },
    # Sprint 2: unpaid B2B pilot workspace. New organizations start here.
    # This is NOT a contract and can never be treated as a paid tier.
    "pilot": {
        "id": "pilot",
        "plan_id": "pilot",
        "display_name": "Không Gian Pilot Tổ Chức (Unpaid Pilot)",
        "target_audience": "Nông hộ liên kết, hợp tác xã, đại lý và doanh nghiệp đang thử nghiệm",
        "description": "Không gian miễn phí để hoàn tất onboarding, mời thành viên và đánh giá nhu cầu trước khi ký hợp đồng dịch vụ.",
        "billing_interval": "monthly",
        "price": 0,
        "price_status": "pilot_unpaid",
        "price_display_note": "Miễn phí trong giai đoạn pilot; không tự động trở thành hợp đồng trả phí.",
        "currency": "VND",
        "quota_limit": 50,
        "is_unlimited_quota": False,
        "refresh_hours": 24,
        "max_members": 10,
        "allowed_features": ["diagnosis_basic", "farm_records", "data_export", "team_management", "usage_metering", "view_knowledge"],
        "allowed_models": ["standard_global", "crop_specific"],
        "has_vip_models": False,
        "has_api_access": False,
        "max_api_keys": 0,
        "can_export_data": True,
        "custom_branding": False,
        "is_active": True,
        "commercial_status": "Pilot miễn phí — chưa phải hợp đồng dịch vụ"
    }
}


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_plans_database() -> None:
    """Initialize audit trail and subscription state tables."""
    with _PLANS_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Subscriptions table: tracks formal subscription/pilot state
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                plan_id TEXT NOT NULL,
                status TEXT NOT NULL, -- 'trial', 'pilot_active', 'active', 'pending_contract', 'expired', 'canceled'
                billing_interval TEXT NOT NULL,
                start_date DATETIME NOT NULL,
                end_date DATETIME,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """)

            # Entitlement & Plan Audit Trail table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS plan_audit_trail (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_type TEXT NOT NULL, -- 'user', 'organization'
                target_id INTEGER NOT NULL,
                old_plan TEXT,
                new_plan TEXT NOT NULL,
                action TEXT NOT NULL,      -- 'assigned', 'upgraded', 'downgraded', 'pilot_activated'
                changed_by_user_id INTEGER,
                reason TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # User Onboarding Profiles table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_onboarding_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                persona_type TEXT NOT NULL, -- 'individual', 'smallholder', 'cooperative', 'enterprise'
                primary_crops TEXT,        -- JSON list of crops e.g. ["Rice", "Tomato"]
                farming_region TEXT,       -- e.g. "Ba Vì, Hà Nội", "Tây Nguyên"
                farming_scale TEXT,        -- e.g. "Dưới 1 ha", "1-5 ha", "Trên 10 ha"
                onboarding_completed BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sub_uid ON user_subscriptions(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_target ON plan_audit_trail(target_type, target_id);")
            conn.commit()


# Initialize tables on module load
init_plans_database()


# -----------------------------------------------------------------------------
# 2. ENTITLEMENT RESOLUTION (User & Organization)
# -----------------------------------------------------------------------------

PLAN_ALIASES: Dict[str, str] = {
    "pro": "personal",
    "team": "business",
}

def get_plan_definition(plan_id: str) -> Dict[str, Any]:
    """Retrieve verified plan specification from centralized database engine."""
    try:
        import gari_entitlements
        return gari_entitlements.get_plan_definition(plan_id)
    except Exception:
        pid = (plan_id or "").lower().strip()
        canonical_id = PLAN_ALIASES.get(pid, pid)
        plan = PRODUCT_PLANS.get(canonical_id)
        if not plan:
            plan = PRODUCT_PLANS.get(pid, PRODUCT_PLANS["free"])
        return dict(plan)


def list_active_plans() -> List[Dict[str, Any]]:
    """List canonical active product plans for public catalog."""
    canonical_order = ["guest", "free", "personal", "business", "enterprise", "pilot"]
    seen = set()
    result = []
    for pid in canonical_order:
        p = PRODUCT_PLANS.get(pid)
        if p and p["is_active"] and pid not in seen:
            seen.add(pid)
            result.append(dict(p))
    return result


def get_user_subscription(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetch active subscription state for user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_subscriptions WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def _resolve_user_entitlement_raw(
    user: Optional[Dict[str, Any]],
    org_id: Optional[int] = None,
    allow_dev_header: bool = False
) -> Dict[str, Any]:
    """
    Authoritative resolution of a user's capabilities, quota, and VIP model access:
    1. Checks if operating under an Organization with an active Team or Enterprise plan.
    2. Checks user's authoritative personal subscription table.
    3. Falls back to Free Plan.
    Development header bypasses are permanently disabled for production security.
    """
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # 1. Guest / Unauthenticated
    if not user:
        guest_plan = PRODUCT_PLANS["guest"]
        return {
            "source": "guest_tier",
            "plan_id": "guest",
            "plan_name": guest_plan["display_name"],
            "has_vip_models": False,
            "has_api_access": False,
            "is_unlimited_quota": False,
            "quota_limit": guest_plan["quota_limit"],
            "allowed_models": guest_plan["allowed_models"],
            "allowed_features": guest_plan["allowed_features"],
            "subscription_status": "trial",
            "is_organization_sponsored": False,
            "is_pro": False,
            "can_create_organization": False
        }

    user_id = user["id"]

    # Import gari_revenue lazily to prevent circular imports
    try:
        import gari_revenue
    except ImportError:
        gari_revenue = None

    # 3. Organization Entitlement Inheritance
    # Only an ACTIVE organization may sponsor capabilities. Pending, suspended
    # and archived organizations never inherit VIP/API access (Sprint 2).
    if org_id:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT o.id, o.name, o.plan_id, o.status, om.role
                FROM organizations o
                JOIN organization_members om ON o.id = om.organization_id
                WHERE o.id = ? AND om.user_id = ?
            """, (org_id, user_id))
            org_row = cursor.fetchone()
            if org_row:
                org_status = (org_row["status"] or "").strip().lower()
                if org_status not in ("active", "enabled", "approved"):
                    return {
                        "source": "organization_inactive",
                        "organization_id": org_row["id"],
                        "organization_name": org_row["name"],
                        "organization_status": org_status or "pending",
                        "user_role": org_row["role"],
                        "plan_id": "pilot",
                        "plan_name": PRODUCT_PLANS["pilot"]["display_name"],
                        "has_vip_models": False,
                        "has_api_access": False,
                        "is_unlimited_quota": False,
                        "quota_limit": PRODUCT_PLANS["pilot"]["quota_limit"],
                        "allowed_models": PRODUCT_PLANS["pilot"]["allowed_models"],
                        "allowed_features": PRODUCT_PLANS["pilot"]["allowed_features"],
                        "subscription_status": "organization_inactive",
                        "is_organization_sponsored": False
                    }

                # Check authoritative organization subscription in revenue engine
                org_sub = None
                if gari_revenue:
                    org_sub = gari_revenue.get_active_subscription("organization", org_row["id"])

                if org_sub:
                    sub_status = org_sub.get("status")
                    if sub_status in ("active", "trialing", "cancel_at_period_end"):
                        # Entitled to subscription plan!
                        org_plan = get_plan_definition(org_sub["plan_id"])
                        return {
                            "source": "organization_subscription",
                            "organization_id": org_row["id"],
                            "organization_name": org_row["name"],
                            "organization_status": "active",
                            "user_role": org_row["role"],
                            "plan_id": org_plan["plan_id"],
                            "plan_name": org_plan["display_name"],
                            "has_vip_models": org_plan["has_vip_models"],
                            "has_api_access": org_plan["has_api_access"],
                            "is_unlimited_quota": org_plan["is_unlimited_quota"],
                            "quota_limit": org_plan["quota_limit"],
                            "allowed_models": org_plan["allowed_models"],
                            "allowed_features": org_plan["allowed_features"],
                            "subscription_status": sub_status,
                            "current_period_end": org_sub.get("current_period_end"),
                            "is_organization_sponsored": True
                        }
                    elif sub_status in ("expired", "canceled", "suspended", "past_due"):
                        # Subscription has expired/suspended: revoke paid privileges, fallback to pilot
                        pilot_plan = PRODUCT_PLANS["pilot"]
                        return {
                            "source": "organization_subscription_expired",
                            "organization_id": org_row["id"],
                            "organization_name": org_row["name"],
                            "organization_status": "active",
                            "user_role": org_row["role"],
                            "plan_id": "pilot",
                            "plan_name": pilot_plan["display_name"],
                            "has_vip_models": False,
                            "has_api_access": False,
                            "is_unlimited_quota": False,
                            "quota_limit": pilot_plan["quota_limit"],
                            "allowed_models": pilot_plan["allowed_models"],
                            "allowed_features": pilot_plan["allowed_features"],
                            "subscription_status": sub_status,
                            "is_organization_sponsored": True
                        }

                # Fallback to org table plan if no revenue subscription entry
                org_plan = get_plan_definition(org_row["plan_id"])
                return {
                    "source": "organization",
                    "organization_id": org_row["id"],
                    "organization_name": org_row["name"],
                    "organization_status": "active",
                    "user_role": org_row["role"],
                    "plan_id": org_plan["plan_id"],
                    "plan_name": org_plan["display_name"],
                    "has_vip_models": org_plan["has_vip_models"],
                    "has_api_access": org_plan["has_api_access"],
                    "is_unlimited_quota": org_plan["is_unlimited_quota"],
                    "quota_limit": org_plan["quota_limit"],
                    "allowed_models": org_plan["allowed_models"],
                    "allowed_features": org_plan["allowed_features"],
                    "subscription_status": "pilot_active",
                    "is_organization_sponsored": True
                }

    # 4. Personal Subscription in Revenue Engine
    user_rev_sub = None
    if gari_revenue:
        user_rev_sub = gari_revenue.get_active_subscription("user", user_id)

    if user_rev_sub:
        sub_status = user_rev_sub.get("status")
        if sub_status in ("active", "trialing", "cancel_at_period_end"):
            user_plan = get_plan_definition(user_rev_sub["plan_id"])
            access_source = "voucher" if user_rev_sub.get("provider") == "voucher" else "subscription"
            return {
                "source": "personal_subscription",
                "access_source": access_source,
                "plan_id": user_plan["plan_id"],
                "plan_name": user_plan["display_name"],
                "price": user_plan.get("price"),
                "currency": user_plan.get("currency", "VND"),
                "billing_interval": user_plan.get("billing_interval", "monthly"),
                "has_vip_models": user_plan["has_vip_models"],
                "has_api_access": user_plan["has_api_access"],
                "is_unlimited_quota": user_plan["is_unlimited_quota"],
                "quota_limit": user_plan["quota_limit"],
                "allowed_models": user_plan["allowed_models"],
                "allowed_features": user_plan["allowed_features"],
                "subscription_status": sub_status,
                "current_period_start": user_rev_sub.get("current_period_start"),
                "current_period_end": user_rev_sub.get("current_period_end"),
                "is_active": True,
                "is_organization_sponsored": False
            }
        elif sub_status in ("expired", "canceled", "suspended", "past_due"):
            # Explicitly expired/suspended personal subscription -> drop to free tier immediately!
            free_plan = PRODUCT_PLANS["free"]
            return {
                "source": "personal_subscription_expired",
                "access_source": "free",
                "plan_id": "free",
                "plan_name": free_plan["display_name"],
                "price": 0,
                "currency": "VND",
                "billing_interval": "daily",
                "has_vip_models": False,
                "has_api_access": False,
                "is_unlimited_quota": False,
                "quota_limit": free_plan["quota_limit"],
                "allowed_models": free_plan["allowed_models"],
                "allowed_features": free_plan["allowed_features"],
                "subscription_status": sub_status,
                "current_period_start": None,
                "current_period_end": None,
                "is_active": False,
                "is_organization_sponsored": False
            }

    # Legacy Personal Subscription Table (Backward Compatibility)
    sub = get_user_subscription(user_id)
    if sub:
        legacy_status = sub.get("status")
        # Check explicit end_date expiration on legacy table
        if legacy_status in ("active", "pilot_active", "trial") and sub.get("end_date"):
            try:
                raw_end = str(sub["end_date"])[:19].replace("T", " ")
                end_dt = datetime.strptime(raw_end, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) >= end_dt:
                    with get_db_connection() as conn:
                        conn.cursor().execute(
                            "UPDATE user_subscriptions SET status = 'expired', updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                            (user_id,)
                        )
                        conn.commit()
                    legacy_status = "expired"
            except Exception:
                pass

        if legacy_status in ("active", "pilot_active", "trial"):
            user_plan = get_plan_definition(sub["plan_id"])
            return {
                "source": "personal_subscription_legacy",
                "plan_id": user_plan["plan_id"],
                "plan_name": user_plan["display_name"],
                "has_vip_models": user_plan["has_vip_models"],
                "has_api_access": user_plan["has_api_access"],
                "is_unlimited_quota": user_plan["is_unlimited_quota"],
                "quota_limit": user_plan["quota_limit"],
                "allowed_models": user_plan["allowed_models"],
                "allowed_features": user_plan["allowed_features"],
                "subscription_status": legacy_status,
                "is_organization_sponsored": False
            }
        elif legacy_status in ("expired", "canceled", "suspended"):
            # Terminal state in legacy table: strictly drop to free tier without falling through to account_type
            free_plan = PRODUCT_PLANS["free"]
            return {
                "source": "personal_subscription_legacy_expired",
                "plan_id": "free",
                "plan_name": free_plan["display_name"],
                "has_vip_models": False,
                "has_api_access": False,
                "is_unlimited_quota": False,
                "quota_limit": free_plan["quota_limit"],
                "allowed_models": free_plan["allowed_models"],
                "allowed_features": free_plan["allowed_features"],
                "subscription_status": legacy_status,
                "is_organization_sponsored": False
            }

    # 5. Legacy Account Type Mapping (Backward Compatibility)
    acc_type = (user.get("account_type") or "").strip()
    if acc_type in ("Đơn vị dịch vụ nông nghiệp", "Pro", "Chuyên gia", "VIP", "expert"):
        pro_plan = PRODUCT_PLANS["pro"]
        return {
            "source": "legacy_account_type",
            "plan_id": "pro",
            "plan_name": pro_plan["display_name"],
            "has_vip_models": True,
            "has_api_access": False,
            "is_unlimited_quota": False,
            "quota_limit": pro_plan["quota_limit"],
            "allowed_models": pro_plan["allowed_models"],
            "allowed_features": pro_plan["allowed_features"],
            "subscription_status": "pilot_active",
            "is_organization_sponsored": False
        }
    elif acc_type in ("Hợp tác xã", "Trang trại", "cooperative"):
        team_plan = PRODUCT_PLANS["team"]
        return {
            "source": "legacy_account_type",
            "plan_id": "team",
            "plan_name": team_plan["display_name"],
            "has_vip_models": True,
            "has_api_access": True,
            "is_unlimited_quota": False,
            "quota_limit": team_plan["quota_limit"],
            "allowed_models": team_plan["allowed_models"],
            "allowed_features": team_plan["allowed_features"],
            "subscription_status": "pilot_active",
            "is_organization_sponsored": False
        }
    elif acc_type in ("Enterprise", "Doanh nghiệp", "enterprise"):
        ent_plan = PRODUCT_PLANS["enterprise"]
        return {
            "source": "legacy_account_type",
            "plan_id": "enterprise",
            "plan_name": ent_plan["display_name"],
            "has_vip_models": True,
            "has_api_access": True,
            "is_unlimited_quota": True,
            "quota_limit": None,
            "allowed_models": ent_plan["allowed_models"],
            "allowed_features": ent_plan["allowed_features"],
            "subscription_status": "active",
            "is_organization_sponsored": False
        }

    # 6. Default Free Personal Tier
    free_plan = PRODUCT_PLANS["free"]
    return {
        "source": "free_tier",
        "plan_id": "free",
        "plan_name": free_plan["display_name"],
        "has_vip_models": False,
        "has_api_access": False,
        "is_unlimited_quota": False,
        "quota_limit": free_plan["quota_limit"],
        "allowed_models": free_plan["allowed_models"],
        "allowed_features": free_plan["allowed_features"],
        "subscription_status": "active",
        "is_organization_sponsored": False
    }


def can_user_create_organization(user: Optional[Dict[str, Any]]) -> Tuple[bool, str]:
    """
    Checks if user is entitled to create a new organization.
    Free tier personal accounts cannot create organizations without upgrading to Pro or Enterprise.
    Platform admins and Pro/Team/Enterprise active users can create organizations.
    Enforces maximum organizations allowed per tier:
      - free: 0
      - pro / personal: 1
      - team / business: 3
      - enterprise: 100
    """
    if not user:
        return False, "Yêu cầu đăng nhập để khởi tạo tổ chức."
    if user.get("is_admin") or user.get("role") in ("admin", "host_admin"):
        return True, "Quản trị viên có toàn quyền khởi tạo tổ chức."
    entitlement = _resolve_user_entitlement_raw(user)
    plan_id = entitlement.get("plan_id", "free")
    sub_status = entitlement.get("subscription_status", "expired")
    allowed_plans = {"pro", "personal", "ultra", "team", "business", "organization", "enterprise"}
    if plan_id not in allowed_plans or sub_status not in (
        "active", "pilot_active", "trial", "trialing", "cancel_at_period_end"
    ):
        return False, "Tạo Hợp tác xã hoặc Doanh nghiệp yêu cầu tài khoản nâng cấp gói Pro hoặc Doanh nghiệp. Vui lòng nâng cấp gói để tiếp tục."

    # Tier-based limit check on owned organizations
    plan_org_limits = {
        "pro": 1,
        "personal": 1,
        "ultra": 2,
        "team": 3,
        "business": 3,
        "organization": 10,
        "enterprise": 100,
    }
    max_orgs = plan_org_limits.get(plan_id, 1)

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM organization_members
                WHERE user_id = ? AND role = 'owner'
            """, (user["id"],))
            row = cursor.fetchone()
            owned_count = row[0] if row else 0

            if owned_count >= max_orgs:
                plan_name = entitlement.get("plan_name", plan_id.upper())
                return False, f"Gói {plan_name} chỉ cho phép sở hữu tối đa {max_orgs} tổ chức. Bạn hiện đã sở hữu {owned_count} tổ chức. Vui lòng nâng cấp gói Doanh nghiệp để quản lý thêm tổ chức."
    except Exception as e:
        logger.warning(f"Error checking user owned organizations count: {e}")

    return True, f"Gói {entitlement.get('plan_name')} có quyền khởi tạo tổ chức."


def resolve_user_entitlement(
    user: Optional[Dict[str, Any]],
    org_id: Optional[int] = None,
    allow_dev_header: bool = False
) -> Dict[str, Any]:
    """
    Authoritative resolution of a user's capabilities, quota, and VIP model access:
    1. Checks if operating under an Organization with an active Team or Enterprise plan.
    2. Checks user's authoritative personal subscription table.
    3. Falls back to Free Plan.
    Always includes `can_create_organization` and `is_pro` status flags.
    """
    res = _resolve_user_entitlement_raw(user, org_id=org_id, allow_dev_header=False)
    can_create, _ = can_user_create_organization(user)
    res["can_create_organization"] = can_create
    res["is_pro"] = bool(res.get("has_vip_models"))
    return res


# -----------------------------------------------------------------------------
# 3. SUBSCRIPTION & AUDIT MANAGEMENT
# -----------------------------------------------------------------------------

def assign_user_plan(
    user_id: int,
    plan_id: str,
    status: str = "pilot_active",
    notes: Optional[str] = None,
    changed_by_user_id: Optional[int] = None
) -> Dict[str, Any]:
    """Assign or upgrade a user's personal subscription with full audit trail."""
    plan_def = get_plan_definition(plan_id)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    with _PLANS_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Find existing plan
            cursor.execute("SELECT plan_id FROM user_subscriptions WHERE user_id = ?", (user_id,))
            existing = cursor.fetchone()
            old_plan = existing["plan_id"] if existing else "free"

            # Upsert subscription in user_subscriptions (backward compatibility)
            cursor.execute("""
                INSERT INTO user_subscriptions (user_id, plan_id, status, billing_interval, start_date, notes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    plan_id = excluded.plan_id,
                    status = excluded.status,
                    billing_interval = excluded.billing_interval,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
            """, (user_id, plan_def["plan_id"], status, plan_def["billing_interval"], now_iso, notes or "Cấp quyền Sprint 1", now_iso))

            # Upsert in unified subscriptions table
            cursor.execute("""
                UPDATE subscriptions
                SET status = 'canceled', updated_at = CURRENT_TIMESTAMP
                WHERE target_type = 'user' AND target_id = ?
                  AND status IN ('trialing', 'active', 'cancel_at_period_end', 'past_due', 'suspended')
            """, (user_id,))

            cursor.execute("""
                INSERT INTO subscriptions (
                    target_type, target_id, user_id, plan_id, status,
                    billing_interval, current_period_start, current_period_end,
                    commercial_intent, is_paid, provider, notes
                ) VALUES ('user', ?, ?, ?, ?, ?, ?, datetime('now', '+30 days'), 'pilot_active', 0, 'manual', ?)
            """, (user_id, user_id, plan_def["plan_id"], status, plan_def["billing_interval"], now_iso, notes or "Cấp quyền gói"))

            # Record in Audit Trail
            cursor.execute("""
                INSERT INTO plan_audit_trail (target_type, target_id, old_plan, new_plan, action, changed_by_user_id, reason)
                VALUES ('user', ?, ?, ?, 'assigned', ?, ?)
            """, (user_id, old_plan, plan_def["plan_id"], changed_by_user_id, notes or "Cập nhật gói cước"))

            conn.commit()

    logger.info(f"Assigned plan '{plan_id}' to user_id {user_id} (old={old_plan})")
    return {
        "success": True,
        "user_id": user_id,
        "plan_id": plan_def["plan_id"],
        "status": status,
        "updated_at": now_iso
    }


def save_user_onboarding_profile(
    user_id: int,
    persona_type: str,
    primary_crops: Optional[List[str]] = None,
    farming_region: Optional[str] = None,
    farming_scale: Optional[str] = None
) -> Dict[str, Any]:
    """Store business-oriented onboarding profile for user."""
    crops_json = json.dumps(primary_crops or [], ensure_ascii=False)

    with _PLANS_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_onboarding_profiles (user_id, persona_type, primary_crops, farming_region, farming_scale)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    persona_type = excluded.persona_type,
                    primary_crops = excluded.primary_crops,
                    farming_region = excluded.farming_region,
                    farming_scale = excluded.farming_scale,
                    onboarding_completed = 1
            """, (user_id, persona_type, crops_json, farming_region, farming_scale))
            conn.commit()

    return {
        "success": True,
        "user_id": user_id,
        "persona_type": persona_type,
        "farming_region": farming_region,
        "farming_scale": farming_scale,
        "primary_crops": primary_crops or []
    }


def get_user_onboarding_profile(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve onboarding profile."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_onboarding_profiles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        try:
            data["primary_crops"] = json.loads(data["primary_crops"])
        except Exception:
            data["primary_crops"] = []
        return data
