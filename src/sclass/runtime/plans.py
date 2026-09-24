"""
S-Class Runtime: Plan & Task Distinction Substrate.
Implements Directive Section 12:
- Harvests the runtime distinction between:
    plan
    task
    execution
    completion
- Maps:
    Step plan        -> ExecutionPlanCandidate
    Step task        -> RuntimeTask
    S-Class obligation -> Canonical technical acceptance requirement
- Invariant:
    The model/runtime can freely update runtime tasks.
    However, RuntimeTask or ExecutionPlanCandidate completion CANNOT mark an S-Class obligation satisfied.
    Only the canonical S-Class state reducer can mark an obligation satisfied through independent evidence.
"""

from __future__ import annotations
import uuid
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sclass.core.errors import SecurityViolationError


class RuntimeTaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


@dataclass
class RuntimeTask:
    """
    Step-Code runtime task representation.
    Represents an operational execution step. Can be updated by the model,
    but possesses ZERO assurance authority over canonical S-Class obligations.
    """
    task_id: str
    title: str
    description: str
    status: RuntimeTaskStatus = RuntimeTaskStatus.PENDING
    assigned_lane_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def update_status(self, new_status: RuntimeTaskStatus, metadata_update: Optional[Dict[str, Any]] = None) -> None:
        """Model or runtime update to task status."""
        self.status = new_status
        if metadata_update:
            self.metadata.update(metadata_update)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def assert_cannot_satisfy_canonical_obligation(self, obligation_id: str) -> None:
        """
        Enforces Directive Section 12 invariant:
        Runtime task state cannot establish canonical obligation satisfaction.
        """
        raise SecurityViolationError(
            f"RuntimeTask '{self.task_id}' cannot satisfy canonical obligation '{obligation_id}'. "
            "Only independent S-Class verifiers and the canonical reducer can satisfy obligations."
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "assigned_lane_id": self.assigned_lane_id,
            "metadata": dict(self.metadata),
            "updated_at": self.updated_at,
        }


@dataclass
class ExecutionPlanCandidate:
    """
    Execution plan candidate proposed by the model or Step-Code planner.
    Remains an untrusted execution proposal until verified by S-Class.
    """
    plan_id: str
    session_id: str
    goal: str
    tasks: List[RuntimeTask] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def add_task(self, title: str, description: str, task_id: Optional[str] = None) -> RuntimeTask:
        tid = task_id or f"rtask_{uuid.uuid4().hex[:8]}"
        task = RuntimeTask(task_id=tid, title=title, description=description)
        self.tasks.append(task)
        return task

    def get_task(self, task_id: str) -> Optional[RuntimeTask]:
        for t in self.tasks:
            if t.task_id == task_id:
                return t
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "session_id": self.session_id,
            "goal": self.goal,
            "tasks": [t.to_dict() for t in self.tasks],
            "created_at": self.created_at,
        }
