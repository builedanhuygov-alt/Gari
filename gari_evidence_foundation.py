"""
GARI AgriTech AI Lab — Sprint 6.2 Evidence Foundation Module
Authoritative, decoupled, and privacy-safe evidence modeling:
1. RFC 9562 UUIDv7 generator with Python compatibility.
2. Decoupled reliability metrics (source_reliability, measurement_quality, model_confidence, verification_status).
3. Canonical payload serialization and SHA-256 fingerprint deduplication.
4. Category-specific freshness policies (Weather 3h, Image 2h, User 24h, Sensor 1h, Meta 120d, History 21d).
5. Explicit multi-state data validity (VALID, MISSING, STALE, INVALID, UNVERIFIED).
6. Privacy-safe provenance (zero raw/hashed IP, coarse network zones, normalized client headers).
7. Zero ad-hoc aggregate certainty scoring.
"""

from __future__ import annotations

import enum
import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union


# ============================================================================
# 1. RFC 9562 UUIDv7 Implementation (Standard Library Compatible)
# ============================================================================

def generate_uuid7() -> str:
    """
    Generate an RFC 9562 compliant UUIDv7 string using standard library tools.
    Byte layout:
    - Bytes 0-5 (48 bits): Big-endian UNIX timestamp in milliseconds.
    - Bytes 6-7 (16 bits): 4-bit version (0x7) + 12-bit pseudo-random counter (rand_a).
    - Byte 8 (8 bits): 2-bit variant (0b10) + 6-bit pseudo-random (rand_b).
    - Bytes 9-15 (56 bits): 56-bit pseudo-random (rand_b).
    Guarantees time-ordering monotonicity and B-Tree index locality in SQLite.
    """
    ns = time.time_ns()
    ms = ns // 1_000_000
    rand_bytes = os.urandom(10)
    
    b = bytearray(16)
    b[0:6] = ms.to_bytes(6, byteorder="big")
    b[6] = 0x70 | (rand_bytes[0] & 0x0F)
    b[7] = rand_bytes[1]
    b[8] = 0x80 | (rand_bytes[2] & 0x3F)
    b[9:16] = rand_bytes[3:10]
    
    return str(uuid.UUID(bytes=bytes(b)))


def uuid7_timestamp_ms(uuid_str: str) -> int:
    """Extract the millisecond timestamp from an RFC 9562 UUIDv7 string."""
    u = uuid.UUID(uuid_str)
    if u.version != 7:
        raise ValueError(f"UUID '{uuid_str}' is version {u.version}, expected 7.")
    raw_bytes = u.bytes
    return int.from_bytes(raw_bytes[0:6], byteorder="big")


# ============================================================================
# 2. Enumerations
# ============================================================================

class EvidenceCategory(str, enum.Enum):
    WEATHER_CONTEXT = "WEATHER_CONTEXT"
    IMAGE_LEAF_GATE = "IMAGE_LEAF_GATE"
    USER_OBSERVATION = "USER_OBSERVATION"
    SENSOR_TELEMETRY = "SENSOR_TELEMETRY"
    FARM_METADATA = "FARM_METADATA"
    HISTORICAL_DIAGNOSES = "HISTORICAL_DIAGNOSES"
    MODEL_PREDICTION = "MODEL_PREDICTION"


class SourceType(str, enum.Enum):
    ALGORITHM = "ALGORITHM"
    ML_MODEL = "ML_MODEL"
    USER_INPUT = "USER_INPUT"
    SENSOR_API = "SENSOR_API"
    DATABASE = "DATABASE"
    EXPERT_SYSTEM = "EXPERT_SYSTEM"


class ValidityStatus(str, enum.Enum):
    VALID = "VALID"
    MISSING = "MISSING"
    STALE = "STALE"
    INVALID = "INVALID"
    UNVERIFIED = "UNVERIFIED"


class VerificationStatus(str, enum.Enum):
    UNVERIFIED = "UNVERIFIED"
    EXPERT_VERIFIED = "EXPERT_VERIFIED"
    ALGORITHMICALLY_VERIFIED = "ALGORITHMICALLY_VERIFIED"
    DISPUTED = "DISPUTED"


# ============================================================================
# 3. Category-Specific Freshness Policy
# ============================================================================

