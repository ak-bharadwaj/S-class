"""
S-Class EOS V11.2 - D5 Controller / Action Authorization Layer (§8.1, §8.3, §11.4).
"""

from controller.token import (
    ActionBinding,
    ExecutionToken,
    ExecutionAdmissionResult,
    compute_action_digest,
    verify_and_consume_execution_token,
    verify_execution_token_signature,
    verify_admission_signature,
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
    ExecutionCompletionResult,
)

__all__ = [
    "ActionBinding",
    "ExecutionToken",
    "ExecutionAdmissionResult",
    "compute_action_digest",
    "verify_and_consume_execution_token",
    "verify_execution_token_signature",
    "verify_admission_signature",
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
    "ExecutionCompletionResult",
]
