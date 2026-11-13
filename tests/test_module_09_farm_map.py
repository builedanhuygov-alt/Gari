"""
GARI Module 09 — Farm Intelligence 2D Map Test Suite
Verifies:
1. Valid GeoJSON polygon geometry validation and centroid calculation.
2. Rejection of invalid polygon (unclosed ring, fewer than 4 points, out-of-range coords).
3. Update farm center coordinates and outer perimeter boundary.
4. Update plot polygon boundary with automatic centroid and area calculation.
5. Explicit geometry source tracking (user_drawn vs surveyed vs estimated).
6. Farm 2D map GeoJSON bundle returns located FeatureCollection and unlocated plots list.
7. Deterministic health status: plot with recent severe disease marked attention_needed.
8. Deterministic health status: plot with overdue cultivation task marked attention_needed.
9. Deterministic health status: plot with clean diagnosis marked healthy; unmonitored marked unknown.
10. Strict tenant & organization boundary: unauthorized user cannot view or mutate another farm's map data (HTTP 403 Forbidden).
"""

import unittest
import sys
import os
import json
import uuid

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi.testclient import TestClient
from api_server import app
from gari_database import get_connection
import gari_farm_map

client = TestClient(app)


def _create_user(name_prefix="FarmerMap"):
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


def _create_farm_with_plots(user_headers, farm_name="Nông trại Test 2D"):
    # 1. Create farm
    f_res = client.post("/api/farms", json={
        "name": farm_name,
        "location": "Xã Ea Ktur, Huyện Cư Kuin",
        "province": "Đắk Lắk",
        "area_hectares": 3.5,
        "primary_crop": "coffee"
    }, headers=user_headers)
    assert f_res.status_code == 200, f_res.text
    farm = f_res.json().get("farm") or f_res.json().get("data")
    farm_id = farm["id"]

    # 2. Create plot 1
    p1_res = client.post(f"/api/farms/{farm_id}/plots", json={
        "plot_name": "Lô Cà phê Catimor 1",
        "crop_id": "coffee",
        "area_hectares": 1.5,
        "planting_date": "2023-05-15"
    }, headers=user_headers)
    assert p1_res.status_code == 200, p1_res.text
    plot1 = p1_res.json().get("plot") or p1_res.json().get("data")

    # 3. Create plot 2 (unlocated)
    p2_res = client.post(f"/api/farms/{farm_id}/plots", json={
        "plot_name": "Lô Hồ tiêu Vĩnh Linh 2",
        "crop_id": "pepper",
        "area_hectares": 1.0,
        "planting_date": "2024-03-20"
    }, headers=user_headers)
    assert p2_res.status_code == 200, p2_res.text
    plot2 = p2_res.json().get("plot") or p2_res.json().get("data")

    return farm, plot1, plot2


