"""
Unit Test Suite for Sprint 6.2 Evidence Foundation (gari_evidence_foundation.py)
Covers:
1. RFC 9562 UUIDv7 generation, version, variant, time extraction, and monotonicity.
2. Canonical payload serialization and SHA-256 fingerprint deduplication.
3. Decoupled reliability metrics (source_reliability, measurement_quality, model_confidence, verification_status).
4. Category-specific freshness policies (Weather 3h, Image 2h, User 24h, Sensor 1h, Meta 120d, History 21d).
5. Provenance privacy and data minimization (zero raw/hashed IP, network zones).
6. EvidenceItem database serialization and roundtrip hydration.
7. EvidenceBundle deduplication and idempotent ingestion.
"""

import time
import unittest
import uuid
from datetime import datetime, timezone, timedelta

from gari_evidence_foundation import (
    generate_uuid7,
    uuid7_timestamp_ms,
    canonicalize_payload,
    compute_evidence_fingerprint,
    evaluate_freshness,
    create_evidence_item,
    create_missing_evidence_item,
    EvidenceCategory,
    SourceType,
    ValidityStatus,
    VerificationStatus,
    ProvenanceRecord,
    EvidenceItem,
    EvidenceBundle,
    CATEGORY_FRESHNESS_LIMITS,
)


