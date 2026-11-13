import asyncio, json, sys
sys.path.insert(0, '.')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
from playwright.async_api import async_playwright
import gari_database, gari_auth

PAGES = [
    ("predict", "/frontend2/predict.html"),
    ("farms", "/frontend2/farms.html"),
    ("reports", "/frontend2/reports.html"),
    ("disease", "/frontend2/disease.html"),
    ("crops", "/frontend2/crops.html"),
    ("support", "/frontend2/support.html"),
    ("pricing", "/frontend2/pricing.html"),
    ("organization", "/frontend2/organization.html"),
    ("admin", "/frontend2/admin.html"),
    ("settings", "/frontend2/settings.html")
]

async def inspect():
    with gari_database.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, email, full_name, account_type FROM users WHERE account_type = 'farmer' LIMIT 1")
        farmer = cur.fetchone()
        cur.execute("SELECT u.id, u.email, u.full_name, u.account_type FROM users u JOIN organization_members om ON u.id = om.user_id LIMIT 1")
        biz = cur.fetchone() or farmer

    tok = gari_auth.create_session(biz['id'], '127.0.0.1', 'Inspect')

    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(viewport={'width': 1280, 'height': 800})
        await ctx.add_cookies([{'name': 'gari_session', 'value': tok, 'domain': 'localhost', 'path': '/'}])
        page = await ctx.new_page()

        await page.goto("http://localhost:8000/frontend2/cookie-policy.html", wait_until="commit")
        user_json = json.dumps({"id": biz['id'], "email": biz['email'], "full_name": biz['full_name'], "account_type": biz['account_type'], "has_organizations": True, "organizations": [{"id": 1, "name": "HTX Ba Vì"}]})
        await page.evaluate(f"""() => {{
            localStorage.setItem('gari_token', '{tok}');
            localStorage.setItem('gari_user', '{user_json}');
            localStorage.setItem('gari_cookie_consent', 'accepted');
            localStorage.setItem('gari-theme', 'light');
        }}""")

        results = {}
        for name, path in PAGES:
            await page.goto(f"http://localhost:8000{path}", wait_until="networkidle")
            await page.wait_for_timeout(600)
            
            data = await page.evaluate("""() => {
                const getBox = sel => {
                    const el = document.querySelector(sel);
                    return el ? { height: el.offsetHeight, width: el.offsetWidth } : null;
                };
                return {
                    title: document.title,
                    h1: document.querySelector('h1')?.textContent?.trim(),
                    pageHead: getBox('.page-head, .risk-head'),
                    contentBody: getBox('.content-body'),
                    cardsCount: document.querySelectorAll('.card').length,
                    buttonsCount: document.querySelectorAll('.btn, button').length,
                    tablesCount: document.querySelectorAll('table').length,
                    hasOverflow: document.documentElement.scrollWidth > window.innerWidth
                };
            }""")
            results[name] = data
            # Also capture screenshot
            await page.screenshot(path=f"C:/Users/danhu/.gemini/antigravity/brain/f726ce3c-fc1b-42bc-a6f0-9ea2576ca58b/inspect_{name}_1280.png")
            print(f"[{name:12s}] H1: {data['h1'][:30] if data['h1'] else 'NONE':30s} | Cards: {data['cardsCount']:2d} | Tables: {data['tablesCount']} | HOverflow: {data['hasOverflow']}")

        await ctx.close()
        await b.close()

if __name__ == '__main__':
    asyncio.run(inspect())
