# GARI AGRITECH AI LAB — PHASE 5.7 COMPREHENSIVE SECURITY AUDIT
## Production Verification, Threat Assessment & Vulnerability Analysis

**Audit Date:** 2026-11-10  
**Audit Scope:** Full Application Stack (`D:\leaf-diseases-detector-main`)  
**Targets Audited:** FastAPI Backend (`api_server.py`), Authentication Layer (`gari_auth.py`), Database Layer (`gari_database.py`), Farm & B2B Management (`gari_farm_management.py`, `gari_b2b.py`), AI Inference Engine (`gari_inference_engine.py`), Frontend (`frontend2/`), Configuration & Secrets.  
**Production Readiness Verdict:** **READY WITH LIMITATIONS (NOT PRODUCTION READY UNTIL SEC-01 & SEC-02 REMEDIATED)**

---

## 1. Executive Summary

A comprehensive pre-production security audit was executed across all components of GARI AgriTech AI Lab. The audit verified positive defensive architectural choices (e.g. Bcrypt cost-12 hashing, sliding-window brute force rate limiting, strict single active account type normalization, SQLite WAL mode with foreign keys, and PyTorch model registry safety with safetensors).

However, the audit discovered **7 security findings**, including **2 CRITICAL vulnerabilities** and **2 HIGH vulnerabilities** that require immediate remediation before onboarding real external agricultural cooperatives, enterprises, and farmers:

- **Total Findings:** 7
  - **CRITICAL:** 2 (SEC-01: IDOR / Anonymous Data Exposure in Diagnoses; SEC-02: User 1 Fallback in Notifications, Tasks & Copilot)
  - **HIGH:** 2 (SEC-03: BOLA / IDOR in Organization Farm Listing; SEC-04: Cross-Expert Case Interception)
  - **MEDIUM:** 2 (SEC-05: Stored XSS via unescaped innerHTML; SEC-06: Hardcoded Admin Email Escalation)
  - **LOW / INFO:** 1 (SEC-07: Unbounded Upload Guard on Field Dataset API)

All tests were performed without disrupting running services or modifying production data. A new regression security test suite was authored in `tests/test_phase5_7_security_audit.py` (11/11 tests passing).

---

## 2. Threat Vector Assessment by Domain

### Task A — Authentication & Authorization Audit

| Subsystem | Security Posture | Audit Findings |
| :--- | :---: | :--- |
| **Password Hashing** | **SECURE** | Uses `bcrypt.hashpw` with `rounds=12` and random salt. Verification uses constant-time comparison. |
| **Brute Force Protection** | **SECURE** | Sliding-window memory rate limiter locks out IP/email after 5 failures in 300 seconds (HTTP 429). |
| **Session Tokens** | **SECURE** | 36-byte cryptographically secure random tokens (`secrets.token_urlsafe(36)`), stored in `user_sessions` with 7-day default / 30-day remember-me expiration. |
| **Password Reset** | **SECURE** | 15-minute temporary token (`secrets.token_urlsafe(24)`), invalidated upon single use, revoking all active sessions upon password reset. |
| **Privilege Escalation Guard** | **SECURE** | `update_user_profile` strictly rejects updates containing `is_admin`, `is_host_admin`, `is_expert`, or `account_type` with HTTP 400. |
| **Admin Authorization** | **VULNERABLE (SEC-06)** | `get_current_admin_user` in `gari_auth.py:542` contains hardcoded email checks (`email in ("danhuynh@gari.vn", "admin@gari.vn")`). |
| **Expert Authorization** | **VULNERABLE (SEC-04)** | Any verified expert can read and post messages to cases assigned to other experts (`api_server.py:7704-7730`). |

### Task B — API Security & IDOR Audit

| Vector | Security Posture | Audit Findings |
| :--- | :---: | :--- |
| **Diagnosis Data Exposure** | **CRITICAL (SEC-01)** | `GET /api/diagnoses` uses optional auth and omits user/org filter when unauthenticated, returning all leaf disease diagnoses. `GET /api/diagnoses/{id}` skips auth check if anonymous. |
| **Default User 1 Fallback** | **CRITICAL (SEC-02)** | 19 endpoints across notifications, cultivation tasks, and AI copilot use `user_id = current_user["id"] if current_user else 1`, exposing Admin/User 1 records to anonymous requests. |
| **Cross-Org Farm Listing** | **HIGH (SEC-03)** | `GET /api/farms?org_id=X` filters by `organization_id` without checking if the requester belongs to organization X. |
| **File Upload Safety** | **SECURE** | `/api/predict` validates 15 MB limit, checks image bytes via PIL `.verify()`, uses randomized UUID filenames, and runs automated moderation scanning. |
| **SQL Injection** | **SECURE** | All dynamic SQL queries in `gari_database.py` and `gari_b2b.py` use `?` parameter markers. F-strings are restricted to column names from static whitelists or parameter placeholder generation. |
| **CORS Policy** | **SECURE** | Strict origin allowlist (`ALLOWED_ORIGINS`). Startup validation terminates the server if wildcard `*` is configured with credentials in production. |

