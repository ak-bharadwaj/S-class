

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
4. Gate 3 Asymmetric Authority & Key Boundary Verification:
   - arbitrary caller cannot choose issuer key -> TypeError / protected keystore
   - wrong key object -> TypeError
   - malformed signature -> reject (returns False)
   - invalid signature -> reject (returns False via InvalidSignature)
   - genuine authority signature -> ACCEPT
   - certificate signed by wrong key -> REJECT
   - modified certificate -> REJECT
   - timestamp/provenance mutation -> REJECT
   - wrong issuer -> REJECT
   - wrong source_sha -> REJECT
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
import json
import os
import uuid
import re
from typing import Dict, List, Optional, Set, Tuple, Mapping
from hypothesis import given, strategies as st, settings
import jsonschema
from jsonschema import Draft202012Validator
import pytest
import yaml
from cryptography.hazmat.primitives.asymmetric import ed25519

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
    Gate3AuthorityKeyStore,
    Gate3ProviderKeyStore,
    Gate3NonceTracker,
    compute_gate3_evidence_digest,
    sign_provider_evidence,
    verify_provider_evidence_signature,
    issue_gate_3_evidence_certificate,
)
from benchmark.parity.verify_gate_3_certificate import (
    Gate3PublicKeystore,
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
    PolicyActorKeyRegistry,
    ActorKeyRecord,
    canonicalize_policy_exception_preimage,
    meet_policies,
    compose_policies,
    verify_and_merge_rules,
    verify_non_weakening_rule,
    evaluate_rule,
    evaluate_expression,
    evaluate_policy,
)

DEFAULT_TEST_SHA = "a" * 40

# Test Authority Ed25519 Key Pair & Provider Key
TEST_AUTHORITY_PRIVATE_KEY = ed25519.Ed25519PrivateKey.generate()
TEST_AUTHORITY_PUBLIC_KEY = TEST_AUTHORITY_PRIVATE_KEY.public_key()
TEST_PROVIDER_SECRET = b"TEST_GATE3_PROVIDER_KEYSTORE_SECRET_32B"


@pytest.fixture(autouse=True)
def setup_test_authority_keystore():
    """Initializes the protected authority keystore, verifier public keystore, and actor keystore for tests."""
    Gate3AuthorityKeyStore.clear()
    Gate3AuthorityKeyStore.set_private_key(TEST_AUTHORITY_PRIVATE_KEY)
    Gate3PublicKeystore.clear()
    Gate3PublicKeystore.set_public_key(TEST_AUTHORITY_PUBLIC_KEY)
    Gate3ProviderKeyStore.clear()
    Gate3ProviderKeyStore.register_provider_key("KEY-001", TEST_PROVIDER_SECRET)
    Gate3NonceTracker.clear()
    PolicyActorKeyRegistry.clear()

    yield
    Gate3AuthorityKeyStore.clear()
    Gate3PublicKeystore.clear()
    Gate3ProviderKeyStore.clear()
    Gate3NonceTracker.clear()
    PolicyActorKeyRegistry.clear()


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
    timestamp: str = "2026-08-19T10:00:00Z",
    key_id: str = "KEY-001",
    nonce: Optional[str] = None,
    custom_signature: HmacSessionSignature = None,
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
        timestamp=timestamp,
    )

    if custom_signature is not None:
        sig = custom_signature
    else:
        sig = sign_provider_evidence(
            evidence_id=ev_id,
            claim_id=claim_id,
            provider_id=provider_id,
            capability=capability,
            execution_id=execution_id,
            source_sha=source_sha,
            scope=scope,
            observation=obs,
            provenance=prov,
            key_id=key_id,
            nonce=nonce,
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
) -> PolicyEvaluationContext:
    """Helper creating PolicyEvaluationContext with Gate 3 certified trust certificates."""
    certs = {}
    if trust_certificates is not None:
        certs.update(trust_certificates)
    elif auto_verify_certificates and expected_source_sha:
        for ev in evidence:
            certs[ev.evidence_id] = issue_gate_3_evidence_certificate(ev, expected_source_sha)

    return PolicyEvaluationContext(
        obligation=obligation,
        claims=claims,
        evidence=evidence,
        exceptions=exceptions,
        expected_source_sha=expected_source_sha,
        trust_certificates=certs,
        evaluation_timestamp=evaluation_timestamp,
    )


def _sign_test_exception(
    exception_id: str,
    obligation_id: str,
    policy_id: str,
    justification: str,
    actor_id: str,
    actor_role: str,
    private_key: Any,
    compensating_controls: Tuple[str, ...],
    expiry: Optional[str] = None,
    signer_identity: Optional[str] = None,
    timestamp: str = "2026-08-19T10:00:00Z",
    auto_enroll: bool = True,
) -> PolicyException:
    """Test-only helper to generate cryptographically valid PolicyException instances."""
    pub_key = private_key.public_key()
    pub_fp = hashlib.sha256(pub_key.public_bytes_raw()).hexdigest()

    if auto_enroll and not PolicyActorKeyRegistry.is_revoked(pub_fp):
        if PolicyActorKeyRegistry.lookup_actor(pub_fp) is None:
            PolicyActorKeyRegistry.enroll_actor(actor_id, actor_role, pub_key)

    actor = AuthorizedActor(
        actor_id=actor_id,
        actor_role=actor_role,
        public_key_fingerprint=pub_fp,
    )
    dummy_sig = AsymmetricAuthoritySignature(
        algorithm="ED25519",
        signer_identity=signer_identity or actor_id,
        public_key_fingerprint=pub_fp,
        payload_digest="0" * 64,
        signature_hex="0" * 128,
        timestamp=timestamp,
    )
    raw_exc = PolicyException(
        exception_id=exception_id,
        obligation_id=obligation_id,
        policy_id=policy_id,
        justification=justification,
        authorized_by=actor,
        compensating_controls=compensating_controls,
        signature=dummy_sig,
        expiry=expiry,
    )
    canonical_bytes = canonicalize_policy_exception_preimage(raw_exc)
    payload_digest = hashlib.sha256(canonical_bytes).hexdigest()
    sig_bytes = private_key.sign(canonical_bytes)

    real_sig = AsymmetricAuthoritySignature(
        algorithm="ED25519",
        signer_identity=signer_identity or actor_id,
        public_key_fingerprint=pub_fp,
        payload_digest=payload_digest,
        signature_hex=sig_bytes.hex(),
        timestamp=timestamp,
    )
    return PolicyException(
        exception_id=exception_id,
        obligation_id=obligation_id,
        policy_id=policy_id,
        justification=justification,
        authorized_by=actor,
        compensating_controls=compensating_controls,
        signature=real_sig,
        expiry=expiry,
    )


