# -*- coding: utf-8 -*-
"""
Automated Test Suite for GARI Predict Module Overhaul:
1. Firebase Client Config & Status Endpoints
2. 5-layer User Profile model
3. Free Tier Organization Creation Block (403 Forbidden)
4. Pro Mode AI Diagnosis Gating (Free user rejected with 403; Dev headers rejected with 403)
5. Admin & Pro Organization Creation (200 OK)
6. Pro Tier AI Diagnosis Allowed (200/422 OK)
"""

import sys
import io
import os
import requests
import json
import time
from PIL import Image

sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8000"

def make_leaf_img(color):
    img = Image.new('RGB', (300, 300), color=color)
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    return buf.getvalue()

def run_tests():
    print("=" * 60)
    print("TEST 1: Firebase Client Config & Status Endpoints")
    print("=" * 60)
    r = requests.get(f"{BASE_URL}/api/auth/firebase-config")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    cfg = r.json()
    assert cfg.get("success") is True
    print(f"PASS: /api/auth/firebase-config -> configured={cfg.get('configured')}")

    r = requests.get(f"{BASE_URL}/api/auth/firebase-status")
    assert r.status_code == 200
    st = r.json()
    assert st.get("success") is True
    print(f"PASS: /api/auth/firebase-status -> admin_initialized={st.get('admin_initialized')}, client_configured={st.get('client_configured')}")

    print("\n" + "=" * 60)
    print("TEST 2: Register Free Tier Test User & Verify 5-Layer Profile")
    print("=" * 60)
    uid_suffix = int(time.time())
    free_email = f"farmer_free_{uid_suffix}@gari.vn"
    reg_payload = {
        "full_name": f"Nong Dan Free {uid_suffix}",
        "email": free_email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "phone": "0912345678",
        "province": "Lâm Đồng",
        "account_type": "Nông hộ cá thể"
    }
    r = requests.post(f"{BASE_URL}/api/auth/register", json=reg_payload)
    assert r.status_code == 200, f"Registration failed: {r.text}"
    reg_data = r.json()
    free_token = reg_data["token"]
    free_headers = {"Authorization": f"Bearer {free_token}"}
    print(f"PASS: Registered free user {free_email}")

    # Check 5-Layer User Profile
    r = requests.get(f"{BASE_URL}/api/user/profile", headers=free_headers)
    assert r.status_code == 200
    prof = r.json()
    assert prof.get("success") is True
    assert "identity" in prof
    assert "profile" in prof
    assert "subscription" in prof
    assert "organizations" in prof
    assert "system_role" in prof

    sub = prof["subscription"]
    assert sub["plan"] == "free", f"Expected free plan, got {sub['plan']}"
    assert sub["is_vip"] is False
    assert sub["can_create_organization"] is False, "Free user must NOT have can_create_organization=True"
    print("PASS: /api/user/profile successfully returned separated 5-layer model with can_create_organization=False")

    print("\n" + "=" * 60)
    print("TEST 3: Organization Creation Gating (Free User -> 403 Forbidden)")
    print("=" * 60)
    org_payload = {
        "name": "HTX Nông Nghiệp Thử Nghiệm Free",
        "organization_type": "cooperative",
        "region": "Lâm Đồng",
        "primary_crops": ["Cà phê", "Tiêu"],
        "contact_email": free_email,
        "contact_phone": "0912345678"
    }
    r = requests.post(f"{BASE_URL}/api/organizations", json=org_payload, headers=free_headers)
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
    err_detail = r.json().get("detail", "")
    assert "Tạo Hợp tác xã hoặc Doanh nghiệp yêu cầu tài khoản nâng cấp gói Pro hoặc Doanh nghiệp" in err_detail
    print(f"PASS: Free user blocked from creating organization with 403: {err_detail}")

    print("\n" + "=" * 60)
    print("TEST 4: Pro Mode Inference Gating on Free Tier (Blocked -> 403 Forbidden)")
    print("=" * 60)
    # Free user attempts mode=auto_pro without Pro subscription
    files = {'file': ('leaf1.jpg', make_leaf_img((34, 139, 34)), 'image/jpeg')}
    data = {'crop': 'auto', 'mode': 'auto_pro'}
    r = requests.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=data, headers=free_headers)
    assert r.status_code == 403, f"Expected 403 for free user auto_pro, got {r.status_code}: {r.text}"
    print(f"PASS: Free user rejected with 403 when invoking auto_pro: {r.json().get('detail')}")

    # Free user attempts with fake dev header bypass (MUST STILL BE REJECTED 403!)
    files = {'file': ('leaf2.jpg', make_leaf_img((40, 145, 40)), 'image/jpeg')}
    bypass_headers = {**free_headers, 'X-Gari-Dev-Pro': 'true'}
    r = requests.post(f"{BASE_URL}/api/plant/diagnose?dev_pro=true", files=files, data=data, headers=bypass_headers)
    assert r.status_code == 403, f"Expected 403 even with dev header/query, got {r.status_code}: {r.text}"
    print("PASS: Fake X-Gari-Dev-Pro header and ?dev_pro=1 rejected with 403 (Zero Bypass)")

    # Free user uses standard auto_standard mode (Allowed)
    files = {'file': ('leaf3.jpg', make_leaf_img((45, 150, 45)), 'image/jpeg')}
    data = {'crop': 'auto', 'mode': 'auto_standard'}
    r = requests.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=data, headers=free_headers)
    assert r.status_code in (200, 422), f"Expected 200 or 422 for standard inference, got {r.status_code}: {r.text}"
    print(f"PASS: Free user permitted for auto_standard mode (Status={r.status_code})")

    print("\n" + "=" * 60)
    print("TEST 5: Admin & Upgraded Pro Organization Creation (Allowed -> 200 OK)")
    print("=" * 60)
    import gari_auth, gari_plans
    # Admin creates organization
    admin_token = gari_auth.create_session(user_id=1)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    admin_org_payload = {
        "name": f"HTX Nông Nghiệp Hữu Cơ {uid_suffix}",
        "organization_type": "cooperative",
        "region": "Đắk Lắk",
        "primary_crops": ["Cà phê", "Hồ tiêu"],
        "contact_email": "admin@gari.vn",
        "contact_phone": "0988668866"
    }
    r = requests.post(f"{BASE_URL}/api/organizations", json=admin_org_payload, headers=admin_headers)
    assert r.status_code in (200, 201), f"Admin org creation failed: {r.status_code} {r.text}"
    org_res = r.json()
    created_org = org_res["organization"]
    print(f"PASS: Admin successfully created organization id={created_org['id']} name='{created_org['name']}'")

    # Upgrade user to Pro subscription
    free_user_id = prof["profile"]["id"]
    gari_plans.assign_user_plan(free_user_id, "pro", status="active")
    # Verify profile now reflects Pro status and can_create_organization=True
    r = requests.get(f"{BASE_URL}/api/user/profile", headers=free_headers)
    updated_prof = r.json()
    assert updated_prof["subscription"]["plan"] == "pro"
    assert updated_prof["subscription"]["can_create_organization"] is True
    assert updated_prof["subscription"]["is_vip"] is True
    print("PASS: Upgraded user to Pro: plan=pro, can_create_organization=True, is_vip=True")

    # Pro user creates organization
    pro_org_payload = {
        "name": f"HTX Cà Phê Chuyên Nghiệp {uid_suffix}",
        "organization_type": "cooperative",
        "region": "Lâm Đồng",
        "primary_crops": ["Cà phê", "Tiêu"],
        "contact_email": free_email,
        "contact_phone": "0912345678"
    }
    r = requests.post(f"{BASE_URL}/api/organizations", json=pro_org_payload, headers=free_headers)
    assert r.status_code in (200, 201), f"Pro org creation failed: {r.status_code} {r.text}"
    print(f"PASS: Pro user successfully created organization id={r.json()['organization']['id']}")

    print("\n" + "=" * 60)
    print("TEST 6: Pro Mode Inference by Upgraded Pro User (Allowed -> 200/422 OK)")
    print("=" * 60)
    files = {'file': ('leaf4.jpg', make_leaf_img((50, 160, 50)), 'image/jpeg')}
    data = {'crop': 'auto', 'mode': 'auto_pro'}
    r = requests.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=data, headers=free_headers)
    assert r.status_code in (200, 422), f"Expected 200 or 422 for pro user, got {r.status_code}: {r.text}"
    print(f"PASS: Pro user successfully authorized to invoke auto_pro mode (Status={r.status_code})")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY! (6/6 PASS)")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
