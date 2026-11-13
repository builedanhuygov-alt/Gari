# GARI AgriTech AI Lab — Forensic Root Cause Analysis: Live Vercel 502 Errors & Pending Login

**Document ID:** GARI-FORENSIC-LIVE-502-LOGIN-2026-05  
**Target Deployment:** `https://gari-team.vercel.app` (Path: `/frontend2/predict.html`)  
**Date:** 2026-11-11  
**Investigation Mode:** READ-ONLY FORENSIC REPRODUCTION & NETWORK TRACE  

---

## 1. Executive Summary

A live network probe and binary trace of the production deployment at `https://gari-team.vercel.app` definitively isolated the dual root cause of the observed HTTP 502 errors and the permanently pending login request:

1. **Root Cause of HTTP 502:**  
   The environment variable `VERCEL_BACKEND_API_URL` in the active Vercel deployment points to an **unreachable / expired backend origin** (an ephemeral Cloudflare Quick Tunnel domain that has expired). When the Vercel gateway attempts to proxy general API routes (`/api/supported-crops`, `/api/monitoring`, `/api/notifications`), Node.js `https.request` fails with DNS `ENOTFOUND` / `ECONNREFUSED`. The gateway catches this error and returns `HTTP 502 Bad Gateway` with `{ "code": "BACKEND_UNAVAILABLE" }`.

2. **Root Cause of Pending Login ("Đang đăng nhập..."):**  
   The deployed site is running an **outdated prebuilt bundle from November 10, 2026**. When `POST /api/auth/login` fails to connect to the dead backend, the legacy gateway error handler diverts to `handleEdgeAuth()`. However, the request stream (`req`) was **already consumed/drained** by `req.pipe(upstream)`. The legacy `readBody(req)` function waits indefinitely for `'data'` and `'end'` events on the already-closed stream with **no timeout**. Concurrently, the deployed client (`firebase-client.js`) invokes native `fetch()` with **no `AbortController` timeout**. Both the Vercel serverless function and the browser hang indefinitely in `Pending` state.

---

## 2. Actual Deployment & Commit Information

- **Production Domain:** `https://gari-team.vercel.app`
- **Vercel Project ID:** `prj_WSNxryEdSCGbZQ5yBbQMzdjbvE1Y`
- **Vercel Team ID:** `team_oGV23ZOnH1KCPDtiuLtRYl0L`
- **Target Environment:** `Production`
- **Deployed Commit Hash:** `2318ee758e7a1bbeff49262961b16e8064574d3d` (Baseline: Pre-GARI 2.0 Redesign)
- **Deployed Build Timestamp:** `2026-11-10 16:39:07 UTC` (Captured in `frontend2/.vercel/output/diagnostics/cli_traces.json`)
- **Active Code Artifact:** The live site is running the prebuilt bundle stored in `frontend2/.vercel/output/functions/api/[...path].func/api/[...path].js`. It has **not received** any of the fail-closed gateway or timeout patches developed in the local workspace.

---

## 3. Status and Endpoint Matrix (Live Probe Evidence)

Live HTTP probe executed directly against `https://gari-team.vercel.app`:

| HTTP Method | Request URL | Status Code | Response Body | Root Cause |
| :--- | :--- | :---: | :--- | :--- |
| `GET` | `/api/health` | **200 OK** | `{"status":"healthy","services":{"ai_inference":"connected"...}}` | Gateway running; confirms `VERCEL_BACKEND_API_URL` is set |
| `GET` | `/api/auth/firebase-config` | **200 OK** | `{"success":true,"configured":false,"config":{"apiKey":""...}}` | Firebase client config unpopulated (`configured: false`) |
| `GET` | `/api/user/profile` | **401 Unauthorized**| `{"success":false,"code":"UNAUTHORIZED","detail":"Phiên đăng nhập đã hết hạn..."}` | Normal unauthenticated rejection on first visit |
| `GET` | `/api/supported-crops` | **502 Bad Gateway** | `{"success":false,"code":"BACKEND_UNAVAILABLE","detail":"Dịch vụ máy chủ hiện không khả dụng."}` | Proxy upstream connection error to dead backend |
| `GET` | `/api/monitoring` | **502 Bad Gateway** | `{"success":false,"code":"BACKEND_UNAVAILABLE","detail":"Dịch vụ máy chủ hiện không khả dụng."}` | Proxy upstream connection error to dead backend |
| `GET` | `/api/notifications` | **502 Bad Gateway** | `{"success":false,"code":"BACKEND_UNAVAILABLE","detail":"Dịch vụ máy chủ hiện không khả dụng."}` | Proxy upstream connection error to dead backend |
| `POST`| `/api/auth/provider-lookup`| **503 Service Unavail**| `{"success":false,"code":"BACKEND_NOT_CONFIGURED","detail":"Dịch vụ máy chủ hiện chưa được cấu hình."}` | Deployed bundle predates provider-lookup endpoint |
| `POST`| `/api/auth/login` | **Pending (Timed Out)** | *No response emitted (Hangs until client disconnect)* | Dead stream deadlock in legacy `readBody(req)` |

---

## 4. Backend Availability & Network Path Verification

