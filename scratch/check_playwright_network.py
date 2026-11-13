import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from playwright.async_api import async_playwright
import gari_database, gari_auth

async def check():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page()
        page.on('response', lambda res: print(f'RESP {res.status}: {res.url}') if res.status >= 400 else None)
        token = gari_auth.create_session(1)
        await page.goto('http://localhost:8000/frontend2/host-login.html')
        await page.evaluate(f"""() => {{
            localStorage.setItem('gari_host_token', '{token}');
            localStorage.setItem('gari_token', '{token}');
        }}""")
        await page.goto('http://localhost:8000/frontend2/host.html')
        await asyncio.sleep(2)
        print("Clicking tab-experts...")
        await page.click('button[data-tab="tab-experts"]')
        await asyncio.sleep(2)
        print("Evaluating /api/host/ai/test...")
        res_text = await page.evaluate('''async () => {
            try {
                const res = await fetch('/api/host/ai/test', {
                    method: 'POST',
                    headers: getAuthHeaders(),
                    credentials: 'include'
                });
                return { status: res.status, data: await res.json() };
            } catch(e) {
                return { error: e.toString() };
            }
        }''')
        print('AI Test eval result:', res_text)
        await b.close()

if __name__ == "__main__":
    asyncio.run(check())
