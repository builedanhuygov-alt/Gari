"""
GARI Module — Geospatial & GIS Mapping Service Layer (P3.1)
Authoritative implementation for:
1. Multi-tier GeoJSON FeatureCollections (Farms, Zones, Plots, and Geolocated Diagnoses).
2. Zone polygon geometry validation and spatial updates.
3. Spatial diagnosis history linkage with plot boundaries and coordinates.
4. Tenant-isolated geospatial search and multi-criteria filtering.
5. Graceful handling of unlocated assets.
"""

import json
import logging
import sqlite3
from typing import Dict, Any, List, Optional, Tuple, Union

from gari_database import get_connection
import gari_farm_management
import gari_farm_map

logger = logging.getLogger("gari.gis")


def update_zone_geometry(
    zone_id: int,
    geometry: Union[Dict[str, Any], str],
    user_id: int,
    org_id: Optional[int] = None,
    geometry_source: str = "user_drawn"
) -> Dict[str, Any]:
    """
    Validate GeoJSON Polygon for a farm zone, compute centroid and area,
    and update farm_zones record with tenant permission enforcement.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT farm_id FROM farm_zones WHERE id = ? AND archived_at IS NULL", (zone_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Không tìm thấy phân khu #{zone_id} hoặc phân khu đã bị xóa.")
        farm_id = row["farm_id"]

    if not gari_farm_management.check_farm_access(farm_id=farm_id, user_id=user_id, org_id=org_id, require_write=True):
        raise PermissionError(f"Bạn không có quyền chỉnh sửa ranh giới phân khu #{zone_id}.")

    valid_geom = gari_farm_map.validate_polygon_geometry(geometry)
    ring = valid_geom["coordinates"][0]

    centroid_lat, centroid_lon = gari_farm_map.calculate_polygon_centroid(ring)
    calc_area_m2 = gari_farm_map.calculate_polygon_area_m2(ring)
    calc_area_ha = round(calc_area_m2 / 10000.0, 4)

    if geometry_source not in gari_farm_map.VALID_GEOMETRY_SOURCES:
        geometry_source = "user_drawn"

    boundary_json = json.dumps(valid_geom)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE farm_zones SET
                latitude = ?,
                longitude = ?,
                boundary_geojson = ?,
                geometry_source = ?,
                area_m2 = CASE WHEN area_m2 IS NULL OR area_m2 <= 0 THEN ? ELSE area_m2 END,
                area_hectare = CASE WHEN area_hectare IS NULL OR area_hectare <= 0 THEN ? ELSE area_hectare END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (centroid_lat, centroid_lon, boundary_json, geometry_source, calc_area_m2, calc_area_ha, zone_id))
        conn.commit()

    return {
        "success": True,
        "zone_id": zone_id,
        "farm_id": farm_id,
        "latitude": centroid_lat,
        "longitude": centroid_lon,
        "geometry": valid_geom,
        "calculated_area_m2": calc_area_m2,
        "calculated_area_ha": calc_area_ha,
        "geometry_source": geometry_source
    }


def get_farm_gis_bundle(
    farm_id: int,
    user_id: int,
    org_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Retrieve comprehensive GIS data bundle for a farm:
    1. Farm perimeter boundary (Polygon / Point)
    2. Zones feature collection (Polygons / Points)
    3. Plots feature collection (Polygons with crop and health indicators)
    4. Diagnoses feature collection (Geolocated disease detection pins)
    5. Unlocated plots & unlocated zones list
    """
    farm = gari_farm_management.get_farm_ext(farm_id=farm_id, user_id=user_id, org_id=org_id)
    if not farm:
        raise PermissionError(f"Không có quyền truy cập dữ liệu GIS nông trại #{farm_id}.")

    # Get standard farm map from gari_farm_map
    map_data = gari_farm_map.get_farm_map_data(farm_id=farm_id, user_id=user_id, org_id=org_id)

    with get_connection() as conn:
        cursor = conn.cursor()

        # Query Zones
        cursor.execute("""
            SELECT id, name, code, zone_type, area_m2, area_hectare, latitude, longitude, boundary_geojson, geometry_source
            FROM farm_zones
            WHERE farm_id = ? AND archived_at IS NULL
            ORDER BY id ASC
        """, (farm_id,))
        zone_rows = [dict(r) for r in cursor.fetchall()]

        zone_features = []
        unlocated_zones = []

        for z in zone_rows:
            z_geom = None
            if z.get("boundary_geojson"):
                try:
                    z_geom = json.loads(z["boundary_geojson"])
                except Exception:
                    z_geom = None

            if not z_geom and z.get("latitude") is not None and z.get("longitude") is not None:
                z_geom = {"type": "Point", "coordinates": [z["longitude"], z["latitude"]]}

            z_props = {
                "id": z["id"],
                "farm_id": farm_id,
                "name": z["name"],
                "code": z.get("code"),
                "zone_type": z.get("zone_type"),
                "area_m2": z.get("area_m2"),
                "area_hectare": z.get("area_hectare"),
                "geometry_source": z.get("geometry_source") or "user_drawn"
            }

            if z_geom:
                zone_features.append({
                    "type": "Feature",
                    "id": f"zone_{z['id']}",
                    "geometry": z_geom,
                    "properties": z_props
                })
            else:
                unlocated_zones.append(z_props)

        # Query Geolocated Diagnoses linked to plots in this farm
        cursor.execute("""
            SELECT d.id, d.plot_id, d.crop_name, d.predicted_disease, d.confidence,
                   d.severity, d.diagnosis_status, d.created_at, d.image_path,
                   p.plot_name, p.latitude, p.longitude
            FROM diagnoses d
            JOIN farm_plots p ON d.plot_id = p.id
            WHERE p.farm_id = ? AND p.archived_at IS NULL
            ORDER BY d.id DESC
            LIMIT 50
        """, (farm_id,))
        diag_rows = [dict(r) for r in cursor.fetchall()]

        diagnosis_features = []
        for d in diag_rows:
            if d.get("latitude") is not None and d.get("longitude") is not None:
                diagnosis_features.append({
                    "type": "Feature",
                    "id": f"diag_{d['id']}",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [d["longitude"], d["latitude"]]
                    },
                    "properties": {
                        "id": d["id"],
                        "plot_id": d["plot_id"],
                        "plot_name": d["plot_name"],
                        "crop_name": d["crop_name"],
                        "predicted_disease": d["predicted_disease"],
                        "confidence": d["confidence"],
                        "severity": d["severity"],
                        "diagnosis_status": d["diagnosis_status"],
                        "created_at": d["created_at"],
                        "image_path": d["image_path"]
                    }
                })

    return {
        "success": True,
        "farm_id": farm_id,
        "farm": map_data["farm"],
        "zones_feature_collection": {
            "type": "FeatureCollection",
            "features": zone_features
        },
        "plots_feature_collection": map_data["plots_feature_collection"],
        "diagnoses_feature_collection": {
            "type": "FeatureCollection",
            "features": diagnosis_features
        },
        "unlocated_plots": map_data["unlocated_plots"],
        "unlocated_zones": unlocated_zones,
        "counts": {
            "total_zones": len(zone_rows),
            "located_zones": len(zone_features),
            "total_plots": map_data["total_plots"],
            "located_plots": map_data["located_plots_count"],
            "geolocated_diagnoses": len(diagnosis_features)
        }
    }


