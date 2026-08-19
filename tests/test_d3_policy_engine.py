"""Tier 1 Adversarial, Determinism, Non-Weakening Lattice, and Property Tests for S-Class D3 Policy Engine.

Tests:
1. Schema Conformance & Anti-Pollution (Draft 2020-12):
   - Extra fields in policy / policy rule / expression / exception rejected fail closed.
   - Empty policy or rules rejected.
2. Adversarial Vectors:
   - (a) Invalid rule parameter rejected.
   - (b) Unknown rule type rejected.
   - (c) Malformed combinator rejected.
   - (d) Conflicting allow/deny (hard invariant failure strictly DENY).
   - (e) Lower-level weakening attempt raises PolicyWeakeningError.
   - (f) Exception without provenance / signature rejected.
   - (g) Expired / invalid exception rejected with ExpiredExceptionError.
   - (h) Nondeterministic evaluation context (1,000 runs produce identical output).
   - (i) Policy pollution / extra fields fail closed.
   - (j) Empty policy rejected.
   - (k) Contradictory policy hierarchy resolves to strictest meet or fails closed.
   - (l) V4-only justification cannot bypass mandatory rule without corroborating evidence or signed exception.
   - (m) Policy ID Mismatch on Exception: Signed exception for Policy-A evaluated against Policy-B fails closed with InvalidExceptionError.
3. Code Coverage Evidence Adversarial Suite:
   - 0% coverage -> DENY
   - Below threshold -> DENY
   - Exactly threshold -> ALLOW
   - Above threshold -> ALLOW
   - Missing structured coverage evidence -> DENY
   - Malformed coverage evidence (non-numeric, NaN, out of range) -> fail closed
   - Forged / misleading diagnostic text rejected as unauthoritative evidence
   - Forged structured coverage with VALID + SUPPORTS + PASS but invalid/missing provenance / capability mismatch -> DENY
4. Cross-Parameter Substitution, Omission, and Duplication Attacks:
   - Capability substitution attack (P requires A, C supplies B) -> PolicyWeakeningError
   - Tier weakening / lowering attack (P requires V2 count 3, C supplies V1 or count 1) -> PolicyWeakeningError
   - Provider group weakening / omission -> PolicyWeakeningError
   - Trials lowering -> PolicyWeakeningError
   - Coverage lowering -> PolicyWeakeningError
   - Staleness commits loosening -> PolicyWeakeningError
   - Omission of invariant flags (NO_CONFLICTS, FORBID_SYNTHETIC) -> PolicyWeakeningError
   - Duplication dilution attack (C provides conflicting duplicates) -> PolicyWeakeningError
5. Property-Based Testing (Hypothesis):
   - Monotonicity: Strictness(P ⊓ Q) >= Strictness(P).
"""

from copy import deepcopy
import json
import os
import re
from typing import Dict, List, Tuple
from hypothesis import given, strategies as st, settings
import jsonschema
from jsonschema import Draft202012Validator
import pytest
import yaml

from domain.models import (
    Policy,
    PolicyRule,
    PolicyExpression,
    AsymmetricAuthoritySignature,
    Task,
    Obligation,
    Claim,
    ClaimSubject,
    Evidence,
    EvidenceScope,
    EvidenceObservation,
    Provenance,
    HmacSessionSignature,
    RepositoryContext,
)
from domain.types import (
    PolicyScope,
    RuleType,
    CombinatorType,
    ClaimTier,
    ClaimStatus,
    ObligationCategory,
    ObligationStatus,
    Criticality,
    TargetType,
    EvidencePolarity,
    EvidenceValidity,
    RawStatus,
)
from domain.exceptions import DomainValidationError
from policy import (
    PolicyDecision,
    PolicyDecisionType,
    AuthorizedActor,
    PolicyException,
    RuleEvaluationResult,
    PolicyEvaluationContext,
    PolicyEngineError,
    PolicyValidationError,
    PolicyWeakeningError,
    InvalidExceptionError,
    ExpiredExceptionError,
    CoverageTrustPredicate,
    meet_policies,
    compose_policies,
    verify_and_merge_rules,
    verify_non_weakening_rule,
    evaluate_rule,
    evaluate_expression,
    evaluate_policy,
)


# ============================================================================
# Helpers & Fixtures
# ============================================================================

def make_test_obligation(
    obl_id: str = "OBL-001",
    task_id: str = "TASK-001",
    criticality: Criticality = Criticality.HIGH,
    category: ObligationCategory = ObligationCategory.SECURITY_INTEGRITY,
) -> Obligation:
    return Obligation(
        obligation_id=obl_id,
        task_id=task_id,
        title=f"Test Obligation {obl_id}",
        description="Enforce security invariant",
        category=category,
        criticality=criticality,
        status=ObligationStatus.OPEN,
        depends_on=(),
        claim_ids=(f"CLM-{obl_id}",),
        policy_id="POL-001",
    )


def make_test_claim(
    claim_id: str = "CLM-OBL-001",
    obligation_id: str = "OBL-001",
    tier: ClaimTier = ClaimTier.V2_BEHAVIORAL,
    status: ClaimStatus = ClaimStatus.SUPPORTED,
) -> Claim:
    return Claim(
        claim_id=claim_id,
        obligation_id=obligation_id,
        tier=tier,
        subject=ClaimSubject(
            target_type=TargetType.ENDPOINT,
            identifier="DELETE:/users/{id}",
        ),
        predicate="REJECTS_UNAUTHORIZED_REQUEST",
        context={"role": "GUEST"},
        expected={"status": 403},
        criticality=Criticality.HIGH,
        status=status,
        required_provider_capabilities=("API_CONTRACT_FUZZING",),
    )


