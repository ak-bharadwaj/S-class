"""
S-Class Assurance: Canonical Authority Invariants & Dual-Layer Enforcement.
Maintains the supreme authority of S-Class over project truth:
- DualLayerAuthorizer coordination.
- Non-delegation of canonical truth certification to child runtimes or subagents.
- Anti-forgery protections preventing unverified status promotion.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.control.composite_auth import DualLayerAuthorizer
from sclass.core.errors import SecurityViolationError


class CanonicalAuthorityGate:
    """
    Enforces that only authorized operations proceed and that no external runtime
    or subagent can certify its own truth claims.
    """

    @classmethod
    def verify_action_request(
        cls,
        action: ActionRequest,
        authorizer: DualLayerAuthorizer,
    ) -> AuthorizationDecision:
        decision = authorizer.authorize(action)
        if decision.decision != DecisionOutcome.ALLOW:
            raise SecurityViolationError(f"Action denied by S-Class canonical authority: {decision.reason}")
        return decision

    @classmethod
    def assert_cannot_self_certify(cls, actor_id: str, is_subagent: bool = False) -> None:
        """Enforces that an agent or runtime process cannot self-certify completion."""
        if is_subagent or "subagent" in actor_id.lower() or "runtime" in actor_id.lower():
            raise SecurityViolationError(
                f"AUTHORITY_VIOLATION: Subagent or runtime actor '{actor_id}' cannot certify technical obligations or project truth."
            )
