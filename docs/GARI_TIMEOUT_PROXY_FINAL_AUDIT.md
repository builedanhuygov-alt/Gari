# GARI AgriTech AI Lab — Timeout & Trusted Proxy Architectural Audit

**Document ID:** GARI-AUDIT-TIMEOUT-PROXY-2026-04  
**Date:** 2026-11-11  
**Project:** `D:\leaf-diseases-detector-main`  
**Audit Scope:** Vercel function timeouts, edge gateway socket timeouts, PyTorch model cold-start latency, reverse proxy topology, and client IP rate limiting  
**Mode:** READ-ONLY ARCHITECTURAL INVESTIGATION  

---

## 1. Source Files & Exact Relevant Configuration

### 1.1. Vercel Configuration & Gateway Configuration
- **`vercel.json` (Lines 1–140):**
  ```json
  {
    "version": 2,
    "cleanUrls": true,
    "trailingSlash": false,
    "public": false,
    "rewrites": [ ... ]
  }
  ```
  *Analysis:* `vercel.json` contains **no `functions` block** and **no `maxDuration` declaration**.
  *Platform Limit:* On Vercel, when `maxDuration` is omitted:
  - **Hobby Plan:** Serverless Functions have an unchangeable maximum execution limit of **15 seconds** (formerly 10s).
  - **Pro Plan:** Serverless Functions default to **15 seconds**, but can be configured up to **300 seconds** (Fluid Compute).

- **`api/[...path].js` (Lines 4, 169–174, 211–226):**
  ```javascript
  module.exports.config = { api: { bodyParser: false } };
  ...
  timeout: isAuthOrHealthRoute ? 6000 : Number(process.env.VERCEL_BACKEND_TIMEOUT_MS || 15000),
  ...
  upstream.on('timeout', () => {
    upstream.destroy(new Error('Upstream timeout'));
  });
  upstream.on('error', () => {
    handleBackendUnavailable(pathStr, res);
  });
  ```
  *Analysis:*
  - Auth/Health routes time out at **6,000ms (6s)**.
  - General backend routes (including `/api/predict`) time out at **15,000ms (15s)** unless `VERCEL_BACKEND_TIMEOUT_MS` is explicitly passed in the environment.
  - An upstream timeout triggers `upstream.destroy()`, calling `handleBackendUnavailable()`, which responds with `HTTP 503 AI_INFERENCE_STANDBY`.

### 1.2. FastAPI Backend & Inference Configuration
- **`gari_config.py` (Line 90):**
  ```python
  INFERENCE_TIMEOUT_SECONDS = int(os.getenv("INFERENCE_TIMEOUT_SECONDS", "60"))
  ```
- **`gari_model_lifecycle.py` (Lines 130–146):**
  ```python
  self.idle_timeout_seconds = float(os.getenv("MODEL_IDLE_TIMEOUT_SECONDS", "300"))
  self.max_cached = int(os.getenv("MAX_CACHED_MODELS", "3"))
  self.preload_enabled = bool(os.getenv("MODEL_PRELOAD_ENABLED", "false").lower() in ("true", "1", "yes"))
  ```
  *Analysis:*
  - `MODEL_PRELOAD_ENABLED` defaults to `False`. When the server boots, **zero AI models are resident in RAM**.
  - `MODEL_IDLE_TIMEOUT_SECONDS` defaults to `300s` (5 minutes). A model loaded in RAM is purged after 5 minutes of inactivity.
- **`api_server.py` (Lines 810–832, 847):**
  ```python
  _PROVIDER_LOOKUP_RATE_LIMIT: Dict[str, list] = {}
  PROVIDER_LOOKUP_RATE_LIMIT_MAX = 60
  PROVIDER_LOOKUP_RATE_LIMIT_WINDOW = 60

  @app.post("/api/auth/provider-lookup")
  async def provider_lookup_endpoint(payload: ProviderLookupPayload, request: Request):
      client_ip = request.client.host if request.client else "0.0.0.0"
      ...
  ```
  *Analysis:*
  - `_PROVIDER_LOOKUP_RATE_LIMIT` is stored in process-local memory.
  - `client_ip` is extracted exclusively from `request.client.host` (the immediate TCP socket peer).