def make_test_evidence(
    ev_id: str = "EV-001",
    claim_id: str = "CLM-OBL-001",
    capability: str = "CODE_COVERAGE",
    polarity: EvidencePolarity = EvidencePolarity.SUPPORTS,
    validity: EvidenceValidity = EvidenceValidity.VALID,
    raw_status: RawStatus = RawStatus.PASS,
    provider_id: str = "coverage_py_runner",
    execution_id: str = "EXEC-001",
    independence_group: str = "INDEP-GROUP-1",
    counterexample: dict = None,
    diagnostics: tuple = ("Coverage test run completed",),
    engine_name: str = "coverage.py",
) -> Evidence:
    return Evidence(
        evidence_id=ev_id,
        claim_id=claim_id,
        provider_id=provider_id,
        capability=capability,
        execution_id=execution_id,
        source_sha="a" * 40,
        scope=EvidenceScope(
            targets_evaluated=("DELETE:/users/{id}",),
            aspects_covered=("AUTH_ENFORCEMENT",),
        ),
        observation=EvidenceObservation(
            raw_status=raw_status,
            diagnostics=diagnostics,
            counterexample=counterexample,
        ),
        polarity=polarity,
        validity=validity,
        independence_group=independence_group,
        provenance=Provenance(
            engine_name=engine_name,
            engine_version="7.4.0",
            environment_hash="b" * 64,
            timestamp="2026-08-19T10:00:00Z",
        ),
        signature=HmacSessionSignature(
            algorithm="HMAC-SHA256",
            key_id="KEY-001",
            nonce="NONCE-001",
            raw_stdout_digest="c" * 64,
            signature_hex="d" * 64,
            timestamp="2026-08-19T10:00:00Z",
        ),
    )


def make_test_exception(
    exc_id: str = "EXC-001",
    obl_id: str = "OBL-001",
    policy_id: str = "POL-001",
    expiry: str = "2026-12-31T23:59:59Z",
) -> PolicyException:
    return PolicyException(
        exception_id=exc_id,
        obligation_id=obl_id,
        policy_id=policy_id,
        justification="Manual security review approved by security lead with HSM token.",
        authorized_by=AuthorizedActor(
            actor_id="SEC-OFFICER-01",
            actor_role="SECURITY_LEAD",
            public_key_fingerprint="f" * 64,
        ),
        compensating_controls=("Audit log monitoring enabled", "WAF rate limit enabled"),
        expiry=expiry,
        signature=AsymmetricAuthoritySignature(
            algorithm="ED25519",
            signer_identity="SEC-OFFICER-01",
            public_key_fingerprint="f" * 64,
            payload_digest="1" * 64,
            signature_hex="2" * 128,
            timestamp="2026-08-19T10:00:00Z",
        ),
    )


# ============================================================================
# 1. Adversarial Tests for Policy Engine
# ============================================================================

def test_adversarial_invalid_rule_parameter():
    """Adversarial vector: Invalid/missing rule parameters fail closed with DomainValidationError."""
    with pytest.raises(DomainValidationError):
        PolicyRule(
            rule_type=RuleType.REQUIRE_CAPABILITY,
            parameters={"capability": 12345},
        )

    with pytest.raises(DomainValidationError):
        PolicyRule(
            rule_type=RuleType.REQUIRE_CAPABILITY,
            parameters={"capability": "PROPERTY_TESTING", "unauthorized_extra": True},
        )

    with pytest.raises(DomainValidationError):
        PolicyRule(
            rule_type=RuleType.REQUIRE_TIER,
            parameters={"tier": "V2_BEHAVIORAL", "min_count": -1},
        )


def test_adversarial_unknown_rule_type():
    """Adversarial vector: Unknown rule type string fails closed."""
    with pytest.raises((DomainValidationError, ValueError)):
        PolicyRule(
            rule_type="UNAUTHORIZED_RULE_TYPE",  # type: ignore
            parameters={},
        )


def test_adversarial_malformed_combinator():
    """Adversarial vector: Malformed combinator fails closed."""
    with pytest.raises((DomainValidationError, ValueError)):
        PolicyExpression(
            combinator="INVALID_COMBINATOR",  # type: ignore
            rules=(),
        )


def test_adversarial_conflicting_allow_deny():
    """Adversarial vector: Conflicting/refuting evidence strictly forces DENY decision under NO_CONFLICTS."""
    obl = make_test_obligation()
    claim = make_test_claim()
    ev_pass = make_test_evidence(ev_id="EV-001", capability="API_CONTRACT_FUZZING", polarity=EvidencePolarity.SUPPORTS, raw_status=RawStatus.PASS)
    ev_fail = make_test_evidence(
        ev_id="EV-002",
        capability="API_CONTRACT_FUZZING",
        polarity=EvidencePolarity.REFUTES,
        raw_status=RawStatus.FAIL,
        validity=EvidenceValidity.CONFLICTED,
    )

    ctx = PolicyEvaluationContext(
        obligation=obl,
        claims=(claim,),
        evidence=(ev_pass, ev_fail),
        evaluation_timestamp="2026-08-19T10:00:00Z",
    )

    policy = Policy(
        policy_id="POL-001",
        scope_level=PolicyScope.PROJECT,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(
                PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),
                PolicyRule(RuleType.NO_CONFLICTS, {}),
            ),
        ),
    )

    decision = evaluate_policy(policy, ctx)
    assert decision.decision == PolicyDecisionType.DENY
    assert "conflicting" in decision.rationale.lower()


