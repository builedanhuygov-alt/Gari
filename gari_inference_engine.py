import argparse
import io
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
from PIL import Image, ImageOps
from safetensors.torch import load_file
import timm

from gari_crop_registry import (
    CROP_CATALOG,
    ALIAS_MAP,
    normalize_crop_id,
    get_crop_metadata,
    get_vietnamese_crop_name,
)

# Force UTF-8 encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gari_engine")

WORKSPACE_DIR = Path(__file__).resolve().parent
DEFAULT_MODELS_DIR = WORKSPACE_DIR / "models"
MODELS_DIR = Path(os.getenv("MODELS_DIR", str(DEFAULT_MODELS_DIR)))

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
MAX_CACHED_MODELS = int(os.getenv("MAX_CACHED_MODELS", "3"))

from gari_visual_localization import generate_visual_localization_bundle, ATTENTION_DISCLAIMER_VI

LOCALIZATION_DIR = WORKSPACE_DIR / "localization"

def _load_localization_files():
    crops_vi = {}
    diseases_vi = {}
    symptoms_vi = {}
    recommendations_vi = {}
    try:
        p = LOCALIZATION_DIR / "crop_vi.json"
        if p.exists():
            crops_vi = json.loads(p.read_text(encoding="utf-8"))
        p = LOCALIZATION_DIR / "disease_vi.json"
        if p.exists():
            diseases_vi = json.loads(p.read_text(encoding="utf-8"))
        p = LOCALIZATION_DIR / "symptom_vi.json"
        if p.exists():
            symptoms_vi = json.loads(p.read_text(encoding="utf-8"))
        p = LOCALIZATION_DIR / "recommendation_vi.json"
        if p.exists():
            recommendations_vi = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Error loading localization files: %s", e)
    return crops_vi, diseases_vi, symptoms_vi, recommendations_vi

CROPS_VI, DISEASES_VI, SYMPTOMS_VI, RECOMMENDATIONS_VI = _load_localization_files()

def localize_crop(crop_id: str) -> Dict[str, str]:
    if crop_id in CROPS_VI:
        item = CROPS_VI[crop_id]
        return {
            "crop_id": crop_id,
            "name_vi": item.get("name_vi", crop_id),
            "common_name": item.get("common_name", item.get("name_vi", crop_id)),
            "scientific_name": item.get("scientific_name", ""),
            "family": item.get("family", "")
        }
    meta = get_crop_metadata(crop_id)
    if meta:
        return {
            "crop_id": crop_id,
            "name_vi": meta.get("vi_name", crop_id),
            "common_name": meta.get("vi_name", crop_id),
            "scientific_name": "",
            "family": ""
        }
    return {
        "crop_id": crop_id,
        "name_vi": crop_id,
        "common_name": crop_id,
        "scientific_name": "",
        "family": ""
    }

def localize_disease(class_id: str) -> str:
    if class_id in DISEASES_VI:
        return DISEASES_VI[class_id]
    if "___" in class_id:
        sub = class_id.split("___")[-1]
        if sub in DISEASES_VI:
            return DISEASES_VI[sub]
    elif "_" in class_id:
        parts = class_id.split("_", 1)
        if len(parts) > 1 and parts[1] in DISEASES_VI:
            return DISEASES_VI[parts[1]]
    if "healthy" in class_id.lower():
        return "Lá khỏe mạnh, không phát hiện dấu hiệu bệnh"
    clean = class_id.replace("___", " ").replace("__", " ").replace("_", " ").strip()
    return f"Bệnh {clean}"

def get_disease_symptom_profile(class_id: str) -> Dict[str, Any]:
    key = class_id
    if "___" in class_id:
        key = class_id.split("___")[-1]
    for k in (key, class_id):
        if k in SYMPTOMS_VI:
            return SYMPTOMS_VI[k]
    if "healthy" in class_id.lower():
        return SYMPTOMS_VI.get("Healthy", SYMPTOMS_VI.get("Default", {}))
    return SYMPTOMS_VI.get("Default", {
        "symptoms": ["Có dấu hiệu biến đổi sắc tố hoặc đốm bất thường trên phiến lá."],
        "causes": ["Nấm bệnh hoặc vi khuẩn hại lá phát triển trong điều kiện ẩm độ cao."],
        "severity": "Cần theo dõi"
    })

def get_disease_recommendations(class_id: str) -> List[str]:
    key = class_id
    if "___" in class_id:
        key = class_id.split("___")[-1]
    for k in (key, class_id):
        if k in RECOMMENDATIONS_VI:
            return RECOMMENDATIONS_VI[k].get("recommendations", [])
    if "healthy" in class_id.lower():
        return RECOMMENDATIONS_VI.get("Healthy", {}).get("recommendations", ["Duy trì chế độ chăm sóc và tưới tiêu hợp lý."])
    return RECOMMENDATIONS_VI.get("Default", {}).get("recommendations", [
        "Kiểm tra thêm các lá xung quanh cây trồng.",
        "Theo dõi sự thay đổi của vết bệnh sau 2-3 ngày.",
        "Giữ khu vực trồng thông thoáng, tránh tưới ướt đẫm lá vào buổi chiều tối.",
        "Tham khảo cán bộ nông nghiệp địa phương nếu vết bệnh lan rộng."
    ])


# Crops in both detectors where original detector has higher precision (99.8% on 2,621 test photos)
ORIGINAL_PREFERRED_CROPS = {"Apple", "Mango", "Cashew", "Cherry", "Strawberry", "Rose"}

# Official author thresholds from models/README.md
CROP_CONFIDENCE_THRESHOLD = 0.60
DISEASE_CONFIDENCE_THRESHOLD = 0.45

# =============================================================================
# SEVEN PRIORITY CROPS (PART 2)
# =============================================================================
PRIORITY_CROPS: Dict[str, Dict[str, Any]] = {
    "coffee": {
        "id": "coffee",
        "name_vi": "Cà phê",
        "name_en": "Coffee",
        "has_disease_model": True,
        "disease_model_dir": "Coffee",
        "arch": "convnext_small",
        "aliases": ["coffee", "cà phê", "ca phe", "cà_phê", "ca_phe"]
    },
    "pepper": {
        "id": "pepper",
        "name_vi": "Hồ tiêu",
        "name_en": "Black Pepper",
        "has_disease_model": True,
        "disease_model_dir": "Black_Pepper",
        "arch": "convnext_small",
        "aliases": ["pepper", "hồ tiêu", "ho tieu", "black_pepper", "black pepper", "tiêu", "hồ_tiêu", "ho_tieu"]
    },
    "rice": {
        "id": "rice",
        "name_vi": "Lúa",
        "name_en": "Rice",
        "has_disease_model": True,
        "disease_model_dir": "Rice",
        "arch": "convnext_small",
        "aliases": ["rice", "lúa", "lua", "lúa_nước", "lua_nuoc"]
    },
    "durian": {
        "id": "durian",
        "name_vi": "Sầu riêng",
        "name_en": "Durian",
        "has_disease_model": False,
        "disease_model_dir": None,
        "arch": None,
        "aliases": ["durian", "sầu riêng", "sau rieng", "sầu_riêng", "sau_rieng"]
    },
    "tomato": {
        "id": "tomato",
        "name_vi": "Cà chua",
        "name_en": "Tomato",
        "has_disease_model": True,
        "disease_model_dir": "Tomato",
        "arch": "convnext_small",
        "aliases": ["tomato", "cà chua", "ca chua", "cà_chua", "ca_chua"]
    },
    "chili": {
        "id": "chili",
        "name_vi": "Ớt",
        "name_en": "Chili",
        "has_disease_model": False,
        "disease_model_dir": None,
        "arch": None,
        "aliases": ["chili", "chilli", "ớt", "ot", "pepper_bell", "pepper,_bell"]
    },
    "maize": {
        "id": "maize",
        "name_vi": "Ngô",
        "name_en": "Maize",
        "has_disease_model": True,
        "disease_model_dir": "Maize",
        "arch": "convnext_small",
        "aliases": ["maize", "corn", "ngô", "ngo", "bắp", "bap"]
    }
}

# Mapping from PlantVillage class prefix in Model tong to priority & out-of-scope crops
PLANTVILLAGE_CROP_MAP: Dict[str, Dict[str, Any]] = {
    "Corn_(maize)": {
        "priority_id": "maize",
        "name_vi": "Ngô",
        "name_en": "Maize",
        "is_priority": True,
        "has_disease_model": True,
        "disease_model_dir": "Maize"
    },
    "Tomato": {
        "priority_id": "tomato",
        "name_vi": "Cà chua",
        "name_en": "Tomato",
        "is_priority": True,
        "has_disease_model": True,
        "disease_model_dir": "Tomato"
    },
    "Pepper,_bell": {
        "priority_id": "chili",
        "name_vi": "Ớt",
        "name_en": "Chili",
        "is_priority": True,
        "has_disease_model": False,
        "disease_model_dir": None
    },
    # Out of scope PlantVillage crops (Part 2: Reject or mark unsupported, do not force into 7 crops)
    "Apple": {"priority_id": "apple", "name_vi": "Táo tây", "name_en": "Apple", "is_priority": False, "has_disease_model": False},
    "Blueberry": {"priority_id": "blueberry", "name_vi": "Việt quất", "name_en": "Blueberry", "is_priority": False, "has_disease_model": False},
    "Cherry_(including_sour)": {"priority_id": "cherry", "name_vi": "Anh đào", "name_en": "Cherry", "is_priority": False, "has_disease_model": False},
    "Grape": {"priority_id": "grape", "name_vi": "Nho", "name_en": "Grape", "is_priority": False, "has_disease_model": False},
    "Orange": {"priority_id": "orange", "name_vi": "Cam", "name_en": "Orange", "is_priority": False, "has_disease_model": False},
    "Peach": {"priority_id": "peach", "name_vi": "Đào", "name_en": "Peach", "is_priority": False, "has_disease_model": False},
    "Potato": {"priority_id": "potato", "name_vi": "Khoai tây", "name_en": "Potato", "is_priority": False, "has_disease_model": False},
    "Raspberry": {"priority_id": "raspberry", "name_vi": "Mâm xôi", "name_en": "Raspberry", "is_priority": False, "has_disease_model": False},
    "Soybean": {"priority_id": "soybean", "name_vi": "Đậu nành", "name_en": "Soybean", "is_priority": False, "has_disease_model": False},
    "Squash": {"priority_id": "squash", "name_vi": "Bí đỏ", "name_en": "Squash", "is_priority": False, "has_disease_model": False},
    "Strawberry": {"priority_id": "strawberry", "name_vi": "Dâu tây", "name_en": "Strawberry", "is_priority": False, "has_disease_model": False},
}

