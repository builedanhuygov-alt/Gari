import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.stdout.reconfigure(encoding="utf-8")

def validate_leaf_gate(img: Image.Image):
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

    # 1. Dimensions
    if img.width < 64 or img.height < 64:
        return {
            "status": "IMAGE_QUALITY_LOW",
            "score": 0.0,
            "message_vi": "Ảnh chưa đủ rõ để kiểm tra. Hãy chụp gần hơn, đủ sáng và giữ lá trong khung hình.",
            "metrics": metrics
        }

    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    R, G, B = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    # Luminance
    lum = 0.299 * R + 0.587 * G + 0.114 * B
    mean_lum = float(lum.mean())
    metrics["mean_lum"] = round(mean_lum, 2)

    # Sharpness (Laplacian variance)
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    lap = gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:] - 4.0 * gray[1:-1, 1:-1]
    lap_var = float(lap.var())
    metrics["lap_var"] = round(lap_var, 2)

    color_std = float(arr.std())
    metrics["color_std"] = round(color_std, 2)

    # Low quality checks (blurry, dark, overexposed, blank)
    if mean_lum < 18.0 or mean_lum > 248.0 or lap_var < 12.0 or color_std < 5.0:
        return {
            "status": "IMAGE_QUALITY_LOW",
            "score": round(min(lap_var / 50.0, 0.4), 2),
            "message_vi": "Ảnh chưa đủ rõ để kiểm tra. Hãy chụp gần hơn, đủ sáng và giữ lá trong khung hình.",
            "metrics": metrics
        }

    # Botanical multi-spectral analysis
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

    # Band A: Green Foliage
    green_mask = ((H >= 65.0) & (H <= 165.0) & (S >= 0.15)) | ((g_n > 0.36) & (2.0 * G - R - B > 5.0))
    green_ratio = float(green_mask.mean())
    metrics["green_ratio"] = round(green_ratio, 4)

    # Band B: Chlorotic Yellow Foliage
    yellow_mask = (H >= 35.0) & (H < 65.0) & (S >= 0.20) & (b_n < 0.26) & (r_n > 0.34) & (g_n > 0.32)
    yellow_ratio = float(yellow_mask.mean())
    metrics["yellow_ratio"] = round(yellow_ratio, 4)

    # Band C: Brown Necrotic / Senescent Dry Leaf Tissue
    brown_mask = (H >= 15.0) & (H < 35.0) & (S >= 0.18) & (r_n > 0.40) & (g_n > 0.26) & (b_n < 0.22) & ((G - B) > 8.0)
    brown_ratio = float(brown_mask.mean())
    metrics["brown_ratio"] = round(brown_ratio, 4)

    # Botanical total
    botanical_tissue = green_mask | yellow_mask | brown_mask
    botanical_ratio = float(botanical_tissue.mean())
    metrics["botanical_ratio"] = round(botanical_ratio, 4)

    # Blue dominance
    blue_dom_mask = (b_n > 0.42) & (B > R + 15.0) & (B > G + 10.0)
    blue_ratio = float(blue_dom_mask.mean())
    metrics["blue_ratio"] = round(blue_ratio, 4)

    # Skin mask
    r_g_diff = np.maximum(R - G, 0.1)
    skin_ratio_test = (R - B) / r_g_diff
    skin_mask = (H >= 0.0) & (H <= 25.0) & (S >= 0.15) & (S <= 0.65) & (R > G + 15.0) & (G > B + 8.0) & (skin_ratio_test >= 1.7) & (skin_ratio_test <= 4.2)
    skin_ratio = float(skin_mask.mean())
    metrics["skin_ratio"] = round(skin_ratio, 4)

    # ExG
    mean_exg = float((2.0 * G - R - B).mean())
    metrics["mean_exg"] = round(mean_exg, 2)

    # NOT_A_LEAF rules:
    # 1. Synthetic blue/cyan
    if blue_ratio > 0.35:
        return {
            "status": "NOT_A_LEAF",
            "score": 0.02,
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # 2. Human skin
    if skin_ratio > 0.38 and botanical_ratio < 0.12:
        return {
            "status": "NOT_A_LEAF",
            "score": 0.05,
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # 3. Non-plant object / strong negative ExG
    if mean_exg < -18.0 and botanical_ratio < 0.15:
        return {
            "status": "NOT_A_LEAF",
            "score": 0.04,
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # 4. Total lack of botanical tissue (< 10%)
    if botanical_ratio < 0.10:
        return {
            "status": "NOT_A_LEAF",
            "score": round(botanical_ratio, 3),
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # UNCERTAIN rules:
    # Marginal botanical presence (10% - 20%) or somewhat low contrast/clarity
    if botanical_ratio < 0.20 or (lap_var < 24.0 and botanical_ratio < 0.30):
        return {
            "status": "UNCERTAIN",
            "score": round(0.40 + botanical_ratio * 0.5, 2),
            "message_vi": "Gari chưa xác định được đây có phải ảnh lá cây hay không. Hãy chụp rõ một chiếc lá.",
            "metrics": metrics
        }

    # LEAF_VALID
    # Sufficient botanical tissue, clear sharpness, healthy or diseased/yellow/brown leaf
    confidence = min(0.99, max(0.65, 0.50 + botanical_ratio * 0.35 + min(lap_var / 500.0, 0.15)))
    return {
        "status": "LEAF_VALID",
        "score": round(confidence, 3),
        "message_vi": None,
        "metrics": metrics
    }

# Create test images
tests = {}

# 1. Clear healthy green leaf
img_green = Image.new("RGB", (256, 256), (34, 139, 34))
d = ImageDraw.Draw(img_green)
d.ellipse([30, 20, 226, 236], fill=(46, 175, 46), outline=(20, 100, 20))
d.line([128, 20, 128, 236], fill=(18, 90, 18), width=3)
for y in range(40, 220, 30):
    d.line([128, y, 60, y - 15], fill=(25, 110, 25), width=2)
    d.line([128, y, 196, y - 15], fill=(25, 110, 25), width=2)
tests["Healthy green leaf"] = img_green

# 2. Diseased leaf with brown spots
img_diseased = img_green.copy()
d_dis = ImageDraw.Draw(img_diseased)
for pos in [(70, 80), (160, 120), (110, 170), (140, 70), (90, 140)]:
    d_dis.ellipse([pos[0]-15, pos[1]-15, pos[0]+15, pos[1]+15], fill=(139, 69, 19), outline=(90, 40, 10))
tests["Diseased leaf with spots"] = img_diseased

# 3. Yellow leaf (chlorosis)
img_yellow = Image.new("RGB", (256, 256), (200, 180, 40))
d_yel = ImageDraw.Draw(img_yellow)
d_yel.ellipse([30, 20, 226, 236], fill=(225, 205, 30), outline=(150, 130, 20))
d_yel.line([128, 20, 128, 236], fill=(140, 120, 15), width=3)
tests["Yellow leaf (chlorosis)"] = img_yellow

# 4. Brown / dry leaf (necrosis)
img_brown = Image.new("RGB", (256, 256), (120, 75, 35))
d_br = ImageDraw.Draw(img_brown)
d_br.ellipse([30, 20, 226, 236], fill=(140, 90, 45), outline=(90, 50, 20))
d_br.line([128, 20, 128, 236], fill=(80, 45, 15), width=3)
tests["Brown dry leaf"] = img_brown

# 5. Non-leaf object (brick wall / concrete)
img_wall = Image.new("RGB", (256, 256), (160, 80, 70))
d_wall = ImageDraw.Draw(img_wall)
for y in range(0, 256, 32):
    d_wall.line([0, y, 256, y], fill=(60, 40, 30), width=2)
tests["Brick wall / object"] = img_wall

# 6. Human skin
img_skin = Image.new("RGB", (256, 256), (220, 160, 130))
d_skin = ImageDraw.Draw(img_skin)
d_skin.ellipse([40, 40, 216, 216], fill=(235, 180, 150), outline=(200, 140, 110))
tests["Human face / skin"] = img_skin

# 7. Blurry leaf
img_blurry = img_green.filter(ImageFilter.GaussianBlur(radius=15))
tests["Blurry leaf"] = img_blurry

# 8. Dark / low light leaf
img_dark = Image.new("RGB", (256, 256), (10, 12, 10))
tests["Low-light / dark"] = img_dark

# 9. Ambiguous / small leaf snippet on desk
img_desk = Image.new("RGB", (256, 256), (180, 150, 120))
d_desk = ImageDraw.Draw(img_desk)
d_desk.ellipse([100, 100, 140, 140], fill=(46, 175, 46))
tests["Ambiguous snippet"] = img_desk

print(f"{'Image Scenario':<30} | {'Expected':<18} | {'Actual Status':<18} | {'Score':<6} | {'Match'}")
print("-" * 85)
for name, im in tests.items():
    res = validate_leaf_gate(im)
    status = res["status"]
    score = res["score"]
    # Verify expected
    if "green" in name or "spots" in name or "Yellow" in name or "Brown" in name:
        exp = "LEAF_VALID"
    elif "Blurry" in name or "dark" in name:
        exp = "IMAGE_QUALITY_LOW"
    elif "skin" in name or "wall" in name:
        exp = "NOT_A_LEAF"
    elif "Ambiguous" in name:
        exp = "UNCERTAIN"
    else:
        exp = "?"
    match = "PASS" if status == exp else "FAIL"
    print(f"{name:<30} | {exp:<18} | {status:<18} | {score:<6.2f} | {match}")
