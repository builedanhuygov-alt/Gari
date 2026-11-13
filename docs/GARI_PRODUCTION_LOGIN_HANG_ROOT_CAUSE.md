# GARI AgriTech AI Platform — Root Cause Forensic Analysis
## Incident: Production Login Remains Stuck at "Đang đăng nhập..."

**Document ID:** GARI-RCA-AUTH-HANG-2026-01  
**Target URL:** `https://gari-team.vercel.app/frontend2/predict`  
**Date:** 2026-11-13  
**Status:** ROOT CAUSE CONFIRMED  
**Final Verdict:** `ROOT CAUSE CONFIRMED`  

---

## 1. Executive Summary

A comprehensive, non-destructive forensic audit of the authentication request lifecycle was conducted on production (`https://gari-team.vercel.app`) to isolate why the login button remains permanently frozen at **"Đang đăng nhập..."** without navigation or visible errors.

### Confirmed Root Cause:
The login freeze is a **compound three-tier deadlock**:
1. **Frontend Layer (Browser):** The deployed `frontend2/predict.html` and `frontend2/firebase-client.js` execute an unconstrained `await fetch('/api/auth/login')` with **zero AbortController timeout** and **zero Promise.race timeout**. When the upstream hangs, the JavaScript thread halts at the `await` statement indefinitely; neither `catch` nor `finally` is ever reached, leaving `#btnSubmitLogin` permanently disabled and frozen.
2. **Gateway Layer (Vercel Serverless):** The live deployment on Vercel is running legacy commit `2318ee75` (built Nov 10, 2026). When the upstream connection fails, its legacy error handler diverts to `handleEdgeAuth()`, which invokes `await readBody(req)`. Because `req.pipe(upstream)` has already consumed and closed the incoming request stream, `readBody(req)` deadlocks waiting for events on a dead stream. The function emits **zero bytes** and **zero headers** until Vercel platform termination.
3. **Infrastructure Layer (DNS & Origin):** The production `VERCEL_BACKEND_API_URL` environment variable targets an ephemeral Cloudflare Quick Tunnel (`*.trycloudflare.com`) whose DNS record expired. Concurrently, the Windows host FastAPI process and Cloudflare tunnel are stopped.
4. **Non-Deployment of Previous Repairs:** The repaired files in the local workspace (`api/[...path].js`, `frontend2/firebase-client.js`, and `frontend2/predict.html`) that fix the stream deadlock and introduce `safeFetch` with a 10s timeout **have never been deployed to Vercel Production**.

---

## 2. Phase 1 — Frontend Trace

### 2.1 File & Code Inspection
- **Authentication Form:** Located in `frontend2/predict.html` lines 2848–2875 (`formLogin.onsubmit`).
- **Live Deployed Code:** Extracted directly from `https://gari-team.vercel.app/frontend2/predict`:
  ```javascript
  formLogin.onsubmit = async (e) => {
      e.preventDefault();
      const email = document.getElementById('loginEmail').value.trim();
      const password = document.getElementById('loginPassword').value;
      const errBox = document.getElementById('loginErrorMsg');
      const btn = document.getElementById('btnSubmitLogin');

      errBox.style.display = 'none';
      btn.disabled = true;
      btn.textContent = 'Đang đăng nhập...';

      try {
          await window.gariAuth.login(email, password);
          toast('Đăng nhập thành công! Đã kết nối hệ thống.', 'success');
      } catch (err) {
          errBox.textContent = err.message || 'Đăng nhập không thành công. Vui lòng thử lại.';
          errBox.style.display = 'block';
      } finally {
          btn.disabled = false;
          btn.textContent = 'Đăng nhập hệ thống';
      }
  };
  ```
- **Live Deployed Client (`firebase-client.js`):** Extracted from `https://gari-team.vercel.app/frontend2/firebase-client.js`:
  ```javascript
  // 2. Native Backend Fallback
  const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password, remember_me: Boolean(rememberMe) })
  });
  const data = await safeJson(res);
  ```

### 2.2 Seven-Point Trace Verification

| Checkpoint | Status | Forensic Evidence |
| :--- | :---: | :--- |
| **1. Login Handler Called?** | **YES** | User clicks submit; `onsubmit` sets `btn.disabled = true` and `btn.textContent = 'Đang đăng nhập...'`. |
| **2. Request Actually Sent?** | **YES** | Browser dispatches HTTP POST `/api/auth/login` with JSON payload. |
| **3. Request URL Correct?** | **YES** | URL is `/api/auth/login`. |
| **4. Body Consumed Exactly Once?** | **NO (At Gateway)** | Frontend sends payload once. Gateway attempts to read stream twice (`req.pipe` then `readBody`). |
| **5. Timeout Applied to Request?** | **NO** | Native `fetch()` invoked with no `signal: AbortSignal.timeout()`; no `Promise.race()` in live `predict.html`. |
| **6. Loading State Resets?** | **NO** | Because `await fetch()` never resolves or rejects, execution is suspended at line 2860; `finally` is unreachable. |
| **7. Firebase Blocks Execution?** | **NO** | `/api/auth/firebase-config` returns `configured: false`. Firebase is skipped immediately in ~0ms. |

