"""Append-Only Event Store Implementations for S-Class D2.

Provides:
- InMemoryEventStore: Thread-safe in-memory store with sequence mutex preventing concurrent write races.
- FileAppendEventStore: Robust, fail-closed file-backed JSON Lines store with atomic append,
  strict fail-closed historical corruption rejection, and safe torn final write recovery at EOF.
"""

import json
import os
import threading
from typing import List, Optional, Tuple, Set

from domain.models import EventEnvelope
from domain.types import EventType
from events.interfaces import EventStoreInterface, NonceReservationInterface
from events.state import MaterializedState, GENESIS_PARENT_DIGEST
from events.reducer import reduce_event, replay_events
from events.serializer import verify_event_digest, canonicalize_json
from events.exceptions import (
    StorageUnavailableError,
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
        """Scans the event log file, distinguishing recoverable torn final writes at EOF from authenticated corruption.
        
        Rules:
        - If corruption / invalid digest / broken chain occurs in a completed record, it is authenticated corruption.
          It MUST raise CorruptEventLogError and halt (fail closed, never silently discarded).
        - If and only if the final line at EOF is an incomplete/torn write fragment, and all preceding records are valid,
          it is recognized as a crash during atomic write and truncated to the last valid newline offset.
        """
        if not os.path.exists(self._file_path):
            parent_dir = os.path.dirname(self._file_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(self._file_path, "w", encoding="utf-8") as f:
                pass
            return

        with open(self._file_path, "rb") as f:
            content = f.read()

        if not content:
            self._events = []
            return

        lines = content.splitlines(keepends=True)
        recovered_events: List[EventEnvelope] = []
        expected_parent = GENESIS_PARENT_DIGEST
        valid_bytes_offset = 0
        num_lines = len(lines)

        for idx, line in enumerate(lines):
            line_trimmed = line.strip()
            if not line_trimmed:
                continue

            is_last_line = (idx == num_lines - 1)
            is_terminated = line.endswith(b"\n") or line.endswith(b"\r\n")

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
            except Exception as parse_err:
                if is_last_line and not is_terminated:
                    with open(self._file_path, "r+b") as f_trunc:
                        f_trunc.seek(valid_bytes_offset)
                        f_trunc.truncate()
                    break
                raise CorruptEventLogError(
                    f"Corrupt event record at line {idx + 1}: {parse_err}"
                )

            expected_seq = len(recovered_events) + 1
            if event.sequence_number != expected_seq:
                raise CorruptEventLogError(
                    f"Sequence discontinuity in log at line {idx + 1}: got {event.sequence_number}, expected {expected_seq}."
                )

            if event.parent_digest != expected_parent:
                raise CorruptEventLogError(
                    f"Cryptographic chain broken at line {idx + 1}: got parent '{event.parent_digest}', expected '{expected_parent}'."
                )

            if not verify_event_digest(event):
                raise CorruptEventLogError(
                    f"Cryptographic digest forgery/corruption at line {idx + 1} for event '{event.event_id}'."
                )

            recovered_events.append(event)
            expected_parent = event.digest
            valid_bytes_offset += len(line)

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


class D2NonceStore(NonceReservationInterface):
    """D2 Durable, cross-process atomic single-use nonce reservation engine with kernel advisory locking."""

    def __init__(self, file_path: Optional[str] = None):
        if file_path is None:
            file_path = os.environ.get("GATE3_NONCE_STORE_PATH") or os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "benchmark", "parity", ".gate3_nonces.log"
            )
        self._file_path = os.path.abspath(file_path)
        self._lock_path = self._file_path + ".lock"
        self._process_cache: Set[str] = set()
        self._local_lock = threading.Lock()

    @property
    def file_path(self) -> str:
        return self._file_path

    def reserve_nonce(self, nonce: str) -> bool:
        """Atomically reserves a single-use nonce (INSERT-if-absent).
        
        Returns:
            True: If nonce was absent and successfully reserved.
            False: If nonce is already present (duplicate/replayed).
            
        Raises:
            TypeError: If nonce is malformed.
            CorruptEventLogError: If storage file contains corrupted or invalid records.
            StorageUnavailableError: If storage, locking, or I/O is unavailable (fail closed).
        """
        if not nonce or not isinstance(nonce, str):
            raise TypeError("Nonce must be a non-empty string.")

        import hashlib
        from datetime import datetime, timezone
        from file_lock import FileLock
        from events.exceptions import StorageUnavailableError, CorruptEventLogError

        with self._local_lock:
            if nonce in self._process_cache:
                return False

            parent_dir = os.path.dirname(self._file_path)
            if parent_dir and not os.path.exists(parent_dir):
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                except OSError as e:
                    raise StorageUnavailableError(f"Cannot create directory for nonce store: {e}") from e

            try:
                with FileLock(self._lock_path, timeout=10.0):
                    consumed: Set[str] = set()
                    if os.path.exists(self._file_path):
                        try:
                            with open(self._file_path, "r", encoding="utf-8") as f:
                                for line_idx, line in enumerate(f, 1):
                                    line_str = line.strip()
                                    if not line_str:
                                        continue
                                    try:
                                        record = json.loads(line_str)
                                        rec_nonce = record.get("nonce")
                                        if not rec_nonce or not isinstance(rec_nonce, str):
                                            raise CorruptEventLogError(f"Corrupt nonce record at line {line_idx}: missing 'nonce'")
                                        consumed.add(rec_nonce)
                                    except json.JSONDecodeError as json_err:
                                        raise CorruptEventLogError(f"Corrupt JSON at line {line_idx}: {json_err}") from json_err
                        except CorruptEventLogError:
                            raise
                        except (OSError, IOError) as io_err:
                            raise StorageUnavailableError(f"I/O failure reading nonce store: {io_err}") from io_err

                    if nonce in consumed:
                        self._process_cache.add(nonce)
                        return False

                    rec_payload = {
                        "nonce": nonce,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "digest": hashlib.sha256(nonce.encode("utf-8")).hexdigest(),
                    }
                    line_bytes = canonicalize_json(rec_payload) + b"\n"

                    try:
                        with open(self._file_path, "ab") as f:
                            f.write(line_bytes)
                            f.flush()
                            os.fsync(f.fileno())
                    except (OSError, IOError) as io_err:
                        raise StorageUnavailableError(f"I/O failure writing to nonce store: {io_err}") from io_err

                    consumed.add(nonce)
                    self._process_cache.add(nonce)
                    return True
            except (CorruptEventLogError, StorageUnavailableError):
                raise
            except Exception as lock_err:
                raise StorageUnavailableError(f"Locking or storage operational failure: {lock_err}") from lock_err

    def is_nonce_consumed(self, nonce: str) -> bool:
        """Queries whether a nonce is consumed.
        
        Returns:
            True: If nonce is present in the committed store.
            False: If nonce is absent (not found).
            
        Raises:
            CorruptEventLogError: If storage file contains corrupted or invalid records.
            StorageUnavailableError: If storage, locking, or I/O is unavailable (fail closed).
        """
        if not nonce or not isinstance(nonce, str):
            return False

        from file_lock import FileLock
        from events.exceptions import StorageUnavailableError, CorruptEventLogError

        with self._local_lock:
            if nonce in self._process_cache:
                return True

            if not os.path.exists(self._file_path):
                return False

            try:
                with FileLock(self._lock_path, timeout=5.0):
                    if not os.path.exists(self._file_path):
                        return False
                    try:
                        with open(self._file_path, "r", encoding="utf-8") as f:
                            for line_idx, line in enumerate(f, 1):
                                line_str = line.strip()
                                if not line_str:
                                    continue
                                try:
                                    record = json.loads(line_str)
                                    rec_nonce = record.get("nonce")
                                    if not rec_nonce or not isinstance(rec_nonce, str):
                                        raise CorruptEventLogError(f"Corrupt nonce record at line {line_idx}: missing 'nonce'")
                                    if rec_nonce == nonce:
                                        self._process_cache.add(nonce)
                                        return True
                                except json.JSONDecodeError as json_err:
                                    raise CorruptEventLogError(f"Corrupt JSON at line {line_idx}: {json_err}") from json_err
                    except CorruptEventLogError:
                        raise
                    except (OSError, IOError) as io_err:
                        raise StorageUnavailableError(f"I/O failure reading nonce store: {io_err}") from io_err
                    return False
            except (CorruptEventLogError, StorageUnavailableError):
                raise
            except Exception as lock_err:
                raise StorageUnavailableError(f"Locking or storage uncertainty during query: {lock_err}") from lock_err

    def clear(self) -> None:
        """Controlled teardown of nonce store for test fixtures."""
        from file_lock import FileLock
        with self._local_lock:
            self._process_cache.clear()
            if os.path.exists(self._file_path):
                try:
                    with FileLock(self._lock_path, timeout=5.0):
                        if os.path.exists(self._file_path):
                            try:
                                os.remove(self._file_path)
                            except OSError:
                                with open(self._file_path, "w", encoding="utf-8") as f:
                                    pass
                except Exception:
                    if os.path.exists(self._file_path):
                        try:
                            os.remove(self._file_path)
                        except OSError:
                            pass
