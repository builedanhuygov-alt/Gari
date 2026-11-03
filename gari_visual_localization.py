"""
GARI AI LAB — Plant Intelligence Engine
Visual Disease Localization Module (Part 5)
Provides:
1. Grad-CAM Neural Attention Heatmap Visualization (ConvNeXt & ViT)
2. Computer Vision Pathology Region Extraction (Necrosis & Chlorosis Bounding Boxes)
3. Dual-View & Annotated Overlay Image Generation
4. Standardized Vietnamese Pathology Region Metadata
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch
from PIL import Image

logger = logging.getLogger("gari_visual_localization")

ATTENTION_DISCLAIMER_VI = (
    "Grad-CAM là bản đồ vùng chú ý của mạng nơ-ron (Model Attention), cho biết khu vực mô hình "
    "tập trung quan sát nhất khi đưa ra dự đoán, không phải là ranh giới phân đoạn tế bào bệnh tuyệt đối."
)


def compute_gradcam(
    net: torch.nn.Module,
    entry: Any,
    image: Image.Image,
    target_class_idx: Optional[int] = None,
    device: Optional[torch.device] = None,
) -> Tuple[np.ndarray, Image.Image]:
    """
    Computes Grad-CAM attention heatmap for ConvNeXt classification models.
    Backpropagates gradient of target class into final feature stage (stages[3].blocks[-1]).
    Returns:
        (cam_normalized_0_1, pil_overlay_image)
    """
    if device is None:
        device = next(net.parameters()).device

    img_w, img_h = image.size
    activations: List[torch.Tensor] = []
    gradients: List[torch.Tensor] = []

    def forward_hook(module, inp, out):
        activations.append(out)

    def backward_hook(module, grad_in, grad_out):
        gradients.append(grad_out[0])

    # Find the target layer in ConvNeXt or generic CNN
    target_layer = None
    if hasattr(net, "stages") and len(net.stages) > 3:
        target_layer = net.stages[3].blocks[-1]
    elif hasattr(net, "stages") and len(net.stages) > 0:
        target_layer = net.stages[-1]
    elif hasattr(net, "features"):
        target_layer = net.features[-1]

    if target_layer is None:
        # Fallback if layer cannot be hooked
        blank = np.zeros((img_h, img_w), dtype=np.float32)
        return blank, image.copy()

    h_fwd = target_layer.register_forward_hook(forward_hook)
    h_bwd = target_layer.register_full_backward_hook(backward_hook)

    net.eval()
    tensor = entry.preprocess(image).to(device)
    tensor.requires_grad = True

    net.zero_grad()
    logits = net(tensor)

    if target_class_idx is None:
        target_class_idx = int(torch.argmax(logits, dim=1).item())

    score = logits[0, target_class_idx]
    score.backward()

    h_fwd.remove()
    h_bwd.remove()

    if not activations or not gradients:
        blank = np.zeros((img_h, img_w), dtype=np.float32)
        return blank, image.copy()

    act = activations[0].detach().cpu().numpy()[0]  # [C, H, W]
    grad = gradients[0].detach().cpu().numpy()[0]   # [C, H, W]
    weights = np.mean(grad, axis=(1, 2))            # [C]

    cam = np.zeros(act.shape[1:], dtype=np.float32)
    for i, w in enumerate(weights):
        cam += w * act[i]

    cam = np.maximum(cam, 0)
    if cam.max() > 0:
        cam = cam / cam.max()

    cam_resized = cv2.resize(cam, (img_w, img_h), interpolation=cv2.INTER_LINEAR)
    heatmap_bgr = cv2.applyColorMap(np.uint8(255 * cam_resized), cv2.COLORMAP_JET)
    heatmap_rgb = cv2.cvtColor(heatmap_bgr, cv2.COLOR_BGR2RGB)

    orig_np = np.array(image.convert("RGB"))
    blended = np.uint8(0.52 * orig_np + 0.48 * heatmap_rgb)
    pil_overlay = Image.fromarray(blended)

    return cam_resized, pil_overlay


def extract_pathology_regions(
    image: Image.Image,
    max_regions: int = 5,
    min_area_px: int = 35,
) -> Tuple[List[Dict[str, Any]], Image.Image]:
    """
    Extracts suspicious pathology lesion regions on the leaf blade using color-space
    segmentation (necrotic dark spots and chlorotic yellow halos).
    Returns:
        (regions_metadata_list, pil_annotated_overlay_image)
    """
    img_rgb = np.array(image.convert("RGB"))
    img_w, img_h = image.size
    img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)

    # 1. Segment the leaf blade from neutral or white background
    # Vegetation mask: saturation > 20, value < 248, hue in plant palette
    leaf_mask = (hsv[:, :, 1] > 20) & (hsv[:, :, 2] < 248)
    leaf_mask = leaf_mask & (
        ((hsv[:, :, 0] >= 10) & (hsv[:, :, 0] <= 100)) | (lab[:, :, 1] < 128)
    )

    total_leaf_pixels = int(np.sum(leaf_mask))
    regions: List[Dict[str, Any]] = []
    overlay_rgb = img_rgb.copy()

    if total_leaf_pixels < 200:
        # If leaf mask is negligible, analyze full image center
        center_mask = np.zeros((img_h, img_w), dtype=bool)
        center_mask[int(img_h * 0.15) : int(img_h * 0.85), int(img_w * 0.15) : int(img_w * 0.85)] = True
        leaf_mask = center_mask

    l_channel = lab[:, :, 0]
    b_channel = lab[:, :, 2]
    leaf_l = l_channel[leaf_mask]
    leaf_b = b_channel[leaf_mask]

    med_l = float(np.median(leaf_l)) if len(leaf_l) > 0 else 128.0
    med_b = float(np.median(leaf_b)) if len(leaf_b) > 0 else 128.0

    # Necrotic dark lesions: luminance significantly below parenchyma median
    necrotic_mask = leaf_mask & (l_channel < (med_l - 26))

    # Chlorotic yellowing halo: yellow chroma higher than parenchyma median
    chlorosis_mask = leaf_mask & (b_channel > (med_b + 20)) & (l_channel >= (med_l - 26))

    # Morphological opening to suppress single-pixel sensor noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    necrotic_clean = cv2.morphologyEx(np.uint8(necrotic_mask * 255), cv2.MORPH_OPEN, kernel)
    chlorosis_clean = cv2.morphologyEx(np.uint8(chlorosis_mask * 255), cv2.MORPH_OPEN, kernel)

    cnts_nec, _ = cv2.findContours(necrotic_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts_chl, _ = cv2.findContours(chlorosis_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates: List[Dict[str, Any]] = []

    for c in cnts_nec:
        area = cv2.contourArea(c)
        if area >= min_area_px:
            x, y, w, h = cv2.boundingRect(c)
            # Add slight padding
            pad_x = max(2, int(w * 0.1))
            pad_y = max(2, int(h * 0.1))
            bx = max(0, x - pad_x)
            by = max(0, y - pad_y)
            bw = min(img_w - bx, w + 2 * pad_x)
            bh = min(img_h - by, h + 2 * pad_y)
            candidates.append({
                "type": "necrotic_spot",
                "box": [bx, by, bw, bh],
                "area": area,
                "type_vi": "Đốm nâu hoại tử",
                "desc_vi": "Xuất hiện đốm nâu sẫm, nghi có dấu hiệu tổn thương tế bào mô lá.",
                "severity": "Cảnh báo",
            })

    for c in cnts_chl:
        area = cv2.contourArea(c)
        if area >= (min_area_px * 1.2):
            x, y, w, h = cv2.boundingRect(c)
            pad_x = max(2, int(w * 0.1))
            pad_y = max(2, int(h * 0.1))
            bx = max(0, x - pad_x)
            by = max(0, y - pad_y)
            bw = min(img_w - bx, w + 2 * pad_x)
            bh = min(img_h - by, h + 2 * pad_y)
            candidates.append({
                "type": "chlorosis_halo",
                "box": [bx, by, bw, bh],
                "area": area,
                "type_vi": "Quầng vàng / Biến đổi màu",
                "desc_vi": "Vùng lá bị vàng hóa hoặc biến đổi sắc tố do suy giảm diệp lục tố.",
                "severity": "Theo dõi",
            })

    # Sort candidates by area descending
    candidates.sort(key=lambda item: item["area"], reverse=True)
    selected = candidates[:max_regions]

    for idx, r in enumerate(selected, 1):
        r["id"] = idx
        r["title_vi"] = f"Vùng {idx}: {r['type_vi']}"
        bx, by, bw, bh = r["box"]
        r["box_norm"] = [
            round(bx / img_w, 4),
            round(by / img_h, 4),
            round(bw / img_w, 4),
            round(bh / img_h, 4),
        ]
        regions.append(r)

        # Draw on overlay image
        color = (239, 68, 68) if r["type"] == "necrotic_spot" else (245, 158, 11)
        # Bounding box
        cv2.rectangle(overlay_rgb, (bx, by), (bx + bw, by + bh), color, 2)
        # Header badge
        badge_w = min(75, bw)
        badge_h = min(22, max(16, int(bh * 0.25)))
        cv2.rectangle(overlay_rgb, (bx, max(0, by - 22)), (bx + 70, max(0, by)), color, -1)
        cv2.putText(
            overlay_rgb,
            f"Vung {idx}",
            (bx + 4, max(14, by - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    pil_overlay = Image.fromarray(overlay_rgb)
    return regions, pil_overlay


def generate_visual_localization_bundle(
    net: Optional[torch.nn.Module],
    entry: Any,
    image: Image.Image,
    output_dir: Path,
    file_prefix: str,
    target_class_idx: Optional[int] = None,
    device: Optional[torch.device] = None,
) -> Dict[str, Any]:
    """
    Coordinates full visual disease localization:
    - Generates and saves Grad-CAM attention overlay (leaf_{id}_attention.png)
    - Generates and saves Lesion bounding box overlay (leaf_{id}_overlay.png)
    - Returns structured regions array and web URLs.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    img_w, img_h = image.size

    attention_filename = f"{file_prefix}_attention.png"
    overlay_filename = f"{file_prefix}_overlay.png"

    attention_path = output_dir / attention_filename
    overlay_path = output_dir / overlay_filename

    # 1. Grad-CAM (if CNN model available)
    try:
        if net is not None and entry is not None and hasattr(net, "stages"):
            _, cam_overlay = compute_gradcam(
                net, entry, image, target_class_idx=target_class_idx, device=device
            )
            cam_overlay.save(attention_path, format="PNG")
            has_cam = True
        else:
            # ViT or non-CNN fallback: produce a clean copy
            image.save(attention_path, format="PNG")
            has_cam = False
    except Exception as exc:
        logger.warning("Grad-CAM generation failed: %s", exc)
        image.save(attention_path, format="PNG")
        has_cam = False

    # 2. Pathology Lesion Extraction
    try:
        regions, lesion_overlay = extract_pathology_regions(image)
        lesion_overlay.save(overlay_path, format="PNG")
    except Exception as exc:
        logger.warning("Pathology region extraction failed: %s", exc)
        regions = []
        image.save(overlay_path, format="PNG")

    return {
        "success": True,
        "method": "gradcam_and_pathology_regions",
        "has_attention_map": has_cam,
        "disclaimer_vi": ATTENTION_DISCLAIMER_VI,
        "attention_image_url": f"/uploads/{attention_filename}",
        "overlay_image_url": f"/uploads/{overlay_filename}",
        "regions_count": len(regions),
        "regions": regions,
        "image_dimensions": {"width": img_w, "height": img_h},
    }
