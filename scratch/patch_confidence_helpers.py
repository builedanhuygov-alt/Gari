import sys

with open('gari_inference_engine.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''def resolve_priority_crop(crop_input: Optional[str]) -> Optional[Dict[str, Any]]:
    """Resolves any input string or Vietnamese/English crop name to the 7 priority crops."""
    if not crop_input:
        return None
    raw = crop_input.strip().lower()
    for cid, meta in PRIORITY_CROPS.items():
        if raw == cid or raw == meta["name_vi"].lower() or raw == meta["name_en"].lower():
            return meta
        if raw in meta.get("aliases", []):
            return meta
    return None'''

replacement = '''def resolve_priority_crop(crop_input: Optional[str]) -> Optional[Dict[str, Any]]:
    """Resolves any input string or Vietnamese/English crop name to the 7 priority crops."""
    if not crop_input:
        return None
    raw = crop_input.strip().lower()
    for cid, meta in PRIORITY_CROPS.items():
        if raw == cid or raw == meta["name_vi"].lower() or raw == meta["name_en"].lower():
            return meta
        if raw in meta.get("aliases", []):
            return meta
    return None


def normalize_crop_input(crop_input: Optional[str]) -> Optional[str]:
    """Normalizes any crop input (Vietnamese name, English name, or alias) to standard crop id."""
    resolved = resolve_priority_crop(crop_input)
    if resolved:
        return resolved["id"]
    if crop_input:
        return crop_input.strip().lower()
    return None


def categorize_confidence(conf_val: float, status: str = "OK") -> Dict[str, Any]:
    """
    Categorizes model confidence score into High (>=0.70), Medium (>=0.45), Low (<0.45).
    Provides structured Vietnamese explanation and uncertainty flags.
    """
    conf = float(conf_val or 0.0)
    CONF_THRESH_HIGH = 0.70
    CONF_THRESH_MEDIUM = 0.45

    if conf >= CONF_THRESH_HIGH:
        return {
            "level": "high",
            "level_vi": "Cao",
            "is_uncertain": False,
            "uncertainty_explanation_vi": None,
            "threshold": CONF_THRESH_HIGH
        }
    elif conf >= CONF_THRESH_MEDIUM:
        return {
            "level": "medium",
            "level_vi": "Trung bình",
            "is_uncertain": False,
            "uncertainty_explanation_vi": "Độ tin cậy ở mức trung bình (45% - 70%). Khuyến nghị quan sát thêm triệu chứng trên các lá lân cận.",
            "threshold": CONF_THRESH_MEDIUM
        }
    else:
        return {
            "level": "low",
            "level_vi": "Thấp",
            "is_uncertain": True,
            "uncertainty_explanation_vi": "Độ tin cậy của mô hình dưới 45%. Kết quả mang tính tham khảo và chưa đủ cơ sở chắc chắn để khẳng định bệnh lý.",
            "threshold": CONF_THRESH_MEDIUM
        }'''

if target in text:
    text = text.replace(target, replacement, 1)
    with open('gari_inference_engine.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Added normalize_crop_input and categorize_confidence to gari_inference_engine.py")
else:
    print("Target not found in gari_inference_engine.py")
