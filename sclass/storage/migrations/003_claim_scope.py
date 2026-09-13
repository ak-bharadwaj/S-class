"""
Migration 003: Claim Scope and Verification Events schema.
"""
import sqlite3

def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS claims (
            claim_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            statement TEXT NOT NULL,
            claim_type TEXT NOT NULL,
            requested_verifier TEXT,
            scope_json TEXT,
            created_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS verification_events (
            event_id TEXT PRIMARY KEY,
            claim_id TEXT NOT NULL,
            receipt_id TEXT NOT NULL,
            receipt_hash TEXT NOT NULL,
            verifier TEXT NOT NULL,
            result TEXT NOT NULL,
            reason TEXT NOT NULL,
            repository_fingerprint TEXT NOT NULL,
            verification_time TEXT NOT NULL,
            metadata_json TEXT NOT NULL
        )
        """
    )
