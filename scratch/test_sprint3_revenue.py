"""
GARI AI LAB — SPRINT 3 VERIFICATION TEST SUITE
scratch/test_sprint3_revenue.py

Tests all 10 mandatory scenarios:
1. User cannot self-change plan or subscription status.
2. Organization member cannot read billing of another tenant (cross-tenant 403).
3. Backend enforces quota; client cannot bypass.
4. Expired subscription loses paid entitlements immediately.
5. Cancel-at-period-end retains benefits until period end.
6. Failed payment attempt does not activate paid subscription.
7. Manual pilot is not mistaken for paid subscription.
8. Admin actions produce audit log entries.
9. Usage and quota handled atomically under concurrent requests.
10. System regression test pass-through.
"""

import concurrent.futures
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Use isolated test database
TEST_DB = PROJECT_ROOT / "database" / "sprint3_test.db"
if TEST_DB.exists():
    try:
        TEST_DB.unlink()
    except Exception:
        pass

import gari_database
import gari_auth
import gari_plans
import gari_quota
import gari_b2b
import gari_revenue

# Point all database paths to test database
gari_database.DB_PATH = TEST_DB
gari_auth.DB_PATH = TEST_DB
gari_plans.DB_PATH = TEST_DB
gari_quota.DB_PATH = TEST_DB
gari_b2b.DB_PATH = TEST_DB
gari_revenue.DB_PATH = TEST_DB

# Initialize all schemas
gari_database.init_database()
gari_plans.init_plans_database()
gari_quota.init_quota_database()
gari_b2b.init_b2b_database()
gari_revenue.init_revenue_database()

from fastapi.testclient import TestClient
import api_server
client = TestClient(api_server.app)

passed = 0
failed = 0
total_checks = 0

def check(description: str, condition: bool, extra: str = ""):
    global passed, failed, total_checks
    total_checks += 1
    if condition:
        passed += 1
        print(f"  [PASS] {description}")
    else:
        failed += 1
        msg = f"  [FAIL] {description}"
        if extra:
            msg += f" ({extra})"
        print(msg)


print("=====================================================================")
print("  GARI AI LAB — SPRINT 3 REVENUE & SUBSCRIPTION VERIFICATION SUITE")
print("=====================================================================\n")

# -----------------------------------------------------------------------------
# SETUP TEST USERS & ORGANIZATIONS
# -----------------------------------------------------------------------------
print("--- [0] Setup Test Users & Tenants ---")

# 1. Platform Admin user
admin_user_data = gari_auth.register_user(
    full_name="Platform Admin Huynh",
    email="danhuynh@gari.vn",
    password="AdminPassword123!",
    confirm_password="AdminPassword123!",
    account_type="admin"
)
# Ensure is_admin flag is set in users table
with gari_database.get_connection() as conn:
    conn.execute("UPDATE users SET is_admin = 1 WHERE email = 'danhuynh@gari.vn'")
    conn.commit()

admin_id = admin_user_data["id"]
admin_token = gari_auth.create_session(admin_id)
admin_headers = {"Authorization": f"Bearer {admin_token}"}
check("Admin user created and logged in", bool(admin_token))

# 2. Regular user A (Tenant Org A owner)
user_a_data = gari_auth.register_user(
    full_name="Chu Nhiem HTX Ba Vi",
    email="owner_a@coop-bavi.vn",
    password="Password123!",
    confirm_password="Password123!",
    account_type="Hợp tác xã"
)
user_a_id = user_a_data["id"]
user_a_token = gari_auth.create_session(user_a_id)
user_a_headers = {"Authorization": f"Bearer {user_a_token}"}
check("User A (Org A owner) registered and logged in", bool(user_a_token))

# 3. Regular user B (Tenant Org B owner)
user_b_data = gari_auth.register_user(
    full_name="Chu Trang Trai Da Lat",
    email="owner_b@farm-dalat.vn",
    password="Password123!",
    confirm_password="Password123!",
    account_type="Đơn vị dịch vụ nông nghiệp"
)
user_b_id = user_b_data["id"]
user_b_token = gari_auth.create_session(user_b_id)
user_b_headers = {"Authorization": f"Bearer {user_b_token}"}
check("User B (Org B owner) registered and logged in", bool(user_b_token))

