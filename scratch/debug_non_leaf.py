import sys
from pathlib import Path
from PIL import Image
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Let's inspect 7_animal.jpg vs a brown leaf
p_animal = ROOT_DIR / "data/test_samples_17/7_animal.jpg"
p_face = ROOT_DIR / "data/test_samples_17/6_human_face.jpg"
p_obj = ROOT_DIR / "data/test_samples_17/8_general_object.jpg"
p_nonleaf = ROOT_DIR / "data/test_samples_17/5_non_leaf.jpg"

for p in [p_animal, p_face, p_obj, p_nonleaf]:
    if not p.exists(): continue
    img = Image.open(p).convert("RGB")
    arr = np.asarray(img, dtype=np.float32)
    R, G, B = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    max_c = np.maximum(np.maximum(R, G), B)
    min_c = np.minimum(np.minimum(R, G), B)
    delta = max_c - min_c + 1e-6
    H = np.zeros_like(max_c)
    mask_r = (max_c == R)
    mask_g = (max_c == G)
    mask_b = (max_c == B)
    H[mask_r] = (60.0 * ((G[mask_r] - B[mask_r]) / delta[mask_r]) + 360.0) % 360.0
    H[mask_g] = 60.0 * ((B[mask_g] - R[mask_g]) / delta[mask_g]) + 120.0
    H[mask_b] = 60.0 * ((R[mask_b] - G[mask_b]) / delta[mask_b]) + 240.0
    S = delta / (max_c + 1e-6)
    tot = R + G + B + 1e-6
    r_n, g_n, b_n = R/tot, G/tot, B/tot
    exg = 2.0 * G - R - B
    
    print(f"\n{p.name}:")
    print(f"  R mean={R.mean():.1f}, G mean={G.mean():.1f}, B mean={B.mean():.1f}, ExG mean={exg.mean():.1f}")
    print(f"  green pixels (H 60-165, S>0.12): {((H>=60)&(H<=165)&(S>0.12)).mean():.4f}")
    print(f"  yellow pixels (H 35-60, S>0.15): {((H>=35)&(H<60)&(S>0.15)).mean():.4f}")
    print(f"  brown pixels (H 15-35, S>0.18): {((H>=15)&(H<35)&(S>0.18)).mean():.4f}")
