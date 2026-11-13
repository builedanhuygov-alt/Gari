# GARI — Sprint H.2.1: Cloud Authentication Reality Check Report
**Document:** `docs/GARI_SPRINT_H2_1_CLOUD_AUTH_VERIFICATION.md`  
**Date:** November 13, 2026  
**Status:** FORENSIC REALITY CHECK COMPLETE  
**Deployment Evaluated:** `https://gari-team-lzge5yqpp-bui11.vercel.app` (Deployment ID: `dpl_CczjwZVTegUDMvmagcwaECDmEiy2`)  
**Previous Preview:** `https://gari-team-258545zzp-bui11.vercel.app` (Deployment ID: `dpl_B2MSmbgPWPdBLTFP7fWgzW1tLCFq`)  

---

## 1. Executive Summary & Final Verdict

**FINAL VERDICT: CLOUD AUTH NOT INTEGRATED (BLOCKED — PREVIEW CONFIGURATION MISSING)**

A forensic investigation into the live Preview deployment and repository source code reveals that **Supabase Auth is NOT currently integrated into the user-facing application**:
1. While a standalone Supabase client exists on disk (`frontend2/supabase-client.js`), it is **completely orphaned**: zero HTML pages or JS modules import or invoke it.
2. The active login interface (`frontend2/predict.html`) exclusively imports `frontend2/firebase-client.js`.
3. In `frontend2/firebase-client.js`, Firebase is unconfigured (`configured: false`), causing all login requests to route directly to `POST /api/auth/login`.
4. The Edge Gateway (`api/[...path].js`) forwards `/api/auth/login` directly to `VERCEL_BACKEND_API_URL` (the local Windows FastAPI backend).
5. No Supabase environment variables (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `NEXT_PUBLIC_SUPABASE_URL`) are configured on Vercel Preview.
6. The Supabase cloud projects under the user's organization are currently in `INACTIVE` (paused) status.
7. Consequently, **when the Windows PC is offline, 100% of login attempts fail with HTTP 503 `BACKEND_UNAVAILABLE`**. True Cloud Authentication does not yet operate in the cloud environment.

---

## 2. Phase 1 — Trace Authority (Forensic Source Analysis)