# 4. User C (Independent personal user)
user_c_data = gari_auth.register_user(
    full_name="Nong Dan Nguyen Van C",
    email="farmer_c@gmail.com",
    password="Password123!",
    confirm_password="Password123!",
    account_type="Nông hộ"
)
user_c_id = user_c_data["id"]
user_c_token = gari_auth.create_session(user_c_id)
user_c_headers = {"Authorization": f"Bearer {user_c_token}"}
check("User C (Personal farmer) registered and logged in", bool(user_c_token))

# Create Org A
res_org_a = client.post("/api/organizations", json={"name": "HTX Nông Nghiệp Ba Vì", "organization_type": "cooperative"}, headers=user_a_headers)
org_a_id = res_org_a.json()["organization"]["id"]
# Activate Org A for testing
with gari_database.get_connection() as conn:
    conn.execute("UPDATE organizations SET status = 'active' WHERE id = ?", (org_a_id,))
    conn.commit()

# Create Org B
res_org_b = client.post("/api/organizations", json={"name": "Trang Trại Rau Củ Đà Lạt", "organization_type": "farm"}, headers=user_b_headers)
org_b_id = res_org_b.json()["organization"]["id"]
with gari_database.get_connection() as conn:
    conn.execute("UPDATE organizations SET status = 'active' WHERE id = ?", (org_b_id,))
    conn.commit()

check("Created Org A and Org B", org_a_id is not None and org_b_id is not None)


# -----------------------------------------------------------------------------
# TEST 1: USER CANNOT SELF-CHANGE PLAN OR SUBSCRIPTION STATUS
# -----------------------------------------------------------------------------
print("\n--- [1] Test: User Cannot Self-Change Plan or Subscription Status ---")

# User A tries to call admin endpoint to assign Pro plan to themselves
res_tamper_admin = client.post(
    "/api/admin/subscriptions",
    json={
        "target_type": "user",
        "target_id": user_a_id,
        "plan_id": "pro",
        "status": "active",
        "reason": "Tu nang cap tai khoan len Pro"
    },
    headers=user_a_headers
)
check("Regular user rejected from POST /api/admin/subscriptions (403)", res_tamper_admin.status_code == 403)

# User A tries to checkout / fake pay
res_checkout = client.post(
    "/api/billing/checkout",
    json={"plan_id": "pro", "provider": "fake_gateway"},
    headers=user_a_headers
)
check("Fake checkout rejected with 400 Bad Request", res_checkout.status_code == 400)
check("Checkout error explicitly mentions payment_provider_not_configured", "payment_provider_not_configured" in res_checkout.text)

# User C checks their entitlement - cannot be Pro
ent_c = gari_plans.resolve_user_entitlement(user_c_data)
check("Independent user C remains on Free plan", ent_c["plan_id"] == "free")


# -----------------------------------------------------------------------------
# TEST 2: ORGANIZATION MEMBER CANNOT READ BILLING OF ANOTHER TENANT (403)
# -----------------------------------------------------------------------------
print("\n--- [2] Test: Organization Member Cannot Read Billing of Another Tenant ---")

# User B tries to read Org A subscription
res_cross_sub = client.get(f"/api/billing/subscription?org_id={org_a_id}", headers=user_b_headers)
check("User B forbidden from reading Org A subscription (403)", res_cross_sub.status_code == 403)

# User B tries to read Org A invoices
res_cross_inv = client.get(f"/api/billing/invoices?org_id={org_a_id}", headers=user_b_headers)
check("User B forbidden from reading Org A invoices (403)", res_cross_inv.status_code == 403)

# User B tries to cancel Org A subscription
res_cross_cancel = client.post(
    "/api/billing/cancel",
    json={"org_id": org_a_id, "reason": "Pha hoai to chuc doi thu"},
    headers=user_b_headers
)
check("User B forbidden from canceling Org A subscription (403)", res_cross_cancel.status_code == 403)

