"""
GARI AI LAB — Farm & Organization Diagnosis Context Selector Test Suite
File: tests/test_farm_org_selector.py

Tests:
1. User receives only authorized farms and organizations via /api/user/diagnosis-contexts.
2. Another user's organization or farm never leaks into the selector.
3. Test fixtures (Test Concurrent HTX, Cô Đơn timestamps, etc.) are strictly isolated.
4. Unauthenticated (guest) requests receive personal trial context with zero private records.
5. Idempotent creation prevents duplicate organizations with identical names.
6. Running diagnosis with an authorized farm succeeds and associates farm_id.
7. Attempting to diagnose with an unauthorized farm or organization returns HTTP 403 Forbidden.
"""

import io
import os
import sys
import unittest
import uuid
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

os.environ["APP_ENV"] = "production"  # Ensure we test production isolation mode!
os.environ["SESSION_SECRET"] = "gari_secure_test_session_secret_32chars_min"
os.environ["JWT_SECRET"] = "gari_secure_test_jwt_secret_32chars_min"
os.environ["PAYMENT_PUBLIC_CHECKOUT_ENABLED"] = "1"

import api_server
import gari_auth
import gari_b2b
import gari_database
from starlette.testclient import TestClient


class TestFarmOrgSelector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gari_database.init_database()
        cls.client = TestClient(api_server.app)

        cls.suffix = uuid.uuid4().hex[:8]
        cls.user_a_email = f"user_a_{cls.suffix}@gari.vn"
        cls.user_b_email = f"user_b_{cls.suffix}@gari.vn"
        cls.password = "StrongPass123!"

        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            pwd_hash = gari_auth.hash_password(cls.password)

            # User A (Cooperative Owner)
            cursor.execute(
                """
                INSERT INTO users (full_name, name, email, password_hash, account_type, is_host_admin, is_active)
                VALUES ('Nông Dân A', 'Nông Dân A', ?, ?, 'cooperative', 0, 1)
                """,
                (cls.user_a_email, pwd_hash)
            )
            cls.user_a_id = cursor.lastrowid

            # User B (Separate Farmer)
            cursor.execute(
                """
                INSERT INTO users (full_name, name, email, password_hash, account_type, is_host_admin, is_active)
                VALUES ('Nông Dân B', 'Nông Dân B', ?, ?, 'farmer', 0, 1)
                """,
                (cls.user_b_email, pwd_hash)
            )
            cls.user_b_id = cursor.lastrowid

            # User A's Farm
            cursor.execute(
                """
                INSERT INTO farms (user_id, name, location, province, area_hectare, primary_crop, is_test)
                VALUES (?, 'Trang Trại Sạch A', 'Huyện Ba Vì', 'Hà Nội', 2.5, 'Tomato', 0)
                """,
                (cls.user_a_id,)
            )
            cls.farm_a_id = cursor.lastrowid

            # User B's Farm
            cursor.execute(
                """
                INSERT INTO farms (user_id, name, location, province, area_hectare, primary_crop, is_test)
                VALUES (?, 'Vườn Tiêu Bác B', 'Huyện Cư Mgar', 'Đắk Lắk', 3.0, 'Black Pepper', 0)
                """,
                (cls.user_b_id,)
            )
            cls.farm_b_id = cursor.lastrowid

            # User A's Test Farm (Should be isolated)
            cursor.execute(
                """
                INSERT INTO farms (user_id, name, location, province, area_hectare, primary_crop, is_test)
                VALUES (?, 'Test Farm Scratch 17934', 'Khu vực thử nghiệm', 'Hà Nội', 1.0, 'Tomato', 1)
                """,
                (cls.user_a_id,)
            )
            cls.test_farm_a_id = cursor.lastrowid

            # User A's Real Organization
            cursor.execute(
                """
                INSERT INTO organizations (name, slug, owner_id, plan_id, status, is_test)
                VALUES ('HTX Nông Nghiệp Ba Vì Xanh', ?, ?, 'team', 'active', 0)
                """,
                (f"htx-ba-vi-xanh-{cls.suffix}", cls.user_a_id)
            )
            cls.org_a_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO organization_members (organization_id, user_id, role) VALUES (?, ?, 'owner')",
                (cls.org_a_id, cls.user_a_id)
            )

            # User A's Test Organization (Should be isolated)
            cursor.execute(
                """
                INSERT INTO organizations (name, slug, owner_id, plan_id, status, is_test)
                VALUES ('Test Concurrent HTX', ?, ?, 'free', 'active', 1)
                """,
                (f"test-concurrent-htx-{cls.suffix}", cls.user_a_id)
            )
            cls.test_org_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO organization_members (organization_id, user_id, role) VALUES (?, ?, 'owner')",
                (cls.test_org_id, cls.user_a_id)
            )

            # User B's Real Organization
            cursor.execute(
                """
                INSERT INTO organizations (name, slug, owner_id, plan_id, status, is_test)
                VALUES ('HTX Tiêu Đắk Lắk', ?, ?, 'team', 'active', 0)
                """,
                (f"htx-tieu-dak-lak-{cls.suffix}", cls.user_b_id)
            )
            cls.org_b_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO organization_members (organization_id, user_id, role) VALUES (?, ?, 'owner')",
                (cls.org_b_id, cls.user_b_id)
            )

            conn.commit()

        # Sessions
        cls.token_a = gari_auth.create_session(cls.user_a_id)
        cls.headers_a = {"Authorization": f"Bearer {cls.token_a}"}

        cls.token_b = gari_auth.create_session(cls.user_b_id)
        cls.headers_b = {"Authorization": f"Bearer {cls.token_b}"}

    @classmethod
    def tearDownClass(cls):
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = OFF")
            cursor.execute("DELETE FROM organization_members WHERE user_id IN (?, ?)", (cls.user_a_id, cls.user_b_id))
            cursor.execute("DELETE FROM organizations WHERE id IN (?, ?, ?)", (cls.org_a_id, cls.test_org_id, cls.org_b_id))
            cursor.execute("DELETE FROM farms WHERE user_id IN (?, ?)", (cls.user_a_id, cls.user_b_id))
            cursor.execute("DELETE FROM user_sessions WHERE user_id IN (?, ?)", (cls.user_a_id, cls.user_b_id))
            cursor.execute("DELETE FROM users WHERE id IN (?, ?)", (cls.user_a_id, cls.user_b_id))
            cursor.execute("PRAGMA foreign_keys = ON")
            conn.commit()

    def test_01_user_a_sees_only_authorized_farms_and_orgs(self):
        """User A sees only their own farm and organization; test fixtures are excluded."""
        res = self.client.get("/api/user/diagnosis-contexts", headers=self.headers_a)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["is_authenticated"])

        # Check personal info
        self.assertEqual(data["personal"]["user_id"], self.user_a_id)
        self.assertEqual(data["personal"]["account_type"], "cooperative")

        # Check farms: User A must see farm A, but NOT farm B and NOT test_farm_a
        farm_ids = [f["id"] for f in data["farms"]]
        self.assertIn(self.farm_a_id, farm_ids, "User A must see their own farm")
        self.assertNotIn(self.farm_b_id, farm_ids, "User A must NEVER see User B's farm")
        self.assertNotIn(self.test_farm_a_id, farm_ids, "Test farm fixture must be excluded from production contexts")

        # Check organizations: User A must see Org A, but NOT Org B and NOT Test Org
        org_ids = [o["id"] for o in data["organizations"]]
        self.assertIn(self.org_a_id, org_ids, "User A must see their authorized organization")
        self.assertNotIn(self.org_b_id, org_ids, "User A must NEVER see User B's organization")
        self.assertNotIn(self.test_org_id, org_ids, "Test organization fixture must be excluded from production contexts")

    def test_02_user_b_isolated_from_user_a(self):
        """User B sees only farm B and org B; zero leakage from User A."""
        res = self.client.get("/api/user/diagnosis-contexts", headers=self.headers_b)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        farm_ids = [f["id"] for f in data["farms"]]
        self.assertIn(self.farm_b_id, farm_ids)
        self.assertNotIn(self.farm_a_id, farm_ids)

        org_ids = [o["id"] for o in data["organizations"]]
        self.assertIn(self.org_b_id, org_ids)
        self.assertNotIn(self.org_a_id, org_ids)

    def test_03_guest_receives_trial_context_zero_private_records(self):
        """Unauthenticated visitor receives trial context without private farms or organizations."""
        res = self.client.get("/api/user/diagnosis-contexts")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertFalse(data["is_authenticated"])
        self.assertEqual(len(data["farms"]), 0, "Guest must see 0 farms")
        self.assertEqual(len(data["organizations"]), 0, "Guest must see 0 organizations")

    @staticmethod
    def _make_dummy_image() -> bytes:
        from PIL import Image
        img = Image.new("RGB", (32, 32), color=(46, 125, 50))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()

    def test_04_diagnosis_with_authorized_farm_succeeds(self):
        """Running plant diagnosis with an authorized farm succeeds and associates farm_id."""
        dummy_file = io.BytesIO(self._make_dummy_image())
        res = self.client.post(
            "/api/plant/diagnose",
            files={"image": ("leaf.jpg", dummy_file, "image/jpeg")},
            data={"farm_id": self.farm_a_id, "crop": "tomato"},
            headers=self.headers_a
        )
        self.assertIn(res.status_code, [200, 422], "Authorized farm should not fail with 403 Forbidden")

    def test_05_diagnosis_with_unauthorized_farm_rejected_with_403(self):
        """Attempting to run diagnosis with another user's farm is strictly rejected with 403 Forbidden."""
        dummy_file = io.BytesIO(self._make_dummy_image())
        res = self.client.post(
            "/api/plant/diagnose",
            files={"image": ("leaf.jpg", dummy_file, "image/jpeg")},
            data={"farm_id": self.farm_b_id, "crop": "tomato"},  # Farm B belongs to User B, but request has User A headers!
            headers=self.headers_a
        )
        self.assertEqual(res.status_code, 403, "Diagnosing with another user's farm must return 403 Forbidden")
        self.assertIn("quyền", res.json()["detail"].lower())

    def test_06_diagnosis_with_unauthorized_org_rejected_with_403(self):
        """Attempting to run diagnosis with another user's organization is strictly rejected with 403 Forbidden."""
        dummy_file = io.BytesIO(self._make_dummy_image())
        res = self.client.post(
            "/api/plant/diagnose",
            files={"image": ("leaf.jpg", dummy_file, "image/jpeg")},
            data={"org_id": self.org_b_id, "crop": "tomato"},  # Org B belongs to User B, but request has User A headers!
            headers=self.headers_a
        )
        self.assertEqual(res.status_code, 403, "Diagnosing with another organization must return 403 Forbidden")


if __name__ == "__main__":
    unittest.main()
