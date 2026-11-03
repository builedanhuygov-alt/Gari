"""
GARI AI LAB — Reproducible AI Pipeline Evaluation Suite
Evaluates:
1. Crop Identification Pipeline (Original 16 vs New 36 vs Gari Ensemble Gate)
2. Disease Classification Pipeline (Multi-class disease models)
3. Calibration metrics (ECE - Expected Calibration Error & Reliability Diagrams)
"""

import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import torch
from PIL import Image

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gari_inference_engine import engine
from gari_crop_registry import normalize_crop_id

WORKSPACE_DIR = Path("D:/leaf-diseases-detector-main")
DATA_DIR = WORKSPACE_DIR / "data" / "organized" / "PlantVillage"


def calculate_ece(confidences: List[float], accuracies: List[bool], n_bins: int = 10) -> float:
    """Computes Expected Calibration Error (ECE) across confidence bins."""
    if not confidences:
        return 0.0
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    total = len(confidences)

    for i in range(n_bins):
        b_low, b_high = bins[i], bins[i + 1]
        in_bin = [j for j, c in enumerate(confidences) if b_low <= c < b_high or (i == n_bins - 1 and c == b_high)]
        if in_bin:
            bin_acc = np.mean([accuracies[j] for j in in_bin])
            bin_conf = np.mean([confidences[j] for j in in_bin])
            ece += (len(in_bin) / total) * abs(bin_acc - bin_conf)
    return float(ece)


def calculate_metrics(y_true: List[str], y_pred: List[str], classes: List[str]) -> Dict[str, Any]:
    """Calculates accuracy, per-class precision, recall, F1, and Macro F1."""
    acc = np.mean([1 if t == p else 0 for t, p in zip(y_true, y_pred)]) if y_true else 0.0

    cm = defaultdict(lambda: defaultdict(int))
    for t, p in zip(y_true, y_pred):
        cm[t][p] += 1

    per_class = {}
    f1_list = []

    for cls in classes:
        tp = cm[cls][cls]
        fp = sum(cm[other][cls] for other in classes if other != cls)
        fn = sum(cm[cls][other] for other in classes if other != cls)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

        per_class[cls] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "support": tp + fn,
        }
        if tp + fn > 0:
            f1_list.append(f1)

    macro_f1 = np.mean(f1_list) if f1_list else 0.0

    return {
        "accuracy": round(float(acc), 4),
        "macro_f1": round(float(macro_f1), 4),
        "per_class": per_class,
        "confusion_matrix": {t: dict(cm[t]) for t in classes},
    }


