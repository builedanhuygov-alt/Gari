"""
Pre-Migration Backup Script using SQLite Online Backup API.
Ensures 100% consistent point-in-time snapshot of SQLite WAL database.
"""

import hashlib
import os
import sqlite3
import sys

PROD_DB = os.path.abspath("database/disease_detector.db")
BACKUP_DIR = os.path.abspath("database/backups")
BACKUP_DB = os.path.join(BACKUP_DIR, "disease_detector_pre_sprint6_2.bak")
STAGING_DB = os.path.abspath("database/staging_disease_detector.db")

def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def main():
    print("=== GARI SPRINT 6.2 PRE-MIGRATION BACKUP ===")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    if not os.path.exists(PROD_DB):
        print(f"ERROR: Production database not found at {PROD_DB}")
        sys.exit(1)
        
    print(f"1. Connecting to Production DB: {PROD_DB}")
    src_conn = sqlite3.connect(PROD_DB)
    src_cur = src_conn.cursor()
    
    src_cur.execute("PRAGMA journal_mode;")
    jm = src_cur.fetchone()[0]
    print(f"   Production Journal Mode: {jm}")
    
    src_cur.execute("PRAGMA integrity_check;")
    ic = src_cur.fetchone()[0]
    print(f"   Production Integrity Check: {ic}")
    if ic != "ok":
        print("ERROR: Production integrity check failed!")
        sys.exit(1)
        
    # Online Backup API
    print(f"2. Performing SQLite Online Backup to: {BACKUP_DB}")
    if os.path.exists(BACKUP_DB):
        os.remove(BACKUP_DB)
        
    dst_conn = sqlite3.connect(BACKUP_DB)
    src_conn.backup(dst_conn, pages=250)
    dst_conn.close()
    src_conn.close()
    print("   Online Backup API completed successfully.")
    
    # Checksum verification
    prod_hash = compute_sha256(PROD_DB)
    bak_hash = compute_sha256(BACKUP_DB)
    print(f"   Production DB File SHA-256 : {prod_hash}")
    print(f"   Online Backup File SHA-256 : {bak_hash}")
    
    # Verify the backup file
    print(f"3. Verifying Backup File: {BACKUP_DB}")
    bak_conn = sqlite3.connect(BACKUP_DB)
    bak_cur = bak_conn.cursor()
    
    bak_cur.execute("PRAGMA integrity_check;")
    bak_ic = bak_cur.fetchone()[0]
    print(f"   Backup Integrity Check: {bak_ic}")
    if bak_ic != "ok":
        print("ERROR: Backup integrity check failed!")
        sys.exit(1)
        
    bak_cur.execute("PRAGMA foreign_key_check;")
    fk_errors = bak_cur.fetchall()
    print(f"   Backup Foreign Key Check Errors: {len(fk_errors)}")
    if fk_errors:
        print(f"   FK Errors detail: {fk_errors[:5]}")
        
    bak_cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
    tbl_count = bak_cur.fetchone()[0]
    print(f"   Total Tables in Backup: {tbl_count}")
    
    # Important row counts
    key_tables = [
        "users", "diagnoses", "farms", "farm_plots", 
        "expert_cases", "cultivation_tasks", "notifications",
        "plot_timeline_events", "risk_alerts"
    ]
    row_counts = {}
    for t in key_tables:
        try:
            bak_cur.execute(f"SELECT COUNT(*) FROM {t};")
            row_counts[t] = bak_cur.fetchone()[0]
        except Exception as e:
            row_counts[t] = f"MISSING ({e})"
    print("   Key Table Row Counts:")
    for t, c in row_counts.items():
        print(f"     - {t:22}: {c}")
        
    bak_conn.close()
    
    # Provision Staging DB from verified backup
    print(f"4. Provisioning Staging DB from Verified Backup...")
    if os.path.exists(STAGING_DB):
        os.remove(STAGING_DB)
    # Also remove any leftover wal/shm files for staging
    for ext in ["-wal", "-shm"]:
        if os.path.exists(STAGING_DB + ext):
            os.remove(STAGING_DB + ext)
            
    # Use backup API again to clone from backup to staging
    b_conn = sqlite3.connect(BACKUP_DB)
    stg_conn = sqlite3.connect(STAGING_DB)
    b_conn.backup(stg_conn, pages=250)
    
    # Ensure staging uses WAL
    stg_conn.execute("PRAGMA journal_mode = WAL;")
    stg_conn.execute("PRAGMA foreign_keys = ON;")
    stg_conn.commit()
    b_conn.close()
    stg_conn.close()
    
    stg_hash = compute_sha256(STAGING_DB)
    print(f"   Staging DB created at: {STAGING_DB}")
    print(f"   Staging DB SHA-256   : {stg_hash}")
    
    # Verify staging path != production path
    assert os.path.normpath(STAGING_DB) != os.path.normpath(PROD_DB), "Staging path MUST NOT match production path!"
    print("   Path Isolation: CONFIRMED (Staging != Production)")
    print("=== PRE-MIGRATION BACKUP & STAGING PROVISIONING COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()

