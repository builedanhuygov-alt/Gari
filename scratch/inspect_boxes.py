import asyncio, json, sys
sys.path.insert(0, '.')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
from playwright.async_api import async_playwright
import gari_database, gari_auth

async def inspect():
    with gari_database.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE account_type = 'farmer' LIMIT 1")
        uid = cur.fetchone()['id']
    tok = gari_auth.create_session(uid, '127.0.0.1', 'inspect')
    
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(viewport={'width': 1280, 'height': 900})
        await ctx.add_cookies([{'name': 'gari_session', 'value': tok, 'domain': 'localhost', 'path': '/'}])
        page = await ctx.new_page()
        await page.goto('http://localhost:8000/frontend2/cookie-policy.html')
        await page.evaluate(f"() => localStorage.setItem('gari_token', '{tok}')")
        await page.goto('http://localhost:8000/frontend2/risk.html', wait_until='networkidle')
        await page.wait_for_timeout(1000)
        
        info = await page.evaluate('''() => {
            const getBox = el => el ? {
                tag: el.tagName,
                cls: el.className,
                top: Math.round(el.getBoundingClientRect().top),
                bottom: Math.round(el.getBoundingClientRect().bottom),
                height: el.offsetHeight,
                marginTop: window.getComputedStyle(el).marginTop,
                marginBottom: window.getComputedStyle(el).marginBottom,
                padding: window.getComputedStyle(el).padding
            } : null;
            
            return {
                windowInnerHeight: window.innerHeight,
                documentScrollHeight: document.documentElement.scrollHeight,
                pageHead: getBox(document.querySelector('.page-head')),
                weatherBar: getBox(document.querySelector('.card')),
                grid: getBox(document.querySelector('.content-body > div:last-of-type')),
                alertsCard: getBox(document.querySelector('.alerts-list')?.closest('.card')),
                methodologyCard: getBox(document.querySelector('.card h3')?.closest('.card')),
                ipmCard: getBox(document.querySelector('.card h4')?.closest('.card')),
                footer: getBox(document.getElementById('appLegalFooter')),
                contentBody: getBox(document.querySelector('.content-body'))
            };
        }''')
        print(json.dumps(info, indent=2))
        await b.close()

asyncio.run(inspect())
