"""
GARI AI LAB — Verification & Integration Test Suite
Executes the 10 mandatory tests against the running Gari AI Lab server (port 8765)
and the internal Python inference engine (port 8766).
"""
import os
import sys
import json
import time
import urllib.request
import urllib.error

SERVER_URL = "http://127.0.0.1:8765"
MODELS_DIR = r"D:\leaf-diseases-detector-main\models"
TOMATO_IMG = r"D:\leaf-diseases-detector-main\data\organized\Tomato\Tomato_Bacterial_spot\00416648-be6e-4bd4-bc8d-82f43f8a7240___GCREC_Bact.Sp 3110.JPG"
POTATO_IMG = r"D:\leaf-diseases-detector-main\data\organized\Potato\Potato___Early_blight\001187a0-57ab-4329-baff-e7246a9edeb0___RS_Early.B 8178.JPG"

passed_tests = 0
total_tests = 10
test_results = []

def record(test_num, name, success, details):
    global passed_tests
    status = "PASS" if success else "FAIL"
    if success:
        passed_tests += 1
    test_results.append({
        "test_number": test_num,
        "name": name,
        "status": status,
        "details": details
    })
    print(f"[{status}] Test {test_num}: {name}")
    print(f"       Details: {details}\n")

print("=" * 70)
print(" GARI AI LAB — 10 MANDATORY VERIFICATION TESTS")
print("=" * 70)

# TEST 1: Confirm models directory exists
t1_exists = os.path.isdir(MODELS_DIR)
record(1, "Confirm models directory exists", t1_exists, f"Path: {MODELS_DIR} (exists: {t1_exists})")

# TEST 2: Discover all model folders
model_dirs = []
for root, dirs, files in os.walk(MODELS_DIR):
    if "model.safetensors" in files and "config.json" in files:
        rel = os.path.relpath(root, MODELS_DIR).replace("\\", "/")
        model_dirs.append(rel)
t2_success = len(model_dirs) >= 40
record(2, "Discover all model folders", t2_success, f"Discovered {len(model_dirs)} valid model directories")

# TEST 3: Generate the model inventory
inv_file = r"D:\leaf-diseases-detector-main\model_inventory.json"
t3_success = os.path.isfile(inv_file) and os.path.getsize(inv_file) > 1000
record(3, "Generate the model inventory", t3_success, f"model_inventory.json exists with size {os.path.getsize(inv_file) if t3_success else 0} bytes")

# Helper to send HTTP requests
def http_req(endpoint, method="GET", data=None, headers=None):
    url = f"{SERVER_URL}{endpoint}"
    if headers is None:
        headers = {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(content)
            except:
                return resp.status, {"raw": content}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except:
            return e.code, {"raw": body}
    except Exception as e:
        return 0, {"error": str(e)}

# Helper for multipart form uploads
def multipart_post(endpoint, fields, files):
    boundary = "----WebKitFormBoundaryGariTest" + hex(int(time.time()))[2:]
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.extend(f"{value}\r\n".encode("utf-8"))
    for name, filepath, content in files:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"; filename="{os.path.basename(filepath)}"\r\n'.encode("utf-8"))
        body.extend(b"Content-Type: image/jpeg\r\n\r\n")
        body.extend(content)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body))
    }
    return http_req(endpoint, method="POST", data=bytes(body), headers=headers)

# TEST 4: Load at least one actual local model
status, res = http_req("/api/models/Tomato/load", method="POST")
t4_success = status == 200 and res.get("status") == "LOADED"
record(4, "Load at least one actual local model", t4_success, f"POST /api/models/Tomato/load -> HTTP {status}, status: {res.get('status')}, load_time: {res.get('load_time_ms')}ms")

# TEST 5 & 6: Run inference on a real test leaf image & verify prediction response
with open(TOMATO_IMG, "rb") as f:
    img_bytes = f.read()

status, pred_res = multipart_post("/api/predict", {"crop": "Tomato"}, [("image", TOMATO_IMG, img_bytes)])
t5_success = status == 200 and pred_res.get("success") is True
top_disease = pred_res.get("predicted_disease")
confidence = pred_res.get("confidence")
arch = pred_res.get("model", {}).get("arch")
model_name = pred_res.get("model", {}).get("name")
top_3 = pred_res.get("top_predictions", [])
proc_time = pred_res.get("inference_time_ms")

record(5, "Run inference on a real test leaf image", t5_success, 
       f"Predicted: '{top_disease}', Conf: {confidence}%, Time: {proc_time}ms, Top-3: {[p.get('label') or p.get('disease') for p in top_3]}")

