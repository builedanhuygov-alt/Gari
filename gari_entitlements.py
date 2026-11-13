"""
GARI AI LAB — Centralized Entitlements & Usage Management System
(gari_entitlements.py)

Module 11: Subscription & Usage Management
Single Source of Truth for:
1. Configurable Plans (Free, Pro, Ultra, Organization, Enterprise)
   - Stored in database, dynamically configurable by admin.
2. Backend-Enforced Entitlements:
   - AI usage, diagnosis usage, farms, plots, organization seats, storage,
     expert consultations, and advanced features (scene_3d, reports).
3. Real-Time Usage Tracking:
   - Accurate usage recording, remaining quota calculation, percentage meters.
4. Clear Upgrade Messaging & Structured Payloads:
   - Actionable upgrade prompts when limits are reached or features are gated.
5. Subscription Lifecycle State Machine:
   - trial, active, past_due, cancel_at_period_end, canceled, expired, failed.
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("gari_entitlements")
DB_PATH = Path(__file__).resolve().parent / "database" / "disease_detector.db"
_ENTITLEMENT_LOCK = threading.RLock()

# In-memory plan cache
_PLANS_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TIMESTAMP: float = 0.0
CACHE_TTL_SECONDS = 60.0


class EntitlementError(Exception):
    """Base exception for entitlement and quota errors."""


class EntitlementExceededError(EntitlementError):
    """Raised when a usage quota is exhausted or an unentitled feature is requested."""

    def __init__(self, metric_or_feature: str, message: str, upgrade_data: Dict[str, Any]):
        super().__init__(message)
        self.metric_or_feature = metric_or_feature
        self.message = message
        self.upgrade_data = upgrade_data


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
    conn.row_factory = sqlite3.Row
    return conn


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().strftime("%Y-%m-%d %H:%M:%S")


# -----------------------------------------------------------------------------
# 1. CONFIGURABLE PLANS (Database-Driven with Memory Cache)
# -----------------------------------------------------------------------------

def invalidate_plans_cache() -> None:
    global _PLANS_CACHE, _CACHE_TIMESTAMP
    with _ENTITLEMENT_LOCK:
        _PLANS_CACHE.clear()
        _CACHE_TIMESTAMP = 0.0


def _load_plans_from_db() -> Dict[str, Dict[str, Any]]:
    global _PLANS_CACHE, _CACHE_TIMESTAMP
    plans: Dict[str, Dict[str, Any]] = {}
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM subscription_plans WHERE is_active = 1 ORDER BY tier_level ASC;")
            rows = cursor.fetchall()
            for r in rows:
                p = dict(r)
                if isinstance(p.get("allowed_features"), str):
                    try:
                        p["allowed_features"] = json.loads(p["allowed_features"])
                    except Exception:
                        p["allowed_features"] = []
                if isinstance(p.get("metadata_json"), str):
                    try:
                        p["metadata"] = json.loads(p["metadata_json"])
                    except Exception:
                        p["metadata"] = {}
                else:
                    p["metadata"] = {}
                plans[p["id"]] = p
    except Exception as exc:
        logger.error("Failed to load subscription plans from DB: %s", exc)

    # Fallback default plans if DB empty or query fails
    if not plans:
        plans["free"] = {
            "id": "free",
            "name": "free",
            "display_name": "Gói Miễn Phí (Free)",
            "tier_level": 0,
            "price": 0,
            "billing_interval": "monthly",
            "currency": "VND",
            "diagnosis_limit": 30,
            "ai_usage_limit": 10,
            "max_farms": 1,
            "max_plots": 3,
            "max_seats": 1,
            "storage_mb": 50,
            "expert_consultations_limit": 0,
            "allowed_features": ["diagnosis_basic", "farm_records", "view_knowledge", "scene_3d"],
            "metadata": {"badge": "Cơ bản"}
        }
        plans["pro"] = {
            "id": "pro",
            "name": "pro",
            "display_name": "Gói Chuyên Nghiệp (Pro)",
            "tier_level": 10,
            "price": 129000,
            "billing_interval": "monthly",
            "currency": "VND",
            "diagnosis_limit": 150,
            "ai_usage_limit": 100,
            "max_farms": 3,
            "max_plots": 15,
            "max_seats": 1,
            "storage_mb": 500,
            "expert_consultations_limit": 2,
            "allowed_features": [
                "diagnosis_basic", "diagnosis_vip", "farm_records", "data_export",
                "view_knowledge", "ai_assistant", "priority_support", "expert_consultation", "scene_3d"
            ],
            "metadata": {"badge": "Phổ biến", "highlight": True}
        }

    _PLANS_CACHE = plans
    _CACHE_TIMESTAMP = datetime.now().timestamp()
    return plans


def get_all_plans(force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
    global _PLANS_CACHE, _CACHE_TIMESTAMP
    with _ENTITLEMENT_LOCK:
        now_ts = datetime.now().timestamp()
        if force_refresh or not _PLANS_CACHE or (now_ts - _CACHE_TIMESTAMP > CACHE_TTL_SECONDS):
            return _load_plans_from_db()
        return dict(_PLANS_CACHE)


def get_plan_definition(plan_id: str) -> Dict[str, Any]:
    plans = get_all_plans()
    pid = (plan_id or "").strip().lower()
    
    # Check direct match
    if pid in plans:
        raw_plan = dict(plans[pid])
    else:
        # Check aliases
        aliases = {
            "personal": "pro",
            "team": "organization",
            "business": "organization",
            "guest": "free",
            "pilot": "free"
        }
        mapped_id = aliases.get(pid, "free")
        if mapped_id in plans:
            raw_plan = dict(plans[mapped_id])
        else:
            raw_plan = dict(plans.get("free", next(iter(plans.values()))))

    # Compatibility enrichments for legacy modules
    tier = raw_plan.get("tier_level", 0)
    diag_lim = raw_plan.get("diagnosis_limit", 30)
    is_unlimited = (tier >= 40) or (diag_lim == -1)
    
    raw_plan["plan_id"] = raw_plan.get("id", pid)
    raw_plan["has_vip_models"] = tier >= 10
    raw_plan["has_api_access"] = tier >= 30
    raw_plan["is_unlimited_quota"] = is_unlimited
    raw_plan["quota_limit"] = None if is_unlimited else diag_lim
    raw_plan["max_members"] = raw_plan.get("max_seats", 1)
    raw_plan["allowed_models"] = (
        ["standard_global", "crop_specific", "pro_global", "vip_models"]
        if tier >= 10 else
        ["standard_global", "crop_specific"]
    )
    raw_plan["can_export_data"] = True
    raw_plan["custom_branding"] = tier >= 40
    return raw_plan


def list_configurable_plans() -> List[Dict[str, Any]]:
    plans = get_all_plans()
    canonical_order = ["free", "pro", "ultra", "organization", "enterprise"]
    result = []
    seen = set()
    for pid in canonical_order:
        if pid in plans and pid not in seen:
            seen.add(pid)
            result.append(dict(plans[pid]))
    # Add any remaining custom plans
    for pid, p in plans.items():
        if pid not in seen:
            seen.add(pid)
            result.append(dict(p))
    return result


def update_plan_configuration(plan_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Allows platform admin to dynamically configure plan details, limits, and features."""
    pid = (plan_id or "").strip().lower()
    allowed_keys = {
        "display_name", "price", "billing_interval", "description", "target_audience",
        "diagnosis_limit", "ai_usage_limit", "max_farms", "max_plots", "max_seats",
        "storage_mb", "expert_consultations_limit", "allowed_features", "is_active"
    }

    cleaned_updates = {}
    for k, v in updates.items():
        if k in allowed_keys:
            if k == "allowed_features" and isinstance(v, list):
                cleaned_updates[k] = json.dumps(v)
            else:
                cleaned_updates[k] = v

    if not cleaned_updates:
        raise ValueError("Không có trường dữ liệu cập nhật hợp lệ.")

    cleaned_updates["updated_at"] = _now_iso()

    with _ENTITLEMENT_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            set_clause = ", ".join(f"{k} = :{k}" for k in cleaned_updates.keys())
            cleaned_updates["id"] = pid
            cursor.execute(f"UPDATE subscription_plans SET {set_clause} WHERE id = :id", cleaned_updates)
            if cursor.rowcount == 0:
                raise ValueError(f"Không tìm thấy gói cước với mã: {plan_id}")
            conn.commit()

        invalidate_plans_cache()
        return get_plan_definition(pid)


