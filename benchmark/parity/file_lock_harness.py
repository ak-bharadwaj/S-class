#!/usr/bin/env python3
"""
OSS Parity Gate 1: Differential Benchmark & Capability Verification Harness
Comparing S-Class Locking Engine vs Reference Portalocker 4.1.0

Architecture & Methodology:
1. Layer A — Primitive Parity:
   - Measures bare OS kernel advisory lock acquisition/release (open, lock, unlock, close).
   - Compares S-Class NativeLock vs Reference portalocker.Lock.
   - Strict Gate Criterion: NativeLock median latency <= Reference * 1.005 (<= 0.5% slower).

2. Layer B — Full S-Class Lifecycle:
   - Measures complete FileLock abstraction (primitive + diagnostic metadata + process ownership + GC).
   - Microsegment latency profiling across open, lock, metadata JSON serialization, write/flush, unlock, close.

3. Statistical Rigor:
   - Interleaved / randomized paired trial ordering across multiple independent repetitions to eliminate order/thermal bias.
   - Standard linear interpolation percentile estimation (median, P95).
   - 95% Confidence Intervals (CIs) for median and P95 performance ratios.
   - Peak RSS working set memory measurement.
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
import portalocker.utils

# Add plugin root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from file_lock import FileLock, NativeLock, HAS_PORTALOCKER
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
    """Freezes system environment metadata."""
    return {
        "os_platform": sys.platform,
        "os_version": os.name,
        "python_version": sys.version,
        "cpu_count_logical": os.cpu_count(),
        "portalocker_version": getattr(portalocker, "__version__", "4.1.0"),
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
# Layer A: Primitive Parity (0.5% Gate Threshold)
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

        # Strict Gate Threshold: Primitive S-Class <= Reference * 1.005 (<= 0.5% slower)
        gate_passed = (sclass_med <= ref_med * 1.005)

        return {
            "gate_passed": gate_passed,
            "threshold_applied": "S-Class NativeLock <= Reference Portalocker * 1.005 (+0.5% max)",
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
# Correctness & Contract Verification Suite (Dimensions 2-10)
# ============================================================================
def test_timeout_semantics() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = os.path.join(tmpdir, "timeout.lock")
        t_ref_start = time.time()
        with portalocker.Lock(lock_path, timeout=0.1):
            try:
                with portalocker.Lock(lock_path, timeout=0.2):
                    pass
                ref_timed_out = False
            except (portalocker.exceptions.AlreadyLocked, portalocker.exceptions.LockException):
                ref_timed_out = True
        ref_elapsed = time.time() - t_ref_start

        t_sclass_start = time.time()
        with FileLock(lock_path, timeout=0.1):
            try:
                with FileLock(lock_path, timeout=0.2):
                    pass
                sclass_timed_out = False
            except TimeoutError:
                sclass_timed_out = True
        sclass_elapsed = time.time() - t_sclass_start

        return {
            "ref_timed_out": ref_timed_out,
            "ref_elapsed_sec": round(ref_elapsed, 4),
            "sclass_timed_out": sclass_timed_out,
            "sclass_elapsed_sec": round(sclass_elapsed, 4),
            "timeout_parity": ref_timed_out and sclass_timed_out
        }


def test_multithreaded_contention(threads: int = 8, increments_per_thread: int = 50) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = os.path.join(tmpdir, "mt.lock")
        counter = {"val": 0}

        def worker():
            for _ in range(increments_per_thread):
                with FileLock(lock_path, timeout=10.0):
                    curr = counter["val"]
                    time.sleep(0.0001)
                    counter["val"] = curr + 1

        t0 = time.time()
        t_list = [threading.Thread(target=worker) for _ in range(threads)]
        for t in t_list:
            t.start()
        for t in t_list:
            t.join()
        elapsed = time.time() - t0

        expected = threads * increments_per_thread
        return {
            "expected_count": expected,
            "actual_count": counter["val"],
            "elapsed_sec": round(elapsed, 3),
            "thread_safety_passed": (counter["val"] == expected)
        }


def _proc_worker(lock_path: str, count_file: str, increments: int):
    for _ in range(increments):
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


def test_multiprocess_exclusion(procs: int = 4, increments_per_proc: int = 25) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = os.path.join(tmpdir, "mp.lock")
        count_file = os.path.join(tmpdir, "mp_count.txt")
        with open(count_file, "w") as f:
            f.write("0")

        t0 = time.time()
        p_list = []
        for _ in range(procs):
            cmd = [
                sys.executable, "-c",
                f"from benchmark.parity.file_lock_harness import _proc_worker; _proc_worker(r'{lock_path}', r'{count_file}', {increments_per_proc})"
            ]
            p = subprocess.Popen(cmd)
            p_list.append(p)

        for p in p_list:
            p.wait()
        elapsed = time.time() - t0

        final_val = 0
        with open(count_file, "r") as f:
            final_val = int(f.read().strip())

        expected = procs * increments_per_proc
        return {
            "expected_count": expected,
            "actual_count": final_val,
            "elapsed_sec": round(elapsed, 3),
            "multiprocess_exclusion_passed": (final_val == expected)
        }


def test_crash_recovery() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = os.path.join(tmpdir, "crash.lock")
        cmd = [
            sys.executable, "-c",
            f"from file_lock import FileLock; fl = FileLock(r'{lock_path}', timeout=2.0); fl.__enter__(); import os; os._exit(1)"
        ]
        p = subprocess.Popen(cmd)
        p.wait()

        t0 = time.time()
        reclaimed = False
        try:
            with FileLock(lock_path, timeout=1.0):
                reclaimed = True
        except Exception:
            reclaimed = False
        elapsed = time.time() - t0

        return {
            "reclaimed_after_abrupt_exit": reclaimed,
            "reclaim_latency_sec": round(elapsed, 6),
            "crash_resilience_passed": reclaimed
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
    print("RUNNING OSS PARITY GATE 1: S-CLASS LOCKING ENGINE VS PORTALOCKER 4.1.0")
    print("=" * 80)
    print(f"Frozen Environment:\n{json.dumps(env_info, indent=2)}\n")

    print("[1/8] Layer A — Primitive Parity Verification (5 Reps x 500 Interleaved Trials)...")
    layer_a = test_layer_a_primitive_parity(n_trials=500, n_repetitions=5)

    print("[2/8] Layer B — Full S-Class Lifecycle & Microsegment Profiling...")
    layer_b = test_layer_b_full_lifecycle(n_trials=500)

    print("[3/8] Timeout Semantics Verification...")
    timeout_res = test_timeout_semantics()

    print("[4/8] Multithreaded Contention Verification (8 Threads x 50 Increments)...")
    mt_res = test_multithreaded_contention()

    print("[5/8] Multiprocess Cross-Process Mutual Exclusion (4 Procs x 25 Increments)...")
    mp_res = test_multiprocess_exclusion()

    print("[6/8] Crash & Abrupt Termination Release Verification...")
    crash_res = test_crash_recovery()

    print("[7/8] Stale Metadata Recovery Verification...")
    stale_res = test_stale_metadata()

    print("[8/8] Config GC Non-Destructive Interaction Verification...")
    gc_res = test_gc_interaction()

    master_results = {
        "environment": env_info,
        "layer_a_primitive_parity": layer_a,
        "layer_b_full_sclass_lifecycle": layer_b,
        "timeout_verification": timeout_res,
        "multithreaded_contention": mt_res,
        "multiprocess_exclusion": mp_res,
        "crash_recovery": crash_res,
        "stale_metadata": stale_res,
        "gc_interaction": gc_res,
        "final_gate_verdict": "PASS" if layer_a["gate_passed"] else "FAIL"
    }

    out_file = os.path.join(os.path.dirname(__file__), "parity_gate_1_raw_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(master_results, f, indent=2)

    print("\nRaw results successfully saved to:", out_file)
    print("Layer A Gate Passed:", layer_a["gate_passed"])
    print(f"NativeLock Median: {layer_a['sclass_native_primitive']['median_us']} us vs Portalocker: {layer_a['reference_portalocker']['median_us']} us ({layer_a['statistical_metrics']['median_latency_diff_pct']}% diff)")
    print(f"Full FileLock Median: {layer_b['full_sclass_filelock']['median_us']} us")
    print(f"Final Gate Verdict: {master_results['final_gate_verdict']}")
    return master_results


if __name__ == "__main__":
    run_full_parity_gate()
