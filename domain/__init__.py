"""S-Class Domain Kernel (D1).

Pure, canonical domain primitives and deterministic DAG/Frontier calculation.
Zero framework dependencies, no execution authorization, no controller, no reducers.
"""

from domain.types import (
    ObligationCategory,
    Criticality,
    ObligationStatus,
    ClaimTier,
    TargetType,
    ClaimStatus,
    PolicyScope,
    RuleType,
    CombinatorType,
    EvidencePolarity,
    EvidenceValidity,
    RawStatus,
    AssessmentVerdict,
    EventType,
    DriftType,
)
from domain.models import (
    RepositoryContext,
    TaskConstraints,
    Task,
    Obligation,
    ClaimSubject,
    Claim,
    PolicyRule,
    PolicyExpression,
    Policy,
    EvidenceScope,
    EvidenceObservation,
    Provenance,
    HmacSessionSignature,
    Evidence,
    AsymmetricAuthoritySignature,
    ClaimAssessment,
    ConflictDetail,
    AssessmentReceipt,
    EventEnvelope,
)
from domain.dag import (
    ObligationGraph,
    FrontierSnapshot,
)
from domain.exceptions import (
    DomainError,
    DomainValidationError,
    DuplicateObligationError,
    MissingDependencyError,
    CyclicDependencyError,
    CrossTaskContaminationError,
    ImmutabilityViolationError,
)

__all__ = [
    # Types
    "ObligationCategory",
    "Criticality",
    "ObligationStatus",
    "ClaimTier",
    "TargetType",
    "ClaimStatus",
    "PolicyScope",
    "RuleType",
    "CombinatorType",
    "EvidencePolarity",
    "EvidenceValidity",
    "RawStatus",
    "AssessmentVerdict",
    "EventType",
    "DriftType",
    # Models
    "RepositoryContext",
    "TaskConstraints",
    "Task",
    "Obligation",
    "ClaimSubject",
    "Claim",
    "PolicyRule",
    "PolicyExpression",
    "Policy",
    "EvidenceScope",
    "EvidenceObservation",
    "Provenance",
    "HmacSessionSignature",
    "Evidence",
    "AsymmetricAuthoritySignature",
    "ClaimAssessment",
    "ConflictDetail",
    "AssessmentReceipt",
    "EventEnvelope",
    # DAG
    "ObligationGraph",
    "FrontierSnapshot",
    # Exceptions
    "DomainError",
    "DomainValidationError",
    "DuplicateObligationError",
    "MissingDependencyError",
    "CyclicDependencyError",
    "CrossTaskContaminationError",
    "ImmutabilityViolationError",
]
