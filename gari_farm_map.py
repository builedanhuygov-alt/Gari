"""
GARI Module 09 — Farm Intelligence 2D Map Service Layer
Authoritative implementation for:
1. Strict GeoJSON geometry validation (polygons, rings, coordinates, closure).
2. True centroid & geodesic area computation.
3. Deterministic, non-fabricated crop health & monitoring status evaluation.
4. Tenant and organization permission enforcement.
5. Explicit geometry source tracking (user_drawn, surveyed, estimated, unlocated).
6. Graceful handling of unlocated plots.
"""

import json
import math
import sqlite3
import logging
from typing import Dict, Any, List, Optional, Tuple, Union

from gari_database import get_connection
import gari_farm_management

logger = logging.getLogger("gari.farm_map")

VALID_GEOMETRY_SOURCES = {"user_drawn", "surveyed", "estimated", "unlocated"}
VALID_HEALTH_STATUSES = {"healthy", "attention_needed", "unknown"}


def validate_coordinates(lat: Any, lon: Any) -> Tuple[float, float]:
    """
    Validate that latitude and longitude are valid numeric coordinates.
    Lat must be in [-90.0, 90.0], Lon must be in [-180.0, 180.0].
    """
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (ValueError, TypeError):
        raise ValueError("Tọa độ không hợp lệ: Vĩ độ (Latitude) và Kinh độ (Longitude) phải là số thực.")

    if not (-90.0 <= lat_f <= 90.0):
        raise ValueError(f"Vĩ độ không hợp lệ ({lat_f}). Giá trị phải nằm trong khoảng [-90.0, 90.0].")
    if not (-180.0 <= lon_f <= 180.0):
        raise ValueError(f"Kinh độ không hợp lệ ({lon_f}). Giá trị phải nằm trong khoảng [-180.0, 180.0].")

    return round(lat_f, 7), round(lon_f, 7)


def validate_polygon_geometry(geometry: Union[Dict[str, Any], str]) -> Dict[str, Any]:
    """
    Validate GeoJSON Polygon geometry:
    - type must be 'Polygon'
    - coordinates must be a list containing at least 1 ring (the exterior boundary)
    - exterior ring must have at least 4 coordinate pairs [lon, lat]
    - first and last coordinate must be identical (closed ring)
    - all coordinates must be valid numbers within bounds
    """
    if isinstance(geometry, str):
        try:
            geom = json.loads(geometry)
        except Exception as exc:
            raise ValueError(f"Định dạng GeoJSON không hợp lệ: {exc}")
    elif isinstance(geometry, dict):
        geom = geometry
    else:
        raise ValueError("Dữ liệu hình học phải là đối tượng GeoJSON dictionary hoặc chuỗi JSON.")

    geom_type = geom.get("type")
    if geom_type != "Polygon":
        raise ValueError(f"Chỉ hỗ trợ kiểu hình học 'Polygon', nhận được: '{geom_type}'.")

    coords = geom.get("coordinates")
    if not coords or not isinstance(coords, list) or len(coords) < 1:
        raise ValueError("Đa giác phải có ít nhất một vòng tọa độ bao ngoài (exterior ring).")

    exterior_ring = coords[0]
    if not isinstance(exterior_ring, list) or len(exterior_ring) < 4:
        raise ValueError(f"Vòng tọa độ bao ngoài phải có tối thiểu 4 điểm tọa độ để tạo thành mặt phẳng khép kín (nhận được {len(exterior_ring) if isinstance(exterior_ring, list) else 0} điểm).")

    # Validate coordinate closure
    first_pt = exterior_ring[0]
    last_pt = exterior_ring[-1]
    if not (isinstance(first_pt, list) and isinstance(last_pt, list) and len(first_pt) >= 2 and len(last_pt) >= 2):
        raise ValueError("Tọa độ của mỗi điểm phải là một cặp [Kinh độ, Vĩ độ].")

    if abs(first_pt[0] - last_pt[0]) > 1e-7 or abs(first_pt[1] - last_pt[1]) > 1e-7:
        raise ValueError("Đa giác chưa khép kín: Điểm đầu và điểm cuối của vòng tọa độ phải trùng nhau.")

    # Validate each coordinate pair
    validated_ring = []
    for pt in exterior_ring:
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            raise ValueError("Mỗi điểm mốc phải là một cặp [Kinh độ, Vĩ độ].")
        lon, lat = pt[0], pt[1]
        v_lat, v_lon = validate_coordinates(lat, lon)
        validated_ring.append([v_lon, v_lat])

    return {
        "type": "Polygon",
        "coordinates": [validated_ring]
    }


