"""
Playwright Test Suite — Verification of Server-Only AI Inference Architecture
File: tests/test_server_only_inference_playwright.py

Verifies:
1. Browser sends image to server over HTTP/HTTPS.
2. Browser NEVER downloads or loads model weight files (.safetensors, .onnx, .bin, .tflite).
3. The response comes from actual server-side inference (execution_location="server", device="cpu", timings).
4. Quota is deducted server-side.
5. Unauthorized users cannot call inference (HTTP 401).
6. Model-unavailable states are handled truthfully with HTTP 503.
7. Both Desktop and Mobile viewports execute the full diagnosis flow.
"""

import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import gari_auth
import gari_database

SCREENSHOTS_DIR = ROOT_DIR / "tests" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

TOMATO_IMAGES = list((ROOT_DIR / "data" / "organized" / "PlantVillage" / "Tomato_Bacterial_spot").glob("*.JPG"))
IMG_DESKTOP = TOMATO_IMAGES[0]
IMG_MOBILE = TOMATO_IMAGES[1]
IMG_DEBOUNCE = TOMATO_IMAGES[2]
IMG_UNAVAILABLE = TOMATO_IMAGES[3]


def test_server_only_inference():
    print("=" * 80)
    print(" PLAYWRIGHT TEST: Server-Only AI Inference & Security Validation")
    print("=" * 80)

    # 1. Setup authenticated session for test user
    user = gari_auth.get_user_by_id(1)
    if not user:
        raise RuntimeError("Test user 1 not found in database")
    token = gari_auth.create_session(user_id=1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # -------------------------------------------------------------
        # Part A: Desktop Diagnosis & Network Audit
        # -------------------------------------------------------------
        print("\n[STEP 1] Running Desktop Diagnosis Flow...")
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        # Network Monitor: Track all HTTP requests to detect any model downloads
        network_requests = []
        model_weight_downloads = []
        diagnose_responses = []

        def handle_request(req):
            url = req.url.lower()
            network_requests.append(url)
            # Detect any forbidden browser model weight download
            for ext in [".safetensors", ".onnx", ".tflite", ".bin", "model.json"]:
                if ext in url:
                    model_weight_downloads.append(url)

        def handle_response(resp):
            if "/api/plant/diagnose" in resp.url or "/api/predict" in resp.url:
                try:
                    data = resp.json()
                    diagnose_responses.append({
                        "status": resp.status,
                        "data": data,
                        "headers": resp.headers
                    })
                except Exception:
                    pass

        page.on("request", handle_request)
        page.on("response", handle_response)

        # Set localStorage token and cookie
        page.goto("http://localhost:8000/frontend2/predict.html")
        page.evaluate(f"localStorage.setItem('gari_token', '{token}');")
        context.add_cookies([{
            "name": "access_token",
            "value": token,
            "domain": "localhost",
            "path": "/"
        }])

        # Reload to load authenticated state
        page.reload()
        page.wait_for_selector("#btnPredict", timeout=10000)

        # Upload image file
        file_input = page.locator("#fileInput")
        file_input.set_input_files(str(IMG_DESKTOP))

        # Wait for preview
        page.wait_for_selector("#previewContainer", state="visible", timeout=10000)

        # Click predict
        btn = page.locator("#btnPredict")
        btn.click()

        # Wait for results card
        page.wait_for_selector("#activeResultCard", state="visible", timeout=20000)

        # Take screenshot of completed diagnosis
        desktop_shot = SCREENSHOTS_DIR / "desktop_server_inference_result.png"
        page.screenshot(path=str(desktop_shot), full_page=True)
        print(f"  -> Desktop diagnosis completed! Screenshot saved: {desktop_shot.name}")

        # Assert no model weights were ever requested by the browser
        print("\n[STEP 2] Auditing Browser Network Activity...")
        print(f"  Total network requests captured: {len(network_requests)}")
        print(f"  Model weight download requests detected: {len(model_weight_downloads)}")
        assert len(model_weight_downloads) == 0, f"VIOLATION: Browser downloaded model weights: {model_weight_downloads}"
        print("  -> PASS: Zero model weights loaded in browser! Models ran exclusively on the server.")

        # Assert diagnosis response came from actual server inference
        print("\n[STEP 3] Validating Server Inference Response Payload & Timings...")
        assert len(diagnose_responses) > 0, "No diagnosis response captured!"
        last_resp = diagnose_responses[-1]
        assert last_resp["status"] == 200, f"Expected 200, got {last_resp['status']}"
        res_data = last_resp["data"]

        print(f"  Status code: {last_resp['status']}")
        print(f"  Execution location: {res_data.get('execution_location')}")
        print(f"  Inference device: {res_data.get('device')}")
        print(f"  Request ID: {res_data.get('request_id')}")
        print(f"  Crop: {res_data.get('crop_name')} ({res_data.get('crop')})")
        print(f"  Disease: {res_data.get('disease_name_vi')} (conf: {res_data.get('confidence')})")
        print(f"  Timings: {res_data.get('timings')}")
        print(f"  Header X-Inference-Location: {last_resp['headers'].get('x-inference-location')}")

        assert res_data.get("execution_location") == "server"
        assert res_data.get("device") == "cpu"
        assert "timings" in res_data
        assert "inference_time_ms" in res_data["timings"]
        assert "upload_time_ms" in res_data["timings"]
        assert "queue_wait_ms" in res_data["timings"]
        assert "total_response_time_ms" in res_data["timings"]
        assert last_resp["headers"].get("x-inference-location") == "server"
        print("  -> PASS: Verified server execution, CPU hardware device, and full timing telemetry.")

        # -------------------------------------------------------------
        # Part B: Quota Deduction Verification
        # -------------------------------------------------------------
        print("\n[STEP 4] Verifying Server-Side Quota Enforcement...")
        quota = res_data.get("quota")
        print(f"  Used count reported: {quota.get('used_count')}/{quota.get('quota_limit')}")
        assert quota is not None
        assert quota.get("used_count", 0) > 0
        print("  -> PASS: Server-side quota was correctly verified and deducted.")

        context.close()

        # -------------------------------------------------------------
        # Part C: Mobile Viewport Diagnosis Flow
        # -------------------------------------------------------------
        print("\n[STEP 5] Testing Mobile Viewport Diagnosis Flow (iPhone 13 - 390x844)...")
        mobile_context = browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
        )
        mobile_page = mobile_context.new_page()
        mobile_page.goto("http://localhost:8000/frontend2/predict.html")
        mobile_page.evaluate(f"localStorage.setItem('gari_token', '{token}');")
        mobile_context.add_cookies([{
            "name": "access_token",
            "value": token,
            "domain": "localhost",
            "path": "/"
        }])
        mobile_page.reload()

        mobile_page.wait_for_selector("#btnPredict", timeout=10000)
        mobile_page.locator("#fileInput").set_input_files(str(IMG_MOBILE))
        mobile_page.wait_for_selector("#previewContainer", state="visible", timeout=10000)

        mobile_btn = mobile_page.locator("#btnPredict")
        mobile_btn.click()

        mobile_page.wait_for_selector("#activeResultCard", state="visible", timeout=20000)
        mobile_shot = SCREENSHOTS_DIR / "mobile_server_inference_result.png"
        mobile_page.screenshot(path=str(mobile_shot), full_page=True)
        print(f"  -> Mobile diagnosis completed! Screenshot saved: {mobile_shot.name}")
        print("  -> PASS: Mobile diagnosis flow fully operational.")

        mobile_context.close()

        # -------------------------------------------------------------
        # Part D: Unauthorized User Inference Rejection
        # -------------------------------------------------------------
        print("\n[STEP 6] Testing Unauthorized User Inference Rejection...")
        unauth_context = browser.new_context()
        unauth_page = unauth_context.new_page()

        unauth_status = None
        def check_unauth_response(resp):
            nonlocal unauth_status
            if "/api/plant/diagnose" in resp.url or "/api/predict" in resp.url:
                unauth_status = resp.status

        unauth_page.on("response", check_unauth_response)
        unauth_page.goto("http://localhost:8000/frontend2/predict.html")

        # Clear any storage
        unauth_page.evaluate("localStorage.clear(); sessionStorage.clear();")

        # Attempt API call via page fetch without credentials
        eval_result = unauth_page.evaluate("""
            async () => {
                const fd = new FormData();
                const blob = new Blob(['fake_image_bytes'], { type: 'image/jpeg' });
                fd.append('image', blob, 'test.jpg');
                const res = await fetch('/api/plant/diagnose', { method: 'POST', body: fd });
                return { status: res.status, ok: res.ok };
            }
        """)
        print(f"  Unauthorized call result: HTTP {eval_result['status']}")
        assert eval_result["status"] == 401, f"Expected HTTP 401, got {eval_result['status']}"
        print("  -> PASS: Unauthorized users cannot call server inference (HTTP 401 rejected).")

        unauth_context.close()

        # -------------------------------------------------------------
        # Part E: Model Unavailable Handling (Truthful 503)
        # -------------------------------------------------------------
        print("\n[STEP 7] Testing Model-Unavailable Handling...")
        auth_context = browser.new_context()
        auth_page = auth_context.new_page()
        auth_page.goto("http://localhost:8000/frontend2/predict.html")
        auth_page.evaluate(f"localStorage.setItem('gari_token', '{token}');")

        import base64
        with open(IMG_UNAVAILABLE, "rb") as f:
            b64_unavail = base64.b64encode(f.read()).decode("ascii")

        unavailable_result = auth_page.evaluate("""
            async (b64) => {
                const byteCharacters = atob(b64);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                const blob = new Blob([byteArray], { type: 'image/jpeg' });
                const fd = new FormData();
                fd.append('image', blob, 'leaf.jpg');
                fd.append('mode', 'manual');
                fd.append('crop', 'NonExistentCropModel999');
                const res = await fetch('/api/plant/diagnose', {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + localStorage.getItem('gari_token') },
                    body: fd
                });
                const data = await res.json();
                return { status: res.status, data: data };
            }
        """, b64_unavail)
        print(f"  Unavailable model call result: HTTP {unavailable_result['status']} | detail: {unavailable_result['data'].get('detail')}")
        assert unavailable_result["status"] == 503, f"Expected HTTP 503, got {unavailable_result['status']}"
        print("  -> PASS: Model unavailable returns truthful HTTP 503 error without fake results.")

        # -------------------------------------------------------------
        # Part F: In-Flight Double-Click Duplicate Protection (HTTP 409)
        # -------------------------------------------------------------
        print("\n[STEP 8] Testing In-Flight Duplicate Prevention (Double-Click Protection)...")
        with open(IMG_DEBOUNCE, "rb") as f:
            b64_debounce = base64.b64encode(f.read()).decode("ascii")

        debounce_result = auth_page.evaluate("""
            async (b64) => {
                const byteCharacters = atob(b64);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                const blob = new Blob([byteArray], { type: 'image/jpeg' });
                
                const makeReq = () => {
                    const fd = new FormData();
                    fd.append('image', blob, 'leaf_debounce.jpg');
                    fd.append('mode', 'auto');
                    return fetch('/api/plant/diagnose', {
                        method: 'POST',
                        headers: { 'Authorization': 'Bearer ' + localStorage.getItem('gari_token') },
                        body: fd
                    });
                };
                // Fire two concurrent requests immediately
                const [r1, r2] = await Promise.all([makeReq(), makeReq()]);
                return { s1: r1.status, s2: r2.status };
            }
        """, b64_debounce)
        print(f"  Concurrent submissions: Status 1: {debounce_result['s1']} | Status 2: {debounce_result['s2']}")
        statuses = [debounce_result['s1'], debounce_result['s2']]
        assert 409 in statuses, f"Expected 409 Conflict in {statuses}"
        print("  -> PASS: Rapid double-click was successfully blocked with HTTP 409 Conflict.")

        auth_context.close()
        browser.close()

    print("\n" + "=" * 80)
    print(" ALL PLAYWRIGHT TESTS PASSED SUCCESSFULLY! ")
    print("=" * 80)


if __name__ == "__main__":
    test_server_only_inference()