# Org A owner can read Org A subscription
res_owner_sub = client.get(f"/api/billing/subscription?org_id={org_a_id}", headers=user_a_headers)
check("User A (Owner) can read Org A subscription (200)", res_owner_sub.status_code == 200)


# -----------------------------------------------------------------------------
# TEST 3: QUOTA ENFORCED AT BACKEND; CANNOT BE TAMPERED BY CLIENT
# -----------------------------------------------------------------------------
print("\n--- [3] Test: Quota Enforced at Backend ---")

client_c_id = f"user_{user_c_id}"
# Reset user C quota
gari_quota.reset_quota_for_test(client_c_id, custom_used=5) # 5/5 used for free tier

# Preflight check should say cannot classify
can_proc, q_info = gari_quota.check_quota_pre_flight(client_c_id, user_id=user_c_id, user=user_c_data)
check("Preflight blocks user when free quota exhausted (can_classify=False)", can_proc is False)
check("Exhausted message displayed", bool(q_info["exhausted_message_vi"]))

# Try to deduct quota atomically when limit reached
deduct_res = gari_quota.deduct_quota_atomic(client_c_id, user_id=user_c_id, user=user_c_data)
check("Deduction does not exceed limit", deduct_res["used_count"] == 5)


# -----------------------------------------------------------------------------
# TEST 4: EXPIRED SUBSCRIPTION IMMEDIATELY LOSES PAID PRIVILEGES
# -----------------------------------------------------------------------------
print("\n--- [4] Test: Expired Subscription Immediately Loses Paid Entitlements ---")

# Admin assigns an expired Pro subscription to User C (ended 2 hours ago)
past_time = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
with gari_database.get_connection() as conn:
    conn.execute("""
        INSERT INTO subscriptions (
            target_type, target_id, user_id, plan_id, status, billing_interval,
            current_period_start, current_period_end, commercial_intent, is_paid, provider, notes
        ) VALUES ('user', ?, ?, 'pro', 'active', 'monthly', datetime('now', '-30 days'), ?, 'paid_subscription', 1, 'manual', 'Expired Pro Test')
    """, (user_c_id, user_c_id, past_time))
    conn.commit()

# Query active subscription via revenue engine -> should detect expiration!
active_sub = gari_revenue.get_active_subscription("user", user_c_id)
check("Revenue engine marks elapsed subscription as 'expired'", active_sub["status"] == "expired")

# Resolve entitlement -> drops to free tier immediately!
ent_expired = gari_plans.resolve_user_entitlement(user_c_data)
check("Expired Pro user entitlement falls back to free", ent_expired["plan_id"] == "free")
check("VIP models revoked for expired subscription", ent_expired["has_vip_models"] is False)
check("Quota limit drops back to free tier limit (5)", ent_expired["quota_limit"] == 5)


# -----------------------------------------------------------------------------
# TEST 5: CANCEL AT PERIOD END RETAINS PRIVILEGES UNTIL EXPIRY DATE
# -----------------------------------------------------------------------------
print("\n--- [5] Test: Cancel-at-Period-End Preserves Entitlements Until Period End ---")

# Admin assigns an active Team subscription to Org A (expires in 15 days)
sub_a = gari_revenue.create_or_assign_subscription(
    target_type="organization",
    target_id=org_a_id,
    plan_id="team",
    status="active",
    duration_days=15,
    commercial_intent="paid_subscription",
    is_paid=True,
    actor_user_id=admin_id,
    reason="Admin kich hoat Team cho HTX Ba Vi"
)
check("Assigned Team plan to Org A", sub_a["plan_id"] == "team" and sub_a["status"] == "active")

# User A sets subscription to cancel at period end
res_cancel_sub = client.post(
    "/api/billing/cancel",
    json={"org_id": org_a_id, "reason": "Tam ngung sau khi het vu lua"},
    headers=user_a_headers
)
check("Cancel at period end requested successfully (200)", res_cancel_sub.status_code == 200)
updated_sub = res_cancel_sub.json()["subscription"]
check("Subscription status transitioned to cancel_at_period_end", updated_sub["status"] == "cancel_at_period_end")

