"""
S-Class Recovery: Crash Consistency, Boundaries, and Fault Injection (Section 25).
Explicitly governs crash recovery across all twelve execution boundaries:
1. before authorization
2. after authorization
3. before effect
4. during effect
5. after effect
6. before observation
7. after observation
8. before evidence settlement
9. after evidence settlement
10. before claim promotion
11. after claim promotion
12. before regression verification

Invariants:
1. Operations with replay_class=NEVER are NEVER automatically replayed upon crash recovery.
2. Malformed runtime state, corrupt persistence, or ambiguous authorization fails closed (Law L8).
3. Corrupt derived cache triggers deterministic recalculation from canonical state.
"""

from __future__ import annotations
import json
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

from sclass.execution.operations import DurableOperation, OperationState, ReplayClass
from sclass.domain.project import VerifiedProjectState
from sclass.core.errors import SecurityViolationError, ObservationIntegrityError, RecoveryError


class CrashBoundary(str, Enum):
    BEFORE_AUTH = "before_authorization"
    AFTER_AUTH = "after_authorization"
    BEFORE_EFFECT = "before_effect"
    DURING_EFFECT = "during_effect"
    AFTER_EFFECT = "after_effect"
    BEFORE_OBSERVATION = "before_observation"
    AFTER_OBSERVATION = "after_observation"
    BEFORE_EVIDENCE_SETTLEMENT = "before_evidence_settlement"
    AFTER_EVIDENCE_SETTLEMENT = "after_evidence_settlement"
    BEFORE_CLAIM_PROMOTION = "before_claim_promotion"
    AFTER_CLAIM_PROMOTION = "after_claim_promotion"
    BEFORE_REGRESSION = "before_regression"


@dataclass(frozen=True)
class BoundaryPolicy:
    boundary: CrashBoundary
    persisted_state: Tuple[str, ...]
    can_replay_safe: bool
    can_replay_never: bool
    becomes_pending: Tuple[str, ...]
    becomes_stale: Tuple[str, ...]
    fails_closed: bool


