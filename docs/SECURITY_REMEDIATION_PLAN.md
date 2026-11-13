# GARI AGRITECH AI LAB — SECURITY REMEDIATION PLAN
## Structured Engineering Roadmaps, Pre-Requisite Backups & Rollback Procedures

**Author:** DevSecOps & Security Engineering Team  
**Effective Date:** 2026-11-10  
**Target Release:** Production Release Gate 1.0  
**Rollback Policy:** Zero Database Destructive Operations / Automated Git Revert

---

## 1. Remediation Strategy & Phasing

```
[Phase 1: Immediate Blockers (Sprint 1)]
  ├─ SEC-01: Lock down /api/diagnoses & /api/diagnoses/{id}
  ├─ SEC-02: Eliminate 'if current_user else 1' across 19 endpoints
  ├─ SEC-03: Enforce tenant membership check in /api/farms?org_id=X
  └─ SEC-04: Restrict expert case messaging to assigned experts
         │
         ▼
[Phase 2: Client & Privilege Hardening (Sprint 2)]
  ├─ SEC-05: Implement escapeHtml() & sanitize innerHTML in frontend2/
  └─ SEC-06: Remove hardcoded admin email list in gari_auth.py
         │
         ▼
[Phase 3: Defense-in-Depth (Sprint 3)]
  └─ SEC-07: Add upload size & MIME checks to /api/field/upload
```

---

## 2. Step-by-Step Implementation Runbook

### Step 1.1: Pre-Remediation Safety Checkpoint
Before modifying any source files:
1. Ensure the active database is backed up using the verified online backup tool:
   ```powershell
   pwsh .\scripts\backup_database.ps1
   ```
2. Verify git working directory state:
   ```powershell
   git status
   ```

### Step 1.2: Remediating SEC-01 (Diagnoses Data Isolation)
- **Target File:** `api_server.py`
- **Action:**
  1. Change line 1897:
     ```python
     # Replace:
     current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
     # With:
     current_user: Dict[str, Any] = Depends(get_current_user)
     ```
  2. Change line 1937 in `get_diagnosis_detail`:
     ```python
     # Replace:
     current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
     # With:
     current_user: Dict[str, Any] = Depends(get_current_user)
     ```
  3. In `gari_database.py:1707`, add guard: if `user_id is None and organization_id is None`, return empty list `[]` instead of returning all rows.
- **Verification:** Run `.\.venv\Scripts\python.exe -m unittest tests/test_phase5_7_security_audit.py`.

### Step 1.3: Remediating SEC-02 (Eliminate Default User 1 Fallback)
- **Target File:** `api_server.py`
- **Action:**
  Across lines 1864, 1872, 1880, 2286, 2325, 2351, 2377, 2403, 2416, 2432, 2451, 2470, 2509, 2519, 2537, 2563:
  1. Change `Depends(get_current_user_optional)` to `Depends(get_current_user)`.
  2. Remove `user_id = current_user["id"] if current_user else 1` and replace with `user_id = current_user["id"]`.
- **Impact on Frontend:** Unauthenticated users accessing `/frontend2/farms.html` or `/frontend2/index.html` will receive HTTP 401 and be redirected smoothly to `login.html?redirect=...`.

### Step 1.4: Remediating SEC-03 (Cross-Organization Farm Enumeration)
- **Target File:** `api_server.py`
- **Action:**
  In `get_farms` (`api_server.py:1130`):
  ```python
  if org_id is not None:
      if not gari_b2b.get_member_role(org_id, current_user["id"]) and not current_user.get("is_admin", False):
          raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không thuộc tổ chức này.")
  ```

### Step 1.5: Remediating SEC-04 (Expert Consultation Scoping)
- **Target File:** `api_server.py`
- **Action:**
  In `get_case_messages_api` (line 7707) and `post_case_message_api` (line 7729):
  ```python
  is_assigned_expert = (
      case.get("assigned_expert_id") == current_user["id"]
      or case.get("expert_user_id") == current_user["id"]
  )
  if not (is_owner or is_assigned_expert or is_host):
      raise HTTPException(
          status_code=status.HTTP_403_FORBIDDEN,
          detail="Bạn không có quyền xem hoặc gửi tin nhắn trong ca bệnh này."
      )
  ```

### Step 2.1: Remediating SEC-05 (Stored XSS Sanitization)
- **Target Files:** `frontend2/app.js` and `frontend2/*.html`
- **Action:**
  1. Add standard `escapeHtml(str)` helper to `frontend2/app.js`:
     ```javascript
     window.escapeHtml = function(str) {
         if (str === null || str === undefined) return '';
         return String(str)
             .replace(/&/g, '&amp;')
             .replace(/</g, '&lt;')
             .replace(/>/g, '&gt;')
             .replace(/"/g, '&quot;')
             .replace(/'/g, '&#39;');
     };
     ```
  2. In `frontend2/farms.html`, wrap `z.name`, `f.name`, `t.title` with `escapeHtml(...)`.

### Step 2.2: Remediating SEC-06 (Hardcoded Email Admin Removal)
- **Target File:** `gari_auth.py`
- **Action:**
  In line 542, replace:
  ```python
  # Old:
  is_admin = bool(user.get("is_admin")) or account_type in ("admin", "quản trị viên", "platform_admin") or email in ("danhuynh@gari.vn", "admin@gari.vn")
  # New:
  is_admin = bool(user.get("is_admin")) or bool(user.get("is_host_admin"))
  ```
  Ensure real administrators have `is_admin = 1` set in the database prior to applying.

---

## 3. Post-Remediation Verification & Rollback Procedures

### Post-Remediation Test Commands
```powershell
# 1. Run security audit test suite
.\.venv\Scripts\python.exe -m unittest tests/test_phase5_7_security_audit.py

# 2. Run zero-cost operations regression
.\.venv\Scripts\python.exe -m unittest tests/test_zero_cost_operations.py

# 3. Verify backend health
pwsh .\scripts\backend_healthcheck.ps1
```

### Emergency Rollback Procedure
If any unexpected breakage occurs during code modification:
1. Revert changes to source files via git:
   ```powershell
   git checkout api_server.py gari_auth.py gari_database.py
   ```
2. Restart backend:
   ```powershell
   pwsh .\scripts\restart_backend.ps1
   ```
3. Run healthcheck to verify recovery:
   ```powershell
   pwsh .\scripts\backend_healthcheck.ps1
   ```

