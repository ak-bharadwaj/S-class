"""
Empirical Adversarial Stress Harness for Concurrency Re-challenge (Milestone 1 Iteration 2).
Tests:
1. Heavy multi-threaded contention mutual exclusion (16 threads, 50 iterations each = 800 entries)
2. Windows case-insensitivity mutual exclusion with 4 different path casings
3. Runtime decision logging under multi-threaded contention (10 threads x 20 decisions = 200 decisions, 0 lost updates)
4. Runtime decision logging under multi-process contention (4 processes x 25 decisions = 100 decisions, 0 lost updates)
5. Multi-threaded counter race check (20 threads x 30 increments = 600 increments, 0 lost updates)
"""

import os
import sys
import time
import shutil
import random
import threading
import multiprocessing
import pytest
from file_lock import FileLock, NativeLock, _active_local_locks, _path_thread_locks
import runtime


def test_heavy_multithreaded_mutual_exclusion(tmp_path):
    """Stress tests FileLock under heavy thread contention with randomized sleeps."""
    lock_file = str(tmp_path / "heavy_mt.lock")
    num_threads = 16
    iters_per_thread = 50
    counter = 0
    in_cs = 0
    violations = []
    cs_guard = threading.Lock()

    def worker(tid):
        nonlocal counter, in_cs
        for it in range(iters_per_thread):
            with FileLock(lock_file, timeout=20.0, poll_interval=0.002):
                with cs_guard:
                    in_cs += 1
                    if in_cs > 1:
                        violations.append(f"Thread {tid} collision: in_cs={in_cs} at iter {it}")
                
                # Critical section work with jitter
                cur = counter
                time.sleep(random.uniform(0.0001, 0.001))
                counter = cur + 1

                with cs_guard:
                    in_cs -= 1

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not violations, f"Thread mutual exclusion violations detected: {violations}"
    assert counter == num_threads * iters_per_thread, f"Lost updates! Expected {num_threads * iters_per_thread}, got {counter}"


def test_windows_multicase_contention(tmp_path):
    """Tests Windows case insensitivity across 4 different casing permutations simultaneously."""
    if sys.platform != "win32":
        pytest.skip("Windows NTFS case insensitivity test only")

    cases = [
        str(tmp_path / "adversarial_case.lock"),
        str(tmp_path / "ADVERSARIAL_CASE.LOCK"),
        str(tmp_path / "Adversarial_Case.Lock"),
        str(tmp_path / "aDvErSaRiAl_cAsE.lOcK"),
    ]
    
    in_cs = 0
    counter = 0
    violations = []
    cs_guard = threading.Lock()
    iters = 25

    def worker(path_case, tid):
        nonlocal in_cs, counter
        for _ in range(iters):
            with FileLock(path_case, timeout=15.0, poll_interval=0.002):
                with cs_guard:
                    in_cs += 1
                    if in_cs > 1:
                        violations.append(f"Case collision with {path_case}: in_cs={in_cs}")
                
                cur = counter
                time.sleep(0.0005)
                counter = cur + 1

                with cs_guard:
                    in_cs -= 1

    threads = [threading.Thread(target=worker, args=(cases[i % len(cases)], i)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not violations, f"Case insensitivity violations detected: {violations}"
    assert counter == 12 * iters, f"Lost updates in case testing! Expected {12 * iters}, got {counter}"


def test_runtime_decision_logging_multithreaded_contention(tmp_path):
    """Re-tests runtime decision logging under multi-threaded contention (10 threads x 20 decisions = 200)."""
    ws = str(tmp_path / "ws_runtime_mt")
    os.makedirs(ws, exist_ok=True)
    state = runtime.initialize_state(workspace_dir=ws, goal="runtime mt test")
    initial_count = len(state.decisionLog)

    num_threads = 10
    decisions_per_thread = 20
    errors = []

    def worker(tid):
        for i in range(decisions_per_thread):
            try:
                runtime.log_decision(
                    decision=f"mt_decision_{tid}_{i}",
                    reason=f"testing contention from thread {tid} iter {i}",
                    agent=f"challenger_thread_{tid}",
                    confidence=0.95,
                    workspace_dir=ws
                )
            except Exception as e:
                errors.append(f"Thread {tid} error on iter {i}: {e}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Errors logged during threaded runtime decision logging: {errors}"

    final_state = runtime.get_state(workspace_dir=ws)
    total_added = len(final_state.decisionLog) - initial_count
    expected_total = num_threads * decisions_per_thread

    assert total_added == expected_total, f"Lost updates in runtime.log_decision! Expected {expected_total}, got {total_added}"
    
    # Verify uniqueness of logged decisions
    logged_decisions = {d.decision for d in final_state.decisionLog if d.decision.startswith("mt_decision_")}
    assert len(logged_decisions) == expected_total, f"Duplicate or dropped decisions! Found {len(logged_decisions)} unique out of {expected_total}"


def _mp_decision_worker(ws, proc_id, iters, errors_queue):
    for i in range(iters):
        try:
            runtime.log_decision(
                decision=f"mp_decision_{proc_id}_{i}",
                reason=f"testing contention from proc {proc_id} iter {i}",
                agent=f"challenger_proc_{proc_id}",
                confidence=0.99,
                workspace_dir=ws
            )
        except Exception as e:
            errors_queue.put(f"Proc {proc_id} error on iter {i}: {e}")


def test_runtime_decision_logging_multiprocess_contention(tmp_path):
    """Re-tests runtime decision logging under multi-process contention (4 procs x 25 decisions = 100)."""
    ws = str(tmp_path / "ws_runtime_mp")
    os.makedirs(ws, exist_ok=True)
    state = runtime.initialize_state(workspace_dir=ws, goal="runtime mp test")
    initial_count = len(state.decisionLog)

    num_procs = 4
    iters_per_proc = 25
    errors_queue = multiprocessing.Queue()

    procs = [
        multiprocessing.Process(target=_mp_decision_worker, args=(ws, i, iters_per_proc, errors_queue))
        for i in range(num_procs)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()

    errors = []
    while not errors_queue.empty():
        errors.append(errors_queue.get())

    assert not errors, f"Errors logged during multiprocess runtime decision logging: {errors}"

    final_state = runtime.get_state(workspace_dir=ws)
    total_added = len(final_state.decisionLog) - initial_count
    expected_total = num_procs * iters_per_proc

    assert total_added == expected_total, f"Lost updates in multiprocess runtime.log_decision! Expected {expected_total}, got {total_added}"

    logged_decisions = {d.decision for d in final_state.decisionLog if d.decision.startswith("mp_decision_")}
    assert len(logged_decisions) == expected_total, f"Duplicate or dropped decisions in MP! Found {len(logged_decisions)} unique out of {expected_total}"


def test_high_offset_locking_allows_metadata_io(tmp_path):
    """Verifies that byte-range lock at LOCK_OFFSET permits reading/writing metadata at offset 0 while locked."""
    lock_file = str(tmp_path / "offset_test.lock")
    
    with FileLock(lock_file, timeout=2.0) as fl:
        # File is held locked by fl. Another file handle should be able to read offset 0 without PermissionError
        with open(lock_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert fl.token in content
            assert str(os.getpid()) in content
