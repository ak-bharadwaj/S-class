"""
S-Class Recovery: Domain Models and Types for Bounded Recovery and Convergence Kernel.
Enforces Invariant:
1. Recovery is evidence-driven.
2. Repair obligations are deterministic and identity-bound.
3. Recovery attempt bounds are strict and monotonic.
4. Convergence requires independent re-verification, not optimism.
5. Regression protection preserves unaffected accepted obligations.
"""

from __future__ import annotations
import uuid
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple


class RecoveryState(str, Enum):
    """Authoritative states of the D9 recovery lifecycle."""
    FAILED = "FAILED"
    DIAGNOSING = "DIAGNOSING"
    REPAIR_REQUIRED = "REPAIR_REQUIRED"
    REPAIR_IN_PROGRESS = "REPAIR_IN_PROGRESS"
    REVERIFY_REQUIRED = "REVERIFY_REQUIRED"
    CONVERGED = "CONVERGED"
    RECOVERY_EXHAUSTED = "RECOVERY_EXHAUSTED"

    @property
    def is_terminal(self) -> bool:
        return self in (RecoveryState.CONVERGED, RecoveryState.RECOVERY_EXHAUSTED)


@dataclass(frozen=True)
class RepairObligation:
    """
    A deterministic technical obligation derived from an authoritative failure or drift condition.
    Explicitly distinguishable from the original obligation.
    """
    obligation_id: str
    task_id: str
    affected_obligation_id: str
    affected_claim_id: Optional[str] = None
    affected_evidence_id: Optional[str] = None
    failure_classification: str = "EXECUTION_FAILURE"
    reason: str = ""
    staleness_cause: Optional[str] = None
    attempt_number: int = 1
    parent_event_id: Optional[str] = None
    project_state_ref: str = ""
    target: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "task_id": self.task_id,
            "affected_obligation_id": self.affected_obligation_id,
            "affected_claim_id": self.affected_claim_id,
            "affected_evidence_id": self.affected_evidence_id,
            "failure_classification": self.failure_classification,
            "reason": self.reason,
            "staleness_cause": self.staleness_cause,
            "attempt_number": self.attempt_number,
            "parent_event_id": self.parent_event_id,
            "project_state_ref": self.project_state_ref,
            "target": self.target,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RepairObligation:
        return cls(
            obligation_id=data["obligation_id"],
            task_id=data["task_id"],
            affected_obligation_id=data["affected_obligation_id"],
            affected_claim_id=data.get("affected_claim_id"),
            affected_evidence_id=data.get("affected_evidence_id"),
            failure_classification=data.get("failure_classification", "EXECUTION_FAILURE"),
            reason=data.get("reason", ""),
            staleness_cause=data.get("staleness_cause"),
            attempt_number=int(data.get("attempt_number", 1)),
            parent_event_id=data.get("parent_event_id"),
            project_state_ref=data.get("project_state_ref", ""),
            target=data.get("target", ""),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class RecoveryAttempt:
    """Audit record of a single bounded recovery attempt."""
    attempt_number: int
    started_at: str
    repair_obligation_id: str
    completed_at: Optional[str] = None
    verification_status: Optional[str] = None
    receipt_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempt_number": self.attempt_number,
            "started_at": self.started_at,
            "repair_obligation_id": self.repair_obligation_id,
            "completed_at": self.completed_at,
            "verification_status": self.verification_status,
            "receipt_id": self.receipt_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RecoveryAttempt:
        return cls(
            attempt_number=int(data["attempt_number"]),
            started_at=data["started_at"],
            repair_obligation_id=data["repair_obligation_id"],
            completed_at=data.get("completed_at"),
            verification_status=data.get("verification_status"),
            receipt_id=data.get("receipt_id"),
        )


@dataclass
class RecoveryRecord:
    """
    Durable record of a recovery lifecycle.
    Persistable and reconstructible after process restart.
    """
    recovery_id: str
    task_id: str
    affected_obligation_id: str
    current_state: RecoveryState
    attempt_number: int
    max_attempts: int
    created_at: str
    updated_at: str
    failure_classification: str
    reason: str
    parent_event_id: Optional[str] = None
    affected_claim_id: Optional[str] = None
    affected_evidence_id: Optional[str] = None
    project_state_ref: str = ""
    current_repair_obligation: Optional[RepairObligation] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    resulting_verification: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recovery_id": self.recovery_id,
            "task_id": self.task_id,
            "affected_obligation_id": self.affected_obligation_id,
            "current_state": self.current_state.value if isinstance(self.current_state, RecoveryState) else str(self.current_state),
            "attempt_number": self.attempt_number,
            "max_attempts": self.max_attempts,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "failure_classification": self.failure_classification,
            "reason": self.reason,
            "parent_event_id": self.parent_event_id,
            "affected_claim_id": self.affected_claim_id,
            "affected_evidence_id": self.affected_evidence_id,
            "project_state_ref": self.project_state_ref,
            "current_repair_obligation": self.current_repair_obligation.to_dict() if self.current_repair_obligation else None,
            "history": list(self.history),
            "resulting_verification": dict(self.resulting_verification) if self.resulting_verification else None,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RecoveryRecord:
        repair_ob = None
        if data.get("current_repair_obligation"):
            repair_ob = RepairObligation.from_dict(data["current_repair_obligation"])

        return cls(
            recovery_id=data["recovery_id"],
            task_id=data["task_id"],
            affected_obligation_id=data["affected_obligation_id"],
            current_state=RecoveryState(data["current_state"]),
            attempt_number=int(data.get("attempt_number", 0)),
            max_attempts=int(data.get("max_attempts", 3)),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            failure_classification=data.get("failure_classification", "EXECUTION_FAILURE"),
            reason=data.get("reason", ""),
            parent_event_id=data.get("parent_event_id"),
            affected_claim_id=data.get("affected_claim_id"),
            affected_evidence_id=data.get("affected_evidence_id"),
            project_state_ref=data.get("project_state_ref", ""),
            current_repair_obligation=repair_ob,
            history=list(data.get("history", [])),
            resulting_verification=dict(data.get("resulting_verification")) if data.get("resulting_verification") else None,
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class RecoveryResult:
    """
    Authoritative outcome of a recovery cycle.
    Enforces regression protection by distinguishing repaired, preserved, and invalidated obligations.
    """
    recovery_id: str
    status: str
    is_converged: bool
    repaired_obligation_id: str
    preserved_obligation_ids: Tuple[str, ...]
    invalidated_obligation_ids: Tuple[str, ...]
    attempts_used: int
    max_attempts: int
    final_evidence_id: Optional[str] = None
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recovery_id": self.recovery_id,
            "status": self.status,
            "is_converged": self.is_converged,
            "repaired_obligation_id": self.repaired_obligation_id,
            "preserved_obligation_ids": list(self.preserved_obligation_ids),
            "invalidated_obligation_ids": list(self.invalidated_obligation_ids),
            "attempts_used": self.attempts_used,
            "max_attempts": self.max_attempts,
            "final_evidence_id": self.final_evidence_id,
            "reason": self.reason,
        }
