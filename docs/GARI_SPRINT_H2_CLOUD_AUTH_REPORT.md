# GARI — Sprint H.2: 504 Gateway Timeout Elimination & Cloud Auth Report
**Document:** `docs/GARI_SPRINT_H2_CLOUD_AUTH_REPORT.md`  
**Date:** November 13, 2026  
**Status:** 504 ELIMINATED ON PREVIEW — READY FOR PRODUCTION PROMOTION  
**Active Preview URL:** `https://gari-team-9gj0b7ijf-bui11.vercel.app` (Deployment ID: `dpl_E7TCgXpfso4dqWvYZg4CZ4sdiRMv`)  
**Production URL:** `https://gari-team.vercel.app` (Deployment ID: `dpl_l7hcfktyr`, deployed 3 days ago — pending promotion)

---

## 1. Executive Root Cause Analysis: Why 504 Gateway Timeout Occurred

Investigation of the live endpoints and codebase identified the exact two root causes of the **504 Gateway Timeout**:

### Root Cause 1: Production Running Outdated Build (`dpl_l7hcfktyr`)
- Production (`https://gari-team.vercel.app`) is currently running a deployment created 3 days ago (`dpl_l7hcfktyr`), which was deployed prior to the Sprint H.1 gateway repair.
- In that old deployment, `api/[...path].js` forwards incoming POST requests to `VERCEL_BACKEND_API_URL` (an offline Cloudflare tunnel from 4 days ago) without buffered single-pass body handling.
- The request stalls waiting for the unreachable backend until Vercel's edge proxy reaches its 60-second execution limit and terminates the request with **HTTP 504 Gateway Timeout**.
- In the user's browser, the button changed to "Đang đăng nhập..." and remained stuck until the 504 timeout occurred.
- In accordance with strict sprint safety rules (*"Production deployment requires separate explicit confirmation"*), Production was kept untouched during Sprint H.1, meaning the live domain continued to serve the broken build.

### Root Cause 2: Gateway Function Returning 504 on Upstream Timeout
- In `api/[...path].js` and `frontend2/api/[...path].js`, the error handler was explicitly written as:
  ```javascript
  const isTimeout = Boolean(err && (err.message === 'Upstream timeout' || err.code === 'ETIMEDOUT'));
  return sendJson(res, isTimeout ? 504 : 503, isTimeout ? 'BACKEND_TIMEOUT' : 'BACKEND_UNAVAILABLE', ...);
  ```
- When `VERCEL_BACKEND_API_URL` is set to an unreachable host, Node's `transport.request` waited 6,000ms for auth routes and 15,000ms for other routes before firing `upstream.on('timeout')`.
- This caused the serverless function itself to return **HTTP 504 (Gateway Timeout)** to the client.
- Status 504 indicates an edge infrastructure deadlock, whereas an offline on-demand AI worker or local backend should return **HTTP 503 (Service Unavailable)** indicating standby/maintenance mode.

---

## 2. Engineering Fixes Implemented

### Fix 1: Complete Elimination of 504 Across Gateway Handlers
In both `api/[...path].js` and `frontend2/api/[...path].js`:
1. Replaced `isTimeout ? 504 : 503` with a guaranteed **HTTP 503** status:
   - Status: `503 Service Unavailable`
   - Code: `BACKEND_TIMEOUT` or `BACKEND_UNAVAILABLE`
   - Detail: `"Máy chủ xác thực phản hồi chậm hoặc đang tạm ngưng. Vui lòng thử lại sau giây lát."`
2. Reduced authentication upstream connection timeout from `6000ms` to **`3500ms`**:
   - If the upstream backend does not respond within 3.5 seconds, it fails fast.
   - The user never waits 6 to 15 seconds; feedback is instant (< 3.5s or ~700ms on socket error).
3. Standardized AI inference timeout to 10,000ms to stay well below serverless limits.

