import os
import sys
import time
import subprocess
import urllib.request
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath("."))

import gari_auth
import gari_database

SERVER_PORT = 8000
BASE_URL = f"http://127.0.0.1:{SERVER_PORT}"
LEAF_IMAGE_PATH = os.path.abspath("tests/fixtures/test_leaf.jpg")

def start_server_if_needed():
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=1) as resp:
            if resp.status == 200:
                print(f"[TEST SETUP] Server already listening on {BASE_URL}")
                return None
    except Exception:
        pass

    print(f"[TEST SETUP] Spawning test FastAPI server on port {SERVER_PORT}...")
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "api_server:app",
            "--host", "127.0.0.1", "--port", str(SERVER_PORT)
        ]
    )

    for _ in range(35):
        time.sleep(1)
        try:
            with urllib.request.urlopen(f"{BASE_URL}/health", timeout=1) as resp:
                if resp.status == 200:
                    print("[TEST SETUP] Server listening!")
                    return proc
        except Exception:
            continue

    raise RuntimeError("Failed to start server within 35 seconds.")

def run_browser_tests():
    proc = start_server_if_needed()
    try:
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

            # -------------------------------------------------------------
            # TEST 1: DESKTOP VIEWPORT (1280x800)
            # -------------------------------------------------------------
            print("\n--- [TEST 1] DESKTOP VIEWPORT (1280x800) ---")
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()

            page.on("console", lambda m: print(f"[{m.type}] {m.text}"))
            page.on("response", lambda r: print(f"[HTTP {r.status}] {r.url[:80]}") if "/api/" in r.url else None)

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

            # Manual mode: tomato
            page.click("#btnModeManual")
            page.select_option("#cropSelect", "tomato")
            page.locator("#fileInput").set_input_files(LEAF_IMAGE_PATH)
            time.sleep(1)

            page.click("#btnPredict")
            print("Clicked predict, waiting for activeResultCard...")
            page.wait_for_selector("#activeResultCard", state="visible", timeout=30000)
            print("Desktop test: #activeResultCard is visible!")

            # Verify Attention Tab is functional
            tab_att = page.locator("#tabAttention")
            assert tab_att.is_visible()
            print("Desktop test: #tabAttention verified.")

            os.makedirs("tests/screenshots", exist_ok=True)
            page.screenshot(path="tests/screenshots/desktop_diagnosis_success.png")
            print("Screenshot saved to tests/screenshots/desktop_diagnosis_success.png")
            context.close()

            # -------------------------------------------------------------
            # TEST 2: MOBILE VIEWPORT (390x844 - iPhone 12)
            # -------------------------------------------------------------
            print("\n--- [TEST 2] MOBILE VIEWPORT (390x844) ---")
            time.sleep(3.5) # Duplicate inference guard
            m_ctx = browser.new_context(viewport={"width": 390, "height": 844})
            m_page = m_ctx.new_page()

            m_page.goto(f"{BASE_URL}/frontend2/predict.html")
            m_page.evaluate(f"""() => {{
                localStorage.setItem('gari_token', '{token}');
                localStorage.setItem('gari_user', JSON.stringify({{
                    id: {user_id},
                    email: '{user_email}',
                    name: '{user_name}',
                    role: 'farmer'
                }}));
            }}""")
            m_page.reload()
            m_page.wait_for_selector("#btnPredict")

            m_page.click("#btnModeManual")
            m_page.select_option("#cropSelect", "pepper")
            m_page.locator("#fileInput").set_input_files(LEAF_IMAGE_PATH)
            time.sleep(1)

            m_page.click("#btnPredict")
            m_page.wait_for_selector("#activeResultCard", state="visible", timeout=30000)
            print("Mobile test: #activeResultCard is visible!")

            m_page.screenshot(path="tests/screenshots/mobile_diagnosis_success.png")
            print("Screenshot saved to tests/screenshots/mobile_diagnosis_success.png")
            m_ctx.close()

            # -------------------------------------------------------------
            # TEST 3: CANCELLATION & NON-HANGING PIPELINE
            # -------------------------------------------------------------
            print("\n--- [TEST 3] CANCELLATION FLOW ---")
            time.sleep(3.5)
            c_ctx = browser.new_context(viewport={"width": 1280, "height": 800})
            c_page = c_ctx.new_page()

            c_page.goto(f"{BASE_URL}/frontend2/predict.html")
            c_page.evaluate(f"""() => {{
                localStorage.setItem('gari_token', '{token}');
                localStorage.setItem('gari_user', JSON.stringify({{
                    id: {user_id},
                    email: '{user_email}',
                    name: '{user_name}',
                    role: 'farmer'
                }}));
            }}""")
            c_page.reload()
            c_page.wait_for_selector("#btnPredict")

            c_page.locator("#fileInput").set_input_files(LEAF_IMAGE_PATH)
            time.sleep(1)

            c_page.click("#btnPredict")
            c_page.wait_for_selector("#btnCancelDiagnosis", state="visible")
            c_page.click("#btnCancelDiagnosis")
            print("Clicked cancel button!")

            time.sleep(1)
            msg = c_page.locator("#pipelineStatusMessage").text_content()
            assert "hủy" in msg.lower(), f"Expected cancelled message, got {msg}"
            assert c_page.locator("#btnPredict").is_enabled(), "Predict button should be re-enabled"
            print("Cancellation verified: Pipeline gracefully aborted without hanging.")
            c_ctx.close()

            browser.close()

        print("\n=========================================================================")
        print("ALL PLAYWRIGHT BROWSER PIPELINE TESTS PASSED 100%!")
        print("=========================================================================")

    finally:
        if proc:
            proc.terminate()
            proc.wait()

if __name__ == "__main__":
    run_browser_tests()
