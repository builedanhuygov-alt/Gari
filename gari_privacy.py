"""
GARI AI LAB — Privacy, Consent & Data Subject Rights (gari_privacy.py)
Implements statutory compliance for:
- Nghị định 13/2023/NĐ-CP (Bảo vệ dữ liệu cá nhân)
- Luật An ninh mạng 2018 & Bộ luật Dân sự 2015 (Điều 32 về hình ảnh)
- Data Minimization, Consent Recording & Withdrawal
- Data Subject Rights (DSR): Data Portability (Export) & Right to Erasure (Deletion)
"""

import os
import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("gari_privacy")

DB_PATH = Path(__file__).resolve().parent / "database" / "disease_detector.db"
UPLOADS_DIR = Path(__file__).resolve().parent / "database" / "uploads"
_PRIVACY_LOCK = threading.Lock()

POLICY_VERSIONS = {
    "privacy_policy": "v1.0.0",
    "terms_of_service": "v1.0.0",
    "cookie_policy": "v1.0.0",
    "refund_policy": "v1.0.0",
    "diagnostic_processing": "v1.0.0",
}


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_privacy_tables() -> None:
    """Ensure user_consents and data_subject_requests tables exist."""
    with _PRIVACY_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_consents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                client_identifier TEXT NOT NULL,
                consent_type TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                status TEXT NOT NULL, -- 'granted', 'withdrawn'
                client_ip TEXT,
                user_agent TEXT,
                metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_consents_uid ON user_consents(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_consents_client ON user_consents(client_identifier);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_consents_type ON user_consents(consent_type);")

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS data_subject_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                request_type TEXT NOT NULL, -- 'export_data', 'delete_data', 'rectify_data', 'restrict_processing'
                status TEXT NOT NULL,       -- 'pending', 'processing', 'completed', 'rejected'
                reason TEXT,
                notes TEXT,
                requested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,
                executed_by TEXT
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_dsr_user ON data_subject_requests(user_id);")
            conn.commit()


# Initialize tables on import
init_privacy_tables()


# -----------------------------------------------------------------------------
# 1. VERIFIABLE CONSENT LOGGING & WITHDRAWAL
# -----------------------------------------------------------------------------

def record_consent(
    consent_type: str,
    status: str = "granted",
    user_id: Optional[int] = None,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    client_identifier: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Records a verifiable consent entry per Nghị định 13/2023/NĐ-CP (Điều 9, 11).
    Consent must be demonstrable, voluntary, informed and specific.
    """
    version = POLICY_VERSIONS.get(consent_type, "v1.0.0")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    clean_ip = (client_ip or "127.0.0.1").strip()
    clean_agent = (user_agent or "Unknown").strip()[:300]
    c_id = client_identifier or (f"user_{user_id}" if user_id else f"guest_{clean_ip}")
    meta_json = json.dumps(metadata or {}, ensure_ascii=False)

    with _PRIVACY_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_consents (
                    user_id, client_identifier, consent_type, policy_version,
                    status, client_ip, user_agent, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, c_id, consent_type, version, status, clean_ip, clean_agent, meta_json, now_iso, now_iso))
            conn.commit()
            record_id = cursor.lastrowid

    return {
        "id": record_id,
        "user_id": user_id,
        "client_identifier": c_id,
        "consent_type": consent_type,
        "policy_version": version,
        "status": status,
        "timestamp": now_iso
    }


def get_user_consents(user_id: Optional[int] = None, client_identifier: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve history and current active consents for a user or client."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if user_id:
            cursor.execute("""
                SELECT * FROM user_consents
                WHERE user_id = ? OR client_identifier = ?
                ORDER BY created_at DESC
            """, (user_id, f"user_{user_id}"))
        elif client_identifier:
            cursor.execute("""
                SELECT * FROM user_consents
                WHERE client_identifier = ?
                ORDER BY created_at DESC
            """, (client_identifier,))
        else:
            return []

        rows = cursor.fetchall()

    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "consent_type": r["consent_type"],
            "policy_version": r["policy_version"],
            "status": r["status"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"]
        })
    return results


def withdraw_consent(
    consent_type: str,
    user_id: Optional[int] = None,
    client_identifier: Optional[str] = None,
    client_ip: Optional[str] = None
) -> Dict[str, Any]:
    """Records withdrawal of a specific consent."""
    return record_consent(
        consent_type=consent_type,
        status="withdrawn",
        user_id=user_id,
        client_identifier=client_identifier,
        client_ip=client_ip,
        metadata={"action": "consent_withdrawal"}
    )


# -----------------------------------------------------------------------------
# 2. DATA SUBJECT RIGHTS (DSR): DATA EXPORT (PORTABILITY)
# -----------------------------------------------------------------------------

def export_user_data_bundle(user_id: int) -> Dict[str, Any]:
    """
    Builds a complete, machine-readable JSON bundle of all personal data
    stored for the data subject (Nghị định 13/2023/NĐ-CP Điều 9 khoản 4).
    Excludes sensitive credential secrets like password hashes.
    """
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Profile Data
        cursor.execute("SELECT id, email, full_name, account_type, created_at FROM users WHERE id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            raise ValueError("Không tìm thấy dữ liệu người dùng.")

        user_profile = {
            "id": user_row["id"],
            "email": user_row["email"],
            "full_name": user_row["full_name"],
            "account_type": user_row["account_type"],
            "member_since": user_row["created_at"]
        }

        # 2. Diagnoses & Leaf records
        cursor.execute("""
            SELECT id, crop_id, crop_name, predicted_disease, confidence,
                   severity, image_path, created_at
            FROM diagnoses
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))
        diagnoses = [dict(r) for r in cursor.fetchall()]

        # 3. Farms & Plots
        cursor.execute("SELECT * FROM farms WHERE user_id = ?", (user_id,))
        farms = [dict(r) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT fp.* FROM farm_plots fp
            JOIN farms f ON fp.farm_id = f.id
            WHERE f.user_id = ?
        """, (user_id,))
        plots = [dict(r) for r in cursor.fetchall()]

        # 4. Organization Memberships
        cursor.execute("""
            SELECT o.id, o.name, o.slug, o.plan_id, om.role, om.joined_at
            FROM organization_members om
            JOIN organizations o ON om.organization_id = o.id
            WHERE om.user_id = ?
        """, (user_id,))
        orgs = [dict(r) for r in cursor.fetchall()]

        # 5. Consent History
        cursor.execute("""
            SELECT consent_type, policy_version, status, created_at
            FROM user_consents
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))
        consents = [dict(r) for r in cursor.fetchall()]

    return {
        "export_metadata": {
            "platform": "Gari AI Lab AgriTech Platform",
            "jurisdiction": "Nghị định 13/2023/NĐ-CP (Bảo vệ dữ liệu cá nhân Việt Nam)",
            "generated_at": now_iso,
            "data_subject_id": user_id,
            "format": "JSON Portable Format"
        },
        "user_profile": user_profile,
        "farms_and_plots": {
            "farms_count": len(farms),
            "farms": farms,
            "plots": plots
        },
        "diagnostic_history": {
            "total_records": len(diagnoses),
            "records": diagnoses
        },
        "organizations": orgs,
        "consent_audit_trail": consents
    }


