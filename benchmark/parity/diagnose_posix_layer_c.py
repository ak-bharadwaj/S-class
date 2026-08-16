"""
POSIX Diagnostic Script: Comprehensive Multi-Run Layer C Breakdown & Profiling.
Runs 5 independent repeated Layer C benchmark passes on Linux/POSIX, collecting
microsegment breakdowns (open, lock, serialize, write_flush_enter, serialize_exit, write_flush_exit, unlock, close),
paired distribution percentiles (p50, p90, p95, p99, max), and bootstrap metrics.
"""

import os
import sys
import time
import json
import random
import tempfile
import portalocker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from file_lock import FileLock, _CACHED_PID, _CACHED_HOSTNAME, _CACHED_PROC_START
from benchmark.parity.file_lock_harness import (
    calculate_linear_percentile,
    compute_paired_bootstrap_metrics,
    get_system_environment_info
)


def profile_layer_c_run(run_id: int, n_trials: int = 500, n_repetitions: int = 5):
    with tempfile.TemporaryDirectory() as tmpdir:
        ref_file = os.path.join(tmpdir, f"ref_lifecycle_{run_id}.lock")
        sclass_file = os.path.join(tmpdir, f"sclass_lifecycle_{run_id}.lock")

        paired_latencies_us = []
        ref_microsegments = {
            "open_ns": [],
            "lock_ns": [],
            "write_enter_flush_ns": [],
            "write_exit_flush_ns": [],
            "unlock_ns": [],
            "close_ns": []
        }
        sclass_microsegments = {
            "open_ns": [],
            "lock_ns": [],
            "json_serialize_enter_ns": [],
            "write_flush_enter_ns": [],
            "json_serialize_exit_ns": [],
            "write_flush_exit_ns": [],
            "unlock_ns": [],
            "close_ns": []
        }

        ref_pid = _CACHED_PID
        ref_host = _CACHED_HOSTNAME
        ref_proc_start = _CACHED_PROC_START
        meta_enter_template = f'{{"pid": {ref_pid}, "host": "{ref_host}", "process_start_time": {ref_proc_start}, "token": "ref-token", "start_time": '
        meta_exit_template = f'{{"status": "released", "pid": {ref_pid}, "token": "ref-token"}}'.encode("utf-8")

        rng = random.Random(1000 + run_id)
        for rep in range(n_repetitions):
            for i in range(n_trials):
                run_ref_first = rng.choice([True, False])
                t_ref_us = 0.0
                t_sclass_us = 0.0

                def run_ref() -> float:
                    t0 = time.perf_counter_ns()
                    with portalocker.Lock(ref_file, mode="a+b", timeout=5.0) as fh:
                        t_now = time.time()
                        enter_payload = f'{meta_enter_template}{t_now}}}'.encode("utf-8")
                        fh.seek(0)
                        fh.truncate(0)
                        fh.write(enter_payload)
                        fh.flush()

                        fh.seek(0)
                        fh.truncate(0)
                        fh.write(meta_exit_template)
                        fh.flush()
                    t1 = time.perf_counter_ns()
                    return (t1 - t0) / 1000.0

                def run_sclass() -> float:
                    t0 = time.perf_counter_ns()
                    fl = FileLock(sclass_file, timeout=5.0, enable_profiling=(rep == 0 and i < 100))
                    with fl:
                        pass
                    t1 = time.perf_counter_ns()
                    if fl.enable_profiling:
                        for k, v in fl.profile_timings.items():
                            if k in sclass_microsegments:
                                sclass_microsegments[k].append(v / 1000.0)
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

        percentiles = [0.50, 0.90, 0.95, 0.99]
        ref_dist = {f"p{int(p*100)}": round(calculate_linear_percentile(r_lats, p), 2) for p in percentiles}
        ref_dist["max"] = round(max(r_lats), 2)
        ref_dist["min"] = round(min(r_lats), 2)

        sclass_dist = {f"p{int(p*100)}": round(calculate_linear_percentile(s_lats, p), 2) for p in percentiles}
        sclass_dist["max"] = round(max(s_lats), 2)
        sclass_dist["min"] = round(min(s_lats), 2)

        bootstrap_metrics = compute_paired_bootstrap_metrics(paired_latencies_us)

        # Slowest 10 outlier pairs
        slowest_pairs = sorted(
            [{"index": idx, "sclass_us": round(p[0], 2), "ref_us": round(p[1], 2), "ratio": round(p[0]/p[1], 4)} for idx, p in enumerate(paired_latencies_us)],
            key=lambda x: max(x["sclass_us"], x["ref_us"]),
            reverse=True
        )[:10]

        return {
            "run_id": run_id,
            "total_pairs": len(paired_latencies_us),
            "ref_distribution": ref_dist,
            "sclass_distribution": sclass_dist,
            "bootstrap_metrics": bootstrap_metrics,
            "slowest_outliers": slowest_pairs,
            "sclass_profile_samples": {k: {"median_us": round(calculate_linear_percentile(v, 0.50), 2) if v else 0, "p95_us": round(calculate_linear_percentile(v, 0.95), 2) if v else 0} for k, v in sclass_microsegments.items()}
        }


def main():
    print("=" * 80)
    print("POSIX DIAGNOSTIC AUDIT: 5 REPEATED RUNS OF LAYER C (1:1 EQUIVALENT LIFECYCLE)")
    print("=" * 80)
    env = get_system_environment_info()
    print("Environment:", json.dumps(env, indent=2))

    all_runs = []
    for r in range(1, 6):
        print(f"\nExecuting POSIX Diagnostic Run {r}/5 (2,500 trials)...")
        res = profile_layer_c_run(r, n_trials=500, n_repetitions=5)
        all_runs.append(res)
        bm = res["bootstrap_metrics"]
        print(f"  Run {r} Result:")
        print(f"    Median Latency: Ref = {res['ref_distribution']['p50']} us | S-Class = {res['sclass_distribution']['p50']} us | Ratio = {bm['median_ratio']} (95% CI: {bm['median_ratio_95_ci']}) | Gate: {bm['median_gate_passed']}")
        print(f"    P95 Latency:    Ref = {res['ref_distribution']['p95']} us | S-Class = {res['sclass_distribution']['p95']} us | Ratio = {bm['p95_ratio']} (95% CI: {bm['p95_ratio_95_ci']}) | Gate: {bm['p95_gate_passed']}")
        print(f"    Throughput:     Ratio = {bm['throughput_ratio']} (95% CI: {bm['throughput_ratio_95_ci']}) | Gate: {bm['throughput_gate_passed']}")
        print(f"    All Gates Passed: {bm['all_gates_passed']} | Bootstraps: {bm['bootstraps_evaluated']}")

    output_path = "benchmark/parity/posix_diagnostic_5_runs_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"environment": env, "runs": all_runs}, f, indent=2)
    print(f"\nSaved diagnostic evidence to {output_path}")


if __name__ == "__main__":
    main()