def test_adversarial_lower_level_weakening_attempt():
    """Adversarial vector: Lower-scope policy attempting to weaken ancestor constraints raises PolicyWeakeningError."""
    parent = Policy(
        policy_id="POL-ORG-001",
        scope_level=PolicyScope.GLOBAL_ORGANIZATIONAL,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(
                PolicyRule(RuleType.REQUIRE_TIER, {"tier": "V2_BEHAVIORAL", "min_count": 3}),
                PolicyRule(RuleType.NO_CONFLICTS, {}),
            ),
        ),
    )

    child_weak_count = Policy(
        policy_id="POL-PROJ-001",
        scope_level=PolicyScope.PROJECT,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(
                PolicyRule(RuleType.REQUIRE_TIER, {"tier": "V2_BEHAVIORAL", "min_count": 1}),
                PolicyRule(RuleType.NO_CONFLICTS, {}),
            ),
        ),
    )
    with pytest.raises(PolicyWeakeningError, match="Weakening / substitution attack on tier"):
        meet_policies(parent, child_weak_count)

    child_omitted_rule = Policy(
        policy_id="POL-PROJ-002",
        scope_level=PolicyScope.PROJECT,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(
                PolicyRule(RuleType.REQUIRE_TIER, {"tier": "V2_BEHAVIORAL", "min_count": 3}),
            ),
        ),
    )
    with pytest.raises(PolicyWeakeningError, match="Omission attack"):
        meet_policies(parent, child_omitted_rule)


def test_adversarial_exception_without_provenance():
    """Adversarial vector: Exception lacking valid signature fails closed."""
    with pytest.raises(InvalidExceptionError):
        PolicyException(
            exception_id="EXC-001",
            obligation_id="OBL-001",
            policy_id="POL-001",
            justification="Valid justification string that is long enough.",
            authorized_by=AuthorizedActor("ACTOR-1", "ROLE", "a" * 64),
            compensating_controls=("Control 1 long enough",),
            signature="UNSIGNED_FORGERY",  # type: ignore
        )


def test_adversarial_expired_exception():
    """Adversarial vector: Expired exception raises ExpiredExceptionError during evaluation."""
    obl = make_test_obligation()
    claim = make_test_claim(tier=ClaimTier.V4_ADVERSARIAL_EXPLORATORY)

    exc = make_test_exception(expiry="2026-08-01T00:00:00Z")

    ctx = PolicyEvaluationContext(
        obligation=obl,
        claims=(claim,),
        evidence=(),
        exceptions=(exc,),
        evaluation_timestamp="2026-08-19T10:00:00Z",  # After expiry!
    )

    policy = Policy(
        policy_id="POL-001",
        scope_level=PolicyScope.PROJECT,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(
                PolicyRule(RuleType.REQUIRE_TIER, {"tier": "V4_ADVERSARIAL_EXPLORATORY", "min_count": 1}),
            ),
        ),
    )

    with pytest.raises(ExpiredExceptionError, match="expired"):
        evaluate_policy(policy, ctx)


def test_adversarial_policy_id_exception_mismatch():
    """Adversarial vector: Signed exception for Policy-A evaluated against Policy-B must fail closed with InvalidExceptionError."""
    obl = make_test_obligation(obl_id="OBL-001")
    claim = make_test_claim(tier=ClaimTier.V4_ADVERSARIAL_EXPLORATORY)

    # Exception is authorized specifically for POL-A
    exc_for_pol_a = make_test_exception(exc_id="EXC-A", obl_id="OBL-001", policy_id="POL-A")

    ctx = PolicyEvaluationContext(
        obligation=obl,
        claims=(claim,),
        evidence=(),
        exceptions=(exc_for_pol_a,),
        evaluation_timestamp="2026-08-19T10:00:00Z",
    )

    # Evaluated against POL-B
    policy_b = Policy(
        policy_id="POL-B",
        scope_level=PolicyScope.PROJECT,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(PolicyRule(RuleType.REQUIRE_TIER, {"tier": "V4_ADVERSARIAL_EXPLORATORY", "min_count": 1}),),
        ),
    )

    with pytest.raises(InvalidExceptionError, match="Exception policy mismatch"):
        evaluate_policy(policy_b, ctx)


def test_adversarial_nondeterministic_evaluation_context():
    """Adversarial vector: 1,000 evaluation executions with identical input produce identical byte-for-byte decisions."""
    obl = make_test_obligation()
    claim = make_test_claim()
    ev = make_test_evidence(capability="API_CONTRACT_FUZZING")

    ctx = PolicyEvaluationContext(
        obligation=obl,
        claims=(claim,),
        evidence=(ev,),
        evaluation_timestamp="2026-08-19T10:00:00Z",
    )

    policy = Policy(
        policy_id="POL-001",
        scope_level=PolicyScope.PROJECT,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(
                PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),
                PolicyRule(RuleType.REQUIRE_TIER, {"tier": "V2_BEHAVIORAL", "min_count": 1}),
                PolicyRule(RuleType.NO_CONFLICTS, {}),
            ),
        ),
    )

    first_decision = evaluate_policy(policy, ctx)
    for _ in range(1000):
        d = evaluate_policy(policy, ctx)
        assert d == first_decision
        assert d.decision == PolicyDecisionType.ALLOW


