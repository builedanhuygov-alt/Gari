import sys
from pathlib import Path
from PIL import Image
import random

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import gari_inference_engine

pv_dir = ROOT_DIR / "data" / "organized" / "PlantVillage"
folders = [f for f in pv_dir.iterdir() if f.is_dir()]

total_tested = 0
results_by_folder = {}
failures = []

for folder in sorted(folders):
    images = list(folder.glob("*.JPG")) + list(folder.glob("*.jpg"))
    sample = images[:10]  # Take 10 per class
    folder_stats = {"LEAF_VALID": 0, "NOT_A_LEAF": 0, "UNCERTAIN": 0, "IMAGE_QUALITY_LOW": 0}
    
    for img_path in sample:
        total_tested += 1
        try:
            img = Image.open(img_path)
            res = gari_inference_engine.validate_leaf_gate(img)
            st = res.get("status")
            folder_stats[st] = folder_stats.get(st, 0) + 1
            if st != "LEAF_VALID":
                failures.append({
                    "path": str(img_path.relative_to(ROOT_DIR)),
                    "status": st,
                    "score": res.get("score"),
                    "metrics": res.get("metrics")
                })
        except Exception as e:
            print(f"Error reading {img_path}: {e}")
            
    results_by_folder[folder.name] = folder_stats

print(f"\nTested {total_tested} PlantVillage images across {len(folders)} classes:")
for f_name, stats in results_by_folder.items():
    print(f"  {f_name:40s}: VALID={stats.get('LEAF_VALID', 0)}, NOT_A_LEAF={stats.get('NOT_A_LEAF', 0)}, UNCERTAIN={stats.get('UNCERTAIN', 0)}, LOW_QUALITY={stats.get('IMAGE_QUALITY_LOW', 0)}")

print(f"\nTotal Failures (False Rejections): {len(failures)} / {total_tested}")
for fail in failures[:15]:
    print(f"  FAILED: {fail['path']} -> {fail['status']}")
    print(f"    Metrics: {fail['metrics']}")
