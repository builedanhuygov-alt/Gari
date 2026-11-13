import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import gari_auth

token = gari_auth.create_session(user_id=1)
out_dir = ROOT_DIR / "tests" / "screenshots" / "audit"
out_dir.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_cookies([
        {"name": "access_token", "value": token, "domain": "localhost", "path": "/"}
    ])
    page = ctx.new_page()

    # 1. Vite React App on 5173
    print("Testing Vite React app at http://localhost:5173/ ...")
    try:
        page.goto("http://localhost:5173/")
        page.evaluate(f"localStorage.setItem('gari_token', '{token}');")
        page.reload()
        page.wait_for_timeout(2000)
        page.screenshot(path=str(out_dir / "vite_dashboard_auth.png"), full_page=True)
        print(f"Vite React dashboard captured: {page.url} (Title: {page.title()})")
    except Exception as e:
        print("Vite error:", e)

    # 2. Frontend2 index.html on 8000
    print("\nTesting Frontend2 index.html at http://localhost:8000/ ...")
    try:
        page.goto("http://localhost:8000/")
        page.evaluate(f"localStorage.setItem('gari_token', '{token}');")
        page.reload()
        page.wait_for_timeout(2000)
        page.screenshot(path=str(out_dir / "frontend2_index_auth.png"), full_page=True)
        print(f"Frontend2 index captured: {page.url} (Title: {page.title()})")
    except Exception as e:
        print("Frontend2 index error:", e)

    # 3. Frontend2 predict.html on 8000
    print("\nTesting Frontend2 predict.html at http://localhost:8000/frontend2/predict.html ...")
    try:
        page.goto("http://localhost:8000/frontend2/predict.html")
        page.wait_for_timeout(2000)
        page.screenshot(path=str(out_dir / "frontend2_predict_auth.png"), full_page=True)
        print(f"Frontend2 predict captured: {page.url} (Title: {page.title()})")
    except Exception as e:
        print("Frontend2 predict error:", e)

    browser.close()