---

## 2. Investigation A: Vercel Timeout Compatibility

### 2.1. Request Path & Timeout Layering
```
[User Browser]
      │
      ▼ (HTTPS Request)
[Vercel Edge Proxy] ────────── Platform Limit: Default 15s (Hobby / Unconfigured Pro)
      │
      ▼
[api/[...path].js] ─────────── Socket Timeout: 15s (VERCEL_BACKEND_TIMEOUT_MS default)
      │
      ▼ (Network Tunnel / Cloudflare / Public IP)
[FastAPI / api_server.py] ──── Inference Timeout: 60s (INFERENCE_TIMEOUT_SECONDS)
      │
      ▼
[PyTorch CPU Model Load] ───── Cold-Start Latency: ~41s (ViT Model tong: 327MB)
```

### 2.2. Cold-Start vs Warm Inference Latency
1. **Cold Start (Model not in RAM):**
   - Disk read (327MB) + PyTorch tensor allocation + graph initialization on CPU: **~41.0 seconds**.
   - Result:
     - At second 15, `api/[...path].js` fires `upstream.on('timeout')` and aborts with `HTTP 503 AI_INFERENCE_STANDBY`.
     - At second 15, Vercel's serverless edge terminates with `HTTP 504 FUNCTION_INVOCATION_TIMEOUT`.
     - **A 41-second cold start CANNOT complete through the deployed request path under default settings.**
2. **Warm State (Model cached in RAM):**
   - Image decoding + forward pass on CPU: **~2.1 seconds**.
   - Result: Easily completes within both the 15s gateway timeout and 15s platform limit.
3. **Idle Eviction Risk:**
   - Because `MODEL_IDLE_TIMEOUT_SECONDS = 300` (5 minutes), any idle period over 5 minutes evicts the model back to disk. The subsequent request becomes a cold start and fails.

### 2.3. Platform Limits vs Application Limits
| Level | Component | Setting | Default Value | Max Value |
| :--- | :--- | :--- | :--- | :--- |
| **Platform** | Vercel Serverless Function | `maxDuration` | 15 seconds | 15s (Hobby) / 300s (Pro/Fluid) |
| **Gateway** | `api/[...path].js` | `VERCEL_BACKEND_TIMEOUT_MS` | 15,000 ms (15s) | Up to function `maxDuration` |
| **Application**| `gari_config.py` | `INFERENCE_TIMEOUT_SECONDS` | 60 seconds | Process internal |
| **Lifecycle** | `gari_model_lifecycle.py` | `MODEL_IDLE_TIMEOUT_SECONDS`| 300 seconds | Memory capacity bound |

---

## 3. Investigation B: Trusted Proxy & Rate Limiting

### 3.1. Request Flow & Client IP Resolution
When deployed with Vercel Preview frontend and Cloudflare Tunnel backend:
```
[User: 14.232.208.50]
         │
         ▼
[Vercel Serverless Function] 
  - Sees client IP: 14.232.208.50
  - Sets req.headers['x-forwarded-for'] = '14.232.208.50'
  - Egress IP: Vercel AWS Lambda node (e.g. 76.76.21.21)
         │
         ▼ (Public Internet)
[Cloudflare Edge]
  - Injects headers: cf-connecting-ip, x-forwarded-for
         │
         ▼ (QUIC Tunnel)
[cloudflared daemon on Host]
  - Forwards over local TCP socket to http://127.0.0.1:8000
         │
         ▼
[FastAPI / Uvicorn]
  - Reads request.client.host
  - Socket peer address is 127.0.0.1!
```

### 3.2. Critical Finding: Rate Limit Collusion under Reverse Proxy
1. **Under Cloudflare Tunnel:**
   - The TCP connection to Uvicorn originates from the local `cloudflared` process.
   - `request.client.host` evaluates to **`"127.0.0.1"` for 100% of public internet requests**.
   - **Impact:** All users across the globe share a **single rate limit bucket** of 60 requests/minute. Once the collective traffic exceeds 60 lookups in 60 seconds, **all subsequent users are blocked with HTTP 429 Too Many Requests**.
