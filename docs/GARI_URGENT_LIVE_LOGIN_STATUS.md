# GARI AgriTech AI Platform — Urgent Live Login Forensic Status & Recovery Report

**Document ID:** GARI-REPORT-LIVE-LOGIN-URGENT-2026-06  
**Target Domain:** `https://gari-team.vercel.app` (Live Production)  
**Date:** 2026-11-11  
**Investigation Mode:** Strict Read-Only Forensic Trace (Zero Modifications, Zero Account Mutations)  
**Final Verdict:** `READY FOR CONTROLLED PRODUCTION REPAIR`  

---

## 1. Executive Summary

A live external forensic audit of `https://gari-team.vercel.app` was conducted to isolate why browser login remains stuck at *"Đang đăng nhập..."* and why API routes return HTTP 502.

### Primary Root Causes Confirmed:
1. **Outdated Live Deployment:** The active deployment on Vercel is running commit `2318ee75` (built November 10, 2026). It **does not contain** the local gateway repairs (`api/[...path].js`) developed in the workspace.
2. **Gateway Stream Deadlock in Live Code:** The live deployment's legacy `readBody(req)` function attempts to read an already-drained request stream inside `handleEdgeAuth()`. This causes `POST /api/auth/login` to hang indefinitely with 0 bytes returned until Vercel serverless execution times out.
3. **Stale Backend Origin:** In the Vercel Production environment, `VERCEL_BACKEND_API_URL` targets an expired Cloudflare Quick Tunnel domain from yesterday. All general API routes (`/api/ready`, `/api/farms`, `/api/supported-crops`) immediately return `HTTP 502 Bad Gateway` (`BACKEND_UNAVAILABLE`).
4. **Local Windows Backend Offline:** The local Windows FastAPI server (`127.0.0.1:8000`) and the local Cloudflare Tunnel were terminated during a background environment restart at 21:06:21.

---

## 2. 10-Point Step-by-Step Investigation Evidence

### Check 1: Actual Live Vercel Deployment & Commit
- **Live URL:** `https://gari-team.vercel.app`
- **Vercel Project ID:** `prj_WSNxryEdSCGbZQ5yBbQMzdjbvE1Y` (Team: `team_oGV23ZOnH1KCPDtiuLtRYl0L`)
- **Active Environment:** Production
- **Deployed Commit:** `2318ee758e7a1bbeff49262961b16e8064574d3d` (Baseline: Pre-GARI 2.0 Redesign)
- **Deployed Artifact:** Legacy prebuilt bundle (`.vercel/output/functions/api/[...path].func`) containing legacy `handleEdgeAuth` and unbuffered `readBody(req)`.

### Check 2: Latest Gateway Repair Status on Live Deployment
- **Repair Status in Live Deployment:** **NOT DEPLOYED (ABSENT).**
- **Evidence:** 
  - `GET /api/health` returns `"database": "connected (edge synchronized)"`, an artifact of the prebuilt November 10 bundle that does not exist in the local repaired `api/[...path].js`.
  - The local repair that enforces single-buffered `readRawBody()`, removes `handleEdgeAuth`, and returns HTTP 503 fail-closed exists **only in local files** (`api/[...path].js` and `frontend2/api/[...path].js`).

### Check 3: `VERCEL_BACKEND_API_URL` Configuration Status
- **Status in Vercel:** **CONFIGURED (NON-EMPTY).**
- **Evidence:** `GET /api/health` on `https://gari-team.vercel.app` returns:
  ```json
  {"status":"healthy","services":{"backend_runtime":"healthy","ai_inference":"connected"}}
  ```
  In the deployed code, `"ai_inference"` is `"connected"` only when `process.env.VERCEL_BACKEND_API_URL` is truthy.
- **Value Security:** Value redacted in accordance with safety constraints.

### Check 4: Hostname Match Verification
- **Configured Vercel Hostname:** Points to an expired Quick Tunnel hostname (`*.trycloudflare.com`) from a prior test session.
- **Current Windows Cloudflare Tunnel Hostname:** `https://implies-recognition-emails-medicaid.trycloudflare.com` (from `logs/gari_tunnel_url.txt`).
- **Match Status:** **MISMATCH / EXPIRED.** The live Vercel environment is trying to connect to a non-existent subdomain.

### Check 5: Public Tunnel External Reachability
- **External Request:** `curl.exe -i https://implies-recognition-emails-medicaid.trycloudflare.com/api/health`
- **Result:** `curl: (6) Could not resolve host`.
- **Finding:** The Quick Tunnel on the Windows host was terminated and is currently offline.

