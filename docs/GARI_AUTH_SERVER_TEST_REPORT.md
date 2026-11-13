# GARI Auth Server 1.0 — Test Execution & Verification Report
**Document:** `docs/GARI_AUTH_SERVER_TEST_REPORT.md`  
**Date:** November 13, 2026  
**Status:** ALL 20 TESTS PASSED (100% PASS RATE)  
**Test Suite:** `auth-server/tests/`  
**Runner:** `pytest 9.1.1` on Python 3.14  

---

## 1. Executive Summary

A comprehensive automated test suite was executed against GARI Auth Server 1.0 to validate every functional, security, concurrency, and persistence requirement.

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.1.1, pluggy-1.6.0
collected 20 items

auth-server/tests/test_admin.py::test_admin_bootstrap_one_time PASSED    [  5%]
auth-server/tests/test_admin.py::test_admin_privilege_escalation_prevention PASSED [ 10%]
auth-server/tests/test_admin.py::test_admin_user_management PASSED       [ 15%]
auth-server/tests/test_auth.py::test_registration_success PASSED         [ 20%]
auth-server/tests/test_auth.py::test_duplicate_email PASSED              [ 25%]
auth-server/tests/test_auth.py::test_login_success PASSED                [ 30%]
auth-server/tests/test_auth.py::test_incorrect_password PASSED           [ 35%]
auth-server/tests/test_auth.py::test_session_persistence PASSED          [ 40%]
auth-server/tests/test_auth.py::test_session_expiry PASSED               [ 45%]
auth-server/tests/test_auth.py::test_logout PASSED                       [ 50%]
auth-server/tests/test_auth.py::test_session_revocation PASSED           [ 55%]
auth-server/tests/test_auth.py::test_inactive_account_login PASSED       [ 60%]
auth-server/tests/test_backup_restore.py::test_database_backup_and_recovery PASSED [ 65%]
auth-server/tests/test_backup_restore.py::test_restart_persistence PASSED [ 70%]
auth-server/tests/test_registration_limit.py::test_registration_limit_at_10 PASSED [ 75%]
auth-server/tests/test_registration_limit.py::test_concurrent_registration_race PASSED [ 80%]
auth-server/tests/test_security.py::test_csrf_protection PASSED          [ 85%]
auth-server/tests/test_security.py::test_cors_restrictions PASSED        [ 90%]
auth-server/tests/test_security.py::test_rate_limiting PASSED            [ 95%]
auth-server/tests/test_security.py::test_security_headers PASSED         [100%]

============================= 20 passed in 3.47s ==============================
```

---

## 2. Test Case Breakdown & Evidence

### 2.1. Registration Capacity & Concurrency (Section 5 Requirements)
- **`test_registration_limit_at_10`:**
  - Registered 10 consecutive accounts -> All succeeded with HTTP 201 Created.
  - Attempted 11th registration -> Immediately rejected with HTTP 403 Forbidden:
    `"Cổng đăng ký tài khoản mới hiện đã đạt giới hạn thử nghiệm (10 tài khoản). Vui lòng liên hệ quản trị viên."`
  - Verified database count remained strictly at 10.
- **`test_concurrent_registration_race`:**
  - Launched 15 concurrent registration threads simultaneously targeting the endpoint.
  - SQLite `BEGIN IMMEDIATE` write lock ensured serialized transaction boundary.
  - Exactly 10 requests succeeded (HTTP 201); exactly 5 requests were rejected (HTTP 403).
  - Zero capacity overrun occurred.

### 2.2. Authentication & Session Security (Section 4 Requirements)
- **`test_registration_success`:** Verified Argon2id password hash format (`$argon2id$v=19$m=65536...`), forced role `farmer`, and automatic HttpOnly cookie issuance.
- **`test_duplicate_email`:** Verified lowercase email normalization and 409 Conflict rejection.
- **`test_login_success`:** Authenticated valid user, confirmed HttpOnly session cookie.
- **`test_incorrect_password`:** Rejected invalid password with generic 401 error.
- **`test_session_persistence`:** Verified profile retrieval via session cookie.
- **`test_session_expiry`:** Fast-forwarded expiration timestamp to past; confirmed 401 rejection.
- **`test_logout`:** Verified database session revocation and cookie deletion.
- **`test_session_revocation`:** Revoked all other sessions for user while maintaining current device session.
- **`test_inactive_account_login`:** Deactivated user; confirmed login rejection with HTTP 403.

### 2.3. Security & Anti-Abuse (Section 4 & 6 Requirements)
- **`test_csrf_protection`:** Verified state-changing requests without `X-CSRF-Token` header return HTTP 403 `CSRF_VERIFICATION_FAILED`. Verified requests with valid CSRF token succeed.
- **`test_cors_restrictions`:** Verified approved origins receive `Access-Control-Allow-Origin`; disallowed origins are blocked.
- **`test_rate_limiting`:** 5 rapid failed login attempts succeeded in triggering HTTP 429 Too Many Requests with valid `Retry-After` header.
- **`test_security_headers`:** Confirmed `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection`, and `Referrer-Policy`.

### 2.4. Administrative Operations (Section 6 Requirements)
- **`test_admin_bootstrap_one_time`:** Bootstrap succeeded with valid secret token; subsequent bootstrap attempts permanently locked with HTTP 409 Conflict.
- **`test_admin_privilege_escalation_prevention`:** Ordinary farmer account attempts to access admin endpoints rejected with HTTP 403 Forbidden.
- **`test_admin_user_management`:** Admin successfully queried operational metrics, listed users, and toggled public registration off.

### 2.5. Persistence & Disaster Recovery (Section 3 Requirements)
- **`test_database_backup_and_recovery`:** Lock-free online point-in-time backup created a compressed `.db.gz` file with `PRAGMA integrity_check = ok`. Safely restored to target with 100% data integrity.
- **`test_restart_persistence`:** Simulated process shutdown and restarted; confirmed user records persist intact on disk.
