"""
POSIX Tail-Cause Diagnostic: Comparing 4 Isolated Lifecycle Variants.

Variants Evaluated (2,500 paired trials each):
- Variant A: Reference Lifecycle (Portalocker lock -> enter write/flush -> exit write/flush -> unlock)
- Variant B: Standard S-Class FileLock Lifecycle (open -> lock -> enter seek/trunc/write/flush -> exit seek/trunc/write/flush -> unlock -> close)
- Variant C: S-Class FileLock with Metadata Write/Flush Disabled (open -> lock -> unlock -> close)
- Variant D: S-Class FileLock with Write/Flush replaced by simple unbuffered OS os.write without Python flush overhead
"""

import os
import sys
import time
import json
import random
import tempfile
import portalocker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from file_lock import FileLock, _CACHED_PID, _CACHED_HOSTNAME, _CACHED_PROC_START, _META_PREFIX
from benchmark.parity.file_lock_harness import (
    calculate_linear_percentile,
    compute_paired_bootstrap_metrics,
    get_system_environment_info
)


def run_tail_isolation_experiment(n_trials: int = 500, n_repetitions: int = 5):
    with tempfile.TemporaryDirectory() as tmpdir:
        path_a = os.path.join(tmpdir, "variant_a.lock")
        path_b = os.path.join(tmpdir, "variant_b.lock")
        path_c = os.path.join(tmpdir, "variant_c.lock")
        path_d = os.path.join(tmpdir, "variant_d.lock")

        ref_pid = _CACHED_PID
        ref_host = _CACHED_HOSTNAME
        ref_proc_start = _CACHED_PROC_START
        meta_enter_template = f'{{"pid": {ref_pid}, "host": "{ref_host}", "process_start_time": {ref_proc_start}, "token": "ref-token", "start_time": '
        meta_exit_template = f'{{"status": "released", "pid": {ref_pid}, "token": "ref-token"}}'.encode("utf-8")

        # Preservation lists
        lat_a, lat_b, lat_c, lat_d = [], [], [], []
        pairs_b_vs_a = []
        pairs_c_vs_a = []
        pairs_d_vs_a = []

        rng = random.Random(42)

        for rep in range(n_repetitions):
            for i in range(n_trials):
                # Execute Variant A (Reference Portalocker Lifecycle)
                t0 = time.perf_counter_ns()
                with portalocker.Lock(path_a, mode="a+b", timeout=5.0) as fh:
                    t_now = time.time()
                    fh.seek(0)
                    fh.truncate(0)
                    fh.write(f'{meta_enter_template}{t_now}}}'.encode("utf-8"))
                    fh.flush()

                    fh.seek(0)
                    fh.truncate(0)
                    fh.write(meta_exit_template)
                    fh.flush()
                t1 = time.perf_counter_ns()
                ta = (t1 - t0) / 1000.0

                # Execute Variant B (Standard S-Class Lifecycle)
                t0 = time.perf_counter_ns()
                with FileLock(path_b, timeout=5.0):
                    pass
                t1 = time.perf_counter_ns()
                tb = (t1 - t0) / 1000.0

                # Execute Variant C (S-Class Lifecycle - Metadata Write/Flush DISABLED)
                t0 = time.perf_counter_ns()
                fl_c = FileLock(path_c, timeout=5.0)
                # open + lock
                f_c = open(fl_c.lock_path, "a+b")
                fl_c._lock_handle(f_c)
                # unlock + close (no seek, no truncate, no write, no flush)
                fl_c._unlock_handle(f_c)
                f_c.close()
                t1 = time.perf_counter_ns()
                tc = (t1 - t0) / 1000.0

                # Execute Variant D (S-Class Lifecycle - os.pwrite without seek/truncate/flush overhead)
                t0 = time.perf_counter_ns()
                fl_d = FileLock(path_d, timeout=5.0)
                f_d = open(fl_d.lock_path, "a+b")
                fl_d._lock_handle(f_d)
                fd_d = f_d.fileno()
                # Single direct write to offset 0
                payload_enter = f'{_META_PREFIX}token-d", "start_time": {time.time()}}}'.encode("utf-8")
                os.pwrite(fd_d, payload_enter, 0)
                payload_exit = b'{"status": "released", "pid": 123, "token": "token-d"}'
                os.pwrite(fd_d, payload_exit, 0)
                fl_d._unlock_handle(f_d)
                f_d.close()
                t1 = time.perf_counter_ns()
                td = (t1 - t0) / 1000.0

                lat_a.append(ta)
                lat_b.append(tb)
                lat_c.append(tc)
                lat_d.append(td)

                pairs_b_vs_a.append((tb, ta))
                pairs_c_vs_a.append((tc, ta))
                pairs_d_vs_a.append((td, ta))

        def calc_dist(lats):
            return {
                "p50": round(calculate_linear_percentile(lats, 0.50), 2),
                "p90": round(calculate_linear_percentile(lats, 0.90), 2),
                "p95": round(calculate_linear_percentile(lats, 0.95), 2),
                "p99": round(calculate_linear_percentile(lats, 0.99), 2),
                "max": round(max(lats), 2),
                "min": round(min(lats), 2),
            }

        return {
            "total_trials": len(lat_a),
            "variant_a_reference": calc_dist(lat_a),
            "variant_b_sclass_standard": calc_dist(lat_b),
            "variant_c_sclass_no_meta_write": calc_dist(lat_c),
            "variant_d_sclass_direct_pwrite": calc_dist(lat_d),
            "bootstrap_b_vs_a": compute_paired_bootstrap_metrics(pairs_b_vs_a),
            "bootstrap_c_vs_a": compute_paired_bootstrap_metrics(pairs_c_vs_a),
            "bootstrap_d_vs_a": compute_paired_bootstrap_metrics(pairs_d_vs_a),
        }


