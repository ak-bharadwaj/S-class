"""RFC 8785 (JSON Canonicalization Scheme / JCS) Serializer and SHA-256 Engine.

Integrates the standard-compliant, mature, permissively licensed rfc8785 library
for deterministic JSON Canonicalization Scheme (JCS) encoding:
1. Canonical JSON domain: null, bool, finite numbers (int, float), str, ordered arrays (list, tuple),
   and mappings (dict, MappingProxyType, Mapping) with string keys.
2. Explicit S-Class domain types: Enum instances and pure domain model dataclasses.
3. Strict Fail-Closed Input Boundary:
   - Sets and frozensets are REJECTED with CanonicalSerializationError (no non-deterministic conversion).
   - Generic __dict__ and str(obj) fallbacks are REMOVED. Unsupported objects fail closed.
4. Cryptographic SHA-256 event digest computation and verification over canonical preimage bytes.
"""

import dataclasses
from enum import Enum
import hashlib
import math
from typing import Any, Mapping
from types import MappingProxyType
import rfc8785

from domain.models import EventEnvelope
from domain.types import EventType
from events.exceptions import CanonicalSerializationError, DigestMismatchError


def _prepare_for_rfc8785(obj: Any) -> Any:
    """Strictly validates and converts supported canonical JSON domain types into primitives for RFC 8785.
    
    Supported domain:
    - None (null)
    - bool (true/false)
    - int, float (finite numbers; NaN and Inf fail closed)
    - str (string)
    - Enum (converted to .value string)
    - list, tuple (ordered arrays)
    - dict, MappingProxyType, Mapping (mappings with string keys)
    - Pure S-Class domain model dataclasses (converted to dict of fields)
    
    Any other type (including set, frozenset, arbitrary custom classes, generator, etc.) fails closed.
    """
    if obj is None:
        return None
    elif isinstance(obj, bool):
        return obj
    elif isinstance(obj, (int, float)):
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            raise CanonicalSerializationError(f"Non-finite float value '{obj}' cannot be canonicalized under RFC 8785.")
        return obj
    elif isinstance(obj, str):
        return obj
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, (list, tuple)):
        return [_prepare_for_rfc8785(x) for x in obj]
    elif isinstance(obj, (dict, MappingProxyType, Mapping)):
        out = {}
        for k, v in obj.items():
            if not isinstance(k, str):
                raise CanonicalSerializationError(f"Mapping key must be a string, got '{type(k).__name__}'.")
            out[k] = _prepare_for_rfc8785(v)
        return out
    elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        module_name = getattr(obj.__class__, "__module__", "")
        if "domain." in module_name or module_name == "domain" or "models" in module_name:
            fields_dict = {f.name: getattr(obj, f.name) for f in dataclasses.fields(obj)}
            return _prepare_for_rfc8785(fields_dict)
        else:
            raise CanonicalSerializationError(f"Unsupported custom dataclass: '{obj.__class__.__name__}' from module '{module_name}'.")
    else:
        raise CanonicalSerializationError(
            f"Unsupported canonical serialization type: '{type(obj).__name__}'. Sets, frozensets, and arbitrary custom objects fail closed."
        )


def canonicalize_json(data: Any) -> bytes:
    """Serializes arbitrary data to standard-compliant RFC 8785 / JCS canonical UTF-8 bytes using the mature rfc8785 library."""
    prepared = _prepare_for_rfc8785(data)
    try:
        return rfc8785.dumps(prepared)
    except Exception as exc:
        if isinstance(exc, CanonicalSerializationError):
            raise
        raise CanonicalSerializationError(f"RFC 8785 canonicalization failed: {exc}") from exc


def compute_event_preimage(
    event_id: str,
    event_type: EventType,
    sequence_number: int,
    aggregate_id: str,
    timestamp: str,
    payload: Mapping[str, Any],
    parent_digest: str,
) -> bytes:
    """Produces the exact RFC 8785 canonical preimage bytes for an event envelope (excluding digest)."""
    envelope_dict = {
        "event_id": event_id,
        "event_type": event_type.value if isinstance(event_type, EventType) else str(event_type),
        "sequence_number": sequence_number,
        "aggregate_id": aggregate_id,
        "timestamp": timestamp,
        "payload": payload,
        "parent_digest": parent_digest,
    }
    return canonicalize_json(envelope_dict)


def compute_event_digest(
    event_id: str,
    event_type: EventType,
    sequence_number: int,
    aggregate_id: str,
    timestamp: str,
    payload: Mapping[str, Any],
    parent_digest: str,
) -> str:
    """Computes SHA-256 digest hex string from canonical RFC 8785 event preimage."""
    preimage = compute_event_preimage(
        event_id=event_id,
        event_type=event_type,
        sequence_number=sequence_number,
        aggregate_id=aggregate_id,
        timestamp=timestamp,
        payload=payload,
        parent_digest=parent_digest,
    )
    return hashlib.sha256(preimage).hexdigest()


def verify_event_digest(event: EventEnvelope) -> bool:
    """Verifies that an EventEnvelope instance's digest matches its canonical preimage hash."""
    expected_digest = compute_event_digest(
        event_id=event.event_id,
        event_type=event.event_type,
        sequence_number=event.sequence_number,
        aggregate_id=event.aggregate_id,
        timestamp=event.timestamp,
        payload=event.payload,
        parent_digest=event.parent_digest,
    )
    return event.digest == expected_digest


