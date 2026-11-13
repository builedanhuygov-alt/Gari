"""
GARI AI LAB — Diagnosis Performance Benchmarking & Profiling Tool
File: tests/benchmark_diagnosis_perf.py

Measures latency across repeated requests:
1. Cold start vs Warm cache
2. Measures End-to-End latency
3. Inspects server timing logs
4. Reports median and p95 latency
"""

import os
import sys
import time
from pathlib import Path
import numpy as np
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import gari_auth

def run_benchmark(image_path: Path, mode: str = "auto", crop: str = None, iterations: int = 10):
    print("=" * 85)
    print(f" BENCHMARK: {image_path.name} | Mode: {mode} | Crop: {crop} | Runs: {iterations}")
    print("=" * 85)

    token = gari_auth.create_session(user_id=1)
    headers = {"Authorization": f"Bearer {token}"}

    with open(image_path, "rb") as f:
        img_bytes = f.read()

    latencies = []
    infer_latencies = []
    results = []

    for i in range(1, iterations + 1):
        files = {"image": (image_path.name, img_bytes, "image/jpeg")}
        data = {"mode": mode, "consent_store_image": "false", "save_history": "true"}
        if crop:
            data["crop"] = crop

        t0 = time.perf_counter()
        res = requests.post("http://localhost:8000/api/plant/diagnose", headers=headers, files=files, data=data)
        t_elapsed_ms = (time.perf_counter() - t0) * 1000.0

        latencies.append(t_elapsed_ms)
        if res.status_code == 200:
            json_res = res.json()
            reported_infer_ms = json_res.get("inference_time_ms", 0.0)
            infer_latencies.append(reported_infer_ms)
            status = json_res.get("status")
            disease = json_res.get("prediction") or json_res.get("disease_name_vi")
            crop_name = json_res.get("crop_name") or json_res.get("crop_id")
            conf = json_res.get("confidence") or json_res.get("disease_score")
            print(f"  [Run {i:02d}] HTTP {res.status_code} | Total: {t_elapsed_ms:7.2f} ms | Model Infer: {reported_infer_ms:7.2f} ms | Status: {status} | Crop: {crop_name} | Disease: {disease} ({conf})")
            results.append(json_res)
        else:
            print(f"  [Run {i:02d}] HTTP {res.status_code} | Total: {t_elapsed_ms:7.2f} ms | Error: {res.text[:100]}")

    median_lat = np.median(latencies)
    p95_lat = np.percentile(latencies, 95)
    min_lat = np.min(latencies)
    max_lat = np.max(latencies)

    infer_med = np.median(infer_latencies) if infer_latencies else 0
    infer_p95 = np.percentile(infer_latencies, 95) if infer_latencies else 0
    infer_min = np.min(infer_latencies) if infer_latencies else 0
    infer_max = np.max(infer_latencies) if infer_latencies else 0

    print("-" * 85)
    print(f" END-TO-END LATENCY: Min: {min_lat:7.2f} ms | Median: {median_lat:7.2f} ms | P95: {p95_lat:7.2f} ms | Max: {max_lat:7.2f} ms")
    print(f" MODEL INFERENCE   : Min: {infer_min:7.2f} ms | Median: {infer_med:7.2f} ms | P95: {infer_p95:7.2f} ms | Max: {infer_max:7.2f} ms")
    print("=" * 85)
    return latencies, results

if __name__ == "__main__":
    tomato_img = next(Path("data/organized/PlantVillage/Tomato_Bacterial_spot").glob("*.JPG"))

    print("\n--- TEST 1: Real Tomato Leaf (Auto Mode - 10 iterations) ---")
    run_benchmark(tomato_img, mode="auto", iterations=10)

    print("\n--- TEST 2: Real Tomato Leaf (Manual Mode - Crop: Tomato - 10 iterations) ---")
    run_benchmark(tomato_img, mode="manual", crop="Tomato", iterations=10)
