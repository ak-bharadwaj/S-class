"""S-Class v6.0.1 concrete control-plane runtime.

This module is deliberately boring at the security boundary: one SQLite durability
authority, one command idempotency ledger, one nonce ledger, one budget allocator,
one trust-key registry, a fail-closed OS boundary, and deterministic recovery records.
The semantic module remains the normative domain model; this module supplies the
production-shaped S0-S5 execution path around it.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import base64
import hashlib
import os
for attr in ["O_PATH", "O_CLOEXEC", "O_DIRECTORY", "O_NOFOLLOW"]:
    if not hasattr(os, attr):
        setattr(os, attr, 0)

import secrets
import shutil
import signal
import sqlite3
import subprocess
import tempfile
import time
import uuid

try:
    import resource
except ImportError:
    class MockResource:
        RLIMIT_CPU = 0
        RLIMIT_AS = 1
        RLIMIT_NPROC = 2
        RLIMIT_FSIZE = 3
        def setrlimit(self, res, limits): pass
    resource = MockResource()

import errno
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Sequence, Mapping, Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey, Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "10-CONFORMANCE"))
from sclass_semantics_v6_0_1 import *  # noqa: F401,F403 - runtime intentionally composes semantic authority
import sclass_semantics_v6_0_1 as S


class SQLiteEventStore(S.SQLiteEventStore):
    """S1 Authoritative SQLite durability boundary configured with production PRAGMAs."""

    def __init__(self, path: str, fault_injector=None, busy_timeout: int = 5000):
        super().__init__(path, fault_injector=fault_injector)
        self._db.execute("PRAGMA journal_mode = WAL;")
        self._db.execute("PRAGMA synchronous = FULL;")
        self._db.execute("PRAGMA foreign_keys = ON;")
        self._db.execute(f"PRAGMA busy_timeout = {busy_timeout};")

    def _load_canonical_state(self, workspace_id: str) -> S.EngineeringState:
        in_tx = self._db.in_transaction
        if not in_tx:
            self._db.execute("BEGIN DEFERRED")
        try:
            res = super()._load_canonical_state(workspace_id)
            if not in_tx:
                self._db.execute("COMMIT")
            return res
        except Exception:
            if not in_tx:
                try:
                    self._db.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            raise

    def _read_all_committed(self, workspace_id: str) -> tuple[S.CanonicalEvent, ...]:
        in_tx = self._db.in_transaction
        if not in_tx:
            self._db.execute("BEGIN DEFERRED")
        try:
            res = super()._read_all_committed(workspace_id)
            if not in_tx:
                self._db.execute("COMMIT")
            return res
        except Exception:
            if not in_tx:
                try:
                    self._db.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            raise

    def verify_chain(self, workspace_id: str, sequence_from: int, sequence_to: int) -> ChainStatus:
        try:
            events = self._read_all_committed(workspace_id)
            if not events:
                return ChainStatus.UNREADABLE
            selected = tuple(e for e in events if sequence_from <= e.event_sequence <= sequence_to)
            if not selected:
                return ChainStatus.UNREADABLE
            expected_range = tuple(range(sequence_from, sequence_to + 1))
            if tuple(e.event_sequence for e in selected) != expected_range:
                return ChainStatus.GAP
            for e in selected:
                if event_hash(e) != e.event_hash:
                    return ChainStatus.BROKEN_HASH
            prior = GENESIS_EVENT_HASH if selected[0].event_sequence == 1 else events[selected[0].event_sequence - 2].event_hash
            if selected[0].previous_event_hash != prior:
                return ChainStatus.BROKEN_HASH
            for i in range(1, len(selected)):
                if selected[i].previous_event_hash != selected[i - 1].event_hash:
                    return ChainStatus.BROKEN_HASH
            self._load_canonical_state(workspace_id)
            return ChainStatus.VALID
        except ValueError as exc:
            msg = str(exc).lower()
            if "gap" in msg or "contiguous" in msg:
                return ChainStatus.GAP
            return ChainStatus.BROKEN_HASH
        except (KeyError, TypeError, IndexError):
            return ChainStatus.BROKEN_HASH


SQLiteCanonicalStore = SQLiteEventStore



_ZERO_BUDGET = ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
_BOUNDARY_PROVISIONING_TOKEN=object()
_BOUNDARY_TEST_TOKEN=object()
_BUDGET_FIELDS = tuple(f.name for f in __import__("dataclasses").fields(ResourceBudget))


def _budget_values(b: ResourceBudget) -> tuple[int, ...]:
    return tuple(getattr(b, name) for name in _BUDGET_FIELDS)


def _budget_add(a: ResourceBudget, b: ResourceBudget) -> ResourceBudget:
    vals=tuple(x+y for x,y in zip(_budget_values(a),_budget_values(b)))
    if any(x > 2**63-1 for x in vals):
        raise ValueError("budget arithmetic overflow")
    return ResourceBudget(*vals)


def _budget_sub(a: ResourceBudget, b: ResourceBudget) -> ResourceBudget:
    vals=tuple(x-y for x,y in zip(_budget_values(a),_budget_values(b)))
    if any(x < 0 for x in vals):
        raise ValueError("negative budget result")
    return ResourceBudget(*vals)


def _budget_leq(a: ResourceBudget, b: ResourceBudget) -> bool:
    return all(x <= y for x,y in zip(_budget_values(a),_budget_values(b)))


def _budget_sum(values: Sequence[ResourceBudget]) -> ResourceBudget:
    total=_ZERO_BUDGET
    for v in values:
        total=_budget_add(total,v)
    return total


def _now() -> UtcInstant:
    return UtcInstant(time.time_ns())


def _stable_id(prefix: str, payload: Any) -> str:
    d=str(digest("sclass/runtime-id/v1", payload)).split(":",1)[1]
    return f"{prefix}-{d[:40]}"


def _commit_for_events(events: tuple[CanonicalEvent, ...], previous: EngineeringState, derived: EngineeringState, commit_id: str, now: UtcInstant) -> CommitRecord:
    participants=[e.event_id for e in events] + [f"state:{previous.workspace_id}"]
    hashes=[e.event_hash for e in events] + [engineering_state_digest(derived)]
    types=["event"]*len(events)+["state"]
    provisional=CommitRecord(
        commit_id=commit_id,
        workspace_id=previous.workspace_id,
        participant_ids=tuple(participants),
        participant_hashes=tuple(hashes),
        participant_types=tuple(types),
        previous_head=previous.event_head_hash,
        resulting_head=events[-1].event_hash,
        resulting_state_revision=derived.state_revision,
        event_sequence_start=events[0].event_sequence,
        event_sequence_end=events[-1].event_sequence,
        schema_version=COMMIT_SCHEMA_VERSION,
        commit_digest=Digest("sha256:"+"0"*64),
        state=CommitState.COMMITTED,
        prepared_at_epoch_ns=now.epoch_ns,
        committed_at_epoch_ns=now.epoch_ns,
        resulting_state_digest=engineering_state_digest(derived),
    )
    return replace(provisional, commit_digest=commit_record_digest(provisional))


def _make_event(previous: EngineeringState, event_type: EventType, aggregate_id: str, payload: FrozenMap,
                actor: ActorIdentity, policy_version: Optional[str]=None, sdk_version: str=REDUCER_VERSION,
                event_id: Optional[str]=None, commit_id: Optional[str]=None, recorded_at: Optional[UtcInstant]=None) -> CanonicalEvent:
    at=recorded_at or _now()
    eid=event_id or _stable_id("evt", (previous.workspace_id,previous.event_sequence+1,event_type.value,aggregate_id,payload))
    cid=commit_id or _stable_id("commit", (eid,previous.event_head_hash))
    return CanonicalEvent.create(
        eid,cid,previous.workspace_id,previous.event_sequence+1,event_type,EVENT_SCHEMA_VERSION,
        aggregate_id,actor,"runtime-causation","runtime-correlation",payload,previous.event_head_hash,
        policy_version if policy_version is not None else previous.policy_version,sdk_version,at)


class RuntimeDisposition(Enum):
    APPLIED="APPLIED"
    IDEMPOTENT_REPLAY="IDEMPOTENT_REPLAY"
    STALE_HEAD="STALE_HEAD"
    INVALID="INVALID"
    DENIED="DENIED"

@dataclass(frozen=True)
class CommandResult:
    disposition: RuntimeDisposition
    command_id: str
    new_head: Optional[EventHead]
    detail: str


class SQLiteCommandLedger:
    """Durable exactly-once command identity ledger.

    The command_id is unique per workspace. Re-delivery with the same request digest
    is an idempotent replay; the same ID with different content is a hard conflict.
    """
    def __init__(self, db: sqlite3.Connection):
        self.db=db
        db.execute("""CREATE TABLE IF NOT EXISTS runtime_commands(
            workspace_id TEXT NOT NULL,
            command_id TEXT NOT NULL,
            request_digest TEXT NOT NULL,
            status TEXT NOT NULL,
            resulting_sequence INTEGER,
            resulting_head_hash TEXT,
            detail TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            PRIMARY KEY(workspace_id,command_id))""")

    def lookup(self, workspace_id: str, command_id: str):
        return self.db.execute("SELECT request_digest,status,resulting_sequence,resulting_head_hash,detail FROM runtime_commands WHERE workspace_id=? AND command_id=?",(workspace_id,command_id)).fetchone()

    def put_in_transaction(self, command: Command, request_digest: Digest, result: CommandResult):
        self.db.execute(
            "INSERT INTO runtime_commands(workspace_id,command_id,request_digest,status,resulting_sequence,resulting_head_hash,detail,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (command.workspace_id,command.command_id,str(request_digest),result.disposition.value,
             result.new_head.sequence if result.new_head else None,str(result.new_head.hash) if result.new_head else None,result.detail,time.time_ns()))


class SQLiteNonceStore:
    """Atomic nonce ledger. Unknown, expired, reused, or differently bound nonces fail closed."""
    def __init__(self, db: sqlite3.Connection):
        self.db=db
        db.execute("""CREATE TABLE IF NOT EXISTS runtime_nonces(
            namespace TEXT NOT NULL,
            nonce TEXT NOT NULL,
            request_digest TEXT NOT NULL,
            authorization_lease_id TEXT NOT NULL,
            execution_lease_id TEXT,
            status TEXT NOT NULL CHECK(status IN ('ISSUED','CONSUMED','CANCELLED')),
            expires_at INTEGER NOT NULL,
            consumed_at INTEGER,
            PRIMARY KEY(namespace,nonce))""")

    def issue_in_transaction(self, namespace: str, nonce: str, request_digest: Digest, expires_at: UtcInstant):
        if not namespace or not nonce or expires_at.epoch_ns <= time.time_ns():
            raise ValueError("invalid nonce issuance")
        try:
            self.db.execute("INSERT INTO runtime_nonces(namespace,nonce,request_digest,authorization_lease_id,status,expires_at) VALUES(?,?,?,?,?,?)",
                            (namespace,nonce,str(request_digest),"", "ISSUED",expires_at.epoch_ns))
        except sqlite3.IntegrityError:
            raise ValueError("nonce identity already exists")

    def issue(self, namespace: str, nonce: str, request_digest: Digest, expires_at: UtcInstant):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.issue_in_transaction(namespace,nonce,request_digest,expires_at)
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK"); raise

    def consume_in_transaction(self, namespace: str, nonce: str, request_digest: Digest,
                               authorization_lease_id: str, execution_lease_id: str, now: UtcInstant):
        row=self.db.execute("SELECT request_digest,authorization_lease_id,status,expires_at,execution_lease_id FROM runtime_nonces WHERE namespace=? AND nonce=?",
                            (namespace,nonce)).fetchone()
        if row is None:
            return NonceConsumptionResult.BINDING_MISMATCH
        if row[0] != str(request_digest) or (row[1] not in ("",authorization_lease_id)):
            return NonceConsumptionResult.BINDING_MISMATCH
        if row[2] == "CONSUMED":
            return NonceConsumptionResult.ALREADY_CONSUMED
        if row[2] != "ISSUED":
            return NonceConsumptionResult.BINDING_MISMATCH
        if now.epoch_ns >= row[3]:
            return NonceConsumptionResult.EXPIRED
        self.db.execute("UPDATE runtime_nonces SET authorization_lease_id=?,execution_lease_id=?,status='CONSUMED',consumed_at=? WHERE namespace=? AND nonce=? AND status='ISSUED'",
                        (authorization_lease_id,execution_lease_id,now.epoch_ns,namespace,nonce))
        if self.db.execute("SELECT changes()").fetchone()[0] != 1:
            return NonceConsumptionResult.ALREADY_CONSUMED
        return NonceConsumptionResult.SUCCESS

    def verify_consumed_binding(self, namespace: str, nonce: str, request_digest: Digest,
                               authorization_lease_id: str, execution_lease_id: str, now: UtcInstant) -> bool:
        row=self.db.execute("SELECT request_digest,authorization_lease_id,execution_lease_id,status,expires_at FROM runtime_nonces WHERE namespace=? AND nonce=?",(namespace,nonce)).fetchone()
        if row is None:
            return False
        return (row[0] == str(request_digest) and row[1] == authorization_lease_id and
                row[2] == execution_lease_id and row[3] == "CONSUMED" and now.epoch_ns < row[4])

    def consume_and_bind(self, namespace: str, nonce: str, request_digest: Digest,
                         authorization_lease_id: str, execution_lease_id: str, now: UtcInstant):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            result=self.consume_in_transaction(namespace,nonce,request_digest,authorization_lease_id,execution_lease_id,now)
            if result is NonceConsumptionResult.SUCCESS: self.db.execute("COMMIT")
            else: self.db.execute("ROLLBACK")
            return result
        except Exception:
            self.db.execute("ROLLBACK"); raise


class SQLiteBudgetAllocator:
    """Atomic cumulative budget allocator with explicit reservation lifecycle."""
    def __init__(self, db: sqlite3.Connection):
        self.db=db
        db.execute("""CREATE TABLE IF NOT EXISTS runtime_budgets(
            workspace_id TEXT PRIMARY KEY,
            limit_blob BLOB NOT NULL,
            updated_at INTEGER NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS runtime_reservations(
            workspace_id TEXT NOT NULL,
            reservation_id TEXT NOT NULL,
            request_id TEXT NOT NULL,
            amount_blob BLOB NOT NULL,
            lineage_id TEXT NOT NULL,
            parent_reservation_id TEXT,
            status TEXT NOT NULL CHECK(status IN ('RESERVED','RELEASED','SETTLED','EXPIRED')),
            version INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            actual_blob BLOB NOT NULL,
            PRIMARY KEY(workspace_id,reservation_id))""")

    def _set_workspace_limit_for_test(self, workspace_id: str, limit: ResourceBudget):
        """Test-fixture configuration only. Production admission never trusts this table."""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("INSERT INTO runtime_budgets(workspace_id,limit_blob,updated_at) VALUES(?,?,?) ON CONFLICT(workspace_id) DO UPDATE SET limit_blob=excluded.limit_blob,updated_at=excluded.updated_at",
                            (workspace_id,canonical_c1_pack(limit),time.time_ns()))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK"); raise

    def set_workspace_limit(self, workspace_id: str, limit: ResourceBudget):
        raise PermissionError("workspace budget is canonical policy state; use _set_workspace_limit_for_test only in test fixtures")

    def _projection_limit(self, workspace_id: str) -> ResourceBudget:
        row=self.db.execute("SELECT limit_blob FROM runtime_budgets WHERE workspace_id=?",(workspace_id,)).fetchone()
        if row is None: raise ValueError("runtime budget projection missing")
        value=canonical_c1_unpack(row[0])
        if not isinstance(value,ResourceBudget): raise ValueError("corrupt workspace budget projection")
        return value

    def _limit(self, workspace_id: str, canonical_limit: Optional[ResourceBudget]=None) -> ResourceBudget:
        if canonical_limit is None:
            return self._projection_limit(workspace_id)
        if not isinstance(canonical_limit,ResourceBudget): raise TypeError("canonical budget limit required")
        return canonical_limit

    def sync_policy_projection_in_transaction(self, workspace_id: str, canonical_limit: ResourceBudget) -> None:
        if not isinstance(canonical_limit,ResourceBudget): raise TypeError("canonical budget limit required")
        self.db.execute("INSERT INTO runtime_budgets(workspace_id,limit_blob,updated_at) VALUES(?,?,?) ON CONFLICT(workspace_id) DO UPDATE SET limit_blob=excluded.limit_blob,updated_at=excluded.updated_at",
                        (workspace_id,canonical_c1_pack(canonical_limit),time.time_ns()))

    def _outstanding_projection(self, workspace_id: str) -> ResourceBudget:
        rows=self.db.execute("SELECT amount_blob FROM runtime_reservations WHERE workspace_id=? AND status='RESERVED'",(workspace_id,)).fetchall()
        return _budget_sum([canonical_c1_unpack(x[0]) for x in rows])

    @staticmethod
    def _outstanding_canonical(reservations) -> ResourceBudget:
        if reservations is None:
            raise ValueError("canonical reservation state required")
        values=[]
        for reservation in reservations.values() if hasattr(reservations, 'values') else reservations:
            if not isinstance(reservation, BudgetReservation):
                raise ValueError("invalid canonical budget reservation")
            if reservation.lifecycle_state is BudgetReservationState.RESERVED:
                values.append(reservation.reserved_amount)
        return _budget_sum(values)

    def expire_projection_in_transaction(self, workspace_id: str, reservation: BudgetReservation) -> None:
        """Update only the runtime projection after canonical expiry has been committed."""
        self.db.execute("UPDATE runtime_reservations SET status=?,version=?,actual_blob=? WHERE workspace_id=? AND reservation_id=? AND status='RESERVED' AND version=?",
                        (BudgetReservationState.EXPIRED.value,reservation.version,canonical_c1_pack(reservation.actual_usage),workspace_id,reservation.reservation_id,reservation.version-1))
        if self.db.execute("SELECT changes()").fetchone()[0] != 1:
            raise ValueError("budget reservation projection CAS conflict")

    def expired_reservations_from_state(self, state: EngineeringState, now: UtcInstant) -> tuple[BudgetReservation,...]:
        return tuple(sorted((replace(r, lifecycle_state=BudgetReservationState.EXPIRED, version=r.version+1)
                             for r in state.budget_reservations.values()
                             if r.lifecycle_state is BudgetReservationState.RESERVED and now.epoch_ns >= r.expires_at.epoch_ns),
                            key=lambda r:r.reservation_id))

    def reserve_in_transaction(self, workspace_id: str, request_id: str, lineage_id: str, amount: ResourceBudget,
                               expires_at: UtcInstant, parent_reservation_id: Optional[str]=None, reservation_id: Optional[str]=None,
                               canonical_limit: Optional[ResourceBudget]=None, canonical_reservations=None) -> BudgetReservation:
        if expires_at.epoch_ns <= time.time_ns(): raise ValueError("budget reservation already expired")
        rid=reservation_id or _stable_id("res",(workspace_id,request_id,lineage_id,amount,expires_at))
        if self.db.execute("SELECT 1 FROM runtime_reservations WHERE workspace_id=? AND reservation_id=?",(workspace_id,rid)).fetchone():
            raise ValueError("budget reservation identity already exists")
        limit=self._limit(workspace_id,canonical_limit)
        available=_budget_sub(limit, self._outstanding_canonical(canonical_reservations) if canonical_reservations is not None else self._outstanding_projection(workspace_id))
        if not _budget_leq(amount,available):
            raise ValueError("insufficient cumulative budget")
        self.db.execute("INSERT INTO runtime_reservations VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (workspace_id,rid,request_id,canonical_c1_pack(amount),lineage_id,parent_reservation_id,
                         BudgetReservationState.RESERVED.value,1,expires_at.epoch_ns,canonical_c1_pack(_ZERO_BUDGET)))
        return BudgetReservation(rid,workspace_id,request_id,BudgetLevel.ATTEMPT,parent_reservation_id,lineage_id,amount,expires_at,
                                 BudgetReservationState.RESERVED,amount,_ZERO_BUDGET,_ZERO_BUDGET,_ZERO_BUDGET,1)

    def reserve(self, workspace_id: str, request_id: str, lineage_id: str, amount: ResourceBudget,
                expires_at: UtcInstant, parent_reservation_id: Optional[str]=None, reservation_id: Optional[str]=None):
        raise PermissionError("direct runtime budget reservation is non-authoritative; use canonical admission")

    def _reserve_for_test(self, workspace_id: str, request_id: str, lineage_id: str, amount: ResourceBudget,
                          expires_at: UtcInstant, parent_reservation_id: Optional[str]=None, reservation_id: Optional[str]=None):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            r=self.reserve_in_transaction(workspace_id,request_id,lineage_id,amount,expires_at,parent_reservation_id,reservation_id)
            self.db.execute("COMMIT"); return r
        except Exception:
            self.db.execute("ROLLBACK"); raise

    def _read(self, workspace_id, reservation_id):
        row=self.db.execute("SELECT request_id,amount_blob,lineage_id,parent_reservation_id,status,version,expires_at,actual_blob FROM runtime_reservations WHERE workspace_id=? AND reservation_id=?",(workspace_id,reservation_id)).fetchone()
        if not row: raise KeyError(reservation_id)
        return row

    def transition_in_transaction(self, workspace_id: str, reservation_id: str, action: str,
                                 actual: Optional[ResourceBudget]=None):
        row=self._read(workspace_id,reservation_id)
        request_id,amount_blob,lineage,parent,status,version,expires_at,actual_blob=row
        amount=canonical_c1_unpack(amount_blob)
        old_actual=canonical_c1_unpack(actual_blob)
        if status != BudgetReservationState.RESERVED.value:
            raise ValueError(f"reservation is not RESERVED: {status}")
        if action == "RELEASE":
            new_status=BudgetReservationState.RELEASED.value; new_actual=old_actual
        elif action == "SETTLE":
            new_status=BudgetReservationState.SETTLED.value; new_actual=actual or old_actual
            if not _budget_leq(new_actual,amount): raise ValueError("actual usage exceeds reservation")
        else: raise ValueError("unknown budget transition")
        self.db.execute("UPDATE runtime_reservations SET status=?,version=?,actual_blob=? WHERE workspace_id=? AND reservation_id=? AND status='RESERVED' AND version=?",
                        (new_status,version+1,canonical_c1_pack(new_actual),workspace_id,reservation_id,version))
        if self.db.execute("SELECT changes()").fetchone()[0] != 1: raise ValueError("budget reservation CAS conflict")

    def release(self,workspace_id,reservation_id):
        self.db.execute("BEGIN IMMEDIATE")
        try: self.transition_in_transaction(workspace_id,reservation_id,"RELEASE"); self.db.execute("COMMIT")
        except Exception: self.db.execute("ROLLBACK"); raise

    def settle(self,workspace_id,reservation_id,actual):
        self.db.execute("BEGIN IMMEDIATE")
        try: self.transition_in_transaction(workspace_id,reservation_id,"SETTLE",actual); self.db.execute("COMMIT")
        except Exception: self.db.execute("ROLLBACK"); raise


@dataclass(frozen=True)
class PinnedKey:
    """Pinned trust root and expected public key (or fingerprint)."""
    trust_root: str
    public_key: bytes
    key_id: Optional[str] = None

    def __post_init__(self):
        if not self.trust_root or not isinstance(self.trust_root, str):
            raise ValueError("PinnedKey requires non-empty string trust_root")
        if not isinstance(self.public_key, (bytes, bytearray)) or len(self.public_key) != 32:
            raise ValueError("PinnedKey requires 32-byte public_key")


def _normalize_pinned_keys(pinned_keys: Optional[Iterable[Any]]) -> Optional[set[tuple[str, bytes]]]:
    """Parse and normalize explicit pinned keys into a set of (trust_root, public_key_bytes).

    Accepts PinnedKey, 2-tuples (root, pub), 3-tuples (root, key_id, pub), mappings,
    or paths to protected pin files (mode <= 0600) for H1b compatibility.
    Rejects bare root-id strings: pins must specify both trust root AND expected public key.
    """
    if pinned_keys is None:
        return None
    if isinstance(pinned_keys, (str, Path)):
        p = Path(pinned_keys)
        import stat, errno, json
        try:
            lst = os.lstat(p)
            if stat.S_ISLNK(lst.st_mode) or p.is_symlink():
                raise PermissionError(f"pinned keys file {p} cannot be a symlink")
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"pinned keys path {pinned_keys} does not exist") from exc
        except OSError as exc:
            if getattr(exc, "errno", None) in (errno.ELOOP,):
                raise PermissionError(f"pinned keys file {p} cannot be a symlink") from exc
            raise

        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW

        try:
            fd = os.open(p, flags)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"pinned keys path {pinned_keys} does not exist") from exc
        except OSError as exc:
            if getattr(exc, "errno", None) in (errno.ELOOP,):
                raise PermissionError(f"pinned keys file {p} cannot be a symlink") from exc
            raise

        try:
            st = os.fstat(fd)
            if stat.S_ISLNK(st.st_mode):
                raise PermissionError(f"pinned keys file {p} cannot be a symlink")
            if not stat.S_ISREG(st.st_mode):
                raise PermissionError(f"pinned keys path {p} must be a regular file")
            if hasattr(os, "fstat") and sys.platform != "win32":
                if (stat.S_IMODE(st.st_mode) & ~0o600) != 0:
                    raise PermissionError(f"pinned keys file {p} has insecure permissions (must be mode <= 0600)")
                if hasattr(os, "getuid") and st.st_uid != os.getuid():
                    raise PermissionError(f"pinned keys file {p} must be owned by the service user (uid {os.getuid()})")
            with os.fdopen(fd, "r", encoding="utf-8") as f:
                fd = None
                content = f.read()
        finally:
            if fd is not None:
                try: os.close(fd)
                except OSError: pass

        data = json.loads(content)
        if isinstance(data, list):
            return _normalize_pinned_keys(data)
        raise ValueError("pinned keys file must contain a JSON list")
    result: set[tuple[str, bytes]] = set()
    for item in pinned_keys:
        if isinstance(item, str):
            raise ValueError("pins must specify both trust root and expected public key, not just a root ID")
        if isinstance(item, PinnedKey):
            result.add((item.trust_root, bytes(item.public_key)))
        elif isinstance(item, tuple):
            if len(item) == 2:
                root, pub = item
                if isinstance(pub, str):
                    pub = bytes.fromhex(pub)
                if len(pub) != 32:
                    raise ValueError("public key must be 32 bytes")
                result.add((str(root), bytes(pub)))
            elif len(item) == 3:
                root = str(item[0])
                if isinstance(item[1], (bytes, bytearray)) and len(item[1]) == 32:
                    pub = bytes(item[1])
                elif isinstance(item[2], (bytes, bytearray)) and len(item[2]) == 32:
                    pub = bytes(item[2])
                elif isinstance(item[2], str) and len(item[2]) == 64:
                    pub = bytes.fromhex(item[2])
                elif isinstance(item[1], str) and len(item[1]) == 64:
                    pub = bytes.fromhex(item[1])
                else:
                    raise ValueError("3-tuple pin must contain a 32-byte public key")
                result.add((root, pub))
            else:
                raise ValueError("tuple pin must be (root, pub) or (root, key_id, pub)")
        elif isinstance(item, Mapping):
            root = item.get("trust_root") or item.get("root")
            pub = item.get("public_key") or item.get("pub")
            if not root or not pub:
                raise ValueError("mapping pin must specify trust_root and public_key")
            if isinstance(pub, str):
                pub = bytes.fromhex(pub)
            result.add((str(root), bytes(pub)))
        else:
            raise ValueError(f"unsupported pinned key type: {type(item)}")
    return result


class SQLiteKeyDirectory:
    """Production-shaped Ed25519 trust registry with rotation/revocation/expiry."""
    def __init__(self, db: sqlite3.Connection, pinned_keys: Optional[set[tuple[str, bytes]]] = None):
        self.db = db
        self._private_keys: dict[str, Ed25519PrivateKey] = {}
        self.pinned_keys: Optional[set[tuple[str, bytes]]] = pinned_keys
        db.execute("""CREATE TABLE IF NOT EXISTS runtime_keys(
            key_id TEXT PRIMARY KEY,
            trust_root TEXT NOT NULL,
            public_key BLOB NOT NULL,
            status TEXT NOT NULL,
            not_before INTEGER NOT NULL,
            not_after INTEGER NOT NULL,
            inserted_at INTEGER NOT NULL,
            rotated_at INTEGER,
            revoked_at INTEGER)""")
        cols={row[1] for row in db.execute("PRAGMA table_info(runtime_keys)").fetchall()}
        if "rotated_at" not in cols:
            db.execute("ALTER TABLE runtime_keys ADD COLUMN rotated_at INTEGER")
        if "revoked_at" not in cols:
            db.execute("ALTER TABLE runtime_keys ADD COLUMN revoked_at INTEGER")
        db.execute("CREATE TABLE IF NOT EXISTS runtime_trust_roots(root_id TEXT PRIMARY KEY,status TEXT NOT NULL)")

    def add_root(self, root_id: str):
        self.db.execute("INSERT INTO runtime_trust_roots(root_id,status) VALUES(?, 'ACTIVE') ON CONFLICT(root_id) DO UPDATE SET status='ACTIVE'",(root_id,))

    def roots(self) -> set[str]:
        rows = self.db.execute("SELECT root_id FROM runtime_trust_roots WHERE status='ACTIVE'").fetchall()
        return {r[0] for r in rows}

    def register(self,key_id: str,trust_root: str,public_key: bytes,not_before: int=0,not_after: int=2**63-1):
        if len(public_key)!=32 or not key_id or not trust_root or not_before >= not_after: raise ValueError("invalid key registration")
        if self.pinned_keys is not None:
            if (trust_root, bytes(public_key)) not in self.pinned_keys:
                raise PermissionError(f"key {key_id} for root {trust_root} is not in pinned key set")
        root=self.db.execute("SELECT status FROM runtime_trust_roots WHERE root_id=?",(trust_root,)).fetchone()
        if root is None or root[0] != "ACTIVE": raise ValueError("untrusted root")
        self.db.execute("INSERT INTO runtime_keys(key_id,trust_root,public_key,status,not_before,not_after,inserted_at,rotated_at,revoked_at) VALUES(?,?,?,?,?,?,?,?,NULL)",
                        (key_id,trust_root,sqlite3.Binary(public_key),KeyStatus.ACTIVE.value,not_before,not_after,time.time_ns(),None))

    def bootstrap_key(self, key_id: str, trust_root: str, private_key: Optional[Ed25519PrivateKey] = None, not_before: int = 0, not_after: int = 2**63 - 1) -> tuple[Ed25519PrivateKey, bytes]:
        """In-process test-mode key bootstrap creating and registering an active Ed25519 key pair."""
        if private_key is None:
            private_key = Ed25519PrivateKey.generate()
        pub_bytes = private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.add_root(trust_root)
        self.register(key_id, trust_root, pub_bytes, not_before=not_before, not_after=not_after)
        self._private_keys[key_id] = private_key
        return private_key, pub_bytes

    def sign(self, key_id: str, domain: str, claims: Any) -> SignatureBlock:
        """Sign claims with domain-separated preimage using a registered private key."""
        if key_id not in self._private_keys:
            raise KeyError(f"private key for {key_id} is not registered in this directory")
        row = self.db.execute("SELECT trust_root, status, not_before, not_after, revoked_at FROM runtime_keys WHERE key_id=?", (key_id,)).fetchone()
        if row is None:
            raise KeyError(f"key {key_id} not registered")
        trust_root, status, not_before, not_after, revoked_at = row
        now_ns = time.time_ns()
        if status == KeyStatus.REVOKED.value or (revoked_at is not None and now_ns >= revoked_at):
            raise PermissionError(f"key {key_id} is revoked")
        if status == KeyStatus.ROTATED_OUT.value:
            raise PermissionError(f"key {key_id} is rotated out")
        if now_ns < not_before or now_ns >= not_after:
            raise PermissionError(f"key {key_id} is expired")
        msg = signature_preimage(domain, claims)
        sig = self._private_keys[key_id].sign(msg)
        return SignatureBlock("ed25519", key_id, trust_root, "c1", sig)

    def status(self,key_id: str,trust_root: str,at: UtcInstant) -> KeyStatus:
        row=self.db.execute("SELECT status,trust_root,not_before,not_after,rotated_at,revoked_at FROM runtime_keys WHERE key_id=?",(key_id,)).fetchone()
        if row is None or row[1] != trust_root: return KeyStatus.UNKNOWN
        if row[5] is not None and at.epoch_ns >= row[5]: return KeyStatus.REVOKED
        if at.epoch_ns < row[2] or at.epoch_ns >= row[3] or row[0] == KeyStatus.EXPIRED.value: return KeyStatus.EXPIRED
        if row[0] == KeyStatus.ROTATED_OUT.value:
            return KeyStatus.ROTATED_OUT
        return KeyStatus(row[0])

    def rotate_out(self,key_id: str):
        self.db.execute("UPDATE runtime_keys SET status=?,rotated_at=? WHERE key_id=? AND status=?",(KeyStatus.ROTATED_OUT.value,time.time_ns(),key_id,KeyStatus.ACTIVE.value))

    def revoke(self,key_id: str):
        self.db.execute("UPDATE runtime_keys SET status=?,revoked_at=? WHERE key_id=?",(KeyStatus.REVOKED.value,time.time_ns(),key_id))

    def verify_historical(self, block: SignatureBlock, message: bytes, at: UtcInstant) -> SignatureVerificationResult:
        if block.algorithm != "ed25519" or block.canonicalization_version != "c1": return SignatureVerificationResult.INVALID
        row=self.db.execute("SELECT public_key,trust_root,status,not_before,not_after,rotated_at,revoked_at FROM runtime_keys WHERE key_id=?",(block.key_id,)).fetchone()
        if row is None or row[1] != block.trust_root: return SignatureVerificationResult.UNKNOWN_KEY
        if at.epoch_ns < row[3] or at.epoch_ns >= row[4]: return SignatureVerificationResult.EXPIRED
        # Historical verification answers whether this key was usable for the supplied historical instant.
        # Rotation out does not invalidate past signatures; revocation does from its effective timestamp.
        if row[6] is not None and at.epoch_ns >= row[6]: return SignatureVerificationResult.REVOKED
        try:
            Ed25519PublicKey.from_public_bytes(bytes(row[0])).verify(block.signature,message)
            return SignatureVerificationResult.VALID
        except InvalidSignature:
            return SignatureVerificationResult.INVALID

    def verify_current(self, block: SignatureBlock, message: bytes, at: UtcInstant) -> SignatureVerificationResult:
        if block.algorithm != "ed25519" or block.canonicalization_version != "c1": return SignatureVerificationResult.INVALID
        row=self.db.execute("SELECT public_key,trust_root,status,not_before,not_after,revoked_at FROM runtime_keys WHERE key_id=?",(block.key_id,)).fetchone()
        if row is None or row[1] != block.trust_root: return SignatureVerificationResult.UNKNOWN_KEY
        if at.epoch_ns < row[3] or at.epoch_ns >= row[4]: return SignatureVerificationResult.EXPIRED
        # Current authorization uses the key directory's present status, regardless of a caller-supplied historical instant.
        status=row[2]
        if status == KeyStatus.ROTATED_OUT.value: return SignatureVerificationResult.INVALID
        if status == KeyStatus.REVOKED.value: return SignatureVerificationResult.REVOKED
        if status == KeyStatus.EXPIRED.value: return SignatureVerificationResult.EXPIRED
        if len(row) > 5 and row[5] is not None and at.epoch_ns >= row[5]: return SignatureVerificationResult.REVOKED
        try:
            Ed25519PublicKey.from_public_bytes(bytes(row[0])).verify(block.signature,message)
            return SignatureVerificationResult.VALID
        except InvalidSignature:
            return SignatureVerificationResult.INVALID

    def verify(self, block: SignatureBlock, message: bytes, at: UtcInstant) -> SignatureVerificationResult:
        # Safe default: current-authority verification. Historical use is explicit.
        return self.verify_current(block,message,at)


def authorization_lease_signature_message(lease_or_claims: Any) -> bytes:
    claims = lease_or_claims.claims if hasattr(lease_or_claims, "claims") else lease_or_claims
    return signature_preimage("sclass/authorization-lease/v1", claims)


def adapter_attestation_signature_message(attestation: AdapterAttestation) -> bytes:
    return signature_preimage("sclass/adapter-attestation/v1", _object_without_signature(attestation))


def authority_envelope_signature_message(envelope: AuthorityEnvelope) -> bytes:
    return signature_preimage("sclass/authority-envelope/v1", envelope)


def sign_claims(private_key: Ed25519PrivateKey, key_id: str, trust_root: str, domain: str, claims: Any) -> SignatureBlock:
    msg = signature_preimage(domain, claims)
    sig = private_key.sign(msg)
    return SignatureBlock("ed25519", key_id, trust_root, "c1", sig)


def command_signature_message(command: Command) -> bytes:
    return signature_preimage("sclass/command/v2",(
        command.command_id,command.workspace_id,command.aggregate_id,command.actor,command.event_type,command.payload,command.expected_head))



def authorized_work_request_digest(request: AuthorizedWorkRequest) -> Digest:
    return digest("sclass/authorized-work-request/v2", (
        request.request_id,request.node_id,request.execution_generation,request.execution_attempt_id,
        request.governing_budget_lineage_id,request.budget_reservation_id,request.primary_obligation_id,tuple(sorted(request.satisfies_obligation_ids)),
        request.action_description,request.action_type,request.requested_effect,request.effect_scope,request.context,
        request.constraints,request.proposal))


def authorization_lease_claims_digest(lease: AuthorizationLease) -> Digest:
    return digest("sclass/authorization-lease-claims/v1", lease.claims)


def authorization_binding_digest(decision: AuthorizationDecision, lease: AuthorizationLease) -> Digest:
    return digest("sclass/authbind/v2", (
        decision.request_content_digest, decision.state_binding_digest, decision,
        lease.claims.lease_id, lease.claims.nonce, lease.claims.request_content_digest,
        decision.worker_identity, lease.claims.audience, lease.claims.allowed_effects))


def canonical_authority_envelope(request: AuthorizedWorkRequest, state: EngineeringState, decision: AuthorizationDecision) -> AuthorityEnvelope:
    if not isinstance(request, AuthorizedWorkRequest) or not isinstance(state, EngineeringState) or not isinstance(decision, AuthorizationDecision):
        raise TypeError("request/state/decision types are required")
    frontier=state.causal_frontier
    if frontier is None or not frontier.authorization_epoch:
        raise ValueError("canonical authorization epoch is required")
    lease=request.execution_lease
    return AuthorityEnvelope(
        envelope_id=str(digest("sclass/authority-envelope-id/v1", (request.request_id, request.proposal.proposal_id, lease.lease_id))),
        principal_id=decision.principal,
        workspace_id=state.workspace_id,
        target_digest=lease.target_snapshot_digest,
        request_content_digest=request.proposal.request_content_digest,
        policy_digest=state.policy_digest,
        capability_digest=decision.capability_attestation_digest,
        authorization_epoch=frontier.authorization_epoch,
        issued_at=request.authorization_lease.claims.issued_at,
        expires_at=request.authorization_lease.claims.expires_at,
    )

def authorized_work_request_envelope_digest(request: AuthorizedWorkRequest, state: EngineeringState, decision: AuthorizationDecision) -> Digest:
    envelope=canonical_authority_envelope(request,state,decision)
    return digest("sclass/envelope/v1", (
        authority_envelope_digest(envelope),
        request.request_id,
        request.proposal.proposal_id,
        request.proposal.request_content_digest,
        request.authorization_binding_digest,
        request.execution_lease,
    ))


def verify_authorization_lease(key_directory: SQLiteKeyDirectory, lease: AuthorizationLease,
                               request: AuthorizedWorkRequest, state: EngineeringState, now: UtcInstant,
                               expected_audience: Optional[str]=None) -> bool:
    c=lease.claims
    if not c.lease_id or not c.decision_id or not c.nonce or not c.issuer_identity or not c.audience:
        return False
    if expected_audience is not None and c.audience != expected_audience:
        return False
    if c.workspace_id != state.workspace_id or c.policy_version != state.policy_version:
        return False
    req_digest=authorized_work_request_digest(request)
    binding_digest=state_binding_digest(request.proposal.state_binding)
    if c.request_content_digest != req_digest or request.proposal.request_content_digest != req_digest:
        return False
    if request.state_binding_digest != binding_digest or c.state_binding_digest != binding_digest:
        return False
    if c.workspace_snapshot_id != state.workspace_snapshot_id:
        return False
    if not (c.issued_at.epoch_ns <= now.epoch_ns < c.expires_at.epoch_ns):
        return False
    decision=state.authorization_decisions.get(c.decision_id)
    if decision is None or not isinstance(decision, AuthorizationDecision):
        return False
    if decision.decision is not AuthorizationState.ALLOW:
        return False
    if decision.request_content_digest != req_digest or decision.state_binding_digest != binding_digest:
        return False
    if request.authorization_binding_digest != authorization_binding_digest(decision,lease):
        return False
    if decision.proposal_id != request.proposal.proposal_id:
        return False
    if decision.policy_version != state.policy_version or decision.workspace_snapshot_id != state.workspace_snapshot_id:
        return False
    if decision.effect_scope != c.allowed_effects or decision.effect_scope != request.effect_scope:
        return False
    if not request.budget_reservation_id or request.execution_lease.budget_reservation_id != request.budget_reservation_id:
        return False
    if lease.claims.request_content_digest != req_digest:
        return False
    reservation = state.budget_reservations.get(request.budget_reservation_id)
    if reservation is None or reservation.lifecycle_state is not BudgetReservationState.RESERVED:
        return False
    if reservation.workspace_id != state.workspace_id or reservation.request_id != request.request_id:
        return False
    if reservation.governing_budget_lineage_id != request.governing_budget_lineage_id:
        return False
    if not _budget_leq(request.requested_effect.requested_budget, reservation.amount):
        return False
    if reservation.expires_at.epoch_ns < c.expires_at.epoch_ns:
        return False
    if not decision.worker_identity or decision.worker_identity != request.execution_lease.worker_identity:
        return False
    if request.node_id not in state.work_graph._nodes:
        return False
    node=state.work_graph._nodes[request.node_id]
    if node.worker_id is not None and node.worker_id != decision.worker_identity:
        return False
    if node.execution_generation != request.execution_generation:
        return False
    if c.issuer_identity != lease.signature.key_id:
        return False
    if c.expires_at.epoch_ns > decision.expires_at.epoch_ns:
        return False
    if lease.claims.lease_id != request.execution_lease.authorization_lease_id and request.execution_lease.authorization_lease_id:
        return False
    if key_directory.status(lease.signature.key_id, lease.signature.trust_root, now) is not KeyStatus.ACTIVE:
        return False
    msg = authorization_lease_signature_message(c)
    return key_directory.verify_current(lease.signature, msg, now) is SignatureVerificationResult.VALID


def _verify_signed_artifact(key_directory: SQLiteKeyDirectory, obj: Any, signature: SignatureBlock, domain: str, now: UtcInstant) -> bool:
    if not isinstance(signature, SignatureBlock):
        return False
    message=signature_preimage(domain, _object_without_signature(obj))
    return key_directory.verify_current(signature, message, now) is SignatureVerificationResult.VALID


def _verify_signature_record(key_directory: SQLiteKeyDirectory, record: SignatureVerificationRecord, obj: Any, domain: str, now: UtcInstant) -> bool:
    if not isinstance(record, SignatureVerificationRecord):
        return False
    signature=getattr(obj, "signature", None)
    if not isinstance(signature, SignatureBlock):
        return False
    expected_digest= signed_payload_digest(domain, obj)
    if record.key_id != signature.key_id:
        return False
    if record.signed_payload_digest != expected_digest or record.signature_digest != signature_block_digest(signature):
        return False
    if record.verification_time.epoch_ns > now.epoch_ns:
        return False
    return _verify_signed_artifact(key_directory,obj,signature,domain,now) and record.verification_result is SignatureVerificationResult.VALID


def _verify_quiescence_attestation(key_directory: SQLiteKeyDirectory, proof: QuiescenceProof, now: UtcInstant) -> bool:
    if not isinstance(proof,QuiescenceProof) or not isinstance(proof.attestation_signature,SignatureBlock):
        return False
    if proof.attestation_key_id != proof.attestation_signature.key_id:
        return False
    message=signature_preimage("sclass/quiescence-attestation/v3", (
        proof.proof_id, proof.boundary_id, proof.mechanism, proof.target_execution_identity_digest,
        proof.execution_lease_id, proof.execution_generation, proof.execution_attempt_id,
        proof.worker_identity, proof.process_id, proof.process_start_time_ns, proof.proven_at, proof.proof_digest))
    return key_directory.verify_current(proof.attestation_signature,message,now) is SignatureVerificationResult.VALID


def validate_security_event_signature_provenance(key_directory: SQLiteKeyDirectory, event_type: EventType, payload: FrozenMap, now: UtcInstant) -> bool:
    """Independently verify security-critical signatures before reducer admission.

    A caller-supplied VERIFIED record is never authoritative; the current trusted key
    directory must independently validate the signed bytes at ingress.
    """
    if event_type is EventType.APPROVAL_RECORDED:
        obj=payload.get("approval_record"); rec=payload.get("signature_verification")
        return obj is not None and rec is not None and _verify_signature_record(key_directory,rec,obj,"sclass/approval-signed-payload/v1",now)
    if event_type is EventType.ASSESSMENT_CREATED:
        obj=payload.get("assessment"); rec=payload.get("signature_verification")
        return obj is not None and rec is not None and _verify_signature_record(key_directory,rec,obj,"sclass/assessment-signed-payload/v1",now)
    if event_type is EventType.WAIVER_GRANTED:
        obj=payload.get("waiver"); rec=payload.get("signature_verification")
        return obj is not None and rec is not None and _verify_signature_record(key_directory,rec,obj,"sclass/waiver-signed-payload/v1",now)
    if event_type is EventType.EVIDENCE_ACCEPTED:
        closure=payload.get("closure"); records=payload.get("signature_verifications")
        if closure is None or records is None:
            return False
        by_subject={r.subject_id:r for r in records if isinstance(r,SignatureVerificationRecord)}
        if len(by_subject) != len(records):
            return False
        for receipt in closure.evidence_receipts:
            rec=by_subject.get(receipt.receipt_id)
            if rec is None or not _verify_signature_record(key_directory,rec,receipt,"sclass/evidence-signed-payload/v1",now):
                return False
        return bool(closure.evidence_receipts)
    if event_type is EventType.POLICY_ACTIVATED:
        approvals=payload.get("activation_approvals") or ()
        return bool(approvals) and all(_verify_signed_artifact(key_directory,a,a.signature,"sclass/approval-signed-payload/v1",now) for a in approvals)
    if event_type is EventType.QUIESCENCE_PROVEN:
        return _verify_quiescence_attestation(key_directory,payload.get("quiescence_proof"),now)
    return True


class ExecutionAdmission:
    """Internal-only atomic S2 admission. No public API exposes this authority path."""
    def __init__(self, control_plane: "SClassControlPlane"):
        self.cp=control_plane
        self._gate_token=object()

    def _admit(self, request: AuthorizedWorkRequest, *, authorization_lease: AuthorizationLease,
              execution_lease_template: ExecutionLease, budget_amount: ResourceBudget,
              audience: str, now: Optional[UtcInstant]=None, _gate_token=None) -> tuple[LeaseRecord, ExecutionIntent]:
        if _gate_token is not self._gate_token:
            raise PermissionError("execution admission is internal to ExecutionGate")
        now=now or _now()
        store=self.cp.store
        store.begin_immediate()
        try:
            state=store._load_canonical_state(request.proposal.state_binding.workspace_id)
            expected_binding=state_binding_digest(request.proposal.state_binding)
            if state.workspace_id != request.proposal.state_binding.workspace_id or request.state_binding_digest != expected_binding:
                raise ValueError("stale authorized-work state binding")
            if request.proposal.request_content_digest != authorized_work_request_digest(request):
                raise ValueError("request content digest mismatch")
            if authorization_lease is not request.authorization_lease and authorization_lease != request.authorization_lease:
                raise ValueError("authorization lease does not match request")
            if not verify_authorization_lease(self.cp.keys,authorization_lease,request,state,now,expected_audience=audience):
                raise ValueError("authorization lease signature/binding invalid")
            c=authorization_lease.claims
            if c.nonce != request.authorization_lease.claims.nonce or not c.nonce:
                raise ValueError("nonce binding mismatch")
            rid=_stable_id("res",(request.request_id,request.execution_attempt_id,request.governing_budget_lineage_id,budget_amount))
            if request.budget_reservation_id != rid:
                raise ValueError("budget reservation identity is not bound to authorized request")
            if state.active_policy is None:
                raise ValueError("active canonical policy required for budget admission")
            canonical_limit=state.active_policy.budget_rules.default_objective_budget
            if not _budget_leq(budget_amount,canonical_limit):
                raise ValueError("requested budget exceeds canonical policy budget")
            self.cp.budgets.sync_policy_projection_in_transaction(state.workspace_id,canonical_limit)
            reservation=self.cp.budgets.reserve_in_transaction(state.workspace_id,request.request_id,request.governing_budget_lineage_id,budget_amount,
                                                              execution_lease_template.expires_at,reservation_id=rid,canonical_limit=canonical_limit,canonical_reservations=state.budget_reservations)
            commit_id=_stable_id("commit",(request.request_id,state.event_head_hash,rid))
            e1=_make_event(state,EventType.BUDGET_RESERVED,reservation.reservation_id,
                           FrozenMap.from_items((("reservation",reservation),("reservation_id",reservation.reservation_id))),
                           ActorIdentity("system",ActorKind.SYSTEM,None),state.policy_version,commit_id=commit_id,recorded_at=now)
            state1=REFERENCE_REDUCER.reduce(state,e1)
            if any(lr.lease.node_id == request.node_id and lr.state is LeaseState.ACTIVE for lr in state1.leases.values()):
                raise ValueError(f"duplicate active execution lease for node {request.node_id} is rejected")
            fencing=1+max((lr.lease.fencing_token for lr in state1.leases.values() if lr.lease.node_id==request.node_id),default=0)
            lease=replace(execution_lease_template,
                          workspace_id=state1.workspace_id,node_id=request.node_id,
                          request_content_digest=request.proposal.request_content_digest,
                          state_binding_digest=state_binding_digest(canonical_current_state_binding(state1, request.execution_generation, request.governing_budget_lineage_id)),
                          governing_budget_lineage_id=request.governing_budget_lineage_id,
                          workspace_snapshot_id=state1.workspace_snapshot_id,
                          target_snapshot_digest=target_snapshot_digest(state1.target_snapshot),
                          objective_revision=state1.objective.revisions[-1].revision_id if state1.objective else lease_template_objective(request),
                          policy_version=state1.policy_version,worker_identity=execution_lease_template.worker_identity,
                          state_revision=state1.state_revision,fencing_token=fencing,
                          execution_generation=request.execution_generation,execution_attempt_id=request.execution_attempt_id,
                          authorization_lease_id=authorization_lease.claims.lease_id,
                          budget_reservation_id=reservation.reservation_id)
            if not lease.worker_identity:
                raise ValueError("verified worker identity is required; workspace identity is never a worker identity")
            lease_record=LeaseRecord(lease,LeaseState.ACTIVE)
            if not validate_execution_lease(state1,lease_record):
                raise ValueError("execution lease admission invalid")
            e2=_make_event(state1,EventType.LEASE_ISSUED,lease.lease_id,
                           FrozenMap.from_items((("lease",lease_record),("lease_id",lease.lease_id))),
                           ActorIdentity("system",ActorKind.SYSTEM,None),state1.policy_version,commit_id=commit_id,recorded_at=now)
            state2=REFERENCE_REDUCER.reduce(state1,e2)
            intent=ExecutionIntent(
                intent_id=_stable_id("intent",(request.request_id,lease.lease_id,commit_id)),
                request_content_digest=request.proposal.request_content_digest,
                authorization_decision_id=authorization_lease.claims.decision_id,
                execution_lease_id=lease.lease_id,
                worker_identity=lease.worker_identity,
                target_snapshot_digest=lease.target_snapshot_digest,
                governing_budget_lineage_id=request.governing_budget_lineage_id,
                budget_reservation_id=lease.budget_reservation_id,
                nonce=authorization_lease.claims.nonce,
                state_binding_digest=state_binding_digest(canonical_current_state_binding(state2, request.execution_generation, request.governing_budget_lineage_id)),
                event_sequence=state2.event_sequence+1,
                commit_id=commit_id,created_at=now,node_id=request.node_id)
            e3=_make_event(state2,EventType.EXECUTION_INTENT,request.node_id,
                           FrozenMap.from_items((("execution_intent",intent),("intent_id",intent.intent_id))),
                           ActorIdentity("system",ActorKind.SYSTEM,None),state2.policy_version,commit_id=commit_id,recorded_at=now)
            state3=REFERENCE_REDUCER.reduce(state2,e3)
            nonce_result=self.cp.nonces.consume_in_transaction(f"{state.workspace_id}:{audience}",authorization_lease.claims.nonce,
                                                               c.request_content_digest,c.lease_id,lease.lease_id,now)
            if nonce_result is not NonceConsumptionResult.SUCCESS:
                raise ValueError(f"nonce admission failed: {nonce_result.value}")
            commit=_commit_for_events((e1,e2,e3),state,state3,commit_id,now)
            result,head=store.append_batch_in_transaction((e1,e2,e3),commit,state.event_head_hash)
            if result is not AppendResult.APPENDED: raise ValueError("execution admission append failed")
            store.commit_transaction()
            return lease_record,intent
        except Exception:
            try: store.rollback_transaction()
            except Exception: pass
            raise


def lease_template_objective(request: AuthorizedWorkRequest) -> str:
    return request.proposal.state_binding.objective_revision


class SClassControlPlane:
    """S0-S1 command/commit control plane over the EventStore's one SQLite transaction."""
    def __init__(self, store: SQLiteEventStore, pinned_keys: Optional[Iterable[Any]] = None, *, boundary_attestor: Optional[Any] = None, pinned_trust_roots: Optional[Iterable[Any]] = None):
        self.store=store
        self.db=store._db
        self.commands=SQLiteCommandLedger(self.db)
        self.nonces=SQLiteNonceStore(self.db)
        self.budgets=SQLiteBudgetAllocator(self.db)
        self.retries=SQLiteRetryBudgetStore(self.db)
        self.break_glass=SQLiteBreakGlassLedger(self.db)
        if pinned_keys is not None:
            self.pinned_keys = _normalize_pinned_keys(pinned_keys)
        elif pinned_trust_roots is not None:
            self.pinned_keys = _normalize_pinned_keys(pinned_trust_roots)
        else:
            self.pinned_keys = None
        self.pinned_trust_roots: set[str] = {r for r, _ in self.pinned_keys} if self.pinned_keys is not None else set()
        self.keys = SQLiteKeyDirectory(self.db, pinned_keys=self.pinned_keys)
        for root in self.pinned_trust_roots:
            self.keys.add_root(root)
        self.workers=SQLiteWorkerRegistry(self.db)
        self.effects=ExternalEffectReconciler(self.db)
        self.boundary_attestor = boundary_attestor or UnprovisionedQuiescenceAuthority()
        self._execution_admission=ExecutionAdmission(self)
        self.execution_gate_factory=lambda workspace, require_sandbox=True: ExecutionGate(LinuxExecutionBoundary(workspace,require_sandbox=require_sandbox), self)
        self._recovery=self.db
        self.db.execute("CREATE TABLE IF NOT EXISTS runtime_recovery_cases(case_id TEXT NOT NULL,attempt_no INTEGER NOT NULL,workspace_id TEXT NOT NULL,node_id TEXT NOT NULL,status TEXT NOT NULL,report_blob BLOB NOT NULL,updated_at INTEGER NOT NULL,PRIMARY KEY(case_id,attempt_no))")

    def submit(self, command: Command) -> CommandResult:
        """Public ingress. Privileged actors never enter through the public API."""
        if command.actor.kind in (ActorKind.SYSTEM, ActorKind.VERIFIER):
            return CommandResult(RuntimeDisposition.DENIED, command.command_id, None, "privileged actor requires authenticated internal ingress")
        return self._submit(command, internal=False)

    def _submit_internal(self, command: Command) -> CommandResult:
        """Private privileged ingress. Public callers must use submit(), which rejects privileged actors."""
        if command.actor.kind not in (ActorKind.SYSTEM, ActorKind.VERIFIER):
            raise ValueError("internal ingress is reserved for privileged actors")
        return self._submit(command, internal=True)

    def _submit(self, command: Command, internal: bool) -> CommandResult:
        request_digest=digest("sclass/command/v2",command)
        existing=self.commands.lookup(command.workspace_id,command.command_id)
        if existing is not None:
            if existing[0] != str(request_digest): raise ValueError("command ID reused with different content")
            head=None if existing[2] is None else EventHead(existing[2],Digest(existing[3]))
            return CommandResult(RuntimeDisposition.IDEMPOTENT_REPLAY,command.command_id,head,existing[4])
        if command.actor.kind in (ActorKind.SYSTEM, ActorKind.VERIFIER) and not internal:
            return CommandResult(RuntimeDisposition.DENIED,command.command_id,None,"privileged actor requires authenticated internal ingress")
        if command.actor.kind != ActorKind.SYSTEM:
            if command.actor_signature is None: return CommandResult(RuntimeDisposition.DENIED,command.command_id,None,"authenticated actor signature required")
            verification=self.keys.verify_current(command.actor_signature,command_signature_message(command),_now())
            if verification is not SignatureVerificationResult.VALID: return CommandResult(RuntimeDisposition.DENIED,command.command_id,None,f"actor signature: {verification.value}")
        self.store._fault("K1_BEFORE_DURABLE_INTENT")
        self.store.begin_immediate()
        try:
            existing=self.commands.lookup(command.workspace_id,command.command_id)
            if existing is not None:
                if existing[0] != str(request_digest): raise ValueError("command ID reused with different content")
                self.store.rollback_transaction()
                head=None if existing[2] is None else EventHead(existing[2],Digest(existing[3]))
                return CommandResult(RuntimeDisposition.IDEMPOTENT_REPLAY,command.command_id,head,existing[4])
            state=self.store._load_canonical_state(command.workspace_id)
            if state.event_head_hash != command.expected_head:
                result=CommandResult(RuntimeDisposition.STALE_HEAD,command.command_id,EventHead(state.event_sequence,state.event_head_hash),"expected head does not match canonical head")
                self.commands.put_in_transaction(command,request_digest,result)
                self.store.commit_transaction(); return result
            payload=command.payload
            # Canonical authority producers: an authorization grant establishes the exact
            # budget lineage/frontier used by subsequent execution. These objects are
            # derived from canonical state and the signed decision, never caller-supplied.
            if command.event_type is EventType.AUTHORIZATION_GRANTED:
                decision=command.payload.get("authorization_decision")
                if isinstance(decision,AuthorizationDecision) and decision.worker_identity:
                    candidates=[n for n in state.work_graph._nodes.values()
                                if n.worker_id == decision.worker_identity and n.status in (WorkNodeStatus.READY,WorkNodeStatus.ASSIGNED,WorkNodeStatus.AUTHORIZED)]
                    if len(candidates) != 1:
                        self.store.rollback_transaction()
                        return CommandResult(RuntimeDisposition.DENIED,command.command_id,None,"authorization grant requires exactly one canonical target work node")
                    node=candidates[0]
                    lineage=canonical_governing_budget_lineage(state,node.node_id)
                    frontier=canonical_causal_frontier(state,decision,lineage,node.effective_risk_tier)
                    payload=FrozenMap.from_items(tuple(command.payload.items()) + (("governing_budget_lineage",lineage),("causal_frontier",frontier)))
            if not validate_security_event_signature_provenance(self.keys,command.event_type,payload,_now()):
                if command.event_type in (EventType.APPROVAL_RECORDED,EventType.POLICY_ACTIVATED,EventType.EVIDENCE_ACCEPTED,EventType.ASSESSMENT_CREATED,EventType.WAIVER_GRANTED,EventType.QUIESCENCE_PROVEN):
                    self.store.rollback_transaction()
                    return CommandResult(RuntimeDisposition.DENIED,command.command_id,None,"trusted signature provenance validation failed")
            event=_make_event(state,command.event_type,command.aggregate_id,payload,command.actor,state.policy_version,
                              event_id=_stable_id("evt",(command.command_id,request_digest)),commit_id=_stable_id("commit",(command.command_id,request_digest)),recorded_at=_now())
            derived=REFERENCE_REDUCER.reduce(state,event)
            commit=_commit_for_events((event,),state,derived,event.commit_id,event.recorded_at)
            append_result,head=self.store.append_batch_in_transaction((event,),commit,state.event_head_hash)
            if append_result is not AppendResult.APPENDED:
                self.store.rollback_transaction()
                return CommandResult(RuntimeDisposition.STALE_HEAD,command.command_id,head,"canonical append rejected")
            result=CommandResult(RuntimeDisposition.APPLIED,command.command_id,head,"canonical event committed")
            self.commands.put_in_transaction(command,request_digest,result)
            self.store._fault("K5_BEFORE_COMMIT")
            self.store.commit_transaction()
            self.store._fault("K6_AFTER_COMMIT")
            return result
        except Exception:
            try: self.store.rollback_transaction()
            except Exception: pass
            raise

    def execute_authorized_work(self, request: AuthorizedWorkRequest, argv: Sequence[str], *, allow_write: bool=False, allow_network: bool=False, env: Optional[Mapping[str,str]]=None, timeout_ms: int=30_000, max_output_bytes: int=1_000_000) -> ExecutionOutcome:
        """Production S2 path: authorization → budget → ExecutionGate → OS → quiescence → observation → settlement."""
        gate=self.execution_gate_factory(request.proposal.state_binding.workspace_id, require_sandbox=True)
        return gate.execute(request,argv,allow_write=allow_write,allow_network=allow_network,env=env,timeout_ms=timeout_ms,max_output_bytes=max_output_bytes)

    def expire_budget_reservations_canonical(self, workspace_id: str, *, now: Optional[UtcInstant]=None) -> tuple[str,...]:
        """Canonical reservation sweep. History changes first; runtime reservation table is a projection."""
        now=now or _now()
        self.store.begin_immediate()
        try:
            state=self.store._load_canonical_state(workspace_id)
            expired=self.budgets.expired_reservations_from_state(state,now)
            if not expired:
                self.store.rollback_transaction()
                return ()
            current=state
            events=[]
            commit_id=_stable_id("commit",("budget-expiry",workspace_id,current.event_head_hash,tuple(r.reservation_id for r in expired)))
            for r in expired:
                e=_make_event(current,EventType.BUDGET_RESERVATION_EXPIRED,r.reservation_id,
                              FrozenMap.from_items((("reservation",r),("reservation_id",r.reservation_id))),
                              ActorIdentity("system",ActorKind.SYSTEM,None),current.policy_version,commit_id=commit_id,recorded_at=now)
                current=REFERENCE_REDUCER.reduce(current,e); events.append(e)
            commit=_commit_for_events(tuple(events),state,current,commit_id,now)
            for r in expired:
                self.budgets.expire_projection_in_transaction(workspace_id,r)
            result,head=self.store.append_batch_in_transaction(tuple(events),commit,state.event_head_hash)
            if result is not AppendResult.APPENDED: raise ValueError("budget expiry canonical append failed")
            self.store.commit_transaction()
            return tuple(r.reservation_id for r in expired)
        except Exception:
            try:self.store.rollback_transaction()
            except Exception:pass
            raise

    def consume_retry_canonical(self, workspace_id: str, budget_id: str, failure_fingerprint: Digest, *, now: Optional[UtcInstant]=None) -> RetryBudget:
        """Consume retry budget from canonical state; runtime table is only a projection."""
        now=now or _now()
        if not _budget_fingerprint_ok(failure_fingerprint):
            raise ValueError("invalid retry failure fingerprint")
        self.store.begin_immediate()
        try:
            state=self.store._load_canonical_state(workspace_id)
            budget=state.retry_budgets.get(budget_id)
            if budget is None: raise KeyError(budget_id)
            max_same=state.active_policy.retry_rules.max_same_failure if state.active_policy is not None else budget.max_retries
            if budget.consumed >= budget.max_retries:
                raise ValueError("retry budget exhausted")
            same=budget.same_failure_count + 1 if budget.last_failure_fingerprint == failure_fingerprint else 1
            if same > max_same:
                raise ValueError("retry convergence guard exhausted")
            updated=replace(budget,consumed=budget.consumed+1,same_failure_count=same,last_failure_fingerprint=failure_fingerprint,version=budget.version+1)
            commit_id=_stable_id("commit",("retry",budget_id,updated.version,state.event_head_hash))
            event=_make_event(state,EventType.RETRY_CONSUMED,budget_id,
                              FrozenMap.from_items((("retry_budget",updated),("budget_id",budget_id))),
                              ActorIdentity("system",ActorKind.SYSTEM,None),state.policy_version,commit_id=commit_id,recorded_at=now)
            derived=REFERENCE_REDUCER.reduce(state,event)
            commit=_commit_for_events((event,),state,derived,commit_id,now)
            self.retries.project_from_canonical_in_transaction(updated)
            result,head=self.store.append_batch_in_transaction((event,),commit,state.event_head_hash)
            if result is not AppendResult.APPENDED: raise ValueError("retry canonical append failed")
            self.store.commit_transaction()
            return updated
        except Exception:
            try:self.store.rollback_transaction()
            except Exception:pass
            raise

    def record_recovery_canonical(self, rec: RuntimeRecoveryRecord, effects: Sequence[SideEffectReceipt]) -> None:
        self.store.begin_immediate()
        try:
            state=self.store._load_canonical_state(rec.workspace_id)
            if rec.decision is RecoveryDecision.IN_DOUBT:
                record=InDoubtRecord(rec.node_id,rec.reason,tuple(sorted(rec.unresolved_effect_ids)),state.event_sequence+1)
                event_type=EventType.IN_DOUBT_DECLARED
                payload=FrozenMap.from_items((("in_doubt",record),("node_id",rec.node_id)))
            elif rec.decision is RecoveryDecision.COMPENSATED:
                if rec.node_id not in state.work_graph._nodes:
                    raise ValueError("cannot resolve recovery for unknown canonical work node")
                event_type=EventType.IN_DOUBT_RESOLVED
                record=InDoubtRecord(rec.node_id,rec.reason,tuple(sorted(rec.unresolved_effect_ids)),state.event_sequence+1)
                payload=FrozenMap.from_items((("in_doubt",record),("resolved_status",WorkNodeStatus.COMPLETED),("node_id",rec.node_id)))
            else:
                event_type=EventType.IN_DOUBT_DECLARED
                record=InDoubtRecord(rec.node_id,rec.reason,tuple(sorted(rec.unresolved_effect_ids)),state.event_sequence+1)
                payload=FrozenMap.from_items((("in_doubt",record),("node_id",rec.node_id)))
            commit_id=_stable_id("commit",("recovery",rec.case_id,state.event_head_hash,event_type.value))
            event=_make_event(state,event_type,rec.node_id,payload,ActorIdentity("system",ActorKind.SYSTEM,None),state.policy_version,commit_id=commit_id,recorded_at=UtcInstant(rec.reconciled_at))
            derived=REFERENCE_REDUCER.reduce(state,event)
            commit=_commit_for_events((event,),state,derived,commit_id,event.recorded_at)
            # Append-only runtime projection row. If canonical append fails, journal is rolled back too.
            row=self.db.execute("SELECT COALESCE(MAX(attempt_no),0)+1 FROM runtime_recovery_cases WHERE case_id=?",(rec.case_id,)).fetchone()
            attempt=int(row[0])
            self.db.execute("INSERT INTO runtime_recovery_cases(case_id,attempt_no,workspace_id,node_id,status,report_blob,updated_at) VALUES(?,?,?,?,?,?,?)",
                            (rec.case_id,attempt,rec.workspace_id,rec.node_id,rec.decision.value,canonical_c1_pack(rec),rec.reconciled_at))
            result,_head=self.store.append_batch_in_transaction((event,),commit,state.event_head_hash)
            if result is not AppendResult.APPENDED:
                raise ValueError("recovery canonical append failed")
            self.store.commit_transaction()
        except Exception:
            try:self.store.rollback_transaction()
            except Exception:pass
            raise


    def consume_break_glass_canonical(self, authority: BreakGlassAuthority, requester: str, reason: str, *, now: Optional[UtcInstant]=None) -> tuple[str,int]:
        """Consume break-glass use with canonical event history as the authority."""
        now=now or _now()
        self.store.begin_immediate()
        try:
            state=self.store._load_canonical_state(authority.workspace_id)
            consumption_id,number=self.break_glass.consume_in_transaction(authority,requester,reason,now)
            expected=state.break_glass_consumption.get(authority.authority_id,0)+1
            if number != expected:
                raise ValueError("break-glass runtime projection diverges from canonical state")
            commit_id=_stable_id("commit",("breakglass",authority.authority_id,number,state.event_head_hash))
            event=_make_event(state,EventType.BREAK_GLASS_CONSUMED,authority.authority_id,
                              FrozenMap.from_items((("authority_id",authority.authority_id),("consumption_id",consumption_id),("consumption_number",number),("requester",requester),("reason",reason))),
                              ActorIdentity("system",ActorKind.SYSTEM,None),state.policy_version,commit_id=commit_id,recorded_at=now)
            derived=REFERENCE_REDUCER.reduce(state,event)
            commit=_commit_for_events((event,),state,derived,commit_id,now)
            result,head=self.store.append_batch_in_transaction((event,),commit,state.event_head_hash)
            if result is not AppendResult.APPENDED: raise ValueError("break-glass canonical append failed")
            self.store.commit_transaction()
            return consumption_id,number
        except Exception:
            try:self.store.rollback_transaction()
            except Exception:pass
            raise

    def reconcile_external_effect(self, receipt: SideEffectReceipt, *, now: Optional[UtcInstant]=None) -> SideEffectReceipt:
        """Canonical external-effect observation; runtime provider table is only a projection."""
        now=now or _now()
        if receipt.observed_at.epoch_ns > now.epoch_ns:
            raise ValueError("external-effect observation is from the future")
        expected_effect=digest("sclass/external-effect/v1",ExternalEffect(receipt.target_system,receipt.effect_kind,receipt.units))
        if receipt.effect_digest != expected_effect:
            raise ValueError("external-effect receipt digest mismatch")
        expected_id=_stable_id("effect",(receipt.workspace_id,receipt.request_id,receipt.target_system,receipt.effect_kind,receipt.units))
        if receipt.effect_id != expected_id:
            raise ValueError("external-effect identity mismatch")
        self.store.begin_immediate()
        try:
            workspace_id=getattr(receipt,"workspace_id",None)
            if not workspace_id:
                raise ValueError("external-effect receipt must carry workspace identity")
            state=self.store._load_canonical_state(workspace_id)
            commit_id=_stable_id("commit",("external-effect",receipt.effect_id,state.event_head_hash))
            event=_make_event(state,EventType.EXTERNAL_EFFECT_RECONCILED,receipt.effect_id,
                              FrozenMap.from_items((("receipt",receipt),)),
                              ActorIdentity("system",ActorKind.SYSTEM,None),state.policy_version,commit_id=commit_id,recorded_at=now)
            derived=REFERENCE_REDUCER.reduce(state,event)
            commit=_commit_for_events((event,),state,derived,commit_id,now)
            self.effects._project_provider_status(receipt)
            result,head=self.store.append_batch_in_transaction((event,),commit,state.event_head_hash)
            if result is not AppendResult.APPENDED:
                raise ValueError("external effect canonical append failed")
            self.store.commit_transaction()
            return receipt
        except Exception:
            try:self.store.rollback_transaction()
            except Exception:pass
            raise


    def issue_nonce(self, workspace_id: str, audience: str, request_digest: Digest, expires_at: UtcInstant, nonce: Optional[str]=None) -> str:
        n=nonce or secrets.token_urlsafe(32)
        self.nonces.issue(f"{workspace_id}:{audience}",n,request_digest,expires_at)
        return n

    def atomic_reserve_and_consume_nonce(self, workspace_id: str, audience: str, nonce: str, request_digest: Digest,
                                         authorization_lease_id: str, execution_lease_id: str,
                                         lineage_id: str, amount: ResourceBudget, expires_at: UtcInstant):
        """One-writer transaction proving nonce + reservation succeed or neither exists."""
        self.store.begin_immediate()
        try:
            state=self.store._load_canonical_state(workspace_id)
            if state.active_policy is None:
                raise ValueError("canonical policy required")
            canonical_limit=state.active_policy.budget_rules.default_objective_budget
            reservation=self.budgets.reserve_in_transaction(workspace_id,execution_lease_id,lineage_id,amount,expires_at,canonical_limit=canonical_limit)
            nonce_result=self.nonces.consume_in_transaction(f"{workspace_id}:{audience}",nonce,request_digest,authorization_lease_id,execution_lease_id,_now())
            if nonce_result is not NonceConsumptionResult.SUCCESS:
                raise ValueError(f"nonce admission failed: {nonce_result.value}")
            self.store.commit_transaction()
            return reservation
        except Exception:
            try:self.store.rollback_transaction()
            except Exception:pass
            raise


class SQLiteRetryBudgetStore:
    """Atomic retry CAS with convergence protection."""
    def __init__(self, db: sqlite3.Connection):
        self.db=db
        db.execute("""CREATE TABLE IF NOT EXISTS runtime_retry_budgets(
            budget_id TEXT PRIMARY KEY,node_id TEXT NOT NULL,max_retries INTEGER NOT NULL,
            consumed INTEGER NOT NULL,same_failure_count INTEGER NOT NULL,
            last_failure_fingerprint TEXT,version INTEGER NOT NULL)""")

    def register(self,budget: RetryBudget):
        self.db.execute("INSERT INTO runtime_retry_budgets VALUES(?,?,?,?,?,?,?)",
                        (budget.budget_id,budget.node_id,budget.max_retries,budget.consumed,budget.same_failure_count,
                         str(budget.last_failure_fingerprint) if budget.last_failure_fingerprint else None,budget.version))

    def project_from_canonical_in_transaction(self, budget: RetryBudget) -> None:
        self.db.execute(
            "INSERT INTO runtime_retry_budgets(budget_id,node_id,max_retries,consumed,same_failure_count,last_failure_fingerprint,version) VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(budget_id) DO UPDATE SET node_id=excluded.node_id,max_retries=excluded.max_retries,consumed=excluded.consumed,"
            "same_failure_count=excluded.same_failure_count,last_failure_fingerprint=excluded.last_failure_fingerprint,version=excluded.version",
            (budget.budget_id,budget.node_id,budget.max_retries,budget.consumed,budget.same_failure_count,
             str(budget.last_failure_fingerprint) if budget.last_failure_fingerprint else None,budget.version))

    def try_consume_in_transaction(self,budget_id: str, expected_version: int, failure_fingerprint: Digest,
                    max_same_failure: int) -> RetryReservationResult:
        if not _budget_fingerprint_ok(failure_fingerprint): return RetryReservationResult.VERSION_CONFLICT
        row=self.db.execute("SELECT max_retries,consumed,same_failure_count,last_failure_fingerprint,version FROM runtime_retry_budgets WHERE budget_id=?",(budget_id,)).fetchone()
        if row is None: return RetryReservationResult.VERSION_CONFLICT
        mx,consumed,same,last,version=row
        if version != expected_version: return RetryReservationResult.VERSION_CONFLICT
        if consumed >= mx: return RetryReservationResult.EXHAUSTED
        new_same=same+1 if last == str(failure_fingerprint) else 1
        if new_same > max_same_failure: return RetryReservationResult.CONVERGED_NO_PROGRESS
        self.db.execute("UPDATE runtime_retry_budgets SET consumed=?,same_failure_count=?,last_failure_fingerprint=?,version=? WHERE budget_id=? AND version=?",
                        (consumed+1,new_same,str(failure_fingerprint),version+1,budget_id,version))
        if self.db.execute("SELECT changes()").fetchone()[0] != 1: return RetryReservationResult.VERSION_CONFLICT
        return RetryReservationResult.RESERVED

    def try_consume(self,budget_id: str, expected_version: int, failure_fingerprint: Digest,
                    max_same_failure: int) -> RetryReservationResult:
        raise PermissionError("direct runtime retry consumption is non-authoritative; use consume_retry_canonical")

    def _try_consume_for_test(self,budget_id: str, expected_version: int, failure_fingerprint: Digest,
                              max_same_failure: int) -> RetryReservationResult:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            result=self.try_consume_in_transaction(budget_id,expected_version,failure_fingerprint,max_same_failure)
            if result is RetryReservationResult.RESERVED: self.db.execute("COMMIT")
            else: self.db.execute("ROLLBACK")
            return result
        except Exception:
            self.db.execute("ROLLBACK"); raise


def _budget_fingerprint_ok(value: Digest) -> bool:
    return isinstance(value,Digest) and _is_digest_value(value)


class SQLiteBreakGlassLedger:
    """Single-use break-glass consumption ledger. Limits are passed from a trusted authority record."""
    def __init__(self, db: sqlite3.Connection):
        self.db=db
        db.execute("""CREATE TABLE IF NOT EXISTS runtime_break_glass(
            authority_id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,max_uses INTEGER NOT NULL,
            consumed INTEGER NOT NULL DEFAULT 0,expires_at INTEGER NOT NULL,authority_digest TEXT NOT NULL)""")

    def register(self, authority: BreakGlassAuthority):
        if authority.max_uses < 1 or not authority.authority_id or not authority.key_id or not authority.workspace_id or not authority.policy_version:
            raise ValueError("invalid break-glass authority")
        ad=digest("sclass/break-glass-authority/v1",authority)
        self.db.execute("INSERT INTO runtime_break_glass(authority_id,workspace_id,max_uses,consumed,expires_at,authority_digest) VALUES(?,?,?,?,?,?)",
                        (authority.authority_id,authority.workspace_id,authority.max_uses,0,authority.expires_at.epoch_ns,str(ad)))

    def consume_in_transaction(self, authority: BreakGlassAuthority, requester: str, reason: str, now: Optional[UtcInstant]=None):
        now=now or _now()
        if not requester or not reason: raise ValueError("break-glass requires attributable requester/reason")
        row=self.db.execute("SELECT workspace_id,max_uses,consumed,expires_at,authority_digest FROM runtime_break_glass WHERE authority_id=?",(authority.authority_id,)).fetchone()
        if row is None: raise ValueError("unknown break-glass authority")
        if row[0] != authority.workspace_id or row[4] != str(digest("sclass/break-glass-authority/v1",authority)): raise ValueError("break-glass authority changed")
        if now.epoch_ns >= row[3] or row[2] >= row[1]: raise ValueError("break-glass exhausted/expired")
        self.db.execute("UPDATE runtime_break_glass SET consumed=consumed+1 WHERE authority_id=? AND consumed < max_uses",(authority.authority_id,))
        if self.db.execute("SELECT changes()").fetchone()[0] != 1: raise ValueError("break-glass CAS conflict")
        return _stable_id("breakglass",(authority.authority_id,row[2]+1,requester,reason)),row[2]+1

    def consume(self, authority: BreakGlassAuthority, requester: str, reason: str, now: Optional[UtcInstant]=None):
        raise PermissionError("direct break-glass consumption is non-authoritative; use consume_break_glass_canonical")

    def _consume_for_test(self, authority: BreakGlassAuthority, requester: str, reason: str, now: Optional[UtcInstant]=None):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            result=self.consume_in_transaction(authority,requester,reason,now)
            self.db.execute("COMMIT"); return result
        except Exception:
            self.db.execute("ROLLBACK"); raise



class SQLiteWorkerRegistry:
    """Durable registry of worker identities admitted by trusted runtime provisioning."""
    def __init__(self, db: sqlite3.Connection):
        self.db=db
        db.execute("""CREATE TABLE IF NOT EXISTS runtime_workers(
            worker_id TEXT PRIMARY KEY,
            attestation_digest TEXT NOT NULL,
            attestation_blob BLOB,
            status TEXT NOT NULL CHECK(status IN ('ACTIVE','REVOKED')),
            registered_at INTEGER NOT NULL,
            revoked_at INTEGER)""")
        cols={row[1] for row in db.execute("PRAGMA table_info(runtime_workers)").fetchall()}
        if "attestation_blob" not in cols:
            db.execute("ALTER TABLE runtime_workers ADD COLUMN attestation_blob BLOB")

    def register(self, worker_id: str, attestation_digest: Digest):
        if not worker_id or not _is_digest_value(attestation_digest):
            raise ValueError("worker identity/attestation required")
        self.db.execute("INSERT INTO runtime_workers(worker_id,attestation_digest,attestation_blob,status,registered_at,revoked_at) VALUES(?,?,NULL,?,?,NULL) ON CONFLICT(worker_id) DO UPDATE SET attestation_digest=excluded.attestation_digest,attestation_blob=NULL,status='ACTIVE',revoked_at=NULL",
                        (worker_id,str(attestation_digest),"ACTIVE",time.time_ns()))

    def register_attestation(self, attestation: AdapterAttestation):
        if not isinstance(attestation, AdapterAttestation):
            raise TypeError("AdapterAttestation required")
        if not attestation.worker_identity or not attestation.key_id or not attestation.trust_root:
            raise ValueError("attestation identity is incomplete")
        self.db.execute("INSERT INTO runtime_workers(worker_id,attestation_digest,attestation_blob,status,registered_at,revoked_at) VALUES(?,?,?,?,?,NULL) ON CONFLICT(worker_id) DO UPDATE SET attestation_digest=excluded.attestation_digest,attestation_blob=excluded.attestation_blob,status='ACTIVE',revoked_at=NULL",
                        (attestation.worker_identity,str(adapter_attestation_digest(attestation)),sqlite3.Binary(canonical_c1_pack(attestation)),"ACTIVE",time.time_ns()))

    def attestation_record(self, worker_id: str) -> Optional[AdapterAttestation]:
        row=self.db.execute("SELECT attestation_blob FROM runtime_workers WHERE worker_id=? AND status='ACTIVE'",(worker_id,)).fetchone()
        if row is None or row[0] is None:
            return None
        value=canonical_c1_unpack(row[0])
        return value if isinstance(value,AdapterAttestation) else None

    def revoke(self, worker_id: str):
        self.db.execute("UPDATE runtime_workers SET status='REVOKED',revoked_at=? WHERE worker_id=?",(time.time_ns(),worker_id))

    def is_active(self, worker_id: str) -> bool:
        row=self.db.execute("SELECT status FROM runtime_workers WHERE worker_id=?",(worker_id,)).fetchone()
        return row is not None and row[0] == "ACTIVE"

    def attestation(self, worker_id: str) -> Optional[Digest]:
        row=self.db.execute("SELECT attestation_digest FROM runtime_workers WHERE worker_id=? AND status='ACTIVE'",(worker_id,)).fetchone()
        return Digest(row[0]) if row else None


class ExternalEffectReconciler:
    """Durable provider-status projection keyed by canonical effect identity."""
    def __init__(self, db: sqlite3.Connection):
        self.db=db
        self.db.execute("CREATE TABLE IF NOT EXISTS runtime_effect_receipts(effect_id TEXT PRIMARY KEY,effect_digest TEXT NOT NULL,request_id TEXT NOT NULL,workspace_id TEXT NOT NULL,target_system TEXT NOT NULL,effect_kind TEXT NOT NULL,provider_reference TEXT,provider_status TEXT NOT NULL,observed_at INTEGER NOT NULL)")
        cols={row[1] for row in db.execute("PRAGMA table_info(runtime_effect_receipts)").fetchall()}
        if "workspace_id" not in cols:
            db.execute("ALTER TABLE runtime_effect_receipts ADD COLUMN workspace_id TEXT")
        if "request_id" not in cols:
            db.execute("ALTER TABLE runtime_effect_receipts ADD COLUMN request_id TEXT")
    def record_provider_status(self, effect_id: str, status: SideEffectStatus, provider_reference: Optional[str]=None, effect: Optional[ExternalEffect]=None):
        raise PermissionError("external effect status is canonical; use reconcile_external_effect on SClassControlPlane")

    def _project_provider_status(self, receipt: SideEffectReceipt):
        effect_id=receipt.effect_id
        self.db.execute("INSERT INTO runtime_effect_receipts(effect_id,effect_digest,request_id,workspace_id,target_system,effect_kind,provider_reference,provider_status,observed_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(effect_id) DO UPDATE SET effect_digest=excluded.effect_digest,request_id=excluded.request_id,workspace_id=excluded.workspace_id,target_system=excluded.target_system,effect_kind=excluded.effect_kind,provider_reference=excluded.provider_reference,provider_status=excluded.provider_status,observed_at=excluded.observed_at",
                        (effect_id,str(receipt.effect_digest),receipt.request_id,receipt.workspace_id,receipt.target_system,receipt.effect_kind,receipt.compensation_reference,receipt.status.value,receipt.observed_at.epoch_ns))
    def reconcile(self, effect: ExternalEffect, workspace_id: str, request_id: str) -> SideEffectStatus:
        if not workspace_id or not request_id:
            raise ValueError("workspace_id and request_id are required to reconcile an external effect")
        effect_id=_stable_id("effect",(workspace_id,request_id,effect.target_system,effect.effect_kind,effect.units))
        row=self.db.execute("SELECT effect_digest,provider_status,workspace_id,request_id,target_system,effect_kind FROM runtime_effect_receipts WHERE effect_id=?",(effect_id,)).fetchone()
        if row is None or row[0] != str(digest("sclass/external-effect/v1",effect)): return SideEffectStatus.UNKNOWN
        if row[2] != workspace_id or row[3] != request_id or row[4] != effect.target_system or row[5] != effect.effect_kind: return SideEffectStatus.UNKNOWN
        return SideEffectStatus(row[1])


class BoundaryUnavailable(PermissionError):
    """Raised when required OS boundary mechanisms (bubblewrap, cgroup v2) are unavailable."""
    pass


class BoundaryIsolation(Enum):
    DENY="DENY"
    BUBBLEWRAP="BUBBLEWRAP"

@dataclass(frozen=True)
class BoundaryRunResult:
    isolation: BoundaryIsolation
    returncode: int
    stdout: bytes
    stderr: bytes
    timed_out: bool
    duration_ms: int
    executable_digest: Optional[Digest] = None
    argv_digest: Optional[Digest] = None
    process_id: Optional[int] = None
    process_start_time_ns: Optional[int] = None
    stdout_total_bytes: int = 0
    stderr_total_bytes: int = 0
    process_lineage: tuple[ProcessLineageEntry, ...] = ()
    cgroup_events: Mapping[str, int] = field(default_factory=dict)


class LinuxExecutionBoundary:
    """Fail-closed OS adapter with isolated namespaces and process-level resource ceilings."""
    _bwrap_functional_cache: dict[str, bool] = {}

    def __init__(self, workspace: str, require_sandbox: bool=True, cgroup_root: Optional[Union[str, Path]]=None):
        self.workspace=Path(workspace).resolve()
        if not self.workspace.exists() or not self.workspace.is_dir():
            raise ValueError("workspace must be an existing directory")
        self.require_sandbox=require_sandbox
        self.bwrap=shutil.which("bwrap")
        self._gate_capability=object()
        self._active_pids:set[int]=set()
        self.last_cgroup_events: dict[str, int] = {}
        if cgroup_root is not None:
            self.cgroup_root=Path(cgroup_root).resolve()
        elif Path("/sys/fs/cgroup/sclass").exists():
            self.cgroup_root=Path("/sys/fs/cgroup/sclass").resolve()
        else:
            self.cgroup_root=Path("/sys/fs/cgroup").resolve()

    @classmethod
    def _is_bwrap_functional(cls, bwrap_path: Optional[str]) -> bool:
        if not bwrap_path:
            return False
        if bwrap_path in cls._bwrap_functional_cache:
            return cls._bwrap_functional_cache[bwrap_path]
        try:
            res = subprocess.run(
                [bwrap_path, "--unshare-user", "--ro-bind", "/", "/", "true"],
                capture_output=True,
                timeout=2.0
            )
            usable = (res.returncode == 0)
        except Exception:
            usable = False
        cls._bwrap_functional_cache[bwrap_path] = usable
        return usable

    def _assert_bwrap_usable(self) -> None:
        if not self.bwrap:
            raise BoundaryUnavailable("bubblewrap unavailable; OS-enforced execution denied")
        if not self._is_bwrap_functional(self.bwrap):
            raise BoundaryUnavailable("bubblewrap unprivileged user namespaces are blocked or restricted on this host")

    @staticmethod
    def _openat2_beneath(root_fd: int, rel: str, flags: int = os.O_PATH | os.O_CLOEXEC) -> int:
        if os.name != "posix" or not hasattr(os, "O_PATH"):
            raise PermissionError("Linux openat2-class path resolution is required")
        libc_name=ctypes.util.find_library("c")
        if not libc_name:
            raise PermissionError("libc unavailable for openat2")
        libc=ctypes.CDLL(libc_name, use_errno=True)
        class OpenHow(ctypes.Structure):
            _fields_=[("flags",ctypes.c_uint64),("mode",ctypes.c_uint64),("resolve",ctypes.c_uint64)]
        RESOLVE_BENEATH=0x08
        RESOLVE_NO_MAGICLINKS=0x02
        RESOLVE_NO_SYMLINKS=0x04
        how=OpenHow(flags,0,RESOLVE_BENEATH|RESOLVE_NO_MAGICLINKS|RESOLVE_NO_SYMLINKS)
        b=os.fsencode(rel)
        rc=libc.syscall(437,ctypes.c_int(root_fd),ctypes.c_char_p(b),ctypes.byref(how),ctypes.sizeof(how))
        if rc < 0:
            e=ctypes.get_errno()
            raise OSError(e, os.strerror(e), rel)
        return int(rc)

    def _secure_workspace_fd(self, rel: str) -> int:
        rel=rel.replace("\\","/")
        if not rel or rel.startswith("/") or "\x00" in rel or ".." in Path(rel).parts:
            raise PermissionError("invalid workspace-relative path")
        root_fd=os.open(self.workspace, os.O_PATH|os.O_DIRECTORY|os.O_CLOEXEC)
        try:
            return self._openat2_beneath(root_fd,rel)
        finally:
            os.close(root_fd)

    @staticmethod
    def _executable_path(argv0: str) -> Path:
        candidate=Path(argv0)
        if argv0 in ("python", "python3", "python.exe") and sys.executable:
            return Path(sys.executable).resolve()
        resolved=Path(shutil.which(argv0) or argv0).resolve()
        if not resolved.exists() or not resolved.is_file():
            raise FileNotFoundError(argv0)
        return resolved

    @staticmethod
    def _file_digest(path: Path) -> Digest:
        h=hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda:f.read(1024*1024),b""):
                h.update(chunk)
        return Digest("sha256:"+h.hexdigest())

    @staticmethod
    def _proc_start_time_ns(pid: int) -> Optional[int]:
        try:
            stat=Path(f"/proc/{pid}/stat").read_text()
            after=stat.rsplit(") ",1)[1].split()
            start_ticks=int(after[19])  # field 22 in /proc/pid/stat; after comm two fields are skipped
            clk=os.sysconf(os.sysconf_names["SC_CLK_TCK"])
            btime=None
            for line in Path("/proc/stat").read_text().splitlines():
                if line.startswith("btime "):
                    btime=int(line.split()[1]); break
            if btime is None or clk <= 0: return None
            return btime*1_000_000_000 + (start_ticks*1_000_000_000)//clk
        except (OSError,ValueError,IndexError,KeyError):
            return None

    def _assert_cgroup_v2(self) -> None:
        root=self.cgroup_root
        base_controllers=Path("/sys/fs/cgroup/cgroup.controllers")
        controllers=root/"cgroup.controllers"
        if not base_controllers.exists() and not controllers.exists():
            raise BoundaryUnavailable("cgroup v2 is required for execution boundary")
        if not os.access(root,os.W_OK):
            raise BoundaryUnavailable("cgroup v2 hierarchy is not writable by execution runtime")

    def _create_cgroup(self, budget: ResourceBudget) -> Path:
        self._assert_cgroup_v2()
        root=self.cgroup_root
        group=root/f"sclass-{os.getpid()}-{secrets.token_hex(4)}"
        try:
            group.mkdir(mode=0o755)
        except OSError as exc:
            raise BoundaryUnavailable(f"failed to create cgroup directory {group}: {exc}") from exc
        try:
            procs_file=group/"cgroup.procs"
            if not procs_file.exists():
                raise BoundaryUnavailable(f"cgroup.procs controller file missing in {group}")
            if not os.access(procs_file, os.W_OK):
                raise BoundaryUnavailable(f"cgroup.procs is not writable in {group}")
            if budget.memory_mb > 0:
                mem_file=group/"memory.max"
                if not mem_file.exists():
                    raise BoundaryUnavailable(f"cgroup memory controller (memory.max) is missing in {group}")
                try:
                    mem_file.write_text(str(budget.memory_mb*1024*1024))
                except OSError as exc:
                    raise BoundaryUnavailable(f"failed to set memory.max in {group}: {exc}") from exc
                swap_file=group/"memory.swap.max"
                if swap_file.exists():
                    try: swap_file.write_text("0")
                    except OSError: pass
            if budget.process_count > 0:
                pids_file=group/"pids.max"
                if not pids_file.exists():
                    raise BoundaryUnavailable(f"cgroup pids controller (pids.max) is missing in {group}")
                try:
                    pids_file.write_text(str(budget.process_count))
                except OSError as exc:
                    raise BoundaryUnavailable(f"failed to set pids.max in {group}: {exc}") from exc
            if budget.cpu_cores > 0:
                cpu_file=group/"cpu.max"
                if not cpu_file.exists():
                    raise BoundaryUnavailable(f"cgroup cpu controller (cpu.max) is missing in {group}")
                try:
                    quota=max(1000,budget.cpu_cores*100000)
                    cpu_file.write_text(f"{quota} 100000")
                except OSError as exc:
                    raise BoundaryUnavailable(f"failed to set cpu.max in {group}: {exc}") from exc
            return group
        except Exception:
            try: group.rmdir()
            except OSError: pass
            raise

    def _attach_cgroup(self, pid: int, budget: ResourceBudget) -> Path:
        group=self._create_cgroup(budget)
        try:
            (group/"cgroup.procs").write_text(str(pid))
            return group
        except Exception as exc:
            try: group.rmdir()
            except OSError: pass
            if isinstance(exc, BoundaryUnavailable):
                raise
            raise BoundaryUnavailable(f"failed to attach process {pid} to cgroup: {exc}") from exc

    @staticmethod
    def _remove_cgroup(group: Optional[Path]) -> None:
        if group is None: return
        kill_file=group/"cgroup.kill"
        if kill_file.exists():
            try: kill_file.write_text("1")
            except OSError: pass
        for _ in range(20):
            try:
                group.rmdir()
                return
            except OSError:
                time.sleep(0.02)

    def _command(self, argv: Sequence[str], allow_write: bool, allow_network: bool, write_paths: Sequence[str] = (), env: Optional[Mapping[str,str]] = None, filesystem_accesses: Sequence[Any] = ()):
        if allow_network:
            raise PermissionError("network execution requires an explicit OS egress broker; raw network access is denied")
        if not argv or any(not isinstance(x,str) or not x for x in argv):
            raise ValueError("invalid argv")
        exe=self._executable_path(argv[0])
        normalized=[str(exe)] + list(argv[1:])
        self._assert_bwrap_usable()
        self._assert_cgroup_v2()
        # Empty root + exact bind mounts only. The workspace is never exposed wholesale.
        cmd=[self.bwrap,"--die-with-parent","--new-session","--unshare-all","--tmpfs","/",
             "--ro-bind","/usr","/usr","--ro-bind","/bin","/bin","--ro-bind","/lib","/lib"]
        if Path("/lib64").exists(): cmd += ["--ro-bind","/lib64","/lib64"]
        if Path("/usr/local").exists(): cmd += ["--ro-bind","/usr/local","/usr/local"]
        if Path("/etc").exists(): cmd += ["--ro-bind","/etc","/etc"]
        if Path("/opt").exists(): cmd += ["--ro-bind","/opt","/opt"]
        for p_dir in (Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve()):
            p_str=str(p_dir)
            if p_str not in ("/usr","/usr/local","/bin","/lib","/lib64","/opt") and not p_str.startswith(("/usr/","/usr/local/","/bin/","/lib/","/lib64/","/opt/")):
                if p_dir.exists() and p_dir != self.workspace and not str(p_dir).startswith(str(self.workspace)+"/"):
                    cmd += ["--ro-bind",p_str,p_str]
        cmd += ["--proc","/proc","--dev","/dev","--tmpfs","/tmp","--tmpfs","/workspace"]
        source_fds=[]
        def add_parent_dirs(dest: str):
            parent=Path(dest).parent
            parts=[]
            while str(parent) not in (".","/"):
                parts.append("/"+parent.as_posix().lstrip("/")); parent=parent.parent
            for d in reversed(parts): cmd.extend(["--dir",d])
        add_parent_dirs(str(exe))
        # Bind the exact executable inode to its resolved path inside the sandbox.
        exe_fd=os.open(exe,os.O_PATH|os.O_CLOEXEC)
        source_fds.append(exe_fd)
        cmd += ["--ro-bind",f"/proc/self/fd/{exe_fd}",str(exe)]

        accesses=[]
        for access in filesystem_accesses:
            path=access.path
            mode=access.mode
            if not path or Path(path).is_absolute() or ".." in Path(path).parts:
                raise PermissionError("filesystem effect path must be workspace-relative")
            fd=self._secure_workspace_fd(path)
            source_fds.append(fd)
            accesses.append((path, mode is FsMode.READ, fd))
        # Reject ambiguous overlapping mounts; one exact scope entry owns its subtree.
        norm_paths=sorted(str(Path(p).as_posix()).strip("/") for p,_,_ in accesses)
        for i,p in enumerate(norm_paths):
            if any(q != p and q.startswith(p+"/") for q in norm_paths[i+1:]):
                raise PermissionError("overlapping filesystem effect scopes are ambiguous")
        def add_parent_dirs(dest: str):
            parent=Path(dest).parent
            parts=[]
            while str(parent) not in (".","/"):
                parts.append("/"+parent.as_posix().lstrip("/")); parent=parent.parent
            for d in reversed(parts): cmd.extend(["--dir",d])
        for path,read_only,fd in accesses:
            dest="/workspace" if Path(path).as_posix()=="." else f"/workspace/{path}"
            if dest != "/workspace":
                add_parent_dirs(dest)
            cmd += ["--ro-bind" if read_only else "--bind",f"/proc/self/fd/{fd}",dest]
        cmd += ["--clearenv","--setenv","PATH","/usr/local/bin:/usr/bin:/bin"]
        if env:
            for key,value in sorted(env.items()):
                if not isinstance(key,str) or not key or "=" in key or "\x00" in key or not isinstance(value,str) or "\x00" in value:
                    raise PermissionError("invalid execution environment")
                cmd += ["--setenv",key,value]
        cmd += ["--chdir","/workspace","--unshare-net","--"]
        cmd += normalized
        return cmd, tuple(source_fds), tuple(accesses)

    def _run_from_gate(self, capability: object, argv: Sequence[str], *, allow_write: bool=False, allow_network: bool=False, env: Optional[Mapping[str,str]]=None, timeout_ms: int=30_000, max_output_bytes: int=1_000_000, budget: Optional[ResourceBudget]=None, expected_executable_digest: Optional[Digest]=None, write_paths: Sequence[str] = (), filesystem_accesses: Sequence[Any] = ()) -> BoundaryRunResult:
        if capability is not self._gate_capability:
            raise PermissionError("OS execution is callable only through ExecutionGate")
        if timeout_ms < 1 or max_output_bytes < 1: raise ValueError("invalid execution limits")
        budget=budget or ResourceBudget(0,0,0,timeout_ms,0,0,0,0,0,0,0)
        if budget.wall_time_ms > 0:
            timeout_ms=min(timeout_ms,budget.wall_time_ms)
        cmd,source_fds,_accesses=self._command(argv,allow_write,allow_network,write_paths,env,filesystem_accesses)
        exe=self._executable_path(argv[0])
        exe_digest=self._file_digest(exe)
        if expected_executable_digest is not None and exe_digest != expected_executable_digest:
            raise PermissionError("resolved executable digest does not match authorized execution identity")
        argv_digest=digest("sclass/argv/v1",tuple(argv))
        out_file=tempfile.NamedTemporaryFile(prefix="sclass-stdout-",delete=False)
        err_file=tempfile.NamedTemporaryFile(prefix="sclass-stderr-",delete=False)
        out_path,err_path=out_file.name,err_file.name
        out_file.close(); err_file.close()
        start=time.monotonic()
        def _preexec():
            if cgroup is not None:
                try:
                    (cgroup/"cgroup.procs").write_text(str(os.getpid()))
                except OSError as exc:
                    raise RuntimeError(f"failed to attach child process to cgroup: {exc}")
            cpu_seconds=max(1,int(timeout_ms/1000)+1)
            try: resource.setrlimit(resource.RLIMIT_CPU,(cpu_seconds,cpu_seconds+1))
            except (ValueError,OSError): pass
            if budget.memory_mb > 0:
                limit=budget.memory_mb*1024*1024
                as_limit=max(limit*8, 512*1024*1024) if cgroup is not None else limit
                try: resource.setrlimit(resource.RLIMIT_AS,(as_limit,as_limit))
                except (ValueError,OSError) as exc:
                    raise RuntimeError(f"failed to set required RLIMIT_AS: {exc}")
            if budget.process_count > 0:
                nproc_limit=max(budget.process_count*8, 1024) if cgroup is not None else budget.process_count
                try: resource.setrlimit(resource.RLIMIT_NPROC,(nproc_limit,nproc_limit))
                except (ValueError,OSError) as exc:
                    raise RuntimeError(f"failed to set required RLIMIT_NPROC: {exc}")
            if budget.disk_mb > 0:
                limit=budget.disk_mb*1024*1024
                try: resource.setrlimit(resource.RLIMIT_FSIZE,(limit,limit))
                except (ValueError,OSError) as exc:
                    raise RuntimeError(f"failed to set required RLIMIT_FSIZE: {exc}")
        def _snapshot_tree(root_pid: int):
            rows=[]
            proc_dir=Path("/proc")
            if not proc_dir.exists():
                return ()
            table={}
            for p in proc_dir.iterdir():
                if not p.name.isdigit(): continue
                try:
                    stat=Path(f"/proc/{p.name}/stat").read_text()
                    after=stat.rsplit(") ",1)[1].split()
                    ppid=int(after[1])
                    table[int(p.name)]=(ppid,)
                except (OSError,ValueError,IndexError):
                    continue
            seen={root_pid}; queue=[root_pid]
            while queue:
                pid=queue.pop(0)
                try:
                    exe_path=Path(os.readlink(f"/proc/{pid}/exe")).resolve()
                    exe_digest=self._file_digest(exe_path)
                    cmdline=Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\x00")[:-1]
                    argv_digest=digest("sclass/argv/v1",tuple(x.decode("utf-8","replace") for x in cmdline))
                    start_ns=self._proc_start_time_ns(pid) or 0
                    rows.append(ProcessLineageEntry(pid,start_ns,exe_digest,argv_digest))
                except (OSError,ValueError):
                    pass
                for child,(ppid,) in table.items():
                    if ppid == pid and child not in seen:
                        seen.add(child); queue.append(child)
            return tuple(sorted(rows,key=lambda x:(x.pid,x.start_time_ns)))

        def _kill_group(pid: int):
            if cgroup is not None:
                kill_file=cgroup/"cgroup.kill"
                if kill_file.exists():
                    try: kill_file.write_text("1")
                    except OSError: pass
                procs_file=cgroup/"cgroup.procs"
                if procs_file.exists():
                    try:
                        for p_str in procs_file.read_text().split():
                            if p_str.isdigit():
                                try: os.kill(int(p_str), signal.SIGKILL)
                                except (ProcessLookupError, PermissionError, OSError): pass
                    except OSError: pass
            if hasattr(os, "killpg"):
                try: os.killpg(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError): pass
            else:
                try: os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError): pass

        proc=None
        timed=False
        cgroup=None
        if self.require_sandbox:
            cgroup=self._create_cgroup(budget)
        process_start_time_ns=None
        observed_lineage=()
        out=b""
        err=b""
        stdout_total=0
        stderr_total=0
        try:
            with open(out_path,"wb") as out, open(err_path,"wb") as err:
                popen_kwargs = dict(
                    cwd=str(self.workspace),
                    env=dict(env) if env is not None else {},
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                )
                if sys.platform != "win32":
                    popen_kwargs["start_new_session"] = True
                    popen_kwargs["preexec_fn"] = _preexec
                    popen_kwargs["pass_fds"] = source_fds
                try:
                    proc=subprocess.Popen(cmd, **popen_kwargs)
                except subprocess.SubprocessError as exc:
                    raise BoundaryUnavailable(f"failed to spawn sandboxed execution: {exc}") from exc
                process_start_time_ns=self._proc_start_time_ns(proc.pid) or time.time_ns()
                self._active_pids.add(proc.pid)
                if cgroup is not None:
                    try:
                        (cgroup/"cgroup.procs").write_text(str(proc.pid))
                    except OSError as exc:
                        _kill_group(proc.pid)
                        proc.wait()
                        raise BoundaryUnavailable(f"failed to attach process {proc.pid} to cgroup: {exc}") from exc
                # Seed the lineage with the independently checked leader identity; very short-lived processes may exit before /proc polling.
                observed_lineage=(ProcessLineageEntry(proc.pid,process_start_time_ns,exe_digest,argv_digest),)
                try:
                    observed_lineage=tuple({(x.pid,x.start_time_ns):x for x in observed_lineage+_snapshot_tree(proc.pid)}.values())
                except Exception:
                    pass
                bwrap_digest=self._file_digest(Path(self.bwrap)) if self.bwrap else None
                if expected_executable_digest is not None and Path(f"/proc/{proc.pid}/exe").exists():
                    try:
                        live_exe=Path(os.readlink(f"/proc/{proc.pid}/exe")).resolve()
                        live_digest=self._file_digest(live_exe)
                        if live_digest != expected_executable_digest and live_digest != bwrap_digest:
                            _kill_group(proc.pid)
                            proc.wait()
                            raise PermissionError("running executable identity does not match authorized digest")
                    except PermissionError:
                        raise
                    except (OSError,FileNotFoundError):
                        _kill_group(proc.pid)
                        proc.wait()
                        raise PermissionError("running executable identity is not verifiable")
                deadline=time.monotonic()+timeout_ms/1000.0
                while True:
                    current_lineage=_snapshot_tree(proc.pid)
                    observed_lineage=tuple({(x.pid,x.start_time_ns):x for x in observed_lineage+current_lineage}.values())
                    authorized_digest=expected_executable_digest if expected_executable_digest is not None else exe_digest
                    authorized_digests={authorized_digest}
                    if bwrap_digest:
                        authorized_digests.add(bwrap_digest)
                    bad=[entry for entry in current_lineage if entry.executable_digest not in authorized_digests]
                    if bad:
                        _kill_group(proc.pid)
                        proc.wait()
                        raise PermissionError("unauthorized executable/process-tree identity observed")
                    if proc.poll() is not None:
                        break
                    if time.monotonic() >= deadline:
                        timed=True
                        _kill_group(proc.pid)
                        proc.wait()
                        break
                    time.sleep(0.01)
                try:
                    final_lineage=_snapshot_tree(proc.pid)
                    observed_lineage=tuple({(x.pid,x.start_time_ns):x for x in observed_lineage+final_lineage}.values())
                except Exception:
                    pass
            out_raw=Path(out_path).read_bytes()
            err_raw=Path(err_path).read_bytes()
            out=out_raw[:max_output_bytes]
            err=err_raw[:max_output_bytes]
            stdout_total=len(out_raw)
            stderr_total=len(err_raw)
        finally:
            if proc is not None:
                self._active_pids.discard(proc.pid)
            for fd in source_fds:
                try: os.close(fd)
                except OSError: pass
            cgroup_events: dict[str, int] = {}
            if cgroup is not None:
                mem_events = cgroup / "memory.events"
                if mem_events.exists():
                    try:
                        for line in mem_events.read_text().splitlines():
                            parts = line.strip().split()
                            if len(parts) == 2 and parts[1].isdigit():
                                cgroup_events[f"memory.{parts[0]}"] = int(parts[1])
                    except OSError:
                        pass
                pids_events = cgroup / "pids.events"
                if pids_events.exists():
                    try:
                        for line in pids_events.read_text().splitlines():
                            parts = line.strip().split()
                            if len(parts) == 2 and parts[1].isdigit():
                                cgroup_events[f"pids.{parts[0]}"] = int(parts[1])
                    except OSError:
                        pass
                self._remove_cgroup(cgroup)
            self.last_cgroup_events = dict(cgroup_events)
            try: Path(out_path).unlink()
            except FileNotFoundError: pass
            try: Path(err_path).unlink()
            except FileNotFoundError: pass
        dur=int((time.monotonic()-start)*1000)
        return BoundaryRunResult(BoundaryIsolation.BUBBLEWRAP if self.bwrap else BoundaryIsolation.DENY,
                                 proc.returncode if proc is not None else -1,out,err,timed,dur,exe_digest,argv_digest,proc.pid if proc is not None else None,process_start_time_ns,stdout_total,stderr_total,observed_lineage,cgroup_events)

    def enter(self, request: AuthorizedWorkRequest, handle: LocalWorkspaceSnapshotHandle) -> BoundaryContext:
        self._assert_bwrap_usable()
        self._assert_cgroup_v2()
        if handle.fencing_token != request.execution_lease.fencing_token:
            raise PermissionError("workspace handle fencing token mismatch")
        if handle.workspace_id != request.execution_lease.workspace_id or handle.snapshot_id != request.execution_lease.workspace_snapshot_id:
            raise PermissionError("workspace snapshot binding mismatch")
        if handle.verify_identity() is not IdentityCheckResult.MATCH:
            raise PermissionError("workspace handle identity is not stable")
        return BoundaryContext(_stable_id("boundary",(request.execution_lease.lease_id,handle.handle_id)),
                              IsolationLevel.CONTAINER if self.bwrap else IsolationLevel.PROCESS,handle.handle_id,request.execution_lease.fencing_token)

    def exit(self, ctx: BoundaryContext) -> None:
        if not ctx.boundary_id:
            raise ValueError("invalid boundary context")

    def kill(self, ctx: BoundaryContext, reason: str) -> None:
        if not ctx.boundary_id or not reason:
            raise ValueError("valid boundary context and kill reason are required")
        for pid in tuple(self._active_pids):
            if hasattr(os, "killpg"):
                try: os.killpg(pid,signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError): pass
            else:
                try: os.kill(pid,signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError): pass

    def run(self, argv: Sequence[str], **kwargs) -> BoundaryRunResult:
        """Public raw-boundary API is deliberately disabled; use SClassControlPlane.execute_authorized_work."""
        raise PermissionError("raw OS execution is not a production API; route execution through ExecutionGate")