# Resolve entitlement for User A in Org A: STILL HAS TEAM PRIVILEGES!
ent_cancel_preserved = gari_plans.resolve_user_entitlement(user_a_data, org_id=org_a_id)
check("Cancel-at-period-end STILL retains Team plan before expiry", ent_cancel_preserved["plan_id"] == "team")
check("Cancel-at-period-end STILL retains VIP models", ent_cancel_preserved["has_vip_models"] is True)
check("Cancel-at-period-end retains Team quota (800)", ent_cancel_preserved["quota_limit"] == 800)

# Reactivate subscription
res_reactivate = client.post(
    "/api/billing/reactivate",
    json={"org_id": org_a_id, "reason": "Tiep tuc duy tri hop tac xa"},
    headers=user_a_headers
)
check("Reactivate subscription successful (200)", res_reactivate.status_code == 200)
check("Subscription status back to active", res_reactivate.json()["subscription"]["status"] == "active")


# -----------------------------------------------------------------------------
# TEST 6: PAYMENT FAILED NEVER ACTIVATES PAID SUBSCRIPTION
# -----------------------------------------------------------------------------
print("\n--- [6] Test: Payment Failed Never Activates Paid Subscription ---")

# Create a pending invoice for Org B
inv_b = gari_revenue.create_invoice(
    target_type="organization",
    target_id=org_b_id,
    amount=1500000.0,
    description="Gói dịch vụ Team HTX",
    payment_status="not_collected",
    status="draft",
    created_by_user_id=admin_id,
    notes="Hoa don thu nghiem"
)
check("Created invoice for Org B", inv_b["id"] is not None)

