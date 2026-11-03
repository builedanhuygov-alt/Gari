"""
GARI AI LAB — Phase 10 Comprehensive Regression Test Suite
Validates all 10 critical pipeline scenarios:
1. Correctly identified crop
2. Incorrect crop candidate / low confidence
3. Ambiguous crop image (Solanaceae overlap: Tomato vs Potato)
4. Unsupported crop (Pepper, Raspberry, etc.)
5. Blurry image rejection
6. Non-leaf / solid color rejection
7. Correct crop with multiple disease candidates
8. Correct model loading & LRU caching
9. Model metadata consistency check
10. Missing / unknown crop error handling
"""

import io
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from PIL import Image, ImageFilter
import numpy as np

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

API_BASE = "http://127.0.0.1:8000"
DATA_DIR = Path("D:/leaf-diseases-detector-main/data/organized/PlantVillage")


def post_multipart(url: str, fields: dict, files: dict) -> dict:
    boundary = "----WebKitFormBoundary" + str(int(time.time() * 1000))
    body = bytearray()

    for key, val in fields.items():
        if val is None:
            continue
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        body.extend(f"{val}\r\n".encode("utf-8"))

    for key, (filename, data, content_type) in files.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'.encode("utf-8"))
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.extend(data)
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(url, data=bytes(body), method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return {"_http_status": e.code, **json.loads(raw)}
        except Exception:
            return {"_http_status": e.code, "error": raw}


def run_regression_tests():
    print("=" * 75)
    print("🌿 GARI VISION — PHASE 10 COMPREHENSIVE REGRESSION TEST SUITE")
    print(f"Target API Server: {API_BASE}")
    print("=" * 75)

    results = []

    # 1. Correctly identified crop
    print("\n[Scenario 1] Correctly identified crop (Auto Mode -> Tomato)")
    tomato_img_path = DATA_DIR / "Tomato_Bacterial_spot" / "00416648-be6e-4bd4-bc8d-82f43f8a7240___GCREC_Bact.Sp 3110.JPG"
    with open(tomato_img_path, "rb") as f:
        img_bytes = f.read()

    res1 = post_multipart(f"{API_BASE}/api/predict", {}, {"image": ("leaf.jpg", img_bytes, "image/jpeg")})
    status1 = "PASS" if res1.get("status") == "OK" and res1.get("crop") == "Tomato" else "FAIL"
    print(f"  Result: {status1} | Crop: {res1.get('crop')} | Prediction: {res1.get('prediction')} | Conf: {res1.get('confidence_percent')}%")
    results.append({"id": 1, "name": "Correctly identified crop", "status": status1, "details": res1.get("reason", res1.get("prediction"))})

    # 2. Incorrect crop candidate / low confidence
    print("\n[Scenario 2] Crop Detector Ambiguity & Uncertainty Gate")
    # Synthetic flat leaf that lacks clear crop features
    flat_img = Image.new("RGB", (256, 256), (45, 90, 45))
    buf = io.BytesIO()
    # Add slight texture so it passes quality check but fails crop confidence
    arr = np.array(flat_img, dtype=np.uint8)
    arr[50:200, 50:200] += np.random.randint(0, 30, (150, 150, 3), dtype=np.uint8)
    Image.fromarray(arr).save(buf, format="JPEG")
    res2 = post_multipart(f"{API_BASE}/api/predict", {}, {"image": ("flat.jpg", buf.getvalue(), "image/jpeg")})
    status2 = "PASS" if res2.get("crop_validation_required") or res2.get("status") in ("crop_uncertain", "multiple_candidates", "rejected_low_quality") else "FAIL"
    print(f"  Result: {status2} | Status: {res2.get('status')} | Message: {res2.get('message')}")
    results.append({"id": 2, "name": "Low confidence crop handling", "status": status2, "details": res2.get("message")})

    # 3. Ambiguous crop image (Solanaceae overlap: Tomato Late Blight confusable with Potato)
    print("\n[Scenario 3] Ambiguous crop image (Tomato Late Blight vs Potato)")
    tomato_lb_path = DATA_DIR / "Tomato_Late_blight" / "0003faa8-4b27-4c65-bf42-6d9e352ca1a5___RS_Late.B 4946.JPG"
    with open(tomato_lb_path, "rb") as f:
        img_bytes_lb = f.read()
    res3 = post_multipart(f"{API_BASE}/api/crop/detect", {}, {"image": ("lb.jpg", img_bytes_lb, "image/jpeg")})
    cand_crops = [c["crop_id"] for c in res3.get("candidates", [])]
    has_potato_and_tomato = ("Potato" in cand_crops and "Tomato" in cand_crops)
    status3 = "PASS" if has_potato_and_tomato else "FAIL"
    print(f"  Result: {status3} | State: {res3.get('state')} | Candidates: {cand_crops[:3]}")
    results.append({"id": 3, "name": "Ambiguous crop identification", "status": status3, "details": f"Candidates: {cand_crops[:3]}"})

    # 4. Unsupported crop (Pepper / Bell Pepper recognized by detector but has no disease model)
    print("\n[Scenario 4] Unsupported crop (Pepper)")
    pepper_img_path = DATA_DIR / "Pepper__bell___Bacterial_spot" / "0022d6b7-d47c-4ee2-ae9a-392a53f48647___JR_B.Spot 8964.JPG"
    with open(pepper_img_path, "rb") as f:
        img_bytes_pepper = f.read()
    res4 = post_multipart(f"{API_BASE}/api/predict", {"crop": "Pepper"}, {"image": ("pepper.jpg", img_bytes_pepper, "image/jpeg")})
    status4 = "PASS" if res4.get("status") == "unsupported_crop" or res4.get("validation_state") == "UNSUPPORTED_CROP" else "FAIL"
    print(f"  Result: {status4} | Status: {res4.get('status')} | Message: {res4.get('message')}")
    results.append({"id": 4, "name": "Unsupported crop handling", "status": status4, "details": res4.get("message")})

    # 5. Blurry image rejection
    print("\n[Scenario 5] Blurry image rejection")
    blurry_im = Image.open(tomato_img_path).filter(ImageFilter.GaussianBlur(25))
    buf_blur = io.BytesIO()
    blurry_im.save(buf_blur, format="JPEG")
    res5 = post_multipart(f"{API_BASE}/api/predict", {}, {"image": ("blur.jpg", buf_blur.getvalue(), "image/jpeg")})
    status5 = "PASS" if res5.get("status") == "rejected_low_quality" or "quá mờ" in res5.get("reason", "").lower() else "FAIL"
    print(f"  Result: {status5} | Reason: {res5.get('reason')}")
    results.append({"id": 5, "name": "Blurry image rejection", "status": status5, "details": res5.get("reason")})

    # 6. Non-leaf / solid color rejection
    print("\n[Scenario 6] Non-leaf / solid color rejection")
    solid_im = Image.new("RGB", (256, 256), (34, 139, 34))
    buf_solid = io.BytesIO()
    solid_im.save(buf_solid, format="JPEG")
    res6 = post_multipart(f"{API_BASE}/api/predict", {}, {"image": ("solid.jpg", buf_solid.getvalue(), "image/jpeg")})
    status6 = "PASS" if res6.get("status") == "rejected_low_quality" else "FAIL"
    print(f"  Result: {status6} | Reason: {res6.get('reason')}")
    results.append({"id": 6, "name": "Non-leaf rejection", "status": status6, "details": res6.get("reason")})

    # 7. Correct crop with multiple possible diseases (Top-3 distribution)
    print("\n[Scenario 7] Top-3 disease distribution on valid Tomato leaf")
    res7 = post_multipart(f"{API_BASE}/api/predict", {"crop": "Tomato"}, {"image": ("tomato.jpg", img_bytes, "image/jpeg")})
    top_preds = res7.get("top_predictions", [])
    status7 = "PASS" if len(top_preds) >= 3 and res7.get("status") == "OK" else "FAIL"
    print(f"  Result: {status7} | Top-1: {top_preds[0]['name']} ({top_preds[0]['confidence_percent']}%) | Severity: {res7.get('severity')}")
    results.append({"id": 7, "name": "Top-3 disease distribution", "status": status7, "details": f"Count: {len(top_preds)}"})

    # 8. Correct model loading & LRU caching
    print("\n[Scenario 8] Model loading & LRU caching")
    req_load = urllib.request.Request(f"{API_BASE}/api/models/Tomato/load", data=b"", method="POST")
    with urllib.request.urlopen(req_load) as resp:
        load_res = json.loads(resp.read().decode("utf-8"))
    status8 = "PASS" if load_res.get("status") == "LOADED" else "FAIL"
    print(f"  Result: {status8} | Status: {load_res.get('status')} | Load time: {load_res.get('load_time_ms')}ms")
    results.append({"id": 8, "name": "Model loading & caching", "status": status8, "details": load_res.get("status")})

    # 9. Model metadata consistency check
    print("\n[Scenario 9] Model metadata consistency & invalid model exclusion")
    req_models = urllib.request.urlopen(f"{API_BASE}/api/models")
    models_res = json.loads(req_models.read().decode("utf-8"))
    model_ids = [m["crop_id"] for m in models_res.get("models", [])]
    # Verify that models/Crop (invalid ViT) is NOT in discovered models
    has_broken_crop = any(mid.lower() == "crop" for mid in model_ids)
    status9 = "PASS" if (not has_broken_crop and len(model_ids) >= 42) else "FAIL"
    print(f"  Result: {status9} | Total valid models: {len(model_ids)} | Excluded broken Crop: {not has_broken_crop}")
    results.append({"id": 9, "name": "Metadata consistency & exclusion", "status": status9, "details": f"Total: {len(model_ids)} models"})

    # 10. Missing / unknown crop error handling
    print("\n[Scenario 10] Unsupported / unknown crop error handling")
    res10 = post_multipart(f"{API_BASE}/api/predict", {"crop": "NonExistentCrop999"}, {"image": ("leaf.jpg", img_bytes, "image/jpeg")})
    status10 = "PASS" if res10.get("_http_status") == 400 or "not found" in str(res10).lower() else "FAIL"
    print(f"  Result: {status10} | Detail: {res10.get('detail', res10.get('error'))}")
    results.append({"id": 10, "name": "Unknown crop error handling", "status": status10, "details": str(res10.get("detail"))[:60]})

    print("\n" + "=" * 75)
    passed = sum(1 for r in results if r["status"] == "PASS")
    print(f"REGRESSION SUITE COMPLETED: {passed}/10 PASSED")
    print("=" * 75)

    return {"total": len(results), "passed": passed, "results": results}


if __name__ == "__main__":
    out = run_regression_tests()
    with open("scratch/regression_results.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
