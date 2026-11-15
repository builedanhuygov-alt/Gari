"""
GARI 3.0 — Smart Farming Calendar & Geo-Spatial Personalization Engine
Authoritative agronomic phenology and weather-adaptive scheduling engine for Vietnamese crops.
"""
from datetime import datetime, timedelta, timezone
import json
import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import gari_database
import gari_weather_service

logger = logging.getLogger("gari.calendar")

# ---------------------------------------------------------------------------
# VIETNAM 63 PROVINCES DATASET WITH GEOGRAPHIC CENTROIDS & CLIMATE ZONES
# ---------------------------------------------------------------------------
VIETNAM_PROVINCES = [
    {"code": "GL", "name": "Gia Lai", "region": "Tây Nguyên", "lat": 13.9833, "lon": 108.0000, "altitude_m": 750},
    {"code": "DL", "name": "Đắk Lắk", "region": "Tây Nguyên", "lat": 12.6667, "lon": 108.0500, "altitude_m": 500},
    {"code": "LD", "name": "Lâm Đồng", "region": "Tây Nguyên", "lat": 11.9404, "lon": 108.4583, "altitude_m": 1500},
    {"code": "DN", "name": "Đắk Nông", "region": "Tây Nguyên", "lat": 12.0000, "lon": 107.6833, "altitude_m": 600},
    {"code": "KT", "name": "Kon Tum", "region": "Tây Nguyên", "lat": 14.3500, "lon": 108.0000, "altitude_m": 600},
    {"code": "TG", "name": "Tiền Giang", "region": "Đồng bằng Sông Cửu Long", "lat": 10.3667, "lon": 106.3500, "altitude_m": 2},
    {"code": "BT", "name": "Bến Tre", "region": "Đồng bằng Sông Cửu Long", "lat": 10.2333, "lon": 106.3833, "altitude_m": 2},
    {"code": "CT", "name": "Cần Thơ", "region": "Đồng bằng Sông Cửu Long", "lat": 10.0333, "lon": 105.7833, "altitude_m": 2},
    {"code": "AG", "name": "An Giang", "region": "Đồng bằng Sông Cửu Long", "lat": 10.5167, "lon": 105.1167, "altitude_m": 4},
    {"code": "DT", "name": "Đồng Tháp", "region": "Đồng bằng Sông Cửu Long", "lat": 10.4500, "lon": 105.6333, "altitude_m": 3},
    {"code": "VL", "name": "Vĩnh Long", "region": "Đồng bằng Sông Cửu Long", "lat": 10.2500, "lon": 105.9667, "altitude_m": 2},
    {"code": "ST", "name": "Sóc Trăng", "region": "Đồng bằng Sông Cửu Long", "lat": 9.6000, "lon": 105.9833, "altitude_m": 1},
    {"code": "BL", "name": "Bạc Liêu", "region": "Đồng bằng Sông Cửu Long", "lat": 9.2833, "lon": 105.7167, "altitude_m": 1},
    {"code": "CM", "name": "Cà Mau", "region": "Đồng bằng Sông Cửu Long", "lat": 9.1833, "lon": 105.1500, "altitude_m": 1},
    {"code": "KG", "name": "Kiên Giang", "region": "Đồng bằng Sông Cửu Long", "lat": 10.0167, "lon": 105.0833, "altitude_m": 2},
    {"code": "HG", "name": "Hậu Giang", "region": "Đồng bằng Sông Cửu Long", "lat": 9.7833, "lon": 105.4667, "altitude_m": 2},
    {"code": "TV", "name": "Trà Vinh", "region": "Đồng bằng Sông Cửu Long", "lat": 9.9333, "lon": 106.3333, "altitude_m": 2},
    {"code": "LA", "name": "Long An", "region": "Đồng bằng Sông Cửu Long", "lat": 10.5333, "lon": 106.4000, "altitude_m": 3},
    {"code": "DNI", "name": "Đồng Nai", "region": "Đông Nam Bộ", "lat": 10.9500, "lon": 106.8167, "altitude_m": 50},
    {"code": "BD", "name": "Bình Dương", "region": "Đông Nam Bộ", "lat": 11.1667, "lon": 106.6500, "altitude_m": 30},
    {"code": "BP", "name": "Bình Phước", "region": "Đông Nam Bộ", "lat": 11.7500, "lon": 106.9000, "altitude_m": 100},
    {"code": "TN", "name": "Tây Ninh", "region": "Đông Nam Bộ", "lat": 11.3000, "lon": 106.1000, "altitude_m": 35},
    {"code": "BRVT", "name": "Bà Rịa - Vũng Tàu", "region": "Đông Nam Bộ", "lat": 10.5000, "lon": 107.1667, "altitude_m": 10},
    {"code": "HCM", "name": "Hồ Chí Minh", "region": "Đông Nam Bộ", "lat": 10.7769, "lon": 106.7009, "altitude_m": 10},
    {"code": "HN", "name": "Hà Nội", "region": "Đồng bằng Sông Hồng", "lat": 21.0285, "lon": 105.8542, "altitude_m": 15},
    {"code": "HP", "name": "Hải Phòng", "region": "Đồng bằng Sông Hồng", "lat": 20.8651, "lon": 106.6838, "altitude_m": 5},
    {"code": "HD", "name": "Hải Dương", "region": "Đồng bằng Sông Hồng", "lat": 20.9372, "lon": 106.3145, "altitude_m": 8},
    {"code": "HY", "name": "Hưng Yên", "region": "Đồng bằng Sông Hồng", "lat": 20.6500, "lon": 106.0500, "altitude_m": 6},
    {"code": "TB", "name": "Thái Bình", "region": "Đồng bằng Sông Hồng", "lat": 20.4500, "lon": 106.3333, "altitude_m": 4},
    {"code": "ND", "name": "Nam Định", "region": "Đồng bằng Sông Hồng", "lat": 20.4167, "lon": 106.1667, "altitude_m": 4},
    {"code": "NB", "name": "Ninh Bình", "region": "Đồng bằng Sông Hồng", "lat": 20.2500, "lon": 105.9667, "altitude_m": 5},
    {"code": "HNA", "name": "Hà Nam", "region": "Đồng bằng Sông Hồng", "lat": 20.5833, "lon": 105.9167, "altitude_m": 6},
    {"code": "BN", "name": "Bắc Ninh", "region": "Đồng bằng Sông Hồng", "lat": 21.1833, "lon": 106.0667, "altitude_m": 10},
    {"code": "VP", "name": "Vĩnh Phúc", "region": "Đồng bằng Sông Hồng", "lat": 21.3000, "lon": 105.6000, "altitude_m": 20},
    {"code": "TH", "name": "Thanh Hóa", "region": "Bắc Trung Bộ", "lat": 19.8000, "lon": 105.7667, "altitude_m": 15},
    {"code": "NA", "name": "Nghệ An", "region": "Bắc Trung Bộ", "lat": 18.6667, "lon": 105.6667, "altitude_m": 15},
    {"code": "HT", "name": "Hà Tĩnh", "region": "Bắc Trung Bộ", "lat": 18.3333, "lon": 105.9000, "altitude_m": 10},
    {"code": "QB", "name": "Quảng Bình", "region": "Bắc Trung Bộ", "lat": 17.4833, "lon": 106.6000, "altitude_m": 10},
    {"code": "QT", "name": "Quảng Trị", "region": "Bắc Trung Bộ", "lat": 16.7500, "lon": 107.1833, "altitude_m": 10},
    {"code": "TTH", "name": "Thừa Thiên Huế", "region": "Bắc Trung Bộ", "lat": 16.4667, "lon": 107.5833, "altitude_m": 12},
    {"code": "DNA", "name": "Đà Nẵng", "region": "Duyên hải Nam Trung Bộ", "lat": 16.0544, "lon": 108.2022, "altitude_m": 10},
    {"code": "QNA", "name": "Quảng Nam", "region": "Duyên hải Nam Trung Bộ", "lat": 15.5667, "lon": 108.4833, "altitude_m": 15},
    {"code": "QNG", "name": "Quảng Ngãi", "region": "Duyên hải Nam Trung Bộ", "lat": 15.1167, "lon": 108.8000, "altitude_m": 10},
    {"code": "BDH", "name": "Bình Định", "region": "Duyên hải Nam Trung Bộ", "lat": 14.1667, "lon": 109.0000, "altitude_m": 15},
    {"code": "PY", "name": "Phú Yên", "region": "Duyên hải Nam Trung Bộ", "lat": 13.0833, "lon": 109.3000, "altitude_m": 10},
    {"code": "KH", "name": "Khánh Hòa", "region": "Duyên hải Nam Trung Bộ", "lat": 12.2500, "lon": 109.1833, "altitude_m": 10},
    {"code": "NT", "name": "Ninh Thuận", "region": "Duyên hải Nam Trung Bộ", "lat": 11.5667, "lon": 108.9833, "altitude_m": 10},
    {"code": "BTH", "name": "Bình Thuận", "region": "Duyên hải Nam Trung Bộ", "lat": 11.1000, "lon": 108.2000, "altitude_m": 20},
    {"code": "TN", "name": "Thái Nguyên", "region": "Đông Bắc Bộ", "lat": 21.5833, "lon": 105.8333, "altitude_m": 45},
    {"code": "BG", "name": "Bắc Giang", "region": "Đông Bắc Bộ", "lat": 21.2667, "lon": 106.2000, "altitude_m": 25},
    {"code": "QN", "name": "Quảng Ninh", "region": "Đông Bắc Bộ", "lat": 21.0000, "lon": 107.3000, "altitude_m": 10},
    {"code": "LS", "name": "Lạng Sơn", "region": "Đông Bắc Bộ", "lat": 21.8500, "lon": 106.7500, "altitude_m": 260},
    {"code": "CB", "name": "Cao Bằng", "region": "Đông Bắc Bộ", "lat": 22.6667, "lon": 105.9667, "altitude_m": 300},
    {"code": "BK", "name": "Bắc Kạn", "region": "Đông Bắc Bộ", "lat": 22.1500, "lon": 105.8333, "altitude_m": 180},
    {"code": "TQ", "name": "Tuyên Quang", "region": "Đông Bắc Bộ", "lat": 21.8167, "lon": 105.2167, "altitude_m": 80},
    {"code": "HG", "name": "Hà Giang", "region": "Đông Bắc Bộ", "lat": 22.8167, "lon": 104.9833, "altitude_m": 450},
    {"code": "PT", "name": "Phú Thọ", "region": "Đông Bắc Bộ", "lat": 21.3167, "lon": 105.2167, "altitude_m": 35},
    {"code": "LC", "name": "Lào Cai", "region": "Tây Bắc Bộ", "lat": 22.4833, "lon": 103.9667, "altitude_m": 450},
    {"code": "YB", "name": "Yên Bái", "region": "Tây Bắc Bộ", "lat": 21.7167, "lon": 104.8667, "altitude_m": 120},
    {"code": "SL", "name": "Sơn La", "region": "Tây Bắc Bộ", "lat": 21.3167, "lon": 103.9000, "altitude_m": 650},
    {"code": "HB", "name": "Hòa Bình", "region": "Tây Bắc Bộ", "lat": 20.8167, "lon": 105.3333, "altitude_m": 60},
    {"code": "DB", "name": "Điện Biên", "region": "Tây Bắc Bộ", "lat": 21.3833, "lon": 103.0167, "altitude_m": 500},
    {"code": "LCH", "name": "Lai Châu", "region": "Tây Bắc Bộ", "lat": 22.3833, "lon": 103.4667, "altitude_m": 700}
]

