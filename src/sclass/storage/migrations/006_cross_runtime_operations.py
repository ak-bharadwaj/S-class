"""
Migration 006: Schema for cross-runtime operation references.
"""
from __future__ import annotations
import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cross_runtime_operations (
            operation_id TEXT PRIMARY KEY,
            runtime_name TEXT NOT NULL,
            runtime_operation_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            action_id TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            intent_hash TEXT NOT NULL,
            action_hash TEXT NOT NULL,
            replay_class TEXT NOT NULL,
            adapter_version TEXT NOT NULL,
            state TEXT NOT NULL,
            authorization_id TEXT,
            effect_result_json TEXT,
            settlement_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cross_runtime_op_task
        ON cross_runtime_operations(task_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cross_runtime_op_session
        ON cross_runtime_operations(session_id)
        """
    )
