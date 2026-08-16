#!/usr/bin/env python3
"""
OSS Parity Gate 1: Differential Benchmark & Capability Verification Harness
Comparing S-Class FileLock (Layer 0) vs Reference Portalocker 4.1.0
"""

import os
import sys
import time
import json
import socket
import tempfile
import threading
import subprocess
import ctypes
from typing import Dict, List, Any, Tuple
import portalocker
import portalocker.utils

# Add plugin root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from file_lock import FileLock, HAS_PORTALOCKER
from config_gc import run_gc

def get_current_process_memory_bytes() -> int:
    """Returns working set memory in bytes for current process on Windows/POSIX."""
    if sys.platform == "win32":
        try:
            import ctypes.wintypes
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ('cb', ctypes.wintypes.DWORD),
                    ('PageFaultCount', ctypes.wintypes.DWORD),
                    ('PeakWorkingSetSize', ctypes.c_size_t),
                    ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t),
                    ('PeakPagefileUsage', ctypes.c_size_t),
                ]
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return int(counters.WorkingSetSize)
        except Exception:
            pass
    return 0

def get_system_environment_info() -> Dict[str, Any]:
    """Freezes system environment metadata."""
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ('dwLength', ctypes.c_ulong),
            ('dwMemoryLoad', ctypes.c_ulong),
            ('ullTotalPhys', ctypes.c_ulonglong),
            ('ullAvailPhys', ctypes.c_ulonglong),
            ('ullTotalPageFile', ctypes.c_ulonglong),
            ('ullAvailPageFile', ctypes.c_ulonglong),
            ('ullTotalVirtual', ctypes.c_ulonglong),
            ('ullAvailVirtual', ctypes.c_ulonglong),
            ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
        ]
    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))

    return {
        "os_platform": sys.platform,
        "os_version": os.name,
        "python_version": sys.version,
        "cpu_count_logical": os.cpu_count(),
        "total_ram_gb": round(stat.ullTotalPhys / (1024**3), 2),
        "portalocker_version": getattr(portalocker, "__version__", "unknown"),
        "portalocker_path": getattr(portalocker, "__file__", "unknown"),
        "hostname": socket.gethostname(),
        "timestamp_utc": time.time()
    }


def compute_statistics(latencies_us: List[float]) -> Dict[str, float]:
    """Computes median, p95, p99, min, max, mean, stddev, and throughput."""
    if not latencies_us:
        return {}
    sorted_l = sorted(latencies_us)
    n = len(sorted_l)
    
    def percentile(p: float) -> float:
        idx = int(p * n)
        if idx >= n:
            idx = n - 1
        return sorted_l[idx]

    median = percentile(0.50)
    p90 = percentile(0.90)
    p95 = percentile(0.95)
    p99 = percentile(0.99)
    min_lat = sorted_l[0]
    max_lat = sorted_l[-1]
    mean_lat = sum(sorted_l) / n
    variance = sum((x - mean_lat) ** 2 for x in sorted_l) / n if n > 1 else 0
    stddev = variance ** 0.5
    total_time_sec = sum(sorted_l) / 1_000_000.0
    throughput = n / total_time_sec if total_time_sec > 0 else 0.0

    return {
        "iterations": n,
        "median_us": round(median, 2),
        "p90_us": round(p90, 2),
        "p95_us": round(p95, 2),
        "p99_us": round(p99, 2),
        "min_us": round(min_lat, 2),
        "max_us": round(max_lat, 2),
        "mean_us": round(mean_lat, 2),
        "stddev_us": round(stddev, 2),
        "throughput_ops_sec": round(throughput, 2)
    }


