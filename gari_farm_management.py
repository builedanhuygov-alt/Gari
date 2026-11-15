"""
GARI AI LAB — Module 04: Agricultural Data Hierarchy & Farm Management
File: gari_farm_management.py

Provides structured, extensible agricultural data system supporting:
Organization -> Farm -> Zone -> Plot -> Crop Cycle -> Plant / Plant Group -> Observations, Diagnoses & Timeline.
Includes area conversions, parent-child integrity validation, idempotency, archiving,
summaries, and multi-tenant access control.
"""

import json
import logging
import math
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import gari_database
import gari_b2b

logger = logging.getLogger("gari_farm_management")

# ---------------------------------------------------------------------------
# Area Unit Conversion & Normalization
# ---------------------------------------------------------------------------
# Standard Vietnamese & Metric Area Unit conversions to Square Meters (m²)
AREA_CONVERSIONS_TO_M2: Dict[str, float] = {
    "m2": 1.0,
    "sqm": 1.0,
    "ha": 10000.0,
    "hectare": 10000.0,
    "hectares": 10000.0,
    "sao_bac_bo": 360.0,     # 1 sào Bắc Bộ = 360 m²
    "sao_trung_bo": 500.0,   # 1 sào Trung Bộ = 500 m²
    "sao_nam_bo": 1000.0,    # 1 sào Nam Bộ (1 công) = 1,000 m²
    "cong": 1000.0,          # 1 công Nam Bộ = 1,000 m²
    "mau_bac_bo": 3600.0,    # 1 mẫu Bắc Bộ = 10 sào = 3,600 m²
    "mau_trung_bo": 5000.0,  # 1 mẫu Trung Bộ = 10 sào = 5,000 m²
    "mau_nam_bo": 10000.0,   # 1 mẫu Nam Bộ = 10 công = 10,000 m² = 1 ha
}

SUPPORTED_AREA_UNITS = list(AREA_CONVERSIONS_TO_M2.keys())


def normalize_area(value: Union[int, float, str, None], unit: Optional[str] = "ha") -> Tuple[float, float, str]:
    """
    Normalize any supported area input to (area_m2, area_hectare, standard_unit).
    Default unit is 'ha'. If value is None or <= 0, defaults to (10000.0, 1.0, 'ha').
    """
    if value is None or value == "":
        return 10000.0, 1.0, "ha"

    try:
        val_float = float(value)
    except (ValueError, TypeError):
        val_float = 1.0

    if val_float <= 0:
        val_float = 1.0

    clean_unit = (unit or "ha").strip().lower()
    factor = AREA_CONVERSIONS_TO_M2.get(clean_unit, 10000.0)

    area_m2 = round(val_float * factor, 2)
    area_ha = round(area_m2 / 10000.0, 4)

    return area_m2, area_ha, clean_unit


def format_area_display(area_m2: float, preferred_unit: str = "ha") -> str:
    """Format area for user-friendly Vietnamese display."""
    if preferred_unit in ("ha", "hectare", "hectares"):
        ha = round(area_m2 / 10000.0, 2)
        return f"{ha} ha"
    elif preferred_unit in ("cong", "sao_nam_bo"):
        cong = round(area_m2 / 1000.0, 1)
        return f"{cong} công"
    elif preferred_unit == "sao_bac_bo":
        sao = round(area_m2 / 360.0, 1)
        return f"{sao} sào Bắc Bộ"
    else:
        return f"{area_m2:,.0f} m²"


# ---------------------------------------------------------------------------
# Authorization & Access Control Helpers
# ---------------------------------------------------------------------------
def check_farm_access(farm_id: int, user_id: int, org_id: Optional[int] = None, require_write: bool = False) -> bool:
    """
    Verify whether user or organization has read/write permission to the farm.
    """
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, organization_id, status FROM farms WHERE id = ?", (farm_id,))
        row = cursor.fetchone()
        if not row:
            return False

        farm_user_id = row["user_id"]
        farm_org_id = row["organization_id"]

        # 1. Direct owner
        if farm_user_id == user_id:
            return True

        # 2. Organization member check
        target_org = org_id or farm_org_id
        if target_org:
            role = gari_b2b.get_member_role(target_org, user_id)
            if role:
                if require_write:
                    return role in ("owner", "admin")
                return True

    return False


def check_plot_access(plot_id: int, user_id: int, org_id: Optional[int] = None, require_write: bool = False) -> bool:
    """
    Verify whether user or organization has read/write permission to the plot.
    """
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, farm_id, user_id, organization_id FROM farm_plots WHERE id = ?", (plot_id,))
        plot = cursor.fetchone()
        if not plot:
            return False

        if plot["user_id"] == user_id:
            return True

        target_org = org_id or plot["organization_id"]
        if target_org:
            role = gari_b2b.get_member_role(target_org, user_id)
            if role:
                if require_write:
                    return role in ("owner", "admin")
                return True

        # Check farm-level ownership
        if plot["farm_id"]:
            return check_farm_access(plot["farm_id"], user_id, org_id, require_write)

    return False


