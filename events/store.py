"""Append-Only Event Store Implementations for S-Class D2.

Provides:
- InMemoryEventStore: Thread-safe in-memory store with sequence mutex preventing concurrent write races.
- FileAppendEventStore: Robust, fail-closed file-backed JSON Lines store with atomic append and crash/partial-write recovery.
"""

import json
import os
import threading
from typing import List, Optional, Tuple

from domain.models import EventEnvelope
from domain.types import EventType
from events.interfaces import EventStoreInterface
from events.state import MaterializedState, GENESIS_PARENT_DIGEST
from events.reducer import reduce_event, replay_events
from events.serializer import verify_event_digest, canonicalize_json
from events.exceptions import (
    ConcurrencyConflictError,
    CorruptEventLogError,
    DuplicateSequenceError,
    SequenceGapError,
    InvalidParentDigestError,
    DigestMismatchError,
)


class InMemoryEventStore(EventStoreInterface):
    """Thread-safe in-memory append-only event store."""

    def __init__(self):
        self._events: List[EventEnvelope] = []
        self._lock = threading.Lock()

    def append(self, event: EventEnvelope) -> None:
        if not isinstance(event, EventEnvelope):
            raise TypeError("Expected EventEnvelope instance.")

        with self._lock:
            head_seq = len(self._events)
            expected_seq = head_seq + 1
            expected_parent = self._events[-1].digest if self._events else GENESIS_PARENT_DIGEST

            if event.sequence_number < expected_seq:
                raise DuplicateSequenceError(
                    f"Duplicate sequence: {event.sequence_number} <= head {head_seq}."
                )
            elif event.sequence_number > expected_seq:
                raise SequenceGapError(
                    f"Sequence gap: got {event.sequence_number}, expected {expected_seq}."
                )

            if event.parent_digest != expected_parent:
                raise InvalidParentDigestError(
                    f"Invalid parent digest: got '{event.parent_digest}', expected '{expected_parent}'."
                )

            if not verify_event_digest(event):
                raise DigestMismatchError(
                    f"Digest verification failed for event '{event.event_id}'."
                )

            self._events.append(event)

    def get_events(self, after_sequence: int = 0, limit: Optional[int] = None) -> Tuple[EventEnvelope, ...]:
        with self._lock:
            selected = [e for e in self._events if e.sequence_number > after_sequence]
            if limit is not None:
                selected = selected[:limit]
            return tuple(selected)

    def get_latest_event(self) -> Optional[EventEnvelope]:
        with self._lock:
            return self._events[-1] if self._events else None

    def replay(self, from_sequence: int = 0) -> MaterializedState:
        with self._lock:
            events_to_replay = [e for e in self._events if e.sequence_number > from_sequence]
            return replay_events(events_to_replay)

    def verify_integrity(self) -> bool:
        with self._lock:
            expected_parent = GENESIS_PARENT_DIGEST
            for idx, event in enumerate(self._events):
                if event.sequence_number != idx + 1:
                    return False
                if event.parent_digest != expected_parent:
                    return False
                if not verify_event_digest(event):
                    return False
                expected_parent = event.digest
            return True

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)


