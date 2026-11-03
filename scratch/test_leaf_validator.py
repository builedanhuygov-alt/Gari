import io
import sys
import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

def validate_leaf_gate(img: Image.Image):
    """
    Centralized Leaf Validation Gate (Part 1 & 2)
    Returns:
    {
        "status": "LEAF_VALID" | "NOT_A_LEAF" | "UNCERTAIN" | "IMAGE_QUALITY_LOW",
        "passed": bool,
        "score": float,
        "reason": str,
        "message_vi": str,
        "metrics": dict
    }
    """
    metrics = {
        "width": img.width,
        "height": img.height
    }

    # 1. Dimension Check
    if img.width < 64 or img.height < 64:
        return {
            "status": "IMAGE_QUALITY_LOW",
            "passed": False,
            "score": 0.0,
            "reason": f"Kích thước ảnh quá nhỏ ({img.width}x{img.height} pixel).",
            "message_vi": "Ảnh chưa đủ rõ để kiểm tra. Hãy chụp gần hơn, đủ sáng và giữ lá trong khung hình.",
            "metrics": metrics
        }

    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    R, G, B = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    # 2. Exposure & Luminance
    lum = 0.299 * R + 0.587 * G + 0.114 * B
    mean_lum = float(lum.mean())
    metrics["mean_lum"] = round(mean_lum, 2)

    if mean_lum < 16.0:
        return {
            "status": "IMAGE_QUALITY_LOW",
            "passed": False,
            "score": 0.0,
            "reason": f"Hình ảnh quá tối (độ sáng trung bình = {mean_lum:.1f}/255).",
            "message_vi": "Ảnh chưa đủ rõ để kiểm tra. Hãy chụp gần hơn, đủ sáng và giữ lá trong khung hình.",
            "metrics": metrics
        }

    if mean_lum > 248.0:
        return {
            "status": "IMAGE_QUALITY_LOW",
            "passed": False,
            "score": 0.0,
            "reason": f"Hình ảnh bị chói sáng hoặc phơi sáng quá mức (độ sáng trung bình = {mean_lum:.1f}/255).",
            "message_vi": "Ảnh chưa đủ rõ để kiểm tra. Hãy chụp gần hơn, đủ sáng và giữ lá trong khung hình.",
            "metrics": metrics
        }

    # 3. Color Diversity & Featurelessness
    color_std = float(arr.std())
    metrics["color_std"] = round(color_std, 2)
    if color_std < 6.0:
        return {
            "status": "IMAGE_QUALITY_LOW",
            "passed": False,
            "score": 0.0,
            "reason": "Hình ảnh đơn sắc hoặc không có chi tiết.",
            "message_vi": "Ảnh chưa đủ rõ để kiểm tra. Hãy chụp gần hơn, đủ sáng và giữ lá trong khung hình.",
            "metrics": metrics
        }

    # 4. Sharpness / Blur Check (Laplacian Variance)
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    lap = gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:] - 4.0 * gray[1:-1, 1:-1]
    lap_var = float(lap.var())
    metrics["lap_var"] = round(lap_var, 2)

    if lap_var < 14.0:
        return {
            "status": "IMAGE_QUALITY_LOW",
            "passed": False,
            "score": 0.0,
            "reason": f"Hình ảnh quá mờ (độ sắc nét LapVar = {lap_var:.1f} < 14.0).",
            "message_vi": "Ảnh chưa đủ rõ để kiểm tra. Hãy chụp gần hơn, đủ sáng và giữ lá trong khung hình.",
            "metrics": metrics
        }

    if lap_var > 45000.0:
        return {
            "status": "IMAGE_QUALITY_LOW",
            "passed": False,
            "score": 0.0,
            "reason": f"Hình ảnh bị nhiễu hạt kỹ thuật số quá mức (LapVar = {lap_var:.1f}).",
            "message_vi": "Ảnh chưa đủ rõ để kiểm tra. Hãy chụp gần hơn, đủ sáng và giữ lá trong khung hình.",
            "metrics": metrics
        }

    # 5. Botanical Multi-Spectral Analysis (HSV + Normalized RGB)
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

    # Band A: Green Foliage (Healthy or early lesion)
    green_mask = ((H >= 65.0) & (H <= 165.0) & (S >= 0.15)) | ((g_n > 0.36) & (2.0 * G - R - B > 5.0))
    green_ratio = float(green_mask.mean())
    metrics["green_ratio"] = round(green_ratio, 4)

    # Band B: Chlorotic Yellow Foliage (Vàng lá do nấm, virus hoặc thiếu vi lượng)
    yellow_mask = (H >= 35.0) & (H < 65.0) & (S >= 0.20) & (b_n < 0.26) & (r_n > 0.34) & (g_n > 0.32)
    yellow_ratio = float(yellow_mask.mean())
    metrics["yellow_ratio"] = round(yellow_ratio, 4)

    # Band C: Brown Necrotic / Senescent Dry Leaf Tissue (Đốm nâu hoại tử, cháy lá, lá khô)
    brown_mask = (H >= 15.0) & (H < 35.0) & (S >= 0.18) & (r_n > 0.40) & (g_n > 0.26) & (b_n < 0.22) & ((G - B) > 5.0)
    brown_ratio = float(brown_mask.mean())
    metrics["brown_ratio"] = round(brown_ratio, 4)

    # Combined Botanical Tissue
    botanical_tissue = green_mask | yellow_mask | brown_mask
    botanical_ratio = float(botanical_tissue.mean())
    metrics["botanical_ratio"] = round(botanical_ratio, 4)

    # Band D: Blue / Synthetic Fabric Dominance (Non-plant)
    blue_dom_mask = (b_n > 0.40) & (B > R + 12.0) & (B > G + 8.0)
    blue_ratio = float(blue_dom_mask.mean())
    metrics["blue_ratio"] = round(blue_ratio, 4)

    # Band E: Human Skin Profile
    r_g_diff = np.maximum(R - G, 0.1)
    skin_ratio_test = (R - B) / r_g_diff
    skin_mask = (H >= 0.0) & (H <= 25.0) & (S >= 0.15) & (S <= 0.65) & (R > G + 15.0) & (G > B + 8.0) & (skin_ratio_test >= 1.7) & (skin_ratio_test <= 4.2)
    skin_ratio = float(skin_mask.mean())
    metrics["skin_ratio"] = round(skin_ratio, 4)

    # Excess Green Index
    mean_exg = float((2.0 * G - R - B).mean())
    metrics["mean_exg"] = round(mean_exg, 2)

    # 6. NON-LEAF DETERMINATION (Part 1: NOT_A_LEAF)
    # A) Human Face / Skin Dominant
    if skin_ratio > 0.35 and botanical_ratio < 0.12:
        return {
            "status": "NOT_A_LEAF",
            "passed": False,
            "score": round(1.0 - skin_ratio, 4),
            "reason": f"Phát hiện bề mặt da người (tỷ lệ {skin_ratio*100:.1f}%), không phải lá cây.",
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # B) Synthetic Blue Fabric / Surface
    if blue_ratio > 0.35 and botanical_ratio < 0.12:
        return {
            "status": "NOT_A_LEAF",
            "passed": False,
            "score": round(1.0 - blue_ratio, 4),
            "reason": f"Phát hiện màu xanh nhân tạo hoặc vải bạt (tỷ lệ {blue_ratio*100:.1f}%), không phải mô thực vật.",
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # C) General Non-Plant Objects (Animals, cars, furniture, indoor items with no botanical tissue)
    if botanical_ratio < 0.12 and mean_exg < -15.0:
        return {
            "status": "NOT_A_LEAF",
            "passed": False,
            "score": round(botanical_ratio, 4),
            "reason": f"Không phát hiện mô thực vật (tỷ lệ mô sinh học = {botanical_ratio*100:.1f}%, ExG = {mean_exg:.1f}).",
            "message_vi": "Ảnh này không có lá cây phù hợp để chẩn đoán. Hãy tải ảnh chụp một chiếc lá.",
            "metrics": metrics
        }

    # 7. UNCERTAIN DETERMINATION (Part 1: UNCERTAIN)
    # Ambiguous botanical presence (distant foliage, partial greenery in clutter, borderline blur)
    if botanical_ratio < 0.22 or (lap_var < 22.0 and botanical_ratio < 0.30):
        return {
            "status": "UNCERTAIN",
            "passed": False,
            "score": round(botanical_ratio, 4),
            "reason": f"Dấu hiệu phiến lá không rõ ràng hoặc bị phân tán (tỷ lệ mô thực vật = {botanical_ratio*100:.1f}%).",
            "message_vi": "Gari chưa xác định được đây có phải ảnh lá cây hay không. Hãy chụp rõ một chiếc lá.",
            "metrics": metrics
        }

    # 8. VALID LEAF (Part 1: LEAF_VALID)
    leaf_score = min(1.0, round(float(botanical_ratio / 0.55), 4))
    return {
        "status": "LEAF_VALID",
        "passed": True,
        "score": leaf_score,
        "reason": "Ảnh lá cây hợp lệ, đạt tiêu chuẩn chẩn đoán nông học.",
        "message_vi": "Ảnh lá cây hợp lệ, sẵn sàng chẩn đoán.",
        "metrics": metrics
    }

# Test against available sample images
img_tomato = Image.open("test_leaf.jpg")
print("Tomato leaf result:", validate_leaf_gate(img_tomato))

img_coffee = Image.open("data/field_dataset/images/field_1793374087037_1a78f2_coffee.jpg")
print("Coffee leaf result:", validate_leaf_gate(img_coffee))

# Synthetic skin / face image
skin_arr = np.full((224, 224, 3), [220, 160, 140], dtype=np.uint8)
img_skin = Image.fromarray(skin_arr)
print("Skin/Face image result:", validate_leaf_gate(img_skin))

# Synthetic blue fabric image
blue_arr = np.full((224, 224, 3), [30, 80, 210], dtype=np.uint8)
img_blue = Image.fromarray(blue_arr)
print("Blue fabric result:", validate_leaf_gate(img_blue))

# Synthetic dark/blurry image
dark_arr = np.full((224, 224, 3), [10, 12, 10], dtype=np.uint8)
img_dark = Image.fromarray(dark_arr)
print("Dark image result:", validate_leaf_gate(img_dark))
