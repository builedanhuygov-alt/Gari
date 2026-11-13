import asyncio
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    import gari_auth
    token = gari_auth.create_session(user_id=1)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        await context.add_cookies([
            {"name": "gari_session", "value": token, "domain": "localhost", "path": "/"}
        ])
        await context.add_init_script(f"""
            localStorage.setItem('gari_token', '{token}');
            localStorage.setItem('gari_user', JSON.stringify({{ id: 1, email: 'danhuynh@gari.vn', name: 'Đan Huỳnh', role: 'admin' }}));
        """)

        page = await context.new_page()
        page.on("console", lambda msg: print(f"BROWSER CONSOLE [{msg.type}]: {msg.text}"))

        await page.goto("http://localhost:8000/frontend2/predict.html", wait_until="networkidle")

        # Select manual crop 'tomato' so inference is guaranteed fast and direct
        await page.click("#btnModeManual")
        await page.evaluate("() => document.getElementById('cropSelect').value = 'tomato'")
        await page.wait_for_timeout(300)

        print("Setting file input...")
        await page.set_input_files("#fileInput", "test_leaf.jpg")
        await page.wait_for_timeout(600)

        print("Clicking #btnPredict...")
        await page.click("#btnPredict")

        print("Waiting for #activeResultCard or failure card...")
        # Wait up to 30s
        for _ in range(60):
            await page.wait_for_timeout(500)
            vis = await page.evaluate("""() => {
                const a = document.getElementById('activeResultCard');
                const v = document.getElementById('leafValidationFailureCard');
                const r = document.getElementById('rejectionCard');
                const i = document.getElementById('infoNoticeCard');
                const c = document.getElementById('cropConfirmationCard');
                return {
                    active: a && window.getComputedStyle(a).display !== 'none',
                    valFail: v && window.getComputedStyle(v).display !== 'none',
                    reject: r && window.getComputedStyle(r).display !== 'none',
                    info: i && window.getComputedStyle(i).display !== 'none',
                    cropConf: c && window.getComputedStyle(c).display !== 'none'
                };
            }""")
            if any(vis.values()):
                print("Card appeared!", vis)
                break

        # Check recommendation buttons
        rec_btns = await page.query_selector_all(".btn-create-task-from-rec")
        print(f"Found {len(rec_btns)} .btn-create-task-from-rec buttons")
        if rec_btns:
            await rec_btns[0].click()
            await page.wait_for_timeout(600)
            btn_txt = await rec_btns[0].inner_text()
            print(f"Button text after click: '{btn_txt}'")

        await page.screenshot(path="scratch/predict_success.png")
        print("Saved scratch/predict_success.png")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