def make_test_exception(
    exc_id: str = "EXC-001",
    obl_id: str = "OBL-001",
    policy_id: str = "POL-001",
    expiry: str = "2026-12-31T23:59:59Z",
    private_key: Optional[Any] = None,
    actor_id: str = "SEC-OFFICER-01",
    actor_role: str = "SECURITY_LEAD",
) -> PolicyException:
    priv = private_key or TEST_AUTHORITY_PRIVATE_KEY
    return _sign_test_exception(
        exception_id=exc_id,
        obligation_id=obl_id,
        policy_id=policy_id,
        justification="Manual security review approved by security lead with HSM token.",
        actor_id=actor_id,
        actor_role=actor_role,
        private_key=priv,
        compensating_controls=("Audit log monitoring enabled", "WAF rate limit enabled"),
        expiry=expiry,
        signer_identity=actor_id,
        timestamp="2026-08-19T10:00:00Z",
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
    cert_diff = issue_gate_3_evidence_certificate(ev_diff_sha, expected_source_sha="b" * 40)
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
# 3. Gate 3 Asymmetric Authority & Key Boundary Verification
# ============================================================================

def test_adversarial_caller_cannot_choose_issuer_key():
    """Adversarial check: Caller cannot pass an arbitrary authority_key parameter to issue_gate_3_evidence_certificate."""
    ev = make_test_evidence(ev_id="EV-KEY-PARAM", counterexample={"coverage_pct": 95.0})
    with pytest.raises(TypeError):
        issue_gate_3_evidence_certificate(ev, expected_source_sha=DEFAULT_TEST_SHA, authority_key="UNAUTHORIZED_KEY")  # type: ignore


def test_adversarial_wrong_key_object_type_errors():
    """Adversarial check: Keystores strictly reject non-Ed25519 key types with TypeError."""
    with pytest.raises(TypeError, match="Expected Ed25519PublicKey"):
        Gate3PublicKeystore.set_public_key("invalid_string_key")  # type: ignore

    with pytest.raises(TypeError, match="Expected Ed25519PublicKey"):
        Gate3PublicKeystore.set_public_key(12345)  # type: ignore

    with pytest.raises(TypeError, match="Expected Ed25519PrivateKey"):
        Gate3AuthorityKeyStore.set_private_key("invalid_private_key")  # type: ignore

    ev = make_test_evidence(ev_id="EV-KEY-OBJ", counterexample={"coverage_pct": 95.0})
    cert = issue_gate_3_evidence_certificate(ev, expected_source_sha=DEFAULT_TEST_SHA)

    with pytest.raises(TypeError, match="Expected Ed25519PublicKey"):
        verify_gate_3_evidence_trust_certificate(cert, expected_source_sha=DEFAULT_TEST_SHA, public_key="invalid_key_obj")  # type: ignore


def test_adversarial_malformed_and_invalid_ed25519_signatures():
    """Adversarial check: Verifier handles malformed and invalid Ed25519 signatures without swallowing arbitrary exceptions."""
    obl = make_test_obligation()
    claim = make_test_claim()
    ev = make_test_evidence(ev_id="EV-SIG-ERRS", counterexample={"coverage_pct": 95.0})
    genuine_cert = issue_gate_3_evidence_certificate(ev, expected_source_sha=DEFAULT_TEST_SHA)

    # 1. Non-hex characters in signature construction fails schema validation
    with pytest.raises(DomainValidationError):
        AsymmetricAuthoritySignature(
            algorithm="ED25519",
            signer_identity=genuine_cert.authority_signature.signer_identity,
            public_key_fingerprint=genuine_cert.authority_signature.public_key_fingerprint,
            payload_digest=genuine_cert.authority_signature.payload_digest,
            signature_hex="zz" * 64,  # Non-hex characters
            timestamp=genuine_cert.authority_signature.timestamp,
        )

    # 2. Invalid cryptographic signature (valid 128-hex chars, but wrong signature bytes) -> returns False via InvalidSignature
    invalid_crypto_sig = AsymmetricAuthoritySignature(
        algorithm="ED25519",
        signer_identity=genuine_cert.authority_signature.signer_identity,
        public_key_fingerprint=genuine_cert.authority_signature.public_key_fingerprint,
        payload_digest=genuine_cert.authority_signature.payload_digest,
        signature_hex="aa" * 64,  # Cryptographically invalid signature (128 hex chars)
        timestamp=genuine_cert.authority_signature.timestamp,
    )
    invalid_sig_cert = EvidenceTrustCertificate(
        evidence_id=genuine_cert.evidence_id,
        source_sha=DEFAULT_TEST_SHA,
        is_verified=True,
        digest_verified=True,
        signature_verified=True,
        provenance_verified=True,
        verifier_identity=genuine_cert.verifier_identity,
        timestamp=genuine_cert.timestamp,
        certificate_hash=genuine_cert.certificate_hash,
        authority_signature=invalid_crypto_sig,
    )
    assert verify_gate_3_evidence_trust_certificate(invalid_sig_cert, expected_source_sha=DEFAULT_TEST_SHA, public_key=TEST_AUTHORITY_PUBLIC_KEY) is False


def test_adversarial_gate3_asymmetric_authority_matrix():
    """Adversarial matrix verifying Gate 3 Asymmetric Authority (Ed25519) verification:
    1. genuine authority signature -> ACCEPT
    2. certificate signed by wrong key -> REJECT
    3. modified certificate -> REJECT
    4. timestamp/provenance mutation -> REJECT
    5. wrong issuer -> REJECT
    6. wrong source_sha -> REJECT
    """
    obl = make_test_obligation()
    claim = make_test_claim()
    pol_cov_85 = Policy("POL-COV85", PolicyScope.PROJECT, 1, PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CODE_COVERAGE, {"min_coverage_pct": 85.0}),)))

    ev = make_test_evidence(ev_id="EV-G3-ASYMM", counterexample={"coverage_pct": 95.0}, timestamp="2026-08-19T14:30:00Z")

    # 1. Genuine authority signature -> ACCEPT
    genuine_cert = issue_gate_3_evidence_certificate(ev, expected_source_sha=DEFAULT_TEST_SHA)
    assert verify_gate_3_evidence_trust_certificate(genuine_cert, expected_source_sha=DEFAULT_TEST_SHA, public_key=TEST_AUTHORITY_PUBLIC_KEY) is True
    assert genuine_cert.timestamp == "2026-08-19T14:30:00Z"  # Exact execution timestamp binding
    ctx_genuine = PolicyEvaluationContext(
        obligation=obl,
        claims=(claim,),
        evidence=(ev,),
        expected_source_sha=DEFAULT_TEST_SHA,
        trust_certificates={ev.evidence_id: genuine_cert},
    )
    assert CoverageTrustPredicate.is_trusted(ev, ctx_genuine) is True
    assert evaluate_policy(pol_cov_85, ctx_genuine).decision == PolicyDecisionType.ALLOW

    # 2. Certificate signed by wrong key -> REJECT
    rogue_private_key = ed25519.Ed25519PrivateKey.generate()
    rogue_pub = rogue_private_key.public_key()
    rogue_fp = hashlib.sha256(rogue_pub.public_bytes_raw()).hexdigest()
    raw_payload = {
        "evidence_id": ev.evidence_id,
        "source_sha": DEFAULT_TEST_SHA,
        "is_verified": True,
        "digest_verified": True,
        "signature_verified": True,
        "provenance_verified": True,
        "verifier_identity": "Gate3AuthoritativeVerifier",
        "timestamp": "2026-08-19T14:30:00Z",
    }
    canonical_bytes = canonicalize_json(raw_payload)
    rogue_digest = hashlib.sha256(canonical_bytes).hexdigest()
    rogue_sig = rogue_private_key.sign(canonical_bytes).hex()
    rogue_authority_sig = AsymmetricAuthoritySignature(
        algorithm="ED25519",
        signer_identity="Gate3AuthoritativeVerifier",
        public_key_fingerprint=rogue_fp,
        payload_digest=rogue_digest,
        signature_hex=rogue_sig,
        timestamp="2026-08-19T14:30:00Z",
    )
    rogue_cert = EvidenceTrustCertificate(
        evidence_id=ev.evidence_id,
        source_sha=DEFAULT_TEST_SHA,
        is_verified=True,
        digest_verified=True,
        signature_verified=True,
        provenance_verified=True,
        verifier_identity="Gate3AuthoritativeVerifier",
        timestamp="2026-08-19T14:30:00Z",
        certificate_hash=rogue_digest,
        authority_signature=rogue_authority_sig,
    )
    # Verifier possessing only official authority public key rejects rogue certificate
    assert verify_gate_3_evidence_trust_certificate(rogue_cert, expected_source_sha=DEFAULT_TEST_SHA, public_key=TEST_AUTHORITY_PUBLIC_KEY) is False
    ctx_rogue = PolicyEvaluationContext(
        obligation=obl,
        claims=(claim,),
        evidence=(ev,),
        expected_source_sha=DEFAULT_TEST_SHA,
        trust_certificates={ev.evidence_id: rogue_cert},
    )
    assert CoverageTrustPredicate.is_trusted(ev, ctx_rogue) is False
    assert evaluate_policy(pol_cov_85, ctx_rogue).decision == PolicyDecisionType.DENY

    # 3. Modified certificate (tampered signature hex) -> REJECT
    tampered_sig = AsymmetricAuthoritySignature(
        algorithm="ED25519",
        signer_identity=genuine_cert.authority_signature.signer_identity,
        public_key_fingerprint=genuine_cert.authority_signature.public_key_fingerprint,
        payload_digest=genuine_cert.authority_signature.payload_digest,
        signature_hex="0" * 128,  # Corrupted signature
        timestamp=genuine_cert.authority_signature.timestamp,
    )
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
        authority_signature=tampered_sig,
    )
    assert verify_gate_3_evidence_trust_certificate(modified_cert, expected_source_sha=DEFAULT_TEST_SHA, public_key=TEST_AUTHORITY_PUBLIC_KEY) is False

    # 4. Timestamp / Provenance mutation -> REJECT
    mutated_time_sig = AsymmetricAuthoritySignature(
        algorithm="ED25519",
        signer_identity=genuine_cert.authority_signature.signer_identity,
        public_key_fingerprint=genuine_cert.authority_signature.public_key_fingerprint,
        payload_digest=genuine_cert.authority_signature.payload_digest,
        signature_hex=genuine_cert.authority_signature.signature_hex,
        timestamp="2026-08-19T23:59:59Z",  # Mismatched timestamp!
    )
    time_mutated_cert = EvidenceTrustCertificate(
        evidence_id=genuine_cert.evidence_id,
        source_sha=DEFAULT_TEST_SHA,
        is_verified=genuine_cert.is_verified,
        digest_verified=genuine_cert.digest_verified,
        signature_verified=genuine_cert.signature_verified,
        provenance_verified=genuine_cert.provenance_verified,
        verifier_identity=genuine_cert.verifier_identity,
        timestamp="2026-08-19T14:30:00Z",
        certificate_hash=genuine_cert.certificate_hash,
        authority_signature=mutated_time_sig,
    )
    assert verify_gate_3_evidence_trust_certificate(time_mutated_cert, expected_source_sha=DEFAULT_TEST_SHA, public_key=TEST_AUTHORITY_PUBLIC_KEY) is False

    # 5. Wrong issuer -> REJECT
    wrong_issuer_cert = issue_gate_3_evidence_certificate(ev, expected_source_sha=DEFAULT_TEST_SHA, verifier_identity="UntrustedForeignIssuer")
    assert verify_gate_3_evidence_trust_certificate(wrong_issuer_cert, expected_source_sha=DEFAULT_TEST_SHA, public_key=TEST_AUTHORITY_PUBLIC_KEY) is False

    # 6. Wrong source_sha -> REJECT
    assert verify_gate_3_evidence_trust_certificate(genuine_cert, expected_source_sha="b" * 40, public_key=TEST_AUTHORITY_PUBLIC_KEY) is False


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


