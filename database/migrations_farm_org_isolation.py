"""
GARI AI LAB — Database Migration: Farm & Organization Test Data Isolation
File: database/migrations_farm_org_isolation.py

Adds `is_test` column to `organizations` and `farms` tables.
Flags automated test fixtures so they never pollute production/user UI.
Preserves all legitimate user records.
"""

import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DB_PATH = Path("database/disease_detector.db")
BACKUP_DIR = Path("database/backups")


def run_migration():
    if not DB_PATH.exists():
        print(f"[!] Database file not found at {DB_PATH}")
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"disease_detector_pre_isolation_{timestamp}.db"
    shutil.copy2(DB_PATH, backup_file)
    print(f"[+] Created safety snapshot backup at: {backup_file}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 1. Add is_test column to organizations
        cursor.execute("PRAGMA table_info(organizations)")
        org_columns = [r["name"] for r in cursor.fetchall()]
        if "is_test" not in org_columns:
            cursor.execute("ALTER TABLE organizations ADD COLUMN is_test INTEGER DEFAULT 0")
            print("[+] Added 'is_test' column to 'organizations' table.")
        else:
            print("[*] 'is_test' column already exists on 'organizations'.")

        # 2. Add is_test column to farms
        cursor.execute("PRAGMA table_info(farms)")
        farm_columns = [r["name"] for r in cursor.fetchall()]
        if "is_test" not in farm_columns:
            cursor.execute("ALTER TABLE farms ADD COLUMN is_test INTEGER DEFAULT 0")
            print("[+] Added 'is_test' column to 'farms' table.")
        else:
            print("[*] 'is_test' column already exists on 'farms'.")

        # 3. Flag test organizations as is_test = 1
        # Test fixture criteria: Test Concurrent HTX, Cô Đơn timestamps, Audit/Payment orgs, duplicate test seeds
        flag_orgs_sql = """
            UPDATE organizations
            SET is_test = 1
            WHERE name LIKE '%Test%'
               OR name LIKE '%Cô Đơn%'
               OR name LIKE '%cô đơn%'
               OR slug LIKE '%co-don%'
               OR slug LIKE '%cô-đơn%'
               OR slug LIKE 'test-%'
               OR slug LIKE 'audit-%'
               OR slug LIKE 'payment-%'
               OR (name LIKE '%Nông Dân 7%' AND id > 2)
        """
        cursor.execute(flag_orgs_sql)
        flagged_orgs_count = cursor.rowcount
        print(f"[+] Flagged {flagged_orgs_count} test organizations with is_test = 1.")

        # 4. Flag test farms as is_test = 1
        flag_farms_sql = """
            UPDATE farms
            SET is_test = 1
            WHERE name LIKE '%17934%'
               OR name LIKE '%(Đã cập nhật)%'
               OR name LIKE 'Test %'
               OR name LIKE 'test %'
        """
        cursor.execute(flag_farms_sql)
        flagged_farms_count = cursor.rowcount
        print(f"[+] Flagged {flagged_farms_count} test farms with is_test = 1.")

        # 5. Create index on is_test for rapid filtering
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_organizations_is_test ON organizations(is_test)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_farms_is_test ON farms(is_test)")

        conn.commit()
        print("[+] Migration completed successfully!")

        # Verify real records count
        cursor.execute("SELECT id, name, owner_id FROM organizations WHERE is_test = 0")
        real_orgs = cursor.fetchall()
        print(f"\n[*] Active Real Organizations ({len(real_orgs)}):")
        for o in real_orgs:
            print(f"    - ID {o['id']}: {o['name']} (Owner #{o['owner_id']})")

        cursor.execute("SELECT id, name, user_id, province FROM farms WHERE is_test = 0")
        real_farms = cursor.fetchall()
        print(f"\n[*] Active Real Farms ({len(real_farms)}):")
        for f in real_farms:
            print(f"    - ID {f['id']}: {f['name']} ({f['province']}) - User #{f['user_id']}")

    except Exception as e:
        conn.rollback()
        print(f"[-] Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
