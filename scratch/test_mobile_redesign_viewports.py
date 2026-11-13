import sys
import os
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

ARTIFACT_DIR = r"C:\Users\danhu\.gemini\antigravity\brain\f726ce3c-fc1b-42bc-a6f0-9ea2576ca58b"
VIEWPORTS = [
    {"name": "iPhone_SE_320", "width": 320, "height": 640},
    {"name": "Android_Compact_360", "width": 360, "height": 740},
    {"name": "iPhone_X_375", "width": 375, "height": 812},
    {"name": "iPhone_14_Pro_390", "width": 390, "height": 844},
    {"name": "iPhone_ProMax_430", "width": 430, "height": 932},
    {"name": "Tablet_768", "width": 768, "height": 1024},
    {"name": "Desktop_1200", "width": 1200, "height": 800},
]

def run_tests():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        results = []

        for vp in VIEWPORTS:
            context = browser.new_context(
                viewport={"width": vp["width"], "height": vp["height"]},
                device_scale_factor=2,
            )
            page = context.new_page()

            # Navigate to GARI home dashboard
            page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
            page.wait_for_timeout(1000)

            # Check horizontal overflow
            scroll_width = page.evaluate("document.documentElement.scrollWidth")
            client_width = page.evaluate("document.documentElement.clientWidth")
            body_overflow = scroll_width > client_width

            # Check key elements existence and visibility
            hero_visible = page.is_visible("#heroBanner")
            quick_visible = page.is_visible("#quickAccessTrack")
            diag_visible = page.is_visible("#aiCropDiagnosisSection")
            farms_visible = page.is_visible("#farmsCardsTrack")
            pro_visible = page.is_visible("#proUpgradeBanner")

            is_mobile = vp["width"] <= 1024
            bottom_nav_visible = page.is_visible("#mobileBottomNav") if is_mobile else True

            # Server status text
            server_status = page.inner_text("#serverStatusText") if page.is_visible("#serverStatusText") else "N/A"

            # Take screenshot for key targets
            if vp["name"] in ["iPhone_SE_320", "iPhone_14_Pro_390", "iPhone_ProMax_430", "Desktop_1200"]:
                shot_path = os.path.join(ARTIFACT_DIR, f"mobile_redesign_{vp['name'].lower()}.png")
                page.screenshot(path=shot_path, full_page=False)
                # Also save full page for 390 (reference match)
                if vp["name"] == "iPhone_14_Pro_390":
                    full_shot_path = os.path.join(ARTIFACT_DIR, "mobile_redesign_reference_390_full.png")
                    page.screenshot(path=full_shot_path, full_page=True)
                    print(f"Saved full reference screenshot to: {full_shot_path}")

            results.append({
                "viewport": vp["name"],
                "width": vp["width"],
                "overflow": body_overflow,
                "hero": hero_visible,
                "quick": quick_visible,
                "diag": diag_visible,
                "farms": farms_visible,
                "pro": pro_visible,
                "bottom_nav": bottom_nav_visible,
                "server_status": server_status
            })

            context.close()

        browser.close()

        print("\n" + "="*70)
        print("MOBILE REDESIGN RESPONSIVENESS & INTEGRITY TEST RESULTS")
        print("="*70)
        all_ok = True
        for r in results:
            status = "PASS" if not r["overflow"] and r["hero"] and r["diag"] and r["farms"] else "FAIL"
            if status == "FAIL": all_ok = False
            print(f"[{status}] {r['viewport']} ({r['width']}px):")
            print(f"       Horizontal Overflow: {'YES (ERROR)' if r['overflow'] else 'NO (PERFECT)'}")
            print(f"       Hero: {r['hero']} | Quick Cards: {r['quick']} | Diag: {r['diag']} | Farms: {r['farms']}")
            print(f"       Bottom Nav: {r['bottom_nav']} | Server: '{r['server_status']}'")

        print("="*70)
        if all_ok:
            print("ALL VIEWPORT QUALITY CHECKS PASSED SUCCESSFULLY!")
        else:
            print("SOME CHECKS FAILED!")
            sys.exit(1)

if __name__ == "__main__":
    run_tests()
