"""
S-Class Verification: Verification State Machine.
Formalizes the strict monotonic progression of claim verification:
CLAIMED -> EVIDENCE_REQUIRED -> OBSERVED -> VERIFICATION_RUNNING -> (ACCEPTED | REJECTED | INCONCLUSIVE)
and mutation invalidation:
ACCEPTED -> INVALIDATED.
Strictly rejects direct transitions (e.g. CLAIMED -> ACCEPTED).
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Set

from sclass.core.errors import StateTransitionError


class VerificationState(str, Enum):
    """Authoritative states of the verification lifecycle."""
    CLAIMED = "CLAIMED"
    EVIDENCE_REQUIRED = "EVIDENCE_REQUIRED"
    OBSERVED = "OBSERVED"
    VERIFICATION_RUNNING = "VERIFICATION_RUNNING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    INVALIDATED = "INVALIDATED"


@dataclass
class VerificationStateTransition:
    """Audit record of a verification state transition."""
    from_state: str
    to_state: str
    timestamp: str
    reason: str = ""


class VerificationStateMachine:
    """
    State machine enforcing the claim verification lifecycle.
    Guarantees that an agent claim cannot bypass evidence requirements or verification.
    """

    VALID_TRANSITIONS: Dict[VerificationState, Set[VerificationState]] = {
        VerificationState.CLAIMED: {
            VerificationState.EVIDENCE_REQUIRED,
            VerificationState.REJECTED,
        },
        VerificationState.EVIDENCE_REQUIRED: {
            VerificationState.OBSERVED,
            VerificationState.REJECTED,
            VerificationState.INCONCLUSIVE,
        },
        VerificationState.OBSERVED: {
            VerificationState.VERIFICATION_RUNNING,
            VerificationState.REJECTED,
            VerificationState.INCONCLUSIVE,
        },
        VerificationState.VERIFICATION_RUNNING: {
            VerificationState.ACCEPTED,
            VerificationState.REJECTED,
            VerificationState.INCONCLUSIVE,
        },
        VerificationState.ACCEPTED: {
            VerificationState.INVALIDATED,
        },
        VerificationState.REJECTED: {
            VerificationState.CLAIMED,  # Allow retry
        },
        VerificationState.INCONCLUSIVE: {
            VerificationState.VERIFICATION_RUNNING,
            VerificationState.REJECTED,
            VerificationState.CLAIMED,
        },
        VerificationState.INVALIDATED: {
            VerificationState.CLAIMED,  # Allow re-verification on new work
        },
    }

    def __init__(self, initial_state: VerificationState = VerificationState.CLAIMED, claim_id: str = ""):
        self.claim_id = claim_id
        self._current_state = initial_state
        self._history: List[VerificationStateTransition] = [
            VerificationStateTransition(
                from_state="NONE",
                to_state=initial_state.value,
                timestamp=datetime.now(timezone.utc).isoformat(),
                reason="Initial claim creation",
            )
        ]

    @property
    def current_state(self) -> VerificationState:
        return self._current_state

    def transition_to(self, next_state: VerificationState, reason: str = "") -> None:
        """
        Transitions claim state to next_state.
        Raises StateTransitionError if the transition is illegal (e.g. CLAIMED -> ACCEPTED).
        """
        valid_targets = self.VALID_TRANSITIONS.get(self._current_state, set())
        if next_state not in valid_targets:
            raise StateTransitionError(
                f"Illegal verification state transition for claim '{self.claim_id}': "
                f"cannot transition from '{self._current_state.value}' directly to '{next_state.value}'. "
                f"Agent claims require independent observation and verification."
            )

        now = datetime.now(timezone.utc).isoformat()
        self._history.append(
            VerificationStateTransition(
                from_state=self._current_state.value,
                to_state=next_state.value,
                timestamp=now,
                reason=reason,
            )
        )
        self._current_state = next_state

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "current_state": self._current_state.value,
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
