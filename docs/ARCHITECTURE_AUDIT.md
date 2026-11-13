# GARI AgriTech Platform — Comprehensive Architecture Audit

**Author**: Principal Software Architect & Senior Full-Stack Engineer  
**Date**: November 2026 (GARI 2.0 Initiative)  
**System Version**: 2.0.0-rc1  
**Target Environment**: Production Agricultural AI Platform (Vietnam)

---

## 1. Executive Summary

GARI (Gari AI Lab / Gari AgriTech) is an AI-powered agricultural diagnostics and farm-management platform designed for Vietnamese farmers, cooperatives, crop protection specialists, and agribusiness enterprises. It combines 51 local machine-learning models for leaf disease classification with multi-tenant cooperative management, automated and manual moderation, multi-gateway subscription billing (VietQR/SePay, PayOS), and an isolated Host Server Admin Console.

This audit documents the state of the existing codebase prior to and following the GARI 2.0 platform evolution, identifying architectural strengths, legacy technical debt, test fixture isolation gaps, and migration trajectories toward a modern Firebase-backed, Host-controlled infrastructure.

---

## 2. Codebase Topology & Technology Stack

```
leaf-diseases-detector-main/
├── api_server.py                 # FastAPI backend (core REST API & middleware)
├── gari_auth.py                  # Authentication, sessions, single active account type
├── gari_b2b.py                   # Multi-tenant B2B engine, quotas, organizations
├── gari_database.py              # SQLite data access layer & connection pooling
├── gari_moderation.py            # Automated violation detection & human review cases
├── gari_payment.py               # Payment gateways (VietQR, SePay, PayOS, Vouchers)
├── model_services.py             # PyTorch & torchvision model loading and inference
├── frontend/                     # Modern React 19 + Vite + Tailwind frontend (Port 5173)
│   ├── src/components/VisionView.tsx # React AI diagnosis workbench
│   └── src/App.tsx               # Client state, routing, and onboarding
├── frontend2/                    # Multi-page SaaS portal (Port 8000 static mount)
│   ├── predict.html              # Core plant health diagnosis workbench
│   ├── host.html                 # Dedicated Host Server Admin Console
│   ├── host-login.html           # Dedicated Host login & step-up authentication
│   ├── pricing.html              # Subscription tiers & Bank QR modal
│   ├── organization.html         # Cooperative & enterprise team portal
│   └── app.js                    # Vanilla JS client SaaS shell & auth guard
├── models/                       # 51 deep-learning model checkpoints (CPU/GPU)
├── database/
│   ├── disease_detector.db       # Primary SQLite database (WAL mode)
│   ├── backups/                  # Automated pre-migration backups
│   ├── migrations_account_types.py
│   └── migrations_farm_org_isolation.py
├── tests/                        # 37+ automated unit & integration tests
│   ├── test_farm_org_selector.py
│   ├── test_moderation_system.py
│   ├── test_host_admin_console.py
│   ├── test_account_type_selection.py
│   └── verify_selector_browser.py # Playwright automated E2E browser tests
└── docs/                         # Technical specifications and runbooks
```

### 2.1 Technology Matrix

| Layer | Implementation | Version / Standard |
|---|---|---|
| **Backend Runtime** | Python 3.13.5 | Uvicorn / Starlette / FastAPI |
| **Relational Storage** | SQLite with WAL mode & Foreign Keys | SQLite 3.45+ |
| **Primary Frontend** | HTML5 / CSS3 / ES Modules SaaS Portal | `/frontend2/*` |
| **Vite SPA Frontend** | React 19 / TypeScript / Tailwind CSS | `/frontend/*` |
| **Inference Engine** | PyTorch / torchvision | CPU default (optional CUDA) |
| **Authentication** | SHA-256 PBKDF2 / Bearer Tokens / Cookies | `gari_auth.py` |
| **Multi-Tenancy** | Scoped RBAC (Owner, Admin, Member, Viewer) | `gari_b2b.py` |
| **Payments** | VietQR Pro, SePay Webhooks, PayOS SDK | `gari_payment.py` |
| **E2E Verification** | Playwright Chromium | 1.64.1 |

---

## 3. Data Architecture & Schema Audit

### 3.1 Core Entity Relational Model

1. **`users`**:
   - Primary key: `id INTEGER PRIMARY KEY AUTOINCREMENT`
   - Attributes: `email`, `password_hash`, `full_name`, `account_type`, `is_vip`, `vip_expires_at`, `is_host_admin`, `is_active`, `created_at`.
   - **GARI 2.0 Invariant**: `account_type` is strictly single-valued: `'farmer'`, `'cooperative'`, `'expert'`, or `'enterprise'`.

2. **`user_account_type_audit`**:
   - Audit trail capturing every account type change with `user_id`, `previous_type`, `new_type`, `changed_by_user_id`, `reason`, `created_at`.

3. **`organizations` & `organization_members`**:
   - Organizations support multi-tenant isolation, custom branding, domain whitelisting, and centralized billing quotas.
   - `is_test INTEGER DEFAULT 0`: Flags simulated fixtures to prevent test contamination in production UI.
   - Roles: `owner` (Chủ nhiệm/Đại diện), `admin` (Quản trị viên), `member` (Thành viên nông dân), `viewer` (Giám sát viên).

