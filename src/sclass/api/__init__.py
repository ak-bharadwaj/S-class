"""
S-Class API: Public Python API surface.
"""
from sclass.domain.claim import Claim, ClaimType, ClaimScope
from sclass.domain.evidence import EvidenceReceipt, ObservedReceipt
from sclass.domain.task import Task, TaskState
from sclass.domain.project import Project, ProjectBoundary
from sclass.domain.verification import VerificationResult, VerificationEvent
from sclass.execution.identity import ExecutionIdentity
from sclass.verification.engine import verify_claim
from sclass.trust.ledger import LocalLedger

__all__ = [
    "Claim",
    "ClaimType",
    "ClaimScope",
    "EvidenceReceipt",
    "ObservedReceipt",
    "Task",
    "TaskState",
    "Project",
    "ProjectBoundary",
    "VerificationResult",
    "VerificationEvent",
    "ExecutionIdentity",
    "verify_claim",
    "LocalLedger",
]
