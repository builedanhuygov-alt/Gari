"""
GARI AI LAB — Agricultural Knowledge Engine
Curates and serves evidence-based agricultural knowledge for 42+ crops and 180+ diseases.
Includes scientific names, verified symptoms, environmental conditions,
prevention protocols, field verification guidelines, and reference citations.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

INV_PATH = Path(__file__).resolve().parent / "model_inventory.json"
LOCALIZATION_DIR = Path(__file__).resolve().parent / "localization"

def _load_crop_vi() -> Dict[str, Any]:
    try:
        with open(LOCALIZATION_DIR / "crop_vi.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _load_disease_vi() -> Dict[str, str]:
    try:
        with open(LOCALIZATION_DIR / "disease_vi.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

# Verified Agricultural Knowledge Base
VERIFIED_KNOWLEDGE: Dict[str, Dict[str, Any]] = {
    "Tomato_Bacterial_spot": {
        "disease_vi": "Đốm vi khuẩn trên cà chua",
        "scientific_name": "Xanthomonas campestris pv. vesicatoria",
        "symptoms": "Vết bệnh dạng đốm nhỏ 1-3mm, ban đầu màu xanh đậm úng nước, sau chuyển sang nâu đen hoặc đen có quầng vàng nhạt bao quanh. Vết bệnh trên thân và cuống hình bầu dục dài.",
        "favorable_conditions": "Nhiệt độ 24-30°C kết hợp mưa rào, sương mù hoặc tưới phun mưa tạo giọt bắn làm lây lan vi khuẩn qua khí khổng và vết thương cơ giới.",
        "prevention": [
            "Sử dụng hạt giống và cây con sạch bệnh có xử lý nhiệt hoặc khử trùng.",
            "Tưới nhỏ giọt tại gốc, tuyệt đối không tưới phun mưa trên tán lá vào buổi chiều tối.",
            "Luân canh với cây trồng không cùng họ cà (lúa nước, ngô, họ đậu) ít nhất 2-3 năm.",
            "Vệ sinh đồng ruộng, tiêu hủy tàn dư cây bệnh sau thu hoạch."
        ],
        "field_verification": [
            "Dùng kính lúp kiểm tra vết đốm: không thấy sợi nấm trắng/xám mọc ra trong điều kiện ẩm.",
            "Thử nghiệm đùn dịch vi khuẩn (bacterial ooze test): Cắt cuống lá bệnh nhúng vào ly nước trong, quan sát dòng dịch mủ trắng sữa đùn ra từ bó mạch sau 2-5 phút."
        ],
        "chemical_advisory": "Khi vết bệnh mới chớm, ưu tiên chế phẩm sinh học Bacillus subtilis hoặc gốc đồng (Copper hydroxide, Copper oxychloride) luân phiên. Hạn chế lạm dụng kháng sinh Streptomycin để tránh kháng thuốc.",
        "references": "Viện Bảo Vệ Thực Vật (NIPP), FAO Plant Health Manual, PlantVillage Database.",
        "version": "2026.1"
    },
    "Tomato_Early_blight": {
        "disease_vi": "Bệnh đốm sớm cà chua (Đốm vòng)",
        "scientific_name": "Alternaria solani",
        "symptoms": "Vết bệnh hình tròn hoặc bầu dục, đặc trưng bởi các vòng tròn đồng tâm giống như bia bắn (target spot), màu nâu sẫm hoặc đen, xuất hiện đầu tiên trên các lá già sát mặt đất.",
        "favorable_conditions": "Thời tiết ấm ẩm, nhiệt độ 24-29°C xen kẽ giữa các đợt mưa nắng thất thường, ẩm độ lá kéo dài trên 8 tiếng.",
        "prevention": [
            "Phủ bạt nilon hoặc rơm rạ sạch quanh gốc để ngăn bào tử nấm bắn từ đất lên lá dưới.",
            "Tỉa bỏ các lá già sát mặt đất sau khi cây phân nhánh để tạo độ thông thoáng.",
            "Bón cân đối phân N-P-K, tăng cường Kali và Silic để tăng độ dày vách tế bào lá."
        ],
        "field_verification": [
            "Quan sát các vòng đồng tâm rõ nét bằng mắt thường hoặc kính lúp cầm tay.",
            "Phân biệt với đốm muộn: Đốm sớm có mép rõ ràng hơn, có quầng vàng hẹp và thường khô giòn."
        ],
        "chemical_advisory": "Phun phòng khi thời tiết chuyển ẩm ướt kéo dài bằng hoạt chất Mancozeb, Chlorothalonil hoặc Difenoconazole theo đúng liều lượng khuyến cáo.",
        "references": "CGIAR Vegetable Research Program, Cẩm nang BVTV Cây Cà Chua Việt Nam.",
        "version": "2026.1"
    },
    "Tomato_Late_blight": {
        "disease_vi": "Bệnh mốc sương cà chua (Bệnh đốm muộn)",
        "scientific_name": "Phytophthora infestans",
        "symptoms": "Vết bệnh dạng úng nước màu xanh tái xám, sau đó chuyển sang màu nâu sẫm, viền lan rộng nhanh chóng làm lá cháy xém. Khi ẩm ướt, mặt dưới lá xuất hiện lớp mốc trắng mỏng như sương muối.",
        "favorable_conditions": "Thời tiết lạnh ẩm, nhiệt độ 15-22°C kết hợp sương mù, mưa phùn liên tục và độ ẩm không khí > 90%.",
        "prevention": [
            "Chọn giống có tính kháng hoặc chịu đựng cao với mốc sương.",
            "Bố trí mật độ trồng thông thoáng, đảm bảo luống thoát nước triệt để trong mùa mưa.",
            "Dừng tưới nước ngay khi phát hiện ổ bệnh đầu tiên trong vườn."
        ],
        "field_verification": [
            "Kiểm tra mặt dưới lá vào sáng sớm: quan sát lớp lông mốc trắng như nhung ở rìa vết bệnh.",
            "Thân và quả có vết thâm lõm màu nâu xám sũng nước, quả sượng cứng."
        ],
        "chemical_advisory": "Xử lý khẩn cấp bằng hoạt chất chuyên biệt: Metalaxyl-M, Cymoxanil, Cyazofamid hoặc Dimethomorph. Luân phiên nhóm thuốc để tránh kháng.",
        "references": "CIP (International Potato Center), Tạp chí BVTV Việt Nam.",
        "version": "2026.1"
    },
    "Tomato_Healthy": {
        "disease_vi": "Lá cà chua khỏe mạnh",
        "scientific_name": "Solanum lycopersicum",
        "symptoms": "Lá xanh đều, phiến lá phẳng mịn, mép lá răng cưa tự nhiên, không có vết thâm úng, đốm quầng hay biến dạng.",
        "favorable_conditions": "Ánh sáng đầy đủ (6-8h/ngày), đất thoát nước tốt pH 6.0-6.8, chế độ dinh dưỡng cân đối.",
        "prevention": [
            "Duy trì chế độ tưới nhỏ giọt đều đặn theo nhu cầu sinh trưởng.",
            "Bón phân hữu cơ ủ hoai mục kết hợp nấm đối kháng Trichoderma để bảo vệ bộ rễ.",
            "Theo dõi mật độ côn trùng chích hút (bọ trĩ, bọ phấn trắng) để phòng truyền virus."
        ],
        "field_verification": ["Lá bóng mượt, mặt trên và dưới sạch sâu bệnh."],
        "chemical_advisory": "Không cần sử dụng hóa chất BVTV. Ưu tiên chế phẩm kích kháng sinh học tự nhiên.",
        "references": "Tiêu chuẩn VietGAP Cà Chua An Toàn.",
        "version": "2026.1"
    },
    "Potato_Early_blight": {
        "disease_vi": "Bệnh đốm sớm khoai tây",
        "scientific_name": "Alternaria solani",
        "symptoms": "Đốm lá màu nâu sẫm hoặc đen có các vân tròn đồng tâm rõ rệt. Lá bị nặng chuyển vàng rồi khô rụng sớm, làm giảm năng suất củ nghiêm trọng.",
        "favorable_conditions": "Nhiệt độ ấm 22-28°C kết hợp thời kỳ khô hạn xen lẫn mưa ẩm hoặc sương mù.",
        "prevention": [
            "Chọn củ giống khoai tây sạch bệnh, xử lý củ trước khi gieo trồng.",
            "Vun cao luống, hạn chế cày xới làm tổn thương rễ và lá gốc khi cây đã lớn.",
            "Luân canh với ngô, lúa nước ít nhất 2 vụ liên tiếp."
        ],
        "field_verification": ["Quan sát vết bệnh hình đĩa bia trên tầng lá già."],
        "chemical_advisory": "Phun luân phiên Chlorothalonil, Mancozeb hoặc Azoxystrobin.",
        "references": "CIP Potato Compendium, Viện Khoa học Nông nghiệp Việt Nam (VAAS).",
        "version": "2026.1"
    },
    "Potato_Late_blight": {
        "disease_vi": "Bệnh mốc sương khoai tây",
        "scientific_name": "Phytophthora infestans",
        "symptoms": "Vết bệnh dạng úng nước không định hình ở chóp hoặc mép lá, lan rất nhanh làm cả ruộng khoai tây cháy đen như bị luộc nước sôi trong vài ngày.",
        "favorable_conditions": "Nhiệt độ mát 16-20°C, ẩm độ > 90%, thời tiết mưa phùn hoặc sương muối kéo dài.",
        "prevention": [
            "Dự báo thời tiết và phun phòng trước các đợt gió mùa đông bắc kèm mưa phùn.",
            "Vun đất dày để bảo vệ củ dưới đất không bị bào tử trôi từ lá xuống.",
            "Thu hoạch củ vào ngày khô ráo, loại bỏ củ thối trước khi cất trữ."
        ],
        "field_verification": ["Lớp mốc tơ trắng mịn ở rìa vết bệnh mặt dưới lá vào sáng sớm."],
        "chemical_advisory": "Sử dụng Metalaxyl-M, Propamocarb hoặc Dimethomorph theo nguyên tắc 4 đúng.",
        "references": "Cục Trồng Trọt & Cục Bảo Vệ Thực Vật Việt Nam.",
        "version": "2026.1"
    },
    "Potato_Healthy": {
        "disease_vi": "Khoai tây khỏe mạnh",
        "scientific_name": "Solanum tuberosum",
        "symptoms": "Tán lá xòe đều, màu xanh tươi, thân cây mập mạp vững chắc, không có triệu chứng héo rũ hay cháy lá.",
        "favorable_conditions": "Khí hậu mát mẻ, đất tơi xốp giàu mùn, ẩm độ đất 70-80%.",
        "prevention": ["Duy trì chăm sóc theo quy trình VietGAP, kiểm soát sâu hại."],
        "field_verification": ["Kiểm tra toàn bộ khóm cây phát triển đồng đều."],
        "chemical_advisory": "Không cần can thiệp hóa chất.",
        "references": "Sổ tay kỹ thuật canh tác khoai tây xuất khẩu.",
        "version": "2026.1"
    },
    "Rice_Blast": {
        "disease_vi": "Bệnh đạo ôn lúa",
        "scientific_name": "Magnaporthe oryzae (Pyricularia oryzae)",
        "symptoms": "Vết bệnh điển hình hình quả trám (mắt én), ở giữa màu xám tro, xung quanh viền nâu đậm, ngoài cùng có quầng vàng nhạt. Trên cổ bông làm cháy khô cổ bông khiến hạt lép lửng.",
        "favorable_conditions": "Nhiệt độ 20-28°C, ẩm độ > 90%, sáng nhiều sương, bón thừa đạm (thừa phân N).",
        "prevention": [
            "Gieo cấy mật độ hợp lý, không gieo sạ quá dày.",
            "Bón phân cân đối N-P-K, ngưng bón đạm khi thấy vết chấm kim đầu tiên.",
            "Giữ mực nước nông hợp lý trên ruộng, không để ruộng bị khô hạn."
        ],
        "field_verification": ["Tìm vết bệnh hình mắt én trên các lá non phía trên."],
        "chemical_advisory": "Phun các hoạt chất chuyên trị: Tricyclazole, Isoprothiolane, Fenoxanil hoặc Kasugamycin.",
        "references": "Viện Lúa ĐBSCL (CLRRI), IRRI Rice Knowledge Bank.",
        "version": "2026.1"
    },
    "Rice_Brown_Spot": {
        "disease_vi": "Bệnh đốm nâu lúa (Bệnh tiêm lửa)",
        "scientific_name": "Bipolaris oryzae (Cochliobolus miyabeanus)",
        "symptoms": "Vết bệnh hình tròn hoặc bầu dục nhỏ màu nâu sẫm giống hạt mè, xuất hiện khắp mặt lá, thường xuất hiện ở chân ruộng phèn, nghèo dinh dưỡng.",
        "favorable_conditions": "Đất thiếu lân, nghèo silic, ngộ độc phèn hoặc ngộ độc hữu cơ.",
        "prevention": [
            "Bón lót vôi và lân nung chảy để hạ phèn, giải độc đất.",
            "Bổ sung phân bón hữu cơ sinh học và phân bón qua lá chứa Silic, Kẽm.",
            "Cày ải phơi đất triệt để giữa hai vụ lúa."
        ],
        "field_verification": ["Vết đốm nâu nhỏ như hạt mè phân bố đều trên phiến lá."],
        "chemical_advisory": "Phun Propiconazole hoặc Difenoconazole kết hợp phục hồi dinh dưỡng rễ.",
        "references": "Cẩm nang BVTV Cây Lúa Việt Nam.",
        "version": "2026.1"
    },
    "Tea_Anthracnose": {
        "disease_vi": "Bệnh thán thư chè",
        "scientific_name": "Colletotrichum camelliae",
        "symptoms": "Vết bệnh loang màu nâu đậm từ mép lá hoặc chóp lá vào trong, trên vết bệnh già xuất hiện các chấm đen nhỏ li ti là ổ bào tử nấm.",
        "favorable_conditions": "Nhiệt độ 25-30°C, mưa nhiều, sương mù ở các vùng chè đồi cao.",
        "prevention": [
            "Đốn tỉa chè đúng kỹ thuật, tạo tán thoáng mát, dọn sạch cành lá đốn.",
            "Hái búp đúng lứa, tránh để búp chè quá già tạo điều kiện cho nấm tích tụ.",
            "Bón đủ kali và phân chuồng hoai mục."
        ],
        "field_verification": ["Các chấm đen li ti xếp thành vòng trên vết cháy nâu khô."],
        "chemical_advisory": "Sử dụng chế phẩm sinh học hoặc gốc đồng vào thời kỳ đốn chè để cách ly an toàn.",
        "references": "Viện KHKT Nông Lâm Nghiệp Miền Núi Phía Bắc (NOMAFSI).",
        "version": "2026.1"
    }
}


def _load_inventory() -> List[Dict[str, Any]]:
    if not INV_PATH.is_file():
        return []
    try:
        with open(INV_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def get_crop_catalog() -> List[Dict[str, Any]]:
    """Return all discovered crops with metadata, class counts, and Vietnamese labels."""
    inv = _load_inventory()
    crop_vi_dict = _load_crop_vi()
    disease_vi_dict = _load_disease_vi()
    crops = []
    for item in inv:
        if item.get("kind") != "disease":
            continue
        crop_id = item["crop_id"]
        c_meta = crop_vi_dict.get(crop_id, {})
        crop_name_vi = c_meta.get("name_vi", item.get("crop_name", crop_id))

        raw_labels = item.get("labels", [])
        raw_classes = item.get("classes", [])
        vi_labels = []
        for idx, l in enumerate(raw_labels):
            cls_name = raw_classes[idx] if idx < len(raw_classes) else l
            d_vi = disease_vi_dict.get(l) or disease_vi_dict.get(cls_name) or disease_vi_dict.get(l.lower()) or l
            vi_labels.append(d_vi)

        crops.append({
            "crop_id": crop_id,
            "crop_name": crop_name_vi,
            "crop_name_en": crop_id,
            "classes_count": item.get("classes_count", 0),
            "classes": raw_classes,
            "labels": vi_labels,
            "labels_en": raw_labels,
            "accuracy": item.get("accuracy"),
            "arch": item.get("arch", "convnext_small"),
            "weight_size_mb": item.get("weight_size_mb", 94.4),
        })
    return sorted(crops, key=lambda x: x["crop_name"])


def search_diseases(query: Optional[str] = None, crop: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search diseases across crops, symptoms, scientific names, and Vietnamese descriptions."""
    inv = _load_inventory()
    crop_vi_dict = _load_crop_vi()
    disease_vi_dict = _load_disease_vi()
    results = []

    q_lower = query.lower().strip() if query else None
    crop_lower = crop.lower().strip() if crop and crop != "all" else None

    for item in inv:
        if item.get("kind") != "disease":
            continue
        c_id = item["crop_id"]
        c_meta = crop_vi_dict.get(c_id, {})
        c_name = c_meta.get("name_vi", item.get("crop_name", c_id))

        if crop_lower and c_id.lower() != crop_lower and c_name.lower() != crop_lower and item.get("crop_name", "").lower() != crop_lower:
            continue

        classes = item.get("classes", [])
        labels = item.get("labels", [])

        for idx, cls_name in enumerate(classes):
            label = labels[idx] if idx < len(labels) else cls_name
            lookup_key = f"{c_id}_{cls_name}"
            kb = VERIFIED_KNOWLEDGE.get(lookup_key)

            dis_vi = kb.get("disease_vi") if kb else None
            if not dis_vi:
                raw_dis = disease_vi_dict.get(cls_name) or disease_vi_dict.get(label) or disease_vi_dict.get(cls_name.lower()) or disease_vi_dict.get(label.lower())
                if not raw_dis:
                    dis_vi = "Chưa có bản dịch tiếng Việt cho nhãn này."
                elif "khỏe" in raw_dis.lower() or "healthy" in cls_name.lower():
                    dis_vi = f"Lá {c_name.lower()} khỏe mạnh"
                elif raw_dis.lower().startswith("bệnh "):
                    dis_vi = f"{raw_dis} trên {c_name.lower()}"
                else:
                    dis_vi = f"Bệnh {raw_dis} trên {c_name.lower()}"

            entry: Dict[str, Any] = {
                "crop_id": c_id,
                "crop_name": c_name,
                "class_id": cls_name,
                "disease_name": label,
                "disease_vi": dis_vi,
                "scientific_name": kb.get("scientific_name", "Đang cập nhật phân loại học") if kb else "Đang cập nhật phân loại học",
                "symptoms": kb.get("symptoms", f"Triệu chứng biểu hiện trên tán lá và cuống của cây {c_name}.") if kb else f"Triệu chứng biểu hiện trên tán lá và cuống của cây {c_name}.",
                "favorable_conditions": kb.get("favorable_conditions", "Nhiệt độ ẩm độ thuận lợi cho mầm bệnh phát tán.") if kb else "Nhiệt độ ẩm độ thuận lợi cho mầm bệnh phát tán.",
                "prevention": kb.get("prevention", [
                    f"Vệ sinh đồng ruộng và kiểm tra cây con {c_name} thường xuyên.",
                    "Đảm bảo thoát nước tốt, hạn chế làm ẩm ướt tán lá kéo dài.",
                    "Luân canh với các nhóm cây trồng khác họ."
                ]) if kb else [
                    f"Vệ sinh đồng ruộng và kiểm tra cây con {c_name} thường xuyên.",
                    "Đảm bảo thoát nước tốt, hạn chế làm ẩm ướt tán lá kéo dài.",
                    "Luân canh với các nhóm cây trồng khác họ."
                ],
                "field_verification": kb.get("field_verification", [
                    "Sử dụng kính lúp cầm tay kiểm tra mép và mặt dưới phiến lá.",
                    "So sánh với các biểu hiện sinh lý do thiếu phân hoặc ngộ độc rễ."
                ]) if kb else [
                    "Sử dụng kính lúp cầm tay kiểm tra mép và mặt dưới phiến lá.",
                    "So sánh với các biểu hiện sinh lý do thiếu phân hoặc ngộ độc rễ."
                ],
                "chemical_advisory": kb.get("chemical_advisory", "Tuân thủ nguyên tắc 4 đúng khi dùng thuốc BVTV, ưu tiên chế phẩm sinh học.") if kb else "Tuân thủ nguyên tắc 4 đúng khi dùng thuốc BVTV, ưu tiên chế phẩm sinh học.",
                "references": kb.get("references", "Gari Agricultural Intelligence Library, Plant Health Database.") if kb else "Gari Agricultural Intelligence Library, Plant Health Database.",
                "is_verified": kb is not None,
                "version": kb.get("version", "2026.1") if kb else "2026.1"
            }

            # Filter by query string
            if q_lower:
                searchable_text = f"{entry['disease_name']} {entry['disease_vi']} {entry['scientific_name']} {entry['crop_name']} {entry['symptoms']}".lower()
                if q_lower not in searchable_text:
                    continue

            results.append(entry)

    return results


