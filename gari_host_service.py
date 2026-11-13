"""
GARI MODULE 12 — HOST CONSOLE SYSTEM ADMINISTRATION SERVICE
File: gari_host_service.py

Centralized business logic for Host Console:
1. User Management & Detailed User Inspector (with sensitive password reset & confirmation)
2. Organization Management & Tenant Hierarchy
3. Expert Application Review & Verification Lifecycle
4. Subscription and Dynamic Entitlement Configuration (database-driven)
5. AI Provider and Model Configuration (secure credential storage, masked secrets, explicit states)
6. Model Availability and Inference Status (CV models, leaf gate, device, benchmarks)
7. System-wide Usage Monitoring & Resource Consumption
8. Moderation Queue & Content Actions (community reports + user cases)
9. Host Audit Logging & Immutable Event Trails
10. System Health & Error Monitoring (telemetry, DB ping, error logs)
"""

import json
import logging
import os
import shutil
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import psutil

import gari_auth
import gari_config
import gari_database
import gari_entitlements

logger = logging.getLogger("gari.host_service")

ROOT = Path(__file__).resolve().parent
SERVER_START_TIME = time.time()


# ============================================================================
# 1. SYSTEM ERROR LOGGING & MONITORING
# ============================================================================
def log_system_event(
    log_level: str,
    component: str,
    message: str,
    error_details: Optional[str] = None,
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None
) -> int:
    """Record an operational or error event in system_logs table."""
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO system_logs (log_level, component, message, error_details, user_id, ip_address, created_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (log_level.upper(), component, message, error_details, user_id, ip_address)
        )
        conn.commit()
        return cursor.lastrowid


