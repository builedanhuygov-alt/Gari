"""
GARI AI LAB — Authoritative Crop & Model Capability Registry
Single source of truth reconciling:
- 48 crop translations
- 46 crop detector classes (detectors/original + detectors/new)
- 44 disease models (42 ConvNeXt-Small + 2 PlantVillage-ViT: Pepper & Squash)
- Explicit capability fields per crop
"""

import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent
MODELS_DIR = ROOT_DIR / "models"
LOCALIZATION_DIR = ROOT_DIR / "localization"

def load_json(path: Path) -> Dict[str, Any]:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

CROPS_VI = load_json(LOCALIZATION_DIR / "crop_vi.json")
DISEASES_VI = load_json(LOCALIZATION_DIR / "disease_vi.json")

def build_authoritative_capability_registry() -> Dict[str, Any]:
    # 1. Load Detector Classes
    det_orig_cfg = load_json(MODELS_DIR / "detectors" / "original" / "config.json")
    det_new_cfg = load_json(MODELS_DIR / "detectors" / "new" / "config.json")
    
    orig_classes = set(det_orig_cfg.get("classes", []))
    new_classes = set(det_new_cfg.get("classes", []))
    all_detectable = orig_classes | new_classes

    # Canonical aliases mapping
    canonical_alias = {
        "corn": "Maize",
        "Corn": "Maize",
        "castard_apple": "Custard_apple",
        "Castard_apple": "Custard_apple",
        "custard_apple": "Custard_apple",
        "pomrgranet": "pomrgranet",
        "pomegranate": "pomrgranet",
        "Pomegranate": "pomrgranet",
        "okra": "okra",
        "Okra": "okra",
        "eggplant": "Brinjal",
        "Eggplant": "Brinjal",
        "black_pepper": "Black_Pepper",
        "bitter_gourd": "Bitter_gourd",
        "bottle_gourd": "Bottle_gourd",
        "ridge_gourd": "Ridge_gourd",
        "snake_gourd": "Snake_gourd"
    }

    # 2. Discover Disease Models
    disease_models = {}
    if MODELS_DIR.exists():
        for d in sorted(MODELS_DIR.iterdir()):
            if d.is_dir() and d.name not in ["detectors", "Crop", ".cache", "kaggle_simple", "kaggle_trained"]:
                cfg_path = d / "config.json"
                weights_path = d / "model.safetensors"
                if cfg_path.exists() and weights_path.exists():
                    cfg = load_json(cfg_path)
                    classes = cfg.get("classes", [])
                    arch = cfg.get("arch", "convnext_small")
                    disease_models[d.name] = {
                        "arch": arch,
                        "classes": classes,
                        "weight_size_mb": round(weights_path.stat().st_size / (1024 * 1024), 2)
                    }

    # 3. Model tong special handling (provides Pepper and Squash disease models)
    model_tong_cfg = load_json(MODELS_DIR / "Model tong" / "config.json")
    id2label = model_tong_cfg.get("id2label", {})
    all_tong_classes = list(id2label.values())

    pepper_classes = [c for c in all_tong_classes if "Pepper" in c]
    squash_classes = [c for c in all_tong_classes if "Squash" in c]

    # 4. Synthesize all 48 cataloged crops
    registry = {}
    all_crop_keys = sorted(list(CROPS_VI.keys()))

    for cid in all_crop_keys:
        target_model_key = canonical_alias.get(cid, cid)
        meta_vi = CROPS_VI.get(cid, {})
        
        # Determine detection capability
        in_orig = cid in orig_classes or target_model_key in orig_classes or cid.lower() in [c.lower() for c in orig_classes]
        in_new = cid in new_classes or target_model_key in new_classes or cid.lower() in [c.lower() for c in new_classes]
        can_identify = in_orig or in_new
        
        det_sources = []
        if in_orig:
            det_sources.append("detectors/original (16 crops)")
        if in_new:
            det_sources.append("detectors/new (36 crops)")

        # Determine disease diagnosis capability
        can_diagnose = False
        disease_models_available = []
        supported_disease_labels = []

        if target_model_key in disease_models:
            can_diagnose = True
            m_info = disease_models[target_model_key]
            disease_models_available.append(f"{m_info['arch']} ({target_model_key})")
            supported_disease_labels = m_info["classes"]
        elif cid == "Pepper" or target_model_key == "Pepper":
            can_diagnose = True
            disease_models_available.append("vit_plantvillage (Model tong)")
            supported_disease_labels = pepper_classes
        elif cid == "Squash" or target_model_key == "Squash":
            can_diagnose = True
            disease_models_available.append("vit_plantvillage (Model tong)")
            supported_disease_labels = squash_classes
        
        # Build structured disease labels with Vietnamese translation
        labeled_diseases = []
        for d_lbl in supported_disease_labels:
            vi_name = DISEASES_VI.get(d_lbl)
            if not vi_name:
                sub = d_lbl.split("___")[-1] if "___" in d_lbl else d_lbl
                vi_name = DISEASES_VI.get(sub, f"Bệnh {sub.replace('_', ' ').strip()}")
            labeled_diseases.append({
                "label_id": d_lbl,
                "name_vi": vi_name
            })

        registry[cid] = {
            "id": cid,
            "crop_id": cid,
            "name_vi": meta_vi.get("name_vi", cid),
            "name_en": cid,
            "common_name": meta_vi.get("common_name", meta_vi.get("name_vi", cid)),
            "scientific_name": meta_vi.get("scientific_name", ""),
            "family": meta_vi.get("family", ""),
            "can_identify_crop": can_identify,
            "can_diagnose_disease": can_diagnose,
            "has_disease_model": can_diagnose,
            "detector_sources": det_sources,
            "disease_models_available": disease_models_available,
            "disease_classes_count": len(supported_disease_labels),
            "supported_disease_labels": supported_disease_labels,
            "supported_diseases_vi": labeled_diseases,
            "status_notes": "Sẵn sàng chẩn đoán cục bộ" if can_diagnose else ("Chỉ nhận diện loại cây, chưa có mô hình bệnh" if can_identify else "Chưa có mô hình nhận diện hoặc chẩn đoán")
        }

    return registry