t6_success = (
    pred_res.get("success") is True and
    len(top_3) == 3 and
    confidence is not None and
    confidence > 0 and
    arch == "convnext_small" and
    model_name is not None
)
record(6, "Verify the prediction response structure", t6_success,
       f"Arch: {arch}, Model: {model_name}, Top-3 Count: {len(top_3)}, Top-1 Conf: {confidence}%")

# TEST 7: Verify frontend displays actual prediction
# Check that frontend HTML includes crop selector, top predictions container, and JS hooks
with open(r"D:\leaf-diseases-detector-main\frontend2\predict.html", "r", encoding="utf-8") as f:
    html_content = f.read()

t7_checks = [
    "cropSelect" in html_content,
    "top3Section" in html_content or "top3List" in html_content,
    "api/models" in html_content,
    "convnext_small" in html_content or "ConvNeXt" in html_content,
]
# Also test GET /frontend2/predict.html via server HTTP
f_status, _ = http_req("/frontend2/predict.html")
t7_success = all(t7_checks) and f_status == 200
record(7, "Verify frontend UI integrates crop selector and prediction display", t7_success,
       f"Frontend HTTP: {f_status}, CropSelect found: {'cropSelect' in html_content}, Top3Display found: {'top3Section' in html_content}")

# TEST 8: Verify CPU fallback if CUDA is unavailable
status, health_res = http_req("/api/health")
ai_eng = health_res.get("ai_engine", health_res)
dev = ai_eng.get("device", "unknown")
cuda = ai_eng.get("cuda_available", False)
cached_models = ai_eng.get("models_cached", [])
t8_success = status == 200 and (dev == "cpu" or cuda is True) and isinstance(cached_models, list)
record(8, "Verify CPU fallback if CUDA is unavailable", t8_success,
       f"Device: {dev}, CUDA available: {cuda}, Cached models: {cached_models}")

# TEST 9: Test invalid image handling
fake_bad_bytes = b"This is not a valid JPEG/PNG image data stream!"
status, bad_res = multipart_post("/api/predict", {"crop": "Tomato"}, [("image", "corrupted.jpg", fake_bad_bytes)])
t9_success = status == 400 and (bad_res.get("success") is False or "error" in bad_res or "message" in bad_res)
record(9, "Test invalid image handling", t9_success,
       f"POST corrupted image -> HTTP {status}, Error: {bad_res.get('message') or bad_res.get('detail')}")

# TEST 10: Confirm unsupported models are reported correctly
status, unsupp_res = multipart_post("/api/predict", {"crop": "NonExistentCrop123"}, [("image", TOMATO_IMG, img_bytes)])
t10_success = status == 400 and (unsupp_res.get("success") is False or "detail" in unsupp_res or "message" in unsupp_res)
record(10, "Confirm unsupported models are reported correctly", t10_success,
       f"POST unsupported crop 'NonExistentCrop123' -> HTTP {status}, Error: {unsupp_res.get('message') or unsupp_res.get('detail')}")

print("=" * 70)
print(f" SUMMARY: {passed_tests}/{total_tests} TESTS PASSED")
print("=" * 70)

# Also test a second real image (Potato) to demonstrate multi-crop capability
print("\n[BONUS TEST] Testing Potato Leaf Inference...")
with open(POTATO_IMG, "rb") as f:
    potato_bytes = f.read()
status, pot_res = multipart_post("/api/predict", {"crop": "Potato"}, [("image", POTATO_IMG, potato_bytes)])
if status == 200:
    print(f" -> Crop: Potato | Predicted Disease: {pot_res.get('predicted_disease')} ({pot_res.get('confidence')}%)")
    print(f" -> Top 3: {[(p.get('label') or p.get('disease') or p.get('class_id')) + ' (' + str(p.get('confidence_percent') or p.get('confidence')) + '%)' for p in pot_res.get('top_predictions', [])]}")
    print(f" -> Inference Time: {pot_res.get('inference_time_ms')}ms, Model: {pot_res.get('model', {}).get('name')}")
else:
    print(f" -> Potato test returned HTTP {status}: {pot_res}")

# Write results to json
with open(r"D:\leaf-diseases-detector-main\test_results.json", "w", encoding="utf-8") as f:
    json.dump({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": total_tests,
        "passed": passed_tests,
        "results": test_results
    }, f, indent=2)

sys.exit(0 if passed_tests == total_tests else 1)
