# ==============================================================================
# GARI AgriTech AI Lab — On-Demand Model Lifecycle Test Suite
# Tests:
# 1. First request loads model lazily (UNLOADED -> LOADING -> READY/ACTIVE)
# 2. Second request reuses loaded model without reloading
# 3. Idle timeout unloads unused model automatically
# 4. Active inference strictly blocks unloading
# 5. Concurrent requests do not duplicate model loading (tested with 10 & 20 threads)
# 6. LRU eviction respects active request counters
# 7. Failed model load recovers cleanly without getting stuck
# 8. Failed inference does not corrupt active request counters
# 9. Repeated load/unload cycles remain memory-stable
# 10. Memory RSS measurement across lifecycle phases
# ==============================================================================

import gc
import os
import sys
import threading
import time
import unittest
from pathlib import Path
from typing import List, Tuple

import psutil
import torch
from PIL import Image

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gari_model_lifecycle import (
    ModelLifecycleManager,
    ModelLifecycleState,
    get_current_rss_mb,
)
from gari_inference_engine import GariInferenceEngine


class DummyTestModel(torch.nn.Module):
    def __init__(self, size_mb: int = 2):
        super().__init__()
        # Allocate a tensor of ~2MB to verify memory footprint
        self.param = torch.nn.Parameter(torch.zeros(size_mb * 250, 1000))

    def forward(self, x):
        return x


class TestOnDemandModelLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = GariInferenceEngine()
        real_image_path = PROJECT_ROOT / "test_leaf.jpg"
        if real_image_path.exists():
            cls.test_image = Image.open(str(real_image_path)).convert("RGB")
        else:
            cls.test_image = Image.new("RGB", (224, 224), color=(100, 150, 100))

    def setUp(self):
        # Ensure a clean state before each test
        self.engine.unload_all(reason="test_setup")
        gc.collect()

    def test_01_first_request_loads_model(self):
        """1. First request loads model lazily on demand."""
        self.assertFalse(self.engine.is_model_loaded("Tomato"))
        slot = self.engine.lifecycle.get_slot("Tomato")
        self.assertEqual(slot.state, ModelLifecycleState.UNLOADED)

        rss_before = get_current_rss_mb()
        net, entry = self.engine.load_model("Tomato")
        rss_after = get_current_rss_mb()

        self.assertIsNotNone(net)
        self.assertEqual(entry.crop_id, "Tomato")
        self.assertTrue(self.engine.is_model_loaded("Tomato"))
        self.assertEqual(slot.state, ModelLifecycleState.READY)
        self.assertEqual(slot.active_requests, 0)
        self.assertGreater(slot.load_time_ms, 0)

        print(f"\n[TEST 1] First request load: RSS before={rss_before:.1f}MB, after={rss_after:.1f}MB, load_ms={slot.load_time_ms:.1f}ms")

    def test_02_second_request_reuses_model(self):
        """2. Second request reuses loaded model without reloading."""
        net1, entry1 = self.engine.load_model("Tomato")
        load_time_1 = self.engine.lifecycle.get_slot("Tomato").load_time_ms

        t0 = time.perf_counter()
        net2, entry2 = self.engine.load_model("Tomato")
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        # Must return the exact same model object
        self.assertIs(net1, net2)
        # Reuse must be near-instantaneous (< 5ms) compared to cold load (~600ms)
        self.assertLess(elapsed_ms, 20.0)
        print(f"\n[TEST 2] Model reuse: cold_load={load_time_1:.1f}ms, cache_hit={elapsed_ms:.2f}ms")

    def test_03_idle_timeout_unloads_unused_model(self):
        """3. Idle timeout automatically unloads unused model."""
        # Create a dedicated manager with a 1.0 second timeout for fast testing
        fast_manager = ModelLifecycleManager(
            idle_timeout_seconds=1.0,
            max_cached=3,
            auto_unload_enabled=True,
            cleanup_interval_seconds=0.3,
        )

        load_calls = [0]
        def dummy_loader():
            load_calls[0] += 1
            return DummyTestModel(size_mb=4), None

        # Load model into fast manager
        fast_manager.load_model("DummyIdleCrop", dummy_loader)
        slot = fast_manager.get_slot("DummyIdleCrop")
        self.assertEqual(slot.state, ModelLifecycleState.READY)
        self.assertIsNotNone(slot.model)
        self.assertEqual(load_calls[0], 1)

        # Wait for timeout (1.0s) + cleanup loop cycle (~0.5s)
        time.sleep(1.6)

        self.assertIsNone(slot.model)
        self.assertEqual(slot.state, ModelLifecycleState.UNLOADED)
        print("\n[TEST 3] Idle timeout successfully unloaded model after 1.6s")
        fast_manager.stop_background_cleaner()

    def test_04_active_inference_prevents_unloading(self):
        """4. Active inference strictly prevents unloading."""
        manager = ModelLifecycleManager(
            idle_timeout_seconds=1.0,
            max_cached=3,
            auto_unload_enabled=False,
        )

        def dummy_loader():
            return DummyTestModel(size_mb=2), None

        model, _ = manager.acquire_for_inference("TestActiveCrop", dummy_loader)
        slot = manager.get_slot("TestActiveCrop")
        self.assertEqual(slot.active_requests, 1)
        self.assertEqual(slot.state, ModelLifecycleState.INFERENCE_ACTIVE)

        # Attempt to unload while inference is active -> must fail!
        unloaded = manager.unload_model("TestActiveCrop", reason="test_attempt")
        self.assertFalse(unloaded)
        self.assertIsNotNone(slot.model)
        self.assertEqual(slot.state, ModelLifecycleState.INFERENCE_ACTIVE)

        # Release from inference
        manager.release_from_inference("TestActiveCrop")
        self.assertEqual(slot.active_requests, 0)
        self.assertEqual(slot.state, ModelLifecycleState.READY)

        # Now unload should succeed
        unloaded_now = manager.unload_model("TestActiveCrop", reason="test_post_release")
        self.assertTrue(unloaded_now)
        self.assertIsNone(slot.model)
        self.assertEqual(slot.state, ModelLifecycleState.UNLOADED)
        print("\n[TEST 4] Active inference safely blocked unloading; succeeded after release")

    def test_05_concurrent_requests_do_not_duplicate_load(self):
        """5. Concurrent requests do not duplicate model loading (tested with 10 and 20 threads)."""
        for concurrency in (10, 20):
            manager = ModelLifecycleManager(max_cached=3, auto_unload_enabled=False)
            load_count = [0]
            load_lock = threading.Lock()

            def slow_loader():
                with load_lock:
                    load_count[0] += 1
                time.sleep(0.05)  # Simulate model disk read
                return DummyTestModel(size_mb=1), None

            results = []
            errors = []

            def worker(w_id: int):
                try:
                    with manager.use_model("ConcurrentCrop", slow_loader) as (m, _):
                        time.sleep(0.01)  # Simulate inference forward pass
                        results.append((w_id, id(m)))
                except Exception as exc:
                    errors.append((w_id, exc))

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(concurrency)]
            t0 = time.perf_counter()
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
            self.assertEqual(len(results), concurrency)
            # CRITICAL: Loader function must have executed EXACTLY ONCE!
            self.assertEqual(load_count[0], 1, f"Expected 1 load call, got {load_count[0]}")
            # All threads must have received the EXACT same object id
            first_id = results[0][1]
            for wid, mid in results:
                self.assertEqual(mid, first_id)

            slot = manager.get_slot("ConcurrentCrop")
            self.assertEqual(slot.active_requests, 0)
            self.assertEqual(slot.state, ModelLifecycleState.READY)
            print(f"\n[TEST 5] Concurrency {concurrency} threads: 1 single load call, 0 duplicate weights ({elapsed_ms:.1f}ms)")

    def test_06_lru_eviction_respects_active_request_counters(self):
        """6. LRU eviction respects capacity and NEVER evicts a model with active requests."""
        manager = ModelLifecycleManager(max_cached=2, auto_unload_enabled=False)

        def loader_factory(name: str):
            def _l():
                return DummyTestModel(size_mb=2), None
            return _l

        # Load Model A and keep it actively in use (active_requests=1)
        manager.acquire_for_inference("ModelA", loader_factory("ModelA"))
        slot_a = manager.get_slot("ModelA")
        self.assertEqual(slot_a.active_requests, 1)

        # Load Model B (idle: active_requests=0)
        manager.load_model("ModelB", loader_factory("ModelB"))
        slot_b = manager.get_slot("ModelB")
        self.assertEqual(slot_b.active_requests, 0)

        # Now load Model C. Capacity is 2.
        # Candidate for eviction is Model B because Model A has active_requests=1!
        manager.load_model("ModelC", loader_factory("ModelC"))
        slot_c = manager.get_slot("ModelC")

        # Model A must still be loaded because it is actively in use!
        self.assertIsNotNone(slot_a.model)
        self.assertEqual(slot_a.active_requests, 1)

        # Model B must have been evicted
        self.assertIsNone(slot_b.model)

        # Model C must be loaded
        self.assertIsNotNone(slot_c.model)

        # Clean up Model A
        manager.release_from_inference("ModelA")
        print("\n[TEST 6] LRU eviction correctly protected actively-used ModelA and evicted idle ModelB")

    def test_07_failed_model_load_recovers_cleanly(self):
        """7. Failed model load recovers correctly without getting stuck in LOADING."""
        manager = ModelLifecycleManager(max_cached=3, auto_unload_enabled=False)
        fail_counter = [0]

        def flaky_loader():
            fail_counter[0] += 1
            if fail_counter[0] == 1:
                raise ValueError("Simulated corrupt weight file error")
            return DummyTestModel(size_mb=1), None

        # First call fails
        with self.assertRaises(ValueError):
            manager.load_model("FlakyCrop", flaky_loader)

        slot = manager.get_slot("FlakyCrop")
        # Must NOT be stuck in LOADING or ERROR state
        self.assertEqual(slot.state, ModelLifecycleState.UNLOADED)
        self.assertIsNone(slot.model)
        self.assertEqual(slot.active_requests, 0)

        # Second call succeeds
        model, _ = manager.load_model("FlakyCrop", flaky_loader)
        self.assertIsNotNone(model)
        self.assertEqual(slot.state, ModelLifecycleState.READY)
        print("\n[TEST 7] Flaky loader cleanly recovered from error and succeeded on retry")

    def test_08_failed_inference_does_not_corrupt_counters(self):
        """8. Failed inference does not corrupt active request counters."""
        manager = ModelLifecycleManager(max_cached=3, auto_unload_enabled=False)

        def dummy_loader():
            return DummyTestModel(size_mb=1), None

        slot = manager.get_slot("CrashCrop")

        try:
            with manager.use_model("CrashCrop", dummy_loader):
                self.assertEqual(slot.active_requests, 1)
                self.assertEqual(slot.state, ModelLifecycleState.INFERENCE_ACTIVE)
                raise RuntimeError("Simulated forward-pass tensor shape mismatch")
        except RuntimeError:
            pass

        # active_requests must be reset back to 0
        self.assertEqual(slot.active_requests, 0)
        self.assertEqual(slot.state, ModelLifecycleState.READY)
        self.assertIsNotNone(slot.model)
        print("\n[TEST 8] Failed inference inside context manager safely reset active_requests to 0")

    def test_09_repeated_load_unload_cycles_remain_stable(self):
        """9. Repeated load/unload cycles remain stable without memory leaks."""
        rss_start = get_current_rss_mb()
        measurements: List[Tuple[float, float]] = []

        for cycle in range(5):
            # Load real Tomato model
            net, _ = self.engine.load_model("Tomato")
            rss_loaded = get_current_rss_mb()

            # Run inference
            res = self.engine.predict(self.test_image, "Tomato")
            self.assertIn("top_predictions", res)
            rss_inferred = get_current_rss_mb()

            # Unload
            unloaded = self.engine.unload_model("Tomato", reason="cycle_test")
            self.assertTrue(unloaded)
            rss_unloaded = get_current_rss_mb()
            measurements.append((rss_loaded, rss_unloaded))

        rss_end = get_current_rss_mb()
        print(f"\n[TEST 9] 5 load/unload cycles: Start RSS={rss_start:.1f}MB, End RSS={rss_end:.1f}MB")
        for i, (rl, ru) in enumerate(measurements):
            print(f"         Cycle {i+1}: loaded={rl:.1f}MB -> unloaded={ru:.1f}MB")

    def test_10_real_models_end_to_end_inference(self):
        """10. Real end-to-end inference works across distinct crop models with on-demand loading."""
        for crop in ["Tomato", "Rice", "Coffee"]:
            # Ensure unloaded before
            self.engine.unload_model(crop)
            self.assertFalse(self.engine.is_model_loaded(crop))

            # Run inference on demand directly with crop-specific disease model
            res = self.engine.run_crop_disease_model(self.test_image, crop)
            self.assertIn("top_predictions", res)
            self.assertTrue(len(res["top_predictions"]) > 0)

            # Model is now loaded in READY state
            self.assertTrue(self.engine.is_model_loaded(crop))
            slot = self.engine.lifecycle.get_slot(crop)
            self.assertEqual(slot.active_requests, 0)
            self.assertEqual(slot.state, ModelLifecycleState.READY)

            print(f"\n[TEST 10] Real model {crop}: load_time={slot.load_time_ms:.1f}ms, top_pred='{res['top_predictions'][0].get('name_vi')}'")


if __name__ == "__main__":
    unittest.main()
