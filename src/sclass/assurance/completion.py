"""
S-Class Assurance: Independent Completion Adjudicator.
Authoritatively adjudicates proposed completion:
Agent says 'DONE' / Runtime says 'GOAL COMPLETE' -> Evaluated independently by S-Class.
Verdicts: ACCEPT | BLOCK | RECOVER | CORRUPT | UNAVAILABLE.
"""

from sclass.core.completion_evaluator import (
    CompletionEvaluator,
    CompletionVerdict,
    CompletionAssessment,
)

__all__ = ["CompletionEvaluator", "CompletionVerdict", "CompletionAssessment"]