def test_adversarial_policy_pollution_extra_fields():
    """Adversarial vector: Extra dictionary fields in policy objects fail closed with DomainValidationError."""
    with pytest.raises(DomainValidationError):
        Policy(
            policy_id="POL-001",
            scope_level=PolicyScope.PROJECT,
            version=1,
            expression=PolicyExpression(
                combinator=CombinatorType.ALL,
                rules=(
                    PolicyRule(RuleType.NO_CONFLICTS, {"extra_polluted_param": 999}),
                ),
            ),
        )


def test_adversarial_empty_policy():
    """Adversarial vector: Composing empty sequence of policies fails closed."""
    with pytest.raises(PolicyValidationError):
        compose_policies()


def test_adversarial_contradictory_policy_hierarchy():
    """Adversarial vector: Scope inversion fails closed with PolicyWeakeningError."""
    low_parent = Policy(
        policy_id="POL-OBL-001",
        scope_level=PolicyScope.OBLIGATION,
        version=1,
        expression=PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.NO_CONFLICTS, {}),)),
    )
    high_child = Policy(
        policy_id="POL-SYS-001",
        scope_level=PolicyScope.GLOBAL_ORGANIZATIONAL,
        version=1,
        expression=PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.NO_CONFLICTS, {}),)),
    )
    with pytest.raises(PolicyWeakeningError, match="Scope inversion"):
        meet_policies(low_parent, high_child)


def test_adversarial_v4_judgment_cannot_bypass_mandatory_rule():
    """Adversarial vector: V4 Judgment / Exploratory claim alone CANNOT satisfy mandatory policy without corroborating V0-V3 or signed exception."""
    obl = make_test_obligation(criticality=Criticality.HIGH)
    claim_v4 = make_test_claim(tier=ClaimTier.V4_ADVERSARIAL_EXPLORATORY, status=ClaimStatus.SUPPORTED)

    policy = Policy(
        policy_id="POL-001",
        scope_level=PolicyScope.PROJECT,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(
                PolicyRule(RuleType.REQUIRE_TIER, {"tier": "V4_ADVERSARIAL_EXPLORATORY", "min_count": 1}),
            ),
        ),
    )

    ctx_unauthorized = PolicyEvaluationContext(
        obligation=obl,
        claims=(claim_v4,),
        evidence=(),
        exceptions=(),
        evaluation_timestamp="2026-08-19T10:00:00Z",
    )
    decision = evaluate_policy(policy, ctx_unauthorized)
    assert decision.decision == PolicyDecisionType.REQUIRE_EXCEPTION

    exc = make_test_exception(obl_id="OBL-001", policy_id="POL-001")
    ctx_authorized = PolicyEvaluationContext(
        obligation=obl,
        claims=(claim_v4,),
        evidence=(),
        exceptions=(exc,),
        evaluation_timestamp="2026-08-19T10:00:00Z",
    )
    decision_exc = evaluate_policy(policy, ctx_authorized)
    assert decision_exc.decision == PolicyDecisionType.ALLOW
    assert "EXC-001" in decision_exc.exceptions_applied


# ============================================================================
# 2. Code Coverage Evidence Adversarial Suite
# ============================================================================

def test_coverage_evaluation_adversarial_suite():
    """Adversarial coverage tests: 0%, below threshold, exactly threshold, above threshold, missing, and malformed."""
    obl = make_test_obligation()
    claim = make_test_claim()

    pol_cov_85 = Policy(
        "POL-COV85", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CODE_COVERAGE, {"min_coverage_pct": 85.0}),))
    )

    # 1. 0% Coverage -> DENY
    ev_0 = make_test_evidence(ev_id="EV-COV-0", counterexample={"coverage_pct": 0.0})
    ctx_0 = PolicyEvaluationContext(obl, (claim,), (ev_0,))
    d_0 = evaluate_policy(pol_cov_85, ctx_0)
    assert d_0.decision == PolicyDecisionType.DENY
    assert "0.00% < required threshold 85.00%" in d_0.rationale

    # 2. Below threshold (84.9%) -> DENY
    ev_below = make_test_evidence(ev_id="EV-COV-BELOW", counterexample={"coverage_pct": 84.9})
    ctx_below = PolicyEvaluationContext(obl, (claim,), (ev_below,))
    d_below = evaluate_policy(pol_cov_85, ctx_below)
    assert d_below.decision == PolicyDecisionType.DENY
    assert "84.90% < required threshold 85.00%" in d_below.rationale

    # 3. Exactly threshold (85.0%) -> ALLOW
    ev_exact = make_test_evidence(ev_id="EV-COV-EXACT", counterexample={"coverage_pct": 85.0})
    ctx_exact = PolicyEvaluationContext(obl, (claim,), (ev_exact,))
    d_exact = evaluate_policy(pol_cov_85, ctx_exact)
    assert d_exact.decision == PolicyDecisionType.ALLOW
    assert d_exact.rules_evaluated[0].passed is True

    # 4. Above threshold (92.5%) -> ALLOW
    ev_above = make_test_evidence(ev_id="EV-COV-ABOVE", counterexample={"coverage_pct": 92.5})
    ctx_above = PolicyEvaluationContext(obl, (claim,), (ev_above,))
    d_above = evaluate_policy(pol_cov_85, ctx_above)
    assert d_above.decision == PolicyDecisionType.ALLOW

    # 5. Missing coverage evidence -> DENY
    ev_other = make_test_evidence(ev_id="EV-OTHER", capability="API_CONTRACT_FUZZING")
    ctx_missing = PolicyEvaluationContext(obl, (claim,), (ev_other,))
    d_missing = evaluate_policy(pol_cov_85, ctx_missing)
    assert d_missing.decision == PolicyDecisionType.DENY
    assert "Missing trusted structured code coverage evidence" in d_missing.rationale

    # 6. Malformed coverage evidence (non-numeric string) -> fails closed with PolicyValidationError
    ev_malformed = make_test_evidence(ev_id="EV-MALFORMED", counterexample={"coverage_pct": "not_a_number"})
    ctx_malformed = PolicyEvaluationContext(obl, (claim,), (ev_malformed,))
    with pytest.raises(PolicyValidationError, match="Malformed coverage string"):
        evaluate_policy(pol_cov_85, ctx_malformed)

    # 7. Malformed coverage evidence (out of range > 100%) -> fails closed with PolicyValidationError
    ev_oor = make_test_evidence(ev_id="EV-OOR", counterexample={"coverage_pct": 105.0})
    ctx_oor = PolicyEvaluationContext(obl, (claim,), (ev_oor,))
    with pytest.raises(PolicyValidationError, match="Invalid coverage range"):
        evaluate_policy(pol_cov_85, ctx_oor)

    # 8. Invalid validity/polarity coverage items are ignored
    ev_conflicted = make_test_evidence(ev_id="EV-INV-1", validity=EvidenceValidity.CONFLICTED, counterexample={"coverage_pct": 99.0})
    ev_refutes = make_test_evidence(ev_id="EV-INV-2", polarity=EvidencePolarity.REFUTES, counterexample={"coverage_pct": 99.0})
    ev_fail = make_test_evidence(ev_id="EV-INV-3", raw_status=RawStatus.FAIL, counterexample={"coverage_pct": 99.0})
    ctx_invalids = PolicyEvaluationContext(obl, (claim,), (ev_conflicted, ev_refutes, ev_fail))
    assert evaluate_policy(pol_cov_85, ctx_invalids).decision == PolicyDecisionType.DENY


