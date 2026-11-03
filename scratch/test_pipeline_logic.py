import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import torch
from PIL import Image, ImageFilter
from safetensors.torch import load_file
import timm

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

MODELS_DIR = Path("D:/leaf-diseases-detector-main/models")

# Crop alias mapping to guarantee exact match to folder names in models/
CROP_FOLDER_MAPPING = {
    "castard_apple": "Custard_apple",
    "custard_apple": "Custard_apple",
    "pomegranate": "pomrgranet",
    "pomrgranet": "pomrgranet",
    "okra": "okra",
    "black_pepper": "Black_Pepper",
    "bitter_gourd": "Bitter_gourd",
    "bottle_gourd": "Bottle_gourd",
    "ridge_gourd": "Ridge_gourd",
    "snake_gourd": "Snake_gourd",
}

# Crops in detector 36 that do NOT have a disease model in models/
UNSUPPORTED_DISEASE_CROPS = {
    "Pepper": "Ớt (Pepper) - Hiện chưa có mô hình bệnh chuyên biệt trong kho mô hình",
    "Raspberry": "Mâm xôi (Raspberry) - Hiện chưa có mô hình bệnh chuyên biệt",
    "Sorghum": "Lúa miến (Sorghum) - Hiện chưa có mô hình bệnh chuyên biệt",
    "Squash": "Bí ngô / Bí đỏ (Squash) - Hiện chưa có mô hình bệnh chuyên biệt",
}

# Overlapping crops in both detectors where original detector has higher precision (99.8%)
ORIGINAL_PREFERRED_CROPS = {"Apple", "Mango", "Cashew", "Cherry", "Strawberry", "Rose"}

class CropValidationGate:
    def __init__(self, net_orig, cfg_orig, net_new, cfg_new):
        self.net_orig = net_orig
        self.cfg_orig = cfg_orig
        self.net_new = net_new
        self.cfg_new = cfg_new

    def validate_image_quality(self, img: Image.Image) -> Tuple[bool, str]:
        """Check image dimensions, color diversity, and sharpness."""
        if img.width < 64 or img.height < 64:
            return False, f"Kích thước ảnh quá nhỏ ({img.width}x{img.height}). Cần tối thiểu 64x64 pixel."
        
        arr_rgb = np.asarray(img.convert("RGB"), dtype=np.float32)
        color_std = float(arr_rgb.std())
        if color_std < 5.0:
            return False, "Hình ảnh đơn sắc hoặc không có chi tiết bề mặt lá cây."

        gray = np.asarray(img.convert("L"), dtype=np.float32)
        lap = gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:] - 4 * gray[1:-1, 1:-1]
        lap_var = float(lap.var())

        if lap_var < 15.0:
            return False, f"Hình ảnh quá mờ (độ sắc nét LapVar = {lap_var:.1f} < 15.0). Vui lòng chụp rõ nét hơn."
        if lap_var > 35000.0:
            return False, f"Hình ảnh bị nhiễu hạt kỹ thuật số quá mức (LapVar = {lap_var:.1f})."

        return True, "OK"

    def _infer_detector(self, net, cfg, img: Image.Image) -> List[Tuple[str, float]]:
        img_resized = img.resize((224, 224), Image.BILINEAR)
        mean = np.array(cfg["mean"], dtype=np.float32)
        std = np.array(cfg["std"], dtype=np.float32)
        x = (np.asarray(img_resized, np.float32) / 255.0 - mean) / std
        tensor = torch.from_numpy(x.transpose(2, 0, 1)).float().unsqueeze(0)
        with torch.no_grad():
            logits = net(tensor)
            probs = torch.softmax(logits, dim=1)[0]
        top_indices = torch.argsort(probs, descending=True)
        return [(cfg["classes"][i], float(probs[i])) for i in top_indices]

    def evaluate_crop(self, img: Image.Image) -> Dict[str, Any]:
        valid, msg = self.validate_image_quality(img)
        if not valid:
            return {
                "state": "REJECTED_LOW_QUALITY",
                "is_leaf_valid": False,
                "reason": msg,
                "selected_crop": None,
                "candidates": []
            }

        preds_orig = self._infer_detector(self.net_orig, self.cfg_orig, img)
        preds_new = self._infer_detector(self.net_new, self.cfg_new, img)

        top_orig_crop, top_orig_conf = preds_orig[0]
        top_new_crop, top_new_conf = preds_new[0]

        # Combine candidates for transparency
        candidates_map: Dict[str, float] = {}
        for c, p in preds_new[:5]:
            candidates_map[c] = max(candidates_map.get(c, 0.0), p)
        for c, p in preds_orig[:3]:
            # Weight original detector slightly higher for its 16 known crops
            candidates_map[c] = max(candidates_map.get(c, 0.0), p)

        sorted_candidates = sorted(
            [{"crop": c, "confidence": round(p, 4), "percent": round(p * 100, 2)}
             for c, p in candidates_map.items()],
            key=lambda x: x["confidence"],
            reverse=True
        )[:5]

        # Decision flow as designed by the model author:
        # 1. If detectors/new names a crop outside (Apple, Mango, Cashew, Cherry, Strawberry, Rose) with at least 80% confidence:
        selected_crop = None
        decision_confidence = 0.0

        if top_new_crop not in ORIGINAL_PREFERRED_CROPS and top_new_conf >= 0.60:
            selected_crop = top_new_crop
            decision_confidence = top_new_conf
        elif top_orig_conf >= 0.60:
            selected_crop = top_orig_crop
            decision_confidence = top_orig_conf
        elif top_new_conf >= 0.60:
            selected_crop = top_new_crop
            decision_confidence = top_new_conf

        # Check for ambiguity: if top2 difference is small (< 15% and both > 20%)
        is_ambiguous = False
        if len(sorted_candidates) >= 2:
            c1 = sorted_candidates[0]["confidence"]
            c2 = sorted_candidates[1]["confidence"]
            if (c1 - c2 < 0.15) and c1 < 0.75:
                is_ambiguous = True

        # Check if selected crop is supported for disease classification
        if selected_crop in UNSUPPORTED_DISEASE_CROPS:
            return {
                "state": "UNSUPPORTED_CROP",
                "is_leaf_valid": True,
                "selected_crop": selected_crop,
                "confidence": decision_confidence,
                "reason": UNSUPPORTED_DISEASE_CROPS[selected_crop],
                "candidates": sorted_candidates
            }

        if is_ambiguous:
            return {
                "state": "MULTIPLE_CANDIDATES",
                "is_leaf_valid": True,
                "selected_crop": selected_crop,
                "confidence": decision_confidence,
                "reason": f"Phát hiện nhiều khả năng ({sorted_candidates[0]['crop']} {sorted_candidates[0]['percent']}%, {sorted_candidates[1]['crop']} {sorted_candidates[1]['percent']}%). Cần người dùng xác nhận.",
                "candidates": sorted_candidates
            }

        if not selected_crop or decision_confidence < 0.60:
            return {
                "state": "CROP_UNCERTAIN",
                "is_leaf_valid": True,
                "selected_crop": None,
                "confidence": decision_confidence,
                "reason": "Chưa đủ cơ sở để xác định chính xác loại cây trồng (Điểm tin cậy < 60%).",
                "candidates": sorted_candidates
            }

        return {
            "state": "CROP_CONFIDENT",
            "is_leaf_valid": True,
            "selected_crop": selected_crop,
            "confidence": decision_confidence,
            "reason": "Cây trồng được xác định tin cậy.",
            "candidates": sorted_candidates
        }

print("CropValidationGate logic created successfully.")
