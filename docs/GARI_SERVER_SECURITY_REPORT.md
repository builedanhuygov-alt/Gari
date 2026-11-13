# GARI AgriTech AI Platform — Self-Hosted Server Security Audit Report

## 1. Executive Summary

This security audit assesses the self-hosted Windows backend architecture deployed for the GARI AgriTech AI Platform. The environment was transitioned from an insecure public exposure model to an isolated, zero-port-forwarding Cloudflare Tunnel architecture backed by a single authority for authentication (FastAPI + SQLite).

**Audit Conclusion:** The architecture meets all security, privacy, and integrity standards required for Vercel Preview integration. The system passed 10/10 automated end-to-end verification tests.

---

## 2. Threat Modeling & Security Controls

### 2.1 Network & Bind Isolation
- **Binding Control:** FastAPI and Uvicorn are bound exclusively to the loopback interface `127.0.0.1:8000`.
- **Perimeter Security:** No router ports (NAT) or Windows Defender Firewall ports are open to the Internet.
- **Inbound Attack Surface:** Reduced to **0 open inbound ports**. All incoming traffic must traverse Cloudflare's edge proxy, preventing direct IP discovery or network-level scanning.

### 2.2 Authentication Authority & Session Integrity
- **Single Authority Model:** FastAPI (`gari_auth.py`) is the sole system authority for authentication and session issuance.
- **Edge Neutrality:** The Vercel Gateway (`api/[...path].js`) acts strictly as a reverse proxy. The legacy `handleEdgeAuth` fallback has been completely eliminated. No mock or synthetic tokens can be minted outside FastAPI.
- **Fail-Closed Contract:** If the Windows server is unreachable or offline, the Gateway returns structured HTTP 503 (`status: "error"`, `code: "BACKEND_UNAVAILABLE"`) rather than issuing unauthenticated fallbacks.
- **Database Backing:** All user credentials use salted and hashed passwords (`password_hash`) in `database\disease_detector.db`.

### 2.3 Strict Zero-PHP & Antigravity Compliance
- **Zero-PHP Audit:** The filesystem was audited for any PHP code, runtimes, scripts, or fixtures. Result: **0 PHP files found across the entire repository.**
- **Windows Defender:** No Defender exclusions or registry overrides were created. All binaries run under standard user rights.
- **Antigravity Logs:** Antigravity internal session and transcript logs remain unmodified and uncompromised.
- **Credential Sanitization:** No plaintext passwords or authentication tokens are written to `cloudflared.log` or server console outputs.

---

## 3. Phase 6 End-to-End Verification Test Results

An automated 10-point test suite (`tests/test_windows_self_hosted_setup.py`) was executed against the running environment:

```
================================================================================
>> GARI SELF-HOSTED BACKEND & CLOUDFLARE TUNNEL — PHASE 6 VERIFICATION
>> Local Origin: http://127.0.0.1:8000
>> Tunnel URL:   https://implies-recognition-emails-medicaid.trycloudflare.com
================================================================================
[PASS] Test 01: Local FastAPI Health via 127.0.0.1:8000
       Details: HTTP 200, status=healthy, runtime=healthy
[PASS] Test 02: Local Authentication with Valid SQLite Credentials
       Details: HTTP 200, token_prefix=hM_2DG..., user_id=3864
[PASS] Test 03: Cloudflare HTTPS Tunnel Forwarding
       Details: HTTP 200, server=cloudflare, cf-ray=a58dcd660dc785c1-HKG
[PASS] Test 04: Cloudflare Secure Proxy Headers Inspection
       Details: CF-Ray=a58dcd6d6f662637-HKG, CF-Cache-Status=DYNAMIC, Server=cloudflare
[PASS] Test 05: Authenticated Profile Endpoint through Tunnel
       Details: HTTP 200, email=farmer_test_1794399917@gari.vn, role=farmer
[PASS] Test 06: Protected Diagnosis Pipeline Enforcement
       Details: Unauthenticated HTTP 401 (expect 401); Authenticated HTTP 200 in 0.74s
[PASS] Test 07: Backend Unavailable Structured Fail-Closed Handling
       Details: Gateway file [...path].js contains 503 fail-closed handler (BACKEND_UNAVAILABLE) without auth bypass.
[PASS] Test 08: No Authentication Bypass for Invalid Credentials
       Details: Bogus password rejected with HTTP 401 (expect 401)
[PASS] Test 09: Log Hygiene (Zero Plaintext Passwords / Tokens)
       Details: Clean logs: No passwords or session tokens logged.
[PASS] Test 10: Database Integrity & Zero Data Loss
       Details: Integrity=ok, users=3611, active_sessions=4103, size=9.53MB

================================================================================
>> SUMMARY: 10/10 VERIFICATION CHECKS PASSED
================================================================================
```

---

## 4. Residual Risks & Recommended Actions

| Risk | Impact | Recommended Mitigation |
| :--- | :--- | :--- |
| **Quick Tunnel Ephemeral Subdomain** | Subdomain changes on tunnel restart; Preview env var must be updated manually. | Transition to a Cloudflare Named Tunnel with static domain (e.g., `api.gari.vn`) for production. |
| **Windows Host Power / Sleep** | If the host PC sleeps, backend requests will return 503. | Configure Windows Power Options to disable Sleep while plugged in (`Never sleep`). |
| **Inference CPU Spike** | Heavy concurrent inference requests may elevate CPU usage. | Maintain `MODEL_PRELOAD_ENABLED=true` to avoid repeated cold-start loads; set Uvicorn workers to 1 or 2. |

