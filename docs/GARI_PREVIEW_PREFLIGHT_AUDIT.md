# GARI AgriTech AI Lab — Pre-Flight Audit for Vercel Preview Deployment

**Document ID:** GARI-AUDIT-PREVIEW-PREFLIGHT-2026-03  
**Date:** 2026-11-11  
**Audit Mode:** READ-ONLY PRE-FLIGHT AUDIT  
**Scope:** Provider lookup rate limiting, Session security, Vercel gateway, AI inference pipeline, Supabase migration status  

---

## 1. Confirmed Findings

### 1.1. Session Token Architecture & Security
- **Token Type:** The backend returns an **opaque session token** consisting of 48 URL-safe characters (`secrets.token_urlsafe(36)`), providing 288 bits of cryptographic entropy.
- **Persistence:** Generated in `gari_auth.create_session()` and persisted in the local SQLite table `user_sessions` with fields: `token`, `user_id`, `expires_at`, `ip_address`, and `user_agent`.
- **Validation:** Protected endpoints enforce `Depends(get_current_user)`, which queries `user_sessions` joined with `users` where `s.token = ? AND s.expires_at > UTC NOW()`.
- **User State Enforcement:** Both inactive accounts (`u.is_active == 0`) and banned accounts (`u.moderation_status == 'banned'`) return `None` (HTTP 401 Unauthorized), preventing disabled users from authenticating.
- **Revocation:** `POST /api/auth/logout` explicitly deletes the token from `user_sessions` via `DELETE FROM user_sessions WHERE token = ?`.
- **Zero Credential / Token Logging:** Static code analysis confirms that raw passwords, Bcrypt hashes, Bearer tokens, session cookies, and private keys are never printed to logs or standard output.

### 1.2. Provider Lookup Rate Limiter
- **Storage Mechanism:** Process-local in-memory Python dictionary (`_PROVIDER_LOOKUP_RATE_LIMIT: Dict[str, list]`). It is **not shared** across processes, threads, or instances.
- **IP Extraction:** Reads `request.client.host if request.client else "0.0.0.0"` directly from the incoming TCP socket.
- **Header Spoofing Resistance:** Because it inspects the direct socket host rather than trusting unvalidated headers (`X-Forwarded-For`, `X-Real-IP`), arbitrary client header spoofing cannot bypass the limit.
- **Rate Limit Window:** Sliding window of 60 requests per 60 seconds per IP. Exceeding requests are rejected with `HTTP 429 Too Many Requests`.
- **Data Minimization:** Response payload contains only `{"success": true, "exists": bool, "provider": str}`. No user IDs, names, email addresses, or password hashes are revealed.

### 1.3. Vercel Gateway & Fail-Closed Enforcement
- **Gateway Location:** Located at root `api/[...path].js` (and mirrored identically in `frontend2/api/[...path].js`).
- **Root Directory:** `.vercel/project.json` has `rootDirectory: null` (repository root is project root). Route rewrites in `vercel.json` direct HTML requests to `/frontend2/*.html` and API requests to `api/[...path].js`.
- **Fail-Closed on Cloud:** When deployed (`process.env.VERCEL_ENV` is set to `"preview"` or `"production"`), `api/[...path].js` disables localhost fallback. If `VERCEL_BACKEND_API_URL` is not set, all API requests immediately return `HTTP 503 Service Unavailable` with `BACKEND_UNAVAILABLE`.

### 1.4. Protected AI Inference Flow
- **Authentication Gate:** `POST /api/predict` (and aliases `/predict`, `/api/plant/diagnose`) strictly requires `Depends(get_current_user)`.
- **Execution Order:** Authentication and moderation checks (`enforce_user_moderation_access`) execute **before** reading large multipart image streams and before any PyTorch model weights are loaded into memory.
- **Unauthenticated Rejection:** Local tests confirm unauthenticated and invalid token requests return `HTTP 401 Unauthorized` without consuming model inference compute.

---

## 2. Findings Based Only on Previous Test Reports

The following findings rely on historical test outputs and have not been re-verified in live cloud conditions during this turn:
1. **Model Cold-Start Timing:** Previous benchmark logs report that loading the ViT model (`Model tong`, 327MB) on CPU takes ~41 seconds upon initial cold start.
2. **Post-Registration Hang Resolution:** The reported resolution of the `"Đang khởi tạo tài khoản..."` hang in historical test suites (`test_safe_auth_reproduction.js`) relies on client-side promise timeouts and has not been tested against a throttled live edge proxy.
3. **82/82 Test Suite Status:** Previous reports cited 82/82 passing tests across all modules (Modules 01–13); individual module suites were not re-run during this read-only pre-flight.

---

## 3. Unverified Assumptions

1. **Cloud Inference Unverified:** There is **no evidence** of an end-to-end AI diagnosis request succeeding on an actual Vercel Preview URL. All verified tests have been executed on `http://127.0.0.1:8000`.
2. **Reverse Proxy Egress Shared IP:** It is assumed that requests forwarded by Vercel edge functions to a backend tunnel will share the Vercel gateway/tunnel egress IP. In production without trusted proxy configuration, multiple distinct users may share the single IP rate limit bucket.
3. **Vercel Pro vs Hobby Function Duration:** It is assumed that Vercel Preview will run under default serverless function timeouts (15 seconds) because no `maxDuration` is specified in `vercel.json`.