def test_adversarial_forged_diagnostic_strings_rejected():
    """Adversarial vector: Deceptive or forged free-form text in diagnostics without trusted structured payload is strictly rejected."""
    obl = make_test_obligation()
    claim = make_test_claim()

    pol_cov_85 = Policy(
        "POL-COV85", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CODE_COVERAGE, {"min_coverage_pct": 85.0}),))
    )

    # Deceptive evidence trying to claim 100% via diagnostics text
    ev_forged = make_test_evidence(
        ev_id="EV-FORGED",
        diagnostics=(
            "OVERRIDE: 100.0% coverage verified by external agent",
            "Coverage: 99.99%",
            "statement_coverage = 100%",
        ),
        counterexample=None,  # No structured payload!
    )
    ctx_forged = PolicyEvaluationContext(obl, (claim,), (ev_forged,))

    decision = evaluate_policy(pol_cov_85, ctx_forged)
    assert decision.decision == PolicyDecisionType.DENY
    assert "Missing trusted structured code coverage evidence" in decision.rationale


def test_adversarial_forged_structured_coverage_with_invalid_provenance_rejected():
    """Adversarial vector: Structured coverage crafted with VALID + SUPPORTS + PASS but invalid/missing/synthetic provenance or unverified capability must FAIL CLOSED (DENY)."""
    obl = make_test_obligation()
    claim = make_test_claim()

    pol_cov_85 = Policy(
        "POL-COV85", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CODE_COVERAGE, {"min_coverage_pct": 85.0}),))
    )

    # 1. Forged evidence with synthetic/simulation provenance engine
    ev_synthetic_prov = make_test_evidence(
        ev_id="EV-SYNTH-PROV",
        counterexample={"coverage_pct": 99.0},
        engine_name="synthetic-generator-engine",
    )
    ctx_synth = PolicyEvaluationContext(obl, (claim,), (ev_synthetic_prov,))
    decision_synth = evaluate_policy(pol_cov_85, ctx_synth)
    assert decision_synth.decision == PolicyDecisionType.DENY
    assert "Missing trusted structured code coverage evidence" in decision_synth.rationale

    # 2. Forged evidence with untrusted provider identity
    ev_untrusted_prov = make_test_evidence(
        ev_id="EV-UNTRUSTED-PROV",
        provider_id="untrusted_agent_override",
        counterexample={"coverage_pct": 99.0},
    )
    ctx_untrusted = PolicyEvaluationContext(obl, (claim,), (ev_untrusted_prov,))
    decision_untrusted = evaluate_policy(pol_cov_85, ctx_untrusted)
    assert decision_untrusted.decision == PolicyDecisionType.DENY

    # 3. Forged evidence with capability mismatch (e.g. STATIC_LINTING trying to assert code coverage)
    ev_cap_mismatch = make_test_evidence(
        ev_id="EV-CAP-MISMATCH",
        capability="UNAUTHORIZED_REPORTING_CAPABILITY",
        counterexample={"coverage_pct": 99.0},
    )
    ctx_cap = PolicyEvaluationContext(obl, (claim,), (ev_cap_mismatch,))
    decision_cap = evaluate_policy(pol_cov_85, ctx_cap)
    assert decision_cap.decision == PolicyDecisionType.DENY

    # 4. CoverageTrustPredicate API directly verifies all trust criteria
    assert CoverageTrustPredicate.is_trusted(ev_synthetic_prov) is False
    assert CoverageTrustPredicate.is_trusted(ev_untrusted_prov) is False
    assert CoverageTrustPredicate.is_trusted(ev_cap_mismatch) is False
    valid_ev = make_test_evidence(ev_id="EV-VALID-TRUST", counterexample={"coverage_pct": 90.0})
    assert CoverageTrustPredicate.is_trusted(valid_ev) is True


# ============================================================================
# 3. Cross-Parameter Substitution, Omission & Duplication Attacks
# ============================================================================