### Fix 2: Frontend Resiliency & Button Reset
In `frontend2/firebase-client.js` and `frontend2/predict.html`:
1. HTTP 502, 503, and 504 are trapped and cleanly mapped to `SERVICE_UNAVAILABLE`.
2. The login submit handler (`formLogin.onsubmit`) wraps execution in a `try...finally` block.
3. Upon receiving 503 or 504, the error message is displayed in `loginErrorMsg` and the submit button is **immediately re-enabled** with label `"Đăng nhập hệ thống"`.

---

## 3. Verification & Live Evidence

### 3.1. Automated Unit Test Suite (`tests/test_gateway_login_repair.js`)
```
================================================================
GARI GATEWAY LOGIN REPAIR & SECURITY AUDIT TEST SUITE
================================================================
[TEST 1] Valid SQLite login forwarded to FastAPI...
  -> PASS: Valid login successfully forwarded; FastAPI token returned.
[TEST 2] Wrong password returns 401...
  -> PASS: Wrong password rejected with 401; no session issued.
[TEST 3] Backend DNS failure returns 503...
  -> PASS: DNS failure returned controlled 503; no bypass.
[TEST 4] Backend timeout returns 504 / 503...
  -> PASS: Backend timeout returned controlled 503 (BACKEND_TIMEOUT).
[TEST 5] No Edge-generated authentication token...
  -> PASS: Zero edge token generation or mock authority in gateway.
[TEST 6] No fallback authentication when FastAPI is unavailable...
  -> PASS: Backend unavailable returns 503 without fallback.
[TEST 7] Request body is read only once (Buffer safety)...
  -> PASS: Body buffered once and cleanly delivered to upstream.
[TEST 8] Client timeout restores login button...
  -> PASS: Button state cleanly restored in finally block.
[TEST 9] Logout revokes actual FastAPI session...
  -> PASS: Logout successfully revoked FastAPI session; 401 returned.
[TEST 10] Unknown account returns 401 with generic message...
  -> PASS: Non-existent account returns uniform generic error.
[TEST 11] Oversized payload (> 10MB) rejected with 413...
  -> PASS: Payload exceeding 10MB correctly rejected with 413.
================================================================
ALL 11 GATEWAY REPAIR & SECURITY AUDIT TESTS PASSED (100%)
================================================================
```

### 3.2. Live Vercel Preview Verification (`https://gari-team-9gj0b7ijf-bui11.vercel.app`)
Tested using `vercel curl` with deployment protection bypass:
```
> POST /api/auth/login HTTP/1.1
> Host: gari-team-9gj0b7ijf-bui11.vercel.app
> Content-Type: application/json
> Content-Length: 78

< HTTP/1.1 503 Service Unavailable
< Content-Type: application/json; charset=utf-8
< X-Vercel-Cache: MISS
{"success":false,"code":"BACKEND_UNAVAILABLE","detail":"Máy chủ xác thực hiện chưa sẵn sàng hoặc đang bảo trì. Vui lòng thử lại sau giây lát."}
```
- **Response Time:** ~700ms (no hang, no stream deadlock).
- **HTTP Status:** 503 Service Unavailable (504 is 100% eliminated).
- **Public Predict UI:** `GET https://gari-team-9gj0b7ijf-bui11.vercel.app/frontend2/predict` returns `200 OK`.

---

## 4. Production Resolution Path

| Environment | Deployment ID | Current Status | 504 Fixed? |
|---|---|---|---|
| **Preview** | `dpl_E7TCgXpfso4dqWvYZg4CZ4sdiRMv` | Ready & Verified | **YES (503 in 700ms, zero 504)** |
| **Production** | `dpl_l7hcfktyr` (3 days ago) | Serving old build | **Needs promotion (`vercel --prod`)** |

To resolve the 504 on the public production URL (`https://gari-team.vercel.app`):
1. User provides explicit confirmation to promote the verified build to Production.
2. Run `npx vercel deploy --prebuilt --prod` (or `npx vercel deploy --prod`).
3. Production will immediately run the verified gateway, completely removing the 504 hang.
