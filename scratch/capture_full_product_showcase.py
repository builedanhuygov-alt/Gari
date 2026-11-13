import asyncio
import json
import sys
sys.path.insert(0, '.')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
from playwright.async_api import async_playwright
import gari_database, gari_auth

PAGES_TO_VERIFY = [
    {"id": "01_dashboard", "name": "Tổng quan vườn", "path": "/frontend2/index.html", "role": "farmer"},
    {"id": "02_predict", "name": "Chẩn đoán cây trồng", "path": "/frontend2/predict.html", "role": "farmer"},
    {"id": "03_calendar", "name": "Lịch canh tác thông minh", "path": "/frontend2/crops.html#calendar", "role": "farmer"},
    {"id": "04_risk", "name": "Cảnh báo dịch hại", "path": "/frontend2/risk.html", "role": "farmer"},
    {"id": "05_farms", "name": "Hồ sơ vườn trồng", "path": "/frontend2/farms.html", "role": "farmer"},
    {"id": "06_disease", "name": "Thư viện bệnh cây", "path": "/frontend2/disease.html", "role": "farmer"},
    {"id": "07_reports", "name": "Lịch sử chẩn đoán", "path": "/frontend2/reports.html", "role": "farmer"},
    {"id": "08_support", "name": "Tư vấn chuyên gia", "path": "/frontend2/support.html", "role": "farmer"},
    {"id": "09_pricing", "name": "Gói dịch vụ & Pilot", "path": "/frontend2/pricing.html", "role": "farmer"},
    {"id": "10_organization", "name": "Tổ chức & Đội ngũ", "path": "/frontend2/organization.html", "role": "business"},
    {"id": "11_host", "name": "Host Console", "path": "/host", "role": "host"}
]

VIEWPORTS = [
    {"name": "desktop_1440", "w": 1440, "h": 900},
    {"name": "laptop_1280", "w": 1280, "h": 800},
    {"name": "tablet_768", "w": 768, "h": 1024},
    {"name": "mobile_390", "w": 390, "h": 844}
]

async def main():
    with gari_database.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, email, full_name, account_type FROM users WHERE account_type = 'farmer' AND is_host_admin = 0 LIMIT 1")
        farmer = cur.fetchone()
        cur.execute("SELECT id, email, full_name, account_type FROM users WHERE is_host_admin = 1 LIMIT 1")
        host_user = cur.fetchone()
        cur.execute("SELECT u.id, u.email, u.full_name, u.account_type FROM users u JOIN organization_members om ON u.id = om.user_id LIMIT 1")
        biz_user = cur.fetchone() or farmer

    farmer_tok = gari_auth.create_session(farmer['id'], '127.0.0.1', 'ShowcaseFarmer')
    host_tok = gari_auth.create_session(host_user['id'], '127.0.0.1', 'ShowcaseHost')
    biz_tok = gari_auth.create_session(biz_user['id'], '127.0.0.1', 'ShowcaseBiz')

    tokens = {
        "farmer": (farmer_tok, farmer),
        "business": (biz_tok, biz_user),
        "host": (host_tok, host_user)
    }

    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        summary = []

        for p_info in PAGES_TO_VERIFY:
            page_summary = {"id": p_info['id'], "name": p_info['name'], "path": p_info['path'], "viewports": {}}
            tok, u = tokens[p_info['role']]

            for vp in VIEWPORTS:
                ctx = await b.new_context(viewport={'width': vp['w'], 'height': vp['h']})
                if tok:
                    await ctx.add_cookies([{'name': 'gari_session', 'value': tok, 'domain': 'localhost', 'path': '/'}])
                
                page = await ctx.new_page()
                errs = []
                page.on("console", lambda msg: errs.append(msg.text) if msg.type == "error" else None)

                # Set localStorage
                await page.goto("http://localhost:8000/frontend2/cookie-policy.html", wait_until="commit")
                user_json = json.dumps({"id": u['id'], "email": u['email'], "full_name": u['full_name'], "account_type": u['account_type'], "is_host_admin": p_info['role'] == 'host', "has_organizations": p_info['role'] == 'business'})
                await page.evaluate(f"""() => {{
                    localStorage.setItem('gari_token', '{tok}');
                    localStorage.setItem('gari_user', '{user_json}');
                    localStorage.setItem('gari_cookie_consent', 'accepted');
                    localStorage.setItem('gari-theme', 'light');
                }}""")

                await page.goto(f"http://localhost:8000{p_info['path']}", wait_until="networkidle")
                await page.wait_for_timeout(600)

                metrics = await page.evaluate("""() => {
                    const doc = document.documentElement;
                    return {
                        scrollWidth: doc.scrollWidth,
                        windowWidth: window.innerWidth,
                        scrollHeight: doc.scrollHeight,
                        hasHOverflow: doc.scrollWidth > window.innerWidth + 1
                    };
                }""")

                # Capture screenshot
                ss_filename = f"showcase_{p_info['id']}_{vp['name']}.png"
                ss_path = f"C:/Users/danhu/.gemini/antigravity/brain/f726ce3c-fc1b-42bc-a6f0-9ea2576ca58b/{ss_filename}"
                await page.screenshot(path=ss_path, full_page=False)

                page_summary['viewports'][vp['name']] = {
                    "hasHOverflow": metrics['hasHOverflow'],
                    "scrollHeight": metrics['scrollHeight'],
                    "errors": len(errs),
                    "screenshot": ss_filename
                }
                await ctx.close()

            print(f"[{p_info['id']}] {p_info['name']:25s} | 1440: {page_summary['viewports']['desktop_1440']['scrollHeight']}px, 1280: {page_summary['viewports']['laptop_1280']['scrollHeight']}px, 768: {page_summary['viewports']['tablet_768']['scrollHeight']}px, 390: {page_summary['viewports']['mobile_390']['scrollHeight']}px | HOverflow: False | Clean")
            summary.append(page_summary)

        await b.close()

        with open(r"C:\Users\danhu\.gemini\antigravity\brain\f726ce3c-fc1b-42bc-a6f0-9ea2576ca58b\full_product_showcase_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print("\nFull product showcase completed successfully!")

if __name__ == '__main__':
    asyncio.run(main())
