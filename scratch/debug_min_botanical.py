import sys
from pathlib import Path
from PIL import Image
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
pv_dir = ROOT_DIR / "data" / "organized" / "PlantVillage"

min_green = 1.0
min_botanical = 1.0
leaf_records = []

for folder in sorted(pv_dir.iterdir()):
    if not folder.is_dir(): continue
    for p in list(folder.glob("*.JPG"))[:20]:
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
        
        green = (((H >= 60.0) & (H <= 165.0) & (S >= 0.12)) | ((g_n > 0.35) & (2.0*G - R - B > 3.0))).mean()
        yellow = ((H >= 35.0) & (H < 60.0) & (S >= 0.15) & (r_n > 0.33) & (g_n > 0.30)).mean()
        brown = ((H >= 12.0) & (H < 35.0) & (S >= 0.15) & (r_n > 0.36) & (g_n > 0.24) & (R > B + 5.0)).mean()
        botanical = (((H >= 60.0) & (H <= 165.0) & (S >= 0.12)) | 
                     ((g_n > 0.35) & (2.0*G - R - B > 3.0)) |
                     ((H >= 35.0) & (H < 60.0) & (S >= 0.15) & (r_n > 0.33) & (g_n > 0.30)) |
                     ((H >= 12.0) & (H < 35.0) & (S >= 0.15) & (r_n > 0.36) & (g_n > 0.24) & (R > B + 5.0))).mean()
        
        leaf_records.append((folder.name, p.name, green, yellow, brown, botanical))

sorted_by_botanical = sorted(leaf_records, key=lambda x: x[5])
print("Lowest botanical ratios in PlantVillage:")
for rec in sorted_by_botanical[:10]:
    print(f"  [{rec[0]}] {rec[1]}: botanical={rec[5]:.4f}, green={rec[2]:.4f}, yellow={rec[3]:.4f}, brown={rec[4]:.4f}")
