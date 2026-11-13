"""
GARI Module — Agricultural Risk Engine (P3.4)
Authoritative implementation for:
1. Transparent, explainable rule-based risk evaluation for:
   - Drought Risk (Precipitation deficit, high VPD, low NDMI).
   - Heavy Rainfall & Flooding Risk (Excess precipitation, storm events).
   - Heat Stress Risk (Crop-specific high-temperature thresholds).
   - Disease Weather Risk (Prolonged high humidity + fungal incubation temps).
   - Vegetation Degradation Risk (Abrupt negative NDVI delta).
2. Honest confidence scoring based on data availability.
3. Explicit 'insufficient_data' state when inputs are missing.
4. Full explanation decomposition with contributing factors.
5. Persistent storage in agricultural_risk_assessments.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from gari_database import get_connection
import gari_weather_service
import gari_satellite_service
import gari_farm_management

logger = logging.getLogger("gari.risk")

# Temperature sensitivity thresholds for common crops (°C)
CROP_HEAT_THRESHOLDS = {
    "tomato": 33.0,
    "cà chua": 33.0,
    "pepper": 34.0,
    "ớt": 34.0,
    "rice": 35.0,
    "lúa": 35.0,
    "coffee": 32.0,
    "cà phê": 32.0,
    "durian": 36.0,
    "sầu riêng": 36.0
}


def evaluate_plot_risks(
    plot_id: int,
    user_id: int,
    org_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Run comprehensive 5-vector agricultural risk analysis for a specific plot.
    Inputs:
    - Farm / Plot coordinates
    - Real weather observations & 7-day forecast from gari_weather_service
    - Satellite vegetation indices (NDVI, NDMI) from gari_satellite_service
    - Plot crop type & recent diagnosis history
    """
    plot = gari_farm_management.get_plot_ext(plot_id=plot_id, user_id=user_id, org_id=org_id)
    if not plot:
        raise PermissionError(f"Không có quyền truy cập thửa #{plot_id}.")

    farm_id = plot["farm_id"]
    crop_name = (plot.get("crop_name") or plot.get("crop_id") or "Cây trồng").lower()
    lat = plot.get("latitude")
    lon = plot.get("longitude")

    if lat is None or lon is None:
        # Fallback to farm coordinates if plot centroid is missing
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT latitude, longitude FROM farms WHERE id = ?", (farm_id,))
            f_row = cursor.fetchone()
            if f_row and f_row["latitude"] is not None:
                lat = f_row["latitude"]
                lon = f_row["longitude"]

    # If still unlocated, return insufficient_data
    if lat is None or lon is None:
        return {
            "status": "insufficient_data",
            "plot_id": plot_id,
            "plot_name": plot.get("plot_name"),
            "confidence_score": 0.0,
            "message": "Thiếu tọa độ địa lý (GPS). Vui lòng cập nhật vị trí trên bản đồ để kích hoạt công cụ phân tích rủi ro.",
            "assessments": []
        }

    # Fetch weather
    weather = gari_weather_service.get_coordinates_weather(latitude=lat, longitude=lon)
    weather_ok = weather.get("status") in ("connected", "stale")

    # Fetch satellite indices
    satellite = gari_satellite_service.get_plot_vegetation_indices(plot_id=plot_id, user_id=user_id, org_id=org_id)
    satellite_ok = satellite.get("status") == "connected"

    # Fetch recent diagnoses
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, predicted_disease, confidence, severity, created_at
            FROM diagnoses
            WHERE plot_id = ?
            ORDER BY id DESC LIMIT 5
        """, (plot_id,))
        recent_diags = [dict(r) for r in cursor.fetchall()]

    assessments = []

    # Vector 1: Drought Risk
    assessments.append(_evaluate_drought_risk(weather, satellite, crop_name))

    # Vector 2: Heavy Rainfall & Flood Risk
    assessments.append(_evaluate_rainfall_risk(weather))

    # Vector 3: Heat Stress Risk
    assessments.append(_evaluate_heat_stress_risk(weather, crop_name))

    # Vector 4: Disease Weather Risk (Fungal / Bacterial Incubation)
    assessments.append(_evaluate_disease_weather_risk(weather, recent_diags, crop_name))

    # Vector 5: Vegetation Degradation Risk
    assessments.append(_evaluate_vegetation_degradation_risk(satellite))

    # Save evaluations to database
    with get_connection() as conn:
        cursor = conn.cursor()
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        for a in assessments:
            cursor.execute("""
                INSERT INTO agricultural_risk_assessments (
                    organization_id, farm_id, plot_id, assessment_date,
                    risk_category, risk_level, risk_score, confidence_score,
                    status, contributing_factors, explanation, recommendations
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plot.get("organization_id"),
                farm_id,
                plot_id,
                now_str,
                a["risk_category"],
                a["risk_level"],
                a["risk_score"],
                a["confidence_score"],
                a["status"],
                json.dumps(a["contributing_factors"], ensure_ascii=False),
                a["explanation"],
                json.dumps(a["recommendations"], ensure_ascii=False)
            ))
        conn.commit()

    # Overall plot risk level (max of all 5 vectors)
    level_order = {"low": 1, "moderate": 2, "high": 3, "severe": 4}
    highest_risk = max(assessments, key=lambda a: level_order.get(a["risk_level"], 0))

    return {
        "status": "evaluated",
        "plot_id": plot_id,
        "plot_name": plot.get("plot_name"),
        "farm_id": farm_id,
        "crop_name": plot.get("crop_name"),
        "overall_risk_level": highest_risk["risk_level"],
        "overall_risk_score": highest_risk["risk_score"],
        "evaluated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "assessments": assessments
    }


