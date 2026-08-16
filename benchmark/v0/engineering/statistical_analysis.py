#!/usr/bin/env python3
"""
Gate 1.6E — Advanced Statistical & Efficiency Engine
(benchmark/v0/engineering/statistical_analysis.py)

Computes:
1. Exact Binomial McNemar's Test (exact two-tailed p-value for paired discordance).
2. 95% Confidence Interval for difference in pass rates (Delta = p_B4 - p_B2).
3. Efficiency Metrics per Success:
   - Cost / Success ($/pass)
   - Calls / Success (calls/pass)
   - Latency / Success (seconds/pass)
4. Severity-Weighted Failure Scoring:
   - wrong_requirement: 3.0
   - missing_requirement: 2.5
   - implementation_bug: 2.0
   - test_api_mismatch: 1.5
   - environment_failure: 1.0
"""

import math
from typing import Dict, List, Any, Tuple

SEVERITY_WEIGHTS = {
    "wrong_requirement": 3.0,
    "missing_requirement": 2.5,
    "implementation_bug": 2.0,
    "test_api_mismatch": 1.5,
    "environment_failure": 1.0
}

class StatisticalAnalysisEngine:
    @staticmethod
    def exact_binomial_mcnemar_p_value(b: int, c: int) -> float:
        """Computes exact two-tailed McNemar p-value using binomial distribution."""
        n = b + c
        if n == 0:
            return 1.0
        min_bc = min(b, c)
        
        # Cumulative binomial probability P(K <= min_bc) where K ~ Binomial(n, 0.5)
        p_one_tail = 0.0
        for k in range(0, min_bc + 1):
            p_one_tail += math.comb(n, k) * (0.5 ** n)
        
        p_two_tail = min(1.0, 2.0 * p_one_tail)
        return round(p_two_tail, 5)

    @staticmethod
    def compute_difference_95ci(b2_passed: int, b4_passed: int, n: int) -> Dict[str, float]:
        """Calculates 95% Confidence Interval for Delta = p_B4 - p_B2 using Wald score interval."""
        if n == 0:
            return {"delta_percentage": 0.0, "ci_lower_percentage": 0.0, "ci_upper_percentage": 0.0}

        p1 = b4_passed / float(n)
        p2 = b2_passed / float(n)
        delta = p1 - p2
        
        # Standard error of difference for paired samples (approximate)
        se = math.sqrt(max(0.0, (p1 * (1.0 - p1) + p2 * (1.0 - p2)) / float(n)))
        z_crit = 1.96  # 95% confidence level
        
        margin = z_crit * se
        ci_lower = max(-1.0, delta - margin)
        ci_upper = min(1.0, delta + margin)

        return {
            "delta_percentage": round(delta * 100.0, 2),
            "ci_lower_percentage": round(ci_lower * 100.0, 2),
            "ci_upper_percentage": round(ci_upper * 100.0, 2)
        }

    @staticmethod
    def calculate_severity_score(failure_counts: Dict[str, int]) -> float:
        """Calculates severity-weighted failure score for a baseline."""
        score = 0.0
        for cat, weight in SEVERITY_WEIGHTS.items():
            score += failure_counts.get(cat, 0) * weight
        return round(score, 2)

    @staticmethod
    def analyze_paired_baselines(b2_runs: List[Dict[str, Any]], b4_runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Computes exact McNemar test, 95% CIs, efficiency metrics, and severity scores."""
        b2_map = {r["task_id"]: r for r in b2_runs}
        b4_map = {r["task_id"]: r for r in b4_runs}
        common_tasks = sorted(list(set(b2_map.keys()).intersection(set(b4_map.keys()))))
        n_tasks = len(common_tasks)

        a, b, c, d = 0, 0, 0, 0
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

        # Exact McNemar test
        exact_p = StatisticalAnalysisEngine.exact_binomial_mcnemar_p_value(b, c)
        chi2_stat = (((abs(b - c) - 1.0) ** 2) / float(b + c)) if (b + c) > 0 else 0.0

        # 95% Confidence Interval for difference
        b2_pass_total = sum(1 for r in b2_runs if r["oracle_result"]["all_passed"])
        b4_pass_total = sum(1 for r in b4_runs if r["oracle_result"]["all_passed"])
        ci_stats = StatisticalAnalysisEngine.compute_difference_95ci(b2_pass_total, b4_pass_total, n_tasks)

        # Efficiency & Severity calculation
        def compute_efficiency_and_severity(b_runs):
            passed_count = sum(1 for r in b_runs if r["oracle_result"]["all_passed"])
            tot_cost = sum(sum(t["cost_usd"] for t in r.get("execution_trace", [])) for r in b_runs)
            tot_calls = sum(len(r.get("execution_trace", [])) for r in b_runs)
            tot_latency = sum(sum(t["latency_sec"] for t in r.get("execution_trace", [])) for r in b_runs)
            avg_latency = tot_latency / max(1, len(b_runs))

            # Failure taxonomy counts
            failed_runs = [r for r in b_runs if not r["oracle_result"]["all_passed"]]
            tax_counts = {cat: 0 for cat in SEVERITY_WEIGHTS.keys()}
            for r in failed_runs:
                cat = r.get("failure_taxonomy", {}).get("category", "wrong_requirement")
                if cat in tax_counts:
                    tax_counts[cat] += 1
                else:
                    tax_counts["wrong_requirement"] += 1

            severity_score = StatisticalAnalysisEngine.calculate_severity_score(tax_counts)

            return {
                "passed_tasks": passed_count,
                "total_tasks": len(b_runs),
                "pass_rate": round((passed_count / max(1, len(b_runs))) * 100.0, 2),
                "total_cost_usd": round(tot_cost, 6),
                "cost_per_success_usd": round(tot_cost / max(1, passed_count), 6),
                "total_model_calls": tot_calls,
                "calls_per_success": round(tot_calls / max(1, passed_count), 2),
                "avg_latency_sec": round(avg_latency, 3),
                "latency_per_success_sec": round(tot_latency / max(1, passed_count), 3),
                "failure_taxonomy_counts": tax_counts,
                "severity_weighted_failure_score": severity_score
            }

        b2_metrics = compute_efficiency_and_severity(b2_runs)
        b4_metrics = compute_efficiency_and_severity(b4_runs)

        return {
            "comparison": "B4 (Model + S-Class + Test Repair) vs B2 (Model + Test Repair)",
            "sample_size_tasks": n_tasks,
            "contingency_table": {
                "a_both_pass": a,
                "b_b2_pass_b4_fail": b,
                "c_b4_pass_b2_fail": c,
                "d_both_fail": d,
                "discordant_pairs": b + c
            },
            "statistical_test": {
                "test_name": "Exact Binomial McNemar Test",
                "chi2_statistic": round(chi2_stat, 4),
                "exact_p_value": exact_p,
                "statistically_significant_p05": exact_p < 0.05
            },
            "difference_confidence_interval_95": ci_stats,
            "efficiency_and_severity_metrics": {
                "B2_Model_Pytest_Loop": b2_metrics,
                "B4_Model_SClass_Pytest_Loop": b4_metrics
            },
            "task_level_outcomes": task_outcomes
        }