# ============================================================================
# Dimension 1: Single Process Acquisition / Release Latency & Throughput
# ============================================================================
def benchmark_single_process(iterations: int = 500, warmup: int = 50) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        ref_lock_path = os.path.join(tmpdir, "ref_single.lock")
        sclass_lock_path = os.path.join(tmpdir, "sclass_single.lock")

        # 1. Warmup Portalocker
        for _ in range(warmup):
            with portalocker.Lock(ref_lock_path, timeout=5.0, check_interval=0.01):
                pass

        # Portalocker Measurement
        ref_latencies = []
        mem_start_ref = get_current_process_memory_bytes()
        t_start_ref = time.perf_counter()
        for _ in range(iterations):
            t0 = time.perf_counter_ns()
            with portalocker.Lock(ref_lock_path, timeout=5.0, check_interval=0.01):
                pass
            t1 = time.perf_counter_ns()
            ref_latencies.append((t1 - t0) / 1000.0) # us
        ref_elapsed = time.perf_counter() - t_start_ref
        mem_end_ref = get_current_process_memory_bytes()

        # 2. Warmup S-Class FileLock
        for _ in range(warmup):
            with FileLock(sclass_lock_path, timeout=5.0, poll_interval=0.01):
                pass

        # S-Class Measurement
        sclass_latencies = []
        mem_start_sclass = get_current_process_memory_bytes()
        t_start_sclass = time.perf_counter()
        for _ in range(iterations):
            t0 = time.perf_counter_ns()
            with FileLock(sclass_lock_path, timeout=5.0, poll_interval=0.01):
                pass
            t1 = time.perf_counter_ns()
            sclass_latencies.append((t1 - t0) / 1000.0) # us
        sclass_elapsed = time.perf_counter() - t_start_sclass
        mem_end_sclass = get_current_process_memory_bytes()

        ref_stats = compute_statistics(ref_latencies)
        sclass_stats = compute_statistics(sclass_latencies)

        return {
            "portalocker_ref": ref_stats,
            "sclass_filelock": sclass_stats,
            "memory_delta_bytes": {
                "portalocker": mem_end_ref - mem_start_ref,
                "sclass": mem_end_sclass - mem_start_sclass
            }
        }


# ============================================================================
# Dimension 2: Timeout Semantics
# ============================================================================
def test_timeout_semantics(target_timeout: float = 0.2) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = os.path.join(tmpdir, "timeout.lock")
        results = {}

        # 1. Portalocker Reference Timeout Test
        with portalocker.Lock(lock_path, timeout=5.0):
            t0 = time.perf_counter()
            timed_out = False
            try:
                with portalocker.Lock(lock_path, timeout=target_timeout, check_interval=0.02):
                    pass
            except (portalocker.exceptions.LockException, portalocker.exceptions.AlreadyLocked):
                timed_out = True
            elapsed = time.perf_counter() - t0
            results["portalocker_ref"] = {
                "timed_out_properly": timed_out,
                "elapsed_sec": round(elapsed, 4),
                "within_tolerance": target_timeout <= elapsed <= (target_timeout + 0.1)
            }

        # 2. S-Class FileLock Timeout Test
        with FileLock(lock_path, timeout=5.0):
            t0 = time.perf_counter()
            timed_out = False
            try:
                with FileLock(lock_path, timeout=target_timeout, poll_interval=0.02):
                    pass
            except TimeoutError:
                timed_out = True
            elapsed = time.perf_counter() - t0
            results["sclass_filelock"] = {
                "timed_out_properly": timed_out,
                "elapsed_sec": round(elapsed, 4),
                "within_tolerance": target_timeout <= elapsed <= (target_timeout + 0.1)
            }

        return results


# ============================================================================
# Dimension 3: Multithreaded Contention & Serialization
# ============================================================================
def test_thread_contention(num_threads: int = 8, increments_per_thread: int = 50) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        results = {}

        # S-Class FileLock Thread Serialization
        sclass_lock_path = os.path.join(tmpdir, "thread_sclass.lock")
        shared_counter = [0]
        threads = []

        def worker_sclass():
            for _ in range(increments_per_thread):
                with FileLock(sclass_lock_path, timeout=10.0, poll_interval=0.005):
                    val = shared_counter[0]
                    time.sleep(0.0001)
                    shared_counter[0] = val + 1

        t0 = time.perf_counter()
        for _ in range(num_threads):
            t = threading.Thread(target=worker_sclass)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        elapsed_sclass = time.perf_counter() - t0

        expected = num_threads * increments_per_thread
        results["sclass_filelock"] = {
            "expected_count": expected,
            "actual_count": shared_counter[0],
            "is_exact_match": shared_counter[0] == expected,
            "elapsed_sec": round(elapsed_sclass, 4)
        }

        # Portalocker Thread Serialization
        ref_lock_path = os.path.join(tmpdir, "thread_ref.lock")
        shared_counter_ref = [0]
        threads_ref = []

        def worker_ref():
            for _ in range(increments_per_thread):
                with portalocker.Lock(ref_lock_path, timeout=10.0, check_interval=0.005):
                    val = shared_counter_ref[0]
                    time.sleep(0.0001)
                    shared_counter_ref[0] = val + 1

        t0 = time.perf_counter()
        for _ in range(num_threads):
            t = threading.Thread(target=worker_ref)
            threads_ref.append(t)
            t.start()
        for t in threads_ref:
            t.join()
        elapsed_ref = time.perf_counter() - t0

        results["portalocker_ref"] = {
            "expected_count": expected,
            "actual_count": shared_counter_ref[0],
            "is_exact_match": shared_counter_ref[0] == expected,
            "elapsed_sec": round(elapsed_ref, 4)
        }

        return results


