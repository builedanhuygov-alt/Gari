"""
GARI AI LAB — Phase 5.8 Critical Security Remediation Regression Suite
Tests Sprint 1 security remediations (SEC-01 to SEC-04) and verifies
all 9 mandatory security & authorization boundary scenarios.
"""

import os
import sys
import json
import unittest
from pathlib import Path

# Enforce test environment
os.environ["APP_ENV"] = "test"
os.environ["GARI_ENV"] = "test"
os.environ["DEBUG"] = "0"

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
import gari_auth
import gari_database
from api_server import app


class TestPhase58SecurityRemediation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

        with gari_database.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Create or ensure test users
            # User A (Farmer A)
            cursor.execute("SELECT id FROM users WHERE email = 'test_farmer_a_sec@gari.vn'")
            row = cursor.fetchone()
            if row:
                cls.user_a_id = row["id"]
            else:
                cursor.execute("""
                    INSERT INTO users (email, full_name, account_type, is_admin, is_expert, is_host_admin)
                    VALUES ('test_farmer_a_sec@gari.vn', 'Test Farmer A', 'farmer', 0, 0, 0)
                """)
                cls.user_a_id = cursor.lastrowid

            # User B (Farmer B)
            cursor.execute("SELECT id FROM users WHERE email = 'test_farmer_b_sec@gari.vn'")
            row = cursor.fetchone()
            if row:
                cls.user_b_id = row["id"]
            else:
                cursor.execute("""
                    INSERT INTO users (email, full_name, account_type, is_admin, is_expert, is_host_admin)
                    VALUES ('test_farmer_b_sec@gari.vn', 'Test Farmer B', 'farmer', 0, 0, 0)
                """)
                cls.user_b_id = cursor.lastrowid

            # Expert 1 (Assigned Expert)
            cursor.execute("SELECT id FROM users WHERE email = 'test_expert_1_sec@gari.vn'")
            row = cursor.fetchone()
            if row:
                cls.expert_1_id = row["id"]
            else:
                cursor.execute("""
                    INSERT INTO users (email, full_name, account_type, is_admin, is_expert, is_host_admin)
                    VALUES ('test_expert_1_sec@gari.vn', 'Test Expert One', 'expert', 0, 1, 0)
                """)
                cls.expert_1_id = cursor.lastrowid

            # Expert 2 (Unassigned Expert)
            cursor.execute("SELECT id FROM users WHERE email = 'test_expert_2_sec@gari.vn'")
            row = cursor.fetchone()
            if row:
                cls.expert_2_id = row["id"]
            else:
                cursor.execute("""
                    INSERT INTO users (email, full_name, account_type, is_admin, is_expert, is_host_admin)
                    VALUES ('test_expert_2_sec@gari.vn', 'Test Expert Two', 'expert', 0, 1, 0)
                """)
                cls.expert_2_id = cursor.lastrowid

            # Host Admin User (id 1 or custom)
            cursor.execute("SELECT id FROM users WHERE is_host_admin = 1 LIMIT 1")
            admin_row = cursor.fetchone()
            cls.admin_id = admin_row["id"] if admin_row else 1

            # 2. Create test diagnosis owned by User A
            cursor.execute("""
                INSERT INTO diagnoses (
                    user_id, crop_id, crop_name, predicted_disease, disease_name_vi, confidence, diagnosis_status, created_at
                ) VALUES (?, 'tomato', 'Cà chua', 'Tomato_Bacterial_spot', 'Đốm lá vi khuẩn', 0.95, 'completed', CURRENT_TIMESTAMP)
            """, (cls.user_a_id,))
            cls.diag_a_id = cursor.lastrowid

            # 3. Create test expert case owned by User A, assigned to Expert 1
            cursor.execute("""
                INSERT INTO expert_cases (
                    user_id, farmer_name, crop_name, symptoms_description, status, assigned_expert_id, assigned_expert
                ) VALUES (?, 'Test Farmer A', 'Cà chua', 'Lá xoăn vàng đốm nâu nghiêm trọng', 'in_review', ?, 'Test Expert One')
            """, (cls.user_a_id, cls.expert_1_id))
            cls.case_id = cursor.lastrowid

            # Add an initial case message
            cursor.execute("""
                INSERT INTO expert_case_messages (
                    case_id, sender_user_id, sender_role, sender_name, message
                ) VALUES (?, ?, 'farmer', 'Test Farmer A', 'Kính nhờ chuyên gia thẩm định giúp vườn cà chua.')
            """, (cls.case_id, cls.user_a_id))
            cls.initial_msg_id = cursor.lastrowid

            # 4. Create an isolated organization where User A is NOT a member
            cursor.execute("SELECT id FROM organizations WHERE name = 'Isolated Secure Org B'")
            org_row = cursor.fetchone()
            if org_row:
                cls.isolated_org_id = org_row["id"]
            else:
                cursor.execute("""
                    INSERT INTO organizations (name, slug, owner_id)
                    VALUES ('Isolated Secure Org B', 'isolated-secure-org-b', ?)
                """, (cls.user_b_id,))
                cls.isolated_org_id = cursor.lastrowid

            conn.commit()

        # Generate sessions
        cls.token_user_a = gari_auth.create_session(cls.user_a_id)
        cls.token_user_b = gari_auth.create_session(cls.user_b_id)
        cls.token_expert_1 = gari_auth.create_session(cls.expert_1_id)
        cls.token_expert_2 = gari_auth.create_session(cls.expert_2_id)
        cls.token_admin = gari_auth.create_session(cls.admin_id)

    @classmethod
    def tearDownClass(cls):
        """Cleanup test records to preserve pristine database state."""
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM expert_case_messages WHERE case_id = ?", (cls.case_id,))
            cursor.execute("DELETE FROM expert_cases WHERE id = ?", (cls.case_id,))
            cursor.execute("DELETE FROM diagnoses WHERE id = ?", (cls.diag_a_id,))
            cursor.execute("DELETE FROM user_sessions WHERE user_id IN (?, ?, ?, ?)", (
                cls.user_a_id, cls.user_b_id, cls.expert_1_id, cls.expert_2_id
            ))
            cursor.execute("DELETE FROM organizations WHERE id = ?", (cls.isolated_org_id,))
            cursor.execute("DELETE FROM users WHERE email IN ('test_farmer_a_sec@gari.vn', 'test_farmer_b_sec@gari.vn', 'test_expert_1_sec@gari.vn', 'test_expert_2_sec@gari.vn')")
            conn.commit()

    # -------------------------------------------------------------------------
    # Scenario 1: Anonymous Access to Diagnosis List Blocked
    # -------------------------------------------------------------------------
    def test_01_anonymous_cannot_list_diagnoses(self):
        """SEC-01: Anonymous request to GET /api/diagnoses must return HTTP 401."""
        response = self.client.get("/api/diagnoses")
        self.assertEqual(response.status_code, 401, f"Expected 401, got {response.status_code}: {response.text}")
        self.assertIn("Chưa đăng nhập", response.json().get("detail", ""))

    # -------------------------------------------------------------------------
    # Scenario 2: Anonymous Access to Single Diagnosis Detail Blocked
    # -------------------------------------------------------------------------
    def test_02_anonymous_cannot_read_diagnosis_detail(self):
        """SEC-01: Anonymous request to GET /api/diagnoses/{id} must return HTTP 401."""
        response = self.client.get(f"/api/diagnoses/{self.diag_a_id}")
        self.assertEqual(response.status_code, 401, f"Expected 401, got {response.status_code}: {response.text}")

    # -------------------------------------------------------------------------
    # Scenario 3: Cross-User Diagnosis IDOR Blocked
    # -------------------------------------------------------------------------
    def test_03_cross_user_diagnosis_idor_blocked(self):
        """SEC-01: User B attempting to read User A's diagnosis must return HTTP 403 or 404."""
        headers = {"Authorization": f"Bearer {self.token_user_b}"}
        response = self.client.get(f"/api/diagnoses/{self.diag_a_id}", headers=headers)
        self.assertIn(
            response.status_code,
            [403, 404],
            f"Expected 403 or 404 for cross-user diagnosis access, got {response.status_code}: {response.text}"
        )

    # -------------------------------------------------------------------------
    # Scenario 4: Anonymous Access to Notifications Blocked
    # -------------------------------------------------------------------------
    def test_04_anonymous_cannot_read_notifications(self):
        """SEC-02: Anonymous request to GET /api/notifications must return HTTP 401 (not fallback to User 1)."""
        response = self.client.get("/api/notifications")
        self.assertEqual(response.status_code, 401, f"Expected 401, got {response.status_code}: {response.text}")

    # -------------------------------------------------------------------------
    # Scenario 5: Anonymous Access to Calendar Tasks Blocked
    # -------------------------------------------------------------------------
    def test_05_anonymous_cannot_access_or_modify_calendar_tasks(self):
        """SEC-02: Anonymous requests to /api/calendar/tasks must return HTTP 401."""
        get_res = self.client.get("/api/calendar/tasks")
        self.assertEqual(get_res.status_code, 401, f"Expected 401, got {get_res.status_code}")

        post_res = self.client.post("/api/calendar/tasks", json={"title": "Hacked Task"})
        self.assertEqual(post_res.status_code, 401, f"Expected 401, got {post_res.status_code}")

    # -------------------------------------------------------------------------
    # Scenario 6: Cross-Organization Farm Isolation Enforced
    # -------------------------------------------------------------------------
    def test_06_cross_org_farm_isolation_enforced(self):
        """SEC-03: User A attempting to view farms in Org B where they are not a member returns HTTP 403."""
        headers = {"Authorization": f"Bearer {self.token_user_a}"}
        response = self.client.get(f"/api/farms?org_id={self.isolated_org_id}", headers=headers)
        self.assertEqual(
            response.status_code,
            403,
            f"Expected 403 Forbidden for cross-org access, got {response.status_code}: {response.text}"
        )
        self.assertIn("không phải thành viên của tổ chức", response.json().get("detail", ""))

    # -------------------------------------------------------------------------
    # Scenario 7: Assigned Expert Can Access and Post Case Messages
    # -------------------------------------------------------------------------
    def test_07_assigned_expert_can_access_case_messages(self):
        """SEC-04: Assigned expert (Expert 1) can read and post case messages."""
        headers = {"Authorization": f"Bearer {self.token_expert_1}"}

        # 1. Read messages
        get_res = self.client.get(f"/api/expert/cases/{self.case_id}/messages", headers=headers)
        self.assertEqual(get_res.status_code, 200, f"Expected 200, got {get_res.status_code}: {get_res.text}")
        data = get_res.json()
        self.assertTrue(data.get("success"))
        self.assertGreaterEqual(len(data.get("messages", [])), 1)

        # 2. Post a message
        post_payload = {
            "message": "Tôi đã tiếp nhận và đang tiến hành phân tích triệu chứng.",
            "attachments": []
        }
        post_res = self.client.post(f"/api/expert/cases/{self.case_id}/messages", json=post_payload, headers=headers)
        self.assertEqual(post_res.status_code, 200, f"Expected 200, got {post_res.status_code}: {post_res.text}")
        self.assertTrue(post_res.json().get("success"))

    # -------------------------------------------------------------------------
    # Scenario 8: Unassigned Expert Denied Access to Another Expert's Case
    # -------------------------------------------------------------------------
    def test_08_unassigned_expert_denied_access_to_case_messages(self):
        """SEC-04: Unassigned expert (Expert 2) is rejected from reading or posting to Expert 1's case."""
        headers = {"Authorization": f"Bearer {self.token_expert_2}"}

        # 1. Attempt to read messages
        get_res = self.client.get(f"/api/expert/cases/{self.case_id}/messages", headers=headers)
        self.assertEqual(
            get_res.status_code,
            403,
            f"Expected 403 for unassigned expert reading messages, got {get_res.status_code}: {get_res.text}"
        )

        # 2. Attempt to post message
        post_payload = {"message": "Can thiệp trái phép từ chuyên gia khác."}
        post_res = self.client.post(f"/api/expert/cases/{self.case_id}/messages", json=post_payload, headers=headers)
        self.assertEqual(
            post_res.status_code,
            403,
            f"Expected 403 for unassigned expert posting message, got {post_res.status_code}: {post_res.text}"
        )

    # -------------------------------------------------------------------------
    # Scenario 9: Valid Owner and Host Admin Workflows Remain Functional
    # -------------------------------------------------------------------------
    def test_09_valid_owner_and_admin_workflows(self):
        """Verifies legitimate owner and host admin access are completely unhindered."""
        headers_owner = {"Authorization": f"Bearer {self.token_user_a}"}
        headers_admin = {"Authorization": f"Bearer {self.token_admin}"}

        # 1. Owner can list their own diagnoses
        owner_list = self.client.get("/api/diagnoses", headers=headers_owner)
        self.assertEqual(owner_list.status_code, 200)
        items = owner_list.json().get("diagnoses", [])
        self.assertTrue(any(d["id"] == self.diag_a_id for d in items))

        # 2. Owner can read their single diagnosis detail
        owner_diag = self.client.get(f"/api/diagnoses/{self.diag_a_id}", headers=headers_owner)
        self.assertEqual(owner_diag.status_code, 200)
        self.assertEqual(owner_diag.json().get("diagnosis", {}).get("crop_name"), "Cà chua")

        # 3. Owner can view their expert case messages
        owner_msgs = self.client.get(f"/api/expert/cases/{self.case_id}/messages", headers=headers_owner)
        self.assertEqual(owner_msgs.status_code, 200)

        # 4. Host Admin can view case messages for platform moderation
        admin_msgs = self.client.get(f"/api/expert/cases/{self.case_id}/messages", headers=headers_admin)
        self.assertEqual(admin_msgs.status_code, 200)


if __name__ == "__main__":
    unittest.main()
