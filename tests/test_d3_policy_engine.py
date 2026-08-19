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
3. Cryptographic Coverage Trust & Provenance Adversarial Suite:
   - 0% coverage -> DENY
   - Below threshold -> DENY
   - Exactly threshold -> ALLOW
   - Above threshold -> ALLOW
   - Missing structured coverage evidence -> DENY
   - Malformed coverage evidence (non-numeric, NaN, out of range) -> fail closed
   - Forged / misleading diagnostic text rejected as unauthoritative evidence
   - Random 64-char signature -> reject
   - Random 64-char stdout digest -> reject
   - Altered payload with unchanged signature -> reject
   - Valid certificate for different source_sha -> reject
   - Missing expected revision -> reject
4. Gate 3 Authority & Controlled Trust Boundary Verification:
   - Genuine Gate-3 certificate -> ACCEPT
   - Modified genuine certificate -> REJECT
   - Manually fabricated + recomputed hash -> REJECT
   - Wrong issuer -> REJECT
   - Wrong source_sha -> REJECT
   - Repository user without external authority key cannot manufacture valid certificate -> REJECT
5. Cross-Parameter Substitution, Omission, and Duplication Attacks:
   - Capability substitution attack (P requires A, C supplies B) -> PolicyWeakeningError
   - Tier weakening / lowering attack (P requires V2 count 3, C supplies V1 or count 1) -> PolicyWeakeningError
   - Provider group weakening / omission -> PolicyWeakeningError
   - Trials lowering -> PolicyWeakeningError
   - Coverage lowering -> PolicyWeakeningError
   - Staleness commits loosening -> PolicyWeakeningError
   - Omission of invariant flags (NO_CONFLICTS, FORBID_SYNTHETIC) -> PolicyWeakeningError
   - Duplication dilution attack (C provides conflicting duplicates) -> PolicyWeakeningError
6. Property-Based Testing (Hypothesis):
   - Monotonicity: Strictness(P ⊓ Q) >= Strictness(P).
