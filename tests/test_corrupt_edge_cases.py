import os
import sys
import time
import json
import pytest
from file_lock import FileLock, NativeLock, _process_exists

def test_corrupt_json_stale(tmp_path):
    lock_file = str(tmp_path / "corrupt_stale.lock")
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write('{"status": "active", "pid": ')
    
    # Backdate mtime beyond stale_ttl
    old = time.time() - 100.0
    os.utime(lock_file, (old, old))

    # Should recover from stale corrupt file
    with FileLock(lock_file, timeout=1.0, stale_ttl=2.0):
        assert os.path.exists(lock_file)

def test_empty_lock_file_reclamation(tmp_path):
    lock_file = str(tmp_path / "empty.lock")
    with open(lock_file, "w", encoding="utf-8") as f:
        pass # 0 bytes
    
    old = time.time() - 10.0
    os.utime(lock_file, (old, old))

    # Should reclaim empty lock file older than 0.5s
    with FileLock(lock_file, timeout=1.0, stale_ttl=2.0):
        assert os.path.exists(lock_file)

def test_negative_pid(tmp_path):
    lock_file = str(tmp_path / "neg_pid.lock")
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({"status": "active", "pid": -5}))
    
    # Negative PID should be recognized as dead process and reclaimed
    with FileLock(lock_file, timeout=1.0, stale_ttl=2.0):
        assert os.path.exists(lock_file)

def test_unparseable_pid(tmp_path):
    lock_file = str(tmp_path / "str_pid.lock")
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({"status": "active", "pid": "not-a-number"}))
    
    old = time.time() - 100.0
    os.utime(lock_file, (old, old))

    # Unparseable PID older than stale_ttl should be reclaimed
    with FileLock(lock_file, timeout=1.0, stale_ttl=2.0):
        assert os.path.exists(lock_file)

def test_zero_pid(tmp_path):
    lock_file = str(tmp_path / "zero_pid.lock")
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({"status": "active", "pid": 0}))

    # PID 0 should be treated as non-existent process and reclaimed
    with FileLock(lock_file, timeout=1.0, stale_ttl=2.0):
        assert os.path.exists(lock_file)
