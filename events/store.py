"""Append-Only Event Store Implementations for S-Class D2.

Provides:
- InMemoryEventStore: Thread-safe in-memory store with sequence mutex preventing concurrent write races.
- FileAppendEventStore: Robust, fail-closed file-backed JSON Lines store with atomic append,
  strict fail-closed historical corruption rejection, and safe torn final write recovery at EOF.
"""

from __future__ import annotations
import json
import os
import threading
from typing import Any, Dict, List, Optional, Tuple, Set

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
            if not os.path.exists(self._file_path) or os.path.getsize(self._file_path) == 0:
                if allow_uninitialized:
                    return (0, None, None)
                raise StorageUnavailableError(
                    f"Canonical D2 authority store is missing or empty at '{self._file_path}'; fail closed against silent state reset."
                )
            store = FileAppendEventStore(self._file_path)
            state = store.replay()
            return (state.active_manifest_version, state.active_manifest_id, state.active_manifest_digest)

    _class_lock = threading.RLock()

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
        from events.serializer import compute_event_digest
        from domain.models import EventEnvelope
        from domain.types import EventType
        from events.exceptions import DuplicateSequenceError
        from policy.exceptions import ManifestRollbackError, CorruptManifestError

        with self._class_lock:
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

            try:
                store.append(event)
            except DuplicateSequenceError:
                recheck_state = store.replay()
                if (
                    recheck_state.active_manifest_version == manifest_version
                    and recheck_state.active_manifest_digest == payload_digest
                ):
                    return
                raise

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


def get_canonical_d2_installation_marker_path() -> str:
    """Returns absolute path to the canonical D2 installation provisioning marker."""
    event_store_path = get_canonical_d2_event_store_path()
    directory = os.path.dirname(os.path.abspath(event_store_path))
    return os.path.join(directory, ".d2_installation_seal.json")


def get_canonical_d2_installation_stage_path() -> str:
    """Returns absolute path to the transient D2 installation staging file."""
    event_store_path = get_canonical_d2_event_store_path()
    directory = os.path.dirname(os.path.abspath(event_store_path))
    return os.path.join(directory, ".d2_installation_stage.json")


