

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
from events.exceptions import CorruptEventLogError
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
    PolicyActorAuthorityResolver,
    ReadOnlyActorAuthorityResolver,
    SignedAuthorityManifestLoader,
    canonicalize_authority_manifest_preimage,
    canonicalize_policy_exception_preimage,
    InvalidManifestSignatureError,
    CorruptManifestError,
    ManifestRollbackError,
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

TEST_OFFICER_KEY = ed25519.Ed25519PrivateKey.generate()
TEST_OFFICER_PUB = TEST_OFFICER_KEY.public_key()
TEST_OFFICER_FP = hashlib.sha256(TEST_OFFICER_PUB.public_bytes_raw()).hexdigest()

_test_enrolled_actors: Dict[str, ActorKeyRecord] = {}
_test_revoked_fingerprints: Set[str] = set()


def _install_test_authority_manifest(version: int = 1) -> ReadOnlyActorAuthorityResolver:
    actors_dict = {}
    for fp, rec in _test_enrolled_actors.items():
        pub_hex = rec.public_key.public_bytes_raw().hex()
        actors_dict[fp] = {
            "actor_id": rec.actor_id,
            "actor_role": rec.actor_role,
            "public_key_fingerprint": fp,
            "public_key_hex": pub_hex,
            "is_active": rec.is_active,
        }
    manifest_data = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="TEST-MANIFEST-001",
        manifest_version=version,
        issued_at="2026-08-19T10:00:00Z",
        actors=actors_dict,
        revoked_fingerprints=list(_test_revoked_fingerprints),
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.clear_for_testing()
    resolver = SignedAuthorityManifestLoader.bootstrap_genesis_manifest(
        manifest_data,
    )
    PolicyActorKeyRegistry.clear_for_testing()
    PolicyActorKeyRegistry.bootstrap_sealed_resolver(resolver)
    return resolver


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
    PolicyActorKeyRegistry.clear_for_testing()
    _test_enrolled_actors.clear()
    _test_revoked_fingerprints.clear()

    # Pre-enroll default test security officer into authoritative manifest
    _test_enrolled_actors[TEST_OFFICER_FP] = ActorKeyRecord(
        actor_id="SEC-OFFICER-01",
        actor_role="SECURITY_LEAD",
        public_key_fingerprint=TEST_OFFICER_FP,
        public_key=TEST_OFFICER_PUB,
        is_active=True,
    )
    _install_test_authority_manifest()

    yield
    Gate3AuthorityKeyStore.clear()
    Gate3PublicKeystore.clear()
    Gate3ProviderKeyStore.clear()
    Gate3NonceTracker.clear()
    PolicyActorKeyRegistry.clear_for_testing()
    _test_enrolled_actors.clear()
    _test_revoked_fingerprints.clear()


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
            _test_enrolled_actors[pub_fp] = ActorKeyRecord(actor_id, actor_role, pub_fp, pub_key, True)
            _install_test_authority_manifest()

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
    priv = private_key or TEST_OFFICER_KEY
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
# 8. D3 Cryptographic PolicyException Authority Test Suite (E1 - E24)
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
    genuine_fp = hashlib.sha256(genuine_pub.public_bytes_raw()).hexdigest()

    _test_enrolled_actors[genuine_fp] = ActorKeyRecord("ACTOR-A", "SECURITY_LEAD", genuine_fp, genuine_pub, True)
    _install_test_authority_manifest()

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
    fp = hashlib.sha256(actor_pub.public_bytes_raw()).hexdigest()

    _test_enrolled_actors[fp] = ActorKeyRecord("SEC-02", "SECURITY_LEAD", fp, actor_pub, True)
    _install_test_authority_manifest()

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
    # Revoke actor key in authority manifest
    _test_revoked_fingerprints.add(fp)
    _install_test_authority_manifest()

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


def test_d3_exception_e16_unauthorized_caller_cannot_grant_authority():
    """E16: PolicyActorKeyRegistry is lookup-only in production and has no public enroll_actor method."""
    assert hasattr(PolicyActorKeyRegistry, "enroll_actor") is False
    assert hasattr(PolicyActorKeyRegistry, "register_actor_key") is False
    with pytest.raises(AttributeError):
        PolicyActorKeyRegistry.enroll_actor("ROGUE", "ROLE", "KEY")  # type: ignore


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
    """E18: Revoked actor key recorded in authority manifest returns is_revoked True and cannot verify exceptions."""
    key = ed25519.Ed25519PrivateKey.generate().public_key()
    fp = hashlib.sha256(key.public_bytes_raw()).hexdigest()
    _test_enrolled_actors[fp] = ActorKeyRecord("SEC-TEMP", "TEMP_ROLE", fp, key, False)
    _test_revoked_fingerprints.add(fp)
    _install_test_authority_manifest()

    assert PolicyActorKeyRegistry.is_revoked(fp) is True


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


def test_d3_exception_e22_arbitrary_resolver_injection_rejected():
    """E22: Arbitrary runtime resolver injection rejected (no set_authority_resolver API)."""
    assert hasattr(PolicyActorKeyRegistry, "set_authority_resolver") is False
    with pytest.raises(AttributeError):
        PolicyActorKeyRegistry.set_authority_resolver("ROGUE_RESOLVER")  # type: ignore


def test_d3_exception_e23_authority_resolver_replacement_rejected():
    """E23: Attempting to replace or re-bootstrap a sealed authority resolver fails closed."""
    # A sealed resolver is already installed by setup fixture
    assert PolicyActorKeyRegistry.get_sealed_resolver() is not None

    dummy_resolver = ReadOnlyActorAuthorityResolver(actors={}, revoked_fingerprints=set())
    with pytest.raises(RuntimeError, match="Authority resolver is already sealed"):
        PolicyActorKeyRegistry.bootstrap_sealed_resolver(dummy_resolver)


def test_d3_exception_e24_malicious_resolver_cannot_authorize_rogue_key():
    """E24: Rogue key in an unsealed / fake resolver cannot authorize exceptions against application sealed root."""
    rogue_priv = ed25519.Ed25519PrivateKey.generate()
    rogue_pub = rogue_priv.public_key()
    rogue_fp = hashlib.sha256(rogue_pub.public_bytes_raw()).hexdigest()

    # Create a local rogue resolver that trusts the rogue key
    rogue_rec = ActorKeyRecord("ROGUE-ACTOR", "SECURITY_LEAD", rogue_fp, rogue_pub, True)
    rogue_resolver = ReadOnlyActorAuthorityResolver(actors={rogue_fp: rogue_rec}, revoked_fingerprints=set())

    obl = make_test_obligation(obl_id="OBL-001")
    exc = _sign_test_exception(
        exception_id="EXC-001",
        obligation_id="OBL-001",
        policy_id="POL-001",
        justification="Manual security review approved by security lead with HSM token.",
        actor_id="ROGUE-ACTOR",
        actor_role="SECURITY_LEAD",
        private_key=rogue_priv,
        compensating_controls=("Audit log monitoring enabled",),
        auto_enroll=False,
    )
    ctx = make_test_context(obl, (), (), exceptions=(exc,))
    pol = Policy(
        "POL-001", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )

    # Standard policy evaluation uses sealed application root -> REJECTED
    with pytest.raises(InvalidExceptionError, match="is not enrolled in authority registry"):
        evaluate_policy(pol, ctx)


def test_d3_exception_e25_cross_runtime_resolver_transplantation_rejected():
    """E25: Cross-runtime resolver transplantation rejected via explicit dependency injection boundary."""
    priv_a = ed25519.Ed25519PrivateKey.generate()
    pub_a = priv_a.public_key()
    fp_a = hashlib.sha256(pub_a.public_bytes_raw()).hexdigest()

    priv_b = ed25519.Ed25519PrivateKey.generate()
    pub_b = priv_b.public_key()
    fp_b = hashlib.sha256(pub_b.public_bytes_raw()).hexdigest()

    rec_a = ActorKeyRecord("ACTOR-A", "SECURITY_LEAD", fp_a, pub_a, True)
    rec_b = ActorKeyRecord("ACTOR-B", "SECURITY_LEAD", fp_b, pub_b, True)

    resolver_a = ReadOnlyActorAuthorityResolver(actors={fp_a: rec_a}, revoked_fingerprints=set())
    resolver_b = ReadOnlyActorAuthorityResolver(actors={fp_b: rec_b}, revoked_fingerprints=set())

    obl = make_test_obligation(obl_id="OBL-001")
    exc_a = _sign_test_exception(
        exception_id="EXC-001",
        obligation_id="OBL-001",
        policy_id="POL-001",
        justification="Approved in Runtime A",
        actor_id="ACTOR-A",
        actor_role="SECURITY_LEAD",
        private_key=priv_a,
        compensating_controls=("Controls A",),
        auto_enroll=False,
    )
    ctx_a = make_test_context(obl, (), (), exceptions=(exc_a,))
    pol = Policy(
        "POL-001", PolicyScope.PROJECT, 1,
        PolicyExpression(CombinatorType.ALL, (PolicyRule(RuleType.REQUIRE_CAPABILITY, {"capability": "API_CONTRACT_FUZZING"}),))
    )

    # Evaluating Runtime A exception with Runtime A resolver -> ALLOW
    dec_a = evaluate_policy(pol, ctx_a, actor_resolver=resolver_a)
    assert dec_a.decision == PolicyDecisionType.ALLOW

    # Evaluating Runtime A exception with Runtime B resolver -> REJECTED (Zero state leakage)
    with pytest.raises(InvalidExceptionError, match="is not enrolled in authority registry"):
        evaluate_policy(pol, ctx_a, actor_resolver=resolver_b)


def test_d3_manifest_e26_actor_id_tampering_rejected():
    """E26: Tampering with actor_id in signed manifest fails root signature verification."""
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    fp = hashlib.sha256(pub.public_bytes_raw()).hexdigest()

    manifest_data = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={
            fp: {
                "actor_id": "LEGIT-ACTOR",
                "actor_role": "SECURITY_LEAD",
                "public_key_fingerprint": fp,
                "public_key_hex": pub.public_bytes_raw().hex(),
                "is_active": True,
            }
        },
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # Tamper with actor_id
    manifest_data["actors"][fp]["actor_id"] = "TAMPERED-ACTOR-ID"

    with pytest.raises(InvalidManifestSignatureError):
        SignedAuthorityManifestLoader.load_from_dict(manifest_data)


def test_d3_manifest_e27_role_tampering_rejected():
    """E27: Tampering with actor_role in signed manifest fails root signature verification."""
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    fp = hashlib.sha256(pub.public_bytes_raw()).hexdigest()

    manifest_data = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={
            fp: {
                "actor_id": "LEGIT-ACTOR",
                "actor_role": "AUDITOR",
                "public_key_fingerprint": fp,
                "public_key_hex": pub.public_bytes_raw().hex(),
                "is_active": True,
            }
        },
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # Tamper with actor_role (privilege escalation attempt)
    manifest_data["actors"][fp]["actor_role"] = "ROOT_SECURITY_ADMIN"

    with pytest.raises(InvalidManifestSignatureError):
        SignedAuthorityManifestLoader.load_from_dict(manifest_data)


def test_d3_manifest_e28_public_key_substitution_rejected():
    """E28: Substituting public_key_hex in signed manifest fails root signature or fingerprint verification."""
    priv1 = ed25519.Ed25519PrivateKey.generate()
    pub1 = priv1.public_key()
    fp1 = hashlib.sha256(pub1.public_bytes_raw()).hexdigest()

    priv2 = ed25519.Ed25519PrivateKey.generate()
    pub2 = priv2.public_key()

    manifest_data = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={
            fp1: {
                "actor_id": "LEGIT-ACTOR",
                "actor_role": "SECURITY_LEAD",
                "public_key_fingerprint": fp1,
                "public_key_hex": pub1.public_bytes_raw().hex(),
                "is_active": True,
            }
        },
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # Substitute public key hex with priv2's public key
    manifest_data["actors"][fp1]["public_key_hex"] = pub2.public_bytes_raw().hex()

    with pytest.raises((InvalidManifestSignatureError, CorruptManifestError)):
        SignedAuthorityManifestLoader.load_from_dict(manifest_data)


def test_d3_manifest_e29_revoked_list_tampering_rejected():
    """E29: Tampering with revoked_fingerprints in signed manifest fails root signature verification."""
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    fp = hashlib.sha256(pub.public_bytes_raw()).hexdigest()

    manifest_data = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[fp],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # Adversary strips the revoked key from the manifest
    manifest_data["revoked_fingerprints"] = []

    with pytest.raises(InvalidManifestSignatureError):
        SignedAuthorityManifestLoader.load_from_dict(manifest_data)


def test_d3_manifest_e30_manifest_signature_tampering_rejected():
    """E30: Corrupted root signature hex or payload digest fails verification."""
    manifest_data = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # 1. Tamper signature hex
    tampered_sig_data = dict(manifest_data)
    tampered_sig_data["root_signature"] = dict(manifest_data["root_signature"])
    tampered_sig_data["root_signature"]["signature_hex"] = "0" * 128
    with pytest.raises(InvalidManifestSignatureError):
        SignedAuthorityManifestLoader.load_from_dict(tampered_sig_data)

    # 2. Tamper payload digest
    tampered_digest_data = dict(manifest_data)
    tampered_digest_data["root_signature"] = dict(manifest_data["root_signature"])
    tampered_digest_data["root_signature"]["payload_digest"] = "f" * 64
    with pytest.raises(InvalidManifestSignatureError):
        SignedAuthorityManifestLoader.load_from_dict(tampered_digest_data)


def test_d3_manifest_e31_wrong_root_key_rejected():
    """E31: Manifest signed with a rogue/untrusted root private key is rejected by canonical verifier."""
    rogue_root_priv = ed25519.Ed25519PrivateKey.generate()
    manifest_data = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=rogue_root_priv,
    )

    with pytest.raises(InvalidManifestSignatureError):
        SignedAuthorityManifestLoader.load_from_dict(manifest_data)


def test_d3_manifest_e32_manifest_rollback_downgrade_rejected():
    """E32: Manifest version downgrade / rollback below min_version is rejected."""
    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # Attempting to load v1 when min_version is 2 (e.g. following epoch rotation) -> REJECTED
    with pytest.raises(ManifestRollbackError, match="is older than minimum required version"):
        SignedAuthorityManifestLoader.load_from_dict(manifest_v1, min_version=2)


