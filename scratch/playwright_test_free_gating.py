# -*- coding: utf-8 -*-
import sys
import os
import requests
import time
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')

ARTIFACT_DIR = "C:/Users/danhu/.gemini/antigravity/brain/f726ce3c-fc1b-42bc-a6f0-9ea2576ca58b"
BASE_URL = "http://localhost:8000"

def test_free_gating():
    # Register fresh free user
    uid_suffix = int(time.time())
    email = f"farmer_free_gate_{uid_suffix}@gari.vn"
    reg_payload = {
        "full_name": f"Nong Ho Tu Do {uid_suffix}",
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "phone": "0987654321",
        "province": "Đắk Lắk",
        "account_type": "Nông hộ cá thể"
    }
    r = requests.post(f"{BASE_URL}/api/auth/register", json=reg_payload)
    assert r.status_code == 200

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(f"{BASE_URL}/frontend2/predict.html")
        page.wait_for_timeout(500)

        # Login as free user
        page.fill("#loginEmail", email)
        page.fill("#loginPassword", "Password123!")
        page.click("#btnSubmitLogin")
        page.wait_for_timeout(1000)

        # Check badge says Free
        badge = page.locator("#userPlanBadge").inner_text()
        print(f"Plan Badge: {badge}")

        # 1. Click Pro mode tab -> should trigger Pro Upgrade modal
        page.click("#btnModePro")
        page.wait_for_timeout(500)
        modal_pro = page.locator("#modalProUpgrade")
        assert modal_pro.is_visible(), "Pro modal should open for free user!"
        print("PASS: Pro upgrade modal opened when Free user clicked Pro Mode tab.")

        shot_pro_modal = f"{ARTIFACT_DIR}/predict_pro_upgrade_modal.png"
        page.screenshot(path=shot_pro_modal, full_page=False)
        print(f"Captured: {shot_pro_modal}")

        # Close modal
        page.click("#btnCloseProModal")
        page.wait_for_timeout(300)

        # 2. Click Create Org button -> should trigger Pro Upgrade guidance modal
        page.click("#btnHeaderCreateOrg")
        page.wait_for_timeout(500)
        assert modal_pro.is_visible(), "Pro modal should open when Free user clicks Create Org!"
        print("PASS: Pro upgrade guidance modal opened when Free user clicked Create Org button.")

        browser.close()

if __name__ == "__main__":
    test_free_gating()
