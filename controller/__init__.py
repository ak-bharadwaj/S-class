"""
S-Class EOS V11.2 - D5 Controller / Action Authorization Layer (§8.1, §8.3, §11.4).
"""

from controller.token import (
    ActionBinding,
    ExecutionContext,
    ExecutionToken,
    ExecutionAdmissionResult,
    ExecutionEnvelope,
    compute_action_digest,
    compute_context_digest,
    verify_execution_token,
    commit_admission,
    verify_execution_token_signature,
    verify_admission_signature,
    verify_execution_envelope,
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
from controller.authority import (
    LeaseAuthority,
    StateAuthority,
    StaticLeaseAuthority,
    StaticStateAuthority,
    ProposalAuthorityContext,
    resolve_proposal_authority_context,
)
from controller.controller import (
    SClassController,
    ControllerDispatchResult,
    ExecutionCompletionResult,
)

__all__ = [
    "ProposalAuthorityContext",
    "resolve_proposal_authority_context",
    "LeaseAuthority",
    "StateAuthority",
    "StaticLeaseAuthority",
    "StaticStateAuthority",
    "ActionBinding",
    "ExecutionContext",
    "ExecutionToken",
    "ExecutionAdmissionResult",
    "ExecutionEnvelope",
    "compute_action_digest",
    "compute_context_digest",
    "verify_execution_token",
    "commit_admission",
    "verify_execution_token_signature",
    "verify_admission_signature",
    "verify_execution_envelope",
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
