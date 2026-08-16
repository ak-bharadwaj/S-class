#!/usr/bin/env python3
"""
Claude Cross-Model Replication Script (H6.2 Tasks)
(benchmark/v0/h6_2_invariant/run_claude_replication.py)

Executes Claude (Claude 3.5 Sonnet / Haiku) on the 12 held-out H6.2 tasks:
- Baseline B2: Claude + Pytest Test Repair
- Baseline B4: Claude + S-Class + Pytest Test Repair

Evaluated against the exact bi-directionally pre-validated Layer 2 behavioral probes.
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
from statistical_analysis import StatisticalAnalysisEngine

def run_claude_replication(model_name: str = "claude-3-5-sonnet-20241022", api_key: Optional[str] = None, allow_mock: bool = False):
    h6_2_dir = CURRENT_DIR
    tasks_dir = os.path.join(h6_2_dir, "tasks_h6_2")
    runs_dir = os.path.join(h6_2_dir, "runs_claude_h6_2")
    os.makedirs(runs_dir, exist_ok=True)

    config = LLMProviderConfig(provider_type="claude", model_name=model_name, api_key=api_key)
    provider = LLMProvider(config=config, allow_mock_fallback=allow_mock)

    print(f"=== Starting Claude Cross-Model Replication (12 Tasks) ===")
    print(f"Provider: claude | Model: {model_name}")
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

        print(f"--- Running Task: {task_id} ({spec.get('category', '')}) ---")

        # Claude B2 Run
        print("  Running Claude B2 (Agent + Pytest Repair)...", end="", flush=True)
        b2_art = run_baseline_b2(tdir, spec, provider)
        b2_pass_l1 = b2_art["oracle_result"]["all_passed"]
        
        target_code = b2_art.get("final_code", "")
        b2_adj = BehavioralInvariantAdjudicator.run_l2_behavioral_probes(tdir, target_code, b2_pass_l1, b2_art.get("execution_trace", []))
        b2_art["layer2_behavioral_adjudication"] = b2_adj

        with open(os.path.join(task_runs_dir, "b2_raw.json"), "w", encoding="utf-8") as f:
            json.dump(b2_art, f, indent=2)

        l1_str = "PASS" if b2_pass_l1 else "FAIL"
        l2_str = "PASS" if b2_adj["layer2_passed"] else "FAIL"
        print(f" [L1: {l1_str} | L2: {l2_str}]")
        time.sleep(2)

        # Claude B4 Run
        print("  Running Claude B4 (Agent + S-Class + Pytest Repair)...", end="", flush=True)
        b4_art = run_baseline_b4(tdir, spec, provider)
        b4_pass_l1 = b4_art["oracle_result"]["all_passed"]
        
        target_code_b4 = b4_art.get("final_code", "")
        b4_adj = BehavioralInvariantAdjudicator.run_l2_behavioral_probes(tdir, target_code_b4, b4_pass_l1, b4_art.get("execution_trace", []))
        b4_art["layer2_behavioral_adjudication"] = b4_adj

        with open(os.path.join(task_runs_dir, "b4_raw.json"), "w", encoding="utf-8") as f:
            json.dump(b4_art, f, indent=2)

        l1_b4_str = "PASS" if b4_pass_l1 else "FAIL"
        l2_b4_str = "PASS" if b4_adj["layer2_passed"] else "FAIL"
        print(f" [L1: {l1_b4_str} | L2: {l2_b4_str}]")
        time.sleep(2)

        all_results.extend([b2_art, b4_art])

    generate_claude_summary_reports(all_results, h6_2_dir)

def generate_claude_summary_reports(results: List[Dict[str, Any]], h6_2_dir: str):
    b2_runs = [r for r in results if r["baseline"] == "B2"]
    b4_runs = [r for r in results if r["baseline"] == "B4"]
    total_tasks = len(b2_runs)

    a = b = c = d = 0
    for b2, b4 in zip(b2_runs, b4_runs):
        b2_l2 = b2.get("layer2_behavioral_adjudication", {}).get("layer2_passed", False)
        b4_l2 = b4.get("layer2_behavioral_adjudication", {}).get("layer2_passed", False)
        if b2_l2 and b4_l2:
            a += 1
        elif b2_l2 and not b4_l2:
            b += 1
        elif not b2_l2 and b4_l2:
            c += 1
        else:
            d += 1

    exact_p = StatisticalAnalysisEngine.exact_binomial_mcnemar_p_value(b, c)
    b2_l2_passed = sum(1 for r in b2_runs if r.get("layer2_behavioral_adjudication", {}).get("layer2_passed", False))
    b4_l2_passed = sum(1 for r in b4_runs if r.get("layer2_behavioral_adjudication", {}).get("layer2_passed", False))
    ci_stats = StatisticalAnalysisEngine.compute_difference_95ci(b2_l2_passed, b4_l2_passed, total_tasks)

    report = {
        "title": "Claude Cross-Model H6.2 Replication Report",
        "sample_size_tasks": total_tasks,
        "total_executions": len(results),
        "model_evaluated": b2_runs[0].get("provider_config", {}).get("model_name", "claude"),
        "contingency_table": {"a": a, "b": b, "c": c, "d": d, "discordant_pairs": b + c},
        "exact_mcnemar_p_value": exact_p,
        "ci_stats": ci_stats
    }

    json_path = os.path.join(h6_2_dir, "claude_h6_2_replication_report.json")
    md_path = os.path.join(h6_2_dir, "claude_h6_2_replication_report.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nClaude Cross-Model Replication Reports saved to {json_path} and {md_path}")

def main():
    parser = argparse.ArgumentParser(description="Claude Cross-Model H6.2 Replication Runner")
    parser.add_argument("--model", type=str, default="claude-3-5-sonnet-20241022")
    parser.add_argument("--api-key", type=str, default=None)
    parser.add_argument("--allow-mock", action="store_true")
    args = parser.parse_args()

    run_claude_replication(model_name=args.model, api_key=args.api_key, allow_mock=args.allow_mock)

if __name__ == "__main__":
    main()