def get_system_errors(limit: int = 50, offset: int = 0, min_level: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve filtered system logs with error counts for Host Console."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    where_clauses = ["1=1"]
    params: List[Any] = []

    if min_level:
        lvl = min_level.upper().strip()
        if lvl == "ERROR":
            where_clauses.append("log_level IN ('ERROR', 'CRITICAL')")
        elif lvl == "WARNING":
            where_clauses.append("log_level IN ('WARNING', 'ERROR', 'CRITICAL')")
        else:
            where_clauses.append("log_level = ?")
            params.append(lvl)

    where_str = " AND ".join(where_clauses)

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        total = cursor.execute(f"SELECT count(*) FROM system_logs WHERE {where_str}", params).fetchone()[0]

        # Recent error counts by level
        error_count_24h = cursor.execute(
            "SELECT count(*) FROM system_logs WHERE log_level IN ('ERROR', 'CRITICAL') AND created_at >= datetime('now', '-1 day')"
        ).fetchone()[0]
        warning_count_24h = cursor.execute(
            "SELECT count(*) FROM system_logs WHERE log_level = 'WARNING' AND created_at >= datetime('now', '-1 day')"
        ).fetchone()[0]

        # By component breakdown
        cursor.execute(
            """
            SELECT component, count(*) as count
            FROM system_logs
            WHERE log_level IN ('ERROR', 'CRITICAL')
            GROUP BY component
            ORDER BY count DESC
            LIMIT 5
            """
        )
        component_breakdown = [dict(r) for r in cursor.fetchall()]

        cursor.execute(
            f"SELECT * FROM system_logs WHERE {where_str} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [limit, offset]
        )
        rows = [dict(r) for r in cursor.fetchall()]

    return {
        "success": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "errors_24h": error_count_24h,
        "warnings_24h": warning_count_24h,
        "component_breakdown": component_breakdown,
        "logs": rows
    }


def clear_system_errors(host_admin: Dict[str, Any], confirm: bool, reason: str, ip_address: Optional[str] = None) -> Dict[str, Any]:
    """Clear error logs requiring explicit confirmation."""
    if not confirm:
        return {
            "success": False,
            "error": "confirmation_required",
            "message": "Thao tác xóa nhật ký lỗi hệ thống yêu cầu xác nhận rõ ràng (confirm=True)."
        }

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        deleted_count = cursor.execute("DELETE FROM system_logs WHERE log_level IN ('ERROR', 'CRITICAL', 'WARNING')").rowcount
        conn.commit()

    gari_auth.record_host_audit(
        host_admin_id=host_admin["id"],
        host_email=host_admin.get("email"),
        action_type="CLEAR_SYSTEM_ERRORS",
        target_resource="system_logs",
        details={"deleted_count": deleted_count},
        reason=reason,
        ip_address=ip_address
    )

    return {
        "success": True,
        "message": f"Đã xóa thành công {deleted_count} bản ghi nhật ký lỗi.",
        "deleted_count": deleted_count
    }


# ============================================================================
# 2. SYSTEM HEALTH & TELEMETRY MONITORING
# ============================================================================
def get_system_health() -> Dict[str, Any]:
    """Return comprehensive system health and hardware telemetry."""
    # 1. CPU, RAM, Disk
    cpu_percent = psutil.cpu_percent(interval=0.05)
    vm = psutil.virtual_memory()
    ram_data = {
        "total_gb": round(vm.total / (1024 ** 3), 2),
        "used_gb": round(vm.used / (1024 ** 3), 2),
        "available_gb": round(vm.available / (1024 ** 3), 2),
        "percent": vm.percent
    }
    du = shutil.disk_usage(str(ROOT))
    disk_data = {
        "total_gb": round(du.total / (1024 ** 3), 2),
        "used_gb": round(du.used / (1024 ** 3), 2),
        "free_gb": round(du.free / (1024 ** 3), 2),
        "percent": round((du.used / du.total) * 100, 1)
    }

    # 2. Database ping
    t0 = time.perf_counter()
    db_healthy = True
    db_latency_ms = 0.0
    try:
        with gari_database.get_connection() as conn:
            conn.cursor().execute("SELECT 1").fetchone()
            db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    except Exception as exc:
        db_healthy = False
        logger.error("DB health check failed: %s", exc)

    # 3. Overall health status
    overall_status = "healthy"
    if not db_healthy or disk_data["percent"] > 95 or ram_data["percent"] > 95:
        overall_status = "failing"
    elif cpu_percent > 85 or ram_data["percent"] > 85 or disk_data["percent"] > 85:
        overall_status = "degraded"

    uptime_seconds = int(time.time() - SERVER_START_TIME)

    return {
        "success": True,
        "status": overall_status,
        "uptime_seconds": uptime_seconds,
        "database": {
            "status": "healthy" if db_healthy else "failing",
            "latency_ms": db_latency_ms
        },
        "cpu": {
            "percent": cpu_percent
        },
        "memory": ram_data,
        "disk": disk_data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ============================================================================
# 3. USER MANAGEMENT & DETAILED USER INSPECTOR
# ============================================================================
def get_user_details(user_id: int) -> Dict[str, Any]:
    """Retrieve detailed profile of a single user with farm, subscription, and audit metrics."""
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, email, full_name, name, phone, account_type, is_active, is_host_admin, is_expert, created_at, updated_at
            FROM users WHERE id = ?
            """,
            (user_id,)
        )
        user_row = cursor.fetchone()
        if not user_row:
            return {"success": False, "error": "user_not_found", "message": "Không tìm thấy người dùng."}

        user = dict(user_row)
        user["full_name"] = user.get("full_name") or user.get("name") or "Người dùng GARI"
        user["is_host_admin"] = bool(user.get("is_host_admin"))
        user["is_expert"] = bool(user.get("is_expert"))
        user["is_active"] = bool(user.get("is_active", 1))

        # Farm & Plot counts
        farm_count = cursor.execute("SELECT count(*) FROM farms WHERE user_id = ? AND status != 'archived'", (user_id,)).fetchone()[0]
        plot_count = cursor.execute(
            """
            SELECT count(*) FROM farm_plots p
            JOIN farms f ON p.farm_id = f.id
            WHERE f.user_id = ? AND p.status != 'archived'
            """,
            (user_id,)
        ).fetchone()[0]

        # Diagnoses count
        diag_count = cursor.execute("SELECT count(*) FROM diagnoses WHERE user_id = ?", (user_id,)).fetchone()[0]

        # Active session count
        session_count = cursor.execute(
            "SELECT count(*) FROM user_sessions WHERE user_id = ? AND expires_at > datetime('now')",
            (user_id,)
        ).fetchone()[0]

        # Subscription details
        sub_row = cursor.execute(
            """
            SELECT plan_id, status, start_date, end_date
            FROM user_subscriptions
            WHERE user_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (user_id,)
        ).fetchone()

        # Audit logs concerning this user
        cursor.execute(
            """
            SELECT id, action_type, host_email, reason, outcome, created_at
            FROM host_audit_logs
            WHERE target_resource = ? OR target_resource = ?
            ORDER BY id DESC LIMIT 5
            """,
            (f"user:{user_id}", f"user_id:{user_id}")
        )
        audit_history = [dict(r) for r in cursor.fetchall()]

    subscription_info = dict(sub_row) if sub_row else {"plan_id": "free", "status": "active"}

    return {
        "success": True,
        "user": user,
        "stats": {
            "farm_count": farm_count,
            "plot_count": plot_count,
            "diagnoses_count": diag_count,
            "active_sessions": session_count
        },
        "subscription": subscription_info,
        "recent_audit": audit_history
    }


def admin_reset_user_password(
    host_admin: Dict[str, Any],
    user_id: int,
    new_password: str,
    confirm: bool,
    reason: str,
    ip_address: Optional[str] = None
) -> Dict[str, Any]:
    """Host Admin resets user password. Requires explicit confirmation and audits."""
    if not confirm:
        return {
            "success": False,
            "error": "confirmation_required",
            "message": "Thao tác đặt lại mật khẩu người dùng yêu cầu xác nhận rõ ràng (confirm=True)."
        }

    if len(new_password) < 8:
        return {
            "success": False,
            "error": "weak_password",
            "message": "Mật khẩu mới phải có tối thiểu 8 ký tự."
        }

    hashed = gari_auth.hash_password(new_password)

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email FROM users WHERE id = ?", (user_id,))
        target_user = cursor.fetchone()
        if not target_user:
            return {"success": False, "error": "user_not_found", "message": "Không tìm thấy người dùng."}

        cursor.execute(
            "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (hashed, user_id)
        )
        # Revoke all active sessions
        cursor.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
        conn.commit()

    gari_auth.record_host_audit(
        host_admin_id=host_admin["id"],
        host_email=host_admin.get("email"),
        action_type="ADMIN_RESET_PASSWORD",
        target_resource=f"user:{user_id}",
        details={"target_user_id": user_id, "target_email": target_user["email"], "sessions_revoked": True},
        reason=reason,
        ip_address=ip_address
    )

    return {
        "success": True,
        "message": f"Đã đặt lại mật khẩu thành công cho tài khoản {target_user['email']} và hủy toàn bộ phiên làm việc cũ."
    }


# ============================================================================
# 4. ORGANIZATION MANAGEMENT & DETAILS
# ============================================================================
def get_organization_details(org_id: int) -> Dict[str, Any]:
    """Retrieve detailed organization view with owner info, farms, and member roster."""
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
        org_row = cursor.fetchone()
        if not org_row:
            return {"success": False, "error": "org_not_found", "message": "Không tìm thấy tổ chức."}

        org = dict(org_row)

        # Owner info
        cursor.execute("SELECT id, email, full_name, phone FROM users WHERE id = ?", (org.get("owner_id"),))
        owner_row = cursor.fetchone()
        owner_info = dict(owner_row) if owner_row else {}

        # Members count and roster
        cursor.execute(
            """
            SELECT m.id, m.user_id, m.role, m.created_at as joined_at, u.email, u.full_name
            FROM organization_members m
            JOIN users u ON m.user_id = u.id
            WHERE m.organization_id = ? AND m.role != 'archived'
            ORDER BY m.id ASC
            """,
            (org_id,)
        )
        members = [dict(r) for r in cursor.fetchall()]

        # Farms owned by org
        cursor.execute("SELECT id, name, area_m2, status FROM farms WHERE organization_id = ?", (org_id,))
        farms = [dict(r) for r in cursor.fetchall()]

    return {
        "success": True,
        "organization": org,
        "owner": owner_info,
        "member_count": len(members),
        "members": members,
        "farms": farms
    }


# ============================================================================
# 5. EXPERT APPLICATION DETAILS
# ============================================================================
def get_expert_application_details(app_id: int) -> Dict[str, Any]:
    """Retrieve detailed expert application with qualification docs and history."""
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_applications WHERE id = ?", (app_id,))
        app_row = cursor.fetchone()
        if not app_row:
            return {"success": False, "error": "app_not_found", "message": "Không tìm thấy hồ sơ chuyên gia."}

        app_data = dict(app_row)
        # Parse JSON fields if present
        for json_field in ("specialties", "primary_crops", "qualifications", "documents"):
            if app_data.get(json_field) and isinstance(app_data[json_field], str):
                try:
                    app_data[json_field] = json.loads(app_data[json_field])
                except Exception:
                    pass

        # User profile
        cursor.execute("SELECT id, email, full_name, phone, created_at FROM users WHERE id = ?", (app_data.get("user_id"),))
        user_row = cursor.fetchone()

    return {
        "success": True,
        "application": app_data,
        "user": dict(user_row) if user_row else {}
    }


# ============================================================================
# 6. SUBSCRIPTION & ENTITLEMENT PLANS CONFIGURATION
# ============================================================================
def get_all_subscription_plans() -> Dict[str, Any]:
    """Retrieve all dynamic plans from subscription_plans table."""
    plans = gari_entitlements.get_all_plans()
    plans_list = list(plans.values()) if isinstance(plans, dict) else plans
    return {
        "success": True,
        "total": len(plans_list),
        "plans": plans_list
    }


def update_subscription_plan(
    host_admin: Dict[str, Any],
    plan_id: str,
    payload: Dict[str, Any],
    confirm: bool,
    reason: str,
    ip_address: Optional[str] = None
) -> Dict[str, Any]:
    """Update dynamic subscription plan limits and pricing. Requires confirmation and audits."""
    if not confirm:
        return {
            "success": False,
            "error": "confirmation_required",
            "message": "Thao tác cập nhật hạn ngạch gói cước yêu cầu xác nhận rõ ràng (confirm=True)."
        }

    try:
        plan = gari_entitlements.update_plan_configuration(plan_id, payload)
        res = {'success': True, 'plan': plan}
    except Exception as e:
        res = {'success': False, 'message': str(e)}
    if not res.get("success"):
        return res

    gari_auth.record_host_audit(
        host_admin_id=host_admin["id"],
        host_email=host_admin.get("email"),
        action_type="UPDATE_SUBSCRIPTION_PLAN",
        target_resource=f"subscription_plan:{plan_id}",
        details={"plan_id": plan_id, "updated_fields": list(payload.keys())},
        reason=reason,
        ip_address=ip_address
    )

    return res


# ============================================================================
# 7. AI PROVIDER & MODEL CONFIGURATION (SECURE CREDENTIALS & HEALTH STATES)
# ============================================================================
def get_ai_configuration() -> Dict[str, Any]:
    """
    Retrieve active AI configuration with MASKED credentials and explicit health states:
    - unconfigured
    - configured
    - healthy
    - failing
    Secrets are NEVER returned to frontend.
    """
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM host_api_config WHERE key LIKE 'assistant_%'")
        db_rows = dict(cursor.fetchall())

    provider = db_rows.get("assistant_provider") or os.environ.get("GARI_ASSISTANT_PROVIDER", "mock")
    model = db_rows.get("assistant_model") or os.environ.get("GARI_ASSISTANT_MODEL", "mock-agri-v1")
    raw_key = db_rows.get("assistant_api_key") or os.environ.get("GEMINI_API_KEY", "")
    base_url = db_rows.get("assistant_base_url") or os.environ.get("OPENAI_BASE_URL", "")

    # Health tracking from DB
    last_health_status = db_rows.get("assistant_last_health_status", "")
    last_health_check = db_rows.get("assistant_last_health_check", "")
    last_health_latency = db_rows.get("assistant_last_health_latency_ms", "")
    last_health_error = db_rows.get("assistant_last_health_error", "")

    # Mask key: only first 4 and last 4 characters shown, or ***
    if raw_key and len(raw_key) > 8:
        masked_key = raw_key[:4] + "..." + raw_key[-4:]
    elif raw_key:
        masked_key = "***"
    else:
        masked_key = ""

    is_configured = bool(provider and provider != "disabled" and (raw_key or provider == "mock"))

    # Determine explicit state
    if provider == "disabled" or not is_configured:
        explicit_state = "unconfigured"
    elif last_health_status == "failing":
        explicit_state = "failing"
    elif last_health_status == "healthy":
        explicit_state = "healthy"
    else:
        explicit_state = "configured"

    return {
        "success": True,
        "config": {
            "provider": provider,
            "model": model,
            "api_key_masked": masked_key,
            "has_api_key": bool(raw_key),
            "base_url": base_url,
            "temperature": float(db_rows.get("assistant_temperature", 0.2)),
            "timeout_sec": float(db_rows.get("assistant_timeout_sec", 20.0)),
            "citations_enabled": db_rows.get("assistant_citations_enabled", "1") in ("1", "true", "True"),
            "deep_dive_enabled": db_rows.get("assistant_deep_dive_enabled", "1") in ("1", "true", "True"),
            "is_configured": is_configured,
            "state": explicit_state,
            "last_health_check": last_health_check,
            "last_health_latency_ms": float(last_health_latency) if last_health_latency else None,
            "last_health_error": last_health_error or None
        },
        "available_providers": ["gemini", "openai", "anthropic", "mock", "disabled"]
    }


def update_ai_configuration(
    host_admin: Dict[str, Any],
    payload: Dict[str, Any],
    reason: str,
    ip_address: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update AI provider, model, keys, and parameters.
    Ensures secrets are NEVER logged or leaked.
    """
    updates = []
    audited_fields = []

    if "provider" in payload:
        p = str(payload["provider"]).strip().lower()
        updates.append(("assistant_provider", p, "AI Provider cho Trợ lý Nông học"))
        audited_fields.append(f"provider={p}")

    if "model" in payload:
        m = str(payload["model"]).strip()
        updates.append(("assistant_model", m, "Tên mô hình LLM chính"))
        audited_fields.append(f"model={m}")

    if "api_key" in payload:
        k = str(payload["api_key"]).strip()
        # Protect against saving masked placeholder back
        if k and not k.startswith("***") and "..." not in k:
            updates.append(("assistant_api_key", k, "API Key bảo mật cho Trợ lý AI"))
            audited_fields.append("api_key=[SECRET_REDACTED]")

    if "base_url" in payload:
        b = str(payload["base_url"]).strip()
        updates.append(("assistant_base_url", b, "Base URL cho OpenAI-compatible LLM"))
        audited_fields.append(f"base_url={b}")

    if "temperature" in payload:
        t = str(payload["temperature"]).strip()
        updates.append(("assistant_temperature", t, "Độ sáng tạo nhiệt độ LLM"))
        audited_fields.append(f"temperature={t}")

    if "timeout_sec" in payload:
        to = str(payload["timeout_sec"]).strip()
        updates.append(("assistant_timeout_sec", to, "Thời gian chờ tối đa phản hồi AI"))
        audited_fields.append(f"timeout_sec={to}")

    if "citations_enabled" in payload:
        c = "1" if payload["citations_enabled"] in (True, 1, "1", "true") else "0"
        updates.append(("assistant_citations_enabled", c, "Bật/Tắt trích dẫn nguồn"))
        audited_fields.append(f"citations={c}")

    if "deep_dive_enabled" in payload:
        dd = "1" if payload["deep_dive_enabled"] in (True, 1, "1", "true") else "0"
        updates.append(("assistant_deep_dive_enabled", dd, "Bật/Tắt phân tích chuyên sâu"))
        audited_fields.append(f"deep_dive={dd}")

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        for key, val, desc in updates:
            cursor.execute(
                """
                INSERT INTO host_api_config (key, value, description, updated_by_host_id, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    description = excluded.description,
                    updated_by_host_id = excluded.updated_by_host_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, val, desc, host_admin["id"])
            )
        conn.commit()

    gari_auth.record_host_audit(
        host_admin_id=host_admin["id"],
        host_email=host_admin.get("email"),
        action_type="UPDATE_AI_CONFIG",
        target_resource="host_api_config:assistant",
        details={"updated_fields": audited_fields},
        reason=reason,
        ip_address=ip_address
    )

    return {
        "success": True,
        "message": "Đã lưu và áp dụng cấu hình AI Provider thành công.",
        "updated_keys": [u[0] for u in updates]
    }


def record_ai_health_probe(status: str, latency_ms: float, error_detail: Optional[str] = None) -> None:
    """Record health test outcome into host_api_config."""
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            INSERT INTO host_api_config (key, value, description, updated_at)
            VALUES ('assistant_last_health_status', ?, 'Last AI Health status', CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
            (status,)
        )
        cursor.execute(
            """
            INSERT INTO host_api_config (key, value, description, updated_at)
            VALUES ('assistant_last_health_check', ?, 'Timestamp of last health check', CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
            (now_iso,)
        )
        cursor.execute(
            """
            INSERT INTO host_api_config (key, value, description, updated_at)
            VALUES ('assistant_last_health_latency_ms', ?, 'Latency of last health check', CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
            (str(round(latency_ms, 2)),)
        )
        cursor.execute(
            """
            INSERT INTO host_api_config (key, value, description, updated_at)
            VALUES ('assistant_last_health_error', ?, 'Error of last health check', CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
            (error_detail or "",)
        )
        conn.commit()


# ============================================================================
# 8. USAGE MONITORING & SYSTEM-WIDE TOTALS
# ============================================================================
def get_system_usage_summary() -> Dict[str, Any]:
    """Calculate system-wide resource utilization across all users and organizations."""
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()

        # Users and Orgs count
        total_users = cursor.execute("SELECT count(*) FROM users").fetchone()[0]
        active_users = cursor.execute("SELECT count(*) FROM users WHERE is_active = 1").fetchone()[0]
        total_orgs = cursor.execute("SELECT count(*) FROM organizations").fetchone()[0]
        total_seats = cursor.execute("SELECT count(*) FROM organization_members WHERE role != 'archived'").fetchone()[0]

        # Farms & Plots
        total_farms = cursor.execute("SELECT count(*) FROM farms WHERE status != 'archived'").fetchone()[0]
        total_plots = cursor.execute("SELECT count(*) FROM farm_plots WHERE status != 'archived'").fetchone()[0]

        # Diagnoses
        total_diagnoses = cursor.execute("SELECT count(*) FROM diagnoses").fetchone()[0]
        diagnoses_24h = cursor.execute(
            "SELECT count(*) FROM diagnoses WHERE created_at >= datetime('now', '-1 day')"
        ).fetchone()[0]
        diagnoses_30d = cursor.execute(
            "SELECT count(*) FROM diagnoses WHERE created_at >= datetime('now', '-30 day')"
        ).fetchone()[0]

        # AI Assistant Usage
        total_ai_queries = cursor.execute("SELECT count(*) FROM chat_history").fetchone()[0]
        ai_queries_24h = cursor.execute(
            "SELECT count(*) FROM chat_history WHERE created_at >= datetime('now', '-1 day')"
        ).fetchone()[0]

        # Storage consumption (sum of uploaded image sizes if available or estimated)
        cursor.execute("SELECT count(*) FROM diagnoses WHERE image_path IS NOT NULL")
        image_count = cursor.fetchone()[0]
        estimated_storage_mb = round(image_count * 0.85, 2)  # ~850 KB per leaf capture

        # Plan distribution
        cursor.execute(
            """
            SELECT plan_id, count(*) as count
            FROM user_subscriptions
            WHERE status = 'active'
            GROUP BY plan_id
            """
        )
        plan_distribution = {r["plan_id"]: r["count"] for r in cursor.fetchall()}

    return {
        "success": True,
        "users": {
            "total": total_users,
            "active": active_users
        },
        "organizations": {
            "total": total_orgs,
            "seats_assigned": total_seats
        },
        "agriculture": {
            "total_farms": total_farms,
            "total_plots": total_plots
        },
        "diagnoses": {
            "total": total_diagnoses,
            "last_24h": diagnoses_24h,
            "last_30d": diagnoses_30d
        },
        "ai_assistant": {
            "total_queries": total_ai_queries,
            "last_24h": ai_queries_24h
        },
        "storage": {
            "total_images": image_count,
            "estimated_mb": estimated_storage_mb,
            "estimated_gb": round(estimated_storage_mb / 1024, 2)
        },
        "plans": plan_distribution
    }


# ============================================================================
# 9. COMBINED MODERATION QUEUE & ACTIONS
# ============================================================================
def get_moderation_queue(status_filter: Optional[str] = "pending", limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """Retrieve unified moderation items from both community reports and moderation cases."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    items = []
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()

        # 1. Community reports
        cr_query = "SELECT * FROM community_reports WHERE 1=1"
        cr_params = []
        if status_filter:
            cr_query += " AND status = ?"
            cr_params.append(status_filter)
        cr_query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        cr_params.extend([limit, offset])

        cursor.execute(cr_query, cr_params)
        for r in cursor.fetchall():
            row = dict(r)
            items.append({
                "id": f"comm_report_{row['id']}",
                "source": "community",
                "raw_id": row["id"],
                "reporter_user_id": row.get("reporter_user_id"),
                "target_type": row.get("target_type"),
                "target_id": row.get("target_id"),
                "reason": row.get("reason"),
                "details": row.get("details"),
                "status": row.get("status"),
                "created_at": row.get("created_at")
            })

        # 2. Moderation cases
        mc_query = "SELECT * FROM moderation_cases WHERE 1=1"
        mc_params = []
        if status_filter:
            mc_query += " AND status = ?"
            mc_params.append(status_filter)
        mc_query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        mc_params.extend([limit, offset])

        cursor.execute(mc_query, mc_params)
        for r in cursor.fetchall():
            row = dict(r)
            items.append({
                "id": f"mod_case_{row['id']}",
                "source": "system_case",
                "raw_id": row["id"],
                "reporter_user_id": row.get("user_id"),
                "target_type": row.get("category"),
                "target_id": row.get("id"),
                "reason": row.get("reason"),
                "details": row.get("description"),
                "status": row.get("status"),
                "created_at": row.get("created_at")
            })

    return {
        "success": True,
        "total": len(items),
        "items": items
    }


def resolve_moderation_item(
    host_admin: Dict[str, Any],
    source: str,
    raw_id: int,
    action: str,
    reason: str,
    confirm: bool,
    ip_address: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resolve a moderation item (dismiss, hide_content, warn_user, ban_user).
    Requires explicit confirmation for sensitive actions (hide_content, ban_user).
    """
    sensitive_actions = ("hide_content", "ban_user", "suspend_user")
    if action in sensitive_actions and not confirm:
        return {
            "success": False,
            "error": "confirmation_required",
            "message": f"Thao tác '{action}' yêu cầu xác nhận rõ ràng (confirm=True)."
        }

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        if source == "community":
            cursor.execute(
                """
                UPDATE community_reports
                SET status = 'reviewed', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP, admin_notes = ?
                WHERE id = ?
                """,
                (host_admin["id"], f"Action: {action}. Reason: {reason}", raw_id)
            )
        else:
            cursor.execute(
                """
                UPDATE moderation_cases
                SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP, host_notes = ?
                WHERE id = ?
                """,
                (f"Action: {action}. Reason: {reason}", raw_id)
            )
        conn.commit()

    gari_auth.record_host_audit(
        host_admin_id=host_admin["id"],
        host_email=host_admin.get("email"),
        action_type=f"MODERATION_{action.upper()}",
        target_resource=f"{source}:{raw_id}",
        details={"source": source, "raw_id": raw_id, "action": action},
        reason=reason,
        ip_address=ip_address
    )

    return {
        "success": True,
        "message": f"Đã xử lý mục kiểm duyệt #{raw_id} với hành động: {action}."
    }