class FileAppendEventStore(EventStoreInterface):
    """Fail-closed, append-only file event store using JSON Lines format with crash/partial-write recovery."""

    def __init__(self, file_path: str):
        self._file_path = file_path
        self._lock = threading.Lock()
        self._events: List[EventEnvelope] = []
        self._recover_and_load()

    def _recover_and_load(self) -> None:
        """Scans the event log file, recovers from trailing partial writes, and validates chain integrity."""
        if not os.path.exists(self._file_path):
            # Ensure parent directory exists
            parent_dir = os.path.dirname(self._file_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            # Create empty file
            with open(self._file_path, "w", encoding="utf-8") as f:
                pass
            return

        recovered_events: List[EventEnvelope] = []
        expected_parent = GENESIS_PARENT_DIGEST
        has_corrupt_trailing = False
        valid_bytes_offset = 0

        with open(self._file_path, "rb") as f:
            for line_idx, line in enumerate(f):
                line_trimmed = line.strip()
                if not line_trimmed:
                    continue

                try:
                    record = json.loads(line_trimmed.decode("utf-8"))
                    event = EventEnvelope(
                        event_id=record["event_id"],
                        event_type=EventType(record["event_type"]),
                        sequence_number=int(record["sequence_number"]),
                        aggregate_id=record["aggregate_id"],
                        timestamp=record["timestamp"],
                        payload=record["payload"],
                        parent_digest=record["parent_digest"],
                        digest=record["digest"],
                    )
                except Exception as e:
                    # Partial or corrupt line detected
                    has_corrupt_trailing = True
                    break

                # Validate sequential continuity
                expected_seq = len(recovered_events) + 1
                if event.sequence_number != expected_seq or event.parent_digest != expected_parent or not verify_event_digest(event):
                    has_corrupt_trailing = True
                    break

                recovered_events.append(event)
                expected_parent = event.digest
                valid_bytes_offset = f.tell()

        if has_corrupt_trailing:
            # Truncate corrupt trailing data to restore clean crash recovery point
            with open(self._file_path, "r+b") as f:
                f.seek(valid_bytes_offset)
                f.truncate()

        self._events = recovered_events

    def append(self, event: EventEnvelope) -> None:
        if not isinstance(event, EventEnvelope):
            raise TypeError("Expected EventEnvelope instance.")

        with self._lock:
            head_seq = len(self._events)
            expected_seq = head_seq + 1
            expected_parent = self._events[-1].digest if self._events else GENESIS_PARENT_DIGEST

            if event.sequence_number < expected_seq:
                raise DuplicateSequenceError(
                    f"Duplicate sequence: {event.sequence_number} <= head {head_seq}."
                )
            elif event.sequence_number > expected_seq:
                raise SequenceGapError(
                    f"Sequence gap: got {event.sequence_number}, expected {expected_seq}."
                )

            if event.parent_digest != expected_parent:
                raise InvalidParentDigestError(
                    f"Invalid parent digest: got '{event.parent_digest}', expected '{expected_parent}'."
                )

            if not verify_event_digest(event):
                raise DigestMismatchError(
                    f"Digest verification failed for event '{event.event_id}'."
                )

            # Serialize to canonical JSON line
            event_dict = {
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "sequence_number": event.sequence_number,
                "aggregate_id": event.aggregate_id,
                "timestamp": event.timestamp,
                "payload": event.payload,
                "parent_digest": event.parent_digest,
                "digest": event.digest,
            }
            line_bytes = canonicalize_json(event_dict) + b"\n"

            # Atomic append with fsync
            with open(self._file_path, "ab") as f:
                f.write(line_bytes)
                f.flush()
                os.fsync(f.fileno())

            self._events.append(event)

    def get_events(self, after_sequence: int = 0, limit: Optional[int] = None) -> Tuple[EventEnvelope, ...]:
        with self._lock:
            selected = [e for e in self._events if e.sequence_number > after_sequence]
            if limit is not None:
                selected = selected[:limit]
            return tuple(selected)

    def get_latest_event(self) -> Optional[EventEnvelope]:
        with self._lock:
            return self._events[-1] if self._events else None

    def replay(self, from_sequence: int = 0) -> MaterializedState:
        with self._lock:
            events_to_replay = [e for e in self._events if e.sequence_number > from_sequence]
            return replay_events(events_to_replay)

    def verify_integrity(self) -> bool:
        with self._lock:
            expected_parent = GENESIS_PARENT_DIGEST
            for idx, event in enumerate(self._events):
                if event.sequence_number != idx + 1:
                    return False
                if event.parent_digest != expected_parent:
                    return False
                if not verify_event_digest(event):
                    return False
                expected_parent = event.digest
            return True

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)