PROVINCE_BY_NAME = {p["name"].lower(): p for p in VIETNAM_PROVINCES}


def lookup_province(query: str) -> Optional[Dict[str, Any]]:
    """Fuzzy lookup province by name or code."""
    if not query:
        return None
    q = query.strip().lower()
    for p in VIETNAM_PROVINCES:
        if q == p["name"].lower() or q == p["code"].lower():
            return p
        if q in p["name"].lower():
            return p
    return None


# ---------------------------------------------------------------------------
# CROP PHENOLOGY PROFILES (7 MAJOR VIETNAMESE CROPS)
# ---------------------------------------------------------------------------
CROP_PROFILES: Dict[str, Dict[str, Any]] = {
    "Coffee": {
        "name_vi": "Cà phê",
        "scientific_name": "Coffea canephora / arabica",
        "type": "perennial",  # Cây lâu năm
        "default_varieties": ["Robusta TR4", "Robusta TR9", "Catimor", "Thiện Trường"],
        "stages": [
            {
                "id": "seedling",
                "name": "Kiến thiết cơ bản (Năm 1 - 3)",
                "duration_days": 1095,
                "water_need": "Trung bình (20-30 lít/gốc, chu kỳ 15-20 ngày)",
                "fertilizer_focus": "Đạm & Lân cao (NPK 16-16-8) kích rễ non và đâm cành cấp 1",
                "key_tasks": [
                    {"title": "Tỉa cành tạo hình định khung tán", "type": "pruning", "interval_days": 60, "priority": "medium", "time_window": "Buổi sáng"},
                    {"title": "Bón lót phân hữu cơ hoai mục quanh tán", "type": "fertilizing", "interval_days": 90, "priority": "high", "time_window": "Sáng sớm mát"},
                    {"title": "Kiểm tra sâu đục thân và rệp sáp gốc", "type": "scouting", "interval_days": 15, "priority": "high", "time_window": "Sáng sớm"}
                ],
                "disease_risks": ["Rệp sáp gốc", "Sâu đục thân", "Lở cổ rễ non"],
                "ipm_practices": "Dùng nấm đối kháng Trichoderma, quét vôi gốc chống sâu đục thân."
            },
            {
                "id": "bud_induction",
                "name": "Hãm nước & Phân hóa mầm hoa (Tháng 12 - Tháng 1)",
                "duration_days": 60,
                "water_need": "Tuyệt đối không tưới nước (Hãm nước tối thiểu 45-60 ngày để hoa ngủ nghỉ)",
                "fertilizer_focus": "Rửa vườn bằng Bo + Kẽm, không bón đạm để tránh ra lộc non",
                "key_tasks": [
                    {"title": "Xiết nước tạo khô hạn kích hoa", "type": "watering", "interval_days": 30, "priority": "urgent", "time_window": "Cả ngày", "rationale": "Cà phê cần giai đoạn khô hạn để mầm hoa hoàn thiện miên trạng."},
                    {"title": "Phun rửa vườn sát khuẩn Bo-Kẽm", "type": "spraying", "interval_days": 25, "priority": "high", "time_window": "Sáng sớm không nắng gắt"},
                    {"title": "Tỉa sạch cành tăm, chồi vượt mùa khô", "type": "pruning", "interval_days": 20, "priority": "medium", "time_window": "Buổi sáng"}
                ],
                "disease_risks": ["Rỉ sắt giai đoạn rụng lá", "Rệp sáp vảy"],
                "ipm_practices": "Làm sạch cỏ gốc tạo độ thoáng, bắt bọ xít muỗi."
            },
            {
                "id": "flowering",
                "name": "Nở hoa & Thụ phấn (Tháng 2 - Tháng 3)",
                "duration_days": 45,
                "water_need": "Rất cao (Tưới bung hoa đợt 1: 350-450 lít/cây, tưới nhắc lại sau 15-20 ngày)",
                "fertilizer_focus": "Bón NPK cân đối sau tưới đợt 1, bổ sung Canxi-Bo chống rụng hoa",
                "key_tasks": [
                    {"title": "Tưới bung hoa đợt 1 đuổi hoa", "type": "watering", "interval_days": 20, "priority": "urgent", "time_window": "Sáng sớm", "rationale": "Cung cấp đủ nước để hoa nở bung trắng đồng loạt, tỷ lệ thụ phấn tối đa."},
                    {"title": "Phun vi lượng Bo hỗ trợ hạt phấn vươn dài", "type": "spraying", "interval_days": 15, "priority": "high", "time_window": "Chiều mát trước hoa nở"},
                    {"title": "Thăm vườn theo dõi mọt đục cành & bọ xít", "type": "scouting", "interval_days": 7, "priority": "medium", "time_window": "Sáng sớm"}
                ],
                "disease_risks": ["Khô cành khô quả non", "Bọ xít muỗi chích hoa"],
                "ipm_practices": "Không phun thuốc hóa học khi hoa đang nở rộ để bảo vệ ong thụ phấn."
            },
            {
                "id": "fruit_development",
                "name": "Nuôi quả & Phát triển nhân (Tháng 4 - Tháng 8)",
                "duration_days": 150,
                "water_need": "Dồi dào (Mùa mưa Tây Nguyên, chú ý thoát nước chống úng rễ)",
                "fertilizer_focus": "NPK 19-9-19 + TE giàu Kali giúp vào nhân chắc hạt",
                "key_tasks": [
                    {"title": "Bón phân nuôi quả đợt mùa mưa (NPK 19-9-19)", "type": "fertilizing", "interval_days": 40, "priority": "high", "time_window": "Sau mưa khi đất đủ ẩm"},
                    {"title": "Kiểm tra phòng trị bệnh rỉ sắt và nấm hồng", "type": "scouting", "interval_days": 10, "priority": "high", "time_window": "Sáng sớm", "rationale": "Mùa mưa ẩm là điều kiện tối ưu để nấm Hemileia vastatrix gây rỉ sắt lan truyền."},
                    {"title": "Tỉa bỏ chồi vượt và cành vô hiệu nuôi quả", "type": "pruning", "interval_days": 30, "priority": "medium", "time_window": "Buổi sáng nắng ráo"}
                ],
                "disease_risks": ["Bệnh rỉ sắt lá", "Nấm hồng cành", "Rệp sáp cuống quả"],
                "ipm_practices": "Tỉa thông thoáng tán, dùng thuốc trừ nấm sinh học hoạt chất Bacillus/Copper."
            },
            {
                "id": "harvest",
                "name": "Chín quả & Thu hoạch (Tháng 9 - Tháng 12)",
                "duration_days": 90,
                "water_need": "Giảm dần để tích đường trong quả",
                "fertilizer_focus": "Ngừng phân hóa học trước thu hái 20 ngày",
                "key_tasks": [
                    {"title": "Thu hái quả chín có chọn lọc (Tỷ lệ chín > 90%)", "type": "harvesting", "interval_days": 10, "priority": "urgent", "time_window": "Sáng và chiều mát", "rationale": "Hái chọn từng đợt quả chín để đạt hương vị cupping và khối lượng nhân tốt nhất."},
                    {"title": "Vận chuyển và phơi sấy trong ngày", "type": "routine", "interval_days": 7, "priority": "high", "time_window": "Trong vòng 24h sau hái"}
                ],
                "disease_risks": ["Nấm mốc quả sau thu hoạch", "Rụng quả non đợt sau"],
                "ipm_practices": "Không tuốt cành bẻ mắt mầm cuống, vệ sinh bạt thu hái sạch sẽ."
            },
            {
                "id": "post_harvest",
                "name": "Phục hồi sau thu hoạch (Tháng 12 - Tháng 1)",
                "duration_days": 45,
                "water_need": "Hạn chế để chuẩn bị bước vào chu kỳ phân hóa mầm hoa mới",
                "fertilizer_focus": "Bón vôi nông nghiệp và lân nung chảy cải tạo pH đất",
                "key_tasks": [
                    {"title": "Cắt tỉa toàn bộ cành khô, cành sâu bệnh", "type": "pruning", "interval_days": 20, "priority": "high", "time_window": "Sáng ráo"},
                    {"title": "Bón phân hữu cơ vi sinh phục hồi rễ", "type": "fertilizing", "interval_days": 30, "priority": "high", "time_window": "Sáng sớm"}
                ],
                "disease_risks": ["Nấm hoại tử cành cắt", "Bệnh thối rễ"],
                "ipm_practices": "Quét keo liền sẹo hoặc gốc đồng lên vết cắt lớn."
            }
        ]
    },
    "Pepper": {
        "name_vi": "Hồ tiêu",
        "scientific_name": "Piper nigrum",
        "type": "perennial",
        "default_varieties": ["Vĩnh Linh", "Ấn Độ", "Trâu", "Lộc Ninh"],
        "stages": [
            {
                "id": "seedling",
                "name": "Kiến thiết cơ bản (Trồng mới & Leo trụ)",
                "duration_days": 730,
                "water_need": "Đều đặn, chống úng triệt để",
                "fertilizer_focus": "Phân hữu cơ hoai + Lân nung chảy kích rễ",
                "key_tasks": [
                    {"title": "Buộc thân dây tiêu vào trụ sống", "type": "routine", "interval_days": 15, "priority": "medium", "time_window": "Chiều mát"},
                    {"title": "Xới phá váng và thoát rãnh thoát nước", "type": "routine", "interval_days": 30, "priority": "high", "time_window": "Sáng sớm"}
                ],
                "disease_risks": ["Tuyến trùng rễ", "Lở cổ rễ"],
                "ipm_practices": "Tưới men vi sinh rễ Trichoderma 3 tháng/lần."
            },
            {
                "id": "vegetative",
                "name": "Sinh trưởng cơi tược & Làm sạch tán trụ",
                "duration_days": 90,
                "water_need": "Trung bình",
                "fertilizer_focus": "NPK cân đối + trung vi lượng",
                "key_tasks": [
                    {"title": "Rong tỉa cành trụ sống tăng ánh sáng", "type": "pruning", "interval_days": 45, "priority": "high", "time_window": "Sáng ráo"},
                    {"title": "Kiểm tra triệu chứng chết nhanh Phytophthora", "type": "scouting", "interval_days": 7, "priority": "urgent", "time_window": "Sáng sớm", "rationale": "Phytophthora capsici có thể làm vàng lá rụng đốt chỉ sau 5-7 ngày."}
                ],
                "disease_risks": ["Chết nhanh (Phytophthora)", "Tuyến trùng hại rễ"],
                "ipm_practices": "Rãnh thoát nước sâu 40-50cm giữa 2 hàng tiêu."
            },
            {
                "id": "flowering",
                "name": "Ra gié hoa & Thụ phấn",
                "duration_days": 40,
                "water_need": "Đủ ẩm đều, tránh khô hạn đột ngột",
                "fertilizer_focus": "Bổ sung Canxi-Bo chống rụng chuỗi tiêu",
                "key_tasks": [
                    {"title": "Phun Bo vi lượng tăng đậu quả gié tiêu", "type": "spraying", "interval_days": 14, "priority": "high", "time_window": "Chiều râm"},
                    {"title": "Kiểm tra bọ xít lưới chích bông", "type": "scouting", "interval_days": 7, "priority": "medium", "time_window": "Sáng sớm"}
                ],
                "disease_risks": ["Bọ xít lưới", "Thán thư gié hoa"],
                "ipm_practices": "Phun dầu khoáng sinh học xua đuổi côn trùng."
            },
            {
                "id": "fruit_development",
                "name": "Nuôi quả & Vào chắc hạt",
                "duration_days": 120,
                "water_need": "Đầy đủ trong mùa mưa",
                "fertilizer_focus": "Tăng Kali Sunfat (K2SO4) giúp quả bóng mẩy, thơm cay",
                "key_tasks": [
                    {"title": "Bón thúc nuôi hạt sọ NPK giàu Kali", "type": "fertilizing", "interval_days": 30, "priority": "high", "time_window": "Đất ẩm"},
                    {"title": "Thăm vườn kiểm tra vàng lá chết chậm (Fusarium)", "type": "scouting", "interval_days": 10, "priority": "urgent", "time_window": "Sáng"}
                ],
                "disease_risks": ["Bệnh chết chậm (Tuyến trùng + Nấm)", "Bệnh tảo đỏ"],
                "ipm_practices": "Tránh cày xới sâu đứt rễ tiêu, dùng thuốc trừ tuyến trùng sinh học."
            },
            {
                "id": "harvest",
                "name": "Thu hoạch & Phơi tiêu sọ/tiêu đen",
                "duration_days": 60,
                "water_need": "Khô ráo",
                "fertilizer_focus": "Ngừng phân hóa học",
                "key_tasks": [
                    {"title": "Thu hoạch chùm tiêu có quả đỏ", "type": "harvesting", "interval_days": 10, "priority": "high", "time_window": "Sáng ráo"},
                    {"title": "Tách hạt và phơi sạch trên sân phơi lót bạt", "type": "routine", "interval_days": 7, "priority": "medium", "time_window": "Ban ngày"}
                ],
                "disease_risks": ["Nấm mốc bảo quản"],
                "ipm_practices": "Độ ẩm hạt sau phơi < 12.5%."
            }
        ]
    },
    "Durian": {
        "name_vi": "Sầu riêng",
        "scientific_name": "Durio zibethinus",
        "type": "perennial",
        "default_varieties": ["Ri6", "Monthong (Dona)", "Musang King", "Black Thorn"],
        "stages": [
            {
                "id": "seedling",
                "name": "Kiến thiết cơ bản (Năm 1 - 4)",
                "duration_days": 1460,
                "water_need": "Tưới phun gốc 2-3 ngày/lần, không đọng úng cổ rễ",
                "fertilizer_focus": "Phân chuồng ủ Trichoderma + NPK 20-10-10",
                "key_tasks": [
                    {"title": "Tạo bồn nổi mô cao chống úng cổ rễ", "type": "routine", "interval_days": 90, "priority": "urgent", "time_window": "Sáng sớm"},
                    {"title": "Kiểm tra rầy xanh và bọ trĩ phá cơi đọt", "type": "scouting", "interval_days": 7, "priority": "high", "time_window": "Chiều mát"}
                ],
                "disease_risks": ["Xì mủ thân (Phytophthora palmivora)", "Rầy xanh phá đọt non"],
                "ipm_practices": "Phòng trừ rầy xanh ngay khi nhú mũi giáo bằng nấm xanh nấm trắng."
            },
            {
                "id": "flush_recovery",
                "name": "Kéo đọt & Phục hồi cơi lá (Cơi 1 - Cơi 2)",
                "duration_days": 60,
                "water_need": "Đầy đủ, kích thích đọt bung đều",
                "fertilizer_focus": "Humic + Amino Axit + Đạm cao",
                "key_tasks": [
                    {"title": "Tưới dưỡng rễ Humic + Vi lượng đọt", "type": "fertilizing", "interval_days": 15, "priority": "high", "time_window": "Sáng sớm"},
                    {"title": "Phun phòng rầy xanh bảo vệ cơi đọt non", "type": "spraying", "interval_days": 7, "priority": "urgent", "time_window": "Chiều mát khi tắt nắng", "rationale": "Rầy xanh chích hút làm đọt non rụt ngọn chổi chà."}
                ],
                "disease_risks": ["Rầy xanh chích đọt", "Cháy lá chết ngọn (Rhizoctonia)"],
                "ipm_practices": "Phun luân phiên gốc sinh học bảo vệ tầng lá nguyên vẹn."
            },
            {
                "id": "flower_induction",
                "name": "Xử lý xiết nước ra hoa & Mắt cua",
                "duration_days": 50,
                "water_need": "Cắt nước hoàn toàn 20-30 ngày cho đến khi mắt cua sáng",
                "fertilizer_focus": "Lân cao (MKP 0-52-34) ủ mầm hoa, hãm đọt",
                "key_tasks": [
                    {"title": "Vét rãnh xiết nước tạo khô hạn", "type": "watering", "interval_days": 20, "priority": "urgent", "time_window": "Cả ngày"},
                    {"title": "Tỉa hoa đợt 1 (bỏ chùm hoa đầu cành, sát thân)", "type": "pruning", "interval_days": 10, "priority": "high", "time_window": "Sáng ráo"}
                ],
                "disease_risks": ["Mốc sương hoa", "Thán thư bông"],
                "ipm_practices": "Chỉ nhấp nhẹ nước khi mắt cua đã sáng rõ > 80%."
            },
            {
                "id": "anthesis",
                "name": "Xả nhị & Đậu trái non",
                "duration_days": 30,
                "water_need": "Giảm nước xuống 30-50% mức bình thường",
                "fertilizer_focus": "Bo-Canxi chống rụng cánh và cuống hoa",
                "key_tasks": [
                    {"title": "Thụ phấn bổ sung vào ban đêm (18h-20h)", "type": "routine", "interval_days": 3, "priority": "urgent", "time_window": "18:00 - 20:30 tối", "rationale": "Hoa sầu riêng nở về đêm, quét phấn nhân tạo tăng tỷ lệ trái tròn đều hộc."},
                    {"title": "Phòng bọ trĩ phá cánh hoa và cuống", "type": "scouting", "interval_days": 5, "priority": "high", "time_window": "Sáng sớm"}
                ],
                "disease_risks": ["Bọ trĩ", "Rụng hoa hàng loạt"],
                "ipm_practices": "Tránh tưới phun trực tiếp vào chùm hoa xả nhị."
            },
            {
                "id": "fruit_development",
                "name": "Nuôi trái & Chống sốc rụng trái",
                "duration_days": 100,
                "water_need": "Tưới đều đặn không để đất nứt rồi ngập nước sốc rụng trái",
                "fertilizer_focus": "NPK 12-12-17 + K2SO4 tăng cơm vàng hạt lép",
                "key_tasks": [
                    {"title": "Tỉa quả chọn lọc giữ trái tròn đều", "type": "pruning", "interval_days": 14, "priority": "high", "time_window": "Sáng"},
                    {"title": "Cột dây neo cành đỡ trái chống gãy gió", "type": "routine", "interval_days": 20, "priority": "urgent", "time_window": "Ban ngày"},
                    {"title": "Kiểm tra sâu đục trái và rệp sáp hốc gai", "type": "scouting", "interval_days": 7, "priority": "high", "time_window": "Sáng sớm"}
                ],
                "disease_risks": ["Xì mủ nứt trái", "Sâu đục trái", "Rệp sáp trái"],
                "ipm_practices": "Bao bọc trái hoặc dùng bẫy pheromone bướm sâu đục trái."
            },
            {
                "id": "harvest",
                "name": "Thu hoạch & Phân loại trái",
                "duration_days": 45,
                "water_need": "Ngừng tưới trước hái 5-7 ngày",
                "fertilizer_focus": "Cách ly tuyệt đối trước thu hoạch 20 ngày",
                "key_tasks": [
                    {"title": "Cắt trái già đạt độ đường (gõ tiếng bộp)", "type": "harvesting", "interval_days": 5, "priority": "urgent", "time_window": "Sáng mát"},
                    {"title": "Lau sạch cuống và đặt nơi thoáng mát", "type": "routine", "interval_days": 5, "priority": "medium", "time_window": "Trong ngày"}
                ],
                "disease_risks": ["Thối đít trái sau hái"],
                "ipm_practices": "Không để cuống trái chạm bùn đất nhiễm khuẩn."
            }
        ]
    },
    "Rice": {
        "name_vi": "Lúa nước",
        "scientific_name": "Oryza sativa",
        "type": "annual",
        "default_varieties": ["ST25", "OM5451", "Jasmine 85", "Nếp Hương", "Bắc Thơm 7"],
        "stages": [
            {
                "id": "nursery",
                "name": "Gieo mạ & Ngâm ủ giống (0 - 12 ngày)",
                "duration_days": 12,
                "water_need": "Giữ ẩm luống mạ",
                "fertilizer_focus": "Xử lý hạt giống bằng Trichoderma",
                "key_tasks": [
                    {"title": "Ngâm ủ mầm nứt nanh và gieo cấy", "type": "routine", "interval_days": 10, "priority": "urgent", "time_window": "Sáng sớm"},
                    {"title": "Kiểm tra bọ trĩ mạ non và ốc bươu vàng", "type": "scouting", "interval_days": 3, "priority": "high", "time_window": "Sáng sớm"}
                ],
                "disease_risks": ["Bọ trĩ", "Ốc bươu vàng", "Lúa von"],
                "ipm_practices": "Bắt ốc thủ công, đặt rãnh thoát bắt ốc."
            },
            {
                "id": "tillering",
                "name": "Đẻ nhánh & Làm cỏ sục bùn (13 - 40 ngày)",
                "duration_days": 28,
                "water_need": "Mực nước nông 2-3cm",
                "fertilizer_focus": "Bón thúc đợt 1 NPK giàu Đạm kích nhánh hữu hiệu",
                "key_tasks": [
                    {"title": "Bón thúc đẻ nhánh đợt 1 + Làm cỏ sục bùn", "type": "fertilizing", "interval_days": 12, "priority": "high", "time_window": "Sáng sớm"},
                    {"title": "Rút nước phơi ruộng nứt chân chim 5 ngày", "type": "watering", "interval_days": 25, "priority": "high", "time_window": "Giữa vụ", "rationale": "Khống chế nhánh vô hiệu, kích rễ ăn sâu chống đổ ngã."}
                ],
                "disease_risks": ["Đạo ôn lá", "Sâu cuốn lá nhỏ"],
                "ipm_practices": "Duy trì mực nước điều hòa nhiệt, không bón thừa đạm."
            },
            {
                "id": "panicle_initiation",
                "name": "Làm đòng & Phân hóa hoa (41 - 65 ngày)",
                "duration_days": 25,
                "water_need": "Giữ nước ruộng 3-5cm",
                "fertilizer_focus": "Bón phân đón đòng (NPK có Kali cao)",
                "key_tasks": [
                    {"title": "Bón phân đón đòng khi đòng nhú 1-2mm", "type": "fertilizing", "interval_days": 20, "priority": "urgent", "time_window": "Chiều mát"},
                    {"title": "Kiểm tra rầy nâu và sâu đục thân 2 chấm", "type": "scouting", "interval_days": 5, "priority": "urgent", "time_window": "Sáng sớm"}
                ],
                "disease_risks": ["Đạo ôn cổ bông", "Rầy nâu", "Khô vằn"],
                "ipm_practices": "Kiểm tra gốc lúa tìm ổ trứng rầy nâu."
            },
            {
                "id": "heading",
                "name": "Trổ bông & Thụ phấn (66 - 85 ngày)",
                "duration_days": 20,
                "water_need": "Đầy đủ nước, tuyệt đối không để hạn",
                "fertilizer_focus": "Phun phòng lem lép hạt trước trổ 3-5 ngày",
                "key_tasks": [
                    {"title": "Phun phòng bệnh lem lép hạt trước và sau trổ đều", "type": "spraying", "interval_days": 10, "priority": "urgent", "time_window": "Sáng không có gió mạnh"},
                    {"title": "Theo dõi bệnh khô vằn bẹ lá", "type": "scouting", "interval_days": 5, "priority": "high", "time_window": "Sáng"}
                ],
                "disease_risks": ["Lem lép hạt", "Bệnh bạc lá vi khuẩn"],
                "ipm_practices": "Không phun thuốc hóa học vào thời điểm hoa đang nở rộ 8h-11h sáng."
            },
            {
                "id": "ripening",
                "name": "Chín sáp & Thu hoạch (86 - 110 ngày)",
                "duration_days": 25,
                "water_need": "Tháo cạn nước trước gặt 7-10 ngày",
                "fertilizer_focus": "Không bón phân",
                "key_tasks": [
                    {"title": "Tháo cạn lòng ruộng tạo nền cứng cho máy gặt", "type": "watering", "interval_days": 15, "priority": "high", "time_window": "Ban ngày"},
                    {"title": "Thu hoạch bằng máy gặt đập liên hợp (Chín 85-90%)", "type": "harvesting", "interval_days": 5, "priority": "urgent", "time_window": "Trưa nắng ráo"}
                ],
                "disease_risks": ["Đổ ngã do mưa dông", "Chuột cắn phá"],
                "ipm_practices": "Thu gom rơm rạ, cày lật gốc rạ vùi phân giải hữu cơ."
            }
        ]
    },
    "Tomato": {
        "name_vi": "Cà chua",
        "scientific_name": "Solanum lycopersicum",
        "type": "annual",
        "default_varieties": ["Anna", "Beef", "Cherry Ngọc Viên", "Mỹ Linh"],
        "stages": [
            {
                "id": "seedling",
                "name": "Gieo ươm & Cây con ra luống (0 - 25 ngày)",
                "duration_days": 25,
                "water_need": "Tưới phun sương nhẹ giữ ẩm 70-75%",
                "fertilizer_focus": "Ủ Trichoderma giá thể + kích rễ nhẹ",
                "key_tasks": [
                    {"title": "Cấy cây con ra luống phủ màng nông nghiệp", "type": "routine", "interval_days": 20, "priority": "urgent", "time_window": "Chiều mát"},
                    {"title": "Kiểm tra sâu vẽ bùa và lở cổ rễ non", "type": "scouting", "interval_days": 4, "priority": "high", "time_window": "Sáng sớm"}
                ],
                "disease_risks": ["Lở cổ rễ Rhizoctonia", "Sâu vẽ bùa"],
                "ipm_practices": "Phủ bạt nylon giữ ẩm và triệt tiêu mầm cỏ dại."
            },
            {
                "id": "vegetative",
                "name": "Phát triển thân lá & Cắm giàn (26 - 45 ngày)",
                "duration_days": 20,
                "water_need": "Tưới rãnh định kỳ",
                "fertilizer_focus": "NPK 20-20-15 thúc sinh khối",
                "key_tasks": [
                    {"title": "Cắm giàn chữ A và bấm tỉa chồi nách", "type": "pruning", "interval_days": 7, "priority": "high", "time_window": "Sáng ráo"},
                    {"title": "Bón thúc đợt 1 NPK hòa tan", "type": "fertilizing", "interval_days": 10, "priority": "medium", "time_window": "Chiều mát"}
                ],
                "disease_risks": ["Đốm lá vi khuẩn", "Bọ phấn trắng truyền xoăn lá"],
                "ipm_practices": "Tỉa sạch toàn bộ nhánh bên dưới chùm hoa thứ nhất."
            },
            {
                "id": "flowering",
                "name": "Ra hoa rộ & Đậu quả non (46 - 65 ngày)",
                "duration_days": 20,
                "water_need": "Không tưới đẫm ngập rãnh, tưới gốc đều",
                "fertilizer_focus": "Bổ sung Canxi-Bo chống rụng hoa & thối đít quả",
                "key_tasks": [
                    {"title": "Phun bổ sung Canxi-Bo chống thối đít quả non", "type": "spraying", "interval_days": 7, "priority": "high", "time_window": "Sáng sớm"},
                    {"title": "Kiểm tra bọ phấn trắng và bọ trĩ", "type": "scouting", "interval_days": 4, "priority": "high", "time_window": "Sáng sớm"}
                ],
                "disease_risks": ["Thối đít trái (thiếu Canxi)", "Thán thư"],
                "ipm_practices": "Dùng bẫy dính màu vàng bắt bọ phấn trắng."
            },
            {
                "id": "fruit_development",
                "name": "Nuôi quả lớn & Chín chuyển màu (66 - 95 ngày)",
                "duration_days": 30,
                "water_need": "Đều đặn, không để khô hạn làm nứt vỏ khi tưới lại",
                "fertilizer_focus": "Tăng Kali Sunfat làm dày cơm, ngọt quả",
                "key_tasks": [
                    {"title": "Bón Kali hòa tưới nuôi quả lớn", "type": "fertilizing", "interval_days": 10, "priority": "high", "time_window": "Chiều mát"},
                    {"title": "Kiểm tra phòng trừ bệnh mốc sương (Phytophthora infestans)", "type": "scouting", "interval_days": 3, "priority": "urgent", "time_window": "Sáng sớm", "rationale": "Sương mù ẩm ướt là tác nhân khiến mốc sương phá hoại toàn bộ ruộng trong 48h."}
                ],
                "disease_risks": ["Mốc sương (Phytophthora infestans)", "Ruồi đục quả"],
                "ipm_practices": "Cắt tỉa lá già sát đất, vệ sinh thông thoáng gốc."
            },
            {
                "id": "harvest",
                "name": "Thu hoạch từng đợt (96 - 120 ngày)",
                "duration_days": 25,
                "water_need": "Vừa phải",
                "fertilizer_focus": "Cách ly an toàn thuốc & phân bón",
                "key_tasks": [
                    {"title": "Thu hái quả chuyển màu ương hoặc đỏ đều", "type": "harvesting", "interval_days": 3, "priority": "urgent", "time_window": "Sáng ráo"},
                    {"title": "Phân loại quả loại 1, xếp sọt lót xốp", "type": "routine", "interval_days": 3, "priority": "medium", "time_window": "Trong ngày"}
                ],
                "disease_risks": ["Dập nát thối nhũn vi khuẩn"],
                "ipm_practices": "Dùng kéo cắt giữ lại cuống quả."
            }
        ]
    },
    "Chili": {
        "name_vi": "Ớt cay",
        "scientific_name": "Capsicum frutescens / annuum",
        "type": "annual",
        "default_varieties": ["Ớt chỉ thiên", "Ớt sừng trâu", "Ớt hiểm F1", "Habanero"],
        "stages": [
            {
                "id": "seedling",
                "name": "Ươm mầm & Cây con ra luống (0 - 30 ngày)",
                "duration_days": 30,
                "water_need": "Ẩm vừa phải, tuyệt đối không ngập úng",
                "fertilizer_focus": "Trichoderma + kích rễ sinh học",
                "key_tasks": [
                    {"title": "Xuất vườn cấy bầu ớt ra luống cao", "type": "routine", "interval_days": 25, "priority": "high", "time_window": "Chiều râm"},
                    {"title": "Kiểm tra sâu ăn lá và lở cổ rễ con", "type": "scouting", "interval_days": 4, "priority": "medium", "time_window": "Sáng sớm"}
                ],
                "disease_risks": ["Héo rũ gốc mốc trắng", "Bọ trĩ đọt non"],
                "ipm_practices": "Vun luống cao 30cm, phủ bạt đục lỗ cấy cây."
            },
            {
                "id": "flowering",
                "name": "Phân cành & Ra hoa rộ (31 - 60 ngày)",
                "duration_days": 30,
                "water_need": "Tưới rãnh định kỳ 3 ngày/lần",
                "fertilizer_focus": "NPK 15-15-15 + Canxi Bo",
                "key_tasks": [
                    {"title": "Cắm cọc cố định thân ớt chống gió lốc", "type": "routine", "interval_days": 15, "priority": "high", "time_window": "Sáng sớm"},
                    {"title": "Phun phòng bệnh thán thư ớt (Colletotrichum)", "type": "spraying", "interval_days": 7, "priority": "urgent", "time_window": "Sáng sớm ráo lá", "rationale": "Thán thư là bệnh dịch nguy hiểm số 1 trên ớt, làm thối đốm mắt cua quả non."}
                ],
                "disease_risks": ["Thán thư ớt", "Héo xanh vi khuẩn"],
                "ipm_practices": "Nhổ bỏ ngay cây ớt bị héo xanh vi khuẩn đem tiêu hủy rắc vôi bột."
            },
            {
                "id": "harvest",
                "name": "Nuôi quả & Thu hoạch từng lứa (61 - 120 ngày)",
                "duration_days": 60,
                "water_need": "Duy trì độ ẩm luống",
                "fertilizer_focus": "Bón dặm phân hữu cơ hoai sau mỗi đợt hái",
                "key_tasks": [
                    {"title": "Thu hái trái ớt chín đỏ từng lứa", "type": "harvesting", "interval_days": 4, "priority": "urgent", "time_window": "Sáng ráo"},
                    {"title": "Bón thúc hồi phục lứa hái kế tiếp", "type": "fertilizing", "interval_days": 12, "priority": "medium", "time_window": "Chiều mát"}
                ],
                "disease_risks": ["Bọ trĩ", "Ruồi vàng đục quả ớt"],
                "ipm_practices": "Treo bẫy dính protein dẫn dụ ruồi vàng quanh bờ ruộng."
            }
        ]
    },
    "Corn": {
        "name_vi": "Ngô (Bắp)",
        "scientific_name": "Zea mays",
        "type": "annual",
        "default_varieties": ["NK7328", "CP511", "Bắp ngọt F1 Sugar 75", "Bắp nếp Tươi"],
        "stages": [
            {
                "id": "vegetative",
                "name": "Cây con 3-5 lá & Vươn lóng (0 - 35 ngày)",
                "duration_days": 35,
                "water_need": "Đủ ẩm nảy mầm",
                "fertilizer_focus": "Bón lót Lân + Bón thúc 1 Đạm Ure",
                "key_tasks": [
                    {"title": "Bón thúc đợt 1 kết hợp xới vun gốc ngô", "type": "fertilizing", "interval_days": 15, "priority": "high", "time_window": "Sáng sớm"},
                    {"title": "Kiểm tra sâu keo mùa thu (Spodoptera frugiperda)", "type": "scouting", "interval_days": 4, "priority": "urgent", "time_window": "Chiều mát", "rationale": "Sâu keo cắn cụt nõn bắp non làm cây chột ngọn không trổ cờ."}
                ],
                "disease_risks": ["Sâu keo mùa thu", "Bệnh lở cổ rễ"],
                "ipm_practices": "Dùng chế phẩm nấm ký sinh Metarhizium diệt ấu trùng sâu non."
            },
            {
                "id": "tasseling",
                "name": "Trổ cờ & Phun râu thụ phấn (36 - 65 ngày)",
                "duration_days": 30,
                "water_need": "Thời kỳ khủng hoảng nước, cần đủ ẩm",
                "fertilizer_focus": "Bón thúc đón bắp NPK giàu Kali",
                "key_tasks": [
                    {"title": "Tưới nước đảm bảo ruộng đủ ẩm khi trổ cờ", "type": "watering", "interval_days": 7, "priority": "urgent", "time_window": "Sáng sớm"},
                    {"title": "Kiểm tra rệp cờ và sâu đục thân bắp", "type": "scouting", "interval_days": 5, "priority": "high", "time_window": "Sáng"}
                ],
                "disease_risks": ["Bệnh đốm lá lớn", "Khô vằn bẹ"],
                "ipm_practices": "Cắt bỏ bớt chồi nách gốc chỉ giữ 1 bắp chính đạt kích thước to."
            },
            {
                "id": "harvest",
                "name": "Chín sữa vào hạt & Thu hoạch (66 - 95 ngày)",
                "duration_days": 30,
                "water_need": "Giảm nước",
                "fertilizer_focus": "Ngừng bón phân",
                "key_tasks": [
                    {"title": "Thu hoạch bắp tươi khi râu bắp chuyển đen nâu", "type": "harvesting", "interval_days": 5, "priority": "urgent", "time_window": "Sáng sớm mát"}
                ],
                "disease_risks": ["Mọt bắp sau thu hoạch"],
                "ipm_practices": "Bẻ bắp phơi sấy ngay, không chất đống ẩm mốc."
            }
        ]
    }
}