2. **Under Direct Public IP (without Tunnel):**
   - The TCP connection originates from Vercel's Serverless Function egress IP pool.
   - Multiple users served by the same Vercel data center share the same egress IP, causing partial rate limit collisions.

### 3.3. Header Spoofing vs Trusted Boundaries
- *Why not read `X-Forwarded-For` naively?*
  If FastAPI reads `request.headers.get("x-forwarded-for")` without verifying the proxy, any attacker can send:
  ```http
  X-Forwarded-For: 1.2.3.4
  ```
  and rotate this header on every request, completely bypassing rate limits.
- *Trusted Boundary Definition:*
  `X-Forwarded-For` or `CF-Connecting-IP` can only be trusted if:
  1. The direct peer (`request.client.host`) is explicitly listed in a trusted IP list (`127.0.0.1` for local tunnel, or known reverse proxy CIDRs).
  2. OR a cryptographically secure shared header (e.g. `X-Gari-Gateway-Secret`) verifies that the request originated from the official Vercel gateway.

### 3.4. Multi-Worker Process Concurrency
- `_PROVIDER_LOOKUP_RATE_LIMIT` is process-local.
- In multi-worker Uvicorn configurations (`--workers 4`), each process maintains an isolated in-memory dictionary.
- Requests distributed round-robin across 4 workers effectively multiply the rate limit to 240 req/min, with non-deterministic enforcement (a user may be blocked on worker 1 but allowed on worker 2).
- Worker restarts or auto-reloads wipe the rate limit state instantly.

### 3.5. Account Enumeration Surface
- `/api/auth/provider-lookup` accepts `{ "email": "user@example.com" }` and returns `{ "exists": true/false, "provider": ... }`.
- Even with rate limiting, an adversary rotating IP addresses through residential proxies can enumerate registered accounts.

---

## 4. Confirmed Facts vs. Unverified Assumptions

| Fact / Assumption | Status | Evidence Source |
| :--- | :--- | :--- |
| **`maxDuration` is omitted in `vercel.json`** | **CONFIRMED FACT** | Direct inspection of `vercel.json`. |
| **Gateway defaults to 15s timeout** | **CONFIRMED FACT** | Direct inspection of `api/[...path].js:211`. |
| **ViT model cold-start takes ~41s** | **CONFIRMED FACT** | Benchmark log in previous test runs (`benchmark_diagnosis_perf.py`). |
| **Synchronous cold start fails on default Vercel** | **CONFIRMED FACT** | 41s latency > 15s gateway timeout = 503/504 abort. |
| **Warm inference executes in ~2.1s** | **CONFIRMED FACT** | Local test run in Task-6467 / Task-6477 (`POST /api/predict`). |
| **`request.client.host` sees 127.0.0.1 under tunnel** | **CONFIRMED FACT** | Socket topology of local `cloudflared` proxying to `127.0.0.1:8000`. |
| **Actual Vercel Preview HTTP behavior** | **UNVERIFIED ASSUMPTION** | No preview deployment has been run; cloud edge behavior is unverified. |
| **Vercel Account Plan (Hobby vs Pro)** | **UNVERIFIED ASSUMPTION** | Project ID `prj_WSNxryEdSCGbZQ5yBbQMzdjbvE1Y` plan tier is unknown. |

---

## 5. Risk Ranking & Severity Assessment

| Rank | Risk | Severity | Root Cause | Failure Mode |
| :---: | :--- | :---: | :--- | :--- |
| **1** | **Cold-Start Gateway Timeout** | **CRITICAL** | Default 15s Vercel/gateway limit vs 41s model load | 503/504 error on first diagnosis after idle >5m |
| **2** | **Tunnel Rate Limit Collusion** | **HIGH** | `request.client.host` sees `127.0.0.1` for all tunnel users | Global 60 req/min lock for all concurrent users |
| **3** | **Account Enumeration via Lookup** | **MEDIUM** | Public endpoint returns boolean account existence | Automated email harvesting via proxy rotation |
| **4** | **Multi-Worker Rate Divergence** | **LOW** | In-memory process-local dictionary | Inconsistent rate enforcement across worker processes |

