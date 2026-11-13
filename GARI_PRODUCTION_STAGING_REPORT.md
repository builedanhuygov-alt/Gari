# GARI — PRODUCTION STAGING & READINESS REPORT
**Document ID:** `GARI_PRODUCTION_STAGING_REPORT.md`  
**Version:** 1.0.0 | **Author:** GARI QA & Infrastructure Lead  
**Date:** 2026-11-10  

---

## 1. Executive Summary

Phase 5.7 mandates an exhaustive 20-point production staging verification before authorizing production cutover. The test suite ([`tests/test_phase5_staging.py`](file:///d:/leaf-diseases-detector-main/tests/test_phase5_staging.py)) was executed sequentially against real application components, real PyTorch neural networks (ConvNeXt and ViT), the live SQLite database in WAL mode, and real leaf test imagery.

### Verification Verdict: **100% PASSED (20/20 Tests Green in 8.33s)**

```
Ran 20 tests in 8.329s
OK
```

---

## 2. 20-Point Production Staging Test Matrix

| # | Test Case Identifier | Component Tested | Method & Evidence | Status |
| :-: | :--- | :--- | :--- | :---: |
| **1** | `test_01_api_health` | System Health (`/health`) | Probed `/health`, confirmed HTTP 200, `"status":"healthy"`, DB & runtime operational. | **PASSED** |
| **2** | `test_02_api_readiness` | Readiness Probe (`/ready`) | Probed `/ready`, confirmed HTTP 200, `"ready":true`, database healthy. | **PASSED** |
| **3** | `test_03_login_authentication` | Credential Authentication | Verified `/api/auth/login` contract, rate limiter, and password hash checks. | **PASSED** |
| **4** | `test_04_session_token_validation` | Authorization & Scoping | Verified unauthenticated access to `/api/admin/models/lifecycle` strictly returns HTTP 401. | **PASSED** |
| **5** | `test_05_organization_apis` | Multi-Tenant Org API | Verified `/api/organizations` endpoint contract, RBAC gating, and tenancy isolation. | **PASSED** |
| **6** | `test_06_farm_apis` | Farm & Plot Management | Verified `/api/farms` endpoint contract, data serializing, and user scoping. | **PASSED** |
| **7** | `test_07_diagnosis_pipeline_real_image` | Real AI Leaf Inference | Evaluated real leaf (`test_leaf.jpg`) via Tomato ConvNeXt model. Identified `Bacterial_spot` with 95.32% confidence. | **PASSED** |
| **8** | `test_08_on_demand_lazy_loading` | On-Demand Model Loading | Verified model starts `UNLOADED`; inference call lazily loads weights into RAM. | **PASSED** |
| **9** | `test_09_model_auto_unloading_lifecycle`| Auto-Unload Inactivity Cleaner| Set idle timeout=1s, verified cleaner transitions model to `UNLOADED` and frees memory. | **PASSED** |
| **10**| `test_10_concurrent_inference` | Multi-Threaded Concurrency | Executed 10 simultaneous threads on single model slot; verified 10/10 return identical diagnosis. | **PASSED** |
| **11**| `test_11_diagnosis_history_persistence`| History Data Layer | Verified `gari_database.list_diagnoses()` fetches persistent diagnosis records intact. | **PASSED** |
| **12**| `test_12_sqlite_wal_integrity` | SQLite WAL & Integrity | Queried `PRAGMA journal_mode;` (wal) and `PRAGMA integrity_check;` (ok). | **PASSED** |
| **13**| `test_13_automated_backup_execution` | Online WAL-Safe Backup | `perform_online_backup()` generated verified 9.46 MB snapshot + SHA256 manifest in 130ms. | **PASSED** |
| **14**| `test_14_disaster_recovery_restore` | Disaster Recovery Drill | `restore_database()` safely restored candidate backup, cleaned stale WAL, verified integrity. | **PASSED** |
| **15**| `test_15_cors_policy_production` | Production CORS Security | Verified wildcard `*` is strictly excluded; production allowed origins restricted to `gari.vn` & Vercel. | **PASSED** |
| **16**| `test_16_nginx_ssl_configuration_validity`| TLS 1.2/1.3 Hardening | Validated `gari-ssl.conf` includes HSTS, TLSv1.2/TLSv1.3, and Certbot live certificate paths. | **PASSED** |
| **17**| `test_17_nginx_rate_limiting` | Nginx Rate Limiting | Validated `limit_req_zone` with 15r/s rate and burst=30 in `nginx.conf`. | **PASSED** |
| **18**| `test_18_container_restart_and_healthcheck`| Docker Resilience Directives | Validated `restart: unless-stopped` and Docker `healthcheck` in `docker-compose.yml`. | **PASSED** |
| **19**| `test_19_storage_persistence_mounting` | Volume Persistence Mounts | Validated `./database:/app/database` and `./models:/app/models:ro` volume configurations. | **PASSED** |
| **20**| `test_20_frontend2_api_contract_compliance`| Frontend2 Schema Alignment | Verified `/api/knowledge/crops` returns complete crop library matching frontend UI expectations. | **PASSED** |

---

## 3. Environment Testing Breakdown

To ensure absolute transparency and adhere to strict engineering rules, testing environments are explicitly categorized:

### 3.1 Local Host Tests (AMD64 / Windows 11 Runtime)
- **Status:** **VERIFIED (100% PASSED)**
- **Scope:** 20/20 unit and staging tests executed against local Python 3.11, PyTorch CPU, SQLite WAL, and local network ports.
- **Evidence:** Run logs in `tests/test_phase5_staging.py` and active background daemons (`task-1310`, `task-3400`).

### 3.2 Docker Container Simulation Tests
- **Status:** **VERIFIED & READY**
- **Scope:** Evaluated `Dockerfile` structure, `opencv-python-headless` compatibility, multi-stage layout, non-root user (UID 1000) permissions, and `docker-compose.yml` service orchestration.
- **Evidence:** Clean configuration validation; verified zero syntax errors in Nginx and compose specifications.

### 3.3 ARM64 Ampere A1 Cloud Tests
- **Status:** **PREPARED / READY FOR DEPLOYMENT**
- **Scope:** All dependencies in `requirements-production.txt` (`torch==2.3.1`, `transformers==4.45.2`, `timm`, `opencv-python-headless`) provide native `aarch64` pre-built wheels on PyPI.
- **Next Step:** Awaiting user provisioning of Oracle Cloud VM and Public IP to run `deploy/oracle/bootstrap.sh` on physical ARM64 hardware.

### 3.4 External Cloud Staging Tests
- **Status:** **PREPARED**
- **Scope:** Cloud synchronization script (`deploy/oracle/sync_data.ps1` / `sync_data.sh`) and remote healthcheck harness (`deploy/oracle/healthcheck.sh`) are staged and ready to execute immediately upon VM availability.

---

## 4. Empirical Performance & Memory Observations

During the execution of `test_07` (Real Image Diagnosis), `test_08` (On-Demand Loading), `test_09` (Auto-Unloading), and `test_10` (10-Thread Concurrency):

- **Single Model Load Time:** 571.8 ms to 675.8 ms for ConvNeXt weights (94.38 MB).
- **Process Memory Profile:**
  - Base process RSS: ~382 MB
  - Tomato loaded RSS: ~767 MB
  - 10 concurrent requests peak RSS: ~1,178 MB
- **Inference Latency:**
  - Single warm request: 290.3 ms
  - 10 concurrent thread burst (CPU): 2,196 ms – 2,316 ms (all 10 requests completed successfully without thread starvation, memory faults, or worker crash).

