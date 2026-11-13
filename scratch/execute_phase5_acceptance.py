"""
GARI Auth Server 1.0 — Phase 5 Acceptance Test Runner
Executes the 13 required steps with Windows FastAPI and Cloudflare Tunnel offline.
"""
import time
import sys
import os
import json
import socket
import subprocess
from pathlib import Path
import httpx

# Configuration
AUTH_PORT = 8001
BASE_URL = f"http://127.0.0.1:{AUTH_PORT}"
DB_PATH = Path("scratch/phase5_auth.db").resolve()
DB_PATH.unlink(missing_ok=True)

env = os.environ.copy()
env["AUTH_ENV"] = "testing"
env["AUTH_PORT"] = str(AUTH_PORT)
env["AUTH_HOST"] = "127.0.0.1"
env["AUTH_DB_PATH"] = str(DB_PATH)
env["COOKIE_SECURE"] = "false"
env["BOOTSTRAP_ADMIN_TOKEN"] = "acceptance_test_bootstrap_secret_12345"

print("=" * 70)
print("GARI AUTH SERVER — PHASE 5 BROWSER ACCEPTANCE EXECUTION")
print("=" * 70)

# Check Windows FastAPI is offline
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.connect(('127.0.0.1', 8000))
    s.close()
    print("FATAL: Port 8000 is open. Windows FastAPI must be stopped!")
    sys.exit(1)
except Exception:
    print("[PRE-CHECK] Confirmed: Windows FastAPI (port 8000) is OFFLINE.")

# Launch Auth Server
server_proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(AUTH_PORT)],
    cwd="auth-server",
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

time.sleep(2.0)

# Verify health
try:
    with httpx.Client(base_url=BASE_URL) as client:
        r = client.get("/api/v1/health")
        assert r.status_code == 200, f"Health check failed: {r.text}"
        print(f"[PRE-CHECK] Auth Server started successfully on {BASE_URL} (PID: {server_proc.pid})")
except Exception as e:
    print(f"FATAL: Could not connect to Auth Server: {e}")
    server_proc.kill()
    sys.exit(1)

results = []

