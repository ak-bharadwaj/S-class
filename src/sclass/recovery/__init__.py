"""
S-Class Recovery: Authoritative Recovery Contract and Bounded Convergence Kernel.
"""

from sclass.recovery.models import (
    RecoveryState,
    RepairObligation,
    RecoveryAttempt,
    RecoveryRecord,
    RecoveryResult,
    RegressionAssessment,
    FrontierRecomputation,
    RepairStrategy,
    RepairStep,
    RecoveryBounds,
    RepairPlan,
)
from sclass.recovery.state_machine import RecoveryStateMachine
from sclass.recovery.persistence import RecoveryPersistence
from sclass.recovery.engine import RecoveryEngine
from sclass.recovery.planner import RecoveryPlanner
from sclass.core.errors import (
    RecoveryError,
    RecoveryStateTransitionError,
    RecoveryExhaustedError,
    RecoveryPersistenceError,
)

from sclass.recovery.crash_consistency import (
    CrashBoundary,
    BoundaryPolicy,
    CrashRecoveryManager,
)

__all__ = [
    "RecoveryState",
    "RecoveryStateMachine",
    "RepairObligation",
    "RecoveryAttempt",
    "RecoveryRecord",
    "RecoveryResult",
    "RegressionAssessment",
    "FrontierRecomputation",
    "RepairStrategy",
    "RepairStep",
    "RecoveryBounds",
    "RepairPlan",
    "RecoveryEngine",
    "RecoveryPlanner",
    "RecoveryPersistence",
    "RecoveryError",
    "RecoveryStateTransitionError",
    "RecoveryExhaustedError",
    "RecoveryPersistenceError",
    "CrashBoundary",
    "BoundaryPolicy",
    "CrashRecoveryManager",
]

