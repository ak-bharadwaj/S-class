"""
Migration 002: Execution Identity support.
"""
import sqlite3

def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS execution_identities (
            identity_hash TEXT PRIMARY KEY,
            executable_path TEXT NOT NULL,
            executable_hash TEXT NOT NULL,
            pid INTEGER,
            parent_pid INTEGER,
            execution_mode TEXT NOT NULL,
            identity_state TEXT NOT NULL,
            created_at TEXT NOT NULL,
            identity_json TEXT NOT NULL
        )
        """
    )
