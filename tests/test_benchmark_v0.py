"""
S-Class EOS — Verification Benchmark V0 Test Suite
(tests/test_benchmark_v0.py)

Validates:
1. Task schema conformance and ground-truth freezing across all 15 tasks.
2. Benchmark harness task loading and execution lifecycle.
3. Baseline evaluation ladder (B1 Plain LLM, B2 LLM + Tests, B4 S-Class Verification Core).
4. Statistical metrics computation (Precision, Recall, FAR, FRR, Intervention Rate, Time-to-Trust).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark.v0.schema import (
    BenchmarkTask, TaskDifficulty, TaskCategory, FailureSeverity, BaselineType
)
from benchmark.v0.harness import VerificationBenchmarkHarness
from benchmark.v0.baselines import (
    B1PlainLLMRunner, B2LLMWithTestsRunner, B4SClassVerificationRunner
)


class TestVerificationBenchmarkV0(unittest.TestCase):
    """Test suite for Gate 1 Verification Benchmark V0 infrastructure."""

    def setUp(self):
        self.plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.tasks_dir = os.path.join(self.plugin_root, "benchmark", "v0", "tasks")
        self.harness = VerificationBenchmarkHarness(self.tasks_dir)

    def test_01_all_15_benchmark_tasks_loaded_and_schema_valid(self):
        """Invariant: All 15 frozen benchmark tasks load with non-empty ground-truth contracts."""
        self.assertGreaterEqual(len(self.harness.tasks), 15, "Must load at least 15 frozen benchmark tasks")
        
        for task_id, task in self.harness.tasks.items():
            self.assertIsInstance(task.task_id, str)
            self.assertGreater(len(task.title), 0)
            self.assertGreater(len(task.explicit_requirements), 0, f"Task {task_id} missing explicit requirements")
            self.assertGreater(len(task.derived_requirements), 0, f"Task {task_id} missing derived requirements")
            self.assertGreater(len(task.file_boundaries.allowed_files), 0, f"Task {task_id} missing allowed files")
            self.assertGreater(len(task.failure_taxonomy), 0, f"Task {task_id} missing failure taxonomy")
            self.assertIsNotNone(task.oracle.test_command)

    def test_02_baseline_runners_execution_and_evaluation(self):
        """Invariant: Benchmark harness evaluates B1, B2, and B4 against independent ground truth."""
        b1_runner = B1PlainLLMRunner()
        b2_runner = B2LLMWithTestsRunner()
        b4_runner = B4SClassVerificationRunner()

        b1_results = []
        b2_results = []
        b4_results = []

        for task_id, task in self.harness.tasks.items():
            # Run B1
            b1_out = b1_runner.run_task(task, self.plugin_root)
            b1_res = self.harness.evaluate_task_execution(
                task=task,
                baseline=b1_out["baseline"],
                modified_files=b1_out["modified_files"],
                oracle_passed=b1_out["oracle_passed"],
                synthesized_requirements=b1_out["synthesized_requirements"],
                execution_duration_sec=b1_out["duration_sec"],
                token_cost_usd=b1_out["token_cost_usd"],
                intervention_required=b1_out["developer_intervention_required"]
            )
            b1_results.append(b1_res)

            # Run B2
            b2_out = b2_runner.run_task(task, self.plugin_root)
            b2_res = self.harness.evaluate_task_execution(
                task=task,
                baseline=b2_out["baseline"],
                modified_files=b2_out["modified_files"],
                oracle_passed=b2_out["oracle_passed"],
                synthesized_requirements=b2_out["synthesized_requirements"],
                execution_duration_sec=b2_out["duration_sec"],
                token_cost_usd=b2_out["token_cost_usd"],
                intervention_required=b2_out["developer_intervention_required"]
            )
            b2_results.append(b2_res)

            # Run B4 (S-Class)
            b4_out = b4_runner.run_task(task, self.plugin_root)
            b4_res = self.harness.evaluate_task_execution(
                task=task,
                baseline=b4_out["baseline"],
                modified_files=b4_out["modified_files"],
                oracle_passed=b4_out["oracle_passed"],
                synthesized_requirements=b4_out["synthesized_requirements"],
                execution_duration_sec=b4_out["duration_sec"],
                token_cost_usd=b4_out["token_cost_usd"],
                intervention_required=b4_out["developer_intervention_required"]
            )
            b4_results.append(b4_res)

        # Calculate summaries
        b1_summary = self.harness.calculate_summary_metrics(BaselineType.B1_PLAIN_LLM, b1_results)
        b2_summary = self.harness.calculate_summary_metrics(BaselineType.B2_LLM_WITH_TESTS, b2_results)
        b4_summary = self.harness.calculate_summary_metrics(BaselineType.B4_SCLASS_VERIFICATION, b4_results)

        # Invariant Assertions: S-Class (B4) must eliminate False Acceptance and maximize Time-to-Trust
        self.assertEqual(b4_summary.false_acceptance_rate, 0.0, "S-Class must have 0% False Acceptance Rate")
        self.assertGreaterEqual(b4_summary.precision, 0.95, "S-Class precision must exceed 95%")
        self.assertGreater(b4_summary.time_to_trust_score, b1_summary.time_to_trust_score, "S-Class trust score must beat Plain LLM")
        self.assertGreater(b4_summary.time_to_trust_score, b2_summary.time_to_trust_score, "S-Class trust score must beat LLM + Tests")

        # Verify markdown report rendering
        report = self.harness.render_markdown_comparison_report({
            "B1": b1_summary,
            "B2": b2_summary,
            "B4": b4_summary
        })
        self.assertIn("S-Class EOS — Verification Benchmark V0 Results", report)
        self.assertIn("Time-to-Trust Score", report)


if __name__ == "__main__":
    unittest.main()
