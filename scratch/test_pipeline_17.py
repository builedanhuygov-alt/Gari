import os
import sys
import json
import io
import urllib.request
import urllib.error
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
import numpy as np

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = r"D:\leaf-diseases-detector-main"
TEST_IMG_DIR = os.path.join(BASE_DIR, "data", "test_samples_17")
os.makedirs(TEST_IMG_DIR, exist_ok=True)

# 1. Source existing leaf images from dataset
healthy_src = os.path.join(BASE_DIR, "data", "organized", "PlantVillage", "Tomato_healthy", "000146ff-92a4-4db6-90ad-8fce2ae4fddd___GH_HL Leaf 259.1.JPG")
diseased_src = os.path.join(BASE_DIR, "data", "organized", "PlantVillage", "Tomato_Early_blight", "0012b9d2-2130-4a06-a834-b1f3af34f57e___RS_Erly.B 8389.JPG")
yellow_src = os.path.join(BASE_DIR, "data", "organized", "PlantVillage", "Tomato__Tomato_YellowLeaf__Curl_Virus", "00139ae8-d881-4edb-925f-46584b0bd68c___YLCV_NREC 2944.JPG")
brown_src = os.path.join(BASE_DIR, "data", "organized", "PlantVillage", "Tomato_Late_blight", "0003faa8-4b27-4c65-bf42-6d9e352ca1a5___RS_Late.B 4946.JPG")
potato_src = os.path.join(BASE_DIR, "data", "organized", "PlantVillage", "Potato___healthy", "00fc2ee5-729f-4757-8aeb-65c3355874f2___RS_HL 1864.JPG")

# Prepare test image dictionary
test_images = {}

# Test 1: Clear healthy leaf
test_images[1] = ("1_healthy_leaf.jpg", healthy_src)

# Test 2: Diseased leaf with spots
test_images[2] = ("2_diseased_leaf.jpg", diseased_src)

# Test 3: Yellow leaf
test_images[3] = ("3_yellow_leaf.jpg", yellow_src)

# Test 4: Brown or dry leaf
test_images[4] = ("4_brown_dry_leaf.jpg", brown_src)

# Test 5: Non-leaf image (geometric pattern / blue desk)
p5 = os.path.join(TEST_IMG_DIR, "5_non_leaf.jpg")
img5 = Image.new("RGB", (256, 256), color=(40, 80, 160))
d5 = ImageDraw.Draw(img5)
d5.rectangle([(30, 30), (220, 220)], fill=(70, 110, 190), outline=(200, 200, 255), width=4)
d5.line([(0, 0), (256, 256)], fill=(220, 220, 240), width=3)
img5.save(p5, quality=95)
test_images[5] = ("5_non_leaf.jpg", p5)

# Test 6: Human face image
p6 = os.path.join(TEST_IMG_DIR, "6_human_face.jpg")
img6 = Image.new("RGB", (256, 256), color=(230, 210, 190))
d6 = ImageDraw.Draw(img6)
# Face oval (skin color)
d6.ellipse([(48, 30), (208, 226)], fill=(225, 175, 140), outline=(180, 120, 90), width=2)
# Hair
d6.chord([(45, 20), (211, 140)], 180, 360, fill=(40, 25, 20))
# Eyes
d6.ellipse([(80, 95), (105, 110)], fill=(255, 255, 255))
d6.ellipse([(88, 98), (98, 108)], fill=(30, 20, 20))
d6.ellipse([(151, 95), (176, 110)], fill=(255, 255, 255))
d6.ellipse([(158, 98), (168, 108)], fill=(30, 20, 20))
# Nose & Mouth
d6.line([(128, 115), (124, 145)], fill=(170, 110, 80), width=2)
d6.line([(124, 145), (134, 145)], fill=(170, 110, 80), width=2)
d6.arc([(105, 160), (151, 185)], 0, 180, fill=(180, 60, 60), width=3)
img6.save(p6, quality=95)
test_images[6] = ("6_human_face.jpg", p6)

# Test 7: Animal image (fur texture / pet)
p7 = os.path.join(TEST_IMG_DIR, "7_animal.jpg")
img7 = Image.new("RGB", (256, 256), color=(180, 140, 100))
d7 = ImageDraw.Draw(img7)
# Animal fur / head
d7.ellipse([(50, 50), (206, 206)], fill=(150, 100, 60), outline=(100, 70, 40), width=2)
# Ears
d7.polygon([(60, 60), (40, 20), (90, 45)], fill=(130, 80, 50))
d7.polygon([(196, 60), (216, 20), (166, 45)], fill=(130, 80, 50))
# Whiskers and snout
d7.ellipse([(108, 130), (148, 160)], fill=(60, 40, 30))
img7.save(p7, quality=95)
test_images[7] = ("7_animal.jpg", p7)

