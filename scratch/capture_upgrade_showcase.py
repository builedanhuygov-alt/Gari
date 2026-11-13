import asyncio
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path('.').resolve()
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding='utf-8')

ARTIFACT_DIR = Path(r"C:\Users\danhu\.gemini\antigravity\brain\f726ce3c-fc1b-42bc-a6f0-9ea2576ca58b")

async def main():
    import gari_auth
    token = gari_auth.create_session(user_id=1)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        await context.add_cookies([
            {"name": "gari_session", "value": token, "domain": "localhost", "path": "/"},
            {"name": "auth_token", "value": token, "domain": "localhost", "path": "/"}
        ])
        await context.add_init_script(f"""
            localStorage.setItem('gari_token', '{token}');
            localStorage.setItem('gari_user', JSON.stringify({{ id: 1, email: 'danhuynh@gari.vn', name: 'Đan Huỳnh', role: 'admin' }}));
        """)

        page = await context.new_page()

        # 1. Copilot Drawer open on Dashboard
        await page.goto("http://localhost:8000/frontend2/index.html", wait_until="networkidle")
        await page.click("#gariCopilotFab")
        await page.wait_for_timeout(800)
        chip = await page.query_selector(".copilot-chip[data-q*='quá hạn']")
        if chip:
            await chip.click()
            await page.wait_for_timeout(1000)
        await page.screenshot(path=str(ARTIFACT_DIR / "showcase_copilot_drawer.png"))
        print("✓ Captured showcase_copilot_drawer.png")

        # 2. Predict Page with 1-click Task action
        await page.goto("http://localhost:8000/frontend2/predict.html", wait_until="networkidle")
        await page.click("#btnModeManual")
        await page.evaluate("() => document.getElementById('cropSelect').value = 'tomato'")
        await page.set_input_files("#fileInput", "test_leaf.jpg")
        await page.click("#btnPredict")
        await page.wait_for_selector("#activeResultCard", timeout=15000)
        await page.wait_for_selector(".btn-create-task-from-rec", timeout=5000)
        rec_btns = await page.query_selector_all(".btn-create-task-from-rec")
        if rec_btns:
            await rec_btns[0].click()
            await page.wait_for_timeout(600)
        await page.screenshot(path=str(ARTIFACT_DIR / "showcase_predict_action.png"))
        print("✓ Captured showcase_predict_action.png")

        # 3. VietGAP Seasonal Report
        await page.goto("http://localhost:8000/api/farms/1/export-season-report", wait_until="networkidle")
        await page.screenshot(path=str(ARTIFACT_DIR / "showcase_vietgap_season_report.png"))
        print("✓ Captured showcase_vietgap_season_report.png")

        # 4. Calendar Page
        await page.goto("http://localhost:8000/frontend2/calendar.html", wait_until="networkidle")
        await page.screenshot(path=str(ARTIFACT_DIR / "showcase_cultivation_calendar.png"))
        print("✓ Captured showcase_cultivation_calendar.png")

        await browser.close()
        print("All showcase captures completed!")

if __name__ == "__main__":
    asyncio.run(main())
