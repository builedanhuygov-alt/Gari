"""
Empirical CPU Inference Benchmark for Sprint 6.1
Measures real performance under PyTorch CPU execution:
- Model load time
- Memory footprint (RAM before and after)
- Cold-start latency
- Warm inference latency (10 iterations)
- Median & P95 latency
- Gate 1 (Leaf Validation) latency
- Dual-Gate full pipeline latency
"""

import time
import os
import sys
import json
import statistics
import psutil
from PIL import Image
import torch

sys.path.insert(0, os.path.abspath("."))
from gari_inference_engine import GariInferenceEngine, validate_leaf_gate

def get_ram_mb():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

def run_benchmark():
    print("=" * 60)
    print("GARI SPRINT 6.1 — EMPIRICAL CPU INFERENCE BENCHMARK")
    print("=" * 60)

    initial_ram = get_ram_mb()
    print(f"Initial Process RAM: {initial_ram:.2f} MB")

    engine = GariInferenceEngine()
    print(f"Discovered models in registry: {len(engine.registry)}")
    print(f"Engine device: {engine.device}")

    # Load test images
    valid_leaf_path = "data/organized/Tomato/Tomato_healthy/000146ff-92a4-4db6-90ad-8fce2ae4fddd___GH_HL Leaf 259.1.JPG"
    non_leaf_path = "data/test_samples_17/5_non_leaf.jpg"
    blurry_leaf_path = "data/test_samples_17/9_blurry_leaf.jpg"

    valid_img = Image.open(valid_leaf_path).convert("RGB")
    non_leaf_img = Image.open(non_leaf_path).convert("RGB")
    blurry_img = Image.open(blurry_leaf_path).convert("RGB")

    print("\n--- 1. Gate 1: Leaf Validation Gate Benchmark ---")
    gate_latencies = []
    for _ in range(20):
        t0 = time.perf_counter()
        res = validate_leaf_gate(valid_img)
        gate_latencies.append((time.perf_counter() - t0) * 1000.0)

    gate_med = statistics.median(gate_latencies)
    gate_p95 = statistics.quantiles(gate_latencies, n=20)[18] if len(gate_latencies) >= 20 else max(gate_latencies)
    print(f"Gate 1 Decision on Valid Leaf: {res['status']} (score: {res.get('score', 0):.3f})")
    print(f"Gate 1 Median Latency: {gate_med:.2f} ms")
    print(f"Gate 1 P95 Latency: {gate_p95:.2f} ms")

    res_non_leaf = validate_leaf_gate(non_leaf_img)
    print(f"Gate 1 Decision on Non-Leaf: {res_non_leaf['status']} (score: {res_non_leaf.get('score', 0):.3f})")
    res_blurry = validate_leaf_gate(blurry_img)
    print(f"Gate 1 Decision on Blurry Leaf: {res_blurry['status']} (score: {res_blurry.get('score', 0):.3f})")

    models_to_test = ["Tomato", "Maize", "detectors/original"]
    results = {}

    for mid in models_to_test:
        print(f"\n--- 2. Benchmarking Model: {mid} ---")
        ram_before_load = get_ram_mb()
        t_load_0 = time.perf_counter()
        net, entry = engine.load_model(mid)
        load_time_sec = time.perf_counter() - t_load_0
        ram_after_load = get_ram_mb()
        delta_ram = ram_after_load - ram_before_load

        print(f"Model Load Time: {load_time_sec:.3f} s")
        print(f"Model RAM Footprint: {delta_ram:.2f} MB (Total RAM: {ram_after_load:.2f} MB)")

        # Prepare dummy tensor
        tensor = entry.preprocess(valid_img).to(engine.device)

        # Cold-start inference
        t_cold_0 = time.perf_counter()
        with torch.no_grad():
            _ = net(tensor)
        cold_latency_ms = (time.perf_counter() - t_cold_0) * 1000.0
        print(f"Cold-Start Latency: {cold_latency_ms:.2f} ms")

        # Warm inference (10 iterations)
        warm_latencies = []
        for _ in range(10):
            t_warm_0 = time.perf_counter()
            with torch.no_grad():
                _ = net(tensor)
            warm_latencies.append((time.perf_counter() - t_warm_0) * 1000.0)

        warm_med = statistics.median(warm_latencies)
        warm_p95 = statistics.quantiles(warm_latencies, n=10)[8] if len(warm_latencies) >= 10 else max(warm_latencies)
        warm_mean = statistics.mean(warm_latencies)

        print(f"Warm Inference Median: {warm_med:.2f} ms")
        print(f"Warm Inference P95: {warm_p95:.2f} ms")
        print(f"Warm Inference Mean: {warm_mean:.2f} ms")

        results[mid] = {
            "load_time_sec": round(load_time_sec, 3),
            "ram_delta_mb": round(delta_ram, 2),
            "total_ram_mb": round(ram_after_load, 2),
            "cold_latency_ms": round(cold_latency_ms, 2),
            "warm_median_ms": round(warm_med, 2),
            "warm_p95_ms": round(warm_p95, 2),
            "warm_mean_ms": round(warm_mean, 2)
        }

    print("\n--- 3. Full Dual-Gate Pipeline End-to-End Latency ---")
    pipe_latencies = []
    for _ in range(5):
        t_pipe_0 = time.perf_counter()
        pred = engine.predict(valid_img, crop_id="Tomato", mode="manual")
        pipe_latencies.append((time.perf_counter() - t_pipe_0) * 1000.0)

    pipe_med = statistics.median(pipe_latencies)
    pipe_p95 = max(pipe_latencies)
    print(f"Full Dual-Gate Pipeline Median: {pipe_med:.2f} ms")
    print(f"Full Dual-Gate Pipeline P95: {pipe_p95:.2f} ms")
    print(f"Full Dual-Gate Result Status: {pred.get('status')} | Disease: {pred.get('disease_name_vi')} ({pred.get('confidence_percent')}%)")

    final_ram = get_ram_mb()
    print(f"\nFinal Process RAM: {final_ram:.2f} MB (Peak Delta: {final_ram - initial_ram:.2f} MB)")

    out_data = {
        "gate1": {
            "median_ms": round(gate_med, 2),
            "p95_ms": round(gate_p95, 2),
            "valid_leaf_status": res['status'],
            "non_leaf_status": res_non_leaf['status'],
            "blurry_leaf_status": res_blurry['status']
        },
        "models": results,
        "dual_gate_e2e": {
            "median_ms": round(pipe_med, 2),
            "p95_ms": round(pipe_p95, 2)
        },
        "ram": {
            "initial_mb": round(initial_ram, 2),
            "final_mb": round(final_ram, 2),
            "delta_mb": round(final_ram - initial_ram, 2)
        }
    }

    with open("scratch/benchmark_results_sprint6_1.json", "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2, ensure_ascii=False)
    print("Benchmark results saved to scratch/benchmark_results_sprint6_1.json")

if __name__ == "__main__":
    run_benchmark()