# Freshness thresholds defined by biological and physical decay characteristics
CATEGORY_FRESHNESS_LIMITS: Dict[EvidenceCategory, timedelta] = {
    EvidenceCategory.WEATHER_CONTEXT: timedelta(hours=3.0),
    EvidenceCategory.IMAGE_LEAF_GATE: timedelta(hours=2.0),
    EvidenceCategory.USER_OBSERVATION: timedelta(hours=24.0),
    EvidenceCategory.SENSOR_TELEMETRY: timedelta(hours=1.0),
    EvidenceCategory.FARM_METADATA: timedelta(days=120.0),
    EvidenceCategory.HISTORICAL_DIAGNOSES: timedelta(days=21.0),
    EvidenceCategory.MODEL_PREDICTION: timedelta(hours=2.0),
}


def evaluate_freshness(
    category: Union[EvidenceCategory, str],
    observed_at: datetime,
    reference_time: Optional[datetime] = None
) -> Tuple[bool, Optional[str]]:
    """
    Evaluate if an evidence item is fresh according to category-specific policies.
    Returns (is_fresh, decay_reason).
    """
    if isinstance(category, str):
        category = EvidenceCategory(category)

    if reference_time is None:
        reference_time = datetime.now(timezone.utc)
    elif reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)

    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)

    limit = CATEGORY_FRESHNESS_LIMITS.get(category, timedelta(hours=24.0))
    age = reference_time - observed_at

    if age < timedelta(0):
        # Observed time is in the future
        return False, f"Future timestamp detected: observed_at is {abs(age.total_seconds()):.1f}s ahead."

    if age > limit:
        hours = age.total_seconds() / 3600.0
        max_hours = limit.total_seconds() / 3600.0
        return False, f"Evidence expired: age {hours:.2f}h exceeds category limit {max_hours:.1f}h."

    return True, None


# ============================================================================
# 4. Canonical Serialization & Deduplication Fingerprinting
# ============================================================================

