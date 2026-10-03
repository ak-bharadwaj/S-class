"""
Unit tests for managed SQLite transactions and rollback semantics.
"""
import sqlite3
import pytest
from sclass.kernel_transaction import managed_transaction

def test_successful_transaction_commits():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE kv (k TEXT, v TEXT)")
    with managed_transaction(conn):
        conn.execute("INSERT INTO kv VALUES ('hello', 'world')")
    
    cur = conn.execute("SELECT v FROM kv WHERE k='hello'")
    assert cur.fetchone()[0] == "world"

def test_failed_transaction_rolls_back():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE kv (k TEXT PRIMARY KEY, v TEXT)")
    conn.execute("INSERT INTO kv VALUES ('key1', 'initial')")
    conn.commit()
    
    with pytest.raises(sqlite3.IntegrityError):
        with managed_transaction(conn):
            conn.execute("UPDATE kv SET v='updated' WHERE k='key1'")
            conn.execute("INSERT INTO kv VALUES ('key1', 'duplicate')")
            
    cur = conn.execute("SELECT v FROM kv WHERE k='key1'")
    assert cur.fetchone()[0] == "initial"
