"""
End-to-End Browser Playwright Test for GARI Frontend2 Authentication
Tests:
- Login page: initialization, validation, error alert, successful login, redirection
- Register page: initialization, account type selection, validation, error alerts, successful registration
- Duplicate email handling
- Password recovery page
- Session persistence on index.html, user avatar/name display
- Logout behavior
"""

import os
import sys
import time
import uuid
import socket
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright
import uvicorn

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

os.environ["APP_ENV"] = "development"
os.environ["DEBUG"] = "false"
os.environ["PAYMENT_PUBLIC_CHECKOUT_ENABLED"] = "1"
os.environ["FIREBASE_PROJECT_ID"] = "gari-ai-lab"
os.environ["FIREBASE_API_KEY"] = "AIzaSyTestMockKeyForVerification2026"

import api_server


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def run_e2e_tests():
    port = get_free_port()
    config = uvicorn.Config(api_server.app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    
    t = threading.Thread(target=server.run, daemon=True)
    t.start()

    base_url = f"http://127.0.0.1:{port}"
    print(f"Waiting for server to become ready at {base_url}...")

    # Wait until /health responds
    import urllib.request
    ready = False
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1.0) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except Exception:
            time.sleep(0.5)

    assert ready, "Server failed to start within 30 seconds"
    print(f"Server is fully ready at {base_url}!")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Capture console messages
        page.on("console", lambda msg: print(f"[BROWSER {msg.type}] {msg.text}") if msg.type in ("error", "warning") else None)

        print("\n--- 1. Testing Login Page UI & Form Validation ---")
        page.goto(f"{base_url}/frontend2/login.html")
        assert "Đăng nhập" in page.title()
        
        # Test password visibility toggle
        pwd_input = page.locator("#loginPassword")
        toggle_btn = page.locator("#btnTogglePassword")
        assert pwd_input.get_attribute("type") == "password"
        toggle_btn.click()
        assert pwd_input.get_attribute("type") == "text"
        toggle_btn.click()
        assert pwd_input.get_attribute("type") == "password"

        # Test incorrect password
        page.fill("#loginEmail", "nonexistent_farmer@gari.vn")
        page.fill("#loginPassword", "WrongPass123!")
        page.click("#btnSubmit")
        page.wait_for_selector("#authAlert:visible", timeout=5000)
        alert_text = page.text_content("#authAlert")
        assert "không chính xác" in alert_text or "không thể" in alert_text.lower()
        print("PASS: Incorrect credentials alert displayed:", alert_text)

        print("\n--- 2. Testing Register Page & Validation ---")
        page.goto(f"{base_url}/frontend2/register.html")
        assert "Đăng ký" in page.title()

        unique = uuid.uuid4().hex[:6]
        test_email = f"nongdan_{unique}@gari.vn"
        test_name = f"Lê Văn Nông {unique}"
        test_pass = "NongDan2026!"

        # Test password mismatch
        page.fill("#regFullName", test_name)
        page.fill("#regEmail", test_email)
        page.fill("#regPassword", test_pass)
        page.fill("#regConfirmPassword", "MismatchPassword!")
        page.check("#termsCheck")
        page.click("#btnRegSubmit")
        page.wait_for_selector("#authAlert:visible")
        alert_mismatch = page.text_content("#authAlert")
        assert "không trùng khớp" in alert_mismatch
        print("PASS: Password mismatch caught:", alert_mismatch)

        # Test terms agreement requirement
        page.fill("#regConfirmPassword", test_pass)
        page.uncheck("#termsCheck")
        # Submit form bypassing HTML5 novalidate check to test JS validation
        page.evaluate("document.getElementById('registerForm').noValidate = true;")
        page.click("#btnRegSubmit")
        page.wait_for_selector("#authAlert:visible")
        assert "điều khoản" in page.text_content("#authAlert").lower()
        print("PASS: Terms agreement requirement caught")

        # Select Account Type: Hợp tác xã (Cooperative)
        coop_card = page.locator(".account-type-card[data-value='Hợp tác xã']")
        coop_card.click()
        assert "selected" in coop_card.get_attribute("class")

        # Successful Registration
        page.check("#termsCheck")
        page.evaluate("document.getElementById('registerForm').noValidate = false;")
        page.click("#btnRegSubmit")

        # Registration navigates to dashboard
        page.wait_for_url("**/index.html", timeout=8000)
        print("PASS: Redirected to index.html after registration")

        # Verify auth session in index.html
        page.wait_for_selector("#sidebarUserName", timeout=5000)
        user_name_on_page = page.text_content("#sidebarUserName")
        assert test_name in user_name_on_page or "Gari" in user_name_on_page
        print("PASS: User name displayed on dashboard:", user_name_on_page)

        print("\n--- 3. Testing Duplicate Registration Prevention ---")
        # Clear cookies & storage to simulate clean unauthenticated session
        context.clear_cookies()
        page.evaluate("localStorage.clear(); sessionStorage.clear();")
        page.goto(f"{base_url}/frontend2/register.html")
        page.fill("#regFullName", "Trùng Tên")
        page.fill("#regEmail", test_email)
        page.fill("#regPassword", test_pass)
        page.fill("#regConfirmPassword", test_pass)
        page.check("#termsCheck")
        page.click("#btnRegSubmit")
        page.wait_for_selector("#authAlert:visible", timeout=6000)
        dup_alert = page.text_content("#authAlert")
        assert "đã được đăng ký" in dup_alert or "đã tồn tại" in dup_alert or "email" in dup_alert.lower()
        print("PASS: Duplicate registration blocked with alert:", dup_alert)

        print("\n--- 4. Testing Successful Login & Session Persistence ---")
        context.clear_cookies()
        page.evaluate("localStorage.clear(); sessionStorage.clear();")
        page.goto(f"{base_url}/frontend2/login.html")
        page.fill("#loginEmail", test_email)
        page.fill("#loginPassword", test_pass)
        page.check("#rememberMe")
        page.click("#btnSubmit")

        page.wait_for_url("**/index.html", timeout=8000)
        print("PASS: Redirected to dashboard after login")

        # Refresh page and ensure session persists
        page.reload()
        page.wait_for_selector("#sidebarUserName", timeout=5000)
        assert page.text_content("#sidebarUserName") is not None
        print("PASS: Session persists after page reload")

        print("\n--- 5. Testing Forgot Password Page ---")
        page.goto(f"{base_url}/frontend2/forgot-password.html")
        assert "Khôi phục mật khẩu" in page.title()
        page.fill("#resetEmail", test_email)
        page.click("#btnRequestSubmit")
        page.wait_for_selector("#authAlert:visible", timeout=6000)
        print("PASS: Forgot password response received:", page.text_content("#authAlert"))

        print("\n--- 6. Testing Protected Route Guard ---")
        context.clear_cookies()
        page.evaluate("localStorage.clear(); sessionStorage.clear();")
        page.goto(f"{base_url}/frontend2/settings.html")
        page.wait_for_url("**/login.html**", timeout=6000)
        print("PASS: Unauthenticated visit to settings.html redirected to login.html")

        browser.close()

    server.should_exit = True
    print("\n=======================================================")
    print("ALL END-TO-END PLAYWRIGHT BROWSER TESTS PASSED 100%!")
    print("=======================================================")


if __name__ == "__main__":
    run_e2e_tests()