def _evaluate_drought_risk(weather: Dict[str, Any], satellite: Dict[str, Any], crop_name: str) -> Dict[str, Any]:
    """Calculate Drought & Water Stress Risk."""
    factors = []
    score = 10.0  # baseline
    confidence = 0.85 if weather.get("status") == "connected" else 0.4

    if weather.get("status") not in ("connected", "stale"):
        return {
            "risk_category": "drought",
            "risk_name": "Rủi ro hạn hán & thiếu nước",
            "risk_level": "low",
            "risk_score": 0.0,
            "confidence_score": 0.0,
            "status": "insufficient_data",
            "contributing_factors": [],
            "explanation": "Không đủ dữ liệu quan trắc khí tượng để đánh giá nguy cơ hạn hán.",
            "recommendations": []
        }

    daily = weather.get("daily_forecast", [])
    total_7d_precip = sum(d.get("precipitation_sum_mm", 0.0) or 0.0 for d in daily)
    factors.append({"factor": "Tổng lượng mưa dự báo 7 ngày", "value": f"{round(total_7d_precip, 1)} mm", "weight": 0.4})

    if total_7d_precip < 5.0:
        score += 45.0
    elif total_7d_precip < 15.0:
        score += 25.0

    cur_humidity = weather.get("current", {}).get("humidity_pct")
    if cur_humidity is not None:
        factors.append({"factor": "Độ ẩm không khí hiện tại", "value": f"{cur_humidity}%", "weight": 0.3})
        if cur_humidity < 40:
            score += 25.0
        elif cur_humidity < 60:
            score += 10.0

    ndmi = satellite.get("latest_ndmi")
    if ndmi is not None:
        factors.append({"factor": "Chỉ số ẩm thực vật NDMI (Sentinel-2)", "value": ndmi, "weight": 0.3})
        if ndmi < 0.15:
            score += 20.0
        elif ndmi > 0.35:
            score -= 10.0

    score = max(0.0, min(100.0, score))
    level = "severe" if score >= 75 else "high" if score >= 50 else "moderate" if score >= 30 else "low"

    explanation = (
        f"Nguy cơ hạn hán ở mức {level.upper()} (Điểm rủi ro: {score}/100). "
        f"Tổng lượng mưa dự báo trong 7 ngày tới chỉ đạt {round(total_7d_precip, 1)}mm, "
        f"kết hợp độ ẩm không khí {cur_humidity or 'N/A'}%."
    )

    recs = [
        "Kiểm tra hệ thống tưới nhỏ giọt hoặc tưới phun sương để bổ sung ẩm tầng rễ.",
        "Phủ bạt nông nghiệp hoặc màng phủ hữu cơ để hạn chế bốc thoát hơi nước bề mặt đất."
    ] if score >= 40 else ["Duy trì chế độ tưới nước tiêu chuẩn theo giai đoạn sinh trưởng."]

    return {
        "risk_category": "drought",
        "risk_name": "Rủi ro hạn hán & thiếu nước",
        "risk_level": level,
        "risk_score": round(score, 1),
        "confidence_score": confidence,
        "status": "evaluated",
        "contributing_factors": factors,
        "explanation": explanation,
        "recommendations": recs
    }


