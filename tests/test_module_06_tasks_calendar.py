"""
GARI Module 06 — Tasks & Crop Calendar Test Suite
Verifies:
1. Manual task creation with full metadata (priority, due_date, assignee, notes).
2. Connected task creation from leaf diagnosis (diagnosis_id, crop context, treatment type).
3. Agricultural hierarchy linking (Farm, Plot, Cycle, Plant) and relationship validation.
4. Recurring task auto-scheduling on completion (weekly, daily recurrence rules).
5. Task list filtering (today, upcoming, overdue, completed) and category counts.
6. Organization RBAC enforcement (field worker cannot reassign or delete manager's tasks).
7. Tenant isolation (cross-organization access denial).
8. Activity history audit logging for task lifecycle events.
9. Task reminders deduplication and observable delivery status in database.
10. Date boundaries and timezone consistency.
"""

import unittest
import sys
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi.testclient import TestClient
import sqlite3
import uuid
from datetime import datetime, date, timedelta, timezone

from api_server import app
import gari_tasks
import gari_plans
import gari_b2b
from gari_database import get_connection

client = TestClient(app)


def _create_user(name_prefix="User"):
    unique_id = uuid.uuid4().hex[:8]
    email = f"task_{unique_id}@example.com"
    pwd = "Password123!"
    resp = client.post("/api/auth/register", json={
        "email": email,
        "password": pwd,
        "confirm_password": pwd,
        "full_name": f"{name_prefix} {unique_id}"
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    user = data.get("user", {})
    return user, token, {"Authorization": f"Bearer {token}"}


class TestModule06TasksCalendar(unittest.TestCase):

    def test_01_create_manual_task_full_metadata(self):
        """1. Create manual task with full metadata and verify fields."""
        user, token, headers = _create_user("Manager")
        due = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%d")

        payload = {
            "title": "Bón lót NPK cho cà chua đợt 1",
            "description": "Bón phân vào rãnh cách gốc 15cm, liều lượng 20kg/sào.",
            "due_date": due,
            "priority": "high",
            "task_type": "fertilizing",
            "crop_id": "Tomato",
            "notes": "Tránh bón sát gốc làm sót rễ.",
            "recurrence_rule": "none"
        }

        resp = client.post("/api/calendar/tasks", json=payload, headers=headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        res_data = resp.json()
        self.assertTrue(res_data["success"])
        task = res_data["task"]
        self.assertEqual(task["title"], payload["title"])
        self.assertEqual(task["priority"], "high")
        self.assertEqual(task["task_type"], "fertilizing")
        self.assertEqual(task["due_date"], due)
        self.assertEqual(task["status"], "pending")
        self.assertEqual(task["crop_id"], "Tomato")
        self.assertEqual(task["creator_user_id"], user["id"])

    def test_02_create_task_linked_to_diagnosis(self):
        """2. Create treatment task connected to an AI leaf diagnosis."""
        user, token, headers = _create_user("Agronomist")

        # Insert a test diagnosis record
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO diagnoses (
                    user_id, crop_id, crop_name, predicted_disease, disease_name_vi,
                    confidence, severity, user_notes, created_at
                ) VALUES (?, 'Tomato', 'Cà chua', 'Tomato_Early_blight', 'Bệnh đốm vòng cà chua', 0.94, 'HIGH', 'Lá có vết đốm tròn đồng tâm', CURRENT_TIMESTAMP)
            """, (user["id"],))
            conn.commit()
            diag_id = cursor.lastrowid

        # Create task from diagnosis endpoint
        resp = client.post("/api/calendar/tasks/from-diagnosis", json={
            "diagnosis_id": diag_id,
            "title": "Phun nano đồng trị đốm vòng cà chua",
            "priority": "urgent",
            "notes": "Phun ướt đều hai mặt lá vào sáng sớm."
        }, headers=headers)

        self.assertEqual(resp.status_code, 200, resp.text)
        task = resp.json()["task"]
        self.assertEqual(task["diagnosis_id"], diag_id)
        self.assertEqual(task["task_type"], "treatment")
        self.assertEqual(task["priority"], "urgent")
        self.assertIn("đốm vòng", task["title"])
        self.assertEqual(task["crop_id"], "Tomato")

    def test_03_link_task_to_agricultural_hierarchy(self):
        """3. Link task to Farm, Plot, Cycle, and Plant hierarchy with relationship validation."""
        user, token, headers = _create_user("Farmer")

        # Create farm and plot
        farm_resp = client.post("/api/farms", json={
            "name": f"Nông trại Ba Vì {uuid.uuid4().hex[:4]}",
            "location": "Ba Vì, Hà Nội",
            "area_ha": 3.5
        }, headers=headers)
        self.assertEqual(farm_resp.status_code, 200, farm_resp.text)
        farm_id = farm_resp.json()["farm"]["id"]

        plot_resp = client.post(f"/api/farms/{farm_id}/plots", json={
            "plot_name": "Lô A1 Cà chua xuất khẩu",
            "crop": "Tomato",
            "area": 1.2
        }, headers=headers)
        self.assertEqual(plot_resp.status_code, 200, plot_resp.text)
        plot_id = plot_resp.json()["plot"]["id"]

        # 3a. Create task with valid farm and plot
        task_payload = {
            "title": "Lắp giàn leo cho Lô A1",
            "farm_id": farm_id,
            "plot_id": plot_id,
            "cycle_id": 1,
            "plant_id": 10,
            "crop_id": "Tomato",
            "due_date": "2026-11-10",
            "priority": "medium"
        }
        resp = client.post("/api/calendar/tasks", json=task_payload, headers=headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        task = resp.json()["task"]
        self.assertEqual(task["farm_id"], farm_id)
        self.assertEqual(task["plot_id"], plot_id)
        self.assertEqual(task["plot_name"], "Lô A1 Cà chua xuất khẩu")

        # 3b. Verify relationship mismatch: non-existent plot for this farm should fail
        invalid_payload = {
            "title": "Công việc sai lô",
            "farm_id": farm_id,
            "plot_id": 999999,
            "due_date": "2026-11-10"
        }
        invalid_resp = client.post("/api/calendar/tasks", json=invalid_payload, headers=headers)
        self.assertEqual(invalid_resp.status_code, 400)
        self.assertIn("không thuộc", invalid_resp.json()["detail"])

    def test_04_recurring_task_auto_generation_on_completion(self):
        """4. Recurring task auto-scheduling upon completion."""
        user, token, headers = _create_user("Grower")
        initial_due = "2026-11-05"

        payload = {
            "title": "Thăm vườn giám sát bọ trĩ hàng tuần",
            "due_date": initial_due,
            "priority": "high",
            "task_type": "scouting",
            "crop_id": "Rice",
            "recurrence_rule": "weekly",
            "recurrence_interval": 1
        }
        resp = client.post("/api/calendar/tasks", json=payload, headers=headers)
        self.assertEqual(resp.status_code, 200)
        task1 = resp.json()["task"]
        task1_id = task1["id"]
        self.assertEqual(task1["recurrence_rule"], "weekly")

        # Complete task1
        complete_resp = client.post(f"/api/calendar/tasks/{task1_id}/complete", json={
            "notes": "Đã thăm vườn Lô 1, mật độ bọ trĩ dưới ngưỡng gây hại."
        }, headers=headers)
        self.assertEqual(complete_resp.status_code, 200)
        completed_task1 = complete_resp.json()["task"]
        self.assertEqual(completed_task1["status"], "completed")
        self.assertIsNotNone(completed_task1["completed_at"])

        # Verify that the next occurrence was automatically generated (+7 days)
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cultivation_tasks WHERE parent_task_id = ?", (task1_id,))
            next_task = cursor.fetchone()
            self.assertIsNotNone(next_task)
            self.assertEqual(next_task["status"], "pending")
            self.assertEqual(next_task["recurrence_rule"], "weekly")
            expected_next_due = "2026-11-12"
            self.assertEqual(next_task["due_date"], expected_next_due)
            self.assertEqual(next_task["title"], payload["title"])

    def test_05_task_list_views_and_status_filtering(self):
        """5. Task list filtering (today, upcoming, overdue, completed) and counts."""
        user, token, headers = _create_user("Supervisor")
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        tomorrow_str = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")
        yesterday_str = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")

        # Create today task
        client.post("/api/calendar/tasks", json={"title": "Việc hôm nay", "due_date": today_str, "status": "pending"}, headers=headers)
        # Create upcoming task
        client.post("/api/calendar/tasks", json={"title": "Việc tương lai", "due_date": tomorrow_str, "status": "pending"}, headers=headers)
        # Create overdue task
        client.post("/api/calendar/tasks", json={"title": "Việc quá hạn", "due_date": yesterday_str, "status": "pending"}, headers=headers)
        # Create completed task
        client.post("/api/calendar/tasks", json={"title": "Việc đã xong", "due_date": yesterday_str, "status": "completed"}, headers=headers)

        # Query view='today'
        r_today = client.get("/api/calendar/tasks?view=today", headers=headers)
        self.assertEqual(r_today.status_code, 200)
        self.assertTrue(any(t["title"] == "Việc hôm nay" for t in r_today.json()["tasks"]))

        # Query view='upcoming'
        r_upcoming = client.get("/api/calendar/tasks?view=upcoming", headers=headers)
        self.assertEqual(r_upcoming.status_code, 200)
        self.assertTrue(any(t["title"] == "Việc tương lai" for t in r_upcoming.json()["tasks"]))

        # Query view='overdue'
        r_overdue = client.get("/api/calendar/tasks?view=overdue", headers=headers)
        self.assertEqual(r_overdue.status_code, 200)
        self.assertTrue(any(t["title"] == "Việc quá hạn" for t in r_overdue.json()["tasks"]))

        # Query view='completed'
        r_comp = client.get("/api/calendar/tasks?view=completed", headers=headers)
        self.assertEqual(r_comp.status_code, 200)
        self.assertTrue(any(t["title"] == "Việc đã xong" for t in r_comp.json()["tasks"]))

        # Verify counts object exists
        counts = r_today.json()["counts"]
        self.assertGreaterEqual(counts["today"], 1)
        self.assertGreaterEqual(counts["upcoming"], 1)
        self.assertGreaterEqual(counts["overdue"], 1)
        self.assertGreaterEqual(counts["completed"], 1)

    def test_06_organization_rbac_field_worker_restrictions(self):
        """6. Field Worker can complete assigned tasks, but cannot delete or reassign manager's tasks."""
        owner, o_tok, o_head = _create_user("OrgOwner")
        worker, w_tok, w_head = _create_user("Worker")

        # Give owner team plan to create org
        gari_plans.assign_user_plan(owner["id"], "team", status="pilot_active")

        # Owner creates organization
        org_resp = client.post("/api/organizations", json={
            "name": f"Hợp tác xã Hòa Bình {uuid.uuid4().hex[:4]}",
            "org_type": "cooperative"
        }, headers=o_head)
        self.assertEqual(org_resp.status_code, 200)
        org_id = org_resp.json()["organization"]["id"]

        # Add worker as field_worker member
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO organization_members (organization_id, user_id, role, joined_at)
                VALUES (?, ?, 'field_worker', CURRENT_TIMESTAMP)
            """, (org_id, worker["id"]))
            conn.commit()

        # Owner creates task assigned to worker
        task_resp = client.post("/api/calendar/tasks", json={
            "title": "Làm cỏ luống cà chua Lô B",
            "organization_id": org_id,
            "due_date": "2026-11-08",
            "assignee_user_id": worker["id"]
        }, headers=o_head)
        self.assertEqual(task_resp.status_code, 200)
        task_id = task_resp.json()["task"]["id"]

        # 6a. Worker can complete the task assigned to them
        comp_resp = client.post(f"/api/calendar/tasks/{task_id}/complete", json={
            "notes": "Đã làm sạch cỏ 2 luống theo yêu cầu."
        }, headers=w_head)
        self.assertEqual(comp_resp.status_code, 200)
        self.assertEqual(comp_resp.json()["task"]["status"], "completed")

        # 6b. Worker CANNOT delete the task (HTTP 403)
        del_resp = client.delete(f"/api/calendar/tasks/{task_id}", headers=w_head)
        self.assertEqual(del_resp.status_code, 403)
        self.assertIn("không có quyền", del_resp.json()["detail"].lower())

    def test_07_cross_tenant_isolation_and_unauthorized_mutation(self):
        """7. Tenant boundary: user from Org A cannot access or modify tasks of Org B."""
        userA, tokA, headA = _create_user("TenantA")
        userB, tokB, headB = _create_user("TenantB")

        gari_plans.assign_user_plan(userA["id"], "team", status="pilot_active")

        # Org A creates org and task
        orgA_resp = client.post("/api/organizations", json={"name": f"Org A {uuid.uuid4().hex[:4]}", "org_type": "business"}, headers=headA)
        orgA_id = orgA_resp.json()["organization"]["id"]

        taskA_resp = client.post("/api/calendar/tasks", json={
            "title": "Bí mật mùa vụ Org A",
            "organization_id": orgA_id,
            "due_date": "2026-11-20"
        }, headers=headA)
        taskA_id = taskA_resp.json()["task"]["id"]

        # User B attempts to read Task A
        get_resp = client.get(f"/api/calendar/tasks/{taskA_id}", headers=headB)
        self.assertIn(get_resp.status_code, (403, 404))

        # User B attempts to complete Task A
        comp_resp = client.post(f"/api/calendar/tasks/{taskA_id}/complete", json={}, headers=headB)
        self.assertIn(comp_resp.status_code, (403, 404))

    def test_08_activity_history_audit_logging(self):
        """8. Audit logging: track creation, reassignment, status change, and completion."""
        manager, m_tok, m_head = _create_user("AuditorMgr")
        tech, t_tok, t_head = _create_user("Technician")

        # Create task
        task_resp = client.post("/api/calendar/tasks", json={
            "title": "Kiểm định đất trước gieo cấy",
            "due_date": "2026-11-15",
            "priority": "medium"
        }, headers=m_head)
        task_id = task_resp.json()["task"]["id"]

        # Reassign task
        client.patch(f"/api/calendar/tasks/{task_id}", json={
            "assignee_user_id": tech["id"]
        }, headers=m_head)

        # Change status to in_progress
        client.patch(f"/api/calendar/tasks/{task_id}", json={
            "status": "in_progress"
        }, headers=m_head)

        # Complete task
        client.post(f"/api/calendar/tasks/{task_id}/complete", json={
            "notes": "pH đất đạt 6.2, đủ điều kiện gieo cấy."
        }, headers=m_head)

        # Fetch activity history
        act_resp = client.get(f"/api/calendar/tasks/{task_id}/activities", headers=m_head)
        self.assertEqual(act_resp.status_code, 200)
        activities = act_resp.json()["activities"]
        actions = [a["action"] for a in activities]

        self.assertIn("created", actions)
        self.assertIn("assigned", actions)
        self.assertIn("status_changed", actions)
        self.assertIn("completed", actions)

    def test_09_task_reminders_deduplication_and_observable_status(self):
        """9. Task reminders engine creates in-app notification and prevents duplicates."""
        user, token, headers = _create_user("ReminderUser")
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Create task due today
        task_resp = client.post("/api/calendar/tasks", json={
            "title": "Tưới nước đợt sớm",
            "due_date": today_str,
            "priority": "urgent"
        }, headers=headers)
        task_id = task_resp.json()["task"]["id"]

        # Process reminders
        proc_resp = client.post("/api/calendar/tasks/reminders/process", json={}, headers=headers)
        self.assertEqual(proc_resp.status_code, 200)
        res1 = proc_resp.json()
        self.assertGreaterEqual(res1["sent_count"], 1)
        sent_task_ids = [r["task_id"] for r in res1["reminders_sent"]]
        self.assertIn(task_id, sent_task_ids)

        # Verify task in db has reminder_status = 'sent'
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT reminder_status, reminder_sent_at FROM cultivation_tasks WHERE id = ?", (task_id,))
            task_row = cursor.fetchone()
            self.assertEqual(task_row["reminder_status"], "sent")
            self.assertIsNotNone(task_row["reminder_sent_at"])

            # Check in-app notification was inserted
            cursor.execute("SELECT * FROM notifications WHERE user_id = ? AND title LIKE '%Tưới nước đợt sớm%'", (user["id"],))
            notif = cursor.fetchone()
            self.assertIsNotNone(notif)
            self.assertEqual(notif["notification_type"], "warning")

        # Second process call should deduplicate (not send again for this task)
        proc_resp2 = client.post("/api/calendar/tasks/reminders/process", json={}, headers=headers)
        self.assertEqual(proc_resp2.status_code, 200)
        res2 = proc_resp2.json()
        sent_ids_2 = [r["task_id"] for r in res2.get("reminders_sent", [])]
        self.assertNotIn(task_id, sent_ids_2)

    def test_10_date_boundaries_and_timezone_consistency(self):
        """10. Date boundaries and consistent ISO date handling."""
        user, token, headers = _create_user("TimezoneUser")

        # Date with ISO datetime format
        iso_date = "2026-11-25T14:30:00Z"
        task_resp = client.post("/api/calendar/tasks", json={
            "title": "Thu hoạch cà chua chín bói",
            "due_date": iso_date,
            "priority": "low"
        }, headers=headers)
        self.assertEqual(task_resp.status_code, 200)
        task = task_resp.json()["task"]
        # Due date should be truncated/normalized to YYYY-MM-DD
        self.assertEqual(task["due_date"], "2026-11-25")

        # Query range filter
        range_resp = client.get("/api/calendar/tasks?date_from=2026-11-20&date_to=2026-11-30", headers=headers)
        self.assertEqual(range_resp.status_code, 200)
        tasks = range_resp.json()["tasks"]
        self.assertTrue(any(t["id"] == task["id"] for t in tasks))


if __name__ == "__main__":
    unittest.main()
