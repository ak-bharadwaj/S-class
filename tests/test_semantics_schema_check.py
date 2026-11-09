"""Semantics Schema Check Test (Task R4 / Round 11).

Asserts:
1. SQLiteEventStore with store_meta schema_version=1:
   - Opens successfully
   - migrate(workspace_id, 3) brings it to 3 atomically and idempotently
2. SQLiteEventStore with store_meta schema_version=2:
   - Opens successfully
   - migrate(workspace_id, 3) brings it to 3 atomically and idempotently
3. SQLiteEventStore with store_meta schema_version=4:
   - Opening is rejected with ValueError
"""

import sys
import sqlite3
import pytest
from pathlib import Path

# Add 10-CONFORMANCE to sys.path
CONFORMANCE_DIR = Path(__file__).resolve().parent.parent / "10-CONFORMANCE"
if str(CONFORMANCE_DIR) not in sys.path:
    sys.path.insert(0, str(CONFORMANCE_DIR))

from sclass_semantics_v6_0_1 import SQLiteEventStore, StateLoadStatus


def test_schema_version_1_migrates_to_3_atomically_and_idempotently(tmp_path):
    db_path = str(tmp_path / "events_v1.db")

    # Seed database with schema_version = 1
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO store_meta (key, value) VALUES ('schema_version', '1')")

    # Open SQLiteEventStore
    store = SQLiteEventStore(db_path)
    try:
        # Check that initial schema_version is 1
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT value FROM store_meta WHERE key='schema_version'").fetchone()
            assert row is not None
            assert row[0] == "1"

        # Migrate to schema_version 3
        status = store.migrate("test-workspace", 3)
        assert status == StateLoadStatus.FOUND

        # Verify atomic update to version 3
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT value FROM store_meta WHERE key='schema_version'").fetchone()
            assert row is not None
            assert row[0] == "3"

        # Verify idempotency: calling migrate again produces the same result
        status_again = store.migrate("test-workspace", 3)
        assert status_again == StateLoadStatus.FOUND

        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT value FROM store_meta WHERE key='schema_version'").fetchone()
            assert row is not None
            assert row[0] == "3"
    finally:
        store.close()


def test_schema_version_2_migrates_to_3_atomically_and_idempotently(tmp_path):
    db_path = str(tmp_path / "events_v2.db")

    # Seed database with schema_version = 2
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO store_meta (key, value) VALUES ('schema_version', '2')")

    # Open SQLiteEventStore
    store = SQLiteEventStore(db_path)
    try:
        # Check that initial schema_version is 2
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT value FROM store_meta WHERE key='schema_version'").fetchone()
            assert row is not None
            assert row[0] == "2"

        # Migrate to schema_version 3
        status = store.migrate("test-workspace", 3)
        assert status == StateLoadStatus.FOUND

        # Verify atomic update to version 3
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT value FROM store_meta WHERE key='schema_version'").fetchone()
            assert row is not None
            assert row[0] == "3"

        # Verify idempotency
        status_again = store.migrate("test-workspace", 3)
        assert status_again == StateLoadStatus.FOUND

        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT value FROM store_meta WHERE key='schema_version'").fetchone()
            assert row is not None
            assert row[0] == "3"
    finally:
        store.close()


def test_schema_version_4_rejected_at_open(tmp_path):
    db_path = str(tmp_path / "events_v4.db")

    # Seed database with schema_version = 4
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO store_meta (key, value) VALUES ('schema_version', '4')")

    # Attempting to open SQLiteEventStore with schema_version 4 must raise ValueError
    with pytest.raises(ValueError, match="unsupported SQLiteEventStore schema version: 4"):
        SQLiteEventStore(db_path)
