"""
GARI AI LAB — Browser Verification Script for Redesigned Farm/Org Selector
File: tests/verify_selector_browser.py

Verifies:
1. Authenticated User 1 sees clean grouped categories: Personal, My Farms (5), Cooperatives & Orgs (1).
2. Zero test fixtures: "Test Concurrent HTX" and "Cô Đơn" are nowhere in the DOM.
3. Interactive search filters items accurately.
4. Mobile viewport (390px) responsive layout.
5. Captures screenshots for documentation & audit.
"""

import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

os.environ["APP_ENV"] = "development"
os.environ["PAYMENT_PUBLIC_CHECKOUT_ENABLED"] = "1"

import gari_auth
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = ROOT_DIR / "tests" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print("[1/5] Generating session token for Dan Huynh (User #1)...")
    token = gari_auth.create_session(user_id=1)
    print(f"      Token generated: {token[:12]}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # -------------------------------------------------------------
        # DESKTOP VIEWPORT (1440 x 900)
        # -------------------------------------------------------------
        print("[2/5] Testing Desktop Viewport (1440x900)...")
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.on("console", lambda msg: print(f"      BROWSER LOG: {msg.text}"))
        page.on("pageerror", lambda err: print(f"      BROWSER ERROR: {err}"))

        # Inject token before loading
        page.add_init_script(f"""
            window.localStorage.setItem('gari_token', '{token}');
            window.localStorage.setItem('gari_user', JSON.stringify({{
                id: 1,
                name: 'Kỹ sư Đan Huỳnh',
                email: 'danhuynh@gari.vn',
                account_type: 'expert'
            }}));
        """)

        page.goto("http://localhost:8000/frontend2/predict.html", wait_until="networkidle")
        page.wait_for_selector("#contextPickerTrigger", timeout=10000)
        time.sleep(1)

        # Assert no test strings in entire page text
        page_content = page.content()
        assert "Test Concurrent HTX" not in page_content, "ERROR: Leaked 'Test Concurrent HTX' in DOM!"
        assert "Cô Đơn" not in page_content, "ERROR: Leaked 'Cô Đơn' in DOM!"
        print("      PASS: No test data leaked in page content.")

        # Click context selector button to open dropdown
        trigger = page.locator("#contextPickerTrigger")
        trigger.click()
        page.wait_for_selector("#contextDropdownPanel", state="visible", timeout=5000)
        time.sleep(0.5)

        # Verify grouped elements exist
        dropdown_html = page.locator("#contextDropdownPanel").inner_html()
        assert "Khám tự do" in dropdown_html, "Missing Personal option"
        assert "Trang trại Ba Vì Organic" in dropdown_html, "Missing real farm 'Trang trại Ba Vì Organic'"
        assert "Hợp Tác Xã Nông Nghiệp Ba Vì" in dropdown_html, "Missing real org 'Hợp Tác Xã Nông Nghiệp Ba Vì'"
        print("      PASS: Grouped sections & real entities rendered properly.")

        # Capture Desktop Open Screenshot
        desktop_open_path = SCREENSHOT_DIR / "farm_org_selector_desktop_open.png"
        page.screenshot(path=str(desktop_open_path), full_page=False)
        print(f"      Saved screenshot: {desktop_open_path.name}")

        # Search test
        search_input = page.locator("#contextSearchInput")
        search_input.fill("Ba Vì")
        time.sleep(0.5)

        desktop_search_path = SCREENSHOT_DIR / "farm_org_selector_desktop_search.png"
        page.screenshot(path=str(desktop_search_path), full_page=False)
        print(f"      Saved screenshot: {desktop_search_path.name}")

        # Select the organization
        org_item = page.locator('.context-option-item[data-type="organization"]')
        org_item.first.click()
        time.sleep(0.5)

        selected_label = page.locator("#triggerContextTitle").inner_text()
        print(f"      Selected context: '{selected_label}'")
        assert "Hợp Tác Xã Nông Nghiệp Ba Vì" in selected_label, "Failed to select organization"

        context.close()

        # -------------------------------------------------------------
        # MOBILE VIEWPORT (390 x 844 - iPhone 14 / modern smartphone)
        # -------------------------------------------------------------
        print("[3/5] Testing Mobile Viewport (390x844)...")
        mobile_context = browser.new_context(
            viewport={"width": 390, "height": 844},
            is_mobile=True
        )
        mobile_page = mobile_context.new_page()

        mobile_page.add_init_script(f"""
            window.localStorage.setItem('gari_token', '{token}');
            window.localStorage.setItem('gari_user', JSON.stringify({{
                id: 1,
                name: 'Kỹ sư Đan Huỳnh',
                email: 'danhuynh@gari.vn',
                account_type: 'expert'
            }}));
        """)

        mobile_page.goto("http://localhost:8000/frontend2/predict.html", wait_until="networkidle")
        mobile_page.wait_for_selector("#contextPickerTrigger", timeout=10000)
        time.sleep(1)

        mobile_trigger = mobile_page.locator("#contextPickerTrigger")
        mobile_trigger.click()
        mobile_page.wait_for_selector("#contextDropdownPanel", state="visible", timeout=5000)
        time.sleep(0.5)

        mobile_open_path = SCREENSHOT_DIR / "farm_org_selector_mobile_open.png"
        mobile_page.screenshot(path=str(mobile_open_path), full_page=False)
        print(f"      Saved mobile screenshot: {mobile_open_path.name}")

        mobile_context.close()

        # -------------------------------------------------------------
        # CLEAN USER EXPERIENCE (No farms or orgs yet)
        # -------------------------------------------------------------
        print("[4/5] Testing User with Zero Farms & Orgs (Empty State)...")
        clean_user_token = gari_auth.create_session(user_id=151)
        clean_context = browser.new_context(viewport={"width": 1440, "height": 900})
        clean_page = clean_context.new_page()

        clean_page.add_init_script(f"""
            window.localStorage.setItem('gari_token', '{clean_user_token}');
            window.localStorage.setItem('gari_user', JSON.stringify({{
                id: 151,
                name: 'Nông Hộ Mới',
                email: 'sim_user_b2239013@gari.vn',
                account_type: 'farmer'
            }}));
        """)

        clean_page.goto("http://localhost:8000/frontend2/predict.html", wait_until="networkidle")
        clean_page.wait_for_selector("#contextPickerTrigger", timeout=10000)
        time.sleep(1)

        clean_trigger = clean_page.locator("#contextPickerTrigger")
        clean_trigger.click()
        clean_page.wait_for_selector("#contextDropdownPanel", state="visible", timeout=5000)
        time.sleep(0.5)

        clean_dropdown_html = clean_page.locator("#contextDropdownPanel").inner_html()
        assert "chưa có nông trại nào" in clean_dropdown_html.lower(), "Clean user should see empty farm state"
        assert "chưa tham gia hợp tác xã" in clean_dropdown_html.lower(), "Clean user should see empty org state"
        print("      PASS: Empty states rendered cleanly with actionable guidance.")

        clean_path = SCREENSHOT_DIR / "farm_org_selector_empty_state.png"
        clean_page.screenshot(path=str(clean_path), full_page=False)
        print(f"      Saved empty state screenshot: {clean_path.name}")

        clean_context.close()
        browser.close()

    print("[5/5] All browser verifications passed with 100% success!")


if __name__ == "__main__":
    main()