# ---------------------------------------------------------------------------
# Farm Management (Create, Edit, Archive, Summary)
# ---------------------------------------------------------------------------
def create_farm_ext(data: Dict[str, Any], user_id: int, org_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Create a new farm with normalized area, optional code, and organization scope.
    Validates organization membership and avoids duplicates.
    """
    raw_name = (data.get("name") or "").strip()
    if not raw_name:
        raise ValueError("Tên nông trại không được để trống.")

    target_org = org_id or data.get("organization_id")
    if target_org:
        role = gari_b2b.get_member_role(target_org, user_id)
        if not role:
            raise PermissionError("Bạn không thuộc tổ chức này để tạo nông trại.")

        # Check farm limit per organization plan
        org_detail = gari_b2b.get_organization_detail(target_org)
        if org_detail:
            org_plan = org_detail.get("plan_id", "pilot")
            org_farm_limits = {
                "pilot": 2,
                "free": 1,
                "personal": 2,
                "pro": 5,
                "team": 10,
                "business": 10,
                "enterprise": 1000
            }
            max_org_farms = org_farm_limits.get(org_plan, 2)
            with gari_database.get_connection() as conn_chk:
                cur_chk = conn_chk.cursor()
                cur_chk.execute("SELECT COUNT(*) FROM farms WHERE organization_id = ? AND status != 'archived'", (target_org,))
                org_farm_cnt = cur_chk.fetchone()[0]
                if org_farm_cnt >= max_org_farms:
                    raise ValueError(
                        f"Tổ chức đã đạt giới hạn tối đa {max_org_farms} nông trại của gói dịch vụ ({org_plan}). "
                        f"Vui lòng nâng cấp gói để tạo thêm nông trại."
                    )

    input_area = data.get("area_m2") or data.get("area_hectare") or data.get("area") or 1.0
    input_unit = data.get("area_unit") or "ha"
    area_m2, area_ha, standard_unit = normalize_area(input_area, input_unit)

    farm_code = (data.get("code") or "").strip() or None
    is_test_flag = 1 if (
        os.environ.get("APP_ENV") == "test"
        or "test" in raw_name.lower()
        or bool(data.get("is_test"))
    ) else 0

    # Auto-resolve coordinates and altitude from province if not explicitly provided
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    altitude_m = data.get("altitude_m")
    if (latitude is None or longitude is None) and data.get("province"):
        try:
            import gari_smart_calendar
            prov_match = gari_smart_calendar.lookup_province(data["province"])
            if prov_match:
                if latitude is None:
                    latitude = prov_match["lat"]
                if longitude is None:
                    longitude = prov_match["lon"]
                if altitude_m is None:
                    altitude_m = prov_match.get("altitude_m", 0.0)
        except Exception:
            pass

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        # Idempotency / Duplicate Check
        cursor.execute("""
            SELECT id FROM farms
            WHERE user_id = ? AND name = ? AND (organization_id IS ? OR organization_id = ?) AND status != 'archived'
        """, (user_id, raw_name, target_org, target_org))
        existing = cursor.fetchone()
        if existing:
            # If already created recently, return existing to prevent double submission
            return get_farm_ext(existing["id"], user_id=user_id, org_id=target_org)  # type: ignore

        cursor.execute("""
            INSERT INTO farms (
                user_id, organization_id, name, code, location, province,
                area_m2, area_hectare, area_unit, primary_crop, variety,
                soil_type, irrigation_type, notes, status, is_test,
                latitude, longitude, altitude_m, terrain, water_source,
                planting_date, tree_age_years, growth_stage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            target_org,
            raw_name,
            farm_code,
            data.get("location", ""),
            data.get("province", ""),
            area_m2,
            area_ha,
            standard_unit,
            data.get("primary_crop", "Tomato"),
            data.get("variety", ""),
            data.get("soil_type", ""),
            data.get("irrigation_type", ""),
            data.get("notes", ""),
            data.get("status", "active"),
            is_test_flag,
            latitude,
            longitude,
            altitude_m or 0.0,
            data.get("terrain", "Bằng phẳng"),
            data.get("water_source", "Nước ngầm / Giếng khoan"),
            data.get("planting_date"),
            float(data.get("tree_age_years") or 1.0),
            data.get("growth_stage", "Kiến thiết cơ bản")
        ))
        conn.commit()
        new_farm_id = cursor.lastrowid

    return get_farm_ext(new_farm_id, user_id=user_id, org_id=target_org)  # type: ignore


