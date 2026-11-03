import os
import sys
import numpy as np
from PIL import Image, ImageFilter
from prototype_quality_gate import botanical_leaf_quality_gate

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

def run_tests():
    print("=" * 80)
    print("TESTING ADVANCED BOTANICAL MULTI-SPECTRAL QUALITY GATE")
    print("=" * 80)

    DATA_DIR = r"D:\leaf-diseases-detector-main\data\organized\PlantVillage"
    real_healthy_path = os.path.join(DATA_DIR, "Potato___healthy", os.listdir(os.path.join(DATA_DIR, "Potato___healthy"))[0])
    real_blight_path = os.path.join(DATA_DIR, "Potato___Early_blight", os.listdir(os.path.join(DATA_DIR, "Potato___Early_blight"))[0])

    cases = []

    # 1. Real Green Healthy Leaf
    im_healthy = Image.open(real_healthy_path).convert("RGB")
    cases.append(("1. Real Green Healthy Leaf", im_healthy, True))

    # 2. Real Leaf with Necrotic Spots
    im_blight = Image.open(real_blight_path).convert("RGB")
    cases.append(("2. Real Leaf with Necrotic Spots", im_blight, True))

    # 3. Chlorotic Yellow Leaf (Vàng lá do virus/nấm/thiếu sắt)
    arr_yellow = np.random.normal(loc=[185, 175, 45], scale=[18, 15, 10], size=(224, 224, 3)).clip(0, 255).astype(np.uint8)
    im_yellow = Image.fromarray(arr_yellow)
    cases.append(("3. Chlorotic Yellow Leaf (Low Green)", im_yellow, True))

    # 4. Dry Brown / Necrotic Leaf (Lá khô, cháy lá)
    arr_brown = np.random.normal(loc=[145, 95, 38], scale=[15, 12, 8], size=(224, 224, 3)).clip(0, 255).astype(np.uint8)
    im_brown = Image.fromarray(arr_brown)
    cases.append(("4. Dry Brown / Necrotic Leaf", im_brown, True))

    # 5. Low-light Outdoor Leaf
    arr_lowlight = np.random.normal(loc=[55, 85, 40], scale=[12, 14, 10], size=(224, 224, 3)).clip(0, 255).astype(np.uint8)
    im_lowlight = Image.fromarray(arr_lowlight)
    cases.append(("5. Low-light Outdoor Leaf", im_lowlight, True))

    # 6. Human Skin (Non-Leaf)
    arr_skin = np.random.normal(loc=[215, 155, 130], scale=[10, 8, 8], size=(224, 224, 3)).clip(0, 255).astype(np.uint8)
    im_skin = Image.fromarray(arr_skin)
    cases.append(("6. Human Skin (Non-Leaf)", im_skin, False))

    # 7. Blue Fabric (Non-Leaf)
    arr_blue = np.random.normal(loc=[40, 60, 190], scale=[15, 15, 20], size=(224, 224, 3)).clip(0, 255).astype(np.uint8)
    im_blue = Image.fromarray(arr_blue)
    cases.append(("7. Blue Fabric (Non-Leaf)", im_blue, False))

    # 8. Dark Image (< 15 Lum)
    arr_dark = np.random.normal(loc=[10, 12, 9], scale=[2, 2, 2], size=(224, 224, 3)).clip(0, 255).astype(np.uint8)
    im_dark = Image.fromarray(arr_dark)
    cases.append(("8. Dark Image (< 15 Lum)", im_dark, False))

    # 9. Blurry Leaf (LapVar < 12)
    im_blurry = im_healthy.filter(ImageFilter.GaussianBlur(radius=20))
    cases.append(("9. Blurry Leaf (LapVar < 12)", im_blurry, False))

    all_passed = True
    for name, img, expected in cases:
        passed, msg, m = botanical_leaf_quality_gate(img)
        ok = (passed == expected)
        if not ok:
            all_passed = False
        tag = "PASS" if ok else "FAIL"
        print(f"[{tag}] {name:35s} -> Expected: {str(expected):5s} | Got: {str(passed):5s}")
        print(f"       Details: Lum={m.get('mean_lum')}, LapVar={m.get('lap_var')}, Green={m.get('green_ratio')}, Yellow={m.get('yellow_ratio')}, Brown={m.get('brown_ratio')}, Botanical={m.get('botanical_tissue_ratio')}, Skin={m.get('skin_like_ratio')}")
        print(f"       Message: {msg}\n")

    print(f"OVERALL RESULT: {'ALL TESTS PASSED!' if all_passed else 'SOME TESTS FAILED'}")

if __name__ == "__main__":
    run_tests()
