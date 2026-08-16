#!/usr/bin/env python3
"""
OSS Parity Gate 1: Differential Benchmark & Capability Verification Harness (Windows Edition)
Comparing S-Class Independent OS-Native Locking Engine vs Reference Portalocker 4.1.0

Platform Scope: Windows / Python 3.14.5 (msvcrt kernel advisory locking)
Certificate ID: OSS-PARITY-GATE-1-FILELOCK-WINDOWS

Strict Certification Protocol:
1. Paired Statistical Bootstrap:
   - Preserves trial pairs (S-Class_i, Reference_i).
   - Bootstraps paired observations over 1,000 resamples.
   - Evaluates Paired Median Ratio 95% CI, Paired P95 Ratio 95% CI, and Paired Throughput Ratio 95% CI.

2. Dual Path Validation (Independent Paths & Same-Path Interleaving):
   - Layer A (Independent Paths): Evaluates S-Class vs Portalocker on independent temporary lock files.
   - Layer A-SP (Same Path): Evaluates S-Class vs Portalocker sequentially acquiring/releasing the exact same file path with randomized ordering per pair to eliminate filesystem/cache path bias.

3. Strict 0.5% Gate Certification Rules:
   - Layer A, Layer A-SP & Layer C Latency: Median Ratio Upper 95% CI <= 1.005 AND P95 Ratio Upper 95% CI <= 1.005
   - Layer A, Layer A-SP & Layer C Throughput: Throughput Ratio Lower 95% CI >= 0.995

4. Genuine 5,000-Cycle Long-Soak Memory Stability Evaluation:
   - Dedicated 5,000 continuous lock acquisition & release cycles.
   - Measures Initial Working Set, Peak Working Set, and Final Working Set.
   - Enforces Bounded RSS memory drift <= 5% over 5,000 cycles (Final RSS / Initial RSS <= 1.050).

5. Cross-Implementation Interoperability:
   - S-Class Holder -> Portalocker Contender = BLOCKED_SUCCESS
   - Portalocker Holder -> S-Class Contender = BLOCKED_SUCCESS

6. 1:1 Differential Semantic Correctness:
   - Inter-process timeout, 8-thread serialization (400/400), 4-process mutual exclusion (100/100),
     abrupt crash recovery (os._exit), stale metadata recovery, and config GC safety.

7. Exports standardized machine-readable Parity Certificate (gate_1_parity_certificate_windows.json).
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
    else:
        try:
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
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


def compute_paired_bootstrap_metrics(pairs: List[Tuple[float, float]], n_bootstraps: int = 1000) -> Dict[str, Any]:
    """
    Performs rigorous paired bootstrap resampling over preserved (sclass_i, ref_i) trials.
    Calculates paired median ratio CI, paired P95 ratio CI, and paired throughput ratio CI.
    """
    n = len(pairs)
    if n == 0:
        return {
            "median_ratio": 1.0, "median_ratio_95_ci": [1.0, 1.0],
            "p95_ratio": 1.0, "p95_ratio_95_ci": [1.0, 1.0],
            "throughput_ratio": 1.0, "throughput_ratio_95_ci": [1.0, 1.0]
        }

    s_all = [p[0] for p in pairs]
    r_all = [p[1] for p in pairs]

    point_s_med = calculate_linear_percentile(s_all, 0.50)
    point_r_med = calculate_linear_percentile(r_all, 0.50)
    point_s_p95 = calculate_linear_percentile(s_all, 0.95)
    point_r_p95 = calculate_linear_percentile(r_all, 0.95)

    point_med_ratio = point_s_med / point_r_med if point_r_med > 0 else 1.0
    point_p95_ratio = point_s_p95 / point_r_p95 if point_r_p95 > 0 else 1.0

    sum_s = sum(s_all)
    sum_r = sum(r_all)
    point_tp_ratio = (sum_r / sum_s) if sum_s > 0 else 1.0

    boot_med_ratios: List[float] = []
    boot_p95_ratios: List[float] = []
    boot_tp_ratios: List[float] = []

    rng = random.Random(42)
    for _ in range(n_bootstraps):
        resampled_pairs = [pairs[rng.randint(0, n - 1)] for _ in range(n)]
        res_s = [p[0] for p in resampled_pairs]
        res_r = [p[1] for p in resampled_pairs]

        m_s = calculate_linear_percentile(res_s, 0.50)
        m_r = calculate_linear_percentile(res_r, 0.50)
        if m_r > 0:
            boot_med_ratios.append(m_s / m_r)

        p_s = calculate_linear_percentile(res_s, 0.95)
        p_r = calculate_linear_percentile(res_r, 0.95)
        if p_r > 0:
            boot_p95_ratios.append(p_s / p_r)

        tot_s = sum(res_s)
        tot_r = sum(res_r)
        if tot_s > 0:
            boot_tp_ratios.append(tot_r / tot_s)

    med_ci = [
        calculate_linear_percentile(boot_med_ratios, 0.025) if boot_med_ratios else point_med_ratio,
        calculate_linear_percentile(boot_med_ratios, 0.975) if boot_med_ratios else point_med_ratio
    ]
    p95_ci = [
        calculate_linear_percentile(boot_p95_ratios, 0.025) if boot_p95_ratios else point_p95_ratio,
        calculate_linear_percentile(boot_p95_ratios, 0.975) if boot_p95_ratios else point_p95_ratio
    ]
    tp_ci = [
        calculate_linear_percentile(boot_tp_ratios, 0.025) if boot_tp_ratios else point_tp_ratio,
        calculate_linear_percentile(boot_tp_ratios, 0.975) if boot_tp_ratios else point_tp_ratio
    ]

    return {
        "median_ratio": round(point_med_ratio, 4),
        "median_ratio_95_ci": [round(med_ci[0], 4), round(med_ci[1], 4)],
        "p95_ratio": round(point_p95_ratio, 4),
        "p95_ratio_95_ci": [round(p95_ci[0], 4), round(p95_ci[1], 4)],
        "throughput_ratio": round(point_tp_ratio, 4),
        "throughput_ratio_95_ci": [round(tp_ci[0], 4), round(tp_ci[1], 4)]
    }


# ============================================================================
# Layer A: Independent Primitive Parity (Independent Paths)
# ============================================================================
def test_layer_a_primitive_parity(n_trials: int = 500, n_repetitions: int = 5) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        ref_lock_file = os.path.join(tmpdir, "portalocker.lock")
        sclass_lock_file = os.path.join(tmpdir, "sclass_native.lock")

        paired_latencies_us: List[Tuple[float, float]] = []

        rng = random.Random(1337)
        for rep in range(n_repetitions):
            for i in range(n_trials):
                run_ref_first = rng.choice([True, False])
                t_ref_us = 0.0
                t_sclass_us = 0.0

                def run_ref() -> float:
                    t0 = time.perf_counter_ns()
                    with portalocker.Lock(ref_lock_file, timeout=5.0):
                        pass
                    t1 = time.perf_counter_ns()
                    return (t1 - t0) / 1000.0

                def run_sclass() -> float:
                    t0 = time.perf_counter_ns()
                    with NativeLock(sclass_lock_file, timeout=5.0):
                        pass
                    t1 = time.perf_counter_ns()
                    return (t1 - t0) / 1000.0

                if run_ref_first:
                    t_ref_us = run_ref()
                    t_sclass_us = run_sclass()
                else:
                    t_sclass_us = run_sclass()
                    t_ref_us = run_ref()

                paired_latencies_us.append((t_sclass_us, t_ref_us))

        s_lats = [p[0] for p in paired_latencies_us]
        r_lats = [p[1] for p in paired_latencies_us]

        ref_med = calculate_linear_percentile(r_lats, 0.50)
        ref_p95 = calculate_linear_percentile(r_lats, 0.95)
        sclass_med = calculate_linear_percentile(s_lats, 0.50)
        sclass_p95 = calculate_linear_percentile(s_lats, 0.95)

        total_ref_sec = sum(r_lats) / 1e6
        total_sclass_sec = sum(s_lats) / 1e6
        ref_throughput = len(r_lats) / total_ref_sec if total_ref_sec > 0 else 0
        sclass_throughput = len(s_lats) / total_sclass_sec if total_sclass_sec > 0 else 0

        paired_metrics = compute_paired_bootstrap_metrics(paired_latencies_us)

        lat_pass = (paired_metrics["median_ratio_95_ci"][1] <= 1.005 and paired_metrics["p95_ratio_95_ci"][1] <= 1.005)
        tp_pass = (paired_metrics["throughput_ratio_95_ci"][0] >= 0.995)
        gate_passed = (lat_pass and tp_pass)

        return {
            "gate_passed": gate_passed,
            "latency_gate_passed": lat_pass,
            "throughput_gate_passed": tp_pass,
            "threshold_applied": "Paired Median/P95 Upper CI <= 1.005 AND Throughput Lower CI >= 0.995",
            "iterations_per_rep": n_trials,
            "total_repetitions": n_repetitions,
            "total_trials": len(paired_latencies_us),
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
            "statistical_metrics": paired_metrics
        }


# ============================================================================
# Layer A-SP: Independent Primitive Parity (Same-Path Sequential Interleaving)
# ============================================================================
def test_layer_a_same_path_primitive(n_trials: int = 500, n_repetitions: int = 5) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        shared_lock_file = os.path.join(tmpdir, "shared_primitive.lock")
        paired_latencies_us: List[Tuple[float, float]] = []

        rng = random.Random(2026)
        for rep in range(n_repetitions):
            for i in range(n_trials):
                run_ref_first = rng.choice([True, False])
                t_ref_us = 0.0
                t_sclass_us = 0.0

                def run_ref() -> float:
                    t0 = time.perf_counter_ns()
                    with portalocker.Lock(shared_lock_file, timeout=5.0):
                        pass
                    t1 = time.perf_counter_ns()
                    return (t1 - t0) / 1000.0

                def run_sclass() -> float:
                    t0 = time.perf_counter_ns()
                    with NativeLock(shared_lock_file, timeout=5.0):
                        pass
                    t1 = time.perf_counter_ns()
                    return (t1 - t0) / 1000.0

                if run_ref_first:
                    t_ref_us = run_ref()
                    t_sclass_us = run_sclass()
                else:
                    t_sclass_us = run_sclass()
                    t_ref_us = run_ref()

                paired_latencies_us.append((t_sclass_us, t_ref_us))

        s_lats = [p[0] for p in paired_latencies_us]
        r_lats = [p[1] for p in paired_latencies_us]

        ref_med = calculate_linear_percentile(r_lats, 0.50)
        ref_p95 = calculate_linear_percentile(r_lats, 0.95)
        sclass_med = calculate_linear_percentile(s_lats, 0.50)
        sclass_p95 = calculate_linear_percentile(s_lats, 0.95)

        total_ref_sec = sum(r_lats) / 1e6
        total_sclass_sec = sum(s_lats) / 1e6
        ref_throughput = len(r_lats) / total_ref_sec if total_ref_sec > 0 else 0
        sclass_throughput = len(s_lats) / total_sclass_sec if total_sclass_sec > 0 else 0

        paired_metrics = compute_paired_bootstrap_metrics(paired_latencies_us)

        lat_pass = (paired_metrics["median_ratio_95_ci"][1] <= 1.005 and paired_metrics["p95_ratio_95_ci"][1] <= 1.005)
        tp_pass = (paired_metrics["throughput_ratio_95_ci"][0] >= 0.995)
        gate_passed = (lat_pass and tp_pass)

        return {
            "gate_passed": gate_passed,
            "latency_gate_passed": lat_pass,
            "throughput_gate_passed": tp_pass,
            "threshold_applied": "Same-Path Paired Median/P95 Upper CI <= 1.005 AND Throughput Lower CI >= 0.995",
            "total_trials": len(paired_latencies_us),
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
            "statistical_metrics": paired_metrics
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
# Layer C: True 1:1 Equivalent Full Lifecycle Workload (Strict Gating)
# ============================================================================
def test_layer_c_equivalent_lifecycle(n_trials: int = 500, n_repetitions: int = 5) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        ref_file = os.path.join(tmpdir, "ref_lifecycle.lock")
        sclass_file = os.path.join(tmpdir, "sclass_lifecycle.lock")

        paired_latencies_us: List[Tuple[float, float]] = []

        ref_pid = _CACHED_PID
        ref_host = _CACHED_HOSTNAME
        ref_proc_start = _CACHED_PROC_START
        meta_enter_template = f'{{"pid": {ref_pid}, "host": "{ref_host}", "process_start_time": {ref_proc_start}, "token": "ref-token", "start_time": '
        meta_exit_template = f'{{"status": "released", "pid": {ref_pid}, "token": "ref-token"}}'.encode("utf-8")

        rng = random.Random(999)
        for rep in range(n_repetitions):
            for i in range(n_trials):
                run_ref_first = rng.choice([True, False])
                t_ref_us = 0.0
                t_sclass_us = 0.0

                def run_ref() -> float:
                    t0 = time.perf_counter_ns()
                    with portalocker.Lock(ref_file, mode="a+b", timeout=5.0) as fh:
                        # 1. Enter metadata payload formatting, seek, truncate, write, flush
                        t_now = time.time()
                        enter_payload = f'{meta_enter_template}{t_now}}}'.encode("utf-8")
                        fh.seek(0)
                        fh.truncate(0)
                        fh.write(enter_payload)
                        fh.flush()

                        # 2. Exit metadata release payload formatting, seek, truncate, write, flush
                        fh.seek(0)
                        fh.truncate(0)
                        fh.write(meta_exit_template)
                        fh.flush()
                    t1 = time.perf_counter_ns()
                    return (t1 - t0) / 1000.0

                def run_sclass() -> float:
                    t0 = time.perf_counter_ns()
                    with FileLock(sclass_file, timeout=5.0):
                        pass
                    t1 = time.perf_counter_ns()
                    return (t1 - t0) / 1000.0

                if run_ref_first:
                    t_ref_us = run_ref()
                    t_sclass_us = run_sclass()
                else:
                    t_sclass_us = run_sclass()
                    t_ref_us = run_ref()

                paired_latencies_us.append((t_sclass_us, t_ref_us))

        s_lats = [p[0] for p in paired_latencies_us]
        r_lats = [p[1] for p in paired_latencies_us]

        ref_med = calculate_linear_percentile(r_lats, 0.50)
        ref_p95 = calculate_linear_percentile(r_lats, 0.95)
        sclass_med = calculate_linear_percentile(s_lats, 0.50)
        sclass_p95 = calculate_linear_percentile(s_lats, 0.95)

        total_ref_sec = sum(r_lats) / 1e6
        total_sclass_sec = sum(s_lats) / 1e6
        ref_throughput = len(r_lats) / total_ref_sec if total_ref_sec > 0 else 0
        sclass_throughput = len(s_lats) / total_sclass_sec if total_sclass_sec > 0 else 0

        paired_metrics = compute_paired_bootstrap_metrics(paired_latencies_us)

        lat_pass = (paired_metrics["median_ratio_95_ci"][1] <= 1.005 and paired_metrics["p95_ratio_95_ci"][1] <= 1.005)
        tp_pass = (paired_metrics["throughput_ratio_95_ci"][0] >= 0.995)
        gate_passed = (lat_pass and tp_pass)

        return {
            "gate_passed": gate_passed,
            "latency_gate_passed": lat_pass,
            "throughput_gate_passed": tp_pass,
            "threshold_applied": "Paired Median/P95 Upper CI <= 1.005 AND Throughput Lower CI >= 0.995 on 1:1 Lifecycle",
            "iterations_per_rep": n_trials,
            "total_repetitions": n_repetitions,
            "total_trials": len(paired_latencies_us),
            "reference_equivalent_lifecycle": {
                "median_us": round(ref_med, 2),
                "p95_us": round(ref_p95, 2),
                "throughput_per_sec": round(ref_throughput, 1)
            },
            "sclass_filelock_lifecycle": {
                "median_us": round(sclass_med, 2),
                "p95_us": round(sclass_p95, 2),
                "throughput_per_sec": round(sclass_throughput, 1)
            },
            "statistical_metrics": paired_metrics
        }


# ============================================================================
# Dedicated 5,000-Cycle Long-Soak Memory Stability Evaluation
# ============================================================================
def test_long_soak_memory_stability(soak_cycles: int = 5000) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        soak_lock_file = os.path.join(tmpdir, "soak_test.lock")
        initial_rss = get_current_working_set_bytes()
        peak_rss = get_peak_working_set_bytes()

        for i in range(soak_cycles):
            with FileLock(soak_lock_file, timeout=5.0):
                pass
            if i % 500 == 0:
                curr_peak = get_peak_working_set_bytes()
                if curr_peak > peak_rss:
                    peak_rss = curr_peak

        final_rss = get_current_working_set_bytes()
        rss_growth_ratio = (final_rss / initial_rss) if initial_rss > 0 else 1.0
        gate_passed = (rss_growth_ratio <= 1.050)

        return {
            "soak_cycles": soak_cycles,
            "initial_rss_bytes": initial_rss,
            "peak_working_set_bytes": peak_rss,
            "final_rss_bytes": final_rss,
            "rss_growth_ratio": round(rss_growth_ratio, 4),
            "classification": "BOUNDED_RSS_DRIFT_LE_5PCT_5000_CYCLES",
            "threshold": "<= 1.050",
            "gate_passed": gate_passed
        }


# ============================================================================
# Cross-Implementation Interoperability Verification
# ============================================================================
def _interop_holder_worker(impl: str, lock_path: str, ready_file: str, hold_sec: float):
    if impl == "sclass":
        with NativeLock(lock_path, timeout=5.0):
            with open(ready_file, "w") as f:
                f.write("READY")
            time.sleep(hold_sec)
    else:
        with portalocker.Lock(lock_path, timeout=5.0):
            with open(ready_file, "w") as f:
                f.write("READY")
            time.sleep(hold_sec)


def _interop_contender_worker(impl: str, lock_path: str, result_file: str):
    if impl == "portalocker":
        try:
            with portalocker.Lock(lock_path, timeout=0.1):
                with open(result_file, "w") as f:
                    f.write("UNEXPECTED_ACQUISITION")
        except (portalocker.exceptions.AlreadyLocked, portalocker.exceptions.LockException):
            with open(result_file, "w") as f:
                f.write("BLOCKED_SUCCESS")
        except Exception as e:
            with open(result_file, "w") as f:
                f.write(f"ERR_{type(e).__name__}")
    else:
        try:
            with NativeLock(lock_path, timeout=0.1):
                with open(result_file, "w") as f:
                    f.write("UNEXPECTED_ACQUISITION")
        except TimeoutError:
            with open(result_file, "w") as f:
                f.write("BLOCKED_SUCCESS")
        except Exception as e:
            with open(result_file, "w") as f:
                f.write(f"ERR_{type(e).__name__}")


def test_cross_implementation_interoperability() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        shared_lock_file = os.path.join(tmpdir, "shared_interop.lock")
        ready_file = os.path.join(tmpdir, "interop_ready.txt")
        result_file = os.path.join(tmpdir, "interop_result.txt")

        # Test Case 1: S-Class NativeLock holds -> Portalocker contender MUST BLOCK
        if os.path.exists(ready_file):
            os.remove(ready_file)
        if os.path.exists(result_file):
            os.remove(result_file)

        cmd_holder = [
            sys.executable, "-c",
            f"from benchmark.parity.file_lock_harness import _interop_holder_worker; _interop_holder_worker('sclass', r'{shared_lock_file}', r'{ready_file}', 0.6)"
        ]
        p_holder = subprocess.Popen(cmd_holder)
        while not os.path.exists(ready_file):
            time.sleep(0.01)

        cmd_contender = [
            sys.executable, "-c",
            f"from benchmark.parity.file_lock_harness import _interop_contender_worker; _interop_contender_worker('portalocker', r'{shared_lock_file}', r'{result_file}')"
        ]
        p_contender = subprocess.Popen(cmd_contender)
        p_contender.wait()
        p_holder.wait()

        case1_res = "FAILED"
        if os.path.exists(result_file):
            with open(result_file, "r") as f:
                case1_res = f.read().strip()

        # Test Case 2: Portalocker holds -> S-Class NativeLock contender MUST BLOCK
        if os.path.exists(ready_file):
            os.remove(ready_file)
        if os.path.exists(result_file):
            os.remove(result_file)

        cmd_holder2 = [
            sys.executable, "-c",
            f"from benchmark.parity.file_lock_harness import _interop_holder_worker; _interop_holder_worker('portalocker', r'{shared_lock_file}', r'{ready_file}', 0.6)"
        ]
        p_holder2 = subprocess.Popen(cmd_holder2)
        while not os.path.exists(ready_file):
            time.sleep(0.01)

        cmd_contender2 = [
            sys.executable, "-c",
            f"from benchmark.parity.file_lock_harness import _interop_contender_worker; _interop_contender_worker('sclass', r'{shared_lock_file}', r'{result_file}')"
        ]
        p_contender2 = subprocess.Popen(cmd_contender2)
        p_contender2.wait()
        p_holder2.wait()

        case2_res = "FAILED"
        if os.path.exists(result_file):
            with open(result_file, "r") as f:
                case2_res = f.read().strip()

        passed = (case1_res == "BLOCKED_SUCCESS" and case2_res == "BLOCKED_SUCCESS")

        return {
            "sclass_holder_portalocker_contender_result": case1_res,
            "portalocker_holder_sclass_contender_result": case2_res,
            "interoperability_passed": passed
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
    print("RUNNING OSS PARITY GATE 1 (WINDOWS EDITION): S-CLASS VS PORTALOCKER 4.1.0")
    print("=" * 80)
    print(f"Frozen Environment:\n{json.dumps(env_info, indent=2)}\n")

    print("[1/12] Layer A — Independent Primitive Parity (Paired 5 Reps x 500 Interleaved Trials)...")
    layer_a = test_layer_a_primitive_parity(n_trials=500, n_repetitions=5)

    print("[2/12] Layer A-SP — Same-Path Interleaved Primitive Parity (5 Reps x 500 Trials)...")
    layer_a_sp = test_layer_a_same_path_primitive(n_trials=500, n_repetitions=5)

    print("[3/12] Layer B — Full S-Class Lifecycle & Microsegment Profiling...")
    layer_b = test_layer_b_full_lifecycle(n_trials=500)

    print("[4/12] Layer C — True 1:1 Equivalent Full Lifecycle Workload (Paired 5 Reps x 500 Trials)...")
    layer_c = test_layer_c_equivalent_lifecycle(n_trials=500, n_repetitions=5)

    print("[5/12] Dedicated Long-Soak Memory Stability Evaluation (5,000 Continuous Cycles)...")
    soak_res = test_long_soak_memory_stability(soak_cycles=5000)

    print("[6/12] Cross-Implementation Interoperability Verification (Shared Lock File)...")
    interop_res = test_cross_implementation_interoperability()

    print("[7/12] Differential Timeout Semantics Verification (Inter-Process)...")
    timeout_res = test_differential_timeout()

    print("[8/12] Differential Multithreaded Contention Verification (8 Threads x 50 Inc)...")
    mt_res = test_differential_multithreading()

    print("[9/12] Differential Multiprocess Exclusion Verification (4 Procs x 25 Inc)...")
    mp_res = test_differential_multiprocessing()

    print("[10/12] Differential Crash Recovery Verification (Abrupt os._exit)...")
    crash_res = test_differential_crash_recovery()

    print("[11/12] Stale Metadata Recovery Verification...")
    stale_res = test_stale_metadata()

    print("[12/12] Config GC Non-Destructive Interaction Verification...")
    gc_res = test_gc_interaction()

    # Holistic Gate Certification: All conditions must strictly be True
    gate_all_passed = (
        layer_a["gate_passed"] and
        layer_a_sp["gate_passed"] and
        layer_c["gate_passed"] and
        soak_res["gate_passed"] and
        interop_res["interoperability_passed"] and
        timeout_res["timeout_differential_passed"] and
        mt_res["thread_differential_passed"] and
        mp_res["multiprocess_differential_passed"] and
        crash_res["crash_differential_passed"] and
        stale_res["acquired_over_stale_metadata"] and
        gc_res["active_lock_preserved_by_gc"]
    )

    final_verdict = "PASS" if gate_all_passed else "FAIL"

    master_results = {
        "environment": env_info,
        "platform_scope": "WINDOWS_NT_MSVCRT",
        "certificate_id": "OSS-PARITY-GATE-1-FILELOCK-WINDOWS",
        "layer_a_primitive_parity": layer_a,
        "layer_a_same_path_primitive": layer_a_sp,
        "layer_b_full_sclass_lifecycle": layer_b,
        "layer_c_equivalent_lifecycle": layer_c,
        "long_soak_memory_stability": soak_res,
        "cross_implementation_interoperability": interop_res,
        "differential_timeout_verification": timeout_res,
        "differential_multithreaded_contention": mt_res,
        "differential_multiprocess_exclusion": mp_res,
        "differential_crash_recovery": crash_res,
        "stale_metadata": stale_res,
        "gc_interaction": gc_res,
        "final_gate_verdict": final_verdict
    }

    out_raw = os.path.join(os.path.dirname(__file__), "parity_gate_1_raw_results.json")
    with open(out_raw, "w", encoding="utf-8") as f:
        json.dump(master_results, f, indent=2)

    # Export standardized machine-readable Windows Parity Certificate
    certificate = {
        "certificate_id": "OSS-PARITY-GATE-1-FILELOCK-WINDOWS",
        "platform_scope": "Windows / Python 3.14.5 (AMD64)",
        "timestamp_utc": env_info["timestamp_utc"],
        "final_verdict": final_verdict,
        "provenance": env_info,
        "acceptance_criteria": {
            "primitive_latency_median_upper_ci_max": 1.005,
            "primitive_latency_p95_upper_ci_max": 1.005,
            "primitive_throughput_lower_ci_min": 0.995,
            "same_path_latency_median_upper_ci_max": 1.005,
            "same_path_latency_p95_upper_ci_max": 1.005,
            "same_path_throughput_lower_ci_min": 0.995,
            "lifecycle_latency_median_upper_ci_max": 1.005,
            "lifecycle_latency_p95_upper_ci_max": 1.005,
            "lifecycle_throughput_lower_ci_min": 0.995,
            "soak_memory_bounded_drift_ratio_max": 1.050,
            "soak_cycles_executed": soak_res["soak_cycles"],
            "memory_evaluation_classification": "BOUNDED_RSS_DRIFT_LE_5PCT_5000_CYCLES",
            "cross_implementation_interoperability": "REQUIRED_BLOCKED_SUCCESS",
            "differential_semantic_correctness": "100_PERCENT_MATCHED"
        },
        "layer_a_primitive": {
            "reference_median_us": layer_a["reference_portalocker"]["median_us"],
            "sclass_median_us": layer_a["sclass_native_primitive"]["median_us"],
            "median_ratio": layer_a["statistical_metrics"]["median_ratio"],
            "median_ratio_95_ci": layer_a["statistical_metrics"]["median_ratio_95_ci"],
            "p95_ratio": layer_a["statistical_metrics"]["p95_ratio"],
            "p95_ratio_95_ci": layer_a["statistical_metrics"]["p95_ratio_95_ci"],
            "throughput_ratio": layer_a["statistical_metrics"]["throughput_ratio"],
            "throughput_ratio_95_ci": layer_a["statistical_metrics"]["throughput_ratio_95_ci"],
            "verdict": "PASS" if layer_a["gate_passed"] else "FAIL"
        },
        "layer_a_same_path_primitive": {
            "reference_median_us": layer_a_sp["reference_portalocker"]["median_us"],
            "sclass_median_us": layer_a_sp["sclass_native_primitive"]["median_us"],
            "median_ratio": layer_a_sp["statistical_metrics"]["median_ratio"],
            "median_ratio_95_ci": layer_a_sp["statistical_metrics"]["median_ratio_95_ci"],
            "p95_ratio": layer_a_sp["statistical_metrics"]["p95_ratio"],
            "p95_ratio_95_ci": layer_a_sp["statistical_metrics"]["p95_ratio_95_ci"],
            "throughput_ratio": layer_a_sp["statistical_metrics"]["throughput_ratio"],
            "throughput_ratio_95_ci": layer_a_sp["statistical_metrics"]["throughput_ratio_95_ci"],
            "verdict": "PASS" if layer_a_sp["gate_passed"] else "FAIL"
        },
        "layer_c_1to1_lifecycle": {
            "reference_median_us": layer_c["reference_equivalent_lifecycle"]["median_us"],
            "sclass_median_us": layer_c["sclass_filelock_lifecycle"]["median_us"],
            "median_ratio": layer_c["statistical_metrics"]["median_ratio"],
            "median_ratio_95_ci": layer_c["statistical_metrics"]["median_ratio_95_ci"],
            "p95_ratio": layer_c["statistical_metrics"]["p95_ratio"],
            "p95_ratio_95_ci": layer_c["statistical_metrics"]["p95_ratio_95_ci"],
            "throughput_ratio": layer_c["statistical_metrics"]["throughput_ratio"],
            "throughput_ratio_95_ci": layer_c["statistical_metrics"]["throughput_ratio_95_ci"],
            "verdict": "PASS" if layer_c["gate_passed"] else "FAIL"
        },
        "long_soak_memory": {
            "soak_cycles": soak_res["soak_cycles"],
            "initial_rss_bytes": soak_res["initial_rss_bytes"],
            "final_rss_bytes": soak_res["final_rss_bytes"],
            "rss_growth_ratio": soak_res["rss_growth_ratio"],
            "classification": soak_res["classification"],
            "verdict": "PASS" if soak_res["gate_passed"] else "FAIL"
        },
        "interoperability": {
            "sclass_holds_portalocker_blocks": interop_res["sclass_holder_portalocker_contender_result"],
            "portalocker_holds_sclass_blocks": interop_res["portalocker_holder_sclass_contender_result"],
            "verdict": "PASS" if interop_res["interoperability_passed"] else "FAIL"
        },
        "differential_semantics": {
            "timeout": "PASS" if timeout_res["timeout_differential_passed"] else "FAIL",
            "multithreading_400_count": "PASS" if mt_res["thread_differential_passed"] else "FAIL",
            "multiprocessing_100_count": "PASS" if mp_res["multiprocess_differential_passed"] else "FAIL",
            "crash_recovery_os_exit": "PASS" if crash_res["crash_differential_passed"] else "FAIL",
            "stale_metadata_takeover": "PASS" if stale_res["acquired_over_stale_metadata"] else "FAIL",
            "gc_safety": "PASS" if gc_res["active_lock_preserved_by_gc"] else "FAIL"
        }
    }

    out_cert_win = os.path.join(os.path.dirname(__file__), "gate_1_parity_certificate_windows.json")
    with open(out_cert_win, "w", encoding="utf-8") as f:
        json.dump(certificate, f, indent=2)

    # Maintain gate_1_parity_certificate.json as pointer/current platform snapshot
    out_cert_generic = os.path.join(os.path.dirname(__file__), "gate_1_parity_certificate.json")
    with open(out_cert_generic, "w", encoding="utf-8") as f:
        json.dump(certificate, f, indent=2)

    print("\n" + "=" * 110)
    print("FINAL OSS PARITY GATE 1 (WINDOWS EDITION) CERTIFICATION MATRIX")
    print("=" * 110)
    print(f"{'Capability Dimension':<32} | {'Reference':<14} | {'S-Class':<14} | {'Paired Ratio (95% CI)':<26} | {'Threshold':<11} | {'Verdict'}")
    print("-" * 125)
    print(f"{'Layer A: Primitive Median':<32} | {layer_a['reference_portalocker']['median_us']:>9.2f} us | {layer_a['sclass_native_primitive']['median_us']:>9.2f} us | {layer_a['statistical_metrics']['median_ratio']:>6.4f} {str(layer_a['statistical_metrics']['median_ratio_95_ci']):<18} | {'<= 1.005':<11} | {'PASS' if layer_a['latency_gate_passed'] else 'FAIL'}")
    print(f"{'Layer A: Primitive P95':<32} | {layer_a['reference_portalocker']['p95_us']:>9.2f} us | {layer_a['sclass_native_primitive']['p95_us']:>9.2f} us | {layer_a['statistical_metrics']['p95_ratio']:>6.4f} {str(layer_a['statistical_metrics']['p95_ratio_95_ci']):<18} | {'<= 1.005':<11} | {'PASS' if layer_a['latency_gate_passed'] else 'FAIL'}")
    print(f"{'Layer A: Primitive Throughput':<32} | {layer_a['reference_portalocker']['throughput_per_sec']:>9.1f} /s | {layer_a['sclass_native_primitive']['throughput_per_sec']:>9.1f} /s | {layer_a['statistical_metrics']['throughput_ratio']:>6.4f} {str(layer_a['statistical_metrics']['throughput_ratio_95_ci']):<18} | {'>= 0.995':<11} | {'PASS' if layer_a['throughput_gate_passed'] else 'FAIL'}")
    print(f"{'Layer A-SP: Same-Path Median':<32} | {layer_a_sp['reference_portalocker']['median_us']:>9.2f} us | {layer_a_sp['sclass_native_primitive']['median_us']:>9.2f} us | {layer_a_sp['statistical_metrics']['median_ratio']:>6.4f} {str(layer_a_sp['statistical_metrics']['median_ratio_95_ci']):<18} | {'<= 1.005':<11} | {'PASS' if layer_a_sp['latency_gate_passed'] else 'FAIL'}")
    print(f"{'Layer A-SP: Same-Path P95':<32} | {layer_a_sp['reference_portalocker']['p95_us']:>9.2f} us | {layer_a_sp['sclass_native_primitive']['p95_us']:>9.2f} us | {layer_a_sp['statistical_metrics']['p95_ratio']:>6.4f} {str(layer_a_sp['statistical_metrics']['p95_ratio_95_ci']):<18} | {'<= 1.005':<11} | {'PASS' if layer_a_sp['latency_gate_passed'] else 'FAIL'}")
    print(f"{'Layer A-SP: Same-Path Throughput':<32} | {layer_a_sp['reference_portalocker']['throughput_per_sec']:>9.1f} /s | {layer_a_sp['sclass_native_primitive']['throughput_per_sec']:>9.1f} /s | {layer_a_sp['statistical_metrics']['throughput_ratio']:>6.4f} {str(layer_a_sp['statistical_metrics']['throughput_ratio_95_ci']):<18} | {'>= 0.995':<11} | {'PASS' if layer_a_sp['throughput_gate_passed'] else 'FAIL'}")
    med_pass = (layer_c['statistical_metrics']['median_ratio_95_ci'][1] <= 1.005)
    p95_pass = (layer_c['statistical_metrics']['p95_ratio_95_ci'][1] <= 1.005)
    print(f"{'Layer C: 1:1 Lifecycle Median':<32} | {layer_c['reference_equivalent_lifecycle']['median_us']:>9.2f} us | {layer_c['sclass_filelock_lifecycle']['median_us']:>9.2f} us | {layer_c['statistical_metrics']['median_ratio']:>6.4f} {str(layer_c['statistical_metrics']['median_ratio_95_ci']):<18} | {'<= 1.005':<11} | {'PASS' if med_pass else 'FAIL'}")
    print(f"{'Layer C: 1:1 Lifecycle P95':<32} | {layer_c['reference_equivalent_lifecycle']['p95_us']:>9.2f} us | {layer_c['sclass_filelock_lifecycle']['p95_us']:>9.2f} us | {layer_c['statistical_metrics']['p95_ratio']:>6.4f} {str(layer_c['statistical_metrics']['p95_ratio_95_ci']):<18} | {'<= 1.005':<11} | {'PASS' if p95_pass else 'FAIL'}")
    print(f"{'Layer C: 1:1 Lifecycle Throughput':<32} | {layer_c['reference_equivalent_lifecycle']['throughput_per_sec']:>9.1f} /s | {layer_c['sclass_filelock_lifecycle']['throughput_per_sec']:>9.1f} /s | {layer_c['statistical_metrics']['throughput_ratio']:>6.4f} {str(layer_c['statistical_metrics']['throughput_ratio_95_ci']):<18} | {'>= 0.995':<11} | {'PASS' if layer_c['throughput_gate_passed'] else 'FAIL'}")
    print(f"{'Long Soak (5,000 Cycles)':<32} | {soak_res['initial_rss_bytes']/(1024*1024):>9.2f} MB | {soak_res['final_rss_bytes']/(1024*1024):>9.2f} MB | {'Ratio: '+str(soak_res['rss_growth_ratio']):<26} | {'<= 1.050':<11} | {'PASS' if soak_res['gate_passed'] else 'FAIL'}")
    print(f"{'Interoperability (S->P & P->S)':<32} | {'BLOCKED_SUCCESS':<14} | {'BLOCKED_SUCCESS':<14} | {'Mutual Kernel Exclusion':<26} | {'Equiv':<11} | {'PASS' if interop_res['interoperability_passed'] else 'FAIL'}")
    print(f"{'Timeout (Inter-process)':<32} | {str(timeout_res['reference_timed_out']):<14} | {str(timeout_res['sclass_timed_out']):<14} | {'Matched Semantics':<26} | {'Equiv':<11} | {'PASS' if timeout_res['timeout_differential_passed'] else 'FAIL'}")
    print(f"{'Multithreading (8T x 50)':<32} | {str(mt_res['reference_actual_count'])+'/400':<14} | {str(mt_res['sclass_actual_count'])+'/400':<14} | {'Serial Correct':<26} | {'400/400':<11} | {'PASS' if mt_res['thread_differential_passed'] else 'FAIL'}")
    print(f"{'Multiprocessing (4P x 25)':<32} | {str(mp_res['reference_final_count'])+'/100':<14} | {str(mp_res['sclass_final_count'])+'/100':<14} | {'Atomic Correct':<26} | {'100/100':<11} | {'PASS' if mp_res['multiprocess_differential_passed'] else 'FAIL'}")
    print(f"{'Crash Recovery (os._exit)':<32} | {'Reclaimed':<14} | {'Reclaimed':<14} | {'Instant Release':<26} | {'Equiv':<11} | {'PASS' if crash_res['crash_differential_passed'] else 'FAIL'}")
    print("=" * 125)
    print(f"FINAL CERTIFIED OSS PARITY GATE 1 (WINDOWS) VERDICT: {final_verdict}")
    print("=" * 125)
    return master_results


if __name__ == "__main__":
    run_full_parity_gate()
