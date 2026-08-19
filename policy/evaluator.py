"""Pure Deterministic Policy Evaluator for S-Class D3."""

from datetime import datetime, timezone
import math
import re
from typing import Dict, List, Optional, Set, Tuple

from domain.models import (
    Policy,
    PolicyRule,
    PolicyExpression,
    Obligation,
    Claim,
    Evidence,
    EvidenceScope,
    EvidenceObservation,
    Provenance,
    HmacSessionSignature,
)
from domain.types import (
    PolicyScope,
    RuleType,
    CombinatorType,
    ClaimTier,
    ClaimStatus,
    EvidencePolarity,
    EvidenceValidity,
    RawStatus,
)
from policy.models import (
    PolicyDecision,
    PolicyDecisionType,
    PolicyEvaluationContext,
    PolicyException,
    RuleEvaluationResult,
)
from policy.exceptions import (
    PolicyEngineError,
    PolicyValidationError,
    InvalidExceptionError,
    ExpiredExceptionError,
)


class CoverageTrustPredicate:
    """Narrow interface consumed by D3 Policy Engine to verify structured coverage trust before evaluation.
    
    Validates:
    - Valid schema & lifecycle state (VALID + SUPPORTS + PASS)
    - Trusted provider identity (no untrusted/synthetic/simulation identifiers)
    - Provider capability matches coverage authorization
    - Provenance present, typed, and non-empty
    - Target / revision binding valid (source_sha)
    - Observation not stale or conflicted
    - Cryptographic session signature present
    """

    TRUSTED_COVERAGE_CAPABILITIES: Set[str] = {
        "CODE_COVERAGE",
        "COVERAGE_ANALYSIS",
        "STATIC_AST_ANALYSIS",
        "PROPERTY_TESTING",
        "API_CONTRACT_FUZZING",
        "TEST_EXECUTION",
    }

    FORBIDDEN_ENGINES: Set[str] = {
        "synthetic",
        "simulation",
        "untrusted",
        "fake",
        "mock",
        "dummy",
    }

    @classmethod
    def is_trusted(
        cls,
        evidence: Evidence,
        expected_source_sha: Optional[str] = None,
    ) -> bool:
        # 1. Schema and lifecycle verification
        if not isinstance(evidence, Evidence):
            return False
        if evidence.validity != EvidenceValidity.VALID:
            return False
        if evidence.polarity != EvidencePolarity.SUPPORTS:
            return False
        if not isinstance(evidence.observation, EvidenceObservation):
            return False
        if evidence.observation.raw_status != RawStatus.PASS:
            return False

        # 2. Capability matches coverage authorization
        if evidence.capability not in cls.TRUSTED_COVERAGE_CAPABILITIES:
            return False

        # 3. Trusted provider identity
        prov_id = (evidence.provider_id or "").lower()
        if not prov_id or any(f in prov_id for f in cls.FORBIDDEN_ENGINES):
            return False

        # 4. Provenance present & valid
        prov = evidence.provenance
        if not isinstance(prov, Provenance):
            return False
        engine_name = (prov.engine_name or "").lower()
        if not engine_name or any(f in engine_name for f in cls.FORBIDDEN_ENGINES):
            return False
        if not prov.engine_version or not prov.environment_hash or len(prov.environment_hash) != 64:
            return False
        if not prov.timestamp:
            return False

        # 5. Target / revision binding valid
        if not evidence.source_sha or len(evidence.source_sha) not in (40, 64):
            return False
        if expected_source_sha and evidence.source_sha != expected_source_sha:
            return False
        if not isinstance(evidence.scope, EvidenceScope):
            return False

        # 6. Session signature present
        sig = evidence.signature
        if not isinstance(sig, HmacSessionSignature):
            return False
        if not sig.signature_hex or len(sig.signature_hex) != 64:
            return False
        if not sig.raw_stdout_digest or len(sig.raw_stdout_digest) != 64:
            return False

        return True


def _check_valid_exception(
    exception: PolicyException,
    obligation_id: str,
    policy_id: str,
    eval_timestamp: str,
) -> None:
    """Validates that a PolicyException is active, unexpired, and strictly bound to target obligation and policy."""
    if exception.obligation_id != obligation_id:
        raise InvalidExceptionError(
            f"Exception obligation mismatch: got '{exception.obligation_id}', expected '{obligation_id}'."
        )

    if exception.policy_id != policy_id:
        raise InvalidExceptionError(
            f"Exception policy mismatch: got '{exception.policy_id}', expected '{policy_id}'."
        )

    if exception.expiry is not None:
        exp_dt = datetime.fromisoformat(exception.expiry.replace("Z", "+00:00"))
        eval_dt = datetime.fromisoformat(eval_timestamp.replace("Z", "+00:00"))
        if eval_dt > exp_dt:
            raise ExpiredExceptionError(
                f"PolicyException '{exception.exception_id}' expired at {exception.expiry} (evaluated at {eval_timestamp})."
            )

    if not exception.signature or not exception.signature.signature_hex:
        raise InvalidExceptionError(
            f"PolicyException '{exception.exception_id}' lacks valid cryptographic signature."
        )