# Test 8: General object image (red coffee cup)
p8 = os.path.join(TEST_IMG_DIR, "8_general_object.jpg")
img8 = Image.new("RGB", (256, 256), color=(240, 240, 240))
d8 = ImageDraw.Draw(img8)
# Red ceramic cup
d8.rectangle([(70, 80), (170, 200)], fill=(210, 40, 40), outline=(160, 20, 20), width=2)
d8.arc([(155, 100), (205, 170)], 270, 90, fill=(210, 40, 40), width=8)
img8.save(p8, quality=95)
test_images[8] = ("8_general_object.jpg", p8)

# Test 9: Blurry leaf image (Gaussian blur on healthy leaf)
p9 = os.path.join(TEST_IMG_DIR, "9_blurry_leaf.jpg")
img_orig = Image.open(healthy_src)
img9 = img_orig.filter(ImageFilter.GaussianBlur(radius=14))
img9.save(p9, quality=90)
test_images[9] = ("9_blurry_leaf.jpg", p9)

# Test 10: Low-light leaf image (darkened healthy leaf, luminance < 40)
p10 = os.path.join(TEST_IMG_DIR, "10_low_light_leaf.jpg")
enhancer = ImageEnhance.Brightness(img_orig)
img10 = enhancer.enhance(0.12)
img10.save(p10, quality=90)
test_images[10] = ("10_low_light_leaf.jpg", p10)

# Test 11: Multiple leaves
p11 = os.path.join(TEST_IMG_DIR, "11_multiple_leaves.jpg")
img11 = Image.new("RGB", (512, 256), color=(250, 250, 250))
img_dis = Image.open(diseased_src).resize((256, 256))
img_hea = Image.open(healthy_src).resize((256, 256))
img11.paste(img_dis, (0, 0))
img11.paste(img_hea, (256, 0))
img11.save(p11, quality=90)
test_images[11] = ("11_multiple_leaves.jpg", p11)

# Test 12: Unknown crop (Potato leaf outside 7 priority crops)
test_images[12] = ("12_potato_unknown_crop.jpg", potato_src)

# Test 13: Missing crop-specific disease model (Chili in manual mode)
p13 = os.path.join(BASE_DIR, "data", "organized", "PlantVillage", "Pepper__bell___healthy", "00100ffa-095e-4881-aebf-61fe5af7226e___JR_HL 7886.JPG")
test_images[13] = ("13_chili_leaf.jpg", p13)

# Test 14: Standard global model (auto_standard on healthy tomato)
test_images[14] = ("14_standard_global.jpg", healthy_src)

# Test 15: Pro global model (auto_pro with Dev Pro auth on healthy tomato)
test_images[15] = ("15_pro_global.jpg", healthy_src)

# Test 16: Manual crop mode (tomato on diseased tomato)
test_images[16] = ("16_manual_tomato.jpg", diseased_src)

# Test 17: Pro access restriction (auto_pro without Dev Pro auth)
test_images[17] = ("17_pro_restriction.jpg", healthy_src)

print(f"Prepared all 17 test images in {TEST_IMG_DIR}")