# -----------------------------------------------------------------------------
# 2. SUBSCRIPTION LIFECYCLE RESOLUTION
# -----------------------------------------------------------------------------

def resolve_subscription(user_id: int, org_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Authoritative resolution of subscription state:
    - If org_id is provided, queries organization subscription first.
    - Otherwise queries user personal subscription.
    - Validates expiration and handles cancel_at_period_end grace period.
    """
    now = _now_utc()
    target_type = "organization" if org_id else "user"
    target_id = org_id if org_id else user_id

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Check `subscriptions` table
        cursor.execute("""
            SELECT * FROM subscriptions 
            WHERE target_type = ? AND target_id = ?
            ORDER BY id DESC LIMIT 1
        """, (target_type, target_id))
        sub_row = cursor.fetchone()

        # If not found and user, check `user_subscriptions` table
        if not sub_row and target_type == "user":
            cursor.execute("""
                SELECT * FROM user_subscriptions
                WHERE user_id = ?
                ORDER BY id DESC LIMIT 1
            """, (user_id,))
            user_sub_row = cursor.fetchone()
            if user_sub_row:
                sub_dict = dict(user_sub_row)
                sub_row = {
                    "id": sub_dict["id"],
                    "target_type": "user",
                    "target_id": user_id,
                    "plan_id": sub_dict["plan_id"],
                    "status": sub_dict["status"],
                    "billing_interval": sub_dict.get("billing_interval", "monthly"),
                    "current_period_start": sub_dict.get("start_date"),
                    "current_period_end": sub_dict.get("end_date"),
                    "cancel_at_period_end": 0,
                    "notes": sub_dict.get("notes")
                }

        # If not found and organization, check `organizations` table
        if not sub_row and target_type == "organization":
            cursor.execute("SELECT id, plan_id, status FROM organizations WHERE id = ?", (org_id,))
            org_row = cursor.fetchone()
            if org_row:
                sub_row = {
                    "id": None,
                    "target_type": "organization",
                    "target_id": org_id,
                    "plan_id": org_row["plan_id"] or "organization",
                    "status": org_row["status"] or "active",
                    "billing_interval": "monthly",
                    "current_period_start": None,
                    "current_period_end": None,
                    "cancel_at_period_end": 0,
                    "notes": "Inherited from organization profile"
                }

    if not sub_row:
        # Default Free subscription
        free_plan = get_plan_definition("free")
        return {
            "has_subscription": False,
            "target_type": target_type,
            "target_id": target_id,
            "plan_id": "free",
            "plan": free_plan,
            "status": "active",
            "is_active": True,
            "current_period_start": None,
            "current_period_end": None,
            "cancel_at_period_end": False,
            "is_paid": False
        }

    sub = dict(sub_row)
    raw_status = (sub.get("status") or "active").strip().lower()
    period_end_str = sub.get("current_period_end") or sub.get("end_date")
    
    # Parse expiration
    is_expired = False
    if period_end_str:
        try:
            # Handle standard formats
            clean_str = period_end_str.replace("T", " ").split(".")[0].split("+")[0]
            end_dt = datetime.strptime(clean_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if now > end_dt:
                is_expired = True
        except Exception:
            pass

    # Status State Machine Evaluation
    effective_status = raw_status
    if is_expired:
        effective_status = "expired"
        # Atomically update DB if not already recorded
        if raw_status in ("active", "trialing", "cancel_at_period_end"):
            try:
                with get_db_connection() as conn:
                    conn.execute("UPDATE subscriptions SET status = 'expired', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (sub["id"],))
                    conn.commit()
            except Exception:
                pass
    elif bool(sub.get("cancel_at_period_end")) and raw_status in ("active", "trialing"):
        effective_status = "cancel_at_period_end"

    is_active = effective_status in ("active", "trialing", "cancel_at_period_end")
    plan_id = sub.get("plan_id", "free")
    
    # If expired, past_due, or canceled, downgrade access to Free
    if not is_active:
        plan_def = get_plan_definition("free")
    else:
        plan_def = get_plan_definition(plan_id)

    return {
        "has_subscription": True,
        "subscription_id": sub.get("id"),
        "target_type": target_type,
        "target_id": target_id,
        "plan_id": plan_def["id"],
        "plan": plan_def,
        "status": effective_status,
        "is_active": is_active,
        "current_period_start": sub.get("current_period_start"),
        "current_period_end": period_end_str,
        "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
        "is_paid": bool(sub.get("is_paid", False))
    }


def resolve_entitlements(user_id: int, org_id: Optional[int] = None) -> Dict[str, Any]:
    """Returns canonical entitlements and limits for user or organization."""
    sub_info = resolve_subscription(user_id, org_id)
    plan = sub_info["plan"]

    tier_level = plan.get("tier_level", 0)
    is_unlimited = tier_level >= 40 or plan.get("diagnosis_limit") == -1

    return {
        "subject_type": sub_info["target_type"],
        "subject_id": sub_info["target_id"],
        "plan_id": plan["id"],
        "plan_name": plan.get("display_name", plan["id"]),
        "tier_level": tier_level,
        "subscription_status": sub_info["status"],
        "is_active": sub_info["is_active"],
        "current_period_end": sub_info["current_period_end"],
        "cancel_at_period_end": sub_info["cancel_at_period_end"],
        "limits": {
            "ai_usage": plan.get("ai_usage_limit"),
            "diagnosis": plan.get("diagnosis_limit"),
            "max_farms": plan.get("max_farms"),
            "max_plots": plan.get("max_plots"),
            "organization_seats": plan.get("max_seats"),
            "storage_mb": plan.get("storage_mb"),
            "expert_consultations": plan.get("expert_consultations_limit"),
        },
        "features": plan.get("allowed_features", []),
        "is_unlimited": is_unlimited
    }


# -----------------------------------------------------------------------------
# 3. REAL-TIME USAGE TRACKING & SUMMARY
# -----------------------------------------------------------------------------

def get_current_billing_cycle(current_period_start: Optional[str] = None) -> Tuple[datetime, datetime]:
    """Calculates start and end datetime for the current monthly usage cycle."""
    now = _now_utc()
    if current_period_start:
        try:
            clean_str = current_period_start.replace("T", " ").split(".")[0].split("+")[0]
            start_dt = datetime.strptime(clean_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            # Cycle aligns with monthly billing
            end_dt = start_dt + timedelta(days=30)
            return start_dt, end_dt
        except Exception:
            pass

    # Default to 30-day sliding window ending in future
    start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # End of month
    if start_dt.month == 12:
        end_dt = start_dt.replace(year=start_dt.year + 1, month=1)
    else:
        end_dt = start_dt.replace(month=start_dt.month + 1)
    return start_dt, end_dt


def get_realtime_usage(user_id: int, org_id: Optional[int] = None) -> Dict[str, float]:
    """
    Computes accurate, non-fabricated usage across all dimensions:
    - ai_usage: queries logged in usage_tracking
    - diagnosis: scans logged in usage_tracking / diagnoses
    - farms: actual non-archived farms owned in database
    - plots: actual non-archived plots across farms
    - organization_seats: active members in organization
    - storage_mb: estimated or tracked storage
    - expert_consultations: consultations requested
    """
    subject_type = "organization" if org_id else "user"
    subject_id = org_id if org_id else user_id

    cycle_start, cycle_end = get_current_billing_cycle()
    cycle_start_str = cycle_start.strftime("%Y-%m-%d %H:%M:%S")

    usage: Dict[str, float] = {
        "ai_usage": 0.0,
        "diagnosis": 0.0,
        "farms": 0.0,
        "plots": 0.0,
        "organization_seats": 1.0,
        "storage_mb": 0.0,
        "expert_consultations": 0.0
    }

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Metric usage recorded in `usage_tracking`
        cursor.execute("""
            SELECT metric_name, used_amount FROM usage_tracking
            WHERE subject_type = ? AND subject_id = ? AND cycle_start >= ?
        """, (subject_type, subject_id, cycle_start_str))
        for row in cursor.fetchall():
            metric = row["metric_name"]
            if metric in usage:
                usage[metric] = float(row["used_amount"])

        # 2. Count active farms from database
        if org_id:
            cursor.execute("SELECT COUNT(*) FROM farms WHERE organization_id = ? AND status != 'archived'", (org_id,))
        else:
            cursor.execute("SELECT COUNT(*) FROM farms WHERE user_id = ? AND status != 'archived'", (user_id,))
        usage["farms"] = float(cursor.fetchone()[0] or 0)

        # 3. Count active plots from database
        if org_id:
            cursor.execute("""
                SELECT COUNT(*) FROM farm_plots fp
                JOIN farms f ON fp.farm_id = f.id
                WHERE f.organization_id = ? AND fp.status != 'archived'
            """, (org_id,))
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM farm_plots fp
                JOIN farms f ON fp.farm_id = f.id
                WHERE f.user_id = ? AND fp.status != 'archived'
            """, (user_id,))
        usage["plots"] = float(cursor.fetchone()[0] or 0)

        # 4. Organization seats
        if org_id:
            cursor.execute("SELECT COUNT(*) FROM organization_members WHERE organization_id = ? AND role != 'archived'", (org_id,))
            usage["organization_seats"] = float(cursor.fetchone()[0] or 1)
        else:
            usage["organization_seats"] = 1.0

        # 5. Check if diagnoses count in cycle exceeds usage_tracking
        if org_id:
            cursor.execute("""
                SELECT COUNT(*) FROM diagnoses d
                JOIN farms f ON d.farm_id = f.id
                WHERE f.organization_id = ? AND d.created_at >= ?
            """, (org_id, cycle_start_str))
        else:
            cursor.execute("SELECT COUNT(*) FROM diagnoses WHERE user_id = ? AND created_at >= ?", (user_id, cycle_start_str))
        diag_count = float(cursor.fetchone()[0] or 0)
        if diag_count > usage["diagnosis"]:
            usage["diagnosis"] = diag_count

        # 6. Check active expert cases created in cycle
        cursor.execute("SELECT COUNT(*) FROM expert_cases WHERE user_id = ? AND created_at >= ?", (user_id, cycle_start_str))
        exp_count = float(cursor.fetchone()[0] or 0)
        if exp_count > usage["expert_consultations"]:
            usage["expert_consultations"] = exp_count

    return usage


