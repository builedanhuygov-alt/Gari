import asyncio, sys
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path('.').resolve()
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    import gari_auth
    token = gari_auth.create_session(user_id=1)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await context.add_cookies([{'name': 'gari_session', 'value': token, 'domain': 'localhost', 'path': '/'}])
        page = await context.new_page()
        await page.goto('http://localhost:8000/frontend2/predict.html')
        await page.click('#btnModeManual')
        await page.evaluate("() => document.getElementById('cropSelect').value = 'tomato'")
        await page.set_input_files('#fileInput', 'test_leaf.jpg')
        await page.click('#btnPredict')
        await page.wait_for_selector('#activeResultCard', timeout=15000)
        
        html = await page.inner_html('#repRecommendationsList')
        print('repRecommendationsList innerHTML:')
        print(html)
        await browser.close()

asyncio.run(main())
