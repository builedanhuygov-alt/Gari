"""
Empirical Leaf Gate Calibration Assessment for Sprint 6.1
Evaluates Gate 1 on available validation images:
- Valid leaves from Tomato, Pepper, Potato
- Non-leaf edge cases (face, animal, object, textures)
Calculates:
- Confusion Matrix (TP, FP, TN, FN)
- Precision, Recall, F1-Score
- False Acceptance Rate (FAR), False Rejection Rate (FRR)
- Per-crop accuracy
"""

import os
import sys
import json
from PIL import Image

sys.path.insert(0, os.path.abspath("."))
from gari_inference_engine import validate_leaf_gate

def evaluate_calibration():
    print("=" * 60)
    print("GARI SPRINT 6.1 — LEAF GATE CALIBRATION ASSESSMENT")
    print("=" * 60)

    # 1. Negative samples (Non-leaf images)
    neg_paths = [
        "data/test_samples_17/5_non_leaf.jpg",
        "data/test_samples_17/6_human_face.jpg",
        "data/test_samples_17/7_animal.jpg",
        "data/test_samples_17/8_general_object.jpg",
        "data/test_samples_17/9_blurry_leaf.jpg",
        "data/test_samples_17/10_low_light_leaf.jpg"
    ]

    # 2. Positive samples across available crops in data/organized/
    pos_samples = []
    crops = ["Tomato", "Potato", "Pepper"]

    for crop in crops:
        base_dir = f"data/organized/{crop}"
        if not os.path.exists(base_dir):
            continue
        for root, dirs, files in os.walk(base_dir):
            for f in files:
                if f.lower().endswith((".jpg", ".jpeg", ".png")):
                    pos_samples.append((crop, os.path.join(root, f)))
                    if len([s for s in pos_samples if s[0] == crop]) >= 50:
                        break
            if len([s for s in pos_samples if s[0] == crop]) >= 50:
                break

    print(f"Total evaluated positive leaf samples: {len(pos_samples)} (50 per crop)")
    print(f"Total evaluated negative/edge-case samples: {len(neg_paths)}")

    tp = 0 # leaf correctly identified as LEAF_VALID
    fn = 0 # leaf incorrectly rejected
    fp = 0 # non-leaf incorrectly accepted as LEAF_VALID
    tn = 0 # non-leaf correctly rejected

    per_crop_results = {c: {"total": 0, "accepted": 0, "rejected": 0} for c in crops}

    # Evaluate Positives
    for crop, path in pos_samples:
        try:
            img = Image.open(path).convert("RGB")
            res = validate_leaf_gate(img)
            per_crop_results[crop]["total"] += 1
            if res["status"] == "LEAF_VALID":
                tp += 1
                per_crop_results[crop]["accepted"] += 1
            else:
                fn += 1
                per_crop_results[crop]["rejected"] += 1
        except Exception as e:
            print(f"Error reading {path}: {e}")

    # Evaluate Negatives
    neg_details = []
    for path in neg_paths:
        try:
            img = Image.open(path).convert("RGB")
            res = validate_leaf_gate(img)
            is_accepted = (res["status"] == "LEAF_VALID")
            if is_accepted:
                fp += 1
            else:
                tn += 1
            neg_details.append({
                "file": os.path.basename(path),
                "decision": res["status"],
                "score": res.get("score", 0.0),
                "correctly_rejected": not is_accepted
            })
        except Exception as e:
            print(f"Error reading {path}: {e}")

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    far = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    frr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

    print("\n--- Calibration Metrics ---")
    print(f"True Positives (TP): {tp}")
    print(f"False Negatives (FN): {fn}")
    print(f"True Negatives (TN): {tn}")
    print(f"False Positives (FP): {fp}")
    print(f"Precision: {precision:.4f} ({precision*100:.2f}%)")
    print(f"Recall: {recall:.4f} ({recall*100:.2f}%)")
    print(f"F1-Score: {f1:.4f}")
    print(f"False Acceptance Rate (FAR): {far:.4f} ({far*100:.2f}%)")
    print(f"False Rejection Rate (FRR): {frr:.4f} ({frr*100:.2f}%)")

    print("\n--- Per-Crop Breakdown ---")
    for c, d in per_crop_results.items():
        if d["total"] > 0:
            rate = d["accepted"] / d["total"] * 100
            print(f"  {c}: Accepted {d['accepted']}/{d['total']} ({rate:.1f}%)")

    print("\n--- Negative Samples Detailed Decisions ---")
    for nd in neg_details:
        status_txt = "CORRECT REJECTION" if nd["correctly_rejected"] else "FALSE ACCEPTANCE"
        print(f"  {nd['file']}: {nd['decision']} (score={nd['score']:.3f}) -> {status_txt}")

    calibration_report = {
        "confusion_matrix": {"TP": tp, "FP": fp, "TN": tn, "FN": fn},
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "far": round(far, 4),
        "frr": round(frr, 4),
        "per_crop": per_crop_results,
        "negatives": neg_details
    }

    with open("scratch/calibration_results_sprint6_1.json", "w", encoding="utf-8") as f:
        json.dump(calibration_report, f, indent=2, ensure_ascii=False)
    print("\nResults saved to scratch/calibration_results_sprint6_1.json")

if __name__ == "__main__":
    evaluate_calibration()