def create_event(
    event_id: str,
    event_type: EventType,
    sequence_number: int,
    aggregate_id: str,
    timestamp: str,
    payload: Mapping[str, Any],
    parent_digest: str,
) -> EventEnvelope:
    """Factory creating an immutable, cryptographically valid EventEnvelope with computed SHA-256 digest."""
    digest = compute_event_digest(
        event_id=event_id,
        event_type=event_type,
        sequence_number=sequence_number,
        aggregate_id=aggregate_id,
        timestamp=timestamp,
        payload=payload,
        parent_digest=parent_digest,
    )
    return EventEnvelope(
        event_id=event_id,
        event_type=event_type,
        sequence_number=sequence_number,
        aggregate_id=aggregate_id,
        timestamp=timestamp,
        payload=payload,
        parent_digest=parent_digest,
        digest=digest,
    )


NONCE_RECORD_DOMAIN_SEPARATOR: str = "SCLASS_NONCE_V1:"


def compute_nonce_preimage(
    nonce: str,
    timestamp: str,
    sequence_number: int,
    parent_digest: str,
) -> bytes:
    """Produces the exact RFC 8785 canonical preimage bytes for a single-use nonce record with frozen domain separator."""
    payload = {
        "domain": NONCE_RECORD_DOMAIN_SEPARATOR,
        "nonce": nonce,
        "parent_digest": parent_digest,
        "sequence_number": sequence_number,
        "timestamp": timestamp,
    }
    return canonicalize_json(payload)


def compute_nonce_digest(
    nonce: str,
    timestamp: str,
    sequence_number: int,
    parent_digest: str,
) -> str:
    """Computes SHA-256 digest hex string from canonical RFC 8785 nonce record preimage with domain separator."""
    preimage = compute_nonce_preimage(
        nonce=nonce,
        timestamp=timestamp,
        sequence_number=sequence_number,
        parent_digest=parent_digest,
    )
    return hashlib.sha256(preimage).hexdigest()


MANIFEST_RECORD_DOMAIN_SEPARATOR: str = "SCLASS_MANIFEST_EPOCH_V1:"


def compute_manifest_record_preimage(
    manifest_id: str,
    manifest_version: int,
    payload_digest: str,
    signer_identity: str,
    root_fingerprint: str,
    sequence_number: int,
    timestamp: str,
    parent_digest: str,
) -> bytes:
    """Produces the exact RFC 8785 canonical preimage bytes for a durable manifest epoch record with frozen domain separator."""
    payload = {
        "domain": MANIFEST_RECORD_DOMAIN_SEPARATOR,
        "manifest_id": manifest_id,
        "manifest_version": manifest_version,
        "parent_digest": parent_digest,
        "payload_digest": payload_digest,
        "root_fingerprint": root_fingerprint,
        "sequence_number": sequence_number,
        "signer_identity": signer_identity,
        "timestamp": timestamp,
    }
    return canonicalize_json(payload)


def compute_manifest_record_digest(
    manifest_id: str,
    manifest_version: int,
    payload_digest: str,
    signer_identity: str,
    root_fingerprint: str,
    sequence_number: int,
    timestamp: str,
    parent_digest: str,
) -> str:
    """Computes SHA-256 digest hex string from canonical RFC 8785 manifest epoch record preimage with domain separator."""
    preimage = compute_manifest_record_preimage(
        manifest_id=manifest_id,
        manifest_version=manifest_version,
        payload_digest=payload_digest,
        signer_identity=signer_identity,
        root_fingerprint=root_fingerprint,
        sequence_number=sequence_number,
        timestamp=timestamp,
        parent_digest=parent_digest,
    )
    return hashlib.sha256(preimage).hexdigest()


D2_ANCHOR_RECORD_DOMAIN_SEPARATOR: str = "SCLASS_D2_ANCHOR_V1:"


def compute_d2_anchor_preimage(
    epoch: int,
    manifest_id: str,
    manifest_digest: str,
    signer_identity: str,
    root_fingerprint: str,
    sequence_number: int,
    timestamp: str,
    parent_digest: str,
) -> bytes:
    """Produces canonical RFC 8785 preimage bytes for an authoritative D2 state anchor record."""
    payload = {
        "domain": D2_ANCHOR_RECORD_DOMAIN_SEPARATOR,
        "epoch": epoch,
        "manifest_digest": manifest_digest,
        "manifest_id": manifest_id,
        "parent_digest": parent_digest,
        "root_fingerprint": root_fingerprint,
        "sequence_number": sequence_number,
        "signer_identity": signer_identity,
        "timestamp": timestamp,
    }
    return canonicalize_json(payload)


def compute_d2_anchor_digest(
    epoch: int,
    manifest_id: str,
    manifest_digest: str,
    signer_identity: str,
    root_fingerprint: str,
    sequence_number: int,
    timestamp: str,
    parent_digest: str,
) -> str:
    """Computes SHA-256 digest hex string for authoritative D2 state anchor record."""
    preimage = compute_d2_anchor_preimage(
        epoch=epoch,
        manifest_id=manifest_id,
        manifest_digest=manifest_digest,
        signer_identity=signer_identity,
        root_fingerprint=root_fingerprint,
        sequence_number=sequence_number,
        timestamp=timestamp,
        parent_digest=parent_digest,
    )
    return hashlib.sha256(preimage).hexdigest()

