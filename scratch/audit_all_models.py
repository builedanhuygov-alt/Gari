import json
import os
import sys
from pathlib import Path
from safetensors import safe_open

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

MODELS_DIR = Path("D:/leaf-diseases-detector-main/models")

results = []

for cfg_path in sorted(MODELS_DIR.rglob("config.json")):
    folder = cfg_path.parent
    rel = str(folder.relative_to(MODELS_DIR)).replace("\\", "/")
    
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
        
    weight_path = folder / "model.safetensors"
    has_weights = weight_path.exists()
    
    classes = cfg.get("classes", [])
    labels = cfg.get("labels", classes)
    arch = cfg.get("arch", cfg.get("model_type", "unknown"))
    mean = cfg.get("mean")
    std = cfg.get("std")
    
    head_weight_shape = None
    if has_weights:
        try:
            with safe_open(str(weight_path), framework="pt", device="cpu") as f:
                # Find classifier head weight
                for key in ["head.fc.weight", "classifier.weight", "head.weight"]:
                    if key in f.keys():
                        head_weight_shape = list(f.get_tensor(key).shape)
                        break
                if not head_weight_shape:
                    # Look for any weight matching class count
                    for k in f.keys():
                        tensor = f.get_tensor(k)
                        if len(tensor.shape) == 2 and tensor.shape[0] == len(classes):
                            head_weight_shape = list(tensor.shape)
                            break
        except Exception as e:
            head_weight_shape = f"ERROR: {e}"
            
    match_classes = None
    if isinstance(head_weight_shape, list):
        match_classes = (head_weight_shape[0] == len(classes))
        
    results.append({
        "folder": rel,
        "arch": arch,
        "classes_count": len(classes),
        "labels_count": len(labels),
        "head_shape": head_weight_shape,
        "dimension_match": match_classes,
        "classes": classes,
        "labels": labels,
        "mean": mean,
        "std": std
    })

print(f"Total model directories audited: {len(results)}")
print("=" * 80)
mismatches = [r for r in results if r["dimension_match"] is False]
if mismatches:
    print(f"WARNING: {len(mismatches)} models have head dimension mismatches!")
    for m in mismatches:
        print(f"  Folder: {m['folder']}, Classes: {m['classes_count']}, Head: {m['head_shape']}")
else:
    print("ALL models have matching head dimensions!")

# Check classes vs labels length
label_mismatches = [r for r in results if r["classes_count"] != r["labels_count"]]
if label_mismatches:
    print(f"WARNING: {len(label_mismatches)} models have label count mismatches!")
    for m in label_mismatches:
        print(f"  Folder: {m['folder']}, Classes: {m['classes_count']}, Labels: {m['labels_count']}")
else:
    print("ALL models have matching classes and labels count!")

# Print table of models
print("\nAudited Models Summary:")
print(f"{'Folder / Crop ID':30s} | {'Arch':15s} | {'Classes':8s} | {'Head Shape':18s} | {'Match?':7s}")
print("-" * 86)
for r in results:
    match_str = "YES" if r["dimension_match"] else ("NO" if r["dimension_match"] is False else "N/A")
    print(f"{r['folder']:30s} | {str(r['arch']):15s} | {r['classes_count']:8d} | {str(r['head_shape']):18s} | {match_str:7s}")
