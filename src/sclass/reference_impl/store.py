"""Non-authoritative reference scaffold SQLite store with safe schema policy, URI validation, and fault injection.

Provided for development, testing, and reference execution; not an authoritative
production execution runtime.
"""
from __future__ import annotations

import sqlite3
from typing import Mapping, Optional, Sequence

from sclass_semantics_v6_0_1 import (
    AppendResult,
    CommitRecord,
    CommitState,
    Digest,
    EngineeringState,
    EventType,
    GENESIS_EVENT_HASH,
    SQLiteEventStore as _BaseSQLiteEventStore,
    StateLoadStatus,
    canonical_c1_pack,
    commit_record_digest,
    engineering_state_digest,
)


class ReferenceSQLiteStore(_BaseSQLiteEventStore):
    """Non-authoritative reference scaffold SQLite store.

    Relocates the accepted SQLite URI validation, crash-stage aliases,
    event-triggered fault points, and safe schema migration extensions outside frozen files.
    """

    STORE_SCHEMA_VERSION = 3

    def __init__(self, path: str, fault_injector=None):
        self._fault_injector = fault_injector
        use_uri = path.startswith("file:")

        # A6.4: SQLite URI acceptance must be restricted to file: paths.
        if ":" in path and not use_uri:
            scheme = path.split(":", 1)[0]
            if len(scheme) > 1:  # Not a Windows single-letter drive like C:\
                raise ValueError(f"unsupported SQLite URI scheme: only file: paths are accepted ({path})")

        self._db = sqlite3.connect(path, uri=use_uri, isolation_level=None, check_same_thread=False, timeout=30.0)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("PRAGMA foreign_keys=ON")

        # A6.3: Safe schema policy
        table_exists = (
            self._db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='store_meta'"
            ).fetchone()
            is not None
        )

        self._db.execute("""CREATE TABLE IF NOT EXISTS store_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )""")

        row = self._db.execute("SELECT value FROM store_meta WHERE key='schema_version'").fetchone()
        if row is None:
            if table_exists:
                raise ValueError("missing schema version in store_meta")
            self._db.execute(
                "INSERT INTO store_meta(key,value) VALUES('schema_version',?)",
                (str(self.STORE_SCHEMA_VERSION),),
            )
        else:
            try:
                ver = int(row[0])
            except (ValueError, TypeError):
                raise ValueError(f"invalid non-integer schema version: {row[0]}")
            if ver > self.STORE_SCHEMA_VERSION or ver <= 0:
                raise ValueError(f"unsupported SQLiteEventStore schema version: {row[0]}")

        self._db.execute("""CREATE TABLE IF NOT EXISTS canonical_commits (
            commit_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            record_blob BLOB NOT NULL,
            commit_digest TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state='COMMITTED'),
            event_sequence_start INTEGER NOT NULL,
            event_sequence_end INTEGER NOT NULL,
            resulting_state_digest TEXT NOT NULL,
            UNIQUE(workspace_id, event_sequence_start, event_sequence_end)
        )""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS canonical_events (
            workspace_id TEXT NOT NULL,
            event_sequence INTEGER NOT NULL,
            event_id TEXT NOT NULL,
            event_hash TEXT NOT NULL PRIMARY KEY,
            event_blob BLOB NOT NULL,
            commit_id TEXT NOT NULL,
            FOREIGN KEY(commit_id) REFERENCES canonical_commits(commit_id),
            UNIQUE(workspace_id,event_sequence),
            UNIQUE(workspace_id,event_id)
        )""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS canonical_projection (
            workspace_id TEXT PRIMARY KEY,
            event_sequence INTEGER NOT NULL,
            state_revision TEXT NOT NULL,
            state_digest TEXT NOT NULL,
            state_blob BLOB NOT NULL,
            event_head_hash TEXT NOT NULL,
            commit_id TEXT NOT NULL,
            FOREIGN KEY(commit_id) REFERENCES canonical_commits(commit_id)
        )""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS checkpoints (
            checkpoint_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            event_sequence INTEGER NOT NULL,
            event_head_hash TEXT NOT NULL,
            state_digest TEXT NOT NULL,
            commit_id TEXT NOT NULL,
            reducer_version TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
            state_blob BLOB NOT NULL,
            FOREIGN KEY(commit_id) REFERENCES canonical_commits(commit_id)
        )""")

    def _fault(self, stage: str) -> None:
        """A6.4: Fault injection must be inert when fault_injector is None."""
        if self._fault_injector is None:
            return
        self._fault_injector(stage)
        alias_map = {
            "K1_BEFORE_DURABLE_INTENT": "K1_PRE_INTENT",
            "K2_AFTER_COMMIT_RECORD": "K2_POST_INTENT",
            "K3_AFTER_EVENT_ROWS": "K3_PRE_ADMISSION",
            "K4_AFTER_PROJECTION": "K4_POST_ADMISSION",
            "K5_BEFORE_COMMIT": "K5_PRE_COMMIT",
            "K6_AFTER_COMMIT": "K6_POST_COMMIT",
            "K7_DURING_CHECKPOINT_WRITE": "K7_PRE_BOUNDARY",
            "K7_CHECKPOINT_WRITE": "K7_PRE_BOUNDARY",
            "K8_DURING_VERIFICATION": "K8_IN_BOUNDARY",
            "K9_AFTER_RECEIPT_SIGNED": "K9_POST_EXECUTION",
            "K10_DURING_RECONCILIATION": "K10_PRE_EVIDENCE",
            "K11_DURING_HANDOFF": "K11_PRE_SETTLE",
            "K12_DURING_GENERATION_ADVANCE": "K12_POST_SETTLE",
        }
        mapped = alias_map.get(stage)
        if mapped is not None:
            self._fault_injector(mapped)

    def _append_batch_in_transaction(self, events, commit, expected_head_hash=GENESIS_EVENT_HASH):
        """Append one canonical commit with K8-K12 crash injection points while caller owns transaction."""
        res, head = super()._append_batch_in_transaction(events, commit, expected_head_hash)
        if self._fault_injector is not None and res is AppendResult.APPENDED:
            event_types_in_batch = frozenset(getattr(e, "event_type", None) for e in events)
            reasons_in_batch = frozenset(
                e.payload.get("reason") for e in events if hasattr(e, "payload") and isinstance(e.payload, Mapping)
            )
            if EventType.EVIDENCE_ACCEPTED in event_types_in_batch or "K8_DURING_VERIFICATION" in reasons_in_batch:
                self._fault("K8_DURING_VERIFICATION")
                self._fault("K8_DURING_EVIDENCE_ACCEPTANCE")
            if EventType.ASSESSMENT_CREATED in event_types_in_batch or "K9_AFTER_RECEIPT_SIGNED" in reasons_in_batch:
                self._fault("K9_AFTER_RECEIPT_SIGNED")
                self._fault("K9_AFTER_RECEIPT_BEFORE_COMMIT")
            if (
                EventType.IN_DOUBT_RESOLVED in event_types_in_batch
                or EventType.EXTERNAL_EFFECT_RECONCILED in event_types_in_batch
                or "K10_DURING_RECONCILIATION" in reasons_in_batch
            ):
                self._fault("K10_DURING_RECONCILIATION")
            if EventType.STATE_CHECKPOINTED in event_types_in_batch or "K11_DURING_HANDOFF" in reasons_in_batch:
                self._fault("K11_DURING_HANDOFF")
            if EventType.EXECUTION_STARTED in event_types_in_batch or "K12_DURING_GENERATION_ADVANCE" in reasons_in_batch:
                self._fault("K12_DURING_GENERATION_ADVANCE")
        return res, head

    def checkpoint(self, checkpoint, state):
        """Relocated K7 fault points in checkpoint serialization."""
        self._fault("K7_CHECKPOINT_WRITE")
        self._fault("K7_DURING_CHECKPOINT_WRITE")
        return super().checkpoint(checkpoint, state)

    def migrate(self, workspace_id: str, target_schema_version: int) -> StateLoadStatus:
        """A6.3: Safe schema migration.

        Idempotent: running twice produces the same result.
        Crash-safe: migration runs inside a single immediate transaction.
        Older versions migrated or rejected as unsupported; newer versions rejected.
        """
        if not isinstance(target_schema_version, int) or target_schema_version > self.STORE_SCHEMA_VERSION or target_schema_version <= 0:
            return StateLoadStatus.UNSUPPORTED_SCHEMA

        row = self._db.execute("SELECT value FROM store_meta WHERE key='schema_version'").fetchone()
        if not row:
            return StateLoadStatus.UNSUPPORTED_SCHEMA
        try:
            current = int(row[0])
        except (ValueError, TypeError):
            return StateLoadStatus.UNSUPPORTED_SCHEMA

        if current == target_schema_version:
            return StateLoadStatus.FOUND
        if current > target_schema_version:
            return StateLoadStatus.UNSUPPORTED_SCHEMA

        self._db.execute("BEGIN IMMEDIATE")
        try:
            for version_step in range(current + 1, target_schema_version + 1):
                if self._fault_injector is not None:
                    self._fault_injector("K8_DURING_MIGRATION")
                migration_method = getattr(self, f"_migrate_to_v{version_step}", None)
                if migration_method:
                    migration_method()
            self._db.execute(
                "UPDATE store_meta SET value=? WHERE key='schema_version'",
                (str(target_schema_version),),
            )
            self._db.execute("COMMIT")
            return StateLoadStatus.FOUND
        except Exception:
            try:
                self._db.execute("ROLLBACK")
            except Exception:
                pass
            raise


ReferenceEventStore = ReferenceSQLiteStore