def record_usage(
    user_id: int, 
    metric_name: str, 
    amount: float = 1.0, 
    org_id: Optional[int] = None
) -> float:
    """
    Atomically records and increments usage for a given metric.
    Returns the new cumulative total for the current billing cycle.
    """
    subject_type = "organization" if org_id else "user"
    subject_id = org_id if org_id else user_id

    cycle_start, cycle_end = get_current_billing_cycle()
    cycle_start_str = cycle_start.strftime("%Y-%m-%d %H:%M:%S")
    cycle_end_str = cycle_end.strftime("%Y-%m-%d %H:%M:%S")
    now_str = _now_iso()

    with _ENTITLEMENT_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO usage_tracking (
                    subject_type, subject_id, metric_name, used_amount,
                    cycle_start, cycle_end, last_recorded_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(subject_type, subject_id, metric_name, cycle_start)
                DO UPDATE SET
                    used_amount = used_amount + ?,
                    last_recorded_at = ?,
                    updated_at = ?
            """, (
                subject_type, subject_id, metric_name, amount,
                cycle_start_str, cycle_end_str, now_str, now_str,
                amount, now_str, now_str
            ))

            cursor.execute("""
                SELECT used_amount FROM usage_tracking
                WHERE subject_type = ? AND subject_id = ? AND metric_name = ? AND cycle_start = ?
            """, (subject_type, subject_id, metric_name, cycle_start_str))
            row = cursor.fetchone()
            total = float(row[0]) if row else amount

            # Also log to billing_usage_events for permanent audit log
            cursor.execute("""
                INSERT INTO billing_usage_events (target_type, target_id, actor_user_id, feature, usage_amount, result, created_at)
                VALUES (?, ?, ?, ?, ?, 'success', ?)
            """, (subject_type, subject_id, user_id, metric_name, int(amount), now_str))

            conn.commit()
            return total


def get_usage_summary(user_id: int, org_id: Optional[int] = None) -> Dict[str, Any]:
    """Generates complete usage metrics vs limits, remaining quota, and upgrade guidance."""
    ent = resolve_entitlements(user_id, org_id)
    usage = get_realtime_usage(user_id, org_id)
    limits = ent["limits"]
    is_unlimited = ent["is_unlimited"]

    metrics_summary: Dict[str, Any] = {}
    metric_labels = {
        "ai_usage": ("Câu hỏi AI", "lượt"),
        "diagnosis": ("Chẩn đoán bệnh lá", "lượt"),
        "farms": ("Trang trại", "trang trại"),
        "plots": ("Phân lô / Vùng trồng", "lô"),
        "organization_seats": ("Thành viên tổ chức", "thành viên"),
        "storage_mb": ("Dung lượng lưu trữ", "MB"),
        "expert_consultations": ("Tư vấn Chuyên gia", "phiên")
    }

    needs_upgrade = False
    bottleneck_metric = None

    for key, (label, unit) in metric_labels.items():
        used = usage.get(key, 0.0)
        lim = limits.get(key)
        
        if is_unlimited or lim is None or lim < 0:
            remaining = None
            pct = 0.0
            unlimited_flag = True
        else:
            remaining = max(0.0, float(lim) - used)
            pct = round((used / float(lim)) * 100.0, 1) if lim > 0 else 100.0
            unlimited_flag = False
            if pct >= 80.0:
                needs_upgrade = True
                if bottleneck_metric is None or pct >= 100.0:
                    bottleneck_metric = key

        metrics_summary[key] = {
            "label": label,
            "unit": unit,
            "used": int(used) if key != "storage_mb" else round(used, 2),
            "limit": lim if not unlimited_flag else None,
            "remaining": int(remaining) if (remaining is not None and key != "storage_mb") else remaining,
            "percentage": pct,
            "is_unlimited": unlimited_flag,
            "is_exhausted": (not unlimited_flag) and (used >= float(lim or 0))
        }

    # Features map
    allowed_features_set = set(ent["features"])
    all_known_features = [
        ("ai_assistant", "Trợ lý AI Nông học", "pro"),
        ("diagnosis_vip", "Mô hình Nhận diện Chuyên sâu (VIP)", "pro"),
        ("scene_3d", "Không gian Nông trại 3D", "pro"),
        ("expert_consultation", "Mạng lưới Chuyên gia Nông học", "pro"),
        ("advanced_reports", "Báo cáo Phân tích Nâng cao", "ultra"),
        ("crop_rotation_calendar", "Lịch Luân canh Vụ mùa Nâng cao", "ultra"),
        ("team_management", "Quản trị Đội ngũ & Phân quyền", "organization"),
        ("api_access", "Kết nối API IoT / Drone", "organization"),
        ("custom_branding", "Tùy biến Thương hiệu Doanh nghiệp", "enterprise")
    ]
    features_summary = {}
    for feat_key, feat_name, min_plan in all_known_features:
        has_feat = is_unlimited or (feat_key in allowed_features_set)
        features_summary[feat_key] = {
            "name": feat_name,
            "enabled": has_feat,
            "required_plan": min_plan
        }

    # Determine suggested upgrade
    tier = ent["tier_level"]
    suggested_plan_id = "pro" if tier < 10 else ("ultra" if tier < 20 else ("organization" if tier < 30 else "enterprise"))
    suggested_plan = get_plan_definition(suggested_plan_id)

    upgrade_guidance = {
        "needs_upgrade": needs_upgrade or tier < 10,
        "current_plan_id": ent["plan_id"],
        "suggested_plan_id": suggested_plan_id,
        "suggested_plan_name": suggested_plan.get("display_name", suggested_plan_id),
        "suggested_plan_price": suggested_plan.get("price"),
        "upgrade_url": f"/frontend2/pricing.html?plan={suggested_plan_id}",
        "message": (
            f"Bạn sắp đạt hạn mức của gói {ent['plan_name']}. Hãy nâng cấp lên {suggested_plan.get('display_name')} để mở khóa thêm tài nguyên canh tác."
            if needs_upgrade else
            f"Nâng cấp lên {suggested_plan.get('display_name')} để tối ưu hóa năng suất và mở rộng quy mô nông trại."
        )
    }

    return {
        "plan": ent,
        "usage": metrics_summary,
        "features": features_summary,
        "upgrade_guidance": upgrade_guidance
    }


# -----------------------------------------------------------------------------
# 4. BACKEND LIMIT ENFORCEMENT
# -----------------------------------------------------------------------------

def check_entitlement(
    user_id: int, 
    metric_or_feature: str, 
    requested_amount: float = 1.0, 
    org_id: Optional[int] = None
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Authoritative backend entitlement check.
    Returns:
    - (True, None, None) if authorized.
    - (False, error_message, upgrade_data) if denied.
    """
    ent = resolve_entitlements(user_id, org_id)
    if ent["is_unlimited"]:
        return True, None, None

    features_set = set(ent["features"])

    # Feature gating check
    if metric_or_feature in (
        "scene_3d", "advanced_reports", "ai_assistant", "expert_consultation",
        "crop_rotation_calendar", "team_management", "api_access", "custom_branding"
    ):
        if metric_or_feature not in features_set:
            tier = ent["tier_level"]
            sug_plan = "pro" if tier < 10 else "ultra"
            sug_def = get_plan_definition(sug_plan)
            msg = f"Tính năng này yêu cầu gói cước từ {sug_def.get('display_name')} trở lên."
            return False, msg, {
                "error": "feature_not_entitled",
                "feature": metric_or_feature,
                "current_plan": ent["plan_id"],
                "suggested_plan": sug_plan,
                "upgrade_url": f"/frontend2/pricing.html?plan={sug_plan}"
            }

    # Metric quota check
    metric_mapping = {
        "ai_usage": "ai_usage",
        "diagnosis": "diagnosis",
        "max_farms": "farms",
        "max_plots": "plots",
        "organization_seats": "organization_seats",
        "storage_mb": "storage_mb",
        "expert_consultations": "expert_consultations"
    }
    canonical_metric = metric_mapping.get(metric_or_feature, metric_or_feature)
    limits = ent["limits"]

    limit_val = limits.get(metric_or_feature) or limits.get(canonical_metric)
    if limit_val is not None and limit_val >= 0:
        usage = get_realtime_usage(user_id, org_id)
        current_used = usage.get(canonical_metric, 0.0)

        if current_used + requested_amount > float(limit_val):
            tier = ent["tier_level"]
            sug_plan = "pro" if tier < 10 else ("ultra" if tier < 20 else "organization")
            sug_def = get_plan_definition(sug_plan)
            metric_display_names = {
                "ai_usage": "câu hỏi AI",
                "diagnosis": "chẩn đoán bệnh lá",
                "farms": "trang trại",
                "plots": "phân lô",
                "organization_seats": "thành viên tổ chức",
                "storage_mb": "dung lượng lưu trữ MB",
                "expert_consultations": "phiên tư vấn chuyên gia"
            }
            name = metric_display_names.get(canonical_metric, canonical_metric)
            msg = f"Bạn đã đạt hạn ngạch tối đa {int(limit_val)} {name} của gói {ent['plan_name']}. Hiện đã dùng: {int(current_used)}."
            return False, msg, {
                "error": "quota_limit_exceeded",
                "metric": canonical_metric,
                "current_usage": int(current_used),
                "limit": int(limit_val),
                "current_plan": ent["plan_id"],
                "suggested_plan": sug_plan,
                "upgrade_url": f"/frontend2/pricing.html?plan={sug_plan}"
            }

    return True, None, None


def enforce_entitlement(
    user_id: int, 
    metric_or_feature: str, 
    requested_amount: float = 1.0, 
    org_id: Optional[int] = None
) -> None:
    """Enforces entitlement on backend; raises EntitlementExceededError if unauthorized."""
    allowed, msg, upgrade_data = check_entitlement(user_id, metric_or_feature, requested_amount, org_id)
    if not allowed:
        raise EntitlementExceededError(
            metric_or_feature=metric_or_feature,
            message=msg or "Hạn ngạch gói cước đã hết.",
            upgrade_data=upgrade_data or {}
        )


# -----------------------------------------------------------------------------
# 5. SUBSCRIPTION LIFECYCLE MANAGEMENT (Assign, Cancel, Reactivate)
# -----------------------------------------------------------------------------

def assign_subscription(
    target_type: str,
    target_id: int,
    plan_id: str,
    duration_days: int = 30,
    notes: str = "",
    is_paid: bool = True,
    provider: str = "manual"
) -> Dict[str, Any]:
    """Atomically activates or renews a subscription for a user or organization."""
    plan = get_plan_definition(plan_id)
    now = _now_utc()
    end_dt = now + timedelta(days=duration_days)

    now_str = _now_iso()
    end_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")

    user_id = target_id if target_type == "user" else None
    org_id = target_id if target_type == "organization" else None

    with _ENTITLEMENT_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Insert into subscriptions table
            cursor.execute("""
                INSERT INTO subscriptions (
                    target_type, target_id, user_id, organization_id, plan_id,
                    status, billing_interval, current_period_start, current_period_end,
                    cancel_at_period_end, is_paid, provider, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, 0, ?, ?, ?, ?)
            """, (
                target_type, target_id, user_id, org_id, plan["id"],
                plan.get("billing_interval", "monthly"), now_str, end_str,
                1 if is_paid else 0, provider, notes, now_str
            ))
            sub_id = cursor.lastrowid

            # Mirror to user_subscriptions if user
            if target_type == "user":
                cursor.execute("""
                    INSERT INTO user_subscriptions (user_id, plan_id, status, billing_interval, start_date, end_date, notes, updated_at)
                    VALUES (?, ?, 'active', ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        plan_id = excluded.plan_id,
                        status = 'active',
                        billing_interval = excluded.billing_interval,
                        start_date = excluded.start_date,
                        end_date = excluded.end_date,
                        notes = excluded.notes,
                        updated_at = excluded.updated_at
                """, (user_id, plan["id"], plan.get("billing_interval", "monthly"), now_str, end_str, notes, now_str))

            # Audit trail
            cursor.execute("""
                INSERT INTO plan_audit_trail (target_type, target_id, old_plan, new_plan, action, reason, created_at)
                VALUES (?, ?, 'unknown', ?, 'assigned', ?, ?)
            """, (target_type, target_id, plan["id"], notes or "Subscription assigned", now_str))

            conn.commit()

        logger.info("Assigned subscription %s to %s #%d until %s", plan["id"], target_type, target_id, end_str)
        return resolve_subscription(user_id or 0, org_id)


def cancel_subscription(
    target_type: str,
    target_id: int,
    immediate: bool = False,
    reason: str = ""
) -> Dict[str, Any]:
    """
    Cancels subscription:
    - If immediate=False: sets cancel_at_period_end = 1. Retains benefits until period end.
    - If immediate=True: sets status = 'canceled'.
    """
    now_str = _now_iso()
    new_status = "canceled" if immediate else "cancel_at_period_end"

    with _ENTITLEMENT_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if immediate:
                cursor.execute("""
                    UPDATE subscriptions
                    SET status = 'canceled', cancel_at_period_end = 0, ended_at = ?, notes = notes || ' | ' || ?, updated_at = ?
                    WHERE target_type = ? AND target_id = ? AND status IN ('active', 'trialing', 'cancel_at_period_end')
                """, (now_str, f"Canceled immediately: {reason}", now_str, target_type, target_id))
            else:
                cursor.execute("""
                    UPDATE subscriptions
                    SET cancel_at_period_end = 1, notes = notes || ' | ' || ?, updated_at = ?
                    WHERE target_type = ? AND target_id = ? AND status IN ('active', 'trialing')
                """, (f"Scheduled cancellation: {reason}", now_str, target_type, target_id))

            if target_type == "user":
                cursor.execute("""
                    UPDATE user_subscriptions
                    SET status = ?, notes = notes || ' | ' || ?, updated_at = ?
                    WHERE user_id = ?
                """, (new_status, reason, now_str, target_id))

            conn.commit()

    user_id = target_id if target_type == "user" else 0
    org_id = target_id if target_type == "organization" else None
    return resolve_subscription(user_id, org_id)


def reactivate_subscription(target_type: str, target_id: int) -> Dict[str, Any]:
    """Reactivates a subscription that was scheduled to cancel at period end."""
    now_str = _now_iso()
    with _ENTITLEMENT_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE subscriptions
                SET cancel_at_period_end = 0, status = 'active', updated_at = ?
                WHERE target_type = ? AND target_id = ? AND cancel_at_period_end = 1
            """, (now_str, target_type, target_id))

            if target_type == "user":
                cursor.execute("""
                    UPDATE user_subscriptions
                    SET status = 'active', updated_at = ?
                    WHERE user_id = ? AND status = 'cancel_at_period_end'
                """, (now_str, target_id))

            conn.commit()

    user_id = target_id if target_type == "user" else 0
    org_id = target_id if target_type == "organization" else None
    return resolve_subscription(user_id, org_id)
