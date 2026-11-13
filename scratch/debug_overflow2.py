import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
from playwright.sync_api import sync_playwright
import gari_auth

token = gari_auth.create_session(user_id=1)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={'width': 1440, 'height': 900})
    ctx.add_cookies([{'name': 'access_token', 'value': token, 'domain': 'localhost', 'path': '/'}])
    page = ctx.new_page()
    page.goto('http://localhost:8000/frontend2/login.html')
    page.evaluate(f'localStorage.setItem("gari_token", "{token}");')
    page.goto('http://localhost:8000/frontend2/index.html')
    page.wait_for_timeout(2000)

    res = page.evaluate('''() => {
        const shell = document.querySelector('.app-shell').getBoundingClientRect();
        const sidebar = document.querySelector('.app-sidebar').getBoundingClientRect();
        const main = document.querySelector('.app-main').getBoundingClientRect();
        const body = document.querySelector('.content-body').getBoundingClientRect();
        const grid = document.querySelector('.dashboard-grid').getBoundingClientRect();
        const dgridCols = Array.from(document.querySelectorAll('.dashboard-grid > .grid-col')).map(c => c.getBoundingClientRect());
        return { shell, sidebar, main, body, grid, dgridCols };
    }''')
    print("Shell:", res["shell"])
    print("Sidebar:", res["sidebar"])
    print("Main:", res["main"])
    print("Body:", res["body"])
    print("Grid:", res["grid"])
    print("Cols:", res["dgridCols"])
    browser.close()
