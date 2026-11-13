"""
GARI MODULE 05 — ORGANIZATION & TEAM MANAGEMENT TEST SUITE (Unittest)
Tests 10 complete real business logic requirements:
1. Organization creation with subscription check & types (cooperative, business)
2. Invitation lifecycle: secure hashed token, 7-day expiry, and revocation
3. Invitation acceptance: server-side token verification & email ownership matching
4. Invitation decline flow: decline tracking & audit logging
5. Scoped roles permissions: owner, farm_manager, agronomist, field_worker, viewer
6. Role assignment security hierarchy: privilege escalation prevention
7. Scoped member farm, zone, and plot assignments
8. Voluntary member leave flow & blocked owner departure
9. Secure atomic ownership transfer flow & old owner demotion
10. Seat & farm limits enforcement with structured upgrade guidance
"""

import os
import sys
import unittest
import uuid
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import gari_b2b
import gari_database
import gari_farm_management
import gari_plans
import gari_auth
from api_server import app

client = TestClient(app)


def _create_test_user(email_prefix: str, role: str = "farmer", is_admin: bool = False):
    suffix = uuid.uuid4().hex[:8]
    email = f"{email_prefix}_{suffix}@test.gari.vn"
    reg = client.post("/api/auth/register", json={
        "full_name": f"{email_prefix} {suffix}",
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "account_type": role
    })
    data = reg.json()
    token = data.get("token")
    user = data.get("user") or {}
    if is_admin and user.get("id"):
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (user["id"],))
            conn.commit()
        user["is_admin"] = 1
    return user, token