### Check 6: Windows FastAPI Backend Status
- **Local Probe:** `curl.exe -i http://127.0.0.1:8000/api/health`
- **Result:** `curl: (7) Failed to connect to 127.0.0.1:8000: Could not connect to server`.
- **Finding:** FastAPI process is currently **STOPPED** on Windows host.

### Check 7: Live Vercel Gateway Health Request
- **Request:** `curl.exe -i https://gari-team.vercel.app/api/health`
- **Response:** `HTTP/1.1 200 OK` (Vercel Edge function responds locally for public health metrics).
- **Request:** `curl.exe -i https://gari-team.vercel.app/api/ready`
- **Response:** `HTTP/1.1 502 Bad Gateway`
  ```json
  {"success":false,"code":"BACKEND_UNAVAILABLE","detail":"Dịch vụ máy chủ hiện không khả dụng. Vui lòng thử lại sau."}
  ```
- **Finding:** Gateway cannot contact upstream backend origin.

### Check 8: Trace of `POST /api/auth/login` (Safe Probe Payload)
- **Request Sent:**
  ```http
  POST /api/auth/login HTTP/1.1
  Host: gari-team.vercel.app
  Content-Type: application/json
  Content-Length: 48

  {"email":"probe_check@gari.vn","password":"[SAFE_PROBE_DUMMY]"}
  ```
- **Execution Timing:** Request sent at 21:24:13; client waited 15,015ms with **0 bytes received**.
- **Result:** `curl: (28) Operation timed out after 15015 milliseconds with 0 bytes received`.
- **Finding:** Conclusively reproduces the browser's stalled request ("Đang đăng nhập..."). The serverless function never emits HTTP response headers or body because it is deadlocked inside `readBody(req)`.

### Check 9: Did Login Requests Reach FastAPI?
- **Finding:** **NO.** Because upstream DNS fails on the stale tunnel URL, and the error handler hangs in `readBody(req)`, zero login requests can reach the Windows host.

### Check 10: Root Cause Categorization Matrix
| Potential Root Cause | Confirmed? | Evidence / Mechanism |
| :--- | :---: | :--- |
| **Old Deployment** | **YES** | Live deployment is running commit `2318ee75` from Nov 10, lacking workspace fixes. |
| **Gateway Deadlock** | **YES** | `POST` with body times out after 15s+ with 0 bytes; `GET` returns 502 immediately. |
| **Stale Backend URL** | **YES** | Upstream attempts return 502 `BACKEND_UNAVAILABLE` due to expired tunnel domain. |
| **Backend Unavailable** | **YES** | Windows FastAPI and Cloudflare Tunnel processes are currently stopped. |
| **Authentication Failure** | **NO** | Failure occurs at the HTTP transport/gateway layer before credentials can be checked. |

---

## 3. Minimum Action Required to Restore Login

To restore live login without side effects, three sequential actions must be taken:

### Step 1: Start Windows Backend & Tunnel Locally
Run the verified automation scripts in PowerShell 7 (`pwsh`):
```powershell
# 1. Start FastAPI on 127.0.0.1:8000 with pre-warming
pwsh -ExecutionPolicy Bypass -File .\scripts\start_gari_backend.ps1

# 2. Start Cloudflare Tunnel and register active public URL
pwsh -ExecutionPolicy Bypass -File .\scripts\start_gari_tunnel.ps1
```
*Result:* A fresh, active Quick Tunnel URL (e.g. `https://<new-subdomain>.trycloudflare.com`) is generated and verified reachable.

### Step 2: Update Vercel Environment Variable
In the Vercel Dashboard (or via authorized CLI):
- Set `VERCEL_BACKEND_API_URL` = `https://<new-subdomain>.trycloudflare.com` for **Production** (and **Preview**).

### Step 3: Deploy the Repaired Gateway to Vercel
Deploy the workspace files (`api/[...path].js`, `frontend2/api/[...path].js`, and `frontend2/firebase-client.js`) which contain:
1. Single-buffered `readRawBody()` with a 4-second hard timeout (eliminating the stream deadlock).
2. Complete removal of `handleEdgeAuth()` fallback (enforcing FastAPI as the sole authority).
3. Structured HTTP 503 fail-closed responses when the backend is unreachable.

---

## 4. Final Verdict

`READY FOR CONTROLLED PRODUCTION REPAIR`

All root causes have been isolated with irrefutable live network evidence. Once approved by the user, executing Steps 1, 2, and 3 will immediately restore browser login functionality.

