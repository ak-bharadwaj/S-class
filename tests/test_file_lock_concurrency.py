"""
S-Class EOS V11.2 - FileLock Multi-Process Concurrency & Authority Test Suite
Verifies:
1. True cross-process mutual exclusion (active holder blocks with TimeoutError).
2. Process termination / exit releases kernel lock, allowing subsequent process acquisition.
3. Multi-process concurrent acquisition contention and serial correctness.
4. Native fallback mode (when HAS_PORTALOCKER = False) on OS primitives.
5. Config GC race safety (active lock never unlinked, stale unheld lock reclaimed).
"""

import os
import sys
import time
import json
import tempfile
import subprocess
import pytest
from file_lock import FileLock, HAS_PORTALOCKER
import file_lock
from config_gc import run_gc


def _worker_hold_lock(lock_path: str, hold_seconds: float, ready_file: str, result_file: str):
    """Worker function executed in separate process to hold lock for a duration."""
    try:
        with FileLock(lock_path, timeout=5.0):
            # Write ready marker to signal parent process
            with open(ready_file, "w", encoding="utf-8") as f:
                f.write("READY")
            time.sleep(hold_seconds)
        with open(result_file, "w", encoding="utf-8") as f:
            f.write("OK")
    except Exception as e:
        with open(result_file, "w", encoding="utf-8") as f:
            f.write(f"ERR: {e}")


def test_cross_process_active_holder_blocks():
    """Verifies that an active lock holder in Process A causes Process B to raise TimeoutError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, "state.lock")
        ready_file = os.path.join(tmpdir, "ready.marker")
        result_file = os.path.join(tmpdir, "result.marker")

        # Spawn child process to hold lock for 3 seconds
        cmd = [
            sys.executable, "-c",
            f"from tests.test_file_lock_concurrency import _worker_hold_lock; "
            f"_worker_hold_lock(r'{lock_file}', 2.5, r'{ready_file}', r'{result_file}')"
        ]
        proc = subprocess.Popen(cmd)

        try:
            # Wait for child process to acquire lock
            start = time.time()
            while not os.path.exists(ready_file) and time.time() - start < 5.0:
                time.sleep(0.05)
            assert os.path.exists(ready_file), "Child process failed to signal ready"

            # In main process, attempting to acquire lock with short timeout MUST fail
            with pytest.raises(TimeoutError):
                with FileLock(lock_file, timeout=0.3):
                    pass

        finally:
            proc.wait(timeout=5.0)

        # After child process terminates, main process MUST be able to acquire lock
        with FileLock(lock_file, timeout=2.0):
            pass


def test_cross_process_termination_releases_lock():
    """Verifies that when a process exits/crashes, OS advisory lock is immediately released."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, "state.lock")
        ready_file = os.path.join(tmpdir, "ready.marker")
        result_file = os.path.join(tmpdir, "result.marker")

        # Spawn child process that acquires lock and terminates after 0.5s
        cmd = [
            sys.executable, "-c",
            f"from tests.test_file_lock_concurrency import _worker_hold_lock; "
            f"_worker_hold_lock(r'{lock_file}', 0.4, r'{ready_file}', r'{result_file}')"
        ]
        proc = subprocess.Popen(cmd)

        start = time.time()
        while not os.path.exists(ready_file) and time.time() - start < 5.0:
            time.sleep(0.05)

        # Wait for child process to terminate
        proc.wait(timeout=5.0)

        # Main process acquires lock immediately without timeout
        acquired = False
        with FileLock(lock_file, timeout=2.0):
            acquired = True
        assert acquired is True


def _concurrent_worker(lock_file: str, counter_file: str, iterations: int):
    """Worker incrementing shared counter file under lock protection."""
    for _ in range(iterations):
        with FileLock(lock_file, timeout=10.0):
            with open(counter_file, "r", encoding="utf-8") as f:
                val = int(f.read().strip() or "0")
            time.sleep(0.01)
            with open(counter_file, "w", encoding="utf-8") as f:
                f.write(str(val + 1))


def test_multi_process_concurrent_acquisition_contention():
    """Verifies that multiple concurrent processes serialize increments without race conditions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, "state.lock")
        counter_file = os.path.join(tmpdir, "counter.txt")
        with open(counter_file, "w", encoding="utf-8") as f:
            f.write("0")

        num_processes = 4
        iterations_per_proc = 5

        procs = []
        for _ in range(num_processes):
            cmd = [
                sys.executable, "-c",
                f"from tests.test_file_lock_concurrency import _concurrent_worker; "
                f"_concurrent_worker(r'{lock_file}', r'{counter_file}', {iterations_per_proc})"
            ]
            procs.append(subprocess.Popen(cmd))

        for p in procs:
            p.wait(timeout=20.0)
            assert p.returncode == 0

        with open(counter_file, "r", encoding="utf-8") as f:
            total = int(f.read().strip())
        assert total == num_processes * iterations_per_proc


def test_native_fallback_mode(monkeypatch):
    """Verifies FileLock authority still functions when HAS_PORTALOCKER is forced False."""
    monkeypatch.setattr(file_lock, "HAS_PORTALOCKER", False)
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, "state.lock")
        with FileLock(lock_file, timeout=2.0) as fl:
            assert os.path.exists(lock_file)
            assert fl._fd is not None
            os.lseek(fl._fd, 0, os.SEEK_SET)
            raw = os.read(fl._fd, 1024)
            payload = json.loads(raw.decode("utf-8").strip())
            assert payload["pid"] == os.getpid()


def test_gc_race_safety_with_active_and_stale_locks():
    """Verifies run_gc leaves actively held lock untouched while removing stale unheld lock."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agents_dir = os.path.join(tmpdir, ".agents")
        os.makedirs(agents_dir, exist_ok=True)
        active_lock = os.path.join(agents_dir, "state.lock")

        # Hold active lock
        with FileLock(active_lock, timeout=5.0):
            # Run GC while active lock is held
            res = run_gc(tmpdir)
            # Active lock MUST NOT be removed
            assert os.path.exists(active_lock)
            assert res.stale_locks_reclaimed == 0
            assert res.stale_locks_removed == 0

        # After releasing active lock and marking it stale (status: released)
        assert os.path.exists(active_lock)
        res2 = run_gc(tmpdir)
        # Stale released lock is reclaimed and reset to idle
        assert res2.stale_locks_reclaimed == 1
        assert res2.stale_locks_removed == 1
        with open(active_lock, "r", encoding="utf-8") as f:
            reclaimed_data = json.load(f)
        assert reclaimed_data.get("status") == "idle"
