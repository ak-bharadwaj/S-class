"""
S-Class Evolution: Candidate Evaluation & Smoke Gate Subsystem.
Fulfills Directive Section 16 & Section 40:
Re-exports evaluation symbols ensuring imports from sclass.evolution.evaluation and sclass.evolution.evaluator both resolve seamlessly.
"""

from __future__ import annotations
from sclass.evolution.evaluator import (
    CandidateEvaluator,
    CandidateEvaluationReport,
    TrialResult,
    TrialOutcome,
    SmokeResult,
)

__all__ = [
    "CandidateEvaluator",
    "CandidateEvaluationReport",
    "TrialResult",
    "TrialOutcome",
    "SmokeResult",
]
