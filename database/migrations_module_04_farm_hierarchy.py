"""
GARI AI LAB — Database Migration: Module 04 Farm Hierarchy & Extensible Ag Data
File: database/migrations_module_04_farm_hierarchy.py

Implements:
1. farms: organization_id, code, area_m2, area_unit, archived_at
2. farm_zones: Zone-level management within farms
3. farm_plots: zone_id, plot_code, area_m2, area_unit, active_cycle_id, soil_type, irrigation_type, archived_at
4. crop_cycles: Successive seasonal crop cycles & crop rotation tracking
5. plot_plants: Individual plant/tree/cluster level tracking (e.g., durian trees, greenhouse rows)
6. plot_timeline_events: plant_id, cycle_id, severity, action_taken, images_json
7. diagnoses: plant_id, crop_cycle_id
8. cultivation_tasks: plant_id, crop_cycle_id
"""

import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DB_PATH = Path("database/disease_detector.db")
BACKUP_DIR = Path("database/backups")


def run_migration():
    if not DB_PATH.exists():
        print(f"[!] Database file not found at {DB_PATH}")
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"disease_detector_pre_module_04_{timestamp}.db"
    shutil.copy2(DB_PATH, backup_file)
    print(f"[+] Created safety snapshot backup at: {backup_file}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 1. Update 'farms' table
        cursor.execute("PRAGMA table_info(farms)")
        farm_cols = [r["name"] for r in cursor.fetchall()]
        if "organization_id" not in farm_cols:
            cursor.execute("ALTER TABLE farms ADD COLUMN organization_id INTEGER REFERENCES organizations(id);")
            print("[+] Added 'organization_id' to 'farms'.")
        if "code" not in farm_cols:
            cursor.execute("ALTER TABLE farms ADD COLUMN code TEXT;")
            print("[+] Added 'code' to 'farms'.")
        if "area_m2" not in farm_cols:
            cursor.execute("ALTER TABLE farms ADD COLUMN area_m2 REAL;")
            print("[+] Added 'area_m2' to 'farms'.")
        if "area_unit" not in farm_cols:
            cursor.execute("ALTER TABLE farms ADD COLUMN area_unit TEXT DEFAULT 'ha';")
            print("[+] Added 'area_unit' to 'farms'.")
        if "archived_at" not in farm_cols:
            cursor.execute("ALTER TABLE farms ADD COLUMN archived_at DATETIME;")
            print("[+] Added 'archived_at' to 'farms'.")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_farms_org_id ON farms(organization_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_farms_status ON farms(status);")

        # 2. Create 'farm_zones' table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS farm_zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_id INTEGER NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                code TEXT,
                zone_type TEXT DEFAULT 'open_field',
                area_m2 REAL,
                area_hectare REAL,
                area_unit TEXT DEFAULT 'ha',
                description TEXT,
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                archived_at DATETIME
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_farm_zones_farm_id ON farm_zones(farm_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_farm_zones_status ON farm_zones(status);")
        print("[+] Ensured 'farm_zones' table exists.")

        # 3. Update 'farm_plots' table
        cursor.execute("PRAGMA table_info(farm_plots)")
        plot_cols = [r["name"] for r in cursor.fetchall()]
        if "zone_id" not in plot_cols:
            cursor.execute("ALTER TABLE farm_plots ADD COLUMN zone_id INTEGER REFERENCES farm_zones(id) ON DELETE SET NULL;")
            print("[+] Added 'zone_id' to 'farm_plots'.")
        if "plot_code" not in plot_cols:
            cursor.execute("ALTER TABLE farm_plots ADD COLUMN plot_code TEXT;")
            print("[+] Added 'plot_code' to 'farm_plots'.")
        if "area_m2" not in plot_cols:
            cursor.execute("ALTER TABLE farm_plots ADD COLUMN area_m2 REAL;")
            print("[+] Added 'area_m2' to 'farm_plots'.")
        if "area_unit" not in plot_cols:
            cursor.execute("ALTER TABLE farm_plots ADD COLUMN area_unit TEXT DEFAULT 'ha';")
            print("[+] Added 'area_unit' to 'farm_plots'.")
        if "active_cycle_id" not in plot_cols:
            cursor.execute("ALTER TABLE farm_plots ADD COLUMN active_cycle_id INTEGER;")
            print("[+] Added 'active_cycle_id' to 'farm_plots'.")
        if "soil_type" not in plot_cols:
            cursor.execute("ALTER TABLE farm_plots ADD COLUMN soil_type TEXT;")
            print("[+] Added 'soil_type' to 'farm_plots'.")
        if "irrigation_type" not in plot_cols:
            cursor.execute("ALTER TABLE farm_plots ADD COLUMN irrigation_type TEXT;")
            print("[+] Added 'irrigation_type' to 'farm_plots'.")
        if "updated_at" not in plot_cols:
            cursor.execute("ALTER TABLE farm_plots ADD COLUMN updated_at DATETIME;")
            print("[+] Added 'updated_at' to 'farm_plots'.")
        if "archived_at" not in plot_cols:
            cursor.execute("ALTER TABLE farm_plots ADD COLUMN archived_at DATETIME;")
            print("[+] Added 'archived_at' to 'farm_plots'.")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_farm_plots_zone_id ON farm_plots(zone_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_farm_plots_status ON farm_plots(status);")

        # 4. Create 'crop_cycles' table (Vụ mùa & Luân canh)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crop_cycles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plot_id INTEGER NOT NULL REFERENCES farm_plots(id) ON DELETE CASCADE,
                cycle_name TEXT NOT NULL,
                cycle_code TEXT,
                crop_id TEXT NOT NULL,
                crop_name TEXT NOT NULL,
                variety TEXT,
                start_date DATE,
                expected_harvest_date DATE,
                actual_harvest_date DATE,
                target_yield_kg REAL,
                actual_yield_kg REAL,
                status TEXT DEFAULT 'active',
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                archived_at DATETIME
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_crop_cycles_plot_id ON crop_cycles(plot_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_crop_cycles_status ON crop_cycles(status);")
        print("[+] Ensured 'crop_cycles' table exists.")

        # 5. Create 'plot_plants' table (Individual plant / tree / row tracking)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plot_plants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plot_id INTEGER NOT NULL REFERENCES farm_plots(id) ON DELETE CASCADE,
                zone_id INTEGER REFERENCES farm_zones(id) ON DELETE SET NULL,
                plant_tag TEXT NOT NULL,
                plant_name TEXT,
                species TEXT,
                variety TEXT,
                planting_date DATE,
                row_index INTEGER,
                col_index INTEGER,
                health_status TEXT DEFAULT 'healthy',
                gps_lat REAL,
                gps_lng REAL,
                notes TEXT,
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                archived_at DATETIME
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plot_plants_plot_id ON plot_plants(plot_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plot_plants_tag ON plot_plants(plot_id, plant_tag);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plot_plants_health ON plot_plants(health_status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plot_plants_status ON plot_plants(status);")
        print("[+] Ensured 'plot_plants' table exists.")

        # 6. Update 'plot_timeline_events'
        cursor.execute("PRAGMA table_info(plot_timeline_events)")
        timeline_cols = [r["name"] for r in cursor.fetchall()]
        if "plant_id" not in timeline_cols:
            cursor.execute("ALTER TABLE plot_timeline_events ADD COLUMN plant_id INTEGER REFERENCES plot_plants(id);")
            print("[+] Added 'plant_id' to 'plot_timeline_events'.")
        if "cycle_id" not in timeline_cols:
            cursor.execute("ALTER TABLE plot_timeline_events ADD COLUMN cycle_id INTEGER REFERENCES crop_cycles(id);")
            print("[+] Added 'cycle_id' to 'plot_timeline_events'.")
        if "severity" not in timeline_cols:
            cursor.execute("ALTER TABLE plot_timeline_events ADD COLUMN severity TEXT;")
            print("[+] Added 'severity' to 'plot_timeline_events'.")
        if "action_taken" not in timeline_cols:
            cursor.execute("ALTER TABLE plot_timeline_events ADD COLUMN action_taken TEXT;")
            print("[+] Added 'action_taken' to 'plot_timeline_events'.")
        if "images_json" not in timeline_cols:
            cursor.execute("ALTER TABLE plot_timeline_events ADD COLUMN images_json TEXT;")
            print("[+] Added 'images_json' to 'plot_timeline_events'.")

        # 7. Update 'diagnoses'
        cursor.execute("PRAGMA table_info(diagnoses)")
        diag_cols = [r["name"] for r in cursor.fetchall()]
        if "plant_id" not in diag_cols:
            cursor.execute("ALTER TABLE diagnoses ADD COLUMN plant_id INTEGER REFERENCES plot_plants(id);")
            print("[+] Added 'plant_id' to 'diagnoses'.")
        if "crop_cycle_id" not in diag_cols:
            cursor.execute("ALTER TABLE diagnoses ADD COLUMN crop_cycle_id INTEGER REFERENCES crop_cycles(id);")
            print("[+] Added 'crop_cycle_id' to 'diagnoses'.")

        # 8. Update 'cultivation_tasks'
        cursor.execute("PRAGMA table_info(cultivation_tasks)")
        task_cols = [r["name"] for r in cursor.fetchall()]
        if "plant_id" not in task_cols:
            cursor.execute("ALTER TABLE cultivation_tasks ADD COLUMN plant_id INTEGER REFERENCES plot_plants(id);")
            print("[+] Added 'plant_id' to 'cultivation_tasks'.")
        if "crop_cycle_id" not in task_cols:
            cursor.execute("ALTER TABLE cultivation_tasks ADD COLUMN crop_cycle_id INTEGER REFERENCES crop_cycles(id);")
            print("[+] Added 'crop_cycle_id' to 'cultivation_tasks'.")

        # Backfill normalized area_m2 for existing farms and plots
        cursor.execute("""
            UPDATE farms
            SET area_m2 = ROUND(area_hectare * 10000.0, 2),
                area_unit = 'ha'
            WHERE (area_m2 IS NULL OR area_m2 = 0) AND area_hectare IS NOT NULL
        """)
        cursor.execute("""
            UPDATE farm_plots
            SET area_m2 = ROUND(COALESCE(area_hectare, area_hectares, 0.5) * 10000.0, 2),
                area_unit = 'ha'
            WHERE (area_m2 IS NULL OR area_m2 = 0)
        """)

        conn.commit()
        print("[✓] Module 04 Farm Hierarchy database migration applied successfully!")

    except Exception as e:
        conn.rollback()
        print(f"[!] Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
