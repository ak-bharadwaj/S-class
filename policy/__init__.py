"""D3 Policy Engine for S-Class EOS."""

from domain.models import Policy, PolicyRule, PolicyExpression
from domain.types import PolicyScope, RuleType, CombinatorType
from policy.models import (
    PolicyDecision,
    PolicyDecisionType,
    AuthorizedActor,
    PolicyException,
    RuleEvaluationResult,
    PolicyEvaluationContext,
)
from policy.exceptions import (
    PolicyEngineError,
    PolicyValidationError,
    PolicyWeakeningError,
    InvalidExceptionError,
    ExpiredExceptionError,
)
from policy.lattice import (
    meet_policies,
    compose_policies,
    verify_non_weakening_rule,
)
from policy.evaluator import (
    evaluate_rule,
    evaluate_expression,
    evaluate_policy,
)

__all__ = [
    "Policy",
    "PolicyRule",
    "PolicyExpression",
    "PolicyScope",
    "RuleType",
    "CombinatorType",
    "PolicyDecision",
    "PolicyDecisionType",
    "AuthorizedActor",
    "PolicyException",
    "RuleEvaluationResult",
    "PolicyEvaluationContext",
    "PolicyEngineError",
    "PolicyValidationError",
    "PolicyWeakeningError",
    "InvalidExceptionError",
    "ExpiredExceptionError",
    "meet_policies",
    "compose_policies",
    "verify_non_weakening_rule",
    "evaluate_rule",
    "evaluate_expression",
    "evaluate_policy",
]