def update_farm_ext(farm_id: int, data: Dict[str, Any], user_id: int, org_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Update farm metadata with access validation."""
    if not check_farm_access(farm_id, user_id, org_id, require_write=True):
        raise PermissionError("Bạn không có quyền chỉnh sửa nông trại này.")

    area_m2 = None
    area_ha = None
    standard_unit = None
    if any(k in data for k in ("area_m2", "area_hectare", "area", "area_unit")):
        input_area = data.get("area_m2") or data.get("area_hectare") or data.get("area")
        input_unit = data.get("area_unit")
        area_m2, area_ha, standard_unit = normalize_area(input_area, input_unit)

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE farms
            SET name = COALESCE(?, name),
                code = COALESCE(?, code),
                location = COALESCE(?, location),
                province = COALESCE(?, province),
                area_m2 = COALESCE(?, area_m2),
                area_hectare = COALESCE(?, area_hectare),
                area_unit = COALESCE(?, area_unit),
                primary_crop = COALESCE(?, primary_crop),
                variety = COALESCE(?, variety),
                soil_type = COALESCE(?, soil_type),
                irrigation_type = COALESCE(?, irrigation_type),
                status = COALESCE(?, status),
                notes = COALESCE(?, notes),
                latitude = COALESCE(?, latitude),
                longitude = COALESCE(?, longitude),
                altitude_m = COALESCE(?, altitude_m),
                terrain = COALESCE(?, terrain),
                water_source = COALESCE(?, water_source),
                planting_date = COALESCE(?, planting_date),
                tree_age_years = COALESCE(?, tree_age_years),
                growth_stage = COALESCE(?, growth_stage),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            data.get("name"),
            data.get("code"),
            data.get("location"),
            data.get("province"),
            area_m2,
            area_ha,
            standard_unit,
            data.get("primary_crop"),
            data.get("variety"),
            data.get("soil_type"),
            data.get("irrigation_type"),
            data.get("status"),
            data.get("notes"),
            data.get("latitude"),
            data.get("longitude"),
            data.get("altitude_m"),
            data.get("terrain"),
            data.get("water_source"),
            data.get("planting_date"),
            float(data["tree_age_years"]) if data.get("tree_age_years") is not None else None,
            data.get("growth_stage"),
            farm_id
        ))
        conn.commit()

    return get_farm_ext(farm_id, user_id=user_id, org_id=org_id)


def archive_farm(farm_id: int, user_id: int, org_id: Optional[int] = None, cascade: bool = True) -> bool:
    """Archive farm and optionally its child zones and plots."""
    if not check_farm_access(farm_id, user_id, org_id, require_write=True):
        raise PermissionError("Bạn không có quyền lưu trữ nông trại này.")

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE farms
            SET status = 'archived', archived_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (farm_id,))
        if cascade:
            cursor.execute("UPDATE farm_zones SET status = 'archived', archived_at = CURRENT_TIMESTAMP WHERE farm_id = ?", (farm_id,))
            cursor.execute("UPDATE farm_plots SET status = 'archived', archived_at = CURRENT_TIMESTAMP WHERE farm_id = ?", (farm_id,))
        conn.commit()
        return cursor.rowcount > 0


def unarchive_farm(farm_id: int, user_id: int, org_id: Optional[int] = None) -> bool:
    """Restore archived farm."""
    if not check_farm_access(farm_id, user_id, org_id, require_write=True):
        raise PermissionError("Bạn không có quyền khôi phục nông trại này.")

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE farms
            SET status = 'active', archived_at = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (farm_id,))
        conn.commit()
        return cursor.rowcount > 0


def delete_farm_ext(farm_id: int, user_id: int, org_id: Optional[int] = None) -> bool:
    """Delete a farm and cascade deletion to zones and plots."""
    if not check_farm_access(farm_id, user_id, org_id, require_write=True):
        raise PermissionError("Bạn không có quyền xóa nông trại này.")

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM farms WHERE id = ?", (farm_id,))
        conn.commit()
        return cursor.rowcount > 0


def get_farm_ext(farm_id: int, user_id: Optional[int] = None, org_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve comprehensive farm profile including summary metrics, zones, plots, and health indicators.
    """
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM farms WHERE id = ?", (farm_id,))
        row = cursor.fetchone()
        if not row:
            return None

        farm = dict(row)

        # Authorization check if user_id supplied
        if user_id is not None:
            if not check_farm_access(farm_id, user_id, org_id):
                return None

        # Fetch Zones
        cursor.execute("""
            SELECT z.*,
                   (SELECT COUNT(*) FROM farm_plots WHERE zone_id = z.id AND status != 'archived') as plots_count,
                   (SELECT COUNT(*) FROM plot_plants WHERE zone_id = z.id AND status != 'archived') as plants_count
            FROM farm_zones z
            WHERE z.farm_id = ? AND z.status != 'archived'
            ORDER BY z.id ASC
        """, (farm_id,))
        farm["zones"] = [dict(r) for r in cursor.fetchall()]

        # Fetch Plots
        cursor.execute("""
            SELECT p.*,
                   z.name as zone_name,
                   c.cycle_name as active_cycle_name,
                   c.crop_name as active_cycle_crop,
                   (SELECT COUNT(*) FROM plot_plants WHERE plot_id = p.id AND status != 'archived') as plants_count,
                   (SELECT COUNT(*) FROM diagnoses WHERE (plot_id = p.id OR farm_plot_id = p.id)) as diagnoses_count
            FROM farm_plots p
            LEFT JOIN farm_zones z ON p.zone_id = z.id
            LEFT JOIN crop_cycles c ON p.active_cycle_id = c.id
            WHERE p.farm_id = ? AND p.status != 'archived'
            ORDER BY p.id ASC
        """, (farm_id,))
        farm["plots"] = [dict(r) for r in cursor.fetchall()]

        # Farm Aggregated Summary Metrics
        cursor.execute("""
            SELECT
                COUNT(DISTINCT p.id) as total_plots,
                COALESCE(SUM(p.area_m2), 0.0) as plots_total_area_m2,
                (SELECT COUNT(*) FROM plot_plants pl JOIN farm_plots p2 ON pl.plot_id = p2.id WHERE p2.farm_id = ? AND pl.status != 'archived') as total_plants,
                (SELECT COUNT(*) FROM diagnoses d WHERE d.farm_id = ?) as total_diagnoses,
                (SELECT COUNT(*) FROM diagnoses d WHERE d.farm_id = ? AND (d.severity = 'HEALTHY' OR d.severity = 'NORMAL')) as healthy_diagnoses,
                (SELECT COUNT(*) FROM diagnoses d WHERE d.farm_id = ? AND d.severity = 'HIGH') as alert_diagnoses,
                (SELECT COUNT(*) FROM cultivation_tasks t WHERE t.farm_id = ? AND t.status != 'completed') as pending_tasks
            FROM farm_plots p
            WHERE p.farm_id = ? AND p.status != 'archived'
        """, (farm_id, farm_id, farm_id, farm_id, farm_id, farm_id))
        metrics = dict(cursor.fetchone() or {})
        farm["summary"] = {
            "total_zones": len(farm["zones"]),
            "total_plots": metrics.get("total_plots", 0),
            "plots_total_area_m2": metrics.get("plots_total_area_m2", 0.0),
            "total_plants": metrics.get("total_plants", 0),
            "total_diagnoses": metrics.get("total_diagnoses", 0),
            "healthy_diagnoses": metrics.get("healthy_diagnoses", 0),
            "alert_diagnoses": metrics.get("alert_diagnoses", 0),
            "pending_tasks": metrics.get("pending_tasks", 0)
        }

        return farm


def list_farms_ext(
    user_id: Optional[int] = None,
    org_id: Optional[int] = None,
    status: Optional[str] = "active",
    include_test: bool = False
) -> List[Dict[str, Any]]:
    """List accessible farms with metrics."""
    where_clauses = []
    params: List[Any] = []

    if status and status != "all":
        where_clauses.append("f.status = ?")
        params.append(status)

    if not include_test and os.environ.get("APP_ENV") != "test":
        where_clauses.append("(f.is_test = 0 OR f.is_test IS NULL)")

    if org_id is not None:
        if user_id is not None:
            user_role = gari_b2b.get_member_role(org_id, user_id)
            user_record = gari_auth.get_user_by_id(user_id)
            is_admin = bool(user_record and (user_record.get("is_admin") or user_record.get("is_host_admin")))
            if not user_role and not is_admin:
                return []
        where_clauses.append("f.organization_id = ?")
        params.append(org_id)
    elif user_id is not None:
        user_orgs = gari_b2b.get_user_organizations(user_id)
        org_ids = [o["id"] for o in user_orgs]
        if org_ids:
            placeholders = ",".join("?" for _ in org_ids)
            where_clauses.append(f"(f.user_id = ? OR f.organization_id IN ({placeholders}))")
            params.append(user_id)
            params.extend(org_ids)
        else:
            where_clauses.append("f.user_id = ?")
            params.append(user_id)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT f.*,
                   (SELECT COUNT(*) FROM farm_zones WHERE farm_id = f.id AND status != 'archived') as total_zones,
                   (SELECT COUNT(*) FROM farm_plots WHERE farm_id = f.id AND status != 'archived') as total_plots,
                   (SELECT COUNT(*) FROM diagnoses WHERE farm_id = f.id) as total_diagnoses
            FROM farms f
            {where_sql}
            ORDER BY f.id DESC
        """, params)
        return [dict(r) for r in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Zone Management (Subdivisions within Farm)
# ---------------------------------------------------------------------------
def create_zone(data: Dict[str, Any], user_id: int, org_id: Optional[int] = None) -> Dict[str, Any]:
    """Create a new zone within an authorized farm."""
    farm_id = data.get("farm_id")
    if not farm_id:
        raise ValueError("farm_id là bắt buộc để tạo khu vực/zone.")

    if not check_farm_access(farm_id, user_id, org_id, require_write=True):
        raise PermissionError("Bạn không có quyền quản lý khu vực trong nông trại này.")

    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Tên khu vực không được để trống.")

    code = (data.get("code") or "").strip() or None
    zone_type = data.get("zone_type") or "open_field"
    area_m2, area_ha, unit = normalize_area(data.get("area_m2") or data.get("area_hectare") or data.get("area"), data.get("area_unit"))

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        # Prevent duplicate zone name in same farm
        cursor.execute("SELECT id FROM farm_zones WHERE farm_id = ? AND name = ? AND status != 'archived'", (farm_id, name))
        existing = cursor.fetchone()
        if existing:
            return get_zone(existing["id"], user_id=user_id, org_id=org_id)  # type: ignore

        cursor.execute("""
            INSERT INTO farm_zones (
                farm_id, name, code, zone_type, area_m2, area_hectare, area_unit, description, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            farm_id,
            name,
            code,
            zone_type,
            area_m2,
            area_ha,
            unit,
            data.get("description", ""),
            data.get("status", "active")
        ))
        conn.commit()
        zone_id = cursor.lastrowid

    return get_zone(zone_id, user_id=user_id, org_id=org_id)  # type: ignore