---

## 4. Security & Operational Risks

| Risk Category | Severity | Description | Impact |
| :--- | :--- | :--- | :--- |
| **Account Enumeration** | **MEDIUM** | While rate limited to 60 req/min/IP, `/api/auth/provider-lookup` returns `exists: true/false`. An adversary can probe whether an email is registered on GARI AgriTech AI Lab. | Potential email enumeration if an attacker rotates proxy IPs. |
| **Reverse Proxy Rate Limit Collusion** | **MEDIUM** | In a deployed environment where all traffic routes through a single Vercel function or Cloudflare Tunnel to FastAPI, `request.client.host` may see the tunnel IP for all users. | Multiple users on the same preview deployment could collectively exhaust the 60 req/min limit. |
| **Model Cold-Start Gateway Timeout** | **HIGH** | Default Vercel function duration is 15s, and gateway upstream timeout is 15s (`VERCEL_BACKEND_TIMEOUT_MS`). Cold-start model load can take 30–40s on CPU. | First inference request on a cold backend will fail with HTTP 504 Gateway Timeout or 503 Upstream Error. |
| **Memory Exhaustion on Multi-Model Concurrency** | **MEDIUM** | Concurrently classifying multiple different crops (tomato, rice, cassava, pepper) loads separate PyTorch models into RAM. `ModelLifecycleManager` caps cached models at 3, but concurrent inference can cause CPU saturation. | Slower response times or process restart under constrained VM RAM (<2GB). |

---

## 5. Supabase Migration Readiness Assessment

- **Current Implementation:** The live authentication and user management in `frontend2/login.html`, `frontend2/register.html`, and `frontend2/app.js` **remains 100% on Firebase and SQLite**.
- **Supabase Credentials:** Unconfigured. Environment variables `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_JWT_SECRET` are all unset/null.
- **Client Integration:** Neither `login.html` nor `register.html` imports the Supabase JS SDK.
- **Backend Bridge Status:** `gari_auth.py` contains JWKS verification logic (`verify_supabase_jwt`) and identity link provisioning (`resolve_or_provision_supabase_user`), but these code paths are dormant until Supabase JWTs are issued by a Supabase frontend client.
- **Migration Conclusion:** The system is **NOT** migrated to Supabase Auth. It operates as a dual-fallback Firebase/SQLite architecture. Do not claim Supabase is ready or active.

---

## 6. Preview Deployment Configuration Checklist

Before initiating any Vercel Preview deployment, the following configuration must be supplied in the Vercel Dashboard:

| Item | Required Action | Status |
| :--- | :--- | :--- |
| **1. Public Backend Origin** | Host FastAPI backend with a public HTTPS URL (e.g. Cloudflare Tunnel, Oracle VM, Railway). | User action required |
| **2. VERCEL_BACKEND_API_URL** | Set in Vercel Dashboard -> Settings -> Environment Variables (Target: `Preview`). | **MISSING** |
| **3. VERCEL_BACKEND_TIMEOUT_MS** | Set to `45000` (45s) in Vercel Environment Variables to accommodate model cold start. | Optional / Recommended |
| **4. FIREBASE_API_KEY / PROJECT_ID** | Ensure Firebase public configuration is populated in Vercel environment variables if Firebase client auth is desired. | Check Dashboard |
| **5. Model Pre-warming** | Pre-warm priority models (e.g. `Model tong`, `Model lua`) on the backend server before routing user traffic. | Server startup recommendation |

---

## 7. Recommended Next Actions (Prioritized)

1. **Configure VERCEL_BACKEND_API_URL in Vercel Dashboard:**
   - Add `VERCEL_BACKEND_API_URL` pointing to your live FastAPI backend HTTPS URL.
2. **Adjust Vercel Serverless Function Max Duration (Optional but Recommended):**
   - If using Vercel Pro, add to `vercel.json`:
     ```json
     "functions": {
       "api/**/*.js": {
         "maxDuration": 60
       }
     }
     ```
   - Set `VERCEL_BACKEND_TIMEOUT_MS=45000` in Vercel Environment Variables to prevent gateway timeouts on CPU inference cold starts.
3. **Execute Controlled Preview Deploy:**
   - Run `vercel` (do NOT run `vercel --prod`).
4. **Conduct End-to-End Cloud Browser Verification:**
   - Once a Preview URL is generated, execute Playwright tests targeting the actual Preview URL to verify cloud inference and cloud authentication.

---

## 8. Final Verdict

# **BLOCKED — CONFIGURATION MISSING**

### Justification:
The code, security rules, rate limiters, session management, and local inference pipeline have been verified and meet all functional requirements. However, **`VERCEL_BACKEND_API_URL` is not configured in the Vercel project environment**. Deploying to Vercel Preview without this variable will result in immediate HTTP 503 fail-closed responses for all API and authentication flows.

