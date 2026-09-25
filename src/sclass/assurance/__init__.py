"""
S-Class Assurance Subsystem.
Enforces the authority plane, state reduction, and independent completion adjudication.
"""

from sclass.assurance.authority import CanonicalAuthorityGate
from sclass.assurance.reducer import VerifiedProjectState, StateReducer
from sclass.assurance.completion import (
    CompletionEvaluator,
    CompletionVerdict,
    CompletionAssessment,
)
from sclass.assurance.certification_registry import (
    CertificationRegistry,
    CertificationEvidenceRecord,
)

__all__ = [
    "CanonicalAuthorityGate",
    "VerifiedProjectState",
    "StateReducer",
    "CompletionEvaluator",
    "CompletionVerdict",
    "CompletionAssessment",
    "CertificationRegistry",
    "CertificationEvidenceRecord",
]

