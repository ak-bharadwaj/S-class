"""
S-Class Domain: Task Model with Deterministic State Machine.
"""

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, List

from sclass.core.lifecycle import TaskState, validate_transition


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Task:
    """An authoritative unit of work governed by S-Class."""
    task_id: str
    project_id: str
    title: str
    description: str = ""
    state: TaskState = TaskState.PLANNED
    priority: TaskPriority = TaskPriority.MEDIUM
    depends_on: List[str] = field(default_factory=list)
    assigned_agent: Optional[str] = None
    claimed_evidence_id: Optional[str] = None
    verified_receipt_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def transition_to(self, new_state: TaskState) -> None:
        """Transitions task state according to deterministic lifecycle rules."""
        validate_transition(self.state, new_state)
        self.state = new_state
        self.updated_at = datetime.now(timezone.utc).isoformat()
        if new_state == TaskState.VERIFIED:
            self.completed_at = self.updated_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "project_id": self.project_id,
            "title": self.title,
            "description": self.description,
            "state": self.state.value,
            "priority": self.priority.value,
            "depends_on": list(self.depends_on),
            "assigned_agent": self.assigned_agent,
            "claimed_evidence_id": self.claimed_evidence_id,
            "verified_receipt_id": self.verified_receipt_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Task:
        return cls(
            task_id=data["task_id"],
            project_id=data.get("project_id", "default_project"),
            title=data["title"],
            description=data.get("description", ""),
            state=TaskState(data.get("state", TaskState.PLANNED.value)),
            priority=TaskPriority(data.get("priority", TaskPriority.MEDIUM.value)),
            depends_on=list(data.get("depends_on", [])),
            assigned_agent=data.get("assigned_agent"),
            claimed_evidence_id=data.get("claimed_evidence_id"),
            verified_receipt_id=data.get("verified_receipt_id"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            completed_at=data.get("completed_at"),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def create(cls, title: str, project_id: str = "default_project", description: str = "", priority: TaskPriority = TaskPriority.MEDIUM, depends_on: Optional[List[str]] = None) -> Task:
        """Helper to create a new task with unique ID."""
        return cls(
            task_id=f"task_{uuid.uuid4().hex[:10]}",
            project_id=project_id,
            title=title,
            description=description,
            priority=priority,
            depends_on=depends_on or [],
        )