class D2InstallationProvisioning:
    """Manages the explicit, cryptographically authenticated first-installation state of S-Class.
    Separates FIRST INSTALL STATE from D2 AUTHORITY HISTORY to prevent authority resets
    when history is missing/deleted/truncated.
    """
    _class_lock = threading.RLock()

    @classmethod
    def get_marker_path(cls) -> str:
        return get_canonical_d2_installation_marker_path()

    @classmethod
    def get_stage_path(cls) -> str:
        return get_canonical_d2_installation_stage_path()

    @classmethod
    def has_seal(cls) -> bool:
        marker = cls.get_marker_path()
        return os.path.exists(marker) and os.path.getsize(marker) > 0

    @classmethod
    def verify_seal(cls, root_public_key: Optional[Any] = None) -> Dict[str, Any]:
        """Cryptographically verifies the installation seal. Fails closed on tampering or forgery."""
        import json
        import hashlib
        from cryptography.exceptions import InvalidSignature
        from events.serializer import canonicalize_json
        from policy.exceptions import InvalidManifestSignatureError, CorruptManifestError

        marker = cls.get_marker_path()
        if not os.path.exists(marker):
            raise FileNotFoundError(f"Installation seal not found at '{marker}'.")

        try:
            with open(marker, "rb") as f:
                content = f.read()
            data = json.loads(content.decode("utf-8"))
        except Exception as e:
            raise CorruptManifestError(f"Installation seal is malformed or unreadable: {e}") from e

        if not isinstance(data, dict):
            raise CorruptManifestError("Installation seal payload must be a JSON object.")

        required_fields = [
            "installation_id",
            "initial_manifest_id",
            "initial_manifest_version",
            "initial_manifest_digest",
            "root_fingerprint",
            "provisioning_epoch",
            "status",
            "installed_at",
            "signature",
        ]
        for field in required_fields:
            if field not in data:
                raise CorruptManifestError(f"Installation seal missing required field '{field}'.")

        if data["status"] != "SEALED":
            raise CorruptManifestError(f"Installation seal has invalid status '{data['status']}', expected 'SEALED'.")

        if data["initial_manifest_version"] != 1:
            raise CorruptManifestError("Installation seal initial_manifest_version must be 1.")

        if data["provisioning_epoch"] != 1:
            raise CorruptManifestError("Installation seal provisioning_epoch must be 1.")

        sig_block = data.get("signature")
        if not isinstance(sig_block, dict):
            raise InvalidManifestSignatureError("Installation seal missing signature object.")

        if sig_block.get("algorithm") != "ED25519":
            raise InvalidManifestSignatureError("Installation seal signature algorithm must be ED25519.")

        if sig_block.get("signer_identity") != "Gate3AuthoritativeVerifier":
            raise InvalidManifestSignatureError("Installation seal signer identity must be 'Gate3AuthoritativeVerifier'.")

        sig_hex = sig_block.get("signature_hex", "")
        if not sig_hex or len(sig_hex) != 128:
            raise InvalidManifestSignatureError("Installation seal signature hex is invalid length.")

        # Resolve trusted public key
        if root_public_key is None:
            from benchmark.parity.verify_gate_3_certificate import Gate3PublicKeystore
            root_public_key = Gate3PublicKeystore.get_public_key()
            if root_public_key is None:
                raise RuntimeError("Canonical Gate 3 Root Authority Public Key is not configured in protected keystore boundary.")

        expected_root_fp = hashlib.sha256(root_public_key.public_bytes_raw()).hexdigest()
        if data["root_fingerprint"] != expected_root_fp:
            raise InvalidManifestSignatureError(
                f"Installation seal root fingerprint '{data['root_fingerprint']}' does not match canonical root '{expected_root_fp}'."
            )

        if sig_block.get("public_key_fingerprint") != expected_root_fp:
            raise InvalidManifestSignatureError("Installation seal signature fingerprint mismatch.")

        # Compute preimage (all fields except signature)
        preimage_dict = {
            "installation_id": data["installation_id"],
            "initial_manifest_id": data["initial_manifest_id"],
            "initial_manifest_version": data["initial_manifest_version"],
            "initial_manifest_digest": data["initial_manifest_digest"],
            "root_fingerprint": data["root_fingerprint"],
            "provisioning_epoch": data["provisioning_epoch"],
            "status": data["status"],
            "installed_at": data["installed_at"],
        }
        preimage_bytes = canonicalize_json(preimage_dict)
        expected_digest = hashlib.sha256(preimage_bytes).hexdigest()

        if sig_block.get("payload_digest") != expected_digest:
            raise InvalidManifestSignatureError("Installation seal payload digest mismatch.")

        try:
            root_public_key.verify(bytes.fromhex(sig_hex), preimage_bytes)
        except InvalidSignature:
            raise InvalidManifestSignatureError("Installation seal Ed25519 signature verification failed.")

        return data

    @classmethod
    def is_installed(cls) -> bool:
        """Returns True if the system has a valid authenticated installation seal,
        or performs deterministic recovery if interrupted during commit.
        """
        # 1. Check if valid seal exists
        if cls.has_seal():
            cls.verify_seal()
            return True

        # 2. Check if transient stage exists for deterministic crash recovery
        stage_path = cls.get_stage_path()
        if os.path.exists(stage_path) and os.path.getsize(stage_path) > 0:
            return cls._recover_from_stage()

        return False

    @classmethod
    def _recover_from_stage(cls) -> bool:
        """Deterministically recovers an interrupted installation."""
        import json
        stage_path = cls.get_stage_path()
        try:
            with open(stage_path, "rb") as f:
                stage_data = json.loads(f.read().decode("utf-8"))
        except Exception:
            return False

        # Check D2 store state
        from events.store import D2AuthorityManifestStore
        store = D2AuthorityManifestStore()
        if os.path.exists(store.file_path) and os.path.getsize(store.file_path) > 0:
            try:
                state = store.store.replay()
                if (
                    state.active_manifest_id == stage_data.get("initial_manifest_id")
                    and state.active_manifest_version == stage_data.get("initial_manifest_version")
                    and state.active_manifest_digest == stage_data.get("initial_manifest_digest")
                ):
                    # Interrupted between D2 commit and seal creation -> promote stage to seal
                    cls.seal_first_installation(
                        manifest_id=stage_data["initial_manifest_id"],
                        manifest_version=stage_data["initial_manifest_version"],
                        payload_digest=stage_data["initial_manifest_digest"],
                        signer_identity=stage_data["signature"]["signer_identity"],
                        root_fingerprint=stage_data["root_fingerprint"],
                        installation_id=stage_data["installation_id"],
                        installed_at=stage_data["installed_at"],
                    )
                    return True
            except Exception:
                pass

        # If D2 store is empty or uncommitted, remove broken stage
        try:
            os.remove(stage_path)
        except OSError:
            pass
        return False

    @classmethod
    def prepare_first_installation(
        cls,
        manifest_id: str,
        manifest_version: int,
        payload_digest: str,
        signer_identity: str,
        root_fingerprint: str,
    ) -> str:
        """Stage 1: FIRST_INSTALL_PREPARED."""
        import uuid
        import hashlib
        from datetime import datetime, timezone
        from file_lock import FileLock
        from events.serializer import canonicalize_json
        from benchmark.parity.gate_3_authority import Gate3AuthorityKeyStore

        root_priv = Gate3AuthorityKeyStore.get_private_key()
        if root_priv is None:
            raise RuntimeError("Canonical Gate 3 Authority private key is not configured for installation preparation.")

        installation_id = str(uuid.uuid4())
        installed_at = datetime.now(timezone.utc).isoformat()
        stage_path = cls.get_stage_path()
        lock_path = stage_path + ".lock"

        preimage_dict = {
            "installation_id": installation_id,
            "initial_manifest_id": manifest_id,
            "initial_manifest_version": manifest_version,
            "initial_manifest_digest": payload_digest,
            "root_fingerprint": root_fingerprint,
            "provisioning_epoch": 1,
            "status": "PREPARED",
            "installed_at": installed_at,
        }
        preimage_bytes = canonicalize_json(preimage_dict)
        payload_digest_calc = hashlib.sha256(preimage_bytes).hexdigest()
        sig_bytes = root_priv.sign(preimage_bytes)

        stage_payload = dict(preimage_dict)
        stage_payload["signature"] = {
            "algorithm": "ED25519",
            "signer_identity": signer_identity,
            "public_key_fingerprint": root_fingerprint,
            "payload_digest": payload_digest_calc,
            "signature_hex": sig_bytes.hex(),
            "timestamp": installed_at,
        }

        with cls._class_lock:
            with FileLock(lock_path, timeout=10.0):
                with open(stage_path, "wb") as f:
                    f.write(canonicalize_json(stage_payload) + b"\n")
                    f.flush()
                    os.fsync(f.fileno())

        return installation_id

    @classmethod
    def seal_first_installation(
        cls,
        manifest_id: str,
        manifest_version: int,
        payload_digest: str,
        signer_identity: str,
        root_fingerprint: str,
        installation_id: Optional[str] = None,
        installed_at: Optional[str] = None,
    ) -> None:
        """Stage 3: FIRST_INSTALL_SEALED."""
        import uuid
        import hashlib
        from datetime import datetime, timezone
        from file_lock import FileLock
        from events.serializer import canonicalize_json
        from benchmark.parity.gate_3_authority import Gate3AuthorityKeyStore

        root_priv = Gate3AuthorityKeyStore.get_private_key()
        if root_priv is None:
            raise RuntimeError("Canonical Gate 3 Authority private key is not configured for installation seal.")

        if installation_id is None:
            installation_id = str(uuid.uuid4())
        if installed_at is None:
            installed_at = datetime.now(timezone.utc).isoformat()

        marker = cls.get_marker_path()
        lock_path = marker + ".lock"

        preimage_dict = {
            "installation_id": installation_id,
            "initial_manifest_id": manifest_id,
            "initial_manifest_version": manifest_version,
            "initial_manifest_digest": payload_digest,
            "root_fingerprint": root_fingerprint,
            "provisioning_epoch": 1,
            "status": "SEALED",
            "installed_at": installed_at,
        }
        preimage_bytes = canonicalize_json(preimage_dict)
        payload_digest_calc = hashlib.sha256(preimage_bytes).hexdigest()
        sig_bytes = root_priv.sign(preimage_bytes)

        seal_payload = dict(preimage_dict)
        seal_payload["signature"] = {
            "algorithm": "ED25519",
            "signer_identity": signer_identity,
            "public_key_fingerprint": root_fingerprint,
            "payload_digest": payload_digest_calc,
            "signature_hex": sig_bytes.hex(),
            "timestamp": installed_at,
        }

        with cls._class_lock:
            with FileLock(lock_path, timeout=10.0):
                with open(marker, "wb") as f:
                    f.write(canonicalize_json(seal_payload) + b"\n")
                    f.flush()
                    os.fsync(f.fileno())

                # Clean up staging file
                stage_path = cls.get_stage_path()
                if os.path.exists(stage_path):
                    try:
                        os.remove(stage_path)
                    except OSError:
                        pass

                provisioner = DeploymentProvisionerRegistry.get_provisioner()
                if provisioner.get_deployment_status() == DeploymentStatus.RECOVERY_AUTHORIZED:
                    try:
                        provisioner.record_reprovisioned(
                            installation_id=installation_id,
                            manifest_id=manifest_id,
                            manifest_version=manifest_version,
                            root_fingerprint=root_fingerprint,
                            payload_digest=payload_digest_calc,
                            root_signature=seal_payload["signature"],
                        )
                    except TypeError:
                        provisioner.record_reprovisioned(
                            installation_id=installation_id,
                            manifest_id=manifest_id,
                            manifest_version=manifest_version,
                            root_fingerprint=root_fingerprint,
                        )
                else:
                    try:
                        provisioner.record_provisioned(
                            installation_id=installation_id,
                            manifest_id=manifest_id,
                            manifest_version=manifest_version,
                            root_fingerprint=root_fingerprint,
                            payload_digest=payload_digest_calc,
                            root_signature=seal_payload["signature"],
                        )
                    except TypeError:
                        provisioner.record_provisioned(
                            installation_id=installation_id,
                            manifest_id=manifest_id,
                            manifest_version=manifest_version,
                            root_fingerprint=root_fingerprint,
                        )

    @classmethod
    def verify_state_agreement(cls) -> None:
        """Verifies that the authenticated installation seal and the canonical D2 event store agree."""
        from policy.exceptions import CorruptManifestError
        from events.exceptions import StorageUnavailableError

        if not cls.has_seal():
            return

        seal_data = cls.verify_seal()

        from events.store import D2AuthorityManifestStore, FileAppendEventStore
        store = D2AuthorityManifestStore()
        if not os.path.exists(store.file_path) or os.path.getsize(store.file_path) == 0:
            raise StorageUnavailableError(
                f"Authoritative D2 history missing at '{store.file_path}' for sealed installation; fail closed against authority reset."
            )

        event_store = FileAppendEventStore(store.file_path)
        events = event_store.get_events()
        if not events:
            raise StorageUnavailableError("Canonical D2 store contains no events for sealed installation.")

        first_event = events[0]
        payload = first_event.payload
        if (
            payload.get("manifest_id") != seal_data["initial_manifest_id"]
            or payload.get("manifest_version") != seal_data["initial_manifest_version"]
            or payload.get("payload_digest") != seal_data["initial_manifest_digest"]
            or payload.get("root_fingerprint") != seal_data["root_fingerprint"]
        ):
            raise CorruptManifestError(
                "Authoritative D2 genesis state does not agree with sealed installation record; state mismatch rejected."
            )

    @classmethod
    def clear_for_testing(cls) -> None:
        """Controlled teardown of installation state strictly for test fixtures."""
        if os.environ.get("SCLASS_TEST_FIXTURE_ACTIVE") != "1" and os.environ.get("PYTEST_CURRENT_TEST") is None:
            raise RuntimeError("Installation state teardown prohibited outside active test fixture harness.")
        for p in [cls.get_marker_path(), cls.get_stage_path()]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
            lock_p = p + ".lock"
            if os.path.exists(lock_p):
                try:
                    os.remove(lock_p)
                except OSError:
                    pass
        DeploymentProvisionerRegistry.reset_for_testing()


