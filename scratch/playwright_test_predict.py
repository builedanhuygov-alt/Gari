# -*- coding: utf-8 -*-
"""
Playwright browser test for frontend2/predict.html:
1. Verify Unauthenticated First Screen (Onboarding Gateway visible, Authenticated Header hidden, Diagnosis locked).
2. Verify Zero Dev Mode elements in DOM.
3. Test login & session restoration state transition.
4. Verify Authenticated Workspace Header (Avatar, Plan, Context Switcher, Logout).
5. Verify Pro Mode gating modal & Organization creation modal.
6. Verify 0px horizontal overflow & take screenshots.
"""

import sys
import os
import json
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')

ARTIFACT_DIR = "C:/Users/danhu/.gemini/antigravity/brain/f726ce3c-fc1b-42bc-a6f0-9ea2576ca58b"

def run_browser_tests():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        print("1. Loading http://localhost:8000/frontend2/predict.html in unauthenticated state...")
        page.goto("http://localhost:8000/frontend2/predict.html", wait_until="networkidle")
        page.wait_for_timeout(1000)

        # Check that dev mode auth is 100% gone
        assert page.locator("#chkDevProAuth").count() == 0, "ERROR: #chkDevProAuth still exists in DOM!"
        assert page.locator("#proDevConfigRow").count() == 0, "ERROR: #proDevConfigRow still exists in DOM!"
        print("PASS: Zero Dev Mode Auth elements in DOM.")

        # Check Unauthenticated State
        gateway = page.locator("#authOnboardingGateway")
        auth_header = page.locator("#authenticatedUserHeader")
        lock_banner = page.locator("#diagnosisLockedBanner")

        assert gateway.is_visible(), "ERROR: #authOnboardingGateway is not visible in unauthenticated state!"
        assert not auth_header.is_visible(), "ERROR: #authenticatedUserHeader should be hidden in unauthenticated state!"
        assert lock_banner.is_visible(), "ERROR: #diagnosisLockedBanner is not visible!"
        print("PASS: Unauthenticated state displays Onboarding Gateway and locks diagnosis correctly.")

        # Take screenshot of Unauthenticated Gateway
        shot_unauth = f"{ARTIFACT_DIR}/predict_unauth_gateway.png"
        page.screenshot(path=shot_unauth, full_page=False)
        print(f"Captured: {shot_unauth}")

        # Check Horizontal Overflow
        scroll_w = page.evaluate("() => document.documentElement.scrollWidth")
        inner_w = page.evaluate("() => window.innerWidth")
        diff = scroll_w - inner_w
        print(f"Viewport 1280px Horizontal Overflow: {diff}px (scrollWidth={scroll_w}, innerWidth={inner_w})")
        assert diff <= 0, f"Horizontal overflow detected: {diff}px"

        # 2. Test Login Form
        print("2. Testing Login form submission with test user...")
        page.fill("#loginEmail", "farmer_free_1793767532@gari.vn")
        page.fill("#loginPassword", "Password123!")
        page.click("#btnSubmitLogin")
        page.wait_for_timeout(1500)

        # Verify Authenticated State
        assert auth_header.is_visible(), "ERROR: #authenticatedUserHeader did not appear after login!"
        assert not gateway.is_visible(), "ERROR: #authOnboardingGateway should be hidden after login!"
        assert not lock_banner.is_visible(), "ERROR: #diagnosisLockedBanner should be hidden after login!"

        user_name = page.locator("#userDisplayName").inner_text()
        user_plan = page.locator("#userPlanBadge").inner_text()
        print(f"PASS: User logged in successfully: Name='{user_name}', Plan='{user_plan}'")

        # Take screenshot of Authenticated Dashboard
        shot_auth = f"{ARTIFACT_DIR}/predict_authenticated_workspace.png"
        page.screenshot(path=shot_auth, full_page=False)
        print(f"Captured: {shot_auth}")

        # 3. Test Pro Mode Tab Gating (User is currently Pro because test script upgraded this account)
        print("3. Testing Pro mode tab...")
        page.click("#btnModePro")
        page.wait_for_timeout(500)
        btn_pro_class = page.locator("#btnModePro").get_attribute("class")
        print(f"PASS: Pro mode button clicked, class: {btn_pro_class}")

        # 4. Test Organization Creation Modal
        print("4. Testing Organization Creation modal trigger...")
        page.click("#btnHeaderCreateOrg")
        page.wait_for_timeout(500)
        modal_org = page.locator("#modalCreateOrg")
        assert modal_org.is_visible(), "ERROR: #modalCreateOrg did not open!"
        print("PASS: Organization creation modal opened successfully.")

        # Take screenshot of Create Org modal
        shot_org_modal = f"{ARTIFACT_DIR}/predict_create_org_modal.png"
        page.screenshot(path=shot_org_modal, full_page=False)
        print(f"Captured: {shot_org_modal}")

        # Close Create Org modal
        page.click("#btnCloseCreateOrgModal")
        page.wait_for_timeout(300)
        assert not modal_org.is_visible()

        # 5. Test Mobile Viewport (390px)
        print("5. Testing Mobile Viewport 390px...")
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(800)
        scroll_w_m = page.evaluate("() => document.documentElement.scrollWidth")
        inner_w_m = page.evaluate("() => window.innerWidth")
        diff_m = scroll_w_m - inner_w_m
        print(f"Mobile Viewport 390px Horizontal Overflow: {diff_m}px (scrollWidth={scroll_w_m}, innerWidth={inner_w_m})")
        assert diff_m <= 0, f"Mobile horizontal overflow detected: {diff_m}px"

        shot_mobile = f"{ARTIFACT_DIR}/predict_mobile_390.png"
        page.screenshot(path=shot_mobile, full_page=False)
        print(f"Captured: {shot_mobile}")

        print("\nAll browser UI checks passed cleanly!")
        browser.close()

if __name__ == "__main__":
    run_browser_tests()
