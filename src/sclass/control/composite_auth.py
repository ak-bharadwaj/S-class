"""
S-Class Control: Dual-Layer Authorization (S-Class + Step-Code Runtime Permissions).
Enforces Section 10:
Agent asks for action -> S-Class policy authorization -> Runtime permission analysis -> execution.

Invariants:
1. S-Class deny always blocks execution.
2. Runtime deny also blocks execution.
3. S-Class allow cannot bypass runtime restrictions.
4. Modified action after authorization requires a new authorization (action hash binding).
5. Runtime permission != S-Class authorization.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.control.authorization import authorize, get_policy_engine
from sclass.control.policy import PolicyEngine
from sclass.execution.harness import StepCodeCommandAnalyzer
from sclass.execution.operations import compute_action_hash
from sclass.core.errors import SecurityViolationError


@dataclass(frozen=True)
class CompositeAuthResult:
    """Consolidated outcome of the dual-layer authorization evaluation."""
    sclass_allowed: bool
    runtime_allowed: bool
    can_execute: bool
    sclass_reason: str
    runtime_reason: str
    action_hash: str
    authorized_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sclass_allowed": self.sclass_allowed,
            "runtime_allowed": self.runtime_allowed,
            "can_execute": self.can_execute,
            "sclass_reason": self.sclass_reason,
            "runtime_reason": self.runtime_reason,
            "action_hash": self.action_hash,
            "authorized_at": self.authorized_at,
        }


class DualLayerAuthorizer:
    """
    Coordinates S-Class governance authorization and lower runtime permission analysis.
    """

    @classmethod
    def authorize_request(
        cls,
        action: ActionRequest,
        workspace_dir: Optional[str] = None,
        engine: Optional[PolicyEngine] = None,
    ) -> AuthorizationDecision:
        """
        Computes S-Class authorization and embeds the cryptographic action_hash.
        """
        ws = workspace_dir or action.workspace or os.getcwd()
        decision = authorize(action, workspace_dir=ws, engine=engine)

        # Embed action_hash for post-authorization tampering protection
        act_hash = compute_action_hash(action.capability, action.action, action.target, action.parameters)
        new_meta = dict(decision.metadata or {})
        new_meta["action_hash"] = act_hash
        req_hash = decision.request_hash or act_hash

        return AuthorizationDecision(
            outcome=decision.outcome,
            policy_id=decision.policy_id,
            risk_level=decision.risk_level,
            reason=decision.reason,
            remediation=decision.remediation,
            evaluated_at=decision.evaluated_at,
            metadata=new_meta,
            issuer=decision.issuer,
            request_hash=req_hash,
            capability_hash=decision.capability_hash,
            capability_id=decision.capability_id,
            capability_version=decision.capability_version,
            capability_registry_generation=decision.capability_registry_generation,
            policy_version=decision.policy_version,
            integrity_token=decision.integrity_token,
            decision_id=decision.decision_id,
            request_id=decision.request_id,
            obligations=decision.obligations,
            required_claims=decision.required_claims,
        )

    @classmethod
    def evaluate_dual_layer(
        cls,
        action: ActionRequest,
        sclass_decision: AuthorizationDecision,
        workspace_dir: str = "",
    ) -> CompositeAuthResult:
        """
        Evaluates the dual-layer authorization hierarchy (Section 10).
        """
        ws = workspace_dir or action.workspace or os.getcwd()

        # Step 1: Verify Action Hash Integrity (Protection against modified action after authorization)
        current_act_hash = compute_action_hash(action.capability, action.action, action.target, action.parameters)
        signed_hash = sclass_decision.metadata.get("action_hash") if sclass_decision.metadata else None

        if signed_hash and signed_hash != current_act_hash:
            raise SecurityViolationError(
                f"ACTION MODIFIED AFTER AUTHORIZATION: Current action hash '{current_act_hash}' "
                f"does not match authorized action hash '{signed_hash}'. Execution is blocked until re-authorized."
            )

        # Step 2: S-Class Authorization Check (Law L3)
        sclass_allowed = sclass_decision.is_allowed
        sclass_reason = sclass_decision.reason

        # Step 3: Runtime Permission Analysis (Step-Code command safety layer)
        cmd_str = action.parameters.get("command") or action.parameters.get("command_line") or action.target or ""
        runtime_analysis = StepCodeCommandAnalyzer.analyze_command(cmd_str, ws)
        runtime_allowed = bool(runtime_analysis.get("allowed", False))
        runtime_reason = runtime_analysis.get("reason", "")

        # Step 4: Strict Conjunction Gate (Section 10)
        # S-Class deny -> execution denied
        # S-Class allow, runtime deny -> execution denied
        # Both allow -> execution may proceed
        can_execute = bool(sclass_allowed and runtime_allowed)

        return CompositeAuthResult(
            sclass_allowed=sclass_allowed,
            runtime_allowed=runtime_allowed,
            can_execute=can_execute,
            sclass_reason=sclass_reason,
            runtime_reason=runtime_reason,
            action_hash=current_act_hash,
        )
