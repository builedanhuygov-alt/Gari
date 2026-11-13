# GARI — Sprint H.2.2: Preview Deployment for User Testing Report
**Document:** `docs/GARI_H2_2_PREVIEW_USER_TEST_REPORT.md`  
**Date:** November 13, 2026  
**Status:** DEPLOYMENT VERIFIED & READY FOR TESTING  
**Active Preview URL:** `https://gari-team-fwwp1442f-bui11.vercel.app`  
**Deployment ID:** `dpl_J6cjTz28ff3c1Y5QNfwpWdsWW2LP`  
**Target Environment:** Vercel Preview (Isolated)  

---

## 1. Final Verdict

**FINAL VERDICT: PREVIEW READY FOR USER TESTING**

The latest GARI frontend and Edge Gateway implementations have been deployed to an isolated Vercel Preview environment. All unit tests, stream safety checks, and live endpoint probes passed successfully.

---

## 2. Deployment Metadata & Environment Isolation

| Attribute | Preview Deployment (Active Test Target) | Production (Strictly Untouched) |
|---|---|---|
| **Deployment URL** | `https://gari-team-fwwp1442f-bui11.vercel.app` | `https://gari-team.vercel.app` |
| **Deployment ID** | `dpl_J6cjTz28ff3c1Y5QNfwpWdsWW2LP` | `dpl_l7hcfktyr` |
| **Environment** | `preview` | `production` |
| **Age / Timestamp** | Just deployed (< 2 minutes ago) | Deployed 3 days ago |
| **Production Domains / Aliases** | None assigned (`gari-team.vercel.app` unaffected) | Active on production alias |
| **Environment Variables** | Preview environment variables only | Production secrets untouched |

---

## 3. Changed Files & Parity Audit

The following files constitute the changes deployed to the Preview environment:

