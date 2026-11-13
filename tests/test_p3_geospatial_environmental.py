"""
GARI AgriTech AI Lab — Phase P3 Automated Test Suite
Geospatial & Environmental Intelligence Verification:
- Scenario A: Farm/Zone/Plot GIS mapping, GeoJSON validation, and centroid computation.
- Scenario B: Weather Intelligence (Open-Meteo live query, caching, and unlocated state).
- Scenario C: Satellite Intelligence (Sentinel-2 STAC, cloud masking, NDVI/NDMI calculation).
- Scenario D: Agricultural Risk Engine (5-vector transparent evaluation and explainability).
- Scenario E: Smart Alerts lifecycle, deduplication, cooldown, and team assignment.
- Scenario F: Farm Digital Twin unified 5-layer profile synthesis.
- Scenario G: Strict tenant and organization isolation enforcement (HTTP 403 / PermissionError).
- Scenario H: Graceful handling of unlocated assets, missing data, and disconnected states.
"""

import json
import unittest
import uuid
from starlette.testclient import TestClient

from api_server import app
import gari_auth
import gari_plans
import gari_entitlements
import gari_farm_management
import gari_gis_service
import gari_weather_service
import gari_satellite_service
import gari_risk_engine
import gari_digital_twin
import gari_smart_alerts
import gari_intelligence_reports


