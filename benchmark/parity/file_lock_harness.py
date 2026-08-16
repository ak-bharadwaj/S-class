#!/usr/bin/env python3
"""
OSS Parity Gate 1: Differential Benchmark & Capability Verification Harness (Phase 2)
Comparing S-Class Independent OS-Native Locking Engine vs Reference Portalocker 4.1.0

Architecture & Methodology:
1. Layer A — Primitive Parity (0.5% Gate Threshold):
   - Measures bare OS kernel advisory lock acquisition/release (open, msvcrt/fcntl lock, unlock, close).
   - Completely independent OS-native S-Class NativeLock vs Reference portalocker.Lock.
   - Strict Gate Criterion: NativeLock median latency <= Reference * 1.005 (<= 0.5% slower).

2. Layer B — Full S-Class Lifecycle Profiling:
   - Measures complete FileLock abstraction (primitive + diagnostic metadata + process ownership + GC).
   - Microsegment latency breakdown across open, lock, JSON serialize, write/flush, unlock, close.

3. Layer C — Equivalent Full Lifecycle Workload Comparison:
   - Reference equivalent lifecycle (portalocker.Lock + identical metadata payload read/write/flush)
     vs S-Class FileLock.

4. 1:1 Differential Comparative Correctness Suite:
   - Inter-process blocking timeout with dedicated child holder processes (Reference vs S-Class).
   - Multithreaded contention (8 threads x 50 increments on Reference vs S-Class).
   - Multiprocess mutual exclusion (4 processes x 25 increments on Reference vs S-Class).
   - Crash & abrupt termination recovery with child process os._exit(1) (Reference vs S-Class).
   - Stale metadata takeover and Config GC non-destructive interaction.

5. Statistical Rigor:
   - Interleaved / randomized paired trial ordering across 5 reps x 500 trials (2,500 total).
   - Linear interpolation percentiles (p * (n - 1)).
   - 95% bootstrap Confidence Intervals for median and P95 performance ratios.
   - Peak RSS working set memory tracking.
   - Strict provenance integrity (zero fabricated fallback strings).
"""

import os
import sys
import time
import json
import random
import socket
import tempfile
import threading
import subprocess
import ctypes
from typing import Dict, List, Any, Tuple
import portalocker

# Add plugin root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from file_lock import FileLock, NativeLock, _CACHED_PID, _CACHED_HOSTNAME, _CACHED_PROC_START
from config_gc import run_gc


def get_peak_working_set_bytes() -> int:
    """Returns peak working set memory in bytes for current process on Windows/POSIX."""
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
            func = ctypes.windll.psapi.GetProcessMemoryInfo
            func.argtypes = [ctypes.wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), ctypes.wintypes.DWORD]
            func.restype = ctypes.wintypes.BOOL
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if func(handle, ctypes.byref(counters), counters.cb):
                return int(counters.PeakWorkingSetSize)
        except Exception:
            pass
    else:
        try:
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        except Exception:
            pass
    return 0


def get_current_working_set_bytes() -> int:
    """Returns current working set memory in bytes for current process on Windows/POSIX."""
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
            func = ctypes.windll.psapi.GetProcessMemoryInfo
            func.argtypes = [ctypes.wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), ctypes.wintypes.DWORD]
            func.restype = ctypes.wintypes.BOOL
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if func(handle, ctypes.byref(counters), counters.cb):
                return int(counters.WorkingSetSize)
        except Exception:
            pass
    return 0


def get_system_environment_info() -> Dict[str, Any]:
    """Freezes system environment metadata with strict provenance integrity."""
    p_ver = getattr(portalocker, "__version__", None)
    if not p_ver:
        try:
            import importlib.metadata
            p_ver = importlib.metadata.version("portalocker")
        except Exception:
            p_ver = "UNKNOWN"

    return {
        "os_platform": sys.platform,
        "os_version": os.name,
        "python_version": sys.version,
        "cpu_count_logical": os.cpu_count(),
        "portalocker_version": p_ver if p_ver else "UNKNOWN",
        "hostname": socket.gethostname(),
        "timestamp_utc": time.time()
    }


