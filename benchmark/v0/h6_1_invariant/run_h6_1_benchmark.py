#!/usr/bin/env python3
"""
H6.1 Independent Adversarial Behavioral Invariant Benchmark Runner
(benchmark/v0/h6_1_invariant/run_h6_1_benchmark.py)

Executes B2 vs B4 ONLY across 24 High-Risk Invariant Tasks with ZERO-REGEX Behavioral Probes:
- Layer 1: Functional Oracle Pytest (test_oracle.py)
- Layer 2: Independent Adversarial Behavioral Invariant Pytest (test_adversarial_invariants.py)
"""

import os
import sys
import json
import time
import argparse
from typing import Dict, List, Any, Optional

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
V0_DIR = os.path.dirname(CURRENT_DIR)
ENGINEERING_DIR = os.path.join(V0_DIR, "engineering")
SCLASS_ROOT = os.path.dirname(V0_DIR)

if SCLASS_ROOT not in sys.path:
    sys.path.insert(0, SCLASS_ROOT)
if ENGINEERING_DIR not in sys.path:
    sys.path.insert(0, ENGINEERING_DIR)

from run_genuine_benchmark import LLMProviderConfig, LLMProvider, run_baseline_b2, run_baseline_b4
from invariant_behavioral_adjudicator import BehavioralInvariantAdjudicator

def run_h6_1_benchmark(provider_type: str = "auto", model_name: str = "gemini-3.5-flash-lite", allow_mock: bool = False, api_key: Optional[str] = None):
    h6_1_dir = CURRENT_DIR
    tasks_dir = os.path.join(h6_1_dir, "tasks_h6_1")
    runs_dir = os.path.join(h6_1_dir, "runs_h6_1")
    os.makedirs(runs_dir, exist_ok=True)

    config = LLMProviderConfig(provider_type=provider_type, model_name=model_name, api_key=api_key)
    provider = LLMProvider(config=config, allow_mock_fallback=allow_mock)

    print("=== Starting H6.1 Independent Adversarial Behavioral Invariant Benchmark ===")
    print(f"Provider: {provider.config.provider_type} | Model: {provider.config.model_name}")
    print(f"Tasks Directory: {tasks_dir}\n")

    task_ids = sorted([d for d in os.listdir(tasks_dir) if os.path.isdir(os.path.join(tasks_dir, d))])
    
    all_results = []

    for task_id in task_ids:
        tdir = os.path.join(tasks_dir, task_id)
        spec_file = os.path.join(tdir, "task_spec.json")
        with open(spec_file, "r", encoding="utf-8") as f:
            spec = json.load(f)

        task_runs_dir = os.path.join(runs_dir, task_id)
        os.makedirs(task_runs_dir, exist_ok=True)

        print(f"--- Running Task: {task_id} ({spec.get('category', '')} / {spec.get('domain', '')}) ---")

        # B2 Run
        print("  Running B2 (Agent + Pytest Repair)...", end="", flush=True)
        b2_art = run_baseline_b2(tdir, spec, provider)
        b2_pass_l1 = b2_art["oracle_result"]["all_passed"]
        
        # Layer 2 Behavioral Probe Execution (ZERO REGEX)
        target_code = b2_art.get("final_code", "")
        b2_adj = BehavioralInvariantAdjudicator.run_l2_behavioral_probes(tdir, target_code, b2_pass_l1, b2_art.get("execution_trace", []))
        b2_art["layer2_behavioral_adjudication"] = b2_adj

        with open(os.path.join(task_runs_dir, "b2_raw.json"), "w", encoding="utf-8") as f:
            json.dump(b2_art, f, indent=2)

        l1_str = "PASS" if b2_pass_l1 else "FAIL"
        l2_str = "PASS" if b2_adj["layer2_passed"] else "FAIL"
        print(f" [Layer 1 Oracle: {l1_str} | Layer 2 Behavioral Probes: {l2_str}]")
        time.sleep(2)

        # B4 Run
        print("  Running B4 (Agent + S-Class + Pytest Repair)...", end="", flush=True)
        b4_art = run_baseline_b4(tdir, spec, provider)
        b4_pass_l1 = b4_art["oracle_result"]["all_passed"]
        
        # Layer 2 Behavioral Probe Execution (ZERO REGEX)
        target_code_b4 = b4_art.get("final_code", "")
        b4_adj = BehavioralInvariantAdjudicator.run_l2_behavioral_probes(tdir, target_code_b4, b4_pass_l1, b4_art.get("execution_trace", []))
        b4_art["layer2_behavioral_adjudication"] = b4_adj

        with open(os.path.join(task_runs_dir, "b4_raw.json"), "w", encoding="utf-8") as f:
            json.dump(b4_art, f, indent=2)

        l1_b4_str = "PASS" if b4_pass_l1 else "FAIL"
        l2_b4_str = "PASS" if b4_adj["layer2_passed"] else "FAIL"
        print(f" [Layer 1 Oracle: {l1_b4_str} | Layer 2 Behavioral Probes: {l2_b4_str}]")
        time.sleep(2)

        all_results.extend([b2_art, b4_art])

    generate_h6_1_summary_reports(all_results, h6_1_dir)