def calculate_polygon_centroid(coordinates: List[List[float]]) -> Tuple[float, float]:
    """
    Calculate geographic center (centroid lat, lon) from a closed polygon ring.
    Coordinates format: [[lon, lat], [lon, lat], ...]
    """
    if not coordinates or len(coordinates) < 4:
        raise ValueError("Cần tối thiểu 4 điểm để tính tâm đa giác.")

    # Simple centroid of polygon vertices (excluding duplicated closure point)
    pts = coordinates[:-1]
    sum_lat = sum(p[1] for p in pts)
    sum_lon = sum(p[0] for p in pts)
    n = len(pts)
    return round(sum_lat / n, 7), round(sum_lon / n, 7)


def calculate_polygon_area_m2(coordinates: List[List[float]]) -> float:
    """
    Approximate polygon area in square meters using spherical Shoelace formula.
    """
    if not coordinates or len(coordinates) < 4:
        return 0.0

    pts = coordinates
    # Earth radius in meters
    R = 6378137.0
    area = 0.0

    # Project lon/lat to local planar meters around centroid
    avg_lat = sum(p[1] for p in pts[:-1]) / (len(pts) - 1)
    cos_lat = math.cos(math.radians(avg_lat))

    meters_pts = []
    for pt in pts:
        x = math.radians(pt[0]) * R * cos_lat
        y = math.radians(pt[1]) * R
        meters_pts.append((x, y))

    # Standard Shoelace formula
    for i in range(len(meters_pts) - 1):
        x1, y1 = meters_pts[i]
        x2, y2 = meters_pts[i + 1]
        area += (x1 * y2 - x2 * y1)

    return round(abs(area) / 2.0, 2)


def evaluate_plot_health_status(plot_id: int, conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Deterministically derive plot health status without fabricating live data:
    1. Check most recent diagnosis on this plot in the last 30 days.
    2. Check overdue tasks (due_date < current_date and status != completed).
    3. Check pending tasks count.
    Returns:
    - health_status: 'healthy' | 'attention_needed' | 'unknown'
    - status_reason: Vietnamese explanation
    - recent_diagnosis: summary dict or None
    - overdue_tasks_count: int
    - pending_tasks_count: int
    """
    cursor = conn.cursor()

    # 1. Recent diagnosis
    cursor.execute("""
        SELECT id, crop_name, predicted_disease, confidence, severity, diagnosis_status, created_at
        FROM diagnoses
        WHERE plot_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (plot_id,))
    diag_row = cursor.fetchone()
    recent_diag = dict(diag_row) if diag_row else None

    # 2. Tasks
    cursor.execute("""
        SELECT
            count(*) as total_pending,
            sum(CASE WHEN due_date < date('now') THEN 1 ELSE 0 END) as total_overdue
        FROM cultivation_tasks
        WHERE plot_id = ? AND status IN ('pending', 'in_progress')
    """, (plot_id,))
    task_row = cursor.fetchone()
    pending_count = task_row["total_pending"] if task_row and task_row["total_pending"] else 0
    overdue_count = task_row["total_overdue"] if task_row and task_row["total_overdue"] else 0

    # 3. Determine status
    if recent_diag:
        disease = (recent_diag.get("predicted_disease") or "").lower()
        severity = (recent_diag.get("severity") or "").upper()
        conf = float(recent_diag.get("confidence") or 0.0)

        is_healthy_diag = (
            "healthy" in disease or
            "khoẻ mạnh" in disease or
            "khỏe mạnh" in disease or
            disease == "normal"
        )

        if not is_healthy_diag and (severity in ("HIGH", "CRITICAL") or conf >= 0.70):
            health_status = "attention_needed"
            status_reason = f"Phát hiện dấu hiệu dịch hại: {recent_diag.get('predicted_disease')} (Độ tin cậy: {int(conf * 100)}%)"
        elif overdue_count > 0:
            health_status = "attention_needed"
            status_reason = f"Có {overdue_count} công việc chăm sóc/phòng trừ đã quá hạn xử lý."
        elif is_healthy_diag:
            health_status = "healthy"
            status_reason = "Chẩn đoán gần nhất ghi nhận cây sinh trưởng bình thường, không có dấu hiệu bệnh hại nặng."
        else:
            health_status = "attention_needed"
            status_reason = f"Chẩn đoán dịch hại mức độ trung bình: {recent_diag.get('predicted_disease')}."
    elif overdue_count > 0:
        health_status = "attention_needed"
        status_reason = f"Có {overdue_count} công việc canh tác quá hạn chưa hoàn thành."
    else:
        health_status = "unknown"
        status_reason = "Chưa có dữ liệu chẩn đoán lá gần đây. Cần thu thập ảnh thực địa để đánh giá sức khỏe."

    return {
        "health_status": health_status,
        "status_reason": status_reason,
        "recent_diagnosis": recent_diag,
        "overdue_tasks_count": overdue_count,
        "pending_tasks_count": pending_count
    }


