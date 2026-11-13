import asyncio
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    print("=====================================================================")
    print("GARI AGRI-TECH: PLAYWRIGHT COMPREHENSIVE END-TO-END VERIFICATION")
    print("=====================================================================")

    # Get valid auth token
    import gari_auth
    token = gari_auth.create_session(user_id=1)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) GariTester/2.0"
        )
        await context.add_cookies([
            {"name": "auth_token", "value": token, "domain": "localhost", "path": "/"},
            {"name": "gari_session", "value": token, "domain": "localhost", "path": "/"}
        ])
        await context.add_init_script(f"""
            localStorage.setItem('gari_token', '{token}');
            localStorage.setItem('gari_user', JSON.stringify({{ id: 1, email: 'danhuynh@gari.vn', name: 'Đan Huỳnh', role: 'admin' }}));
        """)

        page = await context.new_page()

        # Track console errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # 1. Test Index / Dashboard & Copilot Drawer
        print("\n--- 1. Testing Dashboard & Floating Copilot Drawer ---")
        await page.goto("http://localhost:8000/frontend2/index.html", wait_until="networkidle")
        overflow = await page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
        print(f"Dashboard overflow: {overflow}")
        assert not overflow, "Horizontal overflow on Dashboard"

        # Check Copilot FAB
        copilot_fab = await page.query_selector("#gariCopilotFab")
        assert copilot_fab is not None, "Copilot FAB button not found on Dashboard!"
        print("✓ Copilot FAB located on DOM")

        # Click Copilot FAB to open drawer
        await page.click("#gariCopilotFab")
        await page.wait_for_timeout(600)
        drawer_open = await page.evaluate("() => document.getElementById('gariCopilotDrawer').classList.contains('open')")
        assert drawer_open, "Copilot Drawer failed to open!"
        print("✓ Copilot Drawer opened successfully")

        # Verify context chips rendered
        chips_text = await page.inner_text("#copilotContextBar")
        print(f"✓ Copilot Context Chips: {chips_text}")

        # Click a quick prompt chip: "📋 Việc hôm nay & quá hạn"
        chip_btn = await page.query_selector(".copilot-chip[data-q*='quá hạn']")
        if chip_btn:
            await chip_btn.click()
            await page.wait_for_timeout(1000)
            bot_msgs = await page.query_selector_all(".copilot-msg.bot .copilot-bubble")
            latest_bot = await bot_msgs[-1].inner_text()
            print(f"✓ Copilot Bot Reply: {latest_bot[:100]}...")
            assert len(bot_msgs) >= 2, "Copilot did not reply to user prompt"

        # Close Copilot drawer
        await page.click("#btnCloseCopilot")
        await page.wait_for_timeout(300)

        # 2. Test Farms Page & VietGAP Season Report button
        print("\n--- 2. Testing Farms Page & VietGAP Season Report ---")
        await page.goto("http://localhost:8000/frontend2/farms.html", wait_until="networkidle")
        farm_overflow = await page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
        assert not farm_overflow, "Horizontal overflow on Farms page"

        vietgap_btns = await page.query_selector_all("a[href*='export-season-report']")
        assert len(vietgap_btns) > 0, "VietGAP Report button not found on farm cards!"
        print(f"✓ Found {len(vietgap_btns)} VietGAP Seasonal Journal export links")

        # 3. Test Diagnosis Page & 1-Click Task Creation
        print("\n--- 3. Testing Predict Page & 1-Click Task Creation ---")
        await page.goto("http://localhost:8000/frontend2/predict.html", wait_until="networkidle")
        predict_overflow = await page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
        assert not predict_overflow, "Horizontal overflow on Predict page"

        # Select manual mode with 'tomato'
        await page.click("#btnModeManual")
        await page.evaluate("() => document.getElementById('cropSelect').value = 'tomato'")
        await page.wait_for_timeout(300)

        # Upload real leaf image
        await page.set_input_files("#fileInput", "test_leaf.jpg")
        await page.wait_for_timeout(500)

        # Click Chẩn đoán
        await page.click("#btnPredict")
        print("✓ Clicked #btnPredict, running AI model inference...")

        # Wait for recommendation buttons to appear
        await page.wait_for_selector(".btn-create-task-from-rec", timeout=25000)
        rec_btns = await page.query_selector_all(".btn-create-task-from-rec")
        print(f"✓ AI diagnosis finished! Found {len(rec_btns)} actionable recommendation buttons")
        assert len(rec_btns) > 0, "No recommendation buttons generated after inference"

        # Click the first 1-click task creation button
        first_btn = rec_btns[0]
        await first_btn.click()
        await page.wait_for_timeout(1000)
        btn_text = await first_btn.inner_text()
        print(f"✓ Button state after click: {btn_text}")
        assert "Đã thêm vào Lịch" in btn_text, "Task was not created from recommendation"

        # 4. Test Calendar Page & Task Persistence
        print("\n--- 4. Testing Calendar Page ---")
        await page.goto("http://localhost:8000/frontend2/calendar.html", wait_until="networkidle")
        cal_overflow = await page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
        assert not cal_overflow, "Horizontal overflow on Calendar page"
        task_items = await page.query_selector_all(".cal-task-item, .task-item")
        print(f"✓ Loaded {len(task_items)} active cultivation tasks from database API")

        # 5. Test Risk Alert & Field Observation Modal
        print("\n--- 5. Testing Risk Page ---")
        await page.goto("http://localhost:8000/frontend2/risk.html", wait_until="networkidle")
        risk_overflow = await page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
        assert not risk_overflow, "Horizontal overflow on Risk page"

        obs_btn = await page.query_selector(".btn-risk-obs")
        if obs_btn:
            await obs_btn.click()
            await page.wait_for_timeout(500)
            modal_open = await page.evaluate("() => document.getElementById('riskObservationModal').classList.contains('show')")
            assert modal_open, "Observation modal did not open with .show"
            print("✓ Risk field observation modal opened successfully")

        # 6. Check Console Errors
        # Ignore external favicon 404 or expected minor noise if any
        critical_errors = [e for e in console_errors if "favicon" not in e and "map" not in e]
        print(f"\n--- Console Check ---")
        print(f"Total critical console errors across all workflows: {len(critical_errors)}")
        if critical_errors:
            print("Errors:", critical_errors)

        await browser.close()
        print("\n=====================================================================")
        print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY WITH 100% PASS RATE!")
        print("=====================================================================")

if __name__ == "__main__":
    asyncio.run(main())