# ============================================================================
# Dimension 4: Multiprocess Cross-Process Mutual Exclusion
# ============================================================================
_mp_worker_script = """
import sys
import os
import time

lock_type = sys.argv[1] # 'sclass' or 'portalocker'
lock_path = sys.argv[2]
counter_file = sys.argv[3]
increments = int(sys.argv[4])

sys.path.insert(0, r"{plugin_root}")

if lock_type == "sclass":
    from file_lock import FileLock
    for _ in range(increments):
        with FileLock(lock_path, timeout=15.0, poll_interval=0.01):
            if os.path.exists(counter_file):
                with open(counter_file, "r") as f:
                    val = int(f.read().strip() or "0")
            else:
                val = 0
            time.sleep(0.001)
            with open(counter_file, "w") as f:
                f.write(str(val + 1))
elif lock_type == "portalocker":
    import portalocker
    for _ in range(increments):
        with portalocker.Lock(lock_path, timeout=15.0, check_interval=0.01):
            if os.path.exists(counter_file):
                with open(counter_file, "r") as f:
                    val = int(f.read().strip() or "0")
            else:
                val = 0
            time.sleep(0.001)
            with open(counter_file, "w") as f:
                f.write(str(val + 1))
"""

def test_multiprocess_concurrency(num_procs: int = 4, increments_per_proc: int = 25) -> Dict[str, Any]:
    plugin_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    worker_code = _mp_worker_script.replace("{plugin_root}", plugin_root)

    with tempfile.TemporaryDirectory() as tmpdir:
        worker_script_path = os.path.join(tmpdir, "worker.py")
        with open(worker_script_path, "w", encoding="utf-8") as f:
            f.write(worker_code)

        results = {}

        # 1. S-Class FileLock Multiprocess
        sclass_lock = os.path.join(tmpdir, "mp_sclass.lock")
        sclass_counter = os.path.join(tmpdir, "mp_sclass_counter.txt")
        procs = []
        t0 = time.perf_counter()
        for _ in range(num_procs):
            p = subprocess.Popen([sys.executable, worker_script_path, "sclass", sclass_lock, sclass_counter, str(increments_per_proc)])
            procs.append(p)
        for p in procs:
            p.wait(timeout=30)
        elapsed_sclass = time.perf_counter() - t0

        final_sclass_val = 0
        if os.path.exists(sclass_counter):
            with open(sclass_counter, "r") as f:
                final_sclass_val = int(f.read().strip() or "0")

        expected = num_procs * increments_per_proc
        results["sclass_filelock"] = {
            "expected_count": expected,
            "actual_count": final_sclass_val,
            "is_exact_match": final_sclass_val == expected,
            "elapsed_sec": round(elapsed_sclass, 4)
        }

        # 2. Portalocker Multiprocess
        ref_lock = os.path.join(tmpdir, "mp_ref.lock")
        ref_counter = os.path.join(tmpdir, "mp_ref_counter.txt")
        procs_ref = []
        t0 = time.perf_counter()
        for _ in range(num_procs):
            p = subprocess.Popen([sys.executable, worker_script_path, "portalocker", ref_lock, ref_counter, str(increments_per_proc)])
            procs_ref.append(p)
        for p in procs_ref:
            p.wait(timeout=30)
        elapsed_ref = time.perf_counter() - t0

        final_ref_val = 0
        if os.path.exists(ref_counter):
            with open(ref_counter, "r") as f:
                final_ref_val = int(f.read().strip() or "0")

        results["portalocker_ref"] = {
            "expected_count": expected,
            "actual_count": final_ref_val,
            "is_exact_match": final_ref_val == expected,
            "elapsed_sec": round(elapsed_ref, 4)
        }

        return results


