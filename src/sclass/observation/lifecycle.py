"""
S-Class Observation: Explicit Observation State Machine & Lifecycle Tracker.
Enforces the strict monotonic progression of observation evidence:
REQUESTED -> SPAWNED -> IDENTIFIED -> OBSERVED -> ANCHORED -> PUBLISHED
and authoritative terminal failure states:
IDENTITY_UNCERTAIN, OBSERVATION_FAILED, ANCHOR_FAILED.
Guarantees that observations with uncertain identity or failed anchors
are NEVER silently converted into trusted evidence.
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from sclass.core.errors import ObservationIntegrityError


class ObservationLifecycleState(str, Enum):
    """Authoritative states of an observed execution lifecycle."""
    REQUESTED = "REQUESTED"
    AUTHORIZED = "AUTHORIZED"
    STARTED = "STARTED"
    RUNNING = "RUNNING"
    EXITED = "EXITED"
    OBSERVED = "OBSERVED"
    ANCHORED = "ANCHORED"
    VERIFIED = "VERIFIED"
    INVALIDATED = "INVALIDATED"

    # Compatibility / execution states
    SPAWNED = "SPAWNED"
    IDENTIFIED = "IDENTIFIED"
    PUBLISHED = "PUBLISHED"

    # Terminal failure states
    IDENTITY_UNCERTAIN = "IDENTITY_UNCERTAIN"
    OBSERVATION_FAILED = "OBSERVATION_FAILED"
    ANCHOR_FAILED = "ANCHOR_FAILED"


FAILURE_STATES = {
    ObservationLifecycleState.IDENTITY_UNCERTAIN,
    ObservationLifecycleState.OBSERVATION_FAILED,
    ObservationLifecycleState.ANCHOR_FAILED,
}


@dataclass
class ObservationStateTransition:
    """Audit record of a state transition."""
    from_state: str
    to_state: str
    timestamp: str
    reason: str = ""


class ObservationLifecycleTracker:
    """
    State machine enforcing the observation lifecycle.
    Prevents promotion of failed or unanchored observations to trusted evidence.
    """

    VALID_TRANSITIONS = {
        ObservationLifecycleState.REQUESTED: {
            ObservationLifecycleState.AUTHORIZED,
            ObservationLifecycleState.SPAWNED,
            ObservationLifecycleState.OBSERVATION_FAILED,
        },
        ObservationLifecycleState.AUTHORIZED: {
            ObservationLifecycleState.STARTED,
            ObservationLifecycleState.SPAWNED,
            ObservationLifecycleState.OBSERVATION_FAILED,
        },
        ObservationLifecycleState.STARTED: {
            ObservationLifecycleState.RUNNING,
            ObservationLifecycleState.OBSERVATION_FAILED,
        },
        ObservationLifecycleState.RUNNING: {
            ObservationLifecycleState.EXITED,
            ObservationLifecycleState.OBSERVED,
            ObservationLifecycleState.OBSERVATION_FAILED,
        },
        ObservationLifecycleState.EXITED: {
            ObservationLifecycleState.OBSERVED,
            ObservationLifecycleState.OBSERVATION_FAILED,
        },
        ObservationLifecycleState.OBSERVED: {
            ObservationLifecycleState.ANCHORED,
            ObservationLifecycleState.ANCHOR_FAILED,
            ObservationLifecycleState.OBSERVATION_FAILED,
        },
        ObservationLifecycleState.ANCHORED: {
            ObservationLifecycleState.VERIFIED,
            ObservationLifecycleState.PUBLISHED,
            ObservationLifecycleState.INVALIDATED,
        },
        ObservationLifecycleState.VERIFIED: {
            ObservationLifecycleState.INVALIDATED,
        },
        # Compatibility transitions
        ObservationLifecycleState.SPAWNED: {
            ObservationLifecycleState.IDENTIFIED,
            ObservationLifecycleState.IDENTITY_UNCERTAIN,
            ObservationLifecycleState.RUNNING,
            ObservationLifecycleState.OBSERVED,
            ObservationLifecycleState.OBSERVATION_FAILED,
        },
        ObservationLifecycleState.IDENTIFIED: {
            ObservationLifecycleState.OBSERVED,
            ObservationLifecycleState.OBSERVATION_FAILED,
        },
        ObservationLifecycleState.PUBLISHED: {
            ObservationLifecycleState.INVALIDATED,
        },
    }

    def __init__(self, initial_state: ObservationLifecycleState = ObservationLifecycleState.REQUESTED):
        self._current_state = initial_state
        self._history: List[ObservationStateTransition] = [
            ObservationStateTransition(
                from_state="NONE",
                to_state=initial_state.value,
                timestamp=datetime.now(timezone.utc).isoformat(),
                reason="Initial observation request",
            )
        ]

    @property
    def current_state(self) -> ObservationLifecycleState:
        return self._current_state

    @property
    def is_failed(self) -> bool:
        return self._current_state in FAILURE_STATES

    @property
    def can_publish(self) -> bool:
        return self._current_state == ObservationLifecycleState.ANCHORED

    def transition_to(self, next_state: ObservationLifecycleState, reason: str = "") -> None:
        """Transitions state, raising ObservationIntegrityError if transition is invalid."""
        if self._current_state in FAILURE_STATES:
            raise ObservationIntegrityError(
                f"Cannot transition from terminal failure state '{self._current_state.value}' to '{next_state.value}'."
            )

        valid_targets = self.VALID_TRANSITIONS.get(self._current_state, set())
        if next_state not in valid_targets:
            raise ObservationIntegrityError(
                f"Illegal observation state transition from '{self._current_state.value}' to '{next_state.value}'."
            )

        now = datetime.now(timezone.utc).isoformat()
        self._history.append(
            ObservationStateTransition(
                from_state=self._current_state.value,
                to_state=next_state.value,
                timestamp=now,
                reason=reason,
            )
        )
        self._current_state = next_state

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_state": self._current_state.value,
            "is_failed": self.is_failed,
            "history": [
                {
                    "from_state": h.from_state,
                    "to_state": h.to_state,
                    "timestamp": h.timestamp,
                    "reason": h.reason,
                }
                for h in self._history
            ],
        }
