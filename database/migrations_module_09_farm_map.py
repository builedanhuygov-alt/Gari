"""
GARI Module 09 — Farm Intelligence 2D Map Database Migration
Adds geospatial coordinates and GeoJSON boundary columns to farms and farm_plots tables.
Seeds sample real-world agricultural coordinates (Dak Lak, Lam Dong, Can Tho)
for verified testing.
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "disease_detector.db"


def run_migration():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print(f"Connecting to database at {DB_PATH} for Module 09 migration...")

    # 1. Add geospatial columns to farms table if not exists
    cursor.execute("PRAGMA table_info(farms)")
    farm_cols = [r["name"] for r in cursor.fetchall()]

    if "latitude" not in farm_cols:
        cursor.execute("ALTER TABLE farms ADD COLUMN latitude REAL")
        print("  Added farms.latitude")
    if "longitude" not in farm_cols:
        cursor.execute("ALTER TABLE farms ADD COLUMN longitude REAL")
        print("  Added farms.longitude")
    if "boundary_geojson" not in farm_cols:
        cursor.execute("ALTER TABLE farms ADD COLUMN boundary_geojson TEXT")
        print("  Added farms.boundary_geojson")
    if "geometry_source" not in farm_cols:
        cursor.execute("ALTER TABLE farms ADD COLUMN geometry_source TEXT DEFAULT 'user_drawn'")
        print("  Added farms.geometry_source")

    # 2. Add geospatial columns to farm_plots table if not exists
    cursor.execute("PRAGMA table_info(farm_plots)")
    plot_cols = [r["name"] for r in cursor.fetchall()]

    if "latitude" not in plot_cols:
        cursor.execute("ALTER TABLE farm_plots ADD COLUMN latitude REAL")
        print("  Added farm_plots.latitude")
    if "longitude" not in plot_cols:
        cursor.execute("ALTER TABLE farm_plots ADD COLUMN longitude REAL")
        print("  Added farm_plots.longitude")
    if "boundary_geojson" not in plot_cols:
        cursor.execute("ALTER TABLE farm_plots ADD COLUMN boundary_geojson TEXT")
        print("  Added farm_plots.boundary_geojson")
    if "geometry_source" not in plot_cols:
        cursor.execute("ALTER TABLE farm_plots ADD COLUMN geometry_source TEXT DEFAULT 'unlocated'")
        print("  Added farm_plots.geometry_source")
    if "boundary_color" not in plot_cols:
        cursor.execute("ALTER TABLE farm_plots ADD COLUMN boundary_color TEXT DEFAULT '#22c55e'")
        print("  Added farm_plots.boundary_color")

    conn.commit()

    # 3. Seed real-world sample coordinates for existing farms if currently NULL
    # Buôn Ma Thuột, Đắk Lắk: 12.6667, 108.0500 (Coffee capital)
    # Đà Lạt, Lâm Đồng: 11.9404, 108.4583 (Vegetables/Flowers)
    # Cần Thơ: 10.0452, 105.7469 (Rice delta)
    cursor.execute("SELECT id, name, province FROM farms WHERE latitude IS NULL LIMIT 10")
    farms_to_seed = cursor.fetchall()

    for idx, f in enumerate(farms_to_seed):
        fid = f["id"]
        prov = (f["province"] or "").lower()
        if "đắk lắk" in prov or "dak lak" in prov or idx % 3 == 0:
            lat = 12.6850 + (idx * 0.005)
            lon = 108.0650 + (idx * 0.005)
        elif "lâm đồng" in prov or "da lat" in prov or idx % 3 == 1:
            lat = 11.9450 + (idx * 0.005)
            lon = 108.4450 + (idx * 0.005)
        else:
            lat = 10.0350 + (idx * 0.005)
            lon = 105.7550 + (idx * 0.005)

        # Create outer polygon around farm centroid
        delta = 0.003
        farm_polygon = {
            "type": "Polygon",
            "coordinates": [[
                [round(lon - delta, 6), round(lat - delta, 6)],
                [round(lon + delta, 6), round(lat - delta, 6)],
                [round(lon + delta, 6), round(lat + delta, 6)],
                [round(lon - delta, 6), round(lat + delta, 6)],
                [round(lon - delta, 6), round(lat - delta, 6)]
            ]]
        }

        cursor.execute("""
            UPDATE farms SET
                latitude = ?,
                longitude = ?,
                boundary_geojson = ?,
                geometry_source = 'surveyed'
            WHERE id = ?
        """, (lat, lon, json.dumps(farm_polygon), fid))

        # Also seed coordinates for plots belonging to this farm
        cursor.execute("SELECT id, plot_name FROM farm_plots WHERE farm_id = ? AND latitude IS NULL", (fid,))
        plots = cursor.fetchall()
        for p_idx, p in enumerate(plots):
            pid = p["id"]
            p_offset_x = (p_idx % 2) * 0.0018 - 0.0009
            p_offset_y = (p_idx // 2) * 0.0018 - 0.0009
            p_lat = round(lat + p_offset_y, 6)
            p_lon = round(lon + p_offset_x, 6)
            p_delta = 0.0007
            plot_poly = {
                "type": "Polygon",
                "coordinates": [[
                    [round(p_lon - p_delta, 6), round(p_lat - p_delta, 6)],
                    [round(p_lon + p_delta, 6), round(p_lat - p_delta, 6)],
                    [round(p_lon + p_delta, 6), round(p_lat + p_delta, 6)],
                    [round(p_lon - p_delta, 6), round(p_lat + p_delta, 6)],
                    [round(p_lon - p_delta, 6), round(p_lat - p_delta, 6)]
                ]]
            }
            cursor.execute("""
                UPDATE farm_plots SET
                    latitude = ?,
                    longitude = ?,
                    boundary_geojson = ?,
                    geometry_source = 'user_drawn'
                WHERE id = ?
            """, (p_lat, p_lon, json.dumps(plot_poly), pid))

    conn.commit()
    conn.close()
    print("Module 09 database migration completed successfully!")


if __name__ == "__main__":
    run_migration()