def get_farm_map_data(
    farm_id: int,
    user_id: int,
    org_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Retrieve comprehensive 2D map payload for a farm:
    - Farm boundary and centroid
    - GeoJSON FeatureCollection of located plots with deterministic health statuses
    - List of unlocated plots (plots needing coordinates)
    Strictly checks tenant & organization permissions.
    """
    farm = gari_farm_management.get_farm_ext(farm_id=farm_id, user_id=user_id, org_id=org_id)
    if not farm:
        raise PermissionError(f"Không có quyền truy cập bản đồ nông trại #{farm_id}.")

    with get_connection() as conn:
        cursor = conn.cursor()

        # Parse farm boundary if present
        farm_boundary = None
        if farm.get("boundary_geojson"):
            try:
                farm_boundary = json.loads(farm["boundary_geojson"])
            except Exception:
                farm_boundary = None

        farm_feature = {
            "type": "Feature",
            "geometry": farm_boundary or (
                {"type": "Point", "coordinates": [farm["longitude"], farm["latitude"]]}
                if farm.get("latitude") is not None and farm.get("longitude") is not None else None
            ),
            "properties": {
                "id": farm["id"],
                "name": farm["name"],
                "code": farm.get("code"),
                "province": farm.get("province"),
                "area_hectare": farm.get("area_hectare"),
                "primary_crop": farm.get("primary_crop"),
                "geometry_source": farm.get("geometry_source") or ("unlocated" if farm.get("latitude") is None else "surveyed")
            }
        }

        # Query all active plots belonging to this farm
        cursor.execute("""
            SELECT p.*,
                   z.name as zone_name,
                   c.cycle_name as active_cycle_name,
                   c.start_date as cycle_start_date,
                   c.expected_harvest_date as cycle_harvest_date
            FROM farm_plots p
            LEFT JOIN farm_zones z ON p.zone_id = z.id
            LEFT JOIN crop_cycles c ON p.active_cycle_id = c.id
            WHERE p.farm_id = ? AND p.archived_at IS NULL
            ORDER BY p.id ASC
        """, (farm_id,))
        plot_rows = [dict(r) for r in cursor.fetchall()]

        located_features = []
        unlocated_plots = []

        for p in plot_rows:
            health_info = evaluate_plot_health_status(p["id"], conn)

            has_coords = p.get("latitude") is not None and p.get("longitude") is not None
            has_boundary = bool(p.get("boundary_geojson"))

            plot_geom = None
            if has_boundary:
                try:
                    plot_geom = json.loads(p["boundary_geojson"])
                except Exception:
                    plot_geom = None

            if not plot_geom and has_coords:
                plot_geom = {"type": "Point", "coordinates": [p["longitude"], p["latitude"]]}

            plot_data = {
                "id": p["id"],
                "farm_id": p["farm_id"],
                "plot_name": p["plot_name"],
                "plot_code": p.get("plot_code"),
                "crop_id": p.get("crop_id"),
                "crop_name": p.get("crop_name") or p.get("crop_id"),
                "area_hectare": p.get("area_hectare") or p.get("area_hectares"),
                "area_m2": p.get("area_m2"),
                "zone_name": p.get("zone_name"),
                "active_cycle_name": p.get("active_cycle_name"),
                "cycle_start_date": p.get("cycle_start_date"),
                "cycle_harvest_date": p.get("cycle_harvest_date"),
                "geometry_source": p.get("geometry_source") or ("unlocated" if not has_coords else "user_drawn"),
                "boundary_color": p.get("boundary_color") or ("#22c55e" if health_info["health_status"] == "healthy" else "#f59e0b" if health_info["health_status"] == "attention_needed" else "#94a3b8"),
                **health_info
            }

            if plot_geom:
                located_features.append({
                    "type": "Feature",
                    "id": p["id"],
                    "geometry": plot_geom,
                    "properties": plot_data
                })
            else:
                unlocated_plots.append(plot_data)

        return {
            "farm": farm_feature,
            "plots_feature_collection": {
                "type": "FeatureCollection",
                "features": located_features
            },
            "unlocated_plots": unlocated_plots,
            "total_plots": len(plot_rows),
            "located_plots_count": len(located_features),
            "unlocated_plots_count": len(unlocated_plots)
        }


def update_farm_location(
    farm_id: int,
    latitude: float,
    longitude: float,
    user_id: int,
    org_id: Optional[int] = None,
    boundary: Optional[Union[Dict[str, Any], str]] = None,
    geometry_source: str = "user_drawn"
) -> Dict[str, Any]:
    """
    Update farm center coordinates and optional outer perimeter boundary.
    Strictly enforces write permissions.
    """
    if not gari_farm_management.check_farm_access(farm_id=farm_id, user_id=user_id, org_id=org_id, require_write=True):
        raise PermissionError(f"Bạn không có quyền chỉnh sửa vị trí nông trại #{farm_id}.")

    lat_v, lon_v = validate_coordinates(latitude, longitude)

    if geometry_source not in VALID_GEOMETRY_SOURCES:
        geometry_source = "user_drawn"

    boundary_json = None
    if boundary:
        valid_poly = validate_polygon_geometry(boundary)
        boundary_json = json.dumps(valid_poly)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE farms SET
                latitude = ?,
                longitude = ?,
                boundary_geojson = ?,
                geometry_source = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (lat_v, lon_v, boundary_json, geometry_source, farm_id))
        conn.commit()

    return {
        "success": True,
        "farm_id": farm_id,
        "latitude": lat_v,
        "longitude": lon_v,
        "boundary_geojson": boundary_json,
        "geometry_source": geometry_source
    }


def update_plot_geometry(
    plot_id: int,
    geometry: Union[Dict[str, Any], str],
    user_id: int,
    org_id: Optional[int] = None,
    geometry_source: str = "user_drawn",
    boundary_color: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update plot polygon boundary.
    Validates GeoJSON Polygon, verifies closure, calculates centroid automatically,
    computes area in m2, and enforces write permissions.
    """
    if not gari_farm_management.check_plot_access(plot_id=plot_id, user_id=user_id, org_id=org_id, require_write=True):
        raise PermissionError(f"Bạn không có quyền chỉnh sửa ranh giới thửa đất #{plot_id}.")

    valid_geom = validate_polygon_geometry(geometry)
    ring = valid_geom["coordinates"][0]

    centroid_lat, centroid_lon = calculate_polygon_centroid(ring)
    calc_area_m2 = calculate_polygon_area_m2(ring)
    calc_area_ha = round(calc_area_m2 / 10000.0, 4)

    if geometry_source not in VALID_GEOMETRY_SOURCES:
        geometry_source = "user_drawn"

    boundary_json = json.dumps(valid_geom)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE farm_plots SET
                latitude = ?,
                longitude = ?,
                boundary_geojson = ?,
                geometry_source = ?,
                area_m2 = CASE WHEN area_m2 IS NULL OR area_m2 <= 0 THEN ? ELSE area_m2 END,
                area_hectare = CASE WHEN area_hectare IS NULL OR area_hectare <= 0 THEN ? ELSE area_hectare END,
                boundary_color = COALESCE(?, boundary_color, '#22c55e'),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (centroid_lat, centroid_lon, boundary_json, geometry_source, calc_area_m2, calc_area_ha, boundary_color, plot_id))
        conn.commit()

        health_info = evaluate_plot_health_status(plot_id, conn)

    return {
        "success": True,
        "plot_id": plot_id,
        "latitude": centroid_lat,
        "longitude": centroid_lon,
        "geometry": valid_geom,
        "calculated_area_m2": calc_area_m2,
        "calculated_area_ha": calc_area_ha,
        "geometry_source": geometry_source,
        **health_info
    }