def test_adversarial_provider_keystore_overwrite_rejected():
    """Adversarial vector: Overwriting an already-registered provider key fails closed with RuntimeError."""
    with pytest.raises(RuntimeError, match="already registered and cannot be overwritten"):
        Gate3ProviderKeyStore.register_provider_key("KEY-001", b"ATTEMPTED_OVERWRITE_SECRET_KEY_123")


def test_adversarial_provider_keystore_rotation_lifecycle():
    """Test controlled key rotation lifecycle: old key retired, new key activated, retired key fails closed."""
    new_key_secret = b"NEW_ROTATED_PROVIDER_SECRET_KEY_2026"
    Gate3ProviderKeyStore.rotate_provider_key("KEY-001", "KEY-002", new_key_secret)

    # 1. Old key is marked retired and cannot be retrieved
    assert Gate3ProviderKeyStore.is_retired("KEY-001") is True
    with pytest.raises(RuntimeError, match="retired and cannot be used"):
        Gate3ProviderKeyStore.get_provider_key("KEY-001")

    # 2. New key is active and accessible
    assert Gate3ProviderKeyStore.get_provider_key("KEY-002") == new_key_secret

    # 3. Evidence signed with retired key KEY-001 fails closed
    with pytest.raises(RuntimeError, match="retired and cannot be used"):
        sign_provider_evidence(
            evidence_id="EV-RETIRED-TEST",
            claim_id="CLM-1",
            provider_id="prov1",
            capability="CODE_COVERAGE",
            execution_id="EXEC-1",
            source_sha=DEFAULT_TEST_SHA,
            scope=EvidenceScope(targets_evaluated=("TARGET-1",), aspects_covered=("AUTH",)),
            observation=EvidenceObservation(raw_status=RawStatus.PASS),
            provenance=Provenance(engine_name="test", engine_version="1.0", environment_hash="0"*64, timestamp="2026-08-19T10:00:00Z"),
            key_id="KEY-001",
        )

    # 4. New evidence signed with active rotated key KEY-002 verifies successfully
    ev_rotated = make_test_evidence(ev_id="EV-ROTATED", key_id="KEY-002", counterexample={"coverage_pct": 92.0})
    assert verify_provider_evidence_signature(ev_rotated) is True
    cert = issue_gate_3_evidence_certificate(ev_rotated, expected_source_sha=DEFAULT_TEST_SHA)
    assert cert.is_verified is True
    assert cert.signature_verified is True


def test_adversarial_evidence_nonce_replay_rejected():
    """Adversarial vector: Reusing an already-consumed evidence nonce fails under D0 single-use anti-replay rule."""
    ev1 = make_test_evidence(ev_id="EV-FIRST-USE", nonce="SINGLE-USE-NONCE-12345", counterexample={"coverage_pct": 90.0})
    cert1 = issue_gate_3_evidence_certificate(ev1, expected_source_sha=DEFAULT_TEST_SHA)
    assert cert1.is_verified is True
    assert cert1.signature_verified is True
    assert Gate3NonceTracker.is_consumed("SINGLE-USE-NONCE-12345") is True

    # Replay attack: submitting evidence with the exact same consumed nonce
    ev2_replay = make_test_evidence(ev_id="EV-REPLAY-ATTACK", nonce="SINGLE-USE-NONCE-12345", counterexample={"coverage_pct": 90.0})
    cert2_replay = issue_gate_3_evidence_certificate(ev2_replay, expected_source_sha=DEFAULT_TEST_SHA)
    assert cert2_replay.is_verified is False
    assert cert2_replay.signature_verified is False
    assert "Replay detected" in cert2_replay.rejection_reason


def test_adversarial_replayed_evidence_rejected_in_policy_evaluation():
    """Adversarial vector: Replayed evidence rejected during certificate issuance causes policy denial."""
    obl = make_test_obligation()
    claim = make_test_claim()
    pol_cov_85 = Policy("POL-COV85", PolicyScope.PROJECT, 1, PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CODE_COVERAGE, {"min_coverage_pct": 85.0}),)))

    # First issuance succeeds
    ev = make_test_evidence(ev_id="EV-ORIG-COV", nonce="NONCE-FOR-POLICY-REPLAY", counterexample={"coverage_pct": 90.0})
    cert_valid = issue_gate_3_evidence_certificate(ev, expected_source_sha=DEFAULT_TEST_SHA)
    ctx1 = PolicyEvaluationContext(obl, (claim,), (ev,), expected_source_sha=DEFAULT_TEST_SHA, trust_certificates={ev.evidence_id: cert_valid})
    assert evaluate_policy(pol_cov_85, ctx1).decision == PolicyDecisionType.ALLOW

    # Second issuance with same nonce is rejected by Gate 3 Authority
    cert_replayed = issue_gate_3_evidence_certificate(ev, expected_source_sha=DEFAULT_TEST_SHA)
    assert cert_replayed.is_verified is False
    ctx2 = PolicyEvaluationContext(obl, (claim,), (ev,), expected_source_sha=DEFAULT_TEST_SHA, trust_certificates={ev.evidence_id: cert_replayed})
    assert evaluate_policy(pol_cov_85, ctx2).decision == PolicyDecisionType.DENY

def test_cross_process_single_use_same_nonce_two_processes(tmp_path):
    """Test: same nonce, two processes -> exactly one succeeds."""
    import subprocess
    import sys
    store_file = str(tmp_path / "cross_proc_nonce.log")
    nonce = f"CROSS-PROC-NONCE-{uuid.uuid4().hex[:8]}"

    script = f"""
import sys
from benchmark.parity.gate_3_authority import Gate3NonceTracker
Gate3NonceTracker.set_store_path({repr(store_file)})
res = Gate3NonceTracker.consume_nonce({repr(nonce)})
print("SUCCESS" if res else "REJECT")
"""
    p1 = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    p2 = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    out1, _ = p1.communicate(timeout=10)
    out2, _ = p2.communicate(timeout=10)

    results = [out1.strip(), out2.strip()]
    assert results.count("SUCCESS") == 1, f"Expected exactly one SUCCESS, got {results}"
    assert results.count("REJECT") == 1, f"Expected exactly one REJECT, got {results}"