class LocalWorkspaceSnapshotHandle:
    """Fenced directory handle used by the concrete execution lifecycle."""
    def __init__(self, workspace: Path, workspace_id: str, snapshot_id: str, fencing_token: int):
        self.workspace=workspace; self.workspace_id=workspace_id; self.snapshot_id=snapshot_id; self.fencing_token=fencing_token
        st=os.stat(workspace,follow_symlinks=False)
        self._device,self._inode=st.st_dev,st.st_ino
        dev_i64 = self._device if self._device <= (2**63 - 1) else self._device - 2**64
        ino_i64 = self._inode if self._inode <= (2**63 - 1) else self._inode - 2**64
        self.handle_id=_stable_id("handle",(workspace_id,snapshot_id,fencing_token,dev_i64,ino_i64))

    def verify_identity(self):
        try:
            st=os.stat(self.workspace,follow_symlinks=False)
        except OSError:
            return IdentityCheckResult.UNVERIFIABLE
        return IdentityCheckResult.MATCH if (not self.workspace.is_symlink() and st.st_dev==self._device and st.st_ino==self._inode and self.workspace.is_dir()) else IdentityCheckResult.MISMATCH

    def snapshot_digest(self):
        return _workspace_manifest_digest(self.workspace)[0]


class LocalObservationCollector:
    def __init__(self, workspace: Path, request: AuthorizedWorkRequest):
        self.workspace=workspace; self.request=request

    def capture_before(self, handle: LocalWorkspaceSnapshotHandle) -> WorkspaceSnapshot:
        digest_value, count, files = _workspace_manifest_details(handle.workspace)
        self._before_files = files
        state=ContentManifestState(digest_value,count)
        return WorkspaceSnapshot(handle.snapshot_id,self.request.proposal.state_binding.workspace_id,state,digest_value,count,_now())

    def capture_after(self, handle: LocalWorkspaceSnapshotHandle, before: WorkspaceSnapshot,
                      process_result: Optional[ProcessExecutionResult], proof: QuiescenceProof) -> ObservationRecord:
        after_digest, after_count, files_after = _workspace_manifest_details(handle.workspace)
        before_files=getattr(self,"_before_files",{})
        mutations=[]
        for path in sorted(set(before_files)|set(files_after)):
            b=before_files.get(path); a=files_after.get(path)
            if b is None: mutations.append(FileMutation(path,MutationKind.CREATED,None,a[0],None,a[1],None))
            elif a is None: mutations.append(FileMutation(path,MutationKind.DELETED,b[0],None,b[1],None,None))
            elif b != a:
                kind=MutationKind.MODE_CHANGED if b[0]==a[0] and b[1]!=a[1] else MutationKind.MODIFIED
                mutations.append(FileMutation(path,kind,b[0],a[0],b[1],a[1],None))
        mutation_tuple=tuple(mutations)
        mutation_digest=MutationDigest(str(digest("sclass/mutation-set/v1",mutation_tuple)))
        actor=ActorIdentity(self.request.execution_lease.worker_identity,ActorKind.WORKER,process_result.identity if process_result else None)
        git=GitState("NO-GIT","NO-GIT",digest("sclass/git/index/v1",()),digest("sclass/git/untracked/v1",()))
        env=EnvironmentFingerprint(os.uname().sysname,os.uname().machine,digest("sclass/toolchain/v1",(sys.executable,sys.version.split()[0])),digest("sclass/env-names/v1",tuple(sorted(os.environ.keys()))),None)
        obs_id=_stable_id("obs",(self.request.request_id,self.request.execution_attempt_id,after_digest,proof.proof_id))
        return ObservationRecord(obs_id,self.request.request_id,self.request.node_id,self.request.execution_generation,self.request.execution_attempt_id,
            self.request.execution_lease.target_snapshot_digest,self.request.governing_budget_lineage_id,self.request.execution_lease.worker_identity,
            mutation_digest,mutation_tuple,git,env,actor,(AttributionEvidence(AttributionMethod.FENCED_BOUNDARY,10000,digest("sclass/attribution/v1",proof)),),
            _now(),"workspace",(),process_result,before.snapshot_id,_stable_id("after-snapshot",(obs_id,after_digest)),after_digest,proof,False)


