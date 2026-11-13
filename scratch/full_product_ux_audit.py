import asyncio
import json
import sys
sys.path.insert(0, '.')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
from playwright.async_api import async_playwright
import gari_database, gari_auth

PAGES_TO_AUDIT = [
    {"name": "Dashboard", "path": "/frontend2/index.html", "role": "farmer"},
    {"name": "Chẩn đoán cây trồng", "path": "/frontend2/predict.html", "role": "farmer"},
    {"name": "Kiểm tra sức khỏe lá", "path": "/frontend2/predict.html?mode=leaf", "role": "farmer"},
    {"name": "Hồ sơ vườn trồng", "path": "/frontend2/farms.html", "role": "farmer"},
    {"name": "Lịch sử chẩn đoán", "path": "/frontend2/reports.html", "role": "farmer"},
    {"name": "Thư viện cây trồng", "path": "/frontend2/crops.html", "role": "farmer"},
    {"name": "Lịch canh tác (Tab)", "path": "/frontend2/crops.html#calendar", "role": "farmer"},
    {"name": "Lịch canh tác (Standalone)", "path": "/frontend2/calendar.html", "role": "farmer"},
    {"name": "Thư viện bệnh cây", "path": "/frontend2/disease.html", "role": "farmer"},
    {"name": "Giám sát nguy cơ", "path": "/frontend2/risk.html", "role": "farmer"},
    {"name": "Tư vấn chuyên gia", "path": "/frontend2/support.html", "role": "farmer"},
    {"name": "Thu thập thực địa", "path": "/frontend2/collect.html", "role": "farmer"},
    {"name": "Gói dịch vụ & Pilot", "path": "/frontend2/pricing.html", "role": "farmer"},
    {"name": "Tổ chức & Đội ngũ", "path": "/frontend2/organization.html", "role": "business"},
    {"name": "B2B Onboarding", "path": "/frontend2/onboarding.html", "role": "business"},
    {"name": "B2B Chỉ số & Quản trị", "path": "/frontend2/admin.html", "role": "business"},
    {"name": "Cài đặt tài khoản", "path": "/frontend2/settings.html", "role": "farmer"},
    {"name": "Quản lý dữ liệu & GDPR", "path": "/frontend2/data-management.html", "role": "farmer"},
    {"name": "Host Console", "path": "/host", "role": "host"},
    {"name": "Landing page", "path": "/frontend2/landing.html", "role": "guest"},
    {"name": "Login", "path": "/frontend2/login.html", "role": "guest"},
    {"name": "Register", "path": "/frontend2/register.html", "role": "guest"},
]

async def audit():
    with gari_database.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, email, full_name, account_type FROM users WHERE account_type = 'farmer' AND is_host_admin = 0 LIMIT 1")
        farmer = cur.fetchone()
        cur.execute("SELECT id, email, full_name, account_type FROM users WHERE is_host_admin = 1 LIMIT 1")
        host_user = cur.fetchone()
        cur.execute("SELECT u.id, u.email, u.full_name, u.account_type FROM users u JOIN organization_members om ON u.id = om.user_id LIMIT 1")
        biz_user = cur.fetchone() or farmer

    farmer_tok = gari_auth.create_session(farmer['id'], '127.0.0.1', 'AuditFarmer')
    host_tok = gari_auth.create_session(host_user['id'], '127.0.0.1', 'AuditHost')
    biz_tok = gari_auth.create_session(biz_user['id'], '127.0.0.1', 'AuditBiz')

    tokens = {
        "farmer": (farmer_tok, farmer),
        "business": (biz_tok, biz_user),
        "host": (host_tok, host_user),
        "guest": (None, None)
    }

    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        audit_results = []

        for item in PAGES_TO_AUDIT:
            ctx = await b.new_context(viewport={'width': 1280, 'height': 800})
            tok, u = tokens[item['role']]
            
            if tok:
                await ctx.add_cookies([{'name': 'gari_session', 'value': tok, 'domain': 'localhost', 'path': '/'}])

            page = await ctx.new_page()
            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

            if tok:
                await page.goto("http://localhost:8000/frontend2/cookie-policy.html", wait_until="commit")
                user_json = json.dumps({"id": u['id'], "email": u['email'], "full_name": u['full_name'], "account_type": u['account_type'], "is_host_admin": item['role'] == 'host'})
                await page.evaluate(f"""() => {{
                    localStorage.setItem('gari_token', '{tok}');
                    localStorage.setItem('gari_user', '{user_json}');
                    localStorage.setItem('gari_cookie_consent', 'accepted');
                    localStorage.setItem('gari-theme', 'light');
                }}""")

            target_url = f"http://localhost:8000{item['path']}"
            resp = await page.goto(target_url, wait_until="networkidle")
            await page.wait_for_timeout(500)

            status_code = resp.status if resp else 0
            page_data = await page.evaluate("""() => {
                const doc = document.documentElement;
                const h1 = document.querySelector('h1')?.textContent?.trim() || 'NO H1';
                const hasAppShell = !!document.querySelector('.app-shell');
                const hasSidebar = !!document.querySelector('#appSidebar');
                const hasTopbar = !!document.querySelector('#appTopbar');
                const activeNav = document.querySelector('.nav-link.active')?.dataset.key || 'NONE';
                const hasHOverflow = doc.scrollWidth > window.innerWidth + 1;
                const cardsCount = document.querySelectorAll('.card').length;
                const tablesCount = document.querySelectorAll('table').length;
                const modalsCount = document.querySelectorAll('.modal, [id*="Modal"]').length;
                const hasSkeleton = document.querySelectorAll('.skeleton').length > 0;
                
                return {
                    title: document.title,
                    h1,
                    hasAppShell,
                    hasSidebar,
                    hasTopbar,
                    activeNav,
                    hasHOverflow,
                    scrollWidth: doc.scrollWidth,
                    windowWidth: window.innerWidth,
                    scrollHeight: doc.scrollHeight,
                    cardsCount,
                    tablesCount,
                    modalsCount,
                    hasSkeleton
                };
            }""")

            res = {
                "name": item['name'],
                "path": item['path'],
                "role": item['role'],
                "status_code": status_code,
                "errors": console_errors,
                **page_data
            }
            audit_results.append(res)
            print(f"[{status_code}] {item['name']:25s} | H1: {page_data['h1'][:28]:28s} | Nav: {page_data['activeNav']:10s} | HOverflow: {page_data['hasHOverflow']} | Errors: {len(console_errors)}")
            await ctx.close()

        await b.close()

        with open(r"C:\Users\danhu\.gemini\antigravity\brain\f726ce3c-fc1b-42bc-a6f0-9ea2576ca58b\full_product_ux_audit.json", "w", encoding="utf-8") as f:
            json.dump(audit_results, f, indent=2, ensure_ascii=False)
        print("\nAudit completed and saved to full_product_ux_audit.json")

if __name__ == '__main__':
    asyncio.run(audit())