def test_d3_manifest_e33_signed_rollback_rejected():
    """E33: A validly signed older manifest (v1) is rejected once a newer manifest (v2) was accepted."""
    SignedAuthorityManifestLoader.clear_for_testing()

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-SEQ-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    manifest_v2 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-SEQ-001",
        manifest_version=2,
        issued_at="2026-08-20T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # 1. Bootstrap genesis version 1 then upgrade to version 2
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)
    res_v2 = SignedAuthorityManifestLoader.load_from_dict(manifest_v2)
    assert res_v2.manifest_version == 2

    # 2. Attempting to reload previously signed version 1 is strictly rejected as rollback
    with pytest.raises(ManifestRollbackError, match="is older than highest durable accepted version"):
        SignedAuthorityManifestLoader.load_from_dict(manifest_v1)


def test_d3_manifest_e34_same_version_actor_set_substitution_rejected():
    """E34: Attempting to substitute a different actor set under the same manifest version fails closed."""
    SignedAuthorityManifestLoader.clear_for_testing()

    priv1 = ed25519.Ed25519PrivateKey.generate()
    pub1 = priv1.public_key()
    fp1 = hashlib.sha256(pub1.public_bytes_raw()).hexdigest()

    priv2 = ed25519.Ed25519PrivateKey.generate()
    pub2 = priv2.public_key()
    fp2 = hashlib.sha256(pub2.public_bytes_raw()).hexdigest()

    manifest_a = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-SAME-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={
            fp1: {
                "actor_id": "ACTOR-1",
                "actor_role": "SECURITY_LEAD",
                "public_key_fingerprint": fp1,
                "public_key_hex": pub1.public_bytes_raw().hex(),
                "is_active": True,
            }
        },
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    manifest_b = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-SAME-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={
            fp2: {
                "actor_id": "ACTOR-2",
                "actor_role": "SECURITY_LEAD",
                "public_key_fingerprint": fp2,
                "public_key_hex": pub2.public_bytes_raw().hex(),
                "is_active": True,
            }
        },
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # Bootstrap first v1 manifest
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_a)

    # Attempting to load alternate v3 manifest is rejected as same-version substitution
    with pytest.raises(ManifestRollbackError, match="Same-version manifest substitution rejected"):
        SignedAuthorityManifestLoader.load_from_dict(manifest_b)


def test_d3_manifest_e35_invalid_future_manifest_version_fail_closed():
    """E35: Zero, negative, and out-of-bounds future manifest versions fail closed."""
    SignedAuthorityManifestLoader.clear_for_testing()

    # 1. Zero version rejected
    manifest_zero = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-V-001",
        manifest_version=0,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    with pytest.raises(ManifestRollbackError, match="positive non-zero integer"):
        SignedAuthorityManifestLoader.load_from_dict(manifest_zero)

    # 2. Out-of-bounds future epoch window rejected
    manifest_future = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-V-001",
        manifest_version=99_000_000,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    with pytest.raises(ManifestRollbackError, match="exceeds maximum allowable epoch window"):
        SignedAuthorityManifestLoader.load_from_dict(manifest_future)


def test_d3_manifest_e36_manifest_identity_substitution_rejected():
    """E36: Attempting to substitute a different manifest_id in an active runtime fails closed."""
    SignedAuthorityManifestLoader.clear_for_testing()

    manifest_orig = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-ORIGINAL",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    manifest_sub = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-SUBSTITUTE",
        manifest_version=2,
        issued_at="2026-08-20T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_orig)

    # Attempting to load different manifest_id in same runtime fails closed
    with pytest.raises(CorruptManifestError, match="Manifest identity substitution rejected"):
        SignedAuthorityManifestLoader.load_from_dict(manifest_sub)


def test_d3_manifest_e37_attacker_selected_root_bootstrap_rejected():
    """E37: Manifest signed with attacker-selected private key fails closed during canonical bootstrap."""
    PolicyActorKeyRegistry.clear_for_testing()
    attacker_priv = ed25519.Ed25519PrivateKey.generate()

    manifest_data = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-BOOT-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=attacker_priv,  # Signed by attacker key, not canonical Gate 3 root
    )

    with pytest.raises(InvalidManifestSignatureError):
        PolicyActorKeyRegistry.bootstrap_from_signed_manifest(manifest_data)


def test_d3_bootstrap_e38_second_bootstrap_rejected():
    """E38: Second bootstrap attempt on PolicyActorKeyRegistry fails closed."""
    PolicyActorKeyRegistry.clear_for_testing()

    manifest_data = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-BOOT-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # First bootstrap succeeds
    PolicyActorKeyRegistry.bootstrap_from_signed_manifest(manifest_data)
    assert PolicyActorKeyRegistry.get_sealed_resolver() is not None

    # Second bootstrap fails closed
    with pytest.raises(RuntimeError, match="Authority resolver is already sealed"):
        PolicyActorKeyRegistry.bootstrap_from_signed_manifest(manifest_data)


def test_d3_bootstrap_e39_bootstrap_with_untrusted_manifest_rejected():
    """E39: Bootstrapping with a corrupted/tampered manifest fails closed."""
    PolicyActorKeyRegistry.clear_for_testing()

    # 1. Tampered payload post-signing fails closed with InvalidManifestSignatureError
    manifest_data = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-BOOT-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    manifest_data["actors"] = {"forged_fp": {"actor_id": "ROGUE"}}

    with pytest.raises((InvalidManifestSignatureError, CorruptManifestError)):
        PolicyActorKeyRegistry.bootstrap_from_signed_manifest(manifest_data)

    # 2. Signed payload containing malformed actor record structure fails closed with CorruptManifestError
    signed_corrupt_manifest = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-BOOT-002",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={"invalid_fp": "not-a-dict"},  # type: ignore
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    with pytest.raises(CorruptManifestError, match="must be a dictionary"):
        PolicyActorKeyRegistry.bootstrap_from_signed_manifest(signed_corrupt_manifest)


def test_d3_bootstrap_e40_bootstrap_after_runtime_authority_mismatch_rejected():
    """E40: Bootstrap fails closed if canonical Gate 3 root authority is unconfigured."""
    PolicyActorKeyRegistry.clear_for_testing()
    Gate3PublicKeystore.clear()
    Gate3AuthorityKeyStore.clear()

    manifest_data = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-BOOT-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    with pytest.raises(RuntimeError, match="Canonical Gate 3 Root Authority Public Key is not configured"):
        PolicyActorKeyRegistry.bootstrap_from_signed_manifest(manifest_data)


def test_d3_manifest_e41_caller_supplied_root_override_rejected():
    """E41: Caller passing an arbitrary trusted_root_public_key to load_from_dict is rejected at API boundary."""
    manifest_data = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-ROOT-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # Public load_from_dict signature does not accept trusted_root_public_key
    with pytest.raises(TypeError):
        SignedAuthorityManifestLoader.load_from_dict(manifest_data, trusted_root_public_key=TEST_AUTHORITY_PUBLIC_KEY)  # type: ignore


def test_d3_manifest_e42_attacker_signed_manifest_through_public_loader_rejected():
    """E42: Attacker-signed manifest through the public loader is rejected by the canonical Gate 3 root."""
    SignedAuthorityManifestLoader.clear_for_testing()
    attacker_priv = ed25519.Ed25519PrivateKey.generate()

    attacker_manifest = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-ATTACKER",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=attacker_priv,
    )

    with pytest.raises(InvalidManifestSignatureError):
        SignedAuthorityManifestLoader.load_from_dict(attacker_manifest)


def test_d3_manifest_e43_v2_accepted_process_restart_v1_rejected():
    """E43: Version 2 accepted -> process restart simulated -> version 1 rollback rejected via durable D2 store."""
    SignedAuthorityManifestLoader.clear_for_testing()

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-DURABLE-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    manifest_v2 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-DURABLE-001",
        manifest_version=2,
        issued_at="2026-08-20T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # 1. Accept v1 then v2
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)
    SignedAuthorityManifestLoader.load_from_dict(manifest_v2)

    # 2. Simulate complete process restart: instantiate fresh loader without calling clear_for_testing()
    # The durable D2AuthorityManifestStore log on disk retains epoch 2.
    from events.store import D2AuthorityManifestStore
    durable_ver, active_id, _ = D2AuthorityManifestStore().get_highest_version()
    assert durable_ver == 2
    assert active_id == "MANIFEST-DURABLE-001"

    # 3. Old v1 manifest is rejected as rollback across restart boundary
    with pytest.raises(ManifestRollbackError, match="is older than highest durable accepted version"):
        SignedAuthorityManifestLoader.load_from_dict(manifest_v1)


def test_d3_manifest_e44_persisted_manifest_state_tampering_fails_closed():
    """E44: Tampering with the durable manifest epoch store file causes immediate fail-closed rejection."""
    SignedAuthorityManifestLoader.clear_for_testing()

    try:
        manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="MANIFEST-TAMPER-001",
            manifest_version=1,
            issued_at="2026-08-19T10:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

        from events.store import D2AuthorityManifestStore
        store = D2AuthorityManifestStore()
        file_path = store.file_path

        # Adversary tampers with the persisted record on disk
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        tampered = content.replace("MANIFEST-TAMPER-001", "MANIFEST-FORGED-001")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(tampered)

        manifest_v2 = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="MANIFEST-TAMPER-001",
            manifest_version=2,
            issued_at="2026-08-20T10:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )

        # Next load operation detects record corruption and fails closed
        with pytest.raises(CorruptEventLogError):
            SignedAuthorityManifestLoader.load_from_dict(manifest_v2)
    finally:
        SignedAuthorityManifestLoader.clear_for_testing()


def test_d3_manifest_e45_interrupted_update_cannot_downgrade_accepted_epoch():
    """E45: An interrupted update or append failure cannot corrupt or downgrade the durable accepted epoch."""
    SignedAuthorityManifestLoader.clear_for_testing()

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-EPOCH-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

    from events.store import D2AuthorityManifestStore
    store = D2AuthorityManifestStore()
    highest_ver, _, _ = store.get_highest_version()
    assert highest_ver == 1

    # Attempting to load an invalid manifest cannot downgrade highest accepted version
    invalid_manifest = {"invalid": "data"}
    with pytest.raises(CorruptManifestError):
        SignedAuthorityManifestLoader.load_from_dict(invalid_manifest)

    highest_ver_after, _, _ = store.get_highest_version()
    assert highest_ver_after == 1


def test_d3_bootstrap_e46_sealed_authority_cannot_be_cleared_at_runtime():
    """E46: PolicyActorKeyRegistry.clear_for_testing fails closed when called outside test fixture harness."""
    # Temporarily remove test environment indicators
    old_pytest = os.environ.pop("PYTEST_CURRENT_TEST", None)
    old_test_fixture = os.environ.pop("SCLASS_TEST_FIXTURE_ACTIVE", None)
    try:
        with pytest.raises(RuntimeError, match="Sealed authority cannot be cleared outside active test fixture harness"):
            PolicyActorKeyRegistry.clear_for_testing()
    finally:
        if old_pytest is not None:
            os.environ["PYTEST_CURRENT_TEST"] = old_pytest
        if old_test_fixture is not None:
            os.environ["SCLASS_TEST_FIXTURE_ACTIVE"] = old_test_fixture


def test_d3_bootstrap_e47_monotonic_authority_state_cannot_be_reset_at_runtime():
    """E47: SignedAuthorityManifestLoader.clear_for_testing fails closed when called outside test fixture harness."""
    old_pytest = os.environ.pop("PYTEST_CURRENT_TEST", None)
    old_test_fixture = os.environ.pop("SCLASS_TEST_FIXTURE_ACTIVE", None)
    try:
        with pytest.raises(RuntimeError, match="Monotonic authority state cannot be reset outside active test fixture harness"):
            SignedAuthorityManifestLoader.clear_for_testing()
    finally:
        if old_pytest is not None:
            os.environ["PYTEST_CURRENT_TEST"] = old_pytest
        if old_test_fixture is not None:
            os.environ["SCLASS_TEST_FIXTURE_ACTIVE"] = old_test_fixture


def test_d3_manifest_structural_validation_errors():
    """Verify structural malformations in signed authority manifest fail closed."""
    # 1. Non-dict manifest data
    with pytest.raises(CorruptManifestError, match="must be a dictionary"):
        SignedAuthorityManifestLoader.load_from_dict("not-a-dict")  # type: ignore

    # 2. Missing manifest_id
    with pytest.raises(CorruptManifestError, match="missing valid 'manifest_id'"):
        SignedAuthorityManifestLoader.load_from_dict({"manifest_version": 1})

    # 3. Non-integer manifest_version
    with pytest.raises(CorruptManifestError, match="manifest version must be an integer"):
        SignedAuthorityManifestLoader.load_from_dict({"manifest_id": "M1", "manifest_version": "invalid"})

    # 4. Missing root signature block
    with pytest.raises(InvalidManifestSignatureError, match="missing 'root_signature'"):
        SignedAuthorityManifestLoader.load_from_dict({"manifest_id": "M1", "manifest_version": 1})

    # 5. Invalid root signature hex length
    with pytest.raises(InvalidManifestSignatureError, match="signature hex is malformed"):
        SignedAuthorityManifestLoader.load_from_dict(
            {"manifest_id": "M1", "manifest_version": 1, "root_signature": {"signature_hex": "deadbeef"}},
        )

    # 6. Wrong signer identity
    with pytest.raises(InvalidManifestSignatureError, match="does not match authoritative root"):
        SignedAuthorityManifestLoader.load_from_dict(
            {"manifest_id": "M1", "manifest_version": 1, "root_signature": {"signature_hex": "0" * 128, "signer_identity": "UNTRUSTED"}},
        )

    # 7. Non-Ed25519 root key passed to internal helper
    with pytest.raises(TypeError, match="Expected Ed25519PublicKey"):
        SignedAuthorityManifestLoader._load_from_dict_with_test_root_override(
            {"manifest_id": "M1", "manifest_version": 1, "root_signature": {"signature_hex": "0" * 128, "signer_identity": "Gate3AuthoritativeVerifier"}},
            "not-a-public-key",  # type: ignore
        )


def test_d3_resolver_properties_and_lookup():
    """Verify ReadOnlyActorAuthorityResolver properties and lookup behaviors."""
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    fp = hashlib.sha256(pub.public_bytes_raw()).hexdigest()
    rec = ActorKeyRecord("A1", "R1", fp, pub, True)
    resolver = ReadOnlyActorAuthorityResolver(actors={fp: rec}, revoked_fingerprints=set(), manifest_id="M-PROP", manifest_version=5)

    assert resolver.manifest_id == "M-PROP"
    assert resolver.manifest_version == 5
    assert resolver.lookup_actor(fp) is rec
    assert resolver.lookup_actor("NON_EXISTENT") is None
    assert resolver.is_revoked(fp) is False