# Test runner helper
def send_diagnose_request(img_path, mode, crop=None, dev_pro=False):
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = io.BytesIO()

    # file
    filename = os.path.basename(img_path)
    body.write(f"--{boundary}\r\n".encode("utf-8"))
    body.write(f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'.encode("utf-8"))
    body.write(b"Content-Type: image/jpeg\r\n\r\n")
    with open(img_path, "rb") as f:
        body.write(f.read())
    body.write(b"\r\n")

    # mode
    body.write(f"--{boundary}\r\n".encode("utf-8"))
    body.write(f'Content-Disposition: form-data; name="mode"\r\n\r\n'.encode("utf-8"))
    body.write(mode.encode("utf-8"))
    body.write(b"\r\n")

    # crop
    if crop:
        body.write(f"--{boundary}\r\n".encode("utf-8"))
        body.write(f'Content-Disposition: form-data; name="crop"\r\n\r\n'.encode("utf-8"))
        body.write(crop.encode("utf-8"))
        body.write(b"\r\n")

    body.write(f"--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request("http://localhost:8000/api/plant/diagnose", data=body.getvalue())
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    if dev_pro:
        req.add_header("X-Gari-Dev-Pro", "true")

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read().decode("utf-8"))
        except Exception:
            data = {"error": str(e)}
        return e.code, data
    except Exception as ex:
        return 500, {"error": str(ex)}

# Execute 17 tests
print("\n" + "="*80)
print("EXECUTING 17 MANDATORY TEST SCENARIOS")
print("="*80)

scenarios = [
    (1, "Clear healthy leaf", "auto_standard", None, False, "LEAF_VALID", "Healthy leaf accepted & diagnosed"),
    (2, "Diseased leaf with visible spots", "auto_standard", None, False, "LEAF_VALID", "Diseased leaf diagnosed & spots located"),
    (3, "Yellow leaf (chlorosis)", "auto_standard", None, False, "LEAF_VALID", "Yellow leaf NOT rejected, correctly diagnosed"),
    (4, "Brown or dry leaf (necrosis)", "auto_standard", None, False, "LEAF_VALID", "Brown necrosis NOT rejected as non-leaf"),
    (5, "Non-leaf image (geometric pattern)", "auto_standard", None, False, "NOT_A_LEAF", "Stopped at Gate 1, Vietnamese msg displayed"),
    (6, "Human face image", "auto_standard", None, False, "NOT_A_LEAF", "Skin detected, stopped at Gate 1"),
    (7, "Animal image (fur/pet)", "auto_standard", None, False, "NOT_A_LEAF", "Non-leaf detected, stopped at Gate 1"),
    (8, "General object image (cup)", "auto_standard", None, False, "NOT_A_LEAF", "Object detected, stopped at Gate 1"),
    (9, "Blurry leaf image", "auto_standard", None, False, "IMAGE_QUALITY_LOW", "Blur rejected, asked to retake clear photo"),
    (10, "Low-light leaf image", "auto_standard", None, False, "IMAGE_QUALITY_LOW", "Low light rejected, asked for better lighting"),
    (11, "Multiple leaves", "auto_standard", None, False, "LEAF_VALID", "Multiple leaves accepted & diagnosed"),
    (12, "Unknown crop (Potato)", "auto_standard", None, False, "LEAF_VALID", "Identified as unsupported crop, no disease fabricated"),
    (13, "Missing crop disease model (Chili)", "manual", "chili", False, "LEAF_VALID", "Leaf valid, reports disease model unavailable"),
    (14, "Standard global model", "auto_standard", None, False, "LEAF_VALID", "Uses Model tong ViT PlantVillage"),
    (15, "Pro global model", "auto_pro", None, True, "LEAF_VALID", "Uses Model tong 2 ViT GBIF with Pro dev auth"),
    (16, "Manual crop mode", "manual", "tomato", False, "LEAF_VALID", "Routes directly to crop-specific ConvNeXt model"),
    (17, "Pro access restriction", "auto_pro", None, False, None, "Rejects with HTTP 403 Forbidden without Pro auth"),
]

results = []

for idx, name, mode, crop, dev_pro, exp_val, desc in scenarios:
    fname, fpath = test_images[idx]
    code, res = send_diagnose_request(fpath, mode, crop, dev_pro)
    
    val_status = res.get("validation", {}).get("status") if isinstance(res, dict) else None
    pipeline_status = res.get("status") if isinstance(res, dict) else None
    model_id = res.get("model_id") or res.get("model_name") if isinstance(res, dict) else None
    disease = res.get("disease_name_vi") or res.get("prediction") if isinstance(res, dict) else None
    msg_vi = res.get("validation", {}).get("message_vi") or res.get("message") or res.get("detail") if isinstance(res, dict) else str(res)
    
    # Check pass criteria
    passed = False
    if idx == 17:
        passed = (code == 403)
    elif exp_val in ("NOT_A_LEAF", "UNCERTAIN", "IMAGE_QUALITY_LOW"):
        passed = (val_status == exp_val and pipeline_status == exp_val.lower())
    elif exp_val == "LEAF_VALID":
        passed = (val_status == "LEAF_VALID")
        if idx == 12:
            passed = passed and (pipeline_status == "unsupported_crop")
        elif idx == 13:
            passed = passed and (pipeline_status == "disease_model_unavailable")
        elif idx == 14:
            passed = passed and (model_id is not None)
        elif idx == 15:
            passed = passed and ("tong 2" in str(model_id).lower() or "plant-identification" in str(model_id).lower())
        elif idx == 16:
            passed = passed and ("tomato" in str(model_id).lower() or "convnext" in str(model_id).lower())

    results.append({
        "test_idx": idx,
        "name": name,
        "mode": mode,
        "crop": crop,
        "http_code": code,
        "val_status": val_status,
        "pipeline_status": pipeline_status,
        "model_id": model_id,
        "disease": disease,
        "msg_vi": msg_vi,
        "passed": passed,
        "desc": desc
    })

    status_str = "PASS" if passed else "FAIL"
    print(f"[{status_str}] Test {idx:02d}: {name}")
    print(f"       HTTP: {code} | Val: {val_status} | Status: {pipeline_status} | Model: {model_id}")
    print(f"       Msg/Disease: {disease or msg_vi}")

with open(os.path.join(BASE_DIR, "scratch", "test_17_results.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\nSaved detailed test output to scratch/test_17_results.json")
