import io
import json
import os
import sys
import requests

sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8000"

print("======================================================================")
print("GARI AI LAB — END-TO-END MODEL ROUTING & INFERENCE VERIFICATION")
print("======================================================================")

# 1. Health Check
try:
    r = requests.get(f"{BASE_URL}/api/health", timeout=5)
    print(f"[1] Health Check: HTTP {r.status_code}")
    print(json.dumps(r.json(), indent=2, ensure_ascii=False))
except Exception as e:
    print(f"[1] Health Check FAILED: {e}")
    sys.exit(1)

# 2. Supported Crops Check (Scope to 7 priority crops)
try:
    r = requests.get(f"{BASE_URL}/api/plant/supported-crops", timeout=5)
    data = r.json()
    print(f"\n[2] Supported Crops (Total: {data.get('total_crops')}):")
    for c in data.get("crops", []):
        print(f"  • {c['name_vi']:12} | ID: {c['id']:10} | Có mô hình bệnh: {c['has_disease_model']} | Thư mục: {c.get('disease_model_dir')}")
except Exception as e:
    print(f"[2] Supported Crops FAILED: {e}")

# 3. Test Mode A (Auto) with test_leaf.jpg (Tomato leaf)
test_leaf_path = "test_leaf.jpg"
if os.path.exists(test_leaf_path):
    print(f"\n[3] TEST MODE A (Auto) — Uploading {test_leaf_path}...")
    with open(test_leaf_path, "rb") as f:
        files = {"image": ("test_leaf.jpg", f, "image/jpeg")}
        data = {"mode": "auto"}
        r = requests.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=data, timeout=60)
        res = r.json()
        print(f"  HTTP {r.status_code}")
        print(f"  Status:            {res.get('status')}")
        print(f"  Mode:              {res.get('mode')}")
        print(f"  Crop:              {res.get('crop_name_vi')} (ID: {res.get('crop_id')})")
        print(f"  Crop Score (ViT):  {res.get('crop_score')}")
        print(f"  Disease:           {res.get('disease_name_vi')} (Class: {res.get('disease_id')})")
        print(f"  Disease Score:     {res.get('disease_score')}")
        print(f"  Model Used:        {res.get('model_name')}")
        print(f"  Inference Time:    {res.get('inference_time_ms')} ms")
        print(f"  Grad-CAM Heatmap:  {res.get('attention_image_url')}")
        print(f"  Crop Candidates:   {json.dumps(res.get('crop_candidates', []), ensure_ascii=False)}")
else:
    print(f"\n[3] Warning: {test_leaf_path} not found.")

# 4. Test Mode B (Manual) with Coffee Leaf
coffee_leaf_path = "data/field_dataset/images/field_1793374087037_1a78f2_coffee.jpg"
if os.path.exists(coffee_leaf_path):
    print(f"\n[4] TEST MODE B (Manual) — Crop: 'coffee' with {coffee_leaf_path}...")
    with open(coffee_leaf_path, "rb") as f:
        files = {"image": ("coffee.jpg", f, "image/jpeg")}
        data = {"mode": "manual", "crop": "coffee"}
        r = requests.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=data, timeout=60)
        res = r.json()
        print(f"  HTTP {r.status_code}")
        print(f"  Status:            {res.get('status')}")
        print(f"  Mode:              {res.get('mode')}")
        print(f"  Crop:              {res.get('crop_name_vi')} (ID: {res.get('crop_id')})")
        print(f"  Disease:           {res.get('disease_name_vi')} (Class: {res.get('disease_id')})")
        print(f"  Disease Score:     {res.get('disease_score')}")
        print(f"  Model Used:        {res.get('model_name')}")
        print(f"  Inference Time:    {res.get('inference_time_ms')} ms")
        print(f"  Top Predictions:   {json.dumps(res.get('top_predictions', [])[:3], ensure_ascii=False)}")
else:
    print(f"\n[4] Warning: {coffee_leaf_path} not found.")

# 5. Test Mode B (Manual) with Durian (no disease model in models/)
print(f"\n[5] TEST MODE B (Manual) — Crop: 'durian' (no disease model)...")
dummy_img = io.BytesIO()
from PIL import Image
Image.new("RGB", (224, 224), (34, 139, 34)).save(dummy_img, format="JPEG")
dummy_bytes = dummy_img.getvalue()

files = {"image": ("durian.jpg", dummy_bytes, "image/jpeg")}
data = {"mode": "manual", "crop": "durian"}
r = requests.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=data, timeout=10)
res = r.json()
print(f"  HTTP {r.status_code}")
print(f"  Status:            {res.get('status')}")
print(f"  Mode:              {res.get('mode')}")
print(f"  Crop:              {res.get('crop_name_vi')} (ID: {res.get('crop_id')})")
print(f"  Message:           {res.get('message')}")
print(f"  Reason:            {res.get('reason')}")

# 6. Test Mode B (Manual) with Chili (no dedicated disease model directory in models/)
print(f"\n[6] TEST MODE B (Manual) — Crop: 'chili' (no disease model directory)...")
files = {"image": ("chili.jpg", dummy_bytes, "image/jpeg")}
data = {"mode": "manual", "crop": "chili"}
r = requests.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=data, timeout=10)
res = r.json()
print(f"  HTTP {r.status_code}")
print(f"  Status:            {res.get('status')}")
print(f"  Mode:              {res.get('mode')}")
print(f"  Crop:              {res.get('crop_name_vi')} (ID: {res.get('crop_id')})")
print(f"  Message:           {res.get('message')}")

# 7. Test Image Quality Rejection (Corrupt / Blank / Low Quality)
print(f"\n[7] TEST IMAGE VALIDATION — Low quality/corrupt input...")
blank_img = io.BytesIO()
Image.new("RGB", (30, 30), (0, 0, 0)).save(blank_img, format="JPEG")
files = {"image": ("tiny_blank.jpg", blank_img.getvalue(), "image/jpeg")}
data = {"mode": "auto"}
r = requests.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=data, timeout=10)
res = r.json()
print(f"  HTTP {r.status_code}")
print(f"  Status:            {res.get('status')}")
print(f"  Reason:            {res.get('reason')}")
print(f"  Message:           {res.get('message')}")

print("\n======================================================================")
print("TEST COMPLETED SUCCESSFULLY.")
print("======================================================================")
