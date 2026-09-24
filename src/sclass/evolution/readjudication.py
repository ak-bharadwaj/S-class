"""
S-Class Evolution: Offline Readjudication Engine.
Implements Directive Section 32:
- Re-applies selection criteria (noise floors, cost budgets, domain guards)
  to historical stored measurements WITHOUT re-running expensive evaluations.
- Enables rapid policy iteration and sensitivity analysis.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from sclass.evolution.candidate import EvolutionCandidate, EvolutionStatus
from sclass.evolution.selector import CandidateSelector, SelectionResult
from sclass.evolution.evaluator import CandidateEvaluationReport


class Readjudicator:
    """
    Re-evaluates admissibility of stored candidates under revised selection parameters.
    """

    @classmethod
    def readjudicate_candidate(
        cls,
        candidate: EvolutionCandidate,
        report: CandidateEvaluationReport,
        selector: CandidateSelector,
        baseline_score: float,
        baseline_cost: float,
        security_failures: int = 0,
        completion_bypasses: int = 0,
    ) -> SelectionResult:
        result = selector.select(
            candidate=candidate,
            report=report,
            baseline_score=baseline_score,
            baseline_cost=baseline_cost,
            security_failures=security_failures,
            completion_bypasses=completion_bypasses,
        )

        # Update candidate status in-memory
        if result.admissible:
            candidate.status = EvolutionStatus.ADMISSIBLE
        else:
            candidate.status = EvolutionStatus.REJECTED

        return result
