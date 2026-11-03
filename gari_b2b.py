"""
GARI AI LAB — B2B AgriTech Multi-Tenant Architecture & Revenue Foundation (gari_b2b.py)
Supports:
1. Multi-Tenant Organizations with strict RBAC (owner, admin, member, viewer)
2. Centralized Subscription & Plan System (Free, Pro, Team, Enterprise)
3. Organization-level Usage Metering & Concurrency-Safe Quota Management
4. API-as-a-Service Foundation (Hashed API keys, rate limits, revocation, usage logging)
5. Extensibility schemas for 10 revenue streams (White-label, B2B2C, Enterprise, Licensing)
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

logger = logging.getLogger("gari_b2b")

DB_PATH = Path(__file__).resolve().parent / "database" / "disease_detector.db"
# Reentrant lock: several helpers (e.g. onboarding -> quota/audit) call each other.
_B2B_LOCK = threading.RLock()

# -----------------------------------------------------------------------------
# SPRINT 2: ORGANIZATION CUSTOMER ENGINE CONSTANTS
# -----------------------------------------------------------------------------
ORG_STATUSES = ("pending", "active", "suspended", "archived")

# Explicit mapping from legacy / free-form statuses to the canonical lifecycle.
# This avoids a second parallel status system while preserving existing rows.
ORG_STATUS_ALIASES = {
    "pending": "pending",
    "onboarding": "pending",
    "draft": "pending",
    "active": "active",
    "enabled": "active",
    "approved": "active",
    "suspended": "suspended",
    "inactive": "suspended",
    "locked": "suspended",
    "disabled": "suspended",
    "archived": "archived",
    "deleted": "archived",
}

ORG_TYPES = (
    "smallholder_group",
    "cooperative",
    "farm",
    "dealer",
    "agribusiness",
    "other",
)

ORG_SCALES = (
    "under_1ha",
    "1_5ha",
    "5_20ha",
    "over_20ha",
    "unknown",
)

ORG_NEEDS = ("diagnosis", "member_management", "api", "pilot")
COMMERCIAL_INTENTS = ("none", "pilot_interest", "signed_contract")

INVITABLE_ROLES = ("admin", "manager", "member", "viewer")
INVITATION_TTL_HOURS = 168  # 7 days
INVITATION_RATE_LIMIT_PER_HOUR = 10
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

# Unpaid pilot workspace assigned to newly created organizations.
# A paid plan can only be granted by a platform admin.
PILOT_ORG_PLAN_ID = "pilot"
PAID_ORG_PLANS = {"pro", "team", "enterprise", "business", "personal"}

ROLE_PERMISSIONS: Dict[str, set] = {
    "owner": {
        "org.view", "org.profile.update", "org.status.manage", "org.audit.view",
        "members.view", "members.invite", "members.manage", "members.remove",
        "members.role_assign", "members.owner_transfer",
        "api_keys.view", "api_keys.manage", "usage.view",
        "onboarding.manage", "workflow.manage", "data.manage", "diagnosis.use",
    },
    "admin": {
        "org.view", "org.profile.update", "org.audit.view",
        "members.view", "members.invite", "members.manage", "members.remove",
        "members.role_assign",
        "api_keys.view", "api_keys.manage", "usage.view",
        "onboarding.manage", "workflow.manage", "data.manage", "diagnosis.use",
    },
    "manager": {
        "org.view", "members.view", "usage.view",
        "workflow.manage", "data.manage", "diagnosis.use",
    },
    "member": {
        "org.view", "members.view", "usage.view", "data.manage", "diagnosis.use",
    },
    "viewer": {
        "org.view", "members.view", "usage.view",
    },
}


class OrganizationError(Exception):
    """Base class for organization-domain errors."""


class OrganizationPermissionError(PermissionError):
    """Raised when a membership/permission check fails."""


class OrganizationStateError(ValueError):
    """Raised when an action is not allowed in the current lifecycle state."""


class InvitationError(ValueError):
    """Raised when an invitation cannot be created or accepted."""


class InvitationRateLimitError(InvitationError):
    """Raised when invitation creation exceeds the pilot rate limit."""


def normalize_org_status(status: Optional[str]) -> str:
    """Map legacy organization status names to the canonical Sprint 2 lifecycle."""
    return ORG_STATUS_ALIASES.get((status or "").strip().lower(), "pending")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)

# -----------------------------------------------------------------------------
# 1. CENTRALIZED PLAN DEFINITIONS (Single Source of Truth)
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# 1. CENTRALIZED PLAN DEFINITIONS (Single Source of Truth)
# -----------------------------------------------------------------------------
import gari_plans

PLANS_CONFIG = {
    "free": {
        "id": "free",
        "plan_id": "free",
        "name_vi": "Nông Hộ Cá Thể (Personal Free)",
        "display_name": "Nông Hộ Cá Thể (Personal Free)",
        "target_audience": "Nông dân cá thể, người làm vườn gia đình",
        "description": "Theo dõi sức khỏe mùa vụ cơ bản và ghi nhật ký nông trại miễn phí.",
        "quota_limit_per_cycle": 5,
        "quota_limit": 5,
        "is_unlimited_quota": False,
        "refresh_hours": 24,
        "max_members": 1,
        "allowed_models": ["standard_global", "crop_specific"],
        "has_vip_models": False,
        "has_api_access": False,
        "max_api_keys": 0,
        "can_export_csv": True,
        "can_export_data": True,
        "custom_branding": False,
        "support_level": "Cộng đồng & Hướng dẫn sử dụng",
        "price_vnd_month": 0,
        "price": 0,
        "currency": "VND",
        "price_status": "free",
        "price_text": "Miễn phí trọn đời",
        "is_active": True,
        "billing_interval": "daily"
    },
    "pro": {
        "id": "pro",
        "plan_id": "pro",
        "name_vi": "Kỹ Sư & Nhà Vườn Pro (Individual Pro / VIP)",
        "display_name": "Kỹ Sư & Nhà Vườn Pro (Individual Pro / VIP)",
        "target_audience": "Kỹ sư nông học, khuyến nông cơ sở, chủ trang trại độc lập",
        "description": "Mở khóa toàn bộ mô hình VIP (Model 2 & Model 4) với hạn mức phân loại mở rộng.",
        "quota_limit_per_cycle": 150,
        "quota_limit": 150,
        "is_unlimited_quota": False,
        "refresh_hours": 24,
        "max_members": 1,
        "allowed_models": ["standard_global", "crop_specific", "pro_global", "vip_models"],
        "has_vip_models": True,
        "has_api_access": False,
        "max_api_keys": 0,
        "can_export_csv": True,
        "can_export_data": True,
        "custom_branding": False,
        "support_level": "Ưu tiên kỹ thuật qua email/Zalo",
        "price_vnd_month": None,
        "price": None,
        "currency": "VND",
        "price_status": "pilot_beta",
        "price_text": "Thử nghiệm Pilot Beta (Kích hoạt theo đăng ký)",
        "price_display_note": "Chương trình thử nghiệm Pilot Beta (Kích hoạt qua thư mời / thỏa thuận)",
        "is_active": True,
        "billing_interval": "monthly"
    },
    "team": {
        "id": "team",
        "plan_id": "team",
        "name_vi": "Hợp Tác Xã & Trang Trại (Farm / Cooperative)",
        "display_name": "Hợp Tác Xã & Trang Trại (Farm / Cooperative)",
        "target_audience": "Hợp tác xã nông nghiệp, đại lý vật tư BVTV, trang trại vừa & nhỏ",
        "description": "Quản lý thành viên tập trung, phân quyền tổ chức, hạn ngạch chung và tích hợp API IoT.",
        "quota_limit_per_cycle": 800,
        "quota_limit": 800,
        "is_unlimited_quota": False,
        "refresh_hours": 24,
        "max_members": 15,
        "allowed_models": ["standard_global", "crop_specific", "pro_global", "vip_models"],
        "has_vip_models": True,
        "has_api_access": True,
        "max_api_keys": 5,
        "can_export_csv": True,
        "can_export_data": True,
        "custom_branding": False,
        "support_level": "Hỗ trợ triển khai pilot tại chỗ & chuyên gia 24/7",
        "price_vnd_month": None,
        "price": None,
        "currency": "VND",
        "price_status": "pilot_beta",
        "price_text": "Gói tài trợ thử nghiệm HTX Ba Vì & Tây Nguyên",
        "price_display_note": "Gói tài trợ thử nghiệm HTX Ba Vì & Tây Nguyên (Theo hợp đồng chuyển giao)",
        "is_active": True,
        "billing_interval": "monthly"
    },
    "enterprise": {
        "id": "enterprise",
        "plan_id": "enterprise",
        "name_vi": "Doanh Nghiệp & Đối Tác (Business / Enterprise)",
        "display_name": "Doanh Nghiệp & Đối Tác (Business / Enterprise)",
        "target_audience": "Tập đoàn nông nghiệp, đơn vị chế biến xuất khẩu, đối tác công nghệ",
        "description": "Hạn ngạch phân loại linh hoạt, không giới hạn thành viên, SLA cam kết 99.9%, hỗ trợ custom branding.",
        "quota_limit_per_cycle": -1,
        "quota_limit": None,
        "is_unlimited_quota": True,
        "refresh_hours": 24,
        "max_members": 1000,
        "allowed_models": ["standard_global", "crop_specific", "pro_global", "vip_models", "custom_weights"],
        "has_vip_models": True,
        "has_api_access": True,
        "max_api_keys": 50,
        "can_export_csv": True,
        "can_export_data": True,
        "custom_branding": True,
        "support_level": "SLA 99.9%, Kiến trúc sư giải pháp chuyên trách",
        "price_vnd_month": None,
        "price": None,
        "currency": "VND",
        "price_status": "custom_contract",
        "price_text": "Liên hệ đàm phán hợp đồng B2B",
        "price_display_note": "Liên hệ thỏa thuận hợp đồng giải pháp kỹ thuật riêng",
        "is_active": True,
        "billing_interval": "annual"
    },
    # Sprint 2: unpaid pilot workspace. New organizations start here and can
    # never receive a paid plan from a customer-facing request.
    "pilot": {
        "id": "pilot",
        "plan_id": "pilot",
        "name_vi": "Không Gian Pilot Tổ Chức (Unpaid Pilot)",
        "display_name": "Không Gian Pilot Tổ Chức (Unpaid Pilot)",
        "target_audience": "Nông hộ liên kết, hợp tác xã, đại lý và doanh nghiệp đang thử nghiệm",
        "description": "Không gian miễn phí để hoàn tất onboarding, mời thành viên và đánh giá nhu cầu trước khi ký hợp đồng dịch vụ.",
        "quota_limit_per_cycle": 50,
        "quota_limit": 50,
        "is_unlimited_quota": False,
        "refresh_hours": 24,
        "max_members": 10,
        "allowed_models": ["standard_global", "crop_specific"],
        "has_vip_models": False,
        "has_api_access": False,
        "max_api_keys": 0,
        "can_export_csv": True,
        "can_export_data": True,
        "custom_branding": False,
        "support_level": "Hỗ trợ pilot thủ công qua đội ngũ Gari",
        "price_vnd_month": 0,
        "price": None,
        "currency": "VND",
        "price_status": "pilot_unpaid",
        "price_text": "Miễn phí trong giai đoạn pilot (không phải hợp đồng dịch vụ)",
        "price_display_note": "Không tự động trở thành hợp đồng trả phí. Cần xác nhận riêng.",
        "is_active": True,
        "billing_interval": "monthly"
    }
}

# Canonical aliases for production pricing architecture
PLANS_CONFIG["personal"] = dict(
    PLANS_CONFIG["pro"],
    id="personal",
    plan_id="personal",
    name_vi="Cá nhân",
    display_name="Cá nhân",
    price_vnd_month=129000,
    price=129000
)
PLANS_CONFIG["business"] = dict(
    PLANS_CONFIG["team"],
    id="business",
    plan_id="business",
    name_vi="Doanh nghiệp",
    display_name="Doanh nghiệp",
    price_vnd_month=299000,
    price=299000
)

# Supported Roles
ROLES_HIERARCHY = {
    "owner": 5,
    "admin": 4,
    "manager": 3,
    "member": 2,
    "viewer": 1
}


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(cursor: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
    """Idempotently add a column to an existing SQLite table."""
    columns = [row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_b2b_database() -> None:
    """Initialize Multi-tenant B2B, API Key, Quota, and Extensibility tables."""
    with _B2B_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # 1. Organizations Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                owner_id INTEGER NOT NULL,
                plan_id TEXT NOT NULL DEFAULT 'pilot',
                status TEXT NOT NULL DEFAULT 'pending',
                contact_email TEXT,
                contact_phone TEXT,
                address TEXT,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users (id)
            );
            """)
            # Sprint 2 profile, lifecycle and safe-archive columns (idempotent).
            for col, col_type in [
                ("organization_type", "TEXT"),
                ("primary_crops", "TEXT"),
                ("region", "TEXT"),
                ("farming_scale", "TEXT"),
                ("scale_consent", "INTEGER DEFAULT 0"),
                ("business_contact_name", "TEXT"),
                ("business_contact_title", "TEXT"),
                ("business_contact_email", "TEXT"),
                ("business_contact_phone", "TEXT"),
                ("status_reason", "TEXT"),
                ("archived_at", "DATETIME"),
                ("archived_by", "INTEGER"),
                ("suspended_at", "DATETIME"),
            ]:
                _ensure_column(cursor, "organizations", col, col_type)

            # 2. Organization Members & Roles Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS organization_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                invited_by INTEGER,
                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (organization_id, user_id),
                FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
            """)

            # 3. Organization Quotas & Usage Cycles Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS organization_quotas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER UNIQUE NOT NULL,
                plan_id TEXT NOT NULL,
                quota_limit INTEGER NOT NULL,
                used_count INTEGER NOT NULL DEFAULT 0,
                cycle_start DATETIME NOT NULL,
                cycle_end DATETIME NOT NULL,
                last_used_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
            );
            """)

            # 4. API Keys Table (API-as-a-Service Foundation)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER NOT NULL,
                created_by_user_id INTEGER NOT NULL,
                key_name TEXT NOT NULL,
                key_prefix TEXT NOT NULL,
                key_hash TEXT UNIQUE NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                rate_limit_rpm INTEGER NOT NULL DEFAULT 60,
                total_calls INTEGER NOT NULL DEFAULT 0,
                last_used_at DATETIME,
                revoked_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
                FOREIGN KEY (created_by_user_id) REFERENCES users (id)
            );
            """)

            # 5. Fine-Grained Usage Metering Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS usage_metering (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER,
                user_id INTEGER,
                api_key_id INTEGER,
                caller_type TEXT NOT NULL DEFAULT 'web_user',
                model_name TEXT NOT NULL,
                crop_id TEXT,
                disease_predicted TEXT,
                status TEXT NOT NULL,
                quota_deducted BOOLEAN NOT NULL DEFAULT 1,
                latency_ms REAL NOT NULL DEFAULT 0.0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (organization_id) REFERENCES organizations (id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (api_key_id) REFERENCES api_keys (id)
            );
            """)

            # 6. Extensibility Table: White-label Branding (Revenue stream 5)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS organization_brandings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER UNIQUE NOT NULL,
                custom_brand_name TEXT,
                logo_url TEXT,
                primary_color TEXT DEFAULT '#10b981',
                accent_color TEXT DEFAULT '#059669',
                custom_domain TEXT,
                copyright_text TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
            );
            """)

            # 7. Extensibility Table: B2B2C Farmer Allocation (Revenue stream 3)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS b2b2c_allocations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER NOT NULL,
                farmer_name TEXT NOT NULL,
                farmer_phone TEXT NOT NULL,
                voucher_code TEXT UNIQUE NOT NULL,
                allocated_scans INTEGER NOT NULL DEFAULT 10,
                used_scans INTEGER NOT NULL DEFAULT 0,
                expires_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
            );
            """)

            # 8. Extensibility Table: Enterprise Contracts (Revenue stream 6)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS enterprise_contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER UNIQUE NOT NULL,
                contract_code TEXT UNIQUE NOT NULL,
                sla_uptime_percent REAL DEFAULT 99.9,
                custom_monthly_quota INTEGER DEFAULT 50000,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                support_lead TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
            );
            """)

            # 9. Extensibility Table: Software/Model Licensing (Revenue stream 9)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_licenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                licensee_name TEXT NOT NULL,
                license_key TEXT UNIQUE NOT NULL,
                model_identifier TEXT NOT NULL,
                allowed_nodes INTEGER DEFAULT 1,
                offline_token_hash TEXT,
                expires_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 10. Sprint 2: Organization Invitations (hashed token, manual delivery)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS organization_invitations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                token_hash TEXT UNIQUE NOT NULL,
                token_prefix TEXT,
                status TEXT NOT NULL DEFAULT 'pending', -- pending | accepted | revoked | expired
                delivery_mode TEXT NOT NULL DEFAULT 'manual',
                delivery_status TEXT NOT NULL DEFAULT 'pending_manual_delivery',
                invited_by_user_id INTEGER,
                accepted_by_user_id INTEGER,
                expires_at DATETIME NOT NULL,
                accepted_at DATETIME,
                revoked_at DATETIME,
                revoked_by_user_id INTEGER,
                revoke_reason TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
                FOREIGN KEY (invited_by_user_id) REFERENCES users (id),
                FOREIGN KEY (accepted_by_user_id) REFERENCES users (id)
            );
            """)

            # 11. Sprint 2: Organization Audit Trail (actor, org, action, reason)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS organization_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER NOT NULL,
                actor_user_id INTEGER,
                action TEXT NOT NULL,
                target_type TEXT,
                target_id INTEGER,
                reason TEXT,
                metadata_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
                FOREIGN KEY (actor_user_id) REFERENCES users (id)
            );
            """)

            # 12. Sprint 2: Resumable B2B onboarding state
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS organization_onboarding (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id INTEGER UNIQUE NOT NULL,
                current_step INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'in_progress', -- in_progress | completed
                profile_completed INTEGER NOT NULL DEFAULT 0,
                role_confirmed INTEGER NOT NULL DEFAULT 0,
                needs_json TEXT,
                commercial_intent TEXT NOT NULL DEFAULT 'none',
                completed_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
            );
            """)

            # Indexing for high-performance multi-tenant isolation
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_org_members_user ON organization_members(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_org_members_org ON organization_members(organization_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_org ON api_keys(organization_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_metering_org ON usage_metering(organization_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_metering_user ON usage_metering(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_metering_created ON usage_metering(created_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_org_invitations_org ON organization_invitations(organization_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_org_invitations_email ON organization_invitations(email);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_org_invitations_hash ON organization_invitations(token_hash);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_org_audit_org ON organization_audit_log(organization_id, created_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_org_onboarding_org ON organization_onboarding(organization_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_org_status ON organizations(status);")

            # Seed default demo organization for User 1 if not exists
            cursor.execute("SELECT COUNT(*) FROM organizations")
            if cursor.fetchone()[0] == 0:
                # Seed User 1's Coop
                cursor.execute("""
                INSERT INTO organizations (name, slug, owner_id, plan_id, contact_email, contact_phone, address, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    "Hợp Tác Xã Nông Nghiệp Ba Vì",
                    "htx-ba-vi",
                    1,
                    "team",
                    "danhuynh@gari.vn",
                    "0912345678",
                    "Xã Vân Hòa, Ba Vì, Hà Nội",
                    "Hợp tác xã thí nghiệm B2B SaaS quản lý chẩn đoán sức khỏe vùng trồng cà chua và rau hữu cơ."
                ))
                org_id = cursor.lastrowid

                # Add User 1 as Owner
                cursor.execute("""
                INSERT INTO organization_members (organization_id, user_id, role)
                VALUES (?, ?, 'owner')
                """, (org_id, 1))

                # Add User 7 (sample farmer) as Member
                cursor.execute("""
                INSERT INTO organization_members (organization_id, user_id, role)
                VALUES (?, 7, 'member')
                """, (org_id,))

                # Initialize Quota for Team Plan (800 scans / 24h)
                now_utc = datetime.now(timezone.utc)
                now_iso = now_utc.strftime("%Y-%m-%d %H:%M:%S")
                end_iso = (now_utc + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

                cursor.execute("""
                INSERT INTO organization_quotas (organization_id, plan_id, quota_limit, used_count, cycle_start, cycle_end)
                VALUES (?, 'team', 800, 0, ?, ?)
                """, (org_id, now_iso, end_iso))

                # Seed Demo API Key
                demo_key_raw = "gari_live_bavi_sample_team_api_key_2026"
                demo_hash = hashlib.sha256(demo_key_raw.encode("utf-8")).hexdigest()
                cursor.execute("""
                INSERT INTO api_keys (organization_id, created_by_user_id, key_name, key_prefix, key_hash, is_active, rate_limit_rpm)
                VALUES (?, 1, 'Cổng tích hợp Trạm quan trắc IoT', 'gari_live_bavi...', ?, 1, 120)
                """, (org_id, demo_hash))

            conn.commit()


# Initialize on import
init_b2b_database()


# -----------------------------------------------------------------------------
# 2. MULTI-TENANT ORGANIZATION & RBAC OPERATIONS
# -----------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Generate URL-safe slug from organization name."""
    text = (text or "").lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text or f"org-{secrets.token_hex(4)}"


def create_organization(
    name: str,
    owner_id: int,
    plan_id: str = PILOT_ORG_PLAN_ID,
    contact_email: Optional[str] = None,
    contact_phone: Optional[str] = None,
    address: Optional[str] = None,
    actor_is_platform_admin: bool = False,
    organization_type: Optional[str] = None,
    region: Optional[str] = None,
    primary_crops: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Create a new organization.

    Security/product rule: a customer-facing creation starts on the unpaid pilot
    plan and in the `pending` lifecycle state. Only an explicit platform-admin
    action may assign a paid plan. New organizations never silently become
    Enterprise/Team customers.
    """
    name = (name or "").strip()
    if not name or len(name) < 2:
        raise ValueError("Tên tổ chức phải có ít nhất 2 ký tự.")
    if len(name) > 160:
        raise ValueError("Tên tổ chức không được vượt quá 160 ký tự.")

    requested_plan = (plan_id or "").strip().lower()
    if requested_plan not in PLANS_CONFIG:
        requested_plan = PILOT_ORG_PLAN_ID
    if requested_plan in PAID_ORG_PLANS and not actor_is_platform_admin:
        assigned_plan_id = PILOT_ORG_PLAN_ID
    else:
        assigned_plan_id = requested_plan

    plan = PLANS_CONFIG.get(assigned_plan_id, PLANS_CONFIG[PILOT_ORG_PLAN_ID])
    base_slug = slugify(name)
    slug = base_slug

    with _B2B_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Ensure slug uniqueness
            cursor.execute("SELECT id FROM organizations WHERE slug = ?", (slug,))
            if cursor.fetchone():
                slug = f"{base_slug}-{secrets.token_hex(3)}"

            crops_json = json.dumps([str(c).strip()[:60] for c in (primary_crops or []) if str(c).strip()][:10], ensure_ascii=False)
            cursor.execute("""
            INSERT INTO organizations
                (name, slug, owner_id, plan_id, status, contact_email, contact_phone, address,
                 organization_type, region, primary_crops)
            VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)
            """, (name, slug, owner_id, assigned_plan_id, contact_email, contact_phone, address,
                  organization_type, region, crops_json))
            org_id = cursor.lastrowid

            # Add owner member
            cursor.execute("""
            INSERT INTO organization_members (organization_id, user_id, role)
            VALUES (?, ?, 'owner')
            """, (org_id, owner_id))

            # Initialize Organization Quota using the assigned (unpaid) pilot plan
            now = now_utc()
            now_iso = now.strftime("%Y-%m-%d %H:%M:%S")
            end_iso = (now + timedelta(hours=plan["refresh_hours"])).strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
            INSERT INTO organization_quotas (organization_id, plan_id, quota_limit, used_count, cycle_start, cycle_end)
            VALUES (?, ?, ?, 0, ?, ?)
            """, (org_id, plan["id"], plan["quota_limit_per_cycle"], now_iso, end_iso))

            # Initialize resumable onboarding state
            cursor.execute("""
            INSERT OR IGNORE INTO organization_onboarding (organization_id, current_step, status)
            VALUES (?, 1, 'in_progress')
            """, (org_id,))

            _write_audit(cursor, org_id, owner_id, "organization.created", "organization", org_id,
                         reason="Khởi tạo tổ chức", metadata={
                             "requested_plan": requested_plan,
                             "assigned_plan": assigned_plan_id,
                             "status": "pending",
                         })
            conn.commit()

            cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
            return dict(cursor.fetchone())



def get_user_organizations(user_id: int) -> List[Dict[str, Any]]:
    """List all organizations that a user belongs to, including role, plan and onboarding state."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT o.*, m.role as user_role, m.joined_at, q.quota_limit, q.used_count, q.cycle_end,
               ob.current_step as onboarding_step, ob.status as onboarding_status
        FROM organizations o
        JOIN organization_members m ON o.id = m.organization_id
        LEFT JOIN organization_quotas q ON o.id = q.organization_id
        LEFT JOIN organization_onboarding ob ON o.id = ob.organization_id
        WHERE m.user_id = ?
        ORDER BY (m.role = 'owner') DESC, o.created_at DESC
        """, (user_id,))
        rows = cursor.fetchall()

        results = []
        for r in rows:
            item = dict(r)
            plan = PLANS_CONFIG.get(item["plan_id"], PLANS_CONFIG[PILOT_ORG_PLAN_ID])
            item["plan_details"] = plan
            item["status"] = normalize_org_status(item.get("status"))
            item["is_operational"] = item["status"] == "active"
            item["remaining_quota"] = None if item.get("quota_limit") in (None, -1) else max(0, item.get("quota_limit", 0) - item.get("used_count", 0))
            item["permissions"] = sorted(ROLE_PERMISSIONS.get(item.get("user_role"), set()))
            results.append(item)
        return results



def get_organization_detail(org_id: int) -> Optional[Dict[str, Any]]:
    """Get organization metadata, lifecycle, profile, plan, onboarding and quota overview."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT o.*, u.full_name as owner_name, u.email as owner_email
        FROM organizations o
        JOIN users u ON o.owner_id = u.id
        WHERE o.id = ?
        """, (org_id,))
        row = cursor.fetchone()
        if not row:
            return None

        org = dict(row)
        org["status"] = normalize_org_status(org.get("status"))
        org["legacy_status"] = row["status"] if "status" in row.keys() else None
        plan = PLANS_CONFIG.get(org["plan_id"], PLANS_CONFIG[PILOT_ORG_PLAN_ID])
        org["plan_details"] = plan
        try:
            org["primary_crops"] = json.loads(org.get("primary_crops") or "[]")
        except Exception:
            org["primary_crops"] = []

        # Members count
        cursor.execute("SELECT COUNT(*) FROM organization_members WHERE organization_id = ?", (org_id,))
        org["members_count"] = cursor.fetchone()[0]

        # Active API keys count
        cursor.execute("SELECT COUNT(*) FROM api_keys WHERE organization_id = ? AND is_active = 1", (org_id,))
        org["active_api_keys_count"] = cursor.fetchone()[0]

        # Pending invitations count
        cursor.execute("SELECT COUNT(*) FROM organization_invitations WHERE organization_id = ? AND status = 'pending'", (org_id,))
        org["pending_invitations_count"] = cursor.fetchone()[0]

        # Quota status
        org["quota"] = get_organization_quota_status(org_id)

        # Resumable onboarding state
        org["onboarding"] = get_organization_onboarding(org_id)
        org["is_operational"] = org["status"] == "active"
        org["pilot_contact"] = {
            "email": "pilot@gari.vn",
            "note": "Giai đoạn pilot: đội ngũ Gari gửi lời mời và hợp đồng thủ công, chưa có email tự động.",
        }
        return org



def get_member_role(org_id: int, user_id: int) -> Optional[str]:
    """Return the canonical role of a user inside an organization, or None."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role FROM organization_members WHERE organization_id = ? AND user_id = ?",
            (org_id, user_id),
        )
        row = cursor.fetchone()
        return (row["role"] or "").lower() if row else None


def check_user_org_permission(org_id: int, user_id: int, required_role: str = "member") -> Tuple[bool, Optional[str]]:
    """
    Backward-compatible role hierarchy check.
    New code should use has_permission()/require_permission() with explicit
    capabilities instead of relying on role names.
    """
    current_role = get_member_role(org_id, user_id)
    if not current_role:
        return False, None
    current_weight = ROLES_HIERARCHY.get(current_role, 0)
    required_weight = ROLES_HIERARCHY.get(required_role, 0)
    return (current_weight >= required_weight), current_role


def has_permission(org_id: int, user_id: int, permission: str) -> Tuple[bool, Optional[str]]:
    """Authoritative capability check backed by the authenticated membership."""
    role = get_member_role(org_id, user_id)
    if not role:
        return False, None
    return permission in ROLE_PERMISSIONS.get(role, set()), role


def require_permission(org_id: int, user_id: int, permission: str) -> str:
    """Raise OrganizationPermissionError unless membership grants the capability."""
    allowed, role = has_permission(org_id, user_id, permission)
    if not allowed:
        raise OrganizationPermissionError("Bạn không có quyền thực hiện thao tác này trong tổ chức.")
    return role or ""


def get_organization_status(org_id: int) -> Optional[str]:
    """Return the canonical lifecycle status of an organization."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM organizations WHERE id = ?", (org_id,))
        row = cursor.fetchone()
        return normalize_org_status(row["status"]) if row else None


def ensure_organization_operational(org_id: int) -> str:
    """Block usage of an organization that is not active (pending/suspended/archived)."""
    status = get_organization_status(org_id)
    if status is None:
        raise OrganizationStateError("Tổ chức không tồn tại.")
    if status != "active":
        labels = {
            "pending": "đang chờ hoàn tất onboarding",
            "suspended": "đang bị tạm ngưng",
            "archived": "đã được lưu trữ",
        }
        raise OrganizationStateError(
            f"Tổ chức {labels.get(status, status)} nên không thể sử dụng tính năng này. "
            "Vui lòng liên hệ chủ sở hữu hoặc đội ngũ Gari."
        )
    return status


def _ensure_organization_editable(org_id: int) -> str:
    """Membership/profile writes are allowed while pending or active, not suspended/archived."""
    status = get_organization_status(org_id)
    if status is None:
        raise OrganizationStateError("Tổ chức không tồn tại.")
    if status in ("suspended", "archived"):
        raise OrganizationStateError("Tổ chức đang bị tạm ngưng hoặc đã lưu trữ; không thể thay đổi dữ liệu.")
    return status


def _write_audit(
    cursor: sqlite3.Cursor,
    org_id: int,
    actor_user_id: Optional[int],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    reason: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Insert an append-only organization audit record."""
    cursor.execute("""
        INSERT INTO organization_audit_log
            (organization_id, actor_user_id, action, target_type, target_id, reason, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        org_id,
        actor_user_id,
        action,
        target_type,
        target_id,
        reason,
        json.dumps(metadata or {}, ensure_ascii=False, default=str),
    ))


def get_organization_audit_log(org_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    """Return the organization audit trail with actor identity."""
    limit = max(1, min(int(limit or 100), 500))
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.*, u.full_name as actor_name, u.email as actor_email
            FROM organization_audit_log a
            LEFT JOIN users u ON a.actor_user_id = u.id
            WHERE a.organization_id = ?
            ORDER BY a.created_at DESC, a.id DESC
            LIMIT ?
        """, (org_id, limit))
        rows = []
        for row in cursor.fetchall():
            item = dict(row)
            try:
                item["metadata"] = json.loads(item.get("metadata_json") or "{}")
            except Exception:
                item["metadata"] = {}
            rows.append(item)
        return rows


def get_organization_members(org_id: int) -> List[Dict[str, Any]]:
    """List all members of an organization with profile info and capabilities."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT m.id as membership_id, m.role, m.joined_at, u.id as user_id,
               u.full_name, u.name, u.email, u.phone, u.account_type
        FROM organization_members m
        JOIN users u ON m.user_id = u.id
        WHERE m.organization_id = ?
        ORDER BY (m.role = 'owner') DESC, (m.role = 'admin') DESC, m.joined_at ASC
        """, (org_id,))
        members = []
        for r in cursor.fetchall():
            item = dict(r)
            item["full_name"] = item.get("full_name") or item.get("name") or "Người dùng"
            item["role"] = (item.get("role") or "member").lower()
            item["permissions"] = sorted(ROLE_PERMISSIONS.get(item["role"], set()))
            members.append(item)
        return members


def _validate_assignable_role(actor_role: str, new_role: str) -> str:
    """Validate role changes so no one can grant more authority than allowed."""
    new_role = (new_role or "").strip().lower()
    if new_role not in ROLES_HIERARCHY:
        raise ValueError("Vai trò không hợp lệ (owner, admin, manager, member, viewer).")
    if new_role == "owner":
        raise ValueError("Không thể cấp vai trò owner trực tiếp. Hãy dùng luồng chuyển giao quyền sở hữu.")
    if actor_role == "admin" and new_role == "admin":
        raise OrganizationPermissionError("Chỉ Chủ sở hữu mới có quyền chỉ định Quản trị viên (Admin).")
    return new_role


def add_member_by_email(org_id: int, actor_user_id: int, email: str, role: str = "member") -> Dict[str, Any]:
    """
    Directly add an existing user by email. Kept for admin tooling/backward
    compatibility; the primary Sprint 2 flow is the hashed-token invitation.
    """
    actor_role = require_permission(org_id, actor_user_id, "members.manage")
    _ensure_organization_editable(org_id)
    email = (email or "").strip().lower()
    if not EMAIL_REGEX.match(email):
        raise ValueError("Địa chỉ email không đúng định dạng.")
    role = _validate_assignable_role(actor_role, role)
    if actor_role != "owner" and role == "admin":
        raise OrganizationPermissionError("Chỉ Chủ sở hữu mới có quyền chỉ định Quản trị viên (Admin).")

    # Check Plan member limit
    org = get_organization_detail(org_id)
    if not org:
        raise ValueError("Tổ chức không tồn tại.")
    max_m = org["plan_details"]["max_members"]
    if org["members_count"] >= max_m:
        raise ValueError(f"Tổ chức đã đạt giới hạn tối đa {max_m} thành viên theo gói {org['plan_details']['name_vi']}.")

    with _B2B_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, full_name, email FROM users WHERE LOWER(email) = LOWER(?)", (email,))
            user_row = cursor.fetchone()
            if not user_row:
                raise ValueError("Không tìm thấy tài khoản với email này trong hệ thống. Vui lòng gửi lời mời để họ tạo tài khoản.")

            target_user_id = user_row["id"]
            if target_user_id == actor_user_id:
                raise ValueError("Bạn không thể tự thêm mình vào tổ chức.")

            cursor.execute("""
            SELECT id FROM organization_members
            WHERE organization_id = ? AND user_id = ?
            """, (org_id, target_user_id))
            if cursor.fetchone():
                raise ValueError("Thành viên này đã tham gia tổ chức.")

            cursor.execute("""
            INSERT INTO organization_members (organization_id, user_id, role, invited_by)
            VALUES (?, ?, ?, ?)
            """, (org_id, target_user_id, role, actor_user_id))
            _write_audit(cursor, org_id, actor_user_id, "member.added", "user", target_user_id,
                         reason="Thêm thành viên trực tiếp", metadata={"role": role})
            conn.commit()

            return {
                "user_id": target_user_id,
                "email": user_row["email"],
                "full_name": user_row["full_name"],
                "role": role
            }


def update_member_role(org_id: int, actor_user_id: int, target_user_id: int, new_role: str, reason: Optional[str] = None) -> None:
    """Update a member role. Owner is only transferable through transfer_ownership()."""
    actor_role = require_permission(org_id, actor_user_id, "members.role_assign")
    _ensure_organization_editable(org_id)
    new_role = _validate_assignable_role(actor_role, new_role)

    with _B2B_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT role FROM organization_members WHERE organization_id = ? AND user_id = ?", (org_id, target_user_id))
            target_row = cursor.fetchone()
            if not target_row:
                raise ValueError("Thành viên không thuộc tổ chức này.")
            old_role = (target_row["role"] or "member").lower()

            if target_user_id == actor_user_id:
                raise OrganizationPermissionError("Bạn không thể tự thay đổi vai trò của chính mình.")
            if old_role == "owner":
                raise OrganizationPermissionError("Không thể thay đổi vai trò của Chủ sở hữu. Hãy chuyển giao quyền sở hữu trước.")
            if actor_role == "admin" and old_role == "admin":
                raise OrganizationPermissionError("Admin không thể thay đổi vai trò của Admin khác.")
            if actor_role == "admin" and target_user_id == actor_user_id:
                raise OrganizationPermissionError("Admin không thể tự nâng quyền.")

            cursor.execute("""
            UPDATE organization_members SET role = ?
            WHERE organization_id = ? AND user_id = ?
            """, (new_role, org_id, target_user_id))
            _write_audit(cursor, org_id, actor_user_id, "member.role_changed", "user", target_user_id,
                         reason=reason or "Cập nhật vai trò thành viên",
                         metadata={"old_role": old_role, "new_role": new_role})
            conn.commit()


def transfer_ownership(org_id: int, actor_user_id: int, target_user_id: int, reason: str) -> Dict[str, Any]:
    """
    Safely transfer ownership in one transaction:
    - only the current owner may call it
    - the target must already be a member
    - the organization always keeps exactly one owner
    """
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise ValueError("Vui lòng cung cấp lý do chuyển giao quyền sở hữu.")
    _ensure_organization_editable(org_id)

    with _B2B_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT owner_id, status FROM organizations WHERE id = ?", (org_id,))
            org_row = cursor.fetchone()
            if not org_row:
                raise ValueError("Tổ chức không tồn tại.")
            if org_row["owner_id"] != actor_user_id:
                raise OrganizationPermissionError("Chỉ Chủ sở hữu hiện tại mới có quyền chuyển giao quyền sở hữu.")
            if target_user_id == actor_user_id:
                raise ValueError("Bạn đã là Chủ sở hữu của tổ chức.")

            cursor.execute("SELECT role FROM organization_members WHERE organization_id = ? AND user_id = ?", (org_id, target_user_id))
            target_row = cursor.fetchone()
            if not target_row:
                raise ValueError("Người nhận chuyển giao phải là thành viên của tổ chức.")

            cursor.execute("UPDATE organization_members SET role = 'admin' WHERE organization_id = ? AND user_id = ?", (org_id, actor_user_id))
            cursor.execute("UPDATE organization_members SET role = 'owner' WHERE organization_id = ? AND user_id = ?", (org_id, target_user_id))
            cursor.execute("UPDATE organizations SET owner_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (target_user_id, org_id))
            _write_audit(cursor, org_id, actor_user_id, "organization.owner_transferred", "user", target_user_id,
                         reason=reason, metadata={"previous_owner_id": actor_user_id, "new_owner_id": target_user_id})
            conn.commit()

    return {"organization_id": org_id, "previous_owner_id": actor_user_id, "new_owner_id": target_user_id}


def remove_member(org_id: int, actor_user_id: int, target_user_id: int, reason: Optional[str] = None) -> None:
    """Remove a member while protecting the sole-owner invariant."""
    actor_role = get_member_role(org_id, actor_user_id)
    if not actor_role:
        raise OrganizationPermissionError("Bạn không phải thành viên của tổ chức này.")
    _ensure_organization_editable(org_id)

    is_self = actor_user_id == target_user_id
    if not is_self:
        require_permission(org_id, actor_user_id, "members.remove")

    with _B2B_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT role FROM organization_members WHERE organization_id = ? AND user_id = ?", (org_id, target_user_id))
            target_row = cursor.fetchone()
            if not target_row:
                raise ValueError("Thành viên không thuộc tổ chức.")
            target_role = (target_row["role"] or "member").lower()

            if target_role == "owner":
                raise OrganizationPermissionError("Không thể xóa Chủ sở hữu. Hãy chuyển giao quyền sở hữu trước.")
            if is_self and actor_role == "owner":
                raise OrganizationPermissionError("Chủ sở hữu phải chuyển giao quyền trước khi rời tổ chức.")
            if actor_role == "admin" and target_role == "admin" and not is_self:
                raise OrganizationPermissionError("Admin không thể xóa Admin khác.")

            cursor.execute("DELETE FROM organization_members WHERE organization_id = ? AND user_id = ?", (org_id, target_user_id))
            _write_audit(cursor, org_id, actor_user_id, "member.removed", "user", target_user_id,
                         reason=reason or ("Tự rời tổ chức" if is_self else "Xóa thành viên"),
                         metadata={"removed_role": target_role})
            conn.commit()


def transition_organization_status(
    org_id: int,
    actor_user_id: int,
    new_status: str,
    reason: str,
    is_platform_admin: bool = False,
) -> Dict[str, Any]:
    """
    Change the organization lifecycle state with an explicit reason and audit.
    Archive is logical only: rows, usage history, members and plans are retained.
    """
    canonical = normalize_org_status(new_status)
    if (new_status or "").strip().lower() not in ORG_STATUSES and (new_status or "").strip().lower() not in ORG_STATUS_ALIASES:
        raise ValueError("Trạng thái tổ chức không hợp lệ (pending, active, suspended, archived).")
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise ValueError("Vui lòng cung cấp lý do thay đổi trạng thái tổ chức.")

    allowed_transitions = {
        "pending": {"active", "archived"},
        "active": {"suspended", "archived"},
        "suspended": {"active", "archived"},
        "archived": {"active"},
    }

    with _B2B_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError("Tổ chức không tồn tại.")
            old_status = normalize_org_status(row["status"])

            if not is_platform_admin:
                require_permission(org_id, actor_user_id, "org.status.manage")
            if canonical == old_status:
                return {"organization_id": org_id, "status": canonical, "changed": False}
            if canonical not in allowed_transitions.get(old_status, set()):
                raise OrganizationStateError(f"Không thể chuyển tổ chức từ '{old_status}' sang '{canonical}'.")

            sets = ["status = ?", "status_reason = ?", "updated_at = CURRENT_TIMESTAMP"]
            params: List[Any] = [canonical, reason]
            if canonical == "archived":
                sets += ["archived_at = CURRENT_TIMESTAMP", "archived_by = ?"]
                params.append(actor_user_id)
                # Pending invitations must not be usable after archive.
                cursor.execute("""
                    UPDATE organization_invitations
                    SET status = 'revoked', revoked_at = CURRENT_TIMESTAMP,
                        revoked_by_user_id = ?, revoke_reason = 'organization_archived',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE organization_id = ? AND status = 'pending'
                """, (actor_user_id, org_id))
            elif canonical == "suspended":
                sets += ["suspended_at = CURRENT_TIMESTAMP"]
            elif canonical == "active":
                sets += ["archived_at = NULL", "archived_by = NULL", "suspended_at = NULL"]
            params.append(org_id)

            cursor.execute(f"UPDATE organizations SET {', '.join(sets)} WHERE id = ?", params)
            _write_audit(cursor, org_id, actor_user_id, "organization.status_changed", "organization", org_id,
                         reason=reason, metadata={"old_status": old_status, "new_status": canonical,
                                                  "platform_admin": bool(is_platform_admin)})
            conn.commit()

    return {"organization_id": org_id, "old_status": old_status, "status": canonical, "changed": True}


def archive_organization(org_id: int, actor_user_id: int, reason: str, is_platform_admin: bool = False) -> Dict[str, Any]:
    """Safe archive: logical status only, no physical deletion of history."""
    return transition_organization_status(org_id, actor_user_id, "archived", reason, is_platform_admin)


# -----------------------------------------------------------------------------
# SPRINT 2: ORGANIZATION PROFILE
# -----------------------------------------------------------------------------

PROFILE_UPDATE_FIELDS = {
    "name", "organization_type", "primary_crops", "region", "farming_scale",
    "scale_consent", "contact_email", "contact_phone", "address", "notes",
    "business_contact_name", "business_contact_title", "business_contact_email",
    "business_contact_phone",
}

FORBIDDEN_PROFILE_FIELDS = {
    "cccd", "cmnd", "id_number", "national_id", "passport", "bank_account",
    "tax_code", "personal_finance", "exact_latitude", "exact_longitude",
    "gps_coordinates",
}


def _clean_text(value: Any, max_len: int, field_name: str, required: bool = False) -> Optional[str]:
    if value is None:
        if required:
            raise ValueError(f"{field_name} không được để trống.")
        return None
    text = str(value).strip()
    if required and not text:
        raise ValueError(f"{field_name} không được để trống.")
    if len(text) > max_len:
        raise ValueError(f"{field_name} không được vượt quá {max_len} ký tự.")
    return text or None


def update_organization_profile(
    org_id: int,
    actor_user_id: int,
    updates: Dict[str, Any],
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate and update the organization profile. Explicitly rejects sensitive
    personal/financial identifiers and precise farm coordinates.
    """
    require_permission(org_id, actor_user_id, "org.profile.update")
    status = get_organization_status(org_id)
    if status == "archived":
        raise OrganizationStateError("Tổ chức đã lưu trữ; hãy khôi phục trước khi cập nhật hồ sơ.")
    if status not in ("pending", "active", "suspended"):
        raise OrganizationStateError("Không thể cập nhật hồ sơ ở trạng thái hiện tại.")

    updates = dict(updates or {})
    forbidden = sorted(set(updates.keys()) & FORBIDDEN_PROFILE_FIELDS)
    if forbidden:
        raise ValueError("Gari không thu thập CCCD, dữ liệu tài chính cá nhân hoặc tọa độ chính xác của nông trại. "
                         f"Trường không được phép: {', '.join(forbidden)}")
    unknown = sorted(set(updates.keys()) - PROFILE_UPDATE_FIELDS)
    if unknown:
        raise ValueError(f"Trường hồ sơ không hợp lệ: {', '.join(unknown)}")

    clean: Dict[str, Any] = {}
    if "name" in updates:
        clean["name"] = _clean_text(updates["name"], 160, "Tên tổ chức", required=True)
    if "organization_type" in updates:
        value = updates["organization_type"]
        if value in (None, ""):
            clean["organization_type"] = None
        elif str(value) not in ORG_TYPES:
            raise ValueError(f"Loại hình tổ chức không hợp lệ. Hợp lệ: {', '.join(ORG_TYPES)}")
        else:
            clean["organization_type"] = str(value)
    if "primary_crops" in updates:
        crops = updates["primary_crops"]
        if crops is None:
            crops = []
        elif isinstance(crops, str):
            crops = [c.strip() for c in crops.split(",") if c.strip()]
        if not isinstance(crops, list):
            raise ValueError("Cây trồng chủ lực phải là danh sách.")
        if len(crops) > 10:
            raise ValueError("Chỉ được chọn tối đa 10 cây trồng chủ lực.")
        cleaned_crops = []
        for crop in crops:
            crop_text = str(crop).strip()
            if crop_text:
                if len(crop_text) > 60:
                    raise ValueError("Tên cây trồng không được vượt quá 60 ký tự.")
                cleaned_crops.append(crop_text)
        clean["primary_crops"] = json.dumps(cleaned_crops, ensure_ascii=False)
    if "region" in updates:
        clean["region"] = _clean_text(updates["region"], 120, "Khu vực hoạt động")
    if "farming_scale" in updates:
        scale = updates["farming_scale"]
        if scale in (None, ""):
            clean["farming_scale"] = None
        elif str(scale) not in ORG_SCALES:
            raise ValueError(f"Quy mô canh tác không hợp lệ. Hợp lệ: {', '.join(ORG_SCALES)}")
        else:
            clean["farming_scale"] = str(scale)
    if "scale_consent" in updates:
        clean["scale_consent"] = 1 if updates["scale_consent"] in (True, 1, "1", "true", "True") else 0
    if "contact_email" in updates:
        email = _clean_text(updates["contact_email"], 160, "Email liên hệ")
        if email and not EMAIL_REGEX.match(email):
            raise ValueError("Email liên hệ không đúng định dạng.")
        clean["contact_email"] = email.lower() if email else None
    for field, label, max_len in [
        ("contact_phone", "Số điện thoại liên hệ", 40),
        ("address", "Địa chỉ/khu vực", 200),
        ("notes", "Ghi chú", 1000),
        ("business_contact_name", "Tên người liên hệ", 100),
        ("business_contact_title", "Chức danh người liên hệ", 100),
    ]:
        if field in updates:
            clean[field] = _clean_text(updates[field], max_len, label)
    if "business_contact_email" in updates:
        email = _clean_text(updates["business_contact_email"], 160, "Email công việc")
        if email and not EMAIL_REGEX.match(email):
            raise ValueError("Email công việc không đúng định dạng.")
        clean["business_contact_email"] = email.lower() if email else None
    if "business_contact_phone" in updates:
        clean["business_contact_phone"] = _clean_text(updates["business_contact_phone"], 40, "Điện thoại công việc")

    if clean.get("scale_consent", 0) not in (1, True) and clean.get("farming_scale"):
        raise ValueError("Quy mô canh tác là thông tin tự nguyện; cần bật consent trước khi lưu.")

    with _B2B_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
            current = cursor.fetchone()
            if not current:
                raise ValueError("Tổ chức không tồn tại.")
            current_dict = dict(current)

            changed = {}
            for field, value in clean.items():
                old_value = current_dict.get(field)
                if field == "scale_consent":
                    old_value = int(old_value or 0)
                    value = int(value or 0)
                if old_value != value:
                    changed[field] = {"old": old_value, "new": value}

            if changed:
                set_clause = ", ".join(f"{field} = ?" for field in changed.keys())
                params = [clean[field] for field in changed.keys()] + [org_id]
                cursor.execute(
                    f"UPDATE organizations SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    params,
                )
                _write_audit(cursor, org_id, actor_user_id, "organization.profile_updated", "organization", org_id,
                             reason=reason or "Cập nhật hồ sơ tổ chức",
                             metadata={"changed_fields": changed})
                conn.commit()

    return get_organization_detail(org_id) or {}


# -----------------------------------------------------------------------------
# SPRINT 2: INVITATIONS (hashed token, expiry, revoke, manual delivery)
# -----------------------------------------------------------------------------

def _hash_invitation_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_invitation(
    org_id: int,
    actor_user_id: int,
    email: str,
    role: str = "member",
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a hashed, expiring invitation. Raw token is returned once to the
    inviter for manual delivery during the pilot. Email existence is never
    revealed in the response shape.
    """
    actor_role = require_permission(org_id, actor_user_id, "members.invite")
    _ensure_organization_editable(org_id)
    email = (email or "").strip().lower()
    if not EMAIL_REGEX.match(email):
        raise ValueError("Địa chỉ email không đúng định dạng.")
    role = (role or "member").strip().lower()
    if role not in INVITABLE_ROLES:
        raise ValueError("Vai trò được mời không hợp lệ (admin, manager, member, viewer).")
    if role == "admin" and actor_role != "owner":
        raise OrganizationPermissionError("Chỉ Chủ sở hữu mới có quyền mời Quản trị viên (Admin).")

    now = now_utc()
    now_iso = now.strftime("%Y-%m-%d %H:%M:%S")
    expires_iso = (now + timedelta(hours=INVITATION_TTL_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
    raw_token = f"gari_inv_{secrets.token_urlsafe(32)}"
    token_hash = _hash_invitation_token(raw_token)
    token_prefix = raw_token[:18] + "..."

    with _B2B_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Rate limit: per organization, last rolling hour.
            cursor.execute("""
                SELECT COUNT(*) FROM organization_invitations
                WHERE organization_id = ?
                  AND created_at >= datetime('now', '-1 hour')
            """, (org_id,))
            recent_count = cursor.fetchone()[0]
            if recent_count >= INVITATION_RATE_LIMIT_PER_HOUR:
                raise InvitationRateLimitError(
                    "Tổ chức đã tạo quá nhiều lời mời trong một giờ. Vui lòng thử lại sau."
                )

            # Retire any previous pending invite for the same email/org so only
            # the newest link can be used.
            cursor.execute("""
                UPDATE organization_invitations
                SET status = 'revoked', revoked_at = CURRENT_TIMESTAMP,
                    revoked_by_user_id = ?, revoke_reason = 'replaced_by_new_invitation',
                    updated_at = CURRENT_TIMESTAMP
                WHERE organization_id = ? AND LOWER(email) = ? AND status = 'pending'
            """, (actor_user_id, org_id, email))

            cursor.execute("""
                INSERT INTO organization_invitations
                    (organization_id, email, role, token_hash, token_prefix, status,
                     delivery_mode, delivery_status, invited_by_user_id, expires_at)
                VALUES (?, ?, ?, ?, ?, 'pending', 'manual', 'pending_manual_delivery', ?, ?)
            """, (org_id, email, role, token_hash, token_prefix, actor_user_id, expires_iso))
            invitation_id = cursor.lastrowid

            _write_audit(cursor, org_id, actor_user_id, "invitation.created", "invitation", invitation_id,
                         reason=reason or "Tạo lời mời thành viên",
                         metadata={"email": email, "role": role, "expires_at": expires_iso,
                                   "delivery_mode": "manual"})
            conn.commit()

    return {
        "id": invitation_id,
        "organization_id": org_id,
        "email": email,
        "role": role,
        "status": "pending",
        "expires_at": expires_iso,
        "delivery_mode": "manual",
        "delivery_status": "pending_manual_delivery",
        "email_sent": False,
        "message": "Lời mời đã được tạo. Giai đoạn pilot chưa có email provider: hãy gửi liên kết thủ công cho người được mời.",
        "invite_token": raw_token,
        "invite_url": f"/frontend2/organization.html?invite={raw_token}",
    }


def list_organization_invitations(org_id: int, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """List invitations without ever exposing hashes or raw tokens."""
    limit = max(1, min(int(limit or 100), 500))
    with get_db_connection() as conn:
        cursor = conn.cursor()
        params: List[Any] = [org_id]
        where = "organization_id = ?"
        if status:
            where += " AND status = ?"
            params.append(status)
        params.append(limit)
        cursor.execute(f"""
            SELECT i.id, i.organization_id, i.email, i.role, i.token_prefix, i.status,
                   i.delivery_mode, i.delivery_status, i.expires_at, i.accepted_at,
                   i.revoked_at, i.revoke_reason, i.created_at,
                   inviter.email as invited_by_email
            FROM organization_invitations i
            LEFT JOIN users inviter ON i.invited_by_user_id = inviter.id
            WHERE {where}
            ORDER BY i.created_at DESC
            LIMIT ?
        """, params)
        return [dict(r) for r in cursor.fetchall()]


def revoke_invitation(org_id: int, actor_user_id: int, invitation_id: int, reason: str) -> None:
    """Revoke a still-pending invitation."""
    require_permission(org_id, actor_user_id, "members.invite")
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise ValueError("Vui lòng cung cấp lý do thu hồi lời mời.")
    with _B2B_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM organization_invitations WHERE id = ? AND organization_id = ?", (invitation_id, org_id))
            row = cursor.fetchone()
            if not row:
                raise ValueError("Không tìm thấy lời mời trong tổ chức này.")
            if row["status"] != "pending":
                raise InvitationError("Lời mời đã được sử dụng hoặc không còn hiệu lực.")
            cursor.execute("""
                UPDATE organization_invitations
                SET status = 'revoked', revoked_at = CURRENT_TIMESTAMP,
                    revoked_by_user_id = ?, revoke_reason = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND organization_id = ?
            """, (actor_user_id, reason, invitation_id, org_id))
            _write_audit(cursor, org_id, actor_user_id, "invitation.revoked", "invitation", invitation_id,
                         reason=reason, metadata={})
            conn.commit()


def accept_invitation(raw_token: str, user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accept an invitation for the authenticated user.

    Rejects expired, reused, revoked, mismatched-email and archived/suspended
    organization invitations. The token holder must control the invited email.
    """
    raw_token = (raw_token or "").strip()
    if not raw_token:
        raise InvitationError("Lời mời không hợp lệ hoặc đã hết hạn.")
    user_id = user.get("id")
    user_email = (user.get("email") or "").strip().lower()
    token_hash = _hash_invitation_token(raw_token)
    now_iso = now_utc().strftime("%Y-%m-%d %H:%M:%S")

    with _B2B_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT i.*, o.name as org_name, o.status as org_status, o.plan_id
                FROM organization_invitations i
                JOIN organizations o ON i.organization_id = o.id
                WHERE i.token_hash = ?
            """, (token_hash,))
            inv = cursor.fetchone()
            if not inv:
                raise InvitationError("Lời mời không hợp lệ hoặc đã hết hạn.")

            invitation = dict(inv)
            if invitation["status"] != "pending":
                raise InvitationError("Lời mời đã được sử dụng, bị thu hồi hoặc đã hết hạn.")
            if invitation["expires_at"] <= now_iso:
                cursor.execute("UPDATE organization_invitations SET status = 'expired', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                               (invitation["id"],))
                conn.commit()
                raise InvitationError("Lời mời đã hết hạn. Vui lòng yêu cầu quản trị viên gửi lại.")
            if (invitation["email"] or "").strip().lower() != user_email:
                # Deliberately generic: do not reveal whether another email exists.
                raise InvitationError("Lời mời không hợp lệ với tài khoản đang đăng nhập.")
            org_status = normalize_org_status(invitation["org_status"])
            if org_status in ("suspended", "archived"):
                raise InvitationError("Tổ chức đang bị tạm ngưng hoặc đã lưu trữ; không thể chấp nhận lời mời.")

            org_id = invitation["organization_id"]
            cursor.execute("SELECT role FROM organization_members WHERE organization_id = ? AND user_id = ?", (org_id, user_id))
            existing = cursor.fetchone()

            if not existing:
                plan = PLANS_CONFIG.get(invitation["plan_id"], PLANS_CONFIG[PILOT_ORG_PLAN_ID])
                cursor.execute("SELECT COUNT(*) FROM organization_members WHERE organization_id = ?", (org_id,))
                member_count = cursor.fetchone()[0]
                if member_count >= plan["max_members"]:
                    raise InvitationError(f"Tổ chức đã đạt giới hạn {plan['max_members']} thành viên của gói hiện tại.")

                cursor.execute("""
                    INSERT INTO organization_members (organization_id, user_id, role, invited_by)
                    VALUES (?, ?, ?, ?)
                """, (org_id, user_id, invitation["role"], invitation["invited_by_user_id"]))
                joined_role = invitation["role"]
            else:
                joined_role = existing["role"]

            cursor.execute("""
                UPDATE organization_invitations
                SET status = 'accepted', accepted_by_user_id = ?, accepted_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (user_id, invitation["id"]))
            _write_audit(cursor, org_id, user_id, "invitation.accepted", "invitation", invitation["id"],
                         reason="Chấp nhận lời mời thành viên",
                         metadata={"role": invitation["role"], "already_member": bool(existing)})
            conn.commit()

    return {
        "organization_id": org_id,
        "organization_name": invitation["org_name"],
        "role": joined_role,
        "already_member": bool(existing),
        "status": "accepted",
    }


def get_pending_invitations_for_email(email: str) -> List[Dict[str, Any]]:
    """Return pending, unexpired invitations addressed to the authenticated email."""
    email = (email or "").strip().lower()
    now_iso = now_utc().strftime("%Y-%m-%d %H:%M:%S")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT i.id, i.organization_id, i.email, i.role, i.status, i.delivery_mode,
                   i.delivery_status, i.expires_at, i.created_at,
                   o.name as organization_name, o.status as organization_status
            FROM organization_invitations i
            JOIN organizations o ON i.organization_id = o.id
            WHERE LOWER(i.email) = ? AND i.status = 'pending' AND i.expires_at > ?
            ORDER BY i.created_at DESC
        """, (email, now_iso))
        result = []
        for row in cursor.fetchall():
            item = dict(row)
            item["organization_status"] = normalize_org_status(item.get("organization_status"))
            result.append(item)
        return result


# -----------------------------------------------------------------------------
# SPRINT 2: RESUMABLE B2B ONBOARDING
# -----------------------------------------------------------------------------

def get_organization_onboarding(org_id: int) -> Dict[str, Any]:
    """Return persisted onboarding state, creating the initial row if needed."""
    with _B2B_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM organization_onboarding WHERE organization_id = ?", (org_id,))
            row = cursor.fetchone()
            if not row:
                cursor.execute("""
                    INSERT OR IGNORE INTO organization_onboarding (organization_id, current_step, status)
                    VALUES (?, 1, 'in_progress')
                """, (org_id,))
                conn.commit()
                cursor.execute("SELECT * FROM organization_onboarding WHERE organization_id = ?", (org_id,))
                row = cursor.fetchone()
            if not row:
                return {"organization_id": org_id, "current_step": 1, "status": "in_progress",
                        "profile_completed": False, "role_confirmed": False, "needs": [],
                        "commercial_intent": "none", "completed_at": None}
            item = dict(row)
            try:
                item["needs"] = json.loads(item.get("needs_json") or "[]")
            except Exception:
                item["needs"] = []
            item["profile_completed"] = bool(item.get("profile_completed"))
            item["role_confirmed"] = bool(item.get("role_confirmed"))
            return item


def advance_organization_onboarding(
    org_id: int,
    actor_user_id: int,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Merge one or more onboarding steps, persist progress, and activate the
    organization only when the required steps are complete. Plan is never
    changed here.
    """
    payload = dict(payload or {})
    require_permission(org_id, actor_user_id, "onboarding.manage")
    status = get_organization_status(org_id)
    if status is None:
        raise ValueError("Tổ chức không tồn tại.")
    if status == "archived":
        raise OrganizationStateError("Tổ chức đã lưu trữ; hãy khôi phục trước khi tiếp tục onboarding.")

    actor_role = get_member_role(org_id, actor_user_id)
    if payload.get("role_confirmed") and actor_role not in ("owner", "admin"):
        raise OrganizationPermissionError("Chỉ Chủ sở hữu hoặc Quản trị viên mới có thể xác nhận vai trò quản trị.")

    if "needs" in payload:
        needs = payload.get("needs") or []
        if not isinstance(needs, list) or any(str(n) not in ORG_NEEDS for n in needs):
            raise ValueError(f"Nhu cầu sử dụng không hợp lệ. Hợp lệ: {', '.join(ORG_NEEDS)}")
    if "commercial_intent" in payload and payload["commercial_intent"] not in COMMERCIAL_INTENTS:
        raise ValueError(f"Trạng thái thương mại không hợp lệ. Hợp lệ: {', '.join(COMMERCIAL_INTENTS)}")

    # Optional profile fields submitted as part of step 2.
    profile_updates = {k: payload[k] for k in PROFILE_UPDATE_FIELDS if k in payload}
    if profile_updates:
        update_organization_profile(org_id, actor_user_id, profile_updates, reason="Cập nhật hồ sơ trong onboarding")

    org = get_organization_detail(org_id) or {}
    profile_completed = bool(org.get("organization_type"))
    requested_step = int(payload.get("step") or payload.get("current_step") or 1)
    requested_step = max(1, min(requested_step, 5))
    complete = bool(payload.get("complete")) or requested_step >= 5

    with _B2B_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            onboarding = get_organization_onboarding(org_id)
            needs = payload.get("needs") if "needs" in payload else onboarding.get("needs", [])
            role_confirmed = bool(payload.get("role_confirmed")) or bool(onboarding.get("role_confirmed"))
            commercial_intent = payload.get("commercial_intent") or onboarding.get("commercial_intent") or "none"

            if complete:
                if org.get("status") in ("suspended", "archived"):
                    raise OrganizationStateError("Không thể hoàn tất onboarding khi tổ chức bị tạm ngưng/lưu trữ.")
                if not role_confirmed:
                    raise ValueError("Cần xác nhận vai trò Chủ sở hữu/Quản trị viên trước khi hoàn tất.")
                if not profile_completed:
                    raise ValueError("Cần cung cấp loại hình tổ chức trước khi hoàn tất onboarding.")
                if not needs:
                    raise ValueError("Cần chọn ít nhất một nhu cầu sử dụng.")

            new_step = 5 if complete else max(int(onboarding.get("current_step") or 1), requested_step)
            new_status = "completed" if complete else "in_progress"
            cursor.execute("""
                UPDATE organization_onboarding
                SET current_step = ?, status = ?, profile_completed = ?, role_confirmed = ?,
                    needs_json = ?, commercial_intent = ?, completed_at = CASE WHEN ? = 'completed' THEN CURRENT_TIMESTAMP ELSE completed_at END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE organization_id = ?
            """, (new_step, new_status, 1 if profile_completed else 0, 1 if role_confirmed else 0,
                  json.dumps(needs, ensure_ascii=False), commercial_intent, new_status, org_id))

            if complete and normalize_org_status(org.get("status")) == "pending":
                cursor.execute("""
                    UPDATE organizations
                    SET status = 'active', status_reason = 'onboarding_completed', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status = 'pending'
                """, (org_id,))
                _write_audit(cursor, org_id, actor_user_id, "organization.status_changed", "organization", org_id,
                             reason="Hoàn tất onboarding B2B",
                             metadata={"old_status": "pending", "new_status": "active"})

            _write_audit(cursor, org_id, actor_user_id, "organization.onboarding_updated", "organization", org_id,
                         reason="Cập nhật tiến trình onboarding",
                         metadata={"step": new_step, "status": new_status, "needs": needs,
                                   "commercial_intent": commercial_intent,
                                   "role_confirmed": bool(role_confirmed)})
            conn.commit()

    return {
        "onboarding": get_organization_onboarding(org_id),
        "organization": get_organization_detail(org_id),
        "dashboard_url": "/frontend2/organization.html",
    }

# -----------------------------------------------------------------------------
# 3. CONCURRENCY-SAFE USAGE METERING & ORGANIZATIONAL QUOTA
# -----------------------------------------------------------------------------

def get_organization_quota_status(org_id: int) -> Dict[str, Any]:
    """Retrieve or refresh organization quota status (supports unlimited plans)."""
    current = datetime.now(timezone.utc)
    current_iso = current.strftime("%Y-%m-%d %H:%M:%S")

    with _B2B_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM organization_quotas WHERE organization_id = ?", (org_id,))
            row = cursor.fetchone()

            if not row:
                # Find plan of org
                cursor.execute("SELECT plan_id, status FROM organizations WHERE id = ?", (org_id,))
                org_row = cursor.fetchone()
                plan_id = org_row["plan_id"] if org_row else PILOT_ORG_PLAN_ID
                plan = PLANS_CONFIG.get(plan_id, PLANS_CONFIG[PILOT_ORG_PLAN_ID])

                cycle_end = (current + timedelta(hours=plan["refresh_hours"])).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                INSERT INTO organization_quotas (organization_id, plan_id, quota_limit, used_count, cycle_start, cycle_end)
                VALUES (?, ?, ?, 0, ?, ?)
                """, (org_id, plan_id, plan["quota_limit_per_cycle"], current_iso, cycle_end))
                conn.commit()

                cursor.execute("SELECT * FROM organization_quotas WHERE organization_id = ?", (org_id,))
                row = cursor.fetchone()

            record = dict(row)
            plan = PLANS_CONFIG.get(record["plan_id"], PLANS_CONFIG[PILOT_ORG_PLAN_ID])

            # Check for cycle expiration
            cycle_end_dt = datetime.strptime(record["cycle_end"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if current >= cycle_end_dt:
                new_cycle_end = (current + timedelta(hours=plan["refresh_hours"])).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                UPDATE organization_quotas
                SET used_count = 0,
                    cycle_start = ?,
                    cycle_end = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """, (current_iso, new_cycle_end, record["id"]))
                conn.commit()
                record["used_count"] = 0
                record["cycle_start"] = current_iso
                record["cycle_end"] = new_cycle_end
                cycle_end_dt = datetime.strptime(new_cycle_end, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

            limit = record["quota_limit"]
            used = record["used_count"] or 0
            is_unlimited = limit in (None, -1) or bool(plan.get("is_unlimited_quota"))
            remaining = None if is_unlimited else max(0, int(limit) - int(used))

            diff = cycle_end_dt - current
            hrs = max(0, int(diff.total_seconds() // 3600))
            mins = max(0, int((diff.total_seconds() % 3600) // 60))
            org_status = get_organization_status(org_id)

            return {
                "organization_id": org_id,
                "organization_status": org_status,
                "plan_id": record["plan_id"],
                "plan_name_vi": plan["name_vi"],
                "quota_limit": None if is_unlimited else limit,
                "used_count": used,
                "remaining": remaining,
                "is_unlimited": is_unlimited,
                "can_classify": bool(org_status == "active" and (is_unlimited or remaining > 0)),
                "has_vip_models": plan["has_vip_models"],
                "has_api_access": plan["has_api_access"],
                "cycle_start": record["cycle_start"],
                "cycle_end": record["cycle_end"],
                "resets_in_human": f"{hrs} giờ {mins} phút"
            }


def deduct_org_quota_atomic(org_id: int, user_id: Optional[int] = None, api_key_id: Optional[int] = None, caller_type: str = "web_user", model_name: str = "Gari ConvNeXt", crop_id: Optional[str] = None, disease_predicted: Optional[str] = None, latency_ms: float = 0.0) -> bool:
    """
    Atomically deduct exactly 1 turn from organization quota.
    Prevents race condition and negative quota under concurrent loads.
    Logs usage into usage_metering table.
    """
    with _B2B_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT plan_id FROM organizations WHERE id = ?", (org_id,))
            org_row = cursor.fetchone()
            plan_id = org_row["plan_id"] if org_row else PILOT_ORG_PLAN_ID
            plan = PLANS_CONFIG.get(plan_id, PLANS_CONFIG[PILOT_ORG_PLAN_ID])
            is_unlimited = bool(plan.get("is_unlimited_quota"))

            if is_unlimited:
                cursor.execute("""
                UPDATE organization_quotas
                SET used_count = used_count + 1,
                    last_used_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE organization_id = ?
                """, (org_id,))
            else:
                # Atomic decrement
                cursor.execute("""
                UPDATE organization_quotas
                SET used_count = used_count + 1,
                    last_used_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE organization_id = ? AND used_count < quota_limit
                """, (org_id,))
            conn.commit()

            if cursor.rowcount == 0:
                logger.warning("Org Quota exhausted for org_id: %s", org_id)
                # Log failed metering
                cursor.execute("""
                INSERT INTO usage_metering (organization_id, user_id, api_key_id, caller_type, model_name, crop_id, disease_predicted, status, quota_deducted, latency_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'quota_exhausted', 0, ?)
                """, (org_id, user_id, api_key_id, caller_type, model_name, crop_id, disease_predicted, latency_ms))
                conn.commit()
                return False

            # Log successful metering
            cursor.execute("""
            INSERT INTO usage_metering (organization_id, user_id, api_key_id, caller_type, model_name, crop_id, disease_predicted, status, quota_deducted, latency_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'success', 1, ?)
            """, (org_id, user_id, api_key_id, caller_type, model_name, crop_id, disease_predicted, latency_ms))

            if api_key_id:
                cursor.execute("""
                UPDATE api_keys
                SET total_calls = total_calls + 1,
                    last_used_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """, (api_key_id,))

            conn.commit()
            return True


# -----------------------------------------------------------------------------
# 4. API-AS-A-SERVICE FOUNDATION (API Key Management & Authentication)
# -----------------------------------------------------------------------------

def generate_api_key(org_id: int, user_id: int, key_name: str, rate_limit_rpm: int = 60) -> Dict[str, Any]:
    """
    Generate a new cryptographic API key for an organization.
    Format: gari_live_<random_hex>
    Stores only SHA-256 hash. Returns plaintext key once.
    """
    require_permission(org_id, user_id, "api_keys.manage")
    ensure_organization_operational(org_id)

    org = get_organization_detail(org_id)
    if not org or not org["plan_details"]["has_api_access"]:
        raise ValueError(f"Gói dịch vụ {org['plan_details']['name_vi']} chưa hỗ trợ tính năng API-as-a-Service. Vui lòng nâng cấp lên gói Team hoặc Enterprise.")
    if org["active_api_keys_count"] >= org["plan_details"]["max_api_keys"]:
        raise ValueError(f"Đã đạt giới hạn tối đa {org['plan_details']['max_api_keys']} API Key của gói hiện tại.")

    key_name = (key_name or "").strip()[:120] or "Default API Key"
    rate_limit_rpm = max(1, min(int(rate_limit_rpm or 60), 10000))

    raw_secret = secrets.token_hex(20)
    full_key = f"gari_live_{raw_secret}"
    key_prefix = f"gari_live_{raw_secret[:6]}..."
    key_hash = hashlib.sha256(full_key.encode("utf-8")).hexdigest()

    with _B2B_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO api_keys (organization_id, created_by_user_id, key_name, key_prefix, key_hash, is_active, rate_limit_rpm)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """, (org_id, user_id, key_name, key_prefix, key_hash, rate_limit_rpm))
            key_id = cursor.lastrowid
            _write_audit(cursor, org_id, user_id, "api_key.created", "api_key", key_id,
                         reason="Tạo API Key", metadata={"key_name": key_name, "rate_limit_rpm": rate_limit_rpm})
            conn.commit()

    return {
        "id": key_id,
        "key_name": key_name,
        "key_prefix": key_prefix,
        "full_key": full_key,  # Shown only once!
        "rate_limit_rpm": rate_limit_rpm,
        "created_at": datetime.now(timezone.utc).isoformat()
    }


def list_organization_api_keys(org_id: int) -> List[Dict[str, Any]]:
    """List active and revoked API keys (showing only prefixes, never secrets)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, organization_id, created_by_user_id, key_name, key_prefix, is_active, rate_limit_rpm, total_calls, last_used_at, revoked_at, created_at
        FROM api_keys
        WHERE organization_id = ?
        ORDER BY is_active DESC, created_at DESC
        """, (org_id,))
        return [dict(r) for r in cursor.fetchall()]


def revoke_api_key(org_id: int, user_id: int, key_id: int, reason: Optional[str] = None) -> bool:
    """Revoke an active API key immediately."""
    require_permission(org_id, user_id, "api_keys.manage")

    with _B2B_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE api_keys
            SET is_active = 0,
                revoked_at = CURRENT_TIMESTAMP
            WHERE id = ? AND organization_id = ?
            """, (key_id, org_id))
            revoked = cursor.rowcount > 0
            if revoked:
                _write_audit(cursor, org_id, user_id, "api_key.revoked", "api_key", key_id,
                             reason=reason or "Thu hồi API Key", metadata={})
            conn.commit()
            return revoked


def authenticate_api_key(raw_key: str) -> Optional[Dict[str, Any]]:
    """
    Verify raw API key from request headers and return organization context.
    Rejects keys whose organization is not active or whose plan has no API access.
    """
    if not raw_key or not raw_key.startswith("gari_"):
        return None

    hashed = hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT k.*, o.name as org_name, o.slug as org_slug, o.plan_id, o.status as org_status
        FROM api_keys k
        JOIN organizations o ON k.organization_id = o.id
        WHERE k.key_hash = ? AND k.is_active = 1
        """, (hashed,))
        row = cursor.fetchone()
        if not row:
            return None

        key_data = dict(row)
        plan = PLANS_CONFIG.get(key_data["plan_id"], PLANS_CONFIG[PILOT_ORG_PLAN_ID])
        key_data["plan_details"] = plan
        key_data["org_status"] = normalize_org_status(key_data.get("org_status"))
        key_data["is_operational"] = key_data["org_status"] == "active"
        key_data["has_api_access"] = bool(plan.get("has_api_access"))
        return key_data


def get_organization_usage_history(org_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve recent usage metering records for an organization."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT m.*, u.full_name as user_name, u.email as user_email, k.key_name as api_key_label
        FROM usage_metering m
        LEFT JOIN users u ON m.user_id = u.id
        LEFT JOIN api_keys k ON m.api_key_id = k.id
        WHERE m.organization_id = ?
        ORDER BY m.created_at DESC
        LIMIT ?
        """, (org_id, limit))
        return [dict(r) for r in cursor.fetchall()]


def get_organization_usage_summary(org_id: int, days: int = 30) -> Dict[str, Any]:
    """Aggregate real usage telemetry for the organization dashboard."""
    days = max(1, min(int(days or 30), 365))
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT COUNT(*) as total_calls,
               SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_calls,
               SUM(CASE WHEN status = 'quota_exhausted' THEN 1 ELSE 0 END) as quota_exhausted_calls,
               AVG(CASE WHEN latency_ms IS NOT NULL THEN latency_ms END) as avg_latency_ms
        FROM usage_metering
        WHERE organization_id = ?
          AND created_at >= datetime('now', ?)
        """, (org_id, f"-{days} days"))
        row = dict(cursor.fetchone() or {})

        cursor.execute("""
        SELECT caller_type, COUNT(*) as calls
        FROM usage_metering
        WHERE organization_id = ? AND created_at >= datetime('now', ?)
        GROUP BY caller_type
        ORDER BY calls DESC
        """, (org_id, f"-{days} days"))
        by_caller = {r["caller_type"] or "unknown": r["calls"] for r in cursor.fetchall()}

        cursor.execute("""
        SELECT model_name, COUNT(*) as calls
        FROM usage_metering
        WHERE organization_id = ? AND created_at >= datetime('now', ?)
        GROUP BY model_name
        ORDER BY calls DESC
        LIMIT 5
        """, (org_id, f"-{days} days"))
        top_models = [dict(r) for r in cursor.fetchall()]

        cursor.execute("""
        SELECT disease_predicted, COUNT(*) as cases
        FROM usage_metering
        WHERE organization_id = ? AND created_at >= datetime('now', ?)
          AND disease_predicted IS NOT NULL
        GROUP BY disease_predicted
        ORDER BY cases DESC
        LIMIT 5
        """, (org_id, f"-{days} days"))
        top_diseases = [dict(r) for r in cursor.fetchall()]

    quota = get_organization_quota_status(org_id)
    total_calls = int(row.get("total_calls") or 0)
    successful = int(row.get("successful_calls") or 0)
    return {
        "organization_id": org_id,
        "window_days": days,
        "total_calls": total_calls,
        "successful_calls": successful,
        "quota_exhausted_calls": int(row.get("quota_exhausted_calls") or 0),
        "success_rate": round((successful / total_calls) * 100, 1) if total_calls else None,
        "avg_latency_ms": round(row["avg_latency_ms"], 1) if row.get("avg_latency_ms") is not None else None,
        "by_caller_type": by_caller,
        "top_models": top_models,
        "top_diseases": top_diseases,
        "quota": quota,
    }