4. **`farms` & `farm_plots`**:
   - Farms link directly to an individual user (`user_id`) or an organization (`organization_id`).
   - `is_test INTEGER DEFAULT 0`: Quarantines automated test fixtures.
   - Plots track crop types, acreage, planting dates, and soil/irrigation methods.

5. **`moderation_cases` & `moderation_audit_logs`**:
   - Captures automated policy violation alerts across file uploads, diagnostic notes, spam registrations, and voucher abuse.
   - Review statuses: `pending`, `reviewed`, `dismissed`, `action_taken`.
   - Administrative decisions require explicit Host operator human approval before account suspension or permanent banning.

---

## 4. Root-Cause Analysis: Farm/Org Selector Clutter

### 4.1 Prior Symptom
The diagnosis workbench at `/frontend2/predict.html` displayed an overcrowded native dropdown populated with duplicate entries:
- "Test Concurrent HTX"
- "Hợp Tác Xã Cô Đơn <timestamp>"
- Multiple test farms with confusing quota tags.

### 4.2 Architectural Root Cause
1. **Direct Production Database Execution**:
   Development scratch scripts (`scratch/test_b2b_platform.py` and `scratch/test_sprint1_core.py`) ran integration tests directly against `database/disease_detector.db` using the primary administrative account (`danhuynh@gari.vn`, User ID 1).
2. **Missing Test Flagging Column**:
   The `organizations` and `farms` tables lacked an `is_test` column, meaning test creations became indistinguishable from genuine user entities in database queries.
3. **Unscoped Frontend Queries**:
   The frontend previously loaded all organization memberships returned by `/api/b2b/organizations` without differentiating between active production entities and ephemeral test fixtures.

### 4.3 Implemented Fix
1. **Migration (`database/migrations_farm_org_isolation.py`)**:
   - Added `is_test INTEGER DEFAULT 0` and indexes `idx_organizations_is_test` and `idx_farms_is_test`.
   - Quarantined 28 test organizations and 11 test farms by updating `is_test = 1`.
   - Preserved genuine records: 2 legitimate organizations (`Hợp Tác Xã Nông Nghiệp Ba Vì`, `Trang Trại Rau Sạch Nông Dân 7`) and 7 legitimate farms.
2. **Backend Query Scoping**:
   - Updated `gari_b2b.get_user_organizations(..., include_test=False)`.
   - Updated `gari_database.list_farms(..., include_test=False)`.
   - Created unified endpoint `GET /api/user/diagnosis-contexts` returning `{ personal, farms, organizations }` with membership role formatting and remaining quota calculations.
3. **Frontend UI Redesign**:
   - Replaced raw dual native select elements with a unified, searchable modal dropdown.
   - Segmented options into:
     - 🌾 **Cá nhân (Khám tự do)**: Personal quota & standard tier.
     - 🏡 **Nông trại của tôi**: Scoped farms with crop types and hectare sizes.
     - 🏢 **Hợp tác xã & Doanh nghiệp**: Accessible organizations with membership role pills and remaining quota indicators.
   - Added dynamic plot loader that surfaces fields when a farm with plots is selected.

---

## 5. Security & Tenant Isolation Analysis

| Threat Model Vector | Mitigation Strategy | Verification Status |
|---|---|---|
| **Client-Side UID Spoofing** | UIDs derived strictly from server-verified session token (`get_current_user`). Frontend inputs ignored. | Verified (`tests/test_farm_org_selector.py`) |
| **Cross-Tenant Farm Diagnosis** | Diagnosis endpoint verifies `farm.user_id == current_user.id` or matching org membership. Returns HTTP 403 on violation. | Verified (`test_05`) |
| **Cross-Tenant Org Diagnosis** | Diagnosis endpoint verifies `gari_b2b.get_member_role(org_id, user_id)`. Returns HTTP 403 on non-member. | Verified (`test_06`) |
| **Model Inversion / Result Tampering** | Prohibits client-submitted AI prediction labels (`predicted_disease`, `confidence`). | Verified (`test_ai_plant_doctor.py`) |
| **Upload File Tampering** | Scans image headers with PIL verification and automated file format moderation filters. | Verified (`test_moderation_system.py`) |
| **Host Console Access** | Restricts all `/api/host/*` endpoints to authenticated users with `is_host_admin = 1`. | Verified (`test_host_admin_console.py`) |

---

## 6. GARI 2.0 Target Recommendations

1. **Firebase Authentication Integration**:
   - Dual-mode authentication: support Firebase JWT tokens in the `Authorization: Bearer <firebase_jwt>` header alongside existing session tokens.
   - Utilize Firebase Custom Claims to store `gari_account_type` and `gari_is_host_admin`.
2. **Dedicated Host Infrastructure**:
   - Keep host operations completely decoupled from user-facing agricultural dashboards.
   - Expose host endpoints on a segregated network interface or admin subpath with mandatory step-up credentials.
3. **Visual Design Polish**:
   - Apply `design-taste-frontend` and Awesome Design MD guidelines: calm earthy green palette (`#166534`, `#10b981`), clear typographic hierarchy (Be Vietnam Pro / Inter), and responsive mobile drawer navigation.
