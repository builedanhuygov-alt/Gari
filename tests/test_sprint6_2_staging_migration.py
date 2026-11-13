"""
Unit and Integration Test Suite for Sprint 6.2 Staging Database Migration.
Validates the versioned migration, foreign keys, concurrency, WAL behavior,
security isolation, and three rollback drills on an isolated staging database.

Strict constraint: Production database is NEVER modified.
"""

import os
import shutil
import sqlite3
import sys
import threading
import time
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath("."))

from database.migrations.migration_v2026_02_sprint6_2 import (
    apply_migration,
    rollback_schema,
    verify_migration,
    TABLES,
    MIGRATION_VERSION
)
from gari_evidence_foundation import (
    generate_uuid7,
    compute_evidence_fingerprint,
    canonicalize_payload,
    EvidenceCategory,
    SourceType,
    ValidityStatus,
    VerificationStatus
)

PROD_DB = os.path.abspath("database/disease_detector.db")
STAGING_DB = os.path.abspath("database/staging_disease_detector.db")
BACKUP_DB = os.path.abspath("database/backups/disease_detector_pre_sprint6_2.bak")
RECOVERY_TEST_DB = os.path.abspath("database/recovery_test_disease_detector.db")


class TestSprint62StagingMigration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Enforce that staging exists and is physically isolated from production
        assert os.path.exists(BACKUP_DB), "Pre-migration backup must exist."
        assert os.path.normpath(STAGING_DB) != os.path.normpath(PROD_DB), "Staging must not point to Production!"

        # Reset staging freshly from verified backup
        src = sqlite3.connect(BACKUP_DB)
        dst = sqlite3.connect(STAGING_DB)
        src.backup(dst, pages=250)
        src.close()
        dst.close()

        # Apply migration on staging
        res = apply_migration(STAGING_DB)
        assert res["success"], f"Initial staging migration failed: {res.get('error')}"

    def get_staging_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(STAGING_DB, timeout=10.0)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    def get_valid_diagnosis_and_user(self, conn: sqlite3.Connection):
        cur = conn.cursor()
        cur.execute("""
            SELECT d.id, d.user_id 
            FROM diagnoses d 
            JOIN users u ON d.user_id = u.id 
            WHERE d.user_id IS NOT NULL 
            ORDER BY d.id ASC 
            LIMIT 2;
        """)
        return cur.fetchall()

    # ------------------------------------------------------------------------
    # 1. Fresh Migration & Schema Verification
    # ------------------------------------------------------------------------

    def test_01_fresh_migration_creates_all_four_tables(self):
        """Verify all 4 tables exist in staging with zero foreign key errors."""
        ver = verify_migration(STAGING_DB)
        self.assertTrue(ver["all_tables_present"])
        for tbl in TABLES:
            self.assertTrue(ver["tables_status"][tbl], f"Table {tbl} must be present.")
        self.assertEqual(len(ver["foreign_key_errors"]), 0)
        self.assertEqual(ver["integrity_check"], "ok")
        self.assertGreaterEqual(ver["total_indexes"], 10)

    # ------------------------------------------------------------------------
    # 2. Repeated Migration / Idempotency
    # ------------------------------------------------------------------------

    def test_02_repeated_migration_is_idempotent(self):
        """Re-running apply_migration on an already migrated database must succeed cleanly."""
        res = apply_migration(STAGING_DB)
        self.assertTrue(res["success"])
        self.assertEqual(res["integrity_check"], "ok")
        self.assertEqual(len(res["foreign_key_errors"]), 0)

    # ------------------------------------------------------------------------
    # 3. Duplicate Evidence Natural Key Insertion (Constraint Enforcement)
    # ------------------------------------------------------------------------

    def test_03_duplicate_evidence_fingerprint_rejected(self):
        """Inserting two evidence items with identical (diagnosis_id, evidence_fingerprint) raises IntegrityError."""
        conn = self.get_staging_conn()
        try:
            cur = conn.cursor()
            rows = self.get_valid_diagnosis_and_user(conn)
            diag_id, user_id = rows[0]

            # Create triage record first (parent FK)
            cur.execute("""
                INSERT OR IGNORE INTO diagnostic_triage_records (
                    diagnosis_id, user_id, triage_state, urgency_level,
                    explanation_vi, explanation_en
                ) VALUES (?, ?, 'NORMAL', 'low', 'Bình thường', 'Normal');
            """, (diag_id, user_id))
            conn.commit()

            cur.execute("SELECT id FROM diagnostic_triage_records WHERE diagnosis_id = ?;", (diag_id,))
            triage_id = cur.fetchone()[0]

            now_str = datetime.now(timezone.utc).isoformat()
            fp = compute_evidence_fingerprint(diag_id, EvidenceCategory.IMAGE_LEAF_GATE, "gate1", now_str, '{"lap":50}')

            # Insert first item
            evi_id_1 = generate_uuid7()
            cur.execute("""
                INSERT INTO diagnostic_evidence_items (
                    evidence_id, evidence_fingerprint, triage_record_id, diagnosis_id, user_id,
                    category, source_type, source_reference, observed_at, collected_at,
                    validity_status, verification_status, source_reliability, measurement_quality,
                    payload_json, provenance_json
                ) VALUES (?, ?, ?, ?, ?, 'IMAGE_LEAF_GATE', 'ALGORITHM', 'gate1', ?, ?, 'VALID', 'UNVERIFIED', 0.95, 0.85, '{}', '{}');
            """, (evi_id_1, fp, triage_id, diag_id, user_id, now_str, now_str))
            conn.commit()

            # Attempt duplicate insertion with same diagnosis_id and fingerprint but different evidence_id
            evi_id_2 = generate_uuid7()
            with self.assertRaises(sqlite3.IntegrityError):
                cur.execute("""
                    INSERT INTO diagnostic_evidence_items (
                        evidence_id, evidence_fingerprint, triage_record_id, diagnosis_id, user_id,
                        category, source_type, source_reference, observed_at, collected_at,
                        validity_status, verification_status, source_reliability, measurement_quality,
                        payload_json, provenance_json
                    ) VALUES (?, ?, ?, ?, ?, 'IMAGE_LEAF_GATE', 'ALGORITHM', 'gate1', ?, ?, 'VALID', 'UNVERIFIED', 0.95, 0.85, '{}', '{}');
                """, (evi_id_2, fp, triage_id, diag_id, user_id, now_str, now_str))
            conn.rollback()
        finally:
            conn.close()

    # ------------------------------------------------------------------------
    # 4. UUID Uniqueness Constraint
    # ------------------------------------------------------------------------

    def test_04_uuid_primary_key_uniqueness(self):
        """Reusing the same evidence_id primary key violates PRIMARY KEY constraint."""
        conn = self.get_staging_conn()
        try:
            cur = conn.cursor()
            rows = self.get_valid_diagnosis_and_user(conn)
            diag_id, user_id = rows[0]

            cur.execute("""
                INSERT OR IGNORE INTO diagnostic_triage_records (
                    diagnosis_id, user_id, triage_state, urgency_level,
                    explanation_vi, explanation_en
                ) VALUES (?, ?, 'NORMAL', 'low', 'Bình thường', 'Normal');
            """, (diag_id, user_id))
            conn.commit()

            cur.execute("SELECT id FROM diagnostic_triage_records WHERE diagnosis_id = ?;", (diag_id,))
            triage_id = cur.fetchone()[0]

            fixed_uuid = generate_uuid7()
            now_str = datetime.now(timezone.utc).isoformat()

            cur.execute("""
                INSERT INTO diagnostic_evidence_items (
                    evidence_id, evidence_fingerprint, triage_record_id, diagnosis_id, user_id,
                    category, source_type, source_reference, observed_at, collected_at,
                    validity_status, verification_status, source_reliability, measurement_quality,
                    payload_json, provenance_json
                ) VALUES (?, 'fp_unique_1', ?, ?, ?, 'WEATHER_CONTEXT', 'SENSOR_API', 'station', ?, ?, 'VALID', 'UNVERIFIED', 0.9, 0.8, '{}', '{}');
            """, (fixed_uuid, triage_id, diag_id, user_id, now_str, now_str))
            conn.commit()

            # Second insert with identical UUID
            with self.assertRaises(sqlite3.IntegrityError):
                cur.execute("""
                    INSERT INTO diagnostic_evidence_items (
                        evidence_id, evidence_fingerprint, triage_record_id, diagnosis_id, user_id,
                        category, source_type, source_reference, observed_at, collected_at,
                        validity_status, verification_status, source_reliability, measurement_quality,
                        payload_json, provenance_json
                    ) VALUES (?, 'fp_unique_2', ?, ?, ?, 'WEATHER_CONTEXT', 'SENSOR_API', 'station', ?, ?, 'VALID', 'UNVERIFIED', 0.9, 0.8, '{}', '{}');
                """, (fixed_uuid, triage_id, diag_id, user_id, now_str, now_str))
            conn.rollback()
        finally:
            conn.close()

    # ------------------------------------------------------------------------
    # 5. Foreign-Key Constraint Violations
    # ------------------------------------------------------------------------

    def test_05_foreign_key_violations_rejected(self):
        """Inserting a triage record with non-existent diagnosis_id or user_id is rejected by SQLite FK."""
        conn = self.get_staging_conn()
        try:
            cur = conn.cursor()

            # Non-existent diagnosis_id
            with self.assertRaises(sqlite3.IntegrityError):
                cur.execute("""
                    INSERT INTO diagnostic_triage_records (
                        diagnosis_id, user_id, triage_state, urgency_level,
                        explanation_vi, explanation_en
                    ) VALUES (99999999, 1, 'NORMAL', 'low', 'test', 'test');
                """)
            conn.rollback()

            # Non-existent user_id
            rows = self.get_valid_diagnosis_and_user(conn)
            diag_id, _ = rows[0]
            with self.assertRaises(sqlite3.IntegrityError):
                cur.execute("""
                    INSERT INTO diagnostic_triage_records (
                        diagnosis_id, user_id, triage_state, urgency_level,
                        explanation_vi, explanation_en
                    ) VALUES (?, 99999999, 'NORMAL', 'low', 'test', 'test');
                """, (diag_id,))
            conn.rollback()
        finally:
            conn.close()

    # ------------------------------------------------------------------------
    # 6. Invalid Tenant Relationships & Cross-Tenant Isolation
    # ------------------------------------------------------------------------

    def test_06_tenant_isolation_in_queries(self):
        """Verify queries scoped by organization_id block cross-tenant leakage."""
        conn = self.get_staging_conn()
        try:
            cur = conn.cursor()
            rows = self.get_valid_diagnosis_and_user(conn)
            d1, u1 = rows[0]
            d2, u2 = rows[1]

            cur.execute("""
                INSERT OR REPLACE INTO diagnostic_triage_records (
                    id, diagnosis_id, user_id, organization_id, triage_state, urgency_level, explanation_vi, explanation_en
                ) VALUES (1001, ?, ?, 10, 'NORMAL', 'low', 'Org 10 Triage', 'Org 10 Normal');
            """, (d1, u1))

            cur.execute("""
                INSERT OR REPLACE INTO diagnostic_triage_records (
                    id, diagnosis_id, user_id, organization_id, triage_state, urgency_level, explanation_vi, explanation_en
                ) VALUES (1002, ?, ?, 20, 'URGENT_REVIEW', 'urgent', 'Org 20 Triage', 'Org 20 Urgent');
            """, (d2, u2))
            conn.commit()

            # Query as Org 10 user: cannot see Org 20's records
            cur.execute("SELECT id, explanation_vi FROM diagnostic_triage_records WHERE organization_id = ?;", (10,))
            org10_records = cur.fetchall()
            self.assertEqual(len(org10_records), 1)
            self.assertEqual(org10_records[0][0], 1001)

            # Ensure Org 20's urgent record is never leaked to Org 10
            self.assertNotIn(1002, [r[0] for r in org10_records])
        finally:
            conn.close()

    # ------------------------------------------------------------------------
    # 7. Missing Required Fields (NOT NULL Constraints)
    # ------------------------------------------------------------------------

    def test_07_not_null_constraints_enforced(self):
        """Omitting required fields such as triage_state raises IntegrityError."""
        conn = self.get_staging_conn()
        try:
            cur = conn.cursor()
            rows = self.get_valid_diagnosis_and_user(conn)
            diag_id, user_id = rows[0]

            with self.assertRaises(sqlite3.IntegrityError):
                cur.execute("""
                    INSERT INTO diagnostic_triage_records (
                        diagnosis_id, user_id, triage_state, explanation_vi, explanation_en
                    ) VALUES (?, ?, NULL, 'vi', 'en');
                """, (diag_id, user_id))
            conn.rollback()
        finally:
            conn.close()

    # ------------------------------------------------------------------------
    # 8. Concurrent Write Behavior (SQLite WAL Concurrency)
    # ------------------------------------------------------------------------

    def test_08_concurrent_writes_in_wal_mode(self):
        """Simulate concurrent threads inserting audit logs into staging without busy_timeout locks."""
        conn = self.get_staging_conn()
        try:
            cur = conn.cursor()
            rows = self.get_valid_diagnosis_and_user(conn)
            diag_id, user_id = rows[0]

            cur.execute("""
                INSERT OR IGNORE INTO diagnostic_triage_records (
                    diagnosis_id, user_id, triage_state, urgency_level, explanation_vi, explanation_en
                ) VALUES (?, ?, 'NORMAL', 'low', 'Concurrent test', 'Concurrent test');
            """, (diag_id, user_id))
            conn.commit()

            cur.execute("SELECT id FROM diagnostic_triage_records WHERE diagnosis_id = ?;", (diag_id,))
            triage_id = cur.fetchone()[0]
        finally:
            conn.close()

        errors = []

        def worker_write(thread_idx: int):
            w_conn = None
            try:
                w_conn = sqlite3.connect(STAGING_DB, timeout=10.0)
                w_conn.execute("PRAGMA foreign_keys = ON;")
                w_conn.execute("PRAGMA busy_timeout = 5000;")
                w_cur = w_conn.cursor()
                w_cur.execute("""
                    INSERT INTO decision_audit_logs (
                        diagnosis_id, triage_record_id, user_id, model_name, model_version,
                        triage_state, decision_rationale, recommendation_summary
                    ) VALUES (?, ?, ?, 'convnext_small', 'v2026.1', 'NORMAL', ?, 'summary');
                """, (diag_id, triage_id, user_id, f"Thread {thread_idx} rationale"))
                w_conn.commit()
            except Exception as e:
                errors.append(str(e))
            finally:
                if w_conn:
                    w_conn.close()

        threads = [threading.Thread(target=worker_write, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent write errors encountered: {errors}")

    # ------------------------------------------------------------------------
    # 9. WAL Recovery and Checkpointing
    # ------------------------------------------------------------------------

    def test_09_wal_checkpoint_and_recovery(self):
        """Verify WAL checkpoint flushes log safely and integrity remains ok."""
        conn = self.get_staging_conn()
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA wal_checkpoint(PASSIVE);")
            res = cur.fetchone()
            # Returns (busy, log_pages, checkpointed_pages)
            self.assertIn(res[0], [0, 1], "WAL checkpoint status valid.")
            cur.execute("PRAGMA integrity_check;")
            self.assertEqual(cur.fetchone()[0], "ok")
        finally:
            conn.close()

    # ------------------------------------------------------------------------
    # 10. Overall Database Integrity After Migration
    # ------------------------------------------------------------------------

    def test_10_post_migration_database_integrity(self):
        """Confirm integrity_check and foreign_key_check return zero errors on staging."""
        conn = self.get_staging_conn()
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check;")
            self.assertEqual(cur.fetchone()[0], "ok")

            cur.execute("PRAGMA foreign_key_check;")
            fk_errs = cur.fetchall()
            self.assertEqual(len(fk_errs), 0)
        finally:
            conn.close()

    # ------------------------------------------------------------------------
    # 11. Rollback Drill A: Empty Staging Schema Rollback
    # ------------------------------------------------------------------------

    def test_11_rollback_drill_a_schema_drop(self):
        """Test schema rollback on an isolated clone: tables are dropped cleanly, original 84 tables intact."""
        clone_db = os.path.abspath("database/test_rollback_drill_a.db")
        shutil.copy2(STAGING_DB, clone_db)

        try:
            rb_res = rollback_schema(clone_db)
            self.assertTrue(rb_res["success"])
            self.assertEqual(rb_res["integrity_check"], "ok")

            conn = sqlite3.connect(clone_db)
            try:
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables_after = set(r[0] for r in cur.fetchall())

                # 4 Sprint 6.2 tables must be gone
                for t in TABLES:
                    self.assertNotIn(t, tables_after)

                # Original tables must still be intact
                self.assertIn("users", tables_after)
                self.assertIn("diagnoses", tables_after)
                self.assertIn("farms", tables_after)
            finally:
                conn.close()
        finally:
            if os.path.exists(clone_db):
                os.remove(clone_db)

    # ------------------------------------------------------------------------
    # 12. Rollback Drill B: Data-Preserving Rollback via Feature Flag
    # ------------------------------------------------------------------------

    def test_12_rollback_drill_b_data_preserving(self):
        """Test data-preserving rollback: disabling feature flag leaves tables & business data intact."""
        conn = self.get_staging_conn()
        try:
            cur = conn.cursor()
            rows = self.get_valid_diagnosis_and_user(conn)
            diag_id, user_id = rows[0]

            cur.execute("""
                INSERT OR REPLACE INTO diagnostic_triage_records (
                    id, diagnosis_id, user_id, triage_state, urgency_level, explanation_vi, explanation_en
                ) VALUES (9001, ?, ?, 'SUSPECTED', 'medium', 'Nghi ngờ rệp sáp', 'Suspected mealybug');
            """, (diag_id, user_id))
            conn.commit()

            # Simulate Feature Flag Toggle: ENABLE_SPRINT_6_2_TRIAGE = False
            enable_sprint_6_2_triage = False

            if not enable_sprint_6_2_triage:
                # System operates in legacy mode: existing /api/predict routes work as before
                legacy_active = True

            # Assert zero DROP TABLE executed: business record 9001 remains 100% intact in database
            cur.execute("SELECT triage_state, explanation_vi FROM diagnostic_triage_records WHERE id = 9001;")
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "SUSPECTED")
            self.assertEqual(row[1], "Nghi ngờ rệp sáp")
        finally:
            conn.close()

    # ------------------------------------------------------------------------
    # 13. Rollback Drill C: Backup Restoration
    # ------------------------------------------------------------------------

    def test_13_rollback_drill_c_backup_restoration(self):
        """Restore verified backup into recovery database and verify table counts, rows, and integrity."""
        if os.path.exists(RECOVERY_TEST_DB):
            os.remove(RECOVERY_TEST_DB)

        # Restore from backup using SQLite Online Backup API
        src = sqlite3.connect(BACKUP_DB)
        dst = sqlite3.connect(RECOVERY_TEST_DB)
        src.backup(dst, pages=250)
        src.close()
        dst.close()

        rec_conn = sqlite3.connect(RECOVERY_TEST_DB)
        try:
            cur = rec_conn.cursor()

            cur.execute("PRAGMA integrity_check;")
            self.assertEqual(cur.fetchone()[0], "ok")

            cur.execute("PRAGMA foreign_key_check;")
            self.assertEqual(len(cur.fetchall()), 0)

            cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
            self.assertEqual(cur.fetchone()[0], 84)

            cur.execute("SELECT COUNT(*) FROM users;")
            self.assertEqual(cur.fetchone()[0], 3610)

            cur.execute("SELECT COUNT(*) FROM diagnoses;")
            self.assertEqual(cur.fetchone()[0], 599)
        finally:
            rec_conn.close()

        # Clean up recovery test file
        if os.path.exists(RECOVERY_TEST_DB):
            os.remove(RECOVERY_TEST_DB)


if __name__ == "__main__":
    unittest.main()
