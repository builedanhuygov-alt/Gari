import os
import json
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

models_dir = r"D:\leaf-diseases-detector-main\models"
subdirs = [d for d in os.listdir(models_dir) if os.path.isdir(os.path.join(models_dir, d))]
print(f"Total subdirectories in models: {len(subdirs)}")

valid_models = {}
for d in subdirs:
    cfg_path = os.path.join(models_dir, d, "config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        classes = cfg.get("classes", [])
        if not classes and "id2label" in cfg:
            classes = list(cfg["id2label"].values())
        arch = cfg.get("arch", cfg.get("architectures", ["unknown"])[0])
        valid_models[d] = {
            "arch": arch,
            "num_classes": len(classes),
            "classes": classes
        }

# Also check detectors
det_dir = os.path.join(models_dir, "detectors")
if os.path.exists(det_dir):
    for d in os.listdir(det_dir):
        cfg_path = os.path.join(det_dir, d, "config.json")
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            classes = cfg.get("classes", [])
            valid_models[f"detectors/{d}"] = {
                "arch": cfg.get("arch", "unknown"),
                "num_classes": len(classes),
                "classes": classes
            }

print(f"Valid models discovered: {len(valid_models)}")
for k, v in sorted(valid_models.items()):
    print(f"  {k:22s}: {v['arch']:25s} ({v['num_classes']:2d} classes)")
