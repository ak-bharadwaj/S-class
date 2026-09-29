"""
Standardized atomic transaction boundary for S-Class SQLite storage.
"""
import sqlite3
from contextlib import contextmanager

@contextmanager
def managed_transaction(conn: sqlite3.Connection):
    """
    Context manager providing fail-closed atomic transaction handling.
    Automatically rolls back on any exception and re-raises.
    """
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
