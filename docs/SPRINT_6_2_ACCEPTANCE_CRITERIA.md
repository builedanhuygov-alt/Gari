# GARI AGRITECH AI LAB — SPRINT 6.2 ACCEPTANCE CRITERIA
## Automated Verification Specifications & Final Gate Gherkin Scenarios

**Document Reference:** `docs/SPRINT_6_2_ACCEPTANCE_CRITERIA.md`  
**Phase:** Phase 6 — Product Evolution  
**Sprint:** 6.2 — Final Design Gate Hardening  
**Baseline Git Commit:** `2318ee75`  
**Status:** FINAL DESIGN GATE COMPLIANT (Pre-Implementation)  

---

## 1. Specification Overview

This document specifies the formal Acceptance Criteria (AC) for Sprint 6.2 using Gherkin-style specification scenarios (`Given`, `When`, `Then`). All scenarios will be implemented as automated unit and integration tests during the implementation phase.

---

## 2. Hardened Feature Acceptance Criteria

### Feature 1: Evidence Ingestion, UUIDv7 & Deduplication

```gherkin
Feature: Evidence Ingestion, UUIDv7 and Idempotent Deduplication
  As the GARI Agronomic Decision System
  I want to collect heterogeneous evidence with RFC 9562 UUIDv7 identifiers and cryptographic deduplication
  So that evidence items are strictly unique, time-ordered, and idempotent

  Scenario: Generating time-ordered UUIDv7 evidence identifier
    Given an image passes Gate 1 with status "LEAF_VALID"
    When the EvidenceAggregator normalizes the evidence
    Then an EvidenceItem is generated with evidence_id conforming to RFC 9562 UUIDv7
    And the first 48 bits of the UUID match the current UTC millisecond timestamp
    And the database constraint PRIMARY KEY enforces uniqueness

  Scenario: Idempotent handling of duplicate evidence ingestion
    Given an EvidenceItem with evidence_fingerprint "sha256_canonical_hash_abc" exists for diagnosis_id 100
    When an identical evidence payload is submitted for diagnosis_id 100
    Then the system detects the unique constraint match on (diagnosis_id, evidence_fingerprint)
    And performs an idempotent no-op returning the existing evidence_id
    And zero duplicate database rows are created
```

---

### Feature 2: Decoupled Evidence Reliability Metrics

```gherkin
Feature: Decoupled Epistemic Reliability Metrics
  As an agronomist and decision system auditor
  I want evidence reliability separated into source reliability, measurement quality, model confidence, and verification status
  So that decisions are never distorted by uncalibrated aggregate certainty scores

  Scenario: Storing decoupled metrics without ad-hoc aggregation
    Given an image prediction from ConvNeXt-Small with Softmax score 0.82
    And the image has Laplacian variance 65.0 (good quality)
    When the EvidenceAggregator records the model prediction item
    Then source_reliability is set to 0.70 (automated ML channel SLA)
    And measurement_quality is set to 0.85 (normalized image sharpness)
    And model_confidence is set to 0.82 (raw Softmax score)
    And verification_status is set to "ALGORITHMICALLY_VERIFIED"
    And zero aggregate "Agronomic Certainty" percentage is computed or output
```

---

### Feature 3: Category-Specific Freshness Policy

```gherkin
Feature: Granular Freshness Verification by Evidence Category
  As the GARI Evidence Engine
  I want freshness lifetimes tailored to physical and biological decay rates
  So that decisions reflect real-world field conditions

  Scenario: Ingesting weather data older than 3 hours
    Given weather observation data was recorded 3.5 hours ago
    When the EvidenceAggregator validates the weather evidence
    Then validity_status is set to "STALE"
    And measurement_quality is discounted to 0.10
    And invalid_or_missing_reason records "weather_older_than_3h"
    And the system refuses to use this reading to trigger microclimate alerts

  Scenario: Ingesting image captured more than 2 hours ago
    Given a leaf image was photographed 2.5 hours prior to upload
    When the EvidenceAggregator validates the image evidence
    Then validity_status is set to "STALE"
    And the system requires the farmer to submit a fresh in-situ field photo

  Scenario: Preserving farm metadata across the crop cycle
    Given farm plot variety and planting date were recorded 45 days ago within the active cycle
    When the EvidenceAggregator validates the farm metadata
    Then validity_status remains "VALID"
    And the data is accepted as season-invariant agronomic context
```

