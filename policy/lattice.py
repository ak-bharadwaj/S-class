"""Non-Weakening Policy Lattice Algebra (⊓) with Semantic Rule Matching.

Core Rule:
Global Organization Policy (Tier 1)
        ⊓
Project Policy (Tier 2)
        ⊓
Task Policy (Tier 2.5)
        ⊓
Obligation Policy (Tier 3)

Lower layers may ONLY tighten (increase strictness), NEVER weaken a higher-level constraint.
Semantic matching ensures cross-parameter substitution, omission, and duplication attacks fail closed.
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


def verify_and_merge_rules(parent_rules: Sequence[PolicyRule], child_rules: Sequence[PolicyRule]) -> List[PolicyRule]:
    """Semantically validates that child_rules do not weaken, omit, substitute, or dilute parent_rules, and computes the strict meet."""
    # 1. Semantic verification of every parent rule against child rules
    for p_rule in parent_rules:
        rtype = p_rule.rule_type
        p_params = dict(p_rule.parameters)

        if rtype == RuleType.REQUIRE_CAPABILITY:
            p_cap = p_params.get("capability")
            matching = [
                c for c in child_rules
                if c.rule_type == RuleType.REQUIRE_CAPABILITY
                and c.parameters.get("capability") == p_cap
            ]
            if not matching:
                raise PolicyWeakeningError(
                    f"Cross-parameter substitution / omission attack: parent requires capability '{p_cap}', but child omitted it or substituted it."
                )

        elif rtype == RuleType.REQUIRE_TIER:
            p_tier = p_params.get("tier")
            p_rank = TIER_RANK.get(p_tier, -1)
            p_count = p_params.get("min_count", 1)

            matching = [
                c for c in child_rules
                if c.rule_type == RuleType.REQUIRE_TIER
                and TIER_RANK.get(c.parameters.get("tier"), -1) >= p_rank
                and c.parameters.get("min_count", 1) >= p_count
            ]
            if not matching:
                raise PolicyWeakeningError(
                    f"Weakening / substitution attack on tier '{p_tier}' (required count {p_count})."
                )

            # Detect duplication attacks with weaker count for same tier
            for c in child_rules:
                if c.rule_type == RuleType.REQUIRE_TIER and c.parameters.get("tier") == p_tier:
                    if c.parameters.get("min_count", 1) < p_count:
                        raise PolicyWeakeningError(
                            f"Duplication weakening attack: child has conflicting tier rule with count {c.parameters.get('min_count', 1)} < {p_count}."
                        )

        elif rtype == RuleType.REQUIRE_INDEPENDENT_PROVIDERS:
            p_grp = p_params.get("group_by", "PROVIDER_TYPE")
            p_src = p_params.get("min_independent_sources", 1)
            matching = [
                c for c in child_rules
                if c.rule_type == RuleType.REQUIRE_INDEPENDENT_PROVIDERS
                and c.parameters.get("group_by", "PROVIDER_TYPE") == p_grp
                and c.parameters.get("min_independent_sources", 1) >= p_src
            ]
            if not matching:
                raise PolicyWeakeningError(
                    f"Weakening / omission attack on independent providers (group_by={p_grp}, required min={p_src})."
                )

        elif rtype == RuleType.REQUIRE_MIN_TRIALS:
            p_trials = p_params.get("min_trials", 1)
            matching = [
                c for c in child_rules
                if c.rule_type == RuleType.REQUIRE_MIN_TRIALS
                and c.parameters.get("min_trials", 1) >= p_trials
            ]
            if not matching:
                raise PolicyWeakeningError(
                    f"Weakening / omission attack on min_trials (required {p_trials})."
                )

        elif rtype == RuleType.REQUIRE_CODE_COVERAGE:
            p_cov = float(p_params.get("min_coverage_pct", 85.0))
            matching = [
                c for c in child_rules
                if c.rule_type == RuleType.REQUIRE_CODE_COVERAGE
                and float(c.parameters.get("min_coverage_pct", 85.0)) >= p_cov
            ]
            if not matching:
                raise PolicyWeakeningError(
                    f"Weakening / omission attack on code coverage (required {p_cov}%)."
                )

        elif rtype == RuleType.MAX_STALENESS_COMMITS:
            p_comm = p_params.get("max_commits", 10)
            matching = [
                c for c in child_rules
                if c.rule_type == RuleType.MAX_STALENESS_COMMITS
                and c.parameters.get("max_commits", 10) <= p_comm
            ]
            if not matching:
                raise PolicyWeakeningError(
                    f"Weakening / omission attack on max staleness commits (max allowed {p_comm})."
                )

        elif rtype in (RuleType.NO_CONFLICTS, RuleType.FORBID_SYNTHETIC):
            matching = [c for c in child_rules if c.rule_type == rtype]
            if not matching:
                raise PolicyWeakeningError(
                    f"Omission attack: parent requires '{rtype.value}', but child omitted it."
                )

    # 2. Merge rules into canonical meet representation
    merged: List[PolicyRule] = []

    # Capabilities (union)
    all_caps: Set[str] = set()
    for r in list(parent_rules) + list(child_rules):
        if r.rule_type == RuleType.REQUIRE_CAPABILITY:
            cap = r.parameters.get("capability")
            if cap and cap not in all_caps:
                all_caps.add(cap)
                merged.append(PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": cap}))

    # Tiers (max count per tier)
    tier_counts: Dict[str, int] = {}
    for r in list(parent_rules) + list(child_rules):
        if r.rule_type == RuleType.REQUIRE_TIER:
            t = r.parameters.get("tier")
            cnt = r.parameters.get("min_count", 1)
            tier_counts[t] = max(tier_counts.get(t, 0), cnt)
    for t, cnt in tier_counts.items():
        merged.append(PolicyRule(RuleType.REQUIRE_TIER, {"tier": t, "min_count": cnt}))

    # Independent providers (max sources per group_by)
    provider_groups: Dict[str, int] = {}
    for r in list(parent_rules) + list(child_rules):
        if r.rule_type == RuleType.REQUIRE_INDEPENDENT_PROVIDERS:
            grp = r.parameters.get("group_by", "PROVIDER_TYPE")
            src = r.parameters.get("min_independent_sources", 1)
            provider_groups[grp] = max(provider_groups.get(grp, 0), src)
    for grp, src in provider_groups.items():
        merged.append(PolicyRule(RuleType.REQUIRE_INDEPENDENT_PROVIDERS, {"group_by": grp, "min_independent_sources": src}))

    # Trials (max)
    max_trials = None
    for r in list(parent_rules) + list(child_rules):
        if r.rule_type == RuleType.REQUIRE_MIN_TRIALS:
            t = r.parameters.get("min_trials", 1)
            max_trials = max(max_trials or 0, t)
    if max_trials is not None:
        merged.append(PolicyRule(RuleType.REQUIRE_MIN_TRIALS, {"min_trials": max_trials}))

    # Coverage (max)
    max_cov = None
    for r in list(parent_rules) + list(child_rules):
        if r.rule_type == RuleType.REQUIRE_CODE_COVERAGE:
            c = float(r.parameters.get("min_coverage_pct", 85.0))
            max_cov = max(max_cov or 0.0, c)
    if max_cov is not None:
        merged.append(PolicyRule(RuleType.REQUIRE_CODE_COVERAGE, {"min_coverage_pct": max_cov}))

    # Staleness commits (min allowed)
    min_commits = None
    for r in list(parent_rules) + list(child_rules):
        if r.rule_type == RuleType.MAX_STALENESS_COMMITS:
            m = r.parameters.get("max_commits", 10)
            min_commits = min(min_commits if min_commits is not None else 999999, m)
    if min_commits is not None:
        merged.append(PolicyRule(RuleType.MAX_STALENESS_COMMITS, {"max_commits": min_commits}))

    # Invariants
    if any(r.rule_type == RuleType.NO_CONFLICTS for r in list(parent_rules) + list(child_rules)):
        merged.append(PolicyRule(RuleType.NO_CONFLICTS, {}))
    if any(r.rule_type == RuleType.FORBID_SYNTHETIC for r in list(parent_rules) + list(child_rules)):
        merged.append(PolicyRule(RuleType.FORBID_SYNTHETIC, {}))

    return merged


def verify_non_weakening_rule(parent_rule: PolicyRule, child_rule: PolicyRule) -> None:
    """Verifies that child_rule tightens or equals parent_rule without weakening it."""
    verify_and_merge_rules([parent_rule], [child_rule])


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

    merged_rules = verify_and_merge_rules(parent_rules, child_rules)

    combined_expression = PolicyExpression(
        combinator=CombinatorType.ALL,
        rules=tuple(merged_rules),
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
