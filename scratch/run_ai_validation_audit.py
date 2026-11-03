import os
import sys
import json
import io
import time
import requests
import numpy as np
from PIL import Image, ImageFilter
from collections import defaultdict

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = r"D:\leaf-diseases-detector-main"
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

BASE_URL = "http://localhost:8000"
DATA_DIR = r"D:\leaf-diseases-detector-main\data\organized\PlantVillage"
MODELS_DIR = r"D:\leaf-diseases-detector-main\models"

def run_audit():
    print("=" * 80)
    print("GARI AI LAB — POST-IMPLEMENTATION INDEPENDENT AI VALIDATION AUDIT")
    print("=" * 80)
    
    audit_results = {}

    # =========================================================================
    # SECTION 1: TEST AUTOMATIC CROP IDENTIFICATION (WITHOUT crop_id)
    # =========================================================================
    print("\n" + "=" * 80)
    print("SECTION 1: TEST AUTOMATIC CROP IDENTIFICATION (Zero Crop Hint)")
    print("=" * 80)

    # Representative sample set across classes
    test_crops = {
        "Potato": [
            os.path.join(DATA_DIR, "Potato___Early_blight", f) for f in os.listdir(os.path.join(DATA_DIR, "Potato___Early_blight"))[:5]
        ] + [
            os.path.join(DATA_DIR, "Potato___healthy", f) for f in os.listdir(os.path.join(DATA_DIR, "Potato___healthy"))[:5]
        ],
        "Tomato": [
            os.path.join(DATA_DIR, "Tomato_Bacterial_spot", f) for f in os.listdir(os.path.join(DATA_DIR, "Tomato_Bacterial_spot"))[:5]
        ] + [
            os.path.join(DATA_DIR, "Tomato_healthy", f) for f in os.listdir(os.path.join(DATA_DIR, "Tomato_healthy"))[:5]
        ],
        "Pepper": [
            os.path.join(DATA_DIR, "Pepper__bell___Bacterial_spot", f) for f in os.listdir(os.path.join(DATA_DIR, "Pepper__bell___Bacterial_spot"))[:5]
        ] + [
            os.path.join(DATA_DIR, "Pepper__bell___healthy", f) for f in os.listdir(os.path.join(DATA_DIR, "Pepper__bell___healthy"))[:5]
        ]
    }

    crop_y_true = []
    crop_y_pred_top1 = []
    crop_top3_hits = 0
    total_crop_images = 0
    confusion = defaultdict(lambda: defaultdict(int))
    top3_details = []

    for true_crop, filepaths in test_crops.items():
        for fp in filepaths:
            total_crop_images += 1
            with open(fp, "rb") as f:
                # Submit WITHOUT crop hint! Only image upload!
                files = {"image": (os.path.basename(fp), f, "image/jpeg")}
                r = requests.post(f"{BASE_URL}/api/plant/identify", files=files, timeout=20)
            
            res = r.json()
            crop_obj = res.get("crop")
            pred_crop = crop_obj.get("id") if crop_obj else "Unidentified"
            candidates = [c.get("crop_id") for c in res.get("candidates", [])]

            crop_y_true.append(true_crop)
            crop_y_pred_top1.append(pred_crop)
            confusion[true_crop][pred_crop] += 1

            if true_crop == pred_crop:
                is_top1 = True
            else:
                is_top1 = False

            is_top3 = true_crop in candidates[:3]
            if is_top3:
                crop_top3_hits += 1

            top3_details.append({
                "true": true_crop,
                "pred": pred_crop,
                "top3": candidates[:3],
                "conf": crop_obj.get("confidence") if crop_obj else 0.0,
                "top1_hit": is_top1,
                "top3_hit": is_top3
            })

    top1_correct = sum(1 for yt, yp in zip(crop_y_true, crop_y_pred_top1) if yt == yp)
    top1_acc = top1_correct / total_crop_images if total_crop_images > 0 else 0.0
    top3_acc = crop_top3_hits / total_crop_images if total_crop_images > 0 else 0.0

    print(f"Total Test Images (Automatic Identification): {total_crop_images}")
    print(f"Top-1 Accuracy: {top1_acc:.2%} ({top1_correct}/{total_crop_images})")
    print(f"Top-3 Accuracy: {top3_acc:.2%} ({crop_top3_hits}/{total_crop_images})")

    # Per-crop Recall
    print("\n--- Per-Crop Recall ---")
    recalls = {}
    for crop in test_crops.keys():
        total_c = sum(confusion[crop].values())
        correct_c = confusion[crop][crop]
        recall_c = correct_c / total_c if total_c > 0 else 0.0
        recalls[crop] = recall_c
        print(f"  {crop:12s}: Recall = {recall_c:.2%} ({correct_c}/{total_c})")

    # Confusion Matrix
    print("\n--- Confusion Matrix ---")
    all_labels = sorted(list(set(crop_y_true + crop_y_pred_top1)))
    header = f"{'True \\ Pred':15s} | " + " | ".join(f"{lbl:10s}" for lbl in all_labels)
    print(header)
    print("-" * len(header))
    for t in sorted(test_crops.keys()):
        row = f"{t:15s} | " + " | ".join(f"{confusion[t][p]:10d}" for p in all_labels)
        print(row)

    audit_results["crop_identification"] = {
        "total_tested": total_crop_images,
        "top1_accuracy": top1_acc,
        "top3_accuracy": top3_acc,
        "recalls": recalls,
        "confusion_matrix": {k: dict(v) for k, v in confusion.items()}
    }

    # =========================================================================
    # SECTION 2: TEST THE COMPLETE END-TO-END PIPELINE (Zero Manual Override)
    # =========================================================================
    print("\n" + "=" * 80)
    print("SECTION 2: COMPLETE END-TO-END PIPELINE AUDIT (Zero Manual Override)")
    print("=" * 80)

    e2e_samples = [
        {"name": "Potato Early Blight", "path": test_crops["Potato"][0], "expected_crop": "Potato", "expected_disease": "Early_blight"},
        {"name": "Potato Healthy", "path": test_crops["Potato"][5], "expected_crop": "Potato", "expected_disease": "healthy"},
        {"name": "Tomato Bacterial Spot", "path": test_crops["Tomato"][0], "expected_crop": "Tomato", "expected_disease": "Bacterial_spot"},
        {"name": "Tomato Healthy", "path": test_crops["Tomato"][5], "expected_crop": "Tomato", "expected_disease": "healthy"},
        {"name": "Pepper Bacterial Spot", "path": test_crops["Pepper"][0], "expected_crop": "Pepper", "expected_disease": "Bacterial_spot"},
        {"name": "Pepper Healthy", "path": test_crops["Pepper"][5], "expected_crop": "Pepper", "expected_disease": "healthy"},
    ]

    e2e_results = []
    for s in e2e_samples:
        print(f"\nEvaluating Sample: {s['name']}")
        with open(s["path"], "rb") as f:
            # DO NOT SPECIFY CROP! Entire pipeline is automated!
            files = {"image": (os.path.basename(s["path"]), f, "image/jpeg")}
            t0 = time.perf_counter()
            r = requests.post(f"{BASE_URL}/api/plant/diagnose", files=files, timeout=30)
            elapsed = (time.perf_counter() - t0) * 1000.0

        res = r.json()
        crop_info = res.get("crop", {})
        diag_info = res.get("diagnosis", {})
        quality_info = res.get("quality", {})
        loc_info = res.get("localization", {})
        report_vi = res.get("report_vi", "")

        step_output = {
            "sample": s["name"],
            "1_quality_passed": quality_info.get("passed"),
            "1_quality_metrics": res.get("quality_metrics"),
            "2_auto_crop_identified": crop_info.get("id"),
            "2_crop_name_vi": crop_info.get("name_vi"),
            "3_validation_gate_state": res.get("validation_state"),
            "4_model_routed": res.get("model", {}).get("name"),
            "5_predicted_disease": diag_info.get("disease_id"),
            "5_disease_name_vi": diag_info.get("name_vi"),
            "5_prediction_score": diag_info.get("score"),
            "6_gradcam_url": loc_info.get("attention_url"),
            "6_overlay_url": loc_info.get("overlay_url"),
            "6_regions_count": len(res.get("regions", [])),
            "7_report_headline": report_vi.splitlines()[0] if report_vi else "None",
            "latency_ms": round(elapsed, 2)
        }
        e2e_results.append(step_output)
        for k, v in step_output.items():
            print(f"  {k:26s}: {v}")

    audit_results["end_to_end_pipeline"] = e2e_results

    # =========================================================================
    # SECTION 3: VERIFY MODEL TONG (ALL 38 LABELS)
    # =========================================================================
    print("\n" + "=" * 80)
    print("SECTION 3: VERIFY MODEL TONG (38 PlantVillage Classes)")
    print("=" * 80)

    cfg_tong_path = os.path.join(MODELS_DIR, "Model tong", "config.json")
    with open(cfg_tong_path, "r", encoding="utf-8") as f:
        cfg_tong = json.load(f)
    
    id2label = cfg_tong.get("id2label", {})
    from gari_capability_registry import DISEASES_VI, CROPS_VI

    print(f"{'ID':3s} | {'Original Label':46s} | {'Crop':10s} | {'Vietnamese Name':35s} | {'Routing'}")
    print("-" * 115)
    tong_table = []
    for idx_str, orig_lbl in sorted(id2label.items(), key=lambda x: int(x[0])):
        idx = int(idx_str)
        # Parse crop from PlantVillage label
        crop_part = orig_lbl.split("___")[0].replace("_(including_sour)", "").replace("_(maize)", "").replace(",_bell", "")
        disease_part = orig_lbl.split("___")[-1] if "___" in orig_lbl else orig_lbl

        # Routing destination in Gari Lab:
        # Pepper and Squash use Model tong
        # Tomato, Potato, Apple, Corn, Grape, Peach, Cherry, Strawberry have dedicated ConvNeXt models
        # Blueberry, Orange, Raspberry, Soybean are PlantVillage specific
        if crop_part in ["Pepper", "Squash"]:
            routing = "Active Primary Disease Model (Model tong ViT)"
        elif crop_part in ["Tomato", "Potato", "Apple", "Corn", "Grape", "Peach", "Cherry", "Strawberry"]:
            routing = f"Fallback (Primary is ConvNeXt {crop_part})"
        else:
            routing = "PlantVillage reference (No local ConvNeXt)"

        vi_name = DISEASES_VI.get(disease_part) or DISEASES_VI.get(orig_lbl) or f"Bệnh {disease_part.replace('_', ' ')}"
        if "healthy" in orig_lbl.lower():
            vi_name = "Khỏe mạnh, không phát hiện bệnh"

        tong_table.append({
            "id": idx,
            "label_en": orig_lbl,
            "crop": crop_part,
            "disease_en": disease_part,
            "name_vi": vi_name,
            "routing": routing
        })
        print(f"{idx:3d} | {orig_lbl:46s} | {crop_part:10s} | {vi_name:35s} | {routing}")

    audit_results["model_tong_38_labels"] = tong_table

    # =========================================================================
    # SECTION 4: VERIFY LOCALIZATION (GRAD-CAM vs LAB/HSV)
    # =========================================================================
    print("\n" + "=" * 80)
    print("SECTION 4: VERIFY LOCALIZATION (Grad-CAM vs LAB/HSV Pathology)")
    print("=" * 80)

    potato_sample = test_crops["Potato"][0]
    with open(potato_sample, "rb") as f:
        files = {"image": ("potato_loc.jpg", f, "image/jpeg")}
        data = {"crop": "potato", "disease": "Potato___Early_blight"}
        r = requests.post(f"{BASE_URL}/api/plant/analyze-regions", files=files, data=data, timeout=30)
    
    loc_res = r.json()
    print(f"Localization API Status: {r.status_code}")
    print(f"Has Attention Heatmap (Grad-CAM): {loc_res.get('has_attention_map')}")
    print(f"Attention Image URL:              {loc_res.get('attention_url')}")
    print(f"Lesion Overlay Image URL:         {loc_res.get('overlay_url')}")
    print(f"Detected Suspicious Regions:      {loc_res.get('regions_count')}")
    for idx, reg in enumerate(loc_res.get("regions", []), 1):
        print(f"  Vùng {idx}: Type={reg.get('type')}, Box={reg.get('box')}, Area={reg.get('area')}, Desc={reg.get('type_vi')}")

    # =========================================================================
    # SECTION 5: VERIFY IMAGE QUALITY GATE
    # =========================================================================
    print("\n" + "=" * 80)
    print("SECTION 5: VERIFY IMAGE QUALITY GATE (Edge Cases)")
    print("=" * 80)

    quality_tests = []
    
    # 1. Real Leaf
    with open(potato_sample, "rb") as f:
        r = requests.post(f"{BASE_URL}/api/plant/diagnose", files={"image": ("real_leaf.jpg", f, "image/jpeg")}, timeout=30)
    q1 = r.json().get("quality", {})
    quality_tests.append({"case": "Real Leaf Image", "passed": q1.get("passed"), "expected_pass": True, "msg": q1.get("message_vi")})

    # 2. Human Skin
    skin_arr = np.random.normal(loc=[210, 150, 130], scale=[10, 8, 8], size=(224, 224, 3)).clip(0, 255).astype(np.uint8)
    buf_skin = io.BytesIO()
    Image.fromarray(skin_arr).save(buf_skin, format="JPEG")
    buf_skin.seek(0)
    r = requests.post(f"{BASE_URL}/api/plant/diagnose", files={"image": ("skin.jpg", buf_skin, "image/jpeg")}, timeout=30)
    q2 = r.json().get("quality", {})
    quality_tests.append({"case": "Human Skin (Non-Leaf)", "passed": q2.get("passed"), "expected_pass": False, "msg": q2.get("message_vi")})

    # 3. Blue Fabric
    fabric_arr = np.random.normal(loc=[40, 60, 180], scale=[15, 15, 20], size=(224, 224, 3)).clip(0, 255).astype(np.uint8)
    buf_fabric = io.BytesIO()
    Image.fromarray(fabric_arr).save(buf_fabric, format="JPEG")
    buf_fabric.seek(0)
    r = requests.post(f"{BASE_URL}/api/plant/diagnose", files={"image": ("fabric.jpg", buf_fabric, "image/jpeg")}, timeout=30)
    q3 = r.json().get("quality", {})
    quality_tests.append({"case": "Blue Fabric (Non-Leaf)", "passed": q3.get("passed"), "expected_pass": False, "msg": q3.get("message_vi")})

    # 4. Food / Bread
    food_arr = np.random.normal(loc=[180, 100, 50], scale=[20, 15, 10], size=(224, 224, 3)).clip(0, 255).astype(np.uint8)
    buf_food = io.BytesIO()
    Image.fromarray(food_arr).save(buf_food, format="JPEG")
    buf_food.seek(0)
    r = requests.post(f"{BASE_URL}/api/plant/diagnose", files={"image": ("food.jpg", buf_food, "image/jpeg")}, timeout=30)
    q4 = r.json().get("quality", {})
    quality_tests.append({"case": "Food / Bread (Non-Leaf)", "passed": q4.get("passed"), "expected_pass": False, "msg": q4.get("message_vi")})

    # 5. Dark Image
    dark_arr = np.random.normal(loc=[15, 18, 14], scale=[3, 3, 3], size=(224, 224, 3)).clip(0, 255).astype(np.uint8)
    buf_dark = io.BytesIO()
    Image.fromarray(dark_arr).save(buf_dark, format="JPEG")
    buf_dark.seek(0)
    r = requests.post(f"{BASE_URL}/api/plant/diagnose", files={"image": ("dark.jpg", buf_dark, "image/jpeg")}, timeout=30)
    q5 = r.json().get("quality", {})
    quality_tests.append({"case": "Dark Image (< 22 Lum)", "passed": q5.get("passed"), "expected_pass": False, "msg": q5.get("message_vi")})

    # 6. Blurry Leaf
    img_real = Image.open(potato_sample).convert("RGB")
    blurry_img = img_real.filter(ImageFilter.GaussianBlur(radius=16))
    buf_blur = io.BytesIO()
    blurry_img.save(buf_blur, format="JPEG")
    buf_blur.seek(0)
    r = requests.post(f"{BASE_URL}/api/plant/diagnose", files={"image": ("blur.jpg", buf_blur, "image/jpeg")}, timeout=30)
    q6 = r.json().get("quality", {})
    quality_tests.append({"case": "Blurry Leaf (LapVar < 15)", "passed": q6.get("passed"), "expected_pass": False, "msg": q6.get("message_vi")})

    for qt in quality_tests:
        ok = qt["passed"] == qt["expected_pass"]
        status_tag = "PASS" if ok else "FAIL"
        print(f"[{status_tag}] {qt['case']:26s} -> Passed: {str(qt['passed']):5s} | Reason: {qt['msg']}")

    audit_results["quality_gate_tests"] = quality_tests

    # =========================================================================
    # SECTION 7: VERIFY AUTHORITATIVE CAPABILITY REGISTRY
    # =========================================================================
    print("\n" + "=" * 80)
    print("SECTION 7: VERIFY AUTHORITATIVE CAPABILITY REGISTRY")
    print("=" * 80)
    r = requests.get(f"{BASE_URL}/api/plant/supported-crops", timeout=10)
    cap_summary = r.json()
    print(f"Total Crops:                   {cap_summary.get('total_crops')}")
    print(f"Identifiable Crops:            {cap_summary.get('identifiable_count')}")
    print(f"Diagnosable Crops:             {cap_summary.get('diagnosable_count')}")
    print(f"Total Disease Classes:         {cap_summary.get('total_disease_classes')}")
    print(f"Crops without Disease Models:  {cap_summary.get('reconciliation', {}).get('crops_without_disease_models')}")

    audit_results["capability_registry_summary"] = cap_summary

    # Save complete audit report to JSON
    out_path = r"D:\leaf-diseases-detector-main\data\post_implementation_audit_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(audit_results, f, ensure_ascii=False, indent=2)
    print(f"\nAudit complete! Full JSON output written to: {out_path}")

if __name__ == "__main__":
    run_audit()
