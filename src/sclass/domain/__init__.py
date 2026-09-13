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
    "Command",
    "CommandRef",
    "ExecutionIdentity",
    "Observation",
    "EvidenceReceipt",
    "ObservedReceipt",
    "ProposedEvidence",
    "ClaimedEvidence",
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