| Investigation Question | Reality Check Finding | Exact File & Line Reference |
|---|---|---|
| **1. Which provider handles login?** | **FastAPI + SQLite** via Edge Gateway proxy. The UI imports `GariAuthClient` from `firebase-client.js`, which falls through to `/api/auth/login`. | [`frontend2/predict.html#L2684`](file:///d:/leaf-diseases-detector-main/frontend2/predict.html#L2684)<br>[`frontend2/firebase-client.js#L430`](file:///d:/leaf-diseases-detector-main/frontend2/firebase-client.js#L430) |
| **2. Does login call Supabase Auth?** | **NO.** `frontend2/supabase-client.js` is never imported. Neither the frontend nor the Gateway issues any request to GoTrue / Supabase Auth endpoints. | [`frontend2/supabase-client.js#L1-L450`](file:///d:/leaf-diseases-detector-main/frontend2/supabase-client.js) (orphaned file) |
| **3. Does it call FastAPI?** | **YES.** All login submissions invoke `safeFetch('/api/auth/login')`, which `api/[...path].js` proxies to `VERCEL_BACKEND_API_URL`. | [`frontend2/firebase-client.js#L430`](file:///d:/leaf-diseases-detector-main/frontend2/firebase-client.js#L430)<br>[`api/[...path].js#L205-L229`](file:///d:/leaf-diseases-detector-main/api/[...path].js#L205-L229) |
| **4. Does it call Firebase?** | **NO.** Initial handshake checks `/api/auth/firebase-config`. Since no keys are configured, `this.isFirebaseReady` remains `false`. No traffic reaches Google Firebase. | [`frontend2/firebase-client.js#L49-L71`](file:///d:/leaf-diseases-detector-main/frontend2/firebase-client.js#L49-L71) |
| **5. Is there any fallback between providers?** | **NO.** There is no Edge Auth or synthetic session fallback. If FastAPI is offline, Gateway returns HTTP 503 `BACKEND_UNAVAILABLE` (fail-closed). | [`api/[...path].js#L118-L127`](file:///d:/leaf-diseases-detector-main/api/[...path].js#L118-L127) |
| **6. Where is the authenticated session stored?** | In the browser's `localStorage` (`gari_token` and `gari_user`), populated only when FastAPI returns a genuine JWT. | [`frontend2/firebase-client.js#L207`](file:///d:/leaf-diseases-detector-main/frontend2/firebase-client.js#L207) |
| **7. Which component validates authorization?** | The Windows FastAPI backend via `GET /api/user/profile` with `Authorization: Bearer <token>`. Gateway does not validate JWTs locally. | [`frontend2/firebase-client.js#L186-L200`](file:///d:/leaf-diseases-detector-main/frontend2/firebase-client.js#L186-L200) |

---

## 3. Phase 2 — Supabase Configuration Status

| Configuration Requirement | Status on Vercel Preview | Evidence & Details |
|---|---|---|
| **Supabase Project URL** | **NOT CONFIGURED** | `vercel env ls` shows only `VERCEL_BACKEND_API_URL`. No `SUPABASE_URL` exists. |
| **Public Publishable/Anon Key** | **NOT CONFIGURED** | Missing from Preview and Production environment variables. |
| **Supabase Auth Enabled** | **BLOCKED / PAUSED** | Supabase projects (`uvrakfbgtodftczuzggg` & `qwfgeqnkfouzhpshpgzv`) are in `INACTIVE` state. DNS fails (`getaddrinfo failed`). |
| **Email/Password Provider** | **UNVERIFIED** | Cloud project is dormant; management APIs return inactive project state. |
| **Redirect URLs include Preview** | **NOT CONFIGURED** | Cloud project settings not initialized for `*.vercel.app` preview domains. |
| **Profile Provisioning Trigger** | **LOCAL SQL ONLY** | Migrations 1–5 exist locally in `supabase/migrations/` but have not been executed on a live cloud database. |
| **RLS Policies Active** | **LOCAL SQL ONLY** | Defined in migrations; not running on any active live PostgreSQL instance. |

---

## 4. Phase 3 & 4 — Synthetic Account & Windows Offline Tests

Tests executed against live Preview deployment `https://gari-team-lzge5yqpp-bui11.vercel.app` while Windows PC / FastAPI is OFFLINE:

### Test Results

| Step | Action | Expected (if Cloud Auth worked) | Actual Result Observed | Status |
|---|---|---|---|---|
| **1. UI Load** | Load `/frontend2/predict` | 200 OK | HTTP 200 OK (~450ms) | **PASS** |
| **2. Synthetic Login** | Submit `synthetic_preview_test@gari.vn` | 200 OK + Supabase JWT | **HTTP 503 `BACKEND_UNAVAILABLE`** | **FAIL (Hard dependency)** |
| **3. Invalid Password** | Submit wrong password | 401 Invalid Credentials | **HTTP 503 `BACKEND_UNAVAILABLE`** | **FAIL (Hard dependency)** |
| **4. Profile Retrieval** | Fetch `/api/user/profile` | 200 OK with cloud profile | **HTTP 503 `BACKEND_UNAVAILABLE`** | **FAIL (Hard dependency)** |
| **5. Session Persistence** | Refresh page | Session restored from storage | No session created | **BLOCKED** |
| **6. Logout** | Trigger `logout()` | GoTrue revoke + clear storage | No cloud session to revoke | **BLOCKED** |

### Live Request Evidence
```http
POST /api/auth/login HTTP/1.1
Host: gari-team-lzge5yqpp-bui11.vercel.app
Content-Type: application/json
Content-Length: 78

{"email":"synthetic_preview_test@gari.vn","password":"TestPassword123!"}

HTTP/1.1 503 Service Unavailable
Content-Type: application/json; charset=utf-8
X-Vercel-Cache: MISS

{
  "success": false,
  "code": "BACKEND_UNAVAILABLE",
  "detail": "Máy chủ xác thực hiện chưa sẵn sàng hoặc đang bảo trì. Vui lòng thử lại sau giây lát."
}
```

---

## 5. Phase 5 — Gateway Error Semantics Compliance

The Edge Gateway error semantics adhere strictly to HTTP standards:

| Scenario | HTTP Status | Error Code | Semantic Definition | Frontend UI Handling |
|---|---|---|---|---|
| **Upstream Offline / Connection Refused / DNS Error** | **503** | `BACKEND_UNAVAILABLE` | Service Unavailable (standby mode). | Displays standby message, button resets in `finally`. |
| **Upstream Response Timeout (> 3.5s auth, > 10s inference)** | **504** | `BACKEND_TIMEOUT` | Gateway Timeout (upstream slow). | Displays timeout message, button resets in `finally`. |
| **Invalid Credentials (from upstream or GoTrue)** | **401** | `INVALID_CREDENTIALS` | Authentication Rejection. | Displays `"Email hoặc mật khẩu không chính xác."`, button resets. |
| **Rate Limiting** | **429** | `TOO_MANY_REQUESTS` | Rate Limit Exceeded. | Displays rate limit notice, button resets. |

---

## 6. Remaining Dependencies on Windows PC

Every one of the following capabilities currently requires the Windows PC / FastAPI to be actively running:

1. **User Login (`/api/auth/login`):** Requires Windows FastAPI + SQLite Bcrypt hash check.
2. **User Registration (`/api/auth/register`):** Requires Windows FastAPI + SQLite insert.
3. **Session Verification (`/api/user/profile`):** Requires Windows FastAPI JWT signature verification.
4. **User Logout (`/api/auth/logout`):** Requires Windows FastAPI session revocation.
5. **Farm & Plot Management (`/api/farms`):** Requires Windows SQLite database.
6. **Diagnosis History (`/api/history`):** Requires Windows SQLite database.
7. **AI Inference (`/api/plant/diagnose`):** Legitimate on-demand dependency on Windows AI worker.

---

## 7. Exact Blockers to Achieving True Cloud Auth

1. **Missing Frontend Wiring:**
   `frontend2/predict.html` must import and initialize `frontend2/supabase-client.js` instead of `frontend2/firebase-client.js`.
2. **Missing Vercel Environment Variables:**
   `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` must be added to Vercel Preview environment.
3. **Dormant Supabase Cloud Project:**
   The Supabase project must be in `ACTIVE` status so GoTrue Auth endpoints (`POST /auth/v1/token?grant_type=password`) can resolve and respond.
4. **Gateway Hybrid Route Handling:**
   Edge Gateway (`api/[...path].js`) needs a direct handler for `/api/auth/supabase-config` so the frontend can retrieve public connection parameters safely.