---

## 6. Recommended Remediation (Non-Implemented Design)

### 6.1. Remediation for Timeout Risk (Choose Path A or B)
- **Path A: Model Pre-Warming & Keep-Alive (Immediate / Zero-Code Change):**
  1. Set backend environment variable:
     ```env
     MODEL_PRELOAD_ENABLED=true
     MODEL_IDLE_TIMEOUT_SECONDS=86400
     ```
  2. On FastAPI startup, pre-load priority models (`Model tong`, `Model lua`) into RAM.
  3. All requests will execute in warm state (~2.1s), remaining well beneath the 15s limit.
- **Path B: Vercel Function Duration Expansion (Requires Vercel Pro):**
  1. Add to `vercel.json`:
     ```json
     "functions": {
       "api/**/*.js": {
         "maxDuration": 60
       }
     }
     ```
  2. Set `VERCEL_BACKEND_TIMEOUT_MS=60000` in Vercel environment variables.
- **Path C: Asynchronous Job Architecture (Long-term Production):**
  - Transform `/api/predict` into an async worker: returns `202 Accepted` with a `job_id`, client polls `/api/predict/jobs/{job_id}`.

### 6.2. Remediation for Proxy Rate Limiting
- **Extract Client IP via Trusted Proxy Middleware:**
  1. Configure Uvicorn with `--proxy-headers --forwarded-allow-ips="127.0.0.1"`.
  2. In `api_server.py`, inspect `X-Forwarded-For` or `CF-Connecting-IP` **only if** `request.client.host == "127.0.0.1"`:
     ```python
     def get_real_client_ip(request: Request) -> str:
         if request.client and request.client.host == "127.0.0.1":
             cf_ip = request.headers.get("cf-connecting-ip")
             if cf_ip: return cf_ip.strip()
             fwd = request.headers.get("x-forwarded-for")
             if fwd: return fwd.split(",")[0].strip()
         return request.client.host if request.client else "0.0.0.0"
     ```

### 6.3. Remediation for Account Enumeration
- Unify authentication dispatch on the backend:
  Accept email and password at `/api/auth/login`. Have FastAPI evaluate both SQLite bcrypt and Firebase/Supabase internally without exposing an unauthenticated `provider-lookup` endpoint to the public browser.

---

## 7. Preview Safety Evaluation

### Can a Controlled Preview Safely Begin?
- **Authentication & User Management:** **SAFE.** Login, registration, profile checks, session creation, and logout are fast (<100ms) and 100% verified.
- **AI Diagnosis (Prediction):** **UNSAFE on cold start** unless `MODEL_PRELOAD_ENABLED=true` is set on the backend host before testing. If models are not pre-warmed, the first inference request will fail with an HTTP 503 or 504 timeout.
- **Multi-user Concurrency:** **RISK of 429 lock** under Cloudflare Tunnel due to shared `127.0.0.1` IP extraction if more than 60 lookup requests occur per minute.

---

## 8. Final Verdict

# **BLOCKED — TIMEOUT RISK**

### Justification:
The platform's primary value proposition — AI leaf disease diagnosis — cannot reliably complete through the deployed Vercel serverless request path during a cold-start event. The 41-second model load exceeds the 15-second gateway timeout and Vercel Serverless Function duration limits.

Triển khai Preview chỉ nên được kích hoạt sau khi:
1. Kích hoạt `MODEL_PRELOAD_ENABLED=true` trên máy chủ backend để đưa thời gian chẩn đoán xuống 2.1s (warm state).
2. Thiết lập `VERCEL_BACKEND_API_URL` trong Vercel Dashboard.
3. Điều chỉnh logic trích xuất IP qua proxy để tránh việc toàn bộ người dùng dùng chung hạn mức rate-limit `127.0.0.1`.

