"""
Forensic live browser debug script for GARI registration form.
Uses Python Playwright to open Chromium, load register.html, capture all network requests,
console messages, errors, and button states during form submission.
"""

import sys
import os
import time
import json
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright

WORKSPACE_DIR = r"D:\leaf-diseases-detector-main"

class LocalTestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WORKSPACE_DIR, **kwargs)

    def do_POST(self):
        # Mock backend responses if requested
        if self.path.startswith("/api/auth/register"):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            print(f"[TEST SERVER] POST /api/auth/register received body: {body[:100]}...")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "message": "Đăng ký thành công",
                "token": "live_test_session_token_12345",
                "user": {"id": 999, "email": "test@gari.local", "full_name": "Test User"}
            }).encode("utf-8"))
            return

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

def start_server():
    server = HTTPServer(("127.0.0.1", 8899), LocalTestHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server

def run_browser_debug():
    server = start_server()
    print("[DEBUG] Local HTTP test server listening on http://127.0.0.1:8899")

    captured_requests = []
    captured_console = []
    captured_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.on("request", lambda req: captured_requests.append({
            "url": req.url,
            "method": req.method,
            "headers": dict(req.headers)
        }))

        page.on("response", lambda res: print(f"  [NET RESPONSE] {res.status} {res.url}"))
        page.on("requestfailed", lambda req: print(f"  [NET FAILED] {req.method} {req.url} -> {req.failure}"))
        page.on("console", lambda msg: captured_console.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: captured_errors.append(str(err)))

        print("\n--- STAGE 1: Navigate to register.html ---")
        page.goto("http://127.0.0.1:8899/frontend2/register.html")
        page.wait_for_load_state("networkidle")
        print("  Page loaded successfully.")

        print("\n--- STAGE 2: Inspect Initial State & Injected Globals ---")
        has_gari_auth = page.evaluate("() => Boolean(window.gariAuth)")
        print(f"  window.gariAuth exists: {has_gari_auth}")

        print("\n--- STAGE 3: Fill Registration Form ---")
        page.fill("#regFullName", "Huy Nguyen")
        page.fill("#regEmail", "huy_forensic@test.gari")
        page.fill("#regPassword", "Password123!")
        page.fill("#regConfirmPassword", "Password123!")
        page.fill("#regPhone", "0356162193")
        page.check("#termsCheck")

        btn_text_before = page.inner_text("#btnRegSubmit")
        btn_disabled_before = page.is_disabled("#btnRegSubmit")
        print(f"  Button state before click: '{btn_text_before}' (disabled: {btn_disabled_before})")

        print("\n--- STAGE 4: Click Register and Monitor Execution ---")
        page.click("#btnRegSubmit")

        # Poll button state over 5 seconds
        for second in range(1, 6):
            time.sleep(1)
            btn_text = page.inner_text("#btnRegSubmit")
            btn_disabled = page.is_disabled("#btnRegSubmit")
            alert_text = page.inner_text("#authAlert") if page.is_visible("#authAlert") else "(no alert)"
            print(f"  t={second}s: Button: '{btn_text}' (disabled: {btn_disabled}) | Alert: {alert_text}")

        print("\n--- STAGE 5: Console Logs Captured ---")
        for log in captured_console:
            print(f"  {log}")

        print("\n--- STAGE 6: Page Errors Captured ---")
        if captured_errors:
            for err in captured_errors:
                print(f"  [ERROR] {err}")
        else:
            print("  No uncaught page errors.")

        print("\n--- STAGE 7: Network Requests Captured ---")
        for req in captured_requests:
            print(f"  {req['method']} {req['url']}")

        browser.close()
    server.shutdown()

if __name__ == "__main__":
    run_browser_debug()

