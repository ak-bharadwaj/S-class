"""
S-Class EOS V11.2 - D5 Action Authorization Engine (§8.1, §8.2, CORE-05).
Precondition evaluation and immutable AuthorizationDecision creation.
Actually evaluates active D3 Policy using PolicyEvaluationContext.
Enforces:
1. Target obligation must be registered and in Executable Frontier (READY != EXECUTABLE).
2. All prerequisites listed in proposal must be SATISFIED or CONDITIONAL.
3. Action type must be permitted under active security profile.
4. Active D3 Policy evaluated and satisfied (ALLOW).
5. Estimated cost and timeout must not exceed budget bounds.
"""

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Sequence, Tuple, Any
from domain.models import Obligation, Policy, _validate_iso8601
from domain.types import ObligationStatus, PolicyScope
from policy.evaluator import evaluate_policy
from policy.models import PolicyEvaluationContext, PolicyDecisionType
from controller.frontier import compute_frontier, ExecutionFrontier


class AuthorizationStatus(str, Enum):
    """Categorical authorization decision outcomes."""
    AUTHORIZED = "AUTHORIZED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"


@dataclass(frozen=True)
class ActionProposal:
    """Action proposed by an unprivileged planner/agent (§3.6, §8.1)."""
    proposal_id: str
    obligation_id: str
    action_type: str
    target: str
    purpose: str
    estimated_cost_usd: float = 0.0
    timeout_seconds: int = 60
    prerequisites: Tuple[str, ...] = field(default_factory=tuple)
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.proposal_id:
            raise ValueError("proposal_id cannot be empty.")
        if not self.obligation_id:
            raise ValueError("obligation_id cannot be empty.")
        if not self.action_type:
            raise ValueError("action_type cannot be empty.")
        if not self.target:
            raise ValueError("target cannot be empty.")
        if self.estimated_cost_usd < 0.0:
            raise ValueError("estimated_cost_usd cannot be negative.")
        if self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be >= 1.")
        object.__setattr__(self, "prerequisites", tuple(self.prerequisites))


@dataclass(frozen=True)
class AuthorizationDecision:
    """Immutable categorical decision issued upon PRE_AUTHORIZE completion."""
    decision_id: str
    proposal_id: str
    obligation_id: str
    status: AuthorizationStatus
    rejection_reasons: Tuple[str, ...] = field(default_factory=tuple)
    evaluated_at: str = ""
    source_sha: str = ""
    policy_version: int = 1

    def __post_init__(self):
        if not self.decision_id:
            raise ValueError("decision_id cannot be empty.")
        if not self.proposal_id:
            raise ValueError("proposal_id cannot be empty.")
        if not self.obligation_id:
            raise ValueError("obligation_id cannot be empty.")
        if not isinstance(self.status, AuthorizationStatus):
            raise TypeError(f"Invalid status: {self.status}")
        _validate_iso8601(self.evaluated_at, "evaluated_at")
        object.__setattr__(self, "rejection_reasons", tuple(self.rejection_reasons))


class AuthorizationEngine:
    """Pure, deterministic evaluator for action proposals."""

    @staticmethod
    def evaluate_proposal(
        proposal: ActionProposal,
        obligations: Mapping[str, Obligation],
        policies: Mapping[str, Policy],
        source_sha: str,
        policy_version: int,
        evaluated_at: str,
        budget_remaining: float = 100.0,
        allowed_action_types: Optional[Sequence[str]] = None,
        frontier: Optional[ExecutionFrontier] = None,
    ) -> AuthorizationDecision:
        """Evaluates preconditions and produces an immutable AuthorizationDecision."""
        if not evaluated_at:
            raise ValueError("evaluated_at timestamp is required.")

        reasons: list[str] = []

        # 1. Target Obligation Existence
        target_obl = obligations.get(proposal.obligation_id)
        if not target_obl:
            return AuthorizationDecision(
                decision_id=f"DEC-{uuid.uuid4().hex[:8]}",
                proposal_id=proposal.proposal_id,
                obligation_id=proposal.obligation_id,
                status=AuthorizationStatus.REJECTED,
                rejection_reasons=(f"Target obligation '{proposal.obligation_id}' not found.",),
                evaluated_at=evaluated_at,
                source_sha=source_sha,
                policy_version=policy_version,
            )

        # 2. Frontier Check (READY != EXECUTABLE)
        current_frontier = frontier or compute_frontier(
            obligations=obligations,
            policies=policies,
            budget_remaining=budget_remaining,
        )

        if proposal.obligation_id in current_frontier.blocked_obligation_ids:
            reasons.append(f"Target obligation '{proposal.obligation_id}' is in BLOCKED frontier.")
        elif proposal.obligation_id not in current_frontier.executable_obligation_ids:
            if proposal.obligation_id in current_frontier.ready_obligation_ids:
                reasons.append(f"Target obligation '{proposal.obligation_id}' is READY but not EXECUTABLE under active constraints.")
            else:
                reasons.append(f"Target obligation '{proposal.obligation_id}' is not in EXECUTABLE frontier.")

        # 3. Prerequisites Check
        for prereq_id in proposal.prerequisites:
            prereq = obligations.get(prereq_id)
            if not prereq or prereq.status not in (ObligationStatus.SATISFIED, ObligationStatus.CONDITIONAL):
                reasons.append(f"Prerequisite obligation '{prereq_id}' is not satisfied.")

        # 4. Action Type Permission
        allowed_types = set(allowed_action_types or [
            "EXECUTE_TEST", "STATIC_ANALYSIS", "TYPE_CHECK", "FUZZ_CONTRACT", "APPLY_PATCH", "READ_FILE"
        ])
        if proposal.action_type not in allowed_types:
            reasons.append(f"Action type '{proposal.action_type}' is not permitted in active security profile.")

        # 5. Resource Budget Bounds
        if proposal.estimated_cost_usd > budget_remaining:
            reasons.append(f"Estimated cost ${proposal.estimated_cost_usd:.2f} exceeds remaining budget ${budget_remaining:.2f}.")

        # 6. Active D3 Policy Evaluation
        if target_obl.policy_id:
            pol = policies.get(target_obl.policy_id)
            if not pol:
                reasons.append(f"Active policy '{target_obl.policy_id}' not found in registered policies.")
            else:
                pol_ctx = PolicyEvaluationContext(
                    obligation=target_obl,
                    claims=(),
                    evidence=(),
                    evaluation_timestamp=evaluated_at,
                    expected_source_sha=source_sha,
                )
                pol_decision = evaluate_policy(pol, pol_ctx)
                if pol_decision.decision != PolicyDecisionType.ALLOW:
                    reasons.append(f"D3 Policy '{pol.policy_id}' evaluation denied ({pol_decision.decision.value}): {pol_decision.rationale}")

        decision_status = AuthorizationStatus.AUTHORIZED if not reasons else AuthorizationStatus.REJECTED

        return AuthorizationDecision(
            decision_id=f"DEC-{uuid.uuid4().hex[:8]}",
            proposal_id=proposal.proposal_id,
            obligation_id=proposal.obligation_id,
            status=decision_status,
            rejection_reasons=tuple(reasons),
            evaluated_at=evaluated_at,
            source_sha=source_sha,
            policy_version=policy_version,
        )
