import sys
from pathlib import Path
from PIL import Image
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Let's inspect the 6 failed PlantVillage images from benchmark
failed_files = [
    ROOT_DIR / "data/organized/PlantVillage/Tomato_Late_blight/01ece5a1-8398-4e68-a9e3-198c57b51b01___GHLB2 Leaf 8757.JPG",
    ROOT_DIR / "data/organized/PlantVillage/Tomato_Leaf_Mold/03c6374e-c292-440e-b2e3-a70c5e64562a___Crnl_L.Mold 8935.JPG",
    ROOT_DIR / "data/organized/PlantVillage/Tomato_Leaf_Mold/0443d006-9d75-4d46-9312-941f21e3791d___Crnl_L.Mold 9139.JPG",
    ROOT_DIR / "data/organized/PlantVillage/Tomato_Leaf_Mold/053f0efc-038f-471b-9e7b-5b605d45fda4___Crnl_L.Mold 8982.JPG",
    ROOT_DIR / "data/organized/PlantVillage/Tomato_Leaf_Mold/0595201b-049b-47ff-9e56-7e042932c0fe___Crnl_L.Mold 9179.JPG",
    ROOT_DIR / "data/organized/PlantVillage/Tomato_Leaf_Mold/08cdd6ec-9dd7-4fc2-a255-11a70adaffd4___Crnl_L.Mold 9177.JPG",
]

for p in failed_files:
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
    
    # Original masks
    orig_green = ((H >= 65.0) & (H <= 165.0) & (S >= 0.15)) | ((g_n > 0.36) & (2.0 * G - R - B > 5.0))
    orig_yellow = (H >= 35.0) & (H < 65.0) & (S >= 0.20) & (b_n < 0.26) & (r_n > 0.34) & (g_n > 0.32)
    orig_brown = (H >= 15.0) & (H < 35.0) & (S >= 0.18) & (r_n > 0.40) & (g_n > 0.26) & (b_n < 0.22) & ((G - B) > 8.0)
    orig_blue = (b_n > 0.42) & (B > R + 15.0) & (B > G + 10.0)
    
    print(f"\n{p.name}:")
    print(f"  orig green: {orig_green.mean():.4f}, yellow: {orig_yellow.mean():.4f}, brown: {orig_brown.mean():.4f}, blue: {orig_blue.mean():.4f}")
    
    # Let's inspect the pixels where H is green/yellow (35 to 165)
    foliage_broad = (H >= 35.0) & (H <= 165.0) & (S >= 0.10)
    print(f"  broad green/yellow (H 35-165, S>=0.1): {foliage_broad.mean():.4f}")
    
    # Necrotic / Brown / Lesion broad (H 5 to 45, or dark vegetation with G > B)
    lesion_broad = ((H >= 5.0) & (H < 45.0) & (S >= 0.10) & (R > B)) | ((H >= 20.0) & (H < 65.0) & (r_n > 0.33) & (g_n > 0.28))
    print(f"  broad brown/lesion: {lesion_broad.mean():.4f}")
    
    # Combined botanical
    combined_botanical = foliage_broad | lesion_broad
    print(f"  combined botanical: {combined_botanical.mean():.4f}")
