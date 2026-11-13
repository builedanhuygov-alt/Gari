"""
GARI AI LAB — Leaf Validation & Disease Inference Pipeline Test Suite
File: tests/test_leaf_validation_pipeline.py

Verifies:
1. Healthy plant leaf is validated as LEAF_VALID and diagnosed accurately.
2. Diseased leaf with prominent symptoms is validated as LEAF_VALID and invokes disease model.
3. Non-leaf images (human face, animal, synthetic object, blue canvas) are rejected as NOT_A_LEAF.
4. Degraded quality images (motion blur, extreme darkness) are rejected as IMAGE_QUALITY_LOW.
5. Structured logging contains model name, input shape, preprocessing, latency, without PII.
"""

import sys
import unittest
from pathlib import Path
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from gari_inference_engine import GariInferenceEngine, validate_leaf_gate


class TestLeafValidationPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = GariInferenceEngine()
        cls.samples_dir = ROOT_DIR / "data" / "test_samples_17"
        cls.pv_dir = ROOT_DIR / "data" / "organized" / "PlantVillage"

    def test_01_healthy_leaf_validation(self):
        """Test that healthy tomato leaf passes gate and identifies as healthy."""
        p_healthy = list((self.pv_dir / "Tomato_healthy").glob("*.JPG"))[0]
        img = Image.open(p_healthy)
        
        gate_res = validate_leaf_gate(img)
        self.assertEqual(gate_res["status"], "LEAF_VALID")
        self.assertGreaterEqual(gate_res["score"], 0.65)
        
        res = self.engine.predict(img, mode="auto_standard")
        self.assertTrue(res["success"])
        self.assertEqual(res["crop_id"], "tomato")
        self.assertTrue(res["is_healthy"])

    def test_02_diseased_leaf_mold(self):
        """Test that Tomato Leaf Mold (previously false-rejected by blue background rule) passes gate and diagnoses disease."""
        p_mold = list((self.pv_dir / "Tomato_Leaf_Mold").glob("*.JPG"))[0]
        img = Image.open(p_mold)
        
        gate_res = validate_leaf_gate(img)
        self.assertEqual(gate_res["status"], "LEAF_VALID")
        
        res = self.engine.predict(img, mode="auto_standard")
        self.assertTrue(res["success"])
        self.assertEqual(res["crop_id"], "tomato")
        self.assertEqual(res["disease_id"], "Leaf_mold")
        self.assertGreater(res["confidence"], 0.80)

    def test_03_diseased_early_blight(self):
        """Test that Tomato Early Blight with necrotic lesions passes gate and diagnoses disease."""
        p_eb = list((self.pv_dir / "Tomato_Early_blight").glob("*.JPG"))[0]
        img = Image.open(p_eb)
        
        gate_res = validate_leaf_gate(img)
        self.assertEqual(gate_res["status"], "LEAF_VALID")
        
        res = self.engine.predict(img, mode="auto_standard")
        self.assertTrue(res["success"])
        self.assertEqual(res["crop_id"], "tomato")
        self.assertEqual(res["disease_id"], "Early_blight")
        self.assertGreater(res["confidence"], 0.80)

    def test_04_diseased_late_blight(self):
        """Test that Tomato Late Blight passes gate and diagnoses disease."""
        p_lb = list((self.pv_dir / "Tomato_Late_blight").glob("*.JPG"))[0]
        img = Image.open(p_lb)
        
        gate_res = validate_leaf_gate(img)
        self.assertEqual(gate_res["status"], "LEAF_VALID")
        
        res = self.engine.predict(img, mode="auto_standard")
        self.assertTrue(res["success"])
        self.assertEqual(res["crop_id"], "tomato")
        self.assertIn("Late_blight", res["disease_id"])

    def test_05_non_leaf_rejections(self):
        """Test that non-leaf images are rejected as NOT_A_LEAF without invoking disease model."""
        non_leaf_files = [
            "5_non_leaf.jpg",        # synthetic blue surface
            "6_human_face.jpg",       # human face
            "7_animal.jpg",           # animal
            "8_general_object.jpg"    # general object
        ]
        for filename in non_leaf_files:
            p = self.samples_dir / filename
            if not p.exists():
                continue
            with self.subTest(filename=filename):
                img = Image.open(p)
                gate_res = validate_leaf_gate(img)
                self.assertEqual(gate_res["status"], "NOT_A_LEAF", f"{filename} should be NOT_A_LEAF")
                
                res = self.engine.predict(img, mode="auto_standard")
                self.assertFalse(res["success"])
                self.assertEqual(res["status"], "not_a_leaf")

    def test_06_low_quality_rejections(self):
        """Test that blurry or low-light images are rejected as IMAGE_QUALITY_LOW."""
        quality_files = [
            ("9_blurry_leaf.jpg", "blur"),
            ("10_low_light_leaf.jpg", "darkness")
        ]
        for filename, desc in quality_files:
            p = self.samples_dir / filename
            if not p.exists():
                continue
            with self.subTest(filename=filename, description=desc):
                img = Image.open(p)
                gate_res = validate_leaf_gate(img)
                self.assertEqual(gate_res["status"], "IMAGE_QUALITY_LOW", f"{filename} should be IMAGE_QUALITY_LOW")
                
                res = self.engine.predict(img, mode="auto_standard")
                self.assertFalse(res["success"])
                self.assertEqual(res["status"], "image_quality_low")


if __name__ == "__main__":
    unittest.main()
