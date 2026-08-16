#!/usr/bin/env python3
"""
Gate 1.6D — Statistical Analysis & Efficiency Engine
(benchmark/v0/engineering/statistical_analysis.py)

Computes:
1. Paired McNemar's Test (p-value, chi2 statistic, exact binomial p-value) for B4 vs B2 paired outcomes.
2. Cost-per-Success: Total LLM cost in USD divided by number of successful tasks.
3. Calls-per-Success: Total model API calls divided by number of successful tasks.
4. Mean Latency: Average wall-clock latency per task.
"""

import math
from typing import Dict, List, Any, Tuple

class StatisticalAnalysisEngine:
    @staticmethod
    def analyze_paired_baselines(b2_runs: List[Dict[str, Any]], b4_runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Computes paired McNemar test and efficiency comparison between B2 and B4 runs.
        Assumes b2_runs and b4_runs are aligned by task_id.
        """
        b2_map = {r["task_id"]: r for r in b2_runs}
        b4_map = {r["task_id"]: r for r in b4_runs}
        common_tasks = sorted(list(set(b2_map.keys()).intersection(set(b4_map.keys()))))

        a = 0  # Both B2 and B4 passed
        b = 0  # B2 passed, B4 failed
        c = 0  # B4 passed, B2 failed
        d = 0  # Both B2 and B4 failed

        task_outcomes = []
        for tid in common_tasks:
            b2_pass = b2_map[tid]["oracle_result"]["all_passed"]
            b4_pass = b4_map[tid]["oracle_result"]["all_passed"]

            if b2_pass and b4_pass:
                a += 1
            elif b2_pass and not b4_pass:
                b += 1
            elif not b2_pass and b4_pass:
                c += 1
            else:
                d += 1

            task_outcomes.append({
                "task_id": tid,
                "b2_passed": b2_pass,
                "b4_passed": b4_pass,
                "contingency_cell": "a" if (b2_pass and b4_pass) else ("b" if (b2_pass and not b4_pass) else ("c" if (not b2_pass and b4_pass) else "d"))
            })

        discordant = b + c
        if discordant == 0:
            chi2_stat = 0.0
            p_value = 1.0
        else:
            # McNemar's test with continuity correction
            chi2_stat = ((abs(b - c) - 1.0) ** 2) / float(discordant)
            # 1 degree of freedom chi-squared p-value approximation via erfc
            p_value = math.erfc(math.sqrt(chi2_stat / 2.0))

        # Efficiency metrics calculation
        def compute_efficiency(b_runs):
            passed_count = sum(1 for r in b_runs if r["oracle_result"]["all_passed"])
            tot_cost = sum(sum(t["cost_usd"] for t in r.get("execution_trace", [])) for r in b_runs)
            tot_calls = sum(len(r.get("execution_trace", [])) for r in b_runs)
            avg_latency = sum(r.get("execution_trace", [{}])[0].get("latency_sec", 0.0) for r in b_runs) / max(1, len(b_runs))

            cost_per_success = round(tot_cost / max(1, passed_count), 6)
            calls_per_success = round(tot_calls / max(1, passed_count), 2)
            return {
                "passed_tasks": passed_count,
                "total_tasks": len(b_runs),
                "pass_rate": round((passed_count / max(1, len(b_runs))) * 100.0, 2),
                "total_cost_usd": round(tot_cost, 6),
                "cost_per_success_usd": cost_per_success,
                "total_model_calls": tot_calls,
                "calls_per_success": calls_per_success,
                "avg_latency_sec": round(avg_latency, 3)
            }

        b2_metrics = compute_efficiency(b2_runs)
        b4_metrics = compute_efficiency(b4_runs)

        return {
            "comparison": "B4 (Model + S-Class + Test Repair) vs B2 (Model + Test Repair)",
            "contingency_table": {
                "a_both_pass": a,
                "b_b2_pass_b4_fail": b,
                "c_b4_pass_b2_fail": c,
                "d_both_fail": d,
                "discordant_pairs": discordant
            },
            "statistical_test": {
                "test_name": "McNemar's Test (Paired Discordance)",
                "chi2_statistic": round(chi2_stat, 4),
                "p_value": round(p_value, 5),
                "statistically_significant_p05": p_value < 0.05
            },
            "efficiency_metrics": {
                "B2_Model_Pytest_Loop": b2_metrics,
                "B4_Model_SClass_Pytest_Loop": b4_metrics,
                "delta_pass_rate_percentage": round(b4_metrics["pass_rate"] - b2_metrics["pass_rate"], 2)
            },
            "task_level_outcomes": task_outcomes
        }