def evaluate_crop_detection(sample_per_class: int = 25) -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print("PHASE 7.1 — CROP DETECTOR BENCHMARK")
    print(f"Sampling {sample_per_class} test images per category from held-out dataset...")
    print("=" * 70)

    # Category -> True Crop ID
    categories = {
        "Pepper__bell___Bacterial_spot": "Pepper",
        "Pepper__bell___healthy": "Pepper",
        "Potato___Early_blight": "Potato",
        "Potato___healthy": "Potato",
        "Potato___Late_blight": "Potato",
        "Tomato__Target_Spot": "Tomato",
        "Tomato__Tomato_mosaic_virus": "Tomato",
        "Tomato__Tomato_YellowLeaf__Curl_Virus": "Tomato",
        "Tomato_Bacterial_spot": "Tomato",
        "Tomato_Early_blight": "Tomato",
        "Tomato_healthy": "Tomato",
        "Tomato_Late_blight": "Tomato",
        "Tomato_Leaf_Mold": "Tomato",
        "Tomato_Septoria_leaf_spot": "Tomato",
        "Tomato_Spider_mites_Two_spotted_spider_mite": "Tomato",
    }

    crops = ["Pepper", "Potato", "Tomato"]

    # Collect sampled paths
    dataset_samples = []
    for cat_dir, crop in categories.items():
        folder = DATA_DIR / cat_dir
        if not folder.exists():
            continue
        all_imgs = sorted(list(folder.glob("*.jpg")) + list(folder.glob("*.JPG")))
        # Take images from the tail of the sorted list to avoid any training subset bias
        chosen = all_imgs[-sample_per_class:]
        for img_p in chosen:
            dataset_samples.append((img_p, crop, cat_dir))

    print(f"Total test images: {len(dataset_samples)} across {len(categories)} categories")

    # Benchmarks
    results_orig = {"y_true": [], "y_pred": [], "top3_correct": [], "confidences": []}
    results_new = {"y_true": [], "y_pred": [], "top3_correct": [], "confidences": []}
    results_gate = {"y_true": [], "y_pred": [], "top3_correct": [], "confidences": [], "states": defaultdict(int)}

    t0 = time.time()
    for img_p, true_crop, cat_dir in dataset_samples:
        try:
            im = Image.open(img_p)
        except Exception:
            continue

        # 1. Original detector
        preds_orig = engine._infer_detector_raw("detectors/original", im)
        top1_orig = normalize_crop_id(preds_orig[0][0]) if preds_orig else "None"
        top3_orig = [normalize_crop_id(c) for c, _ in preds_orig[:3]]
        conf_orig = preds_orig[0][1] if preds_orig else 0.0

        results_orig["y_true"].append(true_crop)
        results_orig["y_pred"].append(top1_orig)
        results_orig["top3_correct"].append(true_crop in top3_orig)
        results_orig["confidences"].append(conf_orig)

        # 2. New detector
        preds_new = engine._infer_detector_raw("detectors/new", im)
        top1_new = normalize_crop_id(preds_new[0][0]) if preds_new else "None"
        top3_new = [normalize_crop_id(c) for c, _ in preds_new[:3]]
        conf_new = preds_new[0][1] if preds_new else 0.0

        results_new["y_true"].append(true_crop)
        results_new["y_pred"].append(top1_new)
        results_new["top3_correct"].append(true_crop in top3_new)
        results_new["confidences"].append(conf_new)

        # 3. Gari Crop Validation Gate
        gate_res = engine.evaluate_crop_validation_gate(im)
        sel_crop = gate_res.get("selected_crop") or (gate_res["candidates"][0]["crop_id"] if gate_res.get("candidates") else "None")
        top3_gate = [c["crop_id"] for c in gate_res.get("candidates", [])[:3]]
        conf_gate = gate_res.get("confidence", 0.0)

        results_gate["y_true"].append(true_crop)
        results_gate["y_pred"].append(sel_crop)
        results_gate["top3_correct"].append(true_crop in top3_gate)
        results_gate["confidences"].append(conf_gate)
        results_gate["states"][gate_res["state"]] += 1

    latency = (time.time() - t0) / len(dataset_samples)

    # Compute metrics
    m_orig = calculate_metrics(results_orig["y_true"], results_orig["y_pred"], crops)
    top3_acc_orig = float(np.mean(results_orig["top3_correct"]))
    ece_orig = calculate_ece(results_orig["confidences"], [t == p for t, p in zip(results_orig["y_true"], results_orig["y_pred"])])

    m_new = calculate_metrics(results_new["y_true"], results_new["y_pred"], crops)
    top3_acc_new = float(np.mean(results_new["top3_correct"]))
    ece_new = calculate_ece(results_new["confidences"], [t == p for t, p in zip(results_new["y_true"], results_new["y_pred"])])

    m_gate = calculate_metrics(results_gate["y_true"], results_gate["y_pred"], crops)
    top3_acc_gate = float(np.mean(results_gate["top3_correct"]))
    ece_gate = calculate_ece(results_gate["confidences"], [t == p for t, p in zip(results_gate["y_true"], results_gate["y_pred"])])

    print("\n--- RESULTS COMPARISON TABLE ---")
    print(f"{'Detector / Pipeline':30s} | {'Top-1 Acc':10s} | {'Top-3 Acc':10s} | {'Macro F1':10s} | {'ECE':8s}")
    print("-" * 78)
    print(f"{'Original Detector (16 crops)':30s} | {m_orig['accuracy']*100:8.2f}% | {top3_acc_orig*100:8.2f}% | {m_orig['macro_f1']:10.4f} | {ece_orig:8.4f}")
    print(f"{'New Detector (36 crops)':30s} | {m_new['accuracy']*100:8.2f}% | {top3_acc_new*100:8.2f}% | {m_new['macro_f1']:10.4f} | {ece_new:8.4f}")
    print(f"{'Gari Ensemble Gate (Ours)':30s} | {m_gate['accuracy']*100:8.2f}% | {top3_acc_gate*100:8.2f}% | {m_gate['macro_f1']:10.4f} | {ece_gate:8.4f}")

    print("\n--- Gari Gate States Breakdown ---")
    for st, count in sorted(results_gate["states"].items()):
        pct = (count / len(dataset_samples)) * 100
        print(f"  {st:25s}: {count:4d} images ({pct:5.1f}%)")

    return {
        "original_16": {"top1": m_orig["accuracy"], "top3": top3_acc_orig, "macro_f1": m_orig["macro_f1"], "ece": ece_orig, "per_class": m_orig["per_class"]},
        "new_36": {"top1": m_new["accuracy"], "top3": top3_acc_new, "macro_f1": m_new["macro_f1"], "ece": ece_new, "per_class": m_new["per_class"]},
        "gari_gate": {"top1": m_gate["accuracy"], "top3": top3_acc_gate, "macro_f1": m_gate["macro_f1"], "ece": ece_gate, "per_class": m_gate["per_class"], "states": dict(results_gate["states"])},
        "latency_sec": latency,
        "sample_count": len(dataset_samples),
    }


