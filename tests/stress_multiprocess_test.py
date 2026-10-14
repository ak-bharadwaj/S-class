import os
import sys
import time
import multiprocessing
from file_lock import FileLock, NativeLock

def mp_strict_worker(lock_cls, lock_path, iters, shared_in_cs, violations, worker_id):
    for i in range(iters):
        try:
            with lock_cls(lock_path, timeout=15.0, poll_interval=0.005):
                # We are in critical section! Check exclusivity:
                with shared_in_cs.get_lock():
                    shared_in_cs.value += 1
                    current = shared_in_cs.value
                    if current > 1:
                        violations.append(f"Worker {worker_id}: concurrent in_cs={current}")
                
                # Sleep briefly to give other processes time to potentially collide
                time.sleep(0.005)

                with shared_in_cs.get_lock():
                    shared_in_cs.value -= 1
        except Exception as e:
            violations.append(f"Worker {worker_id} exception: {e}")

def run_strict_mp_test(lock_cls, name, num_procs=6, iters=15):
    lock_path = os.path.abspath(f"test_strict_{name}.lock")
    if os.path.exists(lock_path):
        try: os.unlink(lock_path)
        except OSError: pass

    mgr = multiprocessing.Manager()
    violations = mgr.list()
    shared_in_cs = multiprocessing.Value('i', 0)

    procs = []
    for i in range(num_procs):
        p = multiprocessing.Process(
            target=mp_strict_worker,
            args=(lock_cls, lock_path, iters, shared_in_cs, violations, i)
        )
        procs.append(p)
        p.start()

    for p in procs:
        p.join()

    if os.path.exists(lock_path):
        try: os.unlink(lock_path)
        except OSError: pass

    print(f"[{name}] Completed with {len(violations)} violations. Violations sample: {list(violations)[:5]}")
    return len(violations) == 0

def test_multiprocess_strict_lock():
    fl_res = run_strict_mp_test(FileLock, "FileLock", num_procs=4, iters=8)
    nl_res = run_strict_mp_test(NativeLock, "NativeLock", num_procs=4, iters=8)
    assert fl_res, "FileLock failed multiprocessing strict concurrency"
    assert nl_res, "NativeLock failed multiprocessing strict concurrency"

if __name__ == "__main__":
    fl_res = run_strict_mp_test(FileLock, "FileLock", num_procs=6, iters=15)
    nl_res = run_strict_mp_test(NativeLock, "NativeLock", num_procs=6, iters=15)
    print(f"FileLock MP Strict: {'PASS' if fl_res else 'FAIL'}")
    print(f"NativeLock MP Strict: {'PASS' if nl_res else 'FAIL'}")
    if not (fl_res and nl_res):
        sys.exit(1)
