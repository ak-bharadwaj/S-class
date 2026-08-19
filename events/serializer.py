"""RFC 8785 / JCS Canonical JSON Serialization and SHA-256 Digest Engine for D2.

Provides:
- RFC 8785 canonical JSON byte serialization.
- Canonical event preimage generation (excluding digest).
- Deterministic SHA-256 event digest computation.
- Canonical event factory and cryptographic verification.
"""

import hashlib
import json
from typing import Any, Mapping
from types import MappingProxyType

from domain.models import EventEnvelope
from domain.types import EventType
from events.exceptions import DigestMismatchError


def _canonicalize_obj(obj: Any) -> Any:
    """Recursively converts mapping proxies, tuples, and custom structures into canonical JSON primitives."""
    if isinstance(obj, (dict, MappingProxyType)):
        return {str(k): _canonicalize_obj(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set, frozenset)):
        return [_canonicalize_obj(item) for item in obj]
    elif isinstance(obj, EventType):
        return obj.value
    return obj


def canonicalize_json(data: Any) -> bytes:
    """Serializes arbitrary JSON-serializable structure to RFC 8785 / JCS canonical UTF-8 bytes.
    
    Rules:
    - Object keys sorted lexicographically.
    - Compact separators (',' and ':') with zero extraneous whitespace.
    - UTF-8 encoding without ASCII escapes for non-ASCII characters.
    """
    clean_data = _canonicalize_obj(data)
    json_str = json.dumps(
        clean_data,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return json_str.encode("utf-8")


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
