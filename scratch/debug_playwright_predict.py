import os
import sys
sys.path.insert(0, os.path.abspath("."))
import time
import urllib.request
from playwright.sync_api import sync_playwright

SERVER_PORT = 8000
BASE_URL = f"http://127.0.0.1:{SERVER_PORT}"
LEAF_IMAGE_PATH = os.path.abspath("tests/fixtures/test_leaf.jpg")

import gari_auth
import gari_database

# Poll /health until server responds
print("Waiting for server on port 8000...")
for _ in range(30):
    time.sleep(1)
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=1) as resp:
            if resp.status == 200:
                print("Server listening!")
                break
    except Exception:
        continue

with gari_database.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, full_name FROM users WHERE id = 1 LIMIT 1")
    user_row = cursor.fetchone()
    user_id = user_row[0]
    user_email = user_row[1]
    user_name = user_row[2]

token = gari_auth.create_session(user_id=user_id)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()

    page.on("console", lambda msg: print(f"[CONSOLE {msg.type}] {msg.text}"))
    page.on("pageerror", lambda err: print(f"[PAGE ERROR] {err}"))
    page.on("response", lambda resp: print(f"[HTTP {resp.status}] {resp.url}"))

    page.goto(f"{BASE_URL}/frontend2/predict.html")
    page.evaluate(f"""() => {{
        localStorage.setItem('gari_token', '{token}');
        localStorage.setItem('gari_user', JSON.stringify({{
            id: {user_id},
            email: '{user_email}',
            name: '{user_name}',
            role: 'farmer'
        }}));
    }}""")
    page.reload()
    page.wait_for_selector("#btnPredict")

    page.click("#btnModeManual")
    page.select_option("#cropSelect", "tomato")
    page.locator("#fileInput").set_input_files(LEAF_IMAGE_PATH)
    time.sleep(1)

    page.click("#btnPredict")
    print("Clicked predict, waiting for response...")
    time.sleep(6)

    # Inspect visible cards
    card_ids = [
        'emptyStateResult',
        'leafValidationFailureCard',
        'infoNoticeCard',
        'cropConfirmationCard',
        'rejectionCard',
        'uncertainCard',
        'activeResultCard',
        'progressPipeline'
    ]
    for cid in card_ids:
        el = page.locator(f"#{cid}")
        print(f"Card #{cid}: visible={el.is_visible()}, display={el.evaluate('el => getComputedStyle(el).display')}")

    status_msg = page.locator("#pipelineStatusMessage").text_content()
    print(f"Pipeline status message: {status_msg}")

    page.screenshot(path="scratch/predict_debug.png")
    print("Screenshot saved to scratch/predict_debug.png")
    browser.close()
