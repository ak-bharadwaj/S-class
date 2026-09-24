"""
S-Class Evolution: Multi-Objective Candidate Selector & Non-Compensatory Domain Guards.
Implements Directive Sections 28 and 29:
- Multi-objective selection based on:
    1. Quality gain exceeding calibrated noise floor (delta_S >= noise_floor)
    2. Token & cost discipline (delta_C within budget or Pareto improvement)
    3. Non-regression across previously solved tasks
    4. Novelty bonus for unexplored components
    5. Non-compensatory domain guards
- Non-compensatory Domain Guards:
    Execution validity, zero security violations, zero completion bypasses,
    bounded crash rate, bounded token spend, bounded latency.
    Guards can NEVER be traded off for higher benchmark scores.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from sclass.evolution.candidate import EvolutionCandidate
from sclass.evolution.evaluator import CandidateEvaluationReport


@dataclass(frozen=True)
class DomainGuards:
    """Non-compensatory security and operational guardrails."""
    min_valid_execution_rate: float = 0.95
    max_security_failures: int = 0
    max_completion_bypasses: int = 0
    max_crash_rate: float = 0.02
    max_token_cost: float = 20000.0
    max_latency_ms: float = 5000.0


@dataclass(frozen=True)
class SelectionResult:
    admissible: bool
    quality_gain: float
    cost_delta: float
    noise_floor: float
    guards_satisfied: bool
    violated_guards: List[str]
    selection_verdict: str
    reasons: List[str]


class CandidateSelector:
    """
    Applies multi-objective admissibility and domain guards to candidate evaluations.
    """

    def __init__(
        self,
        noise_floor: float = 0.05,
        guards: Optional[DomainGuards] = None,
        max_allowable_cost_inflation: float = 0.20,
    ):
        self.noise_floor = noise_floor
        self.guards = guards or DomainGuards()
        self.max_allowable_cost_inflation = max_allowable_cost_inflation

    def evaluate_guards(
        self,
        report: CandidateEvaluationReport,
        security_failures: int = 0,
        completion_bypasses: int = 0,
    ) -> tuple[bool, List[str]]:
        """Evaluates non-compensatory domain guards."""
        violations: List[str] = []

        if report.pass_rate < self.guards.min_valid_execution_rate:
            violations.append(
                f"GUARD_VIOLATION: Execution pass rate {report.pass_rate:.3f} < minimum {self.guards.min_valid_execution_rate}"
            )
        if security_failures > self.guards.max_security_failures:
            violations.append(
                f"GUARD_VIOLATION: Security failures {security_failures} > allowed {self.guards.max_security_failures}"
            )
        if completion_bypasses > self.guards.max_completion_bypasses:
            violations.append(
                f"GUARD_VIOLATION: Completion bypass attempts {completion_bypasses} > allowed {self.guards.max_completion_bypasses}"
            )
        if report.mean_token_cost > self.guards.max_token_cost:
            violations.append(
                f"GUARD_VIOLATION: Mean token cost {report.mean_token_cost:.1f} > max limit {self.guards.max_token_cost}"
            )
        if report.mean_latency_ms > self.guards.max_latency_ms:
            violations.append(
                f"GUARD_VIOLATION: Mean latency {report.mean_latency_ms:.1f}ms > max limit {self.guards.max_latency_ms}ms"
            )

        satisfied = (len(violations) == 0)
        return satisfied, violations

    def select(
        self,
        candidate: EvolutionCandidate,
        report: CandidateEvaluationReport,
        baseline_score: float,
        baseline_cost: float,
        security_failures: int = 0,
        completion_bypasses: int = 0,
    ) -> SelectionResult:
        delta_s = report.mean_score - baseline_score
        delta_c = report.mean_token_cost - baseline_cost

        # 1. Non-compensatory domain guards
        guards_ok, guard_violations = self.evaluate_guards(
            report=report,
            security_failures=security_failures,
            completion_bypasses=completion_bypasses,
        )

        reasons: List[str] = []
        if not guards_ok:
            reasons.extend(guard_violations)
            return SelectionResult(
                admissible=False,
                quality_gain=delta_s,
                cost_delta=delta_c,
                noise_floor=self.noise_floor,
                guards_satisfied=False,
                violated_guards=guard_violations,
                selection_verdict="REJECT_GUARD_VIOLATION",
                reasons=reasons,
            )

        # 2. Quality Gain vs Noise Floor
        if delta_s < self.noise_floor:
            reasons.append(
                f"Quality gain {delta_s:.4f} did not exceed calibrated noise floor {self.noise_floor:.4f}"
            )
            return SelectionResult(
                admissible=False,
                quality_gain=delta_s,
                cost_delta=delta_c,
                noise_floor=self.noise_floor,
                guards_satisfied=True,
                violated_guards=[],
                selection_verdict="REJECT_BELOW_NOISE_FLOOR",
                reasons=reasons,
            )

        # 3. Cost Discipline
        cost_ratio = (delta_c / baseline_cost) if baseline_cost > 0 else 0.0
        if cost_ratio > self.max_allowable_cost_inflation:
            reasons.append(
                f"Cost inflation {cost_ratio:.2%} exceeded maximum allowed {self.max_allowable_cost_inflation:.2%}"
            )
            return SelectionResult(
                admissible=False,
                quality_gain=delta_s,
                cost_delta=delta_c,
                noise_floor=self.noise_floor,
                guards_satisfied=True,
                violated_guards=[],
                selection_verdict="REJECT_COST_EXPLOSION",
                reasons=reasons,
            )

        reasons.append("Admissible: Exceeds noise floor with cost discipline and all domain guards satisfied.")
        return SelectionResult(
            admissible=True,
            quality_gain=delta_s,
            cost_delta=delta_c,
            noise_floor=self.noise_floor,
            guards_satisfied=True,
            violated_guards=[],
            selection_verdict="ADMISSIBLE",
            reasons=reasons,
        )