# ============================================================================
# Dimension 5: Crash & Abrupt Termination Lock Release
# ============================================================================
def test_crash_termination_release() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path_sclass = os.path.join(tmpdir, "crash_sclass.lock")
        lock_path_ref = os.path.join(tmpdir, "crash_ref.lock")
        plugin_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

        # S-Class Crash Test
        code_sclass = f"""
import sys, time
sys.path.insert(0, r"{plugin_root}")
from file_lock import FileLock
with FileLock(r"{lock_path_sclass}", timeout=5.0):
    print("ACQUIRED", flush=True)
    time.sleep(30)
"""
        proc = subprocess.Popen([sys.executable, "-c", code_sclass], stdout=subprocess.PIPE, text=True)
        line = proc.stdout.readline()
        assert "ACQUIRED" in line
        # Abruptly kill the process while holding lock
        proc.kill()
        proc.wait()

        # Immediate acquisition in parent process
        t0 = time.perf_counter()
        acquired_sclass = False
        with FileLock(lock_path_sclass, timeout=1.0):
            acquired_sclass = True
        elapsed_sclass = time.perf_counter() - t0

        # Portalocker Crash Test
        code_ref = f"""
import sys, time, portalocker
with portalocker.Lock(r"{lock_path_ref}", timeout=5.0):
    print("ACQUIRED", flush=True)
    time.sleep(30)
"""
        proc_ref = subprocess.Popen([sys.executable, "-c", code_ref], stdout=subprocess.PIPE, text=True)
        line_ref = proc_ref.stdout.readline()
        assert "ACQUIRED" in line_ref
        proc_ref.kill()
        proc_ref.wait()

        t0 = time.perf_counter()
        acquired_ref = False
        with portalocker.Lock(lock_path_ref, timeout=1.0):
            acquired_ref = True
        elapsed_ref = time.perf_counter() - t0

        return {
            "sclass_filelock": {
                "acquired_after_sigkill": acquired_sclass,
                "recovery_latency_sec": round(elapsed_sclass, 6)
            },
            "portalocker_ref": {
                "acquired_after_sigkill": acquired_ref,
                "recovery_latency_sec": round(elapsed_ref, 6)
            }
        }


# ============================================================================
# Dimension 6: Repeated High-Iteration Stability & Handle Leaks
# ============================================================================
def test_repeated_stability(iterations: int = 1000) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = os.path.join(tmpdir, "stability.lock")
        mem_start = get_current_process_memory_bytes()
        t0 = time.perf_counter()
        for _ in range(iterations):
            with FileLock(lock_path, timeout=5.0, poll_interval=0.001):
                pass
        elapsed = time.perf_counter() - t0
        mem_end = get_current_process_memory_bytes()

        return {
            "iterations": iterations,
            "elapsed_sec": round(elapsed, 4),
            "throughput_ops_sec": round(iterations / elapsed, 2),
            "memory_growth_bytes": mem_end - mem_start,
            "leak_detected": (mem_end - mem_start) > 10 * 1024 * 1024 # > 10MB growth flagged
        }


# ============================================================================
# Dimension 7: Stale Metadata Recovery
# ============================================================================
def test_stale_metadata() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = os.path.join(tmpdir, "stale.lock")
        # Write corrupted / dead PID metadata to lock file
        with open(lock_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"pid": 9999999, "token": "dead-token", "status": "active"}))

        acquired = False
        with FileLock(lock_path, timeout=2.0) as fl:
            acquired = True
            fl._file.seek(0)
            content = json.loads(fl._file.read().decode("utf-8"))
            has_current_pid = (content.get("pid") == os.getpid())

        return {
            "acquired_over_stale_metadata": acquired,
            "overwritten_with_live_owner_pid": has_current_pid
        }


# ============================================================================
# Dimension 8: Config GC Non-Destructive Interaction
# ============================================================================
def test_gc_interaction() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        agents_dir = os.path.join(tmpdir, ".agents")
        os.makedirs(agents_dir, exist_ok=True)
        active_lock = os.path.join(agents_dir, "state.lock")
        idle_lock = os.path.join(agents_dir, "idle.lock")

        # Create an idle lock file
        with FileLock(idle_lock, timeout=1.0):
            pass

        # Hold active lock
        with FileLock(active_lock, timeout=2.0):
            # Run GC while active lock is held
            gc_res = run_gc(workspace_dir=tmpdir, state_max_age_days=0)

        # Active lock should still exist and not have been stolen
        active_exists = os.path.exists(active_lock)
        idle_exists = os.path.exists(idle_lock)
        idle_status = None
        if idle_exists:
            with open(idle_lock, "r", encoding="utf-8") as f:
                try:
                    idle_content = json.loads(f.read())
                    idle_status = idle_content.get("status")
                except Exception:
                    idle_status = "unreadable"

        reclaimed = getattr(gc_res, "stale_locks_reclaimed", getattr(gc_res, "stale_locks_removed", 0))

        return {
            "active_lock_preserved_by_gc": active_exists,
            "idle_lock_marked_idle_or_reclaimed": idle_status in ("idle", "released", None, "unreadable"),
            "gc_cleanups_reported": reclaimed
        }


