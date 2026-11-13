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

low_quality_samples = []

for p in leaf_files:
    try:
        img = Image.open(p)
        res = gari_inference_engine.validate_leaf_gate(img)
        if res["status"] == "IMAGE_QUALITY_LOW":
            low_quality_samples.append({
                "file": p.name,
                "score": res["score"],
                "metrics": res["metrics"],
                "message": res["message_vi"]
            })
    except Exception as e:
        pass

print(f"Total IMAGE_QUALITY_LOW: {len(low_quality_samples)}")
for s in low_quality_samples[:15]:
    m = s['metrics']
    print(f"  {s['file']}: lum={m['mean_lum']}, lap={m['lap_var']}, std={m['color_std']}, score={s['score']}")