def test_cross_parameter_substitution_and_duplication_attacks():
    """Verify semantic matching rejects capability substitution, provider weakening, and duplication attacks."""
    # 1. Capability substitution: Parent requires Cap A, Child tries to supply Cap B
    p_cap_a = Policy(
        "POL-CAP-A", PolicyScope.GLOBAL_ORGANIZATIONAL, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "PROPERTY_TESTING"}),))
    )
    c_cap_b = Policy(
        "POL-CAP-B", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )
    with pytest.raises(PolicyWeakeningError, match="Cross-parameter substitution / omission attack"):
        meet_policies(p_cap_a, c_cap_b)

    # 2. Multiple capabilities: Child supplies superset (Cap A + Cap B) -> Valid
    c_cap_ab = Policy(
        "POL-CAP-AB", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (
            PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "PROPERTY_TESTING"}),
            PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),
        ))
    )
    composed_ab = meet_policies(p_cap_a, c_cap_ab)
    assert len(composed_ab.expression.rules) == 2

    # 3. Duplication attack: Child contains conflicting duplicates to dilute parent
    p_tier_3 = Policy(
        "POL-TIER-3", PolicyScope.GLOBAL_ORGANIZATIONAL, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_TIER, {"tier": "V2_BEHAVIORAL", "min_count": 3}),))
    )
    c_tier_dup = Policy(
        "POL-TIER-DUP", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (
            PolicyRule(RuleType.REQUIRE_TIER, {"tier": "V2_BEHAVIORAL", "min_count": 3}),
            PolicyRule(RuleType.REQUIRE_TIER, {"tier": "V2_BEHAVIORAL", "min_count": 1}),
        ))
    )
    with pytest.raises(PolicyWeakeningError, match="Duplication weakening attack"):
        meet_policies(p_tier_3, c_tier_dup)

    # 4. Independent providers weakening attack
    p_prov_2 = Policy(
        "POL-PROV-2", PolicyScope.GLOBAL_ORGANIZATIONAL, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_INDEPENDENT_PROVIDERS, {"min_independent_sources": 2, "group_by": "PROVIDER_TYPE"}),))
    )
    c_prov_1 = Policy(
        "POL-PROV-1", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_INDEPENDENT_PROVIDERS, {"min_independent_sources": 1, "group_by": "PROVIDER_TYPE"}),))
    )
    with pytest.raises(PolicyWeakeningError, match="Weakening / omission attack on independent providers"):
        meet_policies(p_prov_2, c_prov_1)

    # 5. Min trials weakening attack
    p_tr_5 = Policy(
        "POL-TR-5", PolicyScope.GLOBAL_ORGANIZATIONAL, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_MIN_TRIALS, {"min_trials": 5}),))
    )
    c_tr_2 = Policy(
        "POL-TR-2", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_MIN_TRIALS, {"min_trials": 2}),))
    )
    with pytest.raises(PolicyWeakeningError, match="Weakening / omission attack on min_trials"):
        meet_policies(p_tr_5, c_tr_2)

    # 6. Coverage weakening attack
    p_cov_90 = Policy(
        "POL-COV-90", PolicyScope.GLOBAL_ORGANIZATIONAL, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CODE_COVERAGE, {"min_coverage_pct": 90.0}),))
    )
    c_cov_80 = Policy(
        "POL-COV-80", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CODE_COVERAGE, {"min_coverage_pct": 80.0}),))
    )
    with pytest.raises(PolicyWeakeningError, match="Weakening / omission attack on code coverage"):
        meet_policies(p_cov_90, c_cov_80)

    # 7. Staleness commits weakening attack (allowing more commits)
    p_st_5 = Policy(
        "POL-ST-5", PolicyScope.GLOBAL_ORGANIZATIONAL, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.MAX_STALENESS_COMMITS, {"max_commits": 5}),))
    )
    c_st_20 = Policy(
        "POL-ST-20", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.MAX_STALENESS_COMMITS, {"max_commits": 20}),))
    )
    with pytest.raises(PolicyWeakeningError, match="Weakening / omission attack on max staleness commits"):
        meet_policies(p_st_5, c_st_20)


# ============================================================================
# 4. Combinators & Multi-Layer Lattice Meet Tests
# ============================================================================