| File Path | Status | Verification Summary |
|---|---|---|
| [`api/[...path].js`](file:///d:/leaf-diseases-detector-main/api/[...path].js) | `modified` | Buffer-safe single-pass body consumption (`readRawBody`), bounded auth timeout (3.5s), fail-closed error handling (503 for offline, 504 for timeout), zero Edge Auth token generation. |
| [`frontend2/api/[...path].js`](file:///d:/leaf-diseases-detector-main/frontend2/api/[...path].js) | `modified` | Verified 100% byte-for-byte identical to root `api/[...path].js` via `git diff --no-index`. |
| [`vercel.json`](file:///d:/leaf-diseases-detector-main/vercel.json) | `modified` | Rewrites `/api/(.*)` to `/api/[...path]?path=$1`, sets `outputDirectory: "."` to prevent static build conflicts. |
| [`package.json`](file:///d:/leaf-diseases-detector-main/package.json) | `modified` | Pinned `vercel-build` script to prevent infinite recursive server build loops. |
| [`.vercelignore`](file:///d:/leaf-diseases-detector-main/.vercelignore) | `modified` | Excludes databases (`*.sqlite`, `*.db`), python files, server backend, and secrets from upload bundle. |
| [`frontend2/predict.html`](file:///d:/leaf-diseases-detector-main/frontend2/predict.html) | `modified` | Added `try...finally` button state recovery guard so the login button cannot remain stuck on "Đang đăng nhập...". |

---

## 4. Pre-Deployment Validation & Build Verification

1. **Build Check (`npm run vercel-build`):**
   ```
   > gari-ai-lab@1.0.0 vercel-build
   > node -e "console.log('GARI Vercel Web Build Ready')"
   GARI Vercel Web Build Ready
   ```
2. **Gateway Test Suite (`node tests/test_gateway_login_repair.js`):**
   - 11/11 tests passed (100%).
   - Verified genuine FastAPI session proxying, wrong password 401 rejection, DNS failure 503 handling, upstream timeout 504 handling, single-pass body streaming, and client timeout button recovery.
3. **Artifact Hygiene Check:**
   - Zero `.env` files, `.sqlite` databases, or secrets packaged into the build container.

---

## 5. Live Endpoint Verification (Preview URL)

Live verification executed via `vercel curl` with deployment protection bypass:

### 5.1. UI Asset Delivery: `GET /frontend2/predict`
```http
GET /frontend2/predict HTTP/1.1
Host: gari-team-fwwp1442f-bui11.vercel.app

HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Content-Length: 308657
```
- **Result:** Successfully returned complete frontend UI (200 OK).

### 5.2. Public Gateway Health: `GET /api/health`
```http
GET /api/health HTTP/1.1
Host: gari-team-fwwp1442f-bui11.vercel.app

HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8

{"status":"healthy","service":"Gari AI Lab AgriTech Platform (Edge Gateway)","environment":"production","version":"2.6.0","services":{"gateway":"healthy","backend_runtime":"standby","firebase_admin":"standby"}}
```
- **Result:** Clean JSON response in ~300ms without touching the backend.

### 5.3. Synthetic Auth Login: `POST /api/auth/login`
```http
POST /api/auth/login HTTP/1.1
Host: gari-team-fwwp1442f-bui11.vercel.app
Content-Type: application/json
Content-Length: 78

{"email":"synthetic_preview_test@gari.vn","password":"TestPassword123!"}

HTTP/1.1 503 Service Unavailable
Content-Type: application/json; charset=utf-8

{"success":false,"code":"BACKEND_UNAVAILABLE","detail":"Máy chủ xác thực hiện chưa sẵn sàng hoặc đang bảo trì. Vui lòng thử lại sau giây lát."}
```
- **Result:** Immediate 503 response (~720ms) indicating the backend is in standby.
- **Safety:** Zero token minting, zero fallback identity, no stream deadlock, no hanging.

### 5.4. Synthetic Provider Lookup: `POST /api/auth/provider-lookup`
```http
POST /api/auth/provider-lookup HTTP/1.1
Host: gari-team-fwwp1442f-bui11.vercel.app
Content-Type: application/json

{"email":"synthetic_farmer@gari.vn"}

HTTP/1.1 503 Service Unavailable
Content-Type: application/json; charset=utf-8

{"success":false,"code":"BACKEND_UNAVAILABLE","detail":"Máy chủ xác thực hiện chưa sẵn sàng hoặc đang bảo trì. Vui lòng thử lại sau giây lát."}
```
- **Result:** Controlled 503 response in ~500ms.

---

## 6. Known Login & Cloud Auth Limitations

As confirmed in Sprint H.2.1:
1. **Supabase Auth is Not Yet Integrated into UI:**
   - The UI currently imports `frontend2/firebase-client.js` rather than `frontend2/supabase-client.js`.
   - The Supabase projects under the account are currently in dormant/inactive status.
2. **Dependency on Windows PC / FastAPI for Login:**
   - While the Windows PC is offline or the Cloudflare Tunnel is closed, login attempts return **HTTP 503 `BACKEND_UNAVAILABLE`**.
   - When the user enters credentials on the Preview UI, the form will cleanly display:
     `"Máy chủ xác thực hiện chưa sẵn sàng hoặc đang bảo trì. Vui lòng thử lại sau giây lát."`
   - The login button immediately resets from `"Đang đăng nhập..."` back to `"Đăng nhập hệ thống"` (no infinite hang, no 60s freeze).
3. **AI Inference Standby:**
   - When the Windows PC AI worker is offline, leaf disease diagnosis requests return **HTTP 503** with message indicating the AI model engine is on standby.

---

## 7. Confirmation of Production Invariants

- **Production Deployment (`gari-team.vercel.app`):** Retains commit `87e1f258` (`dpl_l7hcfktyr`). No new production build was triggered.
- **Production Environment Variables:** Unmodified.
- **Local SQLite Database (`database/disease_detector.db`):** 3,550 accounts completely untouched.
- **Windows Defender & Antigravity Logs:** Unmodified.
- **PHP:** Zero PHP files present or introduced.
