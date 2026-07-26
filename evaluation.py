"""
Continuous Self-Evaluation Engine for S-Class EOS

Evaluates phase completion metrics, detects goal drift, monitors agent confidence,
and determines if the FSM should proceed, pivot profiles, or request clarification.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger("sclass_evaluation")


class EvaluationAction(Enum):
    PROCEED = "proceed"
    CLARIFY = "clarify"
    PIVOT_PROFILE = "pivot_profile"
    RECOVER = "recover"


@dataclass
class PhaseEvaluation:
    phase: str
    action: EvaluationAction
    confidence_score: float
    goal_drift_detected: bool
    suggested_profile: Optional[str]
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)


class SelfEvaluator:
    """Performs continuous self-evaluation at each FSM phase transition."""

    @staticmethod
    def evaluate_phase(
        phase: str,
        confidence_score: float = 1.0,
        retry_count: int = 0,
        max_retries: int = 3,
        goal_text: str = "",
        current_profile: str = "full"
    ) -> PhaseEvaluation:

        # 1. High Retry Count Check -> Trigger Recovery
        if retry_count >= max_retries:
            return PhaseEvaluation(
                phase=phase,
                action=EvaluationAction.RECOVER,
                confidence_score=confidence_score,
                goal_drift_detected=False,
                suggested_profile=None,
                reason=f"Retry count ({retry_count}) exceeded max_retries ({max_retries}). Triggering RECOVERY loop."
            )

        # 2. Low Confidence Check -> Trigger Clarification
        if confidence_score < 0.5 and phase not in ["TRIAGE", "DONE"]:
            return PhaseEvaluation(
                phase=phase,
                action=EvaluationAction.CLARIFY,
                confidence_score=confidence_score,
                goal_drift_detected=False,
                suggested_profile=None,
                reason=f"Agent confidence score ({confidence_score:.2f}) fell below 0.5 threshold. Requesting user clarification."
            )

        # 3. Dynamic Profile Pivot Detection
        goal_lower = goal_text.lower()
        if current_profile == "bug_fix" and any(kw in goal_lower for kw in ["major refactor", "rewrite", "architectural change"]):
            return PhaseEvaluation(
                phase=phase,
                action=EvaluationAction.PIVOT_PROFILE,
                confidence_score=confidence_score,
                goal_drift_detected=True,
                suggested_profile="full",
                reason="Goal expanded from bug fix to major refactor. Pivoting workflow profile to FULL 11-state pipeline."
            )

        # Normal Proceed
        return PhaseEvaluation(
            phase=phase,
            action=EvaluationAction.PROCEED,
            confidence_score=confidence_score,
            goal_drift_detected=False,
            suggested_profile=None,
            reason=f"Phase {phase} passed evaluation cleanly with confidence score {confidence_score:.2f}."
        )
