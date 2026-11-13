import asyncio
import json
import sys
sys.path.insert(0, '.')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
from playwright.async_api import async_playwright
import gari_database, gari_auth

PAGES = [
    {"name": "Dashboard", "path": "/frontend2/index.html", "role": "farmer"},
    {"name": "AI Diagnosis", "path": "/frontend2/predict.html", "role": "farmer"},
    {"name": "Cultivation Calendar", "path": "/frontend2/crops.html#calendar", "role": "farmer"},
    {"name": "Crop Library", "path": "/frontend2/crops.html", "role": "farmer"},
    {"name": "Pest Risk", "path": "/frontend2/risk.html", "role": "farmer"},
    {"name": "Farms & Plots", "path": "/frontend2/farms.html", "role": "farmer"},
    {"name": "Disease Library", "path": "/frontend2/disease.html", "role": "farmer"},
    {"name": "Diagnosis History", "path": "/frontend2/reports.html", "role": "farmer"},
    {"name": "Expert Consultation", "path": "/frontend2/support.html", "role": "farmer"},
    {"name": "B2B Organization", "path": "/frontend2/organization.html", "role": "business"},
    {"name": "Host Console", "path": "/host", "role": "host"}
]

VIEWPORTS = [
    {"name": "1440_desktop", "w": 1440, "h": 900},
    {"name": "1280_laptop", "w": 1280, "h": 800},
    {"name": "1024_tablet_landscape", "w": 1024, "h": 768},
    {"name": "768_tablet_portrait", "w": 768, "h": 1024},
    {"name": "390_mobile", "w": 390, "h": 844},
    {"name": "360_small_mobile", "w": 360, "h": 740}
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

    farmer_tok = gari_auth.create_session(farmer['id'], '127.0.0.1', 'VPTestFarmer')
    host_tok = gari_auth.create_session(host_user['id'], '127.0.0.1', 'VPTestHost')
    biz_tok = gari_auth.create_session(biz_user['id'], '127.0.0.1', 'VPTestBiz')

    tokens = {
        "farmer": (farmer_tok, farmer),
        "business": (biz_tok, biz_user),
        "host": (host_tok, host_user)
    }

    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        all_results = []
        overflow_failures = []
        console_failures = []

        for p_info in PAGES:
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
                user_json = json.dumps({
                    "id": u['id'], "email": u['email'], "full_name": u['full_name'], 
                    "account_type": u['account_type'], "is_host_admin": p_info['role'] == 'host', 
                    "has_organizations": p_info['role'] == 'business'
                })
                await page.evaluate(f"""() => {{
                    localStorage.setItem('gari_token', '{tok}');
                    localStorage.setItem('gari_user', '{user_json}');
                    localStorage.setItem('gari_cookie_consent', 'accepted');
                    localStorage.setItem('gari-theme', 'light');
                }}""")

                await page.goto(f"http://localhost:8000{p_info['path']}", wait_until="networkidle")
                await page.wait_for_timeout(500)

                metrics = await page.evaluate("""() => {
                    const doc = document.documentElement;
                    return {
                        scrollWidth: doc.scrollWidth,
                        windowWidth: window.innerWidth,
                        scrollHeight: doc.scrollHeight,
                        hasHOverflow: doc.scrollWidth > window.innerWidth + 1
                    };
                }""")

                if metrics['hasHOverflow']:
                    overflow_failures.append(f"{p_info['name']} at {vp['name']}: scrollWidth={metrics['scrollWidth']}, winWidth={metrics['windowWidth']}")
                if errs:
                    console_failures.append(f"{p_info['name']} at {vp['name']}: {errs}")

                all_results.append({
                    "page": p_info['name'],
                    "path": p_info['path'],
                    "viewport": vp['name'],
                    "width": vp['w'],
                    "height": vp['h'],
                    "scrollWidth": metrics['scrollWidth'],
                    "scrollHeight": metrics['scrollHeight'],
                    "hasHOverflow": metrics['hasHOverflow'],
                    "errors": len(errs)
                })
                await ctx.close()

            print(f"Tested {p_info['name']} across all 6 viewports.")

        await b.close()

        print("\n================== VERIFICATION SUMMARY ==================")
        print(f"Total viewport checks: {len(all_results)} (11 pages x 6 viewports)")
        print(f"Horizontal Overflow Failures: {len(overflow_failures)}")
        if overflow_failures:
            for f in overflow_failures:
                print("  ❌", f)
        else:
            print("  ✅ 100% PASS: 0 horizontal overflow across all 66 combinations!")

        print(f"Console Error Failures: {len(console_failures)}")
        if console_failures:
            for f in console_failures:
                print("  ❌", f)
        else:
            print("  ✅ 100% PASS: 0 console errors across all 66 combinations!")

        with open(r"C:\Users\danhu\.gemini\antigravity\brain\f726ce3c-fc1b-42bc-a6f0-9ea2576ca58b\viewports_6_verification_summary.json", "w", encoding="utf-8") as f:
            json.dump({
                "total_checks": len(all_results),
                "overflow_failures": overflow_failures,
                "console_failures": console_failures,
                "results": all_results
            }, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    asyncio.run(main())