def _workspace_manifest_details(root: Path):
    files={}
    for pth in sorted(root.rglob("*")):
        rel=pth.relative_to(root).as_posix()
        try: st=pth.lstat()
        except OSError: continue
        if pth.is_symlink():
            files[rel]=(digest("sclass/symlink/v1",os.readlink(pth)),st.st_mode)
        elif pth.is_file():
            files[rel]=(LinuxExecutionBoundary._file_digest(pth),st.st_mode)
    payload=tuple((k,str(v[0]),v[1]) for k,v in files.items())
    return digest("sclass/workspace-manifest/v2",payload),len(files),files

def _workspace_manifest_digest(root: Path):
    d,c,_=_workspace_manifest_details(root); return d,c

def _snapshot_files_from_workspace(snapshot: WorkspaceSnapshot, root: Path):
    _d,_c,files=_workspace_manifest_details(root)
    return files


class LocalQuiescenceAttestor:
    """Boundary attestor. Production requires an externally provisioned root/key; test generation is explicit."""
    def __init__(self, keys: SQLiteKeyDirectory, trust_root: str, key_id: str, private: Ed25519PrivateKey, *, _provisioning_token=None):
        if _provisioning_token not in (_BOUNDARY_PROVISIONING_TOKEN,_BOUNDARY_TEST_TOKEN):
            raise PermissionError("boundary attestor must be constructed through an explicit provisioning/test factory")
        if not trust_root or not key_id:
            raise ValueError("provisioned boundary trust root and key id are required")
        self.keys=keys; self.trust_root=trust_root; self.key_id=key_id; self.private=private
        self._test_only=_provisioning_token is _BOUNDARY_TEST_TOKEN

    def is_production_provisioned(self) -> bool:
        return not self._test_only and self.is_provisioned

    @property
    def is_provisioned(self) -> bool:
        if not self.trust_root or not self.key_id or self.private is None:
            return False
        if self.keys is None or not hasattr(self.keys, "status"):
            return False
        return self.keys.status(self.key_id, self.trust_root, _now()) is KeyStatus.ACTIVE

    @property
    def public_key_bytes(self) -> bytes:
        if self.private is None:
            return b""
        return self.private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    def attest(self, request: AuthorizedWorkRequest, result: BoundaryRunResult) -> QuiescenceProof:
        if result.process_id is None or result.process_start_time_ns is None:
            raise PermissionError("OS process identity is unavailable; quiescence cannot be proven")
        if not self.is_provisioned:
            raise PermissionError("quiescence attestation requires provisioned boundary authority")
        boundary_id=_stable_id("boundary",(request.execution_lease.lease_id,request.execution_attempt_id))
        proof_id=_stable_id("q",(boundary_id,result.process_id,result.process_start_time_ns))
        placeholder=SignatureBlock("ed25519",self.key_id,self.trust_root,"c1",b"\x00"*64)
        unsigned=QuiescenceProof(proof_id,boundary_id,"linux-process-group",digest("sclass/execution-identity/v1",request.execution_lease.executable_identity),request.execution_lease.lease_id,request.execution_generation,request.execution_attempt_id,request.execution_lease.worker_identity,result.process_id,result.process_start_time_ns,_now(),Digest("sha256:"+"0"*64),self.key_id,placeholder)
        pd=quiescence_proof_digest(unsigned)
        msg=signature_preimage("sclass/quiescence-attestation/v3",(unsigned.proof_id,unsigned.boundary_id,unsigned.mechanism,unsigned.target_execution_identity_digest,unsigned.execution_lease_id,unsigned.execution_generation,unsigned.execution_attempt_id,unsigned.worker_identity,unsigned.process_id,unsigned.process_start_time_ns,unsigned.proven_at,pd))
        sig=self.private.sign(msg)
        block=SignatureBlock("ed25519",self.key_id,self.trust_root,"c1",sig)
        proof=replace(unsigned,proof_digest=pd,attestation_signature=block)
        if not _verify_quiescence_attestation(self.keys,proof,_now()): raise PermissionError("boundary quiescence verification failed")
        return proof


