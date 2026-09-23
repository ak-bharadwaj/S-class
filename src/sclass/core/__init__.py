"""
S-Class Core Module.
Exposes lifecycle and errors.
"""

from sclass.core.lifecycle import TaskState, validate_transition
from sclass.core.errors import (
    SClassError,
    SecurityViolationError,
    StateTransitionError,
    ObservationIntegrityError,
    StorageError,
)

from sclass.core.completion_evaluator import (
    CompletionVerdict,
    CompletionAssessment,
    CompletionEvaluator,
)

__all__ = [
    "TaskState",
    "validate_transition",
    "SClassError",
    "SecurityViolationError",
    "StateTransitionError",
    "ObservationIntegrityError",
    "StorageError",
    "CompletionVerdict",
    "CompletionAssessment",
    "CompletionEvaluator",
]

