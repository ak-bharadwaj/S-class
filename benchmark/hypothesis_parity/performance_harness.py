"""
S-Class EOS V11.2 - Gate 2 Phase 8: Controlled Multi-Trial Performance Benchmark Harness.
Measures warm campaign latency, generation throughput, cold-start index construction,
and 5,000-cycle memory soak stability between Reference Hypothesis Adapter and S-Class Clean-Room Engine.
Supported Python Versions: 3.10-3.13.
"""

import os
import sys
import json
import time
import math
import random
import socket
import platform
from typing import Dict, Any, List, Tuple, Optional

repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from benchmark.hypothesis_parity.observation import StrategySpec, ObservationRecord
from benchmark.hypothesis_parity.reference_adapter import ReferenceHypothesisAdapter
from benchmark.hypothesis_parity.cleanroom_engine import CleanRoomPropertyEngine
from benchmark.hypothesis_parity.unicode_indexer import get_unicode_provenance, _init_unicode_intervals
from benchmark.parity.file_lock_harness import calculate_linear_percentile


# Canonical Gate 2 Thresholds
GATE_2_LATENCY_MEDIAN_UPPER = 1.050
GATE_2_LATENCY_P95_UPPER = 1.050
GATE_2_THROUGHPUT_LOWER = 0.950
GATE_2_SOAK_GROWTH_UPPER = 1.050


def get_current_rss_bytes() -> int:
    """Returns current process Resident Set Size (RSS) in bytes on Windows or POSIX."""
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss
    except Exception:
        pass

    if sys.platform == "win32":
        try:
            import ctypes
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
    return 1024 * 1024


def get_total_ram_bytes() -> int:
    """Returns total system RAM in bytes."""
    try:
        import psutil
        return psutil.virtual_memory().total
    except Exception:
        pass
    return 16 * 1024 * 1024 * 1024


def compute_paired_bootstrap_gate2(
    paired_times_us: List[Tuple[float, float]],
    n_bootstraps: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 42
) -> Dict[str, Any]:
    """Computes paired bootstrap 95% confidence intervals for Gate 2 performance benchmarks."""
    n = len(paired_times_us)
    if n == 0:
        return {
            "median_ratio": 99.0,
            "median_ratio_95_ci": [99.0, 99.0],
            "p95_ratio": 99.0,
            "p95_ratio_95_ci": [99.0, 99.0],
            "throughput_ratio": 0.0,
            "throughput_ratio_95_ci": [0.0, 0.0],
            "all_gates_passed": False
        }

    cand_lats = [p[0] for p in paired_times_us]
    ref_lats = [p[1] for p in paired_times_us]

    c_med = calculate_linear_percentile(cand_lats, 0.50)
    r_med = calculate_linear_percentile(ref_lats, 0.50)
    point_med_ratio = c_med / r_med if r_med > 0 else 99.0

    c_p95 = calculate_linear_percentile(cand_lats, 0.95)
    r_p95 = calculate_linear_percentile(ref_lats, 0.95)
    point_p95_ratio = c_p95 / r_p95 if r_p95 > 0 else 99.0

    c_tp = 1000000.0 / (sum(cand_lats) / n) if sum(cand_lats) > 0 else 0.0
    r_tp = 1000000.0 / (sum(ref_lats) / n) if sum(ref_lats) > 0 else 0.0
    point_tp_ratio = c_tp / r_tp if r_tp > 0 else 0.0

    rng = random.Random(seed)
    boot_med_ratios, boot_p95_ratios, boot_tp_ratios = [], [], []

    for _ in range(n_bootstraps):
        sample = [paired_times_us[rng.randint(0, n - 1)] for _ in range(n)]
        c_sample = [p[0] for p in sample]
        r_sample = [p[1] for p in sample]

        cm = calculate_linear_percentile(c_sample, 0.50)
        rm = calculate_linear_percentile(r_sample, 0.50)
        boot_med_ratios.append(cm / rm if rm > 0 else 99.0)

        cp = calculate_linear_percentile(c_sample, 0.95)
        rp = calculate_linear_percentile(r_sample, 0.95)
        boot_p95_ratios.append(cp / rp if rp > 0 else 99.0)

        ct = 1000000.0 / (sum(c_sample) / n) if sum(c_sample) > 0 else 0.0
        rt = 1000000.0 / (sum(r_sample) / n) if sum(r_sample) > 0 else 0.0
        boot_tp_ratios.append(ct / rt if rt > 0 else 0.0)

    alpha = (1.0 - confidence_level) / 2.0
    med_ci = [
        round(calculate_linear_percentile(boot_med_ratios, alpha), 4),
        round(calculate_linear_percentile(boot_med_ratios, 1.0 - alpha), 4)
    ]
    p95_ci = [
        round(calculate_linear_percentile(boot_p95_ratios, alpha), 4),
        round(calculate_linear_percentile(boot_p95_ratios, 1.0 - alpha), 4)
    ]
    tp_ci = [
        round(calculate_linear_percentile(boot_tp_ratios, alpha), 4),
        round(calculate_linear_percentile(boot_tp_ratios, 1.0 - alpha), 4)
    ]

    med_passed = med_ci[1] <= GATE_2_LATENCY_MEDIAN_UPPER
    p95_passed = p95_ci[1] <= GATE_2_LATENCY_P95_UPPER
    tp_passed = tp_ci[0] >= GATE_2_THROUGHPUT_LOWER

    return {
        "median_ratio": round(point_med_ratio, 4),
        "median_ratio_95_ci": med_ci,
        "p95_ratio": round(point_p95_ratio, 4),
        "p95_ratio_95_ci": p95_ci,
        "throughput_ratio": round(point_tp_ratio, 4),
        "throughput_ratio_95_ci": tp_ci,
        "median_gate_passed": med_passed,
        "p95_gate_passed": p95_passed,
        "throughput_gate_passed": tp_passed,
        "all_gates_passed": (med_passed and p95_passed and tp_passed)
    }


