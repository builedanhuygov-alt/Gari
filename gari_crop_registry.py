"""
GARI AI LAB — Multi-Crop Model Registry & Consistency Engine
Defines the strict crop-to-model mapping, label consistency validation,
Vietnamese crop naming, and supported capabilities.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("gari_registry")

# Canonical Crops Registry
# crop_id -> metadata
CROP_CATALOG: Dict[str, Dict[str, Any]] = {
    "Apple": {"vi_name": "Táo tây", "en_name": "Apple", "folder": "Apple", "has_disease_model": True, "detector": "both"},
    "Apricot": {"vi_name": "Mơ tây", "en_name": "Apricot", "folder": "Apricot", "has_disease_model": True, "detector": "new"},
    "Banana": {"vi_name": "Chuối", "en_name": "Banana", "folder": "Banana", "has_disease_model": True, "detector": "original"},
    "Betel": {"vi_name": "Trầu không", "en_name": "Betel", "folder": "Betel", "has_disease_model": True, "detector": "new"},
    "Bitter_gourd": {"vi_name": "Mướp đắng (Khổ qua)", "en_name": "Bitter Gourd", "folder": "Bitter_gourd", "has_disease_model": True, "detector": "new"},
    "Black_Pepper": {"vi_name": "Hồ tiêu", "en_name": "Black Pepper", "folder": "Black_Pepper", "has_disease_model": True, "detector": "new"},
    "Bottle_gourd": {"vi_name": "Bầu sao (Bầu nậm)", "en_name": "Bottle Gourd", "folder": "Bottle_gourd", "has_disease_model": True, "detector": "new"},
    "Brinjal": {"vi_name": "Cà tím", "en_name": "Brinjal (Eggplant)", "folder": "Brinjal", "has_disease_model": True, "detector": "original"},
    "Cashew": {"vi_name": "Điều (Đào lộn hột)", "en_name": "Cashew", "folder": "Cashew", "has_disease_model": True, "detector": "both"},
    "Cassava": {"vi_name": "Sắn (Khoai mì)", "en_name": "Cassava", "folder": "Cassava", "has_disease_model": True, "detector": "new"},
    "Cherry": {"vi_name": "Anh đào (Cherry)", "en_name": "Cherry", "folder": "Cherry", "has_disease_model": True, "detector": "both"},
    "Chrysanthemum": {"vi_name": "Hoa cúc", "en_name": "Chrysanthemum", "folder": "Chrysanthemum", "has_disease_model": True, "detector": "new"},
    "Citrus": {"vi_name": "Cây có múi (Cam, Chanh, Bưởi)", "en_name": "Citrus", "folder": "Citrus", "has_disease_model": True, "detector": "new"},
    "Coconut": {"vi_name": "Dừa", "en_name": "Coconut", "folder": "Coconut", "has_disease_model": True, "detector": "original"},
    "Coffee": {"vi_name": "Cà phê", "en_name": "Coffee", "folder": "Coffee", "has_disease_model": True, "detector": "new"},
    "Cucumber": {"vi_name": "Dưa chuột (Dưa leo)", "en_name": "Cucumber", "folder": "Cucumber", "has_disease_model": True, "detector": "new"},
    "Cucurbit": {"vi_name": "Họ bầu bí (Bí ngô, dưa bở)", "en_name": "Cucurbit", "folder": "Cucurbit", "has_disease_model": True, "detector": "new"},
    "Custard_apple": {"vi_name": "Mãng cầu ta (Na)", "en_name": "Custard Apple", "folder": "Custard_apple", "has_disease_model": True, "detector": "original"},
    "Fig": {"vi_name": "Quả sung (Vả tây)", "en_name": "Fig", "folder": "Fig", "has_disease_model": True, "detector": "new"},
    "Grape": {"vi_name": "Nho", "en_name": "Grape", "folder": "Grape", "has_disease_model": True, "detector": "new"},
    "Guava": {"vi_name": "Ổi", "en_name": "Guava", "folder": "Guava", "has_disease_model": True, "detector": "original"},
    "Loquat": {"vi_name": "Sơn tra (Tỳ bà)", "en_name": "Loquat", "folder": "Loquat", "has_disease_model": True, "detector": "new"},
    "Maize": {"vi_name": "Ngô (Bắp)", "en_name": "Maize (Corn)", "folder": "Maize", "has_disease_model": True, "detector": "new"},
    "Mango": {"vi_name": "Xoài", "en_name": "Mango", "folder": "Mango", "has_disease_model": True, "detector": "both"},
    "Mulberry": {"vi_name": "Dâu tằm", "en_name": "Mulberry", "folder": "Mulberry", "has_disease_model": True, "detector": "original"},
    "okra": {"vi_name": "Đậu bắp", "en_name": "Okra", "folder": "okra", "has_disease_model": True, "detector": "original"},
    "Papaya": {"vi_name": "Đu đủ", "en_name": "Papaya", "folder": "Papaya", "has_disease_model": True, "detector": "original"},
    "Peach": {"vi_name": "Đào", "en_name": "Peach", "folder": "Peach", "has_disease_model": True, "detector": "new"},
    "Pear": {"vi_name": "Lê", "en_name": "Pear", "folder": "Pear", "has_disease_model": True, "detector": "new"},
    "pomrgranet": {"vi_name": "Lựu", "en_name": "Pomegranate", "folder": "pomrgranet", "has_disease_model": True, "detector": "original"},
    "Potato": {"vi_name": "Khoai tây", "en_name": "Potato", "folder": "Potato", "has_disease_model": True, "detector": "new"},
    "Rice": {"vi_name": "Lúa nước", "en_name": "Rice", "folder": "Rice", "has_disease_model": True, "detector": "new"},
    "Ridge_gourd": {"vi_name": "Mướp khía", "en_name": "Ridge Gourd", "folder": "Ridge_gourd", "has_disease_model": True, "detector": "new"},
    "Rose": {"vi_name": "Hoa hồng", "en_name": "Rose", "folder": "Rose", "has_disease_model": True, "detector": "both"},
    "Snake_gourd": {"vi_name": "Mướp rắn", "en_name": "Snake Gourd", "folder": "Snake_gourd", "has_disease_model": True, "detector": "new"},
    "Soybean": {"vi_name": "Đậu nành (Đậu tương)", "en_name": "Soybean", "folder": "Soybean", "has_disease_model": True, "detector": "new"},
    "Strawberry": {"vi_name": "Dâu tây", "en_name": "Strawberry", "folder": "Strawberry", "has_disease_model": True, "detector": "both"},
    "Sugarcane": {"vi_name": "Mía", "en_name": "Sugarcane", "folder": "Sugarcane", "has_disease_model": True, "detector": "new"},
    "Tea": {"vi_name": "Chè (Trà)", "en_name": "Tea", "folder": "Tea", "has_disease_model": True, "detector": "new"},
    "Tomato": {"vi_name": "Cà chua", "en_name": "Tomato", "folder": "Tomato", "has_disease_model": True, "detector": "new"},
    "Walnut": {"vi_name": "Óc chó", "en_name": "Walnut", "folder": "Walnut", "has_disease_model": True, "detector": "new"},
    "Watermelon": {"vi_name": "Dưa hấu", "en_name": "Watermelon", "folder": "Watermelon", "has_disease_model": True, "detector": "original"},
    
    # Supported via Model tong (PlantVillage-ViT 38-class classifier)
    "Pepper": {"vi_name": "Ớt ngọt (Ớt chuông)", "en_name": "Pepper", "folder": "Model tong", "has_disease_model": True, "detector": "new", "model_type": "vit", "classes": ["Pepper__bell___Bacterial_spot", "Pepper__bell___healthy"]},
    "Raspberry": {"vi_name": "Mâm xôi", "en_name": "Raspberry", "folder": None, "has_disease_model": False, "detector": "new", "unsupported_reason": "Cây mâm xôi chưa có mô hình chẩn đoán bệnh cục bộ."},
    "Sorghum": {"vi_name": "Lúa miến (Bo bo)", "en_name": "Sorghum", "folder": None, "has_disease_model": False, "detector": "new", "unsupported_reason": "Cây lúa miến chưa có mô hình chẩn đoán bệnh cục bộ."},
    "Squash": {"vi_name": "Bí ngô (Bí đỏ)", "en_name": "Squash", "folder": "Model tong", "has_disease_model": True, "detector": "new", "model_type": "vit", "classes": ["Squash___Powdery_mildew"]},
}

# Mapping of all alternate spellings/detector class names to canonical ID
ALIAS_MAP: Dict[str, str] = {
    "castard_apple": "Custard_apple",
    "custard_apple": "Custard_apple",
    "pomegranate": "pomrgranet",
    "pomrgranet": "pomrgranet",
    "okra": "okra",
    "eggplant": "Brinjal",
    "corn": "Maize",
    "maize": "Maize",
    "black_pepper": "Black_Pepper",
    "bitter_gourd": "Bitter_gourd",
    "bottle_gourd": "Bottle_gourd",
    "ridge_gourd": "Ridge_gourd",
    "snake_gourd": "Snake_gourd",
}


def normalize_crop_id(crop_input: Optional[str]) -> Optional[str]:
    """Resolve any input string, detector class, or folder name to canonical crop_id."""
    if not crop_input:
        return None
    raw = crop_input.strip()
    if raw.lower() in ("auto", "detect", "all", ""):
        return None

    # Exact match in catalog
    if raw in CROP_CATALOG:
        return raw

    clean_key = raw.lower().replace("-", "_").replace(" ", "_")
    if clean_key in ALIAS_MAP:
        return ALIAS_MAP[clean_key]

    for cid in CROP_CATALOG:
        if cid.lower() == clean_key:
            return cid

    return raw


def get_crop_metadata(crop_id: str) -> Optional[Dict[str, Any]]:
    cid = normalize_crop_id(crop_id)
    if not cid:
        return None
    return CROP_CATALOG.get(cid)


def get_vietnamese_crop_name(crop_id: str) -> str:
    meta = get_crop_metadata(crop_id)
    if meta:
        return f"{meta['vi_name']} ({meta['en_name']})"
    return crop_id.replace("_", " ").title()
