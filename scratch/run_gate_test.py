import sys
from pathlib import Path
from PIL import Image, ImageFilter
import numpy as np

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

import scratch.test_pipeline_logic as tpl
from scratch.test_detectors import load_detector

net_orig, cfg_orig = load_detector("detectors/original")
net_new, cfg_new = load_detector("detectors/new")

gate = tpl.CropValidationGate(net_orig, cfg_orig, net_new, cfg_new)

test_cases = [
    ("Tomato Bacterial Spot", Image.open("data/organized/PlantVillage/Tomato_Bacterial_spot/00416648-be6e-4bd4-bc8d-82f43f8a7240___GCREC_Bact.Sp 3110.JPG")),
    ("Potato Early Blight", Image.open("data/organized/PlantVillage/Potato___Early_blight/001187a0-57ab-4329-baff-e7246a9edeb0___RS_Early.B 8178.JPG")),
    ("Pepper Bell Bacterial Spot", Image.open("data/organized/PlantVillage/Pepper__bell___Bacterial_spot/0022d6b7-d47c-4ee2-ae9a-392a53f48647___JR_B.Spot 8964.JPG")),
    ("Tomato Late Blight (Confusable with Potato)", Image.open("data/organized/PlantVillage/Tomato_Late_blight/0003faa8-4b27-4c65-bf42-6d9e352ca1a5___RS_Late.B 4946.JPG")),
    ("Solid Green", Image.new("RGB", (256, 256), (34, 139, 34))),
    ("Blurry Tomato Leaf", Image.open("data/organized/PlantVillage/Tomato_Bacterial_spot/00416648-be6e-4bd4-bc8d-82f43f8a7240___GCREC_Bact.Sp 3110.JPG").filter(ImageFilter.GaussianBlur(25))),
]

for name, img in test_cases:
    res = gate.evaluate_crop(img)
    print(f"\n=== {name} ===")
    print(f"  State: {res['state']}")
    print(f"  Selected Crop: {res['selected_crop']}")
    print(f"  Confidence: {res.get('confidence', 0)*100:.1f}%")
    print(f"  Reason: {res['reason']}")
    if res["candidates"]:
        cand_list = [f"{c['crop']} ({c['percent']}%)" for c in res["candidates"][:3]]
        print(f"  Top candidates: {', '.join(cand_list)}")
