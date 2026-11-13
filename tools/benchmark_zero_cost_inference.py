"""
GARI AI Model Benchmark: CPU Inference, Peak RAM, and LRU Cache Eviction
Measures resource consumption under Free Tier constraints (2 vCPU, 512MB vs 16GB RAM).
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import psutil
import time
from PIL import Image
import torch
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gari_benchmark")

def get_process_ram_mb() -> float:
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

def run_benchmark():
    ram_init = get_process_ram_mb()
    logger.info("Initial Process RAM: %.2f MB", ram_init)

    from gari_inference_engine import engine

    ram_after_engine_init = get_process_ram_mb()
    logger.info("RAM after Engine Init (Registry discovery): %.2f MB (+%.2f MB)",
                ram_after_engine_init, ram_after_engine_init - ram_init)

    # Test dummy image
    img = Image.new("RGB", (224, 224), color=(73, 109, 137))

    # Priority Crops to benchmark
    test_crops = ["Tomato", "Rice", "Maize", "Coffee", "Black_Pepper"]

    results = []
    for crop in test_crops:
        t0 = time.perf_counter()
        ram_before = get_process_ram_mb()

        # Execute diagnosis
        res = engine.run_crop_disease_model(img, crop)
        duration_ms = (time.perf_counter() - t0) * 1000
        ram_after = get_process_ram_mb()

        logger.info("Crop: %-12s | Time: %6.1f ms | RAM Before: %6.1f MB | RAM After: %6.1f MB (+%5.1f MB)",
                    crop, duration_ms, ram_before, ram_after, ram_after - ram_before)

        results.append({
            "crop": crop,
            "duration_ms": duration_ms,
            "ram_mb": ram_after,
            "disease": res.get("disease_name_vi")
        })

    # Benchmark Global ViT
    t0 = time.perf_counter()
    ram_before = get_process_ram_mb()
    vit_res = engine.run_global_crop_identification(img)
    vit_duration_ms = (time.perf_counter() - t0) * 1000
    ram_after = get_process_ram_mb()
    logger.info("Global ViT Model | Time: %6.1f ms | RAM Before: %6.1f MB | RAM After: %6.1f MB (+%5.1f MB)",
                vit_duration_ms, ram_before, ram_after, ram_after - ram_before)

    # Check cache status
    cached_models = list(engine.cache.keys())
    logger.info("Cached Models in Memory: %s (Total: %d, Max: %d)",
                cached_models, len(cached_models), engine.max_cached)

    peak_ram = get_process_ram_mb()
    logger.info("Peak RAM under LRU Cache: %.2f MB", peak_ram)

    print("\n" + "=" * 60)
    print(" FREE TIER COMPATIBILITY VERDICT")
    print("=" * 60)
    print(f"Total Peak RAM: {peak_ram:.1f} MB")
    if peak_ram > 512:
        print("[FAIL] Render Free (512 MB): Incompatible - will trigger Out-Of-Memory (OOM) SIGKILL.")
    else:
        print("[PASS] Render Free (512 MB): Compatible.")

    if peak_ram < 16384:
        print(f"[PASS] Hugging Face Spaces CPU Basic (16,384 MB): 100% Compatible ({peak_ram / 16384 * 100:.1f}% RAM used).")
    print("=" * 60)

if __name__ == "__main__":
    run_benchmark()
