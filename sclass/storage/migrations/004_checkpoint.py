"""
Migration 004: Project Checkpoints schema for cross-agent handoffs.
"""
import sqlite3

def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS project_checkpoints (
            checkpoint_id TEXT PRIMARY KEY,
            repository_head TEXT NOT NULL,
            working_tree_fingerprint TEXT NOT NULL,
            active_task TEXT,
            next_action TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            checkpoint_json TEXT NOT NULL
        )
        """
    )