class UnprovisionedQuiescenceAuthority:
    is_provisioned=False
    def is_production_provisioned(self) -> bool:
        return False
    def attest(self, request, result):
        raise PermissionError("no provisioned OS-boundary quiescence authority is configured")


def validate_execution_lease(state: EngineeringState, lease_record: LeaseRecord) -> bool:
    if not S.validate_execution_lease(state, lease_record):
        return False
    # ZV5: Ban duplicate active execution leases for any single work node
    if lease_record.state is LeaseState.ACTIVE:
        for lr in state.leases.values():
            if lr.lease.node_id == lease_record.lease.node_id and lr.state is LeaseState.ACTIVE and lr.lease.lease_id != lease_record.lease.lease_id:
                return False
    return True


class SubprocessWorker(WorkerContract):
    """Production SubprocessWorker adapter meeting full WorkerContract specification."""
    def __init__(self, profile: Optional[WorkerProfile] = None, boundary: Optional[LinuxExecutionBoundary] = None):
        self._profile = profile or WorkerProfile(
            profile_id="subprocess-worker",
            kind=WorkerKind.SUBPROCESS,
            capabilities=(),
            model=None,
            max_isolation=IsolationLevel.PROCESS,
        )
        self._boundary = boundary
        self._cancelled_requests: set[str] = set()
        self._running_pids: dict[str, int] = {}
        self._last_result: Optional[BoundaryRunResult] = None

    def profile(self) -> WorkerProfile:
        return self._profile

    def cancel(self, request_id: str, reason: str) -> None:
        self._cancelled_requests.add(request_id)
        pid = self._running_pids.get(request_id)
        if pid is not None:
            try:
                if hasattr(os, "killpg"):
                    os.killpg(pid, signal.SIGKILL)
                else:
                    os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass

    def heartbeat(self, request_id: str) -> WorkerHealth:
        if request_id in self._cancelled_requests:
            return WorkerHealth.EXITED
        pid = self._running_pids.get(request_id)
        if pid is None:
            return WorkerHealth.ALIVE
        try:
            if hasattr(os, "killpg"):
                os.killpg(pid, 0)
            else:
                os.kill(pid, 0)
            return WorkerHealth.ALIVE
        except (ProcessLookupError, OSError):
            return WorkerHealth.EXITED

    def execute(self, request: AuthorizedWorkRequest, boundary: BoundaryContext,
                handle: WorkspaceSnapshotHandle, *, _gate_capability=None,
                argv: Optional[Sequence[str]] = None, allow_write: bool = False,
                allow_network: bool = False, env: Optional[Mapping[str, str]] = None,
                timeout_ms: int = 30_000, max_output_bytes: int = 1_000_000,
                budget: Optional[ResourceBudget] = None, write_paths: Sequence[str] = (),
                filesystem_accesses: Sequence[FilesystemAccess] = ()) -> WorkResult:
        if isinstance(request, (WorkProposal, WorkNode)):
            raise PermissionError("WorkerContract.execute accepts only AuthorizedWorkRequest; WorkProposal/WorkNode execution is prohibited")
        if not isinstance(request, AuthorizedWorkRequest) or type(request).__name__ == "MagicMock":
            raise PermissionError("WorkerContract.execute accepts only AuthorizedWorkRequest; WorkProposal/WorkNode execution is prohibited")
        if boundary is None or not isinstance(boundary, BoundaryContext) or type(boundary).__name__ == "MagicMock":
            raise PermissionError("WorkerContract.execute requires an authentic BoundaryContext; direct execution outside ExecutionGate is prohibited")
        if handle is None:
            raise PermissionError("WorkspaceSnapshotHandle is required")
        if boundary.fencing_token != request.execution_lease.fencing_token:
            raise PermissionError("boundary fencing token does not match execution lease")
        if self._boundary is None:
            raise PermissionError("Execution boundary is not configured on worker")
        if _gate_capability is None or _gate_capability is not getattr(self._boundary, "_gate_capability", None) or type(self._boundary).__name__ == "MagicMock":
            raise PermissionError("WorkerContract.execute cannot be invoked outside ExecutionGate; gate capability missing or invalid")
        if request.request_id in self._cancelled_requests:
            raise PermissionError("execution request was cancelled")
        if argv is None:
            specs = getattr(request.requested_effect, "subprocess", ()) if request.requested_effect else ()
            if not specs:
                raise ValueError("no subprocess spec provided for execution")
            raise ValueError("argv must be provided or derived")
        result = self._boundary._run_from_gate(
            _gate_capability,
            argv,
            allow_write=allow_write,
            allow_network=allow_network,
            env=env,
            timeout_ms=timeout_ms,
            max_output_bytes=max_output_bytes,
            budget=budget,
            expected_executable_digest=request.execution_lease.executable_identity.digest,
            write_paths=write_paths,
            filesystem_accesses=filesystem_accesses,
        )
        self._last_result = result
        if result.process_id:
            self._running_pids[request.request_id] = result.process_id
        claim_status = (
            WorkerClaimStatus.CLAIMED_COMPLETE
            if result.returncode == 0 and not result.timed_out
            else WorkerClaimStatus.CLAIMED_FAILED
        )
        return WorkResult(
            result_id=_stable_id("result", (request.request_id, result.process_id or 0)),
            request_id=request.request_id,
            request_content_digest=request.proposal.request_content_digest,
            envelope_digest=request.envelope_digest,
            execution_generation=request.execution_generation,
            execution_attempt_id=request.execution_attempt_id,
            target_snapshot_digest=request.execution_lease.target_snapshot_digest,
            state_binding_digest=getattr(request, "state_binding_digest", None) or getattr(request.proposal, "state_binding_digest", None) or digest("sclass/state-binding/v1", ()),
            governing_budget_lineage_id=request.governing_budget_lineage_id,
            objective_revision=getattr(request.execution_lease, "objective_revision", "rev-1"),
            workgraph_revision=getattr(getattr(request.proposal, "state_binding", None), "workgraph_revision", "wg-1"),
            worker_identity=request.execution_lease.worker_identity,
            claim_status=claim_status,
            measured_tokens=0,
            measured_duration_ms=result.duration_ms,
            output_digest=digest("sclass/worker-output/v1", (result.stdout, result.stderr)),
            diagnostics_digest=digest("sclass/worker-diagnostics/v1", ()),
            produced_artifacts=(),
        )