class TestSprint62EvidenceFoundation(unittest.TestCase):

    # ------------------------------------------------------------------------
    # 1. UUIDv7 Generation & Compatibility Tests
    # ------------------------------------------------------------------------

    def test_01_uuid7_version_and_variant(self):
        """Verify generated UUIDv7 conforms strictly to RFC 9562 version 7 and variant 1."""
        u_str = generate_uuid7()
        u = uuid.UUID(u_str)
        self.assertEqual(u.version, 7)
        self.assertEqual(u.variant, uuid.RFC_4122)
        self.assertEqual(len(u_str), 36)
        self.assertEqual(u_str.count("-"), 4)

    def test_02_uuid7_time_ordering_and_monotonicity(self):
        """Verify sequential UUIDv7 values are monotonically ordered by time."""
        uuids = []
        for _ in range(20):
            uuids.append(generate_uuid7())
            time.sleep(0.001)  # 1ms advance

        for i in range(len(uuids) - 1):
            self.assertLess(uuids[i], uuids[i + 1])

    def test_03_uuid7_timestamp_extraction(self):
        """Verify timestamp embedded in UUIDv7 matches actual system time."""
        before_ms = int(time.time() * 1000)
        u_str = generate_uuid7()
        after_ms = int(time.time() * 1000)

        extracted_ms = uuid7_timestamp_ms(u_str)
        self.assertGreaterEqual(extracted_ms, before_ms - 50)
        self.assertLessEqual(extracted_ms, after_ms + 50)

    # ------------------------------------------------------------------------
    # 2. Canonical Payload & Fingerprint Deduplication Tests
    # ------------------------------------------------------------------------

    def test_04_canonical_payload_serialization(self):
        """Verify payload keys are sorted and floats are rounded consistently."""
        payload_a = {"temperature_c": 24.5000001, "humidity_pct": 82.0, "details": {"b": 2, "a": 1}}
        payload_b = {"details": {"a": 1, "b": 2}, "humidity_pct": 82.0, "temperature_c": 24.5}

        canon_a = canonicalize_payload(payload_a)
        canon_b = canonicalize_payload(payload_b)
        self.assertEqual(canon_a, canon_b)
        self.assertIn('"details":{"a":1,"b":2}', canon_a)

    def test_05_fingerprint_generation_and_uniqueness(self):
        """Verify identical inputs yield identical fingerprints and changes diverge."""
        now = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
        payload = {"symptom": "lesion", "score": 0.85}
        canon = canonicalize_payload(payload)

        fp1 = compute_evidence_fingerprint(101, EvidenceCategory.IMAGE_LEAF_GATE, "gate1", now, canon)
        fp2 = compute_evidence_fingerprint(101, EvidenceCategory.IMAGE_LEAF_GATE, "gate1", now, canon)
        self.assertEqual(fp1, fp2)

        # Altering diagnosis_id changes fingerprint
        fp3 = compute_evidence_fingerprint(102, EvidenceCategory.IMAGE_LEAF_GATE, "gate1", now, canon)
        self.assertNotEqual(fp1, fp3)

        # Altering timestamp changes fingerprint
        now2 = datetime(2026, 11, 11, 12, 1, 0, tzinfo=timezone.utc)
        fp4 = compute_evidence_fingerprint(101, EvidenceCategory.IMAGE_LEAF_GATE, "gate1", now2, canon)
        self.assertNotEqual(fp1, fp4)

    # ------------------------------------------------------------------------
    # 3. Category-Specific Freshness Policy Tests
    # ------------------------------------------------------------------------

    def test_06_category_specific_freshness_evaluation(self):
        """Test granular freshness windows for weather (3h), image (2h), user (24h), etc."""
        ref_time = datetime(2026, 11, 11, 15, 0, 0, tzinfo=timezone.utc)

        # Weather: 2h ago is fresh; 3.5h ago is stale
        fresh_weather = ref_time - timedelta(hours=2.0)
        stale_weather = ref_time - timedelta(hours=3.5)
        self.assertTrue(evaluate_freshness(EvidenceCategory.WEATHER_CONTEXT, fresh_weather, ref_time)[0])
        is_fresh, reason = evaluate_freshness(EvidenceCategory.WEATHER_CONTEXT, stale_weather, ref_time)
        self.assertFalse(is_fresh)
        self.assertIn("exceeds category limit 3.0h", reason)

        # Image: 1.5h ago is fresh; 2.5h ago is stale
        fresh_img = ref_time - timedelta(hours=1.5)
        stale_img = ref_time - timedelta(hours=2.5)
        self.assertTrue(evaluate_freshness(EvidenceCategory.IMAGE_LEAF_GATE, fresh_img, ref_time)[0])
        is_fresh_img, _ = evaluate_freshness(EvidenceCategory.IMAGE_LEAF_GATE, stale_img, ref_time)
        self.assertFalse(is_fresh_img)

        # Farm Metadata: 90 days ago is fresh (within 120d crop cycle); 130 days is stale
        fresh_meta = ref_time - timedelta(days=90)
        stale_meta = ref_time - timedelta(days=130)
        self.assertTrue(evaluate_freshness(EvidenceCategory.FARM_METADATA, fresh_meta, ref_time)[0])
        is_fresh_meta, _ = evaluate_freshness(EvidenceCategory.FARM_METADATA, stale_meta, ref_time)
        self.assertFalse(is_fresh_meta)

    def test_07_historical_image_remains_available(self):
        """Verify an expired image is flagged STALE but remains fully preserved with reason."""
        ref_time = datetime(2026, 11, 11, 15, 0, 0, tzinfo=timezone.utc)
        old_time = ref_time - timedelta(hours=5.0)

        item = create_evidence_item(
            diagnosis_id=200,
            user_id=1,
            category=EvidenceCategory.IMAGE_LEAF_GATE,
            source_type=SourceType.ALGORITHM,
            source_reference="gate1_botanical",
            payload={"decision": "LEAF_VALID", "laplacian": 45.2},
            observed_at=old_time,
            reference_time=ref_time
        )
        self.assertEqual(item.validity_status, ValidityStatus.STALE)
        self.assertIsNotNone(item.invalid_or_missing_reason)
        self.assertIn("exceeds category limit", item.invalid_or_missing_reason)
        # Old item still exists and has its payload intact
        self.assertEqual(item.payload["decision"], "LEAF_VALID")

    # ------------------------------------------------------------------------
    # 4. Decoupled Reliability Metrics & Validation Tests
    # ------------------------------------------------------------------------

    def test_08_decoupled_reliability_metrics(self):
        """Verify source_reliability, measurement_quality, and model_confidence are stored separately."""
        now = datetime.now(timezone.utc)
        item = create_evidence_item(
            diagnosis_id=300,
            user_id=1,
            category=EvidenceCategory.MODEL_PREDICTION,
            source_type=SourceType.ML_MODEL,
            source_reference="models/Tomato/convnext_small:v2026.1",
            payload={"predicted_class": "Early Blight", "raw_score": 0.88},
            observed_at=now,
            measurement_quality=0.92,
            model_confidence=0.88,
            verification_status=VerificationStatus.ALGORITHMICALLY_VERIFIED
        )

        self.assertEqual(item.source_reliability, 0.70)  # ML_MODEL SLA
        self.assertEqual(item.measurement_quality, 0.92)
        self.assertEqual(item.model_confidence, 0.88)
        self.assertEqual(item.verification_status, VerificationStatus.ALGORITHMICALLY_VERIFIED)

        # Enforce invalid bounds raise ValueError
        with self.assertRaises(ValueError):
            EvidenceItem(
                evidence_id=generate_uuid7(),
                evidence_fingerprint="abc",
                diagnosis_id=300,
                user_id=1,
                category=EvidenceCategory.MODEL_PREDICTION,
                source_type=SourceType.ML_MODEL,
                source_reference="test",
                observed_at=now,
                collected_at=now,
                validity_status=ValidityStatus.VALID,
                verification_status=VerificationStatus.UNVERIFIED,
                source_reliability=1.5,  # Out of bounds
                measurement_quality=0.5,
                payload={},
                provenance=ProvenanceRecord(api_endpoint="/test", payload_sha256="123")
            )

    def test_09_explicit_missing_evidence_item(self):
        """Verify create_missing_evidence_item records explicit missing status without synthetic values."""
        item = create_missing_evidence_item(
            diagnosis_id=400,
            user_id=1,
            category=EvidenceCategory.WEATHER_CONTEXT,
            source_reference="open-meteo.com",
            missing_reason="Weather station API timed out after 3000ms."
        )
        self.assertEqual(item.validity_status, ValidityStatus.MISSING)
        self.assertEqual(item.measurement_quality, 0.0)
        self.assertIsNone(item.model_confidence)
        self.assertEqual(item.payload, {})
        self.assertEqual(item.invalid_or_missing_reason, "Weather station API timed out after 3000ms.")

    # ------------------------------------------------------------------------
    # 5. Provenance & Privacy Data Minimization Tests
    # ------------------------------------------------------------------------

    def test_10_provenance_data_minimization(self):
        """Verify provenance rejects IP addresses and records coarse network zone."""
        prov = ProvenanceRecord(
            api_endpoint="/api/v1/diagnoses",
            payload_sha256="abc123hash",
            client_app_version="GARI-Mobile/v2.1",
            network_zone="cellular_carrier"
        )
        self.assertEqual(prov.network_zone, "cellular_carrier")
        self.assertNotIn("ip", prov.to_dict())
        self.assertNotIn("ip_hash", prov.to_dict())

        # Invalid network zone defaults safely to 'unknown'
        prov_invalid = ProvenanceRecord(
            api_endpoint="/api/v1/diagnoses",
            payload_sha256="abc123hash",
            network_zone="192.168.1.100"  # Accidentally passing IP string
        )
        self.assertEqual(prov_invalid.network_zone, "unknown")

    # ------------------------------------------------------------------------
    # 6. Database Serialization & Roundtrip Hydration Tests
    # ------------------------------------------------------------------------

    def test_11_evidence_item_db_roundtrip(self):
        """Verify EvidenceItem converts to SQLite db_row and hydrades back losslessly."""
        now = datetime.now(timezone.utc)
        item = create_evidence_item(
            diagnosis_id=500,
            user_id=42,
            category=EvidenceCategory.USER_OBSERVATION,
            source_type=SourceType.USER_INPUT,
            source_reference="farmer_symptom_form",
            payload={"symptom": "yellowing", "affected_ratio": 0.15},
            observed_at=now,
            farm_id=10,
            organization_id=2
        )

        row = item.to_db_row()
        self.assertIsInstance(row["payload_json"], str)
        self.assertIsInstance(row["provenance_json"], str)

        hydrated = EvidenceItem.from_db_row(row)
        self.assertEqual(hydrated.evidence_id, item.evidence_id)
        self.assertEqual(hydrated.evidence_fingerprint, item.evidence_fingerprint)
        self.assertEqual(hydrated.diagnosis_id, item.diagnosis_id)
        self.assertEqual(hydrated.user_id, item.user_id)
        self.assertEqual(hydrated.farm_id, item.farm_id)
        self.assertEqual(hydrated.payload, item.payload)
        self.assertEqual(hydrated.category, item.category)

    # ------------------------------------------------------------------------
    # 7. EvidenceBundle Deduplication & Idempotency Tests
    # ------------------------------------------------------------------------

    def test_12_evidence_bundle_deduplication(self):
        """Verify adding identical items to EvidenceBundle performs idempotent no-op."""
        bundle = EvidenceBundle(diagnosis_id=600, user_id=1, organization_id=1)
        now = datetime.now(timezone.utc)

        item1 = create_evidence_item(
            diagnosis_id=600,
            user_id=1,
            category=EvidenceCategory.SENSOR_TELEMETRY,
            source_type=SourceType.SENSOR_API,
            source_reference="soil_tensiometer_01",
            payload={"soil_kpa": 32.4},
            observed_at=now
        )

        # First add: returns (True, item1)
        is_new, eff_item = bundle.add_item(item1)
        self.assertTrue(is_new)
        self.assertEqual(len(bundle), 1)

        # Create another item with exact same payload, time, and diagnosis_id
        item2 = create_evidence_item(
            diagnosis_id=600,
            user_id=1,
            category=EvidenceCategory.SENSOR_TELEMETRY,
            source_type=SourceType.SENSOR_API,
            source_reference="soil_tensiometer_01",
            payload={"soil_kpa": 32.4},
            observed_at=now
        )
        self.assertEqual(item1.evidence_fingerprint, item2.evidence_fingerprint)

        # Second add: returns (False, existing_item)
        is_new2, eff_item2 = bundle.add_item(item2)
        self.assertFalse(is_new2)
        self.assertEqual(eff_item2.evidence_id, item1.evidence_id)
        self.assertEqual(len(bundle), 1)  # Length did not increment!

    def test_13_bundle_filtering_helpers(self):
        """Verify helper queries for valid, missing, and stale items."""
        bundle = EvidenceBundle(diagnosis_id=700, user_id=1)
        now = datetime.now(timezone.utc)

        valid_item = create_evidence_item(
            700, 1, EvidenceCategory.IMAGE_LEAF_GATE, SourceType.ALGORITHM, "gate1",
            {"decision": "LEAF_VALID"}, observed_at=now
        )
        missing_item = create_missing_evidence_item(
            700, 1, EvidenceCategory.WEATHER_CONTEXT, "open-meteo", "offline"
        )
        stale_item = create_evidence_item(
            700, 1, EvidenceCategory.WEATHER_CONTEXT, SourceType.SENSOR_API, "station",
            {"temp": 25.0}, observed_at=now - timedelta(hours=5.0)
        )

        bundle.add_item(valid_item)
        bundle.add_item(missing_item)
        bundle.add_item(stale_item)

        self.assertEqual(len(bundle), 3)
        self.assertEqual(len(bundle.get_valid_items()), 1)
        self.assertEqual(len(bundle.get_missing_items()), 1)
        self.assertEqual(len(bundle.get_stale_items()), 1)
        self.assertEqual(len(bundle.get_by_category(EvidenceCategory.WEATHER_CONTEXT)), 2)


if __name__ == "__main__":
    unittest.main()

