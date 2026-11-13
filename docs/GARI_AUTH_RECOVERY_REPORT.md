# GARI — Auth Recovery Implementation Report
**Document:** `docs/GARI_AUTH_RECOVERY_REPORT.md`  
**Date:** November 13, 2026  
**Status:** IMPLEMENTED & VERIFIED LOCALLY — AWAITING DEPLOYMENT APPROVAL  
**Priority:** CRITICAL — AUTH RECOVERY

---

## 1. Executive Summary

This report documents the end-to-end engineering recovery for the production login hang incident observed at `https://gari-team.vercel.app/frontend2/predict`. In the prior deployment, clicking "Đăng nhập" resulted in the button changing to `"Đang đăng nhập..."` and hanging indefinitely without navigation or error feedback.

The root cause was identified across two interacting layers:
1. **Frontend Request Layer:** The login click handler in `predict.html` and `firebase-client.js` lacked bounded timeouts and duplicate-click guards. An aborted or deadlocked network connection left the button disabled indefinitely.
2. **Gateway Upstream Layer:** The legacy Vercel serverless proxy (`api/[...path].js`) piped the incoming request body stream directly into `fetch()`. When upstream connectivity failed or timed out (due to expired Cloudflare Tunnel URL), the error handler attempted to read from the already-consumed request stream, deadlocking the serverless function execution until hard platform timeout.

Both layers have been surgically refactored, hardened, synchronized, and verified with an 11-point automated test suite.

---

## 2. Frontend Hardening Implementation

### 2.1. `frontend2/firebase-client.js`
- **In-flight Deduplication Guard:** Added `this._loginInFlight` boolean flag. Rapid successive calls to `login()` or `loginWithProvider()` return immediately with an error rather than spawning concurrent uncoordinated HTTP requests.
- **Configurable `AbortSignal` & Timeouts:** Updated `safeFetch()` and `login()` to accept `fetchOptions`, enabling callers to pass an `AbortSignal`.
- **Bounded Request Timeout:** Implemented a default 15-second bounded abort controller in `login()` to ensure network requests cannot hang the client indefinitely.
- **Fail-Closed Cleanup:** Added guaranteed reset of `this._loginInFlight = false` inside `finally` blocks for all authentication methods (`login`, `register`, `logout`).

### 2.2. `frontend2/predict.html`
- **Button Lock Guard:** Added `if (btn.disabled) return;` at the beginning of the modal form submit handler.
- **Explicit Timeout & Controller:** Integrated a dedicated `AbortController` bound to a 15-second timer. If the server or gateway does not respond within 15 seconds, the controller aborts the fetch call.
- **Deterministic UI Restoration:** Encapsulated button reset logic inside a guaranteed `finally` block:
  ```javascript
  btn.disabled = false;
  btn.textContent = originalText;
  ```
- **Actionable User Feedback:** Specific status code handling:
  - `401 Unauthorized`: Displays "Sai thông tin đăng nhập hoặc tài khoản không tồn tại."
  - `503 Service Unavailable`: Displays "Hệ thống xác thực tạm thời không khả dụng. Vui lòng thử lại sau."
  - `504 Gateway Timeout`: Displays "Yêu cầu đăng nhập quá thời gian phản hồi. Vui lòng thử lại."

---

## 3. Vercel Gateway Synchronization & Hardening

Both gateway endpoints have been synchronized with identical, battle-tested proxy logic:
- `api/[...path].js` (Root gateway)
- `frontend2/api/[...path].js` (Frontend2 namespace gateway)

### Key Architectural Invariants:
1. **Zero Edge Auth Fallback:** Completely removed `handleEdgeAuth`. The gateway acts strictly as a transparent, fail-closed proxy. FastAPI or Supabase remains the sole authentication authority. Synthetic tokens and client-side password bypasses are completely eliminated.
2. **Single-Pass Stream Consumption:** Replaced native streaming piping with `readRawBody(req, MAX_BODY_BYTES)`. The body is buffered into a Node.js `Buffer` exactly once before being dispatched upstream:
   - Upper payload limit enforced at **10 MB** (`MAX_BODY_SIZE = 10 * 1024 * 1024`). Payloads exceeding this limit immediately return **HTTP 413 Payload Too Large** without contacting upstream.
   - 4-second bounded read timeout prevents slowloris client hangs.
3. **Bounded Upstream Timeout:** Upstream `fetch()` calls are bounded by an `AbortController` with an 8-second timeout (`UPSTREAM_TIMEOUT_MS = 8000`).
4. **Accurate HTTP Status Mapping:**
   - Upstream timeout -> **HTTP 504 Gateway Timeout** with structured JSON:
     `{"error": "gateway_timeout", "detail": "Upstream service timed out.", "status_code": 504}`
   - Upstream connectivity / DNS error (`ENOTFOUND`, `ECONNREFUSED`, `ETIMEDOUT`) -> **HTTP 503 Service Unavailable**:
     `{"error": "service_unavailable", "detail": "Backend service unreachable.", "status_code": 503}`
   - Upstream HTTP 401/403/404/500 responses are forwarded verbatim to the client with their original headers and payloads.

---

## 4. Verification & Automated Test Suite

The gateway repair was validated against `tests/test_gateway_login_repair.js` covering 11 critical test cases:

| # | Test Scenario | Target Behavior | Result |
|---|---|---|---|
| 1 | Upstream returns 200 OK | Forward 200 with tokens and body | **PASSED** |
| 2 | Upstream returns 401 Invalid Credentials | Forward 401 verbatim to frontend | **PASSED** |
| 3 | Upstream times out (>8s) | Return 504 Gateway Timeout immediately | **PASSED** |
| 4 | Upstream DNS failure (`ENOTFOUND`) | Return 503 Service Unavailable | **PASSED** |
| 5 | Upstream connection refused (`ECONNREFUSED`) | Return 503 Service Unavailable | **PASSED** |
| 6 | No upstream configured in env | Return 503 with configuration message | **PASSED** |
| 7 | Request path rewriting | Forward `/api/auth/login` accurately | **PASSED** |
| 8 | Large response forwarding | Forward body intact without truncation | **PASSED** |
| 9 | Zero Edge Auth verification | Confirm synthetic token minting is absent | **PASSED** |
| 10| Unknown account test | Forward 401 without hanging | **PASSED** |
| 11| Oversized payload test (>10MB) | Return 413 Payload Too Large immediately | **PASSED** |

**Execution Output:**
```
Running Gateway Login Repair Test Suite (11 test cases)...
[PASS] Test 1: Successful login forwards 200 OK
[PASS] Test 2: Invalid credentials forwards 401
[PASS] Test 3: Upstream timeout returns 504 Gateway Timeout
[PASS] Test 4: Upstream DNS failure returns 503 Service Unavailable
[PASS] Test 5: Upstream connection refused returns 503 Service Unavailable
[PASS] Test 6: Missing upstream config returns 503 Service Unavailable
[PASS] Test 7: Path rewriting forwards accurate upstream path
[PASS] Test 8: Response headers and body forwarded intact
[PASS] Test 9: Edge Auth fallback completely absent (no synthetic tokens)
[PASS] Test 10: Unknown account login returns uniform 401
[PASS] Test 11: Oversized payload returns 413 Payload Too Large
All 11 tests passed successfully! (100% pass rate)
```

---

## 5. Deployment Readiness

- **Locally Tested:** Yes.
- **Git State:** Staged in working branch `gari-2.0-redesign`.
- **Production Status:** Ready for deployment upon user explicit approval.
