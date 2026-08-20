"""
S-Class EOS V11.2 - D5 Controller / Action Authorization Layer (§8.1, §8.3, §11.4).
"""

from controller.token import (
    ExecutionToken,
    verify_and_consume_execution_token,
)
from controller.hooks import (
    LifecycleStage,
    HookResult,
    HookContext,
    LifecycleHook,
    LifecyclePipeline,
)
from controller.frontier import (
    ExecutionFrontier,
    compute_ready_frontier,
    compute_blocked_frontier,
    compute_executable_frontier,
    compute_frontier,
    get_topological_dependency_order,
)
from controller.authorization import (
    ActionProposal,
    AuthorizationStatus,
    AuthorizationDecision,
    AuthorizationEngine,
)
from controller.controller import (
    SClassController,
    ControllerDispatchResult,
    ExecutionAdmissionResult,
    ExecutionCompletionResult,
)

__all__ = [
    "ExecutionToken",
    "verify_and_consume_execution_token",
    "LifecycleStage",
    "HookResult",
    "HookContext",
    "LifecycleHook",
    "LifecyclePipeline",
    "ExecutionFrontier",
    "compute_ready_frontier",
    "compute_blocked_frontier",
    "compute_executable_frontier",
    "compute_frontier",
    "get_topological_dependency_order",
    "ActionProposal",
    "AuthorizationStatus",
    "AuthorizationDecision",
    "AuthorizationEngine",
    "SClassController",
    "ControllerDispatchResult",
    "ExecutionAdmissionResult",
    "ExecutionCompletionResult",
]
