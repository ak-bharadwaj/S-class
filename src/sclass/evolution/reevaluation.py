"""
S-Class Evolution: Infrastructure-Only Reevaluation Subsystem.
Implements Directive Section 33:
- Re-evaluates trials marked INVALID_INFRA due to environment, pipe, or process timeouts.
- Invariant: Real candidate failures (negative evidence) can NEVER be discarded or re-run
  under the guise of an infrastructure failure.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Callable
from sclass.evolution.candidate import EvolutionCandidate
from sclass.evolution.evaluator import CandidateEvaluationReport, TrialResult, TrialOutcome


class InfrastructureReevaluator:
    """
    Selectively remeasures trials invalidated by external infrastructure noise.
    """

    @classmethod
    def reevaluate_invalid_trials(
        cls,
        report: CandidateEvaluationReport,
        remeasure_trial_fn: Callable[[str, int], TrialResult],
    ) -> CandidateEvaluationReport:
        updated_trials: List[TrialResult] = []

        for trial in report.trials:
            if trial.outcome == TrialOutcome.INVALID_INFRA:
                # Remeasure only the invalid infrastructure trial
                new_trial = remeasure_trial_fn(trial.task_id, trial.trial_index)
                updated_trials.append(new_trial)
            else:
                # Keep real candidate result untouched
                updated_trials.append(trial)

        total_trials = len(updated_trials)
        passed_trials = [t for t in updated_trials if t.outcome == TrialOutcome.PASS]
        invalid_trials = [t for t in updated_trials if t.outcome == TrialOutcome.INVALID_INFRA]

        denom = total_trials if total_trials > 0 else 1
        mean_score = sum(t.score for t in updated_trials) / denom
        mean_cost = sum(t.token_cost for t in updated_trials) / denom
        mean_latency = sum(t.latency_ms for t in updated_trials) / denom
        pass_rate = len(passed_trials) / denom

        return CandidateEvaluationReport(
            evaluation_id=report.evaluation_id,
            candidate_id=report.candidate_id,
            trials=updated_trials,
            total_tasks=report.total_tasks,
            k_trials_per_task=report.k_trials_per_task,
            mean_score=mean_score,
            mean_token_cost=mean_cost,
            mean_latency_ms=mean_latency,
            pass_rate=pass_rate,
            invalid_infra_count=len(invalid_trials),
            untrusted_candidate_evidence=True,
        )
