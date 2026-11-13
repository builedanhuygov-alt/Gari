import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import gari_auth
token = gari_auth.create_session(user_id=1)
out_dir = ROOT_DIR / "tests" / "screenshots"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # 1. Desktop 1440px Index
    ctx_desktop = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx_desktop.add_cookies([{"name": "access_token", "value": token, "domain": "localhost", "path": "/"}])
    page_d = ctx_desktop.new_page()
    page_d.goto("http://localhost:8000/frontend2/login.html")
    page_d.evaluate(f"localStorage.setItem('gari_token', '{token}');")
    
    page_d.goto("http://localhost:8000/frontend2/index.html")
    page_d.wait_for_timeout(2000)
    page_d.screenshot(path=str(out_dir / "before_redesign_desktop_1440.png"), full_page=True)
    print("Saved before_redesign_desktop_1440.png")

    page_d.goto("http://localhost:8000/frontend2/predict.html")
    page_d.wait_for_timeout(2000)
    page_d.screenshot(path=str(out_dir / "before_redesign_predict_desktop_1440.png"), full_page=True)
    print("Saved before_redesign_predict_desktop_1440.png")
    ctx_desktop.close()

    # 2. Mobile 390px Index & Predict
    ctx_mobile = browser.new_context(
        viewport={"width": 390, "height": 844},
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    )
    ctx_mobile.add_cookies([{"name": "access_token", "value": token, "domain": "localhost", "path": "/"}])
    page_m = ctx_mobile.new_page()
    page_m.goto("http://localhost:8000/frontend2/login.html")
    page_m.evaluate(f"localStorage.setItem('gari_token', '{token}');")
    
    page_m.goto("http://localhost:8000/frontend2/index.html")
    page_m.wait_for_timeout(2000)
    page_m.screenshot(path=str(out_dir / "before_redesign_mobile_390.png"), full_page=True)
    print("Saved before_redesign_mobile_390.png")

    page_m.goto("http://localhost:8000/frontend2/predict.html")
    page_m.wait_for_timeout(2000)
    page_m.screenshot(path=str(out_dir / "before_redesign_predict_mobile_390.png"), full_page=True)
    print("Saved before_redesign_predict_mobile_390.png")
    ctx_mobile.close()

    browser.close()
