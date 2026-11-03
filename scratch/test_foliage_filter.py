import os
import sys
import numpy as np
from PIL import Image

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = r"D:\leaf-diseases-detector-main\data\organized\PlantVillage"

def evaluate_foliage_check(img: Image.Image):
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    R, G, B = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    
    # 1. Luminance
    lum = 0.299 * R + 0.587 * G + 0.114 * B
    mean_lum = float(lum.mean())
    
    # 2. Excess Green (ExG)
    exg = 2.0 * G - R - B
    mean_exg = float(exg.mean())
    
    # 3. HSV Foliage Coverage
    # Green/Yellow-green: H ~ 25..95 (OpenCV scale 0..180 is 1/2 of 360)
    # Let's compute directly in numpy RGB
    # Green dominance or diseased chlorosis: G > R*0.8 and G > B*0.8
    # Or in normalized color space
    total = R + G + B + 1e-6
    r_n, g_n, b_n = R / total, G / total, B / total
    
    # Plant foliage mask:
    # Healthy green: g_n > 0.35 and g_n > r_n and g_n > b_n
    # Yellowing/Chlorotic/Necrotic leaf tissue: (g_n + r_n > 0.70) and (g_n > 0.30) and (b_n < 0.28)
    foliage_mask = (g_n > 0.35) | ((r_n > 0.35) & (g_n > 0.28) & (b_n < 0.25))
    foliage_ratio = float(foliage_mask.mean())
    
    return {
        "mean_lum": round(mean_lum, 2),
        "mean_exg": round(mean_exg, 2),
        "foliage_ratio": round(foliage_ratio, 4)
    }

# Test on real leaves
leaf_samples = [
    os.path.join(DATA_DIR, "Potato___Early_blight", os.listdir(os.path.join(DATA_DIR, "Potato___Early_blight"))[0]),
    os.path.join(DATA_DIR, "Tomato_Bacterial_spot", os.listdir(os.path.join(DATA_DIR, "Tomato_Bacterial_spot"))[0]),
    os.path.join(DATA_DIR, "Pepper__bell___healthy", os.listdir(os.path.join(DATA_DIR, "Pepper__bell___healthy"))[0]),
]

print("--- REAL LEAF IMAGES ---")
for p in leaf_samples:
    im = Image.open(p)
    res = evaluate_foliage_check(im)
    print(f"{os.path.basename(os.path.dirname(p)):25s}: Lum={res['mean_lum']:5.1f}, ExG={res['mean_exg']:6.1f}, FoliageRatio={res['foliage_ratio']*100:5.1f}%")

# Test on non-leaf synthetic images
print("\n--- NON-LEAF SYNTHETIC IMAGES ---")
# 1. Human skin
skin_arr = np.random.normal(loc=[210, 150, 130], scale=[10, 8, 8], size=(224, 224, 3)).clip(0, 255).astype(np.uint8)
skin_img = Image.fromarray(skin_arr)
res_skin = evaluate_foliage_check(skin_img)
print(f"{'Human Skin':25s}: Lum={res_skin['mean_lum']:5.1f}, ExG={res_skin['mean_exg']:6.1f}, FoliageRatio={res_skin['foliage_ratio']*100:5.1f}%")

# 2. Blue fabric
fabric_arr = np.random.normal(loc=[40, 60, 180], scale=[15, 15, 20], size=(224, 224, 3)).clip(0, 255).astype(np.uint8)
fabric_img = Image.fromarray(fabric_arr)
res_fabric = evaluate_foliage_check(fabric_img)
print(f"{'Blue Fabric':25s}: Lum={res_fabric['mean_lum']:5.1f}, ExG={res_fabric['mean_exg']:6.1f}, FoliageRatio={res_fabric['foliage_ratio']*100:5.1f}%")

# 3. Food / bread / burger
food_arr = np.random.normal(loc=[180, 100, 50], scale=[20, 15, 10], size=(224, 224, 3)).clip(0, 255).astype(np.uint8)
food_img = Image.fromarray(food_arr)
res_food = evaluate_foliage_check(food_img)
print(f"{'Food / Bread':25s}: Lum={res_food['mean_lum']:5.1f}, ExG={res_food['mean_exg']:6.1f}, FoliageRatio={res_food['foliage_ratio']*100:5.1f}%")

# 4. Dark image
dark_arr = np.random.normal(loc=[15, 18, 14], scale=[3, 3, 3], size=(224, 224, 3)).clip(0, 255).astype(np.uint8)
dark_img = Image.fromarray(dark_arr)
res_dark = evaluate_foliage_check(dark_img)
print(f"{'Dark Image':25s}: Lum={res_dark['mean_lum']:5.1f}, ExG={res_dark['mean_exg']:6.1f}, FoliageRatio={res_dark['foliage_ratio']*100:5.1f}%")