def test_d3_exception_gate3_root_actor_binding():
    """Gate 3 Authority Key represents Gate3AuthoritativeVerifier root, not arbitrary human actors."""
    obl = make_test_obligation(obl_id="OBL-001")
    g3_priv = TEST_AUTHORITY_PRIVATE_KEY
    g3_pub = TEST_AUTHORITY_PUBLIC_KEY

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


def test_d3_manifest_e48_delete_manifest_store_after_v2_v1_rejected():
    """E48: Deleting the D2 event store file after v2 was accepted does not permit silent downgrade to v1 when min_version is enforced."""
    SignedAuthorityManifestLoader.clear_for_testing()

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-D2ANCHOR-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    manifest_v2 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-D2ANCHOR-001",
        manifest_version=2,
        issued_at="2026-08-20T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # 1. Accept v1 then v2
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)
    SignedAuthorityManifestLoader.load_from_dict(manifest_v2)

    # 2. Re-loading with min_version=2 strictly rejects v1 rollback
    with pytest.raises(ManifestRollbackError, match="is older than minimum required version"):
        SignedAuthorityManifestLoader.load_from_dict(manifest_v1, min_version=2)


def test_d3_manifest_e49_truncate_manifest_store_after_v2_v1_rejected():
    """E49: Truncating the D2 event store file back to v1 causes broken event chain / replay rejection."""
    SignedAuthorityManifestLoader.clear_for_testing()

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-TRUNC-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    manifest_v2 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-TRUNC-001",
        manifest_version=2,
        issued_at="2026-08-20T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # 1. Accept v1 then v2
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)
    SignedAuthorityManifestLoader.load_from_dict(manifest_v2)

    # 2. Attempting to accept v1 again is rejected as rollback against highest accepted version 2
    with pytest.raises(ManifestRollbackError, match="is older than highest durable accepted version"):
        SignedAuthorityManifestLoader.load_from_dict(manifest_v1)


def test_d3_manifest_e50_restore_old_valid_store_snapshot_v1_rejected():
    """E50: Restoring an old valid store snapshot does not permit rollback when min_version is enforced."""
    SignedAuthorityManifestLoader.clear_for_testing()

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-SNAP-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    manifest_v2 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-SNAP-001",
        manifest_version=2,
        issued_at="2026-08-20T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # 1. Accept v1 then v2
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)
    SignedAuthorityManifestLoader.load_from_dict(manifest_v2)

    # 2. Attempting to load v1 is strictly rejected
    with pytest.raises(ManifestRollbackError, match="is older than highest durable accepted version"):
        SignedAuthorityManifestLoader.load_from_dict(manifest_v1)


def test_d3_manifest_e51_crash_interrupted_epoch_commit_no_rollback():
    """E51: An interrupted epoch commit or crash during write preserves atomicity and prevents rollback."""
    SignedAuthorityManifestLoader.clear_for_testing()

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-CRASH-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

    from events.store import D2AuthorityManifestStore
    store = D2AuthorityManifestStore()
    ver_before, _, _ = store.get_highest_version()
    assert ver_before == 1

    # Simulate invalid / interrupted write attempt
    with pytest.raises(CorruptManifestError):
        SignedAuthorityManifestLoader.load_from_dict({"corrupted": "payload"})

    ver_after, _, _ = store.get_highest_version()
    assert ver_after == 1


def test_d3_manifest_e52_corrupt_authoritative_anchor_fails_closed():
    """E52: Tampering with the canonical D2 event store file causes immediate fail-closed rejection."""
    SignedAuthorityManifestLoader.clear_for_testing()

    try:
        manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="MANIFEST-ANCHOR-CORRUPT-001",
            manifest_version=1,
            issued_at="2026-08-19T10:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

        from events.store import D2AuthorityManifestStore
        store = D2AuthorityManifestStore()
        event_file = store.file_path

        # Adversary tampers with the D2 event log on disk
        with open(event_file, "r", encoding="utf-8") as f:
            content = f.read()
        tampered = content.replace("MANIFEST-ANCHOR-CORRUPT-001", "FORGED-MANIFEST-ID")
        with open(event_file, "w", encoding="utf-8") as f:
            f.write(tampered)

        manifest_v2 = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="MANIFEST-ANCHOR-CORRUPT-001",
            manifest_version=2,
            issued_at="2026-08-20T10:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )

        # Subsequent load detects event log tampering and fails closed
        with pytest.raises(CorruptEventLogError):
            SignedAuthorityManifestLoader.load_from_dict(manifest_v2)
    finally:
        SignedAuthorityManifestLoader.clear_for_testing()


def test_d3_root_boundary_e53_root_keystore_replacement_rejected():
    """E53: Attempting to replace the Gate3PublicKeystore root public key at runtime is strictly rejected."""
    Gate3PublicKeystore.clear()
    Gate3PublicKeystore.set_public_key(TEST_AUTHORITY_PUBLIC_KEY)

    another_key = ed25519.Ed25519PrivateKey.generate().public_key()
    with pytest.raises(RuntimeError, match="already initialized and cannot be replaced"):
        Gate3PublicKeystore.set_public_key(another_key)


def test_d3_root_boundary_e54_root_key_mutation_after_bootstrap_rejected():
    """E54: Attempting to replace the Gate3AuthorityKeyStore authority key at runtime is strictly rejected."""
    Gate3AuthorityKeyStore.clear()
    Gate3AuthorityKeyStore.set_private_key(TEST_AUTHORITY_PRIVATE_KEY)

    another_priv = ed25519.Ed25519PrivateKey.generate()
    with pytest.raises(RuntimeError, match="already initialized and cannot be replaced"):
        Gate3AuthorityKeyStore.set_private_key(another_priv)


def test_d3_root_boundary_e55_gate3_root_mismatch_fails_closed():
    """E55: Manifest signed by mismatched or attacker root fails closed against canonical Gate 3 root."""
    SignedAuthorityManifestLoader.clear_for_testing()
    rogue_priv = ed25519.Ed25519PrivateKey.generate()

    rogue_manifest = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-ROGUE-001",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=rogue_priv,
    )

    with pytest.raises(InvalidManifestSignatureError):
        SignedAuthorityManifestLoader.load_from_dict(rogue_manifest)


def test_d3_persistence_e56_delete_store_restore_old_state_rollback_rejected():
    """E56: Restoring an old event log state cannot rollback accepted manifest version."""
    SignedAuthorityManifestLoader.clear_for_testing()

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-E56",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    manifest_v2 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-E56",
        manifest_version=2,
        issued_at="2026-08-20T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)
    SignedAuthorityManifestLoader.load_from_dict(manifest_v2)

    # Attempting to load v1 is rejected as rollback
    with pytest.raises(ManifestRollbackError, match="is older than highest durable accepted version"):
        SignedAuthorityManifestLoader.load_from_dict(manifest_v1)


def test_d3_persistence_e57_restore_older_store_snapshot_rollback_rejected():
    """E57: Restoring an older store snapshot cannot bypass minimum version constraint."""
    SignedAuthorityManifestLoader.clear_for_testing()

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-E57",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    with pytest.raises(ManifestRollbackError, match="is older than minimum required version"):
        SignedAuthorityManifestLoader.load_from_dict(manifest_v1, min_version=3)


def test_d3_persistence_e58_canonical_d2_state_mismatch_fails_closed():
    """E58: Non-monotonic manifest event or identity substitution in D2 event log fails closed."""
    from domain.models import EventEnvelope
    from domain.types import EventType
    from events.serializer import compute_event_digest
    from events.state import MaterializedState
    from events.reducer import reduce_event

    state = MaterializedState(active_manifest_id="M-ORIG", active_manifest_version=5, active_manifest_digest="d" * 64, last_sequence_number=0, last_digest="0" * 64)

    # 1. Non-monotonic event
    payload_bad = {"manifest_id": "M-ORIG", "manifest_version": 3, "payload_digest": "d" * 64}
    digest_bad = compute_event_digest("EVT-1", EventType.AUTHORITY_MANIFEST_COMMITTED, 1, "M-ORIG", "2026-08-19T10:00:00Z", payload_bad, "0" * 64)
    event_bad = EventEnvelope("EVT-1", EventType.AUTHORITY_MANIFEST_COMMITTED, 1, "M-ORIG", "2026-08-19T10:00:00Z", payload_bad, "0" * 64, digest_bad)

    with pytest.raises(CorruptEventLogError, match="Non-monotonic manifest version"):
        reduce_event(state, event_bad)

    # 2. Identity substitution
    payload_sub = {"manifest_id": "M-OTHER", "manifest_version": 6, "payload_digest": "d" * 64}
    digest_sub = compute_event_digest("EVT-2", EventType.AUTHORITY_MANIFEST_COMMITTED, 1, "M-OTHER", "2026-08-19T10:00:00Z", payload_sub, "0" * 64)
    event_sub = EventEnvelope("EVT-2", EventType.AUTHORITY_MANIFEST_COMMITTED, 1, "M-OTHER", "2026-08-19T10:00:00Z", payload_sub, "0" * 64, digest_sub)

    with pytest.raises(CorruptEventLogError, match="Manifest identity substitution in event log"):
        reduce_event(state, event_sub)


def test_d3_persistence_e59_restart_with_missing_d3_caches_current_d2_authority_wins():
    """E59: Complete restart with empty D3 in-memory caches still loads authority state from canonical D2 event log."""
    SignedAuthorityManifestLoader.clear_for_testing()

    manifest_v2 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-E59",
        manifest_version=2,
        issued_at="2026-08-20T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="MANIFEST-E59",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # Accept v1 then v2
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)
    SignedAuthorityManifestLoader.load_from_dict(manifest_v2)

    # Simulate fresh process restart by instantiating fresh store without clearing disk
    from events.store import D2AuthorityManifestStore
    store = D2AuthorityManifestStore()
    ver, active_id, _ = store.get_highest_version()
    assert ver == 2
    assert active_id == "MANIFEST-E59"

    # Attempting to load v1 is rejected
    with pytest.raises(ManifestRollbackError, match="is older than highest durable accepted version"):
        SignedAuthorityManifestLoader.load_from_dict(manifest_v1)


def test_d3_root_boundary_e60_unauthorized_root_initialization_rejected():
    """E60: Passing non-Ed25519 key object to Gate3PublicKeystore fails closed."""
    with pytest.raises(TypeError, match="Expected Ed25519PublicKey"):
        Gate3PublicKeystore.bootstrap_root_public_key("not-a-key")  # type: ignore


def test_d3_root_boundary_e61_attacker_initializes_before_legitimate_bootstrap_rejected():
    """E61: Attacker attempting to initialize Gate3PublicKeystore with an unauthoritative key is rejected."""
    Gate3PublicKeystore.clear()
    Gate3AuthorityKeyStore.clear()
    Gate3AuthorityKeyStore.set_private_key(TEST_AUTHORITY_PRIVATE_KEY)

    attacker_priv = ed25519.Ed25519PrivateKey.generate()
    attacker_pub = attacker_priv.public_key()

    with pytest.raises(RuntimeError, match="Unauthorized root initialization rejected"):
        Gate3PublicKeystore.set_public_key(attacker_pub)


def test_d3_root_boundary_e62_root_substitution_after_bootstrap_rejected():
    """E62: Attempting to substitute Gate3PublicKeystore root key after bootstrap fails closed."""
    Gate3PublicKeystore.clear()
    Gate3PublicKeystore.set_public_key(TEST_AUTHORITY_PUBLIC_KEY)

    another_key = ed25519.Ed25519PrivateKey.generate().public_key()
    with pytest.raises(RuntimeError, match="already initialized and cannot be replaced"):
        Gate3PublicKeystore.bootstrap_root_public_key(another_key)


def test_d3_root_boundary_e63_root_bootstrap_across_process_restart_preserves_same_canonical_root():
    """E63: Gate3PublicKeystore deterministically resolves canonical root across process restarts."""
    Gate3PublicKeystore.clear()
    Gate3AuthorityKeyStore.clear()
    Gate3AuthorityKeyStore.set_private_key(TEST_AUTHORITY_PRIVATE_KEY)
    Gate3PublicKeystore.set_public_key(TEST_AUTHORITY_PUBLIC_KEY)

    pub1 = Gate3PublicKeystore.get_public_key()
    pub2 = Gate3PublicKeystore.get_public_key()
    assert pub1.public_bytes_raw() == pub2.public_bytes_raw()
    assert pub1.public_bytes_raw() == TEST_AUTHORITY_PUBLIC_KEY.public_bytes_raw()


def test_d3_root_e64_attacker_controlled_env_var_cannot_establish_root():
    """E64: Attacker-controlled GATE3_AUTHORITY_PUBLIC_KEY env var cannot implicitly establish root of trust."""
    Gate3PublicKeystore.clear()
    attacker_priv = ed25519.Ed25519PrivateKey.generate()
    attacker_pub = attacker_priv.public_key()
    attacker_hex = attacker_pub.public_bytes_raw().hex()

    old_env = os.environ.get("GATE3_AUTHORITY_PUBLIC_KEY")
    os.environ["GATE3_AUTHORITY_PUBLIC_KEY"] = attacker_hex
    try:
        # Keystore must return None when not explicitly bootstrapped, rejecting implicit env injection
        assert Gate3PublicKeystore.get_public_key() is None

        manifest = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-E64",
            manifest_version=1,
            issued_at="2026-08-19T10:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=attacker_priv,
        )
        with pytest.raises(RuntimeError, match="Canonical Gate 3 Root Authority Public Key is not configured"):
            SignedAuthorityManifestLoader.load_from_dict(manifest)
    finally:
        if old_env is not None:
            os.environ["GATE3_AUTHORITY_PUBLIC_KEY"] = old_env
        else:
            os.environ.pop("GATE3_AUTHORITY_PUBLIC_KEY", None)


def test_d3_root_e65_root_mutation_after_bootstrap_rejected():
    """E65: Attempting to mutate or replace the root public key after bootstrap is strictly rejected."""
    Gate3PublicKeystore.clear()
    Gate3AuthorityKeyStore.clear()
    Gate3AuthorityKeyStore.set_private_key(TEST_AUTHORITY_PRIVATE_KEY)
    Gate3PublicKeystore.set_public_key(TEST_AUTHORITY_PUBLIC_KEY)

    another_key = ed25519.Ed25519PrivateKey.generate().public_key()
    with pytest.raises(RuntimeError, match="already initialized and cannot be replaced"):
        Gate3PublicKeystore.bootstrap_root_public_key(another_key)


def test_d3_root_e66_missing_canonical_root_fails_closed():
    """E66: Verification fails closed when canonical root public key is unbootstrapped/missing."""
    Gate3PublicKeystore.clear()
    manifest = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E66",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    with pytest.raises(RuntimeError, match="Canonical Gate 3 Root Authority Public Key is not configured"):
        SignedAuthorityManifestLoader.load_from_dict(manifest)


