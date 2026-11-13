import os
import sys
import time
import io
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath("."))

import gari_auth
import gari_database

ARTIFACT_DIR = r"C:\Users\danhu\.gemini\antigravity\brain\f726ce3c-fc1b-42bc-a6f0-9ea2576ca58b"
BASE_URL = "http://localhost:8000"

def generate_leaf_file(path="scratch/valid_leaf.jpg"):
    img = Image.new("RGB", (300, 300), (220, 220, 220))
    draw = ImageDraw.Draw(img)
    draw.polygon([(150, 30), (260, 150), (150, 270), (40, 150)], fill=(34, 150, 40), outline=(20, 100, 25))
    for y in range(60, 240, 20):
        draw.line([(150, y), (150 + (y % 40) * 2, y + 15)], fill=(80, 200, 60), width=2)
        draw.line([(150, y), (150 - (y % 40) * 2, y + 15)], fill=(80, 200, 60), width=2)
    draw.ellipse([120, 100, 135, 115], fill=(120, 60, 20))
    draw.ellipse([160, 180, 180, 195], fill=(130, 70, 25))
    img.save(path, format="JPEG")
    return os.path.abspath(path)

def test_browser_e2e():
    print("=== STARTING PLAYWRIGHT BROWSER E2E TEST ===")
    leaf_path = generate_leaf_file()

    # Get or create admin user for full access
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email FROM users WHERE is_admin = 1 LIMIT 1")
        admin_row = cursor.fetchone()
        admin_id = admin_row[0]
        admin_email = admin_row[1]

    session_token = gari_auth.create_session(user_id=admin_id)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # -------------------------------------------------------------
        # TEST 1: DESKTOP VIEWPORT (1280x800)
        # -------------------------------------------------------------
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        # Set auth tokens in localStorage and cookies
        context.add_cookies([
            {"name": "gari_token", "value": session_token, "domain": "localhost", "path": "/"}
        ])

        page = context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        print("Navigating to http://localhost:8000/frontend2/predict.html...")
        page.goto(f"{BASE_URL}/frontend2/predict.html", wait_until="networkidle")

        # Inject token into localStorage
        page.evaluate(f"""() => {{
            localStorage.setItem('gari_token', '{session_token}');
            localStorage.setItem('gari_user', JSON.stringify({{ id: {admin_id}, email: '{admin_email}', full_name: 'Admin Test' }}));
        }}""")
        page.reload(wait_until="networkidle")

        # Check Page Title
        title = page.title()
        print(f"Page title: {title}")
        assert "GARI Leaf Intelligence" in title, f"Title does not match: {title}"

        # Verify Sidebar: no duplicate leaf_check links
        leaf_check_links = page.locator("a[href*='mode=leaf']").count()
        assert leaf_check_links == 0, f"Found {leaf_check_links} duplicate mode=leaf links in navigation!"
        print("PASS: Sidebar contains 0 duplicate mode=leaf links")

        # Check Header
        crumb = page.locator("#topbarCrumb").inner_text()
        print(f"Topbar Breadcrumb: {crumb}")
        assert "GARI Leaf Intelligence" in crumb, f"Header crumb unexpected: {crumb}"

        # Check Multi-image thumbnail strip exists
        sec_strip = page.locator("#multiImageStrip")
        assert sec_strip.count() > 0, "#multiImageStrip not found!"

        # Check Field Observation Accordion exists
        obs_accordion = page.locator("#fieldObservationDetails")
        assert obs_accordion.count() > 0, "#fieldObservationDetails not found!"
        # Expand accordion
        obs_accordion.click()

        # Fill field observations
        page.select_option("#fieldGrowthStage", value="Ra hoa / Đậu quả")
        page.fill("#fieldSymptoms", "Đốm cháy mép phiến lá có quầng vàng")
        page.fill("#fieldConditions", "Mưa liên tục 2 ngày, độ ẩm 90%")
        page.fill("#diagNotes", "Ghi chú khảo sát hàng cây số 4")

        # Upload leaf image
        file_input = page.locator("#fileInput")
        file_input.set_input_files(leaf_path)
        page.wait_for_timeout(500)

        # Check preview is visible and multiImageStrip is displayed
        assert page.locator("#previewContainer").is_visible(), "Preview container not visible after upload!"
        assert page.locator("#multiImageStrip").is_visible(), "MultiImageStrip not visible after upload!"
        print("PASS: Image preview and multi-image strip active")

        # Select Manual Mode & Tomato
        page.locator("#btnModeManual").click()
        page.select_option("#cropSelect", value="tomato")
        page.wait_for_timeout(300)

        # Click Predict button
        btn_predict = page.locator("#btnPredict")
        assert btn_predict.is_enabled(), "Predict button is disabled!"
        print("Clicking 'Tiến hành kiểm tra lá'...")
        btn_predict.click()

        # Wait for results card
        page.wait_for_selector("#activeResultCard", state="visible", timeout=20000)
        print("PASS: Diagnosis results card rendered successfully!")

        # Verify Assistant Chat Card is rendered directly below results
        assistant_card = page.locator("#assistantChatCard")
        assert assistant_card.is_visible(), "#assistantChatCard is not visible!"
        print("PASS: GARI Plant Health Assistant Chatbot card is visible below diagnosis results!")

        # Check Quick Prompts are present
        quick_prompts = page.locator(".quick-prompt-pill")
        qp_count = quick_prompts.count()
        assert qp_count >= 5, f"Expected at least 5 quick prompt pills, found {qp_count}"
        print(f"PASS: {qp_count} contextual quick prompt pills ready")

        # Check Deep dive toggle button
        btn_deep = page.locator("#btnToggleDeepDive")
        assert btn_deep.is_visible(), "Deep dive toggle button not visible!"
        btn_deep.click()
        page.wait_for_timeout(300)
        assert "Bật" in page.locator("#deepDiveStatusText").inner_text()
        print("PASS: Deep-dive toggle functions correctly")

        # Check Horizontal Overflow (1280px)
        overflow = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
        assert not overflow, "Horizontal overflow detected on desktop 1280px!"
        print("PASS: 0px horizontal overflow on desktop 1280px")

        # Take desktop showcase screenshot
        desktop_screenshot = os.path.join(ARTIFACT_DIR, "predict_leaf_intelligence_desktop.png")
        page.screenshot(path=desktop_screenshot, full_page=False)
        print(f"Saved screenshot: {desktop_screenshot}")

        # Scroll to assistant chatbot and take dedicated screenshot
        assistant_card.scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        assistant_screenshot = os.path.join(ARTIFACT_DIR, "predict_leaf_intelligence_assistant.png")
        page.screenshot(path=assistant_screenshot, full_page=False)
        print(f"Saved screenshot: {assistant_screenshot}")

        context.close()

        # -------------------------------------------------------------
        # TEST 2: MOBILE VIEWPORT (390x844 iPhone 14)
        # -------------------------------------------------------------
        print("\nTesting mobile viewport (390x844)...")
        mobile_ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        )
        mobile_ctx.add_cookies([
            {"name": "gari_token", "value": session_token, "domain": "localhost", "path": "/"}
        ])

        mobile_page = mobile_ctx.new_page()
        mobile_page.goto(f"{BASE_URL}/frontend2/predict.html", wait_until="networkidle")

        mobile_overflow = mobile_page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
        assert not mobile_overflow, "Horizontal overflow detected on mobile 390px!"
        print("PASS: 0px horizontal overflow on mobile 390px")

        mobile_screenshot = os.path.join(ARTIFACT_DIR, "predict_leaf_intelligence_mobile.png")
        mobile_page.screenshot(path=mobile_screenshot, full_page=False)
        print(f"Saved mobile screenshot: {mobile_screenshot}")

        mobile_ctx.close()
        browser.close()

    print("\nALL PLAYWRIGHT BROWSER VERIFICATION TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    test_browser_e2e()
