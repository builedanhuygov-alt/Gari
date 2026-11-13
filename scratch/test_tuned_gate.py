import sys
from pathlib import Path
from PIL import Image
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent

def validate_leaf_gate_tuned(img: Image.Image):
    metrics = {
        "width": float(img.width),
        "height": float(img.height),
        "mean_lum": 0.0,
        "color_std": 0.0,
        "lap_var": 0.0,
        "green_ratio": 0.0,
        "yellow_ratio": 0.0,
        "brown_ratio": 0.0,
        "botanical_ratio": 0.0,
        "skin_ratio": 0.0,
        "blue_ratio": 0.0,
        "mean_exg": 0.0,
    }

    # 1. Dimensions Check
    if img.width < 64 or img.height < 64 or img.width > 6000 or img.height > 6000:
        return {
            "status": "IMAGE_QUALITY_LOW",
            "score": 0.0,
            "decision_rule": "dimensions_out_of_bounds",
            "message_vi": "Ảnh chưa đủ rõ để kiểm tra. Hãy chụp gần hơn, đủ sáng và giữ lá trong khung hình.",
            "metrics": metrics
        }

    # Fast analysis thumbnail (max 768px)
    if img.width > 768 or img.height > 768:
        analysis_img = img.copy()
        analysis_img.thumbnail((768, 768), Image.Resampling.BILINEAR)
    else:
        analysis_img = img

    arr = np.asarray(analysis_img.convert("RGB"), dtype=np.float32)
    R, G, B = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    # 2. Luminance & Exposure
    lum = 0.299 * R + 0.587 * G + 0.114 * B
    mean_lum = float(lum.mean())
    metrics["mean_lum"] = round(mean_lum, 2)

    # 3. Color Diversity
    color_std = float(arr.std())
    metrics["color_std"] = round(color_std, 2)

    # 4. Sharpness (Laplacian Variance)
    gray = np.asarray(analysis_img.convert("L"), dtype=np.float32)
    lap = gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:] - 4.0 * gray[1:-1, 1:-1]
    lap_var = float(lap.var())
    metrics["lap_var"] = round(lap_var, 2)

    # Optical quality gate: extreme darkness, blowout, severe blur, or solid blank color
    if mean_lum < 16.0 or mean_lum > 250.0 or lap_var < 8.0 or color_std < 5.0:
        return {
            "status": "IMAGE_QUALITY_LOW",
            "score": round(min(lap_var / 50.0, 0.35), 2),
            "decision_rule": f"optical_quality_low (lum={mean_lum:.1f}, lap={lap_var:.1f}, std={color_std:.1f})",
            "message_vi": "Ảnh chưa đủ rõ để kiểm tra. Hãy chụp gần hơn, đủ sáng và giữ lá trong khung hình.",
            "metrics": metrics
        }

    # 5. Multi-Spectral Color Analysis (HSV + Normalized RGB)
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
    tot_rgb = R + G + B + 1e-6
    r_n, g_n, b_n = R / tot_rgb, G / tot_rgb, B / tot_rgb

    # Band A: Green Foliage (Healthy or early-stage lesion, Hue 55 to 165)
    green_mask = ((H >= 55.0) & (H <= 165.0) & (S >= 0.10)) | ((g_n > 0.35) & (2.0 * G - R - B > 2.0))
    green_ratio = float(green_mask.mean())
    metrics["green_ratio"] = round(green_ratio, 4)

    # Band B: Chlorotic Yellow Foliage (Hue 35 to 60)
    yellow_mask = (H >= 35.0) & (H < 60.0) & (S >= 0.15) & (r_n > 0.33) & (g_n > 0.30)
    yellow_ratio = float(yellow_mask.mean())
    metrics["yellow_ratio"] = round(yellow_ratio, 4)

    # Band C: Brown Necrotic / Fungal Lesion / Dry Leaf Tissue
    brown_mask = (H >= 12.0) & (H < 35.0) & (S >= 0.15) & (r_n > 0.38) & (g_n > 0.24) & (R > B + 5.0) & (G > B + 2.0)
    brown_ratio = float(brown_mask.mean())
    metrics["brown_ratio"] = round(brown_ratio, 4)

    # Combined Botanical Foliage Tissue
    botanical_tissue = green_mask | yellow_mask | brown_mask
    botanical_ratio = float(botanical_tissue.mean())
    metrics["botanical_ratio"] = round(botanical_ratio, 4)
    metrics["botanical_tissue_ratio"] = round(botanical_ratio, 4)

    # Band D: Blue / Synthetic Fabric Dominance
    blue_dom_mask = (b_n > 0.42) & (B > R + 15.0) & (B > G + 10.0)
    blue_ratio = float(blue_dom_mask.mean())
    metrics["blue_ratio"] = round(blue_ratio, 4)
    metrics["blue_dominance_ratio"] = round(blue_ratio, 4)

    # Band E: Human Skin Profile
    r_g_diff = np.maximum(R - G, 0.1)
    skin_ratio_test = (R - B) / r_g_diff
    skin_mask = (H >= 0.0) & (H <= 25.0) & (S >= 0.15) & (S <= 0.65) & (R > G + 15.0) & (G > B + 8.0) & (skin_ratio_test >= 1.7) & (skin_ratio_test <= 4.2)
    skin_ratio = float(skin_mask.mean())
    metrics["skin_ratio"] = round(skin_ratio, 4)
    metrics["skin_like_ratio"] = round(skin_ratio, 4)

    # Excess Green Index (ExG)
    mean_exg = float((2.0 * G - R - B).mean())
    metrics["mean_exg"] = round(mean_exg, 2)

    # ---------------------------------------------------------
    # NOT_A_LEAF Rejection Rules:
    # ---------------------------------------------------------
    # 1. Synthetic blue / cyan surfaces: Only reject if no significant foliage is present
    if blue_ratio > 0.40 and botanical_ratio < 0.08:
        return {
            "status": "NOT_A_LEAF",
            "score": 0.02,
            "decision_rule": f"synthetic_blue (blue={blue_ratio:.3f}, bot={botanical_ratio:.3f})",
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # 2. Human skin dominance: Only reject if skin dominates and foliage is absent
    if skin_ratio > 0.38 and botanical_ratio < 0.08:
        return {
            "status": "NOT_A_LEAF",
            "score": 0.04,
            "decision_rule": f"human_skin (skin={skin_ratio:.3f}, bot={botanical_ratio:.3f})",
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # 3. Non-plant object / strong negative ExG
    if mean_exg < -18.0 and botanical_ratio < 0.06:
        return {
            "status": "NOT_A_LEAF",
            "score": 0.05,
            "decision_rule": f"negative_exg (exg={mean_exg:.1f}, bot={botanical_ratio:.3f})",
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # 4. Total lack of botanical plant tissue (< 6% across green, yellow, brown)
    if botanical_ratio < 0.06:
        return {
            "status": "NOT_A_LEAF",
            "score": round(botanical_ratio, 3),
            "decision_rule": f"lack_of_botanical_tissue (bot={botanical_ratio:.3f})",
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # 5. Complete absence of all plant pigments (green < 1.5% AND yellow < 1.5% AND brown < 3%)
    if green_ratio < 0.015 and yellow_ratio < 0.015 and brown_ratio < 0.03:
        return {
            "status": "NOT_A_LEAF",
            "score": round(max(green_ratio, yellow_ratio, brown_ratio), 3),
            "decision_rule": f"absence_of_all_pigments (g={green_ratio:.3f}, y={yellow_ratio:.3f}, b={brown_ratio:.3f})",
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # ---------------------------------------------------------
    # UNCERTAIN Rules: Truly marginal foliage
    # ---------------------------------------------------------
    if botanical_ratio < 0.08 or (lap_var < 12.0 and botanical_ratio < 0.12):
        return {
            "status": "UNCERTAIN",
            "score": round(0.40 + botanical_ratio * 0.5, 2),
            "decision_rule": f"marginal_foliage (bot={botanical_ratio:.3f}, lap={lap_var:.1f})",
            "message_vi": "Gari chưa xác định được đây có phải ảnh lá cây hay không. Hãy chụp rõ một chiếc lá.",
            "metrics": metrics
        }

    # ---------------------------------------------------------
    # LEAF_VALID: Sufficient plant foliage
    # ---------------------------------------------------------
    confidence = min(0.99, max(0.65, 0.50 + botanical_ratio * 0.35 + min(lap_var / 500.0, 0.15)))
    return {
        "status": "LEAF_VALID",
        "score": round(confidence, 3),
        "decision_rule": f"leaf_valid (bot={botanical_ratio:.3f}, score={confidence:.3f})",
        "message_vi": None,
        "metrics": metrics
    }

# Run tests
print("--- TEST 1: PlantVillage Real Leaf Dataset (450 images) ---")
pv_dir = ROOT_DIR / "data" / "organized" / "PlantVillage"
pv_tested, pv_valid, pv_not_leaf, pv_uncertain, pv_low_q = 0, 0, 0, 0, 0
for folder in sorted(pv_dir.iterdir()):
    if not folder.is_dir(): continue
    for p in list(folder.glob("*.JPG"))[:30]:
        pv_tested += 1
        res = validate_leaf_gate_tuned(Image.open(p))
        st = res["status"]
        if st == "LEAF_VALID": pv_valid += 1
        elif st == "NOT_A_LEAF": 
            pv_not_leaf += 1
            print(f"  False NOT_A_LEAF: {folder.name}/{p.name} -> {res['decision_rule']}")
        elif st == "UNCERTAIN": pv_uncertain += 1
        elif st == "IMAGE_QUALITY_LOW": pv_low_q += 1

print(f"Results: VALID={pv_valid}/{pv_tested} ({pv_valid/pv_tested*100:.2f}%), NOT_A_LEAF={pv_not_leaf}, UNCERTAIN={pv_uncertain}, LOW_Q={pv_low_q}")

print("\n--- TEST 2: test_leaf.jpg ---")
p_leaf = ROOT_DIR / "tests/fixtures/test_leaf.jpg"
if p_leaf.exists():
    res = validate_leaf_gate_tuned(Image.open(p_leaf))
    print(f"test_leaf.jpg -> {res['status']} ({res['decision_rule']})")

print("\n--- TEST 3: Non-Leaf & Quality Samples ---")
non_leaf_dir = ROOT_DIR / "data/test_samples_17"
for p in sorted(non_leaf_dir.glob("*.jpg")):
    res = validate_leaf_gate_tuned(Image.open(p))
    print(f"{p.name:25s} -> {res['status']:18s} ({res['decision_rule']})")
