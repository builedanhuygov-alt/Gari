"""
GARI AI LAB — Frontend Consolidation, Host Console & RBAC Test Suite
File: tests/test_consolidation_and_rbac.py

Tests:
1. Frontend Consolidation: Only frontend2 is served, root aliases (/, /predict, /dashboard, etc.) work,
   legacy /frontend/ and /static/frontend/ are redirected (302), and obsolete files are archived.
2. Personal vs Organization Permissions: Personal user without organization cannot see org menu or access org APIs (HTTP 403).
3. Organization RBAC: Role hierarchy (owner, admin, member, viewer), sole-owner protection, no privilege escalation.
4. Cross-Tenant Isolation: Member of Org A cannot access or mutate Org B data (HTTP 403).
5. Dedicated Host Console Security: Regular users receive HTTP 403 on all /api/host/* endpoints, Host Admins have full access.
6. Server-Side AI Inference: Plant disease diagnosis pipeline continues working with 100% real inference.
"""

import io
import os
import sys
import unittest
import uuid
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

os.environ["APP_ENV"] = "development"
os.environ["PAYMENT_PUBLIC_CHECKOUT_ENABLED"] = "1"
os.environ["SESSION_SECRET"] = "gari_secure_test_session_secret_32chars_min"
os.environ["JWT_SECRET"] = "gari_secure_test_jwt_secret_32chars_min"

import api_server
import gari_auth
import gari_b2b
import gari_database
from starlette.testclient import TestClient
from PIL import Image