def main():
    print("=" * 80)
    print("POSIX TAIL-CAUSE DIAGNOSTIC: 4-WAY ISOLATION EXPERIMENT")
    print("=" * 80)

    env = get_system_environment_info()
    tested_source_sha = "7f50a062b837d7cee696d2b8a0cf533b4a07dbf5"
    current_head_sha = env.get("git_commit_sha", "UNKNOWN")

    provenance_record = {
        "tested_source_sha": tested_source_sha,
        "diagnostic_harness_sha": current_head_sha,
        "environment": env
    }
    print("Provenance:", json.dumps(provenance_record, indent=2))

    print("\nExecuting 2,500 trials across all 4 variants...")
    results = run_tail_isolation_experiment(n_trials=500, n_repetitions=5)

    print("\nVariant Distribution Results (microseconds):")
    print("  Variant A (Reference Portalocker):      ", results["variant_a_reference"])
    print("  Variant B (S-Class Standard FileLock):  ", results["variant_b_sclass_standard"])
    print("  Variant C (S-Class No Metadata Write):  ", results["variant_c_sclass_no_meta_write"])
    print("  Variant D (S-Class Direct os.pwrite):   ", results["variant_d_sclass_direct_pwrite"])

    print("\nBootstrap Metrics vs Reference (Variant A):")
    print("  B vs A (Standard):  Median Ratio =", results["bootstrap_b_vs_a"]["median_ratio"], "| P95 Ratio =", results["bootstrap_b_vs_a"]["p95_ratio"], "(95% CI:", results["bootstrap_b_vs_a"]["p95_ratio_95_ci"], ") | P95 Gate:", results["bootstrap_b_vs_a"]["p95_gate_passed"])
    print("  C vs A (No Meta):   Median Ratio =", results["bootstrap_c_vs_a"]["median_ratio"], "| P95 Ratio =", results["bootstrap_c_vs_a"]["p95_ratio"], "(95% CI:", results["bootstrap_c_vs_a"]["p95_ratio_95_ci"], ") | P95 Gate:", results["bootstrap_c_vs_a"]["p95_gate_passed"])
    print("  D vs A (pwrite):    Median Ratio =", results["bootstrap_d_vs_a"]["median_ratio"], "| P95 Ratio =", results["bootstrap_d_vs_a"]["p95_ratio"], "(95% CI:", results["bootstrap_d_vs_a"]["p95_ratio_95_ci"], ") | P95 Gate:", results["bootstrap_d_vs_a"]["p95_gate_passed"])

    output_path = "benchmark/parity/posix_tail_isolation_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"provenance": provenance_record, "results": results}, f, indent=2)
    print(f"\nSaved tail-cause isolation results to {output_path}")


if __name__ == "__main__":
    main()
