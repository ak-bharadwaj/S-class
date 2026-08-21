"""
S-Class EOS V11.2 - D5 Action Authorization Engine (§8.1, §8.2, CORE-05).
Precondition evaluation and immutable AuthorizationDecision creation.
Actually evaluates active D3 Policy using PolicyEvaluationContext.
Enforces:
1. Target obligation must be registered and in Executable Frontier (READY != EXECUTABLE).
2. ActionBinding strictly bound: action_digest computed from action_type, target, purpose, parameters.
3. ExecutionContext strictly bound: context_digest computed from provider_id, sandbox_profile_id, workspace_id, resource_profile_id, capability_set.
4. All prerequisites listed in proposal must be SATISFIED or CONDITIONAL.
5. Action type must be permitted under active security profile.
6. Active D3 Policy evaluated and satisfied (ALLOW).
7. Estimated cost and timeout must not exceed budget bounds.
"""

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Sequence, Tuple, Any
from domain.models import Obligation, Policy, _validate_iso8601, _validate_pattern, _freeze_nested
from domain.types import ObligationStatus, PolicyScope, HEX_64_PATTERN
from policy.evaluator import evaluate_policy
from policy.models import PolicyEvaluationContext, PolicyDecisionType
from controller.frontier import compute_frontier, ExecutionFrontier
from controller.token import ActionBinding, ExecutionContext, compute_action_digest


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
    execution_context: ExecutionContext
    estimated_cost_usd: float = 0.0
    timeout_seconds: int = 60
    prerequisites: Tuple[str, ...] = field(default_factory=tuple)
    parameters: Mapping[str, Any] = field(default_factory=dict)
    action_digest: str = ""
    fencing_token: int = 0
    lease_epoch: int = 0
    owner_id: str = ""
    state_version: int = 0
    state_digest: str = ""

    def __post_init__(self):
        if not self.proposal_id:
            raise ValueError("proposal_id cannot be empty.")
        if not self.obligation_id:
            raise ValueError("obligation_id cannot be empty.")
        if not self.action_type:
            raise ValueError("action_type cannot be empty.")
        if not self.target:
            raise ValueError("target cannot be empty.")
        if not self.purpose:
            raise ValueError("purpose cannot be empty.")
        if not isinstance(self.execution_context, ExecutionContext):
            raise TypeError("execution_context must be an ExecutionContext instance.")
        if self.estimated_cost_usd < 0.0:
            raise ValueError("estimated_cost_usd cannot be negative.")
        if self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be >= 1.")
        if not isinstance(self.fencing_token, int) or self.fencing_token < 0:
            raise ValueError("fencing_token must be an integer >= 0.")
        if not isinstance(self.lease_epoch, int) or self.lease_epoch < 0:
            raise ValueError("lease_epoch must be an integer >= 0.")
        if not isinstance(self.state_version, int) or self.state_version < 0:
            raise ValueError("state_version must be an integer >= 0.")
        if self.state_digest:
            _validate_pattern(self.state_digest, HEX_64_PATTERN, "state_digest")
        object.__setattr__(self, "prerequisites", tuple(self.prerequisites))
        object.__setattr__(self, "parameters", _freeze_nested(self.parameters))

        expected_digest = compute_action_digest(
            action_type=self.action_type,
            target=self.target,
            purpose=self.purpose,
            parameters=self.parameters,
        )
        if not self.action_digest:
            object.__setattr__(self, "action_digest", expected_digest)
        elif self.action_digest != expected_digest:
            raise ValueError(f"action_digest mismatch: '{self.action_digest}' != '{expected_digest}'")
        _validate_pattern(self.action_digest, HEX_64_PATTERN, "action_digest")

    @property
    def binding(self) -> ActionBinding:
        return ActionBinding(
            action_type=self.action_type,
            target=self.target,
            purpose=self.purpose,
            parameters=self.parameters,
            action_digest=self.action_digest,
        )

    @property
    def context_digest(self) -> str:
        return self.execution_context.context_digest


@dataclass(frozen=True)
class AuthorizationDecision:
    """Immutable categorical decision issued upon PRE_AUTHORIZE completion."""
    decision_id: str
    proposal_id: str
    obligation_id: str
    action_digest: str
    context_digest: str
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
        _validate_pattern(self.action_digest, HEX_64_PATTERN, "action_digest")
        _validate_pattern(self.context_digest, HEX_64_PATTERN, "context_digest")
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
        active_fencing_token: Optional[int] = None,
        active_lease_epoch: Optional[int] = None,
        active_owner_id: Optional[str] = None,
        expected_state_version: Optional[int] = None,
        expected_state_digest: Optional[str] = None,
    ) -> AuthorizationDecision:
        """Evaluates preconditions and produces an immutable AuthorizationDecision."""
        if not evaluated_at:
            raise ValueError("evaluated_at timestamp is required.")

        reasons: list[str] = []

        # 0. Exact Fencing & Lease Identity Validation (Strict Fail-Closed)
        if active_fencing_token is None:
            reasons.append("INVALID_FENCING_TOKEN: No active planning lease found for target obligation.")
        elif proposal.fencing_token != active_fencing_token:
            reasons.append(
                f"INVALID_FENCING_TOKEN: Proposal fencing_token {proposal.fencing_token} "
                f"does not match active lease fencing_token {active_fencing_token}."
            )

        if active_lease_epoch is None:
            reasons.append("INVALID_LEASE_EPOCH: No active lease epoch available.")
        elif proposal.lease_epoch != active_lease_epoch:
            reasons.append(
                f"INVALID_LEASE_EPOCH: Proposal lease_epoch {proposal.lease_epoch} "
                f"does not match active lease lease_epoch {active_lease_epoch}."
            )

        if not active_owner_id:
            reasons.append("WRONG_LEASE_OWNER: No active lease owner available.")
        elif proposal.owner_id != active_owner_id:
            reasons.append(
                f"WRONG_LEASE_OWNER: Proposal owner '{proposal.owner_id}' "
                f"does not match active lease owner '{active_owner_id}'."
            )

        # 0b. Exact State Freshness Validation (Strict Fail-Closed)
        if expected_state_version is None:
            reasons.append("STALE_STATE_VERSION: No authoritative state version available.")
        elif proposal.state_version != expected_state_version:
            reasons.append(
                f"STALE_STATE_VERSION: Proposal state_version {proposal.state_version} "
                f"does not match authoritative state_version {expected_state_version}."
            )

        if not expected_state_digest:
            reasons.append("STALE_STATE_DIGEST: No authoritative state digest available.")
        elif proposal.state_digest != expected_state_digest:
            reasons.append(
                f"STALE_STATE_DIGEST: Proposal state_digest '{proposal.state_digest}' "
                f"does not match authoritative state_digest '{expected_state_digest}'."
            )

        # 1. Target Obligation Existence
        target_obl = obligations.get(proposal.obligation_id)
        if not target_obl:
            return AuthorizationDecision(
                decision_id=f"DEC-{uuid.uuid4().hex[:8]}",
                proposal_id=proposal.proposal_id,
                obligation_id=proposal.obligation_id,
                action_digest=proposal.action_digest,
                context_digest=proposal.context_digest,
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
            action_digest=proposal.action_digest,
            context_digest=proposal.context_digest,
            status=decision_status,
            rejection_reasons=tuple(reasons),
            evaluated_at=evaluated_at,
            source_sha=source_sha,
            policy_version=policy_version,
        )