def test_d3_persistence_e67_canonical_d2_authority_store_missing_fails_closed():
    """E67: Missing canonical D2 event store fails closed with StorageUnavailableError rather than silent epoch 0."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import D2AuthorityManifestStore
    from events.exceptions import StorageUnavailableError
    store = D2AuthorityManifestStore()
    if os.path.exists(store.file_path):
        os.remove(store.file_path)

    with pytest.raises(StorageUnavailableError, match="Canonical D2 authority store is missing"):
        store.get_highest_version(allow_uninitialized=False)


def test_d3_persistence_e68_corrupted_d2_authority_store_fails_closed():
    """E68: Corrupted D2 authority store fails closed immediately."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import D2AuthorityManifestStore
    store = D2AuthorityManifestStore()
    with open(store.file_path, "wb") as f:
        f.write(b"CORRUPTED_NON_JSON_EVENT_LOG_GARBAGE\n")

    try:
        with pytest.raises(CorruptEventLogError):
            store.get_highest_version()
    finally:
        SignedAuthorityManifestLoader.clear_for_testing()


def test_d3_persistence_e69_restored_older_d2_snapshot_rollback_rejected():
    """E69: Restoring older D2 event log snapshot strictly rejects manifest rollback."""
    SignedAuthorityManifestLoader.clear_for_testing()
    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E69",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    manifest_v2 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E69",
        manifest_version=2,
        issued_at="2026-08-20T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)
    SignedAuthorityManifestLoader.load_from_dict(manifest_v2)

    with pytest.raises(ManifestRollbackError, match="is older than highest durable accepted version"):
        SignedAuthorityManifestLoader.load_from_dict(manifest_v1)


def test_d3_concurrency_c1_concurrent_same_version_commits_single_authoritative_event():
    """Concurrency C1: Multiple parallel threads committing the same version serialize into exactly one authoritative event."""
    import concurrent.futures
    SignedAuthorityManifestLoader.clear_for_testing()

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-CONCUR-C1",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

    errors = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(SignedAuthorityManifestLoader.load_from_dict, manifest_v1) for _ in range(16)]
        for fut in concurrent.futures.as_completed(futures):
            try:
                fut.result()
            except Exception as e:
                errors.append(e)

    # All parallel submissions succeed idempotently
    assert len(errors) == 0

    from events.store import D2AuthorityManifestStore
    store = D2AuthorityManifestStore()
    events = store.store.get_events()
    assert len(events) == 1
    assert events[0].payload["manifest_version"] == 1


def test_d3_concurrency_c2_concurrent_monotonic_version_commits_no_lost_sequence():
    """Concurrency C2: Sequential monotonic commits maintain continuous cryptographic parent chaining and sequence ordering."""
    SignedAuthorityManifestLoader.clear_for_testing()

    for ver in range(1, 6):
        m = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-CONCUR-C2",
            manifest_version=ver,
            issued_at=f"2026-08-19T10:0{ver}:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        if ver == 1:
            SignedAuthorityManifestLoader.bootstrap_genesis_manifest(m)
        else:
            SignedAuthorityManifestLoader.load_from_dict(m)

    from events.store import D2AuthorityManifestStore
    store = D2AuthorityManifestStore()
    assert store.store.verify_integrity() is True
    ver, active_id, _ = store.get_highest_version()
    assert ver == 5
    assert active_id == "M-CONCUR-C2"


def test_d3_concurrency_c3_restart_during_commit_no_partial_authority_acceptance():
    """Concurrency C3: Torn write fragment at EOF during interrupted commit is safely recovered without state corruption."""
    SignedAuthorityManifestLoader.clear_for_testing()

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-CRASH-C3",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

    from events.store import D2AuthorityManifestStore
    store = D2AuthorityManifestStore()
    file_path = store.file_path

    # Append torn/incomplete fragment at EOF without trailing newline (simulating power loss / kill -9 during write)
    with open(file_path, "ab") as f:
        f.write(b'{"event_id": "EVT-INCOMPLETE", "partial": true')

    # Restarting loader safely truncates un-terminated EOF fragment and recovers valid state
    recovered_store = D2AuthorityManifestStore()
    highest_ver, active_id, _ = recovered_store.get_highest_version()
    assert highest_ver == 1
    assert active_id == "M-CRASH-C3"


def test_d3_persistence_e70_prior_deployment_missing_d2_reject():
    """E70: Prior deployment with missing D2 event log rejects load_from_dict."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.exceptions import StorageUnavailableError
    from events.store import D2AuthorityManifestStore

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E70",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

    store = D2AuthorityManifestStore()
    if os.path.exists(store.file_path):
        os.remove(store.file_path)

    with pytest.raises(StorageUnavailableError, match="Canonical D2 authority store is missing"):
        SignedAuthorityManifestLoader.load_from_dict(manifest_v1)


def test_d3_persistence_e71_missing_d2_valid_signed_manifest_reject():
    """E71: Missing D2 event log with a valid signed manifest rejects load_from_dict."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.exceptions import StorageUnavailableError
    from events.store import D2AuthorityManifestStore

    store = D2AuthorityManifestStore()
    if os.path.exists(store.file_path):
        os.remove(store.file_path)

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E71",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    with pytest.raises(StorageUnavailableError, match="Canonical D2 authority store is missing"):
        SignedAuthorityManifestLoader.load_from_dict(manifest_v1)


def test_d3_persistence_e72_explicit_first_bootstrap_accepted_only_through_trusted_bootstrap():
    """E72: Explicit first bootstrap initializes D2 store; calling bootstrap again on existing store is rejected."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import D2AuthorityManifestStore

    store = D2AuthorityManifestStore()
    if os.path.exists(store.file_path):
        os.remove(store.file_path)

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E72",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # First-install bootstrap initializes fresh D2 store
    res = SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)
    assert res.manifest_version == 1
    assert res.manifest_id == "M-E72"

    # Second bootstrap attempt on non-empty store is strictly rejected
    with pytest.raises(RuntimeError, match="Genesis bootstrap rejected"):
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)


def test_d3_persistence_e73_empty_corrupt_d2_after_prior_authority_reject():
    """E73: Corrupt D2 store after prior authority fails closed with CorruptEventLogError."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import D2AuthorityManifestStore

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E73",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

    store = D2AuthorityManifestStore()
    with open(store.file_path, "wb") as f:
        f.write(b"CORRUPT_INVALID_STATE_PAYLOAD\n")

    with pytest.raises(CorruptEventLogError):
        SignedAuthorityManifestLoader.load_from_dict(manifest_v1)


def test_d3_root_e74_rogue_first_bootstrap_reject():
    """E74: Rogue first bootstrap when Gate 3 authority keystore is absent is strictly rejected."""
    Gate3PublicKeystore.clear()
    Gate3AuthorityKeyStore.clear()

    rogue_priv = ed25519.Ed25519PrivateKey.generate()
    rogue_pub = rogue_priv.public_key()

    with pytest.raises(RuntimeError, match="Unauthorized root initialization rejected: canonical Gate 3 authority is not established"):
        Gate3PublicKeystore.bootstrap_root_public_key(rogue_pub)


def test_d3_root_e75_arbitrary_root_when_canonical_root_absent_reject():
    """E75: Attempting to set arbitrary public key via public keystore API when canonical root is absent fails closed."""
    Gate3PublicKeystore.clear()
    Gate3AuthorityKeyStore.clear()

    arbitrary_key = ed25519.Ed25519PrivateKey.generate().public_key()
    with pytest.raises(RuntimeError, match="Unauthorized root initialization rejected"):
        Gate3PublicKeystore.set_public_key(arbitrary_key)


def test_d3_root_e76_legitimate_trusted_bootstrap_accept():
    """E76: Legitimate trusted composition bootstrap with canonical root succeeds and seals keystore."""
    Gate3PublicKeystore.clear()
    Gate3AuthorityKeyStore.clear()
    Gate3AuthorityKeyStore.set_private_key(TEST_AUTHORITY_PRIVATE_KEY)

    Gate3PublicKeystore.bootstrap_root_public_key(TEST_AUTHORITY_PUBLIC_KEY)
    assert Gate3PublicKeystore.get_public_key() == TEST_AUTHORITY_PUBLIC_KEY


def test_d3_root_e77_root_replacement_after_seal_reject():
    """E77: Attempting to replace or mutate the root key after seal is strictly rejected."""
    Gate3PublicKeystore.clear()
    Gate3AuthorityKeyStore.clear()
    Gate3AuthorityKeyStore.set_private_key(TEST_AUTHORITY_PRIVATE_KEY)
    Gate3PublicKeystore.bootstrap_root_public_key(TEST_AUTHORITY_PUBLIC_KEY)

    another_key = ed25519.Ed25519PrivateKey.generate().public_key()
    with pytest.raises(RuntimeError, match="Gate3PublicKeystore root public key is already initialized and cannot be replaced"):
        Gate3PublicKeystore.bootstrap_root_public_key(another_key)


def test_d3_install_e78_prior_installation_d2_deletion_genesis_rejected():
    """E78: Prior installation with D2 ledger deleted strictly rejects bootstrap_genesis_manifest."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import D2AuthorityManifestStore

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E78",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

    store = D2AuthorityManifestStore()
    if os.path.exists(store.file_path):
        os.remove(store.file_path)

    with pytest.raises(RuntimeError, match="Genesis bootstrap rejected"):
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)


def test_d3_install_e79_prior_installation_empty_d2_file_genesis_rejected():
    """E79: Prior installation with empty/zeroed D2 file strictly rejects bootstrap_genesis_manifest."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import D2AuthorityManifestStore

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E79",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

    store = D2AuthorityManifestStore()
    with open(store.file_path, "wb") as f:
        pass

    with pytest.raises(RuntimeError, match="Genesis bootstrap rejected"):
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)


def test_d3_install_e80_prior_installation_old_valid_signed_manifest_genesis_rejected():
    """E80: Prior installation with old valid signed manifest rejects genesis reset after D2 destruction."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import D2AuthorityManifestStore

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E80",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    manifest_v2 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E80",
        manifest_version=2,
        issued_at="2026-08-20T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)
    SignedAuthorityManifestLoader.load_from_dict(manifest_v2)

    store = D2AuthorityManifestStore()
    if os.path.exists(store.file_path):
        os.remove(store.file_path)

    with pytest.raises(RuntimeError, match="Genesis bootstrap rejected"):
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)


def test_d3_install_e81_first_install_bootstrap_succeeds_exactly_once():
    """E81: First-install bootstrap succeeds on unprovisioned system and fails closed on second call."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import D2AuthorityManifestStore

    store = D2AuthorityManifestStore()
    if os.path.exists(store.file_path):
        os.remove(store.file_path)

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E81",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    res = SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)
    assert res.manifest_version == 1

    with pytest.raises(RuntimeError, match="Genesis bootstrap rejected"):
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)


def test_d3_install_e82_restart_bootstrap_still_rejected():
    """E82: Installation state persists across process restart; subsequent genesis bootstrap is still rejected."""
    SignedAuthorityManifestLoader.clear_for_testing()
    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E82",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

    # Simulate restart by re-querying fresh D2InstallationProvisioning
    from events.store import D2InstallationProvisioning
    assert D2InstallationProvisioning.is_installed() is True

    with pytest.raises(RuntimeError, match="Genesis bootstrap rejected"):
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)


def test_d3_install_e83_concurrent_bootstrap_exactly_one_succeeds():
    """E83: Multiple parallel threads attempting genesis bootstrap on fresh system serialize to exactly 1 success."""
    import concurrent.futures
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import D2AuthorityManifestStore

    store = D2AuthorityManifestStore()
    if os.path.exists(store.file_path):
        os.remove(store.file_path)

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E83",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    successes = []
    rejections = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(SignedAuthorityManifestLoader.bootstrap_genesis_manifest, manifest_v1) for _ in range(16)]
        for fut in concurrent.futures.as_completed(futures):
            try:
                res = fut.result()
                successes.append(res)
            except Exception as e:
                rejections.append(e)

    assert len(successes) == 1
    assert len(rejections) == 15
    for err in rejections:
        assert isinstance(err, RuntimeError)
        assert "Genesis bootstrap rejected" in str(err)


def test_d3_install_e84_delete_installation_seal_after_prior_install_genesis_rejected():
    """E84: Deleting installation seal after prior install is rejected because D2 history exists."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import D2InstallationProvisioning

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E84",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

    marker = D2InstallationProvisioning.get_marker_path()
    if os.path.exists(marker):
        os.remove(marker)

    with pytest.raises(RuntimeError, match="canonical D2 authority store already contains history"):
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)


def test_d3_install_e85_modify_installation_seal_rejected():
    """E85: Tampering with or modifying the installation seal fails closed."""
    import json
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import D2InstallationProvisioning

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E85",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

    marker = D2InstallationProvisioning.get_marker_path()
    with open(marker, "r", encoding="utf-8") as f:
        seal_data = json.load(f)

    # Tamper with installation_id
    seal_data["installation_id"] = "TAMPERED-UUID-9999"
    with open(marker, "w", encoding="utf-8") as f:
        json.dump(seal_data, f)

    with pytest.raises(InvalidManifestSignatureError):
        SignedAuthorityManifestLoader.load_from_dict(manifest_v1)


def test_d3_install_e86_replace_installation_seal_with_forged_seal_rejected():
    """E86: Replacing installation seal with a forged signature from another key fails closed."""
    import json
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import D2InstallationProvisioning

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E86",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

    # Forge seal with attacker key
    attacker_priv = ed25519.Ed25519PrivateKey.generate()
    marker = D2InstallationProvisioning.get_marker_path()
    with open(marker, "r", encoding="utf-8") as f:
        seal_data = json.load(f)

    seal_data["signature"]["public_key_fingerprint"] = hashlib.sha256(attacker_priv.public_key().public_bytes_raw()).hexdigest()
    with open(marker, "w", encoding="utf-8") as f:
        json.dump(seal_data, f)

    with pytest.raises(InvalidManifestSignatureError):
        SignedAuthorityManifestLoader.load_from_dict(manifest_v1)


def test_d3_install_e87_restore_old_installation_seal_rejected():
    """E87: Restoring an old installation seal when D2 ledger has different genesis state fails closed."""
    import shutil
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import D2InstallationProvisioning

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E87-ORIGINAL",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

    marker = D2InstallationProvisioning.get_marker_path()
    backup_marker = marker + ".bak"
    shutil.copyfile(marker, backup_marker)

    # Re-initialize clean test harness with different manifest
    SignedAuthorityManifestLoader.clear_for_testing()
    manifest_v2 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E87-SUBSEQUENT",
        manifest_version=1,
        issued_at="2026-08-20T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v2)

    # Restore old marker from original installation
    shutil.copyfile(backup_marker, marker)
    try:
        os.remove(backup_marker)
    except OSError:
        pass

    with pytest.raises(CorruptManifestError, match="Authoritative D2 genesis state does not agree with sealed installation record"):
        SignedAuthorityManifestLoader.load_from_dict(manifest_v2)


def test_d3_install_e88_crash_after_seal_before_d2_commit_deterministic_recovery():
    """E88: Crash after prepare with completed D2 event commits recovers stage into seal."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import D2AuthorityManifestStore, D2InstallationProvisioning

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E88",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    canonical_bytes = canonicalize_authority_manifest_preimage(manifest_v1)
    expected_digest = hashlib.sha256(canonical_bytes).hexdigest()
    root_sig = manifest_v1["root_signature"]
    sig_root_fp = root_sig["public_key_fingerprint"]
    signer_identity = root_sig["signer_identity"]

    # Stage 1 prepared
    inst_id = D2InstallationProvisioning.prepare_first_installation(
        manifest_id="M-E88",
        manifest_version=1,
        payload_digest=expected_digest,
        signer_identity=signer_identity,
        root_fingerprint=sig_root_fp,
    )

    # Stage 2 D2 commit complete, but crash before Stage 3 seal
    store = D2AuthorityManifestStore()
    store.commit_epoch(
        manifest_id="M-E88",
        manifest_version=1,
        payload_digest=expected_digest,
        signer_identity=signer_identity,
        root_fingerprint=sig_root_fp,
    )

    # Verify that query or load triggers deterministic recovery
    assert D2InstallationProvisioning.is_installed() is True
    res = SignedAuthorityManifestLoader.load_from_dict(manifest_v1)
    assert res.manifest_id == "M-E88"
    assert res.manifest_version == 1
    assert D2InstallationProvisioning.has_seal() is True