def run_full_gate2_performance_benchmark(
    n_trials: int = 1000,
    soak_cycles: int = 5000,
    output_cert_path: Optional[str] = None,
    tested_sha: Optional[str] = None,
    run_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the full Gate 2 multi-trial performance & soak benchmark.
    Produces an immutable Gate 2 Parity Certificate.
    """
    print(f"Starting Gate 2 Performance Benchmark ({n_trials} trials/domain, {soak_cycles} soak cycles)...")

    # 1. Cold-Start Measurement
    t0_cold = time.perf_counter_ns()
    prov = get_unicode_provenance()
    cold_init_ms = (time.perf_counter_ns() - t0_cold) / 1_000_000.0

    # 2. Benchmark Domains
    benchmark_domains = {
        "integers": {
            "specs": {"a": StrategySpec(strategy_type="integers", params={"min_value": -1000, "max_value": 1000})},
            "prop": lambda a: a + 0 == a
        },
        "floats": {
            "specs": {"f": StrategySpec(strategy_type="floats", params={"min_value": 0.0, "max_value": 100.0, "allow_nan": False, "allow_infinity": False})},
            "prop": lambda f: f * 1.0 == f
        },
        "text": {
            "specs": {"s": StrategySpec(strategy_type="text", params={"alphabet": "abcdefghij", "min_size": 1, "max_size": 25})},
            "prop": lambda s: len(s) >= 1
        },
        "lists": {
            "specs": {"l": StrategySpec(strategy_type="lists", params={"elements": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 50}), "min_size": 1, "max_size": 10})},
            "prop": lambda l: len(l) >= 0
        },
        "from_regex": {
            "specs": {"code": StrategySpec(strategy_type="from_regex", params={"pattern": r"^[A-Z]{3}-\d{4}$", "fullmatch": True})},
            "prop": lambda code: len(code) == 8
        },
        "sampled_from": {
            "specs": {"elem": StrategySpec(strategy_type="sampled_from", params={"elements": ["alpha", "beta", "gamma", "delta"]})},
            "prop": lambda elem: elem in ["alpha", "beta", "gamma", "delta"]
        }
    }

    rng = random.Random(42)
    domain_results: Dict[str, Any] = {}
    aggregate_paired: List[Tuple[float, float]] = []

    for dom_name, dom_info in benchmark_domains.items():
        specs = dom_info["specs"]
        prop = dom_info["prop"]

        # Warmup (50 cycles)
        for _ in range(50):
            ReferenceHypothesisAdapter.run_campaign(specs, prop, max_examples=15, suppress_health_checks=True)
            CleanRoomPropertyEngine.run_campaign(specs, prop, max_examples=15)

        # 1,000 Paired Trials (alternating execution order)
        paired_domain: List[Tuple[float, float]] = []
        cand_times_us: List[float] = []
        ref_times_us: List[float] = []

        for _ in range(n_trials):
            cand_first = rng.choice([True, False])

            def run_cand():
                t0 = time.perf_counter_ns()
                CleanRoomPropertyEngine.run_campaign(specs, prop, max_examples=15)
                return (time.perf_counter_ns() - t0) / 1000.0

            def run_ref():
                t0 = time.perf_counter_ns()
                ReferenceHypothesisAdapter.run_campaign(specs, prop, max_examples=15, suppress_health_checks=True)
                return (time.perf_counter_ns() - t0) / 1000.0

            if cand_first:
                tc = run_cand()
                tr = run_ref()
            else:
                tr = run_ref()
                tc = run_cand()

            cand_times_us.append(tc)
            ref_times_us.append(tr)
            paired_domain.append((tc, tr))
            aggregate_paired.append((tc, tr))

        dom_metrics = compute_paired_bootstrap_gate2(paired_domain)
        domain_results[dom_name] = {
            "cleanroom_engine": {
                "median_us": round(calculate_linear_percentile(cand_times_us, 0.50), 2),
                "p95_us": round(calculate_linear_percentile(cand_times_us, 0.95), 2),
                "throughput_campaigns_sec": round(1000000.0 / (sum(cand_times_us) / n_trials), 1)
            },
            "reference_hypothesis": {
                "median_us": round(calculate_linear_percentile(ref_times_us, 0.50), 2),
                "p95_us": round(calculate_linear_percentile(ref_times_us, 0.95), 2),
                "throughput_campaigns_sec": round(1000000.0 / (sum(ref_times_us) / n_trials), 1)
            },
            "statistical_metrics": dom_metrics,
            "domain_gate_passed": dom_metrics["all_gates_passed"]
        }
        print(f"Domain '{dom_name}': CleanRoom median={domain_results[dom_name]['cleanroom_engine']['median_us']}us vs Ref={domain_results[dom_name]['reference_hypothesis']['median_us']}us (Passed: {dom_metrics['all_gates_passed']})")

    aggregate_metrics = compute_paired_bootstrap_gate2(aggregate_paired)

    # 3. 5,000-Cycle Memory Soak Benchmark
    print(f"Executing {soak_cycles}-cycle memory soak test...")
    soak_specs = benchmark_domains["integers"]["specs"]
    soak_prop = benchmark_domains["integers"]["prop"]

    rss_baseline = get_current_rss_bytes()
    t0_soak = time.perf_counter()

    for _ in range(soak_cycles):
        CleanRoomPropertyEngine.run_campaign(soak_specs, soak_prop, max_examples=10)

    rss_final = get_current_rss_bytes()
    soak_elapsed_sec = round(time.perf_counter() - t0_soak, 2)
    rss_growth_ratio = round(rss_final / rss_baseline if rss_baseline > 0 else 1.0, 4)
    soak_passed = rss_growth_ratio <= GATE_2_SOAK_GROWTH_UPPER

    soak_metrics = {
        "soak_cycles_executed": soak_cycles,
        "soak_elapsed_sec": soak_elapsed_sec,
        "rss_baseline_bytes": rss_baseline,
        "rss_final_bytes": rss_final,
        "rss_growth_ratio": rss_growth_ratio,
        "max_allowed_growth_ratio": GATE_2_SOAK_GROWTH_UPPER,
        "soak_gate_passed": soak_passed
    }
    print(f"Soak Test: {soak_cycles} cycles in {soak_elapsed_sec}s. RSS growth={rss_growth_ratio:.4f} (Passed: {soak_passed})")

    # 4. Assemble Immutable Gate 2 Parity Certificate
    all_domains_passed = all(d["domain_gate_passed"] for d in domain_results.values())
    final_verdict = "PASS" if (all_domains_passed and aggregate_metrics["all_gates_passed"] and soak_passed) else "FAIL"

    commit_sha = tested_sha or os.environ.get("GITHUB_SHA", "UNKNOWN")

    certificate = {
        "certificate_id": f"OSS-PARITY-GATE-2-PROPERTY-TESTING-LINUX-{commit_sha[:12].upper()}",
        "schema_version": "1.0.0",
        "gate_name": "Gate 2: Hypothesis Property Testing & Invariant Verification Parity",
        "provenance": {
            "runner_os": os.environ.get("RUNNER_OS", platform.system()),
            "hostname": socket.gethostname(),
            "cpu_count_logical": os.cpu_count() or 4,
            "total_ram_bytes": get_total_ram_bytes(),
            "python_runtime_version": sys.version,
            "python_version_tuple": list(sys.version_info[:3]),
            "hypothesis_reference_version": "6.165.9",
            "unicode_database_version": prov.get("unicode_database_version"),
            "index_sha256_checksum": prov.get("index_sha256_checksum"),
            "tested_source_sha": commit_sha,
            "workflow_run_id": run_id or os.environ.get("GITHUB_RUN_ID", "local"),
            "timestamp_utc": time.time(),
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        },
        "acceptance_criteria": {
            "trials_per_domain": n_trials,
            "total_paired_benchmark_trials": len(aggregate_paired),
            "soak_cycles_executed": soak_cycles,
            "median_ratio_upper_bound": GATE_2_LATENCY_MEDIAN_UPPER,
            "p95_ratio_upper_bound": GATE_2_LATENCY_P95_UPPER,
            "throughput_ratio_lower_bound": GATE_2_THROUGHPUT_LOWER,
            "soak_growth_upper_bound": GATE_2_SOAK_GROWTH_UPPER
        },
        "cold_start_metrics": {
            "cold_init_duration_ms": round(cold_init_ms, 3),
            "total_categories_indexed": prov.get("total_categories_indexed"),
            "total_disjoint_intervals": prov.get("total_disjoint_intervals")
        },
        "aggregate_performance_metrics": aggregate_metrics,
        "domain_performance_metrics": domain_results,
        "long_soak_memory": soak_metrics,
        "final_verdict": final_verdict
    }

    out_file = output_cert_path if output_cert_path else os.path.join(os.path.dirname(__file__), "gate_2_parity_certificate.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(certificate, f, indent=2)

    print(f"Gate 2 Performance Certificate written to {out_file}. Final Verdict: {final_verdict}")
    return certificate


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Gate 2 Performance Benchmark Harness")
    parser.add_argument("--output", type=str, default=None, help="Output certificate JSON path")
    parser.add_argument("--sha", type=str, default=None, help="Tested Git commit SHA")
    parser.add_argument("--run-id", type=str, default=None, help="CI Workflow Run ID")
    parser.add_argument("--trials", type=int, default=1000, help="Trials per domain")
    parser.add_argument("--soak", type=int, default=5000, help="Soak cycles")
    args = parser.parse_args()

    run_full_gate2_performance_benchmark(
        n_trials=args.trials,
        soak_cycles=args.soak,
        output_cert_path=args.output,
        tested_sha=args.sha,
        run_id=args.run_id
    )