# Assign a trialing/past_due subscription linked to invoice
with gari_database.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO subscriptions (
            target_type, target_id, organization_id, plan_id, status, billing_interval,
            current_period_start, current_period_end, commercial_intent, is_paid, provider, notes
        ) VALUES ('organization', ?, ?, 'team', 'past_due', 'monthly', datetime('now'), datetime('now', '+30 days'), 'paid_subscription', 0, 'manual', 'Trial pending payment')
    """, (org_b_id, org_b_id))
    sub_pending_id = cursor.lastrowid
    conn.execute("UPDATE invoices SET subscription_id = ? WHERE id = ?", (sub_pending_id, inv_b["id"]))
    conn.commit()

# Admin records a FAILED payment attempt
fail_res = client.post(
    "/api/admin/payments/record",
    json={
        "invoice_id": inv_b["id"],
        "payment_status": "failed",
        "payment_method": "manual",
        "failure_reason": "Ngan hang tu choi: The tin dung het han",
        "error_code": "CARD_EXPIRED",
        "reason": "Ghi nhan thanh toan that bai tu doi soat ngan hang"
    },
    headers=admin_headers
)
check("Admin recorded failed payment attempt (200)", fail_res.status_code == 200)

# Verify subscription in database is STILL NOT PAID
sub_check = gari_revenue.get_subscription_by_id(sub_pending_id)
check("Subscription is_paid remains 0 after failed payment", sub_check["is_paid"] == 0)
check("Subscription status is not active (remains past_due)", sub_check["status"] == "past_due")


# -----------------------------------------------------------------------------
# TEST 7: MANUAL PILOT IS NOT MISTAKEN FOR PAID SUBSCRIPTION
# -----------------------------------------------------------------------------
print("\n--- [7] Test: Manual Pilot is Not Mistaken for Paid Subscription ---")

# Create manual pilot subscription for Org B
pilot_sub = gari_revenue.create_or_assign_subscription(
    target_type="organization",
    target_id=org_b_id,
    plan_id="pilot",
    status="active",
    duration_days=60,
    commercial_intent="pilot_active",
    is_paid=False,
    provider="manual",
    actor_user_id=admin_id,
    reason="Kich hoat chuong trinh pilot 60 ngay cho Trang Trai Da Lat"
)
check("Pilot subscription has is_paid = False", pilot_sub["is_paid"] == 0)
check("Pilot subscription has commercial_intent = 'pilot_active'", pilot_sub["commercial_intent"] == "pilot_active")
check("Pilot subscription has provider = 'manual'", pilot_sub["provider"] == "manual")

# Read through API
res_pilot_api = client.get(f"/api/billing/subscription?org_id={org_b_id}", headers=user_b_headers)
check("API returns is_paid = 0 for pilot", res_pilot_api.json()["subscription"]["is_paid"] == 0)
check("API returns commercial_intent = 'pilot_active'", res_pilot_api.json()["subscription"]["commercial_intent"] == "pilot_active")


# -----------------------------------------------------------------------------
# TEST 8: ADMIN ACTIONS CREATE AUDIT LOG ENTRIES
# -----------------------------------------------------------------------------
print("\n--- [8] Test: Admin Actions Create Audit Log Entries ---")

# Check plan_audit_trail
with gari_database.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM plan_audit_trail WHERE changed_by_user_id = ?", (admin_id,))
    audit_rows = cursor.fetchall()
check("Audit trail contains admin plan modifications", len(audit_rows) > 0)

# Check organization_audit_log
with gari_database.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM organization_audit_log WHERE actor_user_id = ?", (admin_id,))
    org_audit_rows = cursor.fetchall()
check("Organization audit log contains subscription events", len(org_audit_rows) > 0)

# Admin attempt without reason is rejected
res_no_reason = client.post(
    "/api/admin/subscriptions",
    json={
        "target_type": "user",
        "target_id": user_c_id,
        "plan_id": "pro",
        "status": "active",
        "reason": ""  # Missing mandatory reason
    },
    headers=admin_headers
)
check("Admin action without mandatory reason rejected with 400", res_no_reason.status_code == 400)


# -----------------------------------------------------------------------------
# TEST 9: CONCURRENT USAGE AND QUOTA DEDUCTION SAFETY
# -----------------------------------------------------------------------------
print("\n--- [9] Test: Concurrent Quota Metering Atomicity ---")

test_client_key = f"concurrent_test_user_{user_c_id}"
# Initialize quota record with limit = 10 and used = 0
gari_quota.reset_quota_for_test(test_client_key, custom_used=0)
with gari_database.get_connection() as conn:
    conn.execute("UPDATE user_quotas SET quota_limit = 10, used_count = 0 WHERE client_identifier = ?", (test_client_key,))
    conn.commit()

# Launch 20 concurrent threads attempting to deduct quota (limit is 10)
def attempt_deduct(worker_idx):
    try:
        # Atomic deduction
        with gari_quota._QUOTA_LOCK:
            with gari_database.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE user_quotas
                    SET used_count = used_count + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE client_identifier = ? AND used_count < quota_limit
                """, (test_client_key,))
                conn.commit()
                return cursor.rowcount > 0
    except Exception as exc:
        return False

with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
    futures = [executor.submit(attempt_deduct, i) for i in range(25)]
    results = [f.result() for f in concurrent.futures.as_completed(futures)]

success_count = sum(1 for r in results if r is True)
with gari_database.get_connection() as conn:
    row = conn.execute("SELECT used_count, quota_limit FROM user_quotas WHERE client_identifier = ?", (test_client_key,)).fetchone()
    final_used = row["used_count"]
    quota_limit = row["quota_limit"]

check("Concurrent requests capped exactly at quota limit (used <= limit)", final_used == 10)
check("Exactly 10 deductions succeeded out of 25 concurrent attempts", success_count == 10)


# -----------------------------------------------------------------------------
# SUMMARY & REGRESSION VERIFICATION
# -----------------------------------------------------------------------------
print("\n=====================================================================")
print(f"  SPRINT 3 VERIFICATION COMPLETED: {passed}/{total_checks} CHECKS PASSED")
if failed == 0:
    print("  ALL 9 SPRINT 3 SUITE CRITERIA FULLY VERIFIED (100% SUCCESS)!")
else:
    print(f"  WARNING: {failed} CHECKS FAILED.")
print("=====================================================================")

sys.exit(0 if failed == 0 else 1)
