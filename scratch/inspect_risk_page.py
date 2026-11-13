import sys
sys.path.insert(0, '.')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
import asyncio
import json
import sys
from playwright.async_api import async_playwright
import gari_database, gari_auth

async def main():
    with gari_database.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, email, full_name, account_type FROM users WHERE account_type = 'farmer' AND is_host_admin = 0 LIMIT 1")
        farmer = cur.fetchone()

    farmer_tok = gari_auth.create_session(farmer['id'], '127.0.0.1', 'Playwright')

    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        for w in [1440, 1280, 768, 390]:
            ctx = await b.new_context(viewport={'width': w, 'height': 900})
            await ctx.add_cookies([{'name': 'gari_session', 'value': farmer_tok, 'domain': 'localhost', 'path': '/'}])
            page = await ctx.new_page()
            
            # Go to cookie policy first to set localStorage
            await page.goto("http://localhost:8000/frontend2/cookie-policy.html", wait_until="commit")
            user_json = json.dumps({"id": farmer['id'], "email": farmer['email'], "full_name": farmer['full_name'], "account_type": farmer['account_type'], "is_host_admin": False})
            await page.evaluate(f"""() => {{
                localStorage.setItem('gari_token', '{farmer_tok}');
                localStorage.setItem('gari_user', '{user_json}');
                localStorage.setItem('gari_cookie_consent', 'accepted');
                localStorage.setItem('gari-theme', 'light');
            }}""")
            
            await page.goto("http://localhost:8000/frontend2/risk.html", wait_until="networkidle")
            await page.wait_for_timeout(1000)
            
            metrics = await page.evaluate("""() => {
                const body = document.body;
                const contentBody = document.querySelector('.content-body');
                const appShell = document.querySelector('.app-shell');
                const appMain = document.querySelector('.app-main');
                const pageHead = document.querySelector('.page-head');
                const cards = Array.from(document.querySelectorAll('.card')).map(c => ({
                    title: c.querySelector('.card-title, h3, h4')?.textContent?.trim() || 'card',
                    height: c.offsetHeight,
                    padding: window.getComputedStyle(c).padding,
                    marginBottom: window.getComputedStyle(c).marginBottom
                }));
                const alertsList = document.querySelector('.alerts-list');
                const alertCards = Array.from(document.querySelectorAll('.alert-card')).map(a => ({
                    region: a.querySelector('.alert-title')?.textContent?.trim(),
                    height: a.offsetHeight,
                    padding: window.getComputedStyle(a).padding,
                    marginBottom: window.getComputedStyle(a).marginBottom
                }));
                
                return {
                    url: window.location.href,
                    windowHeight: window.innerHeight,
                    documentScrollHeight: document.documentElement.scrollHeight,
                    bodyScrollHeight: body.scrollHeight,
                    contentBodyHeight: contentBody ? contentBody.offsetHeight : null,
                    pageHeadHeight: pageHead ? pageHead.offsetHeight : null,
                    appMainHeight: appMain ? appMain.offsetHeight : null,
                    cards,
                    alertCardsCount: alertCards.length,
                    alertCards: alertCards
                };
            }""")
            print(f"Viewport {w}px: scrollHeight={metrics['documentScrollHeight']}, contentBodyHeight={metrics['contentBodyHeight']}")
            print("PageHead height:", metrics['pageHeadHeight'])
            print("Cards:", json.dumps(metrics['cards'], indent=2, ensure_ascii=False))
            print("AlertCards:", json.dumps(metrics['alertCards'], indent=2, ensure_ascii=False))
            
            # Save screenshot
            await page.screenshot(path=f"C:/Users/danhu/.gemini/antigravity/brain/f726ce3c-fc1b-42bc-a6f0-9ea2576ca58b/risk_before_{w}.png", full_page=True)
            await ctx.close()
            
        await b.close()

if __name__ == '__main__':
    asyncio.run(main())
