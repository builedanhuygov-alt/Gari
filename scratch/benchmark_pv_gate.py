import sys
from pathlib import Path
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import gari_inference_engine

pv_dir = ROOT_DIR / "data" / "organized" / "PlantVillage"
folders = sorted([f for f in pv_dir.iterdir() if f.is_dir()])

total = 0
rejections = []
status_counts = {"LEAF_VALID": 0, "NOT_A_LEAF": 0, "UNCERTAIN": 0, "IMAGE_QUALITY_LOW": 0}

for folder in folders:
    images = list(folder.glob("*.JPG")) + list(folder.glob("*.jpg"))
    sample = images[:30] # 30 per class
    for img_path in sample:
        total += 1
        img = Image.open(img_path)
        res = gari_inference_engine.validate_leaf_gate(img)
        st = res["status"]
        status_counts[st] += 1
        if st != "LEAF_VALID":
            rejections.append({
                "class": folder.name,
                "file": img_path.name,
                "status": st,
                "metrics": res["metrics"]
            })

print(f"Tested {total} PlantVillage disease/healthy images:")
for k, v in status_counts.items():
    print(f"  {k}: {v} ({v/total*100:.2f}%)")

print(f"\nTotal False Rejections on real leaf images: {len(rejections)} ({len(rejections)/total*100:.2f}%)")
print(f"False 'NOT_A_LEAF' Rejections: {status_counts['NOT_A_LEAF']} ({status_counts['NOT_A_LEAF']/total*100:.2f}%)")
print(f"False 'UNCERTAIN' Rejections: {status_counts['UNCERTAIN']} ({status_counts['UNCERTAIN']/total*100:.2f}%)")

print("\nBreakdown of NOT_A_LEAF cases:")
for r in [x for x in rejections if x['status'] == 'NOT_A_LEAF']:
    m = r['metrics']
    print(f"  [{r['class']}] {r['file']}")
    print(f"     green={m['green_ratio']}, yellow={m['yellow_ratio']}, brown={m['brown_ratio']}, botanical={m['botanical_ratio']}, blue={m['blue_ratio']}, skin={m['skin_ratio']}, exg={m['mean_exg']}, lap={m['lap_var']}")
