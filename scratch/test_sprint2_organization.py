"""
GARI AI LAB — SPRINT 2/6 ACCEPTANCE TEST SUITE (test_sprint2_organization.py)

Verifies the B2B Customer & Organization Engine end-to-end against an isolated
temporary SQLite database (the real disease_detector.db is never touched):

1. Lifecycle pending -> active -> suspended -> archived -> active (logical archive,
   no physical deletion, audit trail with actor/action/reason).
2. New organizations never receive a paid plan (customer plan_id is ignored).
3. Explicit RBAC: owner/admin/manager/member/viewer capability enforcement.
4. Invitations: hashed token, expiry, reuse, revocation, invalid role, manual
   delivery, generic errors, rate limiting.
5. Organization profile validation and privacy (no CCCD / financial / exact GPS).
6. Resumable B2B onboarding; pilot interest is not a signed contract.
7. Tenant isolation verified at HTTP *and* database level (no mutation on failure).
8. Suspended organization blocks usage endpoints and API keys.

Run:
    .venv\\Scripts\\python.exe scratch\\test_sprint2_organization.py
"""

import io
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# -----------------------------------------------------------------------------
# ISOLATED DATABASE — must happen BEFORE importing api_server
# -----------------------------------------------------------------------------
import gari_database
import gari_plans
import gari_b2b
import gari_quota
import gari_privacy

TMP_DIR = Path(tempfile.mkdtemp(prefix="gari_sprint2_test_"))
TEST_DB = TMP_DIR / "sprint2_test.db"
for _mod in (gari_database, gari_plans, gari_b2b, gari_quota, gari_privacy):
    _mod.DB_PATH = TEST_DB

gari_database.init_database()
gari_plans.init_plans_database()
gari_b2b.init_b2b_database()
gari_quota.init_quota_database()
gari_privacy.init_privacy_tables()

import api_server  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(api_server.app)

RESULTS = []
FAILURES = []


def check(name, condition, detail=""):
    ok = bool(condition)
    RESULTS.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILURES.append((name, detail))


