"""
GARI AgriTech AI Lab — Sprint 6.1 Dual-Gate Pipeline Test Suite
Validates the 10 core verification scenarios:
1. Valid leaf image passes Gate 1.
2. Non-leaf image rejected at Gate 1 (NOT_A_LEAF).
3. Ambiguous/uncertain crop returns CROP_UNCERTAIN.
4. Low quality/blurry image rejected (IMAGE_QUALITY_LOW).
5. Unsupported crop handled gracefully without crash.
6. Low disease confidence properly categorized as uncertain.
7. Missing or corrupted model directory handled cleanly.
8. Invalid model registry lookup handled safely.
9. Gate 1 failure strictly prevents Gate 2 disease model execution.
10. Gate 1 success correctly routes to designated Gate 2 disease model.
"""

import os
import sys
import unittest
from PIL import Image
import numpy as np

sys.path.insert(0, os.path.abspath("."))
from gari_inference_engine import (
    GariInferenceEngine,
    validate_leaf_gate,
    categorize_confidence
)


class TestSprint61DualGatePipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = GariInferenceEngine()

        # Create or verify safe synthetic and real image fixtures
        # 1. Valid leaf fixture (Green botanical gradient with texture)
        cls.valid_leaf_path = "data/organized/Tomato/Tomato_healthy/000146ff-92a4-4db6-90ad-8fce2ae4fddd___GH_HL Leaf 259.1.JPG"
        if os.path.exists(cls.valid_leaf_path):
            cls.valid_leaf_img = Image.open(cls.valid_leaf_path).convert("RGB")
        else:
            # Synthetic botanical foliage fallback
            arr = np.zeros((224, 224, 3), dtype=np.uint8)
            arr[:, :, 1] = 180  # high green
            arr[:, :, 0] = 50   # low red
            arr[:, :, 2] = 40   # low blue
            cls.valid_leaf_img = Image.fromarray(arr)

        # 2. Non-leaf fixture (Solid blue synthetic block)
        blue_arr = np.zeros((224, 224, 3), dtype=np.uint8)
        blue_arr[:, :, 2] = 230
        cls.non_leaf_img = Image.fromarray(blue_arr)

        # 3. Low quality fixture (Extreme blur / solid dark)
        dark_arr = np.ones((100, 100, 3), dtype=np.uint8) * 8
        cls.low_quality_img = Image.fromarray(dark_arr)

    # 1. Valid Leaf passes Gate 1
    def test_01_valid_leaf_passes_gate_1(self):
        res = validate_leaf_gate(self.valid_leaf_img)
        self.assertEqual(res["status"], "LEAF_VALID")
        self.assertGreater(res["score"], 0.60)
        self.assertGreater(res["metrics"]["botanical_ratio"], 0.20)

    # 2. Non-leaf image rejected at Gate 1
    def test_02_non_leaf_image_rejected_at_gate_1(self):
        res = validate_leaf_gate(self.non_leaf_img)
        self.assertIn(res["status"], ("NOT_A_LEAF", "IMAGE_QUALITY_LOW"))
        self.assertLess(res["score"], 0.30)

    # 3. Ambiguous/uncertain crop returns CROP_UNCERTAIN
    def test_03_uncertain_crop_handled(self):
        # A synthetic green texture with no leaf morphology for detectors
        synthetic_texture = Image.new("RGB", (224, 224), color=(60, 140, 50))
        gate_res = self.engine.evaluate_crop_validation_gate(synthetic_texture)
        self.assertIn(gate_res["state"], ("CROP_UNCERTAIN", "MULTIPLE_CANDIDATES", "REJECTED_LOW_QUALITY"))
        self.assertFalse(gate_res["can_proceed_to_disease"])

    # 4. Low quality/blurry image rejected (IMAGE_QUALITY_LOW)
    def test_04_low_quality_blurry_image_rejected(self):
        res = validate_leaf_gate(self.low_quality_img)
        self.assertEqual(res["status"], "IMAGE_QUALITY_LOW")
        self.assertLess(res["metrics"]["mean_lum"], 16.0)

    # 5. Unsupported crop handled gracefully without crash
    def test_05_unsupported_crop_handled(self):
        res = self.engine.predict(self.valid_leaf_img, crop_id="exotic_unsupported_dragonfruit", mode="manual")
        self.assertFalse(res.get("success"))
        self.assertEqual(res.get("status"), "unsupported_crop")
        self.assertIsNone(res.get("disease_id"))

    # 6. Low disease confidence properly categorized as uncertain
    def test_06_low_confidence_disease_categorized(self):
        cat_low = categorize_confidence(0.35)
        self.assertEqual(cat_low["level"], "low")
        self.assertTrue(cat_low["is_uncertain"])

        cat_high = categorize_confidence(0.88)
        self.assertEqual(cat_high["level"], "high")
        self.assertFalse(cat_high["is_uncertain"])

    # 7. Missing or corrupted model directory handled cleanly
    def test_07_missing_or_corrupt_model_handled(self):
        with self.assertRaises(ValueError) as ctx:
            self.engine.load_model("non_existent_crop_model_dir")
        self.assertIn("Unknown or unsupported crop", str(ctx.exception))

    # 8. Invalid model registry lookup handled safely
    def test_08_invalid_model_registry_handled(self):
        entry = self.engine.get_model_entry("definitely_not_a_registered_crop")
        self.assertIsNone(entry)

    # 9. Gate 1 failure strictly prevents Gate 2 disease model execution
    def test_09_gate1_failure_prevents_gate2_disease_model(self):
        # When Gate 1 fails on non-leaf, predict() returns early without running disease model
        res = self.engine.predict(self.non_leaf_img, crop_id="Tomato", mode="manual")
        self.assertFalse(res["success"])
        self.assertIn(res["status"], ("not_a_leaf", "image_quality_low"))
        self.assertIsNone(res["disease_id"])
        self.assertIsNone(res["disease_name_vi"])
        self.assertEqual(res["confidence"], 0.0)

    # 10. Gate 1 success correctly routes to designated Gate 2 disease model
    def test_10_gate1_success_invokes_correct_gate2_model(self):
        res = self.engine.predict(self.valid_leaf_img, crop_id="Tomato", mode="manual")
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "OK")
        self.assertIsNotNone(res["disease_id"])
        self.assertIsNotNone(res["disease_name_vi"])
        self.assertGreater(res["confidence"], 0.50)
        self.assertEqual(res["validation"]["status"], "LEAF_VALID")


if __name__ == "__main__":
    unittest.main()