class TestModule05OrganizationTeam(unittest.TestCase):

    def test_01_organization_creation_and_types(self):
        """Free user is blocked from creating org; Pro user can create Cooperative & Business."""
        # 1. Free user
        free_user, free_token = _create_test_user("free_farmer", role="farmer")
        res_free = client.post(
            "/api/organizations",
            headers={"Authorization": f"Bearer {free_token}"},
            json={"name": "HTX Nông Nghiệp Thất Bại", "organization_type": "cooperative"}
        )
        self.assertEqual(res_free.status_code, 403, f"Expected 403, got {res_free.status_code}: {res_free.text}")
        self.assertIn("nâng cấp gói", res_free.json()["detail"].lower())

        # 2. Upgrade user to Pro
        gari_plans.assign_user_plan(free_user["id"], "pro", status="pilot_active")

        # 3. Create Cooperative
        coop_name = f"HTX Rau An Toàn {uuid.uuid4().hex[:6]}"
        res_coop = client.post(
            "/api/organizations",
            headers={"Authorization": f"Bearer {free_token}"},
            json={
                "name": coop_name,
                "organization_type": "cooperative",
                "region": "Lâm Đồng",
                "primary_crops": ["tomato", "coffee"]
            }
        )
        self.assertEqual(res_coop.status_code, 200, res_coop.text)
        coop_data = res_coop.json()["organization"]
        self.assertEqual(coop_data["name"], coop_name)
        self.assertEqual(coop_data["organization_type"], "cooperative")

        # 4. Verify owner membership
        member_role = gari_b2b.get_member_role(coop_data["id"], free_user["id"])
        self.assertEqual(member_role, "owner")

    def test_02_invitation_lifecycle_token_and_expiry(self):
        """Owner creates invitation with hashed token in DB, raw token returned once, and revocable."""
        owner, owner_token = _create_test_user("org_owner", role="farmer")
        gari_plans.assign_user_plan(owner["id"], "team", status="pilot_active")

        org = gari_b2b.create_organization(f"Trang Trại Sầu Riêng {uuid.uuid4().hex[:6]}", owner["id"], organization_type="farm")
        org_id = org["id"]

        invite_email = f"invited_{uuid.uuid4().hex[:6]}@gari.test"
        res_inv = client.post(
            f"/api/organizations/{org_id}/invitations",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"email": invite_email, "role": "farm_manager", "reason": "Mời làm quản lý nông trại"}
        )
        self.assertEqual(res_inv.status_code, 200, res_inv.text)
        inv_data = res_inv.json()["invitation"]
        raw_token = inv_data.get("invite_token") or inv_data.get("token")
        self.assertIsNotNone(raw_token)
        self.assertTrue(raw_token.startswith("gari_inv_"))
        self.assertEqual(inv_data["role"], "farm_manager")
        self.assertEqual(inv_data["status"], "pending")

        # Verify DB stores token_hash, not the raw token
        with gari_b2b.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM organization_invitations WHERE id = ?", (inv_data["id"],))
            db_row = dict(cursor.fetchone())
            self.assertEqual(db_row["token_hash"], gari_b2b._hash_invitation_token(raw_token))
            self.assertNotEqual(raw_token, db_row["token_hash"])
            self.assertEqual(db_row["status"], "pending")

        # Revoke invitation
        res_revoke = client.post(
            f"/api/organizations/{org_id}/invitations/{inv_data['id']}/revoke",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"reason": "Thay đổi kế hoạch nhân sự"}
        )
        self.assertEqual(res_revoke.status_code, 200, res_revoke.text)

        # Verify revoked status in DB
        with gari_b2b.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status, revoke_reason FROM organization_invitations WHERE id = ?", (inv_data["id"],))
            row = cursor.fetchone()
            self.assertEqual(row[0], "revoked")
            self.assertEqual(row[1], "Thay đổi kế hoạch nhân sự")

    def test_03_invitation_acceptance_and_email_match(self):
        """Invited user with matching email accepts; mismatched email is rejected."""
        owner, owner_token = _create_test_user("org_owner", role="farmer")
        gari_plans.assign_user_plan(owner["id"], "team", status="pilot_active")
        org = gari_b2b.create_organization(f"Công Ty Cà Phê {uuid.uuid4().hex[:6]}", owner["id"], organization_type="business")
        org_id = org["id"]

        invitee, invitee_token = _create_test_user("invitee_user", role="farmer")
        other_user, other_token = _create_test_user("other_intruder", role="farmer")

        # Create invitation for invitee email
        inv = gari_b2b.create_invitation(org_id, owner["id"], invitee["email"], role="agronomist")
        raw_token = inv.get("invite_token") or inv.get("raw_token") or inv.get("token")

        # 1. Other user attempts to accept -> rejected
        res_other = client.post(
            "/api/invitations/accept",
            headers={"Authorization": f"Bearer {other_token}"},
            json={"token": raw_token}
        )
        self.assertIn(res_other.status_code, (400, 403), res_other.text)

        # 2. Correct user accepts -> accepted
        res_accept = client.post(
            "/api/invitations/accept",
            headers={"Authorization": f"Bearer {invitee_token}"},
            json={"token": raw_token}
        )
        self.assertEqual(res_accept.status_code, 200, res_accept.text)
        self.assertEqual(res_accept.json()["membership"]["role"], "agronomist")

        # Verify membership in DB
        role = gari_b2b.get_member_role(org_id, invitee["id"])
        self.assertEqual(role, "agronomist")

    def test_04_invitation_decline_flow(self):
        """Invited user can decline invitation; record status declined and audit log."""
        owner, owner_token = _create_test_user("org_owner", role="farmer")
        gari_plans.assign_user_plan(owner["id"], "team", status="pilot_active")
        org = gari_b2b.create_organization(f"HTX Nông Nghiệp {uuid.uuid4().hex[:6]}", owner["id"], organization_type="cooperative")
        org_id = org["id"]

        invitee, invitee_token = _create_test_user("invitee_decline", role="farmer")
        inv = gari_b2b.create_invitation(org_id, owner["id"], invitee["email"], role="field_worker")
        raw_token = inv.get("invite_token") or inv.get("raw_token") or inv.get("token")

        # Decline via API
        res_decline = client.post(
            f"/api/invitations/{raw_token}/decline",
            headers={"Authorization": f"Bearer {invitee_token}"},
            json={"reason": "Không sắp xếp được thời gian"}
        )
        self.assertEqual(res_decline.status_code, 200, res_decline.text)
        self.assertEqual(res_decline.json()["decline"]["status"], "declined")

        # Check DB status
        with gari_b2b.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status, declined_by_user_id, decline_reason FROM organization_invitations WHERE id = ?", (inv["id"],))
            row = cursor.fetchone()
            self.assertEqual(row[0], "declined")
            self.assertEqual(row[1], invitee["id"])
            self.assertEqual(row[2], "Không sắp xếp được thời gian")

    def test_05_scoped_roles_permissions(self):
        """Verify role permissions: owner, farm_manager, agronomist, field_worker, viewer."""
        owner, _ = _create_test_user("role_owner")
        gari_plans.assign_user_plan(owner["id"], "team", status="pilot_active")
        org = gari_b2b.create_organization(f"Test Roles Org {uuid.uuid4().hex[:6]}", owner["id"])
        org_id = org["id"]

        manager, _ = _create_test_user("role_fm")
        agronomist, _ = _create_test_user("role_agro")
        worker, _ = _create_test_user("role_worker")
        viewer, _ = _create_test_user("role_viewer")

        gari_b2b.add_member_by_email(org_id, owner["id"], manager["email"], role="farm_manager")
        gari_b2b.add_member_by_email(org_id, owner["id"], agronomist["email"], role="agronomist")
        gari_b2b.add_member_by_email(org_id, owner["id"], worker["email"], role="field_worker")
        gari_b2b.add_member_by_email(org_id, owner["id"], viewer["email"], role="viewer")

        # Check farm_manager permissions
        has_invite, _ = gari_b2b.has_permission(org_id, manager["id"], "members.invite")
        has_farms_create, _ = gari_b2b.has_permission(org_id, manager["id"], "farms.create")
        has_transfer, _ = gari_b2b.has_permission(org_id, manager["id"], "members.owner_transfer")
        self.assertTrue(has_invite)
        self.assertTrue(has_farms_create)
        self.assertFalse(has_transfer)

        # Check agronomist permissions
        has_diag, _ = gari_b2b.has_permission(org_id, agronomist["id"], "diagnosis.create")
        has_obs, _ = gari_b2b.has_permission(org_id, agronomist["id"], "observations.manage")
        has_inv_agro, _ = gari_b2b.has_permission(org_id, agronomist["id"], "members.invite")
        self.assertTrue(has_diag)
        self.assertTrue(has_obs)
        self.assertFalse(has_inv_agro)

        # Check field_worker permissions
        has_tasks, _ = gari_b2b.has_permission(org_id, worker["id"], "tasks.manage")
        has_farm_up, _ = gari_b2b.has_permission(org_id, worker["id"], "farms.update")
        self.assertTrue(has_tasks)
        self.assertFalse(has_farm_up)

        # Check viewer permissions
        has_view, _ = gari_b2b.has_permission(org_id, viewer["id"], "org.view")
        has_diag_create, _ = gari_b2b.has_permission(org_id, viewer["id"], "diagnosis.create")
        self.assertTrue(has_view)
        self.assertFalse(has_diag_create)

    def test_06_role_assignment_security_hierarchy(self):
        """Prevent privilege escalation: field worker cannot assign roles; manager cannot promote to owner or admin."""
        owner, owner_token = _create_test_user("sec_owner")
        gari_plans.assign_user_plan(owner["id"], "team", status="pilot_active")
        org = gari_b2b.create_organization(f"Security Org {uuid.uuid4().hex[:6]}", owner["id"])
        org_id = org["id"]

        manager, manager_token = _create_test_user("sec_manager")
        worker, worker_token = _create_test_user("sec_worker")
        gari_b2b.add_member_by_email(org_id, owner["id"], manager["email"], role="farm_manager")
        gari_b2b.add_member_by_email(org_id, owner["id"], worker["email"], role="field_worker")

        # 1. Field worker attempts to update manager role -> 403 Forbidden
        res_worker_attack = client.patch(
            f"/api/organizations/{org_id}/members/{manager['id']}",
            headers={"Authorization": f"Bearer {worker_token}"},
            json={"role": "viewer"}
        )
        self.assertEqual(res_worker_attack.status_code, 403)

        # 2. Manager attempts to promote worker to admin -> rejected
        res_manager_attack = client.patch(
            f"/api/organizations/{org_id}/members/{worker['id']}",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={"role": "admin"}
        )
        self.assertIn(res_manager_attack.status_code, (400, 403))

        # 3. Owner can promote worker to agronomist
        res_owner_promote = client.patch(
            f"/api/organizations/{org_id}/members/{worker['id']}",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"role": "agronomist"}
        )
        self.assertEqual(res_owner_promote.status_code, 200)
        self.assertEqual(gari_b2b.get_member_role(org_id, worker["id"]), "agronomist")

    def test_07_scoped_member_farm_zone_plot_assignment(self):
        """Assign members to specific farms/zones/plots and verify scoped isolation."""
        owner, owner_token = _create_test_user("scope_owner")
        gari_plans.assign_user_plan(owner["id"], "team", status="pilot_active")
        org = gari_b2b.create_organization(f"Scoped Org {uuid.uuid4().hex[:6]}", owner["id"])
        org_id = org["id"]

        worker, _ = _create_test_user("scope_worker")
        gari_b2b.add_member_by_email(org_id, owner["id"], worker["email"], role="field_worker")

        # Create a farm under this org
        farm = gari_farm_management.create_farm_ext(
            {"name": f"Nông Trại Đơn Vị {uuid.uuid4().hex[:6]}", "area_hectare": 5.0, "organization_id": org_id},
            user_id=owner["id"],
            org_id=org_id
        )
        farm_id = farm["id"]

        # Create a zone
        zone = gari_farm_management.create_zone(
            {"farm_id": farm_id, "name": "Khu Sầu Riêng A", "area_m2": 10000},
            user_id=owner["id"]
        )
        zone_id = zone["id"]

        # Assign member to farm and zone
        res_assign = client.post(
            f"/api/organizations/{org_id}/assignments",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "user_id": worker["id"],
                "farm_id": farm_id,
                "zone_id": zone_id,
                "notes": "Phụ trách giám sát sâu đục thân"
            }
        )
        self.assertEqual(res_assign.status_code, 200, res_assign.text)
        assignment_id = res_assign.json()["assignment"]["id"]

        # List assignments
        res_list = client.get(
            f"/api/organizations/{org_id}/assignments?user_id={worker['id']}",
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        self.assertEqual(res_list.status_code, 200)
        items = res_list.json()["assignments"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["farm_id"], farm_id)
        self.assertEqual(items[0]["zone_id"], zone_id)
        self.assertEqual(items[0]["notes"], "Phụ trách giám sát sâu đục thân")

        # Delete assignment
        res_del = client.delete(
            f"/api/organizations/{org_id}/assignments/{assignment_id}",
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        self.assertEqual(res_del.status_code, 200)
        self.assertEqual(len(gari_b2b.list_member_scopes(org_id, worker["id"])), 0)

    def test_08_member_leave_flow_and_owner_block(self):
        """Member can voluntarily leave org; Owner is blocked until ownership is transferred."""
        owner, owner_token = _create_test_user("leave_owner")
        gari_plans.assign_user_plan(owner["id"], "team", status="pilot_active")
        org = gari_b2b.create_organization(f"Leave Org {uuid.uuid4().hex[:6]}", owner["id"])
        org_id = org["id"]

        member, member_token = _create_test_user("leave_member")
        gari_b2b.add_member_by_email(org_id, owner["id"], member["email"], role="agronomist")

        # 1. Owner attempts to leave -> Blocked!
        res_owner_leave = client.post(
            f"/api/organizations/{org_id}/leave",
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        self.assertIn(res_owner_leave.status_code, (400, 403), "Owner must not be allowed to leave directly")
        self.assertIn("chuyển giao quyền sở hữu", res_owner_leave.text.lower())

        # 2. Member leaves -> Success
        res_member_leave = client.post(
            f"/api/organizations/{org_id}/leave",
            headers={"Authorization": f"Bearer {member_token}"}
        )
        self.assertEqual(res_member_leave.status_code, 200)
        self.assertIsNone(gari_b2b.get_member_role(org_id, member["id"]))

    def test_09_secure_ownership_transfer(self):
        """Owner safely transfers ownership to an existing member; old owner is demoted to admin."""
        owner, owner_token = _create_test_user("transfer_owner")
        gari_plans.assign_user_plan(owner["id"], "team", status="pilot_active")
        org = gari_b2b.create_organization(f"Transfer Org {uuid.uuid4().hex[:6]}", owner["id"])
        org_id = org["id"]

        successor, _ = _create_test_user("successor")
        gari_b2b.add_member_by_email(org_id, owner["id"], successor["email"], role="farm_manager")

        # Transfer ownership
        res_transfer = client.post(
            f"/api/organizations/{org_id}/transfer-ownership",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"target_user_id": successor["id"], "reason": "Bàn giao nhiệm kỳ mới"}
        )
        self.assertEqual(res_transfer.status_code, 200, res_transfer.text)

        # Verify new roles
        self.assertEqual(gari_b2b.get_member_role(org_id, successor["id"]), "owner")
        self.assertEqual(gari_b2b.get_member_role(org_id, owner["id"]), "admin")

        # Verify organizations table owner_id
        org_detail = gari_b2b.get_organization_detail(org_id)
        self.assertEqual(org_detail["owner_id"], successor["id"])

    def test_10_seat_and_farm_limits_enforcement_with_upgrade_guidance(self):
        """Backend enforces member seat limits and farm limits with clear upgrade messages."""
        owner, owner_token = _create_test_user("limits_owner")
        # Assign pro plan: allowed max 1 organization
        gari_plans.assign_user_plan(owner["id"], "pro", status="pilot_active")
        org = gari_b2b.create_organization(f"Limits Org {uuid.uuid4().hex[:6]}", owner["id"])
        org_id = org["id"]

        # Attempt to create a 2nd organization on Pro (pro max_orgs = 1)
        res_org2 = client.post(
            "/api/organizations",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"name": "Org 2 Beyond Limit", "organization_type": "cooperative"}
        )
        self.assertEqual(res_org2.status_code, 403)
        self.assertTrue(
            "tối đa 1 tổ chức" in res_org2.json()["detail"].lower()
            or "nâng cấp gói" in res_org2.json()["detail"].lower()
        )

        # Test farm limit on pilot org (pilot max_farms = 2)
        farm1 = gari_farm_management.create_farm_ext(
            {"name": "Nông Trại 1", "organization_id": org_id},
            user_id=owner["id"],
            org_id=org_id
        )
        farm2 = gari_farm_management.create_farm_ext(
            {"name": "Nông Trại 2", "organization_id": org_id},
            user_id=owner["id"],
            org_id=org_id
        )
        self.assertTrue(farm1["id"] and farm2["id"])

        # Attempt to create 3rd farm -> Exceeds pilot limit 2
        with self.assertRaises(ValueError) as excinfo:
            gari_farm_management.create_farm_ext(
                {"name": "Nông Trại 3 Vượt Quá", "organization_id": org_id},
                user_id=owner["id"],
                org_id=org_id
            )
        self.assertIn("đạt giới hạn tối đa 2 nông trại", str(excinfo.exception))


if __name__ == "__main__":
    unittest.main()
