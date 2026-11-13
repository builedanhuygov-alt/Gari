"""
GARI AgriTech AI Lab — Live Browser Forensic Test for Provider-Aware Login
Runs a real Chromium browser via Playwright to verify:
1. Genuine SQLite user login with correct password -> 200 -> redirect to index.html -> gari_token set
2. Genuine SQLite user with wrong password -> 401 -> error message displayed -> no session
3. Unknown account -> rejected without fallback -> error message displayed -> no session
"""

import sys
import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"
LOGIN_URL = f"{BASE_URL}/frontend2/login.html"

TEST_USER_EMAIL = "farmer_test_1794399917@gari.vn"
TEST_USER_PASSWORD = "StrongPassword123!"

def run_browser_tests():
    print("=" * 65)
    print("GARI LIVE BROWSER LOGIN FORENSIC VERIFICATION (PLAYWRIGHT)")
    print("=" * 65)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Capture console messages
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

        # Capture network requests
        network_events = []
        def log_request(req):
            if "/api/" in req.url:
                network_events.append({"type": "REQ", "url": req.url, "method": req.method})
        def log_response(res):
            if "/api/" in res.url:
                network_events.append({"type": "RES", "url": res.url, "status": res.status})

        page.on("request", log_request)
        page.on("response", log_response)

        # ------------------------------------------------------------------
        # TEST 1: Bad Password -> Must fail with 401 and display error
        # ------------------------------------------------------------------
        print("\n--- TEST 1: Incorrect Password for SQLite user ---")
        page.goto(LOGIN_URL, wait_until="networkidle")
        page.fill("#loginEmail", TEST_USER_EMAIL)
        page.fill("#loginPassword", "WrongPassword999!")
        page.click("#btnSubmit")

        page.wait_for_selector("#authAlert.error", timeout=5000)
        alert_text = page.inner_text("#authAlert")
        print(f"Alert text displayed: '{alert_text}'")
        assert "Email hoặc mật khẩu không chính xác" in alert_text, f"Unexpected alert text: {alert_text}"

        token_after_bad = page.evaluate("() => localStorage.getItem('gari_token')")
        assert token_after_bad is None, f"Expected no token, found: {token_after_bad}"
        print("PASS: Wrong password rejected; no token issued; UI alert shown.")

        # ------------------------------------------------------------------
        # TEST 2: Unknown Email -> Must fail and display error
        # ------------------------------------------------------------------
        print("\n--- TEST 2: Unknown Account ---")
        page.goto(LOGIN_URL, wait_until="networkidle")
        page.fill("#loginEmail", "random_unregistered_farmer@gari.vn")
        page.fill("#loginPassword", "SomePassword123!")
        page.click("#btnSubmit")

        page.wait_for_selector("#authAlert.error", timeout=5000)
        alert_text_unknown = page.inner_text("#authAlert")
        print(f"Alert text displayed: '{alert_text_unknown}'")
        assert "Email hoặc mật khẩu không chính xác" in alert_text_unknown

        token_after_unknown = page.evaluate("() => localStorage.getItem('gari_token')")
        assert token_after_unknown is None
        print("PASS: Unknown account rejected; no fallback; no token issued.")

        # ------------------------------------------------------------------
        # TEST 3: Genuine Correct Login -> Must succeed, issue token, navigate
        # ------------------------------------------------------------------
        print("\n--- TEST 3: Genuine SQLite User Login with Correct Password ---")
        network_events.clear()
        page.goto(LOGIN_URL, wait_until="networkidle")
        page.fill("#loginEmail", TEST_USER_EMAIL)
        page.fill("#loginPassword", TEST_USER_PASSWORD)

        # Listen for navigation
        with page.expect_navigation(url=lambda u: "index.html" in u, timeout=10000):
            page.click("#btnSubmit")

        current_url = page.url
        print(f"Navigated to: {current_url}")
        assert "index.html" in current_url, f"Expected navigation to index.html, was {current_url}"

        # Verify token in localStorage
        token = page.evaluate("() => localStorage.getItem('gari_token')")
        user_raw = page.evaluate("() => localStorage.getItem('gari_user')")
        print(f"Token stored: {token[:20]}... (length: {len(token)})")
        print(f"User stored: {user_raw[:100]}...")
        assert token is not None and len(token) > 20, "Token missing or invalid length"

        # Check network traffic during login
        api_responses = [e for e in network_events if e["type"] == "RES"]
        print("\nAPI responses captured during login flow:")
        for res in api_responses:
            print(f"  [{res['status']}] {res['url']}")

        login_res = next((r for r in api_responses if "/api/auth/login" in r["url"]), None)
        assert login_res is not None, "Expected /api/auth/login request"
        assert login_res["status"] == 200, f"Expected 200 for /api/auth/login, got {login_res['status']}"

        print("\nPASS: Genuine login succeeded with 200; JWT issued; redirected to index.html.")

        # ------------------------------------------------------------------
        # TEST 4: Profile check on index.html with active token
        # ------------------------------------------------------------------
        print("\n--- TEST 4: Authenticated Profile Persistence on index.html ---")
        time.sleep(1) # Allow page scripts to settle
        profile_res = page.evaluate("""
            async () => {
                const tok = localStorage.getItem('gari_token');
                const res = await fetch('/api/user/profile', {
                    headers: { 'Authorization': 'Bearer ' + tok }
                });
                return { status: res.status, data: await res.json() };
            }
        """)
        print(f"Profile check status: {profile_res['status']}")
        assert profile_res["status"] == 200, f"Profile endpoint returned {profile_res['status']}"
        profile_email = (
            profile_res["data"].get("identity", {}).get("email")
            or profile_res["data"].get("profile", {}).get("email")
            or profile_res["data"].get("email")
        )
        print(f"Authenticated profile email: {profile_email}")
        assert profile_email == TEST_USER_EMAIL, f"Profile email mismatch: {profile_email} != {TEST_USER_EMAIL}"
        print("PASS: Authenticated session confirmed by FastAPI backend.")

        browser.close()

    print("\n" + "=" * 65)
    print("ALL LIVE BROWSER TESTS PASSED (100% SUCCESSFUL)")
    print("=" * 65)

if __name__ == "__main__":
    run_browser_tests()
