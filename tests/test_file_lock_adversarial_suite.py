import os
import sys
import time
import asyncio
import threading
import pytest
from file_lock import FileLock, NativeLock, AsyncFileLock, AsyncNativeLock, _active_local_locks, _active_locks_guard


def test_exception_safety_cleanup(tmp_path):
    lock_file = str(tmp_path / "exc_test.lock")
    
    # Verify exception inside with block still releases lock
    with pytest.raises(RuntimeError):
        with FileLock(lock_file, timeout=2.0):
            assert lock_file in _active_local_locks
            raise RuntimeError("Boom!")

    with _active_locks_guard:
        assert lock_file not in _active_local_locks

    # Subsequent acquisition should immediately succeed without timeout
    acquired = False
    with FileLock(lock_file, timeout=0.5):
        acquired = True
    assert acquired


def test_multithreaded_mutual_exclusion_file_lock(tmp_path):
    """
    Demonstrates the thread mutual exclusion flaw in FileLock on Windows.
    Because fd is unlocked/closed in __enter__, multiple threads enter concurrently.
    """
    lock_file = str(tmp_path / "mt_fl.lock")
    counter = 0
    in_critical_section = 0
    violations = []
    cs_lock = threading.Lock()

    def worker():
        nonlocal counter, in_critical_section
        for _ in range(15):
            with FileLock(lock_file, timeout=10.0, poll_interval=0.005):
                with cs_lock:
                    in_critical_section += 1
                    if in_critical_section > 1:
                        violations.append(f"Multiple threads in CS: {in_critical_section}")
                
                # Critical section work
                c = counter
                time.sleep(0.001)
                counter = c + 1

                with cs_lock:
                    in_critical_section -= 1

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not violations, f"Mutual exclusion violated: {violations}"
    assert counter == 8 * 15


def test_multithreaded_mutual_exclusion_native_lock(tmp_path):
    """
    Demonstrates that NativeLock correctly enforces kernel mutual exclusion across threads.
    """
    lock_file = str(tmp_path / "mt_nl.lock")
    counter = 0
    in_critical_section = 0
    violations = []
    cs_lock = threading.Lock()

    def worker():
        nonlocal counter, in_critical_section
        for _ in range(15):
            with NativeLock(lock_file, timeout=10.0, poll_interval=0.005):
                with cs_lock:
                    in_critical_section += 1
                    if in_critical_section > 1:
                        violations.append(f"Multiple threads in NativeLock CS: {in_critical_section}")

                # Critical section work
                c = counter
                time.sleep(0.001)
                counter = c + 1

                with cs_lock:
                    in_critical_section -= 1

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not violations, f"NativeLock Mutual exclusion violated: {violations}"
    assert counter == 8 * 15


def test_timeout_handling_file_lock(tmp_path):
    lock_file = str(tmp_path / "timeout_fl.lock")
    barrier = threading.Barrier(2)
    timed_out = False

    def holder():
        with FileLock(lock_file, timeout=2.0):
            barrier.wait()
            time.sleep(0.4)

    def waiter():
        nonlocal timed_out
        barrier.wait()
        time.sleep(0.02)
        try:
            with FileLock(lock_file, timeout=0.1, poll_interval=0.01):
                pass
        except TimeoutError:
            timed_out = True

    t1 = threading.Thread(target=holder)
    t2 = threading.Thread(target=waiter)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert timed_out, "Waiter should have timed out"


def test_timeout_handling_native_lock(tmp_path):
    lock_file = str(tmp_path / "timeout_nl.lock")
    barrier = threading.Barrier(2)
    timed_out = False

    def holder():
        with NativeLock(lock_file, timeout=2.0):
            barrier.wait()
            time.sleep(0.4)

    def waiter():
        nonlocal timed_out
        barrier.wait()
        time.sleep(0.02)
        try:
            with NativeLock(lock_file, timeout=0.1, poll_interval=0.01):
                pass
        except TimeoutError:
            timed_out = True

    t1 = threading.Thread(target=holder)
    t2 = threading.Thread(target=waiter)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert timed_out, "NativeLock waiter should have timed out"


def test_async_file_lock_concurrency(tmp_path):
    lock_file = str(tmp_path / "async_fl.lock")

    async def _runner():
        counter = 0
        in_cs = 0
        violations = []

        async def task_worker():
            nonlocal counter, in_cs
            for _ in range(10):
                async with AsyncFileLock(lock_file, timeout=10.0, poll_interval=0.005):
                    in_cs += 1
                    if in_cs > 1:
                        violations.append(f"AsyncFileLock CS violation: {in_cs}")
                    await asyncio.sleep(0.002)
                    counter += 1
                    in_cs -= 1

        await asyncio.gather(*[task_worker() for _ in range(6)])
        return violations, counter

    violations, counter = asyncio.run(_runner())
    assert not violations, f"AsyncFileLock violations: {violations}"
    assert counter == 6 * 10


def test_async_native_lock_concurrency(tmp_path):
    lock_file = str(tmp_path / "async_nl.lock")

    async def _runner():
        counter = 0
        in_cs = 0
        violations = []

        async def task_worker():
            nonlocal counter, in_cs
            for _ in range(10):
                async with AsyncNativeLock(lock_file, timeout=10.0, poll_interval=0.005):
                    in_cs += 1
                    if in_cs > 1:
                        violations.append(f"AsyncNativeLock CS violation: {in_cs}")
                    await asyncio.sleep(0.002)
                    counter += 1
                    in_cs -= 1

        await asyncio.gather(*[task_worker() for _ in range(6)])
        return violations, counter

    violations, counter = asyncio.run(_runner())
    assert not violations, f"AsyncNativeLock violations: {violations}"
    assert counter == 6 * 10


def test_windows_case_insensitivity_mutual_exclusion(tmp_path):
    """
    On case-insensitive filesystems (Windows/NTFS), 'state.lock' and 'CASE_TEST.LOCK'
    refer to the identical underlying file. Mutual exclusion MUST be maintained
    even if callers pass different case variations of the path.
    """
    if sys.platform != "win32":
        pytest.skip("Windows NTFS case-insensitivity test only")

    path_lower = str(tmp_path / "case_test.lock")
    path_upper = str(tmp_path / "CASE_TEST.LOCK")
    
    in_cs = 0
    violations = []
    cs_lock = threading.Lock()
    barrier = threading.Barrier(2)

    def worker_lower():
        nonlocal in_cs
        with FileLock(path_lower, timeout=5.0):
            with cs_lock:
                in_cs += 1
                if in_cs > 1:
                    violations.append("Violation: Both lower and upper in CS simultaneously!")
            barrier.wait()
            time.sleep(0.3)
            with cs_lock:
                in_cs -= 1

    def worker_upper():
        nonlocal in_cs
        barrier.wait()
        try:
            with FileLock(path_upper, timeout=0.1, poll_interval=0.01):
                with cs_lock:
                    in_cs += 1
                    if in_cs > 1:
                        violations.append("Violation: Both lower and upper in CS simultaneously!")
                time.sleep(0.1)
                with cs_lock:
                    in_cs -= 1
        except TimeoutError:
            pass

    t1 = threading.Thread(target=worker_lower)
    t2 = threading.Thread(target=worker_upper)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert not violations, f"Case-insensitive mutual exclusion failed: {violations}"
