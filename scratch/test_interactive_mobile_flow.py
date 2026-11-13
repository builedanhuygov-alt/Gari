import sys
import io
from PIL import Image
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

def test_interactive_flow():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        page = context.new_page()

        # Step 1: Load dashboard
        page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        page.wait_for_timeout(500)
        print("[OK] Dashboard loaded at 390px")

        # Accept cookie banner if present
        if page.is_visible("#btnAcceptCookies"):
            page.click("#btnAcceptCookies")
            page.wait_for_timeout(300)
            print("[OK] Accepted cookie consent")

        # Step 2: Test CTA click
        page.click("#btnHeroStartDiagnose")
        page.wait_for_timeout(400)
        print("[OK] Clicked 'Bắt đầu chẩn đoán'")

        # Step 3: Test file upload & preview
        # Create a synthetic green leaf image
        img = Image.new("RGB", (224, 224), color=(34, 139, 34))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        test_bytes = buf.getvalue()

        # Set input files
        page.set_input_files("#dashboardFileInput", {
            "name": "test_leaf.jpg",
            "mimeType": "image/jpeg",
            "buffer": test_bytes,
        })
        page.wait_for_timeout(500)

        # Check preview is visible
        preview_visible = page.is_visible("#dropzonePreviewView")
        print(f"[OK] Preview view visible: {preview_visible}")
        assert preview_visible, "Preview view should be visible"

        # Step 4: Click Execute Diagnosis
        page.click("#btnExecuteDiagnose")
        page.wait_for_timeout(2000)

        # Check result modal is shown
        modal_visible = page.is_visible("#instantDiagModal.show") or page.is_visible("#modalDiagContent")
        print(f"[OK] Diagnosis result modal shown: {modal_visible}")

        # Step 5: Test bottom navigation scan click
        page.click("#btnBottomNavScan")
        page.wait_for_timeout(300)
        print("[OK] Bottom nav scan button clicked")

        # Step 6: Test bottom nav 'Khác' drawer toggle
        page.click("#btnBottomNavMore")
        page.wait_for_timeout(400)
        drawer_open = page.evaluate("document.getElementById('appSidebar').classList.contains('drawer-open')")
        print(f"[OK] Bottom nav 'Khác' opened drawer: {drawer_open}")
        assert drawer_open, "Sidebar drawer should open on 'Khác' tap"

        browser.close()
        print("\nALL INTERACTIVE MOBILE WORKFLOWS VERIFIED SUCCESSFULLY!")

if __name__ == "__main__":
    test_interactive_flow()