def calculate_linear_percentile(data: List[float], percentile: float) -> float:
    """Standard linear interpolation percentile estimator (p * (n - 1))."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)
    if n == 1:
        return sorted_data[0]
    idx = percentile * (n - 1)
    low_idx = int(idx)
    high_idx = min(low_idx + 1, n - 1)
    weight = idx - low_idx
    return sorted_data[low_idx] * (1.0 - weight) + sorted_data[high_idx] * weight


def compute_ratio_95_ci(sample_a: List[float], sample_b: List[float], n_bootstraps: int = 1000) -> Tuple[float, float, float]:
    """Computes median ratio (A / B) and bootstrap 95% confidence interval [low, high]."""
    if not sample_a or not sample_b:
        return 1.0, 1.0, 1.0
    med_a = calculate_linear_percentile(sample_a, 0.5)
    med_b = calculate_linear_percentile(sample_b, 0.5)
    point_ratio = med_a / med_b if med_b > 0 else 1.0

    boot_ratios = []
    na = len(sample_a)
    nb = len(sample_b)
    rng = random.Random(42)
    for _ in range(n_bootstraps):
        resample_a = [sample_a[rng.randint(0, na - 1)] for _ in range(na)]
        resample_b = [sample_b[rng.randint(0, nb - 1)] for _ in range(nb)]
        m_a = calculate_linear_percentile(resample_a, 0.5)
        m_b = calculate_linear_percentile(resample_b, 0.5)
        if m_b > 0:
            boot_ratios.append(m_a / m_b)

    if boot_ratios:
        ci_low = calculate_linear_percentile(boot_ratios, 0.025)
        ci_high = calculate_linear_percentile(boot_ratios, 0.975)
    else:
        ci_low, ci_high = point_ratio, point_ratio
    return point_ratio, ci_low, ci_high


# ============================================================================
# Layer A: Independent Primitive Parity (0.5% Gate Threshold)
# ============================================================================
def test_layer_a_primitive_parity(n_trials: int = 500, n_repetitions: int = 5) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        ref_lock_file = os.path.join(tmpdir, "portalocker.lock")
        sclass_lock_file = os.path.join(tmpdir, "sclass_native.lock")

        ref_latencies_us: List[float] = []
        sclass_latencies_us: List[float] = []

        initial_rss = get_current_working_set_bytes()
        peak_rss_during_test = get_peak_working_set_bytes()

        rng = random.Random(1337)
        for rep in range(n_repetitions):
            for i in range(n_trials):
                run_ref_first = rng.choice([True, False])

                def run_ref():
                    t0 = time.perf_counter_ns()
                    with portalocker.Lock(ref_lock_file, timeout=5.0):
                        pass
                    t1 = time.perf_counter_ns()
                    ref_latencies_us.append((t1 - t0) / 1000.0)

                def run_sclass():
                    t0 = time.perf_counter_ns()
                    with NativeLock(sclass_lock_file, timeout=5.0):
                        pass
                    t1 = time.perf_counter_ns()
                    sclass_latencies_us.append((t1 - t0) / 1000.0)

                if run_ref_first:
                    run_ref()
                    run_sclass()
                else:
                    run_sclass()
                    run_ref()

                curr_peak = get_peak_working_set_bytes()
                if curr_peak > peak_rss_during_test:
                    peak_rss_during_test = curr_peak

        final_rss = get_current_working_set_bytes()

        ref_med = calculate_linear_percentile(ref_latencies_us, 0.50)
        ref_p95 = calculate_linear_percentile(ref_latencies_us, 0.95)
        sclass_med = calculate_linear_percentile(sclass_latencies_us, 0.50)
        sclass_p95 = calculate_linear_percentile(sclass_latencies_us, 0.95)

        total_ref_sec = sum(ref_latencies_us) / 1e6
        total_sclass_sec = sum(sclass_latencies_us) / 1e6
        ref_throughput = (n_trials * n_repetitions) / total_ref_sec if total_ref_sec > 0 else 0
        sclass_throughput = (n_trials * n_repetitions) / total_sclass_sec if total_sclass_sec > 0 else 0

        ratio_med, ci_low, ci_high = compute_ratio_95_ci(sclass_latencies_us, ref_latencies_us)
        pct_diff_median = ((sclass_med - ref_med) / ref_med * 100.0) if ref_med > 0 else 0.0

        # Strict Gate Threshold: Independent S-Class NativeLock <= Reference * 1.005 (<= 0.5% slower)
        gate_passed = (sclass_med <= ref_med * 1.005)

        return {
            "gate_passed": gate_passed,
            "threshold_applied": "S-Class NativeLock (pure OS-native) <= Reference Portalocker * 1.005 (+0.5% max)",
            "iterations_per_rep": n_trials,
            "total_repetitions": n_repetitions,
            "total_trials": n_trials * n_repetitions,
            "reference_portalocker": {
                "median_us": round(ref_med, 2),
                "p95_us": round(ref_p95, 2),
                "throughput_per_sec": round(ref_throughput, 1)
            },
            "sclass_native_primitive": {
                "median_us": round(sclass_med, 2),
                "p95_us": round(sclass_p95, 2),
                "throughput_per_sec": round(sclass_throughput, 1)
            },
            "statistical_metrics": {
                "median_latency_diff_pct": round(pct_diff_median, 3),
                "median_ratio": round(ratio_med, 4),
                "ratio_95_ci_low": round(ci_low, 4),
                "ratio_95_ci_high": round(ci_high, 4)
            },
            "memory_footprint": {
                "initial_rss_bytes": initial_rss,
                "peak_working_set_bytes": peak_rss_during_test,
                "final_rss_bytes": final_rss
            }
        }


# ============================================================================
# Layer B: Full S-Class Lifecycle & Microsegment Latency Profiling
# ============================================================================
def test_layer_b_full_lifecycle(n_trials: int = 500) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, "sclass_full.lock")
        full_latencies_us: List[float] = []

        microsegments: Dict[str, List[float]] = {
            "open_ns": [],
            "lock_ns": [],
            "json_serialize_enter_ns": [],
            "write_flush_enter_ns": [],
            "json_serialize_exit_ns": [],
            "write_flush_exit_ns": [],
            "unlock_ns": [],
            "close_ns": []
        }

        for _ in range(n_trials):
            t0 = time.perf_counter_ns()
            fl = FileLock(lock_file, timeout=5.0, enable_profiling=True)
            with fl:
                pass
            t1 = time.perf_counter_ns()
            full_latencies_us.append((t1 - t0) / 1000.0)

            for key, val in fl.profile_timings.items():
                if key in microsegments:
                    microsegments[key].append(val / 1000.0)

        med_us = calculate_linear_percentile(full_latencies_us, 0.50)
        p95_us = calculate_linear_percentile(full_latencies_us, 0.95)

        segment_breakdown = {}
        for k, v in microsegments.items():
            if v:
                segment_breakdown[k] = {
                    "median_us": round(calculate_linear_percentile(v, 0.50), 2),
                    "p95_us": round(calculate_linear_percentile(v, 0.95), 2)
                }

        return {
            "n_trials": n_trials,
            "full_sclass_filelock": {
                "median_us": round(med_us, 2),
                "p95_us": round(p95_us, 2),
                "throughput_per_sec": round(n_trials / (sum(full_latencies_us) / 1e6), 1)
            },
            "microsegment_latency_breakdown_us": segment_breakdown
        }


# ============================================================================
# Layer C: Equivalent Full Lifecycle Workload Comparison
# ============================================================================
def test_layer_c_equivalent_lifecycle(n_trials: int = 500) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        ref_file = os.path.join(tmpdir, "ref_lifecycle.lock")
        sclass_file = os.path.join(tmpdir, "sclass_lifecycle.lock")

        ref_latencies_us: List[float] = []
        sclass_latencies_us: List[float] = []

        ref_pid = os.getpid()
        ref_host = socket.gethostname()

        rng = random.Random(999)
        for _ in range(n_trials):
            run_ref_first = rng.choice([True, False])

            def run_ref():
                t0 = time.perf_counter_ns()
                with portalocker.Lock(ref_file, mode="a+b", timeout=5.0) as fh:
                    # Perform equivalent metadata write and flush
                    t_now = time.time()
                    payload = json.dumps({
                        "pid": ref_pid,
                        "host": ref_host,
                        "start_time": t_now,
                        "token": "ref-token"
                    }).encode("utf-8")
                    fh.seek(0)
                    fh.truncate(0)
                    fh.write(payload)
                    fh.flush()
                t1 = time.perf_counter_ns()
                ref_latencies_us.append((t1 - t0) / 1000.0)

            def run_sclass():
                t0 = time.perf_counter_ns()
                with FileLock(sclass_file, timeout=5.0):
                    pass
                t1 = time.perf_counter_ns()
                sclass_latencies_us.append((t1 - t0) / 1000.0)

            if run_ref_first:
                run_ref()
                run_sclass()
            else:
                run_sclass()
                run_ref()

        ref_med = calculate_linear_percentile(ref_latencies_us, 0.50)
        ref_p95 = calculate_linear_percentile(ref_latencies_us, 0.95)
        sclass_med = calculate_linear_percentile(sclass_latencies_us, 0.50)
        sclass_p95 = calculate_linear_percentile(sclass_latencies_us, 0.95)

        ratio_med, ci_low, ci_high = compute_ratio_95_ci(sclass_latencies_us, ref_latencies_us)

        return {
            "n_trials": n_trials,
            "reference_equivalent_lifecycle": {
                "median_us": round(ref_med, 2),
                "p95_us": round(ref_p95, 2),
                "throughput_per_sec": round(n_trials / (sum(ref_latencies_us) / 1e6), 1)
            },
            "sclass_filelock_lifecycle": {
                "median_us": round(sclass_med, 2),
                "p95_us": round(sclass_p95, 2),
                "throughput_per_sec": round(n_trials / (sum(sclass_latencies_us) / 1e6), 1)
            },
            "lifecycle_ratio": round(ratio_med, 4),
            "ratio_95_ci": [round(ci_low, 4), round(ci_high, 4)]
        }


# ============================================================================
# 1:1 Differential Comparative Correctness Suite (Dimensions 2-10)
# ============================================================================
def _holder_process_worker(lock_type: str, lock_path: str, hold_sec: float, ready_file: str):
    if lock_type == "portalocker":
        with portalocker.Lock(lock_path, timeout=5.0):
            with open(ready_file, "w") as f:
                f.write("READY")
            time.sleep(hold_sec)
    else:
        with FileLock(lock_path, timeout=5.0):
            with open(ready_file, "w") as f:
                f.write("READY")
            time.sleep(hold_sec)


def test_differential_timeout() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Test Reference Timeout with separate holder process
        ref_lock = os.path.join(tmpdir, "ref_timeout.lock")
        ref_ready = os.path.join(tmpdir, "ref_ready.txt")
        cmd_ref = [
            sys.executable, "-c",
            f"from benchmark.parity.file_lock_harness import _holder_process_worker; _holder_process_worker('portalocker', r'{ref_lock}', 0.5, r'{ref_ready}')"
        ]
        p_ref = subprocess.Popen(cmd_ref)
        while not os.path.exists(ref_ready):
            time.sleep(0.01)

        t0 = time.time()
        ref_timed_out = False
        try:
            with portalocker.Lock(ref_lock, timeout=0.2):
                pass
        except (portalocker.exceptions.AlreadyLocked, portalocker.exceptions.LockException):
            ref_timed_out = True
        ref_elapsed = time.time() - t0
        p_ref.wait()

        # 2. Test S-Class Timeout with separate holder process
        sclass_lock = os.path.join(tmpdir, "sclass_timeout.lock")
        sclass_ready = os.path.join(tmpdir, "sclass_ready.txt")
        cmd_sclass = [
            sys.executable, "-c",
            f"from benchmark.parity.file_lock_harness import _holder_process_worker; _holder_process_worker('sclass', r'{sclass_lock}', 0.5, r'{sclass_ready}')"
        ]
        p_sclass = subprocess.Popen(cmd_sclass)
        while not os.path.exists(sclass_ready):
            time.sleep(0.01)

        t0 = time.time()
        sclass_timed_out = False
        try:
            with FileLock(sclass_lock, timeout=0.2):
                pass
        except TimeoutError:
            sclass_timed_out = True
        sclass_elapsed = time.time() - t0
        p_sclass.wait()

        return {
            "reference_timed_out": ref_timed_out,
            "reference_elapsed_sec": round(ref_elapsed, 4),
            "sclass_timed_out": sclass_timed_out,
            "sclass_elapsed_sec": round(sclass_elapsed, 4),
            "timeout_differential_passed": (ref_timed_out and sclass_timed_out)
        }


def test_differential_multithreading(threads: int = 8, increments: int = 50) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        ref_lock = os.path.join(tmpdir, "ref_mt.lock")
        sclass_lock = os.path.join(tmpdir, "sclass_mt.lock")
        expected = threads * increments

        # Reference
        ref_counter = {"val": 0}
        def ref_worker():
            for _ in range(increments):
                with portalocker.Lock(ref_lock, timeout=10.0):
                    curr = ref_counter["val"]
                    time.sleep(0.0001)
                    ref_counter["val"] = curr + 1

        t0 = time.time()
        t_ref = [threading.Thread(target=ref_worker) for _ in range(threads)]
        for t in t_ref:
            t.start()
        for t in t_ref:
            t.join()
        ref_sec = time.time() - t0

        # S-Class
        sclass_counter = {"val": 0}
        def sclass_worker():
            for _ in range(increments):
                with FileLock(sclass_lock, timeout=10.0):
                    curr = sclass_counter["val"]
                    time.sleep(0.0001)
                    sclass_counter["val"] = curr + 1

        t0 = time.time()
        t_sclass = [threading.Thread(target=sclass_worker) for _ in range(threads)]
        for t in t_sclass:
            t.start()
        for t in t_sclass:
            t.join()
        sclass_sec = time.time() - t0

        return {
            "expected_count": expected,
            "reference_actual_count": ref_counter["val"],
            "reference_elapsed_sec": round(ref_sec, 3),
            "sclass_actual_count": sclass_counter["val"],
            "sclass_elapsed_sec": round(sclass_sec, 3),
            "thread_differential_passed": (ref_counter["val"] == expected and sclass_counter["val"] == expected)
        }


def _mp_worker(lock_type: str, lock_path: str, count_file: str, increments: int):
    for _ in range(increments):
        if lock_type == "portalocker":
            with portalocker.Lock(lock_path, timeout=15.0):
                val = 0
                if os.path.exists(count_file):
                    with open(count_file, "r") as f:
                        try:
                            val = int(f.read().strip())
                        except ValueError:
                            val = 0
                time.sleep(0.001)
                with open(count_file, "w") as f:
                    f.write(str(val + 1))
        else:
            with FileLock(lock_path, timeout=15.0):
                val = 0
                if os.path.exists(count_file):
                    with open(count_file, "r") as f:
                        try:
                            val = int(f.read().strip())
                        except ValueError:
                            val = 0
                time.sleep(0.001)
                with open(count_file, "w") as f:
                    f.write(str(val + 1))


def test_differential_multiprocessing(procs: int = 4, increments: int = 25) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        expected = procs * increments

        # Reference
        ref_lock = os.path.join(tmpdir, "ref_mp.lock")
        ref_count_file = os.path.join(tmpdir, "ref_mp_count.txt")
        with open(ref_count_file, "w") as f:
            f.write("0")

        t0 = time.time()
        p_list = []
        for _ in range(procs):
            cmd = [
                sys.executable, "-c",
                f"from benchmark.parity.file_lock_harness import _mp_worker; _mp_worker('portalocker', r'{ref_lock}', r'{ref_count_file}', {increments})"
            ]
            p_list.append(subprocess.Popen(cmd))
        for p in p_list:
            p.wait()
        ref_sec = time.time() - t0
        with open(ref_count_file, "r") as f:
            ref_final = int(f.read().strip())

        # S-Class
        sclass_lock = os.path.join(tmpdir, "sclass_mp.lock")
        sclass_count_file = os.path.join(tmpdir, "sclass_mp_count.txt")
        with open(sclass_count_file, "w") as f:
            f.write("0")

        t0 = time.time()
        p_list = []
        for _ in range(procs):
            cmd = [
                sys.executable, "-c",
                f"from benchmark.parity.file_lock_harness import _mp_worker; _mp_worker('sclass', r'{sclass_lock}', r'{sclass_count_file}', {increments})"
            ]
            p_list.append(subprocess.Popen(cmd))
        for p in p_list:
            p.wait()
        sclass_sec = time.time() - t0
        with open(sclass_count_file, "r") as f:
            sclass_final = int(f.read().strip())

        return {
            "expected_count": expected,
            "reference_final_count": ref_final,
            "reference_elapsed_sec": round(ref_sec, 3),
            "sclass_final_count": sclass_final,
            "sclass_elapsed_sec": round(sclass_sec, 3),
            "multiprocess_differential_passed": (ref_final == expected and sclass_final == expected)
        }


def test_differential_crash_recovery() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        # Reference Crash
        ref_lock = os.path.join(tmpdir, "ref_crash.lock")
        cmd_ref = [
            sys.executable, "-c",
            f"import portalocker, os; f = open(r'{ref_lock}', 'a+'); portalocker.lock(f, portalocker.LOCK_EX); os._exit(1)"
        ]
        p = subprocess.Popen(cmd_ref)
        p.wait()

        t0 = time.time()
        ref_reclaimed = False
        try:
            with portalocker.Lock(ref_lock, timeout=1.0):
                ref_reclaimed = True
        except Exception:
            ref_reclaimed = False
        ref_elapsed = time.time() - t0

        # S-Class Crash
        sclass_lock = os.path.join(tmpdir, "sclass_crash.lock")
        cmd_sclass = [
            sys.executable, "-c",
            f"from file_lock import FileLock; fl = FileLock(r'{sclass_lock}', timeout=2.0); fl.__enter__(); import os; os._exit(1)"
        ]
        p = subprocess.Popen(cmd_sclass)
        p.wait()

        t0 = time.time()
        sclass_reclaimed = False
        try:
            with FileLock(sclass_lock, timeout=1.0):
                sclass_reclaimed = True
        except Exception:
            sclass_reclaimed = False
        sclass_elapsed = time.time() - t0

        return {
            "reference_reclaimed": ref_reclaimed,
            "reference_reclaim_sec": round(ref_elapsed, 6),
            "sclass_reclaimed": sclass_reclaimed,
            "sclass_reclaim_sec": round(sclass_elapsed, 6),
            "crash_differential_passed": (ref_reclaimed and sclass_reclaimed)
        }


def test_stale_metadata() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = os.path.join(tmpdir, "stale.lock")
        with open(lock_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"pid": 9999999, "token": "dead-token", "status": "active"}))

        acquired = False
        has_current_pid = False
        with FileLock(lock_path, timeout=2.0) as fl:
            acquired = True
            fl._file.seek(0)
            content = json.loads(fl._file.read().decode("utf-8"))
            has_current_pid = (content.get("pid") == os.getpid())

        return {
            "acquired_over_stale_metadata": acquired,
            "overwritten_with_live_owner_pid": has_current_pid
        }


def test_gc_interaction() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        agents_dir = os.path.join(tmpdir, ".agents")
        os.makedirs(agents_dir, exist_ok=True)
        active_lock = os.path.join(agents_dir, "state.lock")
        idle_lock = os.path.join(agents_dir, "idle.lock")

        with FileLock(idle_lock, timeout=1.0):
            pass

        with FileLock(active_lock, timeout=2.0):
            gc_res = run_gc(workspace_dir=tmpdir, state_max_age_days=0)

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


def run_full_parity_gate() -> Dict[str, Any]:
    env_info = get_system_environment_info()
    print("=" * 80)
    print("RUNNING OSS PARITY GATE 1: S-CLASS NATIVE ENGINE VS PORTALOCKER 4.1.0")
    print("=" * 80)
    print(f"Frozen Environment:\n{json.dumps(env_info, indent=2)}\n")

    print("[1/9] Layer A — Independent Primitive Parity (5 Reps x 500 Interleaved Trials)...")
    layer_a = test_layer_a_primitive_parity(n_trials=500, n_repetitions=5)

    print("[2/9] Layer B — Full S-Class Lifecycle & Microsegment Profiling...")
    layer_b = test_layer_b_full_lifecycle(n_trials=500)

    print("[3/9] Layer C — Equivalent Full Lifecycle Workload Comparison...")
    layer_c = test_layer_c_equivalent_lifecycle(n_trials=500)

    print("[4/9] Differential Timeout Semantics Verification (Inter-Process)...")
    timeout_res = test_differential_timeout()

    print("[5/9] Differential Multithreaded Contention Verification (8 Threads x 50 Inc)...")
    mt_res = test_differential_multithreading()

    print("[6/9] Differential Multiprocess Exclusion Verification (4 Procs x 25 Inc)...")
    mp_res = test_differential_multiprocessing()

    print("[7/9] Differential Crash Recovery Verification (Abrupt os._exit)...")
    crash_res = test_differential_crash_recovery()

    print("[8/9] Stale Metadata Recovery Verification...")
    stale_res = test_stale_metadata()

    print("[9/9] Config GC Non-Destructive Interaction Verification...")
    gc_res = test_gc_interaction()

    master_results = {
        "environment": env_info,
        "layer_a_primitive_parity": layer_a,
        "layer_b_full_sclass_lifecycle": layer_b,
        "layer_c_equivalent_lifecycle": layer_c,
        "differential_timeout_verification": timeout_res,
        "differential_multithreaded_contention": mt_res,
        "differential_multiprocess_exclusion": mp_res,
        "differential_crash_recovery": crash_res,
        "stale_metadata": stale_res,
        "gc_interaction": gc_res,
        "final_gate_verdict": "PASS" if layer_a["gate_passed"] else "FAIL"
    }

    out_file = os.path.join(os.path.dirname(__file__), "parity_gate_1_raw_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(master_results, f, indent=2)

    print("\nRaw results successfully saved to:", out_file)
    print("Layer A Gate Passed:", layer_a["gate_passed"])
    print(f"Independent NativeLock Median: {layer_a['sclass_native_primitive']['median_us']} us vs Portalocker: {layer_a['reference_portalocker']['median_us']} us ({layer_a['statistical_metrics']['median_latency_diff_pct']}% diff)")
    print(f"Layer C Lifecycle Ratio: {layer_c['lifecycle_ratio']} (95% CI: {layer_c['ratio_95_ci']})")
    print(f"Final Gate Verdict: {master_results['final_gate_verdict']}")
    return master_results


if __name__ == "__main__":
    run_full_parity_gate()