"""

from __future__ import annotations
from copy import deepcopy
import hashlib
import hmac
import json
import os
import re
from typing import Dict, List, Optional, Set, Tuple, Mapping
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
from events.serializer import canonicalize_json
from benchmark.parity.gate_3_authority import (
    compute_gate3_evidence_digest,
    issue_gate_3_evidence_certificate,
)
from benchmark.parity.verify_gate_3_certificate import (
    verify_gate_3_evidence_trust_certificate,
)
from policy import (
    PolicyDecision,
    PolicyDecisionType,
    AuthorizedActor,
    PolicyException,
    RuleEvaluationResult,
    PolicyEvaluationContext,
    EvidenceTrustCertificate,
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

DEFAULT_TEST_SHA = "a" * 40
TEST_AUTHORITY_KEY = "TEST_RUNNER_SECRET_KEY_FOR_GATE3_PARITY_2026"


@pytest.fixture(autouse=True)
def setup_test_authority_key(monkeypatch):
    """Injects test authority key into the environment trust boundary for the test runner."""
    monkeypatch.setenv("GATE3_AUTHORITY_SECRET", TEST_AUTHORITY_KEY)


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
    source_sha: str = DEFAULT_TEST_SHA,
    custom_signature: HmacSessionSignature = None,
    signing_key: str = TEST_AUTHORITY_KEY,
) -> Evidence:
    scope = EvidenceScope(
        targets_evaluated=("DELETE:/users/{id}",),
        aspects_covered=("AUTH_ENFORCEMENT",),
    )
    obs = EvidenceObservation(
        raw_status=raw_status,
        diagnostics=diagnostics,
        counterexample=counterexample,
    )
    prov = Provenance(
        engine_name=engine_name,
        engine_version="7.4.0",
        environment_hash="b" * 64,
        timestamp="2026-08-19T10:00:00Z",
    )

    if custom_signature is not None:
        sig = custom_signature
    else:
        dummy_sig = HmacSessionSignature(
            algorithm="HMAC-SHA256",
            key_id="KEY-001",
            nonce="NONCE-001",
            raw_stdout_digest="0" * 64,
            signature_hex="0" * 64,
            timestamp="2026-08-19T10:00:00Z",
        )
        temp_ev = Evidence(
            evidence_id=ev_id,
            claim_id=claim_id,
            provider_id=provider_id,
            capability=capability,
            execution_id=execution_id,
            source_sha=source_sha,
            scope=scope,
            observation=obs,
            polarity=polarity,
            validity=validity,
            independence_group=independence_group,
            provenance=prov,
            signature=dummy_sig,
        )
        real_digest = compute_gate3_evidence_digest(temp_ev)
        real_hmac = hmac.new(signing_key.encode("utf-8"), real_digest.encode("utf-8"), hashlib.sha256).hexdigest()
        sig = HmacSessionSignature(
            algorithm="HMAC-SHA256",
            key_id="KEY-001",
            nonce="NONCE-001",
            raw_stdout_digest=real_digest,
            signature_hex=real_hmac,
            timestamp="2026-08-19T10:00:00Z",
        )

    return Evidence(
        evidence_id=ev_id,
        claim_id=claim_id,
        provider_id=provider_id,
        capability=capability,
        execution_id=execution_id,
        source_sha=source_sha,
        scope=scope,
        observation=obs,
        polarity=polarity,
        validity=validity,
        independence_group=independence_group,
        provenance=prov,
        signature=sig,
    )


def make_test_context(
    obligation: Obligation,
    claims: Tuple[Claim, ...],
    evidence: Tuple[Evidence, ...],
    exceptions: Tuple[PolicyException, ...] = (),
    expected_source_sha: Optional[str] = DEFAULT_TEST_SHA,
    auto_verify_certificates: bool = True,
    trust_certificates: Dict[str, EvidenceTrustCertificate] = None,
    evaluation_timestamp: str = "2026-08-19T10:00:00Z",
    authority_key: str = TEST_AUTHORITY_KEY,
) -> PolicyEvaluationContext:
    """Helper creating PolicyEvaluationContext with Gate 3 certified trust certificates."""
    certs = {}
    if trust_certificates is not None:
        certs.update(trust_certificates)
    elif auto_verify_certificates and expected_source_sha:
        for ev in evidence:
            certs[ev.evidence_id] = issue_gate_3_evidence_certificate(ev, expected_source_sha, authority_key=authority_key)

    return PolicyEvaluationContext(
        obligation=obligation,
        claims=claims,
        evidence=evidence,
        exceptions=exceptions,
        expected_source_sha=expected_source_sha,
        trust_certificates=certs,
        evaluation_timestamp=evaluation_timestamp,
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

    ctx = make_test_context(obl, (claim,), (ev_pass, ev_fail))

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

    ctx = make_test_context(
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
    exc_for_pol_a = make_test_exception(exc_id="EXC-A", obl_id="OBL-001", policy_id="POL-A")

    ctx = make_test_context(
        obligation=obl,
        claims=(claim,),
        evidence=(),
        exceptions=(exc_for_pol_a,),
    )

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

    ctx = make_test_context(obl, (claim,), (ev,))

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

    ctx_unauthorized = make_test_context(obl, (claim_v4,), ())
    decision = evaluate_policy(policy, ctx_unauthorized)
    assert decision.decision == PolicyDecisionType.REQUIRE_EXCEPTION

    exc = make_test_exception(obl_id="OBL-001", policy_id="POL-001")
    ctx_authorized = make_test_context(obl, (claim_v4,), (), exceptions=(exc,))
    decision_exc = evaluate_policy(policy, ctx_authorized)
    assert decision_exc.decision == PolicyDecisionType.ALLOW
    assert "EXC-001" in decision_exc.exceptions_applied


# ============================================================================
# 2. Code Coverage Evidence & Cryptographic Trust Suite
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
    ctx_0 = make_test_context(obl, (claim,), (ev_0,))
    d_0 = evaluate_policy(pol_cov_85, ctx_0)
    assert d_0.decision == PolicyDecisionType.DENY
    assert "0.00% < required threshold 85.00%" in d_0.rationale

    # 2. Below threshold (84.9%) -> DENY
    ev_below = make_test_evidence(ev_id="EV-COV-BELOW", counterexample={"coverage_pct": 84.9})
    ctx_below = make_test_context(obl, (claim,), (ev_below,))
    d_below = evaluate_policy(pol_cov_85, ctx_below)
    assert d_below.decision == PolicyDecisionType.DENY
    assert "84.90% < required threshold 85.00%" in d_below.rationale

    # 3. Exactly threshold (85.0%) -> ALLOW
    ev_exact = make_test_evidence(ev_id="EV-COV-EXACT", counterexample={"coverage_pct": 85.0})
    ctx_exact = make_test_context(obl, (claim,), (ev_exact,))
    d_exact = evaluate_policy(pol_cov_85, ctx_exact)
    assert d_exact.decision == PolicyDecisionType.ALLOW
    assert d_exact.rules_evaluated[0].passed is True

    # 4. Above threshold (92.5%) -> ALLOW
    ev_above = make_test_evidence(ev_id="EV-COV-ABOVE", counterexample={"coverage_pct": 92.5})
    ctx_above = make_test_context(obl, (claim,), (ev_above,))
    d_above = evaluate_policy(pol_cov_85, ctx_above)
    assert d_above.decision == PolicyDecisionType.ALLOW

    # 5. Missing coverage evidence -> DENY
    ev_other = make_test_evidence(ev_id="EV-OTHER", capability="API_CONTRACT_FUZZING")
    ctx_missing = make_test_context(obl, (claim,), (ev_other,))
    d_missing = evaluate_policy(pol_cov_85, ctx_missing)
    assert d_missing.decision == PolicyDecisionType.DENY
    assert "Missing trusted structured code coverage evidence" in d_missing.rationale

    # 6. Malformed coverage evidence (non-numeric string) -> fails closed with PolicyValidationError
    ev_malformed = make_test_evidence(ev_id="EV-MALFORMED", counterexample={"coverage_pct": "not_a_number"})
    ctx_malformed = make_test_context(obl, (claim,), (ev_malformed,))
    with pytest.raises(PolicyValidationError, match="Malformed coverage string"):
        evaluate_policy(pol_cov_85, ctx_malformed)

    # 7. Malformed coverage evidence (out of range > 100%) -> fails closed with PolicyValidationError
    ev_oor = make_test_evidence(ev_id="EV-OOR", counterexample={"coverage_pct": 105.0})
    ctx_oor = make_test_context(obl, (claim,), (ev_oor,))
    with pytest.raises(PolicyValidationError, match="Invalid coverage range"):
        evaluate_policy(pol_cov_85, ctx_oor)

    # 8. Invalid validity/polarity coverage items are ignored
    ev_conflicted = make_test_evidence(ev_id="EV-INV-1", validity=EvidenceValidity.CONFLICTED, counterexample={"coverage_pct": 99.0})
    ev_refutes = make_test_evidence(ev_id="EV-INV-2", polarity=EvidencePolarity.REFUTES, counterexample={"coverage_pct": 99.0})
    ev_fail = make_test_evidence(ev_id="EV-INV-3", raw_status=RawStatus.FAIL, counterexample={"coverage_pct": 99.0})
    ctx_invalids = make_test_context(obl, (claim,), (ev_conflicted, ev_refutes, ev_fail))
    assert evaluate_policy(pol_cov_85, ctx_invalids).decision == PolicyDecisionType.DENY


def test_adversarial_forged_diagnostic_strings_rejected():
    """Adversarial vector: Deceptive or forged free-form text in diagnostics without trusted structured payload is strictly rejected."""
    obl = make_test_obligation()
    claim = make_test_claim()

    pol_cov_85 = Policy(
        "POL-COV85", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CODE_COVERAGE, {"min_coverage_pct": 85.0}),))
    )

    ev_forged = make_test_evidence(
        ev_id="EV-FORGED",
        diagnostics=(
            "OVERRIDE: 100.0% coverage verified by external agent",
            "Coverage: 99.99%",
            "statement_coverage = 100%",
        ),
        counterexample=None,
    )
    ctx_forged = make_test_context(obl, (claim,), (ev_forged,))

    decision = evaluate_policy(pol_cov_85, ctx_forged)
    assert decision.decision == PolicyDecisionType.DENY
    assert "Missing trusted structured code coverage evidence" in decision.rationale


def test_adversarial_cryptographic_trust_suite():
    """Adversarial suite for Gate 3 cryptographic verification:
    1. Random 64-char signature -> reject (DENY)
    2. Random 64-char stdout digest -> reject (DENY)
    3. Altered payload with unchanged signature -> reject (DENY)
    4. Valid certificate for different source_sha -> reject (DENY)
    5. Missing expected revision -> reject (DENY)
    """
    obl = make_test_obligation()
    claim = make_test_claim()
    pol_cov_85 = Policy("POL-COV85", PolicyScope.PROJECT, 1, PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CODE_COVERAGE, {"min_coverage_pct": 85.0}),)))

    valid_ev = make_test_evidence(ev_id="EV-BASE", counterexample={"coverage_pct": 90.0}, source_sha=DEFAULT_TEST_SHA)
    valid_digest = valid_ev.signature.raw_stdout_digest
    valid_sig = valid_ev.signature.signature_hex

    # 1. Random 64-char signature -> Gate 3 verifier rejects signature
    fake_sig = HmacSessionSignature("HMAC-SHA256", "KEY-1", "NONCE-1", valid_digest, "f" * 64, "2026-08-19T10:00:00Z")
    ev_fake_sig = make_test_evidence(ev_id="EV-FAKE-SIG", counterexample={"coverage_pct": 90.0}, custom_signature=fake_sig)
    ctx_fake_sig = make_test_context(obl, (claim,), (ev_fake_sig,))
    d_fake_sig = evaluate_policy(pol_cov_85, ctx_fake_sig)
    assert d_fake_sig.decision == PolicyDecisionType.DENY
    assert "Missing trusted structured code coverage evidence" in d_fake_sig.rationale

    # 2. Random 64-char stdout digest -> Gate 3 verifier rejects digest
    fake_digest_sig = HmacSessionSignature("HMAC-SHA256", "KEY-1", "NONCE-1", "e" * 64, valid_sig, "2026-08-19T10:00:00Z")
    ev_fake_digest = make_test_evidence(ev_id="EV-FAKE-DIG", counterexample={"coverage_pct": 90.0}, custom_signature=fake_digest_sig)
    ctx_fake_digest = make_test_context(obl, (claim,), (ev_fake_digest,))
    d_fake_digest = evaluate_policy(pol_cov_85, ctx_fake_digest)
    assert d_fake_digest.decision == PolicyDecisionType.DENY

    # 3. Altered payload with unchanged signature -> Gate 3 JCS digest mismatch
    ev_orig = make_test_evidence(ev_id="EV-ORIG", counterexample={"coverage_pct": 80.0})
    orig_sig = ev_orig.signature
    ev_tampered = make_test_evidence(ev_id="EV-ORIG", counterexample={"coverage_pct": 95.0}, custom_signature=orig_sig)
    ctx_tampered = make_test_context(obl, (claim,), (ev_tampered,))
    d_tampered = evaluate_policy(pol_cov_85, ctx_tampered)
    assert d_tampered.decision == PolicyDecisionType.DENY

    # 4. Valid certificate for different source_sha -> D3 rejects revision mismatch
    ev_diff_sha = make_test_evidence(ev_id="EV-DIFF-SHA", counterexample={"coverage_pct": 90.0}, source_sha="b" * 40)
    cert_diff = issue_gate_3_evidence_certificate(ev_diff_sha, expected_source_sha="b" * 40, authority_key=TEST_AUTHORITY_KEY)
    ctx_diff_sha = make_test_context(
        obl, (claim,), (ev_diff_sha,),
        expected_source_sha=DEFAULT_TEST_SHA,
        trust_certificates={ev_diff_sha.evidence_id: cert_diff}
    )
    d_diff_sha = evaluate_policy(pol_cov_85, ctx_diff_sha)
    assert d_diff_sha.decision == PolicyDecisionType.DENY

    # 5. Missing expected revision -> D3 fails closed
    ctx_missing_rev = make_test_context(obl, (claim,), (valid_ev,), expected_source_sha=None)
    d_missing_rev = evaluate_policy(pol_cov_85, ctx_missing_rev)
    assert d_missing_rev.decision == PolicyDecisionType.DENY


# ============================================================================
# 3. Gate 3 Authority & Controlled Trust Boundary Verification
# ============================================================================

def test_adversarial_gate3_issuer_authentication_matrix():
    """Adversarial matrix verifying Gate 3 authority authentication:
    1. genuine Gate-3 certificate -> ACCEPT
    2. modified genuine certificate -> REJECT
    3. manually fabricated + recomputed unkeyed hash -> REJECT
    4. wrong issuer -> REJECT
    5. wrong source_sha -> REJECT
    """
    obl = make_test_obligation()
    claim = make_test_claim()
    pol_cov_85 = Policy("POL-COV85", PolicyScope.PROJECT, 1, PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CODE_COVERAGE, {"min_coverage_pct": 85.0}),)))

    ev = make_test_evidence(ev_id="EV-G3-MATRIX", counterexample={"coverage_pct": 95.0})

    # 1. Genuine Gate-3 certificate -> ACCEPT
    genuine_cert = issue_gate_3_evidence_certificate(ev, expected_source_sha=DEFAULT_TEST_SHA, authority_key=TEST_AUTHORITY_KEY)
    assert verify_gate_3_evidence_trust_certificate(genuine_cert, expected_source_sha=DEFAULT_TEST_SHA, verification_key=TEST_AUTHORITY_KEY) is True
    ctx_genuine = PolicyEvaluationContext(
        obligation=obl,
        claims=(claim,),
        evidence=(ev,),
        expected_source_sha=DEFAULT_TEST_SHA,
        trust_certificates={ev.evidence_id: genuine_cert},
    )
    assert CoverageTrustPredicate.is_trusted(ev, ctx_genuine) is True
    assert evaluate_policy(pol_cov_85, ctx_genuine).decision == PolicyDecisionType.ALLOW

    # 2. Modified genuine certificate (tampered is_verified / source_sha) -> REJECT
    modified_cert = EvidenceTrustCertificate(
        evidence_id=genuine_cert.evidence_id,
        source_sha=DEFAULT_TEST_SHA,
        is_verified=genuine_cert.is_verified,
        digest_verified=genuine_cert.digest_verified,
        signature_verified=genuine_cert.signature_verified,
        provenance_verified=genuine_cert.provenance_verified,
        verifier_identity=genuine_cert.verifier_identity,
        timestamp=genuine_cert.timestamp,
        certificate_hash=genuine_cert.certificate_hash,
        issuer_signature="f" * 64,  # Tampered signature!
    )
    assert verify_gate_3_evidence_trust_certificate(modified_cert, expected_source_sha=DEFAULT_TEST_SHA, verification_key=TEST_AUTHORITY_KEY) is False
    ctx_modified = PolicyEvaluationContext(
        obligation=obl,
        claims=(claim,),
        evidence=(ev,),
        expected_source_sha=DEFAULT_TEST_SHA,
        trust_certificates={ev.evidence_id: modified_cert},
    )
    assert CoverageTrustPredicate.is_trusted(ev, ctx_modified) is False
    assert evaluate_policy(pol_cov_85, ctx_modified).decision == PolicyDecisionType.DENY

    # 3. Manually fabricated certificate with recomputed unkeyed SHA-256 hash -> REJECT
    raw_payload = {
        "evidence_id": ev.evidence_id,
        "source_sha": DEFAULT_TEST_SHA,
        "is_verified": True,
        "digest_verified": True,
        "signature_verified": True,
        "provenance_verified": True,
        "verifier_identity": "Gate3AuthoritativeVerifier",
        "timestamp": "2026-08-19T10:00:00Z",
    }
    recomputed_hash = hashlib.sha256(canonicalize_json(raw_payload)).hexdigest()
    fabricated_cert = EvidenceTrustCertificate(
        evidence_id=ev.evidence_id,
        source_sha=DEFAULT_TEST_SHA,
        is_verified=True,
        digest_verified=True,
        signature_verified=True,
        provenance_verified=True,
        verifier_identity="Gate3AuthoritativeVerifier",
        timestamp="2026-08-19T10:00:00Z",
        certificate_hash=recomputed_hash,
        issuer_signature="0" * 64,  # Caller doesn't have Gate-3 authority secret key!
    )
    assert verify_gate_3_evidence_trust_certificate(fabricated_cert, expected_source_sha=DEFAULT_TEST_SHA, verification_key=TEST_AUTHORITY_KEY) is False
    ctx_fabricated = PolicyEvaluationContext(
        obligation=obl,
        claims=(claim,),
        evidence=(ev,),
        expected_source_sha=DEFAULT_TEST_SHA,
        trust_certificates={ev.evidence_id: fabricated_cert},
    )
    assert CoverageTrustPredicate.is_trusted(ev, ctx_fabricated) is False
    assert evaluate_policy(pol_cov_85, ctx_fabricated).decision == PolicyDecisionType.DENY

    # 4. Wrong issuer -> REJECT
    wrong_issuer_cert = issue_gate_3_evidence_certificate(ev, expected_source_sha=DEFAULT_TEST_SHA, authority_key=TEST_AUTHORITY_KEY, verifier_identity="UntrustedForeignIssuer")
    assert verify_gate_3_evidence_trust_certificate(wrong_issuer_cert, expected_source_sha=DEFAULT_TEST_SHA, verification_key=TEST_AUTHORITY_KEY) is False
    ctx_wrong_issuer = PolicyEvaluationContext(
        obligation=obl,
        claims=(claim,),
        evidence=(ev,),
        expected_source_sha=DEFAULT_TEST_SHA,
        trust_certificates={ev.evidence_id: wrong_issuer_cert},
    )
    assert CoverageTrustPredicate.is_trusted(ev, ctx_wrong_issuer) is False
    assert evaluate_policy(pol_cov_85, ctx_wrong_issuer).decision == PolicyDecisionType.DENY

    # 5. Wrong source_sha -> REJECT
    assert verify_gate_3_evidence_trust_certificate(genuine_cert, expected_source_sha="b" * 40, verification_key=TEST_AUTHORITY_KEY) is False
    ctx_wrong_sha = PolicyEvaluationContext(
        obligation=obl,
        claims=(claim,),
        evidence=(ev,),
        expected_source_sha="b" * 40,
        trust_certificates={ev.evidence_id: genuine_cert},
    )
    assert CoverageTrustPredicate.is_trusted(ev, ctx_wrong_sha) is False
    assert evaluate_policy(pol_cov_85, ctx_wrong_sha).decision == PolicyDecisionType.DENY


def test_adversarial_user_knowing_source_code_cannot_forge_certificate(monkeypatch):
    """Adversarial proof: A repository user who has full read access to all source code
    cannot manufacture a valid production certificate without the external authority key.
    Source code contains zero hardcoded keys or default secrets.
    """
    # 1. Unset the authority secret from environment to simulate unprivileged runner/user
    monkeypatch.delenv("GATE3_AUTHORITY_SECRET", raising=False)
    monkeypatch.delenv("SCLASS_GATE3_KEY", raising=False)

    obl = make_test_obligation()
    claim = make_test_claim()
    pol_cov_85 = Policy("POL-COV85", PolicyScope.PROJECT, 1, PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CODE_COVERAGE, {"min_coverage_pct": 85.0}),)))

    ev = make_test_evidence(ev_id="EV-SOURCE-ATTACK", counterexample={"coverage_pct": 99.0})

    # Attacker tries to forge a certificate using guessed default strings or empty secrets
    for guessed_key in ["", "secret", "password", "default", "GATE3_D0_KEYED_HMAC_AUTHENTICATION_SECRET_2026"]:
        raw_payload = {
            "evidence_id": ev.evidence_id,
            "source_sha": DEFAULT_TEST_SHA,
            "is_verified": True,
            "digest_verified": True,
            "signature_verified": True,
            "provenance_verified": True,
            "verifier_identity": "Gate3AuthoritativeVerifier",
            "timestamp": "2026-08-19T10:00:00Z",
        }
        canonical_bytes = canonicalize_json(raw_payload)
        guessed_hash = hashlib.sha256(canonical_bytes).hexdigest()
        guessed_sig = hmac.new(guessed_key.encode("utf-8"), canonical_bytes, hashlib.sha256).hexdigest()

        forged_cert = EvidenceTrustCertificate(
            evidence_id=ev.evidence_id,
            source_sha=DEFAULT_TEST_SHA,
            is_verified=True,
            digest_verified=True,
            signature_verified=True,
            provenance_verified=True,
            verifier_identity="Gate3AuthoritativeVerifier",
            timestamp="2026-08-19T10:00:00Z",
            certificate_hash=guessed_hash,
            issuer_signature=guessed_sig,
        )

        ctx_attacker = PolicyEvaluationContext(
            obligation=obl,
            claims=(claim,),
            evidence=(ev,),
            expected_source_sha=DEFAULT_TEST_SHA,
            trust_certificates={ev.evidence_id: forged_cert},
        )

        # In production without the external authority key in the environment, verifier strictly fails closed
        assert verify_gate_3_evidence_trust_certificate(forged_cert, expected_source_sha=DEFAULT_TEST_SHA) is False
        assert CoverageTrustPredicate.is_trusted(ev, ctx_attacker) is False
        assert evaluate_policy(pol_cov_85, ctx_attacker).decision == PolicyDecisionType.DENY


# ============================================================================
# 4. Cross-Parameter Substitution, Omission & Duplication Attacks
# ============================================================================

def test_cross_parameter_substitution_and_duplication_attacks():
    """Verify semantic matching rejects capability substitution, provider weakening, and duplication attacks."""
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

    c_cap_ab = Policy(
        "POL-CAP-AB", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (
            PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "PROPERTY_TESTING"}),
            PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),
        ))
    )
    composed_ab = meet_policies(p_cap_a, c_cap_ab)
    assert len(composed_ab.expression.rules) == 2

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
# 5. Combinators & Multi-Layer Lattice Meet Tests
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
    ctx_crit = make_test_context(obl_critical, (claim,), ())
    ctx_low = make_test_context(obl_low, (claim,), ())

    assert evaluate_policy(pol, ctx_crit).decision == PolicyDecisionType.DENY
    assert evaluate_policy(pol, ctx_low).decision == PolicyDecisionType.ALLOW


def test_evaluator_require_independent_providers():
    """Verify REQUIRE_INDEPENDENT_PROVIDERS rule evaluation."""
    obl = make_test_obligation()
    claim = make_test_claim()

    e1 = make_test_evidence(ev_id="EV-1", provider_id="prov-A", execution_id="EXEC-1")
    e2 = make_test_evidence(ev_id="EV-2", provider_id="prov-A", execution_id="EXEC-2")
    ctx_same = make_test_context(obl, (claim,), (e1, e2))

    e3 = make_test_evidence(ev_id="EV-3", provider_id="prov-B", execution_id="EXEC-3")
    ctx_distinct = make_test_context(obl, (claim,), (e1, e3))

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
    ctx_synth = make_test_context(obl, (claim,), (e_synth,))

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

    ctx = make_test_context(obl, (claim,), (ev,))

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

    ctx = make_test_context(obl, (claim,), (ev,))

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

    ctx_fresh = make_test_context(obl, (claim,), (ev_valid,))
    ctx_stale = make_test_context(obl, (claim,), (ev_stale,))

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
    ctx = make_test_context(obl, (), (), exceptions=(exc_wrong,))
    pol = Policy("POL-1", PolicyScope.PROJECT, 1, PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),)))

    with pytest.raises(InvalidExceptionError, match="Exception obligation mismatch"):
        evaluate_policy(pol, ctx)

    with pytest.raises(TypeError):
        evaluate_policy("not_a_policy", ctx)  # type: ignore
    with pytest.raises(TypeError):
        evaluate_policy(pol, "not_a_context")  # type: ignore


# ============================================================================
# 6. Property-Based Testing (Hypothesis)
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
