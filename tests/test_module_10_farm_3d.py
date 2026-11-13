"""
GARI Module 10 — 3D Farm Experience Test Suite
Verifies:
1. Valid 3D scene payload structure, terrain dimensions, camera presets, and summary counts.
2. Strict data integrity: verifies explicit labeling of illustrative terrain and simulated elements vs real records.
3. Truth-in-data: verifies rejection/absence of false sensor readings (sensor_telemetry is None).
4. Real farm, plot, and plant data binding: verifies plot dimensions, crop types, plant counts, and cycle names match DB.
5. Deterministic health visualization: plots with severe disease or overdue task have health_status == 'attention_needed' and has_alert_marker == True.
6. Deterministic health visualization: clean plots are 'healthy' and unmonitored plots are 'unknown'.
7. Instanced mesh batching data: verifies plant instances coordinates generation for high-performance rendering.
8. Multi-tenant isolation: unauthorized users receive HTTP 403 Forbidden on 3D scene endpoint.
9. Empty farm graceful handling: farm with 0 plots returns valid empty scene without errors.
10. Single plot 3D inspection endpoint: verifies /api/plots/{plot_id}/scene-3d returns plot and plant registry.
"""

import unittest
import sys
import os
import json
import uuid
from datetime import datetime, timedelta

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi.testclient import TestClient
from api_server import app
from gari_database import get_connection
import gari_farm_3d

client = TestClient(app)


