"""RFC 8785 (JSON Canonicalization Scheme / JCS) Serializer and SHA-256 Engine.

Integrates the standard-compliant, mature, permissively licensed rfc8785 library
for deterministic JSON Canonicalization Scheme (JCS) encoding:
1. Whitespace: zero whitespace outside strings (compact tokens).
2. Numbers: IEEE 754 double precision without trailing .0 and with ECMAScript exponent formatting.
3. Strings: UTF-8 with strict control character escaping (\b, \t, \n, \f, \r, \u0000..\u001f);
   forward slash / and raw Unicode characters are NOT escaped.
4. Object Keys: strictly sorted lexicographically by UTF-16 code units (key.encode('utf-16-be')).
5. SHA-256 event digest computation and verification over canonical preimage bytes.
"""

import hashlib
import math
import re
from typing import Any, Mapping
from types import MappingProxyType
import rfc8785

from domain.models import EventEnvelope
from domain.types import EventType
from events.exceptions import DigestMismatchError


def _prepare_for_rfc8785(obj: Any) -> Any:
    """Recursively converts custom dataclasses, enums, mapping proxies, and sets into standard JSON primitives for RFC 8785 canonicalization."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    elif isinstance(obj, EventType):
        return obj.value
    elif isinstance(obj, (dict, MappingProxyType)):
        return {str(k): _prepare_for_rfc8785(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set, frozenset)):
        return [_prepare_for_rfc8785(x) for x in obj]
    elif hasattr(obj, "__dict__"):
        return {str(k): _prepare_for_rfc8785(v) for k, v in obj.__dict__.items()}
    else:
        return str(obj)


def canonicalize_json(data: Any) -> bytes:
    """Serializes arbitrary data to standard-compliant RFC 8785 / JCS canonical UTF-8 bytes using the mature rfc8785 library."""
    prepared = _prepare_for_rfc8785(data)
    return rfc8785.dumps(prepared)


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