def normalize_crop_key(crop_input: str) -> str:
    """Map common Vietnamese or English names to standard crop keys."""
    if not crop_input:
        return "Coffee"
    c = str(crop_input).strip().lower()
    if any(k in c for k in ["cà phê", "ca phe", "coffee", "tr4", "tr9", "robusta"]):
        return "Coffee"
    if any(k in c for k in ["tiêu", "hồ tiêu", "ho tieu", "pepper", "vĩnh linh"]):
        return "Pepper"
    if any(k in c for k in ["sầu riêng", "sau rieng", "durian", "ri6", "monthong", "dona"]):
        return "Durian"
    if any(k in c for k in ["lúa", "lua", "rice", "st25", "om5451", "lúa nước"]):
        return "Rice"
    if any(k in c for k in ["cà chua", "ca chua", "tomato"]):
        return "Tomato"
    if any(k in c for k in ["ớt", "ot", "chili", "chilli", "chỉ thiên"]):
        return "Chili"
    if any(k in c for k in ["ngô", "ngo", "bắp", "bap", "corn", "maize"]):
        return "Corn"
    return "Coffee"


# ---------------------------------------------------------------------------
# WEATHER ADAPTIVE TASK SCHEDULER & ALERT ENGINE
# ---------------------------------------------------------------------------
class SmartFarmingScheduleEngine:
    """
    Core engine generating localized, farm-specific phenological schedules
    and dynamically adapting tasks against live Open-Meteo forecasts.
    """

    @staticmethod
    def get_growth_stage_progress(
        crop_key: str,
        stage_id: Optional[str] = None,
        planting_date_str: Optional[str] = None,
        tree_age_years: float = 1.0
    ) -> Dict[str, Any]:
        """Calculate current phenology stage, days in stage, and stage completion pct."""
        profile = CROP_PROFILES.get(crop_key, CROP_PROFILES["Coffee"])
        stages = profile["stages"]

        # Default to first stage or matched stage
        active_idx = 0
        if stage_id:
            for idx, stg in enumerate(stages):
                if stg["id"] == stage_id or stg["name"].lower() == stage_id.lower():
                    active_idx = idx
                    break
        elif profile["type"] == "perennial" and tree_age_years >= 3.0:
            # Perennial adult stage based on current month
            curr_month = datetime.now(timezone.utc).month
            if crop_key == "Coffee":
                if curr_month in [12, 1]:
                    active_idx = 1  # bud_induction
                elif curr_month in [2, 3]:
                    active_idx = 2  # flowering
                elif curr_month in range(4, 9):
                    active_idx = 3  # fruit_development
                elif curr_month in range(9, 12):
                    active_idx = 4  # harvest
                else:
                    active_idx = 5
            elif crop_key == "Durian":
                if curr_month in [11, 12, 1]:
                    active_idx = 2  # flower_induction
                elif curr_month in [2, 3]:
                    active_idx = 3  # anthesis
                elif curr_month in range(4, 8):
                    active_idx = 4  # fruit_development
                elif curr_month in [8, 9]:
                    active_idx = 5  # harvest
                else:
                    active_idx = 1  # flush_recovery

        cur_stage = stages[active_idx]
        next_stage = stages[active_idx + 1] if active_idx + 1 < len(stages) else None

        # Calculate progress estimate
        progress_pct = round(((active_idx + 0.5) / len(stages)) * 100)

        return {
            "crop_key": crop_key,
            "crop_name_vi": profile["name_vi"],
            "type": profile["type"],
            "current_stage_id": cur_stage["id"],
            "current_stage_name": cur_stage["name"],
            "water_need": cur_stage.get("water_need", ""),
            "fertilizer_focus": cur_stage.get("fertilizer_focus", ""),
            "disease_risks": cur_stage.get("disease_risks", []),
            "ipm_practices": cur_stage.get("ipm_practices", ""),
            "progress_pct": min(100, max(5, progress_pct)),
            "stage_index": active_idx + 1,
            "total_stages": len(stages),
            "next_stage_name": next_stage["name"] if next_stage else "Chu kỳ mùa vụ tiếp theo"
        }

    @staticmethod
    def evaluate_weather_adaptations(
        tasks: List[Dict[str, Any]],
        weather_forecast: List[Dict[str, Any]],
        current_weather: Dict[str, Any],
        crop_key: str
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Evaluate tasks against the 7-day weather forecast.
        Returns:
            - modified_tasks: tasks with weather notes or reschedule recommendations.
            - weather_alerts: active agro-climatic advisories.
        """
        adapted_tasks = []
        alerts = []

        # 1. Build lookup of daily forecast by date string (YYYY-MM-DD)
        daily_map: Dict[str, Dict[str, Any]] = {}
        for day in weather_forecast:
            d_str = str(day.get("date", ""))[:10]
            if d_str:
                daily_map[d_str] = day

        curr_temp = current_weather.get("temperature_c") or 25.0
        curr_humidity = current_weather.get("humidity_pct") or 70.0
        curr_precip = current_weather.get("precipitation_mm") or 0.0

        # General high humidity alert (>85%) -> Fungal disease warning
        if curr_humidity >= 82.0:
            crop_name = CROP_PROFILES.get(crop_key, {}).get("name_vi", "cây trồng")
            alerts.append({
                "type": "disease_risk",
                "severity": "high" if curr_humidity >= 88.0 else "medium",
                "title": f"Cảnh báo vi khí hậu ẩm độ cao ({curr_humidity}%)",
                "message": (
                    f"Độ ẩm không khí đạt {curr_humidity}%, nền nhiệt {curr_temp}°C rất thuận lợi cho "
                    f"bào tử nấm bệnh (rỉ sắt, mốc sương, thán thư) phát tán trên {crop_name}. "
                    f"Khuyến nghị tỉa cành thông thoáng và kiểm tra tán lá tầng dưới."
                ),
                "badge": "Nguy cơ nấm bệnh cao",
                "source": "Open-Meteo & Mô hình Dịch tễ Nông nghiệp GARI"
            })

        # General heat/drought alert (>34°C)
        if curr_temp >= 34.0:
            alerts.append({
                "type": "heat_stress",
                "severity": "warning",
                "title": f"Cảnh báo nhiệt độ cao ({curr_temp}°C)",
                "message": (
                    f"Nhiệt độ môi trường chạm ngưỡng {curr_temp}°C gây bốc thoát hơi nước mạnh. "
                    f"Nên phủ gốc bằng tàn dư thực vật/rơm rạ, tránh bón phân hóa học giữa trưa."
                ),
                "badge": "Chống sốc nhiệt & hạn",
                "source": "Open-Meteo Khí tượng Nông nghiệp"
            })

        # Rain forecast scan for task adjustment
        for t in tasks:
            t_copy = dict(t)
            due_d = str(t_copy.get("due_date", ""))[:10]
            day_fc = daily_map.get(due_d)

            t_type = (t_copy.get("task_type") or "").lower()
            title_lower = (t_copy.get("title") or "").lower()

            if day_fc:
                rain_prob = day_fc.get("precipitation_probability_pct") or 0.0
                rain_amount = day_fc.get("precipitation_mm") or 0.0

                # Case A: Heavy rain predicted (> 15mm or prob > 70%) on an irrigation task
                if (rain_amount >= 12.0 or rain_prob >= 70.0) and (t_type == "watering" or "tưới" in title_lower):
                    t_copy["weather_flag"] = "defer_recommended"
                    t_copy["weather_advice"] = (
                        f"Dự báo ngày {due_d} có mưa rào (lượng mưa {rain_amount} mm, xác suất {rain_prob}%). "
                        f"Khuyến nghị hoãn việc tưới nước để tiết kiệm tài nguyên và phòng ngập úng rễ."
                    )
                    alerts.append({
                        "type": "irrigation_save",
                        "severity": "info",
                        "title": f"Dự báo mưa {rain_amount} mm — Hoãn tưới",
                        "message": f"Ngày {due_d} có mưa dồi dào. Tạm hoãn các lịch tưới nhân tạo.",
                        "task_id": t_copy.get("id")
                    })

                # Case B: Rain predicted on a spraying / foliar task
                if (rain_amount >= 5.0 or rain_prob >= 60.0) and (t_type in ["spraying", "treatment"] or "phun" in title_lower):
                    t_copy["weather_flag"] = "rain_wash_risk"
                    t_copy["weather_advice"] = (
                        f"Nguy cơ rửa trôi thuốc/phân bón do dự báo mưa {rain_amount} mm ({rain_prob}% xác suất). "
                        f"Đề xuất dời lịch phun sang ngày khô ráo tiếp theo hoặc bổ sung chất bám dính sinh học."
                    )

            adapted_tasks.append(t_copy)

        return adapted_tasks, alerts

    @staticmethod
    def generate_seasonal_schedule_for_farm(
        farm: Dict[str, Any],
        user_id: int
    ) -> List[Dict[str, Any]]:
        """
        Generate a dynamic, scientifically grounded schedule of cultivation tasks
        tailored to the farm's location, crop, age, and phenology stage.
        """
        farm_id = farm["id"]
        crop_raw = farm.get("primary_crop") or "Coffee"
        crop_key = normalize_crop_key(crop_raw)
        profile = CROP_PROFILES.get(crop_key, CROP_PROFILES["Coffee"])

        growth_stage_str = farm.get("growth_stage")
        tree_age = float(farm.get("tree_age_years") or 1.0)
        variety = farm.get("variety") or (profile["default_varieties"][0] if profile.get("default_varieties") else "")
        province = farm.get("province") or "Gia Lai"

        # Determine target stages to schedule (from current onwards)
        stages = profile["stages"]
        active_idx = 0
        if growth_stage_str:
            for idx, s in enumerate(stages):
                if s["id"] == growth_stage_str or s["name"].lower() == growth_stage_str.lower():
                    active_idx = idx
                    break

        created_tasks = []
        now = datetime.now(timezone.utc)

        # Generate rolling schedule for the next 45 days
        curr_offset_days = 1
        for s_idx in range(active_idx, min(active_idx + 2, len(stages))):
            stage = stages[s_idx]
            key_tasks = stage.get("key_tasks", [])

            for kt in key_tasks:
                due_dt = now + timedelta(days=curr_offset_days)
                due_date_str = due_dt.strftime("%Y-%m-%d")

                task_data = {
                    "title": f"[{variety or profile['name_vi']}] {kt['title']}",
                    "farm_id": farm_id,
                    "crop_id": crop_key,
                    "task_type": kt.get("type", "routine"),
                    "priority": kt.get("priority", "medium"),
                    "status": "pending",
                    "due_date": due_date_str,
                    "time_window": kt.get("time_window", "Buổi sáng sớm"),
                    "growth_stage": stage["name"],
                    "rationale": kt.get("rationale") or f"Áp dụng cho giai đoạn {stage['name']} của {profile['name_vi']}.",
                    "conditions": f"Thời tiết tại {province}: Đảm bảo ráo ráo hoặc đất đủ ẩm phù hợp.",
                    "source": "Khuyến nông Quốc gia & Quy trình canh tác GAP GARI",
                    "schedule_origin": "stage_based",
                    "description": (
                        f"Công việc canh tác cá nhân hóa cho nông trại #{farm_id} ({farm.get('name')}). "
                        f"Giai đoạn: {stage['name']}. "
                        f"Nhu cầu nước: {stage.get('water_need')}. "
                        f"Phân bón/dinh dưỡng trọng tâm: {stage.get('fertilizer_focus')}."
                    )
                }

                # Save task to database
                saved = SmartFarmingScheduleEngine._insert_generated_task(task_data, user_id)
                created_tasks.append(saved)

                # Increment date offset
                curr_offset_days += max(3, kt.get("interval_days", 10) // 3)

        return created_tasks

    @staticmethod
    def _insert_generated_task(task: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """Save a generated task cleanly into SQLite & Neon without duplicating."""
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            # Avoid duplicate insertion if same title and due_date exists for this farm
            cursor.execute("""
                SELECT id FROM cultivation_tasks
                WHERE farm_id = ? AND title = ? AND due_date = ?
            """, (task["farm_id"], task["title"], task["due_date"]))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("SELECT * FROM cultivation_tasks WHERE id = ?", (existing["id"],))
                return dict(cursor.fetchone())

            cursor.execute("""
                INSERT INTO cultivation_tasks (
                    user_id, farm_id, crop_id, title, description,
                    due_date, priority, status, task_type, time_window,
                    growth_stage, rationale, conditions, source, schedule_origin,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                user_id,
                task["farm_id"],
                task["crop_id"],
                task["title"],
                task["description"],
                task["due_date"],
                task["priority"],
                task["status"],
                task["task_type"],
                task["time_window"],
                task["growth_stage"],
                task["rationale"],
                task["conditions"],
                task["source"],
                task["schedule_origin"]
            ))
            conn.commit()
            t_id = cursor.lastrowid
            cursor.execute("SELECT * FROM cultivation_tasks WHERE id = ?", (t_id,))
            return dict(cursor.fetchone())