def evaluate_tomato_disease_model(sample_per_class: int = 25) -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print("PHASE 7.2 — DISEASE CLASSIFIER BENCHMARK (TOMATO CONVNEXT)")
    print(f"Sampling {sample_per_class} test images per disease class...")
    print("=" * 70)

    # Tomato classes mapping from folder name to class ID in models/Tomato/config.json
    folder_to_class = {
        "Tomato_Bacterial_spot": "Bacterial_spot",
        "Tomato_Early_blight": "Early_blight",
        "Tomato_healthy": "Healthy",
        "Tomato_Late_blight": "Late_blight",
        "Tomato_Leaf_Mold": "Leaf_Mold",
        "Tomato_Septoria_leaf_spot": "Septoria_leaf_spot",
        "Tomato_Spider_mites_Two_spotted_spider_mite": "Spider_mites_Two_spotted_spider_mite",
        "Tomato__Target_Spot": "Target_Spot",
        "Tomato__Tomato_YellowLeaf__Curl_Virus": "Tomato_YellowLeaf__Curl_Virus",
        "Tomato__Tomato_mosaic_virus": "Tomato_mosaic_virus",
    }

    entry = engine.get_model_entry("Tomato")
    if not entry:
        print("Tomato model not found!")
        return {}

    all_classes = list(folder_to_class.values())

    y_true = []
    y_pred = []
    confidences = []
    top3_hits = []

    samples = []
    for folder_name, cls_id in folder_to_class.items():
        folder = DATA_DIR / folder_name
        if not folder.exists():
            continue
        all_imgs = sorted(list(folder.glob("*.jpg")) + list(folder.glob("*.JPG")))
        for img_p in all_imgs[-sample_per_class:]:
            samples.append((img_p, cls_id))

    print(f"Evaluating on {len(samples)} held-out Tomato disease photos...")

    for img_p, true_cls in samples:
        try:
            im = Image.open(img_p)
        except Exception:
            continue

        res = engine.predict(im, crop_id="Tomato", top_k=3)
        pred_cls = res.get("class_id", "Unknown")
        conf = res.get("confidence", 0.0)
        top3_classes = [p["class_id"] for p in res.get("top_predictions", [])]

        y_true.append(true_cls)
        y_pred.append(pred_cls)
        confidences.append(conf)
        top3_hits.append(true_cls in top3_classes)

    metrics = calculate_metrics(y_true, y_pred, all_classes)
    top3_acc = float(np.mean(top3_hits))
    ece = calculate_ece(confidences, [t == p for t, p in zip(y_true, y_pred)])

    print(f"\nAccuracy: {metrics['accuracy']*100:.2f}%")
    print(f"Top-3 Accuracy: {top3_acc*100:.2f}%")
    print(f"Macro F1: {metrics['macro_f1']:.4f}")
    print(f"ECE (Expected Calibration Error): {ece:.4f}")

    print("\n--- Per-Class Tomato Disease Performance ---")
    print(f"{'Disease Class':35s} | {'Precision':10s} | {'Recall':10s} | {'F1':10s} | {'Support':8s}")
    print("-" * 82)
    for cls_name in all_classes:
        p = metrics["per_class"].get(cls_name, {})
        print(f"{cls_name:35s} | {p.get('precision', 0):10.4f} | {p.get('recall', 0):10.4f} | {p.get('f1', 0):10.4f} | {p.get('support', 0):8d}")

    return {
        "accuracy": metrics["accuracy"],
        "top3_accuracy": top3_acc,
        "macro_f1": metrics["macro_f1"],
        "ece": ece,
        "per_class": metrics["per_class"],
        "sample_count": len(samples),
    }


if __name__ == "__main__":
    t_start = time.time()
    crop_eval = evaluate_crop_detection(sample_per_class=20)
    disease_eval = evaluate_tomato_disease_model(sample_per_class=20)
    total_time = round(time.time() - t_start, 2)

    eval_summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_time_seconds": total_time,
        "crop_evaluation": crop_eval,
        "disease_evaluation": disease_eval,
    }

    out_file = WORKSPACE_DIR / "scratch" / "evaluation_results.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(eval_summary, f, indent=2, ensure_ascii=False)

    print(f"\nEvaluation complete in {total_time}s! Saved to {out_file}")
