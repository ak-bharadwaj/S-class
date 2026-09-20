"""
S-Class: The Open-Source Trust & Control Plane for AI Coding Agents.

S-Class sits between an AI coding agent (Claude, Cursor, Codex, OpenCode, OpenHands)
and the developer workspace, ensuring every action is authorized, independently observed,
cryptographically recorded, and verified against real evidence.
"""

from __future__ import annotations
from typing import Optional, Dict, Any

from sclass.metadata import VERSION, get_release_metadata

__version__ = VERSION


from sclass.domain.project import Project, ProjectBoundary
from sclass.domain.task import Task, TaskState, TaskPriority
from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.domain.command import Command, CommandRef
from sclass.domain.execution import ExecutionIdentity
from sclass.domain.observation import Observation
from sclass.domain.evidence import EvidenceReceipt, ProposedEvidence, ClaimedEvidence
from sclass.domain.claim import Claim, ClaimType
from sclass.domain.verification import VerificationResult, VerificationEvent
from sclass.control.authorization import authorize
from sclass.control.authority import PathAuthority, PathAuthorityLevel
from sclass.verification.engine import verify_claim
from sclass.trust.ledger import LocalLedger

# Canonical survival alias
AuthorizationRequest = ActionRequest


def verify(
    claim: Claim,
    evidence: Optional[EvidenceReceipt],
    workspace_dir: Optional[str] = None,
    ledger: Optional[LocalLedger] = None,
) -> VerificationResult:
    """Convenience entry point for verifying an agent claim against observed evidence."""
    l = ledger or LocalLedger(workspace_dir=workspace_dir)
    return verify_claim(claim, evidence, workspace_dir=workspace_dir, ledger=l)


def record(
    event_type: str,
    payload: Dict[str, Any],
    workspace_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Convenience entry point for appending an event to the local tamper-evident ledger."""
    ledger = LocalLedger(workspace_dir=workspace_dir)
    return ledger.append(event_type, payload)


__all__ = [
    "__version__",
    "Project",
    "ProjectBoundary",
    "Task",
    "TaskState",
    "TaskPriority",
    "ActionRequest",
    "AuthorizationRequest",
    "AuthorizationDecision",
    "DecisionOutcome",
    "Command",
    "CommandRef",
    "ExecutionIdentity",
    "Observation",
    "EvidenceReceipt",
    "ProposedEvidence",
    "ClaimedEvidence",
    "Claim",
    "ClaimType",
    "VerificationResult",
    "VerificationEvent",
    "authorize",
    "verify",
    "record",
    "PathAuthority",
    "PathAuthorityLevel",
    "verify_claim",
    "LocalLedger",
    "PlatformProfile",
    "CompensationPolicy",
    "PerformanceBudget",
    "PlatformOptimizationEngine",
    "ControlPolicy",
    "PlatformComparisonBenchmark",
    "AgentIdentity",
    "AgentStatus",
    "ResourceLease",
    "LeaseType",
    "ConflictEvent",
    "ConflictType",
    "FleetState",
    "FleetMergeResult",
    "FleetIntegrityEngine",
    "CanonicalVerticalSlice",
    "Obligation",
    "ObligationKind",
    "ObligationStatus",
    "ExecutionEnvelope",
    "SlicePlanner",
    "SliceController",
    "SliceExecutor",
    "verify_canonical_acceptance",
]

from sclass.platform.profile import PlatformProfile
from sclass.platform.policy import CompensationPolicy
from sclass.platform.budget import PerformanceBudget
from sclass.platform.engine import PlatformOptimizationEngine, ControlPolicy
from sclass.platform.benchmark import PlatformComparisonBenchmark
from sclass.agent_fleet import (
    AgentIdentity,
    AgentStatus,
    ResourceLease,
    LeaseType,
    ConflictEvent,
    ConflictType,
    FleetState,
    FleetMergeResult,
    FleetIntegrityEngine,
)

from sclass.core.vertical_slice import (
    CanonicalVerticalSlice,
    Obligation,
    ObligationKind,
    ObligationStatus,
    ExecutionEnvelope,
    SlicePlanner,
    SliceController,
    SliceExecutor,
    verify_canonical_acceptance,
)