def _extract_coverage_pct(
    evidence_item: Evidence,
    expected_source_sha: Optional[str] = None,
) -> Optional[float]:
    """Extracts trusted structured code coverage percentage from an Evidence item.
    
    Enforces strict trust predicate before accepting coverage payload:
    - Valid schema & lifecycle state
    - Trusted provider identity
    - Provider capability matches coverage
    - Provenance present & valid
    - Target/revision binding valid
    - Observation not stale or conflicted
    
    Free-form text in observation.diagnostics is strictly rejected as unauthoritative.
    """
    if not CoverageTrustPredicate.is_trusted(evidence_item, expected_source_sha):
        return None

    obs = evidence_item.observation

    # Only accept structured, typed observation mapping from trusted provider
    if not obs.counterexample:
        return None

    for k in ("coverage_pct", "line_coverage", "coverage", "statement_coverage", "branch_coverage"):
        if k in obs.counterexample:
            val = obs.counterexample[k]
            try:
                if isinstance(val, (int, float)):
                    cov = float(val)
                    if math.isnan(cov) or math.isinf(cov) or cov < 0.0 or cov > 100.0:
                        raise PolicyValidationError(f"Invalid coverage range: {cov}")
                    return cov
                elif isinstance(val, str):
                    m = re.search(r"^([0-9]+(?:\.[0-9]+)?)\s*%?$", val.strip())
                    if m:
                        cov = float(m.group(1))
                        if cov < 0.0 or cov > 100.0:
                            raise PolicyValidationError(f"Invalid coverage range: {cov}")
                        return cov
                    else:
                        raise PolicyValidationError(f"Malformed coverage string: '{val}'")
                else:
                    raise PolicyValidationError(f"Malformed coverage type: '{type(val).__name__}'")
            except Exception as exc:
                if isinstance(exc, PolicyValidationError):
                    raise
                raise PolicyValidationError(f"Malformed code coverage value: {val}") from exc

    return None