---

## 3. Phase 2 — Vercel Gateway Inspection

### 3.1 Local vs Deployed Gateway Matrix

| Metric | Local Workspace (`api/[...path].js`) | Live Deployed Bundle (`https://gari-team.vercel.app`) |
| :--- | :--- | :--- |
| **Body Reading** | `readRawBody(req, limit)` with 4s timeout guard | `req.pipe(upstream)` + `await readBody(req)` |
| **Stream Deadlock** | **ELIMINATED** (single memory buffer before proxy) | **ACTIVE DEADLOCK** on upstream failure |
| **Edge Auth Fallback** | **REMOVED** (Strict Fail-Closed) | **PRESENT** (`handleEdgeAuth('auth/login')`) |
| **DNS Error Handling** | Returns `HTTP 503 BACKEND_UNAVAILABLE` | Enters deadlock in `readBody(req)` |
| **Connection Error Handling** | Returns `HTTP 503 BACKEND_UNAVAILABLE` | Enters deadlock in `readBody(req)` |
| **Upstream Timeout** | Bounded at 6000ms; returns `HTTP 504` | Unbounded upstream timeout |
| **Synchronization** | `api/[...path].js` == `frontend2/api/[...path].js` | Prebuilt artifact from commit `2318ee75` (Nov 10) |

---

## 4. Phase 3 — Backend and Tunnel Inspection

| Subsystem | Target / Port | Status | Diagnostic Evidence |
| :--- | :--- | :---: | :--- |
| **FastAPI Process** | Local Windows PID | **STOPPED** | `Get-Process python`: No active processes. |
| **Local Health Endpoint** | `http://127.0.0.1:8000/health` | **OFFLINE** | `Test-NetConnection 127.0.0.1:8000`: `TcpTestSucceeded: False`. |
| **Cloudflare Tunnel Process** | `cloudflared.exe` | **STOPPED** | No active process; PID file stale. |
| **Tunnel Public DNS 1** | `implies-recognition-emails-medicaid.trycloudflare.com` | **EXPIRED** | `getaddrinfo failed [Errno 11001]` |
| **Tunnel Public DNS 2** | `ist-towards-exclude-said.trycloudflare.com` | **EXPIRED** | `getaddrinfo failed [Errno 11001]` |
| **Tunnel Public DNS 3** | `cats-lang-glory-snow.trycloudflare.com` | **EXPIRED** | `getaddrinfo failed [Errno 11001]` |
| **FastAPI Login Receipt** | Backend request logs | **ZERO** | Zero login requests ever reached the host. |

---

## 5. Phase 4 — Live Network Evidence

Read-only probes executed against production, public tunnel, and local interfaces:

```
================================================================================
                     GARI PHASE 4 LIVE EVIDENCE AUDIT LOG
================================================================================
[FAIL]    Local FastAPI Health (2.047s)        -> URLError: [WinError 10061] No connection could be made
[FAIL]    Local FastAPI API Health (2.018s)    -> URLError: [WinError 10061] No connection could be made
[FAIL]    Cloudflare Tunnel 1 (logs) (0.013s)  -> URLError: [Errno 11001] getaddrinfo failed
[FAIL]    Cloudflare Tunnel 2 (guide) (0.035s) -> URLError: [Errno 11001] getaddrinfo failed
[FAIL]    Cloudflare Tunnel 3 (recent) (0.011s)-> URLError: [Errno 11001] getaddrinfo failed
[200 OK]  Vercel Gateway Health (0.388s)       -> SUCCESS (Static Edge Gateway response)
[200 OK]  Vercel Firebase Config (0.166s)      -> SUCCESS ({"configured": false})
[502 BG]  Vercel Upstream Proxy (GET ready) (0.380s) -> HTTPError 502 BACKEND_UNAVAILABLE
[200 OK]  Vercel Predict HTML (0.172s)         -> SUCCESS (Contains unpatched onsubmit)
[200 OK]  Vercel Firebase Client JS (0.154s)   -> SUCCESS (Contains unpatched fetch)
[TIMEOUT] Vercel Login POST Probe (8.093s)     -> Socket Timeout (0 bytes received from server)
================================================================================
```

### Critical Observation:
- `GET /api/ready` (without body) returns `HTTP 502 Bad Gateway` in **0.380s** because there is no request stream to pipe or deadlock on.
- `POST /api/auth/login` (with body) **HANGS INDEFINITELY** (exceeding socket timeout with 0 bytes received) because the serverless function deadlocks inside `readBody(req)` on the consumed request stream.

---

## 6. Phase 5 — Request Lifecycle Timeline