def search_gis_entities(
    user_id: int,
    org_id: Optional[int] = None,
    query: Optional[str] = None,
    crop: Optional[str] = None,
    province: Optional[str] = None,
    health_status: Optional[str] = None,
    has_coordinates_only: bool = False
) -> Dict[str, Any]:
    """
    Search and filter accessible farms and plots with spatial and metadata criteria.
    Enforces tenant boundaries.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Base accessible farm query
        farm_conditions = ["f.archived_at IS NULL"]
        farm_params: List[Any] = []

        if org_id:
            # Check user membership in org
            cursor.execute("""
                SELECT role FROM organization_members
                WHERE organization_id = ? AND user_id = ?
            """, (org_id, user_id))
            if not cursor.fetchone():
                raise PermissionError("Bạn không có quyền truy cập dữ liệu của tổ chức này.")
            farm_conditions.append("f.organization_id = ?")
            farm_params.append(org_id)
        else:
            # Personal farms or farms belonging to user's active organizations
            farm_conditions.append("""(
                f.user_id = ? OR f.organization_id IN (
                    SELECT organization_id FROM organization_members
                    WHERE user_id = ?
                )
            )""")
            farm_params.extend([user_id, user_id])

        if query:
            farm_conditions.append("(f.name LIKE ? OR f.code LIKE ? OR f.location LIKE ?)")
            q_like = f"%{query}%"
            farm_params.extend([q_like, q_like, q_like])

        if crop:
            farm_conditions.append("f.primary_crop LIKE ?")
            farm_params.append(f"%{crop}%")

        if province:
            farm_conditions.append("f.province LIKE ?")
            farm_params.append(f"%{province}%")

        if has_coordinates_only:
            farm_conditions.append("f.latitude IS NOT NULL AND f.longitude IS NOT NULL")

        where_clause = " AND ".join(farm_conditions)
        cursor.execute(f"""
            SELECT f.id, f.name, f.code, f.location, f.province, f.area_hectare,
                   f.primary_crop, f.latitude, f.longitude, f.organization_id, f.geometry_source
            FROM farms f
            WHERE {where_clause}
            ORDER BY f.id DESC
            LIMIT 50
        """, tuple(farm_params))
        farms = [dict(r) for r in cursor.fetchall()]

        # For matched farms, fetch located plots
        farm_ids = [f["id"] for f in farms]
        plots = []
        if farm_ids:
            placeholders = ",".join("?" for _ in farm_ids)
            plot_sql = f"""
                SELECT p.id, p.farm_id, p.plot_name, p.plot_code, p.crop_name, p.area_hectare,
                       p.latitude, p.longitude, p.boundary_geojson, p.boundary_color
                FROM farm_plots p
                WHERE p.farm_id IN ({placeholders}) AND p.archived_at IS NULL
            """
            plot_params: List[Any] = list(farm_ids)
            if crop:
                plot_sql += " AND p.crop_name LIKE ?"
                plot_params.append(f"%{crop}%")
            if has_coordinates_only:
                plot_sql += " AND p.latitude IS NOT NULL AND p.longitude IS NOT NULL"

            cursor.execute(plot_sql, tuple(plot_params))
            all_plots = [dict(r) for r in cursor.fetchall()]

            # Filter by health status if requested
            for p in all_plots:
                health = gari_farm_map.evaluate_plot_health_status(p["id"], conn)
                p.update(health)
                if not health_status or health["health_status"] == health_status:
                    plots.append(p)

    return {
        "success": True,
        "farms": farms,
        "plots": plots,
        "total_farms": len(farms),
        "total_plots": len(plots)
    }
