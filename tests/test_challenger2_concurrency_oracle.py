"""
Adversarial Oracle & Stress Suite for Milestone 1 Iteration 2 (Challenger 2).
Re-verifies:
1. Foreign locks cannot be stolen from live processes (JSON, raw PID, kernel lock, ancient mtime).
2. Foreign lock exit preservation (unlinking immunity when ownership is foreign).
3. Stale lock recovery for dead PIDs (JSON dead PID, raw dead PID, abruptly killed processes).
4. Repeated crash recovery storm (10 sequential crashes & immediate re-acquisitions).
5. Edge cases (corrupt JSON, empty file, negative PID, zero PID, unparseable PID).
6. Multi-process contention counter integrity (FileLock and NativeLock).
"""

import os
import sys
import time
import json
import pytest
import subprocess
import multiprocessing
from file_lock import FileLock, NativeLock, _process_exists


def _hold_filelock_worker(lock_path, ready_path, stop_path):
    with FileLock(lock_path, timeout=5.0):
        with open(ready_path, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        while not os.path.exists(stop_path):
            time.sleep(0.02)


def _hold_nativelock_worker(lock_path, ready_path, stop_path):
    with NativeLock(lock_path, timeout=5.0):
        with open(ready_path, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        while not os.path.exists(stop_path):
            time.sleep(0.02)


def _hang_worker(lock_cls, lock_path, ready_path):
    with lock_cls(lock_path, timeout=5.0):
        with open(ready_path, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        while True:
            time.sleep(0.5)


# -------------------------------------------------------------
# Group A: Foreign Lock Protection (Live Process Immunity)
# -------------------------------------------------------------

def test_cannot_steal_live_process_json_lock(tmp_path):
    """FileLock must raise TimeoutError when lock is held by a live process with JSON metadata."""
    lock_file = str(tmp_path / "live_json.lock")
    ready_file = str(tmp_path / "live_json.ready")
    stop_file = str(tmp_path / "live_json.stop")

    p = multiprocessing.Process(target=_hold_filelock_worker, args=(lock_file, ready_file, stop_file))
    p.start()
    try:
        # Wait for worker to acquire
        for _ in range(50):
            if os.path.exists(ready_file):
                break
            time.sleep(0.02)
        assert os.path.exists(ready_file)
        worker_pid = p.pid

        # Read original metadata
        with open(lock_file, "r", encoding="utf-8") as f:
            orig_content = f.read()
        assert str(worker_pid) in orig_content

        # Attempt to steal
        with pytest.raises(TimeoutError):
            with FileLock(lock_file, timeout=0.3):
                pytest.fail("Lock was stolen from live process!")

        # Verify content was not modified
        with open(lock_file, "r", encoding="utf-8") as f:
            curr_content = f.read()
        assert curr_content == orig_content
    finally:
        with open(stop_file, "w") as f:
            f.write("stop")
        p.join(timeout=2.0)
        if p.is_alive():
            p.terminate()


def test_cannot_steal_live_process_raw_pid_lock(tmp_path):
    """FileLock must raise TimeoutError when lock contains a raw live PID string."""
    lock_file = str(tmp_path / "live_raw.lock")
    ready_file = str(tmp_path / "live_raw.ready")
    stop_file = str(tmp_path / "live_raw.stop")

    # Spawn a sleeping dummy process to provide a live external PID
    p = subprocess.Popen([sys.executable, "-c", "import time, sys; open(sys.argv[1], 'w').write('ok'); time.sleep(10)", ready_file])
    try:
        for _ in range(50):
            if os.path.exists(ready_file):
                break
            time.sleep(0.02)
        assert _process_exists(p.pid)

        # Write raw PID to lock file
        with open(lock_file, "w", encoding="utf-8") as f:
            f.write(str(p.pid))

        # Attempt to steal with FileLock
        with pytest.raises(TimeoutError):
            with FileLock(lock_file, timeout=0.3):
                pytest.fail("Lock was stolen from live raw PID process!")

        # Verify lock file was not overwritten or deleted
        assert os.path.exists(lock_file)
        with open(lock_file, "r", encoding="utf-8") as f:
            assert f.read().strip() == str(p.pid)
    finally:
        p.terminate()
        p.wait()


def test_cannot_steal_live_process_ancient_mtime(tmp_path):
    """FileLock must NOT steal from a live process even if mtime is older than stale_ttl."""
    lock_file = str(tmp_path / "live_ancient.lock")
    ready_file = str(tmp_path / "live_ancient.ready")

    p = subprocess.Popen([sys.executable, "-c", "import time, sys; open(sys.argv[1], 'w').write('ok'); time.sleep(10)", ready_file])
    try:
        for _ in range(50):
            if os.path.exists(ready_file):
                break
            time.sleep(0.02)
        assert _process_exists(p.pid)

        # Write live PID in JSON
        payload = json.dumps({"status": "active", "pid": p.pid, "token": "foreign-live"})
        with open(lock_file, "w", encoding="utf-8") as f:
            f.write(payload)

        # Backdate mtime by 10,000 seconds
        ancient = time.time() - 10000.0
        os.utime(lock_file, (ancient, ancient))

        # Must raise TimeoutError despite stale mtime
        with pytest.raises(TimeoutError):
            with FileLock(lock_file, timeout=0.3, stale_ttl=1.0):
                pytest.fail("Stole ancient mtime lock from live process!")

        # File must remain intact
        assert os.path.exists(lock_file)
        with open(lock_file, "r", encoding="utf-8") as f:
            data = json.loads(f.read())
            assert data["pid"] == p.pid
    finally:
        p.terminate()
        p.wait()


def test_cannot_steal_live_nativelock_from_filelock(tmp_path):
    """FileLock cannot acquire when NativeLock holds kernel lock."""
    lock_file = str(tmp_path / "cross_nl.lock")
    ready_file = str(tmp_path / "cross_nl.ready")
    stop_file = str(tmp_path / "cross_nl.stop")

    p = multiprocessing.Process(target=_hold_nativelock_worker, args=(lock_file, ready_file, stop_file))
    p.start()
    try:
        for _ in range(50):
            if os.path.exists(ready_file):
                break
            time.sleep(0.02)
        assert os.path.exists(ready_file)

        # Attempt to acquire with FileLock
        with pytest.raises(TimeoutError):
            with FileLock(lock_file, timeout=0.3):
                pytest.fail("FileLock acquired over active NativeLock kernel lock!")
    finally:
        with open(stop_file, "w") as f:
            f.write("stop")
        p.join(timeout=2.0)
        if p.is_alive():
            p.terminate()


def test_foreign_lock_exit_preservation(tmp_path):
    """FileLock.__exit__ must NOT delete a file if ownership was replaced by another entity."""
    lock_file = str(tmp_path / "foreign_exit.lock")

    fl = FileLock(lock_file, timeout=2.0)
    fl.__enter__()

    # Simulate another entity replacing the lock file content
    foreign_meta = json.dumps({"status": "active", "pid": 7777777, "token": "other-token"})
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write(foreign_meta)

    # Exit should NOT unlink the foreign file
    fl.__exit__(None, None, None)
    assert os.path.exists(lock_file), "Foreign lock file was deleted on exit!"
    with open(lock_file, "r", encoding="utf-8") as f:
        assert f.read() == foreign_meta


# -------------------------------------------------------------
# Group B: Stale Lock Recovery for Dead PIDs
# -------------------------------------------------------------

def test_recover_dead_pid_json(tmp_path):
    """FileLock recovers immediately (<0.2s) when lock contains JSON metadata of dead PID."""
    lock_file = str(tmp_path / "dead_json.lock")
    dead_pid = 9999991
    assert not _process_exists(dead_pid)

    with open(lock_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({"status": "active", "pid": dead_pid, "token": "dead-token"}))

    t0 = time.time()
    with FileLock(lock_file, timeout=2.0, stale_ttl=30.0):
        elapsed = time.time() - t0
        assert os.path.exists(lock_file)
    assert elapsed < 0.3, f"Dead PID recovery took too long: {elapsed:.3f}s"


def test_recover_dead_pid_raw(tmp_path):
    """FileLock recovers immediately (<0.2s) when lock contains raw string of dead PID."""
    lock_file = str(tmp_path / "dead_raw.lock")
    dead_pid = 9999992
    assert not _process_exists(dead_pid)

    with open(lock_file, "w", encoding="utf-8") as f:
        f.write(str(dead_pid))

    t0 = time.time()
    with FileLock(lock_file, timeout=2.0, stale_ttl=30.0):
        elapsed = time.time() - t0
        assert os.path.exists(lock_file)
    assert elapsed < 0.3, f"Raw dead PID recovery took too long: {elapsed:.3f}s"


def test_crash_recovery_terminated_process_filelock(tmp_path):
    """FileLock recovers immediately when previous holder is forcefully killed."""
    lock_file = str(tmp_path / "crash_fl.lock")
    ready_file = str(tmp_path / "crash_fl.ready")

    p = multiprocessing.Process(target=_hang_worker, args=(FileLock, lock_file, ready_file))
    p.start()
    for _ in range(50):
        if os.path.exists(ready_file):
            break
        time.sleep(0.02)
    assert os.path.exists(ready_file)

    # Abruptly kill the worker
    p.terminate()
    p.join(timeout=2.0)
    assert not p.is_alive()

    # Next process must acquire immediately
    t0 = time.time()
    with FileLock(lock_file, timeout=2.0, stale_ttl=1.0):
        elapsed = time.time() - t0
        assert os.path.exists(lock_file)
    assert elapsed < 0.3, f"Crash recovery took {elapsed:.3f}s"


def test_crash_recovery_terminated_process_nativelock(tmp_path):
    """NativeLock recovers immediately when previous holder is forcefully killed."""
    lock_file = str(tmp_path / "crash_nl.lock")
    ready_file = str(tmp_path / "crash_nl.ready")

    p = multiprocessing.Process(target=_hang_worker, args=(NativeLock, lock_file, ready_file))
    p.start()
    for _ in range(50):
        if os.path.exists(ready_file):
            break
        time.sleep(0.02)
    assert os.path.exists(ready_file)

    p.terminate()
    p.join(timeout=2.0)
    assert not p.is_alive()

    t0 = time.time()
    with NativeLock(lock_file, timeout=2.0, stale_ttl=1.0):
        elapsed = time.time() - t0
        assert os.path.exists(lock_file)
    assert elapsed < 0.3, f"NativeLock crash recovery took {elapsed:.3f}s"


def test_repeated_crash_recovery_storm(tmp_path):
    """Stress test: 10 consecutive crashes & immediate recoveries in sequence."""
    lock_file = str(tmp_path / "storm.lock")

    for i in range(10):
        ready_file = str(tmp_path / f"storm_{i}.ready")
        p = multiprocessing.Process(target=_hang_worker, args=(FileLock, lock_file, ready_file))
        p.start()
        for _ in range(150):
            if os.path.exists(ready_file):
                break
            time.sleep(0.02)
        assert os.path.exists(ready_file)

        p.terminate()
        p.join(timeout=2.0)
        assert not p.is_alive()

        # Re-acquire immediately
        with FileLock(lock_file, timeout=2.0, stale_ttl=1.0):
            pass


# -------------------------------------------------------------
# Group C: Edge Cases & Corrupt Metadata
# -------------------------------------------------------------

def test_empty_lock_file_handling(tmp_path):
    """Empty lock file older than 0.5s is reclaimed immediately."""
    lock_file = str(tmp_path / "empty.lock")
    open(lock_file, "w").close()
    old = time.time() - 2.0
    os.utime(lock_file, (old, old))

    with FileLock(lock_file, timeout=1.0):
        assert os.path.exists(lock_file)


def test_corrupt_json_stale_handling(tmp_path):
    """Corrupt JSON older than stale_ttl is reclaimed."""
    lock_file = str(tmp_path / "corrupt.lock")
    with open(lock_file, "w") as f:
        f.write("{broken json payload!!!")
    old = time.time() - 10.0
    os.utime(lock_file, (old, old))

    with FileLock(lock_file, timeout=1.0, stale_ttl=2.0):
        assert os.path.exists(lock_file)


def test_zero_and_negative_pids(tmp_path):
    """Zero and negative PIDs are treated as dead and reclaimed immediately."""
    for bad_pid in [0, -1, -999]:
        lock_file = str(tmp_path / f"pid_{bad_pid}.lock")
        with open(lock_file, "w") as f:
            f.write(json.dumps({"status": "active", "pid": bad_pid}))
        with FileLock(lock_file, timeout=1.0):
            assert os.path.exists(lock_file)


# -------------------------------------------------------------
# Group D: Multi-Process Counter Contention (0 Lost Updates)
# -------------------------------------------------------------

def _counter_worker(lock_cls, lock_path, counter_path, iters):
    for _ in range(iters):
        with lock_cls(lock_path, timeout=15.0, poll_interval=0.005):
            with open(counter_path, "r", encoding="utf-8") as f:
                val = int(f.read().strip())
            time.sleep(0.002)
            with open(counter_path, "w", encoding="utf-8") as f:
                f.write(str(val + 1))


def test_4_process_counter_contention_filelock(tmp_path):
    """4 processes increment a shared counter 25 times each using FileLock -> exactly 100."""
    lock_file = str(tmp_path / "cnt_fl.lock")
    cnt_file = str(tmp_path / "cnt_fl.txt")
    with open(cnt_file, "w", encoding="utf-8") as f:
        f.write("0")

    procs = [
        multiprocessing.Process(target=_counter_worker, args=(FileLock, lock_file, cnt_file, 25))
        for _ in range(4)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()

    with open(cnt_file, "r", encoding="utf-8") as f:
        final_val = int(f.read().strip())
    assert final_val == 100, f"Lost updates detected: expected 100, got {final_val}"


def test_4_process_counter_contention_nativelock(tmp_path):
    """4 processes increment a shared counter 25 times each using NativeLock -> exactly 100."""
    lock_file = str(tmp_path / "cnt_nl.lock")
    cnt_file = str(tmp_path / "cnt_nl.txt")
    with open(cnt_file, "w", encoding="utf-8") as f:
        f.write("0")

    procs = [
        multiprocessing.Process(target=_counter_worker, args=(NativeLock, lock_file, cnt_file, 25))
        for _ in range(4)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()

    with open(cnt_file, "r", encoding="utf-8") as f:
        final_val = int(f.read().strip())
    assert final_val == 100, f"NativeLock lost updates detected: expected 100, got {final_val}"


def test_rapid_foreign_steal_attempts_fail(tmp_path):
    """Verify 50 consecutive rapid steal attempts against an active live process lock all fail."""
    lock_file = str(tmp_path / "rapid_foreign.lock")
    ready_file = str(tmp_path / "rapid_foreign.ready")
    stop_file = str(tmp_path / "rapid_foreign.stop")

    p = multiprocessing.Process(target=_hold_filelock_worker, args=(lock_file, ready_file, stop_file))
    p.start()
    try:
        for _ in range(50):
            if os.path.exists(ready_file):
                break
            time.sleep(0.02)
        assert os.path.exists(ready_file)

        # 50 rapid steal attempts
        for _ in range(50):
            with pytest.raises(TimeoutError):
                with FileLock(lock_file, timeout=0.02):
                    pytest.fail("Foreign lock was stolen from live process!")
        assert os.path.exists(lock_file)
    finally:
        with open(stop_file, "w") as f:
            f.write("stop")
        p.join(timeout=2.0)
        if p.is_alive():
            p.terminate()


def _reclaim_worker(lock_path, counter_path):
    with FileLock(lock_path, timeout=10.0, stale_ttl=1.0):
        with open(counter_path, "r", encoding="utf-8") as f:
            val = int(f.read().strip())
        time.sleep(0.01)
        with open(counter_path, "w", encoding="utf-8") as f:
            f.write(str(val + 1))


def test_concurrent_dead_pid_reclamation(tmp_path):
    """5 processes race simultaneously to reclaim a stale dead PID lock file: all must serialize cleanly."""
    lock_file = str(tmp_path / "dead_race.lock")
    cnt_file = str(tmp_path / "dead_race.txt")
    with open(cnt_file, "w", encoding="utf-8") as f:
        f.write("0")

    # Seed with dead PID
    dead_pid = 9999993
    assert not _process_exists(dead_pid)
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({"status": "active", "pid": dead_pid, "token": "dead-seed"}))

    procs = [
        multiprocessing.Process(target=_reclaim_worker, args=(lock_file, cnt_file))
        for _ in range(5)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()

    with open(cnt_file, "r", encoding="utf-8") as f:
        final_val = int(f.read().strip())
    assert final_val == 5, f"Expected counter to reach 5, got {final_val}"

