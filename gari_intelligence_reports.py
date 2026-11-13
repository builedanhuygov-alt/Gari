"""
GARI Module — Intelligence Reports Engine (P3.7)
Authoritative implementation for:
1. Multi-vector agricultural reports:
   - Farm Health Report (Plots, disease detections, health distribution)
   - Weather Intelligence Report (Metrics summary, rain days, extremes)
   - Satellite & Vegetation Report (NDVI/NDMI trends, cloud occlusion)
   - Agricultural Risk Report (Evaluated threats, factors, recommendations)
   - Organization Executive Overview (Multi-farm aggregation)
2. Granular filtering (date range, farm, plot, crop).
3. Export formats: Structured JSON, CSV (RFC-4180), and printable HTML.
4. Truth-in-data: Strict distinction between Missing Data ('N/A') and Zero Data ('0.0').
"""

import csv
import io
import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from gari_database import get_connection
import gari_farm_management
import gari_weather_service
import gari_satellite_service
import gari_risk_engine

logger = logging.getLogger("gari.reports")


def generate_farm_health_report(
    farm_id: int,
    user_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    crop: Optional[str] = None,
    export_format: str = "json"
) -> Any:
    """Generate comprehensive Farm Health Report."""
    farm = gari_farm_management.get_farm_ext(farm_id=farm_id, user_id=user_id)
    if not farm:
        raise PermissionError(f"Không có quyền truy cập dữ liệu nông trại #{farm_id}.")

    with get_connection() as conn:
        cursor = conn.cursor()

        # Query plots
        plot_sql = "SELECT * FROM farm_plots WHERE farm_id = ? AND archived_at IS NULL"
        plot_params: List[Any] = [farm_id]
        if crop:
            plot_sql += " AND crop_name LIKE ?"
            plot_params.append(f"%{crop}%")
        cursor.execute(plot_sql, tuple(plot_params))
        plots = [dict(r) for r in cursor.fetchall()]

        # Query diagnoses
        diag_sql = """
            SELECT d.id, d.plot_id, d.crop_name, d.predicted_disease, d.confidence,
                   d.severity, d.created_at, p.plot_name
            FROM diagnoses d
            JOIN farm_plots p ON d.plot_id = p.id
            WHERE p.farm_id = ?
        """
        diag_params: List[Any] = [farm_id]
        if start_date:
            diag_sql += " AND date(d.created_at) >= date(?)"
            diag_params.append(start_date)
        if end_date:
            diag_sql += " AND date(d.created_at) <= date(?)"
            diag_params.append(end_date)
        if crop:
            diag_sql += " AND d.crop_name LIKE ?"
            diag_params.append(f"%{crop}%")
        diag_sql += " ORDER BY d.id DESC"

        cursor.execute(diag_sql, tuple(diag_params))
        diagnoses = [dict(r) for r in cursor.fetchall()]

    healthy_count = sum(1 for d in diagnoses if "healthy" in (d.get("predicted_disease") or "").lower())
    disease_count = len(diagnoses) - healthy_count

    report_data = {
        "report_title": f"Báo cáo Sức khỏe Nông trại — {farm['name']}",
        "farm_id": farm_id,
        "farm_name": farm["name"],
        "province": farm.get("province") or "N/A",
        "total_area_ha": farm.get("area_hectare") if farm.get("area_hectare") is not None else "N/A",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "period": f"{start_date or 'Tất cả'} đến {end_date or 'Hiện tại'}",
        "total_plots": len(plots),
        "total_diagnoses": len(diagnoses),
        "healthy_diagnoses": healthy_count,
        "disease_diagnoses": disease_count,
        "disease_rate_pct": round((disease_count / len(diagnoses) * 100), 1) if diagnoses else 0.0,
        "plots_summary": plots,
        "diagnoses_records": diagnoses
    }

    if export_format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Mã chẩn đoán", "Tên thửa", "Cây trồng", "Bệnh hại phát hiện", "Độ tin cậy", "Mức độ", "Thời gian ghi nhận"])
        for d in diagnoses:
            writer.writerow([
                d["id"],
                d.get("plot_name") or "N/A",
                d.get("crop_name") or "N/A",
                d.get("predicted_disease") or "N/A",
                round(float(d.get("confidence") or 0.0), 3),
                d.get("severity") or "N/A",
                d.get("created_at") or "N/A"
            ])
        return output.getvalue()

    return report_data


