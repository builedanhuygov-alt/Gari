# GARI AGRITECH AI LAB — SPRINT 6.1 BASELINE REPORT
**Document Reference:** `docs/SPRINT_6_1_BASELINE.md`  
**Execution Date:** 2026-11-11  
**Author:** Senior Machine Learning & Infrastructure Reliability Engineer  
**Sprint:** Sprint 6.1 (Core AI Pipeline Hardening & Dual-Gate Verification)  
**Status:** **ESTABLISHED & EMPIRICALLY VERIFIED**

---

## 1. REPOSITORY & ENVIRONMENT BASELINE

- **Working Directory:** `D:\leaf-diseases-detector-main`
- **Active Git Branch:** `gari-2.0-redesign`
- **Commit Base:** `2318ee75` (*Baseline: Pre-GARI 2.0 Redesign & Firebase Integration*)
- **Python Virtual Environment:** Python 3.13.0 on Windows AMD64 (`.venv/Scripts/python.exe`)
- **PyTorch Device:** `cpu` (Zero GPU requirement, aligned with cost minimization)
- **Host Security:** Windows Defender active with Real-Time Protection enabled. Zero exclusions, zero whitelisting.

---

## 2. SECURITY REMEDIATION BASELINE (PHASE 5.8 VERIFICATION)

Automated execution of `tests/test_phase5_8_remediation.py` verified 100% preservation of security controls:

| Check ID | Security Control | Verified Status | Evidence |
|---|---|---|---|
| **SEC-01** | Diagnosis Privacy | **VERIFIED** | Anonymous access returns HTTP 401; cross-tenant access returns HTTP 403. |
| **SEC-02** | No User 1 Fallback | **VERIFIED** | `/api/notifications` and `/api/calendar/tasks` strictly require session tokens. |
| **SEC-03** | Organization Isolation | **VERIFIED** | Cross-organization farm access rejected with HTTP 403. |
| **SEC-04** | Expert Assignment Integrity | **VERIFIED** | Unassigned agronomists rejected from reading/posting to private cases (HTTP 403). |

---

## 3. MODEL INVENTORY & REGISTRY BASELINE

The GARI inference engine registry discovers **51 active models** across the `models/` directory:
- **Global Crop Detectors:**
  - `detectors/original` (ConvNeXt-Small, 94.38 MB, 16 classes)
  - `detectors/new` (ConvNeXt-Small, 94.38 MB, 36 classes)
  - `Model tong` (ViT-Base PlantVillage, 327.38 MB)
  - `Model tong 2` (ViT-Base GBIF Pro, 327.38 MB, 14,829 plant species)
- **Crop-Specific Disease Models:**
  - 47 crop disease classification models (`Tomato`, `Maize`, `Coffee`, `Rice`, `Cassava`, `Potato`, `Pepper`, `Banana`, `Mango`, `Citrus`, `Grape`, `Apple`, etc.).
- **Model Lifecycle Manager:**
  - Default maximum concurrently cached models in RAM: **3** (`max_cached = 3`).
  - Model idle unloading timeout: **300.0 seconds** (`idle_timeout = 300.0`).
  - Auto-unload background daemon interval: **10.0 seconds**.
  - Model pre-loading: Disabled by default for lean memory footprint (`preload = False`).

---

## 4. DATASET INVENTORY BASELINE

| Dataset Partition | File Location | Class Breakdown | Sample Count |
|---|---|---|---|
| **Tomato Disease Dataset** | `data/organized/Tomato/` | 10 disease/healthy classes (Early blight, Late blight, Leaf mold, Mosaic virus, Yellow curl virus, Bacterial spot, Target spot, Septoria, Spider mites, Healthy) | **16,011 images** |
| **Potato Disease Dataset** | `data/organized/Potato/` | 3 classes (Early blight: 1000, Late blight: 1000, Healthy: 152) | **2,152 images** |
| **Bell Pepper Dataset** | `data/organized/Pepper/` | 2 classes (Bacterial spot: 997, Healthy: 1478) | **2,475 images** |
| **Adversarial / Non-Leaf Test Set** | `data/test_samples_17/` | Non-leaf, human face, animal, general object, blurry leaf, low-light leaf, multiple leaves | **7 images** |
| **Other 48 Crop Models** | External / Pre-Trained | Pre-compiled model weights in `models/` | *Raw images not present locally* |

> [!IMPORTANT]
> **Data Scarcity Notice:** While the model weights for 51 crops are physically present and functional in `models/`, local raw annotated datasets are available only for Tomato, Potato, and Pepper. Any calibration statement for other crops is constrained by this dataset scope.

---

## 5. EMPIRICAL CPU INFERENCE & MEMORY BASELINE

Measured on Intel/AMD x86_64 host running PyTorch CPU inference (`scratch/benchmark_results_sprint6_1.json`):

| Component / Model | Weight Size | Load Time | Cold Latency | Warm Median | Warm P95 | RAM Delta |
|---|---|---|---|---|---|---|
| **Gate 1 (Leaf Gate)** | N/A (Algorithmic) | 0.000 s | 5.70 ms | **2.93 ms** | **5.70 ms** | 0.00 MB |
| **Tomato (ConvNeXt)** | 94.38 MB | 0.801 s | 207.61 ms | **131.72 ms** | **159.77 ms** | +386.06 MB |
| **Maize (ConvNeXt)** | 94.38 MB | 0.801 s | 121.08 ms | **129.03 ms** | **152.73 ms** | +344.34 MB |
| **Detector (ConvNeXt)** | 94.38 MB | 0.871 s | 116.63 ms | **129.04 ms** | **138.20 ms** | +370.79 MB |
| **Dual-Gate Pipeline (E2E)** | Combined | Dynamic | 566.06 ms | **348.10 ms** | **566.06 ms** | Peak 1.05 GB |