def get_zone(zone_id: int, user_id: Optional[int] = None, org_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Retrieve zone details with plot and plant counts."""
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT z.*, f.name as farm_name, f.user_id as farm_user_id, f.organization_id as farm_org_id
            FROM farm_zones z
            JOIN farms f ON z.farm_id = f.id
            WHERE z.id = ?
        """, (zone_id,))
        row = cursor.fetchone()
        if not row:
            return None

        zone = dict(row)
        if user_id is not None:
            if not check_farm_access(zone["farm_id"], user_id, org_id):
                return None

        # Fetch child plots
        cursor.execute("SELECT * FROM farm_plots WHERE zone_id = ? AND status != 'archived' ORDER BY id ASC", (zone_id,))
        zone["plots"] = [dict(r) for r in cursor.fetchall()]

        return zone


def list_zones(farm_id: int, user_id: Optional[int] = None, org_id: Optional[int] = None, include_archived: bool = False) -> List[Dict[str, Any]]:
    """List zones in a farm with plot counts."""
    if user_id is not None:
        if not check_farm_access(farm_id, user_id, org_id):
            return []

    archived_filter = "" if include_archived else "AND status != 'archived'"

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT z.*,
                   (SELECT COUNT(*) FROM farm_plots WHERE zone_id = z.id AND status != 'archived') as plots_count,
                   (SELECT COUNT(*) FROM plot_plants WHERE zone_id = z.id AND status != 'archived') as plants_count
            FROM farm_zones z
            WHERE z.farm_id = ? {archived_filter}
            ORDER BY z.id ASC
        """, (farm_id,))
        return [dict(r) for r in cursor.fetchall()]


def update_zone(zone_id: int, data: Dict[str, Any], user_id: int, org_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Update zone details."""
    zone = get_zone(zone_id, user_id, org_id)
    if not zone:
        return None

    if not check_farm_access(zone["farm_id"], user_id, org_id, require_write=True):
        raise PermissionError("Bạn không có quyền chỉnh sửa khu vực này.")

    area_m2 = None
    area_ha = None
    unit = None
    if any(k in data for k in ("area_m2", "area_hectare", "area", "area_unit")):
        area_m2, area_ha, unit = normalize_area(data.get("area_m2") or data.get("area_hectare") or data.get("area"), data.get("area_unit"))

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE farm_zones
            SET name = COALESCE(?, name),
                code = COALESCE(?, code),
                zone_type = COALESCE(?, zone_type),
                area_m2 = COALESCE(?, area_m2),
                area_hectare = COALESCE(?, area_hectare),
                area_unit = COALESCE(?, area_unit),
                description = COALESCE(?, description),
                status = COALESCE(?, status),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            data.get("name"),
            data.get("code"),
            data.get("zone_type"),
            area_m2,
            area_ha,
            unit,
            data.get("description"),
            data.get("status"),
            zone_id
        ))
        conn.commit()

    return get_zone(zone_id, user_id, org_id)


def archive_zone(zone_id: int, user_id: int, org_id: Optional[int] = None) -> bool:
    """Archive a zone."""
    zone = get_zone(zone_id, user_id, org_id)
    if not zone:
        return False
    if not check_farm_access(zone["farm_id"], user_id, org_id, require_write=True):
        raise PermissionError("Bạn không có quyền lưu trữ khu vực này.")

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE farm_zones SET status = 'archived', archived_at = CURRENT_TIMESTAMP WHERE id = ?", (zone_id,))
        conn.commit()
        return cursor.rowcount > 0