---

### Feature 4: Provenance Privacy & Data Minimization

```gherkin
Feature: Privacy-Safe Provenance Storage
  As a compliance officer and privacy engineer
  I want to prevent persistent storage of raw or hashed IP addresses
  So that farmer network identities are protected against rainbow table deanonymization

  Scenario: Enforcing data minimization on network provenance
    Given a client diagnosis request originating from an external IP address
    When the EvidenceAggregator records the provenance metadata
    Then raw IP addresses are NOT stored in the database
    And hashed IP addresses are NOT stored in the database
    And provenance records coarse network_zone as "internal_lan", "cellular_carrier", or "public_broadband"
    And client user-agent is normalized to client_app_version stripping tracking tokens
```

---

### Feature 5: Conditioned Agronomic Safety in URGENT_REVIEW

```gherkin
Feature: Conditioned Agronomic Safety and Non-Blanket Recommendations
  As a responsible agricultural platform
  I want all emergency guidance to be biologically conditioned and justified
  So that farmers are never given harmful blanket farming directives

  Scenario: Prohibiting unconditioned blanket irrigation shutdown
    Given a diagnosis evaluated as "URGENT_REVIEW" for Tomato Late Blight (foliar fungus)
    When the AgronomicDecisionEngine generates cultural guidance
    Then the guidance conditions overhead watering advice: "Applicable only to foliar fungal pathogens"
    And the guidance includes explicit contraindications: "Maintain scheduled drip irrigation to prevent drought shock"
    And the guidance includes biological rationale: "Prevents water splash spore dissemination"

  Scenario: Prohibiting chemical dosage prescriptions
    Given an agronomic recommendation in state "SUSPECTED" or "URGENT_REVIEW"
    When the AgronomicDecisionEngine generates chemical safety advice
    Then approved active ingredients are cited by generic name (e.g., Copper Hydroxide)
    And the text contains zero volumetric or weight dosages
    And an automated regex assertion confirms no occurrences of "ml/l", "g/l", "kg/ha", or "phun X ml"
    And a pre-harvest interval (PHI) and label compliance warning is attached
```

---

### Feature 6: Safe Migration & Data-Preserving Rollback

```gherkin
Feature: Safe Database Migration and Rollback Verification
  As a Site Reliability Engineer
  I want to distinguish schema rollback from data-preserving rollback
  So that production business records are never deleted by DROP TABLE scripts

  Scenario: Executing data-preserving rollback when business records exist
    Given diagnostic_triage_records contains operational farmer records
    When an operational rollback is requested
    Then the system toggles feature flag ENABLE_SPRINT_6_2_TRIAGE = False
    And existing tables and historical audit rows are preserved intact without DROP TABLE
    And the API gracefully routes diagnosis traffic through legacy endpoints
```

---

## 3. Automated Test Suite Plan for Implementation Phase

During the Sprint 6.2 implementation phase, the following automated test suites will be constructed:

1. `tests/test_sprint6_2_evidence_aggregator.py`:
   - Validates RFC 9562 UUIDv7 generation and B-Tree time ordering.
   - Tests SHA-256 fingerprint deduplication and idempotent ingestion.
   - Validates decoupled metrics (`source_reliability`, `measurement_quality`, `model_confidence`, `verification_status`).
   - Verifies category freshness policies across all 6 categories.
2. `tests/test_sprint6_2_privacy_provenance.py`:
   - Verifies zero raw IP and zero hashed IP in stored payloads.
   - Tests user-agent normalization and URI secret stripping.
3. `tests/test_sprint6_2_triage_engine.py`:
   - Tests state transitions across all 4 triage states with entry/exit checks.
   - Tests contradiction handling matrix (environmental, symptom, classifier divergence).
   - Verifies distinction between `URGENT_REVIEW` and outbreak declaration.
4. `tests/test_sprint6_2_decision_engine.py`:
   - Validates all 7 mandatory decision output dimensions.
   - Enforces conditioned recommendations (conditions, contraindications, rationale).
   - Scans output with regex to verify zero chemical dosage prescriptions.
5. `tests/test_sprint6_2_migration_safety.py`:
   - Executes staging backup, migration DDL, foreign key check, integrity check, and rollback drills.