from abc import ABC, abstractmethod
from enum import Enum


class DeploymentStatus(str, Enum):
    AUTHORITY_UNAVAILABLE = "AUTHORITY_UNAVAILABLE"
    UNPROVISIONED = "UNPROVISIONED"
    PROVISIONING_AUTHORIZED = "PROVISIONING_AUTHORIZED"
    PROVISIONED = "PROVISIONED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    RECOVERY_AUTHORIZED = "RECOVERY_AUTHORIZED"


def _is_test_mode_active() -> bool:
    return bool(
        os.environ.get("SCLASS_TEST_MODE") == "1"
        or os.environ.get("SCLASS_TEST_FIXTURE_ACTIVE") == "1"
        or os.environ.get("PYTEST_CURRENT_TEST") is not None
    )


class TrustedDeploymentProvisioner(ABC):
    """Abstract interface for an explicit external deployment authority.
    The application cannot be its own deployment authority. External authority
    governs initial genesis, reprovisioning, and recovery across catastrophic local-state loss.
    """
    @abstractmethod
    def get_deployment_id(self) -> str:
        """Returns the immutable deployment identifier."""
        pass

    @abstractmethod
    def get_deployment_status(self) -> DeploymentStatus:
        """Returns the current deployment status from the external authority."""
        pass

    @abstractmethod
    def authorize_initial_provisioning(self, authorization_data: Optional[Dict[str, Any]] = None) -> None:
        """Authorizes initial genesis provisioning. Fails closed if unauthorized or already provisioned."""
        pass

    @abstractmethod
    def record_provisioned(
        self,
        installation_id: str,
        manifest_id: str,
        manifest_version: int,
        root_fingerprint: str,
        payload_digest: Optional[str] = None,
        root_signature: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Records that the initial genesis epoch has been durably committed."""
        pass

    @abstractmethod
    def notify_local_state_loss(self) -> None:
        """Notifies the external deployment authority of complete local-state loss,
        transitioning deployment status to RECOVERY_REQUIRED.
        """
        pass

    @abstractmethod
    def authorize_reprovisioning(
        self,
        reprovisioning_authorization: Dict[str, Any],
        root_public_key: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Verifies and consumes an externally issued, root-signed reprovisioning authorization.
        Enforces replay prevention, deployment matching, and signature authenticity externally.
        """
        pass

    @abstractmethod
    def record_reprovisioned(
        self,
        installation_id: str,
        manifest_id: str,
        manifest_version: int,
        root_fingerprint: str,
        payload_digest: Optional[str] = None,
        root_signature: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Records that catastrophic recovery reprovisioning has completed."""
        pass


class IPCDeploymentProvisioner(TrustedDeploymentProvisioner):
    """Production deployment provisioner communicating with an out-of-process
    TrustedDeploymentAuthorityBroker over authenticated OS IPC.
    """
    def __init__(
        self,
        ipc_endpoint: str,
        auth_secret: Optional[str] = None,
    ):
        from events.ipc import OSIPCClient
        self.ipc_endpoint = ipc_endpoint
        self.auth_secret = auth_secret
        self._client = OSIPCClient(endpoint_path=ipc_endpoint, auth_secret=auth_secret)
        self._lock = threading.RLock()

    def get_deployment_id(self) -> str:
        with self._lock:
            resp = self._client.call("get_deployment_id")
            if not resp.get("success"):
                raise RuntimeError(f"Authority broker error: {resp.get('error')}")
            return resp["deployment_id"]

    def get_deployment_status(self) -> DeploymentStatus:
        with self._lock:
            try:
                resp = self._client.call("get_deployment_status")
                if not resp.get("success"):
                    return DeploymentStatus.AUTHORITY_UNAVAILABLE
                return DeploymentStatus(resp["status"])
            except Exception:
                return DeploymentStatus.AUTHORITY_UNAVAILABLE

    def authorize_initial_provisioning(self, authorization_data: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            resp = self._client.call("authorize_initial_provisioning", {"authorization_data": authorization_data})
            if not resp.get("success"):
                raise RuntimeError(f"Authority broker rejected initial provisioning: {resp.get('error')}")

    def record_provisioned(
        self,
        installation_id: str,
        manifest_id: str,
        manifest_version: int,
        root_fingerprint: str,
        payload_digest: Optional[str] = None,
        root_signature: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            resp = self._client.call("record_provisioned", {
                "installation_id": installation_id,
                "manifest_id": manifest_id,
                "manifest_version": manifest_version,
                "root_fingerprint": root_fingerprint,
                "payload_digest": payload_digest,
                "root_signature": root_signature,
            })
            if not resp.get("success"):
                raise RuntimeError(f"Authority broker rejected record_provisioned: {resp.get('error')}")

    def notify_local_state_loss(self) -> None:
        with self._lock:
            resp = self._client.call("notify_local_state_loss")
            if not resp.get("success"):
                raise RuntimeError(f"Authority broker error on notify_local_state_loss: {resp.get('error')}")

    def authorize_reprovisioning(
        self,
        reprovisioning_authorization: Dict[str, Any],
        root_public_key: Optional[Any] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            resp = self._client.call("authorize_reprovisioning", {
                "reprovisioning_authorization": reprovisioning_authorization,
            })
            if not resp.get("success"):
                err = resp.get("error", "Unknown error")
                if "mismatch" in err:
                    from policy.exceptions import CorruptManifestError
                    raise CorruptManifestError(err)
                if "signature" in err.lower() or "root" in err.lower():
                    from policy.exceptions import InvalidManifestSignatureError
                    raise InvalidManifestSignatureError(err)
                raise RuntimeError(f"Authority broker rejected reprovisioning: {err}")
            return resp.get("authorization", reprovisioning_authorization)

    def record_reprovisioned(
        self,
        installation_id: str,
        manifest_id: str,
        manifest_version: int,
        root_fingerprint: str,
        payload_digest: Optional[str] = None,
        root_signature: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            resp = self._client.call("record_reprovisioned", {
                "installation_id": installation_id,
                "manifest_id": manifest_id,
                "manifest_version": manifest_version,
                "root_fingerprint": root_fingerprint,
                "payload_digest": payload_digest,
                "root_signature": root_signature,
            })
            if not resp.get("success"):
                raise RuntimeError(f"Authority broker rejected record_reprovisioned: {resp.get('error')}")

    def close(self) -> None:
        with self._lock:
            self._client.close()


class FailClosedDeploymentProvisioner(TrustedDeploymentProvisioner):
    """Default production provisioner. Fails closed on all genesis, reprovisioning,
    and authority reset requests until an explicit trusted external deployment coordinator is attached.
    """
    def __init__(self, deployment_id: str = "PRODUCTION-UNCONFIGURED"):
        self._deployment_id = deployment_id

    def get_deployment_id(self) -> str:
        return self._deployment_id

    def get_deployment_status(self) -> DeploymentStatus:
        return DeploymentStatus.AUTHORITY_UNAVAILABLE

    def authorize_initial_provisioning(self, authorization_data: Optional[Dict[str, Any]] = None) -> None:
        raise RuntimeError(
            "FailClosedDeploymentProvisioner: No external trusted deployment authority configured. "
            "Initial genesis provisioning is rejected."
        )

    def record_provisioned(
        self,
        installation_id: str,
        manifest_id: str,
        manifest_version: int,
        root_fingerprint: str,
        payload_digest: Optional[str] = None,
        root_signature: Optional[Dict[str, Any]] = None,
    ) -> None:
        raise RuntimeError("FailClosedDeploymentProvisioner: Cannot record provisioning on fail-closed authority.")

    def notify_local_state_loss(self) -> None:
        pass

    def authorize_reprovisioning(self, reprovisioning_authorization: Dict[str, Any], root_public_key: Optional[Any] = None) -> Dict[str, Any]:
        raise RuntimeError(
            "FailClosedDeploymentProvisioner: No external trusted deployment authority configured. "
            "Reprovisioning is rejected."
        )

    def record_reprovisioned(
        self,
        installation_id: str,
        manifest_id: str,
        manifest_version: int,
        root_fingerprint: str,
        payload_digest: Optional[str] = None,
        root_signature: Optional[Dict[str, Any]] = None,
    ) -> None:
        raise RuntimeError("FailClosedDeploymentProvisioner: Cannot record reprovisioning on fail-closed authority.")


class InMemoryTestDeploymentProvisioner(TrustedDeploymentProvisioner):
    """Test-only in-memory deployment provisioner with full external authority state machine.
    Strictly prohibited outside TEST_MODE.
    """
    def __init__(
        self,
        deployment_id: str = "DEPLOYMENT-TEST-001",
        initial_status: DeploymentStatus = DeploymentStatus.UNPROVISIONED,
    ):
        self._check_test_mode()
        self._deployment_id = deployment_id
        self._status = initial_status
        self._consumed_auth_ids: Set[str] = set()
        self._provisioned_records: list = []
        self._lock = threading.RLock()

    @staticmethod
    def _check_test_mode() -> None:
        if not _is_test_mode_active():
            raise RuntimeError("InMemoryTestDeploymentProvisioner is strictly prohibited outside TEST_MODE.")

    def get_deployment_id(self) -> str:
        self._check_test_mode()
        with self._lock:
            return self._deployment_id

    def get_deployment_status(self) -> DeploymentStatus:
        self._check_test_mode()
        with self._lock:
            return self._status

    def authorize_initial_provisioning(self, authorization_data: Optional[Dict[str, Any]] = None) -> None:
        self._check_test_mode()
        with self._lock:
            if self._status == DeploymentStatus.PROVISIONED:
                raise RuntimeError("Genesis bootstrap rejected: external deployment authority is already PROVISIONED. Authority reset prohibited.")
            if self._status == DeploymentStatus.RECOVERY_REQUIRED:
                raise RuntimeError(
                    "Genesis bootstrap rejected: deployment is in RECOVERY_REQUIRED state after complete local-state loss. "
                    "Explicit root-signed external administrative reprovisioning required."
                )
            self._status = DeploymentStatus.PROVISIONING_AUTHORIZED

    def record_provisioned(
        self,
        installation_id: str,
        manifest_id: str,
        manifest_version: int,
        root_fingerprint: str,
        payload_digest: Optional[str] = None,
        root_signature: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._check_test_mode()
        with self._lock:
            self._status = DeploymentStatus.PROVISIONED
            self._provisioned_records.append({
                "installation_id": installation_id,
                "manifest_id": manifest_id,
                "manifest_version": manifest_version,
                "root_fingerprint": root_fingerprint,
                "payload_digest": payload_digest,
                "root_signature": root_signature,
            })

    def notify_local_state_loss(self) -> None:
        self._check_test_mode()
        with self._lock:
            if self._status == DeploymentStatus.PROVISIONED:
                self._status = DeploymentStatus.RECOVERY_REQUIRED

    def authorize_reprovisioning(
        self,
        reprovisioning_authorization: Dict[str, Any],
        root_public_key: Optional[Any] = None,
    ) -> Dict[str, Any]:
        self._check_test_mode()
        import hashlib
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from events.serializer import canonicalize_json
        from policy.exceptions import InvalidManifestSignatureError, CorruptManifestError

        if not isinstance(reprovisioning_authorization, dict):
            raise CorruptManifestError("Reprovisioning authorization must be a dictionary.")

        required_fields = [
            "authorization_id",
            "deployment_id",
            "target_manifest_id",
            "authorized_at",
            "reason",
            "root_fingerprint",
            "is_administrative_reprovisioning",
            "signature",
        ]
        for f in required_fields:
            if f not in reprovisioning_authorization:
                raise CorruptManifestError(f"Reprovisioning authorization missing required field '{f}'.")

        if reprovisioning_authorization.get("is_administrative_reprovisioning") is not True:
            raise CorruptManifestError("Invalid reprovisioning authorization flag.")

        with self._lock:
            auth_id = reprovisioning_authorization["authorization_id"]
            if auth_id in self._consumed_auth_ids:
                raise RuntimeError(f"External deployment authority: reprovisioning authorization '{auth_id}' has already been consumed (replay rejected).")

            if reprovisioning_authorization["deployment_id"] != self._deployment_id:
                raise CorruptManifestError(
                    f"Reprovisioning authorization deployment mismatch: expected '{self._deployment_id}', got '{reprovisioning_authorization['deployment_id']}'."
                )

            if root_public_key is None:
                from benchmark.parity.verify_gate_3_certificate import Gate3PublicKeystore
                root_public_key = Gate3PublicKeystore.get_public_key()
                if root_public_key is None:
                    raise RuntimeError("Canonical Gate 3 Root Authority Public Key is not configured.")

            if not isinstance(root_public_key, ed25519.Ed25519PublicKey):
                raise TypeError("root_public_key must be an Ed25519PublicKey instance.")

            expected_root_fp = hashlib.sha256(root_public_key.public_bytes_raw()).hexdigest()
            if reprovisioning_authorization["root_fingerprint"] != expected_root_fp:
                raise InvalidManifestSignatureError("Reprovisioning authorization root fingerprint mismatch.")

            sig_block = reprovisioning_authorization.get("signature", {})
            if sig_block.get("algorithm") != "ED25519" or sig_block.get("signer_identity") != "Gate3AuthoritativeVerifier":
                raise InvalidManifestSignatureError("Invalid reprovisioning authorization signature metadata.")

            sig_hex = sig_block.get("signature_hex", "")
            if len(sig_hex) != 128:
                raise InvalidManifestSignatureError("Invalid reprovisioning authorization signature length.")

            preimage_dict = {
                "authorization_id": reprovisioning_authorization["authorization_id"],
                "deployment_id": reprovisioning_authorization["deployment_id"],
                "target_manifest_id": reprovisioning_authorization["target_manifest_id"],
                "authorized_at": reprovisioning_authorization["authorized_at"],
                "reason": reprovisioning_authorization["reason"],
                "root_fingerprint": reprovisioning_authorization["root_fingerprint"],
                "is_administrative_reprovisioning": reprovisioning_authorization["is_administrative_reprovisioning"],
            }
            preimage_bytes = canonicalize_json(preimage_dict)
            calc_digest = hashlib.sha256(preimage_bytes).hexdigest()
            if sig_block.get("payload_digest") != calc_digest:
                raise InvalidManifestSignatureError("Reprovisioning authorization payload digest mismatch.")

            try:
                root_public_key.verify(bytes.fromhex(sig_hex), preimage_bytes)
            except InvalidSignature:
                raise InvalidManifestSignatureError("Reprovisioning authorization Ed25519 signature verification failed.")

            self._consumed_auth_ids.add(auth_id)
            self._status = DeploymentStatus.RECOVERY_AUTHORIZED
            return reprovisioning_authorization

    def record_reprovisioned(
        self,
        installation_id: str,
        manifest_id: str,
        manifest_version: int,
        root_fingerprint: str,
        payload_digest: Optional[str] = None,
        root_signature: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._check_test_mode()
        with self._lock:
            self._status = DeploymentStatus.PROVISIONED
            self._provisioned_records.append({
                "installation_id": installation_id,
                "manifest_id": manifest_id,
                "manifest_version": manifest_version,
                "root_fingerprint": root_fingerprint,
                "payload_digest": payload_digest,
                "root_signature": root_signature,
                "reprovisioned": True,
            })

    @classmethod
    def create_reprovisioning_authorization(
        cls,
        deployment_id: str,
        target_manifest_id: str,
        root_private_key: Any,
        reason: str = "CATASTROPHIC_RECOVERY",
    ) -> Dict[str, Any]:
        """Helper to generate a root-signed DeploymentReprovisioningAuthorization."""
        cls._check_test_mode()
        import uuid
        import hashlib
        from datetime import datetime, timezone
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from events.serializer import canonicalize_json

        if not isinstance(root_private_key, ed25519.Ed25519PrivateKey):
            raise TypeError("root_private_key must be an Ed25519PrivateKey instance.")

        auth_id = f"REPROV-{uuid.uuid4().hex[:16]}"
        authorized_at = datetime.now(timezone.utc).isoformat()
        root_fp = hashlib.sha256(root_private_key.public_key().public_bytes_raw()).hexdigest()

        preimage_dict = {
            "authorization_id": auth_id,
            "deployment_id": deployment_id,
            "target_manifest_id": target_manifest_id,
            "authorized_at": authorized_at,
            "reason": reason,
            "root_fingerprint": root_fp,
            "is_administrative_reprovisioning": True,
        }
        preimage_bytes = canonicalize_json(preimage_dict)
        digest = hashlib.sha256(preimage_bytes).hexdigest()
        sig_bytes = root_private_key.sign(preimage_bytes)

        auth_record = dict(preimage_dict)
        auth_record["signature"] = {
            "algorithm": "ED25519",
            "signer_identity": "Gate3AuthoritativeVerifier",
            "public_key_fingerprint": root_fp,
            "payload_digest": digest,
            "signature_hex": sig_bytes.hex(),
            "timestamp": authorized_at,
        }
        return auth_record


class SClassApplication:
    """Explicit application composition root and container.
    Holds the immutable TrustedDeploymentProvisioner dependency for the application lifetime.
    Constructed exclusively at process entrypoint.
    """
    _instance: Optional["SClassApplication"] = None
    _lock = threading.RLock()

    def __init__(self, provisioner: TrustedDeploymentProvisioner):
        if not isinstance(provisioner, TrustedDeploymentProvisioner):
            raise TypeError("provisioner must implement TrustedDeploymentProvisioner ABC.")
        self._provisioner: TrustedDeploymentProvisioner = provisioner
        with SClassApplication._lock:
            if SClassApplication._instance is not None:
                raise RuntimeError("SClassApplication has already been constructed for this process; replacement is prohibited.")
            SClassApplication._instance = self

    @property
    def provisioner(self) -> TrustedDeploymentProvisioner:
        return self._provisioner

    @classmethod
    def get_active_application(cls) -> Optional["SClassApplication"]:
        with cls._lock:
            return cls._instance

    @classmethod
    def is_constructed(cls) -> bool:
        with cls._lock:
            return cls._instance is not None

    @classmethod
    def reset_for_testing(cls) -> None:
        if not _is_test_mode_active():
            raise RuntimeError("reset_for_testing is strictly prohibited outside TEST_MODE.")
        with cls._lock:
            cls._instance = None


class CompositionRootToken:
    """Deprecated capability token. Kept strictly to reject legacy/attacker attempts."""
    def __init__(self, *args, **kwargs):
        raise RuntimeError("CompositionRootToken is obsolete and rejected; use explicit SClassApplication constructor injection.")


class TrustedCompositionRoot:
    """Deprecated static root. Direct invocation is rejected."""
    @classmethod
    def bootstrap_deployment_authority(cls, *args, **kwargs) -> None:
        raise RuntimeError("Direct static composition root bootstrap is prohibited; use SClassApplication constructor injection.")

    @classmethod
    def reset_for_testing(cls) -> None:
        if not _is_test_mode_active():
            raise RuntimeError("reset_for_testing is strictly prohibited outside TEST_MODE.")
        SClassApplication.reset_for_testing()


class DeploymentProvisionerRegistry:
    """Internal construction primitive.
    Inaccessible for direct external or arbitrary runtime mutation.
    Obtains the active provisioner strictly from the constructed SClassApplication,
    or falls back to FailClosedDeploymentProvisioner if unconfigured.
    """
    _lock = threading.RLock()

    @classmethod
    def get_provisioner(cls) -> TrustedDeploymentProvisioner:
        with cls._lock:
            app = SClassApplication.get_active_application()
            if app is not None:
                return app.provisioner
            return FailClosedDeploymentProvisioner()

    @classmethod
    def is_sealed(cls) -> bool:
        with cls._lock:
            return SClassApplication.is_constructed()

    @classmethod
    def bootstrap_provisioner(cls, *args, **kwargs) -> None:
        """Deprecated/prohibited direct bootstrap path. Fails closed."""
        raise RuntimeError("DeploymentProvisionerRegistry cannot be bootstrapped directly; use SClassApplication constructor injection.")

    @classmethod
    def reset_for_testing(cls) -> None:
        if not _is_test_mode_active():
            raise RuntimeError("reset_for_testing is strictly prohibited outside TEST_MODE.")
        with cls._lock:
            SClassApplication.reset_for_testing()


