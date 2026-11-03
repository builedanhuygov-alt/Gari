"""
GARI AI LAB — Phase 8 Failure Reproduction & Pipeline Audit
Runs the saved uploaded leaf through the corrected dual-detector pipeline,
records all required metrics, and documents the failure diagnosis case.
"""

import json
import sys
import time
from pathlib import Path
from PIL import Image

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gari_inference_engine import engine

SAVED_UPLOAD_PATH = Path("D:/leaf-diseases-detector-main/database/uploads/leaf_2b67dcd175554c239fafb1b681bb9317.jpg")

print("=" * 75)
print("PHASE 8 — REPRODUCE AND AUDIT LATEST DIAGNOSIS FAILURE")
print("=" * 75)

if not SAVED_UPLOAD_PATH.exists():
    print(f"Uploaded image {SAVED_UPLOAD_PATH} not found on disk!")
    sys.exit(1)

img = Image.open(SAVED_UPLOAD_PATH)
print(f"Image Path: {SAVED_UPLOAD_PATH}")
print(f"Dimensions: {img.size} | Mode: {img.mode} | Format: {img.format}")

# Step 1: Preprocessing & Quality check
is_valid, q_reason, metrics = engine.evaluate_crop_validation_gate(img)["quality_metrics"], None, None
gate_eval = engine.evaluate_crop_validation_gate(img)

# Step 2: Crop Detector 16 output
t0 = time.perf_counter()
raw_orig = engine._infer_detector_raw("detectors/original", img)
lat_orig = (time.perf_counter() - t0) * 1000

# Step 3: Crop Detector 36 output
t1 = time.perf_counter()
raw_new = engine._infer_detector_raw("detectors/new", img)
lat_new = (time.perf_counter() - t1) * 1000

print("\n--- Crop Detector 16 (Original) Top 5 ---")
for cls, p in raw_orig[:5]:
    print(f"  {cls:20s}: {p*100:6.2f}%")
print(f"  Latency: {lat_orig:.2f} ms")

print("\n--- Crop Detector 36 (New) Top 5 ---")
for cls, p in raw_new[:5]:
    print(f"  {cls:20s}: {p*100:6.2f}%")
print(f"  Latency: {lat_new:.2f} ms")

print("\n--- Crop Validation Gate Evaluation ---")
print(f"  Gate State: {gate_eval['state']}")
print(f"  Can Proceed to Disease Model: {gate_eval['can_proceed_to_disease']}")
print(f"  Selected Crop: {gate_eval.get('selected_crop')}")
print(f"  Decision Confidence: {gate_eval.get('confidence_percent')}%")
print(f"  Reason: {gate_eval.get('reason')}")
print("  Top Candidates:")
for c in gate_eval.get("candidates", [])[:5]:
    print(f"    - {c['crop_full_name']:35s}: {c['percent']:5.2f}% (has model: {c['has_disease_model']})")

# Step 4: Run through complete engine.predict
t_pred = time.perf_counter()
full_result = engine.predict(img)
lat_total = (time.perf_counter() - t_pred) * 1000

print("\n--- End-to-End Corrected Pipeline Result ---")
print(f"  Status: {full_result.get('status')}")
print(f"  Crop: {full_result.get('crop')} ({full_result.get('crop_name')})")
print(f"  Predicted Disease: {full_result.get('prediction')}")
print(f"  Confidence: {full_result.get('confidence_percent')}%")
print(f"  Severity: {full_result.get('severity')}")
print(f"  Model Path: models/{full_result.get('crop')}/model.safetensors")
print(f"  Total Inference Latency: {lat_total:.2f} ms")

print("\nTop Disease Predictions:")
for p in full_result.get("top_predictions", []):
    print(f"  - {p['label']:25s} ({p['class_id']}): {p['confidence_percent']:5.2f}%")

# Save failure reproduction report
report = {
    "image_path": str(SAVED_UPLOAD_PATH),
    "image_dimensions": list(img.size),
    "detector_16_top5": raw_orig[:5],
    "detector_36_top5": raw_new[:5],
    "gate_state": gate_eval["state"],
    "selected_crop": gate_eval.get("selected_crop"),
    "disease_prediction": full_result.get("prediction"),
    "disease_confidence": full_result.get("confidence"),
    "total_latency_ms": lat_total,
    "full_result": full_result,
}

with open("scratch/failure_reproduction_report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print("\nReproduced failure case saved to scratch/failure_reproduction_report.json")