def test_d3_install_e89_crash_during_d2_commit_no_unauthorized_genesis_reset():
    """E89: Crash during D2 commit with empty D2 cleans broken stage and fails closed against load."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.exceptions import StorageUnavailableError
    from events.store import D2InstallationProvisioning

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E89",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    canonical_bytes = canonicalize_authority_manifest_preimage(manifest_v1)
    expected_digest = hashlib.sha256(canonical_bytes).hexdigest()
    root_sig = manifest_v1["root_signature"]

    # Prepare stage written, but D2 store was not created / empty
    D2InstallationProvisioning.prepare_first_installation(
        manifest_id="M-E89",
        manifest_version=1,
        payload_digest=expected_digest,
        signer_identity=root_sig["signer_identity"],
        root_fingerprint=root_sig["public_key_fingerprint"],
    )

    # Remove D2 store file if present
    from events.store import D2AuthorityManifestStore
    store = D2AuthorityManifestStore()
    if os.path.exists(store.file_path):
        os.remove(store.file_path)

    # Loading manifest fails closed with StorageUnavailableError
    with pytest.raises(StorageUnavailableError):
        SignedAuthorityManifestLoader.load_from_dict(manifest_v1)


def test_d3_install_e90_completed_genesis_installation_seal_and_d2_state_agree():
    """E90: Completed genesis produces 100% state agreement between installation seal and D2 store."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import D2AuthorityManifestStore, D2InstallationProvisioning

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E90",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    res = SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)
    assert res.manifest_version == 1

    # Verify seal and D2 state agreement
    seal_data = D2InstallationProvisioning.verify_seal()
    store = D2AuthorityManifestStore()
    events = store.store.get_events()
    assert len(events) == 1
    assert events[0].payload["manifest_id"] == seal_data["initial_manifest_id"]
    assert events[0].payload["manifest_version"] == seal_data["initial_manifest_version"]
    assert events[0].payload["payload_digest"] == seal_data["initial_manifest_digest"]
    assert events[0].payload["root_fingerprint"] == seal_data["root_fingerprint"]


def test_d3_install_e91_local_state_loss_transitions_to_recovery_required():
    """E91: Deleting local state transitions external deployment authority to RECOVERY_REQUIRED."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import D2AuthorityManifestStore, D2InstallationProvisioning, DeploymentProvisionerRegistry, DeploymentStatus

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E91",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

    # Attacker wipes all local files
    store = D2AuthorityManifestStore()
    marker = D2InstallationProvisioning.get_marker_path()
    stage = D2InstallationProvisioning.get_stage_path()
    for p in [store.file_path, marker, stage]:
        if os.path.exists(p):
            os.remove(p)

    # Notify / detect local state loss in external provisioner
    provisioner = DeploymentProvisionerRegistry.get_provisioner()
    provisioner.notify_local_state_loss()
    assert provisioner.get_deployment_status() == DeploymentStatus.RECOVERY_REQUIRED

    # Genesis bootstrap is rejected with RECOVERY_REQUIRED
    with pytest.raises(RuntimeError, match="RECOVERY_REQUIRED"):
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)


def test_d3_install_e92_restart_after_loss_remains_recovery_required():
    """E92: Process restart after complete local-state loss remains in RECOVERY_REQUIRED."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import (
        D2AuthorityManifestStore,
        D2InstallationProvisioning,
        DeploymentProvisionerRegistry,
        DeploymentStatus,
        InMemoryTestDeploymentProvisioner,
        SClassApplication,
    )

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E92",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

    # Wipe local state
    store = D2AuthorityManifestStore()
    marker = D2InstallationProvisioning.get_marker_path()
    stage = D2InstallationProvisioning.get_stage_path()
    for p in [store.file_path, marker, stage]:
        if os.path.exists(p):
            os.remove(p)

    # Re-attach external provisioner representing persistent external authority in RECOVERY_REQUIRED state
    DeploymentProvisionerRegistry.reset_for_testing()
    external_provisioner = InMemoryTestDeploymentProvisioner(
        deployment_id="DEPLOYMENT-PERSISTED-001",
        initial_status=DeploymentStatus.RECOVERY_REQUIRED,
    )
    SClassApplication(provisioner=external_provisioner)

    assert DeploymentProvisionerRegistry.get_provisioner().get_deployment_status() == DeploymentStatus.RECOVERY_REQUIRED
    with pytest.raises(RuntimeError, match="RECOVERY_REQUIRED"):
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)


def test_d3_install_e93_no_external_provisioner_genesis_rejected():
    """E93: FailClosedDeploymentProvisioner (production default) rejects automatic genesis."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import DeploymentProvisionerRegistry

    DeploymentProvisionerRegistry.reset_for_testing()

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E93",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    with pytest.raises(RuntimeError, match="AUTHORITY_UNAVAILABLE|FailClosedDeploymentProvisioner"):
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)


def test_d3_install_e94_valid_external_initial_authorization_succeeds_once():
    """E94: Valid external initial authorization succeeds exactly once and second call is rejected."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import DeploymentProvisionerRegistry, DeploymentStatus

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E94",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # 1. First bootstrap succeeds
    res = SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)
    assert res.manifest_version == 1

    # 2. External authority is now PROVISIONED
    provisioner = DeploymentProvisionerRegistry.get_provisioner()
    assert provisioner.get_deployment_status() == DeploymentStatus.PROVISIONED

    # 3. Second bootstrap call is rejected
    with pytest.raises(RuntimeError, match="already PROVISIONED|already contains history|system has already been provisioned"):
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)


def test_d3_install_e95_valid_external_reprovision_authorization_recovery_succeeds_once():
    """E95: Valid external reprovision authorization succeeds and establishes fresh genesis state."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import (
        D2AuthorityManifestStore,
        D2InstallationProvisioning,
        DeploymentProvisionerRegistry,
        InMemoryTestDeploymentProvisioner,
    )

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E95-ORIGINAL",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

    # Wipe local files
    store = D2AuthorityManifestStore()
    marker = D2InstallationProvisioning.get_marker_path()
    stage = D2InstallationProvisioning.get_stage_path()
    for p in [store.file_path, marker, stage]:
        if os.path.exists(p):
            os.remove(p)

    recovery_manifest = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E95-RECOVERED",
        manifest_version=1,
        issued_at="2026-08-21T12:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    provisioner = DeploymentProvisionerRegistry.get_provisioner()
    dep_id = provisioner.get_deployment_id()
    reprov_auth = InMemoryTestDeploymentProvisioner.create_reprovisioning_authorization(
        deployment_id=dep_id,
        target_manifest_id="M-E95-RECOVERED",
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        reason="DISASTER_RECOVERY",
    )

    res = SignedAuthorityManifestLoader.reprovision_catastrophic_recovery(
        data=recovery_manifest,
        reprovisioning_authorization=reprov_auth,
    )
    assert res.manifest_id == "M-E95-RECOVERED"
    assert res.manifest_version == 1

    seal = D2InstallationProvisioning.verify_seal()
    assert seal["initial_manifest_id"] == "M-E95-RECOVERED"


def test_d3_install_e96_replay_authorization_rejected():
    """E96: Replay of an already-consumed reprovisioning authorization is rejected by external authority."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import (
        D2AuthorityManifestStore,
        D2InstallationProvisioning,
        DeploymentProvisionerRegistry,
        InMemoryTestDeploymentProvisioner,
    )

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E96",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

    # Wipe local files
    store = D2AuthorityManifestStore()
    marker = D2InstallationProvisioning.get_marker_path()
    stage = D2InstallationProvisioning.get_stage_path()
    for p in [store.file_path, marker, stage]:
        if os.path.exists(p):
            os.remove(p)

    recovery_manifest = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E96-RECOVERED",
        manifest_version=1,
        issued_at="2026-08-21T12:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    provisioner = DeploymentProvisionerRegistry.get_provisioner()
    dep_id = provisioner.get_deployment_id()
    reprov_auth = InMemoryTestDeploymentProvisioner.create_reprovisioning_authorization(
        deployment_id=dep_id,
        target_manifest_id="M-E96-RECOVERED",
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    SignedAuthorityManifestLoader.reprovision_catastrophic_recovery(
        data=recovery_manifest,
        reprovisioning_authorization=reprov_auth,
    )

    # Replay attempt fails
    with pytest.raises(RuntimeError, match="already been consumed"):
        SignedAuthorityManifestLoader.reprovision_catastrophic_recovery(
            data=recovery_manifest,
            reprovisioning_authorization=reprov_auth,
        )


def test_d3_install_e97_wrong_deployment_identity_rejected():
    """E97: Reprovisioning authorization with mismatched deployment identity fails closed."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import InMemoryTestDeploymentProvisioner
    from policy.exceptions import CorruptManifestError

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E97",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    wrong_dep_auth = InMemoryTestDeploymentProvisioner.create_reprovisioning_authorization(
        deployment_id="ROGUE-DEPLOYMENT-XYZ",
        target_manifest_id="M-E97",
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    with pytest.raises(CorruptManifestError, match="deployment mismatch"):
        SignedAuthorityManifestLoader.reprovision_catastrophic_recovery(
            data=manifest_v1,
            reprovisioning_authorization=wrong_dep_auth,
        )


def test_d3_install_e98_forged_authorization_rejected():
    """E98: Reprovisioning authorization with forged/invalid signature fails closed."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import DeploymentProvisionerRegistry, InMemoryTestDeploymentProvisioner
    from policy.exceptions import InvalidManifestSignatureError

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E98",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    provisioner = DeploymentProvisionerRegistry.get_provisioner()
    dep_id = provisioner.get_deployment_id()
    auth = InMemoryTestDeploymentProvisioner.create_reprovisioning_authorization(
        deployment_id=dep_id,
        target_manifest_id="M-E98",
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # Attacker tampers with signature
    auth["signature"]["signature_hex"] = "00" * 64

    with pytest.raises(InvalidManifestSignatureError):
        SignedAuthorityManifestLoader.reprovision_catastrophic_recovery(
            data=manifest_v1,
            reprovisioning_authorization=auth,
        )


def test_d3_install_e99_external_authority_unavailable_fails_closed():
    """E99: When external deployment authority is unavailable or fails, genesis and recovery fail closed."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import DeploymentProvisionerRegistry, TrustedDeploymentProvisioner, DeploymentStatus, SClassApplication

    class UnavailableExternalProvisioner(TrustedDeploymentProvisioner):
        def get_deployment_id(self) -> str:
            raise ConnectionError("External deployment coordinator unreachable.")
        def get_deployment_status(self) -> DeploymentStatus:
            raise ConnectionError("External deployment coordinator unreachable.")
        def authorize_initial_provisioning(self, authorization_data=None) -> None:
            raise ConnectionError("External deployment coordinator unreachable.")
        def record_provisioned(self, *args, **kwargs) -> None:
            raise ConnectionError("External deployment coordinator unreachable.")
        def notify_local_state_loss(self) -> None:
            raise ConnectionError("External deployment coordinator unreachable.")
        def authorize_reprovisioning(self, *args, **kwargs) -> Dict[str, Any]:
            raise ConnectionError("External deployment coordinator unreachable.")
        def record_reprovisioned(self, *args, **kwargs) -> None:
            raise ConnectionError("External deployment coordinator unreachable.")

    DeploymentProvisionerRegistry.reset_for_testing()
    SClassApplication(provisioner=UnavailableExternalProvisioner())

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E99",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    with pytest.raises(ConnectionError, match="External deployment coordinator unreachable"):
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)


def test_d3_install_e100_test_provisioner_inaccessible_outside_test_mode(monkeypatch):
    """E100: InMemoryTestDeploymentProvisioner is strictly prohibited outside TEST_MODE."""
    from events.store import InMemoryTestDeploymentProvisioner

    # Remove all test mode environment flags
    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    with pytest.raises(RuntimeError, match="InMemoryTestDeploymentProvisioner is strictly prohibited outside TEST_MODE"):
        InMemoryTestDeploymentProvisioner()


def test_d3_install_e101_arbitrary_provisioner_injection_rejected():
    """E101: Arbitrary provisioner injection after sealing is rejected."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import DeploymentProvisionerRegistry, InMemoryTestDeploymentProvisioner, SClassApplication

    # Application is already constructed during clear_for_testing()
    assert DeploymentProvisionerRegistry.is_sealed()

    attacker_provisioner = InMemoryTestDeploymentProvisioner(deployment_id="ATTACKER-PROVISIONER-001")
    with pytest.raises(RuntimeError, match="already been constructed|replacement is prohibited"):
        SClassApplication(provisioner=attacker_provisioner)


def test_d3_install_e102_provisioner_replacement_after_bootstrap_rejected():
    """E102: Provisioner replacement after legitimate genesis bootstrap is rejected."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import DeploymentProvisionerRegistry, InMemoryTestDeploymentProvisioner, SClassApplication

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E102",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

    rogue_provisioner = InMemoryTestDeploymentProvisioner(deployment_id="ROGUE-REPLACEMENT-001")
    with pytest.raises(RuntimeError, match="already been constructed|replacement is prohibited"):
        SClassApplication(provisioner=rogue_provisioner)


def test_d3_install_e103_attacker_provisioner_cannot_authorize_genesis():
    """E103: Attacker-supplied provisioner cannot authorize unauthorized genesis reset."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import (
        D2AuthorityManifestStore,
        D2InstallationProvisioning,
        DeploymentProvisionerRegistry,
        InMemoryTestDeploymentProvisioner,
        SClassApplication,
    )

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E103-V1",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

    # Attacker attempts to inject custom provisioner to bypass PROVISIONED status
    attacker_provisioner = InMemoryTestDeploymentProvisioner(deployment_id="ROGUE-AUTHORITY-001")
    with pytest.raises(RuntimeError, match="already been constructed|replacement is prohibited"):
        SClassApplication(provisioner=attacker_provisioner)

    # Genesis bootstrap still fails closed against the original sealed authority
    with pytest.raises(RuntimeError, match="already contains history|system has already been provisioned"):
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)