CAPABILITY_REGISTRY = build_authoritative_capability_registry()

def get_crop_capability(crop_id: str) -> Optional[Dict[str, Any]]:
    return CAPABILITY_REGISTRY.get(crop_id)

def get_capabilities_summary() -> Dict[str, Any]:
    crops_list = list(CAPABILITY_REGISTRY.values())
    total_crops = len(crops_list)
    identifiable_crops = [c for c in crops_list if c["can_identify_crop"]]
    diagnosable_crops = [c for c in crops_list if c["can_diagnose_disease"]]
    total_disease_classes = sum(c["disease_classes_count"] for c in diagnosable_crops)

    return {
        "success": True,
        "total_crops": total_crops,
        "identifiable_count": len(identifiable_crops),
        "diagnosable_count": len(diagnosable_crops),
        "total_disease_classes": total_disease_classes,
        "reconciliation": {
            "crop_translations_count": 48,
            "crop_detector_classes": len(identifiable_crops),
            "active_disease_models": len(diagnosable_crops),
            "crops_without_disease_models": [c["crop_id"] for c in crops_list if not c["can_diagnose_disease"]]
        },
        "crops": sorted(crops_list, key=lambda x: x["name_vi"])
    }

if __name__ == "__main__":
    summary = get_capabilities_summary()
    print("=" * 70)
    print("GARI AUTHORITATIVE CAPABILITY REGISTRY SUMMARY")
    print("=" * 70)
    print(f"Total cataloged crops: {summary['total_crops']}")
    print(f"Can identify crop:     {summary['identifiable_count']}/48")
    print(f"Can diagnose disease:  {summary['diagnosable_count']}/48")
    print(f"Total disease classes: {summary['total_disease_classes']}")
    print(f"Crops without disease model: {summary['reconciliation']['crops_without_disease_models']}")