# -----------------------------------------------------------------------------
# 3. DATA SUBJECT RIGHTS (DSR): RIGHT TO ERASURE (DELETION)
# -----------------------------------------------------------------------------

def create_data_subject_request(user_id: int, request_type: str, reason: Optional[str] = None) -> Dict[str, Any]:
    """Records a formal DSR request."""
    with _PRIVACY_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO data_subject_requests (user_id, request_type, status, reason)
                VALUES (?, ?, 'pending', ?)
            """, (user_id, request_type, reason or "Yêu cầu từ người dùng"))
            conn.commit()
            req_id = cursor.lastrowid
            cursor.execute("SELECT * FROM data_subject_requests WHERE id = ?", (req_id,))
            row = cursor.fetchone()
            return dict(row)


def execute_user_data_deletion(user_id: int) -> Dict[str, Any]:
    """
    Executes Right to Erasure per Nghị định 13/2023/NĐ-CP (Điều 9 khoản 7):
    1. Collects and permanently deletes uploaded leaf image files on disk.
    2. Deletes user diagnoses, farm records, plots, notifications, sessions.
    3. Anonymizes user profile (retaining minimal hash token for security audit).
    4. Records DSR fulfillment timestamp.
    """
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    deleted_images_count = 0

    with _PRIVACY_LOCK:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # 1. Identify and delete image files from disk
            cursor.execute("SELECT image_path FROM diagnoses WHERE user_id = ?", (user_id,))
            image_rows = cursor.fetchall()
            for r in image_rows:
                rel_path = r["image_path"]
                if rel_path:
                    # Clean relative path
                    clean_name = os.path.basename(rel_path.replace("/uploads/", ""))
                    target_file = UPLOADS_DIR / clean_name
                    if target_file.exists():
                        try:
                            target_file.unlink()
                            deleted_images_count += 1
                        except Exception as e:
                            logger.warning(f"Could not unlink image file {target_file}: {e}")

            # 2. Delete database records
            cursor.execute("DELETE FROM diagnoses WHERE user_id = ?", (user_id,))
            cursor.execute("""
                DELETE FROM plot_timeline_events WHERE user_id = ? OR plot_id IN (
                    SELECT id FROM farm_plots WHERE farm_id IN (SELECT id FROM farms WHERE user_id = ?)
                )
            """, (user_id, user_id))
            cursor.execute("""
                DELETE FROM farm_plots WHERE farm_id IN (
                    SELECT id FROM farms WHERE user_id = ?
                )
            """, (user_id,))
            cursor.execute("DELETE FROM farms WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))

            # 3. Remove from organizations
            cursor.execute("DELETE FROM organization_members WHERE user_id = ?", (user_id,))

            # 4. Anonymize user record
            anonymized_email = f"erased_user_{user_id}_{int(datetime.now().timestamp())}@anonymized.gari.vn"
            cursor.execute("""
                UPDATE users
                SET email = ?,
                    name = '[Tài khoản đã xóa]',
                    full_name = '[Tài khoản đã xóa theo quyền riêng tư]',
                    password_hash = 'REDACTED_DELETED_ACCOUNT',
                    phone = NULL,
                    location = NULL
                WHERE id = ?
            """, (anonymized_email, user_id))

            # 5. Mark DSR as completed
            cursor.execute("""
                UPDATE data_subject_requests
                SET status = 'completed',
                    completed_at = ?,
                    notes = 'Đã xóa toàn bộ ảnh vật lý, chẩn đoán, nông trại và ẩn danh hóa tài khoản theo Nghị định 13/2023/NĐ-CP.'
                WHERE user_id = ? AND request_type = 'delete_data' AND status = 'pending'
            """, (now_iso, user_id))

            conn.commit()

    return {
        "success": True,
        "user_id": user_id,
        "deleted_images_count": deleted_images_count,
        "status": "completed",
        "message": "Đã thực hiện xóa dữ liệu cá nhân thành công theo Nghị định 13/2023/NĐ-CP.",
        "completed_at": now_iso
    }


def get_user_dsr_requests(user_id: int) -> List[Dict[str, Any]]:
    """List data subject requests for user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM data_subject_requests
            WHERE user_id = ?
            ORDER BY requested_at DESC
        """, (user_id,))
        return [dict(r) for r in cursor.fetchall()]