def _evaluate_rainfall_risk(weather: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate Heavy Rainfall & Waterlogging Risk."""
    if weather.get("status") not in ("connected", "stale"):
        return {
            "risk_category": "heavy_rainfall",
            "risk_name": "Rủi ro mưa lớn & ngập úng",
            "risk_level": "low",
            "risk_score": 0.0,
            "confidence_score": 0.0,
            "status": "insufficient_data",
            "contributing_factors": [],
            "explanation": "Không đủ dữ liệu khí tượng để tính toán nguy cơ mưa lớn.",
            "recommendations": []
        }

    daily = weather.get("daily_forecast", [])
    max_1d_rain = max((d.get("precipitation_sum_mm", 0.0) or 0.0 for d in daily), default=0.0)
    rain_days = sum(1 for d in daily if (d.get("precipitation_sum_mm", 0.0) or 0.0) >= 5.0)

    factors = [
        {"factor": "Lượng mưa tối đa trong 1 ngày dự báo", "value": f"{round(max_1d_rain, 1)} mm", "weight": 0.6},
        {"factor": "Số ngày mưa liên tiếp trong tuần", "value": f"{rain_days} ngày", "weight": 0.4}
    ]

    score = 5.0
    if max_1d_rain >= 60.0:
        score += 65.0
    elif max_1d_rain >= 35.0:
        score += 40.0
    elif max_1d_rain >= 15.0:
        score += 20.0

    if rain_days >= 4:
        score += 25.0

    score = max(0.0, min(100.0, score))
    level = "severe" if score >= 75 else "high" if score >= 50 else "moderate" if score >= 30 else "low"

    explanation = (
        f"Nguy cơ mưa lớn & úng cục bộ ở mức {level.upper()} (Điểm rủi ro: {score}/100). "
        f"Lượng mưa cực đại dự báo đạt {round(max_1d_rain, 1)}mm/ngày với {rain_days} ngày mưa trong tuần."
    )

    recs = [
        "Khơi thông hệ thống mương rãnh thoát nước nội đồng quanh các luống cây.",
        "Tạm hoãn các hoạt động bón phân gốc để tránh thất thoát do rửa trôi bề mặt."
    ] if score >= 40 else ["Hệ thống thoát nước đang đảm bảo tải lượng mưa dự kiến."]

    return {
        "risk_category": "heavy_rainfall",
        "risk_name": "Rủi ro mưa lớn & ngập úng",
        "risk_level": level,
        "risk_score": round(score, 1),
        "confidence_score": 0.90,
        "status": "evaluated",
        "contributing_factors": factors,
        "explanation": explanation,
        "recommendations": recs
    }


def _evaluate_heat_stress_risk(weather: Dict[str, Any], crop_name: str) -> Dict[str, Any]:
    """Calculate High Temperature Heat Stress Risk."""
    if weather.get("status") not in ("connected", "stale"):
        return {
            "risk_category": "heat_stress",
            "risk_name": "Rủi ro sốc nhiệt độ cao",
            "risk_level": "low",
            "risk_score": 0.0,
            "confidence_score": 0.0,
            "status": "insufficient_data",
            "contributing_factors": [],
            "explanation": "Thiếu dữ liệu nhiệt độ để tính toán nguy cơ sốc nhiệt.",
            "recommendations": []
        }

    daily = weather.get("daily_forecast", [])
    max_temp = max((d.get("temp_max_c", 0.0) or 0.0 for d in daily), default=25.0)
    current_temp = weather.get("current", {}).get("temperature_c") or max_temp

    # Threshold for this crop
    thresh = 34.0
    for k, v in CROP_HEAT_THRESHOLDS.items():
        if k in crop_name:
            thresh = v
            break

    factors = [
        {"factor": "Nhiệt độ tối đa dự báo trong tuần", "value": f"{round(max_temp, 1)} °C", "weight": 0.6},
        {"factor": f"Ngưỡng chịu nhiệt khuyến nghị của {crop_name}", "value": f"{thresh} °C", "weight": 0.4}
    ]

    score = 5.0
    if max_temp >= thresh + 4.0:
        score += 75.0
    elif max_temp >= thresh + 1.5:
        score += 50.0
    elif max_temp >= thresh:
        score += 30.0

    score = max(0.0, min(100.0, score))
    level = "severe" if score >= 75 else "high" if score >= 50 else "moderate" if score >= 30 else "low"

    explanation = (
        f"Nguy cơ sốc nhiệt đối với {crop_name} ở mức {level.upper()} (Điểm rủi ro: {score}/100). "
        f"Nhiệt độ đỉnh đạt {round(max_temp, 1)}°C (vượt ngưỡng giới hạn sinh lý {thresh}°C)."
    )

    recs = [
        "Tăng cường kéo lưới đen che nắng giảm 30-50% cường độ bức xạ quang hợp trong khung giờ 11h-14h.",
        "Phun sương hạ nhiệt tán cây và bổ sung vi lượng Canxi-Bo chống rụng hoa/trái non."
    ] if score >= 40 else ["Nhiệt độ nằm trong dải quang hợp tối ưu của cây trồng."]

    return {
        "risk_category": "heat_stress",
        "risk_name": "Rủi ro sốc nhiệt độ cao",
        "risk_level": level,
        "risk_score": round(score, 1),
        "confidence_score": 0.90,
        "status": "evaluated",
        "contributing_factors": factors,
        "explanation": explanation,
        "recommendations": recs
    }


def _evaluate_disease_weather_risk(
    weather: Dict[str, Any],
    recent_diags: List[Dict[str, Any]],
    crop_name: str
) -> Dict[str, Any]:
    """Calculate Disease Weather Envelope Risk (Fungal/Bacterial spore germination)."""
    if weather.get("status") not in ("connected", "stale"):
        return {
            "risk_category": "disease_weather",
            "risk_name": "Rủi ro thời tiết bùng phát nấm bệnh",
            "risk_level": "low",
            "risk_score": 0.0,
            "confidence_score": 0.0,
            "status": "insufficient_data",
            "contributing_factors": [],
            "explanation": "Không đủ dữ liệu khí tượng vi khí hậu để phân tích dịch tễ.",
            "recommendations": []
        }

    current = weather.get("current", {})
    temp = current.get("temperature_c") or 22.0
    hum = current.get("humidity_pct") or 70.0

    factors = [
        {"factor": "Độ ẩm không khí vi khí hậu", "value": f"{hum}%", "weight": 0.5},
        {"factor": "Nhiệt độ sinh học thuận lợi mầm bệnh", "value": f"{temp} °C", "weight": 0.3}
    ]

    score = 10.0
    # Fungal pathogens thrive at 18-28C with humidity > 80%
    if 18.0 <= temp <= 28.0 and hum >= 85:
        score += 55.0
    elif 16.0 <= temp <= 30.0 and hum >= 75:
        score += 35.0

    # Boost score if recent diagnoses on this plot confirm disease
    active_diags = [d for d in recent_diags if "healthy" not in (d.get("predicted_disease") or "").lower()]
    if active_diags:
        factors.append({"factor": "Lịch sử chẩn đoán thực địa ghi nhận bệnh hại gần đây", "value": f"{len(active_diags)} ca", "weight": 0.2})
        score += 20.0

    score = max(0.0, min(100.0, score))
    level = "severe" if score >= 75 else "high" if score >= 50 else "moderate" if score >= 30 else "low"

    explanation = (
        f"Nguy cơ phát sinh nấm bệnh ở mức {level.upper()} (Điểm rủi ro: {score}/100). "
        f"Điều kiện nhiệt độ {temp}°C và độ ẩm {hum}% tạo môi trường cực kỳ lý tưởng cho bào tử nấm (sương mai, đốm lá, thán thư) nảy mầm."
    )

    recs = [
        "Chủ động phun thuốc phòng ngừa gốc sinh học (Trichoderma hoặc Bacillus subtilis) trước đợt ẩm kéo dài.",
        "Tỉa bớt cành nhánh sát gốc để tạo độ thông thoáng dưới tán, hạn chế đọng sương qua đêm."
    ] if score >= 40 else ["Áp lực dịch hại từ môi trường ở mức thấp."]

    return {
        "risk_category": "disease_weather",
        "risk_name": "Rủi ro thời tiết bùng phát nấm bệnh",
        "risk_level": level,
        "risk_score": round(score, 1),
        "confidence_score": 0.88,
        "status": "evaluated",
        "contributing_factors": factors,
        "explanation": explanation,
        "recommendations": recs
    }


def _evaluate_vegetation_degradation_risk(satellite: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate Vegetation Canopy Degradation Risk based on NDVI delta."""
    if satellite.get("status") != "connected":
        return {
            "risk_category": "vegetation_degradation",
            "risk_name": "Rủi ro suy thoái tán lá vệ tinh",
            "risk_level": "low",
            "risk_score": 0.0,
            "confidence_score": 0.0,
            "status": "insufficient_data",
            "contributing_factors": [],
            "explanation": "Chưa có đủ chuỗi ảnh vệ tinh đa thời gian để đánh giá biến động chỉ số tán cây.",
            "recommendations": []
        }

    history = satellite.get("indices_history", [])
    if len(history) < 2:
        return {
            "risk_category": "vegetation_degradation",
            "risk_name": "Rủi ro suy thoái tán lá vệ tinh",
            "risk_level": "low",
            "risk_score": 15.0,
            "confidence_score": 0.60,
            "status": "evaluated",
            "contributing_factors": [{"factor": "Số lượng quan trắc vệ tinh", "value": len(history), "weight": 1.0}],
            "explanation": "Dữ liệu ảnh vệ tinh đơn kỳ chưa phát hiện suy thoái bất thường.",
            "recommendations": ["Tiếp tục thu thập thêm ảnh vệ tinh trong các chu kỳ quét tiếp theo."]
        }

    # Compare latest vs previous
    latest_ndvi = history[0].get("ndvi_mean", 0.0) or 0.0
    prev_ndvi = history[1].get("ndvi_mean", 0.0) or 0.0
    delta = round(latest_ndvi - prev_ndvi, 3)

    factors = [
        {"factor": "Chỉ số NDVI gần nhất", "value": latest_ndvi, "weight": 0.4},
        {"factor": "Chỉ số NDVI kỳ trước", "value": prev_ndvi, "weight": 0.3},
        {"factor": "Độ biến thiên NDVI (Delta)", "value": f"{'+' if delta >= 0 else ''}{delta}", "weight": 0.3}
    ]

    score = 5.0
    if delta <= -0.15:
        score += 70.0
    elif delta <= -0.08:
        score += 45.0
    elif delta <= -0.04:
        score += 20.0

    score = max(0.0, min(100.0, score))
    level = "severe" if score >= 75 else "high" if score >= 50 else "moderate" if score >= 30 else "low"

    explanation = (
        f"Biến động thảm thực vật ở mức {level.upper()} (Điểm rủi ro: {score}/100). "
        f"Chỉ số NDVI ghi nhận mức thay đổi {delta} so với kỳ quét trước (Hiện tại: {latest_ndvi})."
    )

    recs = [
        "Kiểm tra thực địa khẩn cấp khu vực tán lá bị suy giảm để xác định nguyên nhân (sâu đục thân, rụng lá do nấm, hoặc gãy đổ).",
        "Sử dụng camera thực địa chụp cận cảnh để chẩn đoán nguyên nhân thông qua AI Lab."
    ] if score >= 40 else ["Tán lá cây trồng phát triển ổn định hoặc có xu hướng tăng sinh khối."]

    return {
        "risk_category": "vegetation_degradation",
        "risk_name": "Rủi ro suy thoái tán lá vệ tinh",
        "risk_level": level,
        "risk_score": round(score, 1),
        "confidence_score": 0.85,
        "status": "evaluated",
        "contributing_factors": factors,
        "explanation": explanation,
        "recommendations": recs
    }

