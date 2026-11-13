import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
from playwright.sync_api import sync_playwright
import gari_auth

token = gari_auth.create_session(user_id=1)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844},
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    )
    ctx.add_cookies([{'name': 'access_token', 'value': token, 'domain': 'localhost', 'path': '/'}])
    page = ctx.new_page()
    page.goto('http://localhost:8000/frontend2/login.html')
    page.evaluate(f'localStorage.setItem("gari_token", "{token}");')
    page.goto('http://localhost:8000/frontend2/index.html')
    page.wait_for_timeout(2000)

    sw = page.evaluate('document.documentElement.scrollWidth')
    iw = page.evaluate('window.innerWidth')
    print(f'Mobile scrollWidth: {sw}, innerWidth: {iw}')

    overflowing = page.evaluate('''() => {
        const elements = Array.from(document.querySelectorAll('*'));
        return elements
            .filter(el => {
                const rect = el.getBoundingClientRect();
                return rect.right > window.innerWidth;
            })
            .map(el => ({
                tag: el.tagName,
                id: el.id,
                className: el.className,
                right: el.getBoundingClientRect().right,
                width: el.getBoundingClientRect().width
            }));
    }''')
    for o in overflowing[:15]:
        print(o)
    browser.close()
