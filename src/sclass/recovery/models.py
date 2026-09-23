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
import hashlib
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


@dataclass(frozen=True)
class RegressionAssessment:
    """
    Canonical regression assessment outcome.
    Evaluates whether repairs caused regressions to previously accepted claims.
    """
    affected_claim_ids: Tuple[str, ...]
    reverified_claim_ids: Tuple[str, ...]
    failed_claim_ids: Tuple[str, ...]
    stale_claim_ids: Tuple[str, ...]
    regression_passed: bool
    assessment_time: str
    unaffected_claim_ids: Tuple[str, ...] = field(default_factory=tuple)
    provenance_references: Dict[str, str] = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "affected_claim_ids": list(self.affected_claim_ids),
            "reverified_claim_ids": list(self.reverified_claim_ids),
            "failed_claim_ids": list(self.failed_claim_ids),
            "stale_claim_ids": list(self.stale_claim_ids),
            "unaffected_claim_ids": list(self.unaffected_claim_ids),
            "regression_passed": self.regression_passed,
            "assessment_time": self.assessment_time,
            "provenance_references": dict(self.provenance_references),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RegressionAssessment:
        return cls(
            affected_claim_ids=tuple(data.get("affected_claim_ids", [])),
            reverified_claim_ids=tuple(data.get("reverified_claim_ids", [])),
            failed_claim_ids=tuple(data.get("failed_claim_ids", [])),
            stale_claim_ids=tuple(data.get("stale_claim_ids", [])),
            unaffected_claim_ids=tuple(data.get("unaffected_claim_ids", [])),
            regression_passed=bool(data.get("regression_passed", False)),
            assessment_time=data.get("assessment_time", ""),
            provenance_references=dict(data.get("provenance_references", {})),
            reason=data.get("reason", ""),
        )


