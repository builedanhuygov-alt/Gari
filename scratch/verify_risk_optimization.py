import asyncio
import json
import sys
sys.path.insert(0, '.')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
from playwright.async_api import async_playwright
import gari_database, gari_auth

async def main():
    with gari_database.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, email, full_name, account_type FROM users WHERE account_type = 'farmer' AND is_host_admin = 0 LIMIT 1")
        farmer = cur.fetchone()

    farmer_tok = gari_auth.create_session(farmer['id'], '127.0.0.1', 'Playwright')

    viewports = [
        {"name": "desktop_1440", "w": 1440, "h": 900},
        {"name": "laptop_1280", "w": 1280, "h": 800},
        {"name": "tablet_768", "w": 768, "h": 1024},
        {"name": "mobile_390", "w": 390, "h": 844}
    ]

    console_errors = []

    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        results = {}

        for vp in viewports:
            ctx = await b.new_context(viewport={'width': vp['w'], 'height': vp['h']})
            await ctx.add_cookies([{'name': 'gari_session', 'value': farmer_tok, 'domain': 'localhost', 'path': '/'}])
            page = await ctx.new_page()

            page.on("console", lambda msg: console_errors.append(f"[{vp['name']}] {msg.type}: {msg.text}") if msg.type in ["error"] else None)

            # Pre-set localStorage
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

            # Metrics
            data = await page.evaluate("""() => {
                const doc = document.documentElement;
                const body = document.body;
                const hasHOverflow = doc.scrollWidth > window.innerWidth + 1;
                const contentBody = document.querySelector('.content-body');
                const weatherCard = document.querySelector('.risk-weather-card');
                const alertsList = document.querySelector('#alertsList');
                const alertCards = Array.from(document.querySelectorAll('.alert-card')).map(a => ({
                    title: a.querySelector('.alert-title')?.textContent?.trim(),
                    threat: a.querySelector('.alert-threat-inline')?.textContent?.trim(),
                    pill: a.querySelector('.pill')?.textContent?.trim(),
                    height: a.offsetHeight
                }));
                const methodology = document.querySelector('.methodology-items');
                const ipmBtn = document.querySelector('.risk-ipm-box a');
                const footer = document.getElementById('appLegalFooter');
                
                return {
                    windowInnerWidth: window.innerWidth,
                    windowInnerHeight: window.innerHeight,
                    documentScrollWidth: doc.scrollWidth,
                    documentScrollHeight: doc.scrollHeight,
                    hasHorizontalOverflow: hasHOverflow,
                    contentBodyHeight: contentBody ? contentBody.offsetHeight : null,
                    weatherCardHeight: weatherCard ? weatherCard.offsetHeight : null,
                    alertCardsCount: alertCards.length,
                    alertCards: alertCards,
                    methodologyHeight: methodology ? methodology.offsetHeight : null,
                    ipmBtnHref: ipmBtn ? ipmBtn.getAttribute('href') : null,
                    ipmBtnVisible: ipmBtn ? ipmBtn.offsetParent !== null : false,
                    footerTop: footer ? Math.round(footer.getBoundingClientRect().top) : null,
                    footerHeight: footer ? footer.offsetHeight : null
                };
            }""")

            results[vp['name']] = data
            ss_path = f"C:/Users/danhu/.gemini/antigravity/brain/f726ce3c-fc1b-42bc-a6f0-9ea2576ca58b/risk_repaired_{vp['name']}.png"
            await page.screenshot(path=ss_path, full_page=True)
            print(f"=== {vp['name']} ({vp['w']}x{vp['h']}) ===")
            print(f"ScrollHeight: {data['documentScrollHeight']}px (content: {data['contentBodyHeight']}px)")
            print(f"Weather Card Height: {data['weatherCardHeight']}px")
            print(f"Alert cards count: {data['alertCardsCount']}, Heights: {[c['height'] for c in data['alertCards']]}")
            print(f"Horizontal Overflow: {data['hasHorizontalOverflow']}")
            print(f"IPM button visible & valid: {data['ipmBtnVisible']} ({data['ipmBtnHref']})")
            print(f"Screenshot saved: {ss_path}")

            await ctx.close()

        await b.close()

        print("\n=== Console Errors ===")
        print(console_errors if console_errors else "None (Clean)")

        with open(r"C:\Users\danhu\.gemini\antigravity\brain\f726ce3c-fc1b-42bc-a6f0-9ea2576ca58b\risk_optimization_report.json", "w", encoding="utf-8") as f:
            json.dump({"results": results, "console_errors": console_errors}, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    asyncio.run(main())