```
[User Clicks "Đăng nhập hệ thống"]
           │
           ▼ (t = 0.000s)
[#formAuthLogin onsubmit Event Triggered]
  ├─ btn.disabled = true;
  ├─ btn.textContent = 'Đang đăng nhập...';
  └─ Invokes window.gariAuth.login(email, password)
           │
           ▼ (t = 0.005s)
[Firebase Pre-Check]
  └─ /api/auth/firebase-config returns {"configured": false}
  └─ Firebase auth is skipped immediately
           │
           ▼ (t = 0.010s)
[Frontend Network Dispatch]
  └─ Native fetch('/api/auth/login', { method: 'POST', body: ... })
  └─ VULNERABILITY: No AbortSignal timeout; browser will wait up to 300 seconds
           │
           ▼ (t = 0.150s)
[Vercel Edge / Serverless Function Receives Request]
  └─ Runs legacy [...path].js (Commit 2318ee75)
  └─ Checks VERCEL_BACKEND_API_URL -> targets expired Quick Tunnel domain
  └─ Invokes req.pipe(upstream) -> drains request stream
           │
           ▼ (t = 0.200s)
[Upstream DNS Resolution Fails]
  └─ Node.js emits 'error' (ENOTFOUND / getaddrinfo failed)
  └─ Legacy code diverts to handleEdgeAuth('auth/login')
           │
           ▼ (t = 0.205s)
[FATAL SERVERLESS DEADLOCK]
  └─ handleEdgeAuth invokes await readBody(req)
  └─ Stream req is already drained and ended
  └─ Neither 'data' nor 'end' will ever fire
  └─ Serverless function deadlocks in Node.js event loop
  └─ ZERO HTTP headers emitted; ZERO body bytes emitted
           │
           ▼ (t = 0.205s ... 15.000s ... 300.000s)
[EXECUTION FREEZES]
  ├─ Serverless function hangs until Vercel platform termination
  ├─ Browser fetch() remains pending
  ├─ JavaScript execution is stuck at "await window.gariAuth.login()"
  ├─ catch(err) is NEVER entered -> No error box displayed
  ├─ finally is NEVER entered -> Button never re-enabled
  └─ UI REMAINS PERMANENTLY FROZEN AT "Đang đăng nhập..."
```

---

## 7. Categorization & Attribution

| Dimension | Assessment | Evidence |
| :--- | :---: | :--- |
| **Is it Local?** | **PARTIAL** | FastAPI and Cloudflare Tunnel are stopped on Windows, causing upstream unavailability. |
| **Is it Tunnel?** | **YES** | Ephemeral `trycloudflare.com` domain expired; Quick Tunnels do not persist across restarts. |
| **Is it Vercel?** | **YES (PRIMARY)** | Active deployment is running obsolete bundle `2318ee75` with stream deadlock in `readBody`. |
| **Is it Frontend?** | **YES (PRIMARY)** | Active frontend lacks `AbortController` and `Promise.race` timeouts, causing permanent button freeze. |

---

## 8. Minimum Safe Remediation Plan

To permanently eliminate the auth hang without bypassing authentication:

### Step 1: Frontend Hardening (Client-Side Bounded Timeout)
- In `frontend2/predict.html`, ensure `formLogin.onsubmit` wraps `window.gariAuth.login` in `Promise.race` with an explicit 10s–15s timeout:
  ```javascript
  const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('Yêu cầu đăng nhập quá thời gian chờ (15s). Vui lòng thử lại.')), 15000)
  );
  await Promise.race([window.gariAuth.login(email, password), timeoutPromise]);
  ```
- In `frontend2/firebase-client.js`, ensure `safeFetch` with a 10s `AbortController` signal is used on `/api/auth/login`.

### Step 2: Gateway Hardening (Server-Side Bounded Buffer)
- Synchronize and deploy the local `api/[...path].js`:
  1. Buffer request body into memory ONCE via `readRawBody` with a 4s timeout before initiating upstream request.
  2. Eliminate all calls to `handleEdgeAuth`.
  3. Fail-closed with `HTTP 503 BACKEND_UNAVAILABLE` or `HTTP 504 BACKEND_TIMEOUT` on DNS/socket failure.

### Step 3: Infrastructure Stability (Persistent Backend Origin)
- Replace ephemeral Cloudflare Quick Tunnels (`*.trycloudflare.com`) with:
  - A named Cloudflare Tunnel (e.g. `api.gari.vn`), OR
  - A permanent cloud backend instance (e.g. Render / Oracle VM).
- Update `VERCEL_BACKEND_API_URL` in Vercel to point to the persistent URL.

### Step 4: Verification Before Production Promotion
- Run `tests/test_gateway_login_repair.js` locally to verify 503/504 fail-closed responses.
- Probe `POST /api/auth/login` on preview deployment with disconnected backend to verify it returns `HTTP 503` in <500ms rather than hanging.

---

## 9. Final Verdict

```
================================================================================
FINAL VERDICT: ROOT CAUSE CONFIRMED
================================================================================
```
The exact failure mechanism has been identified, traced across the full request lifecycle, and confirmed with live production evidence. Production has not been modified.
