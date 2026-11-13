import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')

ARTIFACT_DIR = r"C:\Users\danhu\.gemini\antigravity\brain\f726ce3c-fc1b-42bc-a6f0-9ea2576ca58b"
COMMUNITY_URL = "http://localhost:8000/frontend2/community.html"

async def run_tests():
    print("=== Starting GARI Community Sidebar & Independent Scroll Validation ===")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # ---------------------------------------------------------
        # TEST 1: DESKTOP TWO-COLUMN LAYOUT & INDEPENDENT SCROLL (1280x800)
        # ---------------------------------------------------------
        print("\n--- 1. Testing Desktop Layout (1280x800) ---")
        context_desktop = await browser.new_context(viewport={"width": 1280, "height": 800})
        await context_desktop.add_init_script("localStorage.setItem('gari_cookie_consent', 'accepted');")
        page = await context_desktop.new_page()

        await page.goto(COMMUNITY_URL, wait_until="networkidle")
        await page.wait_for_timeout(500)

        # 1.1 Verify Sidebar Content is Rendered (NOT a blank dark green block!)
        sidebar = page.locator('#appSidebar')
        assert await sidebar.is_visible(), "Sidebar must be visible on desktop"

        # Check brand logo and brand name
        brand = page.locator('#appSidebar .brand-name')
        assert await brand.count() > 0, "Sidebar must render brand name"
        print(f"Brand rendered: {await brand.inner_text()}")

        # Check navigation links count
        nav_links = page.locator('#appSidebar .nav-link')
        links_count = await nav_links.count()
        print(f"Total sidebar nav links rendered: {links_count}")
        assert links_count >= 10, f"Sidebar must render all navigation items (got {links_count})"

        # Verify Community link exists and is active
        comm_link = page.locator('#appSidebar .nav-link[data-key="community"]')
        assert await comm_link.count() > 0, "Sidebar must contain 'community' nav item"
        
        active_link = page.locator('#appSidebar .nav-link.active')
        assert await active_link.count() > 0, "Sidebar must have an active link"
        active_key = await active_link.get_attribute('data-key')
        print(f"Active nav link key in sidebar: '{active_key}'")
        assert active_key == "community", f"Expected active link to be 'community', got '{active_key}'"

        # Verify user profile at the bottom of sidebar
        user_card = page.locator('#appSidebar .sidebar-user-card')
        assert await user_card.count() > 0, "Sidebar must render user profile area"
        print("✓ Sidebar content successfully rendered with full navigation and active route")

        # 1.2 Verify Dimensions and Positioning
        sidebar_box = await sidebar.bounding_box()
        main_content = page.locator('.app-main')
        main_box = await main_content.bounding_box()
        print(f"Sidebar bounding box (initial): {sidebar_box}")
        print(f"Main content bounding box (initial): {main_box}")

        # Main content must not slide underneath the sidebar
        assert main_box["x"] >= sidebar_box["x"] + sidebar_box["width"] - 2, (
            f"Main content (x={main_box['x']}) must start after sidebar (x={sidebar_box['x']}+w={sidebar_box['width']})"
        )
        print("✓ Main content does not slide underneath the sidebar")

        # Capture Desktop Initial Screenshot
        initial_shot = os.path.join(ARTIFACT_DIR, "community_desktop_top.png")
        await page.screenshot(path=initial_shot)
        print(f"Saved initial desktop screenshot: {initial_shot}")

        # 1.3 Verify Independent Scrolling Behavior
        # Scroll the main content area by 500px
        scroll_res = await page.evaluate("""() => {
            const main = document.querySelector('.app-main');
            const initialMainScroll = main.scrollTop;
            const initialBodyScroll = window.scrollY || document.documentElement.scrollTop;

            // Scroll main content down
            main.scrollTop = 500;

            const scrolledMainScroll = main.scrollTop;
            const scrolledBodyScroll = window.scrollY || document.documentElement.scrollTop;

            return {
                initialMainScroll,
                initialBodyScroll,
                scrolledMainScroll,
                scrolledBodyScroll
            };
        }""")
        print(f"Scroll metrics: {scroll_res}")
        assert scroll_res["scrolledMainScroll"] > 0, "Main content area (.app-main) must scroll vertically"
        assert scroll_res["scrolledBodyScroll"] == 0, "Window / body level scroll must remain 0 (no page double-scrollbar!)"

        # Verify Sidebar remains stationary after scroll
        sidebar_box_after = await sidebar.bounding_box()
        print(f"Sidebar bounding box (after scroll): {sidebar_box_after}")
        assert sidebar_box_after["y"] == sidebar_box["y"], "Sidebar must remain stationary at y=0"
        assert sidebar_box_after["height"] == sidebar_box["height"], "Sidebar height must remain consistent"
        print("✓ Sidebar remains stationary while main content scrolls independently")

        # Capture Scrolled Desktop Screenshot
        scrolled_shot = os.path.join(ARTIFACT_DIR, "community_desktop_scrolled.png")
        await page.screenshot(path=scrolled_shot)
        print(f"Saved scrolled desktop screenshot: {scrolled_shot}")

        await context_desktop.close()

        # ---------------------------------------------------------
        # TEST 2: MOBILE RESPONSIVE BEHAVIOR (390x844)
        # ---------------------------------------------------------
        print("\n--- 2. Testing Mobile Responsive Drawer (390x844) ---")
        context_mobile = await browser.new_context(viewport={"width": 390, "height": 844})
        await context_mobile.add_init_script("localStorage.setItem('gari_cookie_consent', 'accepted');")
        page_mobile = await context_mobile.new_page()

        await page_mobile.goto(COMMUNITY_URL, wait_until="networkidle")
        await page_mobile.wait_for_timeout(500)

        mobile_sidebar = page_mobile.locator('#appSidebar')
        mobile_main = page_mobile.locator('.app-main')
        backdrop = page_mobile.locator('#sidebarBackdrop')
        toggle_btn = page_mobile.locator('#btnToggleSidebar')

        # 2.1 Closed Drawer State
        mobile_main_box = await mobile_main.bounding_box()
        print(f"Mobile main width: {mobile_main_box['width']}")
        assert mobile_main_box["width"] >= 380, "Main content must occupy full width when mobile drawer is closed"

        # Sidebar should be off-screen
        mobile_classes = await mobile_sidebar.get_attribute("class")
        assert "drawer-open" not in mobile_classes, "Sidebar drawer must be closed initially on mobile"
        print("✓ Mobile drawer is closed, main content is full-width")

        mobile_closed_shot = os.path.join(ARTIFACT_DIR, "community_mobile_drawer_closed.png")
        await page_mobile.screenshot(path=mobile_closed_shot)
        print(f"Saved mobile closed drawer screenshot: {mobile_closed_shot}")

        # 2.2 Open Drawer via Menu Button
        assert await toggle_btn.is_visible(), "Mobile hamburger menu toggle button must be visible"
        await toggle_btn.click()
        await page_mobile.wait_for_timeout(350) # wait for smooth CSS transform transition

        mobile_classes_open = await mobile_sidebar.get_attribute("class")
        assert "drawer-open" in mobile_classes_open, "Sidebar must have 'drawer-open' class after menu toggle"
        backdrop_classes = await backdrop.get_attribute("class")
        assert "show" in backdrop_classes, "Backdrop must be shown when drawer is open"
        print("✓ Mobile drawer smoothly opened via hamburger button")

        mobile_open_shot = os.path.join(ARTIFACT_DIR, "community_mobile_drawer_open.png")
        await page_mobile.screenshot(path=mobile_open_shot)
        print(f"Saved mobile open drawer screenshot: {mobile_open_shot}")

        # 2.3 Close Drawer via Backdrop Click
        await backdrop.click(position={"x": 350, "y": 300})
        await page_mobile.wait_for_timeout(350)

        mobile_classes_closed = await mobile_sidebar.get_attribute("class")
        assert "drawer-open" not in mobile_classes_closed, "Sidebar drawer must close when backdrop is clicked"
        print("✓ Mobile drawer smoothly closed upon backdrop tap")

        await context_mobile.close()
        await browser.close()

    print("\n==========================================")
    print("ALL COMMUNITY SIDEBAR & SCROLL TESTS PASSED! 100% SUCCESS")
    print("==========================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