class TestP3GeospatialEnvironmental(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

        # 1. Register User A (Tenant A)
        cls.user_a_email = f"p3_owner_a_{uuid.uuid4().hex[:8]}@gari.vn"
        cls.user_a_pass = "Password123!"
        res_a = cls.client.post("/api/auth/register", json={
            "email": cls.user_a_email,
            "password": cls.user_a_pass,
            "full_name": "Nguyen Van A - Org A"
        })
        assert res_a.status_code == 200, f"Registration failed: {res_a.text}"
        data_a = res_a.json()
        cls.token_a = data_a.get("access_token") or data_a.get("token")
        cls.user_a_id = data_a.get("user", {}).get("id") or data_a.get("user_id")
        cls.headers_a = {"Authorization": f"Bearer {cls.token_a}"}

        # Upgrade User A to 'enterprise' plan so they can create organizations and unlimited farms
        gari_plans.assign_user_plan(cls.user_a_id, "enterprise", status="pilot_active")

        # Create Organization A
        res_org_a = cls.client.post("/api/organizations", headers=cls.headers_a, json={
            "name": f"HTX Rau Sach Da Lat {uuid.uuid4().hex[:6]}",
            "type": "cooperative",
            "description": "Hop tac xa rau sach nong nghiep cong nghe cao Da Lat"
        })
        assert res_org_a.status_code == 200
        cls.org_a_id = res_org_a.json()["organization"]["id"]

        # 2. Register User B (Tenant B)
        cls.user_b_email = f"p3_owner_b_{uuid.uuid4().hex[:8]}@gari.vn"
        cls.user_b_pass = "Password123!"
        res_b = cls.client.post("/api/auth/register", json={
            "email": cls.user_b_email,
            "password": cls.user_b_pass,
            "full_name": "Tran Van B - Org B"
        })
        assert res_b.status_code == 200
        data_b = res_b.json()
        cls.token_b = data_b.get("access_token") or data_b.get("token")
        cls.user_b_id = data_b.get("user", {}).get("id") or data_b.get("user_id")
        cls.headers_b = {"Authorization": f"Bearer {cls.token_b}"}

        gari_plans.assign_user_plan(cls.user_b_id, "enterprise", status="pilot_active")

        # Create Organization B
        res_org_b = cls.client.post("/api/organizations", headers=cls.headers_b, json={
            "name": f"Trang Trai Ca Phe Gia Lai {uuid.uuid4().hex[:6]}",
            "type": "enterprise",
            "description": "Doanh nghiep ca phe Gia Lai"
        })
        assert res_org_b.status_code == 200
        cls.org_b_id = res_org_b.json()["organization"]["id"]

        # Upgrade organizations to enterprise plan for comprehensive multi-farm testing
        import gari_database
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE organizations SET plan_id = 'enterprise' WHERE id IN (?, ?)", (cls.org_a_id, cls.org_b_id))
            conn.commit()

        # Authoritative subscription assignment for both users and organizations
        gari_entitlements.assign_subscription("user", cls.user_a_id, "organization", duration_days=30)
        gari_entitlements.assign_subscription("user", cls.user_b_id, "organization", duration_days=30)
        gari_entitlements.assign_subscription("organization", cls.org_a_id, "organization", duration_days=30)
        gari_entitlements.assign_subscription("organization", cls.org_b_id, "organization", duration_days=30)

    def test_01_scenario_a_gis_hierarchy_and_geojson_mapping(self):
        """Scenario A: Create Farm -> Zone -> Plot with valid GeoJSON geometries, centroids, and GIS bundle."""
        # Create Farm for Org A
        res_farm = self.client.post("/api/farms", headers=self.headers_a, json={
            "name": "Trang trại Đà Lạt Farm 1",
            "location": "Phường 7, TP. Đà Lạt",
            "province": "Lâm Đồng",
            "area_hectare": 3.5,
            "primary_crop": "Tomato",
            "organization_id": self.org_a_id
        })
        self.assertEqual(res_farm.status_code, 200)
        farm_id = res_farm.json()["farm"]["id"]

        # Update Farm Center Coordinates (Da Lat: 11.9404, 108.4583)
        res_farm_loc = self.client.put(f"/api/farms/{farm_id}/location", headers=self.headers_a, json={
            "latitude": 11.9404,
            "longitude": 108.4583,
            "organization_id": self.org_a_id
        })
        self.assertEqual(res_farm_loc.status_code, 200)

        # Create Zone in Farm
        res_zone = self.client.post(f"/api/farms/{farm_id}/zones", headers=self.headers_a, json={
            "name": "Khu Nhà màng Công nghệ cao 1",
            "code": "ZONE-CNC-1",
            "zone_type": "greenhouse",
            "area_hectare": 1.2
        })
        self.assertEqual(res_zone.status_code, 200)
        zone_id = res_zone.json()["zone"]["id"]

        # Update Zone Polygon Geometry
        zone_poly = {
            "type": "Polygon",
            "coordinates": [[
                [108.4570, 11.9390],
                [108.4590, 11.9390],
                [108.4590, 11.9410],
                [108.4570, 11.9410],
                [108.4570, 11.9390]
            ]]
        }
        res_zone_geom = self.client.put(f"/api/gis/zones/{zone_id}/geometry", headers=self.headers_a, json={
            "geometry": zone_poly,
            "organization_id": self.org_a_id
        })
        self.assertEqual(res_zone_geom.status_code, 200)
        zone_data = res_zone_geom.json()
        self.assertAlmostEqual(zone_data["latitude"], 11.9400, places=3)
        self.assertAlmostEqual(zone_data["longitude"], 108.4580, places=3)
        self.assertGreater(zone_data["calculated_area_m2"], 1000)

        # Create Plot within Zone
        res_plot = self.client.post(f"/api/farms/{farm_id}/plots", headers=self.headers_a, json={
            "plot_name": "Lô Cà chua beef A1",
            "crop_id": "Tomato",
            "crop_name": "Cà chua",
            "area_hectare": 0.5,
            "zone_id": zone_id,
            "planting_date": "2026-10-01"
        })
        self.assertEqual(res_plot.status_code, 200)
        plot_id = res_plot.json()["plot"]["id"]

        # Update Plot Polygon Geometry
        plot_poly = {
            "type": "Polygon",
            "coordinates": [[
                [108.4575, 11.9395],
                [108.4585, 11.9395],
                [108.4585, 11.9405],
                [108.4575, 11.9405],
                [108.4575, 11.9395]
            ]]
        }
        res_plot_geom = self.client.put(f"/api/plots/{plot_id}/geometry", headers=self.headers_a, json={
            "geometry": plot_poly,
            "organization_id": self.org_a_id
        })
        self.assertEqual(res_plot_geom.status_code, 200)
        plot_geom_data = res_plot_geom.json()
        self.assertAlmostEqual(plot_geom_data["latitude"], 11.9400, places=3)
        self.assertAlmostEqual(plot_geom_data["longitude"], 108.4580, places=3)

        # Retrieve Full GIS Bundle
        res_gis = self.client.get(f"/api/gis/farms/{farm_id}", headers=self.headers_a)
        self.assertEqual(res_gis.status_code, 200)
        gis_data = res_gis.json()
        self.assertTrue(gis_data["success"])
        self.assertEqual(gis_data["counts"]["total_zones"], 1)
        self.assertEqual(gis_data["counts"]["located_zones"], 1)
        self.assertEqual(gis_data["counts"]["total_plots"], 1)
        self.assertEqual(gis_data["counts"]["located_plots"], 1)
        self.assertEqual(len(gis_data["plots_feature_collection"]["features"]), 1)

    def test_02_scenario_b_weather_intelligence_caching_and_provenance(self):
        """Scenario B: Open-Meteo weather intelligence, live fetch, caching, and provenance metadata."""
        # Query weather for known coordinate (Dalat: 11.9404, 108.4583)
        res_w = self.client.get("/api/weather/coordinates?lat=11.9404&lon=108.4583", headers=self.headers_a)
        self.assertEqual(res_w.status_code, 200)
        data = res_w.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["provider"], "Open-Meteo")
        self.assertEqual(data["status"], "connected")
        self.assertTrue(data["is_real_data"])
        self.assertIn("temperature_c", data["current"])
        self.assertIn("humidity_pct", data["current"])
        self.assertIn("condition", data["current"])
        self.assertEqual(len(data["daily_forecast"]), 7)

        # Check caching behavior (second fetch should be fast and marked cached)
        res_w2 = self.client.get("/api/weather/coordinates?lat=11.9404&lon=108.4583", headers=self.headers_a)
        self.assertEqual(res_w2.status_code, 200)
        data2 = res_w2.json()
        self.assertTrue(data2.get("is_cached", True))

    def test_03_scenario_c_satellite_intelligence_and_spectral_indices(self):
        """Scenario C: Sentinel-2 L2A STAC query and NDVI/NDMI spectral calculations."""
        # Test mathematical formulas directly
        ndvi_val = gari_satellite_service.calculate_ndvi(b08_nir=0.82, b04_red=0.12)
        self.assertAlmostEqual(ndvi_val, (0.82 - 0.12) / (0.82 + 0.12), places=3)
        self.assertGreater(ndvi_val, 0.7)  # dense healthy vegetation

        ndmi_val = gari_satellite_service.calculate_ndmi(b08_nir=0.82, b11_swir=0.35)
        self.assertAlmostEqual(ndmi_val, (0.82 - 0.35) / (0.82 + 0.35), places=3)

        # Query plot vegetation indices for a plot
        # Create a located plot
        res_farm = self.client.post("/api/farms", headers=self.headers_a, json={
            "name": "Trang trại Vệ tinh Thử nghiệm",
            "province": "Lâm Đồng",
            "area_hectare": 2.0,
            "organization_id": self.org_a_id
        })
        fid = res_farm.json()["farm"]["id"]
        res_plot = self.client.post(f"/api/farms/{fid}/plots", headers=self.headers_a, json={
            "plot_name": "Thửa cà chua quan trắc vệ tinh",
            "crop_id": "Tomato"
        })
        pid = res_plot.json()["plot"]["id"]

        # Assign geometry
        self.client.put(f"/api/plots/{pid}/geometry", headers=self.headers_a, json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[108.45, 11.94], [108.46, 11.94], [108.46, 11.95], [108.45, 11.95], [108.45, 11.94]]]
            },
            "organization_id": self.org_a_id
        })

        # Fetch satellite indices API
        res_sat = self.client.get(f"/api/satellite/plots/{pid}/indices", headers=self.headers_a)
        self.assertEqual(res_sat.status_code, 200)
        sat_data = res_sat.json()
        self.assertTrue(sat_data["success"])
        self.assertIn(sat_data["status"], ("connected", "valid"))
        self.assertIsNotNone(sat_data["latest_ndvi"])
        self.assertIsNotNone(sat_data["latest_ndmi"])
        self.assertIn("canopy_assessment", sat_data)

    def test_04_scenario_d_agricultural_risk_engine(self):
        """Scenario D: 5-vector transparent risk evaluation with factor decomposition and explanations."""
        # Create Farm & Plot
        res_farm = self.client.post("/api/farms", headers=self.headers_a, json={
            "name": "Trang trại Rủi ro Khí hậu",
            "province": "Lâm Đồng",
            "organization_id": self.org_a_id
        })
        self.assertEqual(res_farm.status_code, 200, f"res_farm failed: {res_farm.text}")
        fid = res_farm.json()["farm"]["id"]
        res_plot = self.client.post(f"/api/farms/{fid}/plots", headers=self.headers_a, json={
            "plot_name": "Thửa Đánh giá Nguy cơ Dịch tễ",
            "crop_name": "Cà chua"
        })
        pid = res_plot.json()["plot"]["id"]

        self.client.put(f"/api/plots/{pid}/geometry", headers=self.headers_a, json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[108.45, 11.94], [108.46, 11.94], [108.46, 11.95], [108.45, 11.95], [108.45, 11.94]]]
            },
            "organization_id": self.org_a_id
        })

        # Evaluate risk API
        res_risk = self.client.get(f"/api/risk/plots/{pid}/evaluate", headers=self.headers_a)
        self.assertEqual(res_risk.status_code, 200)
        risk_data = res_risk.json()
        self.assertTrue(risk_data["success"])
        self.assertEqual(risk_data["status"], "evaluated")
        self.assertIn("overall_risk_level", risk_data)
        self.assertIn("overall_risk_score", risk_data)

        # Verify 5 risk categories are present
        categories = [a["risk_category"] for a in risk_data["assessments"]]
        self.assertIn("drought", categories)
        self.assertIn("heavy_rainfall", categories)
        self.assertIn("heat_stress", categories)
        self.assertIn("disease_weather", categories)
        self.assertIn("vegetation_degradation", categories)

        # Verify factor decomposition & explanation exist
        for a in risk_data["assessments"]:
            self.assertIn("explanation", a)
            self.assertIn("contributing_factors", a)
            self.assertIn("recommendations", a)

    def test_05_scenario_e_smart_alerts_lifecycle_and_deduplication(self):
        """Scenario E: Smart alerts creation, deduplication, cooldown, assignment, and resolution."""
        # Create Farm
        res_farm = self.client.post("/api/farms", headers=self.headers_a, json={
            "name": "Trang trại Cảnh báo Thông minh",
            "organization_id": self.org_a_id
        })
        fid = res_farm.json()["farm"]["id"]

        # Create alert 1
        res_a1 = self.client.post("/api/alerts", headers=self.headers_a, json={
            "farm_id": fid,
            "organization_id": self.org_a_id,
            "alert_type": "weather",
            "severity": "warning",
            "title": "Cảnh báo mưa to diện rộng kéo dài",
            "description": "Lượng mưa dự báo đạt 65mm có nguy cơ gây úng gốc.",
            "trigger_source": "open_meteo"
        })
        self.assertEqual(res_a1.status_code, 200)
        a1_data = res_a1.json()
        self.assertFalse(a1_data["deduplicated"])
        alert_id = a1_data["alert_id"]

        # Post duplicate alert with identical parameters within cooldown
        res_a2 = self.client.post("/api/alerts", headers=self.headers_a, json={
            "farm_id": fid,
            "organization_id": self.org_a_id,
            "alert_type": "weather",
            "severity": "critical",
            "title": "Cảnh báo mưa to diện rộng kéo dài",
            "description": "Lượng mưa cập nhật mới 70mm.",
            "trigger_source": "open_meteo"
        })
        self.assertEqual(res_a2.status_code, 200)
        a2_data = res_a2.json()
        self.assertTrue(a2_data["deduplicated"])
        self.assertEqual(a2_data["alert_id"], alert_id)

        # Transition lifecycle: Acknowledge -> Assign -> Resolve
        res_ack = self.client.patch(f"/api/alerts/{alert_id}/status", headers=self.headers_a, json={
            "status": "acknowledged"
        })
        self.assertEqual(res_ack.status_code, 200)

        res_assign = self.client.post(f"/api/alerts/{alert_id}/assign", headers=self.headers_a, json={
            "assigned_user_id": self.user_a_id
        })
        self.assertEqual(res_assign.status_code, 200)

        res_res = self.client.patch(f"/api/alerts/{alert_id}/status", headers=self.headers_a, json={
            "status": "resolved",
            "resolution_notes": "Đã khơi thông toàn bộ rãnh thoát nước."
        })
        self.assertEqual(res_res.status_code, 200)
        self.assertEqual(res_res.json()["status"], "resolved")

    def test_06_scenario_f_farm_digital_twin_synthesis(self):
        """Scenario F: Multi-layer Farm Digital Twin aggregating physical, environmental, diagnostic, and risk data."""
        # Create Farm
        res_farm = self.client.post("/api/farms", headers=self.headers_a, json={
            "name": "Trang trại Digital Twin Alpha",
            "location": "Đà Lạt",
            "province": "Lâm Đồng",
            "area_hectare": 5.0,
            "primary_crop": "Tomato",
            "organization_id": self.org_a_id
        })
        fid = res_farm.json()["farm"]["id"]

        # Assign location
        self.client.put(f"/api/farms/{fid}/location", headers=self.headers_a, json={
            "latitude": 11.9404,
            "longitude": 108.4583,
            "organization_id": self.org_a_id
        })

        # Add Zone and Plot
        res_z = self.client.post(f"/api/farms/{fid}/zones", headers=self.headers_a, json={"name": "Khu Digital Twin 1"})
        zid = res_z.json()["zone"]["id"]
        res_p = self.client.post(f"/api/farms/{fid}/plots", headers=self.headers_a, json={"plot_name": "Thửa DT-1", "zone_id": zid})
        pid = res_p.json()["plot"]["id"]

        self.client.put(f"/api/plots/{pid}/geometry", headers=self.headers_a, json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[108.45, 11.94], [108.46, 11.94], [108.46, 11.95], [108.45, 11.95], [108.45, 11.94]]]
            },
            "organization_id": self.org_a_id
        })

        # Query Digital Twin
        res_dt = self.client.get(f"/api/digital-twin/farms/{fid}", headers=self.headers_a)
        self.assertEqual(res_dt.status_code, 200)
        dt = res_dt.json()
        self.assertTrue(dt["success"])
        self.assertEqual(dt["farm_id"], fid)
        self.assertIn("farm_health_score", dt)
        self.assertIn("spatial_profile", dt)
        self.assertIn("biological_profile", dt)
        self.assertIn("environmental_profile", dt)
        self.assertIn("satellite_profile", dt)
        self.assertIn("operational_profile", dt)

    def test_07_scenario_g_tenant_isolation_security(self):
        """Scenario G: User B from Org B cannot access Org A's GIS data, Digital Twin, or Alerts."""
        # Create Farm in Org A
        res_farm = self.client.post("/api/farms", headers=self.headers_a, json={
            "name": "Nông trại Bí mật của HTX A",
            "organization_id": self.org_a_id
        })
        self.assertEqual(res_farm.status_code, 200, f"test_07 res_farm failed: {res_farm.text}")
        fid_a = res_farm.json()["farm"]["id"]

        # User B attempts to access GIS bundle of Org A's farm -> 403 Forbidden
        res_b_gis = self.client.get(f"/api/gis/farms/{fid_a}", headers=self.headers_b)
        self.assertEqual(res_b_gis.status_code, 403)

        # User B attempts to access Digital Twin of Org A's farm -> 403 Forbidden
        res_b_dt = self.client.get(f"/api/digital-twin/farms/{fid_a}", headers=self.headers_b)
        self.assertEqual(res_b_dt.status_code, 403)

        # User B attempts to query alerts filtered by Org A's ID -> 403 Forbidden
        res_b_alerts = self.client.get(f"/api/alerts?organization_id={self.org_a_id}", headers=self.headers_b)
        self.assertEqual(res_b_alerts.status_code, 403)

    def test_08_scenario_h_graceful_missing_data_and_reports(self):
        """Scenario H: Graceful handling of unlocated farms, missing data states, and multi-format reports."""
        # Create unlocated farm (no coordinates set)
        res_farm = self.client.post("/api/farms", headers=self.headers_a, json={
            "name": "Trang trại Chưa có Tọa độ",
            "organization_id": self.org_a_id
        })
        self.assertEqual(res_farm.status_code, 200, f"test_08 res_farm failed: {res_farm.text}")
        fid = res_farm.json()["farm"]["id"]

        # Weather for unlocated farm returns status 'unlocated' without error
        res_w = self.client.get(f"/api/weather/farms/{fid}", headers=self.headers_a)
        self.assertEqual(res_w.status_code, 200)
        w_data = res_w.json()
        self.assertEqual(w_data["status"], "unlocated")
        self.assertFalse(w_data["is_real_data"])

        # Satellite scenes for unlocated farm returns 'unlocated'
        res_sat = self.client.get(f"/api/satellite/farms/{fid}/scenes", headers=self.headers_a)
        self.assertEqual(res_sat.status_code, 200)
        self.assertEqual(res_sat.json()["status"], "unlocated")

        # Reports generation: Farm health report in JSON and CSV
        res_rep_json = self.client.get(f"/api/reports/farm-health?farm_id={fid}&format=json", headers=self.headers_a)
        self.assertEqual(res_rep_json.status_code, 200)
        self.assertTrue(res_rep_json.json()["success"])

        res_rep_csv = self.client.get(f"/api/reports/farm-health?farm_id={fid}&format=csv", headers=self.headers_a)
        self.assertEqual(res_rep_csv.status_code, 200)
        self.assertIn("text/csv", res_rep_csv.headers["content-type"])
        self.assertIn("Mã chẩn đoán", res_rep_csv.text)


if __name__ == "__main__":
    unittest.main()