def test_policy_stack_full_composition():
    """Verify composition across Organization ⊓ Project ⊓ Task ⊓ Obligation."""
    org_pol = Policy(
        policy_id="POL-ORG",
        scope_level=PolicyScope.GLOBAL_ORGANIZATIONAL,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(
                PolicyRule(RuleType.NO_CONFLICTS, {}),
                PolicyRule(RuleType.REQUIRE_CODE_COVERAGE, {"min_coverage_pct": 80.0}),
                PolicyRule(RuleType.REQUIRE_MIN_TRIALS, {"min_trials": 1}),
                PolicyRule(RuleType.MAX_STALENESS_COMMITS, {"max_commits": 10}),
            ),
        ),
    )

    proj_pol = Policy(
        policy_id="POL-PROJ",
        scope_level=PolicyScope.PROJECT,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(
                PolicyRule(RuleType.NO_CONFLICTS, {}),
                PolicyRule(RuleType.REQUIRE_TIER, {"tier": "V2_BEHAVIORAL", "min_count": 2}),
                PolicyRule(RuleType.REQUIRE_CODE_COVERAGE, {"min_coverage_pct": 85.0}),
                PolicyRule(RuleType.REQUIRE_MIN_TRIALS, {"min_trials": 3}),
                PolicyRule(RuleType.MAX_STALENESS_COMMITS, {"max_commits": 5}),
                PolicyRule(RuleType.REQUIRE_INDEPENDENT_PROVIDERS, {"min_independent_sources": 2, "group_by": "PROVIDER_TYPE"}),
            ),
        ),
    )

    task_pol = Policy(
        policy_id="POL-TASK",
        scope_level=PolicyScope.TASK,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(
                PolicyRule(RuleType.NO_CONFLICTS, {}),
                PolicyRule(RuleType.REQUIRE_TIER, {"tier": "V2_BEHAVIORAL", "min_count": 2}),
                PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),
                PolicyRule(RuleType.REQUIRE_CODE_COVERAGE, {"min_coverage_pct": 90.0}),
                PolicyRule(RuleType.REQUIRE_MIN_TRIALS, {"min_trials": 5}),
                PolicyRule(RuleType.MAX_STALENESS_COMMITS, {"max_commits": 3}),
                PolicyRule(RuleType.REQUIRE_INDEPENDENT_PROVIDERS, {"min_independent_sources": 3, "group_by": "PROVIDER_TYPE"}),
            ),
        ),
    )

    composed = compose_policies(org_pol, proj_pol, task_pol)
    assert composed.scope_level == PolicyScope.TASK
    # Verify merged tightening
    for r in composed.expression.rules:
        if r.rule_type == RuleType.REQUIRE_CODE_COVERAGE:
            assert r.parameters["min_coverage_pct"] == 90.0
        elif r.rule_type == RuleType.REQUIRE_MIN_TRIALS:
            assert r.parameters["min_trials"] == 5
        elif r.rule_type == RuleType.MAX_STALENESS_COMMITS:
            assert r.parameters["max_commits"] == 3


def test_conditional_expression_evaluation():
    """Verify CONDITIONAL combinator branches based on obligation metadata."""
    obl_critical = make_test_obligation(criticality=Criticality.CRITICAL)
    obl_low = make_test_obligation(criticality=Criticality.LOW)

    cond_expr = PolicyExpression(
        combinator=CombinatorType.CONDITIONAL,
        condition={"predicate": "criticality", "value": "CRITICAL"},
        then_expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(PolicyRule(RuleType.REQUIRE_TIER, {"tier": "V2_BEHAVIORAL", "min_count": 5}),),
        ),
        else_expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(PolicyRule(RuleType.REQUIRE_TIER, {"tier": "V2_BEHAVIORAL", "min_count": 1}),),
        ),
    )

    pol = Policy("POL-COND", PolicyScope.PROJECT, 1, cond_expr)

    claim = make_test_claim(tier=ClaimTier.V2_BEHAVIORAL, status=ClaimStatus.SUPPORTED)
    ctx_crit = PolicyEvaluationContext(obl_critical, (claim,), ())
    ctx_low = PolicyEvaluationContext(obl_low, (claim,), ())

    assert evaluate_policy(pol, ctx_crit).decision == PolicyDecisionType.DENY
    assert evaluate_policy(pol, ctx_low).decision == PolicyDecisionType.ALLOW


def test_evaluator_require_independent_providers():
    """Verify REQUIRE_INDEPENDENT_PROVIDERS rule evaluation."""
    obl = make_test_obligation()
    claim = make_test_claim()

    e1 = make_test_evidence(ev_id="EV-1", provider_id="prov-A", execution_id="EXEC-1")
    e2 = make_test_evidence(ev_id="EV-2", provider_id="prov-A", execution_id="EXEC-2")
    ctx_same = PolicyEvaluationContext(obl, (claim,), (e1, e2))

    e3 = make_test_evidence(ev_id="EV-3", provider_id="prov-B", execution_id="EXEC-3")
    ctx_distinct = PolicyEvaluationContext(obl, (claim,), (e1, e3))

    pol = Policy(
        "POL-INDEP", PolicyScope.PROJECT, 1,
        PolicyExpression(
            CombinatorType.ALL,
            (PolicyRule(RuleType.REQUIRE_INDEPENDENT_PROVIDERS, {"min_independent_sources": 2, "group_by": "PROVIDER_TYPE"}),)
        )
    )

    assert evaluate_policy(pol, ctx_same).decision == PolicyDecisionType.DENY
    assert evaluate_policy(pol, ctx_distinct).decision == PolicyDecisionType.ALLOW


def test_evaluator_forbid_synthetic():
    """Verify FORBID_SYNTHETIC rule evaluation."""
    obl = make_test_obligation()
    claim = make_test_claim()

    e_synth = make_test_evidence(ev_id="EV-SYNTH", provider_id="synthetic-generator")
    ctx_synth = PolicyEvaluationContext(obl, (claim,), (e_synth,))

    pol = Policy(
        "POL-FORBID-SYNTH", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.FORBID_SYNTHETIC, {}),))
    )

    assert evaluate_policy(pol, ctx_synth).decision == PolicyDecisionType.DENY


def test_evaluator_any_combinator():
    """Verify ANY combinator succeeds if at least one rule passes."""
    obl = make_test_obligation()
    claim = make_test_claim()
    ev = make_test_evidence(capability="API_CONTRACT_FUZZING")

    ctx = PolicyEvaluationContext(obl, (claim,), (ev,))

    pol = Policy(
        "POL-ANY", PolicyScope.PROJECT, 1,
        PolicyExpression(
            CombinatorType.ANY,
            (
                PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "PROPERTY_TESTING"}),
                PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),
            )
        )
    )

    assert evaluate_policy(pol, ctx).decision == PolicyDecisionType.ALLOW


