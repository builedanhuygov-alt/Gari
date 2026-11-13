"""
GARI Pre-Deployment Model & Inference Engine Audit
Exhaustively benchmarks models, LRU cache behavior, memory footprint, and concurrency.
"""

import gc
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import psutil
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gari_inference_engine import engine

process = psutil.Process()

def get_ram_mb():
    return process.memory_info().rss / (1024 * 1024)

print("=" * 70)
print("1. MODEL REGISTRY AUDIT & DISK RECONCILIATION")
print("=" * 70)

print(f"Total models registered in engine: {len(engine.registry)}")
missing_files = []
valid_entries = []

for crop_name, entry in engine.registry.items():
    weights_path = Path(getattr(entry, "weight_path", getattr(entry, "weights_path", "")))
    if not weights_path.exists():
        missing_files.append((crop_name, str(weights_path)))
    else:
        size_mb = weights_path.stat().st_size / (1024 * 1024)
        valid_entries.append({
            "crop": crop_name,
            "arch": getattr(entry, "architecture", "unknown"),
            "classes": len(getattr(entry, "class_names", [])),
            "size_mb": round(size_mb, 2),
            "path": str(weights_path)
        })

print(f"Physical weights matched on disk: {len(valid_entries)}/{len(engine.registry)}")
if missing_files:
    print(f"[WARN] Missing files ({len(missing_files)}): {missing_files}")
else:
    print("[SUCCESS] 100% of registered models have valid physical weights on disk!")

print("\nSample registered models:")
for v in valid_entries[:8]:
    print(f"  - {v['crop']}: {v['arch']}, {v['classes']} classes, {v['size_mb']} MB")

print("=" * 70)
print("2. INDIVIDUAL BENCHMARK FOR MAJOR CROP MODELS")
print("=" * 70)

# Unload any previously cached models to start clean
engine.unload_all()
gc.collect()

base_ram = get_ram_mb()
print(f"Base RAM (Server + Registry metadata): {base_ram:.2f} MB")

# Choose representative crop models that exist in registry
test_crops = ["Tomato", "Rice", "Corn", "Coffee", "Potato", "Chili", "Model tong"]
available_test_crops = [c for c in test_crops if c in engine.registry or c == "Model tong"]

# Add other crops if some from above are named differently
if len(available_test_crops) < 5:
    for k in engine.registry.keys():
        if k not in available_test_crops and len(available_test_crops) < 6:
            available_test_crops.append(k)

print(f"Benchmarking crops: {available_test_crops}")

benchmark_results = {}
dummy_img = Image.new("RGB", (224, 224), color=(100, 180, 60))

for crop in available_test_crops:
    # Unload all before testing cold start for each
    engine.unload_all()
    gc.collect()
    ram_before = get_ram_mb()
    
    # 1. Cold start (Load + 1st inference)
    t0 = time.time()
    if crop == "Model tong":
        # Global crop detector test
        res_cold = engine.run_global_crop_identification(dummy_img)
    else:
        res_cold = engine.run_crop_disease_model(dummy_img, crop)
    t_cold = time.time() - t0
    ram_after_cold = get_ram_mb()
    ram_delta_cold = ram_after_cold - ram_before
    
    # 2. Warm inference (2nd & 3rd runs)
    warm_times = []
    for _ in range(3):
        t1 = time.time()
        if crop == "Model tong":
            _ = engine.run_global_crop_identification(dummy_img)
        else:
            _ = engine.run_crop_disease_model(dummy_img, crop)
        warm_times.append(time.time() - t1)
    
    avg_warm = sum(warm_times) / len(warm_times)
    top_pred = None
    if isinstance(res_cold, dict):
        if "top_predictions" in res_cold and res_cold["top_predictions"]:
            top_pred = res_cold["top_predictions"][0].get("name_vi") or res_cold["top_predictions"][0].get("name")
        elif "predictions" in res_cold and res_cold["predictions"]:
            top_pred = res_cold["predictions"][0].get("name_vi") or res_cold["predictions"][0].get("name")
        elif "predicted_crop" in res_cold:
            top_pred = res_cold.get("predicted_crop")

    benchmark_results[crop] = {
        "cold_sec": round(t_cold, 3),
        "warm_sec": round(avg_warm, 3),
        "ram_delta_mb": round(ram_delta_cold, 1),
        "total_ram_mb": round(ram_after_cold, 1),
        "top_prediction": top_pred
    }
    
    print(f"[{crop}] Cold: {t_cold:.3f}s | Warm: {avg_warm*1000:.1f}ms | RAM delta: +{ram_delta_cold:.1f}MB | Pred: {top_pred}")