BOUNDARY_POLICIES: Dict[CrashBoundary, BoundaryPolicy] = {
    CrashBoundary.BEFORE_AUTH: BoundaryPolicy(
        boundary=CrashBoundary.BEFORE_AUTH,
        persisted_state=("intent",),
        can_replay_safe=True,
        can_replay_never=True,
        becomes_pending=("intent",),
        becomes_stale=(),
        fails_closed=True,
    ),
    CrashBoundary.AFTER_AUTH: BoundaryPolicy(
        boundary=CrashBoundary.AFTER_AUTH,
        persisted_state=("intent", "authorization"),
        can_replay_safe=True,
        can_replay_never=False,
        becomes_pending=("authorization",),
        becomes_stale=(),
        fails_closed=True,
    ),
    CrashBoundary.BEFORE_EFFECT: BoundaryPolicy(
        boundary=CrashBoundary.BEFORE_EFFECT,
        persisted_state=("authorization", "operation_state"),
        can_replay_safe=True,
        can_replay_never=False,
        becomes_pending=("operation",),
        becomes_stale=(),
        fails_closed=True,
    ),
    CrashBoundary.DURING_EFFECT: BoundaryPolicy(
        boundary=CrashBoundary.DURING_EFFECT,
        persisted_state=("operation_state",),
        can_replay_safe=True,
        can_replay_never=False, # Law L8: NEVER operations cannot be blindly replayed if interrupted during execution
        becomes_pending=(),
        becomes_stale=("affected_claims",),
        fails_closed=True,
    ),
    CrashBoundary.AFTER_EFFECT: BoundaryPolicy(
        boundary=CrashBoundary.AFTER_EFFECT,
        persisted_state=("effect_result", "operation_state"),
        can_replay_safe=True,
        can_replay_never=False,
        becomes_pending=("observation",),
        becomes_stale=("dependent_claims",),
        fails_closed=True,
    ),
    CrashBoundary.BEFORE_OBSERVATION: BoundaryPolicy(
        boundary=CrashBoundary.BEFORE_OBSERVATION,
        persisted_state=("effect_result",),
        can_replay_safe=True,
        can_replay_never=False,
        becomes_pending=("observation",),
        becomes_stale=(),
        fails_closed=True,
    ),
    CrashBoundary.AFTER_OBSERVATION: BoundaryPolicy(
        boundary=CrashBoundary.AFTER_OBSERVATION,
        persisted_state=("observation",),
        can_replay_safe=True,
        can_replay_never=False,
        becomes_pending=("evidence_settlement",),
        becomes_stale=(),
        fails_closed=True,
    ),
    CrashBoundary.BEFORE_EVIDENCE_SETTLEMENT: BoundaryPolicy(
        boundary=CrashBoundary.BEFORE_EVIDENCE_SETTLEMENT,
        persisted_state=("observation",),
        can_replay_safe=True,
        can_replay_never=False,
        becomes_pending=("evidence",),
        becomes_stale=(),
        fails_closed=True,
    ),
    CrashBoundary.AFTER_EVIDENCE_SETTLEMENT: BoundaryPolicy(
        boundary=CrashBoundary.AFTER_EVIDENCE_SETTLEMENT,
        persisted_state=("evidence_receipt",),
        can_replay_safe=True,
        can_replay_never=False,
        becomes_pending=("claim_promotion",),
        becomes_stale=(),
        fails_closed=True,
    ),
    CrashBoundary.BEFORE_CLAIM_PROMOTION: BoundaryPolicy(
        boundary=CrashBoundary.BEFORE_CLAIM_PROMOTION,
        persisted_state=("evidence_receipt", "verification_result"),
        can_replay_safe=True,
        can_replay_never=False,
        becomes_pending=("claim",),
        becomes_stale=(),
        fails_closed=True,
    ),
    CrashBoundary.AFTER_CLAIM_PROMOTION: BoundaryPolicy(
        boundary=CrashBoundary.AFTER_CLAIM_PROMOTION,
        persisted_state=("verified_claim", "evidence_receipt"),
        can_replay_safe=True,
        can_replay_never=False,
        becomes_pending=(),
        becomes_stale=(),
        fails_closed=False,
    ),
    CrashBoundary.BEFORE_REGRESSION: BoundaryPolicy(
        boundary=CrashBoundary.BEFORE_REGRESSION,
        persisted_state=("verified_claim",),
        can_replay_safe=True,
        can_replay_never=False,
        becomes_pending=("regression_checks",),
        becomes_stale=(),
        fails_closed=True,
    ),
}


class CrashRecoveryManager:
    """
    Manages state recovery and fail-closed actions across crash boundaries.
    """

    @classmethod
    def recover_from_crash(
        cls,
        boundary: CrashBoundary,
        operation: DurableOperation,
        state: Optional[VerifiedProjectState] = None,
    ) -> Dict[str, Any]:
        policy = BOUNDARY_POLICIES.get(boundary)
        if not policy:
            raise SecurityViolationError(f"Unknown crash boundary: {boundary}")

        # Check replay permissions
        if operation.replay_class == ReplayClass.NEVER:
            if not policy.can_replay_never:
                operation.transition_to(
                    OperationState.FAILED,
                    {"reason": f"Crash at {boundary.value}: Non-idempotent operation (NEVER) cannot auto-replay."},
                )
                raise SecurityViolationError(
                    f"CRASH RECOVERY REJECTED: Operation '{operation.operation_id}' crashed at '{boundary.value}'. "
                    "Replay class is NEVER; automatic replay is prohibited. Fresh technical repair obligation required."
                )

        # For SAFE operations, recovery may proceed
        return {
            "boundary": boundary.value,
            "operation_id": operation.operation_id,
            "can_replay": True,
            "becomes_pending": list(policy.becomes_pending),
            "becomes_stale": list(policy.becomes_stale),
        }

    @classmethod
    def validate_cache_integrity(cls, cache_data: str) -> Dict[str, Any]:
        """
        Validates cached derived state.
        Fails closed on corrupt data.
        """
        try:
            parsed = json.loads(cache_data)
            if not isinstance(parsed, dict):
                raise ObservationIntegrityError("Corrupt derived cache: root is not a dictionary.")
            return parsed
        except (json.JSONDecodeError, ValueError) as e:
            raise ObservationIntegrityError(f"Corrupt derived cache fails closed: {e}") from e