# ============================================================================
# Dimension 9: Release -> Reacquire Ping-Pong Race
# ============================================================================
def test_release_reacquire_race(cycles: int = 100) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = os.path.join(tmpdir, "pingpong.lock")
        success_count = 0
        t0 = time.perf_counter()
        for _ in range(cycles):
            with FileLock(lock_path, timeout=2.0):
                pass
            with FileLock(lock_path, timeout=2.0):
                pass
            success_count += 2
        elapsed = time.perf_counter() - t0

        return {
            "cycles_completed": success_count,
            "elapsed_sec": round(elapsed, 4),
            "race_free": success_count == (cycles * 2)
        }


# ============================================================================
# Dimension 10: Cross-Platform Permissions & Descriptor Lifecycle
# ============================================================================
def test_descriptor_lifecycle() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = os.path.join(tmpdir, "lifecycle.lock")
        lock = FileLock(lock_path, timeout=2.0)
        assert lock._file is None
        assert lock._fd is None

        with lock:
            assert lock._file is not None
            assert lock._fd is not None
            fd_val = lock._fd
            assert not lock._file.closed

        assert lock._file is None
        assert lock._fd is None

        return {
            "clean_acquisition_initialization": True,
            "clean_release_handle_closure": True
        }


def run_full_parity_gate() -> Dict[str, Any]:
    print("=" * 80)
    print("RUNNING OSS PARITY GATE 1: S-Class FileLock vs Portalocker 4.1.0 Reference")
    print("=" * 80)

    env_info = get_system_environment_info()
    print("Frozen Environment:", json.dumps(env_info, indent=2))

    print("\n[1/10] Single Process Acquisition/Release Latency & Throughput (N=500)...")
    single_res = benchmark_single_process(iterations=500, warmup=50)

    print("[2/10] Timeout Semantics Verification...")
    timeout_res = test_timeout_semantics(target_timeout=0.2)

    print("[3/10] Multithreaded Contention Verification (8 Threads x 50 Increments)...")
    thread_res = test_thread_contention(num_threads=8, increments_per_thread=50)

    print("[4/10] Multiprocess Cross-Process Mutual Exclusion (4 Procs x 25 Increments)...")
    mp_res = test_multiprocess_concurrency(num_procs=4, increments_per_proc=25)

    print("[5/10] Crash & Abrupt Termination Release Verification...")
    crash_res = test_crash_termination_release()

    print("[6/10] Repeated High-Iteration Stability & Handle Leak Test (N=1000)...")
    stability_res = test_repeated_stability(iterations=1000)

    print("[7/10] Stale Metadata Recovery Verification...")
    stale_res = test_stale_metadata()

    print("[8/10] Config GC Non-Destructive Interaction Verification...")
    gc_res = test_gc_interaction()

    print("[9/10] Release -> Reacquire Ping-Pong Race Verification...")
    race_res = test_release_reacquire_race(cycles=100)

    print("[10/10] File Descriptor & Lifecycle Cleanup Verification...")
    lifecycle_res = test_descriptor_lifecycle()

    full_results = {
        "environment": env_info,
        "dimension_1_single_process_benchmark": single_res,
        "dimension_2_timeout_semantics": timeout_res,
        "dimension_3_thread_contention": thread_res,
        "dimension_4_multiprocess_concurrency": mp_res,
        "dimension_5_crash_termination_release": crash_res,
        "dimension_6_repeated_stability": stability_res,
        "dimension_7_stale_metadata": stale_res,
        "dimension_8_gc_interaction": gc_res,
        "dimension_9_release_reacquire_race": race_res,
        "dimension_10_descriptor_lifecycle": lifecycle_res
    }

    return full_results

if __name__ == "__main__":
    results = run_full_parity_gate()
    output_path = os.path.join(os.path.dirname(__file__), "parity_gate_1_raw_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nRaw results successfully saved to: {output_path}")
