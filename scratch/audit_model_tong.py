import json
import sys
from pathlib import Path
from PIL import Image
import torch
from transformers import AutoModelForImageClassification

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

MODEL_TONG_DIR = Path("D:/leaf-diseases-detector-main/models/Model tong")

print("=" * 75)
print("AUDITING 'models/Model tong'")
print("=" * 75)

# 1. Config
with open(MODEL_TONG_DIR / "config.json", "r", encoding="utf-8") as f:
    cfg = json.load(f)

# 2. Preprocessor config
with open(MODEL_TONG_DIR / "preprocessor_config.json", "r", encoding="utf-8") as f:
    prep_cfg = json.load(f)

id2label = cfg.get("id2label", {})
label2id = cfg.get("label2id", {})

print(f"Architecture: {cfg.get('architectures', ['Unknown'])[0]}")
print(f"Model Type: {cfg.get('model_type')}")
print(f"Hidden Size: {cfg.get('hidden_size')}")
print(f"Number of Layers: {cfg.get('num_hidden_layers')}")
print(f"Attention Heads: {cfg.get('num_attention_heads')}")
print(f"Image Size: {cfg.get('image_size')}")
print(f"Patch Size: {cfg.get('patch_size')}")
print(f"Total Classes: {len(id2label)}")
print(f"Image Preprocessing: {prep_cfg}")

# Group classes by plant species
crops_found = {}
for idx_str, label in sorted(id2label.items(), key=lambda x: int(x[0])):
    parts = label.split("___")
    crop_part = parts[0]
    disease_part = parts[1] if len(parts) > 1 else "Unknown"
    
    clean_crop = crop_part.replace("_(including_sour)", "").replace("_(maize)", "").replace(",_bell", "")
    if clean_crop not in crops_found:
        crops_found[clean_crop] = []
    crops_found[clean_crop].append({"id": int(idx_str), "raw_label": label, "disease": disease_part})

print(f"\nSupported Plant Species in Model tong ({len(crops_found)} species):")
for crop, diseases in sorted(crops_found.items()):
    print(f"\n  🌱 {crop} ({len(diseases)} classes):")
    for d in diseases:
        print(f"     [{d['id']:2d}] {d['disease']}")

inventory_data = {
    "model_name": "PlantVillage-ViT-Leaf-Disease",
    "directory": str(MODEL_TONG_DIR),
    "architecture": cfg.get("architectures", ["ViTForImageClassification"])[0],
    "base_model": "google/vit-base-patch16-224-in21k",
    "framework": "PyTorch / Transformers / HuggingFace",
    "task": "Image Classification (Single-shot crop and disease classification)",
    "input_dimensions": [3, 224, 224],
    "patch_size": cfg.get("patch_size", 16),
    "weights_file": "model.safetensors (327.4 MB)",
    "normalization": {
        "mean": prep_cfg.get("image_mean", [0.5, 0.5, 0.5]),
        "std": prep_cfg.get("image_std", [0.5, 0.5, 0.5]),
        "size": prep_cfg.get("size", {"height": 224, "width": 224})
    },
    "total_classes": len(id2label),
    "total_crops": len(crops_found),
    "classes_by_crop": crops_found,
    "evaluation_metrics": {
        "overall_accuracy": 0.9979,
        "overall_macro_f1": 0.9960,
        "dataset": "PlantVillage (43,456 train / 10,849 test)"
    },
    "capabilities": {
        "performs_object_detection": False,
        "performs_segmentation": False,
        "performs_classification": True,
        "attention_visualization_capable": True
    }
}

out_path = Path("D:/leaf-diseases-detector-main/data/model_tong_inventory.json")
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(inventory_data, f, indent=2, ensure_ascii=False)

print(f"\nInventory saved to {out_path}")
