"""
S-Class Storage: Schema Migrations Engine.
Manages versioned database migrations for zero-data-loss upgrades.
"""

from __future__ import annotations
import sqlite3
import importlib
from typing import List


MIGRATIONS = [
    "001_initial",
    "002_execution_identity",
    "003_claim_scope",
    "004_checkpoint",
]


def apply_migrations(conn: sqlite3.Connection) -> int:
    """Applies all pending migrations to the SQLite database."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    conn.commit()

    applied = {row[0] for row in conn.execute("SELECT version FROM _schema_migrations").fetchall()}
    count = 0

    for mig_name in MIGRATIONS:
        if mig_name not in applied:
            mod = importlib.import_module(f"sclass.storage.migrations.{mig_name}")
            mod.upgrade(conn)
            conn.execute(
                "INSERT INTO _schema_migrations (version, applied_at) VALUES (?, datetime('now'))",
                (mig_name,),
            )
            conn.commit()
            count += 1

    return count
