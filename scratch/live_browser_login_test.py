import json
import time
from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        console_logs = []
        network_events = []

        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("request", lambda req: network_events.append({
            "type": "REQUEST",
            "url": req.url,
            "method": req.method,
            "post_data": req.post_data
        }))
        page.on("response", lambda res: network_events.append({
            "type": "RESPONSE",
            "url": res.url,
            "status": res.status
        }))

        print("1. Navigating to http://127.0.0.1:8000/frontend2/login.html...")
        page.goto("http://127.0.0.1:8000/frontend2/login.html", wait_until="networkidle")

        print("2. Page title:", page.title())

        # Test with the freshly created test user: farmer_test_1794399917@gari.vn
        email_input = page.locator("#loginEmail")
        pwd_input = page.locator("#loginPassword")
        btn_submit = page.locator("#btnSubmit")

        print("3. Filling credentials: farmer_test_1794399917@gari.vn...")
        email_input.fill("farmer_test_1794399917@gari.vn")
        pwd_input.fill("StrongPassword123!")

        print("4. Clicking submit...")
        btn_submit.click()

        time.sleep(4)

        print("5. Current URL after submit:", page.url)
        alert_el = page.locator("#authAlert")
        alert_text = alert_el.inner_text() if alert_el.is_visible() else "(hidden)"
        btn_text = btn_submit.inner_text() if btn_submit.is_visible() else "(navigated/hidden)"
        btn_disabled = btn_submit.is_disabled() if btn_submit.is_visible() else None

        print("6. Alert box text:", alert_text)
        print("7. Button state:", btn_text, "Disabled:", btn_disabled)

        # Check localStorage
        token = page.evaluate("() => localStorage.getItem('gari_token')")
        user = page.evaluate("() => localStorage.getItem('gari_user')")
        print("8. localStorage gari_token:", bool(token))
        print("9. localStorage gari_user:", user[:80] if user else None)

        print("\n--- NETWORK EVENTS (/api/) ---")
        for evt in network_events:
            if "/api/" in evt.get("url", ""):
                print(evt)

        print("\n--- CONSOLE LOGS ---")
        for log in console_logs:
            print(log)

        browser.close()

if __name__ == "__main__":
    run()