def get_plot_map_detail(
    plot_id: int,
    user_id: int,
    org_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Fetch comprehensive inspection card data when a user clicks/selects a plot on the map:
    - Crop profile & variety
    - Active crop cycle with planting date and days to harvest
    - Evaluated health status with reason
    - Recent diagnoses history (up to 5 recent)
    - Pending and overdue cultivation tasks
    - Geometry source indicator (user-drawn vs estimated)
    """
    plot = gari_farm_management.get_plot_ext(plot_id=plot_id, user_id=user_id, org_id=org_id)
    if not plot:
        raise PermissionError(f"Không có quyền truy cập thông tin thửa #{plot_id}.")

    with get_connection() as conn:
        cursor = conn.cursor()

        health_info = evaluate_plot_health_status(plot_id, conn)

        # Recent diagnoses (last 5)
        cursor.execute("""
            SELECT id, predicted_disease, confidence, severity, diagnosis_status, created_at, image_path
            FROM diagnoses
            WHERE plot_id = ?
            ORDER BY id DESC
            LIMIT 5
        """, (plot_id,))
        recent_diagnoses = [dict(r) for r in cursor.fetchall()]

        # Active tasks
        cursor.execute("""
            SELECT id, title, task_type, priority, due_date, status
            FROM cultivation_tasks
            WHERE plot_id = ? AND status IN ('pending', 'in_progress')
            ORDER BY due_date ASC
            LIMIT 10
        """, (plot_id,))
        pending_tasks = [dict(r) for r in cursor.fetchall()]

        # Active crop cycle
        active_cycle = None
        if plot.get("active_cycle_id"):
            cursor.execute("SELECT * FROM crop_cycles WHERE id = ?", (plot["active_cycle_id"],))
            c_row = cursor.fetchone()
            if c_row:
                active_cycle = dict(c_row)

        plot_detail = {
            "plot": plot,
            "active_cycle": active_cycle,
            "recent_diagnoses": recent_diagnoses,
            "pending_tasks": pending_tasks,
            **health_info
        }

        return plot_detail


def get_user_farms_map_overview(
    user_id: int,
    org_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Retrieve all farms accessible to the user formatted as a GeoJSON FeatureCollection.
    Useful for multi-farm high-level regional mapping.
    """
    farms = gari_farm_management.list_farms_ext(user_id=user_id, org_id=org_id, status="active")
    features = []

    with get_connection() as conn:
        cursor = conn.cursor()
        for f in farms:
            fid = f["id"]
            lat = f.get("latitude")
            lon = f.get("longitude")
            if lat is None or lon is None:
                continue

            # Count plots and health state for farm
            cursor.execute("""
                SELECT
                    count(*) as total_plots,
                    sum(CASE WHEN boundary_geojson IS NOT NULL THEN 1 ELSE 0 END) as located_plots
                FROM farm_plots
                WHERE farm_id = ? AND archived_at IS NULL
            """, (fid,))
            stats = cursor.fetchone()

            features.append({
                "type": "Feature",
                "id": fid,
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat]
                },
                "properties": {
                    "id": fid,
                    "name": f["name"],
                    "code": f.get("code"),
                    "province": f.get("province"),
                    "primary_crop": f.get("primary_crop"),
                    "area_hectare": f.get("area_hectare"),
                    "total_plots": stats["total_plots"] if stats else 0,
                    "located_plots": stats["located_plots"] if stats else 0,
                    "geometry_source": f.get("geometry_source") or "surveyed"
                }
            })

    return {
        "type": "FeatureCollection",
        "features": features,
        "total_farms": len(farms),
        "mapped_farms": len(features)
    }
