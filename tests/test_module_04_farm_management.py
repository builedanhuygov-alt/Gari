"""
GARI AI LAB — Module 04: Farm Management Test Suite
File: tests/test_module_04_farm_management.py

Covers:
1. Farm CRUD and area normalization (ha, m2, sao, cong)
2. Farm idempotency and duplicate prevention
3. Farm archiving, cascading, and unarchiving
4. Zone management and parent-child integrity
5. Plot CRUD with zone validation and area units
6. Crop cycles & automatic crop rotation tracking
7. Individual plant / tree tracking and tag uniqueness
8. Observation timeline and diagnosis linking
9. Multi-tenant organization permissions and boundary isolation
10. Dual-mode support (Large-area fields vs Individual plant orchards)
"""

import os
import sys
import uuid
from typing import Any, Dict, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

os.environ["APP_ENV"] = "test"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from api_server import app
import gari_database
import gari_farm_management
import gari_b2b


def create_auth_headers(client: TestClient, name_prefix: str) -> Tuple[Dict[str, str], Dict[str, Any]]:
    suffix = uuid.uuid4().hex[:8]
    email = f"{name_prefix}_{suffix}@test.gari.vn"
    reg = client.post("/api/auth/register", json={
        "full_name": f"{name_prefix} {suffix}",
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "account_type": "farmer"
    })
    data = reg.json()
    token = data["token"]
    user = data["user"]
    return {"Authorization": f"Bearer {token}"}, user


