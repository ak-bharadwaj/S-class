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
from events.serializer import verify_event_digest, canonicalize_json, compute_nonce_digest, NONCE_RECORD_DOMAIN_SEPARATOR
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

        from file_lock import FileLock
        lock_path = self._file_path + ".lock"
        with self._lock:
            with FileLock(lock_path, timeout=10.0):
                self._recover_and_load()
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
    """D2 Durable, cross-process atomic single-use nonce reservation engine.
    Authoritative D2 store verification on every query; no unverified cache bypass.
    """

    def __init__(self, file_path: Optional[str] = None):
        if file_path is None:
            file_path = os.environ.get("GATE3_NONCE_STORE_PATH")
            if not file_path:
                file_path = os.path.join(
                    os.path.dirname(__file__), ".d2_gate3_nonce_store.jsonl"
                )
        self._file_path = os.path.abspath(file_path)
        self._lock_path = self._file_path + ".lock"
        self._local_lock = threading.Lock()

    @property
    def file_path(self) -> str:
        return self._file_path

    def _read_and_verify_log(self) -> Tuple[Set[str], int, str]:
        """Reads the nonce log from disk, verifying sequence continuity, parent chaining, domain separator, and SHA-256 digest integrity on every record.
        
        Returns:
            Tuple[Set[str], int, str]: (set_of_consumed_nonces, head_sequence_number, head_digest)
            
        Raises:
            CorruptEventLogError: If any record is malformed, missing fields, has wrong domain separator, or invalid cryptographic digest/chaining.
            StorageUnavailableError: If I/O read failure occurs.
        """
        import hmac
        if not os.path.exists(self._file_path):
            return set(), 0, GENESIS_PARENT_DIGEST

        consumed: Set[str] = set()
        expected_parent = GENESIS_PARENT_DIGEST
        head_seq = 0

        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                for line_idx, line in enumerate(f, 1):
                    line_str = line.strip()
                    if not line_str:
                        continue
                    try:
                        record = json.loads(line_str)
                    except json.JSONDecodeError as json_err:
                        raise CorruptEventLogError(f"Corrupt JSON at line {line_idx} in nonce store: {json_err}") from json_err

                    if not isinstance(record, dict):
                        raise CorruptEventLogError(f"Corrupt nonce record at line {line_idx}: record is not a JSON object")

                    for req_key in ("domain", "nonce", "timestamp", "sequence_number", "parent_digest", "digest"):
                        if req_key not in record:
                            raise CorruptEventLogError(f"Corrupt nonce record at line {line_idx}: missing mandatory field '{req_key}'")

                    if record["domain"] != NONCE_RECORD_DOMAIN_SEPARATOR:
                        raise CorruptEventLogError(
                            f"Domain separator mismatch in nonce store at line {line_idx}: got '{record['domain']}', expected '{NONCE_RECORD_DOMAIN_SEPARATOR}'"
                        )

                    rec_nonce = record["nonce"]
                    rec_timestamp = record["timestamp"]
                    rec_seq = record["sequence_number"]
                    rec_parent = record["parent_digest"]
                    rec_digest = record["digest"]

                    if not isinstance(rec_nonce, str) or not rec_nonce:
                        raise CorruptEventLogError(f"Corrupt nonce record at line {line_idx}: invalid 'nonce' value")
                    if not isinstance(rec_timestamp, str) or not rec_timestamp:
                        raise CorruptEventLogError(f"Corrupt nonce record at line {line_idx}: invalid 'timestamp' value")
                    if not isinstance(rec_seq, int) or rec_seq != head_seq + 1:
                        raise CorruptEventLogError(
                            f"Sequence discontinuity in nonce store at line {line_idx}: got {rec_seq}, expected {head_seq + 1}"
                        )
                    if rec_parent != expected_parent:
                        raise CorruptEventLogError(
                            f"Cryptographic chain broken in nonce store at line {line_idx}: got parent '{rec_parent}', expected '{expected_parent}'"
                        )

                    # Cryptographically verify the record's RFC 8785 digest with domain separator
                    expected_digest = compute_nonce_digest(rec_nonce, rec_timestamp, rec_seq, rec_parent)
                    if not hmac.compare_digest(rec_digest, expected_digest):
                        raise CorruptEventLogError(
                            f"Cryptographic digest forgery/corruption in nonce store at line {line_idx} for nonce '{rec_nonce}'"
                        )

                    consumed.add(rec_nonce)
                    expected_parent = rec_digest
                    head_seq = rec_seq

        except CorruptEventLogError:
            raise
        except (OSError, IOError) as io_err:
            raise StorageUnavailableError(f"I/O failure reading nonce store: {io_err}") from io_err

        return consumed, head_seq, expected_parent

    def reserve_nonce(self, nonce: str) -> bool:
        """Atomically reserves a single-use nonce (INSERT-if-absent) with authoritative D2 store verification on every reservation."""
        if not nonce or not isinstance(nonce, str):
            raise TypeError("Nonce must be a non-empty string.")

        from datetime import datetime, timezone
        from file_lock import FileLock
        from events.exceptions import StorageUnavailableError, CorruptEventLogError

        with self._local_lock:
            parent_dir = os.path.dirname(self._file_path)
            if parent_dir and not os.path.exists(parent_dir):
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                except OSError as e:
                    raise StorageUnavailableError(f"Cannot create directory for nonce store: {e}") from e

            try:
                with FileLock(self._lock_path, timeout=10.0):
                    # Authoritative D2 store read and verification
                    consumed, head_seq, expected_parent = self._read_and_verify_log()

                    if nonce in consumed:
                        return False

                    new_seq = head_seq + 1
                    timestamp = datetime.now(timezone.utc).isoformat()
                    digest = compute_nonce_digest(nonce, timestamp, new_seq, expected_parent)

                    rec_payload = {
                        "domain": NONCE_RECORD_DOMAIN_SEPARATOR,
                        "nonce": nonce,
                        "timestamp": timestamp,
                        "sequence_number": new_seq,
                        "parent_digest": expected_parent,
                        "digest": digest,
                    }
                    line_bytes = canonicalize_json(rec_payload) + b"\n"

                    try:
                        with open(self._file_path, "ab") as f:
                            f.write(line_bytes)
                            f.flush()
                            os.fsync(f.fileno())
                    except (OSError, IOError) as io_err:
                        raise StorageUnavailableError(f"I/O failure writing to nonce store: {io_err}") from io_err

                    return True

            except (CorruptEventLogError, StorageUnavailableError):
                raise
            except Exception as lock_err:
                raise StorageUnavailableError(f"Locking or storage operational failure: {lock_err}") from lock_err

    def is_nonce_consumed(self, nonce: str) -> bool:
        """Queries whether a nonce is consumed by directly verifying the authoritative D2 store."""
        if not nonce or not isinstance(nonce, str):
            return False

        from file_lock import FileLock
        from events.exceptions import StorageUnavailableError, CorruptEventLogError

        with self._local_lock:
            if not os.path.exists(self._file_path):
                return False

            try:
                with FileLock(self._lock_path, timeout=5.0):
                    # Authoritative D2 store read and verification
                    consumed, _, _ = self._read_and_verify_log()
                    return nonce in consumed
            except (CorruptEventLogError, StorageUnavailableError):
                raise
            except Exception as lock_err:
                raise StorageUnavailableError(f"Locking or storage operational failure during query: {lock_err}") from lock_err

    def clear(self) -> None:
        """Controlled teardown of nonce store for test fixtures."""
        from file_lock import FileLock
        with self._local_lock:
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


