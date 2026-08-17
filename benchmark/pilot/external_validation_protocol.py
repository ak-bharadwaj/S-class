"""
S-Class EOS V11.2 - External Developer Validation Protocol & Trial Harness.
Provides the protocol specification, within-participant counterbalanced A/B trial assignment,
measurement provenance tracking, and data collection harness for evaluating real developer tasks
comparing Baseline (Ungoverned) vs S-Class Treatment.

DESIGN PRINCIPLES:
1. Target Cohort: 6–10 professional developers performing 3 tasks each (18–30 total task trials).
2. Within-Participant Counterbalancing: Each participant experiences both Baseline and S-Class conditions
   across different tasks to separate individual developer skill variance from the treatment effect.
3. Explicit Measurement Provenance:
   - INSTRUMENTED: task_completion_time_sec
   - RECEIPT_DERIVED: defects_caught_pre_gen, defects_caught_post_gen
   - PARTICIPANT_REPORTED: rework_iterations, developer_interventions, trust_score (1-5), usefulness_score (1-5)
   - PROTOCOL_ASSIGNED: assignment, task_order_index, task_outcome (SUCCESS / FAILURE / ABANDONED)
4. Credibility & Falsifiability: Negative results and abandoned tasks are fully valid and preserved.
"""

import os
import sys
import json
import time
import hashlib
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field, asdict

repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from enterprise_pipeline import EnterpriseGovernancePipeline
from evidence_provider import default_provider_registry
from benchmark.hypothesis_parity.observation import StrategySpec


class MeasurementProvenance:
    INSTRUMENTED = "INSTRUMENTED"
    PARTICIPANT_REPORTED = "PARTICIPANT_REPORTED"
    RECEIPT_DERIVED = "RECEIPT_DERIVED"
    PROTOCOL_ASSIGNED = "PROTOCOL_ASSIGNED"


METRIC_PROVENANCE_SCHEMA = {
    "task_completion_time_sec": MeasurementProvenance.INSTRUMENTED,
    "rework_iterations": MeasurementProvenance.PARTICIPANT_REPORTED,
    "developer_interventions": MeasurementProvenance.PARTICIPANT_REPORTED,
    "developer_trust_score": MeasurementProvenance.PARTICIPANT_REPORTED,
    "developer_usefulness_score": MeasurementProvenance.PARTICIPANT_REPORTED,
    "defects_caught_pre_gen": MeasurementProvenance.RECEIPT_DERIVED,
    "defects_caught_post_gen": MeasurementProvenance.RECEIPT_DERIVED,
    "assignment": MeasurementProvenance.PROTOCOL_ASSIGNED,
    "task_order_index": MeasurementProvenance.PROTOCOL_ASSIGNED,
    "task_outcome": MeasurementProvenance.PROTOCOL_ASSIGNED
}


