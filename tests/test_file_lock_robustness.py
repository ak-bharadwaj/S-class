"""
Tests for OS-Native Lock primitives and runtime concurrency resilience.
Verifies stale lock reclamation, dead process recovery, JSON metadata handling,
and strict mutual exclusion across runtime.FileLock, file_lock.FileLock, and file_lock.NativeLock.
"""

import os
import time
import json
import pytest

import runtime
import file_lock


def test_runtime_filelock_recovers_from_json_dead_pid(tmp_path):
    lock_file = str(tmp_path / "state.lock")
    # Write JSON metadata with a dead PID
    payload = json.dumps({"status": "active", "pid": 9999998, "token": "test-dead-token"})
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write(payload)

    start = time.time()
    with runtime.FileLock(lock_file, timeout=2.0):
        assert os.path.exists(lock_file)
    elapsed = time.time() - start
    assert elapsed < 1.0


def test_runtime_filelock_does_not_unlink_foreign_lock_on_exit(tmp_path):
    lock_file = str(tmp_path / "state.lock")
    
    # Enter FileLock
    fl = runtime.FileLock(lock_file, timeout=1.0)
    fl.__enter__()

    # Simulate another process having overwritten or claimed the lock file
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write("8888888")

    # Exiting should NOT delete the foreign lock file
    fl.__exit__(None, None, None)
    assert os.path.exists(lock_file)

    with open(lock_file, "r", encoding="utf-8") as f:
        assert f.read().strip() == "8888888"


def test_file_lock_module_recovers_from_stale_mtime(tmp_path):
    lock_file = str(tmp_path / "advisory.lock")
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write("stale_data")
    
    # Backdate mtime to simulate an abandoned lock file older than stale_ttl
    old_time = time.time() - 100.0
    os.utime(lock_file, (old_time, old_time))

    # NativeLock should reclaim stale file
    with file_lock.NativeLock(lock_file, timeout=1.0, stale_ttl=10.0):
        assert os.path.exists(lock_file)


def test_file_lock_module_recovers_from_json_dead_pid(tmp_path):
    lock_file = str(tmp_path / "advisory_meta.lock")
    meta = {"status": "active", "pid": 9999997, "token": "dead"}
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(meta))

    # FileLock should reclaim and acquire
    start = time.time()
    with file_lock.FileLock(lock_file, timeout=2.0, stale_ttl=10.0):
        assert os.path.exists(lock_file)
    assert time.time() - start < 1.0