def delete_zone(zone_id: int, user_id: int, org_id: Optional[int] = None) -> bool:
    """Delete a zone."""
    zone = get_zone(zone_id, user_id, org_id)
    if not zone:
        return False
    if not check_farm_access(zone["farm_id"], user_id, org_id, require_write=True):
        raise PermissionError("Bạn không có quyền xóa khu vực này.")

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM farm_zones WHERE id = ?", (zone_id,))
        conn.commit()
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Plot Management (Parent-Child Integrity, Area Normalization, Hierarchy)
# ---------------------------------------------------------------------------
def create_plot_ext(data: Dict[str, Any], user_id: int, org_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Create a new plot with parent-child relationship validation:
    - farm_id must exist and be accessible.
    - zone_id (if supplied) must belong to farm_id.
    - Prevents duplicates and normalizes area.
    """
    farm_id = data.get("farm_id")
    if not farm_id:
        raise ValueError("farm_id là bắt buộc khi tạo lô/thửa.")

    if not check_farm_access(farm_id, user_id, org_id, require_write=True):
        raise PermissionError("Bạn không có quyền thêm lô vào nông trại này.")

    plot_name = (data.get("plot_name") or data.get("name") or "").strip()
    if not plot_name:
        raise ValueError("Tên thửa/vườn không được để trống.")

    # Parent-child check for zone_id
    zone_id = data.get("zone_id")
    if zone_id:
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM farm_zones WHERE id = ? AND farm_id = ?", (zone_id, farm_id))
            if not cursor.fetchone():
                raise ValueError(f"Khu vực #{zone_id} không thuộc nông trại #{farm_id}.")

    area_m2, area_ha, unit = normalize_area(
        data.get("area_m2") or data.get("area_hectare") or data.get("area_hectares") or data.get("area"),
        data.get("area_unit")
    )

    crop_id = data.get("crop_id") or "Tomato"
    crop_name = data.get("crop_name") or "Cà chua"
    target_org = org_id or data.get("organization_id")

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        # Duplicate prevention within farm
        cursor.execute("""
            SELECT id FROM farm_plots
            WHERE farm_id = ? AND plot_name = ? AND status != 'archived'
        """, (farm_id, plot_name))
        existing = cursor.fetchone()
        if existing:
            return get_plot_ext(existing["id"], user_id=user_id, org_id=target_org)  # type: ignore

        cursor.execute("""
            INSERT INTO farm_plots (
                farm_id, zone_id, user_id, organization_id, plot_name, plot_code,
                crop_id, crop_name, region, area_m2, area_hectare, area_hectares, area_unit,
                planting_date, soil_type, irrigation_type, notes, status, monitoring_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            farm_id,
            zone_id,
            user_id,
            target_org,
            plot_name,
            data.get("plot_code"),
            crop_id,
            crop_name,
            data.get("region", ""),
            area_m2,
            area_ha,
            area_ha,
            unit,
            data.get("planting_date"),
            data.get("soil_type", ""),
            data.get("irrigation_type", ""),
            data.get("notes", ""),
            data.get("status", "active"),
            data.get("monitoring_status", "open")
        ))
        conn.commit()
        plot_id = cursor.lastrowid

        # Optionally initialize initial crop cycle
        cycle_name = data.get("cycle_name") or f"Vụ {crop_name} {datetime.now().year}"
        cursor.execute("""
            INSERT INTO crop_cycles (
                plot_id, cycle_name, crop_id, crop_name, variety, start_date, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, 'active', 'Khởi tạo cùng lô canh tác')
        """, (plot_id, cycle_name, crop_id, crop_name, data.get("variety", ""), data.get("planting_date") or datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        cycle_id = cursor.lastrowid

        # Link active_cycle_id
        cursor.execute("UPDATE farm_plots SET active_cycle_id = ? WHERE id = ?", (cycle_id, plot_id))
        conn.commit()

        # Add initial timeline event
        cursor.execute("""
            INSERT INTO plot_timeline_events (
                plot_id, cycle_id, user_id, organization_id, event_type, monitoring_status, notes
            ) VALUES (?, ?, ?, ?, 'plot_created', 'open', ?)
        """, (plot_id, cycle_id, user_id, target_org, f"Tạo mới thửa/vườn: {plot_name} ({crop_name})"))
        conn.commit()

    return get_plot_ext(plot_id, user_id=user_id, org_id=target_org)  # type: ignore


def get_plot_ext(plot_id: int, user_id: Optional[int] = None, org_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Retrieve detailed plot profile with active cycle, plants summary, and timeline."""
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*,
                   f.name as farm_name,
                   f.province as farm_province,
                   z.name as zone_name,
                   z.zone_type as zone_type
            FROM farm_plots p
            JOIN farms f ON p.farm_id = f.id
            LEFT JOIN farm_zones z ON p.zone_id = z.id
            WHERE p.id = ?
        """, (plot_id,))
        row = cursor.fetchone()
        if not row:
            return None

        plot = dict(row)
        if user_id is not None:
            if not check_plot_access(plot_id, user_id, org_id):
                return None

        # Fetch Active Cycle
        if plot.get("active_cycle_id"):
            cursor.execute("SELECT * FROM crop_cycles WHERE id = ?", (plot["active_cycle_id"],))
            active_c = cursor.fetchone()
            plot["active_cycle"] = dict(active_c) if active_c else None
        else:
            plot["active_cycle"] = None

        # Fetch All Crop Cycles (Rotation history)
        cursor.execute("""
            SELECT * FROM crop_cycles
            WHERE plot_id = ? AND status != 'archived'
            ORDER BY id DESC
        """, (plot_id,))
        plot["crop_cycles"] = [dict(r) for r in cursor.fetchall()]

        # Fetch Plants count by health status
        cursor.execute("""
            SELECT health_status, COUNT(*) as count
            FROM plot_plants
            WHERE plot_id = ? AND status != 'archived'
            GROUP BY health_status
        """, (plot_id,))
        health_counts = {r["health_status"]: r["count"] for r in cursor.fetchall()}
        plot["plants_summary"] = {
            "total": sum(health_counts.values()),
            "healthy": health_counts.get("healthy", 0),
            "monitoring": health_counts.get("monitoring", 0),
            "diseased": health_counts.get("diseased", 0),
            "recovering": health_counts.get("recovering", 0),
            "dead": health_counts.get("dead", 0)
        }

        # Fetch Recent Timeline Events
        cursor.execute("""
            SELECT t.*, d.disease_name_vi, d.confidence, d.severity as diag_severity
            FROM plot_timeline_events t
            LEFT JOIN diagnoses d ON t.diagnosis_id = d.id
            WHERE t.plot_id = ?
            ORDER BY t.id DESC LIMIT 15
        """, (plot_id,))
        plot["recent_timeline"] = [dict(r) for r in cursor.fetchall()]

        return plot


def update_plot_ext(plot_id: int, data: Dict[str, Any], user_id: int, org_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Update plot metadata and validate zone parent-child integrity."""
    plot = get_plot_ext(plot_id, user_id, org_id)
    if not plot:
        return None

    if not check_plot_access(plot_id, user_id, org_id, require_write=True):
        raise PermissionError("Bạn không có quyền chỉnh sửa thửa/vườn này.")

    zone_id = data.get("zone_id")
    if zone_id:
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM farm_zones WHERE id = ? AND farm_id = ?", (zone_id, plot["farm_id"]))
            if not cursor.fetchone():
                raise ValueError(f"Khu vực #{zone_id} không thuộc nông trại #{plot['farm_id']}.")

    area_m2 = None
    area_ha = None
    unit = None
    if any(k in data for k in ("area_m2", "area_hectare", "area_hectares", "area", "area_unit")):
        area_m2, area_ha, unit = normalize_area(
            data.get("area_m2") or data.get("area_hectare") or data.get("area_hectares") or data.get("area"),
            data.get("area_unit")
        )

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE farm_plots
            SET plot_name = COALESCE(?, plot_name),
                plot_code = COALESCE(?, plot_code),
                zone_id = COALESCE(?, zone_id),
                crop_id = COALESCE(?, crop_id),
                crop_name = COALESCE(?, crop_name),
                region = COALESCE(?, region),
                area_m2 = COALESCE(?, area_m2),
                area_hectare = COALESCE(?, area_hectare),
                area_hectares = COALESCE(?, area_hectares),
                area_unit = COALESCE(?, area_unit),
                planting_date = COALESCE(?, planting_date),
                soil_type = COALESCE(?, soil_type),
                irrigation_type = COALESCE(?, irrigation_type),
                status = COALESCE(?, status),
                monitoring_status = COALESCE(?, monitoring_status),
                notes = COALESCE(?, notes),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            data.get("plot_name") or data.get("name"),
            data.get("plot_code"),
            zone_id,
            data.get("crop_id"),
            data.get("crop_name"),
            data.get("region"),
            area_m2,
            area_ha,
            area_ha,
            unit,
            data.get("planting_date"),
            data.get("soil_type"),
            data.get("irrigation_type"),
            data.get("status"),
            data.get("monitoring_status"),
            data.get("notes"),
            plot_id
        ))
        conn.commit()

    return get_plot_ext(plot_id, user_id, org_id)


def archive_plot_ext(plot_id: int, user_id: int, org_id: Optional[int] = None) -> bool:
    """Archive a plot."""
    if not check_plot_access(plot_id, user_id, org_id, require_write=True):
        raise PermissionError("Bạn không có quyền lưu trữ thửa/vườn này.")

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE farm_plots
            SET status = 'archived', archived_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (plot_id,))
        cursor.execute("UPDATE crop_cycles SET status = 'archived', archived_at = CURRENT_TIMESTAMP WHERE plot_id = ?", (plot_id,))
        cursor.execute("UPDATE plot_plants SET status = 'archived', archived_at = CURRENT_TIMESTAMP WHERE plot_id = ?", (plot_id,))
        conn.commit()
        return cursor.rowcount > 0


def delete_plot_ext(plot_id: int, user_id: int, org_id: Optional[int] = None) -> bool:
    """Delete a plot."""
    if not check_plot_access(plot_id, user_id, org_id, require_write=True):
        raise PermissionError("Bạn không có quyền xóa thửa/vườn này.")

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM farm_plots WHERE id = ?", (plot_id,))
        conn.commit()
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Crop Cycles & Rotation Tracking (Vụ mùa & Luân canh)
# ---------------------------------------------------------------------------
def create_crop_cycle(plot_id: int, data: Dict[str, Any], user_id: int, org_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Create a new crop cycle on a plot.
    If set to 'active', automatically performs crop rotation by updating
    the plot's current crop and active_cycle_id, archiving previous active cycles.
    """
    if not check_plot_access(plot_id, user_id, org_id, require_write=True):
        raise PermissionError("Bạn không có quyền thêm vụ mùa cho thửa/vườn này.")

    cycle_name = (data.get("cycle_name") or data.get("name") or "").strip()
    if not cycle_name:
        raise ValueError("Tên vụ mùa không được để trống (ví dụ: Vụ Đông Xuân 2026).")

    crop_id = data.get("crop_id") or "Tomato"
    crop_name = data.get("crop_name") or "Cà chua"
    status = data.get("status") or "active"

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()

        # If new cycle is active, transition previous active cycle to 'completed'
        if status == "active":
            cursor.execute("""
                UPDATE crop_cycles
                SET status = 'completed', actual_harvest_date = COALESCE(actual_harvest_date, CURRENT_DATE), updated_at = CURRENT_TIMESTAMP
                WHERE plot_id = ? AND status = 'active'
            """, (plot_id,))

        cursor.execute("""
            INSERT INTO crop_cycles (
                plot_id, cycle_name, cycle_code, crop_id, crop_name, variety,
                start_date, expected_harvest_date, target_yield_kg, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            plot_id,
            cycle_name,
            data.get("cycle_code"),
            crop_id,
            crop_name,
            data.get("variety", ""),
            data.get("start_date") or datetime.now().strftime("%Y-%m-%d"),
            data.get("expected_harvest_date"),
            float(data.get("target_yield_kg", 0.0)) if data.get("target_yield_kg") else None,
            status,
            data.get("notes", "")
        ))
        conn.commit()
        cycle_id = cursor.lastrowid

        # Update plot if this cycle is active
        if status == "active":
            cursor.execute("""
                UPDATE farm_plots
                SET active_cycle_id = ?, crop_id = ?, crop_name = ?, planting_date = COALESCE(?, planting_date), updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (cycle_id, crop_id, crop_name, data.get("start_date"), plot_id))

            # Record crop rotation timeline event
            cursor.execute("""
                INSERT INTO plot_timeline_events (
                    plot_id, cycle_id, user_id, organization_id, event_type, notes
                ) VALUES (?, ?, ?, ?, 'crop_rotation', ?)
            """, (plot_id, cycle_id, user_id, org_id, f"Chuyển vụ mùa/Luân canh sang: {cycle_name} ({crop_name})"))
            conn.commit()

    return get_crop_cycle(cycle_id, user_id=user_id, org_id=org_id)  # type: ignore


def get_crop_cycle(cycle_id: int, user_id: Optional[int] = None, org_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Get crop cycle details."""
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, p.plot_name, p.farm_id, f.name as farm_name
            FROM crop_cycles c
            JOIN farm_plots p ON c.plot_id = p.id
            JOIN farms f ON p.farm_id = f.id
            WHERE c.id = ?
        """, (cycle_id,))
        row = cursor.fetchone()
        if not row:
            return None

        cycle = dict(row)
        if user_id is not None:
            if not check_plot_access(cycle["plot_id"], user_id, org_id):
                return None

        # Fetch cycle diagnoses
        cursor.execute("SELECT id, crop_name, disease_name_vi, confidence, severity, created_at FROM diagnoses WHERE crop_cycle_id = ? ORDER BY id DESC", (cycle_id,))
        cycle["diagnoses"] = [dict(r) for r in cursor.fetchall()]

        return cycle


def list_crop_cycles(plot_id: int, user_id: Optional[int] = None, org_id: Optional[int] = None, include_archived: bool = False) -> List[Dict[str, Any]]:
    """List crop cycles (rotation history) of a plot."""
    if user_id is not None:
        if not check_plot_access(plot_id, user_id, org_id):
            return []

    archived_filter = "" if include_archived else "AND status != 'archived'"

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT * FROM crop_cycles
            WHERE plot_id = ? {archived_filter}
            ORDER BY start_date DESC, id DESC
        """, (plot_id,))
        return [dict(r) for r in cursor.fetchall()]


def update_crop_cycle(cycle_id: int, data: Dict[str, Any], user_id: int, org_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Update crop cycle metadata or mark completed/harvested."""
    cycle = get_crop_cycle(cycle_id, user_id, org_id)
    if not cycle:
        return None

    if not check_plot_access(cycle["plot_id"], user_id, org_id, require_write=True):
        raise PermissionError("Bạn không có quyền chỉnh sửa vụ mùa này.")

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE crop_cycles
            SET cycle_name = COALESCE(?, cycle_name),
                variety = COALESCE(?, variety),
                start_date = COALESCE(?, start_date),
                expected_harvest_date = COALESCE(?, expected_harvest_date),
                actual_harvest_date = COALESCE(?, actual_harvest_date),
                target_yield_kg = COALESCE(?, target_yield_kg),
                actual_yield_kg = COALESCE(?, actual_yield_kg),
                status = COALESCE(?, status),
                notes = COALESCE(?, notes),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            data.get("cycle_name"),
            data.get("variety"),
            data.get("start_date"),
            data.get("expected_harvest_date"),
            data.get("actual_harvest_date"),
            float(data["target_yield_kg"]) if data.get("target_yield_kg") is not None else None,
            float(data["actual_yield_kg"]) if data.get("actual_yield_kg") is not None else None,
            data.get("status"),
            data.get("notes"),
            cycle_id
        ))
        conn.commit()

    return get_crop_cycle(cycle_id, user_id, org_id)


# ---------------------------------------------------------------------------
# Individual Plant / Tree Tracking (Durian, Trees, Clusters)
# ---------------------------------------------------------------------------
def create_plant(plot_id: int, data: Dict[str, Any], user_id: int, org_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Register an individual plant, tree, or plant group within a plot.
    Enforces unique plant_tag per plot.
    """
    if not check_plot_access(plot_id, user_id, org_id, require_write=True):
        raise PermissionError("Bạn không có quyền thêm cây vào thửa/vườn này.")

    plant_tag = (data.get("plant_tag") or data.get("tag") or "").strip()
    if not plant_tag:
        raise ValueError("Mã định danh cây (plant_tag / mã QR) không được để trống.")

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        # Uniqueness check of plant_tag in plot
        cursor.execute("SELECT id FROM plot_plants WHERE plot_id = ? AND plant_tag = ? AND status != 'archived'", (plot_id, plant_tag))
        existing = cursor.fetchone()
        if existing:
            return get_plant(existing["id"], user_id=user_id, org_id=org_id)  # type: ignore

        # Validate zone_id if supplied
        zone_id = data.get("zone_id")
        if zone_id:
            cursor.execute("SELECT p.farm_id FROM farm_plots p WHERE p.id = ?", (plot_id,))
            p_farm = cursor.fetchone()
            if p_farm:
                cursor.execute("SELECT id FROM farm_zones WHERE id = ? AND farm_id = ?", (zone_id, p_farm["farm_id"]))
                if not cursor.fetchone():
                    zone_id = None

        cursor.execute("""
            INSERT INTO plot_plants (
                plot_id, zone_id, plant_tag, plant_name, species, variety,
                planting_date, row_index, col_index, health_status, gps_lat, gps_lng, notes, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            plot_id,
            zone_id,
            plant_tag,
            data.get("plant_name") or f"Cây {plant_tag}",
            data.get("species") or data.get("crop_id") or "durian",
            data.get("variety", ""),
            data.get("planting_date"),
            data.get("row_index"),
            data.get("col_index"),
            data.get("health_status", "healthy"),
            float(data["gps_lat"]) if data.get("gps_lat") is not None else None,
            float(data["gps_lng"]) if data.get("gps_lng") is not None else None,
            data.get("notes", ""),
            data.get("status", "active")
        ))
        conn.commit()
        plant_id = cursor.lastrowid

    return get_plant(plant_id, user_id=user_id, org_id=org_id)  # type: ignore


def batch_create_plants(plot_id: int, plants_list: List[Dict[str, Any]], user_id: int, org_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Batch register multiple plants/trees for a plot."""
    if not check_plot_access(plot_id, user_id, org_id, require_write=True):
        raise PermissionError("Bạn không có quyền thêm cây vào thửa/vườn này.")

    created = []
    for item in plants_list:
        try:
            p = create_plant(plot_id, item, user_id=user_id, org_id=org_id)
            created.append(p)
        except Exception as e:
            logger.warning("Batch plant registration error on item %s: %s", item, e)
    return created


def get_plant(plant_id: int, user_id: Optional[int] = None, org_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Get single plant details with health and observation history."""
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pl.*, p.plot_name, p.farm_id, f.name as farm_name, z.name as zone_name
            FROM plot_plants pl
            JOIN farm_plots p ON pl.plot_id = p.id
            JOIN farms f ON p.farm_id = f.id
            LEFT JOIN farm_zones z ON pl.zone_id = z.id
            WHERE pl.id = ?
        """, (plant_id,))
        row = cursor.fetchone()
        if not row:
            return None

        plant = dict(row)
        if user_id is not None:
            if not check_plot_access(plant["plot_id"], user_id, org_id):
                return None

        # Fetch diagnoses linked to this specific plant
        cursor.execute("""
            SELECT id, predicted_disease, disease_name_vi, confidence, severity, created_at, treatment_status
            FROM diagnoses
            WHERE plant_id = ?
            ORDER BY id DESC LIMIT 20
        """, (plant_id,))
        plant["diagnoses"] = [dict(r) for r in cursor.fetchall()]

        # Fetch timeline events
        cursor.execute("""
            SELECT * FROM plot_timeline_events
            WHERE plant_id = ?
            ORDER BY id DESC LIMIT 20
        """, (plant_id,))
        plant["timeline"] = [dict(r) for r in cursor.fetchall()]

        return plant


def list_plants(
    plot_id: int,
    health_status: Optional[str] = None,
    user_id: Optional[int] = None,
    org_id: Optional[int] = None,
    include_archived: bool = False
) -> List[Dict[str, Any]]:
    """List plants/trees inside a plot."""
    if user_id is not None:
        if not check_plot_access(plot_id, user_id, org_id):
            return []

    conditions = ["plot_id = ?"]
    params: List[Any] = [plot_id]

    if not include_archived:
        conditions.append("status != 'archived'")

    if health_status and health_status != "all":
        conditions.append("health_status = ?")
        params.append(health_status)

    where_sql = "WHERE " + " AND ".join(conditions)

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT pl.*,
                   (SELECT COUNT(*) FROM diagnoses WHERE plant_id = pl.id) as diagnoses_count
            FROM plot_plants pl
            {where_sql}
            ORDER BY pl.row_index ASC, pl.col_index ASC, pl.id ASC
        """, params)
        return [dict(r) for r in cursor.fetchall()]


def update_plant(plant_id: int, data: Dict[str, Any], user_id: int, org_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Update individual plant details or health status."""
    plant = get_plant(plant_id, user_id, org_id)
    if not plant:
        return None

    if not check_plot_access(plant["plot_id"], user_id, org_id, require_write=True):
        raise PermissionError("Bạn không có quyền chỉnh sửa cây này.")

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE plot_plants
            SET plant_name = COALESCE(?, plant_name),
                variety = COALESCE(?, variety),
                planting_date = COALESCE(?, planting_date),
                row_index = COALESCE(?, row_index),
                col_index = COALESCE(?, col_index),
                health_status = COALESCE(?, health_status),
                gps_lat = COALESCE(?, gps_lat),
                gps_lng = COALESCE(?, gps_lng),
                notes = COALESCE(?, notes),
                status = COALESCE(?, status),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            data.get("plant_name"),
            data.get("variety"),
            data.get("planting_date"),
            data.get("row_index"),
            data.get("col_index"),
            data.get("health_status"),
            float(data["gps_lat"]) if data.get("gps_lat") is not None else None,
            float(data["gps_lng"]) if data.get("gps_lng") is not None else None,
            data.get("notes"),
            data.get("status"),
            plant_id
        ))
        conn.commit()

        # If health status turned to diseased or alert, record an observation timeline event
        if data.get("health_status") and data["health_status"] != plant.get("health_status"):
            cursor.execute("""
                INSERT INTO plot_timeline_events (
                    plot_id, plant_id, user_id, organization_id, event_type, severity, notes
                ) VALUES (?, ?, ?, ?, 'plant_health_update', ?, ?)
            """, (
                plant["plot_id"],
                plant_id,
                user_id,
                org_id,
                data["health_status"],
                f"Cập nhật trạng thái cây {plant['plant_tag']}: {plant.get('health_status')} -> {data['health_status']}"
            ))
            conn.commit()

    return get_plant(plant_id, user_id, org_id)


def archive_plant(plant_id: int, user_id: int, org_id: Optional[int] = None) -> bool:
    """Archive a plant."""
    plant = get_plant(plant_id, user_id, org_id)
    if not plant:
        return False
    if not check_plot_access(plant["plot_id"], user_id, org_id, require_write=True):
        raise PermissionError("Bạn không có quyền lưu trữ cây này.")

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE plot_plants SET status = 'archived', archived_at = CURRENT_TIMESTAMP WHERE id = ?", (plant_id,))
        conn.commit()
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Activity & Observation Timeline Linking
# ---------------------------------------------------------------------------
def record_plot_activity(
    plot_id: int,
    event_type: str,
    notes: str,
    user_id: int,
    org_id: Optional[int] = None,
    plant_id: Optional[int] = None,
    cycle_id: Optional[int] = None,
    severity: Optional[str] = None,
    action_taken: Optional[str] = None,
    images: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Record an observation or activity linked to a plot or specific plant/cycle."""
    if not check_plot_access(plot_id, user_id, org_id, require_write=True):
        raise PermissionError("Bạn không có quyền ghi nhật ký vào thửa/vườn này.")

    # Validate plant belongs to plot
    if plant_id:
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM plot_plants WHERE id = ? AND plot_id = ?", (plant_id, plot_id))
            if not cursor.fetchone():
                raise ValueError(f"Cây #{plant_id} không thuộc thửa/vườn #{plot_id}.")

    images_json = json.dumps(images) if images else None

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO plot_timeline_events (
                plot_id, plant_id, cycle_id, user_id, organization_id,
                event_type, severity, action_taken, images_json, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            plot_id,
            plant_id,
            cycle_id,
            user_id,
            org_id,
            event_type,
            severity,
            action_taken,
            images_json,
            notes
        ))
        conn.commit()
        event_id = cursor.lastrowid

        cursor.execute("SELECT * FROM plot_timeline_events WHERE id = ?", (event_id,))
        return dict(cursor.fetchone())


def list_plot_timeline(
    plot_id: int,
    plant_id: Optional[int] = None,
    cycle_id: Optional[int] = None,
    user_id: Optional[int] = None,
    org_id: Optional[int] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """List activity and diagnosis timeline for a plot or plant."""
    if user_id is not None:
        if not check_plot_access(plot_id, user_id, org_id):
            return []

    conditions = ["t.plot_id = ?"]
    params: List[Any] = [plot_id]

    if plant_id is not None:
        conditions.append("t.plant_id = ?")
        params.append(plant_id)

    if cycle_id is not None:
        conditions.append("t.cycle_id = ?")
        params.append(cycle_id)

    where_sql = "WHERE " + " AND ".join(conditions)

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT t.*,
                   d.crop_name, d.disease_name_vi, d.confidence, d.severity as diag_severity, d.image_path,
                   pl.plant_tag, pl.plant_name
            FROM plot_timeline_events t
            LEFT JOIN diagnoses d ON t.diagnosis_id = d.id
            LEFT JOIN plot_plants pl ON t.plant_id = pl.id
            {where_sql}
            ORDER BY t.id DESC LIMIT ?
        """, params + [limit])
        rows = [dict(r) for r in cursor.fetchall()]
        for r in rows:
            if r.get("images_json"):
                try:
                    r["images"] = json.loads(r["images_json"])
                except Exception:
                    r["images"] = []
            else:
                r["images"] = []
        return rows


# ---------------------------------------------------------------------------
# Linking Diagnoses and Tasks to Hierarchy
# ---------------------------------------------------------------------------
def link_diagnosis_to_hierarchy(
    diagnosis_id: int,
    farm_id: int,
    plot_id: int,
    plant_id: Optional[int] = None,
    crop_cycle_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> bool:
    """Link an existing diagnosis to a plot, optional plant, and optional crop cycle."""
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, user_id FROM diagnoses WHERE id = ?", (diagnosis_id,))
        diag = cursor.fetchone()
        if not diag:
            return False

        if user_id is not None and diag["user_id"] != user_id:
            # check farm access
            if not check_farm_access(farm_id, user_id):
                return False

        # Validate parent-child
        cursor.execute("SELECT id FROM farm_plots WHERE id = ? AND farm_id = ?", (plot_id, farm_id))
        if not cursor.fetchone():
            raise ValueError("Thửa/vườn không thuộc nông trại này.")

        if plant_id:
            cursor.execute("SELECT id FROM plot_plants WHERE id = ? AND plot_id = ?", (plant_id, plot_id))
            if not cursor.fetchone():
                raise ValueError("Cây không thuộc thửa/vườn này.")

        cursor.execute("""
            UPDATE diagnoses
            SET farm_id = ?, plot_id = ?, farm_plot_id = ?, plant_id = ?, crop_cycle_id = ?
            WHERE id = ?
        """, (farm_id, plot_id, plot_id, plant_id, crop_cycle_id, diagnosis_id))
        conn.commit()

        # Also add a timeline record
        cursor.execute("""
            INSERT INTO plot_timeline_events (
                plot_id, plant_id, cycle_id, user_id, event_type, diagnosis_id, notes
            ) VALUES (?, ?, ?, ?, 'diagnosis_linked', ?, 'Liên kết chẩn đoán AI vào hồ sơ canh tác')
        """, (plot_id, plant_id, crop_cycle_id, user_id or diag["user_id"], diagnosis_id))
        conn.commit()
        return True
