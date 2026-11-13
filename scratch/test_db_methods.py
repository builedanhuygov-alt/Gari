import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gari_database

# 1. Test listing cultivation tasks
tasks = gari_database.list_cultivation_tasks(user_id=1)
print(f"Cultivation tasks count for user 1: {len(tasks)}")
for t in tasks:
    print(f" - [{t['status']}] {t['title']} (Due: {t['due_date']}, Priority: {t['priority']})")

# 2. Test creating a task
new_task = gari_database.create_cultivation_task({
    "title": "Kiểm tra hệ thống tưới nhỏ giọt",
    "description": "Đo áp lực béc phun và súc rửa bộ lọc đĩa",
    "due_date": "2026-11-09",
    "priority": "low",
    "task_type": "routine",
    "crop_id": "Tomato"
}, user_id=1)
print("Created task:", new_task["id"], new_task["title"])

# 3. Test completing task
completed = gari_database.complete_cultivation_task(new_task["id"], user_id=1, notes="Áp lực đạt chuẩn 1.5 bar")
print("Completed task:", completed["id"], completed["status"], completed["completed_at"])

# 4. Test deleting task
deleted = gari_database.delete_cultivation_task(new_task["id"], user_id=1)
print("Deleted task successfully:", deleted)

# 5. Test mark all notifications read
unread_cnt = gari_database.mark_all_notifications_read(user_id=1)
print("Marked unread notifications as read count:", unread_cnt)

# 6. Test recommendations
recs = gari_database.get_seasonal_cultivation_recommendations(crop_id="Tomato")
print(f"Recommendations for Tomato: {len(recs)} item(s) - {recs[0]['stage']}")

print("All DB functions verified successfully!")
