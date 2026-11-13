import sqlite3
import os

BACKUP_DB = os.path.abspath("database/backups/disease_detector_pre_sprint6_2.bak")
STAGING_DB = os.path.abspath("database/staging_disease_detector.db")

# Re-clone staging from backup
src = sqlite3.connect(BACKUP_DB)
dst = sqlite3.connect(STAGING_DB)
src.backup(dst, pages=250)
src.close()
dst.close()

from database.migrations.migration_v2026_02_sprint6_2 import apply_migration
res = apply_migration(STAGING_DB)
print("Migration result:", res)

conn = sqlite3.connect(STAGING_DB)
conn.execute("PRAGMA foreign_keys = ON;")
cur = conn.cursor()

cur.execute("""
    SELECT d.id, d.user_id 
    FROM diagnoses d 
    JOIN users u ON d.user_id = u.id 
    WHERE d.user_id IS NOT NULL 
    LIMIT 2;
""")
valid_rows = cur.fetchall()
print("Valid rows with users:", valid_rows)

d_id, u_id = valid_rows[0]
cur.execute("""
    INSERT INTO diagnostic_triage_records (
        diagnosis_id, user_id, triage_state, urgency_level, explanation_vi, explanation_en
    ) VALUES (?, ?, 'NORMAL', 'low', 'Bình thường', 'Normal');
""", (d_id, u_id))
conn.commit()

cur.execute("SELECT id FROM diagnostic_triage_records WHERE diagnosis_id = ?;", (d_id,))
print("Triage ID:", cur.fetchone())

conn.close()