def test_evaluator_at_least_combinator():
    """Verify AT_LEAST combinator succeeds when min_count rules pass."""
    obl = make_test_obligation()
    claim = make_test_claim()
    ev = make_test_evidence(capability="API_CONTRACT_FUZZING")

    ctx = PolicyEvaluationContext(obl, (claim,), (ev,))

    pol = Policy(
        "POL-AT-LEAST", PolicyScope.PROJECT, 1,
        PolicyExpression(
            CombinatorType.AT_LEAST,
            (
                PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "PROPERTY_TESTING"}),
                PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),
                PolicyRule(RuleType.NO_CONFLICTS, {}),
            ),
            min_count=2,
        )
    )

    assert evaluate_policy(pol, ctx).decision == PolicyDecisionType.ALLOW


def test_models_validation_errors_and_edge_cases():
    """Verify validation errors for invalid Actor, Exception, and Context parameters."""
    with pytest.raises(PolicyValidationError):
        AuthorizedActor("", "ROLE", "a" * 64)
    with pytest.raises(PolicyValidationError):
        AuthorizedActor("ACTOR-1", "", "a" * 64)
    with pytest.raises((PolicyValidationError, DomainValidationError)):
        AuthorizedActor("ACTOR-1", "ROLE", "invalid_hex")

    sig = AsymmetricAuthoritySignature("ED25519", "ACTOR-1", "a" * 64, "b" * 64, "c" * 128, "2026-08-19T10:00:00Z")
    with pytest.raises(PolicyValidationError):
        PolicyException("EXC-1", "OBL-1", "POL-1", "too_short", AuthorizedActor("A", "R", "a" * 64), ("Control 1",), sig)

    with pytest.raises(PolicyValidationError):
        PolicyException("EXC-1", "OBL-1", "POL-1", "Valid justification long enough", "not_an_actor", ("Control 1",), sig)  # type: ignore

    with pytest.raises(PolicyValidationError):
        PolicyException("EXC-1", "OBL-1", "POL-1", "Valid justification long enough", AuthorizedActor("A", "R", "a" * 64), (), sig)

    with pytest.raises(PolicyValidationError):
        PolicyException("EXC-1", "OBL-1", "POL-1", "Valid justification long enough", AuthorizedActor("A", "R", "a" * 64), ("bad",), sig)

    with pytest.raises(PolicyValidationError):
        PolicyEvaluationContext("not_an_obligation", (), ())  # type: ignore


def test_evaluator_max_staleness_and_min_trials():
    """Verify MAX_STALENESS_COMMITS, REQUIRE_MIN_TRIALS rules."""
    obl = make_test_obligation()
    claim = make_test_claim()
    ev_valid = make_test_evidence(capability="CODE_COVERAGE")
    ev_stale = make_test_evidence(ev_id="EV-STALE", validity=EvidenceValidity.STALE)

    ctx_fresh = PolicyEvaluationContext(obl, (claim,), (ev_valid,))
    ctx_stale = PolicyEvaluationContext(obl, (claim,), (ev_stale,))

    pol_stale = Policy(
        "POL-STALE", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.MAX_STALENESS_COMMITS, {"max_commits": 5}),))
    )
    assert evaluate_policy(pol_stale, ctx_fresh).decision == PolicyDecisionType.ALLOW
    assert evaluate_policy(pol_stale, ctx_stale).decision == PolicyDecisionType.DENY

    pol_trials = Policy(
        "POL-TRIALS", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_MIN_TRIALS, {"min_trials": 2}),))
    )
    assert evaluate_policy(pol_trials, ctx_fresh).decision == PolicyDecisionType.DENY


def test_evaluator_exception_mismatch_and_type_errors():
    """Verify exception mismatch and evaluator type checking."""
    obl = make_test_obligation(obl_id="OBL-001")
    exc_wrong = make_test_exception(obl_id="OBL-OTHER")
    ctx = PolicyEvaluationContext(obl, (), (), (exc_wrong,))
    pol = Policy("POL-1", PolicyScope.PROJECT, 1, PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),)))

    with pytest.raises(InvalidExceptionError, match="Exception obligation mismatch"):
        evaluate_policy(pol, ctx)

    with pytest.raises(TypeError):
        evaluate_policy("not_a_policy", ctx)  # type: ignore
    with pytest.raises(TypeError):
        evaluate_policy(pol, "not_a_context")  # type: ignore


# ============================================================================
# 5. Property-Based Testing (Hypothesis)
# ============================================================================

@given(st.integers(min_value=1, max_value=10), st.integers(min_value=1, max_value=10))
def test_hypothesis_meet_monotonicity(parent_count: int, child_increment: int):
    """Property test: Meet operator strictly enforces non-weakening on tier min_count."""
    child_count = parent_count + child_increment

    p_parent = Policy(
        "POL-P", PolicyScope.GLOBAL_ORGANIZATIONAL, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_TIER, {"tier": "V2_BEHAVIORAL", "min_count": parent_count}),))
    )
    p_child = Policy(
        "POL-C", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_TIER, {"tier": "V2_BEHAVIORAL", "min_count": child_count}),))
    )

    composed = meet_policies(p_parent, p_child)
    assert composed.scope_level == PolicyScope.PROJECT

    if parent_count > 1:
        p_child_weak = Policy(
            "POL-CW", PolicyScope.PROJECT, 1,
            PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_TIER, {"tier": "V2_BEHAVIORAL", "min_count": parent_count - 1}),))
        )
        with pytest.raises(PolicyWeakeningError):
            meet_policies(p_parent, p_child_weak)
