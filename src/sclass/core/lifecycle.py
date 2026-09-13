"""
S-Class Task & Project Lifecycle Definitions.
Deterministic State Machine: Zero LLM required.
"""

from __future__ import annotations
from enum import Enum
from typing import Set, Dict
from sclass.core.errors import StateTransitionError


class TaskState(str, Enum):
    PLANNED = "planned"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    CLAIMED = "claimed"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


VALID_TRANSITIONS: Dict[TaskState, Set[TaskState]] = {
    TaskState.PLANNED: {TaskState.READY, TaskState.CANCELLED, TaskState.SUPERSEDED},
    TaskState.READY: {TaskState.IN_PROGRESS, TaskState.BLOCKED, TaskState.CANCELLED, TaskState.SUPERSEDED},
    TaskState.IN_PROGRESS: {TaskState.CLAIMED, TaskState.BLOCKED, TaskState.CANCELLED, TaskState.SUPERSEDED},
    TaskState.CLAIMED: {TaskState.VERIFYING, TaskState.REJECTED, TaskState.CANCELLED},
    TaskState.VERIFYING: {TaskState.VERIFIED, TaskState.REJECTED, TaskState.CANCELLED},
    TaskState.REJECTED: {TaskState.IN_PROGRESS, TaskState.READY, TaskState.CANCELLED, TaskState.SUPERSEDED},
    TaskState.BLOCKED: {TaskState.READY, TaskState.CANCELLED, TaskState.SUPERSEDED},
    TaskState.VERIFIED: set(),
    TaskState.SUPERSEDED: set(),
    TaskState.CANCELLED: set(),
}

TERMINAL_STATES: Set[TaskState] = {
    TaskState.VERIFIED,
    TaskState.SUPERSEDED,
    TaskState.CANCELLED,
}


def validate_transition(current: TaskState, target: TaskState) -> None:
    """Validates that transition from current to target state is legally allowed."""
    if current == target:
        return
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise StateTransitionError(
            f"Illegal task state transition: {current.value} -> {target.value}. "
            f"Allowed transitions from {current.value}: {[s.value for s in allowed]}"
        )