def get_canonical_d2_event_store_path() -> str:
    path = os.environ.get("SCLASS_EVENT_STORE_PATH")
    if not path:
        path = os.environ.get("D3_AUTHORITY_MANIFEST_STORE_PATH")
    if not path:
        path = os.path.join(os.path.dirname(__file__), ".d2_event_log.jsonl")
    return os.path.abspath(path)


class D2AuthorityManifestStore:
    """D2 Durable Authority Manifest Store.
    Anchored directly into the ONE canonical D2 Event Store (FileAppendEventStore / MaterializedState).
    No separate secondary ledger or independent anchor files.
    """

    def __init__(self, file_path: Optional[str] = None):
        if file_path is None:
            file_path = get_canonical_d2_event_store_path()
        self._file_path = os.path.abspath(file_path)
        self._lock = threading.Lock()

    @property
    def file_path(self) -> str:
        return self._file_path

    @property
    def store(self) -> FileAppendEventStore:
        return FileAppendEventStore(self._file_path)

    def get_highest_version(self, allow_uninitialized: bool = False) -> Tuple[int, Optional[str], Optional[str]]:
        """Atomically replays the canonical D2 event store into MaterializedState
        and returns (active_manifest_version, active_manifest_id, active_manifest_digest).
        Fails closed with StorageUnavailableError if the authoritative D2 store is missing and allow_uninitialized is False.
        """
        with self._lock:
            if not os.path.exists(self._file_path):
                if allow_uninitialized:
                    return (0, None, None)
                raise StorageUnavailableError(
                    f"Canonical D2 authority store is missing at '{self._file_path}'; fail closed against silent state reset."
                )
            store = FileAppendEventStore(self._file_path)
            state = store.replay()
            return (state.active_manifest_version, state.active_manifest_id, state.active_manifest_digest)

    def commit_epoch(
        self,
        manifest_id: str,
        manifest_version: int,
        payload_digest: str,
        signer_identity: str,
        root_fingerprint: str,
    ) -> None:
        """Commits a canonical AUTHORITY_MANIFEST_COMMITTED event to the D2 event store."""
        from datetime import datetime, timezone
        from file_lock import FileLock
        from events.serializer import compute_event_digest
        from domain.models import EventEnvelope
        from domain.types import EventType
        from policy.exceptions import ManifestRollbackError, CorruptManifestError

        lock_path = self._file_path + ".lock"
        with self._lock:
            with FileLock(lock_path, timeout=10.0):
                store = FileAppendEventStore(self._file_path)
                state = store.replay()

                if state.active_manifest_id is not None and manifest_id != state.active_manifest_id:
                    raise CorruptManifestError(
                        f"Manifest identity substitution rejected: expected '{state.active_manifest_id}', got '{manifest_id}'."
                    )

                if manifest_version < state.active_manifest_version:
                    raise ManifestRollbackError(
                        f"Manifest version {manifest_version} is older than highest durable accepted version {state.active_manifest_version} (rollback rejected)."
                    )

                if manifest_version == state.active_manifest_version and state.active_manifest_digest is not None:
                    if payload_digest != state.active_manifest_digest:
                        raise ManifestRollbackError(
                            f"Same-version manifest substitution rejected for version {manifest_version}."
                        )
                    return

                latest = store.get_latest_event()
                new_seq = (latest.sequence_number + 1) if latest else 1
                parent_digest = latest.digest if latest else GENESIS_PARENT_DIGEST
                now_iso = datetime.now(timezone.utc).isoformat()
                event_id = f"EVT-MANIFEST-{manifest_id}-{manifest_version}"

            payload = {
                "manifest_id": manifest_id,
                "manifest_version": manifest_version,
                "payload_digest": payload_digest,
                "signer_identity": signer_identity,
                "root_fingerprint": root_fingerprint,
            }

            digest = compute_event_digest(
                event_id=event_id,
                event_type=EventType.AUTHORITY_MANIFEST_COMMITTED,
                sequence_number=new_seq,
                aggregate_id=manifest_id,
                timestamp=now_iso,
                payload=payload,
                parent_digest=parent_digest,
            )

            event = EventEnvelope(
                event_id=event_id,
                event_type=EventType.AUTHORITY_MANIFEST_COMMITTED,
                sequence_number=new_seq,
                aggregate_id=manifest_id,
                timestamp=now_iso,
                payload=payload,
                parent_digest=parent_digest,
                digest=digest,
            )

            store.append(event)

    def clear(self) -> None:
        """Controlled teardown of event store strictly for test fixtures."""
        if os.environ.get("SCLASS_TEST_FIXTURE_ACTIVE") != "1" and os.environ.get("PYTEST_CURRENT_TEST") is None:
            raise RuntimeError("Authority state cannot be reset outside active test fixture harness.")
        with self._lock:
            if os.path.exists(self._file_path):
                try:
                    os.remove(self._file_path)
                except OSError:
                    with open(self._file_path, "w", encoding="utf-8") as f:
                        pass

