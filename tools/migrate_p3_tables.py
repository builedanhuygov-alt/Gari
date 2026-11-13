"""
GARI Phase P3 Database Migration
Safely creates tables and adds columns for:
- GIS Zone geometries
- Weather cache
- Satellite scenes & plot indices
- Agricultural risk assessments
- Smart alerts lifecycle & deduplication
"""

import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gari_p3_migration")

DB_PATH = "database/disease_detector.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Update farm_zones columns
    zone_cols = [c[1] for c in cursor.execute("PRAGMA table_info(farm_zones)").fetchall()]
    if "boundary_geojson" not in zone_cols:
        logger.info("Adding boundary_geojson to farm_zones")
        cursor.execute("ALTER TABLE farm_zones ADD COLUMN boundary_geojson TEXT")
    if "latitude" not in zone_cols:
        logger.info("Adding latitude to farm_zones")
        cursor.execute("ALTER TABLE farm_zones ADD COLUMN latitude REAL")
    if "longitude" not in zone_cols:
        logger.info("Adding longitude to farm_zones")
        cursor.execute("ALTER TABLE farm_zones ADD COLUMN longitude REAL")
    if "geometry_source" not in zone_cols:
        logger.info("Adding geometry_source to farm_zones")
        cursor.execute("ALTER TABLE farm_zones ADD COLUMN geometry_source TEXT DEFAULT 'user_drawn'")

    # 2. Weather Cache Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS weather_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT UNIQUE,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            provider TEXT NOT NULL,
            timezone TEXT,
            weather_data TEXT NOT NULL,
            fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_weather_cache_key ON weather_cache(cache_key)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_weather_cache_coords ON weather_cache(latitude, longitude)")

    # 3. Satellite Scenes & Indices
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS satellite_scenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id TEXT UNIQUE NOT NULL,
            provider TEXT NOT NULL,
            platform TEXT NOT NULL,
            acquisition_date DATETIME NOT NULL,
            cloud_cover_pct REAL,
            bbox_geojson TEXT,
            assets_json TEXT,
            quality_status TEXT DEFAULT 'valid',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sat_scenes_date ON satellite_scenes(acquisition_date)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS satellite_plot_indices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plot_id INTEGER NOT NULL,
            scene_id TEXT,
            acquisition_date DATE NOT NULL,
            ndvi_mean REAL,
            ndvi_min REAL,
            ndvi_max REAL,
            ndmi_mean REAL,
            ndmi_min REAL,
            ndmi_max REAL,
            cloud_cover_pct REAL,
            quality_status TEXT NOT NULL, -- 'valid', 'cloud_masked', 'insufficient_bands', 'estimated'
            source TEXT NOT NULL,
            metadata_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (plot_id) REFERENCES farm_plots(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sat_indices_plot_date ON satellite_plot_indices(plot_id, acquisition_date)")

    # 4. Agricultural Risk Assessments
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agricultural_risk_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER,
            farm_id INTEGER NOT NULL,
            plot_id INTEGER,
            assessment_date DATETIME NOT NULL,
            risk_category TEXT NOT NULL, -- 'drought', 'heavy_rainfall', 'heat_stress', 'disease_weather', 'vegetation_degradation'
            risk_level TEXT NOT NULL, -- 'low', 'moderate', 'high', 'severe'
            risk_score REAL NOT NULL, -- 0.0 to 100.0
            confidence_score REAL NOT NULL, -- 0.0 to 1.0
            status TEXT NOT NULL DEFAULT 'evaluated', -- 'evaluated', 'insufficient_data'
            contributing_factors TEXT NOT NULL, -- JSON array
            explanation TEXT NOT NULL,
            recommendations TEXT NOT NULL, -- JSON array
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE,
            FOREIGN KEY (plot_id) REFERENCES farm_plots(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_risk_farm_date ON agricultural_risk_assessments(farm_id, assessment_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_risk_plot ON agricultural_risk_assessments(plot_id)")

    # 5. Smart Alerts with Deduplication & Lifecycle
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS smart_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_fingerprint TEXT UNIQUE,
            organization_id INTEGER,
            farm_id INTEGER NOT NULL,
            plot_id INTEGER,
            alert_type TEXT NOT NULL, -- 'weather', 'satellite', 'agricultural_risk', 'data_quality'
            severity TEXT NOT NULL, -- 'info', 'warning', 'critical'
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            trigger_source TEXT NOT NULL, -- 'open_meteo', 'sentinel_2', 'risk_engine', 'sensor'
            evidence_json TEXT,
            status TEXT NOT NULL DEFAULT 'new', -- 'new', 'acknowledged', 'in_progress', 'resolved', 'dismissed'
            assigned_user_id INTEGER,
            resolution_notes TEXT,
            acknowledged_at DATETIME,
            resolved_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE,
            FOREIGN KEY (plot_id) REFERENCES farm_plots(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_smart_alerts_org ON smart_alerts(organization_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_smart_alerts_farm ON smart_alerts(farm_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_smart_alerts_status ON smart_alerts(status)")

    conn.commit()
    conn.close()
    logger.info("Migration completed successfully!")

if __name__ == '__main__':
    migrate()

