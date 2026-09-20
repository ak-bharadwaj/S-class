"""
S-Class Recovery: Authoritative Recovery Contract and Bounded Convergence Kernel.
"""

from sclass.recovery.models import (
    RecoveryState,
    RepairObligation,
    RecoveryAttempt,
    RecoveryRecord,
    RecoveryResult,
)
from sclass.recovery.state_machine import RecoveryStateMachine
from sclass.recovery.persistence import RecoveryPersistence
from sclass.recovery.engine import RecoveryEngine
from sclass.core.errors import (
    RecoveryError,
    RecoveryStateTransitionError,
    RecoveryExhaustedError,
    RecoveryPersistenceError,
)

__all__ = [
    "RecoveryState",
    "RecoveryStateMachine",
    "RepairObligation",
    "RecoveryAttempt",
    "RecoveryRecord",
    "RecoveryResult",
    "RecoveryEngine",
    "RecoveryPersistence",
    "RecoveryError",
    "RecoveryStateTransitionError",
    "RecoveryExhaustedError",
    "RecoveryPersistenceError",
]
