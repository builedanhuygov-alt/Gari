import io
import time
import torch
import numpy as np
from PIL import Image
from transformers import AutoModelForImageClassification
import timm
from safetensors.torch import load_file
from pathlib import Path

MODELS_DIR = Path("models")

# 7 Priority Crops
PRIORITY_CROPS = {
    "coffee": {"id": "coffee", "name_vi": "Cà phê", "name_en": "Coffee", "model_dir": "Coffee", "has_model": True},
    "pepper": {"id": "pepper", "name_vi": "Hồ tiêu", "name_en": "Black Pepper", "model_dir": "Black_Pepper", "has_model": True},
    "rice": {"id": "rice", "name_vi": "Lúa", "name_en": "Rice", "model_dir": "Rice", "has_model": True},
    "durian": {"id": "durian", "name_vi": "Sầu riêng", "name_en": "Durian", "model_dir": None, "has_model": False},
    "tomato": {"id": "tomato", "name_vi": "Cà chua", "name_en": "Tomato", "model_dir": "Tomato", "has_model": True},
    "chili": {"id": "chili", "name_vi": "Ớt", "name_en": "Chili", "model_dir": None, "has_model": False},
    "maize": {"id": "maize", "name_vi": "Ngô", "name_en": "Maize", "model_dir": "Maize", "has_model": True},
}

print("Testing Model tong loading...")
t0 = time.time()
global_model = AutoModelForImageClassification.from_pretrained(str(MODELS_DIR / "Model tong"))
global_model.eval()
print(f"Model tong loaded in {time.time()-t0:.2f}s")

img = Image.open("test_leaf.jpg").convert("RGB").resize((224, 224))
x = (np.array(img, dtype=np.float32) / 255.0 - 0.5) / 0.5
t = torch.from_numpy(x.transpose(2, 0, 1)).unsqueeze(0).float()
with torch.no_grad():
    probs = torch.softmax(global_model(t).logits, dim=1)[0].numpy()

# Aggregate crop scores
crop_scores = {}
for i in range(len(probs)):
    label = global_model.config.id2label[i]
    crop_prefix = label.split("___")[0]
    crop_scores[crop_prefix] = crop_scores.get(crop_prefix, 0.0) + float(probs[i])

sorted_crops = sorted(crop_scores.items(), key=lambda x: x[1], reverse=True)
print("Top 3 identified crops from Model tong:")
for c, s in sorted_crops[:3]:
    print(f"  - {c}: {s*100:.2f}% (uncalibrated score: {s:.4f})")

# Test Tomato model
print("\nTesting Tomato ConvNeXt model...")
tomato_model = timm.create_model("convnext_small", pretrained=False, num_classes=13)
state = load_file(str(MODELS_DIR / "Tomato" / "model.safetensors"))
tomato_model.load_state_dict({k: v.float() for k, v in state.items()})
tomato_model.eval()

mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
x_conv = (np.array(img, dtype=np.float32) / 255.0 - mean) / std
t_conv = torch.from_numpy(x_conv.transpose(2, 0, 1)).unsqueeze(0).float()
with torch.no_grad():
    t_probs = torch.softmax(tomato_model(t_conv), dim=1)[0]
    t_top = torch.topk(t_probs, 3)
    print("Tomato top predictions:")
    for idx, p in zip(t_top.indices.tolist(), t_top.values.tolist()):
        print(f"  Class {idx}: {p*100:.2f}%")
