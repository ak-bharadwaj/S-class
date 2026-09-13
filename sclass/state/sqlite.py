"""
S-Class State: SQLite Authoritative Project Database.
"""

from __future__ import annotations
import os
import json
import sqlite3
from typing import Dict, Any, Optional, List

from sclass.storage.paths import WorkspacePaths
from sclass.storage.migrations import apply_migrations
from sclass.core.errors import StorageError


SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    root_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    active_agent TEXT,
    current_goal TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL,
    priority TEXT NOT NULL,
    depends_on_json TEXT NOT NULL DEFAULT '[]',
    assigned_agent TEXT,
    claimed_evidence_id TEXT,
    verified_receipt_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(project_id) REFERENCES projects(project_id)
);

CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    statement TEXT NOT NULL,
    claim_type TEXT NOT NULL,
    verifier TEXT,
    target_files_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
);

CREATE TABLE IF NOT EXISTS verifications (
    verification_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    receipt_id TEXT,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    observed_exit_code INTEGER,
    observed_files_json TEXT NOT NULL DEFAULT '[]',
    passed_tests INTEGER NOT NULL DEFAULT 0,
    failed_tests INTEGER NOT NULL DEFAULT 0,
    verification_time TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(claim_id) REFERENCES claims(claim_id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state);
CREATE INDEX IF NOT EXISTS idx_claims_task ON claims(task_id);
CREATE INDEX IF NOT EXISTS idx_verifications_claim ON verifications(claim_id);
"""


class SQLiteStateStore:
    """Authoritative local relational store for project and task state with schema migrations."""

    def __init__(self, workspace_dir: str):
        self.paths = WorkspacePaths(workspace_dir)
        self.paths.ensure_directories()
        self.db_path = os.path.join(self.paths.state_dir, "project.db")
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Returns a configured SQLite connection in WAL mode."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        """Initializes database tables, verifies schema, and applies versioned migrations."""
        try:
            with self.get_connection() as conn:
                conn.executescript(SCHEMA_V1)
                conn.execute(
                    "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (1, datetime('now'))"
                )
                conn.commit()
                # Run versioned schema migrations
                apply_migrations(conn)
        except sqlite3.Error as e:
            raise StorageError(f"Failed to initialize SQLite state database at {self.db_path}: {e}") from e