@dataclass
class DeveloperTrialRecord:
    """Records one developer task trial outcome with within-participant sequencing and outcome tracking."""
    participant_id: str
    task_id: str
    task_order_index: int  # 1, 2, or 3 in the developer's session
    assignment: str  # "BASELINE" or "SCLASS_TREATMENT"
    is_real_participant: bool  # False for protocol smoke checks, True for real developer trials
    task_completion_time_sec: float
    defects_caught_pre_gen: int
    defects_caught_post_gen: int
    rework_iterations: int
    developer_interventions: int
    task_outcome: str = "SUCCESS"  # "SUCCESS" | "FAILURE" | "ABANDONED"
    developer_trust_score: Optional[float] = None  # 1.0 - 5.0 (None if not participant-reported)
    developer_usefulness_score: Optional[float] = None  # 1.0 - 5.0 (None if not participant-reported)
    trial_verdict: str = "SUCCESS"
    audit_notes: List[str] = field(default_factory=list)
    measurement_sources: Dict[str, str] = field(default_factory=lambda: dict(METRIC_PROVENANCE_SCHEMA))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ExternalValidationProtocol:
    """Manages randomized counterbalanced trials, real task execution, and paired statistical summaries."""

    def __init__(self):
        self.pipeline = EnterpriseGovernancePipeline(default_provider_registry)
        self.trials: List[DeveloperTrialRecord] = []

    @staticmethod
    def get_standard_task_catalog() -> List[Dict[str, Any]]:
        """Catalog of 3 comparable real-world developer tasks."""
        return [
            {
                "task_id": "TASK-01-TOKEN-RATE-LIMITER",
                "title": "Token Bucket Rate Limiter with Concurrency Safety",
                "description": "Implement token bucket rate limiter with replenish rate, burst capacity, and concurrent file locking.",
                "obligations": [
                    {
                        "obligation_id": "OBL-RATE-NON-NEGATIVE",
                        "obligation_type": "property",
                        "strategy_specs": {"tokens": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 1000})},
                        "max_examples": 30
                    }
                ]
            },
            {
                "task_id": "TASK-02-CONFIG-SCHEMA-PARSER",
                "title": "Strict Configuration Schema Parser",
                "description": "Implement configuration loader parsing JSON schema without dynamic code execution.",
                "obligations": [
                    {
                        "obligation_id": "OBL-CONFIG-AST",
                        "obligation_type": "static_analysis",
                        "forbidden_ast_nodes": ["Exec", "Eval"]
                    }
                ]
            },
            {
                "task_id": "TASK-03-IDEMPOTENT-CACHE",
                "title": "Idempotent State Cache with Eviction",
                "description": "Implement key-value cache guaranteeing idempotency and lossless item retrieval.",
                "obligations": [
                    {
                        "obligation_id": "OBL-CACHE-ROUNDTRIP",
                        "obligation_type": "property",
                        "strategy_specs": {"key": StrategySpec(strategy_type="text", params={"min_size": 1, "max_size": 20})},
                        "max_examples": 25
                    }
                ]
            }
        ]

    @staticmethod
    def assign_treatment_counterbalanced(participant_id: str, task_order_index: int, seed: Optional[int] = None) -> str:
        """
        Assigns treatment condition using within-participant counterbalancing:
        Determines starting condition via participant hash, then alternates across task 1, 2, and 3.
        Distributes individual skill variance and counterbalances learning effects.
        """
        key = f"{participant_id}:{seed or 42}".encode("utf-8")
        h = int(hashlib.sha256(key).hexdigest(), 16)
        starting_condition = "SCLASS_TREATMENT" if (h % 2 == 0) else "BASELINE"

        # Alternate condition across task indices: 1 -> start, 2 -> other, 3 -> start
        if task_order_index % 2 == 1:
            return starting_condition
        else:
            return "BASELINE" if starting_condition == "SCLASS_TREATMENT" else "SCLASS_TREATMENT"

    def record_trial(self, trial: DeveloperTrialRecord) -> None:
        """Records a developer trial record."""
        self.trials.append(trial)

    def execute_protocol_smoke_trial(
        self,
        participant_id: str,
        task_id: str,
        task_order_index: int,
        assignment: str,
        code_generator: Callable[[Any], Any]
    ) -> DeveloperTrialRecord:
        """
        Protocol Smoke Mode:
        Verifies instrument, task sequence, and pipeline mechanics.
        Participant-reported metrics remain strictly None.
        """
        t0 = time.perf_counter()
        task = next((t for t in self.get_standard_task_catalog() if t["task_id"] == task_id), None)
        if task is None:
            raise ValueError(f"Unknown task_id: {task_id}")

        if assignment == "BASELINE":
            target = code_generator(None)
            duration = round(time.perf_counter() - t0, 3)
            return DeveloperTrialRecord(
                participant_id=participant_id,
                task_id=task_id,
                task_order_index=task_order_index,
                assignment="BASELINE",
                is_real_participant=False,
                task_completion_time_sec=duration,
                defects_caught_pre_gen=0,
                defects_caught_post_gen=0,
                rework_iterations=0,
                developer_interventions=0,
                task_outcome="SUCCESS",
                developer_trust_score=None,
                developer_usefulness_score=None,
                trial_verdict="SUCCESS",
                audit_notes=["Protocol smoke simulation - Baseline"]
            )
        else:
            target, receipt = self.pipeline.execute_governed_cycle(
                request_text=task["description"],
                code_generator=code_generator,
                custom_obligations=task["obligations"]
            )
            duration = round(time.perf_counter() - t0, 3)
            verdict = "SUCCESS" if receipt.verdict == "PASS" else "BLOCKED_WITH_REASON"
            return DeveloperTrialRecord(
                participant_id=participant_id,
                task_id=task_id,
                task_order_index=task_order_index,
                assignment="SCLASS_TREATMENT",
                is_real_participant=False,
                task_completion_time_sec=duration,
                defects_caught_pre_gen=0 if receipt.pre_gen_grounded else 1,
                defects_caught_post_gen=receipt.obligations_failed,
                rework_iterations=0,
                developer_interventions=0,
                task_outcome="SUCCESS",
                developer_trust_score=None,
                developer_usefulness_score=None,
                trial_verdict=verdict,
                audit_notes=receipt.blocking_reasons or ["Protocol smoke simulation - Governed Pass"]
            )

    def execute_participant_trial(
        self,
        participant_id: str,
        task_id: str,
        task_order_index: int,
        code_generator: Callable[[Any], Any],
        rework_iterations: int,
        developer_interventions: int,
        task_outcome: str,
        trust_score: float,
        usefulness_score: float,
        seed: Optional[int] = None
    ) -> DeveloperTrialRecord:
        """
        Experimental Participant Mode:
        Executes ONLY the counterbalanced assigned condition for this participant and task index.
        Records instrumented completion time, outcome (SUCCESS/FAILURE/ABANDONED), and Likert scores.
        """
        task = next((t for t in self.get_standard_task_catalog() if t["task_id"] == task_id), None)
        if task is None:
            raise ValueError(f"Unknown task_id: {task_id}")

        assigned_condition = self.assign_treatment_counterbalanced(participant_id, task_order_index, seed)
        t0 = time.perf_counter()

        if assigned_condition == "BASELINE":
            target = code_generator(None)
            duration = round(time.perf_counter() - t0, 3)
            trial = DeveloperTrialRecord(
                participant_id=participant_id,
                task_id=task_id,
                task_order_index=task_order_index,
                assignment="BASELINE",
                is_real_participant=True,
                task_completion_time_sec=duration,
                defects_caught_pre_gen=0,
                defects_caught_post_gen=0,
                rework_iterations=rework_iterations,
                developer_interventions=developer_interventions,
                task_outcome=task_outcome,
                developer_trust_score=trust_score,
                developer_usefulness_score=usefulness_score,
                trial_verdict="SUCCESS" if task_outcome == "SUCCESS" else "FAILED_OR_ABANDONED",
                audit_notes=["Real participant trial - Baseline condition"]
            )
        else:
            target, receipt = self.pipeline.execute_governed_cycle(
                request_text=task["description"],
                code_generator=code_generator,
                custom_obligations=task["obligations"]
            )
            duration = round(time.perf_counter() - t0, 3)
            verdict = "SUCCESS" if (receipt.verdict == "PASS" and task_outcome == "SUCCESS") else "BLOCKED_OR_FAILED"
            trial = DeveloperTrialRecord(
                participant_id=participant_id,
                task_id=task_id,
                task_order_index=task_order_index,
                assignment="SCLASS_TREATMENT",
                is_real_participant=True,
                task_completion_time_sec=duration,
                defects_caught_pre_gen=0 if receipt.pre_gen_grounded else 1,
                defects_caught_post_gen=receipt.obligations_failed,
                rework_iterations=rework_iterations,
                developer_interventions=developer_interventions,
                task_outcome=task_outcome,
                developer_trust_score=trust_score,
                developer_usefulness_score=usefulness_score,
                trial_verdict=verdict,
                audit_notes=receipt.blocking_reasons or ["Real participant trial - S-Class Treatment"]
            )

        self.record_trial(trial)
        return trial

    def generate_validation_summary(self, tested_sha: Optional[str] = None) -> Dict[str, Any]:
        """Aggregates recorded trials into paired statistical metrics and outcome breakdowns."""
        commit_sha = tested_sha or os.environ.get("GITHUB_SHA", "UNKNOWN")
        real_trials = [t for t in self.trials if t.is_real_participant]
        smoke_trials = [t for t in self.trials if not t.is_real_participant]

        real_baseline = [t for t in real_trials if t.assignment == "BASELINE"]
        real_treatment = [t for t in real_trials if t.assignment == "SCLASS_TREATMENT"]

        def _mean(lst: List[float]) -> Optional[float]:
            return round(sum(lst) / len(lst), 3) if lst else None

        real_trust_scores = [t.developer_trust_score for t in real_treatment if t.developer_trust_score is not None]
        real_usefulness_scores = [t.developer_usefulness_score for t in real_treatment if t.developer_usefulness_score is not None]

        # Count outcomes
        baseline_outcomes = {
            "success": sum(1 for t in real_baseline if t.task_outcome == "SUCCESS"),
            "failure": sum(1 for t in real_baseline if t.task_outcome == "FAILURE"),
            "abandoned": sum(1 for t in real_baseline if t.task_outcome == "ABANDONED")
        }
        treatment_outcomes = {
            "success": sum(1 for t in real_treatment if t.task_outcome == "SUCCESS"),
            "failure": sum(1 for t in real_treatment if t.task_outcome == "FAILURE"),
            "abandoned": sum(1 for t in real_treatment if t.task_outcome == "ABANDONED")
        }

        # Status: Real evidence is sufficient once at least 6 developers complete all 3 tasks (>= 18 trials)
        has_sufficient_evidence = (len(set(t.participant_id for t in real_trials)) >= 6 and len(real_trials) >= 18)

        return {
            "protocol_id": f"EXTERNAL-VALIDATION-PROTOCOL-{commit_sha[:12].upper()}",
            "schema_version": "1.1.0",
            "milestone": "THESIS-GATE-1B: External Developer Validation Protocol",
            "protocol_design": {
                "study_design": "Within-participant counterbalanced crossover across 3 tasks",
                "target_cohort_size": "6-10 developers (3 tasks each, 18-30 total trials)",
                "task_catalog_size": len(self.get_standard_task_catalog()),
                "metric_provenance_schema": METRIC_PROVENANCE_SCHEMA,
                "recorded_outcomes": ["SUCCESS", "FAILURE", "ABANDONED"]
            },
            "provenance": {
                "tested_source_sha": commit_sha,
                "total_trials_recorded": len(self.trials),
                "real_participant_trials_count": len(real_trials),
                "protocol_smoke_trials_count": len(smoke_trials),
                "real_participants_enrolled": len(set(t.participant_id for t in real_trials)),
                "timestamp_utc": time.time(),
                "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            },
            "external_evidence_status": "REAL_EVIDENCE_AVAILABLE" if has_sufficient_evidence else "AWAITING_REAL_PARTICIPANTS",
            "real_participant_metrics": {
                "baseline": {
                    "trials_count": len(real_baseline),
                    "outcomes": baseline_outcomes,
                    "mean_completion_time_sec": _mean([t.task_completion_time_sec for t in real_baseline]),
                    "mean_rework_iterations": _mean([float(t.rework_iterations) for t in real_baseline]),
                    "mean_developer_interventions": _mean([float(t.developer_interventions) for t in real_baseline]),
                    "mean_trust_score": _mean([t.developer_trust_score for t in real_baseline if t.developer_trust_score is not None]),
                    "mean_usefulness_score": _mean([t.developer_usefulness_score for t in real_baseline if t.developer_usefulness_score is not None])
                },
                "sclass_treatment": {
                    "trials_count": len(real_treatment),
                    "outcomes": treatment_outcomes,
                    "mean_completion_time_sec": _mean([t.task_completion_time_sec for t in real_treatment]),
                    "mean_rework_iterations": _mean([float(t.rework_iterations) for t in real_treatment]),
                    "mean_developer_interventions": _mean([float(t.developer_interventions) for t in real_treatment]),
                    "mean_trust_score": _mean(real_trust_scores),
                    "mean_usefulness_score": _mean(real_usefulness_scores),
                    "pre_gen_defects_caught": sum(t.defects_caught_pre_gen for t in real_treatment),
                    "post_gen_defects_caught": sum(t.defects_caught_post_gen for t in real_treatment)
                }
            },
            "trials": [t.to_dict() for t in self.trials],
            "protocol_readiness": "READY_FOR_EXTERNAL_PARTICIPANTS"
        }


def run_external_validation_smoke(output_path: Optional[str] = None, tested_sha: Optional[str] = None) -> Dict[str, Any]:
    """Runs a protocol smoke test verifying counterbalancing, instrument mechanics, and schema integrity."""
    protocol = ExternalValidationProtocol()

    def gen_rate_limiter(spec):
        return lambda tokens: tokens >= 0

    def gen_config_parser(spec):
        return "def parse_config(raw_json):\n    import json\n    return json.loads(raw_json)\n"

    def gen_cache(spec):
        return lambda key: len(key) >= 1

    tasks = protocol.get_standard_task_catalog()
    generators = [gen_rate_limiter, gen_config_parser, gen_cache]

    for i, (task, gen) in enumerate(zip(tasks, generators)):
        order_idx = i + 1
        protocol.record_trial(protocol.execute_protocol_smoke_trial(f"smoke_dev_{order_idx}", task["task_id"], order_idx, "BASELINE", gen))
        protocol.record_trial(protocol.execute_protocol_smoke_trial(f"smoke_dev_{order_idx}", task["task_id"], order_idx, "SCLASS_TREATMENT", gen))

    summary = protocol.generate_validation_summary(tested_sha=tested_sha)
    out_file = output_path if output_path else os.path.join(os.path.dirname(__file__), "external_validation_protocol_receipt.json")
    os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"External Validation Protocol Specification written to {out_file}.")
    print(f"Protocol Readiness: {summary['protocol_readiness']}. External Evidence Status: {summary['external_evidence_status']}.")
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="External Validation Protocol Runner")
    parser.add_argument("--mode", type=str, choices=["smoke", "participant"], default="smoke", help="Execution mode")
    parser.add_argument("--participant", type=str, default="test_dev_01", help="Participant ID")
    parser.add_argument("--task", type=str, default="TASK-01-TOKEN-RATE-LIMITER", help="Task ID")
    parser.add_argument("--task-order", type=int, default=1, choices=[1, 2, 3], help="Task order index in session (1, 2, 3)")
    parser.add_argument("--output", type=str, default=None, help="Output JSON receipt path")
    parser.add_argument("--sha", type=str, default=None, help="Tested Git commit SHA")
    args = parser.parse_args()

    if args.mode == "smoke":
        run_external_validation_smoke(output_path=args.output, tested_sha=args.sha)
    else:
        protocol = ExternalValidationProtocol()
        assignment = protocol.assign_treatment_counterbalanced(args.participant, args.task_order)
        print(f"=== S-CLASS EXTERNAL DEVELOPER STUDY TRIAL ===")
        print(f"Participant: {args.participant}")
        print(f"Task: {args.task} (Order #{args.task_order})")
        print(f"Assigned Condition: {assignment}")
        print(f"Instructions: Complete the development task under condition: {assignment}.")