def _create_user(name_prefix="Farmer3D"):
    unique_id = uuid.uuid4().hex[:8]
    email = f"{name_prefix.lower()}_{unique_id}@example.com"
    pwd = "Password123!"
    resp = client.post("/api/auth/register", json={
        "email": email,
        "password": pwd,
        "confirm_password": pwd,
        "full_name": f"{name_prefix} {unique_id}",
        "account_type": "farmer"
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    user = data.get("user", {})
    return user, token, {"Authorization": f"Bearer {token}"}


class TestModule10Farm3D(unittest.TestCase):

    def setUp(self):
        self.user, self.token, self.headers = _create_user("UserMain3D")
        self.stranger, self.stranger_token, self.stranger_headers = _create_user("UserStranger3D")

        # Create a test farm
        resp = client.post("/api/farms", json={
            "name": "Nông trại Thử nghiệm 3D Đắk Lắk",
            "province": "Đắk Lắk",
            "location": "Xã Ea Ktur, Huyện Cư Kuin",
            "area_hectare": 5.0,
            "primary_crop": "Cà phê",
            "code": "FAR-3D-01"
        }, headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        self.farm_id = resp.json()["farm"]["id"]

    def test_01_scene_3d_payload_structure(self):
        """Verifies valid 3D scene payload structure, terrain dimensions, camera presets, and summary counts."""
        # Create a plot
        resp_p = client.post(f"/api/farms/{self.farm_id}/plots", json={
            "name": "Lô Robusta Cao sản 3D",
            "crop_name": "Cà phê",
            "area_hectare": 1.2
        }, headers=self.headers)
        self.assertEqual(resp_p.status_code, 200)

        resp = client.get(f"/api/farms/{self.farm_id}/scene-3d", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertTrue(data.get("success"))
        self.assertIn("scene_metadata", data)
        self.assertIn("farm", data)
        self.assertIn("terrain", data)
        self.assertIn("plots", data)
        self.assertIn("instanced_crops", data)
        self.assertIn("camera_preset", data)
        self.assertIn("summary", data)

        # Check camera presets
        cam = data["camera_preset"]
        self.assertIn("position", cam)
        self.assertIn("target", cam)
        self.assertGreater(cam["fov"], 30)

        # Check terrain
        terrain = data["terrain"]
        self.assertGreater(terrain["width"], 50.0)
        self.assertGreater(terrain["depth"], 50.0)

    def test_02_data_integrity_and_truthful_labeling(self):
        """Verifies strict labeling of illustrative terrain, plant models, and digital twin status."""
        resp = client.get(f"/api/farms/{self.farm_id}/scene-3d", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        meta = resp.json()["scene_metadata"]

        # Geometry source is user_drawn, so is_digital_twin MUST be False
        self.assertFalse(meta["is_digital_twin"])
        self.assertIn("Không phải bản sao số trắc địa GIS", meta["digital_twin_disclaimer"])
        self.assertEqual(meta["model_fidelity"], "schematic_instanced")

        # Must explicitly declare what is real vs what is simulated
        self.assertIn("real_data_elements", meta)
        self.assertIn("simulated_elements", meta)
        self.assertIn("plot_records", meta["real_data_elements"])
        self.assertIn("crop_canopy_geometry", meta["simulated_elements"])

    def test_03_no_false_sensor_or_weather_readings(self):
        """Verifies no false sensor telemetry or environmental readings are generated."""
        resp = client.get(f"/api/farms/{self.farm_id}/scene-3d", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        meta = resp.json()["scene_metadata"]

        self.assertIsNone(meta["sensor_telemetry"])
        self.assertIn("GARI cam kết", meta["sensor_telemetry_notice"])
        self.assertIn("cảm biến", meta["sensor_telemetry_notice"].lower())

    def test_04_real_farm_and_plot_data_binding(self):
        """Verifies plot dimensions, crop types, plant counts, and cycle names match DB."""
        # Create plot with cycle
        resp_p = client.post(f"/api/farms/{self.farm_id}/plots", json={
            "name": "Lô Hồ tiêu Vĩnh Linh 3D",
            "crop_name": "Hồ tiêu",
            "area_hectare": 0.8
        }, headers=self.headers)
        self.assertEqual(resp_p.status_code, 200)
        plot_id = resp_p.json()["plot"]["id"]

        # Add active crop cycle
        resp_c = client.post(f"/api/plots/{plot_id}/cycles", json={
            "cycle_name": "Vụ Tiêu Kinh doanh 2026",
            "crop_name": "Hồ tiêu",
            "start_date": "2026-01-15",
            "status": "active"
        }, headers=self.headers)
        self.assertEqual(resp_c.status_code, 200)

        # Retrieve 3D scene
        resp = client.get(f"/api/farms/{self.farm_id}/scene-3d", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        plots = resp.json()["plots"]

        matching = [p for p in plots if p["plot_id"] == plot_id]
        self.assertEqual(len(matching), 1)
        plot_3d = matching[0]

        self.assertEqual(plot_3d["name"], "Lô Hồ tiêu Vĩnh Linh 3D")
        self.assertEqual(plot_3d["crop_name"], "Hồ tiêu")
        self.assertEqual(plot_3d["active_cycle_name"], "Vụ Tiêu Kinh doanh 2026")
        self.assertIn("position", plot_3d)
        self.assertIn("dimensions", plot_3d)
        self.assertGreater(plot_3d["dimensions"]["width"], 0)

    def test_05_deterministic_health_visualization_attention_marker(self):
        """Plots with severe disease or overdue task have health_status == 'attention_needed' and has_alert_marker == True."""
        resp_p = client.post(f"/api/farms/{self.farm_id}/plots", json={
            "name": "Lô Tiêu Bị Bệnh 3D",
            "crop_name": "Hồ tiêu",
            "area_hectare": 0.5
        }, headers=self.headers)
        self.assertEqual(resp_p.status_code, 200)
        plot_id = resp_p.json()["plot"]["id"]

        # Insert severe diagnosis in last 30 days
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO diagnoses (
                    user_id, crop_id, crop_name, plot_id, farm_id, predicted_disease, confidence,
                    severity, diagnosis_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                self.user["id"], "pepper", "Hồ tiêu", plot_id, self.farm_id,
                "Bệnh chết nhanh (Phytophthora)", 0.92,
                "CRITICAL", "diagnosed"
            ))
            conn.commit()

        resp = client.get(f"/api/farms/{self.farm_id}/scene-3d", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        plots = resp.json()["plots"]

        target = [p for p in plots if p["plot_id"] == plot_id][0]
        self.assertEqual(target["health_status"], "attention_needed")
        self.assertTrue(target["has_alert_marker"])
        self.assertEqual(target["boundary_color"], "#f97316")

    def test_06_deterministic_health_visualization_healthy_and_unknown(self):
        """Clean plot is marked healthy; plot with no history is marked unknown."""
        # Plot A: clean
        resp_a = client.post(f"/api/farms/{self.farm_id}/plots", json={
            "name": "Lô Khỏe mạnh 3D",
            "crop_name": "Cà phê",
            "area_hectare": 0.5
        }, headers=self.headers)
        plot_a_id = resp_a.json()["plot"]["id"]

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO diagnoses (
                    user_id, crop_id, crop_name, plot_id, farm_id, predicted_disease, confidence,
                    severity, diagnosis_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                self.user["id"], "coffee", "Cà phê", plot_a_id, self.farm_id,
                "Cây cà phê khỏe mạnh (Healthy)", 0.95,
                "LOW", "diagnosed"
            ))
            conn.commit()

        # Plot B: no diagnosis
        resp_b = client.post(f"/api/farms/{self.farm_id}/plots", json={
            "name": "Lô Chưa khảo sát 3D",
            "crop_name": "Cà phê",
            "area_hectare": 0.5
        }, headers=self.headers)
        plot_b_id = resp_b.json()["plot"]["id"]

        resp = client.get(f"/api/farms/{self.farm_id}/scene-3d", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        plots = {p["plot_id"]: p for p in resp.json()["plots"]}

        self.assertEqual(plots[plot_a_id]["health_status"], "healthy")
        self.assertFalse(plots[plot_a_id]["has_alert_marker"])
        self.assertEqual(plots[plot_a_id]["boundary_color"], "#22c55e")

        self.assertEqual(plots[plot_b_id]["health_status"], "unknown")
        self.assertFalse(plots[plot_b_id]["has_alert_marker"])
        self.assertEqual(plots[plot_b_id]["boundary_color"], "#94a3b8")

    def test_07_instanced_mesh_matrices_batching(self):
        """Verifies plant instances coordinates generation for high-performance rendering."""
        resp_p = client.post(f"/api/farms/{self.farm_id}/plots", json={
            "name": "Lô Cà phê Catimor 3D",
            "crop_name": "Cà phê",
            "area_hectare": 1.0
        }, headers=self.headers)
        plot_id = resp_p.json()["plot"]["id"]

        resp = client.get(f"/api/farms/{self.farm_id}/scene-3d", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        crops = resp.json()["instanced_crops"]

        # 'shrub_bush' is archetype for cà phê
        self.assertIn("shrub_bush", crops)
        shrub_instances = crops["shrub_bush"]
        self.assertGreater(len(shrub_instances), 0)

        first_inst = shrub_instances[0]
        self.assertIn("world_x", first_inst)
        self.assertIn("world_y", first_inst)
        self.assertIn("world_z", first_inst)
        self.assertIn("scale", first_inst)
        self.assertIn("rotation_y", first_inst)

    def test_08_multi_tenant_and_permission_isolation(self):
        """Unauthorized user cannot access another tenant's 3D farm scene (HTTP 403 Forbidden)."""
        # Stranger attempts to get farm 3D scene
        resp = client.get(f"/api/farms/{self.farm_id}/scene-3d", headers=self.stranger_headers)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("không có quyền", resp.text)

    def test_09_empty_farm_graceful_handling(self):
        """Farm with zero plots returns valid empty scene without errors."""
        # Create empty farm
        resp_f = client.post("/api/farms", json={
            "name": "Nông trại Mới Thành Lập (Chưa có lô)",
            "province": "Lâm Đồng",
            "area_hectare": 2.0
        }, headers=self.headers)
        empty_farm_id = resp_f.json()["farm"]["id"]

        resp = client.get(f"/api/farms/{empty_farm_id}/scene-3d", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(len(data["plots"]), 0)
        self.assertEqual(data["summary"]["total_plots"], 0)
        self.assertEqual(data["summary"]["total_plant_instances"], 0)
        self.assertIn("camera_preset", data)

    def test_10_single_plot_3d_detail_endpoint(self):
        """Single plot 3D endpoint /api/plots/{plot_id}/scene-3d returns plot and plant registry."""
        resp_p = client.post(f"/api/farms/{self.farm_id}/plots", json={
            "name": "Thửa Cây Cá Thể 3D",
            "crop_name": "Sầu riêng",
            "area_hectare": 0.5
        }, headers=self.headers)
        plot_id = resp_p.json()["plot"]["id"]

        # Register individual plant
        resp_plant = client.post(f"/api/plots/{plot_id}/plants", json={
            "plant_tag": "SR-01-MTH",
            "plant_name": "Sầu riêng Monthong Gốc 01",
            "health_status": "healthy",
            "row_index": 1,
            "col_index": 1
        }, headers=self.headers)
        self.assertEqual(resp_plant.status_code, 200)

        # Query single plot 3D detail
        resp = client.get(f"/api/plots/{plot_id}/scene-3d", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        detail = resp.json()

        self.assertEqual(detail["plot"]["id"], plot_id)
        self.assertEqual(detail["total_plants"], 1)
        self.assertEqual(detail["plants"][0]["plant_tag"], "SR-01-MTH")

        # Unauthorized access check
        resp_unauth = client.get(f"/api/plots/{plot_id}/scene-3d", headers=self.stranger_headers)
        self.assertEqual(resp_unauth.status_code, 403)


if __name__ == "__main__":
    unittest.main()
