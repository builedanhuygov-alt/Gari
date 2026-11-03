import os
import sys
import json
import time
from pathlib import Path

def audit_models():
    # Prefer MODEL_PATH env var, fallback to D:\Gari\models\multicrop-disease-models, then models/
    candidate_paths = [
        os.getenv("MODEL_PATH"),
        r"D:\Gari\models\multicrop-disease-models",
        r"D:\leaf-diseases-detector-main\models",
        str(Path(__file__).resolve().parent.parent / "models")
    ]
    model_dir = None
    for p in candidate_paths:
        if p and os.path.isdir(p):
            model_dir = Path(p)
            break
            
    if not model_dir:
        print("ERROR: No valid model directory found!")
        return
        
    print(f"Auditing models from: {model_dir}")
    
    # Check imports
    try:
        import torch
        import timm
        from safetensors.torch import load_file
        has_ml = True
    except ImportError as e:
        print(f"ML libs not yet ready: {e}")
        has_ml = False

    inventory = []
    
    # Scan subdirectories
    subdirs = sorted([d for d in model_dir.iterdir() if d.is_dir()])
    
    # Also check detectors subdirectories if present
    targets = []
    for d in subdirs:
        if d.name == "detectors":
            for det_d in sorted(d.iterdir()):
                if det_d.is_dir() and (det_d / "config.json").exists():
                    targets.append(det_d)
        elif (d / "config.json").exists():
            targets.append(d)
            
    print(f"Found {len(targets)} model directories with config.json.")
    
    for d in targets:
        rel_path = d.relative_to(model_dir)
        config_path = d / "config.json"
        weights_path = d / "model.safetensors"
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            print(f"Error reading {config_path}: {e}")
            continue
            
        weight_size = weights_path.stat().st_size if weights_path.exists() else 0
        weight_size_mb = round(weight_size / (1024 * 1024), 2)
        
        crop_id = str(rel_path).replace("\\", "/")
        crop_name = d.name.replace("_", " ").title()
        
        item = {
            "crop_id": crop_id,
            "crop_name": crop_name,
            "kind": cfg.get("kind", "disease"),
            "arch": cfg.get("arch", "unknown"),
            "weight_file": weights_path.name if weights_path.exists() else None,
            "weight_size_mb": weight_size_mb,
            "weight_size_bytes": weight_size,
            "classes_count": len(cfg.get("classes", [])),
            "classes": cfg.get("classes", []),
            "labels": cfg.get("labels", cfg.get("classes", [])),
            "accuracy": cfg.get("accuracy"),
            "macro_f1": cfg.get("macro_f1"),
            "test_images": cfg.get("test_images"),
            "image_size": cfg.get("image_size", 224),
            "mean": cfg.get("mean"),
            "std": cfg.get("std"),
            "loadable": False,
            "load_error": None
        }
        
        # Test loading if ML available
        if has_ml and weights_path.exists():
            try:
                t0 = time.time()
                # Load architecture without pretrained weights
                net = timm.create_model(cfg["arch"], pretrained=False, num_classes=len(cfg["classes"]))
                # Load state dict
                state_dict = load_file(str(weights_path))
                # Ensure float32
                net.load_state_dict({k: v.float() for k, v in state_dict.items()})
                net.eval()
                # Run test tensor
                dummy = torch.zeros((1, 3, cfg.get("image_size", 224), cfg.get("image_size", 224)), dtype=torch.float32)
                with torch.no_grad():
                    out = net(dummy)
                load_time = time.time() - t0
                item["loadable"] = True
                item["test_latency_ms"] = round(load_time * 1000, 2)
                item["output_shape"] = list(out.shape)
            except Exception as e:
                item["loadable"] = False
                item["load_error"] = str(e)
                
        inventory.append(item)
        print(f"[{'OK' if item['loadable'] else ('SKIP' if not has_ml else 'ERR')}] {crop_id} ({item['classes_count']} classes, {weight_size_mb} MB) -> arch: {item['arch']}")
        
    out_file = Path("model_inventory.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2)
    print(f"\nInventory saved to {out_file.resolve()}. Total models: {len(inventory)}")

if __name__ == "__main__":
    audit_models()