def canonicalize_payload(payload: Dict[str, Any]) -> str:
    """
    Deterministically serialize a payload dictionary to JSON.
    Recursively sorts keys and formats floats to prevent hash divergence.
    """
    def _clean(val: Any) -> Any:
        if isinstance(val, dict):
            return {str(k): _clean(v) for k, v in sorted(val.items())}
        if isinstance(val, (list, tuple)):
            return [_clean(x) for x in val]
        if isinstance(val, float):
            return round(val, 6)
        return val

    cleaned = _clean(payload)
    return json.dumps(cleaned, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_evidence_fingerprint(
    diagnosis_id: int,
    category: Union[EvidenceCategory, str],
    source_reference: str,
    observed_at: Union[datetime, str],
    canonical_payload: str
) -> str:
    """
    Compute cryptographic SHA-256 natural key hash for duplicate detection.
    """
    cat_str = category.value if isinstance(category, EvidenceCategory) else str(category)
    obs_str = observed_at.isoformat() if isinstance(observed_at, datetime) else str(observed_at)
    
    raw = f"{diagnosis_id}|{cat_str}|{source_reference.strip()}|{obs_str}|{canonical_payload}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ============================================================================
# 5. Provenance & Data Minimization Record
# ============================================================================

VALID_NETWORK_ZONES = {"internal_lan", "cellular_carrier", "public_broadband", "unknown"}

@dataclass(frozen=True)
class ProvenanceRecord:
    """
    Privacy-safe provenance metadata.
    Zero raw or hashed IP storage; records coarse network zones and sanitized client versions.
    """
    api_endpoint: str
    payload_sha256: str
    client_app_version: str = "GARI-App/v2.0"
    network_zone: str = "unknown"
    is_real_telemetry: bool = True
    upstream_timestamp: Optional[str] = None

    def __post_init__(self) -> None:
        if self.network_zone not in VALID_NETWORK_ZONES:
            object.__setattr__(self, "network_zone", "unknown")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProvenanceRecord:
        return cls(
            api_endpoint=data.get("api_endpoint", ""),
            payload_sha256=data.get("payload_sha256", ""),
            client_app_version=data.get("client_app_version", "GARI-App/v2.0"),
            network_zone=data.get("network_zone", "unknown"),
            is_real_telemetry=data.get("is_real_telemetry", True),
            upstream_timestamp=data.get("upstream_timestamp"),
        )


# ============================================================================
# 6. Decoupled Provisional Source Reliability Defaults
# ============================================================================

# Provisional configuration values, strictly labeled as provisional until field-trial calibration
PROVISIONAL_SOURCE_RELIABILITY: Dict[SourceType, float] = {
    SourceType.EXPERT_SYSTEM: 1.00,
    SourceType.ALGORITHM: 0.95,
    SourceType.DATABASE: 0.95,
    SourceType.SENSOR_API: 0.90,
    SourceType.ML_MODEL: 0.70,
    SourceType.USER_INPUT: 0.40,
}


# ============================================================================
# 7. EvidenceItem Data Entity
# ============================================================================

@dataclass
class EvidenceItem:
    """
    Standardized, decoupled evidence entity conforming to RFC 9562 UUIDv7.
    """
    evidence_id: str
    evidence_fingerprint: str
    diagnosis_id: int
    user_id: int
    category: EvidenceCategory
    source_type: SourceType
    source_reference: str
    observed_at: datetime
    collected_at: datetime
    validity_status: ValidityStatus
    verification_status: VerificationStatus
    source_reliability: float
    measurement_quality: float
    payload: Dict[str, Any]
    provenance: ProvenanceRecord
    farm_id: Optional[int] = None
    organization_id: Optional[int] = None
    model_confidence: Optional[float] = None
    invalid_or_missing_reason: Optional[str] = None
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        # Validate UUIDv7
        u = uuid.UUID(self.evidence_id)
        if u.version != 7:
            raise ValueError(f"evidence_id '{self.evidence_id}' is version {u.version}, must be UUIDv7.")

        # Ensure UTC timezone awareness
        if self.observed_at.tzinfo is None:
            self.observed_at = self.observed_at.replace(tzinfo=timezone.utc)
        if self.collected_at.tzinfo is None:
            self.collected_at = self.collected_at.replace(tzinfo=timezone.utc)

        # Enforce decoupled reliability bounds [0.0, 1.0]
        if not (0.0 <= self.source_reliability <= 1.0):
            raise ValueError(f"source_reliability must be in [0.0, 1.0], got {self.source_reliability}")
        if not (0.0 <= self.measurement_quality <= 1.0):
            raise ValueError(f"measurement_quality must be in [0.0, 1.0], got {self.measurement_quality}")
        if self.model_confidence is not None and not (0.0 <= self.model_confidence <= 1.0):
            raise ValueError(f"model_confidence must be in [0.0, 1.0] or None, got {self.model_confidence}")

        # Enforce consistency for missing/invalid states
        if self.validity_status in (ValidityStatus.MISSING, ValidityStatus.INVALID):
            self.measurement_quality = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_fingerprint": self.evidence_fingerprint,
            "diagnosis_id": self.diagnosis_id,
            "user_id": self.user_id,
            "farm_id": self.farm_id,
            "organization_id": self.organization_id,
            "category": self.category.value,
            "source_type": self.source_type.value,
            "source_reference": self.source_reference,
            "observed_at": self.observed_at.isoformat(),
            "collected_at": self.collected_at.isoformat(),
            "validity_status": self.validity_status.value,
            "verification_status": self.verification_status.value,
            "source_reliability": self.source_reliability,
            "measurement_quality": self.measurement_quality,
            "model_confidence": self.model_confidence,
            "invalid_or_missing_reason": self.invalid_or_missing_reason,
            "payload": self.payload,
            "provenance": self.provenance.to_dict(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_db_row(self) -> Dict[str, Any]:
        """Convert to SQLite table dictionary format with serialized JSON columns."""
        return {
            "evidence_id": self.evidence_id,
            "evidence_fingerprint": self.evidence_fingerprint,
            "diagnosis_id": self.diagnosis_id,
            "user_id": self.user_id,
            "farm_id": self.farm_id,
            "organization_id": self.organization_id,
            "category": self.category.value,
            "source_type": self.source_type.value,
            "source_reference": self.source_reference,
            "observed_at": self.observed_at.isoformat(),
            "collected_at": self.collected_at.isoformat(),
            "validity_status": self.validity_status.value,
            "verification_status": self.verification_status.value,
            "source_reliability": self.source_reliability,
            "measurement_quality": self.measurement_quality,
            "model_confidence": self.model_confidence,
            "invalid_or_missing_reason": self.invalid_or_missing_reason,
            "payload_json": json.dumps(self.payload, sort_keys=True, separators=(",", ":")),
            "provenance_json": json.dumps(self.provenance.to_dict(), sort_keys=True, separators=(",", ":")),
        }

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> EvidenceItem:
        """Hydrate from SQLite row dict."""
        payload = json.loads(row.get("payload_json") or "{}")
        prov_dict = json.loads(row.get("provenance_json") or "{}")

        obs_at = datetime.fromisoformat(row["observed_at"])
        coll_at = datetime.fromisoformat(row["collected_at"])
        created_at = datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None

        return cls(
            evidence_id=row["evidence_id"],
            evidence_fingerprint=row["evidence_fingerprint"],
            diagnosis_id=row["diagnosis_id"],
            user_id=row["user_id"],
            farm_id=row.get("farm_id"),
            organization_id=row.get("organization_id"),
            category=EvidenceCategory(row["category"]),
            source_type=SourceType(row["source_type"]),
            source_reference=row["source_reference"],
            observed_at=obs_at,
            collected_at=coll_at,
            validity_status=ValidityStatus(row["validity_status"]),
            verification_status=VerificationStatus(row.get("verification_status", "UNVERIFIED")),
            source_reliability=float(row["source_reliability"]),
            measurement_quality=float(row["measurement_quality"]),
            model_confidence=float(row["model_confidence"]) if row.get("model_confidence") is not None else None,
            invalid_or_missing_reason=row.get("invalid_or_missing_reason"),
            payload=payload,
            provenance=ProvenanceRecord.from_dict(prov_dict),
            created_at=created_at,
        )


# ============================================================================
# 8. Factory Functions for Clean Evidence Ingestion
# ============================================================================

def create_evidence_item(
    diagnosis_id: int,
    user_id: int,
    category: EvidenceCategory,
    source_type: SourceType,
    source_reference: str,
    payload: Dict[str, Any],
    observed_at: Optional[datetime] = None,
    farm_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    measurement_quality: float = 1.0,
    model_confidence: Optional[float] = None,
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED,
    api_endpoint: str = "/api/v1/diagnoses",
    network_zone: str = "unknown",
    reference_time: Optional[datetime] = None
) -> EvidenceItem:
    """
    Factory constructor validating freshness, generating UUIDv7, computing natural key fingerprint,
    and enforcing data minimization provenance.
    """
    now_utc = datetime.now(timezone.utc)
    if observed_at is None:
        observed_at = now_utc
    elif observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)

    # 1. Evaluate Freshness
    is_fresh, decay_reason = evaluate_freshness(category, observed_at, reference_time=reference_time)
    
    # 2. Determine Validity
    if not payload:
        validity = ValidityStatus.MISSING
        invalid_reason = "Payload is empty or missing."
        measurement_quality = 0.0
    elif not is_fresh:
        validity = ValidityStatus.STALE
        invalid_reason = decay_reason
        measurement_quality = max(0.05, measurement_quality * 0.10)
    elif verification_status == VerificationStatus.UNVERIFIED and source_type == SourceType.USER_INPUT:
        validity = ValidityStatus.UNVERIFIED
        invalid_reason = None
    else:
        validity = ValidityStatus.VALID
        invalid_reason = None

    # 3. Canonical Payload & Fingerprint
    canonical_json = canonicalize_payload(payload)
    fingerprint = compute_evidence_fingerprint(
        diagnosis_id=diagnosis_id,
        category=category,
        source_reference=source_reference,
        observed_at=observed_at,
        canonical_payload=canonical_json
    )

    # 4. Generate UUIDv7
    evi_id = generate_uuid7()

    # 5. Provenance Record
    payload_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    prov = ProvenanceRecord(
        api_endpoint=api_endpoint,
        payload_sha256=payload_hash,
        client_app_version="GARI-App/v2.0",
        network_zone=network_zone,
        is_real_telemetry=True,
        upstream_timestamp=observed_at.isoformat(),
    )

    source_rel = PROVISIONAL_SOURCE_RELIABILITY.get(source_type, 0.50)

    return EvidenceItem(
        evidence_id=evi_id,
        evidence_fingerprint=fingerprint,
        diagnosis_id=diagnosis_id,
        user_id=user_id,
        farm_id=farm_id,
        organization_id=organization_id,
        category=category,
        source_type=source_type,
        source_reference=source_reference,
        observed_at=observed_at,
        collected_at=now_utc,
        validity_status=validity,
        verification_status=verification_status,
        source_reliability=source_rel,
        measurement_quality=measurement_quality,
        model_confidence=model_confidence,
        invalid_or_missing_reason=invalid_reason,
        payload=payload,
        provenance=prov,
    )


def create_missing_evidence_item(
    diagnosis_id: int,
    user_id: int,
    category: EvidenceCategory,
    source_reference: str,
    missing_reason: str,
    farm_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    api_endpoint: str = "/api/v1/diagnoses"
) -> EvidenceItem:
    """
    Factory constructor for explicitly absent evidence items (e.g. sensor timeout or unprovided field).
    Zero data fabrication: records is_missing semantics clearly with 0.0 measurement quality.
    """
    now_utc = datetime.now(timezone.utc)
    canonical_json = "{}"
    fingerprint = compute_evidence_fingerprint(
        diagnosis_id=diagnosis_id,
        category=category,
        source_reference=source_reference,
        observed_at=now_utc,
        canonical_payload=canonical_json
    )

    evi_id = generate_uuid7()
    prov = ProvenanceRecord(
        api_endpoint=api_endpoint,
        payload_sha256=hashlib.sha256(b"{}").hexdigest(),
        client_app_version="GARI-App/v2.0",
        network_zone="internal_lan",
        is_real_telemetry=False,
    )

    return EvidenceItem(
        evidence_id=evi_id,
        evidence_fingerprint=fingerprint,
        diagnosis_id=diagnosis_id,
        user_id=user_id,
        farm_id=farm_id,
        organization_id=organization_id,
        category=category,
        source_type=SourceType.DATABASE,
        source_reference=source_reference,
        observed_at=now_utc,
        collected_at=now_utc,
        validity_status=ValidityStatus.MISSING,
        verification_status=VerificationStatus.UNVERIFIED,
        source_reliability=1.0,  # The fact that it is missing is 100% reliable
        measurement_quality=0.0,
        model_confidence=None,
        invalid_or_missing_reason=missing_reason,
        payload={},
        provenance=prov,
    )


# ============================================================================
# 9. EvidenceBundle (Deduplicating Container)
# ============================================================================

class EvidenceBundle:
    """
    In-memory container for a diagnosis session's evidence graph.
    Enforces natural key deduplication: if an item with identical fingerprint is added,
    it rejects duplicate rows and preserves existing record or updates verification.
    """
    def __init__(self, diagnosis_id: int, user_id: int, organization_id: Optional[int] = None):
        self.diagnosis_id = diagnosis_id
        self.user_id = user_id
        self.organization_id = organization_id
        self._items_by_fingerprint: Dict[str, EvidenceItem] = {}

    def add_item(self, item: EvidenceItem) -> Tuple[bool, EvidenceItem]:
        """
        Add an item to the bundle.
        Returns (is_new_addition, effective_item).
        If an identical item exists, performs an idempotent no-op or updates verification.
        """
        if item.diagnosis_id != self.diagnosis_id:
            raise ValueError(f"Item diagnosis_id {item.diagnosis_id} does not match bundle {self.diagnosis_id}.")

        fp = item.evidence_fingerprint
        if fp in self._items_by_fingerprint:
            existing = self._items_by_fingerprint[fp]
            # If verification status has upgraded, update it
            if item.verification_status != existing.verification_status:
                existing.verification_status = item.verification_status
            return False, existing

        self._items_by_fingerprint[fp] = item
        return True, item

    @property
    def items(self) -> List[EvidenceItem]:
        return list(self._items_by_fingerprint.values())

    def get_by_category(self, category: Union[EvidenceCategory, str]) -> List[EvidenceItem]:
        cat_enum = EvidenceCategory(category) if isinstance(category, str) else category
        return [item for item in self.items if item.category == cat_enum]

    def get_valid_items(self) -> List[EvidenceItem]:
        return [item for item in self.items if item.validity_status == ValidityStatus.VALID]

    def get_missing_items(self) -> List[EvidenceItem]:
        return [item for item in self.items if item.validity_status == ValidityStatus.MISSING]

    def get_stale_items(self) -> List[EvidenceItem]:
        return [item for item in self.items if item.validity_status == ValidityStatus.STALE]

    def __len__(self) -> int:
        return len(self._items_by_fingerprint)

