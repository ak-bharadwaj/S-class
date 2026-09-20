"""
S-Class Recovery: Durable, Fail-Closed Recovery Persistence.
Persists recovery state records to .sclass/trust/recoveries.jsonl and mirrors to EventJournal.
Enforces:
1. Malformed or corrupt recovery persistence strictly fails closed.
2. Atomicity via WorkspaceLock and os.fsync().
3. Idempotency against duplicate transitions.
"""

from __future__ import annotations
import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from sclass.storage.paths import WorkspacePaths
from sclass.storage.locks import WorkspaceLock
from sclass.state.events import EventJournal
from sclass.core.errors import RecoveryPersistenceError
from sclass.recovery.models import RecoveryRecord, RecoveryState


class RecoveryPersistence:
    """Manages durable recovery state records with fail-closed corruption detection."""

    def __init__(self, workspace_dir: str):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.paths = WorkspacePaths(self.workspace_dir)
        self.paths.ensure_directories()
        self.recoveries_file = os.path.join(self.paths.trust_dir, "recoveries.jsonl")
        self.journal = EventJournal(self.workspace_dir)

    def save_recovery(self, record: RecoveryRecord) -> None:
        """
        Durably commits a recovery record to recoveries.jsonl and EventJournal.
        Fails closed on I/O error.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        record.updated_at = now_iso

        line_payload = json.dumps({
            "record_type": "sclass.recovery.record",
            "recovery_id": record.recovery_id,
            "task_id": record.task_id,
            "affected_obligation_id": record.affected_obligation_id,
            "current_state": record.current_state.value if isinstance(record.current_state, RecoveryState) else str(record.current_state),
            "attempt_number": record.attempt_number,
            "max_attempts": record.max_attempts,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "data": record.to_dict(),
        }, ensure_ascii=False) + "\n"

        with WorkspaceLock(self.workspace_dir, lock_name="recovery"):
            try:
                with open(self.recoveries_file, "a", encoding="utf-8") as f:
                    f.write(line_payload)
                    f.flush()
                    os.fsync(f.fileno())
            except Exception as e:
                raise RecoveryPersistenceError(f"Failed to persist recovery record to trust store: {e}") from e

        # Mirror transition event to EventJournal
        try:
            self.journal.append(
                event_type="sclass.recovery.transition",
                subject=f"recovery:{record.recovery_id}",
                data={
                    "recovery_id": record.recovery_id,
                    "task_id": record.task_id,
                    "state": record.current_state.value if isinstance(record.current_state, RecoveryState) else str(record.current_state),
                    "attempt_number": record.attempt_number,
                },
            )
        except Exception as e:
            raise RecoveryPersistenceError(f"Failed to mirror recovery event to EventJournal: {e}") from e

    def load_recovery(self, recovery_id: str) -> Optional[RecoveryRecord]:
        """
        Reconstructs the authoritative RecoveryRecord for recovery_id from persistent storage.
        Fails closed if the storage is corrupt or malformed.
        """
        all_records = self.load_all()
        return all_records.get(recovery_id)

    def load_all(self) -> Dict[str, RecoveryRecord]:
        """
        Loads all latest recovery records from recoveries.jsonl.
        Fails closed with RecoveryPersistenceError if file is corrupt, unreadable, or malformed.
        """
        if not os.path.exists(self.recoveries_file):
            return {}

        records: Dict[str, RecoveryRecord] = {}
        with WorkspaceLock(self.workspace_dir, lock_name="recovery"):
            try:
                with open(self.recoveries_file, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, start=1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            item = json.loads(line)
                        except Exception as je:
                            raise RecoveryPersistenceError(
                                f"Corrupt JSON in recovery store '{self.recoveries_file}' at line {line_num}: {je}"
                            ) from je

                        if not isinstance(item, dict) or "data" not in item:
                            raise RecoveryPersistenceError(
                                f"Malformed recovery record in '{self.recoveries_file}' at line {line_num}: missing 'data'."
                            )

                        data = item["data"]
                        if not isinstance(data, dict) or "recovery_id" not in data or "current_state" not in data:
                            raise RecoveryPersistenceError(
                                f"Malformed recovery data in '{self.recoveries_file}' at line {line_num}."
                            )

                        rec = RecoveryRecord.from_dict(data)
                        records[rec.recovery_id] = rec

            except RecoveryPersistenceError:
                raise
            except Exception as e:
                raise RecoveryPersistenceError(f"Recovery store is unreadable or corrupt: {e}") from e

        return records