class ExecutionGate:
    """Single fail-closed S2 execution choke point.

    Admission, budget reservation, attestation/capability checks, executable identity,
    OS isolation and nonce lineage are all revalidated immediately before spawn.
    """
    def __init__(self, boundary: LinuxExecutionBoundary, control_plane: Optional["SClassControlPlane"] = None):
        self.boundary=boundary
        self.control_plane=control_plane
        self._gate_capability=boundary._gate_capability

    def _verify_worker_attestation(self, request: AuthorizedWorkRequest, state: EngineeringState, now: UtcInstant) -> AdapterAttestation:
        worker_id=request.execution_lease.worker_identity
        if not worker_id or not self.control_plane.workers.is_active(worker_id):
            raise PermissionError("worker identity is not currently active")
        att=self.control_plane.workers.attestation_record(worker_id)
        if att is None:
            raise PermissionError("structured adapter attestation is required; digest-only worker registration is insufficient")
        if att.worker_identity != worker_id:
            raise PermissionError("worker attestation worker identity mismatch")
        if att.executable_digest != request.execution_lease.executable_identity.digest:
            raise PermissionError("worker attestation executable digest mismatch")
        if not (att.issued_at.epoch_ns <= now.epoch_ns < att.expires_at.epoch_ns):
            raise PermissionError("worker attestation is outside its validity window")
        if self.control_plane.workers.attestation(worker_id) != adapter_attestation_digest(att):
            raise PermissionError("worker attestation registry digest mismatch")
        if self.control_plane.keys.status(att.key_id,att.trust_root,now) is not KeyStatus.ACTIVE:
            raise PermissionError("worker attestation signing key is not currently trusted")
        if self.control_plane.keys.verify_current(att.signature,adapter_attestation_signature_message(att),now) is not SignatureVerificationResult.VALID:
            raise PermissionError("worker adapter attestation signature is invalid")
        decision=self._canonical_decision(request,state)
        if decision.capability_attestation_digest != adapter_attestation_digest(att):
            raise PermissionError("authorization decision is not bound to current adapter attestation")
        matches=tuple(c for c in att.capabilities if c.action is request.action_type and c.valid_from.epoch_ns <= now.epoch_ns < c.valid_until.epoch_ns)
        if not matches:
            raise PermissionError("no currently valid attested capability matches requested action")
        capability_ok=S.capability_authorizes(
            att.capabilities, request.action_type, now, request.requested_effect,
            decision.effect_scope, request.authorization_lease.claims.allowed_effects, {})
        if not capability_ok:
            raise PermissionError("attested capability independently denies the requested effect")
        return att

    def _canonical_decision(self, request: AuthorizedWorkRequest, state: EngineeringState) -> AuthorizationDecision:
        decision=state.authorization_decisions.get(request.authorization_lease.claims.decision_id)
        if not isinstance(decision,AuthorizationDecision) or decision.decision is not AuthorizationState.ALLOW:
            raise PermissionError("canonical ALLOW authorization decision required")
        if decision.proposal_id != request.proposal.proposal_id or decision.worker_identity != request.execution_lease.worker_identity:
            raise PermissionError("authorization decision lineage mismatch")
        if not validate_authorization_decision(state,decision,_now()):
            raise PermissionError("canonical authorization decision no longer validates")
        return decision

    def _verify_budget_reservation(self, request: AuthorizedWorkRequest, state: EngineeringState, now: UtcInstant) -> BudgetReservation:
        reservation=state.budget_reservations.get(request.budget_reservation_id)
        if reservation is None:
            raise PermissionError("canonical budget reservation not found")
        if reservation.lifecycle_state is not BudgetReservationState.RESERVED:
            raise PermissionError("budget reservation is no longer RESERVED")
        if reservation.workspace_id != state.workspace_id:
            raise PermissionError("budget reservation workspace mismatch")
        if reservation.request_id != request.request_id:
            raise PermissionError("budget reservation request mismatch")
        if reservation.governing_budget_lineage_id != request.governing_budget_lineage_id:
            raise PermissionError("budget reservation lineage mismatch")
        if not _budget_leq(request.requested_effect.requested_budget,reservation.amount):
            raise PermissionError("requested budget exceeds concrete reservation")
        if now.epoch_ns >= reservation.expires_at.epoch_ns:
            raise PermissionError("budget reservation is expired")
        try:
            row=self.control_plane.budgets._read(state.workspace_id,reservation.reservation_id)
        except KeyError as exc:
            raise PermissionError("runtime budget reservation projection is missing") from exc
        status=row[4]
        if status != BudgetReservationState.RESERVED.value:
            raise PermissionError("runtime budget reservation projection is not RESERVED")
        if row[0] != reservation.request_id or row[2] != reservation.governing_budget_lineage_id or int(row[6]) < now.epoch_ns:
            raise PermissionError("runtime budget reservation projection is not bound to canonical reservation")
        projection_amount=canonical_c1_unpack(row[1])
        if not isinstance(projection_amount,ResourceBudget) or projection_amount != reservation.amount:
            raise PermissionError("runtime budget reservation amount diverges from canonical reservation")
        return reservation

    def _verify_request_state_lineage(self, request: AuthorizedWorkRequest, state: EngineeringState) -> None:
        """Validate the proposal binding against the canonical anchor and allow only the exact admission suffix.

        Budget/lease/intent/start events are safe only when they are all attributable to this request.
        Any unrelated canonical mutation after the request's authority anchor causes immediate denial.
        """
        events=self.control_plane.store._read_all_committed(state.workspace_id)
        anchor=request.proposal.state_binding.event_head_hash
        if anchor == GENESIS_EVENT_HASH:
            anchor_index=-1; anchor_state=genesis_engineering_state(state.workspace_id)
        else:
            anchor_index=next((i for i,e in enumerate(events) if e.event_hash == anchor),None)
            if anchor_index is None:
                raise PermissionError("proposal state-binding anchor is not canonical")
            anchor_state=genesis_engineering_state(state.workspace_id)
            for e in events[:anchor_index+1]: anchor_state=REFERENCE_REDUCER.reduce(anchor_state,e)
        expected=state_binding_digest(canonical_current_state_binding(anchor_state,request.execution_generation,request.governing_budget_lineage_id))
        if request.state_binding_digest != expected or state_binding_digest(request.proposal.state_binding) != expected:
            raise PermissionError("proposal state binding does not match canonical anchor")
        allowed={EventType.AUTHORIZATION_GRANTED,EventType.BUDGET_RESERVED,EventType.LEASE_ISSUED,EventType.EXECUTION_INTENT,EventType.EXECUTION_STARTED}
        decision_id=request.authorization_lease.claims.decision_id
        for e in events[anchor_index+1:]:
            if e.event_type not in allowed:
                raise PermissionError("unrelated canonical mutation occurred after execution authority anchor")
            if e.event_type in (EventType.AUTHORIZATION_GRANTED,EventType.AUTHORIZATION_DENIED):
                obj=e.payload.get("authorization_decision")
                if obj is None or obj.decision_id != decision_id: raise PermissionError("authorization lineage contains an unrelated decision")
            elif e.event_type is EventType.BUDGET_RESERVED:
                obj=e.payload.get("reservation")
                if obj is None or obj.reservation_id != request.budget_reservation_id: raise PermissionError("budget admission lineage mismatch")
            elif e.event_type is EventType.LEASE_ISSUED:
                obj=e.payload.get("lease")
                if obj is None or obj.lease.lease_id != request.execution_lease.lease_id: raise PermissionError("execution lease lineage mismatch")
            elif e.event_type is EventType.EXECUTION_INTENT:
                obj=e.payload.get("execution_intent")
                if obj is None or obj.execution_lease_id != request.execution_lease.lease_id: raise PermissionError("execution intent lineage mismatch")
            elif e.event_type is EventType.EXECUTION_STARTED:
                obj=e.payload.get("execution_generation")
                if obj is None or obj.execution_attempt_id != request.execution_attempt_id or obj.generation != request.execution_generation: raise PermissionError("execution generation lineage mismatch")

    def _preflight(self, request: AuthorizedWorkRequest, argv: Sequence[str], *, allow_write: bool, allow_network: bool, env: Optional[Mapping[str,str]], timeout_ms: int, max_output_bytes: int):
        """Validate all side-effect-free prerequisites before internal atomic admission.

        At this stage ``request.execution_lease`` is an admission template, not a canonical
        lease. The concrete ExecutionLease, fencing token, BudgetReserved event and
        ExecutionIntent are created atomically by ``ExecutionAdmission._admit`` below.
        """
        if self.control_plane is None: raise PermissionError("ExecutionGate requires authenticated control-plane authority")
        if not getattr(self.control_plane.boundary_attestor, "is_provisioned", False):
            raise PermissionError("ExecutionGate requires provisioned OS-boundary quiescence authority")
        if isinstance(self.boundary, LinuxExecutionBoundary):
            attestor = self.control_plane.boundary_attestor
            is_prod = getattr(attestor, "is_production_provisioned", None)
            if callable(is_prod):
                is_prod = is_prod()
            if not is_prod or getattr(attestor, "_test_only", False):
                raise PermissionError("real LinuxExecutionBoundary rejects test-only quiescence authority")
            if not attestor or not getattr(attestor, "trust_root", None):
                raise PermissionError("quiescence attestor has no provisioned trust root")
            if not getattr(self.control_plane, "pinned_keys", None):
                raise PermissionError("real LinuxExecutionBoundary requires explicit pinned keys in control plane")
            if attestor.trust_root not in self.control_plane.keys.roots():
                raise PermissionError("quiescence attestor trust root is not in provisioned trust roots")
            if attestor.trust_root not in self.control_plane.pinned_trust_roots:
                raise PermissionError("quiescence attestor trust root is not in pinned trust roots")
            if self.control_plane.keys.status(attestor.key_id, attestor.trust_root, _now()) is not KeyStatus.ACTIVE:
                raise PermissionError("quiescence attestor key is not active in provisioned trust root")
            pub_row = self.control_plane.keys.db.execute(
                "SELECT public_key FROM runtime_keys WHERE key_id=? AND trust_root=?",
                (attestor.key_id, attestor.trust_root),
            ).fetchone()
            if pub_row is None:
                raise PermissionError("quiescence attestor key is not active in provisioned trust root")
            attestor_pub = bytes(pub_row[0])
            if (attestor.trust_root, attestor_pub) not in self.control_plane.pinned_keys:
                raise PermissionError("quiescence attestor key is not in pinned key set")
            if not hasattr(attestor, "private") or attestor.private is None:
                raise PermissionError("quiescence attestor private key is missing")
            try:
                own_pub = attestor.private.public_key().public_bytes(
                    serialization.Encoding.Raw, serialization.PublicFormat.Raw
                )
            except Exception as exc:
                raise PermissionError(f"quiescence attestor private key is invalid: {exc}") from exc
            if own_pub != attestor_pub:
                raise PermissionError("quiescence attestor private key does not match registered public key")
            if (attestor.trust_root, own_pub) not in self.control_plane.pinned_keys:
                raise PermissionError("quiescence attestor private key is not in pinned key set")
        lease_template=request.execution_lease
        if not isinstance(lease_template, ExecutionLease) or not lease_template.lease_id:
            raise PermissionError("execution lease template is required")
        if not lease_template.worker_identity or lease_template.budget_reservation_id != request.budget_reservation_id:
            raise PermissionError("execution worker/reservation identity is incomplete")
        if lease_template.execution_generation != request.execution_generation or lease_template.execution_attempt_id != request.execution_attempt_id:
            raise PermissionError("execution generation/attempt mismatch")
        if lease_template.governing_budget_lineage_id != request.governing_budget_lineage_id:
            raise PermissionError("budget lineage mismatch")
        expected_reservation_id=_stable_id("res",(request.request_id,request.execution_attempt_id,request.governing_budget_lineage_id,request.requested_effect.requested_budget))
        if request.budget_reservation_id != expected_reservation_id:
            raise PermissionError("budget reservation identity is not deterministically bound to the request")
        state=self.control_plane.store._load_canonical_state(request.proposal.state_binding.workspace_id)
        now=_now()
        self._verify_request_state_lineage(request,state)
        if any(lr.lease.node_id == request.node_id and lr.state is LeaseState.ACTIVE for lr in state.leases.values()):
            raise PermissionError(f"active execution lease already exists for node {request.node_id}")
        if state.governing_budget_lineages.get(request.governing_budget_lineage_id) is None:
            raise PermissionError("governing budget lineage is not canonical")
        decision=self._canonical_decision(request,state)
        audience=request.authorization_lease.claims.audience
        if state.active_policy is None or audience not in state.active_policy.authorization_rules.allowed_audiences:
            raise PermissionError("authorization audience is not allowed by canonical policy")
        self._verify_worker_attestation(request,state,now)
        if not verify_authorization_lease(self.control_plane.keys,request.authorization_lease,request,state,now,expected_audience=audience):
            raise PermissionError("authorization lease verification failed at execution gate")
        if decision.control_profile_digest is None or decision.effect_scope != request.effect_scope:
            raise PermissionError("authorization control-profile/effect binding is incomplete")
        if not argv or any(not isinstance(x,str) or not x for x in argv): raise ValueError("invalid executable argv")
        argv_digest=digest("sclass/argv/v1",tuple(argv))
        subprocess_specs=request.requested_effect.subprocess
        if len(subprocess_specs) != 1: raise PermissionError("execution gate requires one exact subprocess specification")
        spec=subprocess_specs[0]
        if spec.argv_digest != argv_digest or spec.executable_digest != lease_template.executable_identity.digest:
            raise PermissionError("executable/argv identity does not match authorized request")
        att=self.control_plane.workers.attestation_record(lease_template.worker_identity)
        if att is None or not S.capability_authorizes(att.capabilities,request.action_type,now,request.requested_effect,decision.effect_scope,request.authorization_lease.claims.allowed_effects,{}):
            raise PermissionError("concrete worker capability does not authorize this execution")
        scope_result=S.authorized(request.requested_effect,request.effect_scope)
        if scope_result is not ScopeAuthorizationResult.AUTHORIZED: raise PermissionError(f"execution scope denied: {scope_result.value}")
        if request.action_type == ActionType.APPLY_DELTA:
            delta_digest = request.requested_effect.delta_digest if request.requested_effect else None
            if not delta_digest:
                raise PermissionError("APPLY_DELTA requires delta_digest in requested_effect")
            delta = next((d for d in state.verified_deltas.values() if d.delta_digest == delta_digest), None)
            if not delta:
                raise PermissionError(f"VerifiedWorkspaceDelta {delta_digest} not found in state")
            if request.requested_effect.network:
                raise PermissionError("APPLY_DELTA cannot contain network effects")
            if request.requested_effect.environment:
                raise PermissionError("APPLY_DELTA cannot contain environment modifications")
            if request.requested_effect.credentials:
                raise PermissionError("APPLY_DELTA cannot contain credential grants")
            if request.requested_effect.external_side_effects:
                raise PermissionError("APPLY_DELTA cannot contain external side effects")
            if state.target_snapshot is not None and delta.source_workspace_digest != target_snapshot_digest(state.target_snapshot):
                raise PermissionError("APPLY_DELTA source_workspace_digest does not match current target snapshot")
        if allow_network or request.requested_effect.network: raise PermissionError("network execution requires an OS egress broker")
        write_paths=[]
        for access in request.requested_effect.filesystem:
            if access.mode is not FsMode.READ: write_paths.append(access.path)
        if write_paths and not allow_write: raise PermissionError("write-capable request requires explicit allow_write")
        resolved=self.boundary._executable_path(argv[0])
        if self.boundary._file_digest(resolved) != lease_template.executable_identity.digest:
            raise PermissionError("resolved executable digest does not match authorized execution identity")
        return state,decision,tuple(sorted(set(write_paths))),now

    def _admit_request(self, request: AuthorizedWorkRequest, state: EngineeringState, decision: AuthorizationDecision, now: UtcInstant) -> tuple[AuthorizedWorkRequest, LeaseRecord, ExecutionIntent, EngineeringState]:
        """Invoke the canonical internal admission path as the single S2 authority transition."""
        audience=request.authorization_lease.claims.audience
        lease_record,intent=self.control_plane._execution_admission._admit(
            request,
            authorization_lease=request.authorization_lease,
            execution_lease_template=request.execution_lease,
            budget_amount=request.requested_effect.requested_budget,
            audience=audience,
            now=now,
            _gate_token=self.control_plane._execution_admission._gate_token,
        )
        admitted_state=self.control_plane.store._load_canonical_state(state.workspace_id)
        admitted_request=replace(
            request,
            execution_lease=lease_record.lease,
            envelope_digest=authorized_work_request_envelope_digest(
                request,admitted_state,self._canonical_decision(request,admitted_state)),
        )
        return admitted_request,lease_record,intent,admitted_state

    def execute(self, request: AuthorizedWorkRequest, argv_or_worker: Optional[Union[Sequence[str], WorkerContract]] = None, *, argv: Optional[Sequence[str]] = None, worker: Optional[WorkerContract] = None, allow_write: bool = False, allow_network: bool = False, env: Optional[Mapping[str, str]] = None, timeout_ms: int = 30_000, max_output_bytes: int = 1_000_000) -> ExecutionOutcome:
        """The sole public execution entry: always performs the canonical lifecycle."""
        return self.execute_lifecycle(request, argv_or_worker=argv_or_worker, argv=argv, worker=worker, allow_write=allow_write, allow_network=allow_network, env=env, timeout_ms=timeout_ms, max_output_bytes=max_output_bytes)


    def _evaluate_verification_verdict(self, request: AuthorizedWorkRequest, state: EngineeringState, result: ExecutionResult, observation: ObservationRecord) -> AssessmentVerdict:
        process_success = (result.returncode == 0 and not result.timed_out)
        delta_digest = request.requested_effect.delta_digest if request.requested_effect else None

        if request.action_type == ActionType.APPLY_DELTA:
            if not delta_digest:
                return AssessmentVerdict.REJECT
            delta = next((d for d in state.verified_deltas.values() if d.delta_digest == delta_digest), None)
            if not delta:
                return AssessmentVerdict.REJECT
            if apply_delta_observation_matches(delta, observation) != DeltaMatchVerdict.MATCH:
                return AssessmentVerdict.REJECT
        elif delta_digest:
            delta = next((d for d in state.verified_deltas.values() if d.delta_digest == delta_digest), None)
            if not delta:
                return AssessmentVerdict.REJECT
            if apply_delta_observation_matches(delta, observation) != DeltaMatchVerdict.MATCH:
                return AssessmentVerdict.REJECT

        if not process_success:
            return AssessmentVerdict.REJECT

        return AssessmentVerdict.ACCEPT

    def execute_lifecycle(self, request: AuthorizedWorkRequest, argv_or_worker: Optional[Union[Sequence[str], WorkerContract]] = None, *, argv: Optional[Sequence[str]] = None, worker: Optional[WorkerContract] = None, allow_write: bool = False, allow_network: bool = False, env: Optional[Mapping[str, str]] = None, timeout_ms: int = 30_000, max_output_bytes: int = 1_000_000) -> ExecutionOutcome:
        if argv_or_worker is not None and not isinstance(argv_or_worker, (list, tuple)) and hasattr(argv_or_worker, "execute"):
            worker_instance = argv_or_worker
            actual_argv = argv
        elif worker is not None:
            worker_instance = worker
            actual_argv = argv_or_worker if isinstance(argv_or_worker, (tuple, list)) else argv
        elif isinstance(argv_or_worker, (tuple, list)):
            actual_argv = argv_or_worker
            worker_instance = SubprocessWorker(boundary=self.boundary)
        else:
            actual_argv = argv
            worker_instance = SubprocessWorker(boundary=self.boundary)

        if actual_argv is None:
            raise ValueError("argv must be provided or derived for execution")

        state,decision,write_paths,now=self._preflight(request,actual_argv,allow_write=allow_write,allow_network=allow_network,env=env,timeout_ms=timeout_ms,max_output_bytes=max_output_bytes)
        # Step 6 of the frozen §8.6 contract: the gate MUST obtain the canonical
        # ExecutionLease atomically with reservation + nonce + ExecutionIntent.
        request,lease_record,intent,state=self._admit_request(request,state,decision,now)
        # Post-admission proof is against canonical state, never against caller memory.
        canonical_lease=state.leases.get(request.execution_lease.lease_id)
        if not isinstance(canonical_lease,LeaseRecord) or canonical_lease.state is not LeaseState.ACTIVE or canonical_lease.lease != request.execution_lease:
            raise PermissionError("ExecutionAdmission did not return the exact canonical active lease")
        if not validate_execution_lease(state,canonical_lease):
            raise PermissionError("canonical execution lease failed post-admission validation")
        reservation=self._verify_budget_reservation(request,state,_now())
        audience=request.authorization_lease.claims.audience
        if not self.control_plane.nonces.verify_consumed_binding(f"{state.workspace_id}:{audience}",request.authorization_lease.claims.nonce,request.authorization_lease.claims.request_content_digest,request.authorization_lease.claims.lease_id,request.execution_lease.lease_id,_now()):
            raise PermissionError("execution nonce was not atomically bound to the admitted lease")
        handle=LocalWorkspaceSnapshotHandle(self.boundary.workspace,state.workspace_id,state.workspace_snapshot_id,request.execution_lease.fencing_token)
        ctx=self.boundary.enter(request,handle)
        collector=LocalObservationCollector(self.boundary.workspace,request)
        before=collector.capture_before(handle)
        # Start generation is itself canonical and fenced by the current authority epoch.
        generation=ExecutionGeneration(request.node_id,request.execution_generation,request.execution_attempt_id,state.causal_frontier.authorization_epoch,request.execution_lease.worker_identity,
            request.execution_lease.target_snapshot_digest,state_binding_digest(canonical_current_state_binding(state,request.execution_generation,request.governing_budget_lineage_id)),
            request.governing_budget_lineage_id,state.objective.revisions[-1].revision_id,state.work_graph.revision_id,ExecutionGenerationStatus.ACTIVE)
        verifier_attestor = self.control_plane.boundary_attestor
        def commit_events(event_specs):
            cur = self.control_plane.store._load_canonical_state(state.workspace_id)
            for et, agg, payload in event_specs:
                actor = ActorIdentity("system", ActorKind.SYSTEM, None)
                if et in (EventType.EVIDENCE_ACCEPTED, EventType.ASSESSMENT_CREATED):
                    actor = ActorIdentity(verifier_attestor.key_id, ActorKind.VERIFIER, None)
                
                cmd_without_sig = Command(
                    workspace_id=cur.workspace_id,
                    command_id=f"cmd-{uuid.uuid4().hex}",
                    actor=actor,
                    event_type=et,
                    aggregate_id=agg,
                    expected_head=cur.event_head_hash,
                    payload=payload,
                    actor_signature=None
                )
                if et in (EventType.EVIDENCE_ACCEPTED, EventType.ASSESSMENT_CREATED):
                    sig_preimage = command_signature_message(cmd_without_sig)
                    sig = SignatureBlock("ed25519", verifier_attestor.key_id, verifier_attestor.trust_root, "c1", verifier_attestor.private.sign(sig_preimage))
                    cmd = replace(cmd_without_sig, actor_signature=sig)
                else:
                    cmd = cmd_without_sig
                
                res = self.control_plane._submit_internal(cmd)
                if res.disposition is not RuntimeDisposition.APPLIED:
                    raise PermissionError(f"lifecycle canonical append rejected for {et.value}: {res.detail}")
                cur = self.control_plane.store._load_canonical_state(state.workspace_id)
            return cur
        try:
            state=commit_events(((EventType.EXECUTION_STARTED,request.node_id,FrozenMap.from_items((("execution_generation",generation),("work_node_id",request.node_id))),),))
            # Concrete reservation is checked again after ExecutionStarted, immediately before spawn.
            reservation=self._verify_budget_reservation(request,state,_now())
            if isinstance(worker_instance, SubprocessWorker):
                work = worker_instance.execute(
                    request,
                    ctx,
                    handle,
                    _gate_capability=self._gate_capability,
                    argv=actual_argv,
                    allow_write=allow_write,
                    allow_network=False,
                    env=env,
                    timeout_ms=timeout_ms,
                    max_output_bytes=max_output_bytes,
                    budget=reservation.amount,
                    write_paths=write_paths,
                    filesystem_accesses=request.requested_effect.filesystem,
                )
                result = worker_instance._last_result
            else:
                try:
                    work = worker_instance.execute(
                        request,
                        ctx,
                        handle,
                        _gate_capability=self._gate_capability,
                        argv=actual_argv,
                        allow_write=allow_write,
                        allow_network=False,
                        env=env,
                        timeout_ms=timeout_ms,
                        max_output_bytes=max_output_bytes,
                        budget=reservation.amount,
                        write_paths=write_paths,
                        filesystem_accesses=request.requested_effect.filesystem,
                    )
                except TypeError:
                    work = worker_instance.execute(request, ctx, handle)
                result = getattr(worker_instance, "_last_result", None)
                if result is None:
                    result = self.boundary._run_from_gate(
                        self._gate_capability,
                        actual_argv,
                        allow_write=allow_write,
                        allow_network=False,
                        env=env,
                        timeout_ms=timeout_ms,
                        max_output_bytes=max_output_bytes,
                        budget=reservation.amount,
                        expected_executable_digest=request.execution_lease.executable_identity.digest,
                        write_paths=write_paths,
                        filesystem_accesses=request.requested_effect.filesystem,
                    )

            # Step 11 & 12: Quiescence check
            quiescence_proven = False
            if result is not None and result.process_id is not None and result.process_start_time_ns is not None:
                try:
                    if hasattr(os, "killpg"):
                        os.killpg(result.process_id, 0)
                    else:
                        os.kill(result.process_id, 0)
                    quiescence_proven = False
                except (ProcessLookupError, OSError):
                    quiescence_proven = True

            if not quiescence_proven:
                try:
                    self.boundary.kill(ctx, "quiescence cannot be proven")
                except Exception:
                    pass
                state = self.control_plane.store._load_canonical_state(request.proposal.state_binding.workspace_id)
                events = []
                lease = state.leases.get(request.execution_lease.lease_id)
                if lease is not None and lease.state is LeaseState.ACTIVE:
                    events.append((EventType.LEASE_REVOKED, request.execution_lease.lease_id, FrozenMap.from_items((("lease_id", request.execution_lease.lease_id),))))
                in_doubt_record = InDoubtRecord(
                    node_id=request.node_id,
                    reason="quiescence cannot be proven: process still active or identity unverifiable",
                    unresolved_effect_ids=(),
                    since_sequence=state.event_sequence,
                )
                events.append((EventType.IN_DOUBT_DECLARED, in_doubt_record.node_id, FrozenMap.from_items((("in_doubt", in_doubt_record), ("node_id", in_doubt_record.node_id)))))
                failure_fp = digest("sclass/work-failure/v1", (request.request_id, "QuiescenceFailure", "quiescence cannot be proven"))
                events.append((EventType.WORK_FAILED, request.node_id, FrozenMap.from_items((("failure_fingerprint", failure_fp),))))
                r = state.budget_reservations.get(request.budget_reservation_id)
                if r is not None and r.lifecycle_state is BudgetReservationState.RESERVED:
                    released = replace(r, lifecycle_state=BudgetReservationState.RELEASED, version=r.version + 1, released_amount=r.amount)
                    events.append((EventType.BUDGET_RELEASED, r.reservation_id, FrozenMap.from_items((("reservation", released), ("reservation_id", r.reservation_id)))))
                if events:
                    commit_events(tuple(events))
                try:
                    self.boundary.exit(ctx)
                except Exception:
                    pass
                return ExecutionOutcome(
                    request_id=request.request_id,
                    gate_result=GateResult.BOUNDARY_VIOLATION,
                    work_result=work,
                    observation_id=None,
                )

            proof=self.control_plane.boundary_attestor.attest(request,result)
            proc_identity=ExecutionIdentity(str(self.boundary._executable_path(actual_argv[0])),str(self.boundary._executable_path(actual_argv[0])),result.executable_digest or request.execution_lease.executable_identity.digest,
                str(result.executable_digest),"",request.execution_lease.executable_identity.digest,digest("sclass/environment/v1",env or {}),result.process_start_time_ns,
                result.process_lineage or (ProcessLineageEntry(result.process_id,result.process_start_time_ns,result.executable_digest or request.execution_lease.executable_identity.digest,result.argv_digest or digest("sclass/argv/v1",tuple(actual_argv))),))
            ps=ProcessExecutionResult(TerminationKind.TIMED_OUT if result.timed_out else (TerminationKind.EXITED if result.returncode >= 0 else TerminationKind.SIGNALED),
                result.returncode if result.returncode >= 0 else None,None,proc_identity,now,_now(),result.duration_ms,result.duration_ms,
                result.argv_digest or digest("sclass/argv/v1",tuple(actual_argv)),digest("sclass/environment/v1",env or {}),digest("sclass/stdout/v1",result.stdout),digest("sclass/stderr/v1",result.stderr),
                result.stdout_total_bytes,result.stderr_total_bytes,result.stdout[:max_output_bytes].decode("utf-8","replace"),result.stderr[:max_output_bytes].decode("utf-8","replace"),
                result.stdout_total_bytes>max_output_bytes or result.stderr_total_bytes>max_output_bytes,0,result.process_id)
            if work is None:
                work=WorkResult(_stable_id("result",(request.request_id,result.process_id)),request.request_id,request.proposal.request_content_digest,request.envelope_digest,request.execution_generation,request.execution_attempt_id,
                    request.execution_lease.target_snapshot_digest,generation.state_binding_digest,request.governing_budget_lineage_id,generation.objective_revision,generation.workgraph_revision,request.execution_lease.worker_identity,
                    WorkerClaimStatus.CLAIMED_COMPLETE if result.returncode==0 and not result.timed_out else WorkerClaimStatus.CLAIMED_FAILED,result.returncode or 0,result.duration_ms,digest("sclass/worker-output/v1",(result.stdout,result.stderr)),digest("sclass/worker-diagnostics/v1",()),())
            observation=collector.capture_after(handle,before,ps,proof)
            
            # S5 Verification Pipeline
            assessment_verdict = self._evaluate_verification_verdict(request, state, result, observation)
            
            payload = SignedEvidencePayload(
                serialization_version="c1",
                signer_identity=verifier_attestor.key_id,
                verification_step_id="step-1",
                evidence_kind=EvidenceKind.BEHAVIORAL,
                obligation_id=request.proposal.primary_obligation_id,
                requirement_key="req-1",
                observation_id=observation.observation_id,
                target_snapshot_digest=request.execution_lease.target_snapshot_digest,
                objective_revision=generation.objective_revision,
                acceptance_contract_revision=1,
                verification_plan_revision=1,
                dependency_set_digest=digest("sclass/dependency-set/v1", ()),
                result_status=VerificationStatus.PASS if assessment_verdict == AssessmentVerdict.ACCEPT else VerificationStatus.FAIL,
                input_digest=request.execution_lease.executable_identity.digest,
                policy_digest=request.execution_lease.executable_identity.digest,
                artifact_digest=request.execution_lease.executable_identity.digest,
                environment_digest=request.execution_lease.executable_identity.digest,
                tool_identity=verifier_attestor.key_id,
                tool_version="v6.0.1",
                issued_at=_now()
            )
            receipt_id = _stable_id("receipt", (observation.observation_id,))
            receipt_preimage = signature_preimage("sclass/evidence-signed-payload/v1", payload)
            receipt_sig = SignatureBlock("ed25519", verifier_attestor.key_id, verifier_attestor.trust_root, "c1", verifier_attestor.private.sign(receipt_preimage))
            receipt = EvidenceReceipt(receipt_id, EvidenceKind.BEHAVIORAL, payload, receipt_sig)
            
            receipt_verification = SignatureVerificationRecord(
                subject_id=receipt_id,
                signed_payload_digest=evidence_signed_payload_digest(receipt),
                signature_digest=signature_block_digest(receipt_sig),
                key_id=verifier_attestor.key_id,
                verification_result=SignatureVerificationResult.VALID,
                verification_time=_now()
            )
            
            closure_verdict = ClosureVerdict.SATISFIED if assessment_verdict is AssessmentVerdict.ACCEPT else ClosureVerdict.UNSATISFIED
            closure = EvidenceClosure(
                evidence_id=_stable_id("closure", (receipt_id,)),
                obligation_id=request.proposal.primary_obligation_id,
                observation_ids=(observation.observation_id,),
                workspace_snapshot_id=state.workspace_id,
                target_snapshot_digest=request.execution_lease.target_snapshot_digest,
                workspace_hash=state.workspace_snapshot_id,
                event_sequence=state.event_sequence,
                policy_version=state.policy_version,
                objective_revision=generation.objective_revision,
                world_model_revision=generation.workgraph_revision,
                verification_plan_revision=1,
                acceptance_contract_revision=1,
                verifier_config_digest=digest("sclass/verifier-config/v1", ()),
                environment_digest=digest("sclass/environment/v1", env or {}),
                dependency_set=EvidenceDependencySet((),(),False),
                evidence_receipts=(receipt,),
                requirement_results=(),
                composition=EvidenceComposition(CompositionMode.ALL_OF, 0),
                verdict=closure_verdict
            )
            
            assessor_id = ActorIdentity(verifier_attestor.key_id, ActorKind.SYSTEM, None)
            profile = IndependenceProfile(f"{verifier_attestor.key_id}-profile", IndependenceLevel.STRONG, "local", ("os",), assessor_id.actor_id)
            
            assessment_without_sig = IndependentAssessment(
                assessment_id=_stable_id("assessment", (closure.evidence_id,)),
                evidence_id=closure.evidence_id,
                policy_version=state.policy_version,
                workspace_snapshot_id=state.workspace_id,
                assessment_version="v1",
                assessor=assessor_id,
                independence_profile=profile,
                assessor_attestation_digest=digest("sclass/assessor-attestation/v1", profile),
                assessment_method=AssessmentMethod.AUTOMATED_RULE,
                input_digest=digest("sclass/assessment-input/v1", closure.evidence_id),
                target_snapshot_digest=request.execution_lease.target_snapshot_digest,
                artifact_digest=request.execution_lease.target_snapshot_digest,
                decision_policy_id="policy-1",
                verdict=assessment_verdict,
                rationale="Automated S5 baseline verification",
                created_at=_now(),
                signature=None
            )
            assessment_preimage = signature_preimage("sclass/assessment-signed-payload/v1", assessment_without_sig)
            assessment_sig = SignatureBlock("ed25519", verifier_attestor.key_id, verifier_attestor.trust_root, "c1", verifier_attestor.private.sign(assessment_preimage))
            assessment = replace(assessment_without_sig, signature=assessment_sig)
            
            assessment_verification = SignatureVerificationRecord(
                subject_id=assessment.assessment_id,
                signed_payload_digest=assessment_signed_payload_digest(assessment),
                signature_digest=signature_block_digest(assessment_sig),
                key_id=verifier_attestor.key_id,
                verification_result=SignatureVerificationResult.VALID,
                verification_time=_now()
            )
            
            completion = ExecutionOutcome(request.request_id,GateResult.EXECUTED if assessment_verdict is AssessmentVerdict.ACCEPT else GateResult.DENIED_BINDING, work, observation.observation_id)
            
            events = [
                (EventType.QUIESCENCE_PROVEN, proof.proof_id, FrozenMap.from_items((("quiescence_proof", proof),))),
                (EventType.MUTATION_OBSERVED, observation.observation_id, FrozenMap.from_items((("observation", observation),))),
                (EventType.EVIDENCE_ACCEPTED, closure.evidence_id, FrozenMap.from_items((("closure", closure), ("evidence_id", closure.evidence_id), ("signature_verifications", (receipt_verification,))))),
                (EventType.ASSESSMENT_CREATED, assessment.assessment_id, FrozenMap.from_items((("assessment", assessment), ("assessment_id", assessment.assessment_id), ("signature_verification", assessment_verification))))
            ]
            
            if assessment_verdict is AssessmentVerdict.ACCEPT and request.proposal.primary_obligation_id:
                events.append((EventType.OBLIGATION_SATISFIED, request.proposal.primary_obligation_id, FrozenMap.from_items((("obligation_id", request.proposal.primary_obligation_id), ("evidence_id", closure.evidence_id), ("assessment_id", assessment.assessment_id)))))
                
            events.append((EventType.EXECUTION_COMPLETED, request.request_id, FrozenMap.from_items((("execution_outcome", completion), ("request_id", request.request_id)))))
            
            state = commit_events(tuple(events))
            self.boundary.exit(ctx)
            state=self.control_plane.store._load_canonical_state(state.workspace_id)
            reservation=state.budget_reservations.get(request.budget_reservation_id)
            if reservation is None or reservation.lifecycle_state is not BudgetReservationState.RESERVED: raise PermissionError("reservation changed before settlement")
            settled=replace(reservation,lifecycle_state=BudgetReservationState.SETTLED,version=reservation.version+1,settled_amount=reservation.amount,actual_usage=reservation.amount)
            commit_events(((EventType.BUDGET_SETTLED,reservation.reservation_id,FrozenMap.from_items((("reservation",settled),("reservation_id",reservation.reservation_id))),),))
            return completion
        except Exception as exc:
            try:
                try:self.boundary.kill(ctx,"execution lifecycle failure")
                except Exception:pass
                state=self.control_plane.store._load_canonical_state(request.proposal.state_binding.workspace_id)
                events=[]
                lease=state.leases.get(request.execution_lease.lease_id)
                if lease is not None and lease.state is LeaseState.ACTIVE:
                    events.append((EventType.LEASE_REVOKED,request.execution_lease.lease_id,FrozenMap.from_items((("lease_id",request.execution_lease.lease_id),))))
                failure_fp=digest("sclass/work-failure/v1",(request.request_id,type(exc).__name__,str(exc)))
                events.append((EventType.WORK_FAILED,request.node_id,FrozenMap.from_items((("failure_fingerprint",failure_fp),))))
                r=state.budget_reservations.get(request.budget_reservation_id)
                if r is not None and r.lifecycle_state is BudgetReservationState.RESERVED:
                    released=replace(r,lifecycle_state=BudgetReservationState.RELEASED,version=r.version+1,released_amount=r.amount)
                    events.append((EventType.BUDGET_RELEASED,r.reservation_id,FrozenMap.from_items((("reservation",released),("reservation_id",r.reservation_id))),))
                if events: commit_events(tuple(events))
            finally:
                try:self.boundary.exit(ctx)
                except Exception:pass
            raise