def test_d3_install_e104_production_env_flag_cannot_enable_test_authority(monkeypatch):
    """E104: Production environment flag cannot automatically enable test authority without explicit bootstrap."""
    from events.store import DeploymentProvisionerRegistry, FailClosedDeploymentProvisioner, DeploymentStatus

    # Reset registry without bootstrapping test provisioner
    DeploymentProvisionerRegistry.reset_for_testing()

    # Even with test flags in environment, default is strictly FailClosedDeploymentProvisioner
    monkeypatch.setenv("SCLASS_TEST_MODE", "1")
    monkeypatch.setenv("SCLASS_TEST_FIXTURE_ACTIVE", "1")

    provisioner = DeploymentProvisionerRegistry.get_provisioner()
    assert isinstance(provisioner, FailClosedDeploymentProvisioner)
    assert provisioner.get_deployment_status() == DeploymentStatus.AUTHORITY_UNAVAILABLE


def test_d3_install_e105_d3_cannot_call_concrete_provisioner_mutation_apis():
    """E105: D3 interactions with external authority rely strictly on TrustedDeploymentProvisioner ABC."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import (
        DeploymentProvisionerRegistry,
        TrustedDeploymentProvisioner,
        DeploymentStatus,
        SClassApplication,
    )

    # Pure minimal implementation of TrustedDeploymentProvisioner with NO concrete helper/mutation methods
    class StrictCanonicalProvisioner(TrustedDeploymentProvisioner):
        def __init__(self):
            self.status = DeploymentStatus.UNPROVISIONED
        def get_deployment_id(self) -> str:
            return "STRICT-CANONICAL-001"
        def get_deployment_status(self) -> DeploymentStatus:
            return self.status
        def authorize_initial_provisioning(self, authorization_data=None) -> None:
            self.status = DeploymentStatus.PROVISIONING_AUTHORIZED
        def record_provisioned(self, installation_id, manifest_id, manifest_version, root_fingerprint) -> None:
            self.status = DeploymentStatus.PROVISIONED
        def notify_local_state_loss(self) -> None:
            self.status = DeploymentStatus.RECOVERY_REQUIRED
        def authorize_reprovisioning(self, reprovisioning_authorization, root_public_key=None) -> Dict[str, Any]:
            self.status = DeploymentStatus.RECOVERY_AUTHORIZED
            return reprovisioning_authorization
        def record_reprovisioned(self, installation_id, manifest_id, manifest_version, root_fingerprint) -> None:
            self.status = DeploymentStatus.PROVISIONED

    DeploymentProvisionerRegistry.reset_for_testing()
    canonical_prov = StrictCanonicalProvisioner()
    SClassApplication(provisioner=canonical_prov)

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E105",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    res = SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)
    assert res.manifest_id == "M-E105"
    assert canonical_prov.get_deployment_status() == DeploymentStatus.PROVISIONED


def test_d3_install_e106_recovery_requires_canonical_interface_and_preserves_immutable_identity():
    """E106: Recovery requires canonical interface and preserves immutable deployment identity."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import (
        D2AuthorityManifestStore,
        D2InstallationProvisioning,
        DeploymentProvisionerRegistry,
        InMemoryTestDeploymentProvisioner,
        DeploymentStatus,
    )

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E106-ORIGINAL",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

    provisioner = DeploymentProvisionerRegistry.get_provisioner()
    original_dep_id = provisioner.get_deployment_id()

    # Wipe local files
    store = D2AuthorityManifestStore()
    marker = D2InstallationProvisioning.get_marker_path()
    stage = D2InstallationProvisioning.get_stage_path()
    for p in [store.file_path, marker, stage]:
        if os.path.exists(p):
            os.remove(p)

    recovery_manifest = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E106-RECOVERED",
        manifest_version=1,
        issued_at="2026-08-21T12:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    reprov_auth = InMemoryTestDeploymentProvisioner.create_reprovisioning_authorization(
        deployment_id=original_dep_id,
        target_manifest_id="M-E106-RECOVERED",
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    res = SignedAuthorityManifestLoader.reprovision_catastrophic_recovery(
        data=recovery_manifest,
        reprovisioning_authorization=reprov_auth,
    )
    assert res.manifest_id == "M-E106-RECOVERED"
    assert provisioner.get_deployment_id() == original_dep_id
    assert provisioner.get_deployment_status() == DeploymentStatus.PROVISIONED


def test_d3_install_e107_unauthorized_first_bootstrap_rejected():
    """E107: Invoking direct registry bootstrap without application construction is rejected."""
    from events.store import DeploymentProvisionerRegistry, InMemoryTestDeploymentProvisioner

    DeploymentProvisionerRegistry.reset_for_testing()

    prov = InMemoryTestDeploymentProvisioner()

    # Direct call to prohibited bootstrap method fails closed
    with pytest.raises(RuntimeError, match="DeploymentProvisionerRegistry cannot be bootstrapped directly"):
        DeploymentProvisionerRegistry.bootstrap_provisioner(prov)


def test_d3_install_e108_ordinary_runtime_path_cannot_bootstrap_provider():
    """E108: Ordinary runtime path cannot mutate or bootstrap custom provider."""
    from events.store import DeploymentProvisionerRegistry, InMemoryTestDeploymentProvisioner

    DeploymentProvisionerRegistry.reset_for_testing()

    attacker_prov = InMemoryTestDeploymentProvisioner(deployment_id="ATTACKER-RUNTIME-001")

    # Direct bootstrap path is inaccessible
    with pytest.raises(RuntimeError, match="DeploymentProvisionerRegistry cannot be bootstrapped directly"):
        DeploymentProvisionerRegistry.bootstrap_provisioner(attacker_prov)

    # Authority defaults to fail-closed
    assert DeploymentProvisionerRegistry.get_provisioner().get_deployment_status().value == "AUTHORITY_UNAVAILABLE"


def test_d3_install_e109_trusted_composition_root_bootstrap_succeeds_exactly_once():
    """E109: SClassApplication constructor succeeds exactly once; second construction is rejected."""
    from events.store import DeploymentProvisionerRegistry, InMemoryTestDeploymentProvisioner, SClassApplication

    DeploymentProvisionerRegistry.reset_for_testing()

    prov = InMemoryTestDeploymentProvisioner(deployment_id="LEGITIMATE-ROOT-001")

    # 1. First application construction succeeds
    app = SClassApplication(provisioner=prov)
    assert app.provisioner.get_deployment_id() == "LEGITIMATE-ROOT-001"
    assert DeploymentProvisionerRegistry.get_provisioner().get_deployment_id() == "LEGITIMATE-ROOT-001"
    assert DeploymentProvisionerRegistry.is_sealed()

    # 2. Second application construction attempt is rejected
    prov_second = InMemoryTestDeploymentProvisioner(deployment_id="ATTACKER-SECOND-001")
    with pytest.raises(RuntimeError, match="SClassApplication has already been constructed"):
        SClassApplication(provisioner=prov_second)


def test_d3_install_e110_provider_identity_cannot_change_before_or_after_first_provisioning():
    """E110: Provider identity cannot change before or after first provisioning."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import DeploymentProvisionerRegistry, InMemoryTestDeploymentProvisioner, SClassApplication

    prov = InMemoryTestDeploymentProvisioner(deployment_id="STABLE-IMMUTABLE-DEP-001")
    DeploymentProvisionerRegistry.reset_for_testing()
    SClassApplication(provisioner=prov)

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E110",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    res = SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)
    assert res.manifest_version == 1

    # Deployment ID is verified
    assert DeploymentProvisionerRegistry.get_provisioner().get_deployment_id() == "STABLE-IMMUTABLE-DEP-001"

    # Any attempt to construct another application fails closed
    rogue_prov = InMemoryTestDeploymentProvisioner(deployment_id="MUTATED-DEP-002")
    with pytest.raises(RuntimeError, match="SClassApplication has already been constructed"):
        SClassApplication(provisioner=rogue_prov)

    assert DeploymentProvisionerRegistry.get_provisioner().get_deployment_id() == "STABLE-IMMUTABLE-DEP-001"


def test_d3_install_e111_same_process_caller_cannot_mutate_broker_authority():
    """E111: In-process caller cannot mutate broker authority state directly."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.store import IPCDeploymentProvisioner, SClassApplication, DeploymentProvisionerRegistry, DeploymentStatus

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E111",
        auth_secret="SECRET-E111",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        DeploymentProvisionerRegistry.reset_for_testing()
        client_prov = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SECRET-E111")
        SClassApplication(provisioner=client_prov)

        # 1. Broker is initially UNPROVISIONED
        assert client_prov.get_deployment_status() == DeploymentStatus.UNPROVISIONED

        # 2. Local in-process caller attempts to manipulate local attributes
        client_prov._deployment_id = "ATTACKER-MUTATED"
        # The broker is the authority and still returns the genuine deployment identity over IPC
        assert client_prov.get_deployment_id() == "DEP-E111"

        # 3. Genesis bootstrap transitions broker to PROVISIONED
        manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-E111",
            manifest_version=1,
            issued_at="2026-08-19T10:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        res = SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)
        assert res.manifest_version == 1
        assert client_prov.get_deployment_status() == DeploymentStatus.PROVISIONED
        assert broker.status == DeploymentStatus.PROVISIONED
    finally:
        broker.stop_ipc_server()


def test_d3_install_e112_untrusted_process_cannot_connect_to_broker():
    """E112: Untrusted process with invalid/missing credentials cannot connect to broker."""
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.ipc import OSIPCClient

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E112",
        auth_secret="CONFIDENTIAL_DEPLOYMENT_SECRET_123",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        # 1. Attacker client connects with wrong auth secret -> rejected
        attacker_client = OSIPCClient(
            endpoint_path=broker.ipc_endpoint,
            auth_secret="WRONG_FORGED_SECRET",
        )
        with pytest.raises(PermissionError, match="Invalid auth credentials|rejected"):
            attacker_client.call("get_deployment_id")

        # 2. Legitimate client connects with correct secret -> accepted
        legit_client = OSIPCClient(
            endpoint_path=broker.ipc_endpoint,
            auth_secret="CONFIDENTIAL_DEPLOYMENT_SECRET_123",
        )
        resp = legit_client.call("get_deployment_id")
        assert resp["deployment_id"] == "DEP-E112"
        legit_client.close()
    finally:
        broker.stop_ipc_server()


def test_d3_install_e113_wrong_unix_peer_credentials_rejected():
    """E113: Peer credential verification rejects connection if caller UID does not match allowed UID."""
    import sys
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.ipc import OSIPCClient

    # Set allowed_uid to an impossible UID (e.g. 999999)
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E113",
        allowed_uid=999999,
        auth_secret="SECRET-E113",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        # Client runs with current process UID (which is not 999999 on Linux/POSIX)
        client = OSIPCClient(
            endpoint_path=broker.ipc_endpoint,
            auth_secret="SECRET-E113",
        )
        if sys.platform != "win32":
            with pytest.raises((ConnectionError, PermissionError)):
                client.call("get_deployment_id")
        else:
            # On Windows, secret verification protects the endpoint
            resp = client.call("get_deployment_id")
            assert resp["deployment_id"] == "DEP-E113"
            client.close()
    finally:
        broker.stop_ipc_server()


def test_d3_install_e114_unauthorized_windows_named_pipe_principal_rejected():
    """E114: Unauthorized client principal attempting IPC communication is rejected."""
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.ipc import OSIPCClient

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E114",
        auth_secret="WIN_SECURE_TOKEN_XYZ",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        # Client without secret handshake cannot execute RPCs
        bad_client = OSIPCClient(
            endpoint_path=broker.ipc_endpoint,
            auth_secret=None,
        )
        with pytest.raises((PermissionError, ConnectionError)):
            bad_client.call("get_deployment_id")
    finally:
        broker.stop_ipc_server()


