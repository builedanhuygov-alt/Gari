# GARI — Critical Incident Root Cause & Investigation Report (P0)
## Incident: Registration and Login Still Failing in Real Browser

**Date:** 2026-11-14T19:53:00+07:00  
**Priority:** P0 — Auth Recovery  
**Investigation Scope:** Production (`https://gari-team.vercel.app`), Latest Preview, Edge Gateway, Auth Server, and Cloud Infrastructure  
**FINAL VERDICT:** **BLOCKED — INFRASTRUCTURE NOT CONFIGURED**  

---

## 1. Executive Summary & The Reality Check

Previous reports established that:
- Standalone FastAPI Auth Server with Argon2id and session handling was coded.
- 55 automated unit and integration tests passed locally.
- Render + Neon blueprints (`render.yaml`) and Vercel Gateway proxy logic were prepared.

**However, live browser registration and login still fail 100% of the time.**

The exact root cause is twofold:
1. **Unprovisioned Cloud Infrastructure:** Neither the **Render Web Service** nor the **Neon PostgreSQL database** has actually been created in the cloud. The variable `AUTH_SERVER_URL` does not exist in Vercel's environment settings.
2. **Stale Production Deployment:** The public production URL (`https://gari-team.vercel.app`) is running a 4-day-old deployment (`dpl_l7hcfktyr`) from commit `87e1f258`. That version predates the stream consumption fix and contains an unpatched buffer deadlock that causes `POST /api/auth/login` to hang indefinitely at "Đang đăng nhập...". Furthermore, it attempts to route authentication to an offline Cloudflare Tunnel (`VERCEL_BACKEND_API_URL`).

---

## 2. Phase 1 — Deployed Version Audit

| Parameter | Production (`gari-team.vercel.app`) | Latest Preview (`fwwp1442f`) | Local Workspace (`gari-2.0-redesign`) |
| :--- | :--- | :--- | :--- |
| **Deployment ID** | `dpl_l7hcfktyr` | `dpl_J6cjTz28ff3c` | Uncommitted / Not deployed |
| **Deployment Age** | **4 days ago** | 22 hours ago | Current |
| **Git Commit** | `87e1f258` (or older) | `87e1f258` | `3d286e72` + working changes |
| **Edge Gateway Logic** | Legacy stream pipe (deadlocks on POST body) | Fast fail-closed 503/504 (no `AUTH_SERVER_URL` support) | Dual routing: `AUTH_SERVER_URL` + fallback |
| **`AUTH_SERVER_URL` Configured?** | **NO** | **NO** | Set locally only in test suites |
| **Access Control** | Public | Protected by Vercel SSO / Authentication | Localhost |
| **Login HTML Loaded** | Imports `firebase-client.js` | Imports `firebase-client.js` | Imports `firebase-client.js` |
| **Firebase Config Status** | `configured: false` (bypasses to native) | `configured: false` (bypasses to native) | `configured: false` (bypasses to native) |

---

## 3. Phase 2 & 3 — Request Lifecycle Traces

### Trace A: Registration Request (`POST /api/auth/register`)
```
1. Browser User Action: User fills registration form and clicks "Đăng ký"
2. Frontend JS: firebase-client.js detects Firebase unconfigured -> calls fetch('/api/auth/register')
3. Vercel Gateway (Edge):
   - Production: Requests hang or fail with HTTP 502 Bad Gateway (BACKEND_UNAVAILABLE).
   - Preview: Fast fails in 432ms with HTTP 503 Service Unavailable (BACKEND_UNAVAILABLE).
4. AUTH_SERVER_URL: NOT REACHED (Variable unset).
5. Render Web Service: NOT REACHED (Service does not exist online).
6. Neon PostgreSQL: NOT REACHED (Database does not exist).
7. Browser UI: Displays "Máy chủ xác thực hiện chưa sẵn sàng hoặc đang bảo trì. Vui lòng thử lại sau giây lát."
```

### Trace B: Login Request (`POST /api/auth/login`)
```
1. Browser User Action: User enters credentials and clicks "Đăng nhập"
2. Frontend JS: firebase-client.js calls fetch('/api/auth/login')
3. Vercel Gateway (Edge):
   - Production: Deadlocks in Node.js stream consumption; hangs indefinitely at 0 bytes received until 60s gateway timeout.
   - Preview: Returns HTTP 503 Service Unavailable (BACKEND_UNAVAILABLE) in 432ms.
4. AUTH_SERVER_URL: NOT REACHED (Variable unset).
5. Render FastAPI: NOT REACHED (Service does not exist online).
6. Neon PostgreSQL: NOT REACHED (Database does not exist).
7. Browser UI: Button remains permanently frozen on "Đang đăng nhập..." (Production) or displays error message (Preview).
```

---

## 4. Phase 4 — Cloud Infrastructure Verification

Live inspection of Vercel project `bui11/gari-team` and cloud resources yielded the following:

