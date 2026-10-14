import os
import sys
import time
import json
import threading
import multiprocessing
from file_lock import FileLock, NativeLock, AsyncFileLock, AsyncNativeLock

def crash_holding_worker(lock_cls, lock_path, ready_path):
    # This process acquires the lock and then hangs until killed
    with lock_cls(lock_path, timeout=5.0):
        with open(ready_path, "w", encoding="utf-8") as f:
            f.write("held")
        # Hang forever until terminated
        while True:
            time.sleep(1)

import pytest

@pytest.mark.parametrize("lock_cls,name", [(FileLock, "FileLock"), (NativeLock, "NativeLock")])
def test_crash_recovery(lock_cls, name):
    lock_path = os.path.abspath(f"test_crash_{name}.lock")
    ready_path = os.path.abspath(f"test_crash_{name}.ready")
    for p in [lock_path, ready_path]:
        if os.path.exists(p):
            try: os.unlink(p)
            except OSError: pass

    proc = multiprocessing.Process(target=crash_holding_worker, args=(lock_cls, lock_path, ready_path))
    proc.start()

    # Wait until worker holds lock
    for _ in range(50):
        if os.path.exists(ready_path):
            break
        time.sleep(0.05)
    assert os.path.exists(ready_path), f"Worker failed to signal lock acquisition for {name}"

    # Kill the worker abruptly
    proc.terminate()
    proc.join()
    assert not proc.is_alive()

    # Now attempt to acquire with a new lock instance
    t0 = time.time()
    try:
        with lock_cls(lock_path, timeout=3.0, stale_ttl=1.0):
            elapsed = time.time() - t0
            print(f"[{name}] Crash recovery PASSED: acquired in {elapsed:.3f}s")
            result = True
    except Exception as e:
        print(f"[{name}] Crash recovery FAILED with: {type(e)}: {e}")
        result = False

    for p in [lock_path, ready_path]:
        if os.path.exists(p):
            try: os.unlink(p)
            except OSError: pass

    assert result is True

if __name__ == "__main__":
    fl_crash = test_crash_recovery(FileLock, "FileLock")
    nl_crash = test_crash_recovery(NativeLock, "NativeLock")
    print("Crash tests:", "FileLock:", fl_crash, "NativeLock:", nl_crash)
    if not (fl_crash and nl_crash):
        sys.exit(1)
