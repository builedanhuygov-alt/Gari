"""
GARI AI LAB — Module 11: Subscription & Usage Management Migration
(migrations_module_11_subscriptions.py)

Creates:
1. `subscription_plans`: Configurable product plans (Free, Pro, Ultra, Organization, Enterprise)
   with dynamic names, prices, limits, and included features.
2. `usage_tracking`: Metric usage tracking for users and organizations
   (ai_usage, diagnosis, storage_mb, expert_consultations, etc.)
3. Seeds standard configurable plans with aliases (personal -> pro, team/business -> organization).
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("migrations_module_11")
DB_PATH = Path(__file__).resolve().parent / "database" / "disease_detector.db"


def run_migration(db_path: Optional[Path] = None) -> None:
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path), timeout=20.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 1. Configurable Subscription Plans table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscription_plans (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            tier_level INTEGER NOT NULL DEFAULT 0,
            price INTEGER,
            billing_interval TEXT NOT NULL DEFAULT 'monthly',
            currency TEXT DEFAULT 'VND',
            description TEXT,
            target_audience TEXT,
            is_active BOOLEAN DEFAULT 1,
            commercial_status TEXT,
            diagnosis_limit INTEGER DEFAULT 30,
            ai_usage_limit INTEGER DEFAULT 10,
            max_farms INTEGER DEFAULT 1,
            max_plots INTEGER DEFAULT 3,
            max_seats INTEGER DEFAULT 1,
            storage_mb INTEGER DEFAULT 50,
            expert_consultations_limit INTEGER DEFAULT 0,
            allowed_features TEXT NOT NULL,
            metadata_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 2. Usage Tracking table for metrics and quotas
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_type TEXT NOT NULL, -- 'user', 'organization'
            subject_id INTEGER NOT NULL,
            metric_name TEXT NOT NULL,  -- 'ai_usage', 'diagnosis', 'storage_mb', 'expert_consultations'
            used_amount REAL NOT NULL DEFAULT 0,
            cycle_start DATETIME NOT NULL,
            cycle_end DATETIME NOT NULL,
            last_recorded_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(subject_type, subject_id, metric_name, cycle_start)
        );
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_subject ON usage_tracking(subject_type, subject_id, metric_name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_cycle ON usage_tracking(cycle_start, cycle_end);")

        # 3. Seed Configurable Plans
        default_plans = [
            {
                "id": "free",
                "name": "free",
                "display_name": "Gói Miễn Phí (Free)",
                "tier_level": 0,
                "price": 0,
                "billing_interval": "monthly",
                "currency": "VND",
                "description": "Dành cho nông dân cá thể, người làm vườn gia đình theo dõi mùa vụ cơ bản.",
                "target_audience": "Nông dân cá thể, người làm vườn",
                "is_active": 1,
                "commercial_status": "Miễn phí trọn đời",
                "diagnosis_limit": 30,
                "ai_usage_limit": 50,
                "max_farms": 5,
                "max_plots": 25,
                "max_seats": 1,
                "storage_mb": 50,
                "expert_consultations_limit": 5,
                "allowed_features": json.dumps([
                    "diagnosis_basic", "farm_records", "view_knowledge", "scene_3d", "expert_consultation", "ai_assistant"
                ]),
                "metadata_json": json.dumps({"badge": "Cơ bản", "highlight": False})
            },
            {
                "id": "pro",
                "name": "pro",
                "display_name": "Gói Chuyên Nghiệp (Pro)",
                "tier_level": 10,
                "price": 129000,
                "billing_interval": "monthly",
                "currency": "VND",
                "description": "Mở khóa toàn bộ mô hình VIP, trợ lý AI chuyên sâu và trải nghiệm nông trại 3D.",
                "target_audience": "Kỹ sư nông học, chủ trang trại độc lập",
                "is_active": 1,
                "commercial_status": "Sẵn sàng đăng ký",
                "diagnosis_limit": 150,
                "ai_usage_limit": 100,
                "max_farms": 3,
                "max_plots": 15,
                "max_seats": 1,
                "storage_mb": 500,
                "expert_consultations_limit": 2,
                "allowed_features": json.dumps([
                    "diagnosis_basic", "diagnosis_vip", "farm_records", "data_export",
                    "view_knowledge", "ai_assistant", "priority_support", "expert_consultation", "scene_3d"
                ]),
                "metadata_json": json.dumps({"badge": "Phổ biến", "highlight": True})
            },
            {
                "id": "ultra",
                "name": "ultra",
                "display_name": "Gói Đỉnh Cao (Ultra)",
                "tier_level": 20,
                "price": 249000,
                "billing_interval": "monthly",
                "currency": "VND",
                "description": "Hạn mức AI và chẩn đoán vượt trội, tư vấn chuyên gia và báo cáo phân tích nông học nâng cao.",
                "target_audience": "Chủ trang trại quy mô lớn, kỹ sư tư vấn độc lập",
                "is_active": 1,
                "commercial_status": "Sẵn sàng đăng ký",
                "diagnosis_limit": 500,
                "ai_usage_limit": 500,
                "max_farms": 10,
                "max_plots": 50,
                "max_seats": 3,
                "storage_mb": 2048,
                "expert_consultations_limit": 10,
                "allowed_features": json.dumps([
                    "diagnosis_basic", "diagnosis_vip", "farm_records", "data_export",
                    "view_knowledge", "ai_assistant", "priority_support", "expert_consultation",
                    "scene_3d", "advanced_reports", "crop_rotation_calendar"
                ]),
                "metadata_json": json.dumps({"badge": "Hiệu năng cao", "highlight": False})
            },
            {
                "id": "organization",
                "name": "organization",
                "display_name": "Gói Hợp Tác Xã & Doanh Nghiệp (Organization)",
                "tier_level": 30,
                "price": 499000,
                "billing_interval": "monthly",
                "currency": "VND",
                "description": "Quản lý thành viên đa cấp bậc, phân quyền tổ chức, hạn ngạch chung và kết nối API.",
                "target_audience": "Hợp tác xã nông nghiệp, doanh nghiệp chế biến, đại lý BVTV",
                "is_active": 1,
                "commercial_status": "Sẵn sàng đăng ký",
                "diagnosis_limit": 1500,
                "ai_usage_limit": 2000,
                "max_farms": 25,
                "max_plots": 200,
                "max_seats": 15,
                "storage_mb": 10240,
                "expert_consultations_limit": 30,
                "allowed_features": json.dumps([
                    "diagnosis_basic", "diagnosis_vip", "farm_records", "data_export",
                    "view_knowledge", "ai_assistant", "priority_support", "expert_consultation",
                    "scene_3d", "advanced_reports", "team_management", "usage_metering", "api_access"
                ]),
                "metadata_json": json.dumps({"badge": "Tổ chức", "highlight": False})
            },
            {
                "id": "enterprise",
                "name": "enterprise",
                "display_name": "Gói Tập Đoàn (Enterprise)",
                "tier_level": 40,
                "price": None,
                "billing_interval": "annual",
                "currency": "VND",
                "description": "Giải pháp tùy biến toàn diện, không giới hạn hạn ngạch, SLA 99.9% và hỗ trợ custom branding.",
                "target_audience": "Tập đoàn nông nghiệp, dự án liên kết xuất khẩu",
                "is_active": 1,
                "commercial_status": "Hợp đồng B2B",
                "diagnosis_limit": -1, # -1 indicates unlimited
                "ai_usage_limit": -1,
                "max_farms": -1,
                "max_plots": -1,
                "max_seats": -1,
                "storage_mb": -1,
                "expert_consultations_limit": -1,
                "allowed_features": json.dumps([
                    "diagnosis_basic", "diagnosis_vip", "farm_records", "data_export",
                    "view_knowledge", "ai_assistant", "priority_support", "expert_consultation",
                    "scene_3d", "advanced_reports", "team_management", "usage_metering", "api_access",
                    "custom_branding", "dedicated_weights", "sla_guarantee"
                ]),
                "metadata_json": json.dumps({"badge": "Doanh nghiệp lớn", "highlight": False})
            }
        ]

        for p in default_plans:
            cursor.execute("""
            INSERT OR REPLACE INTO subscription_plans (
                id, name, display_name, tier_level, price, billing_interval, currency,
                description, target_audience, is_active, commercial_status,
                diagnosis_limit, ai_usage_limit, max_farms, max_plots, max_seats,
                storage_mb, expert_consultations_limit, allowed_features, metadata_json,
                updated_at
            ) VALUES (
                :id, :name, :display_name, :tier_level, :price, :billing_interval, :currency,
                :description, :target_audience, :is_active, :commercial_status,
                :diagnosis_limit, :ai_usage_limit, :max_farms, :max_plots, :max_seats,
                :storage_mb, :expert_consultations_limit, :allowed_features, :metadata_json,
                CURRENT_TIMESTAMP
            )
            """, p)

        # Aliases for backward compatibility
        alias_mappings = [
            ("personal", "pro"),
            ("team", "organization"),
            ("business", "organization")
        ]
        for alias_id, target_id in alias_mappings:
            cursor.execute("SELECT * FROM subscription_plans WHERE id = ?", (target_id,))
            target_row = cursor.fetchone()
            if target_row:
                row_dict = dict(target_row)
                row_dict["id"] = alias_id
                row_dict["name"] = alias_id
                row_dict["metadata_json"] = json.dumps({"is_alias_of": target_id})
                cursor.execute("""
                INSERT OR REPLACE INTO subscription_plans (
                    id, name, display_name, tier_level, price, billing_interval, currency,
                    description, target_audience, is_active, commercial_status,
                    diagnosis_limit, ai_usage_limit, max_farms, max_plots, max_seats,
                    storage_mb, expert_consultations_limit, allowed_features, metadata_json,
                    updated_at
                ) VALUES (
                    :id, :name, :display_name, :tier_level, :price, :billing_interval, :currency,
                    :description, :target_audience, :is_active, :commercial_status,
                    :diagnosis_limit, :ai_usage_limit, :max_farms, :max_plots, :max_seats,
                    :storage_mb, :expert_consultations_limit, :allowed_features, :metadata_json,
                    CURRENT_TIMESTAMP
                )
                """, row_dict)

        conn.commit()
        logger.info("Successfully executed Module 11 subscription & usage migration.")
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_migration()
    print("Module 11 Migration completed successfully.")