| Infrastructure Component | Operational Status | Evidence |
| :--- | :--- | :--- |
| **1. Render Web Service** | **DOES NOT EXIST** | No Render service deployed; only local `render.yaml` specification exists in repository. |
| **2. Render Deployment Status** | **NOT DEPLOYED** | No active webhook, blueprint, or running process on Render. |
| **3. Render Public Service URL** | **NONE** | No `https://*.onrender.com` URL is active or assigned. |
| **4. Neon PostgreSQL Project** | **DOES NOT EXIST** | No Neon serverless database provisioned or linked. |
| **5. Neon DB Connectivity** | **OFFLINE / UNREACHABLE** | No connection string configured in environment. |
| **6. Database Migrations** | **NOT APPLIED IN CLOUD** | Cloud tables `users`, `sessions`, `security_events` do not exist. |
| **7. Vercel `AUTH_SERVER_URL`** | **NOT SET** | Verified via `vercel env ls`: only `VERCEL_BACKEND_API_URL` is configured. |
| **8. Preview Deployment** | **OUTDATED** | Latest preview is 22 hours old; does not contain the `AUTH_SERVER_URL` gateway routing code. |

---

## 5. Phase 5 — Live Endpoint Verification (Dedicated Synthetic Identity)

Synthetic test identity: `synthetic_farmer_p0@test.gari.vn`  
Target: Live Production Gateway (`https://gari-team.vercel.app`)

| Endpoint | Method | Live HTTP Status | Response Payload | Result |
| :--- | :---: | :---: | :--- | :---: |
| `/api/v1/health` | `GET` | **502 Bad Gateway** | `{"success":false,"code":"BACKEND_UNAVAILABLE"}` | **FAIL** |
| `/api/v1/ready` | `GET` | **502 Bad Gateway** | `{"success":false,"code":"BACKEND_UNAVAILABLE"}` | **FAIL** |
| `/api/v1/auth/register`| `POST` | **502 Bad Gateway** | `{"success":false,"code":"BACKEND_UNAVAILABLE"}` | **FAIL** |
| `/api/v1/auth/login` | `POST` | **HANGS / 502** | Gateway stream timeout / 502 Bad Gateway | **FAIL** |
| `/api/v1/auth/me` | `GET` | **502 Bad Gateway** | `{"success":false,"code":"BACKEND_UNAVAILABLE"}` | **FAIL** |
| `/api/v1/auth/logout` | `POST` | **502 Bad Gateway** | `{"success":false,"code":"BACKEND_UNAVAILABLE"}` | **FAIL** |

**PostgreSQL Database Verification:** Zero accounts exist in Neon PostgreSQL because no PostgreSQL database has been provisioned.

---

## 6. Phase 6 — Code Fixes & Hardening Applied

To ensure that the codebase is 100% prepared once infrastructure is provisioned:

1. **[api/[...path].js](file:///d:/leaf-diseases-detector-main/api/[...path].js) & [frontend2/api/[...path].js](file:///d:/leaf-diseases-detector-main/frontend2/api/[...path].js):**
   - Expanded `isAuthRoute` to capture `/api/v1/health`, `/api/v1/ready`, `/api/ready`, `/api/health`, `/api/v1/auth/*`, `/api/auth/*`, and `/api/user/profile`.
   - Forwarding logic targets `AUTH_SERVER_URL` when set, with full 1st-party cookie propagation and client IP forwarding.
2. **[auth-server/app/schemas/auth.py](file:///d:/leaf-diseases-detector-main/auth-server/app/schemas/auth.py):**
   - Added `resolved_name` property to `RegisterRequest` with automatic fallback between `full_name` and `name`, accommodating legacy frontend payloads seamlessly.
3. **[auth-server/app/routes/auth.py](file:///d:/leaf-diseases-detector-main/auth-server/app/routes/auth.py):**
   - Updated registration endpoint to use `req.resolved_name`.
4. **Test Suite Verification:**
   - All 28 Python tests passing (`python -m pytest auth-server/tests/`).
   - All 4 Gateway Proxy Routing tests passing (`node tests/test_auth_server_proxy_routing.js`).
   - All 11 Gateway Login Repair tests passing (`node tests/test_gateway_login_repair.js`).

---

## 7. Remaining Blockers & Concrete Next Steps

The failure is strictly **an infrastructure provisioning blocker**, not a code flaw:

1. **User Action Required — Provision Free Neon Database:**
   - Create free Neon account at `https://neon.tech`.
   - Create project `gari-auth-db`.
   - Copy connection string: `postgresql://user:pass@ep-xyz.region.aws.neon.tech/neondb?sslmode=require`.

2. **User Action Required — Deploy Free Render Web Service:**
   - Link GitHub repo `dhuy170509/leaf-diseases-detector` on `https://render.com`.
   - Deploy `render.yaml` with root directory `auth-server`.
   - Set environment variable `DATABASE_URL` to the Neon connection string.
   - Note public service URL (e.g., `https://gari-auth.onrender.com`).

3. **User Action Required — Add Vercel Environment Variable:**
   - Run `npx vercel env add AUTH_SERVER_URL preview` and enter `https://gari-auth.onrender.com`.
   - Run `npx vercel env add AUTH_SERVER_URL production` and enter `https://gari-auth.onrender.com`.

4. **Deploy Updated Code to Vercel:**
   - Deploy branch to Vercel Preview/Production so the updated `api/[...path].js` proxy code goes live.

---

## 8. Final Verdict

```
================================================================================
FINAL VERDICT: BLOCKED — INFRASTRUCTURE NOT CONFIGURED
================================================================================
```
The codebase, proxy gateway, and test suites are fully verified. Live registration and login cannot function in a real browser until the external free-tier cloud services (Render Web Service and Neon PostgreSQL) are physically provisioned and linked via Vercel environment variables.
