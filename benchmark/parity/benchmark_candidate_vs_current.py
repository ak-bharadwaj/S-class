"""
Direct Comparison Benchmark: Current S-Class FileLock vs ExperimentalFileLock (Atomic Positional Writer).

Runs 2,500 paired trials under identical conditions on Linux (Ubuntu 24.04), evaluating:
- Paired median ratio & 95% bootstrap CI
- Paired P95 ratio & 95% bootstrap CI
- Paired throughput ratio & 95% bootstrap CI
- Tail distributions (P50, P90, P95, P99, Max, Min)
"""

import os
import sys
import time
import json
import random
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from file_lock import FileLock
from tests.test_experimental_metadata_writer import ExperimentalFileLock
from benchmark.parity.file_lock_harness import (
    calculate_linear_percentile,
    compute_paired_bootstrap_metrics,
    get_system_environment_info
)


def run_current_vs_candidate_benchmark(n_trials: int = 500, n_repetitions: int = 5):
    with tempfile.TemporaryDirectory() as tmpdir:
        path_cur = os.path.join(tmpdir, "current.lock")
        path_exp = os.path.join(tmpdir, "experimental.lock")

        paired_latencies_us = []
        cur_lats, exp_lats = [], []
        rng = random.Random(999)

        for rep in range(n_repetitions):
            for i in range(n_trials):
                run_cur_first = rng.choice([True, False])
                t_cur_us, t_exp_us = 0.0, 0.0

                def run_current():
                    t0 = time.perf_counter_ns()
                    with FileLock(path_cur, timeout=5.0):
                        pass
                    t1 = time.perf_counter_ns()
                    return (t1 - t0) / 1000.0

                def run_exp():
                    t0 = time.perf_counter_ns()
                    with ExperimentalFileLock(path_exp, timeout=5.0):
                        pass
                    t1 = time.perf_counter_ns()
                    return (t1 - t0) / 1000.0

                if run_cur_first:
                    t_cur_us = run_current()
                    t_exp_us = run_exp()
                else:
                    t_exp_us = run_exp()
                    t_cur_us = run_current()

                cur_lats.append(t_cur_us)
                exp_lats.append(t_exp_us)
                paired_latencies_us.append((t_exp_us, t_cur_us))  # (candidate, current)

        def calc_dist(lats):
            return {
                "p50": round(calculate_linear_percentile(lats, 0.50), 2),
                "p90": round(calculate_linear_percentile(lats, 0.90), 2),
                "p95": round(calculate_linear_percentile(lats, 0.95), 2),
                "p99": round(calculate_linear_percentile(lats, 0.99), 2),
                "max": round(max(lats), 2),
                "min": round(min(lats), 2)
            }

        # Bootstrap: candidate vs current (target <= 1.005)
        metrics = compute_paired_bootstrap_metrics(paired_latencies_us)

        return {
            "total_trials": len(paired_latencies_us),
            "current_filelock_distribution": calc_dist(cur_lats),
            "experimental_filelock_distribution": calc_dist(exp_lats),
            "bootstrap_candidate_vs_current": metrics
        }


def main():
    print("=" * 80)
    print("HEAD-TO-HEAD BENCHMARK: EXPERIMENTAL CANDIDATE VS CURRENT S-CLASS FILELOCK")
    print("=" * 80)

    env = get_system_environment_info()
    provenance = {
        "tested_source_sha": "7f50a062b837d7cee696d2b8a0cf533b4a07dbf5",
        "benchmark_harness_sha": env.get("git_commit_sha", "UNKNOWN"),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID", "LOCAL_RUN"),
        "result_generated_at_utc": env.get("timestamp_utc")
    }

    print("Provenance:", json.dumps(provenance, indent=2))
    print("Environment:", json.dumps(env, indent=2))

    print("\nExecuting 2,500 paired trials (Candidate vs Current FileLock)...")
    res = run_current_vs_candidate_benchmark(n_trials=500, n_repetitions=5)

    print("\nLatency Distributions (microseconds):")
    print("  Current S-Class FileLock:      ", res["current_filelock_distribution"])
    print("  Experimental Candidate FileLock:", res["experimental_filelock_distribution"])

    bm = res["bootstrap_candidate_vs_current"]
    print("\nPaired Bootstrap Results (Candidate vs Current FileLock):")
    print("  Median Latency Ratio:  ", bm["median_ratio"], "95% CI:", bm["median_ratio_95_ci"], "| Gate:", bm["median_gate_passed"])
    print("  P95 Latency Ratio:     ", bm["p95_ratio"], "95% CI:", bm["p95_ratio_95_ci"], "| Gate:", bm["p95_gate_passed"])
    print("  Throughput Ratio:      ", bm["throughput_ratio"], "95% CI:", bm["throughput_ratio_95_ci"], "| Gate:", bm["throughput_gate_passed"])
    print("  All Certification Gates Passed:", bm["all_gates_passed"])

    out_file = "benchmark/parity/candidate_vs_current_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"provenance": provenance, "environment": env, "results": res}, f, indent=2)
    print(f"\nSaved direct comparison results to {out_file}")


if __name__ == "__main__":
    main()