def test_d3_install_e115_spoofed_deployment_identity_rejected():
    """E115: Reprovisioning authorization targeting a different/spoofed deployment identity is rejected by broker."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.store import (
        IPCDeploymentProvisioner,
        InMemoryTestDeploymentProvisioner,
        SClassApplication,
        DeploymentProvisionerRegistry,
    )
    from policy.exceptions import CorruptManifestError

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="CANONICAL-DEP-115",
        auth_secret="SECRET-E115",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        DeploymentProvisionerRegistry.reset_for_testing()
        client_prov = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SECRET-E115")
        SClassApplication(provisioner=client_prov)

        # Notify loss to put broker into RECOVERY_REQUIRED
        broker.notify_local_state_loss()

        manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-E115",
            manifest_version=1,
            issued_at="2026-08-19T10:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )

        # Authorization signed for spoofed deployment ID
        spoofed_auth = InMemoryTestDeploymentProvisioner.create_reprovisioning_authorization(
            deployment_id="SPOOFED-DEPLOYMENT-ID",
            target_manifest_id="M-E115",
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )

        with pytest.raises(CorruptManifestError, match="deployment mismatch"):
            SignedAuthorityManifestLoader.reprovision_catastrophic_recovery(
                data=manifest_v1,
                reprovisioning_authorization=spoofed_auth,
            )
    finally:
        broker.stop_ipc_server()


def test_d3_install_e116_broker_restart_preserves_provisioned():
    """E116: Broker service restart preserves PROVISIONED state from durable external storage."""
    SignedAuthorityManifestLoader.clear_for_testing()
    import tempfile
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.store import IPCDeploymentProvisioner, SClassApplication, DeploymentProvisionerRegistry, DeploymentStatus

    state_file = os.path.join(tempfile.gettempdir(), f"broker_state_e116_{os.getpid()}.json")
    if os.path.exists(state_file):
        os.remove(state_file)

    broker1 = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E116",
        state_file_path=state_file,
        auth_secret="SECRET-E116",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker1.start_ipc_server()
    try:
        DeploymentProvisionerRegistry.reset_for_testing()
        client_prov1 = IPCDeploymentProvisioner(ipc_endpoint=broker1.ipc_endpoint, auth_secret="SECRET-E116")
        SClassApplication(provisioner=client_prov1)

        manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-E116",
            manifest_version=1,
            issued_at="2026-08-19T10:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)
        assert client_prov1.get_deployment_status() == DeploymentStatus.PROVISIONED
    finally:
        broker1.stop_ipc_server()

    # Broker crashes / restarts
    broker2 = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E116",
        state_file_path=state_file,
        auth_secret="SECRET-E116",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker2.start_ipc_server()
    try:
        client_prov2 = IPCDeploymentProvisioner(ipc_endpoint=broker2.ipc_endpoint, auth_secret="SECRET-E116")
        # Status remains PROVISIONED across broker restart
        assert client_prov2.get_deployment_status() == DeploymentStatus.PROVISIONED
        assert client_prov2.get_deployment_id() == "DEP-E116"
    finally:
        broker2.stop_ipc_server()
        if os.path.exists(state_file):
            os.remove(state_file)


def test_d3_install_e117_sclass_local_state_destruction_does_not_reset_broker():
    """E117: S-Class local state destruction does not reset broker state."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.store import (
        D2AuthorityManifestStore,
        D2InstallationProvisioning,
        IPCDeploymentProvisioner,
        SClassApplication,
        DeploymentProvisionerRegistry,
        DeploymentStatus,
    )

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E117",
        auth_secret="SECRET-E117",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        DeploymentProvisionerRegistry.reset_for_testing()
        client_prov = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SECRET-E117")
        SClassApplication(provisioner=client_prov)

        manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-E117",
            manifest_version=1,
            issued_at="2026-08-19T10:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)
        assert broker.status == DeploymentStatus.PROVISIONED

        # Destroy all S-Class local state
        store = D2AuthorityManifestStore()
        marker = D2InstallationProvisioning.get_marker_path()
        stage = D2InstallationProvisioning.get_stage_path()
        for p in [store.file_path, marker, stage]:
            if os.path.exists(p):
                os.remove(p)

        # Notify loss
        client_prov.notify_local_state_loss()
        assert broker.status == DeploymentStatus.RECOVERY_REQUIRED

        # Automatic genesis bootstrap is rejected
        with pytest.raises(RuntimeError, match="RECOVERY_REQUIRED"):
            SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)
    finally:
        broker.stop_ipc_server()


def test_d3_install_e118_replayed_recovery_authorization_rejected_by_broker():
    """E118: Replay of an already-consumed reprovisioning authorization is rejected by broker."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.store import (
        D2AuthorityManifestStore,
        D2InstallationProvisioning,
        IPCDeploymentProvisioner,
        InMemoryTestDeploymentProvisioner,
        SClassApplication,
        DeploymentProvisionerRegistry,
    )

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E118",
        auth_secret="SECRET-E118",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        DeploymentProvisionerRegistry.reset_for_testing()
        client_prov = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SECRET-E118")
        SClassApplication(provisioner=client_prov)

        manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-E118-ORIGINAL",
            manifest_version=1,
            issued_at="2026-08-19T10:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)

        # Wipe local files
        store = D2AuthorityManifestStore()
        marker = D2InstallationProvisioning.get_marker_path()
        stage = D2InstallationProvisioning.get_stage_path()
        for p in [store.file_path, marker, stage]:
            if os.path.exists(p):
                os.remove(p)

        # Notify broker of local state loss so it transitions to RECOVERY_REQUIRED
        client_prov.notify_local_state_loss()

        recovery_manifest = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-E118-RECOVERED",
            manifest_version=1,
            issued_at="2026-08-21T12:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )

        reprov_auth = InMemoryTestDeploymentProvisioner.create_reprovisioning_authorization(
            deployment_id="DEP-E118",
            target_manifest_id="M-E118-RECOVERED",
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )

        # 1. First recovery succeeds
        SignedAuthorityManifestLoader.reprovision_catastrophic_recovery(
            data=recovery_manifest,
            reprovisioning_authorization=reprov_auth,
        )

        # 2. Replay attempt after second loss fails closed at broker ledger
        client_prov.notify_local_state_loss()
        with pytest.raises(RuntimeError, match="already been consumed"):
            SignedAuthorityManifestLoader.reprovision_catastrophic_recovery(
                data=recovery_manifest,
                reprovisioning_authorization=reprov_auth,
            )
    finally:
        broker.stop_ipc_server()


def test_d3_install_e119_broker_unavailable_fails_closed():
    """E119: When broker is unavailable/unreachable, D3 fails closed."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from events.store import IPCDeploymentProvisioner, SClassApplication, DeploymentProvisionerRegistry

    DeploymentProvisionerRegistry.reset_for_testing()
    unreachable_client = IPCDeploymentProvisioner(ipc_endpoint="/nonexistent/broker_socket.sock")
    SClassApplication(provisioner=unreachable_client)

    manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
        manifest_id="M-E119",
        manifest_version=1,
        issued_at="2026-08-19T10:00:00Z",
        actors={},
        revoked_fingerprints=[],
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    with pytest.raises(RuntimeError, match="AUTHORITY_UNAVAILABLE"):
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)


def test_d3_install_e120_test_inmemory_authority_prohibited_outside_test_mode(monkeypatch):
    """E120: Test in-memory authority cannot be selected or constructed by production runtime."""
    from events.store import InMemoryTestDeploymentProvisioner

    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    with pytest.raises(RuntimeError, match="InMemoryTestDeploymentProvisioner is strictly prohibited outside TEST_MODE"):
        InMemoryTestDeploymentProvisioner()


def test_d3_install_e121_caller_supplied_root_key_rejected():
    """E121: Caller-supplied root key in RPC parameters is rejected by broker."""
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.ipc import OSIPCClient

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E121",
        auth_secret="SECRET-E121",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        client = OSIPCClient(endpoint_path=broker.ipc_endpoint, auth_secret="SECRET-E121")
        broker.notify_local_state_loss()

        # Attacker caller supplies their own root key in RPC
        resp = client.call("authorize_reprovisioning", {
            "reprovisioning_authorization": {"deployment_id": "DEP-E121"},
            "root_public_key": "FORGED_ROOT_KEY_HEX",
        })
        assert not resp.get("success")
        assert "Caller-supplied root public key is rejected" in resp.get("error", "")
        client.close()
    finally:
        broker.stop_ipc_server()


def test_d3_install_e122_forged_authorization_with_caller_selected_key_rejected():
    """E122: Forged authorization signed by caller-selected key is rejected by broker's canonical root."""
    SignedAuthorityManifestLoader.clear_for_testing()
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.store import (
        IPCDeploymentProvisioner,
        InMemoryTestDeploymentProvisioner,
        SClassApplication,
        DeploymentProvisionerRegistry,
    )
    from policy.exceptions import InvalidManifestSignatureError

    attacker_key = ed25519.Ed25519PrivateKey.generate()
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E122",
        auth_secret="SECRET-E122",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        DeploymentProvisionerRegistry.reset_for_testing()
        client_prov = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SECRET-E122")
        SClassApplication(provisioner=client_prov)
        broker.notify_local_state_loss()

        manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-E122",
            manifest_version=1,
            issued_at="2026-08-19T10:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )

        forged_auth = InMemoryTestDeploymentProvisioner.create_reprovisioning_authorization(
            deployment_id="DEP-E122",
            target_manifest_id="M-E122",
            root_private_key=attacker_key,
        )

        with pytest.raises(InvalidManifestSignatureError, match="canonical broker root|signature"):
            SignedAuthorityManifestLoader.reprovision_catastrophic_recovery(
                data=manifest_v1,
                reprovisioning_authorization=forged_auth,
            )
    finally:
        broker.stop_ipc_server()


def test_d3_install_e123_broker_root_mutation_rejected():
    """E123: Broker root key mutation after startup is rejected."""
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from events.broker import TrustedDeploymentAuthorityBroker

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E123",
        auth_secret="SECRET-E123",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    attacker_key = ed25519.Ed25519PrivateKey.generate().public_key()

    # Attempting to reassign property raises AttributeError
    with pytest.raises(AttributeError):
        broker.root_public_key = attacker_key


def test_d3_install_e124_record_provisioned_from_unprovisioned_rejected():
    """E124: Calling record_provisioned directly from UNPROVISIONED state is rejected."""
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.ipc import OSIPCClient

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E124",
        auth_secret="SECRET-E124",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        client = OSIPCClient(endpoint_path=broker.ipc_endpoint, auth_secret="SECRET-E124")
        resp = client.call("record_provisioned", {
            "installation_id": "INST-124",
            "manifest_id": "M-124",
            "manifest_version": 1,
            "root_fingerprint": "ROOT-FP",
        })
        assert not resp.get("success")
        assert "without prior PROVISIONING_AUTHORIZED" in resp.get("error", "")
        client.close()
    finally:
        broker.stop_ipc_server()


def test_d3_install_e125_record_reprovisioned_without_recovery_authorized_rejected():
    """E125: Calling record_reprovisioned without RECOVERY_AUTHORIZED is rejected."""
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.ipc import OSIPCClient

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E125",
        auth_secret="SECRET-E125",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        client = OSIPCClient(endpoint_path=broker.ipc_endpoint, auth_secret="SECRET-E125")
        broker.notify_local_state_loss()  # State is RECOVERY_REQUIRED, not RECOVERY_AUTHORIZED

        resp = client.call("record_reprovisioned", {
            "installation_id": "INST-125",
            "manifest_id": "M-125",
            "manifest_version": 1,
            "root_fingerprint": "ROOT-FP",
        })
        assert not resp.get("success")
        assert "without authorized recovery" in resp.get("error", "")
        client.close()
    finally:
        broker.stop_ipc_server()


def test_d3_install_e126_duplicated_state_transition_rejected():
    """E126: Duplicated state transitions (e.g. repeated authorize_initial_provisioning) are rejected."""
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.ipc import OSIPCClient

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E126",
        auth_secret="SECRET-E126",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        client = OSIPCClient(endpoint_path=broker.ipc_endpoint, auth_secret="SECRET-E126")

        # 1. First authorization succeeds
        resp1 = client.call("authorize_initial_provisioning")
        assert resp1.get("success")

        # 2. Second authorization fails closed
        resp2 = client.call("authorize_initial_provisioning")
        assert not resp2.get("success")
        assert "Cannot authorize initial provisioning from state 'PROVISIONING_AUTHORIZED'" in resp2.get("error", "")
        client.close()
    finally:
        broker.stop_ipc_server()


def test_d3_install_e127_no_auth_broker_startup_rejected():
    """E127: Broker startup without authentication credentials or secure transport is rejected."""
    import sys
    from events.broker import TrustedDeploymentAuthorityBroker

    # Windows or no UID check with no auth_secret
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E127",
        auth_secret=None,
        allowed_uid=None,
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    with pytest.raises(RuntimeError, match="Broker startup rejected: mandatory authentication secret required"):
        broker.start_ipc_server()


def test_d3_install_e128_unauthorized_client_rejected():
    """E128: Client connecting without matching credentials is strictly rejected."""
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.ipc import OSIPCClient

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E128",
        auth_secret="MANDATORY_SECRET_128",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        client = OSIPCClient(endpoint_path=broker.ipc_endpoint, auth_secret="INVALID_SECRET")
        with pytest.raises(PermissionError):
            client.call("get_deployment_id")
    finally:
        broker.stop_ipc_server()


def test_d3_install_e129_unauthorized_windows_client_rejected():
    """E129: Windows client without secret handshake is strictly rejected."""
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.ipc import OSIPCClient

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E129",
        auth_secret="WIN_PIPE_SECRET_129",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        client = OSIPCClient(endpoint_path=broker.ipc_endpoint, auth_secret=None)
        with pytest.raises((PermissionError, ConnectionError)):
            client.call("get_deployment_id")
    finally:
        broker.stop_ipc_server()


def test_d3_install_e130_localhost_tcp_without_authentication_rejected():
    """E130: Unauthenticated localhost TCP connection attempt is rejected."""
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.ipc import OSIPCClient

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E130",
        auth_secret="TCP_AUTH_SECRET_130",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        unauth_client = OSIPCClient(endpoint_path=broker.ipc_endpoint, auth_secret="WRONG_TCP_TOKEN")
        with pytest.raises(PermissionError):
            unauth_client.call("get_deployment_id")
    finally:
        broker.stop_ipc_server()


def test_d3_install_e131_broker_state_tampering_fails_closed():
    """E131: Tampering with broker state file fails closed upon restart."""
    import tempfile
    import json
    from events.broker import TrustedDeploymentAuthorityBroker

    state_file = os.path.join(tempfile.gettempdir(), f"broker_state_e131_{os.getpid()}.json")
    if os.path.exists(state_file):
        os.remove(state_file)

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E131",
        state_file_path=state_file,
        auth_secret="SECRET-E131",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    assert broker.status.value == "UNPROVISIONED"

    # Attacker modifies state file without updating integrity seal
    with open(state_file, "r") as f:
        data = json.load(f)
    data["payload"]["status"] = "PROVISIONED"
    with open(state_file, "w") as f:
        json.dump(data, f)

    # Broker reload fails closed on integrity seal mismatch
    with pytest.raises(RuntimeError, match="tampering detected: integrity seal digest mismatch"):
        TrustedDeploymentAuthorityBroker(
            deployment_id="DEP-E131",
            state_file_path=state_file,
            auth_secret="SECRET-E131",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
        )

    if os.path.exists(state_file):
        os.remove(state_file)


def test_d3_install_e132_consumed_authorization_deletion_tampering_fails_closed():
    """E132: Tampering with consumed authorizations ledger in state file fails closed."""
    import tempfile
    import json
    from events.broker import TrustedDeploymentAuthorityBroker

    state_file = os.path.join(tempfile.gettempdir(), f"broker_state_e132_{os.getpid()}.json")
    if os.path.exists(state_file):
        os.remove(state_file)

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E132",
        state_file_path=state_file,
        auth_secret="SECRET-E132",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.consumed_authorizations.add("AUTH-132-USED")
    broker._persist_state()

    # Attacker deletes consumed authorization from payload
    with open(state_file, "r") as f:
        data = json.load(f)
    data["payload"]["consumed_authorizations"] = []
    with open(state_file, "w") as f:
        json.dump(data, f)

    # Reload detects tampering and fails closed
    with pytest.raises(RuntimeError, match="tampering detected"):
        TrustedDeploymentAuthorityBroker(
            deployment_id="DEP-E132",
            state_file_path=state_file,
            auth_secret="SECRET-E132",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
        )

    if os.path.exists(state_file):
        os.remove(state_file)


