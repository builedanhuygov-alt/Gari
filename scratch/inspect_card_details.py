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
        ctx = await b.new_context(viewport={'width': 390, 'height': 800})
        await ctx.add_cookies([{'name': 'gari_session', 'value': tok, 'domain': 'localhost', 'path': '/'}])
        page = await ctx.new_page()
        await page.goto('http://localhost:8000/frontend2/cookie-policy.html')
        await page.evaluate(f"() => localStorage.setItem('gari_token', '{tok}')")
        await page.goto('http://localhost:8000/frontend2/risk.html', wait_until='networkidle')
        await page.wait_for_timeout(1000)
        
        info = await page.evaluate('''() => {
            const card = document.querySelector('.alert-card');
            if (!card) return null;
            const list = document.querySelector('.alerts-list');
            const parentCard = list.closest('.card');
            const grid = parentCard.parentElement;
            return {
                windowWidth: window.innerWidth,
                gridDisplay: window.getComputedStyle(grid).display,
                gridTemplateColumns: window.getComputedStyle(grid).gridTemplateColumns,
                gridWidth: grid.offsetWidth,
                parentCardWidth: parentCard.offsetWidth,
                listWidth: list.offsetWidth,
                cardWidth: card.offsetWidth,
                cardHtml: card.outerHTML,
                cardStyles: {
                    height: card.offsetHeight,
                    lineHeight: window.getComputedStyle(card).lineHeight,
                    padding: window.getComputedStyle(card).padding,
                    margin: window.getComputedStyle(card).margin
                },
                children: Array.from(card.children).map(c => ({
                    tag: c.tagName,
                    text: c.textContent.trim().substring(0, 50),
                    height: c.offsetHeight,
                    margin: window.getComputedStyle(c).margin,
                    padding: window.getComputedStyle(c).padding,
                    fontSize: window.getComputedStyle(c).fontSize,
                    lineHeight: window.getComputedStyle(c).lineHeight
                }))
            };
        }''')
        print(json.dumps(info, indent=2, ensure_ascii=False))
        await b.close()

asyncio.run(inspect())
