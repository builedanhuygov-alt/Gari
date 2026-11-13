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
out_dir.mkdir(parents=True, exist_ok=True)

console_errors = []

def on_console(msg):
    if msg.type == "error":
        console_errors.append(msg.text)

print("[INFO] Starting Playwright UI Redesign Verification...")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # -------------------------------------------------------------
    # 1. Desktop 1440px Viewport Verification
    # -------------------------------------------------------------
    print("[1/4] Verifying Desktop 1440px Index...")
    ctx_desktop = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx_desktop.add_cookies([{"name": "access_token", "value": token, "domain": "localhost", "path": "/"}])
    page_d = ctx_desktop.new_page()
    page_d.on("console", on_console)
    page_d.goto("http://localhost:8000/frontend2/login.html")
    page_d.evaluate(f"localStorage.setItem('gari_token', '{token}');")
    
    page_d.goto("http://localhost:8000/frontend2/index.html")
    page_d.wait_for_selector(".kpi-row")
    page_d.wait_for_timeout(2500) # wait for count-up and stats
    
    # Assert KPI layout
    kpi_cards = page_d.query_selector_all(".kpi-card")
    assert len(kpi_cards) == 4, f"Expected 4 KPI cards, got {len(kpi_cards)}"
    
    # Assert icon circle is hidden/removed (Anti-slop Pure Typography check)
    icon_wrap_visible = page_d.evaluate("""() => {
        const wrap = document.querySelector('.kpi-icon-wrap');
        if (!wrap) return false;
        const style = window.getComputedStyle(wrap);
        return style.display !== 'none';
    }""")
    assert not icon_wrap_visible, "Anti-slop violation: .kpi-icon-wrap must not be visible on KPI tiles!"
    
    # Check no page horizontal overflow
    overflow_d = page_d.evaluate("""() => {
        return document.documentElement.scrollWidth > window.innerWidth;
    }""")
    assert not overflow_d, "Desktop page has unintended horizontal scroll overflow!"
    
    page_d.screenshot(path=str(out_dir / "after_redesign_desktop_1440.png"), full_page=True)
    print("  -> Saved after_redesign_desktop_1440.png")

    # -------------------------------------------------------------
    # 2. Desktop 1440px Predict Page Verification
    # -------------------------------------------------------------
    print("[2/4] Verifying Desktop 1440px Predict...")
    page_d.goto("http://localhost:8000/frontend2/predict.html")
    page_d.wait_for_selector("#dropZone")
    page_d.wait_for_timeout(2000)
    
    page_d.screenshot(path=str(out_dir / "after_redesign_predict_desktop_1440.png"), full_page=True)
    print("  -> Saved after_redesign_predict_desktop_1440.png")
    ctx_desktop.close()

    # -------------------------------------------------------------
    # 3. Mobile 390px Viewport Verification (iPhone 14 / Field Phone)
    # -------------------------------------------------------------
    print("[3/4] Verifying Mobile 390px Index...")
    ctx_mobile = browser.new_context(
        viewport={"width": 390, "height": 844},
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    )
    ctx_mobile.add_cookies([{"name": "access_token", "value": token, "domain": "localhost", "path": "/"}])
    page_m = ctx_mobile.new_page()
    page_m.on("console", on_console)
    page_m.goto("http://localhost:8000/frontend2/login.html")
    page_m.evaluate(f"localStorage.setItem('gari_token', '{token}');")
    
    page_m.goto("http://localhost:8000/frontend2/index.html")
    page_m.wait_for_selector(".kpi-row")
    page_m.wait_for_timeout(2500)
    
    # Assert single-column KPI cards on mobile
    kpi_grid_cols = page_m.evaluate("""() => {
        const row = document.querySelector('.kpi-row');
        return window.getComputedStyle(row).gridTemplateColumns.split(' ').length;
    }""")
    assert kpi_grid_cols == 1, f"Expected 1 column for .kpi-row on 390px mobile, got {kpi_grid_cols}"
    
    # Check no page horizontal overflow on mobile
    overflow_m = page_m.evaluate("""() => {
        return document.documentElement.scrollWidth > window.innerWidth;
    }""")
    assert not overflow_m, "Mobile page has unintended horizontal scroll overflow!"
    
    page_m.screenshot(path=str(out_dir / "after_redesign_mobile_390.png"), full_page=True)
    print("  -> Saved after_redesign_mobile_390.png")

    # -------------------------------------------------------------
    # 4. Mobile 390px Predict Page Verification
    # -------------------------------------------------------------
    print("[4/4] Verifying Mobile 390px Predict...")
    page_m.goto("http://localhost:8000/frontend2/predict.html")
    page_m.wait_for_selector("#dropZone")
    page_m.wait_for_timeout(2000)
    
    # Check context selector trigger
    page_m.wait_for_selector("#contextPickerTrigger")
    
    overflow_mp = page_m.evaluate("""() => {
        return document.documentElement.scrollWidth > window.innerWidth;
    }""")
    assert not overflow_mp, "Mobile predict page has unintended horizontal scroll overflow!"
    
    page_m.screenshot(path=str(out_dir / "after_redesign_predict_mobile_390.png"), full_page=True)
    print("  -> Saved after_redesign_predict_mobile_390.png")
    ctx_mobile.close()

    browser.close()

print(f"[OK] Verification complete! Console errors detected: {len(console_errors)}")
if console_errors:
    for err in console_errors:
        print(f"  - {err}")