def test_concurrent_same_nonce_race_exactly_one_succeeds(tmp_path):
    """Test: concurrent same-nonce race -> exactly one succeeds."""
    import concurrent.futures
    store_file = str(tmp_path / "concurrent_race_nonce.log")
    nonce = f"RACE-NONCE-{uuid.uuid4().hex[:8]}"

    def _attempt_consume(i):
        from benchmark.parity.gate_3_authority import Gate3NonceTracker
        Gate3NonceTracker.set_store_path(store_file)
        return Gate3NonceTracker.consume_nonce(nonce)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(_attempt_consume, i) for i in range(8)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert results.count(True) == 1, f"Expected exactly one successful reservation, got {results.count(True)}"
    assert results.count(False) == 7, f"Expected 7 failed reservations, got {results.count(False)}"


def test_invalid_signature_nonce_remains_reusable():
    """Test: invalid signature -> nonce remains reusable."""
    nonce = f"REUSABLE-NONCE-{uuid.uuid4().hex[:8]}"
    ev_bad = make_test_evidence(
        ev_id="EV-BAD-SIG",
        nonce=nonce,
        counterexample={"coverage_pct": 90.0},
        custom_signature=HmacSessionSignature(
            algorithm="HMAC-SHA256",
            key_id="KEY-001",
            nonce=nonce,
            raw_stdout_digest="0" * 64,
            signature_hex="f" * 64,
            timestamp="2026-08-19T10:00:00Z",
        ),
    )
    # Verification fails closed due to invalid signature
    cert_bad = issue_gate_3_evidence_certificate(ev_bad, expected_source_sha=DEFAULT_TEST_SHA)
    assert cert_bad.is_verified is False
    assert cert_bad.signature_verified is False

    # Nonce MUST NOT have been consumed
    assert Gate3NonceTracker.is_consumed(nonce) is False

    # Now issue valid evidence with the same nonce -> MUST SUCCEED
    ev_good = make_test_evidence(ev_id="EV-GOOD-SIG", nonce=nonce, counterexample={"coverage_pct": 90.0})
    cert_good = issue_gate_3_evidence_certificate(ev_good, expected_source_sha=DEFAULT_TEST_SHA)
    assert cert_good.is_verified is True
    assert cert_good.signature_verified is True
    assert Gate3NonceTracker.is_consumed(nonce) is True


def test_valid_verification_nonce_consumed_and_replay_rejected():
    """Test: valid verification -> nonce consumed, replay after successful verification -> reject."""
    nonce = f"VALID-CONSUMED-NONCE-{uuid.uuid4().hex[:8]}"
    ev = make_test_evidence(ev_id="EV-VALID-ONCE", nonce=nonce, counterexample={"coverage_pct": 90.0})

    # 1. Valid verification -> nonce consumed
    cert1 = issue_gate_3_evidence_certificate(ev, expected_source_sha=DEFAULT_TEST_SHA)
    assert cert1.is_verified is True
    assert cert1.signature_verified is True
    assert Gate3NonceTracker.is_consumed(nonce) is True

    # 2. Replay after successful verification -> rejected
    cert2 = issue_gate_3_evidence_certificate(ev, expected_source_sha=DEFAULT_TEST_SHA)
    assert cert2.is_verified is False
    assert cert2.signature_verified is False
    assert "Replay detected" in cert2.rejection_reason


def test_restart_process_boundary_replay_still_rejected(tmp_path):
    """Test: restart/process boundary -> replay still rejected via persistent store."""
    store_file = str(tmp_path / "persist_restart_nonce.log")
    Gate3NonceTracker.set_store_path(store_file)
    nonce = f"PERSIST-RESTART-NONCE-{uuid.uuid4().hex[:8]}"

    # Process 1 consumes nonce
    ev = make_test_evidence(ev_id="EV-PROC1", nonce=nonce, counterexample={"coverage_pct": 90.0})
    cert1 = issue_gate_3_evidence_certificate(ev, expected_source_sha=DEFAULT_TEST_SHA)
    assert cert1.is_verified is True

    # Simulate fresh process restart by wiping in-memory process-local cache
    Gate3NonceTracker.set_store_path(store_file)
    
    # Process 2 attempts replay -> rejected from persistent disk store
    ev_replay = make_test_evidence(ev_id="EV-PROC2-REPLAY", nonce=nonce, counterexample={"coverage_pct": 90.0})
    cert2 = issue_gate_3_evidence_certificate(ev_replay, expected_source_sha=DEFAULT_TEST_SHA)
    assert cert2.is_verified is False
    assert "Replay detected" in cert2.rejection_reason


def test_environment_provider_keys_explicit_bootstrap():
    """Test: Environment provider keys must be explicitly bootstrapped or registered."""
    Gate3ProviderKeyStore.clear()
    # Unregistered key fails closed
    with pytest.raises(KeyError, match="not registered in certified keystore"):
        Gate3ProviderKeyStore.get_provider_key("KEY-001")

    # Explicit bootstrap from environment
    os.environ["GATE3_PROVIDER_KEY"] = "EXPLICIT_BOOTSTRAP_SECRET_KEY_32BYTES"
    Gate3ProviderKeyStore.bootstrap_from_environment()
    assert Gate3ProviderKeyStore.get_provider_key("KEY-001") == b"EXPLICIT_BOOTSTRAP_SECRET_KEY_32BYTES"

def test_storage_unavailable_fails_closed(tmp_path):
    """Test: storage unavailable -> fail closed (raises StorageUnavailableError, certificate rejected)."""
    from events.exceptions import StorageUnavailableError
    from events.store import D2NonceStore

    # Point store to an invalid/illegal path
    invalid_path = str(tmp_path / "non_existent_dir_1" / "non_existent_dir_2" / "nonce.log")
    store = D2NonceStore(file_path=invalid_path)

    # Force error by making parent directory creation fail or making path a directory
    dir_as_file = tmp_path / "dir_blocked"
    dir_as_file.mkdir()
    blocked_store = D2NonceStore(file_path=str(dir_as_file))

    with pytest.raises(StorageUnavailableError):
        blocked_store.reserve_nonce("NONCE-TEST-BLOCKED")

    # When used in authority issuance, certificate is rejected fail closed
    Gate3NonceTracker.set_store_path(str(dir_as_file))
    ev = make_test_evidence(ev_id="EV-FAIL-CLOSED", nonce="NONCE-STORE-UNAVAILABLE", counterexample={"coverage_pct": 90.0})
    cert = issue_gate_3_evidence_certificate(ev, expected_source_sha=DEFAULT_TEST_SHA)
    assert cert.is_verified is False
    assert cert.signature_verified is False
    assert "storage failure" in cert.rejection_reason.lower() or "operational failure" in cert.rejection_reason.lower()


def test_corrupted_nonce_store_fails_closed(tmp_path):
    """Test: corrupted nonce store -> fail closed (raises CorruptEventLogError, certificate rejected)."""
    from events.exceptions import CorruptEventLogError
    from events.store import D2NonceStore

    corrupt_log = tmp_path / "corrupt_nonces.log"
    # Write invalid corrupted JSON records
    with open(corrupt_log, "w", encoding="utf-8") as f:
        f.write("CORRUPT_NOT_JSON_DATA\n")

    store = D2NonceStore(file_path=str(corrupt_log))
    with pytest.raises(CorruptEventLogError):
        store.reserve_nonce("NONCE-TEST-CORRUPT")

    # In certificate issuance -> fail closed
    Gate3NonceTracker.set_store_path(str(corrupt_log))
    ev = make_test_evidence(ev_id="EV-CORRUPT-FAIL", nonce="NONCE-CORRUPT", counterexample={"coverage_pct": 90.0})
    cert = issue_gate_3_evidence_certificate(ev, expected_source_sha=DEFAULT_TEST_SHA)
    assert cert.is_verified is False
    assert "D2 storage failure" in cert.rejection_reason or "Corrupt" in cert.rejection_reason


def test_duplicate_nonce_rejected_atomic_insert_if_absent(tmp_path):
    """Test: duplicate nonce -> rejected under atomic INSERT-if-absent semantics."""
    from events.store import D2NonceStore
    store_file = str(tmp_path / "insert_if_absent.log")
    store = D2NonceStore(file_path=store_file)
    nonce = f"INSERT-ABSENT-NONCE-{uuid.uuid4().hex[:8]}"

    # First reservation succeeds (absent)
    assert store.reserve_nonce(nonce) is True
    # Second reservation fails (duplicate)
    assert store.reserve_nonce(nonce) is False