def evaluate_rule(
    rule: PolicyRule,
    context: PolicyEvaluationContext,
) -> RuleEvaluationResult:
    """Evaluates a single PolicyRule against the PolicyEvaluationContext."""
    rtype = rule.rule_type
    params = dict(rule.parameters)

    # 1. REQUIRE_CAPABILITY
    if rtype == RuleType.REQUIRE_CAPABILITY:
        required_cap = params.get("capability")
        matching_evidence = [
            e for e in context.evidence
            if e.capability == required_cap
            and e.validity == EvidenceValidity.VALID
            and e.polarity == EvidencePolarity.SUPPORTS
            and e.observation.raw_status == RawStatus.PASS
        ]
        if matching_evidence:
            return RuleEvaluationResult(
                rule=rule,
                passed=True,
                reason=f"Found {len(matching_evidence)} valid supporting evidence items with capability '{required_cap}'.",
            )
        else:
            return RuleEvaluationResult(
                rule=rule,
                passed=False,
                reason=f"No valid supporting evidence with required capability '{required_cap}'.",
            )

    # 2. REQUIRE_TIER
    elif rtype == RuleType.REQUIRE_TIER:
        required_tier = params.get("tier")
        min_count = params.get("min_count", 1)

        # Mandatory Rule for V4 (Judgment / Adversarial Exploratory): Evidence for V4 claims can NEVER satisfy a mandatory obligation on its own
        if required_tier in (ClaimTier.V4_ADVERSARIAL_EXPLORATORY.value, "V4_JUDGMENT"):
            has_corroborating = any(
                c.tier in (ClaimTier.V0_OBSERVABLE, ClaimTier.V1_STRUCTURAL, ClaimTier.V2_BEHAVIORAL, ClaimTier.V3_PROPERTY)
                and c.status in (ClaimStatus.SUPPORTED, ClaimStatus.WAIVED)
                for c in context.claims
            )
            if not has_corroborating:
                return RuleEvaluationResult(
                    rule=rule,
                    passed=False,
                    requires_exception=True,
                    reason="Tier V4 cannot satisfy a mandatory obligation without corroborating V0-V3 evidence or signed exception.",
                )

        supporting_claims = [
            c for c in context.claims
            if c.tier.value == required_tier
            and c.status in (ClaimStatus.SUPPORTED, ClaimStatus.WAIVED)
        ]

        if len(supporting_claims) >= min_count:
            return RuleEvaluationResult(
                rule=rule,
                passed=True,
                reason=f"Found {len(supporting_claims)} supporting claims for tier '{required_tier}' (>= {min_count}).",
            )
        else:
            return RuleEvaluationResult(
                rule=rule,
                passed=False,
                reason=f"Insufficient supporting claims for tier '{required_tier}': found {len(supporting_claims)}, expected {min_count}.",
            )

    # 3. NO_CONFLICTS
    elif rtype == RuleType.NO_CONFLICTS:
        conflicts = [
            e for e in context.evidence
            if e.validity == EvidenceValidity.CONFLICTED
            or e.polarity == EvidencePolarity.REFUTES
            or e.observation.raw_status == RawStatus.FAIL
        ]
        if not conflicts:
            return RuleEvaluationResult(
                rule=rule,
                passed=True,
                reason="No conflicting or refuting evidence detected.",
            )
        else:
            return RuleEvaluationResult(
                rule=rule,
                passed=False,
                reason=f"Detected {len(conflicts)} conflicting/refuting evidence items.",
            )

    # 4. REQUIRE_INDEPENDENT_PROVIDERS
    elif rtype == RuleType.REQUIRE_INDEPENDENT_PROVIDERS:
        min_sources = params.get("min_independent_sources", 1)
        group_by = params.get("group_by", "PROVIDER_TYPE")

        valid_supporting = [
            e for e in context.evidence
            if e.validity == EvidenceValidity.VALID
            and e.polarity == EvidencePolarity.SUPPORTS
            and e.observation.raw_status == RawStatus.PASS
        ]

        if group_by == "PROVIDER_TYPE" or group_by == "AUTHOR":
            distinct_groups = set(e.provider_id for e in valid_supporting)
        elif group_by == "EXECUTION_PROCESS":
            distinct_groups = set(e.execution_id for e in valid_supporting)
        else:
            distinct_groups = set(e.independence_group for e in valid_supporting)

        if len(distinct_groups) >= min_sources:
            return RuleEvaluationResult(
                rule=rule,
                passed=True,
                reason=f"Found {len(distinct_groups)} distinct provider groups (>= required {min_sources}).",
            )
        else:
            return RuleEvaluationResult(
                rule=rule,
                passed=False,
                reason=f"Insufficient independent provider sources: found {len(distinct_groups)}, required {min_sources}.",
            )

    # 5. FORBID_SYNTHETIC
    elif rtype == RuleType.FORBID_SYNTHETIC:
        synthetic_evidence = [
            e for e in context.evidence
            if "synthetic" in e.provider_id.lower() or "simulation" in e.provenance.engine_name.lower()
        ]
        if not synthetic_evidence:
            return RuleEvaluationResult(
                rule=rule,
                passed=True,
                reason="No synthetic/simulation evidence detected.",
            )
        else:
            return RuleEvaluationResult(
                rule=rule,
                passed=False,
                reason=f"Detected {len(synthetic_evidence)} synthetic evidence items violating FORBID_SYNTHETIC.",
            )

    # 6. MAX_STALENESS_COMMITS
    elif rtype == RuleType.MAX_STALENESS_COMMITS:
        stale = [e for e in context.evidence if e.validity == EvidenceValidity.STALE]
        if not stale:
            return RuleEvaluationResult(
                rule=rule,
                passed=True,
                reason="No stale evidence detected.",
            )
        else:
            return RuleEvaluationResult(
                rule=rule,
                passed=False,
                reason=f"Detected {len(stale)} stale evidence items.",
            )

    # 7. REQUIRE_MIN_TRIALS
    elif rtype == RuleType.REQUIRE_MIN_TRIALS:
        min_trials = params.get("min_trials", 1)
        valid_supporting = [
            e for e in context.evidence
            if e.validity == EvidenceValidity.VALID
            and e.polarity == EvidencePolarity.SUPPORTS
            and e.observation.raw_status == RawStatus.PASS
        ]
        if len(valid_supporting) >= min_trials:
            return RuleEvaluationResult(
                rule=rule,
                passed=True,
                reason=f"Found {len(valid_supporting)} trial evidence items (>= {min_trials}).",
            )
        else:
            return RuleEvaluationResult(
                rule=rule,
                passed=False,
                reason=f"Insufficient trial evidence: found {len(valid_supporting)}, expected {min_trials}.",
            )

    # 8. REQUIRE_CODE_COVERAGE
    elif rtype == RuleType.REQUIRE_CODE_COVERAGE:
        min_cov = float(params.get("min_coverage_pct", 85.0))
        extracted_coverages: List[float] = []

        for e in context.evidence:
            cov = _extract_coverage_pct(e)
            if cov is not None:
                extracted_coverages.append(cov)

        if not extracted_coverages:
            return RuleEvaluationResult(
                rule=rule,
                passed=False,
                reason="Missing trusted structured code coverage evidence in evaluation context.",
            )

        max_actual_coverage = max(extracted_coverages)
        if max_actual_coverage >= min_cov:
            return RuleEvaluationResult(
                rule=rule,
                passed=True,
                reason=f"Actual code coverage {max_actual_coverage:.2f}% satisfies required threshold {min_cov:.2f}%.",
            )
        else:
            return RuleEvaluationResult(
                rule=rule,
                passed=False,
                reason=f"Actual code coverage {max_actual_coverage:.2f}% < required threshold {min_cov:.2f}%.",
            )

    raise PolicyValidationError(f"Unsupported rule type: {rtype}")


