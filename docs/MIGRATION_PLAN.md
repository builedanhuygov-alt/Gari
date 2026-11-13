# GARI 2.0 — Zero-Downtime Migration Plan

**Goal**: Transform the existing GARI AI Lab codebase into an enterprise-ready, beautifully designed agricultural AI platform with Firebase identity, dedicated Host-controlled infrastructure, and airtight tenant isolation.

---

## 1. Migration Phase Overview

| Phase | Title | Scope | Status |
|---|---|---|---|
| **Phase 0** | Codebase Audit & Safety Snapshot | Safety backup, Git branching, architecture mapping | **COMPLETED** |
| **Phase 1** | Data Quarantine & Selector Redesign | `is_test` column, database migration, searchable context picker | **COMPLETED** |
| **Phase 2** | Design System & Anti-Slop Visual Uplift | `design-taste-frontend`, `DESIGN.md`, `PRODUCT.md` | **IN PROGRESS** |
| **Phase 3** | Firebase Identity Integration | Firebase Auth SDK, dual JWT verification, custom claims | **UPCOMING** |
| **Phase 4** | Host Infrastructure Hardening | Host admin console isolation, model ops, moderation pipeline | **UPCOMING** |
| **Phase 5** | End-to-End Verification & Runbook | Playwright browser suite (1440px / 390px), load testing | **UPCOMING** |

---

## 2. Phase 0: Safety & Audit (Completed)

1. **Git Version Control Safety**:
   - Created baseline commit on `master`.
   - Created dedicated feature branch `gari-2.0-redesign`.
2. **Database Backup**:
   - `database/backups/disease_detector_pre_gari2_redesign.db`
   - `database/backups/disease_detector_pre_isolation_20261103_194910.db`
3. **Architecture Mapping**:
   - Completed comprehensive audit in `docs/ARCHITECTURE_AUDIT.md`.
   - Specified target architecture in `docs/SYSTEM_ARCHITECTURE.md`.

---

## 3. Phase 1: Data Quarantine & Selector Redesign (Completed)

### 3.1 Deliverables
1. **Database Schema Enhancements (`database/migrations_farm_org_isolation.py`)**:
   - Added `is_test INTEGER DEFAULT 0` to `organizations` and `farms`.
   - Quarantined 28 legacy test organizations and 11 test farms.
   - Preserved genuine farmer and cooperative accounts (`Hợp Tác Xã Nông Nghiệp Ba Vì`, farms 1-5).
2. **Unified Context Endpoint (`GET /api/user/diagnosis-contexts`)**:
   - Returns `{ personal, farms, organizations }` scoped strictly to the authenticated UID.
   - Formats quotas cleanly (e.g., "Còn 782 lượt", "VIP Không giới hạn").
3. **Frontend Selector Redesign (`frontend2/predict.html`)**:
   - Replaced duplicate native `<select>` dropdowns with a searchable floating picker.
   - Real-time search filtering by name, province, crop, or role.
   - Preserved hidden input bindings for 100% backward compatibility with `/api/plant/diagnose`.
4. **Automated Verification**:
   - 6 unit & integration tests in `tests/test_farm_org_selector.py` (100% pass).
   - 5-step Playwright browser verification in `tests/verify_selector_browser.py`:
     - Desktop (1440x900) verified with screenshot.
     - Mobile (390x844) verified with screenshot.
     - Empty state verified with screenshot.

---

## 4. Phase 2: Design System & Visual Uplift (In Progress)

### 4.1 Objectives
- Implement aesthetic guidelines from `design-taste-frontend` and Awesome Design MD.
- Create `DESIGN.md` establishing color harmony, typography tokens, elevation scales, and spacing rhythms.
- Create `PRODUCT.md` establishing user personas, core jobs-to-be-done, and UI constraints.
- Replace generic template styling with authentic Vietnamese agricultural warmth:
  - Dominant foliage deep green (`#166534`, `#14532D`)
  - Accent emerald growth (`#10b981`)
  - Warm earth ochre (`#d97706`) for notifications and harvesting states
  - Crisp high-contrast typography (`Be Vietnam Pro`, `Inter`)
  - Touch-friendly tap targets (minimum 44x44px for field mobile use).

---

## 5. Phase 3: Firebase Identity Integration (Upcoming)

### 5.1 Objectives
- Provision Firebase project configuration (`firebase.json`, client credentials).
- Install and configure Firebase Admin SDK in `api_server.py`.
- Implement dual-token middleware:
  - If `Authorization: Bearer <token>` is a Firebase ID Token, verify via `firebase_admin.auth.verify_id_token`.
  - Fall back seamlessly to local GARI session tokens for offline/local development.
- Map Firebase UIDs to internal SQLite user accounts or synchronize user profiles.
- Set custom claims on Firebase users: `{ gari_account_type: "farmer", gari_is_host_admin: false }`.

---

## 6. Phase 4: Dedicated Host Infrastructure (Upcoming)

### 6.1 Objectives
- Isolate `/frontend2/host.html` from public user navigation.
- Implement server-side telemetry gathering (CPU, RAM, Disk, active sessions).
- Provide model hot-reloading and health status monitoring for the 51 local models.
- Harden the moderation review queue with two-factor human approval for account suspensions.

---

## 7. Phase 5: Verification & Production Runbook (Upcoming)

- Comprehensive test execution across all test suites.
- End-to-end visual regression comparisons.
- Final production deployment readiness checklist in `docs/DEPLOYMENT_CHECKLIST.md`.