def resolve_priority_crop(crop_input: Optional[str]) -> Optional[Dict[str, Any]]:
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



def validate_leaf_gate(img: Image.Image) -> Dict[str, Any]:
    """
    PART 1 & PART 2 — LEAF VALIDATION GATE (Mandatory First Pipeline Gate)
    Determines whether the uploaded image is suitable for plant leaf diagnosis before
    any global crop model, Pro model, crop-specific disease model, or Grad-CAM runs.

    Outcomes:
    - LEAF_VALID: Image contains a sufficiently clear plant leaf.
    - NOT_A_LEAF: Image is clearly not a plant leaf.
    - UNCERTAIN: Image is ambiguous or leaf presence cannot be confidently confirmed.
    - IMAGE_QUALITY_LOW: Image is too blurry, dark, overexposed, or unsuitable.
    """
    metrics = {
        "width": float(img.width),
        "height": float(img.height),
        "mean_lum": 0.0,
        "color_std": 0.0,
        "lap_var": 0.0,
        "green_ratio": 0.0,
        "yellow_ratio": 0.0,
        "brown_ratio": 0.0,
        "botanical_ratio": 0.0,
        "skin_ratio": 0.0,
        "blue_ratio": 0.0,
        "mean_exg": 0.0,
    }

    # 1. Dimensions Check
    if img.width < 64 or img.height < 64:
        return {
            "status": "IMAGE_QUALITY_LOW",
            "score": 0.0,
            "message_vi": "Ảnh chưa đủ rõ để kiểm tra. Hãy chụp gần hơn, đủ sáng và giữ lá trong khung hình.",
            "metrics": metrics
        }

    if img.width > 6000 or img.height > 6000:
        return {
            "status": "IMAGE_QUALITY_LOW",
            "score": 0.0,
            "message_vi": "Ảnh chưa đủ rõ để kiểm tra. Hãy chụp gần hơn, đủ sáng và giữ lá trong khung hình.",
            "metrics": metrics
        }

    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    R, G, B = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    # 2. Luminance & Exposure Check
    lum = 0.299 * R + 0.587 * G + 0.114 * B
    mean_lum = float(lum.mean())
    metrics["mean_lum"] = round(mean_lum, 2)

    # 3. Color Diversity Check
    color_std = float(arr.std())
    metrics["color_std"] = round(color_std, 2)

    # 4. Sharpness / Blur Check (Laplacian Variance)
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    lap = gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:] - 4.0 * gray[1:-1, 1:-1]
    lap_var = float(lap.var())
    metrics["lap_var"] = round(lap_var, 2)

    # Optical quality gate: blur, extreme darkness, severe blowout, or solid blank color
    if mean_lum < 18.0 or mean_lum > 248.0 or lap_var < 12.0 or color_std < 5.0:
        return {
            "status": "IMAGE_QUALITY_LOW",
            "score": round(min(lap_var / 50.0, 0.35), 2),
            "message_vi": "Ảnh chưa đủ rõ để kiểm tra. Hãy chụp gần hơn, đủ sáng và giữ lá trong khung hình.",
            "metrics": metrics
        }

    # 5. Botanical Multi-Spectral Analysis (HSV + Normalized RGB)
    max_c = np.maximum(np.maximum(R, G), B)
    min_c = np.minimum(np.minimum(R, G), B)
    delta = max_c - min_c + 1e-6

    H = np.zeros_like(max_c)
    mask_r = (max_c == R)
    mask_g = (max_c == G)
    mask_b = (max_c == B)
    H[mask_r] = (60.0 * ((G[mask_r] - B[mask_r]) / delta[mask_r]) + 360.0) % 360.0
    H[mask_g] = 60.0 * ((B[mask_g] - R[mask_g]) / delta[mask_g]) + 120.0
    H[mask_b] = 60.0 * ((R[mask_b] - G[mask_b]) / delta[mask_b]) + 240.0

    S = delta / (max_c + 1e-6)
    tot_rgb = R + G + B + 1e-6
    r_n, g_n, b_n = R / tot_rgb, G / tot_rgb, B / tot_rgb

    # Band A: Green Foliage (Healthy or early-stage lesion)
    green_mask = ((H >= 65.0) & (H <= 165.0) & (S >= 0.15)) | ((g_n > 0.36) & (2.0 * G - R - B > 5.0))
    green_ratio = float(green_mask.mean())
    metrics["green_ratio"] = round(green_ratio, 4)

    # Band B: Chlorotic Yellow Foliage (Vàng lá do nấm, virus hoặc thiếu vi lượng)
    yellow_mask = (H >= 35.0) & (H < 65.0) & (S >= 0.20) & (b_n < 0.26) & (r_n > 0.34) & (g_n > 0.32)
    yellow_ratio = float(yellow_mask.mean())
    metrics["yellow_ratio"] = round(yellow_ratio, 4)

    # Band C: Brown Necrotic / Senescent Dry Leaf Tissue (Đốm nâu hoại tử, cháy lá, lá khô)
    brown_mask = (H >= 15.0) & (H < 35.0) & (S >= 0.18) & (r_n > 0.40) & (g_n > 0.26) & (b_n < 0.22) & ((G - B) > 8.0)
    brown_ratio = float(brown_mask.mean())
    metrics["brown_ratio"] = round(brown_ratio, 4)

    # Combined Botanical Foliage Tissue
    botanical_tissue = green_mask | yellow_mask | brown_mask
    botanical_ratio = float(botanical_tissue.mean())
    metrics["botanical_ratio"] = round(botanical_ratio, 4)
    metrics["botanical_tissue_ratio"] = round(botanical_ratio, 4)

    # Band D: Blue / Synthetic Fabric Dominance (Non-plant)
    blue_dom_mask = (b_n > 0.42) & (B > R + 15.0) & (B > G + 10.0)
    blue_ratio = float(blue_dom_mask.mean())
    metrics["blue_ratio"] = round(blue_ratio, 4)
    metrics["blue_dominance_ratio"] = round(blue_ratio, 4)

    # Band E: Human Skin Profile
    r_g_diff = np.maximum(R - G, 0.1)
    skin_ratio_test = (R - B) / r_g_diff
    skin_mask = (H >= 0.0) & (H <= 25.0) & (S >= 0.15) & (S <= 0.65) & (R > G + 15.0) & (G > B + 8.0) & (skin_ratio_test >= 1.7) & (skin_ratio_test <= 4.2)
    skin_ratio = float(skin_mask.mean())
    metrics["skin_ratio"] = round(skin_ratio, 4)
    metrics["skin_like_ratio"] = round(skin_ratio, 4)

    # Excess Green Index (ExG)
    mean_exg = float((2.0 * G - R - B).mean())
    metrics["mean_exg"] = round(mean_exg, 2)

    # ---------------------------------------------------------
    # NOT_A_LEAF Rejection Rules:
    # ---------------------------------------------------------
    # 1. Synthetic blue / cyan surfaces
    if blue_ratio > 0.35:
        return {
            "status": "NOT_A_LEAF",
            "score": 0.02,
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # 2. Human skin dominance
    if skin_ratio > 0.38 and botanical_ratio < 0.12:
        return {
            "status": "NOT_A_LEAF",
            "score": 0.04,
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # 3. Non-plant object / strong negative ExG
    if mean_exg < -18.0 and botanical_ratio < 0.15:
        return {
            "status": "NOT_A_LEAF",
            "score": 0.05,
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # 4. Total lack of botanical plant tissue (< 10%)
    if botanical_ratio < 0.10:
        return {
            "status": "NOT_A_LEAF",
            "score": round(botanical_ratio, 3),
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # 5. Complete absence of photosynthetic pigments (Green & Yellow < 2%)
    if green_ratio < 0.02 and yellow_ratio < 0.02:
        return {
            "status": "NOT_A_LEAF",
            "score": round(max(green_ratio, yellow_ratio), 3),
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # ---------------------------------------------------------
    # UNCERTAIN Rules: Ambiguous foliage or marginal ratio
    # ---------------------------------------------------------
    if botanical_ratio < 0.20 or (lap_var < 24.0 and botanical_ratio < 0.30):
        return {
            "status": "UNCERTAIN",
            "score": round(0.40 + botanical_ratio * 0.5, 2),
            "message_vi": "Gari chưa xác định được đây có phải ảnh lá cây hay không. Hãy chụp rõ một chiếc lá.",
            "metrics": metrics
        }

    # ---------------------------------------------------------
    # LEAF_VALID: Sufficient plant foliage (green, yellow, or brown)
    # ---------------------------------------------------------
    confidence = min(0.99, max(0.65, 0.50 + botanical_ratio * 0.35 + min(lap_var / 500.0, 0.15)))
    return {
        "status": "LEAF_VALID",
        "score": round(confidence, 3),
        "message_vi": None,
        "metrics": metrics
    }


def validate_image_quality(img: Image.Image) -> Tuple[bool, str, Dict[str, float]]:
    """Backward compatibility wrapper returning (passed, message, metrics)."""
    res = validate_leaf_gate(img)
    is_valid = (res["status"] == "LEAF_VALID")
    msg = res["message_vi"] or "Chất lượng ảnh đạt tiêu chuẩn chẩn đoán nông học."
    return is_valid, msg, res["metrics"]


class ModelEntry:
    def __init__(self, crop_id: str, directory: Path, config: Dict[str, Any]):
        self.crop_id = crop_id
        self.directory = directory
        self.config = config
        self.kind = config.get("kind", "disease")
        self.arch = config.get("arch", "convnext_small")
        self.framework = config.get("framework", "timm")
        self.image_size = config.get("image_size", 224)
        if self.framework == "transformers" or "vit" in self.arch.lower():
            self.mean = config.get("mean", [0.5, 0.5, 0.5])
            self.std = config.get("std", [0.5, 0.5, 0.5])
        else:
            self.mean = config.get("mean", [0.485, 0.456, 0.406])
            self.std = config.get("std", [0.229, 0.224, 0.225])
        self.classes: List[str] = config.get("classes", [])
        self.labels: List[str] = config.get("labels", self.classes)
        self.accuracy = config.get("accuracy")
        self.macro_f1 = config.get("macro_f1")
        self.weight_path = directory / "model.safetensors"
        self.weight_size_bytes = self.weight_path.stat().st_size if self.weight_path.exists() else 0
        self.weight_size_mb = round(self.weight_size_bytes / (1024 * 1024), 2)
        
        meta = localize_crop(crop_id)
        self.crop_name = meta["name_vi"]
        self.crop_name_en = meta.get("crop_id", crop_id)
        self.crop_full_name = f"{meta['name_vi']} ({meta.get('crop_id', crop_id)})"

        # Explicit VIP classification based on project markings (Part 3)
        self.is_vip = "(vip)" in directory.name.lower() or "(vip)" in crop_id.lower() or config.get("is_vip", False)

    def preprocess(self, img: Image.Image) -> torch.Tensor:
        """
        Official inference preprocessing matching models/README.md:
        - Handle EXIF orientation
        - Convert to RGB
        - Bilinear resize to 224x224
        - Normalize using model config mean and std
        """
        img_oriented = ImageOps.exif_transpose(img).convert("RGB")
        img_resized = img_oriented.resize((self.image_size, self.image_size), Image.BILINEAR)
        mean_arr = np.array(self.mean, dtype=np.float32)
        std_arr = np.array(self.std, dtype=np.float32)
        x = (np.asarray(img_resized, np.float32) / 255.0 - mean_arr) / std_arr
        tensor = torch.from_numpy(x.transpose(2, 0, 1)).float().unsqueeze(0)
        return tensor

    def to_dict(self, include_classes: bool = True) -> Dict[str, Any]:
        data = {
            "crop_id": self.crop_id,
            "crop_name": self.crop_name,
            "crop_name_en": self.crop_name_en,
            "crop_full_name": self.crop_full_name,
            "kind": self.kind,
            "is_vip": self.is_vip,
            "arch": self.arch,
            "framework": self.framework,
            "classes_count": len(self.classes),
            "weight_file": self.weight_path.name if self.weight_path.exists() else None,
            "weight_size_mb": self.weight_size_mb,
            "accuracy": self.accuracy,
            "macro_f1": self.macro_f1,
            "image_size": self.image_size,
            "mean": self.mean,
            "std": self.std,
        }
        if include_classes:
            data["classes"] = self.classes
            data["labels"] = self.labels
        return data


class GariInferenceEngine:
    def __init__(self, models_dir: Path = MODELS_DIR, max_cached: int = MAX_CACHED_MODELS):
        self.models_dir = models_dir
        self.max_cached = max_cached
        self.device = DEVICE
        self.registry: Dict[str, ModelEntry] = {}
        # Cache: crop_id -> {"model": torch.nn.Module, "last_used": float}
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.discover_models()

    def discover_models(self) -> int:
        self.registry.clear()
        if not self.models_dir.exists():
            logger.error("Models directory not found: %s", self.models_dir)
            return 0

        # Scan all directories containing config.json and model.safetensors
        for cfg_file in sorted(self.models_dir.rglob("config.json")):
            model_dir = cfg_file.parent
            weight_file = model_dir / "model.safetensors"
            if not weight_file.exists():
                continue

            # Explicitly exclude invalid or unconfigured models (e.g. models/Crop ViT with 0 classes)
            if model_dir.name.lower() == "crop":
                logger.warning("Ignoring unconfigured model directory: %s", model_dir)
                continue

            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception as e:
                logger.warning("Failed to read %s: %s", cfg_file, e)
                continue

            # Model tong 1: Standard Global Model (ViT PlantVillage 38 classes) - Non-VIP
            if model_dir.name.lower() == "model tong":
                id2label = cfg.get("id2label", {})
                classes = [id2label[str(i)] if str(i) in id2label else id2label.get(i, f"class_{i}") for i in range(len(id2label))]
                cfg["classes"] = classes
                cfg["labels"] = classes
                cfg["arch"] = "ViTForImageClassification"
                cfg["framework"] = "transformers"
                cfg["kind"] = "global"
                cfg["is_vip"] = False
                cfg["mean"] = [0.5, 0.5, 0.5]
                cfg["std"] = [0.5, 0.5, 0.5]
                entry = ModelEntry("Model tong", model_dir, cfg)
                self.registry["Model tong"] = entry
                continue

            # Model tong 2: Pro Global Model (ViT GBIF 14,829 species) - Marked (vip)
            if model_dir.name.lower() in ("model tong 2", "model tong 2 (vip)"):
                id2label = cfg.get("id2label", {})
                classes = [id2label[str(i)] if str(i) in id2label else id2label.get(i, f"class_{i}") for i in range(len(id2label))]
                cfg["classes"] = classes
                cfg["labels"] = classes
                cfg["arch"] = "ViTForImageClassification"
                cfg["framework"] = "transformers"
                cfg["kind"] = "pro_global"
                cfg["is_vip"] = True
                cfg["mean"] = [0.5, 0.5, 0.5]
                cfg["std"] = [0.5, 0.5, 0.5]
                entry = ModelEntry("Model tong 2 (vip)", model_dir, cfg)
                self.registry["Model tong 2"] = entry
                self.registry["Model tong 2 (vip)"] = entry
                continue

            # Model tong 3: RT-DETRv2 Object Detection (27 classes) - Non-VIP
            if model_dir.name.lower() == "model tong 3":
                id2label = cfg.get("id2label", {})
                classes = [id2label[str(i)] if str(i) in id2label else id2label.get(i, f"class_{i}") for i in range(len(id2label))]
                cfg["classes"] = classes
                cfg["labels"] = classes
                cfg["arch"] = "RTDetrV2ForObjectDetection"
                cfg["framework"] = "transformers"
                cfg["kind"] = "global_detection"
                cfg["is_vip"] = False
                entry = ModelEntry("model tong 3", model_dir, cfg)
                self.registry["model tong 3"] = entry
                continue

            # Model tong 4: DINOv2 (38 classes) - Marked (vip)
            if model_dir.name.lower() in ("model tong 4", "model tong 4 (vip)"):
                id2label = cfg.get("id2label", {})
                classes = [id2label[str(i)] if str(i) in id2label else id2label.get(i, f"class_{i}") for i in range(len(id2label))]
                cfg["classes"] = classes
                cfg["labels"] = classes
                cfg["arch"] = "Dinov2ForImageClassification"
                cfg["framework"] = "transformers"
                cfg["kind"] = "pro_dinov2"
                cfg["is_vip"] = True
                entry = ModelEntry("model tong 4 (vip)", model_dir, cfg)
                self.registry["model tong 4 (vip)"] = entry
                self.registry["model tong 4"] = entry
                continue

            # Verify classes count is valid for crop models
            classes = cfg.get("classes", [])
            if not classes or len(classes) == 0:
                logger.warning("Ignoring model %s with 0 classes in config.json", model_dir)
                continue

            rel = model_dir.relative_to(self.models_dir)
            crop_id = str(rel).replace("\\", "/")
            entry = ModelEntry(crop_id, model_dir, cfg)
            self.registry[crop_id] = entry

        # Model tong 5: YOLOv8 PyTorch best.pt - Non-VIP
        model_5_dir = self.models_dir / "Model tong 5"
        if model_5_dir.exists() and (model_5_dir / "best.pt").exists():
            cfg_5 = {"arch": "yolov8", "kind": "global_yolo", "is_vip": False, "classes": ["leaf", "disease"]}
            entry_5 = ModelEntry("Model tong 5", model_5_dir, cfg_5)
            self.registry["Model tong 5"] = entry_5

        logger.info("Discovered %d valid models in %s (Device: %s)", len(self.registry), self.models_dir, self.device)
        return len(self.registry)

    def list_models(self) -> List[Dict[str, Any]]:
        results = []
        for crop_id, entry in sorted(self.registry.items()):
            d = entry.to_dict(include_classes=True)
            d["is_loaded"] = crop_id in self.cache
            d["device"] = str(self.device)
            results.append(d)
        return results

    def get_model_entry(self, crop_id: str) -> Optional[ModelEntry]:
        canonical = normalize_crop_id(crop_id)
        if canonical and canonical in self.registry:
            return self.registry[canonical]
        if crop_id in self.registry:
            return self.registry[crop_id]

        cid_lower = (canonical or crop_id).lower().replace("-", "_").replace(" ", "_")
        for k, v in self.registry.items():
            if k.lower() == cid_lower:
                return v
        return None

    def load_model(self, crop_id: str) -> Tuple[torch.nn.Module, ModelEntry]:
        entry = self.get_model_entry(crop_id)
        if entry is None:
            supported = [k for k, v in self.registry.items() if v.kind == "disease"]
            raise ValueError(f"Unknown or unsupported crop '{crop_id}'. Supported crops: {', '.join(supported)}")

        actual_id = entry.crop_id
        now = time.time()

        if actual_id in self.cache:
            self.cache[actual_id]["last_used"] = now
            return self.cache[actual_id]["model"], entry

        # Evict least recently used model if cache is full
        if len(self.cache) >= self.max_cached:
            oldest_id = min(self.cache.keys(), key=lambda k: self.cache[k]["last_used"])
            logger.info("Evicting model '%s' from cache (capacity: %d)", oldest_id, self.max_cached)
            del self.cache[oldest_id]["model"]
            del self.cache[oldest_id]
            if self.device.type == "cuda":
                torch.cuda.empty_cache()

        logger.info("Loading model weights for '%s' (%s, %s MB) on %s...",
                    actual_id, entry.arch, entry.weight_size_mb, self.device)
        t0 = time.time()

        try:
            if getattr(entry, "framework", "timm") == "transformers" or entry.arch == "ViTForImageClassification":
                from transformers import AutoModelForImageClassification
                net = AutoModelForImageClassification.from_pretrained(str(entry.directory))
                net.to(self.device)
                net.eval()
            else:
                net = timm.create_model(entry.arch, pretrained=False, num_classes=len(entry.classes))
                state_dict = load_file(str(entry.weight_path))
                net.load_state_dict({k: v.float() for k, v in state_dict.items()})

                # Consistency check: verify output head dimension matches len(classes)
                head = getattr(net, "head", None)
                if head is not None and hasattr(head, "fc"):
                    out_feat = head.fc.out_features
                    if out_feat != len(entry.classes):
                        raise ValueError(f"Checkpoint head dimension {out_feat} does not match config classes {len(entry.classes)}")

                net.to(self.device)
                net.eval()
        except Exception as exc:
            logger.error("Failed to load model '%s': %s", actual_id, exc)
            raise RuntimeError(f"Failed to load weights for {actual_id}: {exc}") from exc

        load_ms = round((time.time() - t0) * 1000, 2)
        logger.info("Model '%s' loaded successfully in %s ms", actual_id, load_ms)

        self.cache[actual_id] = {
            "model": net,
            "last_used": now,
            "load_time_ms": load_ms,
        }
        return net, entry

    def unload_model(self, crop_id: str) -> bool:
        entry = self.get_model_entry(crop_id)
        actual_id = entry.crop_id if entry else crop_id
        if actual_id in self.cache:
            del self.cache[actual_id]["model"]
            del self.cache[actual_id]
            if self.device.type == "cuda":
                torch.cuda.empty_cache()
            logger.info("Unloaded model '%s'", actual_id)
            return True
        return False

    def unload_all(self) -> None:
        self.cache.clear()
        if self.device.type == "cuda":
            torch.cuda.empty_cache()
        logger.info("Unloaded all cached models")

    def _infer_detector_raw(self, detector_id: str, img: Image.Image) -> List[Tuple[str, float]]:
        entry = self.registry.get(detector_id)
        if not entry:
            return []
        net, entry = self.load_model(detector_id)
        tensor = entry.preprocess(img).to(self.device)
        with torch.no_grad():
            logits = net(tensor)
            probs = torch.softmax(logits, dim=1)[0]
        top_indices = torch.argsort(probs, descending=True)
        return [(entry.classes[i], float(probs[i])) for i in top_indices]

    def evaluate_crop_validation_gate(self, img: Image.Image) -> Dict[str, Any]:
        """
        PHASE 5 — CROP VALIDATION GATE (Mandatory)
        Executes dual-detector ensemble (original 16-crop + new 36-crop).
        Returns one of 5 strict states:
        - A: CROP_CONFIDENT (Proceed to disease model)
        - B: MULTIPLE_CANDIDATES (Ambiguous; prompt user to confirm)
        - C: CROP_UNCERTAIN (Confidence < 60%; do not run disease model)
        - D: UNSUPPORTED_CROP (Crop recognized, but has no local disease model)
        - E: REJECTED_LOW_QUALITY (Image blurry, solid, corrupt, or non-leaf)
        """
        # 1. Image Quality Validation
        is_valid, reason_quality, metrics = validate_image_quality(img)
        if not is_valid:
            return {
                "state": "REJECTED_LOW_QUALITY",
                "status": "rejected_low_quality",
                "can_proceed_to_disease": False,
                "selected_crop": None,
                "crop_id": None,
                "crop_name_vi": None,
                "confidence": 0.0,
                "confidence_percent": 0.0,
                "reason": reason_quality,
                "message": reason_quality,
                "candidates": [],
                "quality_metrics": metrics,
                "guidelines": [
                    "Chụp gần một lá cây đơn lẻ rõ nét dưới ánh sáng ban ngày tự nhiên.",
                    "Giữ chắc máy ảnh hoặc điện thoại để tránh rung nhòe (độ mờ LapVar phải đạt chuẩn).",
                    "Đảm bảo vết bệnh nằm ở trung tâm khung hình."
                ]
            }

        # 2. Run both detectors
        preds_orig = self._infer_detector_raw("detectors/original", img)
        preds_new = self._infer_detector_raw("detectors/new", img)

        if not preds_orig and not preds_new:
            return {
                "state": "CROP_UNCERTAIN",
                "status": "crop_uncertain",
                "can_proceed_to_disease": False,
                "selected_crop": None,
                "confidence": 0.0,
                "reason": "Không tìm thấy mô hình nhận diện cây trồng cục bộ.",
                "message": "Chưa đủ cơ sở để xác định bệnh cây trồng.",
                "candidates": []
            }

        top_orig_crop, top_orig_conf = preds_orig[0] if preds_orig else ("None", 0.0)
        top_new_crop, top_new_conf = preds_new[0] if preds_new else ("None", 0.0)

        # Normalize names to canonical catalog IDs
        canonical_orig = normalize_crop_id(top_orig_crop) or top_orig_crop
        canonical_new = normalize_crop_id(top_new_crop) or top_new_crop

        # Aggregate candidates map
        candidates_map: Dict[str, float] = {}
        for c, p in preds_new[:8]:
            cid = normalize_crop_id(c) or c
            candidates_map[cid] = max(candidates_map.get(cid, 0.0), p)

        for c, p in preds_orig[:5]:
            cid = normalize_crop_id(c) or c
            # If the crop belongs to original detector's 16 classes, it has high precision
            candidates_map[cid] = max(candidates_map.get(cid, 0.0), p)

        sorted_candidates = []
        for cid, conf in sorted(candidates_map.items(), key=lambda x: x[1], reverse=True)[:5]:
            meta = get_crop_metadata(cid)
            sorted_candidates.append({
                "crop_id": cid,
                "crop_name": meta["vi_name"] if meta else cid.replace("_", " ").title(),
                "crop_full_name": get_vietnamese_crop_name(cid),
                "confidence": round(conf, 4),
                "percent": round(conf * 100, 2),
                "has_disease_model": meta["has_disease_model"] if meta else (cid in self.registry)
            })

        # Decision flow as specified by the model author:
        # If detectors/new names a crop outside (Apple, Mango, Cashew, Cherry, Strawberry, Rose) with at least 80% confidence, use that.
        selected_crop = None
        decision_confidence = 0.0

        if canonical_new not in ORIGINAL_PREFERRED_CROPS and top_new_conf >= 0.70:
            selected_crop = canonical_new
            decision_confidence = top_new_conf
        elif top_orig_conf >= CROP_CONFIDENCE_THRESHOLD:
            selected_crop = canonical_orig
            decision_confidence = top_orig_conf
        elif top_new_conf >= CROP_CONFIDENCE_THRESHOLD:
            selected_crop = canonical_new
            decision_confidence = top_new_conf

        # Check for ambiguity between top 2 candidates
        is_ambiguous = False
        if len(sorted_candidates) >= 2:
            c1 = sorted_candidates[0]["confidence"]
            c2 = sorted_candidates[1]["confidence"]
            # Close candidates: diff < 15% when top1 < 75%, or top1 < 70% and top2 > 20%
            if (c1 - c2 < 0.15 and c1 < 0.75) or (c1 < 0.70 and c2 > 0.20):
                is_ambiguous = True

        # Check disagreement between detectors on shared crops (e.g. Det16 says Rose 65% but Det36 says Rose 9%)
        if selected_crop in ORIGINAL_PREFERRED_CROPS:
            new_crop_conf = next((p for c, p in preds_new if normalize_crop_id(c) == selected_crop), 0.0)
            if new_crop_conf < 0.20:
                is_ambiguous = True
                logger.info("Detectors disagree on '%s' (Orig: %.2f%% vs New: %.2f%%). Triggering ambiguity gate.",
                            selected_crop, decision_confidence * 100, new_crop_conf * 100)

        # Check if selected crop is unsupported (no local disease model)
        if selected_crop:
            meta = get_crop_metadata(selected_crop)
            if meta and not meta.get("has_disease_model", True):
                unsupported_reason = meta.get("unsupported_reason", f"Cây trồng '{meta['vi_name']}' hiện chưa có mô hình chẩn đoán bệnh cục bộ.")
                return {
                    "state": "UNSUPPORTED_CROP",
                    "status": "unsupported_crop",
                    "can_proceed_to_disease": False,
                    "selected_crop": selected_crop,
                    "crop_id": selected_crop,
                    "crop_name_vi": meta["vi_name"],
                    "crop_full_name": get_vietnamese_crop_name(selected_crop),
                    "confidence": round(decision_confidence, 4),
                    "confidence_percent": round(decision_confidence * 100, 2),
                    "reason": unsupported_reason,
                    "message": unsupported_reason,
                    "candidates": sorted_candidates,
                    "quality_metrics": metrics
                }

        # If ambiguous, prompt user to confirm crop
        if is_ambiguous:
            cand1 = sorted_candidates[0]
            cand2 = sorted_candidates[1]
            return {
                "state": "MULTIPLE_CANDIDATES",
                "status": "multiple_candidates",
                "can_proceed_to_disease": False,
                "selected_crop": selected_crop,
                "crop_id": selected_crop,
                "confidence": round(decision_confidence, 4),
                "confidence_percent": round(decision_confidence * 100, 2),
                "reason": f"Mô hình phát hiện nhiều khả năng cây trồng ({cand1['crop_name']} {cand1['percent']}%, {cand2['crop_name']} {cand2['percent']}%). Vui lòng xác nhận loại cây trồng của bạn trước khi chẩn đoán bệnh.",
                "message": "Phát hiện nhiều loại cây trồng tiềm năng. Vui lòng xác nhận cây trồng của bạn.",
                "candidates": sorted_candidates,
                "quality_metrics": metrics
            }

        # If confidence is below threshold (< 60%), refuse automatic disease diagnosis
        if not selected_crop or decision_confidence < CROP_CONFIDENCE_THRESHOLD:
            return {
                "state": "CROP_UNCERTAIN",
                "status": "crop_uncertain",
                "can_proceed_to_disease": False,
                "selected_crop": None,
                "crop_id": None,
                "confidence": round(decision_confidence, 4),
                "confidence_percent": round(decision_confidence * 100, 2),
                "reason": f"Chưa xác định được loại cây (Điểm dự đoán cao nhất: {decision_confidence * 100:.1f}% < 60%). Vui lòng chọn loại cây hoặc chụp lại ảnh rõ hơn.",
                "message": "Chưa xác định được loại cây. Vui lòng chọn loại cây hoặc chụp lại ảnh rõ hơn.",
                "candidates": sorted_candidates,
                "quality_metrics": metrics,
                "guidelines": [
                    "Vui lòng chụp một chiếc lá cây ở cự ly gần hơn (15-25cm), bao phủ phần lớn khung hình.",
                    "Đảm bảo đủ ánh sáng tự nhiên và lấy nét rõ vào mặt lá.",
                    "Bạn cũng có thể tự chọn loại cây trồng trong danh sách để chạy mô hình chẩn đoán bệnh tương ứng."
                ]
            }

        # Confident identification
        meta = get_crop_metadata(selected_crop)
        return {
            "state": "CROP_CONFIDENT",
            "status": "crop_confident",
            "can_proceed_to_disease": True,
            "selected_crop": selected_crop,
            "crop_id": selected_crop,
            "crop_name_vi": meta["vi_name"] if meta else selected_crop,
            "crop_full_name": get_vietnamese_crop_name(selected_crop),
            "confidence": round(decision_confidence, 4),
            "confidence_percent": round(decision_confidence * 100, 2),
            "reason": f"Xác định tin cậy cây trồng: {get_vietnamese_crop_name(selected_crop)} ({decision_confidence * 100:.1f}%).",
            "message": "Cây trồng được xác định thành công.",
            "candidates": sorted_candidates,
            "quality_metrics": metrics
        }

    def detect_crop(self, image: Image.Image) -> Tuple[str, float]:
        """Convenience method returning top crop and confidence."""
        gate_res = self.evaluate_crop_validation_gate(image)
        if gate_res.get("selected_crop"):
            return gate_res["selected_crop"], gate_res["confidence"]
        candidates = gate_res.get("candidates", [])
        if candidates:
            return candidates[0]["crop_id"], candidates[0]["confidence"]
        return "Unknown", 0.0

    def get_global_model(self):
        """Loads and caches the standard global PlantVillage ViT model in models/Model tong."""
        if "global_vit" not in self.cache:
            model_dir = self.models_dir / "Model tong"
            logger.info("Loading standard global model 'Model tong' (ViT) from %s...", model_dir)
            from transformers import AutoModelForImageClassification
            vit = AutoModelForImageClassification.from_pretrained(str(model_dir))
            vit.to(self.device)
            vit.eval()
            self.cache["global_vit"] = {
                "model": vit,
                "last_used": time.time(),
                "load_time_ms": 0.0,
                "model_dir": model_dir
            }
        self.cache["global_vit"]["last_used"] = time.time()
        return self.cache["global_vit"]["model"]

    def get_pro_global_model(self):
        """Loads and caches the Pro global ViT model in models/Model tong 2 (vip)."""
        if "pro_global_vit" not in self.cache:
            p1 = self.models_dir / "Model tong 2 (vip)"
            p2 = self.models_dir / "Model tong 2"
            model_dir = p1 if p1.exists() else p2
            if not model_dir.exists():
                raise FileNotFoundError(f"Không tìm thấy thư mục mô hình Pro tại {p1} hoặc {p2}")
            logger.info("Loading Pro global model 'Model tong 2' (ViT) from %s...", model_dir)
            from transformers import AutoModelForImageClassification
            vit = AutoModelForImageClassification.from_pretrained(str(model_dir))
            vit.to(self.device)
            vit.eval()
            self.cache["pro_global_vit"] = {
                "model": vit,
                "last_used": time.time(),
                "load_time_ms": 0.0,
                "model_dir": model_dir
            }
        self.cache["pro_global_vit"]["last_used"] = time.time()
        return self.cache["pro_global_vit"]["model"]

    def run_global_crop_identification(self, img: Image.Image) -> Dict[str, Any]:
        """
        Mode A — Standard Automatic Crop Identification using models/Model tong.
        Applies exact ViT preprocessing (224x224 RGB, mean=[0.5,0.5,0.5], std=[0.5,0.5,0.5]).
        Computes 38-class softmax distribution, aggregates marginal crop probabilities,
        and returns top 3 crop candidates with uncalibrated raw scores.
        """
        vit_net = self.get_global_model()
        
        img_oriented = ImageOps.exif_transpose(img).convert("RGB")
        img_resized = img_oriented.resize((224, 224), Image.BILINEAR)
        mean_arr = np.array([0.5, 0.5, 0.5], dtype=np.float32)
        std_arr = np.array([0.5, 0.5, 0.5], dtype=np.float32)
        x = (np.asarray(img_resized, np.float32) / 255.0 - mean_arr) / std_arr
        tensor = torch.from_numpy(x.transpose(2, 0, 1)).float().unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = vit_net(tensor).logits
            probs = torch.softmax(logits, dim=1)[0].cpu().numpy()

        # Aggregate probabilities by crop across the 38 classes
        crop_scores: Dict[str, float] = {}
        id2label = vit_net.config.id2label
        for i in range(len(probs)):
            label = id2label[i] if isinstance(id2label, dict) and i in id2label else str(i)
            pv_prefix = label.split("___")[0] if "___" in label else label
            crop_scores[pv_prefix] = crop_scores.get(pv_prefix, 0.0) + float(probs[i])

        sorted_crops = sorted(crop_scores.items(), key=lambda kv: kv[1], reverse=True)
        
        candidates = []
        for pv_prefix, score in sorted_crops[:3]:
            info = PLANTVILLAGE_CROP_MAP.get(pv_prefix, {
                "priority_id": pv_prefix.lower(),
                "name_vi": pv_prefix,
                "name_en": pv_prefix,
                "is_priority": False,
                "has_disease_model": False,
                "disease_model_dir": None
            })
            candidates.append({
                "pv_crop": pv_prefix,
                "crop_id": info["priority_id"],
                "name_vi": info["name_vi"],
                "name_en": info["name_en"],
                "score": round(float(score), 4),
                "score_percent": round(float(score) * 100, 2),
                "is_priority_crop": info["is_priority"],
                "has_disease_model": info.get("has_disease_model", False),
                "disease_model_dir": info.get("disease_model_dir")
            })

        top_crop = candidates[0] if candidates else None
        
        # Uncertainty check: threshold 0.35, or margin < 0.08 when top1 < 0.50
        is_uncertain = False
        if top_crop is None or top_crop["score"] < 0.35:
            is_uncertain = True
        elif len(candidates) > 1 and top_crop["score"] < 0.50 and (top_crop["score"] - candidates[1]["score"] < 0.08):
            is_uncertain = True

        return {
            "top_crop": top_crop,
            "candidates": candidates,
            "is_uncertain": is_uncertain,
            "raw_probs": probs,
            "model_id": "Model tong (ViT-Base PlantVillage)",
            "model_name": "Model tong (ViT-Base PlantVillage)"
        }

    def run_pro_crop_identification(self, img: Image.Image) -> Dict[str, Any]:
        """
        PART 4 — Pro Automatic Diagnosis using models/Model tong 2 (vip).
        ViT GBIF model with 14,829 plant species.
        Computes 14,829-class distribution, identifies top species,
        and maps to priority crops when applicable.
        """
        pro_net = self.get_pro_global_model()
        
        img_oriented = ImageOps.exif_transpose(img).convert("RGB")
        img_resized = img_oriented.resize((224, 224), Image.BILINEAR)
        mean_arr = np.array([0.5, 0.5, 0.5], dtype=np.float32)
        std_arr = np.array([0.5, 0.5, 0.5], dtype=np.float32)
        x = (np.asarray(img_resized, np.float32) / 255.0 - mean_arr) / std_arr
        tensor = torch.from_numpy(x.transpose(2, 0, 1)).float().unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = pro_net(tensor).logits
            probs = torch.softmax(logits, dim=1)[0].cpu().numpy()

        top_indices = np.argsort(probs)[::-1][:5]
        id2label = pro_net.config.id2label

        top_predictions = []
        for idx in top_indices:
            label = id2label[idx] if isinstance(id2label, dict) and idx in id2label else (id2label.get(str(idx), f"species_{idx}") if isinstance(id2label, dict) else str(idx))
            p_val = float(probs[idx])
            top_predictions.append({
                "species_latin": label,
                "score": round(p_val, 4),
                "score_percent": round(p_val * 100, 2)
            })

        best = top_predictions[0] if top_predictions else {"species_latin": "Unknown", "score": 0.0}
        best_species = best["species_latin"]
        best_score = best["score"]

        # Map species to priority crops if applicable
        resolved_crop = None
        bs_lower = best_species.lower()
        if "coffea" in bs_lower:
            resolved_crop = PRIORITY_CROPS["coffee"]
        elif "lycopersicum" in bs_lower or "tomato" in bs_lower:
            resolved_crop = PRIORITY_CROPS["tomato"]
        elif "zea mays" in bs_lower or "corn" in bs_lower:
            resolved_crop = PRIORITY_CROPS["maize"]
        elif "capsicum" in bs_lower:
            resolved_crop = PRIORITY_CROPS["chili"]
        elif "durio" in bs_lower:
            resolved_crop = PRIORITY_CROPS["durian"]
        elif "piper nigrum" in bs_lower:
            resolved_crop = PRIORITY_CROPS["pepper"]
        elif "oryza" in bs_lower:
            resolved_crop = PRIORITY_CROPS["rice"]

        return {
            "top_species": best_species,
            "species_score": best_score,
            "top_predictions": top_predictions,
            "resolved_priority_crop": resolved_crop,
            "model_id": "Model tong 2 (Pro ViT GBIF 14,829 species)",
            "model_name": "Model tong 2 (Pro ViT-Base GBIF 14,829 loài)"
        }

    def run_crop_disease_model(self, img: Image.Image, model_dir_name: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Runs verified crop-specific disease model with exact ConvNeXt preprocessing
        (224x224 RGB, mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]).
        Returns disease predictions in Vietnamese and Grad-CAM visual attention localization.
        """
        entry = self.get_model_entry(model_dir_name)
        if not entry:
            raise ValueError(f"Không tìm thấy mô hình bệnh '{model_dir_name}' trong registry.")
        
        net, entry = self.load_model(entry.crop_id)
        tensor = entry.preprocess(img).to(self.device)
        
        with torch.no_grad():
            logits = net(tensor)
            probs = torch.softmax(logits, dim=1)[0]
        
        k = min(top_k, len(entry.classes))
        top_vals, top_indices = torch.topk(probs, k=k)
        
        top_predictions = []
        for idx, val in zip(top_indices.tolist(), top_vals.tolist()):
            cls_name = entry.classes[idx]
            name_vi = localize_disease(cls_name)
            top_predictions.append({
                "class_id": cls_name,
                "label": name_vi,
                "name": name_vi,
                "name_vi": name_vi,
                "confidence": round(float(val), 4),
                "confidence_percent": round(float(val) * 100, 2),
            })
            
        best = top_predictions[0] if top_predictions else {}
        best_class = best.get("class_id", "Unknown")
        best_conf = best.get("confidence", 0.0)
        best_name_vi = best.get("name_vi", "Chưa xác định")
        
        # Grad-CAM Visual Localization
        localization_bundle = None
        best_idx = top_indices[0].item() if len(top_indices) > 0 else 0
        try:
            uploads_dir = WORKSPACE_DIR / "database" / "uploads"
            file_prefix = f"diag_{int(time.time()*1000)}"
            localization_bundle = generate_visual_localization_bundle(
                net=net,
                entry=entry,
                image=img,
                output_dir=uploads_dir,
                file_prefix=file_prefix,
                target_class_idx=best_idx,
                device=self.device
            )
        except Exception as exc:
            logger.warning("Visual localization bundle generation failed: %s", exc)
            
        return {
            "disease_id": best_class,
            "disease_name_vi": best_name_vi,
            "disease_score": best_conf,
            "top_predictions": top_predictions,
            "model_name": f"ConvNeXt-Small ({model_dir_name})",
            "model_id": f"ConvNeXt-Small ({model_dir_name})",
            "model_arch": entry.arch,
            "localization": localization_bundle,
            "entry": entry
        }

    def predict(
        self,
        image_input: Any,
        crop_id: Optional[str] = None,
        mode: Optional[str] = "auto_standard",
        dev_pro_authorized: bool = False,
        user_entitled: bool = False,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        CENTRAL MODEL ROUTING PIPELINE (Part 1, 3, 4, 5, 6)
        
        Pipeline:
        1. Decode and validate image.
        2. FIRST GATE: Leaf Validation (validate_leaf_gate).
           If NOT_A_LEAF, UNCERTAIN, or IMAGE_QUALITY_LOW: STOP inference immediately.
           Do not run crop model, Pro model, disease model, or Grad-CAM.
        3. If LEAF_VALID, route based on mode:
           - auto_standard: Standard Global ViT (Model tong) -> priority crop -> disease model.
           - auto_pro: Verify entitlement -> Pro Global ViT (Model tong 2) -> priority crop -> disease model.
           - manual: Verify priority crop -> selected crop disease model only.
        """
        start_ts = time.perf_counter()
        
        # Normalize mode
        raw_mode = (mode or "auto_standard").strip().lower()
        if raw_mode in ("auto", "auto_standard", "standard"):
            norm_mode = "auto_standard"
        elif raw_mode in ("auto_pro", "pro"):
            norm_mode = "auto_pro"
        elif raw_mode in ("manual", "crop_specific"):
            norm_mode = "manual"
        elif crop_id and crop_id.lower() not in ("auto", "all", "detect", "", "unknown") and raw_mode not in ("auto_pro", "pro"):
            norm_mode = "manual"
        else:
            norm_mode = "auto_standard"
            
        # 1. Load and decode PIL Image
        if isinstance(image_input, (bytes, bytearray)):
            img = Image.open(io.BytesIO(image_input))
        elif isinstance(image_input, Image.Image):
            img = image_input
        elif hasattr(image_input, "read"):
            data = image_input.read()
            img = Image.open(io.BytesIO(data))
        else:
            raise ValueError(f"Unsupported image input type: {type(image_input)}")

        img = ImageOps.exif_transpose(img).convert("RGB")
        
        # -------------------------------------------------------------
        # PART 1 — LEAF VALIDATION GATE (MUST RUN FIRST)
        # -------------------------------------------------------------
        gate_res = validate_leaf_gate(img)
        validation_status = gate_res["status"]
        validation_score = gate_res["score"]
        validation_msg = gate_res["message_vi"]

        if validation_status != "LEAF_VALID":
            # STOP INFERENCE IMMEDIATELY.
            # Do NOT run global crop model, Pro model, disease model, or Grad-CAM!
            elapsed_ms = round((time.perf_counter() - start_ts) * 1000.0, 2)
            p_crop = resolve_priority_crop(crop_id)
            return {
                "success": False,
                "status": validation_status.lower(),
                "validation_state": validation_status,
                "validation": {
                    "status": validation_status,
                    "score": validation_score,
                    "message_vi": validation_msg
                },
                "mode": norm_mode,
                "crop_id": None,
                "crop_name_vi": None,
                "disease_id": None,
                "disease_name_vi": None,
                "model_id": None,
                "model_name": None,
                "confidence": 0.0,
                "confidence_percent": 0.0,
                "prediction": "Ảnh chưa phù hợp để chẩn đoán",
                "message": validation_msg,
                "reason": validation_msg,
                "warning": validation_msg,
                "quality_metrics": gate_res["metrics"],
                "inference_time_ms": elapsed_ms,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        validation_dict = {
            "status": "LEAF_VALID",
            "score": validation_score,
            "message_vi": None
        }

        # -------------------------------------------------------------
        # PART 3 — MODE A: STANDARD GLOBAL MODEL (auto_standard)
        # -------------------------------------------------------------
        if norm_mode == "auto_standard":
            global_res = self.run_global_crop_identification(img)
            top_crop = global_res.get("top_crop")
            candidates = global_res.get("candidates", [])
            is_uncertain = global_res.get("is_uncertain", False)
            
            # If crop identification is uncertain
            if is_uncertain or top_crop is None:
                elapsed_ms = round((time.perf_counter() - start_ts) * 1000.0, 2)
                return {
                    "success": True,
                    "status": "crop_uncertain",
                    "validation_state": "CROP_UNCERTAIN",
                    "validation": validation_dict,
                    "mode": "auto_standard",
                    "crop_id": top_crop["crop_id"] if top_crop else None,
                    "crop_name_vi": top_crop["name_vi"] if top_crop else None,
                    "crop_score": top_crop["score"] if top_crop else 0.0,
                    "disease_id": None,
                    "disease_name_vi": None,
                    "prediction": "Chưa đủ cơ sở xác định cây trồng",
                    "predicted_disease": "Chưa đủ cơ sở xác định cây trồng",
                    "confidence": 0.0,
                    "confidence_percent": 0.0,
                    "message": "Chưa đủ cơ sở xác định cây trồng. Vui lòng xác nhận loại cây hoặc chọn chế độ 'Chọn cây thủ công'.",
                    "reason": "Điểm tin cậy nhận diện cây trồng của mô hình toàn cục dưới ngưỡng an toàn.",
                    "crop_candidates": candidates,
                    "model_id": "Model tong (ViT-Base PlantVillage)",
                    "model_name": "Model tong (ViT-Base PlantVillage)",
                    "inference_time_ms": elapsed_ms,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
            # If crop identified is NOT in the 7 priority crops (Part 2)
            if not top_crop.get("is_priority_crop", False):
                elapsed_ms = round((time.perf_counter() - start_ts) * 1000.0, 2)
                return {
                    "success": True,
                    "status": "unsupported_crop",
                    "validation_state": "UNSUPPORTED_CROP",
                    "validation": validation_dict,
                    "mode": "auto_standard",
                    "crop_id": top_crop["crop_id"],
                    "crop_name_vi": top_crop["name_vi"],
                    "crop_score": top_crop["score"],
                    "disease_id": None,
                    "disease_name_vi": None,
                    "prediction": "Cây trồng ngoài phạm vi ưu tiên",
                    "predicted_disease": "Cây trồng ngoài phạm vi ưu tiên",
                    "confidence": 0.0,
                    "confidence_percent": 0.0,
                    "message": f"Cây trồng được nhận diện ({top_crop['name_vi']}) nằm ngoài phạm vi 7 loại cây ưu tiên.",
                    "reason": f"Mô hình toàn cục nhận diện lá cây là '{top_crop['name_vi']}', không nằm trong danh mục 7 loại cây thử nghiệm.",
                    "crop_candidates": candidates,
                    "model_id": "Model tong (ViT-Base PlantVillage)",
                    "model_name": "Model tong (ViT-Base PlantVillage)",
                    "inference_time_ms": elapsed_ms,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
            # Top crop IS a priority crop (tomato, maize, chili)
            # Check if crop-specific disease model exists
            if not top_crop.get("has_disease_model", False):
                # E.g. chili (identified by Model tong as Pepper,_bell, but no crop-specific model in models/)
                elapsed_ms = round((time.perf_counter() - start_ts) * 1000.0, 2)
                return {
                    "success": True,
                    "status": "crop_identified_no_disease_model",
                    "validation_state": "CROP_IDENTIFIED_NO_DISEASE_MODEL",
                    "validation": validation_dict,
                    "mode": "auto_standard",
                    "crop_id": top_crop["crop_id"],
                    "crop_name_vi": top_crop["name_vi"],
                    "crop_score": top_crop["score"],
                    "disease_id": None,
                    "disease_name_vi": None,
                    "prediction": "Chưa có mô hình bệnh lý",
                    "predicted_disease": "Chưa có mô hình bệnh lý",
                    "confidence": 0.0,
                    "confidence_percent": 0.0,
                    "message": f"Đã nhận diện cây ({top_crop['name_vi']}), nhưng mô hình chẩn đoán bệnh cho cây này chưa sẵn sàng.",
                    "reason": f"Cây {top_crop['name_vi']} chưa có mô hình chẩn đoán bệnh lý cục bộ tương thích.",
                    "crop_candidates": candidates,
                    "model_id": "Model tong (ViT-Base PlantVillage)",
                    "model_name": "Model tong (ViT-Base PlantVillage)",
                    "inference_time_ms": elapsed_ms,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
            # Has compatible disease model (Tomato, Maize)
            disease_model_dir = top_crop["disease_model_dir"]
            diag_res = self.run_crop_disease_model(img, disease_model_dir, top_k=top_k)
            
            elapsed_ms = round((time.perf_counter() - start_ts) * 1000.0, 2)
            loc = diag_res.get("localization") or {}
            is_healthy = "healthy" in diag_res["disease_id"].lower()
            best_class = diag_res["disease_id"]
            
            symptom_profile = get_disease_symptom_profile(best_class)
            symptoms_list = symptom_profile.get("symptoms", ["Có dấu hiệu biến đổi sắc tố hoặc đốm bất thường trên phiến lá."])
            causes_list = symptom_profile.get("causes", ["Mầm bệnh phát triển trong điều kiện ẩm độ cao hoặc lây nhiễm qua vết thương."])
            recommendations_list = get_disease_recommendations(best_class)
            
            return {
                "success": True,
                "status": "OK",
                "validation_state": "DIAGNOSIS_CONFIRMED",
                "validation": validation_dict,
                "mode": "auto_standard",
                "crop": top_crop["crop_id"],
                "crop_id": top_crop["crop_id"],
                "crop_name": top_crop["name_vi"],
                "crop_name_vi": top_crop["name_vi"],
                "crop_score": top_crop["score"],
                "crop_candidates": candidates,
                "class_id": diag_res["disease_id"],
                "prediction": diag_res["disease_name_vi"],
                "disease_id": diag_res["disease_id"],
                "disease_name_vi": diag_res["disease_name_vi"],
                "disease_score": diag_res["disease_score"],
                "confidence": diag_res["disease_score"],
                "confidence_percent": round(diag_res["disease_score"] * 100, 2),
                "severity": "NORMAL" if is_healthy else ("HIGH" if diag_res["disease_score"] > 0.85 else "MEDIUM"),
                "is_healthy": is_healthy,
                "top_predictions": diag_res["top_predictions"],
                "model_id": f"Model tong -> ConvNeXt-Small ({disease_model_dir})",
                "model_name": f"Model tong (ViT-Base) -> ConvNeXt-Small ({disease_model_dir})",
                "model_arch": diag_res["model_arch"],
                "inference_time_ms": elapsed_ms,
                "localization_type": "gradcam",
                "overlay_image_url": loc.get("overlay_image_url"),
                "attention_image_url": loc.get("attention_image_url"),
                "regions": loc.get("regions", []),
                "symptoms": symptoms_list,
                "causes": causes_list,
                "recommendations": recommendations_list,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        # -------------------------------------------------------------
        # PART 4 — MODE B: PRO GLOBAL MODEL (auto_pro)
        # -------------------------------------------------------------
        elif norm_mode == "auto_pro":
            # Entitlement verification
            if not (user_entitled or dev_pro_authorized):
                elapsed_ms = round((time.perf_counter() - start_ts) * 1000.0, 2)
                return {
                    "success": False,
                    "status": "pro_access_denied",
                    "validation_state": "PRO_ACCESS_DENIED",
                    "validation": validation_dict,
                    "mode": "auto_pro",
                    "crop_id": None,
                    "crop_name_vi": None,
                    "disease_id": None,
                    "disease_name_vi": None,
                    "model_id": "Model tong 2 (Pro ViT GBIF 14,829 species)",
                    "model_name": "Model tong 2 (Pro ViT-Base GBIF)",
                    "message": "Chế độ chẩn đoán Pro yêu cầu quyền truy cập Pro hoặc tài khoản Đơn vị dịch vụ nông nghiệp.",
                    "reason": "Tài khoản hiện tại chưa được cấp quyền Pro. Vui lòng đăng nhập hoặc kích hoạt cấu hình dev.",
                    "warning": "Yêu cầu quyền truy cập Pro.",
                    "inference_time_ms": elapsed_ms,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

            pro_res = self.run_pro_crop_identification(img)
            top_species = pro_res["top_species"]
            species_score = pro_res["species_score"]
            top_predictions = pro_res["top_predictions"]
            resolved_crop = pro_res.get("resolved_priority_crop")

            # If resolved species matches a priority crop WITH a disease model
            if resolved_crop and resolved_crop["has_disease_model"]:
                disease_model_dir = resolved_crop["disease_model_dir"]
                diag_res = self.run_crop_disease_model(img, disease_model_dir, top_k=top_k)
                
                elapsed_ms = round((time.perf_counter() - start_ts) * 1000.0, 2)
                loc = diag_res.get("localization") or {}
                is_healthy = "healthy" in diag_res["disease_id"].lower()
                best_class = diag_res["disease_id"]
                
                symptom_profile = get_disease_symptom_profile(best_class)
                symptoms_list = symptom_profile.get("symptoms", ["Có dấu hiệu biến đổi sắc tố hoặc đốm bất thường trên phiến lá."])
                causes_list = symptom_profile.get("causes", ["Mầm bệnh phát triển trong điều kiện ẩm độ cao hoặc lây nhiễm qua vết thương."])
                recommendations_list = get_disease_recommendations(best_class)

                return {
                    "success": True,
                    "status": "OK",
                    "validation_state": "DIAGNOSIS_CONFIRMED",
                    "validation": validation_dict,
                    "mode": "auto_pro",
                    "crop": resolved_crop["id"],
                    "crop_id": resolved_crop["id"],
                    "crop_name": resolved_crop["name_vi"],
                    "crop_name_vi": resolved_crop["name_vi"],
                    "crop_score": species_score,
                    "species_latin": top_species,
                    "crop_candidates": [{
                        "crop_id": resolved_crop["id"],
                        "name_vi": f"{resolved_crop['name_vi']} ({top_species})",
                        "score": species_score,
                        "score_percent": round(species_score * 100, 2)
                    }],
                    "class_id": diag_res["disease_id"],
                    "prediction": diag_res["disease_name_vi"],
                    "disease_id": diag_res["disease_id"],
                    "disease_name_vi": diag_res["disease_name_vi"],
                    "disease_score": diag_res["disease_score"],
                    "confidence": diag_res["disease_score"],
                    "confidence_percent": round(diag_res["disease_score"] * 100, 2),
                    "severity": "NORMAL" if is_healthy else ("HIGH" if diag_res["disease_score"] > 0.85 else "MEDIUM"),
                    "is_healthy": is_healthy,
                    "top_predictions": diag_res["top_predictions"],
                    "model_id": f"Model tong 2 (Pro ViT) -> ConvNeXt-Small ({disease_model_dir})",
                    "model_name": f"Model tong 2 (Pro ViT GBIF) -> ConvNeXt-Small ({disease_model_dir})",
                    "model_arch": diag_res["model_arch"],
                    "inference_time_ms": elapsed_ms,
                    "localization_type": "gradcam",
                    "overlay_image_url": loc.get("overlay_image_url"),
                    "attention_image_url": loc.get("attention_image_url"),
                    "regions": loc.get("regions", []),
                    "symptoms": symptoms_list,
                    "causes": causes_list,
                    "recommendations": recommendations_list,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

            # If resolved species matches a priority crop WITHOUT a disease model (chili, durian)
            if resolved_crop and not resolved_crop["has_disease_model"]:
                elapsed_ms = round((time.perf_counter() - start_ts) * 1000.0, 2)
                return {
                    "success": True,
                    "status": "crop_identified_no_disease_model",
                    "validation_state": "CROP_IDENTIFIED_NO_DISEASE_MODEL",
                    "validation": validation_dict,
                    "mode": "auto_pro",
                    "crop_id": resolved_crop["id"],
                    "crop_name_vi": resolved_crop["name_vi"],
                    "crop_score": species_score,
                    "species_latin": top_species,
                    "disease_id": None,
                    "disease_name_vi": None,
                    "prediction": "Chưa có mô hình bệnh lý",
                    "confidence": 0.0,
                    "confidence_percent": 0.0,
                    "message": f"Mô hình Pro đã nhận diện loài {top_species} ({resolved_crop['name_vi']}), nhưng mô hình chẩn đoán bệnh cho cây này chưa sẵn sàng.",
                    "reason": f"Cây {resolved_crop['name_vi']} hiện chưa có mô hình chẩn đoán bệnh lý chuyên biệt.",
                    "model_id": "Model tong 2 (Pro ViT GBIF 14,829 species)",
                    "model_name": "Model tong 2 (Pro ViT-Base GBIF)",
                    "inference_time_ms": elapsed_ms,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

            # Out of priority crops botanical species
            elapsed_ms = round((time.perf_counter() - start_ts) * 1000.0, 2)
            return {
                "success": True,
                "status": "unsupported_crop",
                "validation_state": "UNSUPPORTED_CROP",
                "validation": validation_dict,
                "mode": "auto_pro",
                "crop_id": None,
                "crop_name_vi": f"Loài thực vật: {top_species}",
                "species_latin": top_species,
                "crop_score": species_score,
                "disease_id": None,
                "disease_name_vi": None,
                "prediction": f"Nhận diện thực vật Pro: {top_species}",
                "confidence": species_score,
                "confidence_percent": round(species_score * 100, 2),
                "message": f"Mô hình Pro nhận diện loài: {top_species} ({species_score*100:.1f}%). Cây này nằm ngoài danh mục 7 loại cây ưu tiên chẩn đoán bệnh.",
                "reason": f"Mô hình Pro (Model tong 2) nhận diện loài thực vật là '{top_species}', chưa có mô hình bệnh lý cục bộ.",
                "model_id": "Model tong 2 (Pro ViT GBIF 14,829 species)",
                "model_name": "Model tong 2 (Pro ViT-Base GBIF)",
                "inference_time_ms": elapsed_ms,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        # -------------------------------------------------------------
        # PART 5 — MODE C: MANUAL CROP MODE (manual)
        # -------------------------------------------------------------
        else:
            p_meta = resolve_priority_crop(crop_id)
            if not p_meta:
                elapsed_ms = round((time.perf_counter() - start_ts) * 1000.0, 2)
                return {
                    "success": False,
                    "status": "unsupported_crop",
                    "validation_state": "UNSUPPORTED_CROP",
                    "validation": validation_dict,
                    "mode": "manual",
                    "crop_id": crop_id,
                    "crop_name_vi": None,
                    "disease_id": None,
                    "disease_name_vi": None,
                    "model_id": None,
                    "model_name": None,
                    "message": f"Cây trồng '{crop_id}' không thuộc phạm vi 7 loại cây ưu tiên.",
                    "reason": "Vui lòng chọn một trong 7 loại cây ưu tiên: Cà phê, Hồ tiêu, Lúa, Sầu riêng, Cà chua, Ớt, Ngô.",
                    "inference_time_ms": elapsed_ms,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
            # Check if selected crop has compatible disease model
            if not p_meta["has_disease_model"]:
                # Durian, Chili
                elapsed_ms = round((time.perf_counter() - start_ts) * 1000.0, 2)
                return {
                    "success": True,
                    "status": "disease_model_unavailable",
                    "validation_state": "DISEASE_MODEL_UNAVAILABLE",
                    "validation": validation_dict,
                    "mode": "manual",
                    "crop": p_meta["id"],
                    "crop_id": p_meta["id"],
                    "crop_name": p_meta["name_vi"],
                    "crop_name_vi": p_meta["name_vi"],
                    "crop_score": None,
                    "disease_id": None,
                    "disease_name_vi": None,
                    "prediction": "Mô hình chẩn đoán bệnh cho cây này chưa sẵn sàng.",
                    "predicted_disease": "Mô hình chẩn đoán bệnh cho cây này chưa sẵn sàng.",
                    "confidence": 0.0,
                    "confidence_percent": 0.0,
                    "message": "Mô hình chẩn đoán bệnh cho cây này chưa sẵn sàng.",
                    "reason": f"Hiện tại chưa có mô hình chẩn đoán bệnh lý tương thích cho cây {p_meta['name_vi']}.",
                    "model_id": None,
                    "model_name": "Chưa có mô hình bệnh",
                    "inference_time_ms": elapsed_ms,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
            # Crop has verified disease model (Coffee, Black_Pepper, Rice, Tomato, Maize)
            disease_model_dir = p_meta["disease_model_dir"]
            diag_res = self.run_crop_disease_model(img, disease_model_dir, top_k=top_k)
            
            elapsed_ms = round((time.perf_counter() - start_ts) * 1000.0, 2)
            loc = diag_res.get("localization") or {}
            is_healthy = "healthy" in diag_res["disease_id"].lower()
            best_class = diag_res["disease_id"]
            
            symptom_profile = get_disease_symptom_profile(best_class)
            symptoms_list = symptom_profile.get("symptoms", ["Có dấu hiệu biến đổi sắc tố hoặc đốm bất thường trên phiến lá."])
            causes_list = symptom_profile.get("causes", ["Mầm bệnh phát triển trong điều kiện ẩm độ cao hoặc lây nhiễm qua vết thương."])
            recommendations_list = get_disease_recommendations(best_class)
            
            return {
                "success": True,
                "status": "OK",
                "validation_state": "DIAGNOSIS_CONFIRMED",
                "validation": validation_dict,
                "mode": "manual",
                "crop": p_meta["id"],
                "crop_id": p_meta["id"],
                "crop_name": p_meta["name_vi"],
                "crop_name_vi": p_meta["name_vi"],
                "crop_score": None,
                "class_id": diag_res["disease_id"],
                "prediction": diag_res["disease_name_vi"],
                "disease_id": diag_res["disease_id"],
                "disease_name_vi": diag_res["disease_name_vi"],
                "disease_score": diag_res["disease_score"],
                "confidence": diag_res["disease_score"],
                "confidence_percent": round(diag_res["disease_score"] * 100, 2),
                "severity": "NORMAL" if is_healthy else ("HIGH" if diag_res["disease_score"] > 0.85 else "MEDIUM"),
                "is_healthy": is_healthy,
                "top_predictions": diag_res["top_predictions"],
                "model_id": f"ConvNeXt-Small ({disease_model_dir})",
                "model_name": f"ConvNeXt-Small ({disease_model_dir})",
                "model_arch": diag_res["model_arch"],
                "inference_time_ms": elapsed_ms,
                "localization_type": "gradcam",
                "overlay_image_url": loc.get("overlay_image_url"),
                "attention_image_url": loc.get("attention_image_url"),
                "regions": loc.get("regions", []),
                "symptoms": symptoms_list,
                "causes": causes_list,
                "recommendations": recommendations_list,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }


    def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "brand": "GARI",
            "app_name": "Gari AI Lab",
            "device": str(self.device),
            "cuda_available": torch.cuda.is_available(),
            "models_total": len(self.registry),
            "models_cached": list(self.cache.keys()),
            "cached_count": len(self.cache),
            "max_cached": self.max_cached,
        }


# Singleton engine instance
engine = GariInferenceEngine()


# -------------------------------------------------------------
# Optional FastAPI server for standalone or proxied execution
# -------------------------------------------------------------
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Gari AI Lab Inference Engine",
    description="Real local ConvNeXt crop disease inference microservice",
    version="2.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
@app.get("/health")
async def get_health():
    return engine.health()


@app.get("/api/models")
async def get_models():
    models = engine.list_models()
    return {
        "success": True,
        "total": len(models),
        "device": str(engine.device),
        "cuda_available": torch.cuda.is_available(),
        "models": models,
    }


@app.get("/api/models/{crop_id}")
async def get_model(crop_id: str):
    entry = engine.get_model_entry(crop_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Model for crop '{crop_id}' not found")
    data = entry.to_dict(include_classes=True)
    data["is_loaded"] = entry.crop_id in engine.cache
    data["device"] = str(engine.device)
    return {"success": True, "model": data}


@app.post("/api/crop/detect")
@app.post("/api/detect-crop")
async def detect_crop_endpoint(image: UploadFile = File(...)):
    """PHASE 5 — Standalone Crop Validation Gate Endpoint."""
    try:
        content = await image.read()
        pil_img = Image.open(io.BytesIO(content))
        gate_res = engine.evaluate_crop_validation_gate(pil_img)
        return JSONResponse(gate_res)
    except Exception as exc:
        logger.exception("Crop detection failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/predict")
async def predict_endpoint(
    image: UploadFile = File(...),
    crop: Optional[str] = Form(None)
):
    try:
        content = await image.read()
        result = engine.predict(content, crop_id=crop)
        return JSONResponse(result)
    except Exception as exc:
        logger.exception("Prediction failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766, help="Port to listen on")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface")
    args = parser.parse_args()

    import uvicorn
    logger.info("Starting Gari Inference Service on http://%s:%d", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