# ============================================================================
# 1. FARM CRUD & AREA NORMALIZATION
# ============================================================================
def test_01_farm_crud_and_area_normalization():
    """Verify farm creation with various units, accurate m2/ha normalization, and summary metrics."""
    with TestClient(app) as client:
        headers, user = create_auth_headers(client, "farm_crud_user")

        # 1. Create farm with 'cong' (1 công Nam Bộ = 1,000 m2 = 0.1 ha)
        res1 = client.post("/api/farms", headers=headers, json={
            "name": "Nông trại Miền Tây",
            "province": "Tiền Giang",
            "area": 25.0,
            "area_unit": "cong",
            "primary_crop": "Sầu riêng"
        })
        assert res1.status_code == 200, res1.text
        farm1 = res1.json()["farm"]
        assert farm1["name"] == "Nông trại Miền Tây"
        assert farm1["area_m2"] == 25000.0
        assert farm1["area_hectare"] == 2.5
        assert "summary" in farm1
        assert farm1["summary"]["total_plots"] == 0

        # 2. Create farm with 'sao_bac_bo' (1 sào Bắc Bộ = 360 m2)
        res2 = client.post("/api/farms", headers=headers, json={
            "name": "Vườn Rau Đông Anh",
            "province": "Hà Nội",
            "area": 10.0,
            "area_unit": "sao_bac_bo",
            "primary_crop": "Cà chua"
        })
        assert res2.status_code == 200
        farm2 = res2.json()["farm"]
        assert farm2["area_m2"] == 3600.0
        assert farm2["area_hectare"] == 0.36

        # 3. Retrieve farm detail
        get_res = client.get(f"/api/farms/{farm1['id']}", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["farm"]["id"] == farm1["id"]

        # 4. Update farm
        up_res = client.put(f"/api/farms/{farm1['id']}", headers=headers, json={
            "primary_crop": "Sầu riêng Monthong",
            "notes": "Đã lắp đặt hệ thống tưới tự động"
        })
        assert up_res.status_code == 200
        assert up_res.json()["farm"]["primary_crop"] == "Sầu riêng Monthong"


# ============================================================================
# 2. FARM IDEMPOTENCY & DUPLICATE PREVENTION
# ============================================================================
def test_02_farm_idempotency_and_duplicate_prevention():
    """Verify rapid repeated submissions of the same farm name return existing record without duplicating."""
    with TestClient(app) as client:
        headers, user = create_auth_headers(client, "idempotent_user")

        payload = {
            "name": "Trang trại Trùng Tên Chống Duplicate",
            "province": "Lâm Đồng",
            "area": 5.0,
            "area_unit": "ha"
        }

        # Submission 1
        res1 = client.post("/api/farms", headers=headers, json=payload)
        assert res1.status_code == 200
        id1 = res1.json()["farm"]["id"]

        # Submission 2 (Immediate identical re-post)
        res2 = client.post("/api/farms", headers=headers, json=payload)
        assert res2.status_code == 200
        id2 = res2.json()["farm"]["id"]

        assert id1 == id2, "Duplicate submission must return existing farm record ID"

        # Check total count
        list_res = client.get("/api/farms", headers=headers)
        matching = [f for f in list_res.json()["farms"] if f["name"] == payload["name"]]
        assert len(matching) == 1


# ============================================================================
# 3. FARM ARCHIVE, CASCADING & UNARCHIVE
# ============================================================================
def test_03_farm_archive_and_unarchive_cascade():
    """Verify archiving hides farm from active lists, cascades to child plots, and unarchiving restores it."""
    with TestClient(app) as client:
        headers, user = create_auth_headers(client, "archive_user")

        farm_res = client.post("/api/farms", headers=headers, json={"name": "Nông trại Cần Lưu Trữ", "province": "Sơn La"})
        farm_id = farm_res.json()["farm"]["id"]

        # Add a plot
        plot_res = client.post("/api/plots", headers=headers, json={
            "farm_id": farm_id,
            "plot_name": "Lô 1 Lưu Trữ",
            "crop_id": "Tomato",
            "crop_name": "Cà chua"
        })
        plot_id = plot_res.json()["plot"]["id"]

        # 1. Archive farm
        arc_res = client.post(f"/api/farms/{farm_id}/archive", headers=headers)
        assert arc_res.status_code == 200

        # 2. Active list should NOT include this farm
        active_list = client.get("/api/farms?status=active", headers=headers).json()["farms"]
        assert not any(f["id"] == farm_id for f in active_list)

        # 3. All list SHOULD include this farm
        all_list = client.get("/api/farms?status=all", headers=headers).json()["farms"]
        assert any(f["id"] == farm_id and f["status"] == "archived" for f in all_list)

        # 4. Child plot should also be archived
        plot_detail = client.get(f"/api/plots/{plot_id}", headers=headers).json()["plot"]
        assert plot_detail["status"] == "archived"

        # 5. Unarchive farm
        unarc_res = client.post(f"/api/farms/{farm_id}/unarchive", headers=headers)
        assert unarc_res.status_code == 200

        # 6. Active list now includes it again
        active_list_after = client.get("/api/farms?status=active", headers=headers).json()["farms"]
        assert any(f["id"] == farm_id for f in active_list_after)


# ============================================================================
# 4. ZONE MANAGEMENT & PARENT-CHILD INTEGRITY
# ============================================================================
def test_04_zone_management_and_parent_child_integrity():
    """Verify zone creation within farm, retrieval, and access verification."""
    with TestClient(app) as client:
        headers, user = create_auth_headers(client, "zone_user")

        farm = client.post("/api/farms", headers=headers, json={"name": "Nông trại Công nghệ cao", "province": "Đà Lạt"}).json()["farm"]
        farm_id = farm["id"]

        # 1. Create Zone A
        zone_res = client.post(f"/api/farms/{farm_id}/zones", headers=headers, json={
            "name": "Khu A - Nhà màng số 1",
            "code": "ZONE-A1",
            "zone_type": "greenhouse",
            "area": 2000.0,
            "area_unit": "m2",
            "description": "Nhà màng Israel trồng cà chua cherry"
        })
        assert zone_res.status_code == 200
        zone = zone_res.json()["zone"]
        assert zone["zone_type"] == "greenhouse"
        assert zone["area_m2"] == 2000.0
        assert zone["area_hectare"] == 0.2

        # 2. List zones in farm
        list_zones = client.get(f"/api/farms/{farm_id}/zones", headers=headers).json()["zones"]
        assert len(list_zones) == 1
        assert list_zones[0]["code"] == "ZONE-A1"

        # 3. Other user cannot manage zones of this farm -> 403 Forbidden
        headers_other, _ = create_auth_headers(client, "other_zone_user")
        blocked = client.post(f"/api/farms/{farm_id}/zones", headers=headers_other, json={"name": "Khu Bất hợp pháp"})
        assert blocked.status_code == 403


# ============================================================================
# 5. PLOT CRUD WITH ZONE VALIDATION & AREA UNITS
# ============================================================================
def test_05_plot_crud_with_zone_validation_and_area_units():
    """Verify plot creation enforces that zone_id belongs to the same farm (parent-child integrity)."""
    with TestClient(app) as client:
        headers, user = create_auth_headers(client, "plot_integrity_user")

        farm1 = client.post("/api/farms", headers=headers, json={"name": "Trang trại 1", "province": "Đắk Lắk"}).json()["farm"]
        farm2 = client.post("/api/farms", headers=headers, json={"name": "Trang trại 2", "province": "Gia Lai"}).json()["farm"]

        # Create zone in Farm 2
        zone_farm2 = client.post(f"/api/farms/{farm2['id']}/zones", headers=headers, json={"name": "Khu Vực Farm 2"}).json()["zone"]

        # Invalid Parent-Child: Trying to create a plot in Farm 1 but specifying zone from Farm 2
        invalid_plot = client.post("/api/plots", headers=headers, json={
            "farm_id": farm1["id"],
            "zone_id": zone_farm2["id"],  # Belongs to Farm 2!
            "plot_name": "Lô Sai Khu Vực",
            "crop_id": "Coffee",
            "crop_name": "Cà phê"
        })
        assert invalid_plot.status_code == 400, "Must reject plot when zone_id does not belong to farm_id"
        assert "không thuộc nông trại" in invalid_plot.text

        # Valid Plot Creation in Farm 2 with zone_farm2
        valid_plot = client.post("/api/plots", headers=headers, json={
            "farm_id": farm2["id"],
            "zone_id": zone_farm2["id"],
            "plot_name": "Thửa Cà Phê Voi",
            "crop_id": "Coffee",
            "crop_name": "Cà phê Robusta",
            "area": 2.0,
            "area_unit": "ha"
        })
        assert valid_plot.status_code == 200
        p_data = valid_plot.json()["plot"]
        assert p_data["zone_id"] == zone_farm2["id"]
        assert p_data["zone_name"] == "Khu Vực Farm 2"
        assert p_data["area_hectare"] == 2.0
        assert p_data["area_m2"] == 20000.0


# ============================================================================
# 6. CROP CYCLES & CROP ROTATION TRACKING
# ============================================================================
def test_06_crop_cycle_and_crop_rotation_tracking():
    """Verify successive seasonal crop cycles and automated crop rotation tracking."""
    with TestClient(app) as client:
        headers, user = create_auth_headers(client, "rotation_user")

        farm = client.post("/api/farms", headers=headers, json={"name": "Cánh đồng Đồng Bằng", "province": "An Giang"}).json()["farm"]
        plot = client.post("/api/plots", headers=headers, json={
            "farm_id": farm["id"],
            "plot_name": "Thửa 01 - Cánh đồng mẫu lớn",
            "crop_id": "Rice",
            "crop_name": "Lúa nước",
            "cycle_name": "Vụ Đông Xuân 2025"
        }).json()["plot"]
        plot_id = plot["id"]

        # Verify initial cycle
        cycles1 = client.get(f"/api/plots/{plot_id}/cycles", headers=headers).json()["cycles"]
        assert len(cycles1) == 1
        assert cycles1[0]["crop_name"] == "Lúa nước"
        assert cycles1[0]["status"] == "active"

        # 2. Add second crop cycle: Crop Rotation to Peanut (Đậu phộng)
        rot_res = client.post(f"/api/plots/{plot_id}/cycles", headers=headers, json={
            "cycle_name": "Vụ Hè Thu 2026 - Luân canh Đậu phộng",
            "crop_id": "Peanut",
            "crop_name": "Đậu phộng",
            "variety": "L14",
            "start_date": "2026-05-15",
            "target_yield_kg": 3500.0,
            "status": "active"
        })
        assert rot_res.status_code == 200
        new_cycle = rot_res.json()["cycle"]
        assert new_cycle["crop_name"] == "Đậu phộng"

        # 3. Verify plot details reflect crop rotation
        plot_after = client.get(f"/api/plots/{plot_id}", headers=headers).json()["plot"]
        assert plot_after["crop_name"] == "Đậu phộng", "Plot current crop should be rotated to Đậu phộng"
        assert plot_after["active_cycle_id"] == new_cycle["id"]

        # 4. Verify previous cycle marked as completed
        cycles_all = client.get(f"/api/plots/{plot_id}/cycles", headers=headers).json()["cycles"]
        assert len(cycles_all) == 2
        old_c = [c for c in cycles_all if c["id"] != new_cycle["id"]][0]
        assert old_c["status"] == "completed"

        # 5. Verify timeline recorded rotation event
        timeline = client.get(f"/api/plots/{plot_id}/timeline", headers=headers).json()["events"]
        assert any(e.get("event_type") == "crop_rotation" for e in timeline)


# ============================================================================
# 7. INDIVIDUAL PLANT / TREE TRACKING & TAG UNIQUENESS
# ============================================================================
def test_07_individual_plant_tracking_and_tag_uniqueness():
    """Verify individual plant registration, plant_tag uniqueness within plot, and health tracking."""
    with TestClient(app) as client:
        headers, user = create_auth_headers(client, "durian_tree_user")

        farm = client.post("/api/farms", headers=headers, json={"name": "Vườn Sầu Riêng Đắk Lắk", "province": "Đắk Lắk"}).json()["farm"]
        plot = client.post("/api/plots", headers=headers, json={
            "farm_id": farm["id"],
            "plot_name": "Vườn Đồi Sầu Riêng",
            "crop_id": "Durian",
            "crop_name": "Sầu riêng"
        }).json()["plot"]
        plot_id = plot["id"]

        # 1. Register Tree #1
        plant1_res = client.post(f"/api/plots/{plot_id}/plants", headers=headers, json={
            "plant_tag": "SR-01-A01",
            "plant_name": "Cây Sầu Riêng Monthong Gốc #01",
            "species": "durian",
            "variety": "Monthong",
            "row_index": 1,
            "col_index": 1,
            "health_status": "healthy"
        })
        assert plant1_res.status_code == 200
        p1 = plant1_res.json()["plant"]
        assert p1["plant_tag"] == "SR-01-A01"
        assert p1["health_status"] == "healthy"

        # 2. Duplicate Tag in same plot returns existing or prevents duplication
        plant1_dup = client.post(f"/api/plots/{plot_id}/plants", headers=headers, json={
            "plant_tag": "SR-01-A01",
            "plant_name": "Duplicate Tree"
        })
        assert plant1_dup.status_code == 200
        assert plant1_dup.json()["plant"]["id"] == p1["id"]

        # 3. Batch register 2 more trees
        batch_res = client.post(f"/api/plots/{plot_id}/plants/batch", headers=headers, json={
            "plants": [
                {"plant_tag": "SR-01-A02", "plant_name": "Cây Sầu Riêng Gốc #02", "health_status": "healthy"},
                {"plant_tag": "SR-01-A03", "plant_name": "Cây Sầu Riêng Gốc #03", "health_status": "monitoring"}
            ]
        })
        assert batch_res.status_code == 200
        assert batch_res.json()["count"] == 2

        # 4. List plants in plot
        plants_list = client.get(f"/api/plots/{plot_id}/plants", headers=headers).json()["plants"]
        assert len(plants_list) == 3

        # 5. Update health status of Tree #1 to 'diseased'
        up_plant = client.put(f"/api/plants/{p1['id']}", headers=headers, json={
            "health_status": "diseased",
            "notes": "Phát hiện nứt thân xì mủ Phytophthora"
        })
        assert up_plant.status_code == 200
        assert up_plant.json()["plant"]["health_status"] == "diseased"

        # 6. Verify plot summary reflects updated health count
        plot_summary = client.get(f"/api/plots/{plot_id}/summary", headers=headers).json()
        assert plot_summary["plants_summary"]["total"] == 3
        assert plot_summary["plants_summary"]["diseased"] == 1


# ============================================================================
# 8. OBSERVATION TIMELINE & DIAGNOSIS LINKING
# ============================================================================
def test_08_observation_timeline_and_diagnosis_linking():
    """Verify custom activity logging and linking an existing diagnosis to plot and plant."""
    with TestClient(app) as client:
        headers, user = create_auth_headers(client, "activity_user")

        farm = client.post("/api/farms", headers=headers, json={"name": "Nông trại Ba Vì", "province": "Hà Nội"}).json()["farm"]
        plot = client.post("/api/plots", headers=headers, json={"farm_id": farm["id"], "plot_name": "Luống Cà Chua 1"}).json()["plot"]
        plant = client.post(f"/api/plots/{plot['id']}/plants", headers=headers, json={"plant_tag": "TM-01", "plant_name": "Cây cà chua mẫu 01"}).json()["plant"]

        # 1. Record custom activity
        act_res = client.post(f"/api/plots/{plot['id']}/activities", headers=headers, json={
            "event_type": "pruning",
            "plant_id": plant["id"],
            "notes": "Đã cắt tỉa toàn bộ lá gốc già và lá có đốm vàng nghi ngờ",
            "action_taken": "Tỉa cành vệ sinh"
        })
        assert act_res.status_code == 200
        assert act_res.json()["event"]["event_type"] == "pruning"

        # 2. Save a diagnosis directly
        diag = gari_database.save_diagnosis({
            "crop_id": "tomato",
            "crop_name": "Cà chua",
            "predicted_disease": "Tomato Bacterial spot",
            "disease_name_vi": "Đốm vi khuẩn",
            "confidence": 0.94
        }, user_id=user["id"])

        # 3. Link diagnosis to farm, plot, and plant
        link_res = client.post(f"/api/diagnoses/{diag['id']}/link", headers=headers, json={
            "farm_id": farm["id"],
            "plot_id": plot["id"],
            "plant_id": plant["id"]
        })
        assert link_res.status_code == 200
        assert link_res.json()["success"] is True

        # 4. Check timeline contains the linked diagnosis
        timeline = client.get(f"/api/plots/{plot['id']}/timeline", headers=headers).json()["events"]
        assert any(e.get("diagnosis_id") == diag["id"] or e.get("event_type") == "diagnosis_linked" for e in timeline)

        # 5. Check plant detail contains the linked diagnosis
        plant_detail = client.get(f"/api/plants/{plant['id']}", headers=headers).json()["plant"]
        assert any(d["id"] == diag["id"] for d in plant_detail["diagnoses"])


# ============================================================================
# 9. MULTI-TENANT ORGANIZATION PERMISSIONS & ISOLATION
# ============================================================================
def test_09_multi_tenant_organization_permissions_and_isolation():
    """Verify organization-scoped farm ownership, member visibility, and cross-org access block."""
    with TestClient(app) as client:
        # Org 1 Owner
        headers_org1, user_org1 = create_auth_headers(client, "org1_owner")
        org1 = gari_b2b.create_organization(name="HTX Nông Nghiệp Thống Nhất", owner_id=user_org1["id"])

        # Org 2 Owner
        headers_org2, user_org2 = create_auth_headers(client, "org2_owner")
        org2 = gari_b2b.create_organization(name="HTX Rau Sạch Vĩnh Long", owner_id=user_org2["id"])

        # Create farm belonging to Org 1
        farm_org1 = client.post("/api/farms", headers=headers_org1, json={
            "name": "Nông trại Tập thể HTX Thống Nhất",
            "organization_id": org1["id"],
            "province": "Bình Thuận"
        }).json()["farm"]

        # Org 1 Owner can view
        view1 = client.get(f"/api/farms/{farm_org1['id']}", headers=headers_org1)
        assert view1.status_code == 200

        # Org 2 Owner CANNOT view Org 1's farm -> 404 (Not Found / Access Denied)
        view2 = client.get(f"/api/farms/{farm_org1['id']}", headers=headers_org2)
        assert view2.status_code == 404

        # Org 2 Owner CANNOT delete Org 1's farm -> 404
        del2 = client.delete(f"/api/farms/{farm_org1['id']}", headers=headers_org2)
        assert del2.status_code == 404


# ============================================================================
# 10. DUAL-MODE SUPPORT: LARGE-AREA FIELDS VS INDIVIDUAL PLANT ORCHARDS
# ============================================================================
def test_10_large_area_vs_individual_plant_dual_mode_support():
    """Verify the data model flexibly supports both plot-based farming and individual tree tracking."""
    with TestClient(app) as client:
        headers, user = create_auth_headers(client, "dual_mode_user")

        farm = client.post("/api/farms", headers=headers, json={"name": "Nông trường Đa Dạng", "province": "Tiền Giang"}).json()["farm"]

        # 1. Mode A: Large-area rice field (managed purely by plot area & cycles, 0 individual plants)
        rice_plot = client.post("/api/plots", headers=headers, json={
            "farm_id": farm["id"],
            "plot_name": "Cánh đồng Lúa ST25 (5 Hecta)",
            "crop_id": "Rice",
            "crop_name": "Lúa ST25",
            "area": 5.0,
            "area_unit": "ha"
        }).json()["plot"]

        rice_summary = client.get(f"/api/plots/{rice_plot['id']}/summary", headers=headers).json()
        assert rice_summary["plants_summary"]["total"] == 0, "Large-area field functions with 0 individual plants"
        assert rice_summary["active_cycle"] is not None

        # 2. Mode B: High-density Durian orchard (managed with individual plants)
        durian_plot = client.post("/api/plots", headers=headers, json={
            "farm_id": farm["id"],
            "plot_name": "Vườn Sầu Riêng Xuất Khẩu (1 Hecta)",
            "crop_id": "Durian",
            "crop_name": "Sầu riêng Monthong",
            "area": 1.0,
            "area_unit": "ha"
        }).json()["plot"]

        # Register individual trees
        client.post(f"/api/plots/{durian_plot['id']}/plants/batch", headers=headers, json={
            "plants": [
                {"plant_tag": f"SR-A{i:02d}", "plant_name": f"Gốc sầu riêng #{i}", "health_status": "healthy"}
                for i in range(1, 11)
            ]
        })

        durian_summary = client.get(f"/api/plots/{durian_plot['id']}/summary", headers=headers).json()
        assert durian_summary["plants_summary"]["total"] == 10, "Individual plant orchard tracks all tagged trees"

        # 3. Both coexist under same farm summary
        farm_summary = client.get(f"/api/farms/{farm['id']}/summary", headers=headers).json()
        assert farm_summary["summary"]["total_plots"] == 2
        assert farm_summary["summary"]["total_plants"] == 10


if __name__ == "__main__":
    tests = [
        test_01_farm_crud_and_area_normalization,
        test_02_farm_idempotency_and_duplicate_prevention,
        test_03_farm_archive_and_unarchive_cascade,
        test_04_zone_management_and_parent_child_integrity,
        test_05_plot_crud_with_zone_validation_and_area_units,
        test_06_crop_cycle_and_crop_rotation_tracking,
        test_07_individual_plant_tracking_and_tag_uniqueness,
        test_08_observation_timeline_and_diagnosis_linking,
        test_09_multi_tenant_organization_permissions_and_isolation,
        test_10_large_area_vs_individual_plant_dual_mode_support
    ]

    print("=" * 70)
    print("STARTING GARI MODULE 04 — FARM MANAGEMENT TEST SUITE")
    print("=" * 70)

    passed = 0
    for t in tests:
        name = t.__name__
        print(f"\n[RUNNING] {name}...")
        try:
            t()
            print(f"[PASS] {name} ✓")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed}/{len(tests)} TESTS PASSED ({passed*100//len(tests)}%)")
    print("=" * 70)

    if passed == len(tests):
        print("\nALL 10 MODULE 04 FARM MANAGEMENT TESTS PASSED 100%!")
        sys.exit(0)
    else:
        sys.exit(1)