def db_one(sql, params=()):
    conn = sqlite3.connect(str(TEST_DB), timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def db_all(sql, params=()):
    conn = sqlite3.connect(str(TEST_DB), timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def db_exec(sql, params=()):
    conn = sqlite3.connect(str(TEST_DB), timeout=10.0)
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def register(email, full_name="Sprint 2 User"):
    resp = client.post("/api/auth/register", json={
        "full_name": full_name,
        "email": email,
        "password": "Sprint2Pass123!",
        "confirm_password": "Sprint2Pass123!",
        "account_type": "Nông hộ",
        "terms_agreed": True,
    })
    if resp.status_code != 200:
        raise RuntimeError(f"Registration failed for {email}: {resp.status_code} {resp.text}")
    body = resp.json()
    return body["token"], body["user"]["id"]


def hdr(token):
    return {"Authorization": f"Bearer {token}"}


def create_org(token, name, **extra):
    payload = {"name": name, **extra}
    return client.post("/api/organizations", json=payload, headers=hdr(token))


def create_active_org(token, name):
    resp = create_org(token, name)
    if resp.status_code != 200:
        raise RuntimeError(f"Create org failed: {resp.status_code} {resp.text}")
    org_id = resp.json()["organization"]["id"]
    steps = [
        {"step": 2, "organization_type": "cooperative", "region": "Đồng bằng sông Hồng"},
        {"step": 3, "role_confirmed": True},
        {"step": 4, "needs": ["diagnosis", "member_management"], "commercial_intent": "pilot_interest"},
        {"step": 5, "complete": True, "role_confirmed": True, "needs": ["diagnosis", "member_management"]},
    ]
    for step in steps:
        r = client.patch(f"/api/organizations/{org_id}/onboarding", json=step, headers=hdr(token))
        if r.status_code != 200:
            raise RuntimeError(f"Onboarding step failed: {r.status_code} {r.text}")
    return org_id


def invite_and_accept(org_id, owner_token, email, role, password="Sprint2Pass123!"):
    """Create an invitation, register the recipient, and accept it."""
    inv = client.post(
        f"/api/organizations/{org_id}/invitations",
        json={"email": email, "role": role, "reason": "Sprint 2 acceptance test"},
        headers=hdr(owner_token),
    )
    if inv.status_code != 200:
        raise RuntimeError(f"Invite failed: {inv.status_code} {inv.text}")
    token_value = inv.json()["invitation"]["invite_token"]
    user_token, user_id = register(email, full_name=f"User {role}")
    acc = client.post("/api/invitations/accept", json={"token": token_value}, headers=hdr(user_token))
    if acc.status_code != 200:
        raise RuntimeError(f"Accept failed: {acc.status_code} {acc.text}")
    return user_token, user_id, inv.json()["invitation"]


def jpeg_bytes(color=(34, 139, 34), size=(224, 224)):
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# -----------------------------------------------------------------------------
# 1. LIFECYCLE + NO AUTO PAID PLAN + AUDIT
# -----------------------------------------------------------------------------
def test_lifecycle_and_no_paid_plan(owner_token):
    print("\n--- 1. Organization lifecycle, unpaid pilot plan & audit ---")
    resp = create_org(owner_token, "HTX Sprint 2 Lifecycle", plan_id="enterprise")
    check("Create organization returns 200", resp.status_code == 200, resp.text[:160])
    org = resp.json()["organization"]
    org_id = org["id"]
    check("Customer-supplied paid plan is ignored", org["plan_id"] == "pilot", f"plan={org['plan_id']}")
    check("New organization starts pending", org["status"] == "pending", f"status={org['status']}")

    row = db_one("SELECT plan_id, status FROM organizations WHERE id = ?", (org_id,))
    check("DB confirms pilot/pending", row["plan_id"] == "pilot" and row["status"] == "pending", dict(row))
    quota = db_one("SELECT quota_limit FROM organization_quotas WHERE organization_id = ?", (org_id,))
    check("Pilot quota initialized to 50", quota["quota_limit"] == 50, f"limit={quota['quota_limit']}")
    onboarding = db_one("SELECT status, current_step FROM organization_onboarding WHERE organization_id = ?", (org_id,))
    check("Onboarding state created", onboarding is not None and onboarding["status"] == "in_progress", dict(onboarding) if onboarding else None)

    detail = client.get(f"/api/organizations/{org_id}", headers=hdr(owner_token)).json()["organization"]
    check("Pending org is not operational", detail["is_operational"] is False)

    # Status change requires a reason
    bad = client.post(f"/api/organizations/{org_id}/status", json={"status": "active", "reason": ""}, headers=hdr(owner_token))
    check("Status change without reason rejected", bad.status_code == 400, f"HTTP {bad.status_code}")

    # Complete onboarding -> active, still pilot
    for step in [
        {"step": 2, "organization_type": "cooperative", "region": "Tây Nguyên", "primary_crops": ["Cà phê", "Tiêu"]},
        {"step": 3, "role_confirmed": True},
        {"step": 4, "needs": ["diagnosis"], "commercial_intent": "pilot_interest"},
        {"step": 5, "complete": True, "role_confirmed": True, "needs": ["diagnosis"]},
    ]:
        r = client.patch(f"/api/organizations/{org_id}/onboarding", json=step, headers=hdr(owner_token))
        check(f"Onboarding step {step['step']} accepted", r.status_code == 200, r.text[:120])

    org_after = db_one("SELECT plan_id, status FROM organizations WHERE id = ?", (org_id,))
    check("Onboarding activates organization", org_after["status"] == "active", dict(org_after))
    check("Onboarding never upgrades plan", org_after["plan_id"] == "pilot", f"plan={org_after['plan_id']}")

    # Suspend
    susp = client.post(f"/api/organizations/{org_id}/status", json={"status": "suspended", "reason": "Tạm ngưng để kiểm tra hợp đồng pilot"}, headers=hdr(owner_token))
    check("Owner can suspend organization", susp.status_code == 200, susp.text[:160])
    check("DB status suspended", db_one("SELECT status FROM organizations WHERE id = ?", (org_id,))["status"] == "suspended")

    # Suspended org usage blocked
    files = {"image": ("leaf.jpg", jpeg_bytes(), "image/jpeg")}
    blocked = client.post(f"/api/plant/diagnose", data={"org_id": str(org_id)}, files=files, headers=hdr(owner_token))
    check("Suspended org blocked from usage endpoint", blocked.status_code == 403, f"HTTP {blocked.status_code} {blocked.text[:120]}")

    # Archive (logical only)
    members_before = db_one("SELECT COUNT(*) c FROM organization_members WHERE organization_id = ?", (org_id,))["c"]
    usage_before = db_one("SELECT COUNT(*) c FROM usage_metering WHERE organization_id = ?", (org_id,))["c"]
    arch = client.post(f"/api/organizations/{org_id}/archive", json={"reason": "Lưu trữ an toàn theo yêu cầu khách hàng"}, headers=hdr(owner_token))
    check("Owner can archive organization", arch.status_code == 200, arch.text[:160])
    archived_row = db_one("SELECT status, archived_at, plan_id FROM organizations WHERE id = ?", (org_id,))
    check("Archive is logical (row retained)", archived_row is not None and archived_row["status"] == "archived", dict(archived_row) if archived_row else None)
    check("Archive sets archived_at", archived_row["archived_at"] is not None)
    check("Archive keeps plan metadata", archived_row["plan_id"] == "pilot")
    members_after = db_one("SELECT COUNT(*) c FROM organization_members WHERE organization_id = ?", (org_id,))["c"]
    usage_after = db_one("SELECT COUNT(*) c FROM usage_metering WHERE organization_id = ?", (org_id,))["c"]
    check("Archive does not delete members", members_before == members_after, f"{members_before} -> {members_after}")
    check("Archive does not delete usage history", usage_before == usage_after, f"{usage_before} -> {usage_after}")

    audit = db_all("SELECT action, reason FROM organization_audit_log WHERE organization_id = ? ORDER BY id", (org_id,))
    actions = [a["action"] for a in audit]
    check("Audit records creation", "organization.created" in actions)
    check("Audit records status changes", actions.count("organization.status_changed") >= 2, str(actions))
    check("Audit stores reasons", all(a["reason"] for a in audit if a["action"] == "organization.status_changed"))

    # Restore
    restore = client.post(f"/api/organizations/{org_id}/restore", json={"reason": "Khôi phục để tiếp tục pilot"}, headers=hdr(owner_token))
    check("Archived org can be restored", restore.status_code == 200, restore.text[:160])
    check("DB status active after restore", db_one("SELECT status FROM organizations WHERE id = ?", (org_id,))["status"] == "active")
    return org_id


# -----------------------------------------------------------------------------
# 2. RBAC + OWNERSHIP
# -----------------------------------------------------------------------------
def test_rbac_and_ownership(owner_token):
    print("\n--- 2. Explicit roles & permission enforcement ---")
    org_id = create_active_org(owner_token, "HTX Sprint 2 RBAC")
    stamp = str(int(time.time() * 1000))
    admin_token, admin_id, _ = invite_and_accept(org_id, owner_token, f"admin.{stamp}@test.vn", "admin")
    manager_token, manager_id, _ = invite_and_accept(org_id, owner_token, f"manager.{stamp}@test.vn", "manager")
    member_token, member_id, _ = invite_and_accept(org_id, owner_token, f"member.{stamp}@test.vn", "member")
    viewer_token, viewer_id, _ = invite_and_accept(org_id, owner_token, f"viewer.{stamp}@test.vn", "viewer")

    # Viewer read-only
    check("Viewer can read organization", client.get(f"/api/organizations/{org_id}", headers=hdr(viewer_token)).status_code == 200)
    check("Viewer can read members", client.get(f"/api/organizations/{org_id}/members", headers=hdr(viewer_token)).status_code == 200)
    viewer_patch = client.patch(f"/api/organizations/{org_id}/profile", json={"name": "Hacked by viewer"}, headers=hdr(viewer_token))
    check("Viewer cannot update profile", viewer_patch.status_code == 403, f"HTTP {viewer_patch.status_code}")
    check("Viewer DB name unchanged", db_one("SELECT name FROM organizations WHERE id = ?", (org_id,))["name"] != "Hacked by viewer")

    # Member cannot invite or change roles
    member_invite = client.post(f"/api/organizations/{org_id}/invitations", json={"email": f"x.{stamp}@test.vn", "role": "member"}, headers=hdr(member_token))
    check("Member cannot invite", member_invite.status_code == 403, f"HTTP {member_invite.status_code}")
    member_promote = client.patch(f"/api/organizations/{org_id}/members/{member_id}", json={"role": "admin"}, headers=hdr(member_token))
    check("Member cannot promote self", member_promote.status_code == 403, f"HTTP {member_promote.status_code}")
    check("Member role unchanged in DB", db_one("SELECT role FROM organization_members WHERE organization_id=? AND user_id=?", (org_id, member_id))["role"] == "member")

    # Admin capabilities and limits
    admin_invite = client.post(f"/api/organizations/{org_id}/invitations", json={"email": f"y.{stamp}@test.vn", "role": "member"}, headers=hdr(admin_token))
    check("Admin can invite regular member", admin_invite.status_code == 200, admin_invite.text[:120])
    admin_invite_admin = client.post(f"/api/organizations/{org_id}/invitations", json={"email": f"z.{stamp}@test.vn", "role": "admin"}, headers=hdr(admin_token))
    check("Admin cannot invite another admin", admin_invite_admin.status_code == 403, f"HTTP {admin_invite_admin.status_code}")
    admin_owner = client.patch(f"/api/organizations/{org_id}/members/{admin_id}", json={"role": "owner"}, headers=hdr(admin_token))
    check("Admin cannot self-assign owner", admin_owner.status_code in (400, 403), f"HTTP {admin_owner.status_code}")
    admin_suspend = client.post(f"/api/organizations/{org_id}/status", json={"status": "suspended", "reason": "admin attempt"}, headers=hdr(admin_token))
    check("Admin cannot change lifecycle status", admin_suspend.status_code == 403, f"HTTP {admin_suspend.status_code}")
    check("Org still active after admin attempt", db_one("SELECT status FROM organizations WHERE id=?", (org_id,))["status"] == "active")

    # Owner role assignment
    set_manager = client.patch(f"/api/organizations/{org_id}/members/{member_id}", json={"role": "manager", "reason": "Nâng quyền điều phối"}, headers=hdr(owner_token))
    check("Owner can assign manager", set_manager.status_code == 200, set_manager.text[:120])
    check("DB role updated to manager", db_one("SELECT role FROM organization_members WHERE organization_id=? AND user_id=?", (org_id, member_id))["role"] == "manager")

    # Last owner protections
    owner_id = db_one("SELECT owner_id FROM organizations WHERE id=?", (org_id,))["owner_id"]
    owner_remove = client.delete(f"/api/organizations/{org_id}/members/{owner_id}?reason=leave", headers=hdr(owner_token))
    check("Owner cannot remove self (last owner)", owner_remove.status_code == 403, f"HTTP {owner_remove.status_code}")
    owner_demote = client.patch(f"/api/organizations/{org_id}/members/{owner_id}", json={"role": "admin"}, headers=hdr(owner_token))
    check("Owner cannot demote self directly", owner_demote.status_code in (400, 403), f"HTTP {owner_demote.status_code}")
    check("Organization still has exactly one owner", db_one("SELECT COUNT(*) c FROM organization_members WHERE organization_id=? AND role='owner'", (org_id,))["c"] == 1)

    # Non-member transfer rejected
    outsider_token, outsider_id = register(f"outsider.{stamp}@test.vn", "Outsider")
    transfer_bad = client.post(f"/api/organizations/{org_id}/transfer-owner", json={"target_user_id": outsider_id, "reason": "invalid target"}, headers=hdr(owner_token))
    check("Transfer to non-member rejected", transfer_bad.status_code == 400, f"HTTP {transfer_bad.status_code}")

    # Safe ownership transfer
    transfer = client.post(f"/api/organizations/{org_id}/transfer-owner", json={"target_user_id": admin_id, "reason": "Bàn giao quyền sở hữu cho quản trị viên"}, headers=hdr(owner_token))
    check("Owner can transfer ownership", transfer.status_code == 200, transfer.text[:160])
    roles = {r["user_id"]: r["role"] for r in db_all("SELECT user_id, role FROM organization_members WHERE organization_id=?", (org_id,))}
    check("New owner set in DB", roles.get(admin_id) == "owner", str(roles))
    check("Previous owner becomes admin", roles.get(owner_id) == "admin", str(roles))
    org_owner = db_one("SELECT owner_id FROM organizations WHERE id=?", (org_id,))
    check("organizations.owner_id updated", org_owner["owner_id"] == admin_id, dict(org_owner))
    check("Exactly one owner after transfer", db_one("SELECT COUNT(*) c FROM organization_members WHERE organization_id=? AND role='owner'", (org_id,))["c"] == 1)

    # Audit records
    audit_actions = [a["action"] for a in db_all("SELECT action FROM organization_audit_log WHERE organization_id=?", (org_id,))]
    check("Role change audited", "member.role_changed" in audit_actions)
    check("Ownership transfer audited", "organization.owner_transferred" in audit_actions)
    return org_id


# -----------------------------------------------------------------------------
# 3. INVITATIONS
# -----------------------------------------------------------------------------
def test_invitations(owner_token, other_owner_token):
    print("\n--- 3. Invitation tokens, expiry, reuse, revoke & rate limit ---")
    org_id = create_active_org(owner_token, "HTX Sprint 2 Invitations")
    other_org_id = create_active_org(other_owner_token, "HTX Sprint 2 Other Tenant")
    stamp = str(int(time.time() * 1000))

    email = f"invitee.{stamp}@test.vn"
    inv = client.post(f"/api/organizations/{org_id}/invitations", json={"email": email, "role": "member"}, headers=hdr(owner_token))
    check("Create invitation returns 200", inv.status_code == 200, inv.text[:160])
    inv_body = inv.json()["invitation"]
    raw_token = inv_body["invite_token"]
    check("Raw token returned once", raw_token.startswith("gari_inv_"), raw_token[:14])
    check("Email is NOT claimed as sent", inv_body["email_sent"] is False and inv_body["delivery_mode"] == "manual")
    stored = db_one("SELECT token_hash, token_prefix, delivery_status FROM organization_invitations WHERE id=?", (inv_body["id"],))
    check("Only hash stored, not raw token", stored["token_hash"] != raw_token and len(stored["token_hash"]) == 64, stored["token_hash"][:12])
    check("Manual delivery status honest", stored["delivery_status"] == "pending_manual_delivery")

    # Wrong logged-in account gets a generic rejection (no account enumeration)
    other_token, other_id = register(f"wrong.{stamp}@test.vn", "Wrong User")
    wrong = client.post("/api/invitations/accept", json={"token": raw_token}, headers=hdr(other_token))
    check("Wrong email cannot accept", wrong.status_code == 400, f"HTTP {wrong.status_code} {wrong.text[:120]}")

    # Register after invitation, then accept
    invitee_token, invitee_id = register(email, "Invited User")
    accept = client.post("/api/invitations/accept", json={"token": raw_token}, headers=hdr(invitee_token))
    check("Invited user can accept after registration", accept.status_code == 200, accept.text[:160])
    check("Membership created", db_one("SELECT role FROM organization_members WHERE organization_id=? AND user_id=?", (org_id, invitee_id)) is not None)

    # Reuse rejected
    reuse = client.post("/api/invitations/accept", json={"token": raw_token}, headers=hdr(invitee_token))
    check("Reused token rejected", reuse.status_code == 400, f"HTTP {reuse.status_code}")

    # Expired token rejected
    expired_email = f"expired.{stamp}@test.vn"
    exp_inv = client.post(f"/api/organizations/{org_id}/invitations", json={"email": expired_email, "role": "member"}, headers=hdr(owner_token)).json()["invitation"]
    db_exec("UPDATE organization_invitations SET expires_at = '2000-01-01 00:00:00' WHERE id = ?", (exp_inv["id"],))
    expired_token, _ = register(expired_email, "Expired User")
    expired_resp = client.post("/api/invitations/accept", json={"token": exp_inv["invite_token"]}, headers=hdr(expired_token))
    check("Expired token rejected", expired_resp.status_code == 400, f"HTTP {expired_resp.status_code}")
    check("Expired invitation marked in DB", db_one("SELECT status FROM organization_invitations WHERE id=?", (exp_inv["id"],))["status"] == "expired")

    # Revoked token rejected
    rev_email = f"revoked.{stamp}@test.vn"
    rev_inv = client.post(f"/api/organizations/{org_id}/invitations", json={"email": rev_email, "role": "viewer"}, headers=hdr(owner_token)).json()["invitation"]
    rev = client.post(f"/api/organizations/{org_id}/invitations/{rev_inv['id']}/revoke", json={"reason": "Thu hồi theo yêu cầu kiểm thử"}, headers=hdr(owner_token))
    check("Owner can revoke invitation", rev.status_code == 200, rev.text[:120])
    rev_token, _ = register(rev_email, "Revoked User")
    revoked_resp = client.post("/api/invitations/accept", json={"token": rev_inv["invite_token"]}, headers=hdr(rev_token))
    check("Revoked token rejected", revoked_resp.status_code == 400, f"HTTP {revoked_resp.status_code}")

    # Invalid role
    bad_role = client.post(f"/api/organizations/{org_id}/invitations", json={"email": f"badrole.{stamp}@test.vn", "role": "owner"}, headers=hdr(owner_token))
    check("Invitation with role=owner rejected", bad_role.status_code == 400, f"HTTP {bad_role.status_code}")

    # Cross-tenant revocation: other owner cannot revoke this org's invitation
    cross_inv = client.post(f"/api/organizations/{org_id}/invitations", json={"email": f"cross.{stamp}@test.vn", "role": "member"}, headers=hdr(owner_token)).json()["invitation"]
    cross_revoke = client.post(
        f"/api/organizations/{other_org_id}/invitations/{cross_inv['id']}/revoke",
        json={"reason": "cross tenant attempt"}, headers=hdr(other_owner_token)
    )
    check("Cross-tenant revocation blocked", cross_revoke.status_code in (400, 404), f"HTTP {cross_revoke.status_code}")
    check("Invitation remains pending after cross-tenant attempt", db_one("SELECT status FROM organization_invitations WHERE id=?", (cross_inv["id"],))["status"] == "pending")

    # Invitation to suspended org cannot be accepted
    susp_email = f"susp.{stamp}@test.vn"
    susp_inv = client.post(f"/api/organizations/{org_id}/invitations", json={"email": susp_email, "role": "member"}, headers=hdr(owner_token)).json()["invitation"]
    susp_token, _ = register(susp_email, "Suspended User")
    client.post(f"/api/organizations/{org_id}/status", json={"status": "suspended", "reason": "Suspended for invitation test"}, headers=hdr(owner_token))
    susp_accept = client.post("/api/invitations/accept", json={"token": susp_inv["invite_token"]}, headers=hdr(susp_token))
    check("Invitation to suspended org rejected", susp_accept.status_code == 400, f"HTTP {susp_accept.status_code}")
    client.post(f"/api/organizations/{org_id}/status", json={"status": "active", "reason": "Restore after invitation test"}, headers=hdr(owner_token))

    # Rate limit on a fresh org
    rl_org = create_active_org(owner_token, "HTX Sprint 2 Rate Limit")
    statuses = []
    for i in range(10):
        r = client.post(f"/api/organizations/{rl_org}/invitations", json={"email": f"rl.{stamp}.{i}@test.vn", "role": "member"}, headers=hdr(owner_token))
        statuses.append(r.status_code)
    eleventh = client.post(f"/api/organizations/{rl_org}/invitations", json={"email": f"rl.{stamp}.11@test.vn", "role": "member"}, headers=hdr(owner_token))
    check("First 10 invitations accepted", all(s == 200 for s in statuses), str(statuses))
    check("11th invitation rate-limited (429)", eleventh.status_code == 429, f"HTTP {eleventh.status_code}")
    return org_id


# -----------------------------------------------------------------------------
# 4. PROFILE VALIDATION & PRIVACY
# -----------------------------------------------------------------------------
def test_profile(owner_token, other_owner_token):
    print("\n--- 4. Organization profile validation & privacy ---")
    org_id = create_active_org(owner_token, "HTX Sprint 2 Profile")
    other_org_id = create_active_org(other_owner_token, "HTX Sprint 2 Profile Other")

    cccd = client.patch(f"/api/organizations/{org_id}/profile", json={"cccd": "012345678901"}, headers=hdr(owner_token))
    check("CCCD is rejected", cccd.status_code == 400, f"HTTP {cccd.status_code}")
    gps = client.patch(f"/api/organizations/{org_id}/profile", json={"exact_latitude": 21.0285}, headers=hdr(owner_token))
    check("Exact GPS coordinates rejected", gps.status_code == 400, f"HTTP {gps.status_code}")
    bad_type = client.patch(f"/api/organizations/{org_id}/profile", json={"organization_type": "unknown_type"}, headers=hdr(owner_token))
    check("Invalid organization type rejected", bad_type.status_code == 400, f"HTTP {bad_type.status_code}")
    scale_no_consent = client.patch(f"/api/organizations/{org_id}/profile", json={"farming_scale": "5_20ha", "scale_consent": False}, headers=hdr(owner_token))
    check("Farming scale requires consent", scale_no_consent.status_code == 400, f"HTTP {scale_no_consent.status_code}")

    valid = client.patch(f"/api/organizations/{org_id}/profile", json={
        "name": "HTX Sprint 2 Profile Updated",
        "organization_type": "cooperative",
        "primary_crops": ["Lúa", "Cà chua"],
        "region": "Đồng bằng sông Cửu Long",
        "farming_scale": "5_20ha",
        "scale_consent": True,
        "contact_email": "contact@sprint2.vn",
        "contact_phone": "0900000000",
        "business_contact_name": "Nguyễn Văn A",
        "business_contact_title": "Giám đốc HTX",
        "business_contact_email": "a@sprint2.vn",
        "business_contact_phone": "0911111111",
        "reason": "Cập nhật hồ sơ đầy đủ",
    }, headers=hdr(owner_token))
    check("Valid profile update accepted", valid.status_code == 200, valid.text[:180])
    row = db_one("SELECT name, organization_type, region, farming_scale, primary_crops FROM organizations WHERE id=?", (org_id,))
    check("Profile persisted in DB", row["name"] == "HTX Sprint 2 Profile Updated" and row["organization_type"] == "cooperative", dict(row))
    check("Primary crops persisted as JSON", "Lúa" in (row["primary_crops"] or ""), row["primary_crops"])

    audit = db_all("SELECT action, metadata_json FROM organization_audit_log WHERE organization_id=? AND action='organization.profile_updated'", (org_id,))
    check("Profile changes audited", len(audit) >= 1, f"entries={len(audit)}")

    # Cross-tenant profile write must fail and leave DB untouched
    before = db_one("SELECT name, region FROM organizations WHERE id=?", (other_org_id,))
    cross = client.patch(f"/api/organizations/{other_org_id}/profile", json={"name": "Cross Tenant Hijack"}, headers=hdr(owner_token))
    after = db_one("SELECT name, region FROM organizations WHERE id=?", (other_org_id,))
    check("Cross-tenant profile update blocked", cross.status_code == 403, f"HTTP {cross.status_code}")
    check("Cross-tenant DB unchanged", dict(before) == dict(after), f"{dict(before)} -> {dict(after)}")


# -----------------------------------------------------------------------------
# 5. TENANT ISOLATION, API KEYS & SUSPENDED GATES
# -----------------------------------------------------------------------------
def test_tenant_isolation_and_api_keys(owner_token, other_owner_token):
    print("\n--- 5. Tenant isolation, API keys & suspended gates ---")
    org_a = create_active_org(owner_token, "HTX Sprint 2 Tenant A")
    org_b = create_active_org(other_owner_token, "HTX Sprint 2 Tenant B")
    stamp = str(int(time.time() * 1000))
    b_member_email = f"tenantb.{stamp}@test.vn"
    _, b_member_id, _ = invite_and_accept(org_b, other_owner_token, b_member_email, "member")

    # Read isolation
    read_b = client.get(f"/api/organizations/{org_b}", headers=hdr(owner_token))
    check("Org A cannot read Org B", read_b.status_code == 403, f"HTTP {read_b.status_code}")
    members_b = client.get(f"/api/organizations/{org_b}/members", headers=hdr(owner_token))
    check("Org A cannot read Org B members", members_b.status_code == 403, f"HTTP {members_b.status_code}")

    # Write isolation: remove member
    before_member = db_one("SELECT role FROM organization_members WHERE organization_id=? AND user_id=?", (org_b, b_member_id))
    del_cross = client.delete(f"/api/organizations/{org_b}/members/{b_member_id}?reason=cross", headers=hdr(owner_token))
    after_member = db_one("SELECT role FROM organization_members WHERE organization_id=? AND user_id=?", (org_b, b_member_id))
    check("Org A cannot remove Org B member", del_cross.status_code == 403, f"HTTP {del_cross.status_code}")
    check("Org B membership unchanged in DB", before_member is not None and after_member is not None and before_member["role"] == after_member["role"])

    # Invitation isolation
    inv_before = db_one("SELECT COUNT(*) c FROM organization_invitations WHERE organization_id=?", (org_b,))["c"]
    inv_cross = client.post(f"/api/organizations/{org_b}/invitations", json={"email": f"hijack.{stamp}@test.vn", "role": "admin"}, headers=hdr(owner_token))
    inv_after = db_one("SELECT COUNT(*) c FROM organization_invitations WHERE organization_id=?", (org_b,))["c"]
    check("Org A cannot invite into Org B", inv_cross.status_code == 403, f"HTTP {inv_cross.status_code}")
    check("Org B invitation count unchanged", inv_before == inv_after, f"{inv_before} -> {inv_after}")

    # API key isolation
    keys_cross = client.get(f"/api/organizations/{org_b}/api-keys", headers=hdr(owner_token))
    check("Org A cannot list Org B API keys", keys_cross.status_code == 403, f"HTTP {keys_cross.status_code}")

    # Create a Team-plan org via the platform-admin path to test API keys
    team_org = gari_b2b.create_organization(
        name="HTX Sprint 2 Team API",
        owner_id=db_one("SELECT id FROM users WHERE email LIKE 'sprint2.owner.a%'")["id"],
        plan_id="team",
        actor_is_platform_admin=True,
    )
    team_org_id = team_org["id"]
    owner_a_id = db_one("SELECT owner_id FROM organizations WHERE id=?", (org_a,))["owner_id"]
    gari_b2b.transition_organization_status(team_org_id, owner_a_id, "active", "Kích hoạt cho kiểm thử API", is_platform_admin=True)
    key_obj = gari_b2b.generate_api_key(team_org_id, owner_a_id, "Sprint 2 Team Key")
    check("Team plan API key generated", key_obj["full_key"].startswith("gari_live_"))
    key_ctx = gari_b2b.authenticate_api_key(key_obj["full_key"])
    check("API key authenticates with org context", key_ctx is not None and key_ctx["organization_id"] == team_org_id)
    check("API key context marks operational + API access", key_ctx["is_operational"] is True and key_ctx["has_api_access"] is True)

    # Cross-tenant key revoke via Org B endpoint must fail
    revoke_cross = client.post(f"/api/organizations/{org_b}/api-keys/{key_obj['id']}/revoke", headers=hdr(owner_token))
    check("Org A cannot revoke key through Org B endpoint", revoke_cross.status_code == 403, f"HTTP {revoke_cross.status_code}")
    check("Team API key still active", db_one("SELECT is_active FROM api_keys WHERE id=?", (key_obj["id"],))["is_active"] == 1)

    # Suspend the team org -> API key is rejected with 403
    gari_b2b.transition_organization_status(team_org_id, owner_a_id, "suspended", "Tạm ngưng kiểm thử API", is_platform_admin=True)
    files = {"image": ("leaf.jpg", jpeg_bytes(), "image/jpeg")}
    api_blocked = client.post("/api/v1/diagnose", headers={"X-Gari-API-Key": key_obj["full_key"]}, files=files, data={"mode": "auto_standard"})
    check("API key blocked when org suspended", api_blocked.status_code == 403, f"HTTP {api_blocked.status_code} {api_blocked.text[:120]}")
    gari_b2b.transition_organization_status(team_org_id, owner_a_id, "active", "Khôi phục sau kiểm thử", is_platform_admin=True)

    # Spoofed org_id on the web diagnose endpoint must not change tenant scope
    usage_before = db_one("SELECT COUNT(*) c FROM usage_metering WHERE organization_id=?", (org_b,))["c"]
    spoof = client.post(
        "/api/plant/diagnose",
        data={"org_id": str(org_b)},
        files=files,
        headers=hdr(owner_token),
    )
    usage_after = db_one("SELECT COUNT(*) c FROM usage_metering WHERE organization_id=?", (org_b,))["c"]
    check("Spoofed org_id in usage request blocked", spoof.status_code == 403, f"HTTP {spoof.status_code}")
    check("Spoofed request did not meter Org B", usage_before == usage_after, f"{usage_before} -> {usage_after}")

    # Viewer cannot use an organization they only view? They can diagnose with org quota by design
    # (viewer has diagnosis.use? no — viewer permissions exclude diagnosis.use). Verify capability map.
    check("Viewer lacks diagnosis.use", "diagnosis.use" not in gari_b2b.ROLE_PERMISSIONS["viewer"])
    check("Manager has workflow.manage", "workflow.manage" in gari_b2b.ROLE_PERMISSIONS["manager"])
    check("Admin cannot transfer ownership", "members.owner_transfer" not in gari_b2b.ROLE_PERMISSIONS["admin"])


# -----------------------------------------------------------------------------
# 6. RESUMABLE ONBOARDING & COMMERCIAL INTENT
# -----------------------------------------------------------------------------
def test_onboarding_resume(owner_token):
    print("\n--- 6. Resumable onboarding & pilot vs contract distinction ---")
    resp = create_org(owner_token, "HTX Sprint 2 Resume")
    org_id = resp.json()["organization"]["id"]

    step2 = client.patch(f"/api/organizations/{org_id}/onboarding", json={
        "step": 2, "organization_type": "farm", "region": "Tây Nguyên", "primary_crops": ["Cà phê"]
    }, headers=hdr(owner_token))
    check("Partial onboarding saved", step2.status_code == 200, step2.text[:120])

    resume = client.get(f"/api/organizations/{org_id}/onboarding", headers=hdr(owner_token)).json()
    ob = resume["onboarding"]
    check("Resume step persisted", ob["current_step"] >= 2, f"step={ob['current_step']}")
    check("Profile completion persisted", ob["profile_completed"] is True)
    check("Organization still pending before completion", resume["organization"]["status"] == "pending")
    check("Plan remains pilot during onboarding", resume["organization"]["plan_id"] == "pilot")

    # Completion without role confirmation must fail
    incomplete = client.patch(f"/api/organizations/{org_id}/onboarding", json={
        "step": 5, "complete": True, "needs": ["pilot"], "commercial_intent": "pilot_interest"
    }, headers=hdr(owner_token))
    check("Completion requires role confirmation", incomplete.status_code == 400, f"HTTP {incomplete.status_code}")
    check("Org still pending after failed completion", db_one("SELECT status FROM organizations WHERE id=?", (org_id,))["status"] == "pending")

    # Confirm role + needs, then complete with signed_contract intent -- still no paid plan
    client.patch(f"/api/organizations/{org_id}/onboarding", json={"step": 3, "role_confirmed": True}, headers=hdr(owner_token))
    done = client.patch(f"/api/organizations/{org_id}/onboarding", json={
        "step": 5, "complete": True, "role_confirmed": True,
        "needs": ["diagnosis", "pilot"], "commercial_intent": "signed_contract"
    }, headers=hdr(owner_token))
    check("Onboarding completes", done.status_code == 200, done.text[:160])
    check("Organization active after completion", done.json()["organization"]["status"] == "active")
    check("Signed-contract intent does NOT auto-assign paid plan", done.json()["organization"]["plan_id"] == "pilot", f"plan={done.json()['organization']['plan_id']}")
    ob_row = db_one("SELECT status, commercial_intent, needs_json FROM organization_onboarding WHERE organization_id=?", (org_id,))
    check("Onboarding marked completed", ob_row["status"] == "completed")
    check("Commercial intent stored", ob_row["commercial_intent"] == "signed_contract", ob_row["commercial_intent"])
    check("Pilot interest vs contract are distinct values", {"none", "pilot_interest", "signed_contract"} == set(gari_b2b.COMMERCIAL_INTENTS))
    check("Audit records onboarding completion", any(a["action"] == "organization.status_changed" for a in db_all("SELECT action FROM organization_audit_log WHERE organization_id=?", (org_id,))))


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main():
    print("=" * 74)
    print(" GARI AI LAB — SPRINT 2 ACCEPTANCE SUITE (ISOLATED TEMP DATABASE)")
    print(f" Test DB: {TEST_DB}")
    print("=" * 74)
    stamp = str(int(time.time() * 1000))
    owner_a_token, owner_a_id = register(f"sprint2.owner.a.{stamp}@test.vn", "Owner A")
    owner_b_token, owner_b_id = register(f"sprint2.owner.b.{stamp}@test.vn", "Owner B")
    owner_c_token, owner_c_id = register(f"sprint2.owner.c.{stamp}@test.vn", "Owner C")
    owner_d_token, owner_d_id = register(f"sprint2.owner.d.{stamp}@test.vn", "Owner D")

    try:
        test_lifecycle_and_no_paid_plan(owner_a_token)
        test_rbac_and_ownership(owner_b_token)
        test_invitations(owner_c_token, owner_d_token)
        test_profile(owner_c_token, owner_d_token)
        test_tenant_isolation_and_api_keys(owner_a_token, owner_d_token)
        test_onboarding_resume(owner_b_token)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        check("Suite completed without unhandled exception", False, str(exc))

    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print("\n" + "=" * 74)
    print(f" RESULT: {passed}/{total} checks passed, {len(FAILURES)} failed")
    if FAILURES:
        for name, detail in FAILURES:
            print(f"   FAILED: {name} — {detail}")
        print(" SPRINT 2 ACCEPTANCE: FAILED")
    else:
        print(" SPRINT 2 ACCEPTANCE: PASSED")
    print("=" * 74)

    # Cleanup isolated test database (real database untouched)
    try:
        shutil.rmtree(TMP_DIR, ignore_errors=True)
        print(f" Cleaned up temporary test database: {TMP_DIR}")
    except Exception:
        pass

    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
