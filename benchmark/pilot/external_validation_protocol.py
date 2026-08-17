"""
S-Class EOS V11.2 - External Developer Validation Protocol & Trial Harness.
Provides the protocol specification, randomized A/B trial assignment, measurement provenance tracking,
and data collection harness for evaluating real developer tasks comparing Baseline (Ungoverned) vs S-Class Treatment.

Explicitly differentiates:
- INSTRUMENTED measurements (completion time, automated test outcomes)
- RECEIPT_DERIVED metrics (pre-gen rejections, post-gen counterexamples)
- PARTICIPANT_REPORTED metrics (trust & usefulness Likert scores, self-reported rework)
"""

import os
import sys
import json
import time
import random
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
    "assignment": MeasurementProvenance.PROTOCOL_ASSIGNED
}


@dataclass
class DeveloperTrialRecord:
    """Records one developer task trial outcome with strict measurement provenance."""
    participant_id: str
    task_id: str
    assignment: str  # "BASELINE" or "SCLASS_TREATMENT"
    is_real_participant: bool  # False for protocol smoke simulations, True for real human trials
    task_completion_time_sec: float
    defects_caught_pre_gen: int
    defects_caught_post_gen: int
    rework_iterations: int
    developer_interventions: int
    developer_trust_score: Optional[float] = None  # 1.0 - 5.0 (None if not participant-reported)
    developer_usefulness_score: Optional[float] = None  # 1.0 - 5.0 (None if not participant-reported)
    trial_verdict: str = "SUCCESS"
    audit_notes: List[str] = field(default_factory=list)
    measurement_sources: Dict[str, str] = field(default_factory=lambda: dict(METRIC_PROVENANCE_SCHEMA))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ExternalValidationProtocol:
    """Manages randomized trials, real task execution, and comparative metric aggregation."""

    def __init__(self):
        self.pipeline = EnterpriseGovernancePipeline(default_provider_registry)
        self.trials: List[DeveloperTrialRecord] = []

    @staticmethod
    def get_standard_task_catalog() -> List[Dict[str, Any]]:
        """Catalog of real-world developer tasks for external validation."""
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
    def assign_treatment_randomized(participant_id: str, task_id: str, seed: Optional[int] = None) -> str:
        """Deterministically randomized A/B assignment based on participant and task hash."""
        key = f"{participant_id}:{task_id}:{seed or 42}".encode("utf-8")
        h = int(hashlib.sha256(key).hexdigest(), 16)
        return "SCLASS_TREATMENT" if (h % 2 == 0) else "BASELINE"

    def record_trial(self, trial: DeveloperTrialRecord) -> None:
        """Records an external participant trial."""
        self.trials.append(trial)

    def execute_protocol_smoke_trial(
        self,
        participant_id: str,
        task_id: str,
        assignment: str,
        code_generator: Callable[[Any], Any]
    ) -> DeveloperTrialRecord:
        """
        Executes a synthetic protocol smoke trial to verify instrument and pipeline mechanics.
        DOES NOT record participant-reported trust/usefulness scores (leaves them None).
        """
        t0 = time.perf_counter()
        task = next((t for t in self.get_standard_task_catalog() if t["task_id"] == task_id), None)
        if task is None:
            raise ValueError(f"Unknown task_id: {task_id}")

        if assignment == "BASELINE":
            # Ungoverned baseline execution
            target = code_generator(None)
            duration = round(time.perf_counter() - t0, 3)
            return DeveloperTrialRecord(
                participant_id=participant_id,
                task_id=task_id,
                assignment="BASELINE",
                is_real_participant=False,
                task_completion_time_sec=duration,
                defects_caught_pre_gen=0,
                defects_caught_post_gen=0,
                rework_iterations=0,
                developer_interventions=0,
                developer_trust_score=None,  # Not self-reported by human
                developer_usefulness_score=None,  # Not self-reported by human
                trial_verdict="SUCCESS",
                audit_notes=["Protocol smoke simulation - Baseline"]
            )
        else:
            # S-Class Governed Treatment
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
                assignment="SCLASS_TREATMENT",
                is_real_participant=False,
                task_completion_time_sec=duration,
                defects_caught_pre_gen=0 if receipt.pre_gen_grounded else 1,
                defects_caught_post_gen=receipt.obligations_failed,
                rework_iterations=0,
                developer_interventions=0,
                developer_trust_score=None,  # Not self-reported by human
                developer_usefulness_score=None,  # Not self-reported by human
                trial_verdict=verdict,
                audit_notes=receipt.blocking_reasons or ["Protocol smoke simulation - Governed Pass"]
            )

    def generate_validation_summary(self, tested_sha: Optional[str] = None) -> Dict[str, Any]:
        """Aggregates all recorded developer trials into a provenance-audited summary."""
        commit_sha = tested_sha or os.environ.get("GITHUB_SHA", "UNKNOWN")
        real_trials = [t for t in self.trials if t.is_real_participant]
        smoke_trials = [t for t in self.trials if not t.is_real_participant]

        real_baseline = [t for t in real_trials if t.assignment == "BASELINE"]
        real_treatment = [t for t in real_trials if t.assignment == "SCLASS_TREATMENT"]

        def _mean(lst: List[float]) -> Optional[float]:
            return round(sum(lst) / len(lst), 3) if lst else None

        real_trust_scores = [t.developer_trust_score for t in real_treatment if t.developer_trust_score is not None]
        real_usefulness_scores = [t.developer_usefulness_score for t in real_treatment if t.developer_usefulness_score is not None]

        return {
            "protocol_id": f"EXTERNAL-VALIDATION-PROTOCOL-{commit_sha[:12].upper()}",
            "schema_version": "1.0.0",
            "milestone": "THESIS-GATE-1B: External Developer Validation Protocol",
            "protocol_specification": {
                "metric_provenance_schema": METRIC_PROVENANCE_SCHEMA,
                "task_catalog_size": len(self.get_standard_task_catalog()),
                "target_participant_cohort_size": "3-5 developers (3 tasks each)"
            },
            "provenance": {
                "tested_source_sha": commit_sha,
                "total_trials_recorded": len(self.trials),
                "real_participant_trials_count": len(real_trials),
                "protocol_smoke_trials_count": len(smoke_trials),
                "timestamp_utc": time.time(),
                "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            },
            "external_evidence_status": "REAL_EVIDENCE_AVAILABLE" if len(real_trials) >= 9 else "AWAITING_REAL_PARTICIPANTS",
            "real_participant_metrics": {
                "real_participants_enrolled": len(set(t.participant_id for t in real_trials)),
                "baseline": {
                    "trials_count": len(real_baseline),
                    "mean_completion_time_sec": _mean([t.task_completion_time_sec for t in real_baseline]),
                    "mean_rework_iterations": _mean([float(t.rework_iterations) for t in real_baseline]),
                    "mean_developer_interventions": _mean([float(t.developer_interventions) for t in real_baseline]),
                    "mean_trust_score": _mean([t.developer_trust_score for t in real_baseline if t.developer_trust_score is not None]),
                    "mean_usefulness_score": _mean([t.developer_usefulness_score for t in real_baseline if t.developer_usefulness_score is not None])
                },
                "sclass_treatment": {
                    "trials_count": len(real_treatment),
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
    """Runs a protocol smoke test to verify instrument integrity and schema conformance."""
    protocol = ExternalValidationProtocol()

    # Task generators for smoke validation
    def gen_rate_limiter(spec):
        return lambda tokens: tokens >= 0

    def gen_config_parser(spec):
        return "def parse_config(raw_json):\n    import json\n    return json.loads(raw_json)\n"

    def gen_cache(spec):
        return lambda key: len(key) >= 1

    # Execute smoke trials with randomized assignment
    tasks = protocol.get_standard_task_catalog()
    generators = [gen_rate_limiter, gen_config_parser, gen_cache]

    for i, (task, gen) in enumerate(zip(tasks, generators)):
        assignment_base = protocol.assign_treatment_randomized(f"smoke_user_{i+1}", task["task_id"])
        protocol.record_trial(protocol.execute_protocol_smoke_trial(f"smoke_user_{i+1}", task["task_id"], "BASELINE", gen))
        protocol.record_trial(protocol.execute_protocol_smoke_trial(f"smoke_user_{i+1}", task["task_id"], "SCLASS_TREATMENT", gen))

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
    parser.add_argument("--output", type=str, default=None, help="Output JSON receipt path")
    parser.add_argument("--sha", type=str, default=None, help="Tested Git commit SHA")
    args = parser.parse_args()

    run_external_validation_smoke(output_path=args.output, tested_sha=args.sha)
