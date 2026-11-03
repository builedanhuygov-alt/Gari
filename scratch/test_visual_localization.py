import io
import os
import sys
from pathlib import Path
import numpy as np
import cv2
from PIL import Image
import torch

WORKSPACE = Path("D:/leaf-diseases-detector-main")
sys.path.insert(0, str(WORKSPACE))

from gari_inference_engine import engine

test_img_path = WORKSPACE / "data/organized/PlantVillage/Potato___Early_blight/001187a0-57ab-4329-baff-e7246a9edeb0___RS_Early.B 8178.JPG"
print("Testing visual localization on:", test_img_path)

pil_img = Image.open(test_img_path).convert("RGB")
img_w, img_h = pil_img.size

# Load Potato model
net, entry = engine.load_model("Potato")
print("Loaded model:", entry.crop_id, entry.arch)

# 1. Grad-CAM test
activations = []
gradients = []

def forward_hook(module, input, output):
    activations.append(output)

def backward_hook(module, grad_input, grad_output):
    gradients.append(grad_output[0])

target_layer = net.stages[3].blocks[-1]
h1 = target_layer.register_forward_hook(forward_hook)
h2 = target_layer.register_full_backward_hook(backward_hook)

tensor = entry.preprocess(pil_img).to(engine.device)
tensor.requires_grad = True

net.zero_grad()
logits = net(tensor)
pred_idx = torch.argmax(logits, dim=1).item()
pred_class = entry.classes[pred_idx]
print(f"Predicted class: {pred_class} (index {pred_idx})")

score = logits[0, pred_idx]
score.backward()

h1.remove()
h2.remove()

act = activations[0].detach().cpu().numpy()[0] # [C, H, W]
grad = gradients[0].detach().cpu().numpy()[0] # [C, H, W]
weights = np.mean(grad, axis=(1, 2)) # [C]

cam = np.zeros(act.shape[1:], dtype=np.float32)
for i, w in enumerate(weights):
    cam += w * act[i]

cam = np.maximum(cam, 0)
if cam.max() > 0:
    cam = cam / cam.max()

cam_resized = cv2.resize(cam, (img_w, img_h))
heatmap = cv2.applyColorMap(np.uint8(255 * cam_resized), cv2.COLORMAP_JET)
heatmap_rgb = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)

np_img = np.array(pil_img)
overlay_cam = np.uint8(0.55 * np_img + 0.45 * heatmap_rgb)

out_cam_path = WORKSPACE / "database/uploads/test_cam.jpg"
out_cam_path.parent.mkdir(parents=True, exist_ok=True)
Image.fromarray(overlay_cam).save(out_cam_path)
print("Saved Grad-CAM attention overlay to:", out_cam_path)

# 2. Pathology Lesion Region Extractor test
img_np = np.array(pil_img)
img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)

# Leaf mask: exclude very bright neutral background
# In PlantVillage, background is usually light grey/white (low S, high V)
leaf_mask = (hsv[:, :, 1] > 25) & (hsv[:, :, 2] < 245)
# Further refine leaf: foliage hues (green to yellow-brown, 10 to 95 in OpenCV HSV)
leaf_mask = leaf_mask & ((hsv[:, :, 0] >= 10) & (hsv[:, :, 0] <= 95) | (lab[:, :, 1] < 125))
leaf_mask_uint8 = np.uint8(leaf_mask * 255)

# Necrotic lesions: dark brown/black spots inside leaf mask
l_channel = lab[:, :, 0]
if np.sum(leaf_mask) > 100:
    leaf_l_vals = l_channel[leaf_mask]
    median_l = np.median(leaf_l_vals)
    necrotic_mask = leaf_mask & (l_channel < (median_l - 28))
    # Chlorosis mask: yellowing (high b in LAB)
    b_channel = lab[:, :, 2]
    leaf_b_vals = b_channel[leaf_mask]
    median_b = np.median(leaf_b_vals)
    chlorosis_mask = leaf_mask & (b_channel > (median_b + 22)) & (l_channel >= (median_l - 28))
else:
    necrotic_mask = np.zeros_like(leaf_mask)
    chlorosis_mask = np.zeros_like(leaf_mask)

# Cleanup morphological noise
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
necrotic_clean = cv2.morphologyEx(np.uint8(necrotic_mask * 255), cv2.MORPH_OPEN, kernel)
chlorosis_clean = cv2.morphologyEx(np.uint8(chlorosis_mask * 255), cv2.MORPH_OPEN, kernel)

# Find contours
contours_nec, _ = cv2.findContours(necrotic_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
contours_chl, _ = cv2.findContours(chlorosis_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

candidates = []
for c in contours_nec:
    area = cv2.contourArea(c)
    if area >= 30: # at least 30 px
        x, y, w, h = cv2.boundingRect(c)
        candidates.append({
            "type": "necrotic_spot",
            "box": [x, y, w, h],
            "area": area,
            "type_vi": "Đốm nâu hoại tử",
            "desc_vi": "Xuất hiện đốm nâu sẫm, nghi có dấu hiệu tổn thương mô lá.",
            "severity": "Cảnh báo"
        })

for c in contours_chl:
    area = cv2.contourArea(c)
    if area >= 40:
        x, y, w, h = cv2.boundingRect(c)
        candidates.append({
            "type": "chlorosis",
            "box": [x, y, w, h],
            "area": area,
            "type_vi": "Vùng vàng lá / Biến màu",
            "desc_vi": "Vùng lá bị vàng hóa hoặc biến đổi sắc tố do suy giảm diệp lục.",
            "severity": "Theo dõi"
        })

candidates.sort(key=lambda item: item["area"], reverse=True)
top_regions = candidates[:4]
for idx, r in enumerate(top_regions, 1):
    r["id"] = idx
    r["title_vi"] = f"Vùng {idx}: {r['type_vi']}"
    r["box_norm"] = [
        round(r["box"][0] / img_w, 4),
        round(r["box"][1] / img_h, 4),
        round(r["box"][2] / img_w, 4),
        round(r["box"][3] / img_h, 4)
    ]

print(f"Extracted {len(top_regions)} suspicious lesion regions:")
for r in top_regions:
    print(f" - {r['title_vi']} at box {r['box']} (area {r['area']}px): {r['desc_vi']}")

# Draw annotated overlay
overlay_img = img_np.copy()
for r in top_regions:
    x, y, w, h = r["box"]
    # Draw translucent box
    box_color = (239, 68, 68) if r["type"] == "necrotic_spot" else (245, 158, 11)
    cv2.rectangle(overlay_img, (x, y), (x + w, y + h), box_color, 2)
    # Put badge
    badge_text = f"Vung {r['id']}"
    cv2.rectangle(overlay_img, (x, max(0, y - 22)), (x + 65, max(0, y)), box_color, -1)
    cv2.putText(overlay_img, badge_text, (x + 4, max(14, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

out_overlay_path = WORKSPACE / "database/uploads/test_overlay.jpg"
Image.fromarray(overlay_img).save(out_overlay_path)
print("Saved lesion overlay image to:", out_overlay_path)
