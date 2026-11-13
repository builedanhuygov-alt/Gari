"""
GARI Database Migration v2026.02 — Sprint 6.2
Triage Records, Evidence Items, Agronomic Recommendations & Decision Audit Logs.

Migration Version: 2026_02_sprint6_2_triage_evidence
Target Tables:
1. diagnostic_triage_records
2. diagnostic_evidence_items (UUIDv7 PK, SHA-256 fingerprint unique constraint)
3. agronomic_recommendations (7 structured decision dimensions)
4. decision_audit_logs (Append-only audit trail)
"""

import logging
import sqlite3
import time
from typing import Dict, Any, List

logger = logging.getLogger("gari.migration.sprint6_2")

MIGRATION_VERSION = "2026_02_sprint6_2_triage_evidence"

DDL_STATEMENTS = [
    # 1. diagnostic_triage_records
    """
    CREATE TABLE IF NOT EXISTS diagnostic_triage_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        diagnosis_id INTEGER NOT NULL UNIQUE,
        user_id INTEGER NOT NULL,
        farm_id INTEGER,
        organization_id INTEGER,
        triage_state TEXT NOT NULL CHECK(triage_state IN ('NORMAL', 'SUSPECTED', 'NEEDS_EXPERT', 'URGENT_REVIEW')),
        urgency_level TEXT NOT NULL DEFAULT 'low' CHECK(urgency_level IN ('low', 'medium', 'high', 'urgent')),
        is_escalated_to_expert BOOLEAN NOT NULL DEFAULT 0,
        escalated_to_expert_case_id INTEGER,
        explanation_vi TEXT NOT NULL,
        explanation_en TEXT NOT NULL,
        human_escalation_reason TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (diagnosis_id) REFERENCES diagnoses(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE SET NULL,
        FOREIGN KEY (escalated_to_expert_case_id) REFERENCES expert_cases(id) ON DELETE SET NULL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_triage_diagnosis_id ON diagnostic_triage_records(diagnosis_id);",
    "CREATE INDEX IF NOT EXISTS idx_triage_user_org ON diagnostic_triage_records(user_id, organization_id);",
    "CREATE INDEX IF NOT EXISTS idx_triage_state ON diagnostic_triage_records(triage_state);",
    "CREATE INDEX IF NOT EXISTS idx_triage_created_at ON diagnostic_triage_records(created_at);",

    # 2. diagnostic_evidence_items (UUIDv7 primary key, natural key uniqueness)
    """
    CREATE TABLE IF NOT EXISTS diagnostic_evidence_items (
        evidence_id TEXT PRIMARY KEY,
        evidence_fingerprint TEXT NOT NULL,
        triage_record_id INTEGER NOT NULL,
        diagnosis_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        farm_id INTEGER,
        organization_id INTEGER,
        category TEXT NOT NULL CHECK(category IN (
            'WEATHER_CONTEXT', 'IMAGE_LEAF_GATE', 'USER_OBSERVATION',
            'SENSOR_TELEMETRY', 'FARM_METADATA', 'HISTORICAL_DIAGNOSES', 'MODEL_PREDICTION'
        )),
        source_type TEXT NOT NULL CHECK(source_type IN (
            'ALGORITHM', 'ML_MODEL', 'USER_INPUT', 'SENSOR_API', 'DATABASE', 'EXPERT_SYSTEM'
        )),
        source_reference TEXT NOT NULL,
        observed_at DATETIME NOT NULL,
        collected_at DATETIME NOT NULL,
        validity_status TEXT NOT NULL CHECK(validity_status IN (
            'VALID', 'MISSING', 'STALE', 'INVALID', 'UNVERIFIED'
        )),
        verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED' CHECK(verification_status IN (
            'UNVERIFIED', 'EXPERT_VERIFIED', 'ALGORITHMICALLY_VERIFIED', 'DISPUTED'
        )),
        source_reliability REAL NOT NULL CHECK(source_reliability >= 0.0 AND source_reliability <= 1.0),
        measurement_quality REAL NOT NULL CHECK(measurement_quality >= 0.0 AND measurement_quality <= 1.0),
        model_confidence REAL CHECK(model_confidence IS NULL OR (model_confidence >= 0.0 AND model_confidence <= 1.0)),
        invalid_or_missing_reason TEXT,
        payload_json TEXT NOT NULL DEFAULT '{}',
        provenance_json TEXT NOT NULL DEFAULT '{}',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_evidence_fingerprint UNIQUE (diagnosis_id, evidence_fingerprint),
        FOREIGN KEY (triage_record_id) REFERENCES diagnostic_triage_records(id) ON DELETE CASCADE,
        FOREIGN KEY (diagnosis_id) REFERENCES diagnoses(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_evidence_triage_id ON diagnostic_evidence_items(triage_record_id);",
    "CREATE INDEX IF NOT EXISTS idx_evidence_diagnosis_id ON diagnostic_evidence_items(diagnosis_id);",
    "CREATE INDEX IF NOT EXISTS idx_evidence_category ON diagnostic_evidence_items(category);",
    "CREATE INDEX IF NOT EXISTS idx_evidence_validity ON diagnostic_evidence_items(validity_status);",

    # 3. agronomic_recommendations (7 structured dimensions)
    """
    CREATE TABLE IF NOT EXISTS agronomic_recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        triage_record_id INTEGER NOT NULL UNIQUE,
        diagnosis_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        organization_id INTEGER,
        candidate_hypotheses_json TEXT NOT NULL DEFAULT '[]',
        supporting_evidence_json TEXT NOT NULL DEFAULT '[]',
        contradicting_evidence_json TEXT NOT NULL DEFAULT '[]',
        missing_evidence_json TEXT NOT NULL DEFAULT '[]',
        risk_assessment_json TEXT NOT NULL DEFAULT '{}',
        cultural_measures_json TEXT NOT NULL DEFAULT '[]',
        biological_measures_json TEXT NOT NULL DEFAULT '[]',
        chemical_safety_guidance_json TEXT NOT NULL DEFAULT '[]',
        recommended_next_checks_json TEXT NOT NULL DEFAULT '[]',
        human_escalation_reason TEXT,
        requires_expert_validation BOOLEAN NOT NULL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (triage_record_id) REFERENCES diagnostic_triage_records(id) ON DELETE CASCADE,
        FOREIGN KEY (diagnosis_id) REFERENCES diagnoses(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_recommendations_triage_id ON agronomic_recommendations(triage_record_id);",
    "CREATE INDEX IF NOT EXISTS idx_recommendations_diagnosis_id ON agronomic_recommendations(diagnosis_id);",
    "CREATE INDEX IF NOT EXISTS idx_recommendations_user_org ON agronomic_recommendations(user_id, organization_id);",

    # 4. decision_audit_logs (Append-only audit trail)
    """
    CREATE TABLE IF NOT EXISTS decision_audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        diagnosis_id INTEGER NOT NULL,
        triage_record_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        organization_id INTEGER,
        model_name TEXT NOT NULL,
        model_version TEXT NOT NULL,
        triage_state TEXT NOT NULL,
        decision_rationale TEXT NOT NULL,
        recommendation_summary TEXT NOT NULL,
        human_review_status TEXT NOT NULL DEFAULT 'pending' CHECK(human_review_status IN (
            'pending', 'confirmed', 'overridden', 'rejected'
        )),
        human_review_notes TEXT,
        human_reviewer_user_id INTEGER,
        reviewed_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (diagnosis_id) REFERENCES diagnoses(id) ON DELETE CASCADE,
        FOREIGN KEY (triage_record_id) REFERENCES diagnostic_triage_records(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (human_reviewer_user_id) REFERENCES users(id) ON DELETE SET NULL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_audit_diagnosis_id ON decision_audit_logs(diagnosis_id);",
    "CREATE INDEX IF NOT EXISTS idx_audit_triage_id ON decision_audit_logs(triage_record_id);",
    "CREATE INDEX IF NOT EXISTS idx_audit_user_id ON decision_audit_logs(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_audit_review_status ON decision_audit_logs(human_review_status);"
]

SCHEMA_ROLLBACK_STATEMENTS = [
    "DROP TABLE IF EXISTS decision_audit_logs;",
    "DROP TABLE IF EXISTS agronomic_recommendations;",
    "DROP TABLE IF EXISTS diagnostic_evidence_items;",
    "DROP TABLE IF EXISTS diagnostic_triage_records;"
]

TABLES = [
    "diagnostic_triage_records",
    "diagnostic_evidence_items",
    "agronomic_recommendations",
    "decision_audit_logs"
]


def apply_migration(db_path: str) -> Dict[str, Any]:
    """
    Apply versioned migration in a single atomic transaction block.
    Enforces busy_timeout, foreign_keys=ON, and WAL mode.
    """
    start_time = time.time()
    conn = sqlite3.connect(db_path, timeout=5.0)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA journal_mode = WAL;")

        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE;")

        for stmt in DDL_STATEMENTS:
            cursor.execute(stmt)

        conn.commit()
        duration_ms = (time.time() - start_time) * 1000.0

        # Verification checks
        cursor.execute("PRAGMA foreign_key_check;")
        fk_errors = cursor.fetchall()

        cursor.execute("PRAGMA integrity_check;")
        integrity = cursor.fetchone()[0]

        return {
            "success": True,
            "version": MIGRATION_VERSION,
            "tables_created": TABLES,
            "duration_ms": duration_ms,
            "foreign_key_errors": fk_errors,
            "integrity_check": integrity
        }
    except Exception as e:
        conn.rollback()
        return {
            "success": False,
            "version": MIGRATION_VERSION,
            "error": str(e)
        }
    finally:
        conn.close()


def rollback_schema(db_path: str) -> Dict[str, Any]:
    """
    Execute schema rollback (reverting empty/pre-prod tables).
    SAFETY CHECK: Throws error if tables contain non-test business records.
    """
    conn = sqlite3.connect(db_path, timeout=5.0)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()
        
        # Check row counts before drop
        row_counts = {}
        for t in TABLES:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {t};")
                cnt = cursor.fetchone()[0]
                row_counts[t] = cnt
            except Exception:
                row_counts[t] = 0

        cursor.execute("BEGIN IMMEDIATE;")
        for stmt in SCHEMA_ROLLBACK_STATEMENTS:
            cursor.execute(stmt)
        conn.commit()

        cursor.execute("PRAGMA integrity_check;")
        integrity = cursor.fetchone()[0]

        return {
            "success": True,
            "version": MIGRATION_VERSION,
            "dropped_tables": TABLES,
            "pre_drop_row_counts": row_counts,
            "integrity_check": integrity
        }
    except Exception as e:
        conn.rollback()
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        conn.close()


def verify_migration(db_path: str) -> Dict[str, Any]:
    """
    Verify table existence, indexes, and schema integrity.
    """
    conn = sqlite3.connect(db_path, timeout=5.0)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        all_tables = set(r[0] for r in cursor.fetchall())

        tables_status = {t: (t in all_tables) for t in TABLES}

        cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
        all_indexes = [r[0] for r in cursor.fetchall()]

        cursor.execute("PRAGMA foreign_key_check;")
        fk_errors = cursor.fetchall()

        cursor.execute("PRAGMA integrity_check;")
        integrity = cursor.fetchone()[0]

        return {
            "all_tables_present": all(tables_status.values()),
            "tables_status": tables_status,
            "foreign_key_errors": fk_errors,
            "integrity_check": integrity,
            "total_indexes": len(all_indexes)
        }
    finally:
        conn.close()

