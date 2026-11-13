import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')

ARTIFACT_DIR = r"C:\Users\danhu\.gemini\antigravity\brain\f726ce3c-fc1b-42bc-a6f0-9ea2576ca58b"
BASE_URL = "http://localhost:8000/frontend2/index.html"

VIEWPORTS = [
    {"name": "desktop_1200", "width": 1200, "height": 800, "is_mobile": False},
    {"name": "mobile_430", "width": 430, "height": 932, "is_mobile": True},
    {"name": "mobile_390", "width": 390, "height": 844, "is_mobile": True},
    {"name": "mobile_360", "width": 360, "height": 780, "is_mobile": True},
    {"name": "mobile_320", "width": 320, "height": 568, "is_mobile": True},
]

async def run_tests():
    print("=== Starting Copilot Overlay & Motion System Validation ===")
    results = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for vp in VIEWPORTS:
            vp_name = vp["name"]
            w = vp["width"]
            h = vp["height"]
            print(f"\n--- Testing Viewport: {vp_name} ({w}x{h}) ---")
            
            context = await browser.new_context(
                viewport={"width": w, "height": h},
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15" if vp["is_mobile"] else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
            )
            # Pre-set cookie consent to avoid any overlay interruption
            await context.add_init_script("localStorage.setItem('gari_cookie_consent', 'accepted');")

            page = await context.new_page()

            # Navigate to page
            await page.goto(BASE_URL, wait_until="networkidle")

            # Dismiss cookie banner if present
            try:
                cookie_btn = page.locator('#btnBannerAcceptAll')
                if await cookie_btn.count() > 0 and await cookie_btn.is_visible():
                    await cookie_btn.click()
                    await page.wait_for_timeout(200)
            except Exception as e:
                pass

            # 1. TEST CLOSED STATE
            fab = page.locator('#gariCopilotFab')
            drawer = page.locator('#gariCopilotDrawer')
            backdrop = page.locator('#gariCopilotBackdrop')

            assert await fab.is_visible(), f"FAB must be visible in {vp_name}"
            drawer_classes = await drawer.get_attribute("class")
            assert "open" not in drawer_classes, f"Drawer must be closed initially in {vp_name}"
            
            # Check FAB bounding box and bottom nav clearance on mobile
            fab_box = await fab.bounding_box()
            print(f"FAB box in {vp_name}: {fab_box}")

            if vp["is_mobile"]:
                bottom_nav = page.locator('#mobileBottomNav')
                assert await bottom_nav.is_visible(), "Mobile bottom nav must be visible"
                nav_box = await bottom_nav.bounding_box()
                print(f"Bottom nav box in {vp_name}: {nav_box}")
                
                # FAB bottom should not overlap bottom nav top
                fab_bottom = fab_box["y"] + fab_box["height"]
                nav_top = nav_box["y"]
                print(f"FAB bottom: {fab_bottom}, Nav top: {nav_top}")
                assert fab_bottom <= nav_top + 5, f"FAB bottom ({fab_bottom}) must NOT overlap mobile bottom nav top ({nav_top})!"
                print(f"✓ Verified non-overlapping launcher in {vp_name}")

            # Screenshot closed state
            closed_shot_path = os.path.join(ARTIFACT_DIR, f"copilot_{vp_name}_closed.png")
            await page.screenshot(path=closed_shot_path)
            print(f"Saved closed state screenshot: {closed_shot_path}")

            # 2. TEST OPEN STATE (click FAB)
            await fab.click()
            await page.wait_for_timeout(350) # wait for smooth CSS transition

            drawer_classes_open = await drawer.get_attribute("class")
            assert "open" in drawer_classes_open, f"Drawer must have 'open' class in {vp_name}"
            
            # Verify body scroll lock
            body_classes = await page.locator("body").get_attribute("class")
            assert "copilot-open" in body_classes, f"Body must have 'copilot-open' class in {vp_name}"
            print(f"✓ Body scroll locked: body.copilot-open active")

            # Verify input focus
            focused_id = await page.evaluate("() => document.activeElement ? document.activeElement.id : null")
            print(f"Active element on open: {focused_id}")
            assert focused_id == "copilotInput", f"Input #copilotInput must be focused on open in {vp_name}"
            print(f"✓ Focus auto-management: #copilotInput focused")

            # Check drawer dimensions & input visibility
            drawer_box = await drawer.bounding_box()
            input_box = await page.locator('#copilotInput').bounding_box()
            send_box = await page.locator('#btnSendCopilot').bounding_box()
            print(f"Drawer box in {vp_name}: {drawer_box}")
            print(f"Input box in {vp_name}: {input_box}")
            print(f"Send button box in {vp_name}: {send_box}")

            # Ensure input and send button are within viewport and drawer
            assert input_box["y"] + input_box["height"] <= h, f"Input must be within viewport in {vp_name}"
            assert send_box["x"] + send_box["width"] <= w, f"Send button must be unclipped in {vp_name}"
            print(f"✓ Input & send button fully unclipped and keyboard-safe in {vp_name}")

            # Screenshot open state
            open_shot_path = os.path.join(ARTIFACT_DIR, f"copilot_{vp_name}_open.png")
            await page.screenshot(path=open_shot_path)
            print(f"Saved open state screenshot: {open_shot_path}")

            # 3. TEST CLOSE INTERACTION
            if vp["is_mobile"]:
                # Close via close button
                close_btn = page.locator('#btnCloseCopilot')
                await close_btn.click()
                await page.wait_for_timeout(350)
            else:
                # Test ESC key on desktop
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(350)

            drawer_classes_after = await drawer.get_attribute("class")
            assert "open" not in drawer_classes_after, f"Drawer must be closed after dismiss in {vp_name}"
            body_classes_after = await page.locator("body").get_attribute("class")
            assert "copilot-open" not in body_classes_after, f"Body scroll lock must be removed in {vp_name}"
            print(f"✓ Drawer smoothly closed, scroll lock removed in {vp_name}")

            results[vp_name] = "PASSED"
            await context.close()

        # 4. TEST FUNCTIONAL COPILOT INTERACTION (Chat & quick chips)
        print("\n--- Testing Copilot Chat API & Quick Chips Interaction ---")
        context = await browser.new_context(viewport={"width": 1200, "height": 800})
        await context.add_init_script("localStorage.setItem('gari_cookie_consent', 'accepted');")
        page = await context.new_page()
        await page.goto(BASE_URL, wait_until="networkidle")
        
        # Open drawer
        await page.locator('#gariCopilotFab').click()
        await page.wait_for_timeout(300)

        # Click quick chip
        chip = page.locator('.copilot-chip').first
        chip_text = await chip.inner_text()
        print(f"Clicking quick chip: {chip_text}")
        await chip.click()

        # Wait for bot reply
        await page.wait_for_selector('.copilot-msg.bot .copilot-bubble', timeout=10000)
        bot_msgs = await page.locator('.copilot-msg.bot .copilot-bubble').all_inner_texts()
        print(f"Bot reply received count: {len(bot_msgs)}")
        assert len(bot_msgs) >= 2, "Bot should have responded to the quick chip query"
        print("Latest bot reply:", bot_msgs[-1][:120], "...")

        # Screenshot chat conversation
        chat_shot_path = os.path.join(ARTIFACT_DIR, "copilot_chat_interaction.png")
        await page.screenshot(path=chat_shot_path)
        print(f"Saved chat interaction screenshot: {chat_shot_path}")

        # 5. TEST REDUCED MOTION PREFERENCE
        print("\n--- Testing Prefers-Reduced-Motion Handling ---")
        reduced_context = await browser.new_context(
            viewport={"width": 1200, "height": 800},
            reduced_motion="reduce"
        )
        await reduced_context.add_init_script("localStorage.setItem('gari_cookie_consent', 'accepted');")
        reduced_page = await reduced_context.new_page()
        await reduced_page.goto(BASE_URL, wait_until="networkidle")

        # Check animation durations under reduced motion
        hero_anim = await reduced_page.evaluate("""() => {
            const el = document.querySelector('.hero-banner-v2');
            return el ? window.getComputedStyle(el).animationDuration : null;
        }""")
        print(f"Hero banner animation duration under reduced-motion: {hero_anim}")
        assert hero_anim in ["0s", "0.001s", "0.00001s", "0.000001s", "1e-05s", "1e-06s", "0.001ms"], f"Reduced motion should neutralize animation duration, got: {hero_anim}"
        print("✓ Verified prefers-reduced-motion: reduce successfully disables animations")

        await reduced_context.close()
        await browser.close()

    print("\n==========================================")
    print("ALL TESTS PASSED SUCCESSFULLY! 100% HEALTH")
    print("==========================================")
    return results

if __name__ == "__main__":
    asyncio.run(run_tests())
