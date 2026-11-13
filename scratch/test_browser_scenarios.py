"""
Test live browser behavior under failure and hanging scenarios.
Checks:
1. Backend returns 503: Does button unlock and show alert?
2. Backend hangs indefinitely: Does client timeout at 10s and unlock button?
"""

import sys
import os
import time
import json
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright

WORKSPACE_DIR = r"D:\leaf-diseases-detector-main"

backend_behavior = "offline_503"  # or "hang" or "success"

class ScenarioServerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WORKSPACE_DIR, **kwargs)

    def do_POST(self):
        global backend_behavior
        if self.path.startswith("/api/auth/register") or self.path.startswith("/api/auth/firebase-login"):
            if backend_behavior == "hang":
                print("  [SERVER] Hanging registration request indefinitely (simulating unbuffered stream deadlock)...")
                time.sleep(30)
                return

            if backend_behavior == "offline_503":
                print("  [SERVER] Responding HTTP 503 BACKEND_UNAVAILABLE...")
                self.send_response(503)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "code": "BACKEND_UNAVAILABLE",
                    "detail": "Máy chủ xác thực hiện chưa sẵn sàng hoặc đang bảo trì."
                }).encode("utf-8"))
                return

        super().do_POST()

    def do_GET(self):
        if self.path.startswith("/api/auth/firebase-config"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "configured": False,
                "config": {}
            }).encode("utf-8"))
            return

        if self.path.startswith("/api/user/profile") or self.path.startswith("/api/auth/me"):
            self.send_response(401)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"detail": "Unauthorized"}).encode("utf-8"))
            return

        super().do_GET()

def run_tests():
    global backend_behavior
    server = HTTPServer(("127.0.0.1", 8898), ScenarioServerHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print("[SERVER] Started on http://127.0.0.1:8898")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # TEST 1: Backend returns 503
        print("\n=== TEST 1: BACKEND RETURNS HTTP 503 ===")
        backend_behavior = "offline_503"
        page = browser.new_page()
        page.goto("http://127.0.0.1:8898/frontend2/register.html")
        page.wait_for_load_state("networkidle")

        page.fill("#regFullName", "Huy Nguyen")
        page.fill("#regEmail", "test503@gari.local")
        page.fill("#regPassword", "Password123!")
        page.fill("#regConfirmPassword", "Password123!")
        page.fill("#regPhone", "0356162193")
        page.check("#termsCheck")

        print("  Submitting form...")
        page.click("#btnRegSubmit")

        # Wait up to 3 seconds for 503 response
        time.sleep(1.5)
        btn_text = page.inner_text("#btnRegSubmit")
        btn_disabled = page.is_disabled("#btnRegSubmit")
        alert_visible = page.is_visible("#authAlert")
        alert_text = page.inner_text("#authAlert") if alert_visible else ""
        print(f"  After 503 response: Button text='{btn_text}' | Disabled={btn_disabled}")
        print(f"  Alert displayed: '{alert_text}'")

        assert btn_disabled == False, "Button must NOT remain disabled after 503"
        assert alert_visible == True, "Alert must be visible"
        print("  -> TEST 1 PASSED: 503 properly shows alert and unblocks button!")
        page.close()

        # TEST 2: Backend hangs indefinitely (Testing safeFetch 10s timeout abort)
        print("\n=== TEST 2: BACKEND HANGS (TIMEOUT ABORT TEST) ===")
        backend_behavior = "hang"
        page = browser.new_page()
        page.goto("http://127.0.0.1:8898/frontend2/register.html")
        page.wait_for_load_state("networkidle")

        page.fill("#regFullName", "Huy Nguyen")
        page.fill("#regEmail", "testhang@gari.local")
        page.fill("#regPassword", "Password123!")
        page.fill("#regConfirmPassword", "Password123!")
        page.fill("#regPhone", "0356162193")
        page.check("#termsCheck")

        print("  Submitting form against hanging backend...")
        page.click("#btnRegSubmit")

        # At t=2s, button should be loading
        time.sleep(2)
        print(f"  t=2s: Button='{page.inner_text('#btnRegSubmit')}' | Disabled={page.is_disabled('#btnRegSubmit')}")

        # At t=11s (after safeFetch 10s timeout abort), button MUST be unlocked and alert shown!
        print("  Waiting for 10s timeout window to elapse...")
        time.sleep(9)
        btn_text_t11 = page.inner_text("#btnRegSubmit")
        btn_disabled_t11 = page.is_disabled("#btnRegSubmit")
        alert_visible_t11 = page.is_visible("#authAlert")
        alert_text_t11 = page.inner_text("#authAlert") if alert_visible_t11 else ""
        print(f"  t=11s: Button='{btn_text_t11}' | Disabled={btn_disabled_t11}")
        print(f"  Alert displayed: '{alert_text_t11}'")

        assert btn_disabled_t11 == False, "Button MUST unlock after 10s timeout!"
        assert alert_visible_t11 == True, "Timeout alert MUST be displayed!"
        print("  -> TEST 2 PASSED: 10s timeout abort fired, button unblocked, and alert displayed!")
        page.close()

        browser.close()

    server.shutdown()
    print("\nALL BROWSER LIVE SCENARIOS VERIFIED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()