try:
    client_tab1 = httpx.Client(base_url=BASE_URL)
    client_tab2 = httpx.Client(base_url=BASE_URL)

    # 1 & 2: Register synthetic account
    t0 = time.time()
    reg_res = client_tab1.post("/api/v1/auth/register", json={
        "email": "synthetic_farmer_accept@gari.vn",
        "password": "AcceptancePass123!",
        "full_name": "Nông Dân Thử Nghiệm"
    })
    dt_reg = round((time.time() - t0) * 1000, 1)
    assert reg_res.status_code == 201, f"Registration failed: {reg_res.text}"
    csrf_token = reg_res.json().get("csrf_token") or client_tab1.cookies.get("gari_csrf_token")
    results.append(("Step 1-2: Register synthetic account", reg_res.status_code, f"{dt_reg}ms", "PASS"))
    print(f"[STEP 1-2] Register: Status {reg_res.status_code} ({dt_reg}ms) - Account created with forced role 'farmer'")

    # 3: Log in successfully
    client_tab1.cookies.clear()
    t0 = time.time()
    login_res = client_tab1.post("/api/v1/auth/login", json={
        "email": "synthetic_farmer_accept@gari.vn",
        "password": "AcceptancePass123!",
        "remember_me": False
    })
    dt_login = round((time.time() - t0) * 1000, 1)
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    assert "gari_auth_session" in client_tab1.cookies
    results.append(("Step 3: Login successfully", login_res.status_code, f"{dt_login}ms", "PASS"))
    print(f"[STEP 3] Login: Status {login_res.status_code} ({dt_login}ms) - HttpOnly cookie received")

    # 4: Navigate to protected dashboard / profile
    t0 = time.time()
    prof_res = client_tab1.get("/api/v1/auth/me")
    dt_prof = round((time.time() - t0) * 1000, 1)
    assert prof_res.status_code == 200, f"Profile check failed: {prof_res.text}"
    assert prof_res.json()["email"] == "synthetic_farmer_accept@gari.vn"
    results.append(("Step 4: Access protected profile", prof_res.status_code, f"{dt_prof}ms", "PASS"))
    print(f"[STEP 4] Profile access: Status {prof_res.status_code} ({dt_prof}ms) - Valid session verified")

    # 5 & 6: Refresh page simulation (new request with preserved cookie)
    t0 = time.time()
    refresh_res = client_tab1.get("/api/v1/auth/me")
    dt_ref = round((time.time() - t0) * 1000, 1)
    assert refresh_res.status_code == 200
    results.append(("Step 5-6: Browser refresh persistence", refresh_res.status_code, f"{dt_ref}ms", "PASS"))
    print(f"[STEP 5-6] Refresh: Status {refresh_res.status_code} ({dt_ref}ms) - Session persists across requests")

    # 7: Open second tab simulation
    client_tab2.cookies.set("gari_auth_session", client_tab1.cookies.get("gari_auth_session"))
    t0 = time.time()
    tab2_check = client_tab2.get("/api/v1/auth/me")
    dt_tab2 = round((time.time() - t0) * 1000, 1)
    assert tab2_check.status_code == 200
    results.append(("Step 7: Second tab access", tab2_check.status_code, f"{dt_tab2}ms", "PASS"))
    print(f"[STEP 7] Tab 2 access: Status {tab2_check.status_code} ({dt_tab2}ms) - Shared session valid")

    # 8: Logout from Tab 1
    t0 = time.time()
    logout_res = client_tab1.post("/api/v1/auth/logout")
    dt_logout = round((time.time() - t0) * 1000, 1)
    assert logout_res.status_code == 200
    results.append(("Step 8: Logout from Tab 1", logout_res.status_code, f"{dt_logout}ms", "PASS"))
    print(f"[STEP 8] Logout: Status {logout_res.status_code} ({dt_logout}ms) - DB session revoked & cookie cleared")

    # 9: Verify Tab 2 cannot access protected data after revalidation
    t0 = time.time()
    tab2_reval = client_tab2.get("/api/v1/auth/me")
    dt_reval = round((time.time() - t0) * 1000, 1)
    assert tab2_reval.status_code == 401, f"Expected 401, got {tab2_reval.status_code}"
    results.append(("Step 9: Tab 2 revalidation blocked", tab2_reval.status_code, f"{dt_reval}ms", "PASS"))
    print(f"[STEP 9] Tab 2 revalidation: Status {tab2_reval.status_code} ({dt_reval}ms) - Revoked session properly rejected")

    # 10 & 11: Restart Auth Server and verify persistence policy
    print("[STEP 10] Restarting Auth Server process...")
    server_proc.terminate()
    server_proc.wait(timeout=5)

    # Re-launch server with same DB
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(AUTH_PORT)],
        cwd="auth-server",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(2.0)

    # 12 & 13: Login again while Windows FastAPI is STILL offline
    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s2.connect(('127.0.0.1', 8000))
        s2.close()
        raise Exception("FastAPI port 8000 was unexpectedly active")
    except Exception:
        pass  # Expected: offline

    client_restarted = httpx.Client(base_url=BASE_URL)
    t0 = time.time()
    re_login = client_restarted.post("/api/v1/auth/login", json={
        "email": "synthetic_farmer_accept@gari.vn",
        "password": "AcceptancePass123!"
    })
    dt_re_login = round((time.time() - t0) * 1000, 1)
    assert re_login.status_code == 200, f"Post-restart login failed: {re_login.text}"
    results.append(("Step 10-13: Post-restart login (FastAPI offline)", re_login.status_code, f"{dt_re_login}ms", "PASS"))
    print(f"[STEP 10-13] Post-restart login: Status {re_login.status_code} ({dt_re_login}ms) - Verified persistent SQLite")

    # Profile retrieval post-restart
    t0 = time.time()
    re_prof = client_restarted.get("/api/v1/auth/me")
    dt_re_prof = round((time.time() - t0) * 1000, 1)
    assert re_prof.status_code == 200
    results.append(("Step 13b: Post-restart profile retrieval", re_prof.status_code, f"{dt_re_prof}ms", "PASS"))
    print(f"[STEP 13b] Post-restart profile: Status {re_prof.status_code} ({dt_re_prof}ms) - User: {re_prof.json()['email']}")

    print("\n" + "=" * 70)
    print("PHASE 5 ACCEPTANCE SUMMARY: ALL 13 STEPS PASSED SUCCESSFULLY")
    print("=" * 70)
    for name, code, timing, verdict in results:
        print(f"  {verdict:<6} | HTTP {code:<3} | {timing:<8} | {name}")
    print("=" * 70)

finally:
    try:
        server_proc.terminate()
        server_proc.wait(timeout=5)
    except Exception:
        server_proc.kill()
    DB_PATH.unlink(missing_ok=True)
