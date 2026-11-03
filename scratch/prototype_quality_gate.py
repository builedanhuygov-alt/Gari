import numpy as np
from PIL import Image, ImageFilter
import io

def botanical_leaf_quality_gate(img: Image.Image):
    """
    Evaluates image quality and botanical leaf characteristics.
    Accepts: green leaves, yellow chlorotic leaves, brown dry leaves, outdoor lighting.
    Rejects: human skin, colorful non-leaf fabric, food/bread, extreme dark, extreme blur.
    """
    metrics = {
        "width": float(img.width),
        "height": float(img.height),
        "mean_lum": 0.0,
        "lap_var": 0.0,
        "green_ratio": 0.0,
        "yellow_ratio": 0.0,
        "brown_ratio": 0.0,
        "botanical_tissue_ratio": 0.0,
        "skin_like_ratio": 0.0,
        "blue_dominance_ratio": 0.0,
    }

    if img.width < 64 or img.height < 64:
        return False, f"Kích thước ảnh quá nhỏ ({img.width}x{img.height} pixel). Cần tối thiểu 64x64 pixel.", metrics

    if img.width > 6000 or img.height > 6000:
        return False, f"Kích thước ảnh quá lớn ({img.width}x{img.height} pixel). Vui lòng giới hạn dưới 6000 pixel.", metrics

    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    R, G, B = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    # 1. Luminance
    lum = 0.299 * R + 0.587 * G + 0.114 * B
    mean_lum = float(lum.mean())
    metrics["mean_lum"] = round(mean_lum, 2)

    if mean_lum < 15.0:
        return False, f"Hình ảnh quá tối (độ sáng trung bình = {mean_lum:.1f}/255). Vui lòng chụp trong điều kiện ánh sáng tự nhiên đầy đủ.", metrics

    if mean_lum > 248.0:
        return False, f"Hình ảnh bị chói sáng hoặc phơi sáng quá mức (độ sáng trung bình = {mean_lum:.1f}/255). Vui lòng tránh ánh đèn flash trực tiếp.", metrics

    # 2. Color diversity
    color_std = float(arr.std())
    metrics["color_std"] = round(color_std, 2)
    if color_std < 5.0:
        return False, "Hình ảnh đơn sắc hoặc không có chi tiết phiến lá cây.", metrics

    # 3. Sharpness / Blur Check (Laplacian Variance)
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    lap = gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:] - 4.0 * gray[1:-1, 1:-1]
    lap_var = float(lap.var())
    metrics["lap_var"] = round(lap_var, 2)

    if lap_var < 12.0:
        return False, f"Hình ảnh quá mờ (độ sắc nét LapVar = {lap_var:.1f} < 12.0). Vui lòng chụp rõ nét hơn.", metrics

    # 4. Botanical Multi-Spectral Analysis (HSV + Normalized RGB)
    # Compute HSV
    max_c = np.maximum(np.maximum(R, G), B)
    min_c = np.minimum(np.minimum(R, G), B)
    delta = max_c - min_c + 1e-6

    # Hue in degrees [0, 360]
    H = np.zeros_like(max_c)
    mask_r = (max_c == R)
    mask_g = (max_c == G)
    mask_b = (max_c == B)
    H[mask_r] = (60.0 * ((G[mask_r] - B[mask_r]) / delta[mask_r]) + 360.0) % 360.0
    H[mask_g] = 60.0 * ((B[mask_g] - R[mask_g]) / delta[mask_g]) + 120.0
    H[mask_b] = 60.0 * ((R[mask_b] - G[mask_b]) / delta[mask_b]) + 240.0

    # Saturation [0, 1]
    S = delta / (max_c + 1e-6)
    # Value [0, 255]
    V = max_c

    tot_rgb = R + G + B + 1e-6
    r_n, g_n, b_n = R / tot_rgb, G / tot_rgb, B / tot_rgb

    # Band A: Green Foliage (Healthy or early lesion)
    # Hue ~ 65 to 165, with moderate saturation, or ExG > 0
    green_mask = ((H >= 65.0) & (H <= 165.0) & (S >= 0.15)) | ((g_n > 0.36) & (2.0 * G - R - B > 5.0))
    green_ratio = float(green_mask.mean())
    metrics["green_ratio"] = round(green_ratio, 4)

    # Band B: Chlorotic Yellow Foliage (Vàng lá, thiếu vi lượng, virus khảm)
    # Hue ~ 35 to 65, Saturation >= 0.20, G and R both high, B low
    yellow_mask = (H >= 35.0) & (H < 65.0) & (S >= 0.20) & (b_n < 0.26) & (r_n > 0.34) & (g_n > 0.32)
    yellow_ratio = float(yellow_mask.mean())
    metrics["yellow_ratio"] = round(yellow_ratio, 4)

    # Band C: Brown Necrotic / Senescent Dry Leaf Tissue (Đốm hoại tử, cháy lá, lá khô)
    # Hue ~ 15 to 35, Saturation in [0.20, 0.75], R > G > B, B is significantly lower than G (not skin-like pink)
    brown_mask = (H >= 15.0) & (H < 35.0) & (S >= 0.18) & (r_n > 0.40) & (g_n > 0.26) & (b_n < 0.22) & ((G - B) > 8.0)
    brown_ratio = float(brown_mask.mean())
    metrics["brown_ratio"] = round(brown_ratio, 4)

    # Combined Botanical Tissue Ratio
    botanical_tissue = green_mask | yellow_mask | brown_mask
    botanical_ratio = float(botanical_tissue.mean())
    metrics["botanical_tissue_ratio"] = round(botanical_ratio, 4)

    # Band D: Blue / Synthetic Fabric Dominance (Non-plant)
    blue_dom_mask = (b_n > 0.42) & (B > R + 15.0) & (B > G + 10.0)
    blue_ratio = float(blue_dom_mask.mean())
    metrics["blue_dominance_ratio"] = round(blue_ratio, 4)

    # Band E: Human Skin Profile
    # Skin has R > G > B with specific ratio, H in [0, 25], S in [0.15, 0.65], and (R-B)/(R-G) between 1.8 and 3.8
    r_g_diff = np.maximum(R - G, 0.1)
    skin_ratio_test = (R - B) / r_g_diff
    skin_mask = (H >= 0.0) & (H <= 25.0) & (S >= 0.15) & (S <= 0.65) & (R > G + 15.0) & (G > B + 8.0) & (skin_ratio_test >= 1.7) & (skin_ratio_test <= 4.2)
    skin_ratio = float(skin_mask.mean())
    metrics["skin_like_ratio"] = round(skin_ratio, 4)

    # REJECTION RULES:
    # 1. Blue fabric dominance
    if blue_ratio > 0.40:
        return False, "Hình ảnh có màu xanh nhân tạo hoặc vải bạt, không có cấu trúc quang phổ thực vật.", metrics

    # 2. Human skin dominance
    if skin_ratio > 0.45 and botanical_ratio < 0.15:
        return False, "Hình ảnh nhận diện là bề mặt da người hoặc không phải bộ phận cây trồng. Vui lòng chụp đúng lá cây.", metrics

    # 3. Baked food / Bread / Cardboard check
    # Pure brown with zero green (< 0.015), zero yellow (< 0.02), and deeply negative ExG (< -15.0)
    mean_exg = float((2.0 * G - R - B).mean())
    if brown_ratio > 0.40 and green_ratio < 0.015 and yellow_ratio < 0.02 and mean_exg < -15.0:
        return False, "Hình ảnh có đặc điểm của thực phẩm chế biến hoặc vật thể phi thực vật.", metrics

    # 4. Overall Botanical Content (Accepts green, chlorotic yellow, and necrotic brown leaves)
    if botanical_ratio < 0.18:
        return False, "Hình ảnh không có đủ dấu hiệu của mô thực vật (lá xanh, lá vàng đốm bệnh hoặc lá khô hoại tử). Vui lòng chụp rõ một chiếc lá cây.", metrics

    return True, "Chất lượng ảnh đạt tiêu chuẩn chẩn đoán nông học.", metrics