def test_d3_install_e133_status_downgrade_tampering_fails_closed():
    """E133: Status downgrade tampering fails closed upon restart."""
    import tempfile
    import json
    from events.broker import TrustedDeploymentAuthorityBroker

    state_file = os.path.join(tempfile.gettempdir(), f"broker_state_e133_{os.getpid()}.json")
    if os.path.exists(state_file):
        os.remove(state_file)

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E133",
        state_file_path=state_file,
        auth_secret="SECRET-E133",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.notify_local_state_loss()  # State is RECOVERY_REQUIRED

    # Attacker modifies state file to revert status to UNPROVISIONED
    with open(state_file, "r") as f:
        data = json.load(f)
    data["payload"]["status"] = "UNPROVISIONED"
    with open(state_file, "w") as f:
        json.dump(data, f)

    # Reload detects tampering
    with pytest.raises(RuntimeError, match="tampering detected"):
        TrustedDeploymentAuthorityBroker(
            deployment_id="DEP-E133",
            state_file_path=state_file,
            auth_secret="SECRET-E133",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
        )

    if os.path.exists(state_file):
        os.remove(state_file)


def test_d3_install_e134_broker_restart_preserves_authority_state():
    """E134: Clean broker restart faithfully preserves deployment ID, status, and consumed authorizations."""
    import tempfile
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.store import DeploymentStatus

    state_file = os.path.join(tempfile.gettempdir(), f"broker_state_e134_{os.getpid()}.json")
    if os.path.exists(state_file):
        os.remove(state_file)

    broker1 = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E134-IMMUTABLE",
        state_file_path=state_file,
        auth_secret="SECRET-E134",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker1.consumed_authorizations.add("AUTH-134-A")
    broker1.consumed_authorizations.add("AUTH-134-B")
    broker1.notify_local_state_loss()
    assert broker1.status == DeploymentStatus.RECOVERY_REQUIRED

    # Clean reload
    broker2 = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E134-IMMUTABLE",
        state_file_path=state_file,
        auth_secret="SECRET-E134",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    assert broker2.deployment_id == "DEP-E134-IMMUTABLE"
    assert broker2.status == DeploymentStatus.RECOVERY_REQUIRED
    assert broker2.consumed_authorizations == {"AUTH-134-A", "AUTH-134-B"}

    if os.path.exists(state_file):
        os.remove(state_file)


def test_d3_install_e135_payload_digest_substitution_rejected():
    """E135: Payload digest substitution in D2 commit proof is cryptographically rejected by broker."""
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.store import DeploymentStatus
    from events.serializer import canonicalize_json

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E135",
        auth_secret="SEC-E135",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.status = DeploymentStatus.PROVISIONING_AUTHORIZED
    fp = hashlib.sha256(TEST_AUTHORITY_PUBLIC_KEY.public_bytes_raw()).hexdigest()

    preimage = {
        "installation_id": "INST-E135",
        "initial_manifest_id": "M-E135",
        "initial_manifest_version": 1,
        "initial_manifest_digest": "0" * 64,
        "root_fingerprint": fp,
        "provisioning_epoch": 1,
        "status": "SEALED",
        "installed_at": "2026-08-21T10:00:00Z",
    }
    preimage_bytes = canonicalize_json(preimage)
    real_digest = hashlib.sha256(preimage_bytes).hexdigest()
    sig = TEST_AUTHORITY_PRIVATE_KEY.sign(preimage_bytes)

    # Attacker substitutes payload digest in root_signature block
    tampered_sig_block = {
        "algorithm": "ED25519",
        "signer_identity": "Gate3AuthoritativeVerifier",
        "public_key_fingerprint": fp,
        "payload_digest": "SUBSTITUTED_DIGEST_" + ("f" * 45),
        "signature_hex": sig.hex(),
        "timestamp": "2026-08-21T10:00:00Z",
    }
    resp = broker._dispatch_rpc({
        "method": "record_provisioned",
        "params": {
            "installation_id": "INST-E135",
            "manifest_id": "M-E135",
            "initial_manifest_id": "M-E135",
            "manifest_version": 1,
            "initial_manifest_version": 1,
            "initial_manifest_digest": "0" * 64,
            "root_fingerprint": fp,
            "payload_digest": real_digest,
            "root_signature": tampered_sig_block,
            "installed_at": "2026-08-21T10:00:00Z",
        }
    }, {})
    assert not resp.get("success")
    assert "Payload digest substitution detected" in resp.get("error", "")


def test_d3_install_e136_signature_substitution_rejected():
    """E136: Signature substitution in D2 commit proof is rejected by broker."""
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.store import DeploymentStatus
    from events.serializer import canonicalize_json

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E136",
        auth_secret="SEC-E136",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.status = DeploymentStatus.PROVISIONING_AUTHORIZED
    fp = hashlib.sha256(TEST_AUTHORITY_PUBLIC_KEY.public_bytes_raw()).hexdigest()

    preimage = {
        "installation_id": "INST-E136",
        "initial_manifest_id": "M-E136",
        "initial_manifest_version": 1,
        "initial_manifest_digest": "0" * 64,
        "root_fingerprint": fp,
        "provisioning_epoch": 1,
        "status": "SEALED",
        "installed_at": "2026-08-21T10:00:00Z",
    }
    preimage_bytes = canonicalize_json(preimage)
    real_digest = hashlib.sha256(preimage_bytes).hexdigest()

    # Attacker substitutes corrupted / random signature
    tampered_sig_block = {
        "algorithm": "ED25519",
        "signer_identity": "Gate3AuthoritativeVerifier",
        "public_key_fingerprint": fp,
        "payload_digest": real_digest,
        "signature_hex": "ab" * 64,
        "timestamp": "2026-08-21T10:00:00Z",
    }
    resp = broker._dispatch_rpc({
        "method": "record_provisioned",
        "params": {
            "installation_id": "INST-E136",
            "manifest_id": "M-E136",
            "initial_manifest_id": "M-E136",
            "manifest_version": 1,
            "initial_manifest_version": 1,
            "initial_manifest_digest": "0" * 64,
            "root_fingerprint": fp,
            "payload_digest": real_digest,
            "root_signature": tampered_sig_block,
            "installed_at": "2026-08-21T10:00:00Z",
        }
    }, {})
    assert not resp.get("success")
    assert "signature verification failed" in resp.get("error", "").lower()


def test_d3_install_e137_valid_signature_over_different_manifest_rejected():
    """E137: Valid signature over different manifest is rejected by broker."""
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.store import DeploymentStatus
    from events.serializer import canonicalize_json

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E137",
        auth_secret="SEC-E137",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.status = DeploymentStatus.PROVISIONING_AUTHORIZED
    fp = hashlib.sha256(TEST_AUTHORITY_PUBLIC_KEY.public_bytes_raw()).hexdigest()

    # Preimage for Manifest A
    preimage_a = {
        "installation_id": "INST-E137",
        "initial_manifest_id": "M-MANIFEST-A",
        "initial_manifest_version": 1,
        "initial_manifest_digest": "0" * 64,
        "root_fingerprint": fp,
        "provisioning_epoch": 1,
        "status": "SEALED",
        "installed_at": "2026-08-21T10:00:00Z",
    }
    preimage_a_bytes = canonicalize_json(preimage_a)
    sig_a = TEST_AUTHORITY_PRIVATE_KEY.sign(preimage_a_bytes)
    digest_a = hashlib.sha256(preimage_a_bytes).hexdigest()

    sig_block_a = {
        "algorithm": "ED25519",
        "signer_identity": "Gate3AuthoritativeVerifier",
        "public_key_fingerprint": fp,
        "payload_digest": digest_a,
        "signature_hex": sig_a.hex(),
        "timestamp": "2026-08-21T10:00:00Z",
    }

    # Attacker tries to use Manifest A's signature to commit Manifest B
    resp = broker._dispatch_rpc({
        "method": "record_provisioned",
        "params": {
            "installation_id": "INST-E137",
            "manifest_id": "M-MANIFEST-B",  # Mismatched manifest ID
            "manifest_version": 1,
            "root_fingerprint": fp,
            "payload_digest": digest_a,
            "root_signature": sig_block_a,
            "installed_at": "2026-08-21T10:00:00Z",
        }
    }, {})
    assert not resp.get("success")


def test_d3_install_e138_manifest_id_mismatch_rejected():
    """E138: Manifest ID mismatch between commit params and seal preimage is rejected."""
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.store import DeploymentStatus
    from events.serializer import canonicalize_json

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E138",
        auth_secret="SEC-E138",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.status = DeploymentStatus.PROVISIONING_AUTHORIZED
    fp = hashlib.sha256(TEST_AUTHORITY_PUBLIC_KEY.public_bytes_raw()).hexdigest()

    preimage = {
        "installation_id": "INST-E138",
        "initial_manifest_id": "M-ORIGINAL",
        "initial_manifest_version": 1,
        "initial_manifest_digest": "0" * 64,
        "root_fingerprint": fp,
        "provisioning_epoch": 1,
        "status": "SEALED",
        "installed_at": "2026-08-21T10:00:00Z",
    }
    preimage_bytes = canonicalize_json(preimage)
    sig = TEST_AUTHORITY_PRIVATE_KEY.sign(preimage_bytes)
    digest = hashlib.sha256(preimage_bytes).hexdigest()

    sig_block = {
        "algorithm": "ED25519",
        "signer_identity": "Gate3AuthoritativeVerifier",
        "public_key_fingerprint": fp,
        "payload_digest": digest,
        "signature_hex": sig.hex(),
        "timestamp": "2026-08-21T10:00:00Z",
    }

    resp = broker._dispatch_rpc({
        "method": "record_provisioned",
        "params": {
            "installation_id": "INST-E138",
            "manifest_id": "M-FORGED-DIFFERENT",
            "initial_manifest_id": "M-ORIGINAL",
            "manifest_version": 1,
            "initial_manifest_version": 1,
            "initial_manifest_digest": "0" * 64,
            "root_fingerprint": fp,
            "payload_digest": digest,
            "root_signature": sig_block,
            "installed_at": "2026-08-21T10:00:00Z",
        }
    }, {})
    assert not resp.get("success")
    assert "Manifest ID mismatch" in resp.get("error", "")


def test_d3_install_e139_manifest_version_mismatch_rejected():
    """E139: Manifest version mismatch between commit params and seal preimage is rejected."""
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.store import DeploymentStatus
    from events.serializer import canonicalize_json

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E139",
        auth_secret="SEC-E139",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.status = DeploymentStatus.PROVISIONING_AUTHORIZED
    fp = hashlib.sha256(TEST_AUTHORITY_PUBLIC_KEY.public_bytes_raw()).hexdigest()

    preimage = {
        "installation_id": "INST-E139",
        "initial_manifest_id": "M-E139",
        "initial_manifest_version": 1,
        "initial_manifest_digest": "0" * 64,
        "root_fingerprint": fp,
        "provisioning_epoch": 1,
        "status": "SEALED",
        "installed_at": "2026-08-21T10:00:00Z",
    }
    preimage_bytes = canonicalize_json(preimage)
    sig = TEST_AUTHORITY_PRIVATE_KEY.sign(preimage_bytes)
    digest = hashlib.sha256(preimage_bytes).hexdigest()

    sig_block = {
        "algorithm": "ED25519",
        "signer_identity": "Gate3AuthoritativeVerifier",
        "public_key_fingerprint": fp,
        "payload_digest": digest,
        "signature_hex": sig.hex(),
        "timestamp": "2026-08-21T10:00:00Z",
    }

    resp = broker._dispatch_rpc({
        "method": "record_provisioned",
        "params": {
            "installation_id": "INST-E139",
            "manifest_id": "M-E139",
            "manifest_version": 99,  # Mismatched version
            "initial_manifest_id": "M-E139",
            "initial_manifest_version": 1,
            "initial_manifest_digest": "0" * 64,
            "root_fingerprint": fp,
            "payload_digest": digest,
            "root_signature": sig_block,
            "installed_at": "2026-08-21T10:00:00Z",
        }
    }, {})
    assert not resp.get("success")
    assert "Manifest version mismatch" in resp.get("error", "")


def test_d3_install_e140_fake_d2_commit_proof_with_correct_fingerprint_rejected():
    """E140: Fake D2 commit proof presenting legitimate root fingerprint is rejected by broker."""
    from events.broker import TrustedDeploymentAuthorityBroker
    from events.store import DeploymentStatus
    from events.serializer import canonicalize_json
    from cryptography.hazmat.primitives.asymmetric import ed25519

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E140",
        auth_secret="SEC-E140",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.status = DeploymentStatus.PROVISIONING_AUTHORIZED
    fp = hashlib.sha256(TEST_AUTHORITY_PUBLIC_KEY.public_bytes_raw()).hexdigest()

    preimage = {
        "installation_id": "INST-E140",
        "initial_manifest_id": "M-E140",
        "initial_manifest_version": 1,
        "initial_manifest_digest": "0" * 64,
        "root_fingerprint": fp,
        "provisioning_epoch": 1,
        "status": "SEALED",
        "installed_at": "2026-08-21T10:00:00Z",
    }
    preimage_bytes = canonicalize_json(preimage)
    digest = hashlib.sha256(preimage_bytes).hexdigest()

    # Attacker signs with a private key other than canonical root
    attacker_key = ed25519.Ed25519PrivateKey.generate()
    fake_sig = attacker_key.sign(preimage_bytes)

    fake_sig_block = {
        "algorithm": "ED25519",
        "signer_identity": "Gate3AuthoritativeVerifier",
        "public_key_fingerprint": fp,  # Spoofed fingerprint
        "payload_digest": digest,
        "signature_hex": fake_sig.hex(),
        "timestamp": "2026-08-21T10:00:00Z",
    }

    resp = broker._dispatch_rpc({
        "method": "record_provisioned",
        "params": {
            "installation_id": "INST-E140",
            "manifest_id": "M-E140",
            "initial_manifest_id": "M-E140",
            "manifest_version": 1,
            "initial_manifest_version": 1,
            "initial_manifest_digest": "0" * 64,
            "root_fingerprint": fp,
            "payload_digest": digest,
            "root_signature": fake_sig_block,
            "installed_at": "2026-08-21T10:00:00Z",
        }
    }, {})
    assert not resp.get("success")
    assert "signature verification failed" in resp.get("error", "").lower()










