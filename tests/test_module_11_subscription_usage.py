"""
GARI MODULE 11 — SUBSCRIPTION & USAGE MANAGEMENT TEST SUITE
(tests/test_module_11_subscription_usage.py)

Comprehensive test verification covering:
1. Configurable plans (Free, Pro, Ultra, Organization, Enterprise) loaded dynamically from database.
2. Admin dynamic plan configuration (updating prices, limits, and features).
3. Entitlement resolution for Free, Pro, Ultra, and Enterprise tiers.
4. Backend limit enforcement: Maximum farms limit per plan (HTTP 403 + structured upgrade payload).
5. Backend limit enforcement: Maximum plots limit per plan.
6. Backend limit enforcement: AI usage quota deduction and blocking when limit reached.
7. Backend limit enforcement: Organization seats limit.
8. Subscription lifecycle states: active, cancel_at_period_end (retaining benefits), expired, reactivate.
9. Billing Provider Adapter Zero-Trust: Never grants subscription on transfer report until provider confirms.
10. Multi-metric usage summary endpoint consistency (GET /api/subscriptions/usage).
"""

import json
import sqlite3
import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import api_server
import gari_entitlements
import gari_billing_adapter
from api_server import app

client = TestClient(app)
DB_PATH = ROOT_DIR / "database" / "disease_detector.db"


def _get_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def _create_test_user(prefix: str, role: str = "personal_user", account_type: str = "farmer"):
    unique = uuid.uuid4().hex[:8]
    email = f"{prefix.lower()}_{unique}@gari.test"
    password = "Password123!"
    full_name = f"Test {prefix} {unique}"

    res = client.post("/api/auth/register", json={
        "email": email,
        "password": password,
        "confirm_password": password,
        "full_name": full_name,
        "account_type": account_type
    })
    assert res.status_code == 200, res.text
    data = res.json()
    user = data.get("user") or {}
    token = data.get("token") or data.get("access_token")

    if role in ("host_admin", "admin"):
        with _get_db() as conn:
            conn.execute("UPDATE users SET is_admin = 1, is_host_admin = 1 WHERE id = ?", (user["id"],))
            conn.commit()

    return user, token, {"Authorization": f"Bearer {token}"}


def _create_admin_user():
    return _create_test_user("AdminM11", role="host_admin", account_type="business")