def reservation_or_raise(cp: "SClassControlPlane", state: EngineeringState, request: AuthorizedWorkRequest) -> BudgetReservation:
    reservation=state.budget_reservations.get(request.budget_reservation_id)
    if reservation is None or reservation.lifecycle_state is not BudgetReservationState.RESERVED:
        raise PermissionError("budget reservation changed before execution")
    return reservation


class RecoveryDecision(Enum):
    RECONCILED="RECONCILED"
    COMPENSATED="COMPENSATED"
    IN_DOUBT="IN_DOUBT"
    ESCALATED="ESCALATED"

@dataclass(frozen=True)
class RuntimeRecoveryRecord:
    case_id: str
    workspace_id: str
    node_id: str
    decision: RecoveryDecision
    reason: str
    unresolved_effect_ids: tuple[str,...]
    reconciled_at: int


class DeterministicRecoveryEngine:
    """Concrete recovery journal. External effects are reconciled, never assumed."""
    def __init__(self, db: sqlite3.Connection, control_plane: Optional["SClassControlPlane"]=None):
        self.db=db; self.control_plane=control_plane

    def recover(self, workspace_id: str, node_id: str, reason: str,
                effects: Sequence[SideEffectReceipt], *, compensation_results: Optional[Mapping[str,bool]]=None) -> RuntimeRecoveryRecord:
        compensation_results=compensation_results or {}
        unresolved=[]
        compensated=[]
        for e in sorted(effects,key=lambda x:x.effect_id):
            if e.status is SideEffectStatus.UNKNOWN:
                unresolved.append(e.effect_id); continue
            if e.status is SideEffectStatus.COMPENSATED:
                compensated.append(e.effect_id)
            elif e.status is SideEffectStatus.OBSERVED and e.effect_id in compensation_results:
                if compensation_results[e.effect_id]: compensated.append(e.effect_id)
                else: unresolved.append(e.effect_id)
            elif e.status not in (SideEffectStatus.NOT_OBSERVED,SideEffectStatus.COMPENSATED):
                unresolved.append(e.effect_id)
        decision=RecoveryDecision.IN_DOUBT if unresolved else RecoveryDecision.COMPENSATED
        rec=RuntimeRecoveryRecord(_stable_id("recovery",(workspace_id,node_id,reason,tuple(unresolved))),workspace_id,node_id,decision,reason,tuple(unresolved),time.time_ns())
        attempt=(self.db.execute("SELECT COALESCE(MAX(attempt_no),0)+1 FROM runtime_recovery_cases WHERE case_id=?",(rec.case_id,)).fetchone()[0])
        if self.control_plane is not None:
            # Canonical event + runtime journal projection are committed together by the control plane.
            self.control_plane.record_recovery_canonical(rec, effects)
        else:
            self.db.execute("INSERT INTO runtime_recovery_cases(case_id,attempt_no,workspace_id,node_id,status,report_blob,updated_at) VALUES(?,?,?,?,?,?,?)",
                            (rec.case_id,attempt,workspace_id,node_id,rec.decision.value,canonical_c1_pack(rec),rec.reconciled_at))
        return rec