class TestFrontendConsolidationAndRBAC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gari_database.init_database()
        cls.client = TestClient(api_server.app)

        cls.suffix = uuid.uuid4().hex[:8]
        cls.password = "StrongPassword123!"
        pwd_hash = gari_auth.hash_password(cls.password)

        # 1. Create a pure personal farmer (NO organization membership)
        cls.farmer_email = f"farmer_{cls.suffix}@test.vn"
        with gari_database.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO users (full_name, name, email, password_hash, account_type, is_host_admin, is_active)
                VALUES ('Nông Dân Ba Tri', 'Nông Dân Ba Tri', ?, ?, 'farmer', 0, 1)
                """,
                (cls.farmer_email, pwd_hash)
            )
            cls.farmer_id = cur.lastrowid

            # 2. Create Owner of Org A
            cls.owner_a_email = f"owner_a_{cls.suffix}@htx-a.vn"
            cur.execute(
                """
                INSERT INTO users (full_name, name, email, password_hash, account_type, is_host_admin, is_active)
                VALUES ('Chủ Nhiệm HTX A', 'Chủ Nhiệm HTX A', ?, ?, 'cooperative', 0, 1)
                """,
                (cls.owner_a_email, pwd_hash)
            )
            cls.owner_a_id = cur.lastrowid

            # 3. Create Admin of Org A
            cls.admin_a_email = f"admin_a_{cls.suffix}@htx-a.vn"
            cur.execute(
                """
                INSERT INTO users (full_name, name, email, password_hash, account_type, is_host_admin, is_active)
                VALUES ('Phó Quản Trị HTX A', 'Phó Quản Trị HTX A', ?, ?, 'cooperative', 0, 1)
                """,
                (cls.admin_a_email, pwd_hash)
            )
            cls.admin_a_id = cur.lastrowid

            # 4. Create Member of Org A
            cls.member_a_email = f"member_a_{cls.suffix}@htx-a.vn"
            cur.execute(
                """
                INSERT INTO users (full_name, name, email, password_hash, account_type, is_host_admin, is_active)
                VALUES ('Xã Viên HTX A', 'Xã Viên HTX A', ?, ?, 'cooperative', 0, 1)
                """,
                (cls.member_a_email, pwd_hash)
            )
            cls.member_a_id = cur.lastrowid

            # 5. Create Owner of Org B (Tenant B)
            cls.owner_b_email = f"owner_b_{cls.suffix}@dn-b.vn"
            cur.execute(
                """
                INSERT INTO users (full_name, name, email, password_hash, account_type, is_host_admin, is_active)
                VALUES ('Giám Đốc Doanh Nghiệp B', 'Giám Đốc Doanh Nghiệp B', ?, ?, 'enterprise', 0, 1)
                """,
                (cls.owner_b_email, pwd_hash)
            )
            cls.owner_b_id = cur.lastrowid

            # 6. Create Host Admin User
            cls.host_admin_email = f"host_admin_{cls.suffix}@gari.vn"
            cur.execute(
                """
                INSERT INTO users (full_name, name, email, password_hash, account_type, is_host_admin, is_active)
                VALUES ('Kỹ Sư Trưởng Host', 'Kỹ Sư Trưởng Host', ?, ?, 'expert', 1, 1)
                """,
                (cls.host_admin_email, pwd_hash)
            )
            cls.host_admin_id = cur.lastrowid

            # Create Org A
            cur.execute(
                """
                INSERT INTO organizations (name, slug, organization_type, owner_id, status, plan_id)
                VALUES (?, ?, 'cooperative', ?, 'active', 'cooperative_pilot')
                """,
                (f"HTX Nông Nghiệp Xanh {cls.suffix}", f"htx-xanh-{cls.suffix}", cls.owner_a_id)
            )
            cls.org_a_id = cur.lastrowid

            # Memberships in Org A
            cur.execute(
                "INSERT INTO organization_members (organization_id, user_id, role) VALUES (?, ?, 'owner')",
                (cls.org_a_id, cls.owner_a_id)
            )
            cur.execute(
                "INSERT INTO organization_members (organization_id, user_id, role) VALUES (?, ?, 'admin')",
                (cls.org_a_id, cls.admin_a_id)
            )
            cur.execute(
                "INSERT INTO organization_members (organization_id, user_id, role) VALUES (?, ?, 'member')",
                (cls.org_a_id, cls.member_a_id)
            )

            # Create Org B
            cur.execute(
                """
                INSERT INTO organizations (name, slug, organization_type, owner_id, status, plan_id)
                VALUES (?, ?, 'enterprise', ?, 'active', 'enterprise_annual')
                """,
                (f"Công Ty CP Nông Nghiệp Cao B {cls.suffix}", f"dn-cao-b-{cls.suffix}", cls.owner_b_id)
            )
            cls.org_b_id = cur.lastrowid
            cur.execute(
                "INSERT INTO organization_members (organization_id, user_id, role) VALUES (?, ?, 'owner')",
                (cls.org_b_id, cls.owner_b_id)
            )

        # Create session tokens (create_session returns token string)
        cls.farmer_token = gari_auth.create_session(cls.farmer_id)
        cls.owner_a_token = gari_auth.create_session(cls.owner_a_id)
        cls.admin_a_token = gari_auth.create_session(cls.admin_a_id)
        cls.member_a_token = gari_auth.create_session(cls.member_a_id)
        cls.owner_b_token = gari_auth.create_session(cls.owner_b_id)
        cls.host_admin_token = gari_auth.create_session(cls.host_admin_id)

    # =========================================================================
    # PART 1: FRONTEND CONSOLIDATION & ROUTE ALIASES
    # =========================================================================

    def test_01_root_aliases_serve_frontend2(self):
        """Root route / and clean aliases serve corresponding frontend2 pages."""
        # / -> frontend2/index.html
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("content-type", ""))
        self.assertIn("Gari", res.text)

        # /predict -> frontend2/predict.html
        res = self.client.get("/predict")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Gari AI Lab", res.text)

        # /dashboard -> frontend2/index.html
        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 200)

        # /login -> frontend2/login.html
        res = self.client.get("/login")
        self.assertEqual(res.status_code, 200)

        # /host -> frontend2/host.html
        res = self.client.get("/host")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Host Server Admin Console", res.text)

        # /host-login -> frontend2/host-login.html
        res = self.client.get("/host-login")
        self.assertEqual(res.status_code, 200)

    def test_02_static_files_mapped_to_frontend2(self):
        """Static assets /style.css, /app.js map directly to frontend2 assets."""
        res_css = self.client.get("/style.css")
        self.assertEqual(res_css.status_code, 200)
        self.assertIn("text/css", res_css.headers.get("content-type", ""))

        res_js = self.client.get("/app.js")
        self.assertEqual(res_js.status_code, 200)
        self.assertIn("javascript", res_js.headers.get("content-type", ""))

    def test_03_legacy_frontend_redirects(self):
        """Legacy /frontend/... and /static/frontend/... return 302 redirects to /frontend2/..."""
        res = self.client.get("/frontend/index.html", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers.get("location"), "/frontend2/index.html")

        res_pred = self.client.get("/frontend/predict.html", follow_redirects=False)
        self.assertEqual(res_pred.status_code, 302)
        self.assertEqual(res_pred.headers.get("location"), "/frontend2/predict.html")

        res_static = self.client.get("/static/frontend/app.js", follow_redirects=False)
        self.assertEqual(res_static.status_code, 302)
        self.assertEqual(res_static.headers.get("location"), "/static/frontend2/app.js")

    def test_04_obsolete_frontend_files_archived(self):
        """Obsolete root index.html and frontend/ directory are safely archived."""
        self.assertFalse((ROOT_DIR / "index.html").exists(), "Root index.html should be removed")
        self.assertFalse((ROOT_DIR / "frontend").exists(), "Legacy frontend/ directory should be removed/archived")
        self.assertTrue((ROOT_DIR / "_archive" / "legacy-react-frontend").exists(), "React frontend must be preserved in _archive")
        self.assertTrue((ROOT_DIR / "_archive" / "root-legacy-html").exists(), "Root HTML must be preserved in _archive")

    # =========================================================================
    # PART 2: PERSONAL USER VS ORGANIZATION ACCESS CONTROL
    # =========================================================================

    def test_05_personal_user_has_no_organizations(self):
        """Personal farmer /api/auth/me returns has_organizations=False, empty list, and is_host_admin=False."""
        headers = {"Authorization": f"Bearer {self.farmer_token}"}
        res = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"))
        user = data.get("user")
        self.assertEqual(user["account_type"], "farmer")
        self.assertFalse(user["has_organizations"])
        self.assertEqual(user["organizations"], [])
        self.assertFalse(user["is_host_admin"])

    def test_06_personal_user_forbidden_from_org_endpoints(self):
        """Personal farmer calling organization endpoints receives HTTP 403 Forbidden."""
        headers = {"Authorization": f"Bearer {self.farmer_token}"}
        
        # Access org details
        res_get = self.client.get(f"/api/organizations/{self.org_a_id}", headers=headers)
        self.assertEqual(res_get.status_code, 403)

        # Access org members
        res_mem = self.client.get(f"/api/organizations/{self.org_a_id}/members", headers=headers)
        self.assertEqual(res_mem.status_code, 403)

        # Try to invite into org
        res_inv = self.client.post(
            f"/api/organizations/{self.org_a_id}/invitations",
            headers=headers,
            json={"email": "attacker@test.vn", "role": "admin"}
        )
        self.assertEqual(res_inv.status_code, 403)

    # =========================================================================
    # PART 3: ORGANIZATION RBAC & PRIVILEGE ESCALATION GUARDS
    # =========================================================================

    def test_07_org_member_cannot_invite_or_alter_roles(self):
        """Organization member cannot invite others or modify roles (HTTP 403)."""
        headers = {"Authorization": f"Bearer {self.member_a_token}"}
        
        # Member attempts to invite
        res_inv = self.client.post(
            f"/api/organizations/{self.org_a_id}/invitations",
            headers=headers,
            json={"email": "friend@test.vn", "role": "member"}
        )
        self.assertEqual(res_inv.status_code, 403)

        # Member attempts to promote themselves to admin
        res_role = self.client.patch(
            f"/api/organizations/{self.org_a_id}/members/{self.member_a_id}",
            headers=headers,
            json={"role": "admin"}
        )
        self.assertEqual(res_role.status_code, 403)

    def test_08_org_admin_cannot_demote_or_delete_sole_owner(self):
        """Org admin cannot demote or remove the organization owner."""
        headers = {"Authorization": f"Bearer {self.admin_a_token}"}
        
        # Admin attempts to demote owner to member
        res_demote = self.client.patch(
            f"/api/organizations/{self.org_a_id}/members/{self.owner_a_id}",
            headers=headers,
            json={"role": "member"}
        )
        self.assertIn(res_demote.status_code, [400, 403])

        # Admin attempts to remove owner from org
        res_remove = self.client.delete(
            f"/api/organizations/{self.org_a_id}/members/{self.owner_a_id}",
            headers=headers
        )
        self.assertIn(res_remove.status_code, [400, 403])

    def test_09_org_owner_can_transfer_ownership(self):
        """Org owner can transfer ownership to another member atomically."""
        headers = {"Authorization": f"Bearer {self.owner_a_token}"}
        
        res = self.client.post(
            f"/api/organizations/{self.org_a_id}/transfer-owner",
            headers=headers,
            json={"target_user_id": self.admin_a_id, "reason": "Test ownership transfer"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("success"))

        # Verify new owner is now admin_a
        with gari_database.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT owner_id FROM organizations WHERE id = ?", (self.org_a_id,))
            owner_id = cur.fetchone()[0]
            self.assertEqual(owner_id, self.admin_a_id)

        # Transfer back so later tests maintain consistency
        headers_new_owner = {"Authorization": f"Bearer {self.admin_a_token}"}
        res_back = self.client.post(
            f"/api/organizations/{self.org_a_id}/transfer-owner",
            headers=headers_new_owner,
            json={"target_user_id": self.owner_a_id, "reason": "Test ownership transfer back"}
        )
        self.assertEqual(res_back.status_code, 200)

    # =========================================================================
    # PART 4: CROSS-TENANT ISOLATION
    # =========================================================================

    def test_10_cross_tenant_isolation(self):
        """User from Org B cannot read or alter Org A data (HTTP 403)."""
        headers = {"Authorization": f"Bearer {self.owner_b_token}"}

        # Tenant B tries to read Tenant A details
        res = self.client.get(f"/api/organizations/{self.org_a_id}", headers=headers)
        self.assertEqual(res.status_code, 403)

        # Tenant B tries to read Tenant A members
        res_mem = self.client.get(f"/api/organizations/{self.org_a_id}/members", headers=headers)
        self.assertEqual(res_mem.status_code, 403)

        # Tenant B tries to invite someone to Tenant A
        res_inv = self.client.post(
            f"/api/organizations/{self.org_a_id}/invitations",
            headers=headers,
            json={"email": "spy@tenantb.vn", "role": "admin"}
        )
        self.assertEqual(res_inv.status_code, 403)

    # =========================================================================
    # PART 5: DEDICATED HOST CONSOLE SECURITY
    # =========================================================================

    def test_11_regular_users_forbidden_from_host_endpoints(self):
        """Non-host users (farmer, co-op owner, enterprise owner) receive HTTP 403 on all /api/host/* routes."""
        test_tokens = [self.farmer_token, self.owner_a_token, self.owner_b_token]
        host_endpoints = [
            "/api/host/me",
            "/api/host/overview",
            "/api/host/users",
            "/api/host/organizations",
            "/api/host/models",
            "/api/host/payments",
            "/api/host/vouchers",
            "/api/host/audit-logs",
            "/api/host/moderation/cases",
        ]

        for token in test_tokens:
            h = {"Authorization": f"Bearer {token}"}
            for endpoint in host_endpoints:
                res = self.client.get(endpoint, headers=h)
                self.assertEqual(
                    res.status_code, 403,
                    f"Expected 403 for non-host user on {endpoint}, got {res.status_code}"
                )

    def test_12_host_admin_has_full_management_access(self):
        """Host admin (is_host_admin == 1) has authorized access to all host endpoints."""
        headers = {"Authorization": f"Bearer {self.host_admin_token}"}

        # 1. /api/host/me
        res_me = self.client.get("/api/host/me", headers=headers)
        self.assertEqual(res_me.status_code, 200)
        self.assertTrue(res_me.json()["user"]["is_host_admin"])

        # 2. /api/host/overview (real telemetry, no demo mock)
        res_ov = self.client.get("/api/host/overview", headers=headers)
        self.assertEqual(res_ov.status_code, 200)
        ov = res_ov.json()
        self.assertIn("telemetry", ov)
        self.assertIn("cpu_percent", ov["telemetry"])
        self.assertIn("ram", ov["telemetry"])

        # 3. /api/host/organizations
        res_orgs = self.client.get("/api/host/organizations", headers=headers)
        self.assertEqual(res_orgs.status_code, 200)
        orgs = res_orgs.json()
        self.assertTrue(orgs.get("success"))
        self.assertGreaterEqual(len(orgs.get("organizations", [])), 2)

        # 4. /api/host/organizations/{org_id}/members
        res_mems = self.client.get(f"/api/host/organizations/{self.org_a_id}/members", headers=headers)
        self.assertEqual(res_mems.status_code, 200)
        self.assertTrue(res_mems.json().get("success"))
        self.assertGreaterEqual(len(res_mems.json().get("members", [])), 3)

        # 5. /api/host/models (server-side models)
        res_mod = self.client.get("/api/host/models", headers=headers)
        self.assertEqual(res_mod.status_code, 200)
        models_data = res_mod.json()
        self.assertTrue(models_data.get("success"))
        self.assertGreaterEqual(models_data.get("total_models", 0), 1)

        # 6. /api/host/payments
        res_pay = self.client.get("/api/host/payments", headers=headers)
        self.assertEqual(res_pay.status_code, 200)
        self.assertTrue(res_pay.json().get("success"))

        # 7. Host overrides org status with audit trail
        res_st = self.client.patch(
            f"/api/host/organizations/{self.org_a_id}/status",
            headers=headers,
            json={"status": "active", "reason": "Host verified co-op accreditation"}
        )
        self.assertEqual(res_st.status_code, 200)
        self.assertTrue(res_st.json().get("success"))

        # Verify audit log was recorded
        res_audit = self.client.get("/api/host/audit-logs", headers=headers)
        self.assertEqual(res_audit.status_code, 200)
        audits = res_audit.json().get("logs", [])
        self.assertTrue(any(a.get("action_type") == "organization.status_change" for a in audits))

    # =========================================================================
    # PART 6: SERVER-SIDE AI INFERENCE & LEAF VALIDATION PIPELINE
    # =========================================================================

    def test_13_ai_disease_diagnosis_on_server_succeeds(self):
        """Image sent to POST /api/plant/diagnose executes server-side inference and returns diagnosis."""
        # Create a synthetic green leaf test image
        img = Image.new("RGB", (256, 256), color=(34, 139, 34))
        # Draw some variation to pass leaf texture
        pixels = img.load()
        for x in range(50, 200):
            for y in range(50, 200):
                pixels[x, y] = (46, 204, 113)

        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)

        headers = {"Authorization": f"Bearer {self.farmer_token}"}
        res = self.client.post(
            "/api/plant/diagnose",
            headers=headers,
            data={"crop_type": "Tomato", "language": "vi"},
            files={"file": ("leaf_test.jpg", img_bytes.getvalue(), "image/jpeg")}
        )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"), f"Diagnose response: {data}")
        self.assertEqual(data.get("execution_location"), "server")
        self.assertEqual(data.get("device"), "cpu")
        self.assertIn("predicted_disease", data)
        self.assertIn("status", data)
        self.assertIn("validation", data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