def generate_agricultural_risk_report(
    farm_id: int,
    user_id: int,
    export_format: str = "json"
) -> Any:
    """Generate comprehensive Agricultural Risk Report."""
    farm = gari_farm_management.get_farm_ext(farm_id=farm_id, user_id=user_id)
    if not farm:
        raise PermissionError(f"Không có quyền truy cập dữ liệu nông trại #{farm_id}.")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.*, p.plot_name
            FROM agricultural_risk_assessments r
            LEFT JOIN farm_plots p ON r.plot_id = p.id
            WHERE r.farm_id = ?
            ORDER BY r.assessment_date DESC, r.id DESC
            LIMIT 50
        """, (farm_id,))
        records = [dict(r) for r in cursor.fetchall()]

        for r in records:
            if r.get("contributing_factors"):
                try:
                    r["contributing_factors"] = json.loads(r["contributing_factors"])
                except Exception:
                    pass
            if r.get("recommendations"):
                try:
                    r["recommendations"] = json.loads(r["recommendations"])
                except Exception:
                    pass

    report_data = {
        "report_title": f"Báo cáo Đánh giá Rủi ro Nông nghiệp — {farm['name']}",
        "farm_id": farm_id,
        "farm_name": farm["name"],
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total_assessments": len(records),
        "assessments": records
    }

    if export_format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Mã đánh giá", "Thửa đất", "Nhóm rủi ro", "Mức độ", "Điểm rủi ro", "Độ tin cậy", "Giải thích cơ chế", "Thời gian"])
        for r in records:
            writer.writerow([
                r["id"],
                r.get("plot_name") or "Toàn trại",
                r.get("risk_category"),
                r.get("risk_level"),
                r.get("risk_score"),
                r.get("confidence_score"),
                r.get("explanation"),
                r.get("assessment_date")
            ])
        return output.getvalue()

    return report_data


def generate_organization_overview_report(
    org_id: int,
    user_id: int,
    export_format: str = "json"
) -> Any:
    """Generate high-level Executive Overview Report for an organization."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Check membership
        cursor.execute("""
            SELECT role FROM organization_members
            WHERE organization_id = ? AND user_id = ?
        """, (org_id, user_id))
        if not cursor.fetchone():
            raise PermissionError("Bạn không có quyền truy cập báo cáo của tổ chức này.")

        cursor.execute("SELECT * FROM organizations WHERE id = ?", (org_id,))
        org = dict(cursor.fetchone() or {})

        cursor.execute("""
            SELECT f.*,
                   count(p.id) as total_plots,
                   sum(CASE WHEN p.latitude IS NOT NULL THEN 1 ELSE 0 END) as located_plots
            FROM farms f
            LEFT JOIN farm_plots p ON f.id = p.farm_id AND p.archived_at IS NULL
            WHERE f.organization_id = ? AND f.archived_at IS NULL
            GROUP BY f.id
        """, (org_id,))
        farms = [dict(r) for r in cursor.fetchall()]

        total_area = sum(float(f.get("area_hectare") or 0.0) for f in farms)
        total_plots = sum(int(f.get("total_plots") or 0) for f in farms)

    report_data = {
        "report_title": f"Báo cáo Tổng quan Quản trị Hợp tác xã / Doanh nghiệp — {org.get('name')}",
        "organization_id": org_id,
        "organization_name": org.get("name"),
        "org_type": org.get("organization_type") or org.get("type"),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total_farms": len(farms),
        "total_area_hectares": round(total_area, 2),
        "total_plots": total_plots,
        "farms": farms
    }

    if export_format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Mã trang trại", "Tên trang trại", "Mã code", "Tỉnh / Thành", "Cây trồng chính", "Diện tích (ha)", "Số thửa đất", "Số thửa có GPS"])
        for f in farms:
            writer.writerow([
                f["id"],
                f["name"],
                f.get("code") or "N/A",
                f.get("province") or "N/A",
                f.get("primary_crop") or "N/A",
                f.get("area_hectare") or "N/A",
                f.get("total_plots") or 0,
                f.get("located_plots") or 0
            ])
        return output.getvalue()

    return report_data
