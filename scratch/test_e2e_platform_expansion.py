import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import uuid
from playwright.async_api import async_playwright

async def run_e2e():
    print("=== STARTING PLAYWRIGHT E2E PLATFORM EXPANSION TEST ===")
    os.makedirs("tests/screenshots", exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()
        page.on("console", lambda msg: print(f"PAGE LOG: {msg.text}"))
        page.on("pageerror", lambda err: print(f"PAGE ERROR: {err}"))
        page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))

        # 1. Login as Host Admin
        import gari_database, gari_auth
        admin_email = f"e2e_host_{uuid.uuid4().hex[:6]}@gari.local"
        admin_pw = "HostAdmin@123456"
        admin_hash = gari_auth.hash_password(admin_pw)
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (full_name, name, email, password_hash, account_type, is_admin, is_host_admin, is_expert, is_active)
                VALUES ('Host Administrator', 'HostAdmin', ?, ?, 'admin', 1, 1, 1, 1)
            """, (admin_email, admin_hash))
            admin_id = cursor.lastrowid
            conn.commit()

        # Create session token
        token = gari_auth.create_session(admin_id)

        # Inject into localStorage and navigate to Host Console
        await page.goto("http://localhost:8000/frontend2/host-login.html")
        await page.evaluate(f"""() => {{
            localStorage.setItem('gari_host_token', '{token}');
            localStorage.setItem('gari_token', '{token}');
        }}""")

        await page.goto("http://localhost:8000/frontend2/host.html")
        await page.wait_for_selector(".host-container", timeout=15000)
        print("PASS: Host Console loaded successfully")
        await page.screenshot(path="tests/screenshots/expansion_01_host_console_overview.png")

        # Switch to Expert Tab
        await page.click('button[data-tab="tab-experts"]')
        await page.wait_for_selector("#tab-experts.active", timeout=5000)
        await asyncio.sleep(1)
        print("PASS: Host Console Expert Management Tab active")
        await page.screenshot(path="tests/screenshots/expansion_02_host_experts_management.png")

        # Switch to Models Tab and run AI Realtime Test
        await page.click('button[data-tab="tab-models"]')
        await page.wait_for_selector("#tab-models.active", timeout=5000)
        
        # Call runHostAiTest directly and await promise
        await page.evaluate("async () => await runHostAiTest()")
        await page.wait_for_selector("#aiTestResultBox", state="visible", timeout=10000)
        print("PASS: Host Console AI Realtime Diagnostic Test executed")
        await page.screenshot(path="tests/screenshots/expansion_03_host_ai_benchmark.png")

        # 2. Expert Portal E2E
        await page.goto("http://localhost:8000/frontend2/expert-portal.html")
        await page.wait_for_selector("#expertWorkspace", timeout=15000)
        await asyncio.sleep(1)
        print("PASS: GARI Expert Portal loaded for certified agronomist")
        await page.screenshot(path="tests/screenshots/expansion_04_expert_portal_workspace.png")

        # 3. Farmer Support Page
        await page.goto("http://localhost:8000/frontend2/support.html")
        await page.wait_for_selector(".page-head-title", timeout=15000)
        await asyncio.sleep(1)
        print("PASS: Support Page with Expert Link loaded")
        await page.screenshot(path="tests/screenshots/expansion_05_farmer_support_portal.png")

        # 4. Mobile Viewport test for Expert Portal (iPhone 14 / 390x844)
        mobile_context = await browser.new_context(viewport={"width": 390, "height": 844})
        mobile_page = await mobile_context.new_page()
        await mobile_page.goto("http://localhost:8000/frontend2/host-login.html")
        await mobile_page.evaluate(f"""() => {{
            localStorage.setItem('gari_host_token', '{token}');
            localStorage.setItem('gari_token', '{token}');
        }}""")
        await mobile_page.goto("http://localhost:8000/frontend2/expert-portal.html")
        await mobile_page.wait_for_selector("#expertWorkspace", timeout=15000)
        await asyncio.sleep(1)
        await mobile_page.screenshot(path="tests/screenshots/expansion_06_expert_portal_mobile_390.png")
        print("PASS: Mobile Responsive Expert Portal verified")

        await browser.close()
        print("=== PLAYWRIGHT E2E TESTS COMPLETED WITH 100% SUCCESS ===")

if __name__ == "__main__":
    asyncio.run(run_e2e())
