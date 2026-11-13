# GARI AgriTech AI Lab — Critical Login Gateway Repair & Fail-Closed Hardening Report

**Document ID:** GARI-REPAIR-GATEWAY-LOGIN-2026-07  
**Date:** 2026-11-11  
**Project:** `D:\leaf-diseases-detector-main`  
**Security Posture:** FAIL-CLOSED / ZERO BYPASS / ZERO PHP / SINGLE-READ STREAM SAFETY  

---

## 1. Root Cause Summary & Live Evidence

Investigation of the live deployment `https://gari-team.vercel.app` confirmed the exact failure chain:
1. **HTTP 502 on General Routes:** The Vercel environment variable `VERCEL_BACKEND_API_URL` pointed to an offline / expired backend URL (e.g. an ephemeral Cloudflare Quick Tunnel domain). Outbound requests failed at DNS resolution (`ENOTFOUND`), and the gateway returned HTTP 502 `BACKEND_UNAVAILABLE`.
2. **Pending Login ("Đang đăng nhập..."):** On `/api/auth/login`, the legacy deployed gateway piped the request stream (`req.pipe(upstream)`). When the upstream connection failed, the error handler diverted to `handleEdgeAuth('auth/login')`, which invoked `await readBody(req)`. Because the request stream had already been drained and closed by `req.pipe()`, and because `readBody` had no timeout, the Promise deadlocked in memory. Concurrently, the live client (`firebase-client.js:304`) invoked native `fetch()` without an `AbortController` timeout, leaving both the serverless function and the browser waiting indefinitely.

---

## 2. Changed Files & Modifications

### 2.1. Vercel Gateway (`api/[...path].js` & `frontend2/api/[...path].js`)
- **Single-Read Body Buffering:**  
  All mutating requests (`POST`, `PUT`, `PATCH`) are now buffered in memory exactly once using `readRawBody(req, 10 * 1024 * 1024)`.
- **Elimination of `req.pipe(upstream)`:**  
  The gateway writes the buffered payload directly via `upstream.write(bufferedBody); upstream.end();`. The incoming `req` stream is never piped into an untrusted or failing socket.
- **Controlled Error Termination:**  
  - Socket / DNS failure -> Controlled **HTTP 503** (`BACKEND_UNAVAILABLE`).
  - Upstream gateway timeout -> Controlled **HTTP 504** (`BACKEND_TIMEOUT`).
  - Payload > 10MB -> Controlled **HTTP 413** (`PAYLOAD_TOO_LARGE`).
  - Every single execution path terminates with an explicit HTTP response; hanging is impossible.
- **Complete Elimination of Edge Auth:**  
  Zero edge token generation (`signToken`), zero mock credentials, zero dynamic recovery sessions, zero `handleEdgeAuth()`. FastAPI + SQLite is the sole authority.
- **Synchronization:** `api/[...path].js` and `frontend2/api/[...path].js` are kept byte-for-byte identical.

### 2.2. Client-Side Authentication Router (`frontend2/firebase-client.js`)
- **Bounded Timeout with AbortController:**  
  All client network requests utilize `safeFetch()` with a strict 10,000ms (10s) timeout via `AbortController`.
- **Button Restoration in Finally Block:**  
  `frontend2/login.html` and `firebase-client.js` guarantee that whenever a login succeeds or fails (including timeout and network error), `btnSubmit.disabled = false; btnSubmit.textContent = 'Đang nhập vào hệ thống';` is executed in the `finally` block.
- **Clear Vietnamese Service Messaging:**  
  HTTP 502, 503, and 504 responses trigger an explicit Vietnamese error:
  `"Máy chủ xác thực hiện chưa sẵn sàng hoặc đang bảo trì. Vui lòng thử lại sau giây lát."`
- **Duplicate Prevention:**  
  `isSubmitting` flag and immediate button disabling prevent double-submission.
- **Strict Fallback Rules (A – E):**  
  Invalid passwords (`auth/wrong-password` or SQLite 401) are rejected immediately; silent retries or provider hopping are strictly forbidden.

---

## 3. Backend Configuration Status (Task C Inspection)

Without revealing secret credentials, the backend connectivity status was inspected:

| Inspection Item | Status | Technical Details |
| :--- | :---: | :--- |
| **`VERCEL_BACKEND_API_URL` Configured?** | **YES** | Confirmed by live `/api/health` reporting `"ai_inference": "connected"`. |
| **Hostname Resolves?** | **NO** | The domain configured in Vercel is an ephemeral Quick Tunnel (`*.trycloudflare.com`) that returns `ENOTFOUND` (DNS resolution failed). |
| **HTTPS Connectivity Works?** | **NO** | Cannot connect because the configured hostname does not exist on DNS. |
| **Local FastAPI Responding?** | **YES** | Local instance running at `http://127.0.0.1:8000` responds to `/api/health` with HTTP 200 `{"status": "healthy"}`. |

> **Conclusion on Backend Configuration:**  
> The backend server code is operational locally, but its public tunnel URL on Vercel is dead. To enable cloud reachability, a permanent public HTTPS URL (e.g. Cloudflare Named Tunnel or Oracle VM) must be generated and updated in Vercel Project Settings.

---

## 4. Edge Authentication Bypass Absence Certification

Static and dynamic analysis certifies:
1. `signToken`: **ABSENT** from gateway code.
2. `handleEdgeAuth`: **ABSENT** from gateway code.
3. `gari_edge_`: **ABSENT** from gateway code and database.
4. `edgeUserStore`: **ABSENT** from gateway code.
5. All session tokens originate exclusively from `gari_auth.create_session()` on the FastAPI backend and are validated against SQLite `user_sessions`.