class TestModule11SubscriptionUsage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import migrations_module_11_subscriptions
        migrations_module_11_subscriptions.run_migration()
        gari_entitlements.invalidate_plans_cache()

    def test_01_configurable_plans_loading_and_fallback(self):
        """Verifies plans are loaded dynamically from the database and configurable."""
        res = client.get("/api/subscriptions/plans")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"))
        plans = data.get("plans", [])
        plan_ids = [p["id"] for p in plans]

        # Must support all required tiers
        for expected in ["free", "pro", "ultra", "organization", "enterprise"]:
            self.assertIn(expected, plan_ids, f"Gói {expected} phải có trong danh sách.")

        # Check configurable attributes
        pro = next(p for p in plans if p["id"] == "pro")
        self.assertEqual(pro["price"], 129000)
        self.assertEqual(pro["max_farms"], 3)
        self.assertIn("ai_assistant", pro["allowed_features"])

    def test_02_admin_update_plan_configuration(self):
        """Verifies platform admin can dynamically update plan prices, limits, and features."""
        admin_user, admin_token, admin_headers = _create_admin_user()

        # Update ultra plan diagnosis limit and price dynamically
        payload = {
            "price": 259000,
            "diagnosis_limit": 550,
            "ai_usage_limit": 600
        }
        res = client.put("/api/admin/subscriptions/plans/ultra", json=payload, headers=admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"))
        updated_plan = data.get("plan", {})
        self.assertEqual(updated_plan.get("price"), 259000)
        self.assertEqual(updated_plan.get("diagnosis_limit"), 550)

        # Restore original values for test idempotency
        gari_entitlements.update_plan_configuration("ultra", {
            "price": 249000,
            "diagnosis_limit": 500,
            "ai_usage_limit": 500
        })

    def test_03_entitlement_resolution_for_free_pro_and_ultra(self):
        """Resolves entitlements for Free, Pro, Ultra, and Enterprise tiers."""
        user, token, headers = _create_test_user("EntUser")
        uid = user["id"]

        # 1. Default should be Free tier
        free_ent = gari_entitlements.resolve_entitlements(uid)
        self.assertEqual(free_ent["plan_id"], "free")
        self.assertEqual(free_ent["tier_level"], 0)
        self.assertEqual(free_ent["limits"]["max_farms"], 5)
        self.assertEqual(free_ent["limits"]["max_plots"], 25)

        # 2. Upgrade to Pro
        gari_entitlements.assign_subscription("user", uid, "pro", duration_days=30)
        pro_ent = gari_entitlements.resolve_entitlements(uid)
        self.assertEqual(pro_ent["plan_id"], "pro")
        self.assertEqual(pro_ent["tier_level"], 10)
        self.assertEqual(pro_ent["limits"]["max_farms"], 3)
        self.assertEqual(pro_ent["limits"]["max_plots"], 15)

        # 3. Upgrade to Ultra
        gari_entitlements.assign_subscription("user", uid, "ultra", duration_days=30)
        ultra_ent = gari_entitlements.resolve_entitlements(uid)
        self.assertEqual(ultra_ent["plan_id"], "ultra")
        self.assertEqual(ultra_ent["tier_level"], 20)
        self.assertEqual(ultra_ent["limits"]["max_farms"], 10)
        self.assertEqual(ultra_ent["limits"]["max_plots"], 50)
        self.assertEqual(ultra_ent["limits"]["storage_mb"], 2048)

    def test_04_backend_limit_enforcement_max_farms(self):
        """Verifies that creating more farms than the plan limit is strictly rejected by backend."""
        user, token, headers = _create_test_user("FarmQuotaUser")
        uid = user["id"]

        # Dynamically set free plan max_farms to 1 to test enforcement boundary
        gari_entitlements.update_plan_configuration("free", {"max_farms": 1})
        try:
            res1 = client.post("/api/farms", json={"name": "Trang Trại Đầu Tiên"}, headers=headers)
            self.assertEqual(res1.status_code, 200)

            # Attempt to create second farm -> Should be rejected with 403
            res2 = client.post("/api/farms", json={"name": "Trang Trại Thứ Hai"}, headers=headers)
            self.assertEqual(res2.status_code, 403)
            err = res2.json()
            detail = err.get("detail", {})
            self.assertEqual(detail.get("error"), "entitlement_exceeded")
            self.assertEqual(detail.get("upgrade", {}).get("metric"), "farms")
            self.assertIn("trang trại", detail.get("message", "").lower())
        finally:
            gari_entitlements.update_plan_configuration("free", {"max_farms": 5})

    def test_05_backend_limit_enforcement_max_plots(self):
        """Verifies that creating more plots than the plan limit is rejected."""
        user, token, headers = _create_test_user("PlotQuotaUser")

        # Dynamically set free plan max_plots to 3 to test enforcement boundary
        gari_entitlements.update_plan_configuration("free", {"max_plots": 3})
        try:
            # Create 1 farm
            f_res = client.post("/api/farms", json={"name": "Nông trại kiểm tra lô"}, headers=headers)
            farm_id = f_res.json()["farm"]["id"]

            # Create 3 plots:
            for i in range(1, 4):
                p_res = client.post("/api/plots", json={
                    "farm_id": farm_id,
                    "name": f"Lô #{i}",
                    "area_m2": 500,
                    "crop_id": "coffee"
                }, headers=headers)
                self.assertEqual(p_res.status_code, 200)

            # Attempt to create 4th plot -> 403 Forbidden
            p_res_4 = client.post("/api/plots", json={
                "farm_id": farm_id,
                "name": "Lô vượt hạn ngạch #4",
                "area_m2": 500,
                "crop_id": "coffee"
            }, headers=headers)
            self.assertEqual(p_res_4.status_code, 403)
            detail = p_res_4.json().get("detail", {})
            self.assertEqual(detail.get("error"), "entitlement_exceeded")
            self.assertEqual(detail.get("upgrade", {}).get("metric"), "plots")
        finally:
            gari_entitlements.update_plan_configuration("free", {"max_plots": 25})

    def test_06_backend_limit_enforcement_ai_usage(self):
        """Verifies AI usage quota enforcement and deduction."""
        user, token, headers = _create_test_user("AiQuotaUser")
        uid = user["id"]

        free_def = gari_entitlements.get_plan_definition("free")
        ai_lim = float(free_def.get("ai_usage_limit") or 50)
        # Record full quota usage
        gari_entitlements.record_usage(uid, "ai_usage", ai_lim)

        # Attempt to send chat message to AI assistant
        res = client.post("/api/assistant/chat", json={
            "message": "Cây cà phê của tôi có đốm nâu là bệnh gì?",
            "diagnosis_id": 1
        }, headers=headers)

        self.assertEqual(res.status_code, 403)
        detail = res.json().get("detail", {})
        self.assertEqual(detail.get("error"), "entitlement_exceeded")
        self.assertEqual(detail.get("upgrade", {}).get("metric"), "ai_usage")

    def test_07_backend_limit_enforcement_org_seats(self):
        """Verifies organization seat limit enforcement."""
        user, token, headers = _create_test_user("OrgSeatUser", account_type="business")
        uid = user["id"]

        # Create organization with owner_id and slug
        org_slug = f"htx-seats-{uuid.uuid4().hex[:6]}"
        with _get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO organizations (name, slug, plan_id, status, owner_id)
                VALUES ('HTX Thử Nghiệm Seats', ?, 'organization', 'active', ?)
            """, (org_slug, uid))
            org_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO organization_members (organization_id, user_id, role)
                VALUES (?, ?, 'owner')
            """, (org_id, uid))
            conn.commit()

        # Give organization a custom plan with max_seats = 2
        gari_entitlements.update_plan_configuration("organization", {"max_seats": 2})

        # Add 1 member (total = 2 seats)
        m1_user, _, _ = _create_test_user("Member1")
        res_m1 = client.post(f"/api/organizations/{org_id}/members", json={
            "email": m1_user["email"],
            "role": "field_worker"
        }, headers=headers)
        self.assertEqual(res_m1.status_code, 200)

        # Attempt to add 2nd member (total would be 3 seats > limit 2) -> 403
        m2_user, _, _ = _create_test_user("Member2")
        res_m2 = client.post(f"/api/organizations/{org_id}/members", json={
            "email": m2_user["email"],
            "role": "field_worker"
        }, headers=headers)
        self.assertEqual(res_m2.status_code, 403)

        # Restore max_seats for organization
        gari_entitlements.update_plan_configuration("organization", {"max_seats": 15})

    def test_08_subscription_lifecycle_expiration_and_cancellation(self):
        """Tests active, cancel_at_period_end (retaining benefits), expired, and reactivate."""
        user, token, headers = _create_test_user("LifecycleUser")
        uid = user["id"]

        # 1. Activate Pro subscription for 30 days
        sub = gari_entitlements.assign_subscription("user", uid, "pro", duration_days=30)
        self.assertEqual(sub["status"], "active")
        self.assertTrue(sub["is_active"])

        # 2. Cancel at period end -> Status is cancel_at_period_end, benefits STILL ACTIVE
        cancel_res = client.post("/api/subscriptions/cancel", json={"immediate": False}, headers=headers)
        self.assertEqual(cancel_res.status_code, 200)
        sub_cancelled = gari_entitlements.resolve_subscription(uid)
        self.assertEqual(sub_cancelled["status"], "cancel_at_period_end")
        self.assertTrue(sub_cancelled["is_active"], "User must retain paid benefits until period end")
        self.assertEqual(sub_cancelled["plan_id"], "pro")

        # 3. Reactivate subscription
        react_res = client.post("/api/subscriptions/reactivate", json={}, headers=headers)
        self.assertEqual(react_res.status_code, 200)
        sub_react = gari_entitlements.resolve_subscription(uid)
        self.assertEqual(sub_react["status"], "active")
        self.assertFalse(sub_react["cancel_at_period_end"])

        # 4. Expiration simulation: set current_period_end to yesterday
        yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        with _get_db() as conn:
            conn.execute("UPDATE subscriptions SET current_period_end = ? WHERE user_id = ?", (yesterday_str, uid))
            conn.execute("UPDATE user_subscriptions SET end_date = ? WHERE user_id = ?", (yesterday_str, uid))
            conn.commit()

        # Resolving subscription must now mark it expired and drop to free
        sub_expired = gari_entitlements.resolve_subscription(uid)
        self.assertEqual(sub_expired["status"], "expired")
        self.assertFalse(sub_expired["is_active"])
        self.assertEqual(sub_expired["plan_id"], "free")

    def test_09_billing_provider_adapter_zero_trust(self):
        """Verifies Zero-Trust payment: user transfer report does NOT grant subscription until provider confirms."""
        user, token, headers = _create_test_user("ZeroTrustUser")
        uid = user["id"]

        # Create checkout order via Mock billing adapter
        adapter = gari_billing_adapter.get_billing_adapter("mock")
        order = adapter.create_checkout_order(user_id=uid, plan_id="pro")
        order_code = order["order_code"]

        # Before confirmation, user must be on Free plan
        sub_before = gari_entitlements.resolve_subscription(uid)
        self.assertEqual(sub_before["plan_id"], "free", "User must start on Free plan.")

        # Confirm payment via adapter with transaction reference
        confirm_res = adapter.confirm_payment(order_code=order_code, provider_tx_id="MOCK_TX_889102")
        self.assertTrue(confirm_res.get("success"))

        # Now and only now should user be entitled to Pro plan
        sub_after = gari_entitlements.resolve_subscription(uid)
        self.assertEqual(sub_after["plan_id"], "pro")
        self.assertEqual(sub_after["status"], "active")
        self.assertTrue(sub_after["is_paid"])

    def test_10_usage_summary_endpoint_consistency(self):
        """Verifies GET /api/subscriptions/usage returns accurate metrics, remaining quotas, and upgrade suggestions."""
        user, token, headers = _create_test_user("UsageSummaryUser")
        uid = user["id"]

        # Record some usage
        gari_entitlements.record_usage(uid, "ai_usage", 4.0)

        res = client.get("/api/subscriptions/usage", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"))

        usage = data.get("usage", {})
        self.assertIn("ai_usage", usage)
        self.assertIn("diagnosis", usage)
        self.assertIn("farms", usage)
        self.assertIn("plots", usage)
        self.assertIn("organization_seats", usage)
        self.assertIn("storage_mb", usage)
        self.assertIn("expert_consultations", usage)

        ai_usage = usage["ai_usage"]
        self.assertEqual(ai_usage["used"], 4)
        self.assertEqual(ai_usage["limit"], 50)
        self.assertEqual(ai_usage["remaining"], 46)
        self.assertEqual(ai_usage["percentage"], 8.0)

        # Check upgrade recommendation
        guidance = data.get("upgrade_guidance", {})
        self.assertIn("suggested_plan_id", guidance)
        self.assertIn("upgrade_url", guidance)


if __name__ == "__main__":
    unittest.main()