def evaluate_expression(
    expression: PolicyExpression,
    context: PolicyEvaluationContext,
) -> Tuple[bool, bool, List[RuleEvaluationResult], List[str]]:
    """Evaluates a PolicyExpression tree recursively.
    
    Returns:
        Tuple of (passed: bool, requires_exception: bool, evaluated_rules, unmet_reasons)
    """
    comb = expression.combinator
    results: List[RuleEvaluationResult] = []
    unmet: List[str] = []

    # Conditional branching
    if comb == CombinatorType.CONDITIONAL:
        cond = dict(expression.condition or {})
        pred = cond.get("predicate")
        val = cond.get("value")

        condition_matched = False
        if pred == "criticality":
            condition_matched = (context.obligation.criticality.value == val)
        elif pred == "category":
            condition_matched = (context.obligation.category.value == val)

        sub_expr = expression.then_expression if condition_matched else expression.else_expression
        if sub_expr is None:
            raise PolicyValidationError("CONDITIONAL branch expression is null.")
        return evaluate_expression(sub_expr, context)

    # Flat rule combinators
    for r in expression.rules:
        res = evaluate_rule(r, context)
        results.append(res)
        if not res.passed:
            unmet.append(res.reason)

    if comb == CombinatorType.ALL:
        passed = all(r.passed for r in results)
        req_exc = any(r.requires_exception for r in results)
        return passed, req_exc, results, unmet

    elif comb == CombinatorType.ANY:
        passed = any(r.passed for r in results)
        req_exc = False if passed else any(r.requires_exception for r in results)
        return passed, req_exc, results, unmet

    elif comb == CombinatorType.AT_LEAST:
        min_c = expression.min_count or 1
        pass_count = sum(1 for r in results if r.passed)
        passed = (pass_count >= min_c)
        req_exc = False if passed else any(r.requires_exception for r in results)
        return passed, req_exc, results, unmet

    raise PolicyValidationError(f"Unsupported combinator: {comb}")


def evaluate_policy(
    policy: Policy,
    context: PolicyEvaluationContext,
) -> PolicyDecision:
    """Pure, side-effect free, deterministic evaluation of an effective policy against an evaluation context."""
    if not isinstance(policy, Policy):
        raise TypeError("Expected Policy instance.")
    if not isinstance(context, PolicyEvaluationContext):
        raise TypeError("Expected PolicyEvaluationContext instance.")

    passed, req_exc, rule_results, unmet = evaluate_expression(policy.expression, context)
    exceptions_applied: List[str] = []

    if passed:
        decision = PolicyDecisionType.ALLOW
        rationale = "All policy constraints successfully satisfied."
    else:
        # Check if valid matching exceptions exist for unmet rules
        applicable_exceptions = []
        for exc in context.exceptions:
            try:
                _check_valid_exception(
                    exc,
                    context.obligation.obligation_id,
                    policy.policy_id,
                    context.evaluation_timestamp,
                )
                applicable_exceptions.append(exc)
            except (ExpiredExceptionError, InvalidExceptionError):
                raise

        if applicable_exceptions:
            decision = PolicyDecisionType.ALLOW
            exceptions_applied = [e.exception_id for e in applicable_exceptions]
            rationale = f"Policy satisfied via authorized exceptions: {', '.join(exceptions_applied)}."
        elif req_exc:
            decision = PolicyDecisionType.REQUIRE_EXCEPTION
            rationale = f"Policy requires explicit exception authorization: {'; '.join(unmet)}."
        else:
            decision = PolicyDecisionType.DENY
            rationale = f"Policy evaluation failed: {'; '.join(unmet)}."

    return PolicyDecision(
        decision=decision,
        scope_evaluated=policy.scope_level,
        rules_evaluated=tuple(rule_results),
        unmet_requirements=tuple(unmet),
        exceptions_applied=tuple(exceptions_applied),
        rationale=rationale,
    )