def generate_h6_1_summary_reports(results: List[Dict[str, Any]], h6_1_dir: str):
    b2_runs = [r for r in results if r["baseline"] == "B2"]
    b4_runs = [r for r in results if r["baseline"] == "B4"]
    total_tasks = len(b2_runs)

    def calc_metrics(runs):
        l1_passed = sum(1 for r in runs if r["oracle_result"]["all_passed"])
        l2_passed = sum(1 for r in runs if r.get("layer2_behavioral_adjudication", {}).get("layer2_passed", False))
        false_conf_count = sum(1 for r in runs if r.get("layer2_behavioral_adjudication", {}).get("false_confidence_detected", False))
        avg_audit_completeness = sum(r.get("layer2_behavioral_adjudication", {}).get("audit_trace_completeness_pct", 0.0) for r in runs) / max(1, len(runs))

        tot_cost = sum(sum(t["cost_usd"] for t in r.get("execution_trace", [])) for r in runs)
        tot_calls = sum(len(r.get("execution_trace", [])) for r in runs)
        tot_latency = sum(sum(t["latency_sec"] for t in r.get("execution_trace", [])) for r in runs)

        return {
            "layer1_oracle_passed_tasks": l1_passed,
            "layer1_oracle_pass_rate_pct": round((l1_passed / max(1, len(runs))) * 100.0, 2),
            "layer2_behavioral_invariant_passed_tasks": l2_passed,
            "layer2_behavioral_invariant_pass_rate_pct": round((l2_passed / max(1, len(runs))) * 100.0, 2),
            "false_confidence_count": false_conf_count,
            "false_confidence_rate_pct": round((false_conf_count / max(1, len(runs))) * 100.0, 2),
            "avg_audit_trace_completeness_pct": round(avg_audit_completeness, 2),
            "total_cost_usd": round(tot_cost, 6),
            "cost_per_success_usd": round(tot_cost / max(1, l1_passed), 6),
            "calls_per_success": round(tot_calls / max(1, l1_passed), 2),
            "latency_per_success_sec": round(tot_latency / max(1, l1_passed), 3)
        }

    b2_summary = calc_metrics(b2_runs)
    b4_summary = calc_metrics(b4_runs)

    h6_1_report = {
        "title": "H6.1 Independent Adversarial Behavioral Invariant Benchmark Summary Report",
        "sample_size_tasks": total_tasks,
        "total_executions": len(results),
        "zero_regex_verification": True,
        "metrics": {
            "B2_Model_Pytest_Loop": b2_summary,
            "B4_Model_SClass_Pytest_Loop": b4_summary
        }
    }

    json_path = os.path.join(h6_1_dir, "h6_1_invariant_benchmark_report.json")
    md_path = os.path.join(h6_1_dir, "h6_1_invariant_benchmark_report.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(h6_1_report, f, indent=2)

    md_lines = [
        "# H6.1 Independent Adversarial Behavioral Invariant Benchmark Summary Report",
        "",
        f"- **Verification Protocol**: `ZERO REGEX MATCHING - Pure Executable Adversarial Probes`",
        f"- **Replication Scale**: `{total_tasks} High-Risk Invariant Engineering Tasks`",
        f"- **Total Executions**: `{len(results)} Live LLM Runs`",
        "",
        "## Layer 1 (Executable Oracle) vs Layer 2 (Adversarial Behavioral Invariant Probes) Comparison",
        "",
        "| Metric | B2 (Model + Pytest) | B4 (Model + S-Class + Pytest) | Delta (B4 - B2) |",
        "| :--- | :---: | :---: | :---: |",
        f"| **Layer 1 Oracle Pass Rate (%)** | {b2_summary['layer1_oracle_pass_rate_pct']}% ({b2_summary['layer1_oracle_passed_tasks']}/{total_tasks}) | {b4_summary['layer1_oracle_pass_rate_pct']}% ({b4_summary['layer1_oracle_passed_tasks']}/{total_tasks}) | `{b4_summary['layer1_oracle_pass_rate_pct'] - b2_summary['layer1_oracle_pass_rate_pct']:+.2f}%` |",
        f"| **Layer 2 Behavioral Invariant Pass Rate (%)** | {b2_summary['layer2_behavioral_invariant_pass_rate_pct']}% ({b2_summary['layer2_behavioral_invariant_passed_tasks']}/{total_tasks}) | {b4_summary['layer2_behavioral_invariant_pass_rate_pct']}% ({b4_summary['layer2_behavioral_invariant_passed_tasks']}/{total_tasks}) | `{b4_summary['layer2_behavioral_invariant_pass_rate_pct'] - b2_summary['layer2_behavioral_invariant_pass_rate_pct']:+.2f}%` |",
        f"| **False Confidence Rate (%)** | {b2_summary['false_confidence_rate_pct']}% ({b2_summary['false_confidence_count']} tasks) | {b4_summary['false_confidence_rate_pct']}% ({b4_summary['false_confidence_count']} tasks) | `{b4_summary['false_confidence_rate_pct'] - b2_summary['false_confidence_rate_pct']:+.2f}%` |",
        f"| **Audit Trace Completeness (%)** | {b2_summary['avg_audit_trace_completeness_pct']}% | {b4_summary['avg_audit_trace_completeness_pct']}% | `{b4_summary['avg_audit_trace_completeness_pct'] - b2_summary['avg_audit_trace_completeness_pct']:+.2f}%` |",
        f"| **Calls / Success** | {b2_summary['calls_per_success']} | {b4_summary['calls_per_success']} | `{b4_summary['calls_per_success'] - b2_summary['calls_per_success']:+.2f}` |",
        f"| **Cost / Success ($)** | ${b2_summary['cost_per_success_usd']} | ${b4_summary['cost_per_success_usd']} | `${b4_summary['cost_per_success_usd'] - b2_summary['cost_per_success_usd']:+.6f}` |"
    ]

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    print(f"\nH6.1 Reports saved to {json_path} and {md_path}")

def main():
    parser = argparse.ArgumentParser(description="H6.1 Independent Adversarial Behavioral Invariant Benchmark Runner")
    parser.add_argument("--provider", type=str, default="auto")
    parser.add_argument("--model", type=str, default="gemini-3.5-flash-lite")
    parser.add_argument("--api-key", type=str, default=None)
    parser.add_argument("--allow-mock", action="store_true")
    args = parser.parse_args()

    run_h6_1_benchmark(provider_type=args.provider, model_name=args.model, allow_mock=args.allow_mock, api_key=args.api_key)

if __name__ == "__main__":
    main()
