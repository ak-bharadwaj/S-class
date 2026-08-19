"""RFC 8785 (JSON Canonicalization Scheme / JCS) Serializer and SHA-256 Engine.

Implements standard-compliant RFC 8785 JSON Canonicalization:
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

from domain.models import EventEnvelope
from domain.types import EventType
from events.exceptions import DigestMismatchError


_ESCAPE_MAP = {
    0x08: b"\\b",
    0x09: b"\\t",
    0x0A: b"\\n",
    0x0C: b"\\f",
    0x0D: b"\\r",
    0x22: b'\\"',
    0x5C: b"\\\\",
}
for i in range(0x20):
    if i not in _ESCAPE_MAP:
        _ESCAPE_MAP[i] = f"\\u{i:04x}".encode("ascii")

_ESCAPE_RE = re.compile(r'[\x00-\x1f"\\]')


def _canonical_encode_value(obj: Any) -> bytes:
    """Recursively serializes any Python object according to RFC 8785 rules."""
    if obj is None:
        return b"null"
    elif isinstance(obj, bool):
        return b"true" if obj else b"false"
    elif isinstance(obj, int):
        return str(obj).encode("ascii")
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValueError("NaN and Infinity are not permitted in RFC 8785 JSON.")
        if obj == 0.0:
            return b"0"
        if obj.is_integer() and abs(obj) < 1e21:
            return str(int(obj)).encode("ascii")
        s = f"{obj:.16g}".replace("e+", "e")
        return s.encode("ascii")
    elif isinstance(obj, str):
        if not _ESCAPE_RE.search(obj):
            return b'"' + obj.encode("utf-8") + b'"'
        buf = bytearray(b'"')
        for ch in obj:
            cp = ord(ch)
            if cp in _ESCAPE_MAP:
                buf.extend(_ESCAPE_MAP[cp])
            else:
                buf.extend(ch.encode("utf-8"))
        buf.append(ord('"'))
        return bytes(buf)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        return b"[" + b",".join(_canonical_encode_value(item) for item in obj) + b"]"
    elif isinstance(obj, (dict, MappingProxyType)):
        sorted_keys = sorted(obj.keys(), key=lambda k: str(k).encode("utf-16-be"))
        parts = []
        for k in sorted_keys:
            k_bytes = _canonical_encode_value(str(k))
            v_bytes = _canonical_encode_value(obj[k])
            parts.append(k_bytes + b":" + v_bytes)
        return b"{" + b",".join(parts) + b"}"
    elif isinstance(obj, EventType):
        return _canonical_encode_value(obj.value)
    elif hasattr(obj, "__dict__"):
        return _canonical_encode_value(obj.__dict__)
    else:
        return _canonical_encode_value(str(obj))


def canonicalize_json(data: Any) -> bytes:
    """Serializes arbitrary data to standard-compliant RFC 8785 / JCS canonical UTF-8 bytes."""
    return _canonical_encode_value(data)


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
