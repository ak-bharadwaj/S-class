"""
S-Class Domain Models.
Pure, agent-agnostic domain representations for the S-Class control plane.
"""

from sclass.domain.project import Project, ProjectBoundary
from sclass.domain.task import Task, TaskState, TaskPriority
from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.domain.command import Command, CommandRef
from sclass.domain.execution import ExecutionIdentity
from sclass.domain.observation import Observation
from sclass.domain.evidence import (
    EvidenceReceipt,
    ObservedReceipt,
    ProposedEvidence,
    ClaimedEvidence,
    LIFECYCLE_PROPOSED,
    LIFECYCLE_CLAIMED,
    LIFECYCLE_OBSERVED,
    LIFECYCLE_INTEGRITY_VERIFIED,
    LIFECYCLE_CLAIM_VERIFIED,
    _OBSERVATION_TOKEN,
    EvidenceKind,
    Evidence,
    TestEvidence,
    BuildEvidence,
    LintEvidence,
    SecurityEvidence,
    SemanticEvidence,
    FilesystemEvidence,
    ProcessEvidence,
    build_evidence_from_receipt,
)
from sclass.domain.capability import (
    Capability,
    CapabilityDecision,
    CapabilityEvaluator,
    RiskTier,
    NetworkAccessLevel,
    FilesystemAccessLevel,
    CAP_TERMINAL_EXECUTE,
    CAP_FILESYSTEM_READ,
    CAP_FILESYSTEM_WRITE,
    CAP_GIT_READ,
    CAP_GIT_WRITE,
    CAP_NETWORK_REQUEST,
    CAP_SECRET_READ,
    CAP_PROCESS_SPAWN,
)
from sclass.domain.claim import Claim, ClaimType
from sclass.domain.verification import VerificationResult, VerificationEvent

__all__ = [
    "Project",
    "ProjectBoundary",
    "Task",
    "TaskState",
    "TaskPriority",
    "ActionRequest",
    "AuthorizationDecision",
    "DecisionOutcome",
    "Capability",
    "CapabilityDecision",
    "CapabilityEvaluator",
    "RiskTier",
    "NetworkAccessLevel",
    "FilesystemAccessLevel",
    "CAP_TERMINAL_EXECUTE",
    "CAP_FILESYSTEM_READ",
    "CAP_FILESYSTEM_WRITE",
    "CAP_GIT_READ",
    "CAP_GIT_WRITE",
    "CAP_NETWORK_REQUEST",
    "CAP_SECRET_READ",
    "CAP_PROCESS_SPAWN",
    "Command",
    "CommandRef",
    "ExecutionIdentity",
    "Observation",
    "EvidenceReceipt",
    "ObservedReceipt",
    "ProposedEvidence",
    "ClaimedEvidence",
    "EvidenceKind",
    "Evidence",
    "TestEvidence",
    "BuildEvidence",
    "LintEvidence",
    "SecurityEvidence",
    "SemanticEvidence",
    "FilesystemEvidence",
    "ProcessEvidence",
    "build_evidence_from_receipt",
    "LIFECYCLE_PROPOSED",
    "LIFECYCLE_CLAIMED",
    "LIFECYCLE_OBSERVED",
    "LIFECYCLE_INTEGRITY_VERIFIED",
    "LIFECYCLE_CLAIM_VERIFIED",
    "_OBSERVATION_TOKEN",
    "Claim",
    "ClaimType",
    "VerificationResult",
    "VerificationEvent",
]