@dataclass(frozen=True)
class FrontierRecomputation:
    """
    Authoritative recomputation of task frontier obligations following repair and regression assessment.
    Enforces:
    - Authoritative derivation: (previously accepted claims) - (regressed/unresolved) + (repaired claim).
    - Unresolved/invalidated obligations fail closed.
    - Preserved obligations are verified, not asserted.
    """
    task_id: str
    repaired_obligation_id: str
    preserved_obligation_ids: Tuple[str, ...]
    invalidated_obligation_ids: Tuple[str, ...]
    unresolved_obligation_ids: Tuple[str, ...]
    frontier_obligations: Tuple[str, ...]
    is_valid: bool
    recomputed_at: str
    reason: str = ""

    def __post_init__(self):
        object.__setattr__(self, "preserved_obligation_ids", tuple(sorted(self.preserved_obligation_ids)))
        object.__setattr__(self, "invalidated_obligation_ids", tuple(sorted(self.invalidated_obligation_ids)))
        object.__setattr__(self, "unresolved_obligation_ids", tuple(sorted(self.unresolved_obligation_ids)))
        object.__setattr__(self, "frontier_obligations", tuple(sorted(self.frontier_obligations)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "repaired_obligation_id": self.repaired_obligation_id,
            "preserved_obligation_ids": list(self.preserved_obligation_ids),
            "invalidated_obligation_ids": list(self.invalidated_obligation_ids),
            "unresolved_obligation_ids": list(self.unresolved_obligation_ids),
            "frontier_obligations": list(self.frontier_obligations),
            "is_valid": self.is_valid,
            "recomputed_at": self.recomputed_at,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FrontierRecomputation:
        return cls(
            task_id=data["task_id"],
            repaired_obligation_id=data.get("repaired_obligation_id", ""),
            preserved_obligation_ids=tuple(sorted(data.get("preserved_obligation_ids", []))),
            invalidated_obligation_ids=tuple(sorted(data.get("invalidated_obligation_ids", []))),
            unresolved_obligation_ids=tuple(sorted(data.get("unresolved_obligation_ids", []))),
            frontier_obligations=tuple(sorted(data.get("frontier_obligations", []))),
            is_valid=bool(data.get("is_valid", False)),
            recomputed_at=data.get("recomputed_at", ""),
            reason=data.get("reason", ""),
        )


class RepairStrategy(str, Enum):
    """Deterministic repair strategies for bounded recovery planning."""
    TARGETED_REPAIR = "TARGETED_REPAIR"
    WORKSPACE_RECONCILIATION = "WORKSPACE_RECONCILIATION"
    STATE_RESYNCHRONIZATION = "STATE_RESYNCHRONIZATION"
    DEPENDENCY_RECOMPILATION = "DEPENDENCY_RECOMPILATION"
    ISOLATED_ROLLBACK = "ISOLATED_ROLLBACK"


@dataclass(frozen=True)
class RepairStep:
    """A deterministic, declarative step within a bounded RepairPlan."""
    step_id: str
    action_type: str
    target: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action_type": self.action_type,
            "target": self.target,
            "description": self.description,
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RepairStep:
        return cls(
            step_id=data["step_id"],
            action_type=data["action_type"],
            target=data.get("target", ""),
            description=data.get("description", ""),
            parameters=dict(data.get("parameters", {})),
        )

    def to_action_request(
        self,
        task_id: str,
        workspace_dir: str,
        actor: str = "recovery_planner",
    ) -> Any:
        """Converts declarative repair step into a canonical ActionRequest for Controller submission."""
        from sclass.domain.action import ActionRequest
        return ActionRequest(
            actor=actor,
            session=task_id,
            capability="fs.write" if "patch" in self.action_type else "terminal.execute",
            action=self.action_type,
            target=self.target,
            parameters=dict(self.parameters),
            workspace=workspace_dir,
            context={
                "step_id": self.step_id,
                "intent": self.description,
                "plan_step": True,
            },
        )


@dataclass(frozen=True)
class RecoveryBounds:
    """Execution boundaries and limits enforced on recovery plans."""
    max_attempts: int = 3
    current_attempt: int = 0
    max_recursion_depth: int = 3
    current_recursion_depth: int = 0
    budget_limit: Optional[float] = None
    current_cost: float = 0.0
    max_depth: Optional[int] = None
    max_budget: Optional[float] = None

    def __post_init__(self):
        if self.max_depth is not None and self.max_recursion_depth == 3:
            object.__setattr__(self, "max_recursion_depth", self.max_depth)
        if self.max_budget is not None and self.budget_limit is None:
            object.__setattr__(self, "budget_limit", self.max_budget)

    def is_exhausted(
        self,
        current_attempt: Optional[int] = None,
        current_depth: Optional[int] = None,
        current_cost: Optional[float] = None,
    ) -> bool:
        att = current_attempt if current_attempt is not None else self.current_attempt
        depth = current_depth if current_depth is not None else self.current_recursion_depth
        cost = current_cost if current_cost is not None else self.current_cost

        if att > self.max_attempts:
            return True
        if depth > self.max_recursion_depth:
            return True
        if self.budget_limit is not None and cost > self.budget_limit:
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_attempts": self.max_attempts,
            "current_attempt": self.current_attempt,
            "max_recursion_depth": self.max_recursion_depth,
            "current_recursion_depth": self.current_recursion_depth,
            "budget_limit": self.budget_limit,
            "current_cost": self.current_cost,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RecoveryBounds:
        return cls(
            max_attempts=int(data.get("max_attempts", 3)),
            current_attempt=int(data.get("current_attempt", 0)),
            max_recursion_depth=int(data.get("max_recursion_depth", 3)),
            current_recursion_depth=int(data.get("current_recursion_depth", 0)),
            budget_limit=float(data["budget_limit"]) if data.get("budget_limit") is not None else None,
            current_cost=float(data.get("current_cost", 0.0)),
        )


@dataclass(frozen=True)
class RepairPlan:
    """
    Persisted, serializable planner result converting validated recovery state
    into a deterministic, bounded sequence of repair steps for Controller authorization.
    The planner output is strictly declarative and executes nothing.
    """
    recovery_id: str
    task_id: str
    repair_obligation_id: str
    selected_strategy: str
    ordered_repair_steps: Tuple[RepairStep, ...]
    constraints: Dict[str, Any]
    rationale: str
    is_valid: bool
    provenance: Dict[str, Any]
    created_at: str
    plan_id: str = ""

    def __post_init__(self):
        if not isinstance(self.ordered_repair_steps, tuple):
            object.__setattr__(self, "ordered_repair_steps", tuple(self.ordered_repair_steps))
        if not self.plan_id:
            plan_sig = f"{self.recovery_id}:{self.repair_obligation_id}:{self.selected_strategy}"
            object.__setattr__(
                self,
                "plan_id",
                f"plan_{hashlib.sha256(plan_sig.encode('utf-8')).hexdigest()[:12]}",
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "recovery_id": self.recovery_id,
            "task_id": self.task_id,
            "repair_obligation_id": self.repair_obligation_id,
            "selected_strategy": self.selected_strategy,
            "ordered_repair_steps": [s.to_dict() for s in self.ordered_repair_steps],
            "constraints": dict(self.constraints),
            "rationale": self.rationale,
            "is_valid": self.is_valid,
            "provenance": dict(self.provenance),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RepairPlan:
        steps = tuple(RepairStep.from_dict(s) for s in data.get("ordered_repair_steps", []))
        return cls(
            plan_id=data.get("plan_id", ""),
            recovery_id=data["recovery_id"],
            task_id=data["task_id"],
            repair_obligation_id=data["repair_obligation_id"],
            selected_strategy=data["selected_strategy"],
            ordered_repair_steps=steps,
            constraints=dict(data.get("constraints", {})),
            rationale=data.get("rationale", ""),
            is_valid=bool(data.get("is_valid", False)),
            provenance=dict(data.get("provenance", {})),
            created_at=data.get("created_at", ""),
        )


@dataclass
class RecoveryRecord:
    """
    Durable record of a recovery lifecycle.
    Persistable and reconstructible after process restart.
    """
    recovery_id: str
    task_id: str
    affected_obligation_id: str = ""
    current_state: RecoveryState = RecoveryState.FAILED
    attempt_number: int = 1
    max_attempts: int = 3
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    failure_classification: str = "EXECUTION_FAILURE"
    reason: str = ""
    parent_event_id: Optional[str] = None
    staleness_cause: Optional[str] = None
    affected_claim_id: Optional[str] = None
    affected_evidence_id: Optional[str] = None
    project_state_ref: str = ""
    current_repair_obligation: Optional[RepairObligation] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    resulting_verification: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    regression_assessment: Optional[RegressionAssessment] = None
    frontier_recomputation: Optional[FrontierRecomputation] = None
    repair_plan: Optional[RepairPlan] = None
    bounds: Optional[RecoveryBounds] = None

    def __init__(
        self,
        recovery_id: str,
        task_id: str,
        affected_obligation_id: str = "",
        current_state: Optional[Union[RecoveryState, str]] = None,
        attempt_number: int = 1,
        max_attempts: int = 3,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        failure_classification: str = "EXECUTION_FAILURE",
        reason: str = "",
        parent_event_id: Optional[str] = None,
        staleness_cause: Optional[str] = None,
        affected_claim_id: Optional[str] = None,
        affected_evidence_id: Optional[str] = None,
        project_state_ref: str = "",
        current_repair_obligation: Optional[RepairObligation] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        resulting_verification: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        regression_assessment: Optional[RegressionAssessment] = None,
        frontier_recomputation: Optional[FrontierRecomputation] = None,
        repair_plan: Optional[RepairPlan] = None,
        bounds: Optional[RecoveryBounds] = None,
        state: Optional[Union[RecoveryState, str]] = None,
        current_attempt: Optional[int] = None,
        repair_obligation: Optional[RepairObligation] = None,
        **extra_kwargs: Any,
    ):
        self.recovery_id = recovery_id
        self.task_id = task_id
        rep_ob = repair_obligation or current_repair_obligation
        self.current_repair_obligation = rep_ob
        self.affected_obligation_id = affected_obligation_id or (rep_ob.affected_obligation_id if rep_ob else "")
        raw_state = state if state is not None else (current_state or RecoveryState.FAILED)
        if isinstance(raw_state, str):
            self.current_state = RecoveryState(raw_state)
        else:
            self.current_state = raw_state
        self.attempt_number = current_attempt if current_attempt is not None else attempt_number
        self.max_attempts = max_attempts
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.updated_at = updated_at or datetime.now(timezone.utc).isoformat()
        self.failure_classification = failure_classification
        self.reason = reason
        self.parent_event_id = parent_event_id
        self.staleness_cause = staleness_cause
        self.affected_claim_id = affected_claim_id or (rep_ob.affected_claim_id if rep_ob else None)
        self.affected_evidence_id = affected_evidence_id or (rep_ob.affected_evidence_id if rep_ob else None)
        self.project_state_ref = project_state_ref
        self.history = list(history) if history is not None else []
        self.resulting_verification = resulting_verification
        self.metadata = dict(metadata) if metadata is not None else {}
        self.regression_assessment = regression_assessment
        self.frontier_recomputation = frontier_recomputation
        self.repair_plan = repair_plan
        self.bounds = bounds

    @property
    def current_attempt(self) -> int:
        return self.attempt_number

    @current_attempt.setter
    def current_attempt(self, value: int) -> None:
        self.attempt_number = value

    @property
    def state(self) -> RecoveryState:
        return self.current_state

    @state.setter
    def state(self, value: Union[RecoveryState, str]) -> None:
        self.current_state = RecoveryState(value) if isinstance(value, str) else value

    @property
    def repair_obligation(self) -> Optional[RepairObligation]:
        return self.current_repair_obligation

    @repair_obligation.setter
    def repair_obligation(self, value: Optional[RepairObligation]) -> None:
        self.current_repair_obligation = value
        if value and not self.affected_obligation_id:
            self.affected_obligation_id = value.affected_obligation_id

    @property
    def is_exhausted(self) -> bool:
        if self.bounds is not None:
            return self.bounds.is_exhausted(current_attempt=self.attempt_number)
        return self.attempt_number >= self.max_attempts

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
            "staleness_cause": self.staleness_cause,
            "affected_claim_id": self.affected_claim_id,
            "affected_evidence_id": self.affected_evidence_id,
            "project_state_ref": self.project_state_ref,
            "current_repair_obligation": self.current_repair_obligation.to_dict() if self.current_repair_obligation else None,
            "history": list(self.history),
            "resulting_verification": dict(self.resulting_verification) if self.resulting_verification else None,
            "metadata": dict(self.metadata),
            "regression_assessment": self.regression_assessment.to_dict() if self.regression_assessment else None,
            "frontier_recomputation": self.frontier_recomputation.to_dict() if self.frontier_recomputation else None,
            "repair_plan": self.repair_plan.to_dict() if self.repair_plan else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RecoveryRecord:
        repair_ob = None
        if data.get("current_repair_obligation"):
            repair_ob = RepairObligation.from_dict(data["current_repair_obligation"])

        reg_assess = None
        reg_data = data.get("regression_assessment") or data.get("metadata", {}).get("regression_assessment")
        if reg_data:
            reg_assess = RegressionAssessment.from_dict(reg_data)

        frontier_rec = None
        frontier_data = data.get("frontier_recomputation") or data.get("metadata", {}).get("frontier_recomputation")
        if frontier_data:
            frontier_rec = FrontierRecomputation.from_dict(frontier_data)

        plan = None
        plan_data = data.get("repair_plan") or data.get("metadata", {}).get("repair_plan")
        if plan_data:
            plan = RepairPlan.from_dict(plan_data)

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
            staleness_cause=data.get("staleness_cause"),
            affected_claim_id=data.get("affected_claim_id"),
            affected_evidence_id=data.get("affected_evidence_id"),
            project_state_ref=data.get("project_state_ref", ""),
            current_repair_obligation=repair_ob,
            history=list(data.get("history", [])),
            resulting_verification=dict(data.get("resulting_verification")) if data.get("resulting_verification") else None,
            metadata=dict(data.get("metadata", {})),
            regression_assessment=reg_assess,
            frontier_recomputation=frontier_rec,
            repair_plan=plan,
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
    frontier_recomputation: Optional[FrontierRecomputation] = None

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
            "frontier_recomputation": self.frontier_recomputation.to_dict() if self.frontier_recomputation else None,
        }
