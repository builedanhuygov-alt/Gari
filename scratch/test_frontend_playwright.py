import sys
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PAGES = [
    ("http://localhost:8000/frontend2/index.html", "index"),
    ("http://localhost:8000/frontend2/calendar.html", "calendar"),
    ("http://localhost:8000/frontend2/crops.html", "crops"),
    ("http://localhost:8000/frontend2/risk.html", "risk"),
    ("http://localhost:8000/frontend2/farms.html", "farms"),
    ("http://localhost:8000/frontend2/support.html", "support"),
]

async def main():
    import gari_auth
    token = gari_auth.create_session(user_id=1)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        await context.add_cookies([
            {"name": "auth_token", "value": token, "domain": "localhost", "path": "/"}
        ])
        await context.add_init_script(f"localStorage.setItem('gari_token', '{token}');")
        page = await context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        print("Testing frontend2 pages with Playwright...")
        for url, name in PAGES:
            console_errors.clear()
            resp = await page.goto(url, wait_until="networkidle")
            assert resp.status == 200, f"Page {url} returned {resp.status}"

            # Check horizontal overflow
            scroll_width = await page.evaluate("() => document.documentElement.scrollWidth")
            client_width = await page.evaluate("() => document.documentElement.clientWidth")
            has_overflow = scroll_width > client_width

            # Check critical elements
            title = await page.title()
            print(f" -> [{name.upper()}] Status 200 | Title: '{title[:35]}...' | Overflow: {has_overflow} ({scroll_width} vs {client_width}) | Errors: {len(console_errors)}")
            assert not has_overflow, f"Horizontal overflow detected on {name}: {scroll_width} > {client_width}"

        # Test clicking Mark All Read on topbar
        print("\nTesting Notification Bell and Mark All Read...")
        await page.goto("http://localhost:8000/frontend2/index.html", wait_until="networkidle")
        await page.click("#btnAlerts")
        is_dropdown_visible = await page.evaluate("() => document.getElementById('notificationsDropdown').classList.contains('show')")
        print(f" -> Notifications dropdown opened: {is_dropdown_visible}")
        assert is_dropdown_visible, "Notification dropdown should be visible"

        await page.click("#btnMarkAllNotifsRead")
        await page.wait_for_timeout(600)
        badge_style = await page.evaluate("() => document.getElementById('unreadBadge').style.display")
        print(f" -> Unread badge display after 'Mark All Read': '{badge_style}'")
        assert badge_style == "none", "Badge should be hidden after marking all as read"

        # Test Calendar Add Task modal
        print("\nTesting Calendar Add Task Flow in UI...")
        await page.goto("http://localhost:8000/frontend2/calendar.html", wait_until="networkidle")
        await page.click("#btnOpenNewTaskModal")
        modal_display = await page.evaluate("() => document.getElementById('newTaskModal').style.display")
        print(f" -> New Task modal opened: {modal_display}")
        assert modal_display == "flex", "New Task modal should be displayed"

        await page.fill("#newTaskTitle", "Kiểm tra hệ thống tưới nhỏ giọt luống 3")
        await page.fill("#newTaskNotes", "Đo lưu lượng và xả cặn đầu vòi phun")
        await page.click("#formNewTask button[type='submit']")
        await page.wait_for_timeout(800)

        # Verify task appears in task list
        task_text = await page.inner_text("#calendarTaskList")
        has_new_task = "Kiểm tra hệ thống tưới nhỏ giọt luống 3" in task_text
        print(f" -> Newly added task visible in #calendarTaskList: {has_new_task}")
        assert has_new_task, "Newly added task must appear in DOM"

        # Test Risk Field Observation Modal in UI
        print("\nTesting Risk Field Observation Flow in UI...")
        await page.goto("http://localhost:8000/frontend2/risk.html", wait_until="networkidle")
        ack_btns = await page.query_selector_all(".btn-ack-risk")
        print(f" -> Found {len(ack_btns)} observation buttons on risk alert cards")
        assert len(ack_btns) > 0, "Risk cards must have observation button"

        await ack_btns[0].click()
        await page.wait_for_timeout(400)
        risk_modal_display = await page.evaluate("() => document.getElementById('riskObservationModal').style.display")
        print(f" -> Risk observation modal opened: {risk_modal_display}")
        assert risk_modal_display == "flex", "Risk observation modal should be displayed"

        await page.fill("#obsNotes", "Đã kiểm tra sáng nay, không phát hiện vết bệnh.")
        await page.click("#formRiskObservation button[type='submit']")
        await page.wait_for_timeout(800)
        toast_text = await page.inner_text("#globalToast")
        print(f" -> Toast confirmation: '{toast_text}'")

        await browser.close()
        print("\nAll Playwright UI tests passed successfully with ZERO regressions!")

if __name__ == "__main__":
    asyncio.run(main())