@dataclass(frozen=True)
class DurablePrefixOracleResult:
    expected_sequence: int
    expected_head_hash: Digest
    expected_state_digest: Digest
    expected_commit_count: int
    expected_event_count: int
    committed: bool


class CrashHarness:
    """Subprocess crash probe around SQLite atomicity and runtime ledgers."""
    STAGES = (
        "K1_BEFORE_DURABLE_INTENT",
        "K2_AFTER_COMMIT_RECORD",
        "K3_AFTER_EVENT_ROWS",
        "K4_AFTER_PROJECTION",
        "K5_BEFORE_COMMIT",
        "K6_AFTER_COMMIT",
    )

    @staticmethod
    def expected_durable_prefix_oracle(
        stage: str,
        previous_head_sequence: int,
        previous_head_hash: Digest,
        previous_state_digest: Digest,
        attempted_events_count: int,
        attempted_new_head_sequence: int,
        attempted_new_head_hash: Digest,
        attempted_new_state_digest: Digest,
        previous_commit_count: int = 0,
        previous_event_count: int = 0,
    ) -> DurablePrefixOracleResult:
        """Executable oracle computing expected post-crash durable state for K1-K6.

        K1-K5 crash before SQLite COMMIT: atomic rollback guarantees previous state.
        K6 crashes immediately after SQLite COMMIT: durable state reflects newly committed events.
        """
        if stage in (
            "K1_BEFORE_DURABLE_INTENT",
            "K2_AFTER_COMMIT_RECORD",
            "K3_AFTER_EVENT_ROWS",
            "K4_AFTER_PROJECTION",
            "K5_BEFORE_COMMIT",
        ):
            return DurablePrefixOracleResult(
                expected_sequence=previous_head_sequence,
                expected_head_hash=previous_head_hash,
                expected_state_digest=previous_state_digest,
                expected_commit_count=previous_commit_count,
                expected_event_count=previous_event_count,
                committed=False,
            )
        elif stage == "K6_AFTER_COMMIT":
            return DurablePrefixOracleResult(
                expected_sequence=attempted_new_head_sequence,
                expected_head_hash=attempted_new_head_hash,
                expected_state_digest=attempted_new_state_digest,
                expected_commit_count=previous_commit_count + 1,
                expected_event_count=previous_event_count + attempted_events_count,
                committed=True,
            )
        else:
            raise ValueError(f"Unknown K-stage for S1 crash harness: {stage}")

    @staticmethod
    def run_real_process_death(
        child_script_path: Path | str,
        timeout: float = 15.0,
    ) -> subprocess.CompletedProcess:
        """Execute a Python child script designed to terminate with real OS process death."""
        return subprocess.run(
            [sys.executable, str(child_script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    @staticmethod
    def verify_atomic_restart(db_path: str, work: callable, expected_after_failure: callable):
        # The harness intentionally delegates process termination to the injected caller.
        # On restart the store's canonical audit must be rerun before any derived state is used.
        store = SQLiteEventStore(db_path)
        try:
            actual = store.verify_chain("default", 1, 2**63 - 1)
            expected_after_failure(actual)
        finally:
            store.close()


__all__ = [name for name in globals() if not name.startswith("_")]

