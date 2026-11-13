# GARI AgriTech AI Lab — Authentication Deployment & Rollback Checklist

**Document ID:** GARI-CHECKLIST-AUTH-DEPLOY-2026-01  
**Target Environment:** Vercel Preview & Production  
**Branch:** `gari-2.0-redesign`  
**Git Baseline:** `2318ee75`  
**Status:** **READY FOR CONTROLLED PREVIEW**  

---

## 1. Pre-Deployment Verification Checklist

Before initiating any deployment command, confirm that all local prerequisites are satisfied:

- [x] **File Parity:** Both `api/[...path].js` and `frontend2/api/[...path].js` are byte-for-byte identical (SHA-256: `DF42964FE3C90844BC9F13CBADA1F877ED029E80F99D34F95E75B9A49ED91673`).
- [x] **Node Syntax:** Clean validation under `node -c` for all gateway and client scripts.
- [x] **Edge Authority Cleanliness:** Zero `signToken`, `verifyToken`, `edgeUserStore`, or `revokedEdgeTokens` constructs present.
- [x] **Database Safety:** Production database `database/disease_detector.db` completely untouched.
- [x] **Unit & Integration Tests:** 82 / 82 tests passing across all test suites:
  - `tests/test_auth_fail_closed_gate.js` (12/12)
  - `tests/test_auth_integration_gate.js` (12/12)
  - `tests/test_safe_auth_reproduction.js` (13/13)
  - `tests/test_phase5_8_remediation.py` (9/9)
  - `tests/test_sprint6_1_dual_gate.py` (10/10)
  - `tests/test_sprint6_2_evidence_foundation.py` (13/13)
  - `tests/test_sprint6_2_staging_migration.py` (13/13)

---

## 2. Vercel Environment Configuration Checklist

Verify in the **Vercel Project Dashboard -> Settings -> Environment Variables** that the following keys are populated:

| Variable Name | Environment | Description | Verification Status |
|---|---|---|:---:|
| `VERCEL_BACKEND_API_URL` | Preview & Production | URL of authoritative FastAPI backend (e.g. Cloudflare tunnel or Oracle VM endpoint) | [ ] Confirm |
| `VERCEL_BACKEND_TIMEOUT_MS` | Preview & Production | Upstream timeout ceiling (`15000`) | [ ] Confirm |
| `FIREBASE_API_KEY` | Preview & Production | Public Firebase Web API Key | [ ] Confirm |
| `FIREBASE_PROJECT_ID` | Preview & Production | Firebase Project ID (`gari-agritech` or similar) | [ ] Confirm |
| `FIREBASE_APP_ID` | Preview & Production | Firebase App ID | [ ] Confirm |

*Note: The deprecated `SESSION_SECRET` variable is no longer required by the Edge Gateway since the Edge no longer signs tokens.*

---

## 3. Controlled Preview Deployment Protocol

To avoid risk to live users, the deployment must be executed to a **Preview Environment** first:

### Step 3.1: Trigger Vercel Preview Deployment
```bash
# Deploy to preview URL without promoting to production
vercel --yes
```
*Record the returned Preview URL: `https://gari-team-<preview-hash>.vercel.app`*

### Step 3.2: Live Browser Smoke Test (Incident Resolution Verification)

Open the Preview URL in a clean browser window (or Incognito mode) and verify:

1. **Registration Form Incident Verification (`/register`):**
   - Fill in: Họ và tên (`huy`), Email (`huy175209@gmail.com`), Mật khẩu, Số điện thoại (`0356162193`), Tỉnh/thành (`Lâm Đồng`).
   - Click **Tạo tài khoản nông trại**.
   - **Verification:**
     - If backend is offline: The button must **NOT** hang at *"Đang khởi tạo tài khoản..."*. Within 6 seconds, an error alert must appear: *"Máy chủ xác thực hiện chưa sẵn sàng hoặc đang bảo trì."*, and the button must return to **Tạo tài khoản nông trại** (clickable).
     - If backend is online: User is registered in SQLite, receives session, and redirects to dashboard.
2. **Duplicate Registration Check:**
   - Attempt to register with the same email again.
   - **Verification:** Alert displays: *"Địa chỉ email này đã được đăng ký tài khoản."* Button immediately unblocks.
3. **Login & Session Restoration (`/login`):**
   - Log in with valid credentials -> successfully redirects to `/frontend2/index.html`.
   - Reload page -> Session persists via `checkCurrentSession()`.
4. **Scoped Logout Check:**
   - Click **Đăng xuất**.
   - **Verification:** Only `gari_*` keys removed from `localStorage`. Unrelated storage keys preserved. Token revoked on server.

---

## 4. Production Promotion Protocol

Once Preview Smoke Testing is 100% verified:

### Step 4.1: Promote to Production
```bash
# Promote the verified preview deployment to production domain
vercel --prod
```

### Step 4.2: Post-Cutover Sanity Verification (5 Minutes)
- Verify `https://gari.vn/api/health` returns HTTP 200 with service status.
- Verify `https://gari.vn/api/auth/firebase-config` returns HTTP 200 with public config.
- Verify registration, login, and logout on production domain.

---

## 5. Emergency Rollback Plan

If any critical anomaly occurs during or immediately after production promotion:

### Step 5.1: Instant Platform Rollback (Vercel CLI)
```bash
# Instant rollback to the previous deployment alias
vercel rollback
```
Or via **Vercel Dashboard -> Deployments -> Previous Deployment -> Instant Rollback**.

### Step 5.2: Verification of Rollback
- Confirm traffic returns to previous deployment.
- Check error rates in Vercel Analytics / Monitoring.
- Report incident telemetry to engineering team.

