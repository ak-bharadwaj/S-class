"""
S-Class Recovery: Deterministic Recovery State Machine.
Enforces:
1. Explicit states with illegal transitions rejected.
2. No implicit state jumps.
3. Authoritative state unchanged upon illegal transition attempt.
"""

from __future__ import annotations
from typing import Set, Dict

from sclass.recovery.models import RecoveryState
from sclass.core.errors import RecoveryStateTransitionError


class RecoveryStateMachine:
    """
    Deterministic state machine governing the D9 recovery lifecycle:
    FAILED -> DIAGNOSING -> REPAIR_REQUIRED -> REPAIR_IN_PROGRESS -> REVERIFY_REQUIRED -> CONVERGED
                                    |                                      |
                                    v                                      v
                             RECOVERY_EXHAUSTED                     REPAIR_REQUIRED / RECOVERY_EXHAUSTED
    """

    ALLOWED_TRANSITIONS: Dict[RecoveryState, Set[RecoveryState]] = {
        RecoveryState.FAILED: {RecoveryState.DIAGNOSING},
        RecoveryState.DIAGNOSING: {RecoveryState.REPAIR_REQUIRED},
        RecoveryState.REPAIR_REQUIRED: {RecoveryState.REPAIR_IN_PROGRESS, RecoveryState.RECOVERY_EXHAUSTED},
        RecoveryState.REPAIR_IN_PROGRESS: {RecoveryState.REVERIFY_REQUIRED},
        RecoveryState.REVERIFY_REQUIRED: {
            RecoveryState.CONVERGED,
            RecoveryState.REPAIR_REQUIRED,
            RecoveryState.RECOVERY_EXHAUSTED,
        },
        RecoveryState.CONVERGED: set(),
        RecoveryState.RECOVERY_EXHAUSTED: set(),
    }

    @classmethod
    def validate_transition(cls, current_state: RecoveryState, new_state: RecoveryState) -> None:
        """
        Validates that transition from current_state to new_state is explicitly permitted.
        Raises RecoveryStateTransitionError on illegal transition.
        """
        if not isinstance(current_state, RecoveryState):
            current_state = RecoveryState(current_state)
        if not isinstance(new_state, RecoveryState):
            new_state = RecoveryState(new_state)

        # Idempotent self-transition is permitted
        if current_state == new_state:
            return

        allowed = cls.ALLOWED_TRANSITIONS.get(current_state, set())
        if new_state not in allowed:
            allowed_names = sorted([s.value for s in allowed]) if allowed else ["None (terminal state)"]
            raise RecoveryStateTransitionError(
                f"Illegal recovery state transition from '{current_state.value}' to '{new_state.value}'. "
                f"Allowed transitions from '{current_state.value}': {allowed_names}"
            )
