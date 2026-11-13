import sys
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://localhost:5173/")
    page.wait_for_timeout(2000)

    print("PAGE TITLE:", page.title())
    print("URL:", page.url)

    h1_h2 = [el.inner_text().strip() for el in page.query_selector_all("h1, h2, h3")]
    print("\nHEADINGS:", h1_h2[:10])

    navs = [el.inner_text().strip() for el in page.query_selector_all("aside button, header button")]
    print("\nSIDEBAR/HEADER BUTTONS:", navs[:15])

    visible_text = page.locator("body").inner_text()
    print("\nBODY SNIPPET (first 500 chars):\n", visible_text[:500])

    # Check for modals
    modals = page.query_selector_all("[role='dialog'], .fixed")
    print("\nVISIBLE FIXED/MODAL ELEMENTS:", [m.inner_text().strip()[:80] for m in modals if m.is_visible()])

    browser.close()
