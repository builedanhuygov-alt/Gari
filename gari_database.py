"""
GARI AI LAB — Scalable AgriTech Database & Business Logic Layer
Integrates SQLite persistence for:
- Farms & Planting Areas
- AI Diagnosis History (linked to farms & ConvNeXt models)
- Agricultural Expert Support Cases
- Regional Disease Outbreak Risk Monitoring
- Disease Knowledge Catalog
"""

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("gari_database")

DB_PATH = Path(__file__).resolve().parent / "database" / "disease_detector.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR = Path(__file__).resolve().parent / "database" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=15.0)
    conn.row_factory = sqlite3.Row
    # SRE Production Hardening: WAL mode, referential integrity & concurrency protection
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
    except Exception as pragma_exc:
        logger.warning("Could not set database PRAGMAs: %s", pragma_exc)
    return conn


def check_database_integrity() -> bool:
    """Run SQLite PRAGMA integrity_check to verify database health."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            rows = cursor.fetchall()
            return len(rows) == 1 and rows[0][0].lower() == "ok"
    except Exception as exc:
        logger.error("Database integrity check failed: %s", exc)
        return False


def backup_database_online(dest_path: Path) -> Path:
    """
    Creates a non-blocking, transactionally consistent online backup of SQLite database.
    Uses sqlite3.Connection.backup API rather than unsafe file copies.
    """
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as src_conn:
        with sqlite3.connect(str(dest_path)) as dest_conn:
            src_conn.backup(dest_conn, pages=100, sleep=0.01)
    logger.info("Online database backup created successfully at: %s", dest_path)
    return dest_path



def init_database() -> None:
    """Initialize necessary tables with proper schemas and indexes."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # 0. Users and Auth Tables
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            name TEXT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            phone TEXT,
            account_type TEXT DEFAULT 'farmer',
            is_admin BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_account_type_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            previous_type TEXT,
            new_type TEXT NOT NULL,
            reason TEXT,
            changed_by_user_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_acc_type_audit_user ON user_account_type_audit(user_id);
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL,
            used BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            notification_type TEXT DEFAULT 'info',
            is_read BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS farm_plots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farm_id INTEGER NOT NULL,
            user_id INTEGER DEFAULT 1,
            organization_id INTEGER,
            crop_id TEXT,
            crop_name TEXT,
            plot_name TEXT NOT NULL,
            region TEXT,
            area_hectares REAL DEFAULT 0.5,
            area_hectare REAL DEFAULT 0.5,
            planting_date TEXT,
            notes TEXT,
            status TEXT DEFAULT 'active',
            monitoring_status TEXT DEFAULT 'open',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (farm_id) REFERENCES farms (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)

        # 1. Farms Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS farms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            name TEXT NOT NULL,
            location TEXT,
            province TEXT,
            area_hectare REAL DEFAULT 1.0,
            primary_crop TEXT DEFAULT 'Tomato',
            variety TEXT,
            soil_type TEXT,
            irrigation_type TEXT,
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 2. Diagnoses History Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS diagnoses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            farm_id INTEGER,
            plot_id INTEGER,
            farm_plot_id INTEGER,
            organization_id INTEGER,
            farm_name TEXT,
            crop_id TEXT NOT NULL,
            crop_name TEXT NOT NULL,
            image_path TEXT,
            image_preview TEXT,
            predicted_disease TEXT NOT NULL,
            disease_name_vi TEXT,
            confidence REAL NOT NULL,
            confidence_percent REAL,
            severity TEXT DEFAULT 'MEDIUM',
            top_predictions_json TEXT,
            model_name TEXT,
            model_arch TEXT,
            model_version TEXT DEFAULT '2026.1',
            diagnosis_status TEXT DEFAULT 'diagnosed',
            monitoring_status TEXT DEFAULT 'open',
            monitoring_notes TEXT,
            consent_store_image BOOLEAN DEFAULT 0,
            inference_time_ms REAL,
            device TEXT,
            user_notes TEXT,
            treatment_status TEXT DEFAULT 'pending',
            is_verified_by_expert BOOLEAN DEFAULT 0,
            attention_path TEXT,
            overlay_path TEXT,
            regions_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (farm_id) REFERENCES farms (id),
            FOREIGN KEY (plot_id) REFERENCES farm_plots (id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)

        # 2b. Plot Disease Monitoring Timeline Events Table (Sprint 4)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS plot_timeline_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plot_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            organization_id INTEGER,
            event_type TEXT NOT NULL DEFAULT 'observation',
            diagnosis_id INTEGER,
            monitoring_status TEXT NOT NULL DEFAULT 'open',
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (plot_id) REFERENCES farm_plots (id) ON DELETE CASCADE,
            FOREIGN KEY (diagnosis_id) REFERENCES diagnoses (id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)

        # 3. Expert Consultation Cases Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS expert_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            diagnosis_id INTEGER,
            farm_id INTEGER,
            farm_name TEXT,
            farmer_name TEXT NOT NULL,
            phone TEXT,
            crop_name TEXT NOT NULL,
            suspected_disease TEXT,
            symptoms_description TEXT NOT NULL,
            field_conditions TEXT,
            image_preview TEXT,
            status TEXT DEFAULT 'Submitted',
            expert_notes TEXT,
            assigned_expert TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (diagnosis_id) REFERENCES diagnoses (id),
            FOREIGN KEY (farm_id) REFERENCES farms (id)
        );
        """)

        # 4. Regional Disease Risk Monitoring Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS risk_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region TEXT NOT NULL,
            crop TEXT NOT NULL,
            disease_threat TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            source_type TEXT NOT NULL,
            temperature_c REAL,
            humidity_pct REAL,
            rainfall_mm REAL,
            recommendation TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 5. Startup Audit & Telemetry Metrics Table (Privacy-Safe, Priority E)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            model_name TEXT,
            crop_id TEXT,
            rejection_reason TEXT,
            is_vip BOOLEAN DEFAULT 0,
            user_id INTEGER,
            client_id TEXT,
            latency_ms REAL DEFAULT 0.0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Create Indexes for high-throughput queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON user_sessions(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON user_sessions(expires_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_farms_user_id ON farms(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnoses_farm_id ON diagnoses(farm_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnoses_crop_id ON diagnoses(crop_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnoses_created_at ON diagnoses(created_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expert_cases_status ON expert_cases(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_metrics_event ON audit_metrics(event_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_metrics_created ON audit_metrics(created_at);")

        # Migrate visual localization columns if missing
        for col, col_type in [("attention_path", "TEXT"), ("overlay_path", "TEXT"), ("regions_json", "TEXT")]:
            try:
                cursor.execute(f"ALTER TABLE diagnoses ADD COLUMN {col} {col_type};")
            except Exception:
                pass

        # Migrate user columns if missing
        user_cols = [r[1] for r in cursor.execute("PRAGMA table_info(users)").fetchall()]
        for col, col_type in [
            ("is_admin", "BOOLEAN DEFAULT 0"),
            ("is_host_admin", "BOOLEAN DEFAULT 0"),
            ("is_expert", "BOOLEAN DEFAULT 0"),
            ("is_active", "BOOLEAN DEFAULT 1"),
            ("province", "TEXT"),
            ("address", "TEXT"),
            ("avatar_url", "TEXT"),
            ("bio", "TEXT")
        ]:
            if col not in user_cols:
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type};")
                except Exception:
                    pass

        # Sprint 4: Migrate farm_plots columns
        plot_cols = [r[1] for r in cursor.execute("PRAGMA table_info(farm_plots)").fetchall()]
        for col, col_type in [
            ("organization_id", "INTEGER"),
            ("region", "TEXT"),
            ("status", "TEXT DEFAULT 'active'"),
            ("monitoring_status", "TEXT DEFAULT 'open'")
        ]:
            if col not in plot_cols:
                try:
                    cursor.execute(f"ALTER TABLE farm_plots ADD COLUMN {col} {col_type};")
                except Exception:
                    pass

        # Sprint 4: Migrate diagnoses columns
        diag_cols = [r[1] for r in cursor.execute("PRAGMA table_info(diagnoses)").fetchall()]
        for col, col_type in [
            ("user_id", "INTEGER"),
            ("plot_id", "INTEGER"),
            ("farm_plot_id", "INTEGER"),
            ("organization_id", "INTEGER"),
            ("model_version", "TEXT DEFAULT '2026.1'"),
            ("diagnosis_status", "TEXT DEFAULT 'diagnosed'"),
            ("monitoring_status", "TEXT DEFAULT 'open'"),
            ("monitoring_notes", "TEXT"),
            ("consent_store_image", "BOOLEAN DEFAULT 0"),
            ("growth_stage", "TEXT"),
            ("user_symptoms", "TEXT"),
            ("field_conditions", "TEXT"),
            ("image_references_json", "TEXT")
        ]:
            if col not in diag_cols:
                try:
                    cursor.execute(f"ALTER TABLE diagnoses ADD COLUMN {col} {col_type};")
                except Exception:
                    pass

        # Migrate chat_history columns if missing
        chat_cols = [r[1] for r in cursor.execute("PRAGMA table_info(chat_history)").fetchall()]
        if "actions_json" not in chat_cols:
            try:
                cursor.execute("ALTER TABLE chat_history ADD COLUMN actions_json TEXT;")
            except Exception:
                pass
        if "diagnosis_id" not in chat_cols:
            try:
                cursor.execute("ALTER TABLE chat_history ADD COLUMN diagnosis_id INTEGER REFERENCES diagnoses(id);")
            except Exception:
                pass
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_diagnosis_id ON chat_history(diagnosis_id);")

        # Create Sprint 4 indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnoses_plot_id ON diagnoses(plot_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnoses_org_id ON diagnoses(organization_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnoses_status ON diagnoses(diagnosis_status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_farm_plots_org_id ON farm_plots(organization_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plot_timeline_plot_id ON plot_timeline_events(plot_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plot_timeline_created ON plot_timeline_events(created_at);")

        # 6. Sprint 5: Pilot & Market Validation Tables
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pilot_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT NOT NULL,
            customer_type TEXT NOT NULL DEFAULT 'farmer',
            crops_of_interest TEXT,
            region TEXT,
            problem_statement TEXT,
            consent_given BOOLEAN NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'new',
            internal_notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pilot_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            old_status TEXT,
            new_status TEXT NOT NULL,
            changed_by_user_id INTEGER,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (request_id) REFERENCES pilot_requests (id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS diagnosis_feedbacks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            diagnosis_id INTEGER,
            user_id INTEGER,
            organization_id INTEGER,
            feedback_type TEXT NOT NULL,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'new',
            admin_notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (diagnosis_id) REFERENCES diagnoses (id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
        );
        """)

        # Sprint 5 Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pilot_requests_status ON pilot_requests(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pilot_requests_created ON pilot_requests(created_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pilot_audit_req ON pilot_audit_logs(request_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnosis_feedbacks_diag ON diagnosis_feedbacks(diagnosis_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnosis_feedbacks_user ON diagnosis_feedbacks(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnosis_feedbacks_org ON diagnosis_feedbacks(organization_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnosis_feedbacks_status ON diagnosis_feedbacks(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnosis_feedbacks_created ON diagnosis_feedbacks(created_at);")

        # 7. Cultivation Tasks Engine (Sprint 6)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS cultivation_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            organization_id INTEGER,
            farm_id INTEGER,
            plot_id INTEGER,
            crop_id TEXT,
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT NOT NULL,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'pending',
            task_type TEXT DEFAULT 'routine',
            creator_user_id INTEGER,
            assignee_user_id INTEGER,
            completed_at DATETIME,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (farm_id) REFERENCES farms (id) ON DELETE SET NULL,
            FOREIGN KEY (plot_id) REFERENCES farm_plots (id) ON DELETE SET NULL
        );
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cultivation_tasks_user ON cultivation_tasks(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cultivation_tasks_farm ON cultivation_tasks(farm_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cultivation_tasks_plot ON cultivation_tasks(plot_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cultivation_tasks_status ON cultivation_tasks(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cultivation_tasks_due ON cultivation_tasks(due_date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cultivation_tasks_org ON cultivation_tasks(organization_id);")

        # 8. User Risk Acknowledgments & Field Observations (Sprint 6)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_risk_acknowledgments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            farm_id INTEGER,
            plot_id INTEGER,
            status TEXT NOT NULL DEFAULT 'acknowledged',
            user_observation TEXT,
            severity_observed TEXT,
            acknowledged_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved_at DATETIME,
            FOREIGN KEY (alert_id) REFERENCES risk_alerts (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (farm_id) REFERENCES farms (id) ON DELETE SET NULL,
            FOREIGN KEY (plot_id) REFERENCES farm_plots (id) ON DELETE SET NULL
        );
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_risk_ack_alert ON user_risk_acknowledgments(alert_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_risk_ack_user ON user_risk_acknowledgments(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_risk_ack_farm ON user_risk_acknowledgments(farm_id);")

        conn.commit()

    # Seed realistic initial data if empty
    _seed_initial_data()


def _seed_initial_data() -> None:
    """Seed initial realistic Vietnamese farms and risk alerts if tables are empty."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Seed farms if count == 0
        cursor.execute("SELECT COUNT(*) FROM farms")
        if cursor.fetchone()[0] == 0:
            initial_farms = [
                (
                    "Trang trại Ba Vì Organic",
                    "Xã Vân Hòa, Huyện Ba Vì",
                    "Hà Nội",
                    3.5,
                    "Tomato",
                    "Cà chua bi Cherry F1",
                    "Đất phù sa bồi",
                    "Tưới nhỏ giọt Isarel tự động",
                    "Khu vực chuyên canh cà chua và ớt vụ đông xuân đạt tiêu chuẩn VietGAP.",
                ),
                (
                    "Vườn Rau Công Nghệ Cao Đơn Dương",
                    "Thị trấn Thạnh Mỹ, Huyện Đơn Dương",
                    "Lâm Đồng",
                    5.2,
                    "Potato",
                    "Khoai tây giống Atlantic",
                    "Đất đỏ Bazan màu mỡ",
                    "Tưới phun mưa kết hợp châm phân",
                    "Vùng nguyên liệu khoai tây chất lượng cao, giám sát dịch tễ mốc sương định kỳ.",
                ),
                (
                    "Hợp Tác Xã Chè Hữu Cơ Mộc Châu",
                    "Thị trấn Nông trường Mộc Châu",
                    "Sơn La",
                    12.0,
                    "Tea",
                    "Chè Shan Tuyết cổ thụ",
                    "Đất Feralit đồi núi cao",
                    "Tưới phun sương áp lực cao",
                    "Liên kết 24 hộ nông dân sản xuất chè sạch xuất khẩu Châu Âu.",
                ),
                (
                    "Nông Trường Lúa Nước An Giang",
                    "Huyện Thoại Sơn",
                    "An Giang",
                    25.0,
                    "Rice",
                    "Lúa ST25",
                    "Đất phù sa ngọt ven sông",
                    "Ngập - khô xen kẽ (AWD)",
                    "Mô hình cánh đồng lớn tuần hoàn, kiểm soát rầy nâu và đạo ôn lá.",
                ),
            ]
            cursor.executemany(
                """
                INSERT INTO farms (name, location, province, area_hectare, primary_crop, variety, soil_type, irrigation_type, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                initial_farms,
            )

        # Seed initial diagnoses if count == 0
        cursor.execute("SELECT COUNT(*) FROM diagnoses")
        if cursor.fetchone()[0] == 0:
            initial_diagnoses = [
                (
                    1,
                    "Trang trại Ba Vì Organic",
                    "Tomato",
                    "Cà chua",
                    "Bacterial Spot",
                    "Đốm vi khuẩn",
                    0.9488,
                    94.88,
                    "HIGH",
                    json.dumps([
                        {"class_id": "Bacterial_spot", "label": "Bacterial Spot", "disease": "Đốm vi khuẩn", "confidence": 0.9488, "confidence_percent": 94.88},
                        {"class_id": "Target_spot", "label": "Target Spot", "disease": "Đốm bia", "confidence": 0.0413, "confidence_percent": 4.13},
                        {"class_id": "Late_blight", "label": "Late Blight", "disease": "Mốc sương", "confidence": 0.0070, "confidence_percent": 0.70},
                    ]),
                    "Gari ConvNeXt (Tomato)",
                    "convnext_small",
                    144.5,
                    "cpu",
                    "Phát hiện đốm nhỏ sẫm màu có quầng vàng trên các lá tầng dưới gần mặt đất.",
                    "treated",
                ),
                (
                    2,
                    "Vườn Rau Công Nghệ Cao Đơn Dương",
                    "Potato",
                    "Khoai tây",
                    "Early Blight",
                    "Đốm sớm",
                    0.9717,
                    97.17,
                    "HIGH",
                    json.dumps([
                        {"class_id": "Early_blight", "label": "Early Blight", "disease": "Đốm sớm", "confidence": 0.9717, "confidence_percent": 97.17},
                        {"class_id": "Healthy", "label": "Healthy", "disease": "Khỏe mạnh", "confidence": 0.0147, "confidence_percent": 1.47},
                        {"class_id": "Late_blight", "label": "Late Blight", "disease": "Mốc sương", "confidence": 0.0137, "confidence_percent": 1.37},
                    ]),
                    "Gari ConvNeXt (Potato)",
                    "convnext_small",
                    140.4,
                    "cpu",
                    "Vết bệnh hình tròn đồng tâm xuất hiện rải rác ở luống số 4.",
                    "monitoring",
                ),
                (
                    1,
                    "Trang trại Ba Vì Organic",
                    "Tomato",
                    "Cà chua",
                    "Healthy",
                    "Lá khỏe mạnh",
                    0.9850,
                    98.50,
                    "HEALTHY",
                    json.dumps([
                        {"class_id": "Healthy", "label": "Healthy", "disease": "Khỏe mạnh", "confidence": 0.9850, "confidence_percent": 98.50},
                        {"class_id": "Septoria_leaf_spot", "label": "Septoria Leaf Spot", "disease": "Đốm lá Septoria", "confidence": 0.0080, "confidence_percent": 0.80},
                        {"class_id": "Leaf_mold", "label": "Leaf Mold", "disease": "Mốc lá", "confidence": 0.0050, "confidence_percent": 0.50},
                    ]),
                    "Gari ConvNeXt (Tomato)",
                    "convnext_small",
                    138.2,
                    "cpu",
                    "Kiểm tra định kỳ khu nhà lưới số 2 sau tỉa nhánh, lá xanh bóng khỏe mạnh.",
                    "resolved",
                ),
            ]
            cursor.executemany(
                """
                INSERT INTO diagnoses (
                    farm_id, farm_name, crop_id, crop_name, predicted_disease, disease_name_vi,
                    confidence, confidence_percent, severity, top_predictions_json,
                    model_name, model_arch, inference_time_ms, device, user_notes, treatment_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                initial_diagnoses,
            )

        # Seed initial expert cases if count == 0
        cursor.execute("SELECT COUNT(*) FROM expert_cases")
        if cursor.fetchone()[0] == 0:
            initial_cases = [
                (
                    1,
                    1,
                    "Trang trại Ba Vì Organic",
                    "Nguyễn Văn An",
                    "0912 345 678",
                    "Cà chua",
                    "Nghi ngờ héo xanh vi khuẩn (Ralstonia solanacearum)",
                    "Cây có hiện tượng héo rũ ban ngày nhưng đêm lại tươi nhẹ, lá vẫn giữ màu xanh chứ không vàng rực.",
                    "Nhiệt độ đất cao 29°C sau mưa rào lớn, độ ẩm đất bão hòa.",
                    "Under review",
                    "Đang phân tích mẫu dịch cuống lá cắm vào nước trong để kiểm tra dòng vi khuẩn đùn ra.",
                    "TS. Lê Minh Hoàng (Viện BVTV)",
                ),
                (
                    2,
                    2,
                    "Vườn Rau Công Nghệ Cao Đơn Dương",
                    "Trần Thị Mai",
                    "0983 654 321",
                    "Khoai tây",
                    "Đốm sớm lan nhanh sau sương mù",
                    "Vết bệnh hình tròn viền nâu đậm có quầng vàng lan nhanh trên 15% diện tích lô A3.",
                    "Sương mù ban sáng dày đặc kéo dài đến 9h30, độ ẩm không khí > 90%.",
                    "Submitted",
                    None,
                    "KS. Nguyễn Quốc Dũng (Đà Lạt)",
                ),
            ]
            cursor.executemany(
                """
                INSERT INTO expert_cases (
                    diagnosis_id, farm_id, farm_name, farmer_name, phone, crop_name,
                    suspected_disease, symptoms_description, field_conditions,
                    status, expert_notes, assigned_expert
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                initial_cases,
            )

        # Seed initial risk alerts if count == 0
        cursor.execute("SELECT COUNT(*) FROM risk_alerts")
        if cursor.fetchone()[0] == 0:
            initial_alerts = [
                (
                    "Lâm Đồng (Tây Nguyên)",
                    "Potato",
                    "Mốc sương (Phytophthora infestans)",
                    "High",
                    "RULE_BASED_MODEL",
                    18.5,
                    94.0,
                    14.2,
                    "Độ ẩm ban đêm > 90% kết hợp nhiệt độ 16-20°C tạo điều kiện bùng phát mốc sương. Khuyến cáo phun phòng hoạt chất Mancozeb hoặc Metalaxyl trước khi có mưa.",
                ),
                (
                    "Đồng Bằng Sông Cửu Long",
                    "Rice",
                    "Bệnh đạo ôn lá (Magnaporthe oryzae)",
                    "Moderate",
                    "OBSERVED_WEATHER",
                    26.8,
                    88.0,
                    5.0,
                    "Trời âm u, sáng có sương mù nhẹ. Khuyến nghị thăm đồng buổi sáng kiểm tra chấm kim trên lá non, ngưng bón phân đạm rước đòng nếu có vết bệnh.",
                ),
                (
                    "Hà Nội & Bắc Bộ",
                    "Tomato",
                    "Đốm vi khuẩn & Mốc lá",
                    "Moderate",
                    "RULE_BASED_MODEL",
                    24.2,
                    82.0,
                    2.0,
                    "Thời tiết hanh khô ban ngày, lạnh ẩm về đêm. Giữ thông gió nhà màng và tỉa bớt lá già sát đất để giảm độ ẩm ổ sinh thái.",
                ),
            ]
            cursor.executemany(
                """
                INSERT INTO risk_alerts (
                    region, crop, disease_threat, risk_level, source_type,
                    temperature_c, humidity_pct, rainfall_mm, recommendation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                initial_alerts,
            )

        conn.commit()


# -----------------------------------------------------------------------------
# Farm Management Operations
# -----------------------------------------------------------------------------

def list_farms(user_id: Optional[int] = None, include_test: bool = False) -> List[Dict[str, Any]]:
    env = os.environ.get("APP_ENV", "production")
    if env == "test":
        include_test = True

    where_test = "" if include_test else " AND (f.is_test = 0 OR f.is_test IS NULL)"

    with get_connection() as conn:
        cursor = conn.cursor()
        if user_id is not None:
            cursor.execute(f"""
                SELECT f.*,
                       (SELECT COUNT(*) FROM diagnoses WHERE farm_id = f.id) as total_diagnoses,
                       (SELECT COUNT(*) FROM diagnoses WHERE farm_id = f.id AND (severity = 'HEALTHY' OR severity = 'NORMAL')) as healthy_diagnoses
                FROM farms f
                WHERE f.user_id = ? {where_test}
                ORDER BY f.id DESC
            """, (user_id,))
        else:
            cursor.execute(f"""
                SELECT f.*,
                       (SELECT COUNT(*) FROM diagnoses WHERE farm_id = f.id) as total_diagnoses,
                       (SELECT COUNT(*) FROM diagnoses WHERE farm_id = f.id AND (severity = 'HEALTHY' OR severity = 'NORMAL')) as healthy_diagnoses
                FROM farms f
                WHERE 1=1 {where_test}
                ORDER BY f.id DESC
            """)
        return [dict(row) for row in cursor.fetchall()]


def get_farm(farm_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        if user_id is not None:
            cursor.execute("SELECT * FROM farms WHERE id = ? AND user_id = ?", (farm_id, user_id))
        else:
            cursor.execute("SELECT * FROM farms WHERE id = ?", (farm_id,))
        row = cursor.fetchone()
        if not row:
            return None
        data = dict(row)

        # Fetch plots for this farm
        cursor.execute("SELECT * FROM farm_plots WHERE farm_id = ? ORDER BY id ASC", (farm_id,))
        data["plots"] = [dict(r) for r in cursor.fetchall()]

        # Fetch recent diagnoses for this farm
        cursor.execute("""
            SELECT id, crop_name, predicted_disease, disease_name_vi, confidence, severity, created_at, treatment_status
            FROM diagnoses
            WHERE farm_id = ?
            ORDER BY id DESC LIMIT 20
        """, (farm_id,))
        data["diagnoses"] = [dict(r) for r in cursor.fetchall()]
        return data


def create_farm(data: Dict[str, Any], user_id: int = 1) -> Dict[str, Any]:
    farm_name = data.get("name", "Nông trại mới").strip()
    is_test_flag = 1 if (
        os.environ.get("APP_ENV") == "test"
        or "test" in farm_name.lower()
        or "17934" in farm_name
        or bool(data.get("is_test"))
    ) else 0

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO farms (user_id, name, location, province, area_hectare, primary_crop, variety, soil_type, irrigation_type, notes, is_test)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            farm_name,
            data.get("location", ""),
            data.get("province", ""),
            float(data.get("area_hectare", 1.0)),
            data.get("primary_crop", "Tomato"),
            data.get("variety", ""),
            data.get("soil_type", ""),
            data.get("irrigation_type", ""),
            data.get("notes", ""),
            is_test_flag
        ))
        conn.commit()
        new_id = cursor.lastrowid
        return get_farm(new_id, user_id=user_id)  # type: ignore


def update_farm(farm_id: int, data: Dict[str, Any], user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        # Verify ownership
        if user_id is not None:
            cursor.execute("SELECT id FROM farms WHERE id = ? AND user_id = ?", (farm_id, user_id))
            if not cursor.fetchone():
                return None

        cursor.execute("""
            UPDATE farms
            SET name = COALESCE(?, name),
                location = COALESCE(?, location),
                province = COALESCE(?, province),
                area_hectare = COALESCE(?, area_hectare),
                primary_crop = COALESCE(?, primary_crop),
                variety = COALESCE(?, variety),
                soil_type = COALESCE(?, soil_type),
                irrigation_type = COALESCE(?, irrigation_type),
                status = COALESCE(?, status),
                notes = COALESCE(?, notes),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            data.get("name"),
            data.get("location"),
            data.get("province"),
            float(data["area_hectare"]) if data.get("area_hectare") is not None else None,
            data.get("primary_crop"),
            data.get("variety"),
            data.get("soil_type"),
            data.get("irrigation_type"),
            data.get("status"),
            data.get("notes"),
            farm_id
        ))
        conn.commit()
        return get_farm(farm_id, user_id=user_id)


def delete_farm(farm_id: int, user_id: Optional[int] = None) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        if user_id is not None:
            cursor.execute("DELETE FROM farms WHERE id = ? AND user_id = ?", (farm_id, user_id))
        else:
            cursor.execute("DELETE FROM farms WHERE id = ?", (farm_id,))
        conn.commit()
        return cursor.rowcount > 0


def generate_farm_season_report(farm_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Generate comprehensive seasonal farm management & cultivation adherence report.
    Integrates multi-plot health, task adherence, diagnosis timeline, and VietGAP compliance hash.
    Strictly isolated by user_id ownership.
    """
    import hashlib

    farm = get_farm(farm_id, user_id=user_id)
    if not farm:
        return None

    plots = farm.get("plots", [])
    plot_ids = [p["id"] for p in plots]

    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Fetch cultivation tasks for this farm or its plots
        if plot_ids:
            placeholders = ",".join("?" for _ in plot_ids)
            cursor.execute(f"""
                SELECT * FROM cultivation_tasks
                WHERE farm_id = ? OR plot_id IN ({placeholders})
                ORDER BY due_date DESC, id DESC
            """, [farm_id] + plot_ids)
        else:
            cursor.execute("""
                SELECT * FROM cultivation_tasks
                WHERE farm_id = ?
                ORDER BY due_date DESC, id DESC
            """, (farm_id,))
        all_tasks = [dict(r) for r in cursor.fetchall()]

        # 2. Fetch timeline events for all plots of this farm
        timeline_events = []
        if plot_ids:
            placeholders = ",".join("?" for _ in plot_ids)
            cursor.execute(f"""
                SELECT * FROM plot_timeline_events
                WHERE plot_id IN ({placeholders})
                ORDER BY id DESC LIMIT 50
            """, plot_ids)
            timeline_events = [dict(r) for r in cursor.fetchall()]

        # 3. Fetch all diagnoses for this farm
        cursor.execute("""
            SELECT id, plot_id, crop_name, predicted_disease, disease_name_vi,
                   confidence, severity, treatment_status, monitoring_status, created_at
            FROM diagnoses
            WHERE farm_id = ?
            ORDER BY id DESC LIMIT 50
        """, (farm_id,))
        all_diagnoses = [dict(r) for r in cursor.fetchall()]

    # Task metrics
    today_str = datetime.now().strftime("%Y-%m-%d")
    total_tasks = len(all_tasks)
    completed_tasks = [t for t in all_tasks if t.get("status") == "completed"]
    overdue_tasks = [t for t in all_tasks if t.get("status") == "pending" and t.get("due_date") and t["due_date"] < today_str]
    pending_tasks = [t for t in all_tasks if t.get("status") == "pending" and (not t.get("due_date") or t["due_date"] >= today_str)]

    adherence_pct = round(len(completed_tasks) / total_tasks * 100, 1) if total_tasks > 0 else 100.0

    task_by_type: Dict[str, int] = {}
    for t in all_tasks:
        tt = t.get("task_type") or "other"
        task_by_type[tt] = task_by_type.get(tt, 0) + 1

    # Disease metrics
    disease_counts: Dict[str, int] = {}
    severity_counts = {"high": 0, "medium": 0, "low": 0}
    for d in all_diagnoses:
        dname = d.get("disease_name_vi") or d.get("predicted_disease") or "Chưa xác định"
        disease_counts[dname] = disease_counts.get(dname, 0) + 1
        sev = (d.get("severity") or "medium").lower()
        if sev in severity_counts:
            severity_counts[sev] += 1

    # Total cultivated area
    total_area_ha = sum(float(p.get("area_hectares") or p.get("area_hectare") or 0) for p in plots)
    if total_area_ha == 0:
        total_area_ha = float(farm.get("area_hectare") or 1.0)

    # Compliance & audit digest
    now_iso = datetime.now(timezone.utc).isoformat()
    raw_hash_input = f"FARM:{farm_id}|USER:{farm.get('user_id')}|TASKS:{total_tasks}|COMPLETED:{len(completed_tasks)}|DIAG:{len(all_diagnoses)}|TS:{now_iso}"
    integrity_digest = hashlib.sha256(raw_hash_input.encode("utf-8")).hexdigest().upper()
    cert_code = f"GARI-VG-{farm_id:04d}-{integrity_digest[:8]}"

    vietgap_status = "ĐẠT TIÊU CHUẨN NHẬT KÝ" if adherence_pct >= 75 and severity_counts["high"] == 0 else "CẦN TĂNG CƯỜNG GIÁM SÁT"

    return {
        "report_metadata": {
            "certificate_code": cert_code,
            "integrity_hash": integrity_digest[:24],
            "generated_at": now_iso,
            "generated_by": f"GARI AgriTech AI Platform (User #{farm.get('user_id')})",
            "standard_reference": "TCVN 11892-1:2017 (Thực hành nông nghiệp tốt - VietGAP Trồng trọt)"
        },
        "farm": {
            "id": farm["id"],
            "name": farm["name"],
            "province": farm.get("province") or "Chưa cập nhật",
            "location": farm.get("location") or "Chưa cập nhật",
            "primary_crop": farm.get("primary_crop") or "Đa canh",
            "variety": farm.get("variety") or "Bản địa",
            "soil_type": farm.get("soil_type") or "Đất thịt phù sa",
            "irrigation_type": farm.get("irrigation_type") or "Tưới nhỏ giọt",
            "total_area_ha": total_area_ha,
            "plots_count": len(plots)
        },
        "plots": [
            {
                "id": p["id"],
                "plot_name": p.get("plot_name") or f"Lô {p['id']}",
                "crop_name": p.get("crop_name") or farm.get("primary_crop"),
                "area_ha": float(p.get("area_hectares") or p.get("area_hectare") or 0.5),
                "planting_date": p.get("planting_date") or "2026-01-15",
                "monitoring_status": p.get("monitoring_status") or "normal"
            }
            for p in plots
        ],
        "adherence_metrics": {
            "total_tasks": total_tasks,
            "completed_count": len(completed_tasks),
            "overdue_count": len(overdue_tasks),
            "pending_count": len(pending_tasks),
            "adherence_percentage": adherence_pct,
            "task_type_breakdown": task_by_type,
            "tasks": all_tasks
        },
        "health_and_disease_metrics": {
            "total_diagnoses": len(all_diagnoses),
            "disease_distribution": disease_counts,
            "severity_distribution": severity_counts,
            "diagnoses": all_diagnoses,
            "timeline_events": timeline_events
        },
        "vietgap_compliance": {
            "status": vietgap_status,
            "adherence_score": adherence_pct,
            "chemical_safety_note": "Các hoạt chất phòng trừ sinh học & hoá học được kiểm soát liều lượng và thời gian cách ly (PHI) theo quy định Bộ NN&PTNT.",
            "recommendation": "Duy trì ghi chép nhật ký số hàng ngày để đủ điều kiện cấp chứng nhận VietGAP mở rộng."
        }
    }


def render_farm_season_report_html(report: Dict[str, Any]) -> str:
    """Render a beautiful, printable VietGAP Seasonal Cultivation Journal."""
    meta = report["report_metadata"]
    farm = report["farm"]
    plots = report["plots"]
    adh = report["adherence_metrics"]
    health = report["health_and_disease_metrics"]
    comp = report["vietgap_compliance"]

    plots_rows = "".join(f"""
        <tr>
            <td style="padding:8px; border:1px solid #e2e8f0; font-weight:600;">{p['plot_name']}</td>
            <td style="padding:8px; border:1px solid #e2e8f0;">{p['crop_name']}</td>
            <td style="padding:8px; border:1px solid #e2e8f0; text-align:center;">{p['area_ha']} ha</td>
            <td style="padding:8px; border:1px solid #e2e8f0; text-align:center;">{p['planting_date']}</td>
            <td style="padding:8px; border:1px solid #e2e8f0; text-align:center;">
                <span style="display:inline-block; padding:2px 8px; border-radius:12px; font-size:12px; background:{'#dcfce7; color:#15803d' if p['monitoring_status'] in ('normal', 'resolved') else '#fef3c7; color:#b45309'};">
                    {p['monitoring_status'].upper()}
                </span>
            </td>
        </tr>
    """ for p in plots) or '<tr><td colspan="5" style="padding:12px; text-align:center; color:#94a3b8;">Chưa đăng ký thửa ruộng/lô vườn.</td></tr>'

    tasks_rows = "".join(f"""
        <tr>
            <td style="padding:8px; border:1px solid #e2e8f0; font-size:13px;">{t.get('due_date') or '-'}</td>
            <td style="padding:8px; border:1px solid #e2e8f0; font-size:13px; font-weight:600;">{t.get('title')}</td>
            <td style="padding:8px; border:1px solid #e2e8f0; font-size:13px; text-align:center;">{t.get('task_type')}</td>
            <td style="padding:8px; border:1px solid #e2e8f0; font-size:13px; text-align:center;">
                <span style="display:inline-block; padding:2px 8px; border-radius:12px; font-size:11px; background:{'#dcfce7; color:#15803d' if t.get('status') == 'completed' else '#fee2e2; color:#b91c1c' if t.get('due_date') and t.get('due_date') < datetime.now().strftime('%Y-%m-%d') else '#f1f5f9; color:#475569'};">
                    {'HOÀN THÀNH' if t.get('status') == 'completed' else 'QUÁ HẠN' if t.get('due_date') and t.get('due_date') < datetime.now().strftime('%Y-%m-%d') else 'ĐANG CHỜ'}
                </span>
            </td>
            <td style="padding:8px; border:1px solid #e2e8f0; font-size:12px; color:#64748b;">{t.get('notes') or '-'}</td>
        </tr>
    """ for t in adh["tasks"][:15]) or '<tr><td colspan="5" style="padding:12px; text-align:center; color:#94a3b8;">Chưa có hoạt động canh tác được ghi nhận.</td></tr>'

    diag_rows = "".join(f"""
        <tr>
            <td style="padding:8px; border:1px solid #e2e8f0; font-size:13px;">{d.get('created_at', '')[:10]}</td>
            <td style="padding:8px; border:1px solid #e2e8f0; font-size:13px;">{d.get('crop_name') or '-'}</td>
            <td style="padding:8px; border:1px solid #e2e8f0; font-size:13px; font-weight:600; color:#b91c1c;">{d.get('disease_name_vi')}</td>
            <td style="padding:8px; border:1px solid #e2e8f0; font-size:13px; text-align:center;">{round(float(d.get('confidence') or 0)*100, 1)}%</td>
            <td style="padding:8px; border:1px solid #e2e8f0; font-size:13px; text-align:center;">
                <span style="font-weight:600; color:{'#b91c1c' if d.get('severity') == 'high' else '#d97706' if d.get('severity') == 'medium' else '#16a34a'};">
                    {(d.get('severity') or 'Trung bình').upper()}
                </span>
            </td>
        </tr>
    """ for d in health["diagnoses"][:10]) or '<tr><td colspan="5" style="padding:12px; text-align:center; color:#94a3b8;">Không ghi nhận dịch hại trong kỳ báo cáo.</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Báo Cáo Mùa Vụ & Nhật Ký Canh Tác — {farm['name']}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #1e293b; background: #f8fafc; margin: 0; padding: 24px; }}
        .sheet {{ max-width: 900px; margin: 0 auto; background: #ffffff; padding: 40px; border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; }}
        .header {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #16a34a; padding-bottom: 20px; margin-bottom: 24px; }}
        .title h1 {{ margin: 0 0 6px 0; font-size: 22px; color: #15803d; }}
        .title p {{ margin: 0; font-size: 13px; color: #64748b; }}
        .cert-badge {{ text-align: right; background: #f0fdf4; border: 1px solid #bbf7d0; padding: 8px 14px; border-radius: 6px; }}
        .cert-code {{ font-family: monospace; font-weight: 700; color: #166534; font-size: 14px; }}
        .section-title {{ font-size: 16px; font-weight: 700; color: #0f172a; margin: 24px 0 12px 0; border-left: 4px solid #16a34a; padding-left: 10px; }}
        .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }}
        .metric-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 14px; }}
        .metric-val {{ font-size: 24px; font-weight: 700; color: #15803d; margin-top: 4px; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
        th {{ background: #f1f5f9; text-align: left; padding: 8px; font-size: 13px; color: #475569; border: 1px solid #e2e8f0; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; display: flex; justify-content: space-between; font-size: 12px; color: #64748b; }}
        .signature-box {{ text-align: center; width: 220px; }}
        .print-btn {{ background: #16a34a; color: #fff; border: none; padding: 10px 18px; border-radius: 6px; font-weight: 600; cursor: pointer; }}
        @media print {{
            body {{ background: #fff; padding: 0; }}
            .sheet {{ box-shadow: none; border: none; padding: 0; max-width: 100%; }}
            .no-print {{ display: none !important; }}
        }}
    </style>
</head>
<body>
    <div style="max-width: 900px; margin: 0 auto 16px auto; display: flex; justify-content: flex-end; gap: 10px;" class="no-print">
        <button class="print-btn" onclick="window.print()">🖨️ In Báo Cáo / Xuất PDF</button>
    </div>

    <div class="sheet">
        <div class="header">
            <div class="title">
                <h1>BÁO CÁO MÙA VỤ & NHẬT KÝ CANH TÁC SỐ</h1>
                <p>Nền tảng Nông nghiệp Thông minh GARI AgriTech AI • Mã chuẩn: {meta['standard_reference']}</p>
            </div>
            <div class="cert-badge">
                <div style="font-size: 11px; color: #166534; font-weight: 600;">CHỨNG THỰC TOÀN VẸN SỐ</div>
                <div class="cert-code">{meta['certificate_code']}</div>
                <div style="font-size: 10px; color: #64748b; margin-top: 2px;">Hash: {meta['integrity_hash']}</div>
            </div>
        </div>

        <div class="grid-2">
            <div class="metric-card">
                <div style="font-size:12px; color:#64748b; text-transform:uppercase;">Thông tin nông trại</div>
                <div style="font-weight:700; font-size:16px; margin-top:4px;">{farm['name']}</div>
                <div style="font-size:13px; color:#475569; margin-top:4px;">Địa phương: <strong>{farm['province']}</strong> ({farm['location']})</div>
                <div style="font-size:13px; color:#475569;">Quy mô: <strong>{farm['total_area_ha']} ha</strong> • Cây chủ lực: <strong>{farm['primary_crop']}</strong></div>
            </div>
            <div class="metric-card">
                <div style="font-size:12px; color:#64748b; text-transform:uppercase;">Đánh giá tuân thủ VietGAP</div>
                <div class="metric-val">{adh['adherence_percentage']}%</div>
                <div style="font-size:13px; color:#15803d; font-weight:600; margin-top:2px;">{comp['status']}</div>
                <div style="font-size:12px; color:#64748b; margin-top:4px;">Đã hoàn tất {adh['completed_count']}/{adh['total_tasks']} công việc canh tác</div>
            </div>
        </div>

        <div class="section-title">1. Danh mục thửa ruộng & Lô sản xuất ({len(plots)} lô)</div>
        <table>
            <thead>
                <tr>
                    <th>Tên thửa / Lô</th>
                    <th>Giống cây trồng</th>
                    <th style="text-align:center;">Diện tích</th>
                    <th style="text-align:center;">Ngày xuống giống</th>
                    <th style="text-align:center;">Trạng thái</th>
                </tr>
            </thead>
            <tbody>
                {plots_rows}
            </tbody>
        </table>

        <div class="section-title">2. Nhật ký & Tiến độ thực hiện công việc canh tác</div>
        <table>
            <thead>
                <tr>
                    <th style="width:110px;">Hạn chót</th>
                    <th>Nội dung công việc</th>
                    <th style="text-align:center; width:90px;">Phân loại</th>
                    <th style="text-align:center; width:110px;">Trạng thái</th>
                    <th>Ghi chú / Hoạt chất</th>
                </tr>
            </thead>
            <tbody>
                {tasks_rows}
            </tbody>
        </table>

        <div class="section-title">3. Nhật ký chẩn đoán & Giám sát dịch hại AI</div>
        <table>
            <thead>
                <tr>
                    <th style="width:110px;">Ngày ghi nhận</th>
                    <th>Cây trồng</th>
                    <th>Dịch hại phát hiện</th>
                    <th style="text-align:center;">Độ tin cậy</th>
                    <th style="text-align:center;">Mức độ</th>
                </tr>
            </thead>
            <tbody>
                {diag_rows}
            </tbody>
        </table>

        <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:6px; padding:14px; margin-top:20px;">
            <div style="font-weight:700; color:#166534; font-size:13px;">KẾT LUẬN & KHUYẾN NGHỊ KỸ THUẬT:</div>
            <div style="font-size:13px; color:#15803d; margin-top:4px;">{comp['recommendation']}</div>
            <div style="font-size:12px; color:#475569; margin-top:4px;">{comp['chemical_safety_note']}</div>
        </div>

        <div class="footer">
            <div>
                <div>Báo cáo được lập tự động bởi Hệ thống GARI AgriTech</div>
                <div>Thời gian kết xuất: {meta['generated_at']}</div>
            </div>
            <div class="signature-box">
                <div style="font-weight:600;">Xác nhận Chủ hộ / Giám đốc HTX</div>
                <div style="height:60px;"></div>
                <div style="border-top:1px dashed #cbd5e1; padding-top:4px; font-size:11px;">(Ký và ghi rõ họ tên)</div>
            </div>
        </div>
    </div>
</body>
</html>
"""



# -----------------------------------------------------------------------------
# Farm Plots Operations
# -----------------------------------------------------------------------------

def _format_diagnosis_row(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Format diagnosis database row with all Sprint 4 required fields and aliases."""
    d = dict(row_dict)
    d["diagnosis_id"] = d.get("id")
    d["actor_user_id"] = d.get("user_id")
    p_id = d.get("farm_plot_id") or d.get("plot_id")
    d["farm_plot_id"] = p_id
    d["plot_id"] = p_id
    d["crop"] = d.get("crop_name") or d.get("crop_id") or "Cây trồng"
    d["model_version"] = d.get("model_version") or "2026.1"
    d["diagnosis_status"] = d.get("diagnosis_status") or "diagnosed"
    d["monitoring_status"] = d.get("monitoring_status") or "open"
    d["consent_store_image"] = bool(d.get("consent_store_image", 0))

    if d.get("top_predictions_json"):
        try:
            d["top_predictions"] = json.loads(d["top_predictions_json"])
        except Exception:
            d["top_predictions"] = []
    elif "top_predictions" not in d:
        d["top_predictions"] = []

    if d.get("regions_json"):
        try:
            d["regions"] = json.loads(d["regions_json"])
        except Exception:
            d["regions"] = []
    elif "regions" not in d:
        d["regions"] = []

    return d


# -----------------------------------------------------------------------------
# Farm Plots Operations (Sprint 4: Agri Intelligence & Minimalist Records)
# -----------------------------------------------------------------------------

def get_plot(plot_id: int, user_id: Optional[int] = None, org_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Retrieve a single farm plot with multi-tenant access check."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if user_id is not None and org_id is not None:
            cursor.execute("""
                SELECT p.*, f.name as farm_name FROM farm_plots p
                JOIN farms f ON p.farm_id = f.id
                WHERE p.id = ? AND (p.user_id = ? OR f.user_id = ? OR p.organization_id = ?)
            """, (plot_id, user_id, user_id, org_id))
        elif user_id is not None:
            cursor.execute("""
                SELECT p.*, f.name as farm_name FROM farm_plots p
                JOIN farms f ON p.farm_id = f.id
                WHERE p.id = ? AND (p.user_id = ? OR f.user_id = ?)
            """, (plot_id, user_id, user_id))
        elif org_id is not None:
            cursor.execute("""
                SELECT p.*, f.name as farm_name FROM farm_plots p
                JOIN farms f ON p.farm_id = f.id
                WHERE p.id = ? AND p.organization_id = ?
            """, (plot_id, org_id))
        else:
            cursor.execute("""
                SELECT p.*, f.name as farm_name FROM farm_plots p
                JOIN farms f ON p.farm_id = f.id
                WHERE p.id = ?
            """, (plot_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def list_plots(
    farm_id: Optional[int] = None,
    user_id: Optional[int] = None,
    org_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """List farm plots scoped by farm, user, or organization."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT p.*, f.name as farm_name FROM farm_plots p
            JOIN farms f ON p.farm_id = f.id
            WHERE 1=1
        """
        params: List[Any] = []
        if farm_id is not None:
            query += " AND p.farm_id = ?"
            params.append(farm_id)
        if user_id is not None and org_id is not None:
            query += " AND (p.user_id = ? OR f.user_id = ? OR p.organization_id = ?)"
            params.extend([user_id, user_id, org_id])
        elif user_id is not None:
            query += " AND (p.user_id = ? OR f.user_id = ?)"
            params.extend([user_id, user_id])
        elif org_id is not None:
            query += " AND p.organization_id = ?"
            params.append(org_id)
        query += " ORDER BY p.id ASC"
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def create_plot(data: Dict[str, Any], user_id: int = 1, org_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Create a new farm plot with voluntary minimalist fields and tenant scope."""
    farm_id = data.get("farm_id")
    if not farm_id:
        return None

    with get_connection() as conn:
        cursor = conn.cursor()
        # Verify user or organization owns the farm
        if org_id is not None:
            cursor.execute("SELECT id FROM farms WHERE id = ? AND (user_id = ? OR id IN (SELECT farm_id FROM farm_plots WHERE organization_id = ?))", (farm_id, user_id, org_id))
        else:
            cursor.execute("SELECT id FROM farms WHERE id = ? AND user_id = ?", (farm_id, user_id))
        if not cursor.fetchone():
            return None

        area_val = float(data.get("area_hectare", data.get("area_hectares", 0.5)))
        cursor.execute("""
            INSERT INTO farm_plots (
                farm_id, user_id, organization_id, plot_name, crop_id, crop_name,
                region, area_hectares, area_hectare, planting_date, notes, status, monitoring_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            farm_id,
            user_id,
            org_id or data.get("organization_id"),
            data.get("plot_name", "Lô mới"),
            data.get("crop_id", "Tomato"),
            data.get("crop_name", "Cà chua"),
            data.get("region", ""),
            area_val,
            area_val,
            data.get("planting_date"),
            data.get("notes", ""),
            data.get("status", "active"),
            data.get("monitoring_status", "open")
        ))
        conn.commit()
        new_id = cursor.lastrowid
        return get_plot(new_id, user_id=user_id, org_id=org_id)


def update_plot(
    plot_id: int,
    data: Dict[str, Any],
    user_id: Optional[int] = None,
    org_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """Update plot metadata and monitoring status with tenant ownership verification."""
    plot = get_plot(plot_id, user_id=user_id, org_id=org_id)
    if not plot:
        return None

    with get_connection() as conn:
        cursor = conn.cursor()
        area_val = float(data["area_hectare"]) if ("area_hectare" in data and data["area_hectare"] is not None) else None
        cursor.execute("""
            UPDATE farm_plots
            SET plot_name = COALESCE(?, plot_name),
                crop_id = COALESCE(?, crop_id),
                crop_name = COALESCE(?, crop_name),
                region = COALESCE(?, region),
                area_hectare = COALESCE(?, area_hectare),
                area_hectares = COALESCE(?, area_hectares),
                planting_date = COALESCE(?, planting_date),
                notes = COALESCE(?, notes),
                status = COALESCE(?, status),
                monitoring_status = COALESCE(?, monitoring_status)
            WHERE id = ?
        """, (
            data.get("plot_name"),
            data.get("crop_id"),
            data.get("crop_name"),
            data.get("region"),
            area_val,
            area_val,
            data.get("planting_date"),
            data.get("notes"),
            data.get("status"),
            data.get("monitoring_status"),
            plot_id
        ))
        conn.commit()
        return get_plot(plot_id, user_id=user_id, org_id=org_id)


def delete_plot(plot_id: int, user_id: Optional[int] = None, org_id: Optional[int] = None) -> bool:
    """Delete plot, cascade timeline events, and unlink from diagnoses."""
    plot = get_plot(plot_id, user_id=user_id, org_id=org_id)
    if not plot:
        return False

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM plot_timeline_events WHERE plot_id = ?", (plot_id,))
        cursor.execute("UPDATE diagnoses SET plot_id = NULL, farm_plot_id = NULL WHERE plot_id = ? OR farm_plot_id = ?", (plot_id, plot_id))
        cursor.execute("DELETE FROM farm_plots WHERE id = ?", (plot_id,))
        conn.commit()
        return cursor.rowcount > 0


def add_plot_timeline_event(
    plot_id: int,
    user_id: int,
    data: Dict[str, Any],
    org_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """Record a user observation note or monitoring status update for a plot."""
    plot = get_plot(plot_id, user_id=user_id, org_id=org_id)
    if not plot:
        return None

    status_val = data.get("monitoring_status") or plot.get("monitoring_status", "open")
    if status_val not in ("open", "monitoring", "resolved", "referred_to_expert"):
        status_val = "monitoring"

    notes_val = data.get("notes") or ""
    diag_id = data.get("diagnosis_id")
    event_type = data.get("event_type", "observation")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO plot_timeline_events (
                plot_id, user_id, organization_id, event_type, diagnosis_id, monitoring_status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            plot_id,
            user_id,
            org_id or plot.get("organization_id"),
            event_type,
            diag_id,
            status_val,
            notes_val
        ))
        cursor.execute("UPDATE farm_plots SET monitoring_status = ? WHERE id = ?", (status_val, plot_id))
        conn.commit()
        event_id = cursor.lastrowid
        cursor.execute("SELECT * FROM plot_timeline_events WHERE id = ?", (event_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_plot_timeline(plot_id: int, user_id: Optional[int] = None, org_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve disease monitoring timeline for a plot.
    Adheres strictly to Sprint 4:
    - Lists chronological diagnosis history and user observation notes.
    - Uses monitoring status: open, monitoring, resolved, referred_to_expert.
    - Does NOT falsely claim disease progression without field verification.
    - Does NOT compare confidences across model versions as a trend.
    """
    plot = get_plot(plot_id, user_id=user_id, org_id=org_id)
    if not plot:
        return None

    with get_connection() as conn:
        cursor = conn.cursor()
        # 1. Fetch diagnoses linked to this plot
        cursor.execute("""
            SELECT * FROM diagnoses
            WHERE plot_id = ? OR farm_plot_id = ?
            ORDER BY id ASC
        """, (plot_id, plot_id))
        diag_rows = cursor.fetchall()
        diagnoses = [_format_diagnosis_row(dict(r)) for r in diag_rows]

        # 2. Fetch timeline events
        cursor.execute("""
            SELECT * FROM plot_timeline_events
            WHERE plot_id = ?
            ORDER BY id ASC
        """, (plot_id,))
        event_rows = cursor.fetchall()
        events = [dict(r) for r in event_rows]

    # Combine into chronological timeline feed
    feed: List[Dict[str, Any]] = []
    for d in diagnoses:
        feed.append({
            "type": "diagnosis",
            "id": f"diag_{d['id']}",
            "diagnosis_id": d["id"],
            "title": f"Chẩn đoán AI: {d.get('disease_name_vi', d.get('predicted_disease', 'Chưa rõ'))}",
            "predicted_disease": d.get("predicted_disease"),
            "disease_name_vi": d.get("disease_name_vi"),
            "confidence": d.get("confidence", 0.0),
            "confidence_percent": d.get("confidence_percent", 0.0),
            "model_version": d.get("model_version", "2026.1"),
            "diagnosis_status": d.get("diagnosis_status", "diagnosed"),
            "monitoring_status": d.get("monitoring_status", "open"),
            "user_notes": d.get("user_notes", ""),
            "created_at": d.get("created_at")
        })

    for ev in events:
        if ev.get("event_type") == "diagnosis" and any(f.get("diagnosis_id") == ev.get("diagnosis_id") for f in feed):
            continue
        feed.append({
            "type": ev.get("event_type", "observation"),
            "id": f"event_{ev['id']}",
            "event_id": ev["id"],
            "title": f"Ghi chú theo dõi: {ev.get('monitoring_status', 'monitoring').upper()}",
            "monitoring_status": ev.get("monitoring_status", "open"),
            "notes": ev.get("notes", ""),
            "user_notes": ev.get("notes", ""),
            "created_at": ev.get("created_at")
        })

    # Sort feed chronologically descending (newest first)
    feed.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)

    total_diag = len(diagnoses)
    if total_diag == 0:
        progression_note = "Chưa có lượt quét bệnh nào được ghi nhận cho thửa/vườn này."
    elif total_diag == 1:
        progression_note = "Đã ghi nhận 1 lượt kiểm tra ban đầu. Cần tiếp tục theo dõi diễn biến thực địa."
    else:
        progression_note = f"Đã ghi nhận {total_diag} lượt quan sát độc lập theo chuỗi thời gian. Dữ liệu phục vụ theo dõi thực địa; hệ thống không tự động suy diễn xu hướng bệnh nặng lên khi chưa có xác nhận từ cán bộ khuyến nông."

    return {
        "plot": plot,
        "diagnoses": diagnoses,
        "timeline_events": events,
        "timeline_feed": feed,
        "summary": {
            "total_diagnoses": total_diag,
            "current_status": plot.get("monitoring_status", "open"),
            "progression_analysis": progression_note,
            "latest_check": diagnoses[-1] if diagnoses else None
        }
    }


# -----------------------------------------------------------------------------
# Diagnosis History Operations (Sprint 4: Multi-Tenant & Safe Storage)
# -----------------------------------------------------------------------------

def save_diagnosis(data: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        actual_user_id = user_id if user_id is not None else data.get("user_id")
        plot_val = data.get("farm_plot_id") or data.get("plot_id")
        org_val = data.get("organization_id")
        model_ver = data.get("model_version", "2026.1")
        diag_status = data.get("diagnosis_status", "diagnosed")
        mon_status = data.get("monitoring_status", "open")
        mon_notes = data.get("monitoring_notes", "")
        consent_img = 1 if data.get("consent_store_image") else 0
        regions_data = data.get("regions", [])

        # If user did not consent to store image, redact or clear image_path
        stored_image_path = data.get("image_path", "")
        if not consent_img and stored_image_path:
            stored_image_path = None

        cursor.execute("""
            INSERT INTO diagnoses (
                user_id, farm_id, plot_id, farm_plot_id, organization_id, farm_name, crop_id, crop_name,
                image_path, image_preview, predicted_disease, disease_name_vi, confidence, confidence_percent,
                severity, top_predictions_json, model_name, model_arch, model_version,
                diagnosis_status, monitoring_status, monitoring_notes, consent_store_image,
                inference_time_ms, device, user_notes, treatment_status,
                attention_path, overlay_path, regions_json,
                growth_stage, user_symptoms, field_conditions, image_references_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            actual_user_id,
            data.get("farm_id"),
            plot_val,
            plot_val,
            org_val,
            data.get("farm_name"),
            data.get("crop_id", "Tomato"),
            data.get("crop_name", "Cà chua"),
            stored_image_path,
            data.get("image_preview", "") if consent_img else "",
            data.get("predicted_disease", "Unknown"),
            data.get("disease_name_vi", data.get("predicted_disease", "Unknown")),
            float(data.get("confidence", 0.0)),
            float(data.get("confidence_percent", data.get("confidence", 0.0) * 100)),
            data.get("severity", "MEDIUM"),
            json.dumps(data.get("top_predictions", [])),
            data.get("model_name", "Gari ConvNeXt"),
            data.get("model_arch", "convnext_small"),
            model_ver,
            diag_status,
            mon_status,
            mon_notes,
            consent_img,
            float(data.get("inference_time_ms", 0.0)),
            data.get("device", "cpu"),
            data.get("user_notes", ""),
            data.get("treatment_status", "pending"),
            data.get("attention_path") or data.get("attention_image_url"),
            data.get("overlay_path") or data.get("overlay_image_url"),
            json.dumps(regions_data) if isinstance(regions_data, (list, dict)) else str(regions_data),
            data.get("growth_stage"),
            data.get("user_symptoms"),
            data.get("field_conditions"),
            json.dumps(data.get("image_references", [])) if isinstance(data.get("image_references"), (list, dict)) else data.get("image_references_json")
        ))
        conn.commit()
        new_id = cursor.lastrowid

        # If linked to a plot, record timeline event
        if plot_val:
            try:
                cursor.execute("""
                    INSERT INTO plot_timeline_events (
                        plot_id, user_id, organization_id, event_type, diagnosis_id, monitoring_status, notes
                    ) VALUES (?, ?, ?, 'diagnosis', ?, ?, ?)
                """, (
                    plot_val,
                    actual_user_id or 1,
                    org_val,
                    new_id,
                    mon_status,
                    data.get("user_notes") or f"Ghi nhận chẩn đoán AI: {data.get('disease_name_vi', data.get('predicted_disease', 'Mầm bệnh'))}"
                ))
                cursor.execute("UPDATE farm_plots SET monitoring_status = ? WHERE id = ?", (mon_status, plot_val))
                conn.commit()
            except Exception as e:
                logger.warning(f"Failed to record timeline event for plot {plot_val}: {e}")

        return get_diagnosis(new_id, user_id=actual_user_id)  # type: ignore


def get_diagnosis(diag_id: int, user_id: Optional[int] = None, org_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Retrieve diagnosis record with tenant-aware isolation check."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if user_id is not None and org_id is not None:
            cursor.execute("""
                SELECT * FROM diagnoses
                WHERE id = ? AND (user_id = ? OR organization_id = ?)
            """, (diag_id, user_id, org_id))
        elif user_id is not None:
            cursor.execute("SELECT * FROM diagnoses WHERE id = ? AND user_id = ?", (diag_id, user_id))
        elif org_id is not None:
            cursor.execute("SELECT * FROM diagnoses WHERE id = ? AND organization_id = ?", (diag_id, org_id))
        else:
            cursor.execute("SELECT * FROM diagnoses WHERE id = ?", (diag_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return _format_diagnosis_row(dict(row))


def list_diagnoses(
    user_id: Optional[int] = None,
    farm_id: Optional[int] = None,
    plot_id: Optional[int] = None,
    crop_id: Optional[str] = None,
    organization_id: Optional[int] = None,
    diagnosis_status: Optional[str] = None,
    limit: int = 50,
    allow_unscoped: bool = False
) -> List[Dict[str, Any]]:
    """List diagnoses with strict tenant, farm, and plot scoping."""
    # Security Rule: Never return unscoped diagnoses across all users unless explicitly permitted (e.g. platform admin)
    if user_id is None and organization_id is None and not allow_unscoped:
        return []

    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM diagnoses WHERE 1=1"
        params: List[Any] = []
        if user_id is not None and organization_id is not None:
            query += " AND (user_id = ? OR organization_id = ?)"
            params.extend([user_id, organization_id])
        elif user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)
        elif organization_id is not None:
            query += " AND organization_id = ?"
            params.append(organization_id)

        if farm_id is not None:
            query += " AND farm_id = ?"
            params.append(farm_id)
        if plot_id is not None:
            query += " AND (plot_id = ? OR farm_plot_id = ?)"
            params.extend([plot_id, plot_id])
        if crop_id and crop_id != "all":
            query += " AND crop_id = ?"
            params.append(crop_id)
        if diagnosis_status:
            query += " AND diagnosis_status = ?"
            params.append(diagnosis_status)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        results = []
        for row in cursor.fetchall():
            results.append(_format_diagnosis_row(dict(row)))
        return results


def delete_diagnosis(diag_id: int, user_id: Optional[int] = None, org_id: Optional[int] = None) -> bool:
    """
    Delete a diagnosis record owned by user (Priority B).
    Enforces user isolation, unlinks saved image from disk if exists,
    and removes linked timeline events.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        if user_id is not None and org_id is not None:
            cursor.execute("SELECT id, image_path FROM diagnoses WHERE id = ? AND (user_id = ? OR organization_id = ?)", (diag_id, user_id, org_id))
        elif user_id is not None:
            cursor.execute("SELECT id, image_path FROM diagnoses WHERE id = ? AND user_id = ?", (diag_id, user_id))
        elif org_id is not None:
            cursor.execute("SELECT id, image_path FROM diagnoses WHERE id = ? AND organization_id = ?", (diag_id, org_id))
        else:
            cursor.execute("SELECT id, image_path FROM diagnoses WHERE id = ?", (diag_id,))
        row = cursor.fetchone()
        if not row:
            return False

        img_path = row["image_path"] if isinstance(row, sqlite3.Row) else row[1]
        if img_path:
            try:
                clean_name = os.path.basename(str(img_path).replace("/uploads/", ""))
                target_file = UPLOADS_DIR / clean_name
                if target_file.exists():
                    target_file.unlink()
            except Exception as exc:
                logger.warning(f"Could not unlink image for diagnosis {diag_id}: {exc}")

        # Remove linked timeline events
        cursor.execute("DELETE FROM plot_timeline_events WHERE diagnosis_id = ?", (diag_id,))

        if user_id is not None and org_id is not None:
            cursor.execute("DELETE FROM diagnoses WHERE id = ? AND (user_id = ? OR organization_id = ?)", (diag_id, user_id, org_id))
        elif user_id is not None:
            cursor.execute("DELETE FROM diagnoses WHERE id = ? AND user_id = ?", (diag_id, user_id))
        elif org_id is not None:
            cursor.execute("DELETE FROM diagnoses WHERE id = ? AND organization_id = ?", (diag_id, org_id))
        else:
            cursor.execute("DELETE FROM diagnoses WHERE id = ?", (diag_id,))
        conn.commit()
        return cursor.rowcount > 0


def update_diagnosis_followup(
    diag_id: int,
    monitoring_status: str,
    observation_notes: Optional[str] = None,
    treatment_action: Optional[str] = None,
    user_id: Optional[int] = None,
    org_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Update diagnosis follow-up and field monitoring progress (Queue P1.5).
    Guarantees:
    - Enforces valid monitoring statuses: ('open', 'monitoring', 'treated', 'recovered', 'deteriorated', 'closed').
    - Requires observation notes when claiming recovery or deterioration (prevents unfounded automated claims).
    - Records an audit timeline event in plot_timeline_events when associated with a plot.
    """
    valid_statuses = ("open", "monitoring", "treated", "recovered", "deteriorated", "closed")
    norm_status = str(monitoring_status or "").strip().lower()
    if norm_status not in valid_statuses:
        raise ValueError(f"Trạng thái theo dõi không hợp lệ: {norm_status}. Các giá trị hợp lệ: {', '.join(valid_statuses)}")

    # Enforce evidence check: No plant can be claimed recovered or deteriorated without field observation notes
    if norm_status in ("recovered", "deteriorated"):
        notes_str = str(observation_notes or "").strip()
        if not notes_str or len(notes_str) < 5:
            raise ValueError(
                "Để cập nhật trạng thái 'Phục hồi' (recovered) hoặc 'Suy giảm' (deteriorated), "
                "bắt buộc phải ghi nhận nhật ký quan sát thực địa chi tiết (tối thiểu 5 ký tự) "
                "để đảm bảo tính xác thực lâm sàng và không tạo kết luận tự động thiếu căn cứ."
            )

    diag = get_diagnosis(diag_id, user_id=user_id, org_id=org_id)
    if not diag:
        return None

    with get_connection() as conn:
        cursor = conn.cursor()
        current_notes = diag.get("monitoring_notes") or ""
        timestamp_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
        new_note_entry = f"[{timestamp_str}] [{norm_status.upper()}] "
        if observation_notes:
            new_note_entry += observation_notes.strip()
        if treatment_action:
            new_note_entry += f" (Biện pháp: {treatment_action.strip()})"

        updated_notes = f"{new_note_entry}\n{current_notes}".strip() if current_notes else new_note_entry
        new_treatment_status = "completed" if norm_status in ("recovered", "closed") else ("in_progress" if norm_status in ("treated", "monitoring") else "pending")

        cursor.execute("""
            UPDATE diagnoses
            SET monitoring_status = ?,
                monitoring_notes = ?,
                treatment_status = ?
            WHERE id = ?
        """, (norm_status, updated_notes, new_treatment_status, diag_id))

        # Record timeline event if linked to a plot
        plot_id = diag.get("plot_id") or diag.get("farm_plot_id")
        if plot_id:
            try:
                cursor.execute("""
                    INSERT INTO plot_timeline_events (
                        plot_id, user_id, organization_id, event_type, diagnosis_id, monitoring_status, notes
                    ) VALUES (?, ?, ?, 'followup', ?, ?, ?)
                """, (
                    plot_id,
                    user_id or diag.get("user_id", 1),
                    org_id or diag.get("organization_id"),
                    diag_id,
                    norm_status,
                    new_note_entry
                ))
                cursor.execute("UPDATE farm_plots SET monitoring_status = ? WHERE id = ?", (norm_status, plot_id))
            except Exception as e:
                logger.warning(f"Could not record timeline event for follow-up on plot {plot_id}: {e}")

        conn.commit()

    return get_diagnosis(diag_id, user_id=user_id, org_id=org_id)


def log_audit_metric(
    event_type: str,
    model_name: Optional[str] = None,
    crop_id: Optional[str] = None,
    rejection_reason: Optional[str] = None,
    is_vip: bool = False,
    user_id: Optional[int] = None,
    client_id: Optional[str] = None,
    latency_ms: float = 0.0
) -> None:
    """
    Record an audit or inference event for startup metrics (Priority E).
    Privacy-safe: Does NOT log photos or sensitive personal data.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_metrics (
                    event_type, model_name, crop_id, rejection_reason, is_vip, user_id, client_id, latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_type,
                model_name,
                crop_id,
                rejection_reason,
                1 if is_vip else 0,
                user_id,
                client_id,
                float(latency_ms or 0.0)
            ))
            conn.commit()
    except Exception as exc:
        logger.warning(f"Failed to log audit metric: {exc}")


def get_startup_metrics() -> Dict[str, Any]:
    """
    Computes startup telemetry and operational KPIs (Priority E):
    - Total registered accounts
    - 7-day active users
    - Successful classifications
    - Photo rejection rate (validation failures)
    - Returning user retention rate
    - Free vs VIP usage ratio
    - Inference errors count
    - Model invocation breakdown
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Total registered accounts
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # 2. Active users in last 7 days (distinct users + clients)
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) 
            FROM diagnoses 
            WHERE created_at >= date('now', '-7 days') AND user_id IS NOT NULL
        """)
        active_db_users = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COUNT(DISTINCT COALESCE(client_id, CAST(user_id AS TEXT)))
            FROM audit_metrics
            WHERE created_at >= date('now', '-7 days')
        """)
        active_clients = cursor.fetchone()[0]
        active_users_7d = max(active_db_users, active_clients, 1)

        # 3. Successful classifications
        cursor.execute("SELECT COUNT(*) FROM diagnoses")
        successful_diagnoses = cursor.fetchone()[0]
        
        # 4. Rejected photo rate (validation failures vs total attempts)
        cursor.execute("SELECT COUNT(*) FROM audit_metrics WHERE event_type = 'validation_rejected'")
        rejected_photo_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM audit_metrics WHERE event_type IN ('diagnosis_success', 'validation_rejected')")
        total_attempts = cursor.fetchone()[0]
        if total_attempts == 0:
            total_attempts = successful_diagnoses + rejected_photo_count
        rejection_rate = round((rejected_photo_count / total_attempts * 100), 1) if total_attempts > 0 else 0.0

        # 5. Returning users retention rate (users with >= 2 diagnoses)
        cursor.execute("""
            SELECT COUNT(*) FROM (
                SELECT user_id FROM diagnoses WHERE user_id IS NOT NULL GROUP BY user_id HAVING COUNT(*) >= 2
            )
        """)
        returning_users = cursor.fetchone()[0]
        retention_rate = round((returning_users / total_users * 100), 1) if total_users > 0 else 0.0

        # 6. Free vs VIP usage ratio
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN is_vip = 1 THEN 1 ELSE 0 END) as vip_count,
                SUM(CASE WHEN is_vip = 0 THEN 1 ELSE 0 END) as free_count
            FROM audit_metrics
            WHERE event_type = 'diagnosis_success'
        """)
        row = cursor.fetchone()
        vip_runs = row[0] or 0
        free_runs = row[1] or 0
        total_runs = vip_runs + free_runs
        if total_runs > 0:
            free_pct = round(free_runs / total_runs * 100, 1)
            vip_pct = round(vip_runs / total_runs * 100, 1)
            ratio_text = f"{free_pct}% Miễn phí / {vip_pct}% VIP"
        else:
            free_pct, vip_pct = 100.0, 0.0
            ratio_text = "100.0% Miễn phí / 0.0% VIP"

        # 7. Inference errors count
        cursor.execute("SELECT COUNT(*) FROM audit_metrics WHERE event_type = 'inference_error'")
        inference_errors = cursor.fetchone()[0]

        # 8. Models invoked breakdown
        cursor.execute("""
            SELECT COALESCE(model_name, 'Gari ConvNeXt') as model, COUNT(*) as invocations
            FROM diagnoses
            GROUP BY model_name
            ORDER BY invocations DESC
            LIMIT 6
        """)
        models_invoked = [{"model": r[0], "count": r[1]} for r in cursor.fetchall()]
        if not models_invoked:
            models_invoked = [{"model": "ConvNeXt (Cục bộ)", "count": successful_diagnoses}]

        return {
            "total_registered_accounts": total_users,
            "active_users_7d": active_users_7d,
            "successful_classifications": successful_diagnoses,
            "rejected_photo_count": rejected_photo_count,
            "rejected_photo_rate_percent": rejection_rate,
            "returning_users_count": returning_users,
            "retention_rate_percent": retention_rate,
            "free_vs_vip": {
                "free_count": free_runs,
                "vip_count": vip_runs,
                "free_percent": free_pct,
                "vip_percent": vip_pct,
                "ratio_text": ratio_text
            },
            "inference_errors_count": inference_errors,
            "models_invoked_breakdown": models_invoked,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# -----------------------------------------------------------------------------
# Notifications Operations
# -----------------------------------------------------------------------------

def list_notifications(user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM notifications
            WHERE user_id = ?
            ORDER BY id DESC LIMIT ?
        """, (user_id, limit))
        return [dict(r) for r in cursor.fetchall()]


def mark_notification_as_read(notif_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (notif_id, user_id))
        conn.commit()
        return cursor.rowcount > 0


def mark_all_notifications_read(user_id: int) -> int:
    """Mark all unread notifications as read for a given user."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0", (user_id,))
        conn.commit()
        return cursor.rowcount


def create_notification(user_id: int, title: str, message: str, notification_type: str = "info") -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, notification_type)
            VALUES (?, ?, ?, ?)
        """, (user_id, title, message, notification_type))
        conn.commit()
        new_id = cursor.lastrowid
        cursor.execute("SELECT * FROM notifications WHERE id = ?", (new_id,))
        return dict(cursor.fetchone())


# -----------------------------------------------------------------------------
# Expert Consultation Operations
# -----------------------------------------------------------------------------

def list_expert_cases(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        if user_id is not None:
            cursor.execute("SELECT * FROM expert_cases WHERE user_id = ? ORDER BY id DESC", (user_id,))
        else:
            cursor.execute("SELECT * FROM expert_cases ORDER BY id DESC")
        return [dict(r) for r in cursor.fetchall()]


def submit_expert_case(data: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        actual_user_id = user_id or data.get("user_id") or 1
        cursor.execute("""
            INSERT INTO expert_cases (
                user_id, diagnosis_id, farm_id, farm_name, farmer_name, phone, crop_name,
                suspected_disease, symptoms_description, field_conditions,
                image_preview, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            actual_user_id,
            data.get("diagnosis_id"),
            data.get("farm_id"),
            data.get("farm_name", ""),
            data.get("farmer_name", "Nông dân"),
            data.get("phone", ""),
            data.get("crop_name", ""),
            data.get("suspected_disease", ""),
            data.get("symptoms_description", ""),
            data.get("field_conditions", ""),
            data.get("image_preview", ""),
            "Submitted"
        ))
        conn.commit()
        new_id = cursor.lastrowid
        cursor.execute("SELECT * FROM expert_cases WHERE id = ?", (new_id,))
        return dict(cursor.fetchone())


def update_expert_case(case_id: int, status: str, expert_notes: Optional[str] = None, assigned_expert: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE expert_cases
            SET status = ?,
                expert_notes = COALESCE(?, expert_notes),
                assigned_expert = COALESCE(?, assigned_expert),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (status, expert_notes, assigned_expert, case_id))
        conn.commit()
        cursor.execute("SELECT * FROM expert_cases WHERE id = ?", (case_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


# -----------------------------------------------------------------------------
# Risk Monitoring Operations
# -----------------------------------------------------------------------------

def list_risk_alerts() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM risk_alerts ORDER BY id DESC")
        return [dict(r) for r in cursor.fetchall()]


# -----------------------------------------------------------------------------
# Operational Dashboard Aggregation (User-Scoped & Realistic)
# -----------------------------------------------------------------------------

def get_dashboard_metrics(user_id: Optional[int] = None) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()

        if user_id is not None:
            # 1. Total farms & hectares for user
            cursor.execute("SELECT COUNT(*), COALESCE(SUM(area_hectare), 0.0) FROM farms WHERE user_id = ?", (user_id,))
            farms_count, total_hectares = cursor.fetchone()

            # 2. Total diagnoses & health rates for user
            cursor.execute("SELECT COUNT(*) FROM diagnoses WHERE user_id = ?", (user_id,))
            total_diagnoses = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM diagnoses WHERE user_id = ? AND (severity = 'HEALTHY' OR severity = 'NORMAL')", (user_id,))
            healthy_count = cursor.fetchone()[0]

            health_rate = round((healthy_count / total_diagnoses * 100), 1) if total_diagnoses > 0 else 0.0

            # 3. Disease distribution for user
            cursor.execute("""
                SELECT predicted_disease, COUNT(*) as count
                FROM diagnoses
                WHERE user_id = ? AND severity NOT IN ('HEALTHY', 'NORMAL')
                GROUP BY predicted_disease
                ORDER BY count DESC LIMIT 5
            """, (user_id,))
            disease_dist = [{"disease": r[0], "count": r[1]} for r in cursor.fetchall()]

            # 4. Crop distribution for user
            cursor.execute("""
                SELECT crop_name, COUNT(*) as count
                FROM diagnoses
                WHERE user_id = ?
                GROUP BY crop_name
                ORDER BY count DESC LIMIT 5
            """, (user_id,))
            crop_dist = [{"crop": r[0], "count": r[1]} for r in cursor.fetchall()]

            # 5. Pending expert cases for user
            cursor.execute("SELECT COUNT(*) FROM expert_cases WHERE user_id = ? AND status != 'Resolved'", (user_id,))
            pending_expert_cases = cursor.fetchone()[0]

            # 6. Recent diagnoses for user
            cursor.execute("""
                SELECT id, farm_name, crop_name, predicted_disease, confidence, severity, created_at, treatment_status
                FROM diagnoses
                WHERE user_id = ?
                ORDER BY id DESC LIMIT 5
            """, (user_id,))
            recent_diagnoses = [dict(r) for r in cursor.fetchall()]

            # 7. Unread notifications count
            cursor.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,))
            unread_notifs = cursor.fetchone()[0]

        else:
            # Global fallback
            cursor.execute("SELECT COUNT(*), COALESCE(SUM(area_hectare), 0.0) FROM farms")
            farms_count, total_hectares = cursor.fetchone()

            cursor.execute("SELECT COUNT(*) FROM diagnoses")
            total_diagnoses = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM diagnoses WHERE severity = 'HEALTHY' OR severity = 'NORMAL'")
            healthy_count = cursor.fetchone()[0]
            health_rate = round((healthy_count / total_diagnoses * 100), 1) if total_diagnoses > 0 else 0.0

            cursor.execute("""
                SELECT predicted_disease, COUNT(*) as count
                FROM diagnoses
                WHERE severity NOT IN ('HEALTHY', 'NORMAL')
                GROUP BY predicted_disease
                ORDER BY count DESC LIMIT 5
            """)
            disease_dist = [{"disease": r[0], "count": r[1]} for r in cursor.fetchall()]

            cursor.execute("""
                SELECT crop_name, COUNT(*) as count
                FROM diagnoses
                GROUP BY crop_name
                ORDER BY count DESC LIMIT 5
            """)
            crop_dist = [{"crop": r[0], "count": r[1]} for r in cursor.fetchall()]

            cursor.execute("SELECT COUNT(*) FROM expert_cases WHERE status != 'Resolved'")
            pending_expert_cases = cursor.fetchone()[0]

            cursor.execute("""
                SELECT id, farm_name, crop_name, predicted_disease, confidence, severity, created_at, treatment_status
                FROM diagnoses
                ORDER BY id DESC LIMIT 5
            """)
            recent_diagnoses = [dict(r) for r in cursor.fetchall()]
            unread_notifs = 0

        # Active risk alerts (regional telemetry relevant to all agricultural operators)
        cursor.execute("SELECT * FROM risk_alerts ORDER BY id DESC LIMIT 3")
        recent_alerts = [dict(r) for r in cursor.fetchall()]

        return {
            "farms_total": farms_count,
            "total_hectares": round(total_hectares, 1),
            "diagnoses_total": total_diagnoses,
            "healthy_rate_percent": health_rate,
            "disease_distribution": disease_dist,
            "crop_distribution": crop_dist,
            "pending_expert_cases": pending_expert_cases,
            "recent_diagnoses": recent_diagnoses,
            "recent_alerts": recent_alerts,
            "unread_notifications_count": unread_notifs,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }



# -----------------------------------------------------------------------------
# Sprint 5: Pilot Leads & Market Validation
# -----------------------------------------------------------------------------

PILOT_REQUEST_STATUSES = ("new", "reviewing", "contacted", "accepted", "declined", "closed")
PILOT_CUSTOMER_TYPES = ("farmer", "cooperative", "research", "other")
FEEDBACK_TYPES = ("looks_correct", "uncertain", "looks_incorrect", "image_rejected", "guidance_unhelpful", "other")
FEEDBACK_STATUSES = ("new", "reviewing", "resolved", "dismissed")


def create_pilot_request(
    name: str,
    contact: str,
    customer_type: str = "farmer",
    crops_of_interest: Optional[str] = None,
    region: Optional[str] = None,
    problem_statement: Optional[str] = None,
    consent_given: bool = False
) -> Dict[str, Any]:
    """
    Register a new pilot/demo request.
    Strictly requires consent and valid contact.
    Status starts as 'new'. Never auto-accepted.
    """
    if not name or len(name.strip()) < 2:
        raise ValueError("Họ và tên người liên hệ là bắt buộc (tối thiểu 2 ký tự).")
    if not contact or len(contact.strip()) < 3:
        raise ValueError("Phương thức liên hệ (email hoặc số điện thoại) là bắt buộc.")
    if not consent_given:
        raise ValueError("Bạn cần đồng ý lưu trữ thông tin liên hệ để nhận hỗ trợ pilot.")

    c_type = customer_type.strip().lower() if customer_type else "farmer"
    if c_type not in PILOT_CUSTOMER_TYPES:
        c_type = "other"

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pilot_requests (
                name, contact, customer_type, crops_of_interest, region, problem_statement, consent_given, status
            ) VALUES (?, ?, ?, ?, ?, ?, 1, 'new')
        """, (
            name.strip(),
            contact.strip(),
            c_type,
            crops_of_interest.strip() if crops_of_interest else None,
            region.strip() if region else None,
            problem_statement.strip() if problem_statement else None
        ))
        req_id = cursor.lastrowid

        # Log creation in audit trail
        cursor.execute("""
            INSERT INTO pilot_audit_logs (request_id, old_status, new_status, notes)
            VALUES (?, NULL, 'new', 'Gửi yêu cầu pilot ban đầu')
        """, (req_id,))

        conn.commit()
        return get_pilot_request(req_id)


def get_pilot_request(req_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve single pilot request with audit trail."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pilot_requests WHERE id = ?", (req_id,))
        row = cursor.fetchone()
        if not row:
            return None
        res = dict(row)
        res["consent_given"] = bool(res["consent_given"])

        # Fetch audit history
        cursor.execute("""
            SELECT id, old_status, new_status, changed_by_user_id, notes, created_at
            FROM pilot_audit_logs
            WHERE request_id = ?
            ORDER BY id ASC
        """, (req_id,))
        res["audit_history"] = [dict(r) for r in cursor.fetchall()]
        return res


def list_pilot_requests(
    status: Optional[str] = None,
    customer_type: Optional[str] = None,
    crop: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """List pilot requests with multi-parameter filtering for admin."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM pilot_requests WHERE 1=1"
        params: List[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status.strip().lower())
        if customer_type:
            query += " AND customer_type = ?"
            params.append(customer_type.strip().lower())
        if crop:
            query += " AND crops_of_interest LIKE ?"
            params.append(f"%{crop.strip()}%")
        if date_from:
            query += " AND created_at >= ?"
            params.append(date_from.strip())
        if date_to:
            query += " AND created_at <= ?"
            params.append(date_to.strip())

        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([max(1, min(limit, 500)), max(0, offset)])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["consent_given"] = bool(d["consent_given"])
            results.append(d)
        return results


def update_pilot_request(
    req_id: int,
    status: Optional[str] = None,
    internal_notes: Optional[str] = None,
    changed_by_user_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Update pilot request status or internal notes.
    Logs audit event if status changes.
    """
    req = get_pilot_request(req_id)
    if not req:
        return None

    old_status = req["status"]
    new_status = status.strip().lower() if status else old_status

    if new_status not in PILOT_REQUEST_STATUSES:
        raise ValueError(f"Trạng thái không hợp lệ: {new_status}. Phải thuộc: {PILOT_REQUEST_STATUSES}")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pilot_requests
            SET status = ?,
                internal_notes = COALESCE(?, internal_notes),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_status, internal_notes, req_id))

        if new_status != old_status or internal_notes:
            cursor.execute("""
                INSERT INTO pilot_audit_logs (request_id, old_status, new_status, changed_by_user_id, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (
                req_id,
                old_status,
                new_status,
                changed_by_user_id,
                internal_notes or f"Thay đổi trạng thái từ {old_status} sang {new_status}"
            ))

        conn.commit()
        return get_pilot_request(req_id)


# -----------------------------------------------------------------------------
# Sprint 5: Diagnosis Feedback Operations (User Feedback ≠ Ground Truth)
# -----------------------------------------------------------------------------

def create_diagnosis_feedback(
    diagnosis_id: Optional[int],
    user_id: Optional[int],
    organization_id: Optional[int],
    feedback_type: str,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Record user feedback on diagnosis result.
    Strictly preserves model output: never modifies predicted disease or expert verification.
    """
    f_type = feedback_type.strip().lower() if feedback_type else "other"
    if f_type not in FEEDBACK_TYPES:
        raise ValueError(f"Loại phản hồi không hợp lệ: {feedback_type}. Phải thuộc: {FEEDBACK_TYPES}")

    with get_connection() as conn:
        cursor = conn.cursor()
        # Verify diagnosis exists if diagnosis_id is provided
        if diagnosis_id:
            cursor.execute("SELECT id, user_id, organization_id FROM diagnoses WHERE id = ?", (diagnosis_id,))
            diag = cursor.fetchone()
            if not diag:
                raise ValueError("Không tìm thấy bản ghi chẩn đoán tương ứng.")
            # Inherit organization_id from diagnosis if not provided
            if not organization_id and diag["organization_id"]:
                organization_id = diag["organization_id"]

        cursor.execute("""
            INSERT INTO diagnosis_feedbacks (
                diagnosis_id, user_id, organization_id, feedback_type, notes, status
            ) VALUES (?, ?, ?, ?, ?, 'new')
        """, (
            diagnosis_id,
            user_id,
            organization_id,
            f_type,
            notes.strip() if notes else None
        ))
        fb_id = cursor.lastrowid
        conn.commit()

        return get_diagnosis_feedback(fb_id, user_id=user_id, org_id=organization_id, is_admin=True)


def get_diagnosis_feedback(
    feedback_id: int,
    user_id: Optional[int] = None,
    org_id: Optional[int] = None,
    is_admin: bool = False
) -> Optional[Dict[str, Any]]:
    """Retrieve single diagnosis feedback with tenant/owner authorization."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM diagnosis_feedbacks WHERE id = ?", (feedback_id,))
        row = cursor.fetchone()
        if not row:
            return None
        fb = dict(row)

        if not is_admin:
            is_owner = (user_id is not None and fb.get("user_id") == user_id)
            is_org = (org_id is not None and fb.get("organization_id") == org_id)
            if not (is_owner or is_org):
                return None

        return fb


def list_diagnosis_feedbacks(
    user_id: Optional[int] = None,
    org_id: Optional[int] = None,
    diagnosis_id: Optional[int] = None,
    status: Optional[str] = None,
    is_admin: bool = False,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """List feedbacks respecting tenant scoping or admin overview."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT f.*, d.crop_name, d.predicted_disease FROM diagnosis_feedbacks f LEFT JOIN diagnoses d ON f.diagnosis_id = d.id WHERE 1=1"
        params: List[Any] = []

        if not is_admin:
            if user_id is not None and org_id is not None:
                query += " AND (f.user_id = ? OR f.organization_id = ?)"
                params.extend([user_id, org_id])
            elif user_id is not None:
                query += " AND f.user_id = ?"
                params.append(user_id)
            elif org_id is not None:
                query += " AND f.organization_id = ?"
                params.append(org_id)
            else:
                return []

        if diagnosis_id:
            query += " AND f.diagnosis_id = ?"
            params.append(diagnosis_id)
        if status:
            query += " AND f.status = ?"
            params.append(status.strip().lower())

        query += " ORDER BY f.id DESC LIMIT ? OFFSET ?"
        params.extend([max(1, min(limit, 200)), max(0, offset)])

        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def update_diagnosis_feedback(
    feedback_id: int,
    status: Optional[str] = None,
    admin_notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Admin updates feedback triage status."""
    fb = get_diagnosis_feedback(feedback_id, is_admin=True)
    if not fb:
        return None

    new_status = status.strip().lower() if status else fb["status"]
    if new_status not in FEEDBACK_STATUSES:
        raise ValueError(f"Trạng thái feedback không hợp lệ: {new_status}")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE diagnosis_feedbacks
            SET status = ?,
                admin_notes = COALESCE(?, admin_notes),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_status, admin_notes, feedback_id))
        conn.commit()
        return get_diagnosis_feedback(feedback_id, is_admin=True)


def delete_diagnosis_feedback(
    feedback_id: int,
    user_id: Optional[int] = None,
    org_id: Optional[int] = None,
    is_admin: bool = False
) -> bool:
    """Delete a feedback entry (Right to Erasure / GDPR compliance)."""
    fb = get_diagnosis_feedback(feedback_id, user_id=user_id, org_id=org_id, is_admin=is_admin)
    if not fb:
        return False

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM diagnosis_feedbacks WHERE id = ?", (feedback_id,))
        conn.commit()
        return True


# -----------------------------------------------------------------------------
# Sprint 5: Non-Fabricated Pilot Metrics Engine
# -----------------------------------------------------------------------------

def get_pilot_metrics(time_range: str = "30d") -> Dict[str, Any]:
    """
    Computes real, non-fabricated metrics for market and pilot validation.
    Strictly calculates from active records without dummy counters or false accuracy claims.
    """
    time_range = time_range.strip().lower() if time_range else "30d"
    range_clauses = {
        "7d": "datetime('now', '-7 days')",
        "30d": "datetime('now', '-30 days')",
        "90d": "datetime('now', '-90 days')",
    }
    date_cutoff_sql = range_clauses.get(time_range, None)

    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Pilot Requests Breakdown
        req_query = "SELECT status, COUNT(*) FROM pilot_requests"
        if date_cutoff_sql:
            req_query += f" WHERE created_at >= {date_cutoff_sql}"
        req_query += " GROUP BY status"
        cursor.execute(req_query)
        req_by_status = {s: 0 for s in PILOT_REQUEST_STATUSES}
        total_requests = 0
        for st, cnt in cursor.fetchall():
            if st in req_by_status:
                req_by_status[st] = cnt
            total_requests += cnt

        # By customer type
        type_query = "SELECT customer_type, COUNT(*) FROM pilot_requests"
        if date_cutoff_sql:
            type_query += f" WHERE created_at >= {date_cutoff_sql}"
        type_query += " GROUP BY customer_type"
        cursor.execute(type_query)
        req_by_type = {t: 0 for t in PILOT_CUSTOMER_TYPES}
        for ct, cnt in cursor.fetchall():
            if ct in req_by_type:
                req_by_type[ct] = cnt
            else:
                req_by_type["other"] = req_by_type.get("other", 0) + cnt

        # 2. Pilot Organizations Count (organizations on pilot plan)
        try:
            cursor.execute("SELECT COUNT(*) FROM organizations WHERE plan_id = 'pilot' OR status = 'pending'")
            pilot_orgs_count = cursor.fetchone()[0]
        except Exception:
            pilot_orgs_count = 0

        # 3. Active Users (Strictly: users who either logged in or ran diagnosis in time window)
        active_users_sql = """
            SELECT COUNT(DISTINCT uid) FROM (
                SELECT user_id as uid FROM user_sessions
                WHERE 1=1 {session_date_filter}
                UNION
                SELECT user_id as uid FROM diagnoses
                WHERE user_id IS NOT NULL {diag_date_filter}
            )
        """
        s_filter = f"AND created_at >= {date_cutoff_sql}" if date_cutoff_sql else ""
        d_filter = f"AND created_at >= {date_cutoff_sql}" if date_cutoff_sql else ""
        cursor.execute(active_users_sql.format(session_date_filter=s_filter, diag_date_filter=d_filter))
        active_users_count = cursor.fetchone()[0]

        # 4. Total Diagnoses in Time Window
        diag_cnt_query = "SELECT COUNT(*) FROM diagnoses WHERE 1=1"
        if date_cutoff_sql:
            diag_cnt_query += f" AND created_at >= {date_cutoff_sql}"
        cursor.execute(diag_cnt_query)
        total_diagnoses = cursor.fetchone()[0]

        # 5. Invalid Image Rejection Rate (Leaf Gate)
        gate_sql = """
            SELECT
                SUM(CASE WHEN event_type IN ('inference_leaf_gate_reject', 'leaf_gate_rejected', 'leaf_rejection') OR rejection_reason IS NOT NULL THEN 1 ELSE 0 END) as rejected_cnt,
                COUNT(*) as total_evals
            FROM audit_metrics
            WHERE 1=1
        """
        if date_cutoff_sql:
            gate_sql += f" AND created_at >= {date_cutoff_sql}"
        cursor.execute(gate_sql)
        row = cursor.fetchone()
        rejected_cnt = row[0] or 0
        total_evals = row[1] or 0
        rejection_rate = round((rejected_cnt / total_evals) * 100, 1) if total_evals > 0 else None

        # 6. Uncertain / Needs Review Diagnoses Rate
        uncertain_sql = """
            SELECT
                SUM(CASE WHEN diagnosis_status = 'needs_review' OR confidence < 0.60 OR predicted_disease LIKE '%unknown%' OR predicted_disease LIKE '%unsupported%' THEN 1 ELSE 0 END) as uncertain_cnt,
                COUNT(*) as total_cnt
            FROM diagnoses
            WHERE 1=1
        """
        if date_cutoff_sql:
            uncertain_sql += f" AND created_at >= {date_cutoff_sql}"
        cursor.execute(uncertain_sql)
        u_row = cursor.fetchone()
        uncertain_cnt = u_row[0] or 0
        uncertain_total = u_row[1] or 0
        uncertain_rate = round((uncertain_cnt / uncertain_total) * 100, 1) if uncertain_total > 0 else None

        # 7. Feedback Breakdown
        fb_query = "SELECT feedback_type, COUNT(*) FROM diagnosis_feedbacks WHERE 1=1"
        if date_cutoff_sql:
            fb_query += f" AND created_at >= {date_cutoff_sql}"
        fb_query += " GROUP BY feedback_type"
        cursor.execute(fb_query)
        fb_by_type = {t: 0 for t in FEEDBACK_TYPES}
        total_feedbacks = 0
        for ft, cnt in cursor.fetchall():
            if ft in fb_by_type:
                fb_by_type[ft] = cnt
            total_feedbacks += cnt

        fb_st_query = "SELECT status, COUNT(*) FROM diagnosis_feedbacks WHERE 1=1"
        if date_cutoff_sql:
            fb_st_query += f" AND created_at >= {date_cutoff_sql}"
        fb_st_query += " GROUP BY status"
        cursor.execute(fb_st_query)
        fb_by_status = {s: 0 for s in FEEDBACK_STATUSES}
        for st, cnt in cursor.fetchall():
            if st in fb_by_status:
                fb_by_status[st] = cnt

        resolved_cnt = fb_by_status.get("resolved", 0) + fb_by_status.get("dismissed", 0)
        feedback_resolution_rate = round((resolved_cnt / total_feedbacks) * 100, 1) if total_feedbacks > 0 else None

        return {
            "time_range": time_range,
            "pilot_requests": {
                "total": total_requests,
                "by_status": req_by_status,
                "by_customer_type": req_by_type
            },
            "pilot_organizations": {
                "total": pilot_orgs_count,
                "status_note": "Tổ chức đang trong không gian thử nghiệm (unpaid pilot)"
            },
            "active_users": {
                "count": active_users_count,
                "definition": "Người dùng có phiên đăng nhập hoặc thực hiện chẩn đoán trong khoảng thời gian"
            },
            "diagnoses": {
                "total": total_diagnoses
            },
            "leaf_gate_rejection": {
                "total_evaluations": total_evals,
                "rejected_count": rejected_cnt,
                "rejection_rate_percent": rejection_rate,
                "display_text": f"{rejection_rate}%" if rejection_rate is not None else "Chưa có dữ liệu"
            },
            "uncertainty_screening": {
                "total_diagnoses": uncertain_total,
                "needs_review_count": uncertain_cnt,
                "needs_review_rate_percent": uncertain_rate,
                "display_text": f"{uncertain_rate}%" if uncertain_rate is not None else "Chưa có dữ liệu"
            },
            "feedback_metrics": {
                "total": total_feedbacks,
                "by_type": fb_by_type,
                "by_status": fb_by_status,
                "resolution_rate_percent": feedback_resolution_rate,
                "display_resolution": f"{feedback_resolution_rate}%" if feedback_resolution_rate is not None else "Chưa có dữ liệu"
            },
            "data_policy": {
                "ground_truth_claim": False,
                "has_simulated_metrics": False,
                "disclaimer": "Mọi chỉ số đều được tính toán từ dữ liệu thực tế tại thời điểm truy vấn. Tuyệt đối không suy diễn độ chính xác AI từ phản hồi người dùng."
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# -------------------------------------------------------------
# Sprint 6: Cultivation Tasks Engine & User Risk Observations
# -------------------------------------------------------------

def list_cultivation_tasks(
    user_id: int,
    farm_id: Optional[int] = None,
    plot_id: Optional[int] = None,
    crop_id: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    org_id: Optional[int] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """List cultivation tasks scoped by user or organization with optional filters."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT t.*, f.name as farm_name, p.plot_name
            FROM cultivation_tasks t
            LEFT JOIN farms f ON t.farm_id = f.id
            LEFT JOIN farm_plots p ON t.plot_id = p.id
            WHERE 1=1
        """
        params: List[Any] = []
        if org_id is not None:
            query += " AND (t.organization_id = ? OR (t.user_id = ? AND t.organization_id IS NULL))"
            params.extend([org_id, user_id])
        else:
            query += " AND t.user_id = ?"
            params.append(user_id)

        if farm_id is not None:
            query += " AND t.farm_id = ?"
            params.append(farm_id)
        if plot_id is not None:
            query += " AND t.plot_id = ?"
            params.append(plot_id)
        if crop_id is not None:
            query += " AND LOWER(t.crop_id) = LOWER(?)"
            params.append(crop_id)
        if status is not None:
            query += " AND t.status = ?"
            params.append(status)
        if priority is not None:
            query += " AND t.priority = ?"
            params.append(priority)
        if date_from is not None:
            query += " AND t.due_date >= ?"
            params.append(date_from)
        if date_to is not None:
            query += " AND t.due_date <= ?"
            params.append(date_to)

        query += " ORDER BY t.due_date ASC, t.id DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def get_cultivation_task(task_id: int, user_id: Optional[int] = None, org_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Retrieve a single cultivation task with access check."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT t.*, f.name as farm_name, p.plot_name
            FROM cultivation_tasks t
            LEFT JOIN farms f ON t.farm_id = f.id
            LEFT JOIN farm_plots p ON t.plot_id = p.id
            WHERE t.id = ?
        """
        params: List[Any] = [task_id]
        if user_id is not None and org_id is not None:
            query += " AND (t.user_id = ? OR t.organization_id = ?)"
            params.extend([user_id, org_id])
        elif user_id is not None:
            query += " AND t.user_id = ?"
            params.append(user_id)

        cursor.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None


def create_cultivation_task(data: Dict[str, Any], user_id: int, org_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Create a new cultivation task with validation and defaults."""
    title = (data.get("title") or "").strip()
    if not title:
        return None
    due_date = data.get("due_date") or datetime.now().strftime("%Y-%m-%d")
    farm_id = data.get("farm_id")
    plot_id = data.get("plot_id")
    crop_id = data.get("crop_id") or "Tomato"
    if isinstance(crop_id, dict):
        crop_id = crop_id.get("id") or crop_id.get("name_vi") or crop_id.get("name") or "Tomato"
    else:
        crop_id = str(crop_id)
    priority = data.get("priority") or "medium"
    status = data.get("status") or "pending"
    task_type = data.get("task_type") or "routine"
    description = data.get("description") or ""
    notes = data.get("notes") or ""
    assignee_user_id = data.get("assignee_user_id") or user_id

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cultivation_tasks (
                user_id, organization_id, farm_id, plot_id, crop_id,
                title, description, due_date, priority, status, task_type,
                creator_user_id, assignee_user_id, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, org_id, farm_id, plot_id, crop_id,
            title, description, due_date, priority, status, task_type,
            user_id, assignee_user_id, notes
        ))
        conn.commit()
        task_id = cursor.lastrowid
        return get_cultivation_task(task_id)


def update_cultivation_task(task_id: int, data: Dict[str, Any], user_id: int, org_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Update an existing cultivation task."""
    task = get_cultivation_task(task_id, user_id=user_id, org_id=org_id)
    if not task:
        return None

    allowed_fields = [
        "title", "description", "due_date", "priority", "status",
        "task_type", "farm_id", "plot_id", "crop_id", "notes",
        "assignee_user_id"
    ]
    updates = []
    params = []
    for f in allowed_fields:
        if f in data:
            updates.append(f"{f} = ?")
            params.append(data[f])

    if "status" in data and data["status"] == "completed" and not task.get("completed_at"):
        updates.append("completed_at = CURRENT_TIMESTAMP")

    if not updates:
        return task

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([task_id, user_id])

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            UPDATE cultivation_tasks
            SET {', '.join(updates)}
            WHERE id = ? AND (user_id = ? OR organization_id IS NOT NULL)
        """, params)
        conn.commit()

    return get_cultivation_task(task_id)


def complete_cultivation_task(task_id: int, user_id: int, notes: Optional[str] = None, org_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Mark a cultivation task as completed with completion timestamp."""
    task = get_cultivation_task(task_id, user_id=user_id, org_id=org_id)
    if not task:
        return None

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        if notes:
            cursor.execute("""
                UPDATE cultivation_tasks
                SET status = 'completed', completed_at = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (now_iso, notes, task_id))
        else:
            cursor.execute("""
                UPDATE cultivation_tasks
                SET status = 'completed', completed_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (now_iso, task_id))
        conn.commit()

    return get_cultivation_task(task_id)


def delete_cultivation_task(task_id: int, user_id: int, org_id: Optional[int] = None) -> bool:
    """Delete a cultivation task with permission check."""
    task = get_cultivation_task(task_id, user_id=user_id, org_id=org_id)
    if not task:
        return False
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cultivation_tasks WHERE id = ?", (task_id,))
        conn.commit()
        return cursor.rowcount > 0


def acknowledge_risk_alert(alert_id: int, user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Record a user acknowledgment and field observation for a risk alert."""
    farm_id = data.get("farm_id")
    plot_id = data.get("plot_id")
    status = data.get("status") or "acknowledged"
    observation = data.get("user_observation") or ""
    severity = data.get("severity_observed") or ""

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_risk_acknowledgments (
                alert_id, user_id, farm_id, plot_id, status,
                user_observation, severity_observed
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (alert_id, user_id, farm_id, plot_id, status, observation, severity))
        conn.commit()
        ack_id = cursor.lastrowid
        cursor.execute("SELECT * FROM user_risk_acknowledgments WHERE id = ?", (ack_id,))
        return dict(cursor.fetchone())


def list_risk_acknowledgments(user_id: Optional[int] = None, alert_id: Optional[int] = None, farm_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """List user risk acknowledgments joined with regional alert metadata."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT a.*, r.region, r.crop, r.disease_threat, r.risk_level, f.name as farm_name
            FROM user_risk_acknowledgments a
            JOIN risk_alerts r ON a.alert_id = r.id
            LEFT JOIN farms f ON a.farm_id = f.id
            WHERE 1=1
        """
        params = []
        if user_id is not None:
            query += " AND a.user_id = ?"
            params.append(user_id)
        if alert_id is not None:
            query += " AND a.alert_id = ?"
            params.append(alert_id)
        if farm_id is not None:
            query += " AND a.farm_id = ?"
            params.append(farm_id)
        query += " ORDER BY a.acknowledged_at DESC LIMIT 50"
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def get_seasonal_cultivation_recommendations(crop_id: Optional[str] = None, region: str = "Hà Nội") -> List[Dict[str, Any]]:
    """Return seasonal agronomical recommendations based on current crop and regional microclimate."""
    all_recs = [
        {
            "crop_id": "Tomato",
            "crop_name": "Cà chua",
            "stage": "Phát triển thân lá & Ra hoa",
            "recommendation": "Độ ẩm không khí cao (>80%). Cần chủ động tỉa lá già sát gốc tạo độ thông thoáng, bón bổ sung Canxi-Bo để tăng đậu quả và hạn chế nứt trái do sương mù.",
            "priority": "high",
            "action_type": "care"
        },
        {
            "crop_id": "Potato",
            "crop_name": "Khoai tây",
            "stage": "Tạo củ & Nuôi củ",
            "recommendation": "Vun gốc cao 25-30cm ngăn ánh sáng làm xanh củ. Phun phòng trừ nấm mốc sương định kỳ 7-10 ngày một lần nếu độ ẩm buổi sáng duy trì trên 85%.",
            "priority": "medium",
            "action_type": "spraying"
        },
        {
            "crop_id": "Tea",
            "crop_name": "Cây chè",
            "stage": "Chăm sóc sau đốn & Búp đông",
            "recommendation": "Xới xáo đất phá váng bề mặt sau mưa, bón vôi bột khử chua đất vùng rễ (20-30kg/sào), dọn sạch tàn dư lá bệnh chấm xám.",
            "priority": "medium",
            "action_type": "fertilizing"
        },
        {
            "crop_id": "Corn",
            "crop_name": "Ngô (Bắp)",
            "stage": "Trỗ cờ & Phun râu",
            "recommendation": "Đảm bảo đủ ẩm vùng rễ trong giai đoạn thụ phấn. Thường xuyên kiểm tra bẹ lá phát hiện sớm sâu keo mùa thu.",
            "priority": "high",
            "action_type": "scouting"
        },
        {
            "crop_id": "Rice",
            "crop_name": "Lúa nước",
            "stage": "Làm đất & Gieo cấy Đông Xuân",
            "recommendation": "Cày ải sớm phơi đất tiêu diệt mầm bệnh đạo ôn vụ trước. Xử lý hạt giống bằng nước ấm 3 sôi 2 lạnh trước khi ngâm ủ.",
            "priority": "medium",
            "action_type": "routine"
        }
    ]
    if crop_id and crop_id != "all":
        return [r for r in all_recs if r["crop_id"].lower() == crop_id.lower()]
    return all_recs


# Auto-init database on import
init_database()


# -----------------------------------------------------------------------------
# GARI EXPERT NETWORK & NOTIFICATION REPOSITORY HELPERS
# -----------------------------------------------------------------------------

def create_expert_application(data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        primary_crops = data.get("primary_crops", [])
        if isinstance(primary_crops, list):
            primary_crops_json = json.dumps(primary_crops, ensure_ascii=False)
        else:
            primary_crops_json = str(primary_crops)

        regions = data.get("farming_regions", [])
        if isinstance(regions, list):
            regions_json = json.dumps(regions, ensure_ascii=False)
        else:
            regions_json = str(regions)

        cursor.execute("""
            INSERT INTO expert_applications (
                user_id, full_name, email, phone, institution, degree,
                specialization, primary_crops_json, farming_regions_json,
                bio, certificate_url, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'submitted')
        """, (
            user_id,
            (data.get("full_name") or "").strip(),
            (data.get("email") or "").strip(),
            (data.get("phone") or "").strip(),
            (data.get("institution") or "").strip(),
            (data.get("degree") or "").strip(),
            (data.get("specialization") or "").strip(),
            primary_crops_json,
            regions_json,
            (data.get("bio") or "").strip(),
            (data.get("certificate_url") or "").strip()
        ))
        conn.commit()
        app_id = cursor.lastrowid
        cursor.execute("SELECT * FROM expert_applications WHERE id = ?", (app_id,))
        return dict(cursor.fetchone())


def list_expert_applications(status: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        if status:
            if status in ('pending', 'submitted'):
                cursor.execute("SELECT * FROM expert_applications WHERE status IN ('pending', 'submitted') ORDER BY id DESC")
            else:
                cursor.execute("SELECT * FROM expert_applications WHERE status = ? ORDER BY id DESC", (status,))
        else:
            cursor.execute("SELECT * FROM expert_applications ORDER BY id DESC")
        rows = []
        for r in cursor.fetchall():
            d = dict(r)
            try:
                d["primary_crops"] = json.loads(d.get("primary_crops_json") or "[]")
            except Exception:
                d["primary_crops"] = []
            try:
                d["farming_regions"] = json.loads(d.get("farming_regions_json") or "[]")
            except Exception:
                d["farming_regions"] = []
            rows.append(d)
        return rows


def get_expert_application(app_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_applications WHERE id = ?", (app_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["primary_crops"] = json.loads(d.get("primary_crops_json") or "[]")
        except Exception:
            d["primary_crops"] = []
        try:
            d["farming_regions"] = json.loads(d.get("farming_regions_json") or "[]")
        except Exception:
            d["farming_regions"] = []
        return d


def review_expert_application(app_id: int, action: str, host_id: int, reason: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_applications WHERE id = ?", (app_id,))
        row = cursor.fetchone()
        if not row:
            return None
        app = dict(row)
        user_id = app["user_id"]

        if action == "approve":
            cursor.execute("""
                UPDATE expert_applications
                SET status = 'approved', reviewed_by_host_id = ?, reviewed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (host_id, app_id))

            # Grant user expert role and is_expert flag
            cursor.execute("""
                UPDATE users
                SET is_expert = 1, account_type = 'Chuyên gia', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (user_id,))

            # Create or update expert profile
            cursor.execute("""
                INSERT INTO expert_profiles (
                    user_id, full_name, display_title, institution, degree,
                    specialization, primary_crops_json, farming_regions_json,
                    bio, verification_status, verified_by_host_id, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved', ?, 1)
                ON CONFLICT(user_id) DO UPDATE SET
                    display_title = excluded.display_title,
                    institution = excluded.institution,
                    degree = excluded.degree,
                    specialization = excluded.specialization,
                    primary_crops_json = excluded.primary_crops_json,
                    farming_regions_json = excluded.farming_regions_json,
                    bio = excluded.bio,
                    verification_status = 'approved',
                    verified_by_host_id = excluded.verified_by_host_id,
                    is_active = 1,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                user_id,
                app["full_name"],
                f"Chuyên gia Nông học ({app['degree']})",
                app["institution"],
                app["degree"],
                app["specialization"],
                app["primary_crops_json"],
                app["farming_regions_json"],
                app["bio"],
                host_id
            ))

            # Notify user
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, notification_type, target_url)
                VALUES (?, 'Chúc mừng! Hồ sơ Chuyên gia đã được duyệt',
                        'Bạn đã được cấp quyền Chuyên gia Nông học chính thức trên GARI AI Lab. Hãy truy cập Expert Portal để tiếp nhận các ca chẩn đoán thực địa.',
                        'success', '/frontend2/expert-portal.html')
            """, (user_id,))

        elif action == "reject":
            cursor.execute("""
                UPDATE expert_applications
                SET status = 'rejected', rejection_reason = ?, reviewed_by_host_id = ?, reviewed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (reason or "Hồ sơ xác minh chưa đủ điều kiện theo quy định của ban quản trị.", host_id, app_id))

            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, notification_type, target_url)
                VALUES (?, 'Thông báo về hồ sơ đăng ký Chuyên gia',
                        ?, 'warning', '/frontend2/support.html')
            """, (user_id, f"Hồ sơ đăng ký chuyên gia của bạn chưa được phê duyệt. Lý do: {reason or 'Cần bổ sung thêm văn bằng chứng chỉ.'}"))

        conn.commit()
        return get_expert_application(app_id)


def list_expert_profiles(active_only: bool = True) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        if active_only:
            cursor.execute("SELECT ep.*, u.email, u.phone FROM expert_profiles ep JOIN users u ON ep.user_id = u.id WHERE ep.is_active = 1 ORDER BY ep.cases_resolved_count DESC")
        else:
            cursor.execute("SELECT ep.*, u.email, u.phone FROM expert_profiles ep JOIN users u ON ep.user_id = u.id ORDER BY ep.id DESC")
        rows = []
        for r in cursor.fetchall():
            d = dict(r)
            try:
                d["primary_crops"] = json.loads(d.get("primary_crops_json") or "[]")
            except Exception:
                d["primary_crops"] = []
            try:
                d["farming_regions"] = json.loads(d.get("farming_regions_json") or "[]")
            except Exception:
                d["farming_regions"] = []
            rows.append(d)
        return rows


def get_expert_profile(user_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ep.*, u.email, u.phone FROM expert_profiles ep JOIN users u ON ep.user_id = u.id WHERE ep.user_id = ?", (user_id,))
        r = cursor.fetchone()
        if not r:
            return None
        d = dict(r)
        try:
            d["primary_crops"] = json.loads(d.get("primary_crops_json") or "[]")
        except Exception:
            d["primary_crops"] = []
        try:
            d["farming_regions"] = json.loads(d.get("farming_regions_json") or "[]")
        except Exception:
            d["farming_regions"] = []
        return d


def list_expert_cases_for_expert(expert_user_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        # Returns cases assigned to this expert OR unassigned cases that need review
        if status:
            cursor.execute("""
                SELECT ec.*, u.full_name as farmer_account_name, u.email as farmer_email
                FROM expert_cases ec
                JOIN users u ON ec.user_id = u.id
                WHERE (ec.assigned_expert_id = ? OR ec.assigned_expert_id IS NULL)
                  AND ec.status = ?
                ORDER BY ec.id DESC
            """, (expert_user_id, status))
        else:
            cursor.execute("""
                SELECT ec.*, u.full_name as farmer_account_name, u.email as farmer_email
                FROM expert_cases ec
                JOIN users u ON ec.user_id = u.id
                WHERE ec.assigned_expert_id = ? OR ec.assigned_expert_id IS NULL
                ORDER BY ec.id DESC
            """, (expert_user_id,))
        return [dict(r) for r in cursor.fetchall()]


def get_expert_case(case_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_cases WHERE id = ?", (case_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def claim_expert_case(case_id: int, expert_user_id: int, expert_name: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_cases WHERE id = ?", (case_id,))
        row = cursor.fetchone()
        if not row:
            return None
        case = dict(row)
        if case.get("assigned_expert_id") and case.get("assigned_expert_id") != expert_user_id:
            return None # Already assigned to another expert

        cursor.execute("""
            UPDATE expert_cases
            SET assigned_expert_id = ?, assigned_expert = ?, status = 'under_review', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (expert_user_id, expert_name, case_id))

        cursor.execute("""
            INSERT INTO expert_case_messages (case_id, sender_user_id, sender_role, sender_name, message)
            VALUES (?, ?, 'system', 'Hệ thống GARI', ?)
        """, (case_id, expert_user_id, f"Chuyên gia {expert_name} đã tiếp nhận hồ sơ chẩn đoán này."))

        # Notify farmer
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, notification_type, target_url)
            VALUES (?, 'Chuyên gia đã tiếp nhận ca chẩn đoán',
                    ?, 'info', '/frontend2/support.html')
        """, (case["user_id"], f"Chuyên gia {expert_name} đã tiếp nhận ca bệnh {case.get('crop_name', 'cây trồng')} (#{case_id}) của bạn."))

        conn.commit()
        cursor.execute("SELECT * FROM expert_cases WHERE id = ?", (case_id,))
        return dict(cursor.fetchone())


def add_expert_case_message(case_id: int, sender_user_id: int, sender_role: str, sender_name: str, message: str, attachments: Optional[List[str]] = None, is_internal_note: bool = False) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        att_json = json.dumps(attachments, ensure_ascii=False) if attachments else None
        cursor.execute("""
            INSERT INTO expert_case_messages (case_id, sender_user_id, sender_role, sender_name, message, attachments_json, is_internal_note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (case_id, sender_user_id, sender_role, sender_name, message.strip(), att_json, 1 if is_internal_note else 0))
        msg_id = cursor.lastrowid

        # Update case status if expert replied
        cursor.execute("SELECT * FROM expert_cases WHERE id = ?", (case_id,))
        case = dict(cursor.fetchone())

        if sender_role == "expert":
            new_status = "answered"
            cursor.execute("UPDATE expert_cases SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, case_id))
            # Notify farmer
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, notification_type, target_url)
                VALUES (?, 'Chuyên gia nông học đã gửi tư vấn mới',
                        ?, 'success', '/frontend2/support.html')
            """, (case["user_id"], f"Chuyên gia {sender_name} đã phản hồi cho ca bệnh #{case_id} ({case.get('crop_name', 'Cây trồng')})."))
        elif sender_role == "farmer":
            new_status = "under_review"
            cursor.execute("UPDATE expert_cases SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, case_id))
            if case.get("assigned_expert_id"):
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, notification_type, target_url)
                    VALUES (?, 'Nông dân đã gửi tin nhắn bổ sung',
                            ?, 'info', '/frontend2/expert-portal.html')
                """, (case["assigned_expert_id"], f"Nông dân {sender_name} đã gửi câu hỏi bổ sung cho hồ sơ #{case_id}."))

        conn.commit()
        cursor.execute("SELECT * FROM expert_case_messages WHERE id = ?", (msg_id,))
        return dict(cursor.fetchone())


def get_expert_case_messages(case_id: int, include_internal: bool = False) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        if include_internal:
            cursor.execute("SELECT * FROM expert_case_messages WHERE case_id = ? ORDER BY id ASC", (case_id,))
        else:
            cursor.execute("SELECT * FROM expert_case_messages WHERE case_id = ? AND is_internal_note = 0 ORDER BY id ASC", (case_id,))
        rows = []
        for r in cursor.fetchall():
            d = dict(r)
            try:
                d["attachments"] = json.loads(d.get("attachments_json") or "[]")
            except Exception:
                d["attachments"] = []
            rows.append(d)
        return rows


def resolve_expert_case(case_id: int, expert_user_id: int, resolution_notes: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_cases WHERE id = ?", (case_id,))
        row = cursor.fetchone()
        if not row:
            return None
        case = dict(row)

        cursor.execute("""
            UPDATE expert_cases
            SET status = 'resolved', resolution_notes = ?, resolved_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (resolution_notes.strip(), case_id))

        cursor.execute("""
            UPDATE expert_profiles
            SET cases_resolved_count = cases_resolved_count + 1, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (expert_user_id,))

        cursor.execute("""
            INSERT INTO expert_case_messages (case_id, sender_user_id, sender_role, sender_name, message)
            VALUES (?, ?, 'system', 'Hệ thống GARI', ?)
        """, (case_id, expert_user_id, f"Ca bệnh đã được Chuyên gia đánh dấu giải quyết hoàn tất: {resolution_notes}"))

        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, notification_type, target_url)
            VALUES (?, 'Hồ sơ tư vấn chuyên gia đã hoàn tất',
                    ?, 'success', '/frontend2/support.html')
        """, (case["user_id"], f"Hồ sơ #{case_id} đã được chuyên gia kết luận giải quyết."))

        conn.commit()
        cursor.execute("SELECT * FROM expert_cases WHERE id = ?", (case_id,))
        return dict(cursor.fetchone())


def create_notification(user_id: int, title: str, message: str, notification_type: str = 'info', target_url: Optional[str] = None) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, notification_type, target_url)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, title.strip(), message.strip(), notification_type, target_url))
        conn.commit()
        nid = cursor.lastrowid
        cursor.execute("SELECT * FROM notifications WHERE id = ?", (nid,))
        return dict(cursor.fetchone())


def list_user_notifications(user_id: int, limit: int = 30) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
        return [dict(r) for r in cursor.fetchall()]


def mark_notification_read(notif_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (notif_id, user_id))
        conn.commit()
        return cursor.rowcount > 0


def mark_all_notifications_read(user_id: int) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0", (user_id,))
        conn.commit()
        return cursor.rowcount
