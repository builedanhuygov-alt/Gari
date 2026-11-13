import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import gari_auth
token = gari_auth.create_session(user_id=1)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()

    ctx.add_cookies([
        {"name": "access_token", "value": token, "domain": "localhost", "path": "/"}
    ])
    page = ctx.new_page()

    # Navigate to login page first to set localStorage on localhost origin
    page.goto("http://localhost:8000/frontend2/login.html")
    page.evaluate(f"localStorage.setItem('gari_token', '{token}');")

    # Now navigate to index.html
    page.goto("http://localhost:8000/frontend2/index.html")
    page.wait_for_timeout(2500)

    print("PAGE TITLE:", page.title())
    print("URL:", page.url)

    h1_h2 = [el.inner_text().strip() for el in page.query_selector_all("h1, h2, h3")]
    print("\nHEADINGS:", h1_h2[:10])

    navs = [el.inner_text().strip() for el in page.query_selector_all("nav a, aside a, .sidebar a")]
    print("\nSIDEBAR NAV:", navs[:15])

    shot = ROOT_DIR / "tests" / "screenshots" / "frontend2_index_loaded.png"
    page.screenshot(path=str(shot), full_page=True)
    print(f"Screenshot saved to {shot}")

    browser.close()