class TestModule09FarmMap(unittest.TestCase):

    def setUp(self):
        self.owner, self.owner_token, self.owner_headers = _create_user("FarmOwner09")
        self.stranger, self.stranger_token, self.stranger_headers = _create_user("Stranger09")
        self.farm, self.plot1, self.plot2 = _create_farm_with_plots(self.owner_headers)

    def test_01_valid_geometry_validation_and_centroid_calc(self):
        """1. Valid GeoJSON polygon geometry validation and centroid calculation."""
        # Square polygon in Buon Ma Thuot
        poly = {
            "type": "Polygon",
            "coordinates": [[
                [108.0650, 12.6850],
                [108.0670, 12.6850],
                [108.0670, 12.6870],
                [108.0650, 12.6870],
                [108.0650, 12.6850]
            ]]
        }
        validated = gari_farm_map.validate_polygon_geometry(poly)
        self.assertEqual(validated["type"], "Polygon")
        self.assertEqual(len(validated["coordinates"][0]), 5)

        centroid_lat, centroid_lon = gari_farm_map.calculate_polygon_centroid(validated["coordinates"][0])
        self.assertAlmostEqual(centroid_lat, 12.6860, places=4)
        self.assertAlmostEqual(centroid_lon, 108.0660, places=4)

        area_m2 = gari_farm_map.calculate_polygon_area_m2(validated["coordinates"][0])
        self.assertGreater(area_m2, 40000.0)  # ~4-5 ha

    def test_02_invalid_geometry_rejection(self):
        """2. Rejection of invalid polygon (unclosed ring, fewer than 4 points, out-of-range coords)."""
        # Unclosed ring
        unclosed = {
            "type": "Polygon",
            "coordinates": [[
                [108.0650, 12.6850],
                [108.0670, 12.6850],
                [108.0670, 12.6870],
                [108.0650, 12.6870]  # Missing closure to first point
            ]]
        }
        with self.assertRaises(ValueError):
            gari_farm_map.validate_polygon_geometry(unclosed)

        # Fewer than 4 points
        triangle_unclosed = {
            "type": "Polygon",
            "coordinates": [[[108.0, 12.0], [108.1, 12.1], [108.0, 12.0]]]
        }
        with self.assertRaises(ValueError):
            gari_farm_map.validate_polygon_geometry(triangle_unclosed)

        # Out-of-bounds latitude
        out_of_bounds = {
            "type": "Polygon",
            "coordinates": [[
                [108.0650, 95.0],
                [108.0670, 95.0],
                [108.0670, 95.1],
                [108.0650, 95.1],
                [108.0650, 95.0]
            ]]
        }
        with self.assertRaises(ValueError):
            gari_farm_map.validate_polygon_geometry(out_of_bounds)

    def test_03_update_farm_location_and_boundary(self):
        """3. Update farm center coordinates and outer perimeter boundary."""
        lat = 12.6850
        lon = 108.0650
        farm_poly = {
            "type": "Polygon",
            "coordinates": [[
                [108.0600, 12.6800],
                [108.0700, 12.6800],
                [108.0700, 12.6900],
                [108.0600, 12.6900],
                [108.0600, 12.6800]
            ]]
        }
        payload = {
            "latitude": lat,
            "longitude": lon,
            "boundary": farm_poly,
            "geometry_source": "surveyed"
        }
        resp = client.put(f"/api/farms/{self.farm['id']}/location", json=payload, headers=self.owner_headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("geometry_source"), "surveyed")

        # Verify DB
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT latitude, longitude, boundary_geojson, geometry_source FROM farms WHERE id = ?", (self.farm["id"],))
            row = cursor.fetchone()
            self.assertAlmostEqual(row["latitude"], lat, places=4)
            self.assertAlmostEqual(row["longitude"], lon, places=4)
            self.assertEqual(row["geometry_source"], "surveyed")
            self.assertIsNotNone(row["boundary_geojson"])

    def test_04_update_plot_geometry_with_area_and_centroid(self):
        """4. Update plot polygon boundary with automatic centroid and area calculation."""
        plot_poly = {
            "type": "Polygon",
            "coordinates": [[
                [108.0620, 12.6820],
                [108.0650, 12.6820],
                [108.0650, 12.6850],
                [108.0620, 12.6850],
                [108.0620, 12.6820]
            ]]
        }
        payload = {
            "geometry": plot_poly,
            "geometry_source": "user_drawn",
            "boundary_color": "#16a34a"
        }
        resp = client.put(f"/api/plots/{self.plot1['id']}/geometry", json=payload, headers=self.owner_headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertTrue(data.get("success"))
        self.assertAlmostEqual(data["latitude"], 12.6835, places=4)
        self.assertAlmostEqual(data["longitude"], 108.0635, places=4)
        self.assertGreater(data["calculated_area_m2"], 10000.0)

    def test_05_explicit_geometry_source_tracking(self):
        """5. Explicit geometry source tracking (user_drawn vs surveyed vs estimated)."""
        # Plot 1 updated with 'estimated'
        poly = {
            "type": "Polygon",
            "coordinates": [[
                [108.0620, 12.6820], [108.0650, 12.6820],
                [108.0650, 12.6850], [108.0620, 12.6850],
                [108.0620, 12.6820]
            ]]
        }
        client.put(f"/api/plots/{self.plot1['id']}/geometry", json={
            "geometry": poly,
            "geometry_source": "estimated"
        }, headers=self.owner_headers)

        detail = client.get(f"/api/plots/{self.plot1['id']}/map-detail", headers=self.owner_headers).json()
        self.assertEqual(detail["plot"]["geometry_source"], "estimated")

        # Plot 2 is unlocated
        detail2 = client.get(f"/api/plots/{self.plot2['id']}/map-detail", headers=self.owner_headers).json()
        self.assertEqual(detail2["plot"]["geometry_source"], "unlocated")

    def test_06_farm_map_geojson_bundle_and_unlocated_plots(self):
        """6. Farm 2D map GeoJSON bundle returns located FeatureCollection and unlocated plots list."""
        # Locate Plot 1
        poly = {
            "type": "Polygon",
            "coordinates": [[
                [108.0620, 12.6820], [108.0650, 12.6820],
                [108.0650, 12.6850], [108.0620, 12.6850],
                [108.0620, 12.6820]
            ]]
        }
        client.put(f"/api/plots/{self.plot1['id']}/geometry", json={"geometry": poly}, headers=self.owner_headers)

        # Plot 2 remains unlocated
        map_resp = client.get(f"/api/farms/{self.farm['id']}/map", headers=self.owner_headers)
        self.assertEqual(map_resp.status_code, 200, map_resp.text)
        data = map_resp.json()
        self.assertTrue(data.get("success"))

        fc = data.get("plots_feature_collection")
        self.assertEqual(fc["type"], "FeatureCollection")
        self.assertEqual(len(fc["features"]), 1)
        self.assertEqual(fc["features"][0]["id"], self.plot1["id"])

        unlocated = data.get("unlocated_plots", [])
        self.assertEqual(len(unlocated), 1)
        self.assertEqual(unlocated[0]["id"], self.plot2["id"])
        self.assertEqual(data.get("total_plots"), 2)

    def test_07_deterministic_health_status_attention_needed_disease(self):
        """7. Deterministic health status: plot with recent severe disease marked attention_needed."""
        # Insert severe disease diagnosis for plot 1
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO diagnoses (
                    user_id, crop_id, crop_name, predicted_disease, confidence, severity,
                    diagnosis_status, plot_id, created_at
                ) VALUES (?, 'coffee', 'Cà phê', 'Coffee Rust (Rỉ sắt nặng)', 0.92, 'CRITICAL', 'diagnosed', ?, CURRENT_TIMESTAMP)
            """, (self.owner["id"], self.plot1["id"]))
            conn.commit()

        detail = client.get(f"/api/plots/{self.plot1['id']}/map-detail", headers=self.owner_headers).json()
        self.assertEqual(detail["health_status"], "attention_needed")
        self.assertIn("Rỉ sắt", detail["status_reason"])
        self.assertIsNotNone(detail["recent_diagnosis"])

    def test_08_deterministic_health_status_attention_needed_overdue_tasks(self):
        """8. Deterministic health status: plot with overdue cultivation task marked attention_needed."""
        # Insert overdue task for plot 2 (due in the past)
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cultivation_tasks (
                    user_id, farm_id, plot_id, title, task_type, priority,
                    due_date, status, created_at
                ) VALUES (?, ?, ?, 'Phun phòng trừ nấm gốc định kỳ', 'fertilizing', 'high', '2020-01-01', 'pending', CURRENT_TIMESTAMP)
            """, (self.owner["id"], self.farm["id"], self.plot2["id"]))
            conn.commit()

        detail = client.get(f"/api/plots/{self.plot2['id']}/map-detail", headers=self.owner_headers).json()
        self.assertEqual(detail["health_status"], "attention_needed")
        self.assertGreaterEqual(detail["overdue_tasks_count"], 1)

    def test_09_deterministic_health_status_healthy_and_unknown(self):
        """9. Deterministic health status: plot with clean diagnosis marked healthy; unmonitored marked unknown."""
        # Clean diagnosis on plot 1
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO diagnoses (
                    user_id, crop_id, crop_name, predicted_disease, confidence, severity,
                    diagnosis_status, plot_id, created_at
                ) VALUES (?, 'coffee', 'Cà phê', 'Healthy (Lá sinh trưởng khỏe mạnh)', 0.98, 'LOW', 'diagnosed', ?, CURRENT_TIMESTAMP)
            """, (self.owner["id"], self.plot1["id"]))
            conn.commit()

        detail1 = client.get(f"/api/plots/{self.plot1['id']}/map-detail", headers=self.owner_headers).json()
        self.assertEqual(detail1["health_status"], "healthy")

        # Create plot 3 without any diagnosis or task
        p3_res = client.post(f"/api/farms/{self.farm['id']}/plots", json={
            "plot_name": "Lô Bơ Sáp Mới Trồng 3",
            "crop_id": "avocado",
            "area_hectares": 0.8
        }, headers=self.owner_headers).json()
        p3_id = p3_res["plot"]["id"]

        detail3 = client.get(f"/api/plots/{p3_id}/map-detail", headers=self.owner_headers).json()
        self.assertEqual(detail3["health_status"], "unknown")
        self.assertIn("Chưa có dữ liệu", detail3["status_reason"])

    def test_10_tenant_and_permission_isolation(self):
        """10. Strict tenant & organization boundary: unauthorized user cannot view or mutate another farm's map data (HTTP 403 Forbidden)."""
        # Stranger tries to view Farm map
        stranger_get = client.get(f"/api/farms/{self.farm['id']}/map", headers=self.stranger_headers)
        self.assertEqual(stranger_get.status_code, 403)

        # Stranger tries to update Farm location
        stranger_put_farm = client.put(f"/api/farms/{self.farm['id']}/location", json={
            "latitude": 10.0,
            "longitude": 105.0
        }, headers=self.stranger_headers)
        self.assertEqual(stranger_put_farm.status_code, 403)

        # Stranger tries to update Plot geometry
        poly = {
            "type": "Polygon",
            "coordinates": [[
                [108.0, 12.0], [108.1, 12.0], [108.1, 12.1], [108.0, 12.1], [108.0, 12.0]
            ]]
        }
        stranger_put_plot = client.put(f"/api/plots/{self.plot1['id']}/geometry", json={
            "geometry": poly
        }, headers=self.stranger_headers)
        self.assertEqual(stranger_put_plot.status_code, 403)

        # Stranger tries to view Plot map detail
        stranger_get_plot = client.get(f"/api/plots/{self.plot1['id']}/map-detail", headers=self.stranger_headers)
        self.assertEqual(stranger_get_plot.status_code, 403)


if __name__ == "__main__":
    unittest.main()
