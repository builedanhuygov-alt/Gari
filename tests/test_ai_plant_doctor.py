import os
import sys
import json
import io
import requests
import numpy as np
from PIL import Image, ImageFilter

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://localhost:8000"
DATA_DIR = r"D:\leaf-diseases-detector-main\data\organized\PlantVillage"

def log(test_name, success, detail=""):
    status = " PASS " if success else "[FAIL]"
    print(f"[{status}] {test_name}: {detail}")

def test_suite():
    print("=" * 70)
    print("GARI AI PLANT DOCTOR - AUTOMATED COMPREHENSIVE TEST SUITE")
    print("=" * 70)

    results = {"total": 0, "passed": 0, "failed": 0, "details": []}

    def record(name, condition, msg=""):
        results["total"] += 1
        if condition:
            results["passed"] += 1
            log(name, True, msg)
        else:
            results["failed"] += 1
            log(name, False, msg)
        results["details"].append({"name": name, "passed": condition, "msg": msg})

    # 1. API: Supported Crops
    try:
        r = requests.get(f"{BASE_URL}/api/plant/supported-crops", timeout=10)
        data = r.json()
        record("GET /api/plant/supported-crops", 
               r.status_code == 200 and data.get("total_crops", 0) > 30 and data.get("supported_count", 0) >= 12,
               f"Total crops: {data.get('total_crops')}, Crops with disease models: {data.get('supported_count')}")
    except Exception as e:
        record("GET /api/plant/supported-crops", False, str(e))

    # 2. API: Disease Knowledge Base
    try:
        r = requests.get(f"{BASE_URL}/api/plant/diseases", timeout=10)
        data = r.json()
        record("GET /api/plant/diseases", 
               r.status_code == 200 and data.get("total_diseases", 0) >= 30,
               f"Total diseases cataloged: {data.get('total_diseases')}")
    except Exception as e:
        record("GET /api/plant/diseases", False, str(e))

    # 3. Test Clear Leaf with Known Disease: Potato Early Blight
    potato_eb_dir = os.path.join(DATA_DIR, "Potato___Early_blight")
    potato_eb_files = [f for f in os.listdir(potato_eb_dir) if f.lower().endswith(('.jpg', '.png'))]
    potato_img_path = os.path.join(potato_eb_dir, potato_eb_files[0])

    try:
        with open(potato_img_path, "rb") as f:
            files = {"file": ("potato_eb.jpg", f, "image/jpeg")}
            data = {"crop": "potato"}
            r = requests.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=data, timeout=30)
        res = r.json()
        diag = res.get("diagnosis", {})
        loc = res.get("localization", {})
        regions = res.get("regions", [])

        is_eb = "Early_blight" in diag.get("disease_id", "") or "Early Blight" in diag.get("name_en", "")
        has_overlay = bool(loc.get("overlay_url") or res.get("overlay_url"))
        has_attention = bool(loc.get("attention_url") or res.get("attention_url"))
        has_regions = len(regions) > 0
        has_vi_report = bool(res.get("report_vi"))

        record("Clear Leaf (Potato Early Blight) - Disease Diagnosis", 
               r.status_code == 200 and is_eb,
               f"Disease: {diag.get('name_vi')} ({diag.get('disease_id')}), Score: {diag.get('score'):.2%}")

        record("Disease Localization (Grad-CAM & Pathology Overlay)",
               has_overlay and has_attention and has_regions,
               f"Attention URL: {loc.get('attention_url')}, Overlay URL: {loc.get('overlay_url')}, Detected lesion regions: {len(regions)}")

        record("Vietnamese Natural Report Generation",
               has_vi_report and "KẾT QUẢ KIỂM TRA LÁ" in res.get("report_vi", ""),
               f"Report headline: {res.get('report_vi', '').splitlines()[0] if res.get('report_vi') else 'None'}")
    except Exception as e:
        record("Clear Leaf (Potato Early Blight)", False, str(e))

    # 4. Test Model tong ViT Classifier: Pepper Bell Bacterial Spot
    pepper_dir = os.path.join(DATA_DIR, "Pepper__bell___Bacterial_spot")
    pepper_files = [f for f in os.listdir(pepper_dir) if f.lower().endswith(('.jpg', '.png'))]
    pepper_img_path = os.path.join(pepper_dir, pepper_files[0])

    try:
        with open(pepper_img_path, "rb") as f:
            files = {"file": ("pepper_bs.jpg", f, "image/jpeg")}
            data = {"crop": "pepper"}
            r = requests.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=data, timeout=30)
        res = r.json()
        diag = res.get("diagnosis", {})
        is_bs = "Bacterial_spot" in diag.get("disease_id", "") or "bacterial" in diag.get("name_en", "").lower()

        record("Model tong Routing (Pepper Bacterial Spot ViT)",
               r.status_code == 200 and is_bs,
               f"Crop: {res.get('crop', {}).get('name_vi')}, Disease: {diag.get('name_vi')}, Score: {diag.get('score'):.2%}, Model used: {res.get('metadata', {}).get('model_used')}")
    except Exception as e:
        record("Model tong Routing (Pepper)", False, str(e))

    # 5. Test Healthy Leaf: Potato Healthy
    potato_h_dir = os.path.join(DATA_DIR, "Potato___healthy")
    potato_h_files = [f for f in os.listdir(potato_h_dir) if f.lower().endswith(('.jpg', '.png'))]
    potato_h_path = os.path.join(potato_h_dir, potato_h_files[0])

    try:
        with open(potato_h_path, "rb") as f:
            files = {"file": ("potato_h.jpg", f, "image/jpeg")}
            data = {"crop": "potato"}
            r = requests.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=data, timeout=30)
        res = r.json()
        diag = res.get("diagnosis", {})
        is_healthy = diag.get("is_healthy") or "healthy" in diag.get("disease_id", "").lower()

        record("Healthy Leaf Identification (Potato Healthy)",
               r.status_code == 200 and is_healthy,
               f"Status: {diag.get('status')}, Name: {diag.get('name_vi')}, Message: {diag.get('message_vi')}")
    except Exception as e:
        record("Healthy Leaf Identification", False, str(e))

    # 6. Test Blurry Leaf Image (Image Quality Gate)
    try:
        img = Image.open(potato_img_path).convert("RGB")
        blurry_img = img.filter(ImageFilter.GaussianBlur(radius=15))
        buf = io.BytesIO()
        blurry_img.save(buf, format="JPEG")
        buf.seek(0)

        files = {"file": ("blurry.jpg", buf, "image/jpeg")}
        r = requests.post(f"{BASE_URL}/api/plant/diagnose", files=files, timeout=30)
        res = r.json()
        quality = res.get("quality", {})
        warnings = res.get("warnings", [])
        blur_flagged = not quality.get("passed", True) or any("mờ" in w.lower() or "blur" in w.lower() for w in warnings)

        record("Image Quality Check - Blurry Leaf Rejection / Warning",
               r.status_code == 200 and blur_flagged,
               f"Quality passed: {quality.get('passed')}, Blur score (lap_var): {quality.get('laplacian_variance')}, Message: {quality.get('message_vi') or warnings}")
    except Exception as e:
        record("Image Quality Check - Blurry Leaf", False, str(e))

    # 7. Test Non-Leaf Image (Uniform Synthetic Noise)
    try:
        flat_arr = np.full((300, 300, 3), 128, dtype=np.uint8)
        flat_img = Image.fromarray(flat_arr)
        buf = io.BytesIO()
        flat_img.save(buf, format="JPEG")
        buf.seek(0)

        files = {"file": ("non_leaf.jpg", buf, "image/jpeg")}
        r = requests.post(f"{BASE_URL}/api/plant/diagnose", files=files, timeout=30)
        res = r.json()
        quality = res.get("quality", {})
        diag = res.get("diagnosis", {})
        rejected = not quality.get("passed", True) or diag.get("status") in ["unsupported_image", "not_a_leaf", "uncertain", "quality_rejected"] or len(res.get("warnings", [])) > 0

        record("Non-Leaf Image Detection & Quality Gate",
               r.status_code == 200 and rejected,
               f"Diagnosis status: {diag.get('status')}, Quality passed: {quality.get('passed')}, Message: {quality.get('message_vi') or diag.get('message_vi')}")
    except Exception as e:
        record("Non-Leaf Image Detection", False, str(e))

    # 8. Test Unsupported Crop Handling
    try:
        with open(potato_img_path, "rb") as f:
            files = {"file": ("unsupported.jpg", f, "image/jpeg")}
            data = {"crop": "raspberry"} # Raspberry has no disease model
            r = requests.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=data, timeout=30)
        res = r.json()
        diag = res.get("diagnosis", {})
        correctly_unsupported = diag.get("status") in ["unsupported_crop", "no_model"] or "chưa hỗ trợ" in diag.get("message_vi", "").lower()

        record("Unsupported Crop Gate (No Random Model Execution)",
               r.status_code == 200 and correctly_unsupported,
               f"Status: {diag.get('status')}, Vietnamese guidance: {diag.get('message_vi')}")
    except Exception as e:
        record("Unsupported Crop Gate", False, str(e))

    # 9. Test Dedicated Region Analysis Endpoint
    try:
        with open(potato_img_path, "rb") as f:
            files = {"file": ("potato_region.jpg", f, "image/jpeg")}
            data = {"crop": "potato", "disease": "Potato___Early_blight"}
            r = requests.post(f"{BASE_URL}/api/plant/analyze-regions", files=files, data=data, timeout=30)
        res = r.json()
        has_regions = len(res.get("regions", [])) > 0
        has_attention = bool(res.get("attention_url"))
        has_overlay = bool(res.get("overlay_url"))

        record("POST /api/plant/analyze-regions (Dedicated Visual Localization)",
               r.status_code == 200 and has_regions and has_attention and has_overlay,
               f"Extracted {len(res.get('regions', []))} suspicious regions, Overlay URL: {res.get('overlay_url')}")
    except Exception as e:
        record("Dedicated Region Analysis Endpoint", False, str(e))

    # 10. Test Diagnosis History & Persistence
    try:
        r = requests.get(f"{BASE_URL}/api/diagnoses", timeout=10)
        data = r.json()
        items = data.get("diagnoses", data) if isinstance(data, dict) else data
        record("GET /api/diagnoses (Persistent Diagnosis History)",
               r.status_code == 200 and isinstance(items, list) and len(items) > 0,
               f"Found {len(items)} saved diagnoses. Latest crop: {items[0].get('crop_name')}, Disease: {items[0].get('disease_name')}, Has overlay: {bool(items[0].get('overlay_path'))}")
    except Exception as e:
        record("Diagnosis History & Persistence", False, str(e))

    print("\n" + "=" * 70)
    print(f"TEST SUMMARY: {results['passed']}/{results['total']} PASSED ({(results['passed']/results['total'])*100:.1f}%)")
    print("=" * 70)

if __name__ == "__main__":
    test_suite()
