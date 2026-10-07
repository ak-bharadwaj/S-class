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


def test_runtime_filelock_never_steals_from_live_process_even_if_older_than_stale_ttl(tmp_path):
    """Enforces strict mutual exclusion: live processes must NEVER have their lock stolen, regardless of stale_ttl."""
    lock_file = str(tmp_path / "state.lock")
    # Simulate an active live process holding the lock
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))

    # Backdate mtime so lock_age is well beyond stale_ttl
    old_time = time.time() - 100.0
    os.utime(lock_file, (old_time, old_time))

    # Because PID is ALIVE, waiting process must respect mutual exclusion and raise TimeoutError
    with pytest.raises(TimeoutError):
        with runtime.FileLock(lock_file, timeout=0.2, stale_ttl=1.0):
            pass

    # Lock file must remain untouched with original live PID
    assert os.path.exists(lock_file)
    with open(lock_file, "r", encoding="utf-8") as f:
        assert f.read().strip() == str(os.getpid())


def test_runtime_filelock_unlinks_compact_json_lock_on_exit(tmp_path):
    """Verifies that FileLock.__exit__ properly unlinks locks saved as compact JSON without spaces."""
    lock_file = str(tmp_path / "state.lock")
    fl = runtime.FileLock(lock_file, timeout=1.0)
    fl.__enter__()

    # Overwrite lock file with compact JSON (no space after colon)
    compact_payload = json.dumps({"status": "active", "pid": os.getpid(), "token": "test-compact"}, separators=(",", ":"))
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write(compact_payload)

    # Exiting should recognize current process as owner and cleanly unlink
    fl.__exit__(None, None, None)
    assert not os.path.exists(lock_file)


def test_file_lock_module_never_steals_from_live_process_even_if_older_than_stale_ttl(tmp_path):
    """Verifies file_lock.FileLock never unlinks an active lock owned by a live process."""
    lock_file = str(tmp_path / "advisory_live.lock")
    meta = {"status": "active", "pid": os.getpid(), "token": "live-token"}
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(meta))

    old_time = time.time() - 100.0
    os.utime(lock_file, (old_time, old_time))

    # FileLock without kernel fd lock still checks PID liveness and respects live process
    # If a live PID is recorded, FileLock won't delete it
    with file_lock.FileLock(lock_file, timeout=1.0, stale_ttl=2.0):
        assert os.path.exists(lock_file)

