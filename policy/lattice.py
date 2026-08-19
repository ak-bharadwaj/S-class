"""Non-Weakening Policy Lattice Algebra (⊓).

Core Rule:
Global Organization Policy (Tier 1)
        ⊓
Project Policy (Tier 2)
        ⊓
Task Policy (Tier 2.5)
        ⊓
Obligation Policy (Tier 3)

Lower layers may ONLY tighten (increase strictness), NEVER weaken a higher-level constraint.
"""

from typing import Dict, List, Sequence, Set, Tuple
from domain.models import Policy, PolicyRule, PolicyExpression
from domain.types import PolicyScope, RuleType, CombinatorType, ClaimTier
from policy.exceptions import PolicyWeakeningError, PolicyValidationError

SCOPE_HIERARCHY_RANK: Dict[PolicyScope, int] = {
    PolicyScope.GLOBAL_ORGANIZATIONAL: 0,
    PolicyScope.PROJECT: 1,
    PolicyScope.TASK: 2,
    PolicyScope.OBLIGATION: 3,
}

TIER_RANK: Dict[str, int] = {
    ClaimTier.V0_OBSERVABLE.value: 0,
    ClaimTier.V1_STRUCTURAL.value: 1,
    ClaimTier.V2_BEHAVIORAL.value: 2,
    ClaimTier.V3_PROPERTY.value: 3,
    ClaimTier.V4_ADVERSARIAL_EXPLORATORY.value: 4,
    "V3_SYSTEM_LEVEL": 3,
    "V4_JUDGMENT": 4,
}


def _extract_rules(expression: PolicyExpression) -> List[PolicyRule]:
    """Recursively extracts all flat rules from a PolicyExpression."""
    rules: List[PolicyRule] = list(expression.rules)
    if expression.then_expression:
        rules.extend(_extract_rules(expression.then_expression))
    if expression.else_expression:
        rules.extend(_extract_rules(expression.else_expression))
    return rules


def verify_non_weakening_rule(parent_rule: PolicyRule, child_rule: PolicyRule) -> None:
    """Verifies that child_rule tightens or equals parent_rule without weakening it."""
    if parent_rule.rule_type != child_rule.rule_type:
        return

    rtype = parent_rule.rule_type
    p_params = dict(parent_rule.parameters)
    c_params = dict(child_rule.parameters)

    if rtype == RuleType.REQUIRE_CAPABILITY:
        p_cap = p_params.get("capability")
        c_cap = c_params.get("capability")
        if p_cap != c_cap:
            raise PolicyWeakeningError(
                f"Child policy attempts to substitute required capability '{p_cap}' with '{c_cap}'."
            )

    elif rtype == RuleType.REQUIRE_TIER:
        p_tier = p_params.get("tier")
        c_tier = c_params.get("tier")
        p_count = p_params.get("min_count", 1)
        c_count = c_params.get("min_count", 1)

        p_tier_rank = TIER_RANK.get(p_tier, -1)
        c_tier_rank = TIER_RANK.get(c_tier, -1)

        if c_tier_rank < p_tier_rank:
            raise PolicyWeakeningError(
                f"Child policy attempts to lower tier requirement from '{p_tier}' to '{c_tier}'."
            )
        if c_count < p_count:
            raise PolicyWeakeningError(
                f"Child policy attempts to lower tier min_count from {p_count} to {c_count}."
            )

    elif rtype == RuleType.REQUIRE_INDEPENDENT_PROVIDERS:
        p_src = p_params.get("min_independent_sources", 1)
        c_src = c_params.get("min_independent_sources", 1)
        if c_src < p_src:
            raise PolicyWeakeningError(
                f"Child policy attempts to lower min_independent_sources from {p_src} to {c_src}."
            )

    elif rtype == RuleType.REQUIRE_MIN_TRIALS:
        p_trials = p_params.get("min_trials", 1)
        c_trials = c_params.get("min_trials", 1)
        if c_trials < p_trials:
            raise PolicyWeakeningError(
                f"Child policy attempts to lower min_trials from {p_trials} to {c_trials}."
            )


def meet_policies(parent: Policy, child: Policy) -> Policy:
    """Computes the monotonic non-weakening meet (⊓) of two policies.
    
    Raises:
        PolicyWeakeningError: if child policy weakens any parent constraint.
    """
    p_rank = SCOPE_HIERARCHY_RANK.get(parent.scope_level, 0)
    c_rank = SCOPE_HIERARCHY_RANK.get(child.scope_level, 0)

    if c_rank < p_rank:
        raise PolicyWeakeningError(
            f"Scope inversion: Child scope '{child.scope_level}' is higher than parent scope '{parent.scope_level}'."
        )

    parent_rules = _extract_rules(parent.expression)
    child_rules = _extract_rules(child.expression)

    # 1. Verify every parent rule is present and non-weakened in child
    for p_rule in parent_rules:
        matching_child_rules = [c for c in child_rules if c.rule_type == p_rule.rule_type]
        if not matching_child_rules:
            # If child omitted the mandatory parent rule, it is a weakening violation unless child expression is ALL combined
            raise PolicyWeakeningError(
                f"Child policy at scope '{child.scope_level}' omitted parent rule '{p_rule.rule_type.value}'."
            )
        for c_rule in matching_child_rules:
            verify_non_weakening_rule(p_rule, c_rule)

    # Combined rules: unique union of parent and child rules
    combined_rules: List[PolicyRule] = list(parent_rules)
    for c_rule in child_rules:
        if c_rule not in combined_rules:
            combined_rules.append(c_rule)

    combined_expression = PolicyExpression(
        combinator=CombinatorType.ALL,
        rules=tuple(combined_rules),
    )

    p_clean = parent.policy_id.replace("POL-", "").replace("+", "_").replace("-", "_")
    c_clean = child.policy_id.replace("POL-", "").replace("+", "_").replace("-", "_")

    return Policy(
        policy_id=f"POL-{p_clean}_{c_clean}",
        scope_level=child.scope_level,
        version=max(parent.version, child.version),
        expression=combined_expression,
    )


def compose_policies(*policies: Policy) -> Policy:
    """Composes a chain of policies from highest scope to lowest scope using meet (⊓)."""
    if not policies:
        raise PolicyValidationError("Cannot compose an empty sequence of policies.")

    sorted_policies = sorted(
        policies,
        key=lambda p: SCOPE_HIERARCHY_RANK.get(p.scope_level, 0)
    )

    current = sorted_policies[0]
    for next_policy in sorted_policies[1:]:
        current = meet_policies(current, next_policy)

    return current
