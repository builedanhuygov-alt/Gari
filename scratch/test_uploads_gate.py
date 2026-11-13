import sys
from pathlib import Path
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import gari_inference_engine

uploads_dir = ROOT_DIR / "database" / "uploads"
leaf_files = list(uploads_dir.glob("leaf_*.jpg"))
print(f"Total uploaded leaf files found: {len(leaf_files)}")

stats = {"LEAF_VALID": 0, "NOT_A_LEAF": 0, "UNCERTAIN": 0, "IMAGE_QUALITY_LOW": 0}
not_a_leaf_samples = []

for p in leaf_files:
    try:
        img = Image.open(p)
        res = gari_inference_engine.validate_leaf_gate(img)
        st = res["status"]
        stats[st] = stats.get(st, 0) + 1
        if st == "NOT_A_LEAF":
            not_a_leaf_samples.append({
                "file": p.name,
                "score": res["score"],
                "metrics": res["metrics"],
                "message": res["message_vi"]
            })
    except Exception as e:
        print(f"Error {p.name}: {e}")

print("Uploads Validation Distribution:")
for k, v in stats.items():
    print(f"  {k}: {v} ({v/len(leaf_files)*100:.1f}%)")

print(f"\nSamples rejected as NOT_A_LEAF ({len(not_a_leaf_samples)}):")
for s in not_a_leaf_samples[:10]:
    print(f"  {s['file']}: score={s['score']}")
    m = s['metrics']
    print(f"    green={m['green_ratio']}, yellow={m['yellow_ratio']}, brown={m['brown_ratio']}, botanical={m['botanical_ratio']}, blue={m['blue_ratio']}, skin={m['skin_ratio']}, exg={m['mean_exg']}, lap={m['lap_var']}")