def test_deployment_with_fresh_process_replay_rejected(tmp_path):
    """Test: deployment with fresh process -> replay still rejected from persistent D2 store."""
    import subprocess
    import sys
    store_file = str(tmp_path / "deployment_process_nonce.log")
    nonce = f"DEPLOYMENT-NONCE-{uuid.uuid4().hex[:8]}"

    # Process 1 (initial deployment worker) consumes nonce
    script_p1 = f"""
import sys
from benchmark.parity.gate_3_authority import Gate3NonceTracker
Gate3NonceTracker.set_store_path({repr(store_file)})
res = Gate3NonceTracker.consume_nonce({repr(nonce)})
print("SUCCESS" if res else "FAIL")
"""
    p1 = subprocess.Popen([sys.executable, "-c", script_p1], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out1, _ = p1.communicate(timeout=10)
    assert out1.strip() == "SUCCESS"

    # Process 2 (newly deployed fresh container/process) attempts to reuse nonce
    script_p2 = f"""
import sys
from benchmark.parity.gate_3_authority import Gate3NonceTracker
Gate3NonceTracker.set_store_path({repr(store_file)})
res = Gate3NonceTracker.consume_nonce({repr(nonce)})
print("SUCCESS" if res else "REJECT")
"""
    p2 = subprocess.Popen([sys.executable, "-c", script_p2], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out2, _ = p2.communicate(timeout=10)
    assert out2.strip() == "REJECT"

def test_adversarial_modified_nonce_record_fails_closed(tmp_path):
    """Adversarial vector: Modifying nonce value in record -> CorruptEventLogError (fail closed)."""
    from events.store import D2NonceStore
    from events.exceptions import CorruptEventLogError

    store_file = str(tmp_path / "mod_nonce.log")
    store = D2NonceStore(file_path=store_file)
    store.reserve_nonce("VALID-NONCE-1")

    # Tamper with the nonce value in the JSON line without recomputing hash
    with open(store_file, "r", encoding="utf-8") as f:
        data = f.read()
    tampered_data = data.replace("VALID-NONCE-1", "TAMPERED-NONCE-1")
    with open(store_file, "w", encoding="utf-8") as f:
        f.write(tampered_data)

    tampered_store = D2NonceStore(file_path=store_file)
    with pytest.raises(CorruptEventLogError, match="Cryptographic digest forgery/corruption"):
        tampered_store.reserve_nonce("ANOTHER-NONCE")


def test_adversarial_modified_timestamp_record_fails_closed(tmp_path):
    """Adversarial vector: Modifying timestamp in record -> CorruptEventLogError (fail closed)."""
    import json
    from events.store import D2NonceStore
    from events.exceptions import CorruptEventLogError

    store_file = str(tmp_path / "mod_ts.log")
    store = D2NonceStore(file_path=store_file)
    store.reserve_nonce("VALID-NONCE-TS")

    with open(store_file, "r", encoding="utf-8") as f:
        line = f.readline().strip()
    record = json.loads(line)
    record["timestamp"] = "1970-01-01T00:00:00Z"
    with open(store_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    tampered_store = D2NonceStore(file_path=store_file)
    with pytest.raises(CorruptEventLogError, match="Cryptographic digest forgery/corruption"):
        tampered_store.is_nonce_consumed("VALID-NONCE-TS")


def test_adversarial_modified_digest_record_fails_closed(tmp_path):
    """Adversarial vector: Modifying digest hash in record -> CorruptEventLogError (fail closed)."""
    import json
    from events.store import D2NonceStore
    from events.exceptions import CorruptEventLogError

    store_file = str(tmp_path / "mod_digest.log")
    store = D2NonceStore(file_path=store_file)
    store.reserve_nonce("VALID-NONCE-DIGEST")

    with open(store_file, "r", encoding="utf-8") as f:
        line = f.readline().strip()
    record = json.loads(line)
    record["digest"] = "f" * 64
    with open(store_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    tampered_store = D2NonceStore(file_path=store_file)
    with pytest.raises(CorruptEventLogError, match="Cryptographic digest forgery/corruption"):
        tampered_store.reserve_nonce("ANOTHER-NONCE")


def test_adversarial_deleted_or_partial_record_fails_closed(tmp_path):
    """Adversarial vector: Deleted record breaking sequence/chain or torn record -> fail closed."""
    from events.store import D2NonceStore
    from events.exceptions import CorruptEventLogError

    store_file = str(tmp_path / "partial_record.log")
    store = D2NonceStore(file_path=store_file)
    store.reserve_nonce("NONCE-1")
    store.reserve_nonce("NONCE-2")

    # 1. Truncate / corrupt last line
    with open(store_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    with open(store_file, "w", encoding="utf-8") as f:
        f.write(lines[0] + '{"nonce": "INCOMPLETE')

    tampered_store = D2NonceStore(file_path=store_file)
    with pytest.raises(CorruptEventLogError, match="Corrupt JSON"):
        tampered_store.reserve_nonce("NONCE-3")

    # 2. Sequence / Chain discontinuity (deleting record 1)
    store_file_discontinuity = str(tmp_path / "discontinuity.log")
    store2 = D2NonceStore(file_path=store_file_discontinuity)
    store2.reserve_nonce("NONCE-A")
    store2.reserve_nonce("NONCE-B")
    with open(store_file_discontinuity, "r", encoding="utf-8") as f:
        lines2 = f.readlines()
    # keep only line 2 (which has sequence_number=2, expected=1)
    with open(store_file_discontinuity, "w", encoding="utf-8") as f:
        f.write(lines2[1])

    tampered_store2 = D2NonceStore(file_path=store_file_discontinuity)
    with pytest.raises(CorruptEventLogError, match="Sequence discontinuity"):
        tampered_store2.reserve_nonce("NONCE-C")

def test_adversarial_valid_nonce_cached_then_tamper_durable_record_fails_closed(tmp_path):
    """Adversarial vector: Valid nonce queried -> durable record tampered -> same-process query fails closed with CorruptEventLogError."""
    from events.store import D2NonceStore
    from events.exceptions import CorruptEventLogError

    store_file = str(tmp_path / "cache_tamper.log")
    store = D2NonceStore(file_path=store_file)
    nonce = f"CACHE-TAMPER-NONCE-{uuid.uuid4().hex[:8]}"

    # 1. Valid reservation
    assert store.reserve_nonce(nonce) is True
    assert store.is_nonce_consumed(nonce) is True

    # 2. Adversary tampers with durable record on disk
    with open(store_file, "r", encoding="utf-8") as f:
        data = f.read()
    tampered_data = data.replace(nonce, "FORGED_NONCE_VALUE")
    with open(store_file, "w", encoding="utf-8") as f:
        f.write(tampered_data)

    # 3. Same-process query on the SAME store instance MUST NOT return cached truth; MUST verify durable store and fail closed
    with pytest.raises(CorruptEventLogError, match="Cryptographic digest forgery/corruption"):
        store.is_nonce_consumed(nonce)

    with pytest.raises(CorruptEventLogError, match="Cryptographic digest forgery/corruption"):
        store.reserve_nonce(f"ANOTHER-NONCE-{uuid.uuid4().hex[:8]}")


def test_adversarial_cached_nonce_corrupt_parent_chain_replay_check_fails_closed(tmp_path):
    """Adversarial vector: Cached nonce -> corrupt parent chain on disk -> replay check fails closed with CorruptEventLogError."""
    import json
    from events.store import D2NonceStore
    from events.exceptions import CorruptEventLogError

    store_file = str(tmp_path / "chain_tamper.log")
    store = D2NonceStore(file_path=store_file)
    nonce1 = f"CHAIN-NONCE-1-{uuid.uuid4().hex[:8]}"
    nonce2 = f"CHAIN-NONCE-2-{uuid.uuid4().hex[:8]}"

    assert store.reserve_nonce(nonce1) is True
    assert store.reserve_nonce(nonce2) is True

    # Tamper with the parent digest of record 2 in the durable log
    with open(store_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    rec2 = json.loads(lines[1])
    rec2["parent_digest"] = "e" * 64
    lines[1] = json.dumps(rec2) + "\n"
    with open(store_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # Replay query on the SAME store instance MUST fail closed
    with pytest.raises(CorruptEventLogError, match="Cryptographic chain broken"):
        store.is_nonce_consumed(nonce2)


def test_adversarial_wrong_domain_separator_fails_closed(tmp_path):
    """Adversarial vector: Record with forged/missing domain separator -> CorruptEventLogError."""
    import json
    from events.store import D2NonceStore
    from events.exceptions import CorruptEventLogError

    store_file = str(tmp_path / "wrong_domain.log")
    store = D2NonceStore(file_path=store_file)
    nonce = f"DOMAIN-NONCE-{uuid.uuid4().hex[:8]}"
    store.reserve_nonce(nonce)

    with open(store_file, "r", encoding="utf-8") as f:
        line = f.readline().strip()
    record = json.loads(line)
    record["domain"] = "FORGED_DOMAIN_V0:"
    with open(store_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    with pytest.raises(CorruptEventLogError, match="Domain separator mismatch"):
        store.is_nonce_consumed(nonce)


# ============================================================================
# 8. D3 Cryptographic PolicyException Authority Test Suite (E1 - E21)
# ============================================================================

def test_d3_exception_e1_valid_signature_accepted():
    """E1: Valid genuine Ed25519 signature with registered active actor -> accepted."""
    obl = make_test_obligation(obl_id="OBL-001")
    exc = make_test_exception(obl_id="OBL-001", policy_id="POL-001")
    ctx = make_test_context(obl, (), (), exceptions=(exc,))
    pol = Policy(
        "POL-001", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )
    decision = evaluate_policy(pol, ctx)
    assert decision.decision == PolicyDecisionType.ALLOW
    assert "EXC-001" in decision.exceptions_applied


def test_d3_exception_e2_modified_justification_rejected():
    """E2: Modified justification string after signing -> InvalidExceptionError."""
    obl = make_test_obligation(obl_id="OBL-001")
    exc = make_test_exception(obl_id="OBL-001", policy_id="POL-001")
    tampered_exc = PolicyException(
        exception_id=exc.exception_id,
        obligation_id=exc.obligation_id,
        policy_id=exc.policy_id,
        justification="TAMPERED JUSTIFICATION STRING WITH SUFFICIENT LENGTH TO PASS LENGTH CHECK",
        authorized_by=exc.authorized_by,
        compensating_controls=exc.compensating_controls,
        signature=exc.signature,
        expiry=exc.expiry,
    )
    ctx = make_test_context(obl, (), (), exceptions=(tampered_exc,))
    pol = Policy(
        "POL-001", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )
    with pytest.raises(InvalidExceptionError, match="payload digest mismatch"):
        evaluate_policy(pol, ctx)


def test_d3_exception_e3_modified_obligation_id_rejected():
    """E3: Modified obligation_id in exception -> InvalidExceptionError."""
    obl = make_test_obligation(obl_id="OBL-001")
    exc = make_test_exception(obl_id="OBL-001", policy_id="POL-001")
    tampered_exc = PolicyException(
        exception_id=exc.exception_id,
        obligation_id="OBL-999",
        policy_id=exc.policy_id,
        justification=exc.justification,
        authorized_by=exc.authorized_by,
        compensating_controls=exc.compensating_controls,
        signature=exc.signature,
        expiry=exc.expiry,
    )
    ctx = make_test_context(obl, (), (), exceptions=(tampered_exc,))
    pol = Policy(
        "POL-001", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )
    with pytest.raises(InvalidExceptionError, match="Exception obligation mismatch"):
        evaluate_policy(pol, ctx)


def test_d3_exception_e4_modified_policy_id_rejected():
    """E4: Modified policy_id in exception -> InvalidExceptionError."""
    obl = make_test_obligation(obl_id="OBL-001")
    exc = make_test_exception(obl_id="OBL-001", policy_id="POL-001")
    tampered_exc = PolicyException(
        exception_id=exc.exception_id,
        obligation_id=exc.obligation_id,
        policy_id="POL-999",
        justification=exc.justification,
        authorized_by=exc.authorized_by,
        compensating_controls=exc.compensating_controls,
        signature=exc.signature,
        expiry=exc.expiry,
    )
    ctx = make_test_context(obl, (), (), exceptions=(tampered_exc,))
    pol = Policy(
        "POL-001", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )
    with pytest.raises(InvalidExceptionError, match="Exception policy mismatch"):
        evaluate_policy(pol, ctx)


def test_d3_exception_e5_modified_compensating_controls_rejected():
    """E5: Modified compensating_controls -> InvalidExceptionError."""
    obl = make_test_obligation(obl_id="OBL-001")
    exc = make_test_exception(obl_id="OBL-001", policy_id="POL-001")
    tampered_exc = PolicyException(
        exception_id=exc.exception_id,
        obligation_id=exc.obligation_id,
        policy_id=exc.policy_id,
        justification=exc.justification,
        authorized_by=exc.authorized_by,
        compensating_controls=("Tampered control replacing original",),
        signature=exc.signature,
        expiry=exc.expiry,
    )
    ctx = make_test_context(obl, (), (), exceptions=(tampered_exc,))
    pol = Policy(
        "POL-001", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )
    with pytest.raises(InvalidExceptionError, match="payload digest mismatch"):
        evaluate_policy(pol, ctx)


def test_d3_exception_e6_modified_expiry_rejected():
    """E6: Modified expiry timestamp -> InvalidExceptionError."""
    obl = make_test_obligation(obl_id="OBL-001")
    exc = make_test_exception(obl_id="OBL-001", policy_id="POL-001", expiry="2026-12-31T23:59:59Z")
    tampered_exc = PolicyException(
        exception_id=exc.exception_id,
        obligation_id=exc.obligation_id,
        policy_id=exc.policy_id,
        justification=exc.justification,
        authorized_by=exc.authorized_by,
        compensating_controls=exc.compensating_controls,
        signature=exc.signature,
        expiry="2027-12-31T23:59:59Z",
    )
    ctx = make_test_context(obl, (), (), exceptions=(tampered_exc,))
    pol = Policy(
        "POL-001", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )
    with pytest.raises(InvalidExceptionError, match="payload digest mismatch"):
        evaluate_policy(pol, ctx)


def test_d3_exception_e7_wrong_actor_key_rejected():
    """E7: Signed with rogue Key B while claiming Actor A -> rejected."""
    obl = make_test_obligation(obl_id="OBL-001")
    rogue_priv = ed25519.Ed25519PrivateKey.generate()
    genuine_priv = ed25519.Ed25519PrivateKey.generate()
    genuine_pub = genuine_priv.public_key()
    genuine_fp = PolicyActorKeyRegistry.enroll_actor("ACTOR-A", "SECURITY_LEAD", genuine_pub)

    actor = AuthorizedActor("ACTOR-A", "SECURITY_LEAD", genuine_fp)
    dummy_sig = AsymmetricAuthoritySignature(
        algorithm="ED25519",
        signer_identity="ACTOR-A",
        public_key_fingerprint=genuine_fp,
        payload_digest="0" * 64,
        signature_hex="0" * 128,
        timestamp="2026-08-21T00:00:00Z",
    )
    raw_exc = PolicyException(
        exception_id="EXC-001",
        obligation_id="OBL-001",
        policy_id="POL-001",
        justification="Manual security review approved by security lead with HSM token.",
        authorized_by=actor,
        compensating_controls=("Audit log monitoring enabled",),
        signature=dummy_sig,
        expiry=None,
    )
    # Sign raw_exc using rogue_priv instead of genuine_priv
    canonical_bytes = canonicalize_policy_exception_preimage(raw_exc)
    payload_digest = hashlib.sha256(canonical_bytes).hexdigest()
    rogue_sig_bytes = rogue_priv.sign(canonical_bytes)

    forged_sig = AsymmetricAuthoritySignature(
        algorithm="ED25519",
        signer_identity="ACTOR-A",
        public_key_fingerprint=genuine_fp,
        payload_digest=payload_digest,
        signature_hex=rogue_sig_bytes.hex(),
        timestamp="2026-08-21T00:00:00Z",
    )
    forged_exc = PolicyException(
        exception_id="EXC-001",
        obligation_id="OBL-001",
        policy_id="POL-001",
        justification="Manual security review approved by security lead with HSM token.",
        authorized_by=actor,
        compensating_controls=("Audit log monitoring enabled",),
        signature=forged_sig,
        expiry=None,
    )

    ctx = make_test_context(obl, (), (), exceptions=(forged_exc,))
    pol = Policy(
        "POL-001", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )
    with pytest.raises(InvalidExceptionError, match="signature verification failed"):
        evaluate_policy(pol, ctx)


def test_d3_exception_e8_fingerprint_mismatch_rejected():
    """E8: Signature has genuine signature bytes but AuthorizedActor.public_key_fingerprint tampered -> rejected."""
    obl = make_test_obligation(obl_id="OBL-001")
    exc = make_test_exception(obl_id="OBL-001", policy_id="POL-001")
    tampered_actor = AuthorizedActor("SEC-OFFICER-01", "SECURITY_LEAD", "0" * 64)
    tampered_exc = PolicyException(
        exception_id=exc.exception_id,
        obligation_id=exc.obligation_id,
        policy_id=exc.policy_id,
        justification=exc.justification,
        authorized_by=tampered_actor,
        compensating_controls=exc.compensating_controls,
        signature=exc.signature,
        expiry=exc.expiry,
    )
    ctx = make_test_context(obl, (), (), exceptions=(tampered_exc,))
    pol = Policy(
        "POL-001", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )
    with pytest.raises(InvalidExceptionError, match="does not match AuthorizedActor fingerprint"):
        evaluate_policy(pol, ctx)


def test_d3_exception_e9_revoked_actor_key_rejected():
    """E9: Revoked actor key -> InvalidExceptionError."""
    obl = make_test_obligation(obl_id="OBL-001")
    actor_priv = ed25519.Ed25519PrivateKey.generate()
    actor_pub = actor_priv.public_key()
    fp = PolicyActorKeyRegistry.enroll_actor("SEC-02", "SECURITY_LEAD", actor_pub)

    exc = _sign_test_exception(
        exception_id="EXC-001",
        obligation_id="OBL-001",
        policy_id="POL-001",
        justification="Manual security review approved by security lead with HSM token.",
        actor_id="SEC-02",
        actor_role="SECURITY_LEAD",
        private_key=actor_priv,
        compensating_controls=("Audit log monitoring enabled",),
        auto_enroll=False,
    )
    # Revoke actor key
    PolicyActorKeyRegistry.revoke_actor(fp)

    ctx = make_test_context(obl, (), (), exceptions=(exc,))
    pol = Policy(
        "POL-001", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )
    with pytest.raises(InvalidExceptionError, match="has been revoked"):
        evaluate_policy(pol, ctx)


def test_d3_exception_e10_expired_exception_rejected():
    """E10: Expired exception relative to evaluation timestamp -> ExpiredExceptionError."""
    obl = make_test_obligation(obl_id="OBL-001")
    exc = make_test_exception(
        obl_id="OBL-001",
        policy_id="POL-001",
        expiry="2026-01-01T00:00:00Z",
    )
    ctx = make_test_context(
        obl, (), (), exceptions=(exc,),
        evaluation_timestamp="2026-08-21T12:00:00Z"
    )
    pol = Policy(
        "POL-001", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )
    with pytest.raises(ExpiredExceptionError, match="expired at"):
        evaluate_policy(pol, ctx)


def test_d3_exception_e11_malformed_signature_rejected():
    """E11: Malformed signature hex / invalid length -> DomainValidationError / InvalidExceptionError."""
    obl = make_test_obligation(obl_id="OBL-001")
    exc = make_test_exception(obl_id="OBL-001", policy_id="POL-001")

    # 1. Invalid hex string length rejected at schema validation
    with pytest.raises(DomainValidationError, match="signature_hex"):
        AsymmetricAuthoritySignature(
            algorithm="ED25519",
            signer_identity=exc.signature.signer_identity,
            public_key_fingerprint=exc.signature.public_key_fingerprint,
            payload_digest=exc.signature.payload_digest,
            signature_hex="deadbeef",
            timestamp=exc.signature.timestamp,
        )

    # 2. Valid-length dummy signature failing cryptographic verification
    dummy_sig = AsymmetricAuthoritySignature(
        algorithm="ED25519",
        signer_identity=exc.signature.signer_identity,
        public_key_fingerprint=exc.signature.public_key_fingerprint,
        payload_digest=exc.signature.payload_digest,
        signature_hex="0" * 128,
        timestamp=exc.signature.timestamp,
    )
    tampered_exc = PolicyException(
        exception_id=exc.exception_id,
        obligation_id=exc.obligation_id,
        policy_id=exc.policy_id,
        justification=exc.justification,
        authorized_by=exc.authorized_by,
        compensating_controls=exc.compensating_controls,
        signature=dummy_sig,
        expiry=exc.expiry,
    )
    ctx = make_test_context(obl, (), (), exceptions=(tampered_exc,))
    pol = Policy(
        "POL-001", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )
    with pytest.raises(InvalidExceptionError):
        evaluate_policy(pol, ctx)


def test_d3_exception_e12_replayed_different_obligation_rejected():
    """E12: Replaying valid exception for OBL-001 onto context for OBL-002 -> rejected."""
    obl_different = make_test_obligation(obl_id="OBL-002")
    exc_orig = make_test_exception(obl_id="OBL-001", policy_id="POL-001")
    ctx = make_test_context(obl_different, (), (), exceptions=(exc_orig,))
    pol = Policy(
        "POL-001", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )
    with pytest.raises(InvalidExceptionError, match="Exception obligation mismatch"):
        evaluate_policy(pol, ctx)


def test_d3_exception_e13_replayed_different_policy_rejected():
    """E13: Replaying valid exception for POL-001 onto evaluation for POL-002 -> rejected."""
    obl = make_test_obligation(obl_id="OBL-001")
    exc_orig = make_test_exception(obl_id="OBL-001", policy_id="POL-001")
    ctx = make_test_context(obl, (), (), exceptions=(exc_orig,))
    pol_different = Policy(
        "POL-002", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )
    with pytest.raises(InvalidExceptionError, match="Exception policy mismatch"):
        evaluate_policy(pol_different, ctx)


def test_d3_exception_e14_canonical_reordering_deterministic():
    """E14: Canonical RFC 8785 JSON ordering produces identical byte digest & valid signature."""
    exc1 = make_test_exception(obl_id="OBL-001", policy_id="POL-001")
    canonical_bytes1 = canonicalize_policy_exception_preimage(exc1)

    # Invert dictionary insertion order
    payload_reordered = {
        "expiry": exc1.expiry,
        "signature_metadata": {
            "timestamp": exc1.signature.timestamp,
            "public_key_fingerprint": exc1.signature.public_key_fingerprint,
            "signer_identity": exc1.signature.signer_identity,
            "algorithm": exc1.signature.algorithm,
        },
        "compensating_controls": list(exc1.compensating_controls),
        "authorized_by": {
            "public_key_fingerprint": exc1.authorized_by.public_key_fingerprint,
            "actor_role": exc1.authorized_by.actor_role,
            "actor_id": exc1.authorized_by.actor_id,
        },
        "justification": exc1.justification,
        "policy_id": exc1.policy_id,
        "obligation_id": exc1.obligation_id,
        "exception_id": exc1.exception_id,
    }
    canonical_bytes2 = canonicalize_json(payload_reordered)
    assert canonical_bytes1 == canonical_bytes2


def test_d3_exception_e15_tampered_field_after_signing_rejected():
    """E15: Tampered exception_id after signing -> InvalidExceptionError."""
    obl = make_test_obligation(obl_id="OBL-001")
    exc = make_test_exception(exc_id="EXC-001", obl_id="OBL-001", policy_id="POL-001")
    tampered_exc = PolicyException(
        exception_id="EXC-002",
        obligation_id=exc.obligation_id,
        policy_id=exc.policy_id,
        justification=exc.justification,
        authorized_by=exc.authorized_by,
        compensating_controls=exc.compensating_controls,
        signature=exc.signature,
        expiry=exc.expiry,
    )
    ctx = make_test_context(obl, (), (), exceptions=(tampered_exc,))
    pol = Policy(
        "POL-001", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )
    with pytest.raises(InvalidExceptionError, match="payload digest mismatch"):
        evaluate_policy(pol, ctx)


def test_d3_exception_e16_unauthorized_actor_registration_rejected():
    """E16: Unauthorized/invalid actor registration parameters fail closed."""
    valid_key = ed25519.Ed25519PrivateKey.generate().public_key()
    with pytest.raises(ValueError, match="actor_id must be a non-empty string"):
        PolicyActorKeyRegistry.enroll_actor("", "SECURITY_LEAD", valid_key)

    with pytest.raises(ValueError, match="actor_role must be a non-empty string"):
        PolicyActorKeyRegistry.enroll_actor("SEC-01", "", valid_key)

    with pytest.raises(TypeError, match="Expected Ed25519PublicKey"):
        PolicyActorKeyRegistry.enroll_actor("SEC-01", "ROLE", "not_a_public_key")  # type: ignore


def test_d3_exception_e17_arbitrary_public_key_cannot_become_signer():
    """E17: Arbitrary unenrolled public key cannot verify exceptions in policy evaluator."""
    obl = make_test_obligation(obl_id="OBL-001")
    unenrolled_priv = ed25519.Ed25519PrivateKey.generate()
    # Sign without enrolling in PolicyActorKeyRegistry
    exc = _sign_test_exception(
        exception_id="EXC-001",
        obligation_id="OBL-001",
        policy_id="POL-001",
        justification="Manual security review approved by security lead with HSM token.",
        actor_id="UNENROLLED-ACTOR",
        actor_role="ROGUE_ROLE",
        private_key=unenrolled_priv,
        compensating_controls=("Audit log monitoring enabled",),
        auto_enroll=False,
    )
    ctx = make_test_context(obl, (), (), exceptions=(exc,))
    pol = Policy(
        "POL-001", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )
    with pytest.raises(InvalidExceptionError, match="is not enrolled in authority registry"):
        evaluate_policy(pol, ctx)


def test_d3_exception_e18_revoked_actor_cannot_self_re_register():
    """E18: Revoked actor key cannot be re-enrolled in authority registry."""
    key = ed25519.Ed25519PrivateKey.generate().public_key()
    fp = PolicyActorKeyRegistry.enroll_actor("SEC-TEMP", "TEMP_ROLE", key)
    PolicyActorKeyRegistry.revoke_actor(fp)
    assert PolicyActorKeyRegistry.is_revoked(fp) is True

    # Attempt re-enrollment of the same revoked key fails closed
    with pytest.raises(RuntimeError, match="cannot be re-enrolled"):
        PolicyActorKeyRegistry.enroll_actor("SEC-TEMP", "TEMP_ROLE", key)


def test_d3_exception_e19_signer_identity_tampering_rejected():
    """E19: Signature signer_identity tampering is cryptographically detected and rejected."""
    obl = make_test_obligation(obl_id="OBL-001")
    exc = make_test_exception(obl_id="OBL-001", policy_id="POL-001")

    tampered_sig = AsymmetricAuthoritySignature(
        algorithm=exc.signature.algorithm,
        signer_identity="ROGUE-ACTOR-IDENTITY",  # Tampered signer identity
        public_key_fingerprint=exc.signature.public_key_fingerprint,
        payload_digest=exc.signature.payload_digest,
        signature_hex=exc.signature.signature_hex,
        timestamp=exc.signature.timestamp,
    )
    tampered_exc = PolicyException(
        exception_id=exc.exception_id,
        obligation_id=exc.obligation_id,
        policy_id=exc.policy_id,
        justification=exc.justification,
        authorized_by=exc.authorized_by,
        compensating_controls=exc.compensating_controls,
        signature=tampered_sig,
        expiry=exc.expiry,
    )
    ctx = make_test_context(obl, (), (), exceptions=(tampered_exc,))
    pol = Policy(
        "POL-001", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )
    with pytest.raises(InvalidExceptionError, match="payload digest mismatch"):
        evaluate_policy(pol, ctx)


def test_d3_exception_e20_signature_timestamp_tampering_rejected():
    """E20: Signature timestamp tampering is cryptographically detected and rejected."""
    obl = make_test_obligation(obl_id="OBL-001")
    exc = make_test_exception(obl_id="OBL-001", policy_id="POL-001")

    tampered_sig = AsymmetricAuthoritySignature(
        algorithm=exc.signature.algorithm,
        signer_identity=exc.signature.signer_identity,
        public_key_fingerprint=exc.signature.public_key_fingerprint,
        payload_digest=exc.signature.payload_digest,
        signature_hex=exc.signature.signature_hex,
        timestamp="2026-08-22T12:00:00Z",  # Tampered timestamp
    )
    tampered_exc = PolicyException(
        exception_id=exc.exception_id,
        obligation_id=exc.obligation_id,
        policy_id=exc.policy_id,
        justification=exc.justification,
        authorized_by=exc.authorized_by,
        compensating_controls=exc.compensating_controls,
        signature=tampered_sig,
        expiry=exc.expiry,
    )
    ctx = make_test_context(obl, (), (), exceptions=(tampered_exc,))
    pol = Policy(
        "POL-001", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )
    with pytest.raises(InvalidExceptionError, match="payload digest mismatch"):
        evaluate_policy(pol, ctx)


def test_d3_exception_e21_signature_fingerprint_tampering_rejected():
    """E21: Signature public_key_fingerprint tampering is detected and rejected."""
    obl = make_test_obligation(obl_id="OBL-001")
    exc = make_test_exception(obl_id="OBL-001", policy_id="POL-001")

    tampered_sig = AsymmetricAuthoritySignature(
        algorithm=exc.signature.algorithm,
        signer_identity=exc.signature.signer_identity,
        public_key_fingerprint="0" * 64,  # Tampered fingerprint
        payload_digest=exc.signature.payload_digest,
        signature_hex=exc.signature.signature_hex,
        timestamp=exc.signature.timestamp,
    )
    tampered_exc = PolicyException(
        exception_id=exc.exception_id,
        obligation_id=exc.obligation_id,
        policy_id=exc.policy_id,
        justification=exc.justification,
        authorized_by=exc.authorized_by,
        compensating_controls=exc.compensating_controls,
        signature=tampered_sig,
        expiry=exc.expiry,
    )
    ctx = make_test_context(obl, (), (), exceptions=(tampered_exc,))
    pol = Policy(
        "POL-001", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )
    with pytest.raises(InvalidExceptionError, match="does not match AuthorizedActor fingerprint"):
        evaluate_policy(pol, ctx)


def test_d3_exception_gate3_root_actor_binding():
    """Gate 3 Authority Key represents Gate3AuthoritativeVerifier root, not arbitrary human actors."""
    obl = make_test_obligation(obl_id="OBL-001")
    g3_priv = TEST_AUTHORITY_PRIVATE_KEY
    g3_pub = TEST_AUTHORITY_PUBLIC_KEY
    g3_fp = hashlib.sha256(g3_pub.public_bytes_raw()).hexdigest()

    # 1. Gate3 key used with mismatched human credentials -> REJECTED
    exc_forged_human = _sign_test_exception(
        exception_id="EXC-001",
        obligation_id="OBL-001",
        policy_id="POL-001",
        justification="Manual security review approved by security lead with HSM token.",
        actor_id="SEC-OFFICER-01",
        actor_role="SECURITY_LEAD",
        private_key=g3_priv,
        compensating_controls=("Audit log monitoring enabled",),
        auto_enroll=False,
    )
    ctx_forged = make_test_context(obl, (), (), exceptions=(exc_forged_human,))
    pol = Policy(
        "POL-001", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )
    with pytest.raises(InvalidExceptionError, match="does not match Gate 3 Authority Root identity"):
        evaluate_policy(pol, ctx_forged)

    # 2. Gate3 key used with authoritative Gate 3 identity -> ACCEPTED
    exc_valid_g3 = _sign_test_exception(
        exception_id="EXC-002",
        obligation_id="OBL-001",
        policy_id="POL-001",
        justification="Gate 3 authority signed exception for emergency deployment.",
        actor_id="Gate3AuthoritativeVerifier",
        actor_role="CERTIFICATE_AUTHORITY",
        private_key=g3_priv,
        compensating_controls=("Audit log monitoring enabled",),
        auto_enroll=False,
    )
    ctx_valid = make_test_context(obl, (), (), exceptions=(exc_valid_g3,))
    decision = evaluate_policy(pol, ctx_valid)
    assert decision.decision == PolicyDecisionType.ALLOW
    assert "EXC-002" in decision.exceptions_applied