### Task C — Secrets & Configuration Audit

| Artifact | Audit Assessment |
| :--- | :--- |
| **Git Tracking** | `.env`, `.env.local`, `*.db`, `cloudflared.exe`, `*.key` are properly excluded in `.gitignore`. |
| **Default Secrets** | `gari_config.py:101-122` enforces fail-fast abort on startup if `SESSION_SECRET` or `JWT_SECRET` is unset, too short (< 32 chars), or matches development placeholders. |
| **Logging Sanitization** | `get_safe_config_summary()` outputs booleans and counts without logging raw secrets or API keys. |
| **Frontend Secrets** | `frontend2/` contains only public Firebase configurations and relative API paths. No backend API keys or database connection strings are exposed in client bundles. |

### Task D — Database Security

| Parameter | Configuration & Audit State |
| :--- | :--- |
| **Storage Engine** | SQLite 3 in Write-Ahead Logging mode (`PRAGMA journal_mode = WAL;`). |
| **Foreign Keys** | Active on all connections (`PRAGMA foreign_keys = ON;`). |
| **Busy Timeout** | Set to 5000 ms (`PRAGMA busy_timeout = 5000;`) to prevent locking conflicts. |
| **File Permissions** | Stored in `database/disease_detector.db`, restricted to OS user session context. |
| **Disaster Recovery** | Tested with live Restore Drill (`scripts/run_restore_drill.py`): 83/83 tables reconciled with zero data loss. |

### Task E — Frontend Security

| Vector | Audit Assessment |
| :--- | :--- |
| **Cross-Site Scripting (XSS)** | **MEDIUM (SEC-05)**: Over 300 instances of `innerHTML` in `frontend2/` interpolate server responses (farm names, plot names, user notes) directly into HTML template strings without entity escaping. |
| **Token Storage** | Auth tokens are persisted in `localStorage` (`gari_session` / `gari_token`). Combined with XSS, this presents an account takeover risk. |
| **Client Guard Rails** | `frontend2/predict.html` includes a 45-second `AbortController` timeout guard, 401 redirect handlers, and 502/503 service unavailable alerts. |

### Task F — AI Model & Inference Security

| Subsystem | Audit Assessment |
| :--- | :--- |
| **Path Traversal** | **SECURE**: Model lookups occur strictly via `engine.registry` dictionary populated from discovered configs. Input paths like `../../etc/passwd` trigger immediate `ValueError` without file system interaction. |
| **Weight Serialization** | **SECURE**: Models use `safetensors` format, eliminating Python pickle arbitrary code execution risks. |
| **Resource Quotas** | **SECURE**: Max 3 cached models in RAM. Models auto-unload after 300 seconds of inactivity. Physical RAM threshold guards prevent server crashes. |
| **Concurrency Lock** | **SECURE**: `_ACTIVE_INFERENCES_LOCK` prevents duplicate in-flight requests, and `INFERENCE_SEMAPHORE` bounds active parallel inference tasks. |

---

## 3. Regression & Security Test Results

The automated security regression test suite `tests/test_phase5_7_security_audit.py` was executed:

| Test Case | Objective | Result |
| :--- | :--- | :---: |
| `test_01_password_hashing_bcrypt` | Verify Bcrypt cost 12 and salt verification | **PASS** |
| `test_02_login_rate_limiting` | Verify 5-attempt rate limiting locks out brute force | **PASS** |
| `test_03_invalid_and_expired_session` | Verify invalid/short tokens are rejected | **PASS** |
| `test_04_privilege_escalation_guard` | Verify forbidden fields rejected in profile update | **PASS** |
| `test_05_audit_idor_unauthenticated_diagnoses` | Verify SEC-01 reproduction (diagnoses exposure) | **PASS (Vulnerability Confirmed)** |
| `test_06_audit_idor_default_user_1_notifications` | Verify SEC-02 reproduction (notification leak) | **PASS (Vulnerability Confirmed)** |
| `test_07_audit_idor_default_user_1_tasks` | Verify SEC-02 reproduction (calendar tasks leak) | **PASS (Vulnerability Confirmed)** |
| `test_08_audit_idor_cross_org_farms` | Verify unauth rejected on `/api/farms` | **PASS** |
| `test_09_predict_upload_non_image_rejected` | Verify upload auth + moderation reject non-image | **PASS** |
| `test_10_model_path_traversal_rejected` | Verify path traversal rejected by model registry | **PASS** |
| `test_11_database_integrity_and_wal` | Verify SQLite WAL mode and zero corruption | **PASS** |

**Summary: 11 tests ran in 0.888s — 11 PASSED (0 FAILED, 0 BLOCKED).**

---

## 4. Production Readiness Conclusion

- **Current Status:** **READY WITH LIMITATIONS**
- **Deployment Guidance:**
  The system is robust and operable for closed internal testing and demonstration. However, **public general availability (open self-registration for real agricultural cooperatives) must be gated** until the remediation of **SEC-01** (unauthenticated diagnosis exposure) and **SEC-02** (User 1 default fallback).

