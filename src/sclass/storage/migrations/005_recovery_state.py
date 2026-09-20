"""
Migration 005: Recovery cycles schema for D9 recovery state.
"""
import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recovery_records (
            recovery_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            affected_obligation_id TEXT NOT NULL,
            current_state TEXT NOT NULL,
            attempt_number INTEGER NOT NULL,
            max_attempts INTEGER NOT NULL,
            failure_classification TEXT NOT NULL,
            reason TEXT NOT NULL,
            affected_claim_id TEXT,
            affected_evidence_id TEXT,
            project_state_ref TEXT NOT NULL DEFAULT '',
            parent_event_id TEXT,
            staleness_cause TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            current_repair_obligation_json TEXT,
            resulting_verification_json TEXT,
            history_json TEXT NOT NULL DEFAULT '[]',
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_recovery_records_task
        ON recovery_records(task_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_recovery_records_obligation
        ON recovery_records(affected_obligation_id)
        """
    )
