import json
import os
import sys
from pathlib import Path
import torch
from safetensors.torch import load_file
import timm
from PIL import Image, ImageDraw, ImageFilter
import numpy as np

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

MODELS_DIR = Path("D:/leaf-diseases-detector-main/models")

def load_detector(rel_path):
    cfg_path = MODELS_DIR / rel_path / "config.json"
    weights_path = MODELS_DIR / rel_path / "model.safetensors"
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    net = timm.create_model(cfg["arch"], pretrained=False, num_classes=len(cfg["classes"]))
    state = load_file(str(weights_path))
    net.load_state_dict({k: v.float() for k, v in state.items()})
    net.eval()
    return net, cfg

def predict(net, cfg, img):
    if not isinstance(img, Image.Image):
        img = Image.open(img).convert("RGB")
    else:
        img = img.convert("RGB")
    img_resized = img.resize((224, 224), Image.BILINEAR)
    mean = np.array(cfg["mean"], dtype=np.float32)
    std = np.array(cfg["std"], dtype=np.float32)
    x = (np.asarray(img_resized, np.float32) / 255.0 - mean) / std
    tensor = torch.from_numpy(x.transpose(2, 0, 1)).float().unsqueeze(0)
    with torch.no_grad():
        logits = net(tensor)
        probs = torch.softmax(logits, dim=1)[0]
    top_indices = torch.argsort(probs, descending=True)[:5]
    return [(cfg["classes"][i], float(probs[i])) for i in top_indices]

net_orig, cfg_orig = load_detector("detectors/original")
net_new, cfg_new = load_detector("detectors/new")

pv = Path("data/organized/PlantVillage")
categories = [
    ("Pepper Bell Bacterial Spot", "Pepper__bell___Bacterial_spot/0022d6b7-d47c-4ee2-ae9a-392a53f48647___JR_B.Spot 8964.JPG"),
    ("Pepper Bell Healthy", "Pepper__bell___healthy/00100ffa-095e-4881-aebf-61fe5af7226e___JR_HL 7886.JPG"),
    ("Potato Early Blight", "Potato___Early_blight/001187a0-57ab-4329-baff-e7246a9edeb0___RS_Early.B 8178.JPG"),
    ("Potato Healthy", "Potato___healthy/00fc2ee5-729f-4757-8aeb-65c3355874f2___RS_HL 1864.JPG"),
    ("Potato Late Blight", "Potato___Late_blight/0051e5e8-d1c4-4a84-bf3a-a426cdad6285___RS_LB 4640.JPG"),
    ("Tomato Target Spot", "Tomato__Target_Spot/002213fb-b620-4593-b9ac-6a6cc119b100___Com.G_TgS_FL 8360.JPG"),
    ("Tomato Mosaic Virus", "Tomato__Tomato_mosaic_virus/000ec6ea-9063-4c33-8abe-d58ca8a88878___PSU_CG 2169.JPG"),
    ("Tomato Yellow Leaf Curl", "Tomato__Tomato_YellowLeaf__Curl_Virus/00139ae8-d881-4edb-925f-46584b0bd68c___YLCV_NREC 2944.JPG"),
    ("Tomato Bacterial Spot", "Tomato_Bacterial_spot/00416648-be6e-4bd4-bc8d-82f43f8a7240___GCREC_Bact.Sp 3110.JPG"),
    ("Tomato Early Blight", "Tomato_Early_blight/0012b9d2-2130-4a06-a834-b1f3af34f57e___RS_Erly.B 8389.JPG"),
    ("Tomato Healthy", "Tomato_healthy/000146ff-92a4-4db6-90ad-8fce2ae4fddd___GH_HL Leaf 259.1.JPG"),
    ("Tomato Late Blight", "Tomato_Late_blight/0003faa8-4b27-4c65-bf42-6d9e352ca1a5___RS_Late.B 4946.JPG"),
    ("Tomato Leaf Mold", "Tomato_Leaf_Mold/00694db7-3327-45e0-b4da-a8bb7ab6a4b7___Crnl_L.Mold 6923.JPG"),
    ("Tomato Septoria Leaf Spot", "Tomato_Septoria_leaf_spot/002533c1-722b-44e5-9d2e-91f7747b2543___Keller.St_CG 1831.JPG"),
    ("Tomato Spider Mites", "Tomato_Spider_mites_Two_spotted_spider_mite/002835d1-c18e-4471-aa6e-8d8c29585e9b___Com.G_SpM_FL 8584.JPG"),
]

print(f"{'Category':30s} | {'Det16 Top1':15s} {'Conf':>6s} | {'Det36 Top1':15s} {'Conf':>6s} | {'Det36 Top2':15s} {'Conf':>6s}")
print("-" * 95)
for name, rel_path in categories:
    img_path = pv / rel_path
    o = predict(net_orig, cfg_orig, img_path)
    n = predict(net_new, cfg_new, img_path)
    print(f"{name:30s} | {o[0][0]:15s} {o[0][1]*100:5.1f}% | {n[0][0]:15s} {n[0][1]*100:5.1f}% | {n[1][0]:15s} {n[1][1]*100:5.1f}%")

# Test synthetic non-leaf / OOD
print("\n--- Synthetic / Non-Leaf / Ambiguous Tests ---")
solid_white = Image.new("RGB", (256, 256), (255, 255, 255))
solid_green = Image.new("RGB", (256, 256), (34, 139, 34))
random_noise = Image.fromarray(np.random.randint(0, 256, (256, 256, 3), dtype=np.uint8))
blurry_img = Image.open(pv / categories[8][1]).filter(ImageFilter.GaussianBlur(radius=25))

for name, img in [("Solid White", solid_white), ("Solid Green", solid_green), ("Random Noise", random_noise), ("Severely Blurry Leaf", blurry_img)]:
    o = predict(net_orig, cfg_orig, img)
    n = predict(net_new, cfg_new, img)
    print(f"{name:30s} | {o[0][0]:15s} {o[0][1]*100:5.1f}% | {n[0][0]:15s} {n[0][1]*100:5.1f}% | {n[1][0]:15s} {n[1][1]*100:5.1f}%")