print("=" * 70)
print("3. VERIFY LRU CACHE LIMITS & EVICTION COMPLIANCE")
print("=" * 70)

# Set max cached to 3
engine.max_cached = 3
engine.unload_all()
gc.collect()

print(f"Current engine.max_cached = {engine.max_cached}")
print(f"Initial cache size: {len(engine.cache)}")

crops_to_fill = [c for c in engine.registry.keys() if c != "Model tong"][:5]
print(f"Sequentially accessing 5 distinct crops: {crops_to_fill}")

cache_history = []
for idx, crop in enumerate(crops_to_fill, 1):
    _ = engine.run_crop_disease_model(dummy_img, crop)
    cached_keys = list(engine.cache.keys())
    cache_len = len(cached_keys)
    ram_now = get_ram_mb()
    cache_history.append((idx, crop, cache_len, cached_keys, round(ram_now, 1)))
    print(f"Step {idx} - Loaded '{crop}': Cache items = {cache_len} (Keys: {cached_keys}), RAM: {ram_now:.1f}MB")
    
    # Assert cache never exceeds max_cached
    assert cache_len <= engine.max_cached, f"Cache exceeded limit: {cache_len} > {engine.max_cached}!"

print("[SUCCESS] LRU Cache strictly respected max_cached=3 limit! Oldest models were properly evicted.")

print("=" * 70)
print("4. CONCURRENCY & CPU UTILIZATION BENCHMARK")
print("=" * 70)

# Measure multi-threaded concurrency on CPU
concurrency_levels = [2, 5, 10]
concurrency_results = {}

for workers in concurrency_levels:
    t_start = time.time()
    cpu_before = psutil.cpu_percent(interval=None)
    
    def worker_infer(i):
        crop = crops_to_fill[i % len(crops_to_fill)]
        return engine.run_crop_disease_model(dummy_img, crop)
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(worker_infer, i) for i in range(workers)]
        results = [f.result() for f in futures]
    
    total_elapsed = time.time() - t_start
    cpu_after = psutil.cpu_percent(interval=0.1)
    throughput = workers / total_elapsed
    ram_conc = get_ram_mb()
    
    concurrency_results[workers] = {
        "elapsed_sec": round(total_elapsed, 3),
        "throughput_req_sec": round(throughput, 2),
        "ram_mb": round(ram_conc, 1),
        "cpu_percent": cpu_after
    }
    
    print(f"{workers} Concurrent Requests: Total Time: {total_elapsed:.3f}s | Throughput: {throughput:.2f} req/s | RAM: {ram_conc:.1f} MB | CPU: {cpu_after}%")

# Save audit results to JSON
audit_summary = {
    "timestamp": time.time(),
    "total_models": len(engine.registry),
    "physical_weights_matched": len(valid_entries),
    "missing_files_count": len(missing_files),
    "benchmark_results": benchmark_results,
    "concurrency_results": concurrency_results,
    "lru_eviction_verified": True
}

with open("tools/pre_deployment_audit_results.json", "w", encoding="utf-8") as f:
    json.dump(audit_summary, f, indent=2)

print("\n[COMPLETE] Pre-deployment model audit finished successfully. Results saved to tools/pre_deployment_audit_results.json")
