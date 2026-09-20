"""
S-Class Recovery: Canonical Recovery State Authority and Persistence.
Integrates recovery state with the authoritative S-Class SQLite state store (StateRepository / project.db).
Maintains EventJournal as append-only audit evidence for all recovery transitions.
Eliminates recoveries.jsonl as an independent competing source of truth.

Enforces:
1. Canonical recovery state authority in SQLite.
2. Durable, fail-closed persistence on storage errors.
3. Append-only CloudEvents audit trail in EventJournal.
"""

from __future__ import annotations
import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from sclass.storage.paths import WorkspacePaths
from sclass.storage.locks import WorkspaceLock
from sclass.state.tasks import StateRepository
from sclass.state.events import EventJournal
from sclass.core.errors import RecoveryPersistenceError, StorageError
from sclass.recovery.models import RecoveryRecord, RecoveryState


class RecoveryPersistence:
    """Manages authoritative recovery state records via StateRepository and EventJournal."""

    def __init__(self, workspace_dir: str, repository: Optional[StateRepository] = None):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.paths = WorkspacePaths(self.workspace_dir)
        self.paths.ensure_directories()
        self.repository = repository or StateRepository(self.workspace_dir)
        self.journal = EventJournal(self.workspace_dir)

    def save_recovery(self, record: RecoveryRecord) -> None:
        """
        Durably commits a recovery record to the authoritative SQLite store and mirrors to EventJournal.
        Fails closed on storage or journal errors.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        record.updated_at = now_iso

        with WorkspaceLock(self.workspace_dir, lock_name="recovery"):
            try:
                self.repository.save_recovery(record)
            except (StorageError, sqlite3.Error, Exception) as e:
                raise RecoveryPersistenceError(
                    f"Failed to persist recovery record '{record.recovery_id}' to authoritative state store: {e}"
                ) from e

        # Mirror transition event to EventJournal as append-only audit evidence
        try:
            self.journal.append(
                event_type="sclass.recovery.transition",
                subject=f"recovery:{record.recovery_id}",
                data={
                    "recovery_id": record.recovery_id,
                    "task_id": record.task_id,
                    "affected_obligation_id": record.affected_obligation_id,
                    "state": record.current_state.value if isinstance(record.current_state, RecoveryState) else str(record.current_state),
                    "attempt_number": record.attempt_number,
                    "parent_event_id": record.parent_event_id,
                    "affected_claim_id": record.affected_claim_id,
                    "affected_evidence_id": record.affected_evidence_id,
                },
            )
        except Exception as e:
            raise RecoveryPersistenceError(f"Failed to mirror recovery event to EventJournal: {e}") from e

    def load_recovery(self, recovery_id: str) -> Optional[RecoveryRecord]:
        """
        Reconstructs the authoritative RecoveryRecord for recovery_id from SQLite storage.
        Fails closed with RecoveryPersistenceError if storage is corrupt or unreadable.
        """
        with WorkspaceLock(self.workspace_dir, lock_name="recovery"):
            try:
                return self.repository.get_recovery(recovery_id)
            except (StorageError, sqlite3.Error, Exception) as e:
                raise RecoveryPersistenceError(
                    f"Authoritative recovery store is unreadable or corrupt for '{recovery_id}': {e}"
                ) from e

    def load_all(self) -> Dict[str, RecoveryRecord]:
        """
        Loads all recovery records from the authoritative SQLite state store.
        Fails closed with RecoveryPersistenceError if store is corrupt or unreadable.
        """
        with WorkspaceLock(self.workspace_dir, lock_name="recovery"):
            try:
                records = self.repository.list_recoveries()
                return {r.recovery_id: r for r in records}
            except (StorageError, sqlite3.Error, Exception) as e:
                raise RecoveryPersistenceError(
                    f"Authoritative recovery store is unreadable or corrupt: {e}"
                ) from e
