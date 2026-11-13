import sys
from pathlib import Path
from PIL import Image
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent

def validate_leaf_gate_improved(img: Image.Image):
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

    # Analysis copy
    if img.width > 768 or img.height > 768:
        analysis_img = img.copy()
        analysis_img.thumbnail((768, 768), Image.Resampling.BILINEAR)
    else:
        analysis_img = img

    arr = np.asarray(analysis_img.convert("RGB"), dtype=np.float32)
    R, G, B = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    # 2. Luminance
    lum = 0.299 * R + 0.587 * G + 0.114 * B
    mean_lum = float(lum.mean())
    metrics["mean_lum"] = round(mean_lum, 2)

    # 3. Color Diversity
    color_std = float(arr.std())
    metrics["color_std"] = round(color_std, 2)

    # 4. Sharpness
    gray = np.asarray(analysis_img.convert("L"), dtype=np.float32)
    lap = gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:] - 4.0 * gray[1:-1, 1:-1]
    lap_var = float(lap.var())
    metrics["lap_var"] = round(lap_var, 2)

    # Optical quality gate: extreme darkness, severe blowout, extreme blur, or solid blank color
    # Note: lap_var < 8.0 catches true blur (e.g. 9_blurry_leaf has lap=0.02) without false-rejecting 256x256 test leaves
    if mean_lum < 16.0 or mean_lum > 250.0 or lap_var < 8.0 or color_std < 5.0:
        return {
            "status": "IMAGE_QUALITY_LOW",
            "score": round(min(lap_var / 50.0, 0.35), 2),
            "decision_rule": "optical_quality_low (blur/exposure)",
            "message_vi": "Ảnh chưa đủ rõ để kiểm tra. Hãy chụp gần hơn, đủ sáng và giữ lá trong khung hình.",
            "metrics": metrics
        }

    # 5. Multi-Spectral Color Analysis
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

    # Band A: Green Foliage (Healthy or early-stage lesion, Hue 58 to 165)
    green_mask = ((H >= 58.0) & (H <= 165.0) & (S >= 0.12)) | ((g_n > 0.35) & (2.0 * G - R - B > 3.0))
    green_ratio = float(green_mask.mean())
    metrics["green_ratio"] = round(green_ratio, 4)

    # Band B: Chlorotic Yellow Foliage (Hue 35 to 60)
    yellow_mask = (H >= 35.0) & (H < 60.0) & (S >= 0.15) & (r_n > 0.33) & (g_n > 0.30)
    yellow_ratio = float(yellow_mask.mean())
    metrics["yellow_ratio"] = round(yellow_ratio, 4)

    # Band C: Brown Necrotic / Fungal Lesion / Dry Leaf Tissue (Hue 10 to 35, or dark lesion with R > B)
    brown_mask = ((H >= 10.0) & (H < 35.0) & (S >= 0.12) & (r_n > 0.35) & (g_n > 0.23) & (R > B + 3.0)) | \
                 ((H >= 15.0) & (H < 45.0) & (S >= 0.15) & (2.0 * G - R - B < -2.0) & (R > B + 4.0))
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
    # NOT_A_LEAF Rejection Rules (Must strictly require absence of botanical foliage):
    # ---------------------------------------------------------
    # 1. Synthetic blue / cyan surfaces: only reject if NO significant foliage is present
    if blue_ratio > 0.40 and botanical_ratio < 0.10:
        return {
            "status": "NOT_A_LEAF",
            "score": 0.02,
            "decision_rule": "synthetic_blue_surface",
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # 2. Human skin dominance
    if skin_ratio > 0.38 and botanical_ratio < 0.10:
        return {
            "status": "NOT_A_LEAF",
            "score": 0.04,
            "decision_rule": "human_skin_dominant",
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # 3. Non-plant object / strong negative ExG
    if mean_exg < -18.0 and botanical_ratio < 0.08:
        return {
            "status": "NOT_A_LEAF",
            "score": 0.05,
            "decision_rule": "negative_exg_non_plant",
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # 4. Total lack of botanical plant tissue (< 7% across green, yellow, and brown)
    if botanical_ratio < 0.07:
        return {
            "status": "NOT_A_LEAF",
            "score": round(botanical_ratio, 3),
            "decision_rule": "lack_of_botanical_tissue",
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # 5. Complete absence of all plant pigments (green < 1.5%, yellow < 1.5%, AND brown < 3.0%)
    if green_ratio < 0.015 and yellow_ratio < 0.015 and brown_ratio < 0.03:
        return {
            "status": "NOT_A_LEAF",
            "score": round(max(green_ratio, yellow_ratio, brown_ratio), 3),
            "decision_rule": "absence_of_all_pigments",
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # ---------------------------------------------------------
    # UNCERTAIN Rules: Ambiguous foliage or marginal ratio
    # ---------------------------------------------------------
    if botanical_ratio < 0.10 or (lap_var < 16.0 and botanical_ratio < 0.18):
        return {
            "status": "UNCERTAIN",
            "score": round(0.40 + botanical_ratio * 0.5, 2),
            "decision_rule": "ambiguous_marginal_foliage",
            "message_vi": "Gari chưa xác định được đây có phải ảnh lá cây hay không. Hãy chụp rõ một chiếc lá.",
            "metrics": metrics
        }

    # ---------------------------------------------------------
    # LEAF_VALID: Sufficient plant foliage (green, yellow, or brown)
    # ---------------------------------------------------------
    confidence = min(0.99, max(0.65, 0.50 + botanical_ratio * 0.35 + min(lap_var / 500.0, 0.15)))
    return {
        "status": "LEAF_VALID",
        "score": round(confidence, 3),
        "decision_rule": "leaf_valid",
        "message_vi": None,
        "metrics": metrics
    }

# -------------------------------------------------------------
# RUN BENCHMARK COMPARISON
# -------------------------------------------------------------
pv_dir = ROOT_DIR / "data" / "organized" / "PlantVillage"
folders = sorted([f for f in pv_dir.iterdir() if f.is_dir()])

pv_tested = 0
pv_valid = 0
pv_not_a_leaf = 0
pv_uncertain = 0
pv_low_quality = 0

for folder in folders:
    for p in list(folder.glob("*.JPG"))[:30]:
        pv_tested += 1
        img = Image.open(p)
        res = validate_leaf_gate_improved(img)
        st = res["status"]
        if st == "LEAF_VALID": pv_valid += 1
        elif st == "NOT_A_LEAF": pv_not_a_leaf += 1
        elif st == "UNCERTAIN": pv_uncertain += 1
        elif st == "IMAGE_QUALITY_LOW": pv_low_quality += 1

print(f"PlantVillage Real Leaf Dataset ({pv_tested} images):")
print(f"  LEAF_VALID: {pv_valid} ({pv_valid/pv_tested*100:.2f}%)")
print(f"  NOT_A_LEAF: {pv_not_a_leaf} ({pv_not_a_leaf/pv_tested*100:.2f}%)  <-- False Rejection Rate")
print(f"  UNCERTAIN:  {pv_uncertain} ({pv_uncertain/pv_tested*100:.2f}%)")
print(f"  LOW_QUALITY:{pv_low_quality} ({pv_low_quality/pv_tested*100:.2f}%)")

print("\nNon-Leaf & Low Quality Test Set:")
non_leaf_dir = ROOT_DIR / "data" / "test_samples_17"
for p in sorted(non_leaf_dir.glob("*.jpg")):
    img = Image.open(p)
    res = validate_leaf_gate_improved(img)
    print(f"  {p.name:25s} -> status={res['status']:18s} rule={res['decision_rule']}")