def get_disease_detail(crop_id: str, class_id: str) -> Optional[Dict[str, Any]]:
    diseases = search_diseases(crop=crop_id)
    for d in diseases:
        if d["class_id"].lower() == class_id.lower() or d["disease_name"].lower() == class_id.lower():
            return d
    return None


def _enrich_guidance(d: Dict[str, Any]) -> Dict[str, Any]:
    d["retake_tips"] = d.get("retake_instructions", [])
    d["immediate_low_risk_actions"] = d.get("immediate_actions", [])
    d["when_to_ask_expert"] = d.get("expert_consultation_triggers", [])
    d["sources"] = [d["source_references"]] if d.get("source_references") else []
    d["verified"] = d.get("is_verified", False)
    d["notice"] = d.get("guidance_notice", "")
    return d


def get_action_guidance(
    crop_id: Optional[str] = None,
    disease_id: Optional[str] = None,
    confidence: float = 0.0,
    is_healthy: bool = False,
    diagnosis_status: str = "diagnosed"
) -> Dict[str, Any]:
    """
    Generate grounded, safety-first agricultural action guidance adhering strictly to Sprint 4:
    - Grounded only in verified knowledge or explicit 'unverified' status.
    - Zero chemical pesticide dosages or commercial brand promotion.
    - Prioritizes observation, sanitation, isolation of suspect plants.
    - Explicit guidance on when to consult an agronomist / extension officer.
    - If confidence is low or status is needs_review / rejected, highlights uncertainty
      and prompts retake without strong chemical recommendations.
    """
    # 1. Invalid Image or Leaf Gate Rejection
    if diagnosis_status in ("rejected_invalid_image", "rejected", "not_a_leaf", "image_quality_low"):
        return _enrich_guidance({
            "status": "invalid_image",
            "is_verified": False,
            "status_label_vi": "Ảnh không hợp lệ",
            "guidance_notice": "Ảnh chưa đạt tiêu chuẩn để đưa ra hướng dẫn hành động cụ thể.",
            "retake_instructions": [
                "Chụp lại ảnh một chiếc lá cây rõ nét, đủ ánh sáng tự nhiên.",
                "Đặt lá phẳng trong khung hình, tránh rung tay hoặc chụp quá xa (cách 15-30cm).",
                "Tránh chụp bóng râm tối hoặc ánh sáng chói lóa trực tiếp."
            ],
            "immediate_actions": [
                "Không can thiệp thuốc bảo vệ thực vật khi chưa có kết quả kiểm tra hợp lệ."
            ],
            "observation_signs": [],
            "expert_consultation_triggers": [
                "Tham khảo cán bộ khuyến nông địa phương nếu toàn ruộng xuất hiện triệu chứng bất thường."
            ],
            "chemical_advisory": "Không áp dụng hóa chất khi chưa có kết quả kiểm tra hợp lệ.",
            "source_references": None
        })

    # 2. Uncertain Result or Low Confidence
    if diagnosis_status == "needs_review" or confidence < 0.60 or diagnosis_status in ("uncertain", "crop_uncertain", "disease_uncertain"):
        return _enrich_guidance({
            "status": "uncertain",
            "is_verified": False,
            "status_label_vi": "Kết quả chưa chắc chắn — Cần theo dõi thêm",
            "guidance_notice": "Mức độ tin cậy của mô hình chưa đủ cao để xác nhận bệnh. Tuyệt đối không tự ý phun thuốc hóa chất liều cao dựa trên kết quả này.",
            "retake_instructions": [
                "Chụp lại ảnh lá vào ban ngày dưới ánh sáng tự nhiên đầy đủ.",
                "Chụp cả mặt trên và mặt dưới của phiến lá nghi nhiễm mầm bệnh.",
                "Chọn lá có triệu chứng điển hình nhất, lau nhẹ bụi bẩn trên phiến lá trước khi chụp."
            ],
            "immediate_actions": [
                "Tiếp tục quan sát thêm 24-48 giờ xem vết bệnh có phát triển lan rộng không.",
                "Đánh dấu hoặc cách ly cây nghi nhiễm để theo dõi ổ dịch cục bộ.",
                "Vệ sinh kéo tỉa và dụng cụ làm vườn bằng cồn hoặc nước xà phòng sau khi thao tác."
            ],
            "observation_signs": [
                "Quan sát mép vết bệnh xem có quầng vàng hoặc chảy dịch úng nước khi độ ẩm cao không.",
                "Kiểm tra mật độ vết đốm trên tầng lá già sát gốc so với tầng lá non trên ngọn."
            ],
            "expert_consultation_triggers": [
                "Khi diện tích tổn thương trên lá lan rộng nhanh vượt quá 10% tán cây trong 48 giờ.",
                "Khi cây có hiện tượng héo rũ nhanh hàng loạt không rõ nguyên nhân dù đất vẫn ẩm."
            ],
            "chemical_advisory": "Chưa có khuyến nghị hóa chất. Ưu tiên biện pháp canh tác và chụp lại ảnh để kiểm tra.",
            "source_references": None
        })

    # 3. Healthy Crop Leaf
    if is_healthy or (disease_id and "healthy" in disease_id.lower()) or diagnosis_status == "healthy":
        return _enrich_guidance({
            "status": "healthy",
            "is_verified": True,
            "status_label_vi": "Cây trồng khỏe mạnh",
            "guidance_notice": "Lá cây trong tình trạng sinh trưởng bình thường, không phát hiện dấu hiệu bệnh lý.",
            "retake_instructions": [],
            "immediate_actions": [
                "Duy trì quy trình tưới tiêu hợp lý, tránh tưới đọng nước trên lá vào chiều tối.",
                "Bón phân cân đối N-P-K theo giai đoạn sinh trưởng, bổ sung phân hữu cơ hoai mục.",
                "Tạo độ thông thoáng cho luống trồng và tỉa bỏ các lá già vàng úa sát mặt đất."
            ],
            "observation_signs": [
                "Quan sát màu xanh tươi đồng đều của phiến lá và sự phát triển của chồi ngọn non.",
                "Kiểm tra định kỳ mặt dưới lá để phát hiện sớm trứng hoặc ấu trùng côn trùng chích hút."
            ],
            "expert_consultation_triggers": [
                "Tham vấn định kỳ về lịch chuyển giai đoạn bón thúc nuôi hoa, nuôi củ/quả."
            ],
            "chemical_advisory": "Không sử dụng thuốc hóa chất bảo vệ thực vật khi cây đang khỏe mạnh.",
            "source_references": "Quy trình thực hành sản xuất nông nghiệp tốt (VietGAP)"
        })

    # 4. Unknown or Unsupported Disease
    if diagnosis_status == "unknown_or_unsupported":
        return _enrich_guidance({
            "status": "unverified",
            "is_verified": False,
            "status_label_vi": "Chưa có hướng dẫn đã xác minh",
            "guidance_notice": "Chưa có hướng dẫn đã xác minh cho đối tượng này trong cơ sở dữ liệu hệ thống.",
            "retake_instructions": [
                "Có thể chụp lại góc chụp khác để hỗ trợ phân loại."
            ],
            "immediate_actions": [
                "Cách ly cây có biểu hiện bất thường khỏi các khu vực luống khỏe mạnh lân cận.",
                "Cắt bỏ phần cành lá nghi nhiễm cho vào túi kín tiêu hủy, không vứt bừa bãi tại ruộng.",
                "Tạm dừng việc bón thúc phân đạm để tránh làm vết bệnh phát triển nhanh."
            ],
            "observation_signs": [
                "Theo dõi tốc độ lan rộng và màu sắc tổn thương lá sau 2-3 ngày."
            ],
            "expert_consultation_triggers": [
                "Mang mẫu lá có triệu chứng tới Trạm Khuyến nông hoặc Chi cục Trồng trọt & BVTV gần nhất để được giám định trực tiếp."
            ],
            "chemical_advisory": "Chưa có hướng dẫn đã xác minh. Tuyệt đối không tự ý phối trộn hóa chất không rõ nguồn gốc.",
            "source_references": None
        })

    # 5. Confirmed Disease: Lookup in Verified Knowledge Base
    # Form lookup keys
    target_key = f"{crop_id}_{disease_id}" if crop_id and disease_id else ""
    kb = VERIFIED_KNOWLEDGE.get(target_key)
    if not kb and crop_id:
        # Search by partial match in VERIFIED_KNOWLEDGE
        for k, v in VERIFIED_KNOWLEDGE.items():
            if k.lower() == target_key.lower():
                kb = v
                break
            if disease_id and (disease_id.lower() in k.lower() or k.lower() in disease_id.lower()):
                kb = v
                break

    if kb:
        return _enrich_guidance({
            "status": "verified",
            "is_verified": True,
            "status_label_vi": "Hướng dẫn canh tác đã xác minh",
            "guidance_notice": f"Hướng dẫn thực hành canh tác an toàn đối với {kb.get('disease_vi', disease_id)}.",
            "retake_instructions": [],
            "immediate_actions": kb.get("prevention", [
                "Vệ sinh đồng ruộng, tỉa bỏ các lá già sát mặt đất có triệu chứng bệnh.",
                "Tưới gốc nhỏ giọt, tránh tưới phun mưa lên tán lá vào buổi chiều tối.",
                "Cách ly khu vực nghi nhiễm và tiêu hủy tàn dư cây bệnh đúng quy cách."
            ]),
            "observation_signs": [
                kb.get("symptoms", "Quan sát sự lan rộng của vết đốm trên phiến lá."),
                *(kb.get("field_verification", ["Kiểm tra xem có lớp mốc hoặc dịch đùn ra khi ẩm ướt không."]))
            ],
            "expert_consultation_triggers": [
                "Khi vết bệnh lan rộng trên 10-15% diện tích vườn dù đã thực hiện biện pháp vệ sinh.",
                "Trước khi quyết định sử dụng bất kỳ loại thuốc BVTV nào trên diện tích canh tác lớn.",
                "Khi cần xác định chính xác ngưỡng gây hại kinh tế và thời điểm cách ly an toàn."
            ],
            "chemical_advisory": kb.get("chemical_advisory", "Ưu tiên chế phẩm sinh học. Chỉ sử dụng thuốc BVTV theo nguyên tắc 4 đúng khi vết bệnh vượt ngưỡng kinh tế."),
            "source_references": kb.get("references", "Viện Bảo Vệ Thực Vật (NIPP), Cục Trồng Trọt & BVTV")
        })

    # Fallback when disease is not in VERIFIED_KNOWLEDGE
    return _enrich_guidance({
        "status": "unverified",
        "is_verified": False,
        "status_label_vi": "Chưa có hướng dẫn đã xác minh",
        "guidance_notice": "Chưa có hướng dẫn đã xác minh cho mầm bệnh này trong cơ sở dữ liệu hệ thống.",
        "retake_instructions": [],
        "immediate_actions": [
            "Cách ly các cây xuất hiện triệu chứng nghi ngờ, tránh va chạm làm phát tán mầm bệnh.",
            "Tỉa bỏ bộ phận lá bị tổn thương và thu gom vào bao nilon đem tiêu hủy ngoài khu vườn.",
            "Giữ tán cây thông thoáng, điều chỉnh mật độ luống và ngừng bón đạm tạm thời."
        ],
        "observation_signs": [
            "Theo dõi sự thay đổi màu sắc và kích thước của vết bệnh sau 2-3 ngày quan sát thực địa."
        ],
        "expert_consultation_triggers": [
            "Mang mẫu lá tươi có triệu chứng tới Trạm Khuyến nông / Chi cục BVTV địa phương để được soi kính hiển vi và định danh chính xác."
        ],
        "chemical_advisory": "Chưa có hướng dẫn đã xác minh. Tuyệt đối không tự ý phối trộn hoặc phun thuốc hóa chất liều cao.",
        "source_references": None
    })