### 4.1. `VERCEL_BACKEND_API_URL` Status
- **Is `VERCEL_BACKEND_API_URL` configured in the deployment environment?**  
  **YES.** In the deployed gateway bundle:
  ```javascript
  ai_inference: process.env.VERCEL_BACKEND_API_URL ? 'connected' : 'standby'
  ```
  The live response from `/api/health` reports `"ai_inference": "connected"`. This proves the environment variable exists in Vercel's production environment.

### 4.2. Upstream Reachability
- The upstream origin configured in Vercel points to an ephemeral tunnel (e.g. Cloudflare Quick Tunnel `*.trycloudflare.com`).
- Direct socket resolution probe:
  ```python
  urllib.request.urlopen('https://ist-towards-exclude-said.trycloudflare.com/api/health')
  # Result: <urlopen error [Errno 11001] getaddrinfo failed>
  ```
- The backend URL is completely offline and unresolvable from the public internet.

---

## 5. Tracing the Pending Login Request

### 5.1. Complete Execution Chain
```
[User clicks "Đăng nhập" on https://gari-team.vercel.app/frontend2/predict.html]
                        │
                        ▼
[Deployed frontend2/firebase-client.js:320]
  - Checks Firebase config -> configured: false
  - Skips Firebase sign-in
  - Executes: fetch('/api/auth/login', { method: 'POST', body: ... })
  - NOTE: fetch() has NO AbortController and NO timeout!
                        │
                        ▼ (HTTP POST /api/auth/login)
[Vercel Serverless Function: api/[...path].js:368]
  - configuredOrigin is set (points to dead tunnel)
  - Opens upstream socket: transport.request(...)
  - Pipes request body: req.pipe(upstream)  <--- STREAM CONSUMED HERE
                        │
                        ▼ (TCP / DNS Failure)
[Upstream Socket Error: ENOTFOUND]
  - upstream.on('error') fires at line 388
  - Evaluates: isAuthOrHealthRoute == true
  - Diverts to: return handleEdgeAuth(pathStr, req, res)
                        │
                        ▼
[handleEdgeAuth('auth/login', req, res): line 186]
  - Executes: const body = await readBody(req);
                        │
                        ▼
[readBody(req): line 23]
  - Attaches: req.on('data', ...) and req.on('end', ...)
  - FATAL DEADLOCK: req was already consumed and aborted by req.pipe(upstream)!
  - No further 'data' or 'end' event will ever fire.
  - readBody has NO setTimeout timer!
  - Promise remains PENDING forever.
                        │
                        ▼
[Vercel Serverless Function freezes in memory]
[Browser Network Tab stays "Pending"]
[Form button remains stuck at "Đang đăng nhập..."]
```

---

## 6. Minimal Proposed Fix

To permanently resolve both the HTTP 502 errors and the hanging login, three clean, non-regressive actions are required:

1. **Establish a Live Backend Origin:**
   - Launch your public FastAPI backend with a permanent HTTPS origin (e.g. Cloudflare Named Tunnel or Oracle VM).
   - In the [Vercel Project Dashboard](https://vercel.com) (Settings > Environment Variables), update `VERCEL_BACKEND_API_URL` with the live HTTPS backend URL.

2. **Deploy the Patched Gateway (`api/[...path].js`):**
   - The workspace version of `api/[...path].js` completely eliminates the deadlock:
     * It checks pre-buffered `req.body` and `req.readableEnded`.
     * It uses `readRawBody` with a **hard 4,000ms bounded timeout** (`setTimeout`), making hanging impossible.
     * It eliminates the legacy fallback to `handleEdgeAuth()`.
     * Unreachable backends cleanly return `HTTP 503` instead of hanging or returning unhandled 502s.

3. **Deploy the Patched Client (`frontend2/firebase-client.js`):**
   - The workspace version of `firebase-client.js` uses `safeFetch()` with a **hard 10,000ms timeout** via `AbortController`. Even if an edge proxy stutters, the UI catches the timeout after 10 seconds and displays a clean error banner, immediately restoring the button state.

---

## 7. Redeployment Requirement Assessment

- **Is redeployment required?**  
  **YES. Redeployment is mandatory.**
- **Reason:**  
  The live deployment `https://gari-team.vercel.app` is running stale prebuilt code from November 10. The dead-stream deadlock in `readBody(req)` and the missing `provider-lookup` endpoint exist inside the live deployed bundle. Simply changing environment variables will fix the 502 errors once the backend is reachable, but any future backend disconnect would immediately re-trigger the pending login hang until the patched gateway is deployed.

---

## 8. Final Verdict

# **ROOT CAUSE CONFIRMED**

### Summary of Confirmation:
- **502 Bad Gateway:** Confirmed caused by `VERCEL_BACKEND_API_URL` pointing to an expired / unresolvable backend origin, triggering `upstream.on('error')` in the Vercel gateway.
- **Pending Login ("Đang đăng nhập..."):** Confirmed caused by a stream consumption deadlock in the deployed legacy gateway: `req.pipe(upstream)` drains the request stream before connection failure, after which `handleEdgeAuth()` invokes `readBody(req)` without a timeout on the dead stream, causing both the Vercel function and the browser to hang indefinitely.

