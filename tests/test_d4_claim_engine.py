"""
S-Class EOS V11.2 - D4 Claim & Evidence Engine Test Suite.
Exhaustive verification of:
1. Relevance Derivation R(C, E) (§7.2) with D3 verified trust consumption.
2. Multi-Dimensional Aspect Coverage Calculus (§7.3, CORE-21).
3. Pure Deterministic Claim Epistemic Reducer (§4.2, §5.3, §5.4).
4. Universal Ban on Majority Voting (CORE-20): N support vs 1 refute -> CONFLICTED.
5. CONFLICTED Claim Preservation in ClaimAssessment and AssessmentReceipt.
6. D4 Authority Isolation: D4 consumes narrow authority interface; cannot access private keys directly.
7. Convergence & Drift Analysis Engine (§7.6, CORE-24 Non-Authorization Invariant).
8. Explicit Required Timestamps (missing timestamps fail closed).
9. Assessment Receipt Minting & Ed25519 Cryptographic Verification (§3.10, §7.5).
10. Property-based testing and deterministic reducer replay.
"""

import pytest
import uuid
import hashlib
from typing import Dict, List, Any
from cryptography.hazmat.primitives.asymmetric import ed25519
from hypothesis import given, strategies as st, settings

from domain.models import (
    Claim,
    ClaimSubject,
    Evidence,
    EvidenceScope,
    EvidenceObservation,
    Provenance,
    HmacSessionSignature,
    AsymmetricAuthoritySignature,
    AssessmentReceipt,
)
from domain.types import (
    ClaimTier,
    ClaimStatus,
    Criticality,
    TargetType,
    EvidencePolarity,
    EvidenceValidity,
    RawStatus,
    AssessmentVerdict,
    DriftType,
)
from policy.models import EvidenceTrustCertificate
from benchmark.parity.gate_3_authority import Gate3AuthorityKeyStore, Gate3AuthoritySigner
from claim.relevance import evaluate_relevance, is_capability_compatible, is_scope_compatible, RelevanceResult
from claim.coverage import evaluate_coverage, CoverageStatus, extract_claim_aspects, extract_evidence_aspects
from claim.reducer import (
    ClaimEpistemicState,
    reduce_claim,
    fold_claim_evidence_state,
    ClaimReductionState,
    ClaimEvidenceState,
)
from claim.convergence import ConvergenceEngine, ConvergenceFinding, ConvergenceReport
from claim.receipts import mint_assessment_receipt, verify_assessment_receipt_signature


DEFAULT_TEST_SHA = "a" * 40
ALT_TEST_SHA = "b" * 40
EVAL_TIMESTAMP = "2026-08-20T00:00:00Z"


@pytest.fixture(autouse=True)
def setup_authority_keys():
    """Initializes Gate 3 Authority KeyStore for test runs."""
    Gate3AuthorityKeyStore.clear()
    priv = ed25519.Ed25519PrivateKey.generate()
    Gate3AuthorityKeyStore.set_private_key(priv)
    yield
    Gate3AuthorityKeyStore.clear()


def make_test_claim(
    claim_id: str = "CLM-TEST-001",
    obligation_id: str = "OBL-AUTH-001",
    tier: ClaimTier = ClaimTier.V2_BEHAVIORAL,
    target_identifier: str = "auth.login",
    required_capabilities: tuple = ("PROPERTY_TESTING",),
    aspects: tuple = (),
    status: ClaimStatus = ClaimStatus.UNSUPPORTED,
) -> Claim:
    context = {"aspects": list(aspects)} if aspects else {}
    return Claim(
        claim_id=claim_id,
        obligation_id=obligation_id,
        tier=tier,
        subject=ClaimSubject(target_type=TargetType.FUNCTION, identifier=target_identifier),
        predicate="UNAUTHORIZED_REQUEST_REJECTED",
        context=context,
        expected={"status": 403},
        criticality=Criticality.HIGH,
        status=status,
        required_provider_capabilities=required_capabilities,
    )


def make_test_evidence(
    ev_id: str = "EV-001",
    claim_id: str = "CLM-TEST-001",
    polarity: EvidencePolarity = EvidencePolarity.SUPPORTS,
    validity: EvidenceValidity = EvidenceValidity.VALID,
    capability: str = "PROPERTY_TESTING",
    target_identifier: str = "auth.login",
    aspects_covered: tuple = ("functional_correctness",),
    source_sha: str = DEFAULT_TEST_SHA,
) -> Evidence:
    return Evidence(
        evidence_id=ev_id,
        claim_id=claim_id,
        provider_id="provider-test-1",
        capability=capability,
        execution_id=f"EXEC-{uuid.uuid4().hex[:8]}",
        source_sha=source_sha,
        scope=EvidenceScope(
            targets_evaluated=(target_identifier,),
            aspects_covered=aspects_covered if aspects_covered else ("default_aspect",),
        ),
        observation=EvidenceObservation(
            raw_status=RawStatus.PASS if polarity == EvidencePolarity.SUPPORTS else RawStatus.FAIL,
            diagnostics=("test trace",),
            counterexample=None if polarity == EvidencePolarity.SUPPORTS else {"input": "bad_token"},
        ),
        polarity=polarity,
        validity=validity,
        independence_group="INDEP-1",
        provenance=Provenance(
            engine_name="Hypothesis",
            engine_version="6.165.9",
            environment_hash="e" * 64,
            timestamp="2026-08-20T00:00:00Z",
        ),
        signature=HmacSessionSignature(
            algorithm="HMAC-SHA256",
            key_id="KEY-001",
            nonce=f"NONCE-{uuid.uuid4().hex[:8]}",
            raw_stdout_digest="0" * 64,
            signature_hex="0" * 64,
            timestamp="2026-08-20T00:00:00Z",
        ),
    )


# ============================================================================
# 1. Relevance Derivation Tests (§7.2)
# ============================================================================

def test_relevance_all_indicators_pass():
    """All 4 indicators (capability, scope, commit, trust) pass -> is_relevant is True."""
    claim = make_test_claim()
    ev = make_test_evidence()
    dummy_sig = AsymmetricAuthoritySignature(
        algorithm="ED25519",
        signer_identity="Gate3AuthoritativeVerifier",
        public_key_fingerprint="0" * 64,
        payload_digest="0" * 64,
        signature_hex="0" * 128,
        timestamp="2026-08-20T00:00:00Z",
    )
    cert = EvidenceTrustCertificate(
        evidence_id=ev.evidence_id,
        source_sha=ev.source_sha,
        is_verified=True,
        digest_verified=True,
        signature_verified=True,
        provenance_verified=True,
        verifier_identity="Gate3AuthoritativeVerifier",
        timestamp="2026-08-20T00:00:00Z",
        certificate_hash="0" * 64,
        authority_signature=dummy_sig,
    )
    res = evaluate_relevance(claim, ev, expected_source_sha=DEFAULT_TEST_SHA, trust_certificate=cert)
    assert res.is_relevant is True
    assert res.capability_match is True
    assert res.scope_match is True
    assert res.commit_match is True
    assert res.trust_verified is True


def test_relevance_wildcard_scope_matches():
    """Wildcard target '*' in scope matches any claim subject."""
    claim = make_test_claim(target_identifier="auth.login")
    ev = make_test_evidence(target_identifier="*")
    res = evaluate_relevance(claim, ev, expected_source_sha=DEFAULT_TEST_SHA, verified_trust=True)
    assert res.is_relevant is True
    assert res.scope_match is True


def test_relevance_none_inputs():
    """None claim or evidence returns is_relevant=False."""
    res1 = evaluate_relevance(None, make_test_evidence(), expected_source_sha=DEFAULT_TEST_SHA)
    assert res1.is_relevant is False
    res2 = evaluate_relevance(make_test_claim(), None, expected_source_sha=DEFAULT_TEST_SHA)
    assert res2.is_relevant is False


def test_relevance_capability_mismatch_fails():
    """Capability mismatch -> is_relevant is False."""
    claim = make_test_claim(required_capabilities=("STATIC_AST_ANALYSIS",))
    ev = make_test_evidence(capability="PROPERTY_TESTING")
    res = evaluate_relevance(claim, ev, expected_source_sha=DEFAULT_TEST_SHA, verified_trust=True)
    assert res.is_relevant is False
    assert res.capability_match is False
    assert "Capability mismatch" in res.rejection_reason


def test_relevance_scope_mismatch_fails():
    """Scope target mismatch -> is_relevant is False."""
    claim = make_test_claim(target_identifier="auth.login")
    ev = make_test_evidence(target_identifier="billing.checkout")
    res = evaluate_relevance(claim, ev, expected_source_sha=DEFAULT_TEST_SHA, verified_trust=True)
    assert res.is_relevant is False
    assert res.scope_match is False
    assert "Scope mismatch" in res.rejection_reason


def test_relevance_commit_mismatch_fails():
    """Evidence from old commit SHA -> is_relevant is False."""
    claim = make_test_claim()
    ev = make_test_evidence(source_sha=ALT_TEST_SHA)
    res = evaluate_relevance(claim, ev, expected_source_sha=DEFAULT_TEST_SHA, verified_trust=True)
    assert res.is_relevant is False
    assert res.commit_match is False
    assert "Commit SHA mismatch" in res.rejection_reason


def test_relevance_unverified_trust_fails():
    """Unverified D3 trust certificate -> is_relevant is False."""
    claim = make_test_claim()
    ev = make_test_evidence()
    dummy_sig = AsymmetricAuthoritySignature(
        algorithm="ED25519",
        signer_identity="Gate3AuthoritativeVerifier",
        public_key_fingerprint="0" * 64,
        payload_digest="0" * 64,
        signature_hex="0" * 128,
        timestamp="2026-08-20T00:00:00Z",
    )
    unverified_cert = EvidenceTrustCertificate(
        evidence_id=ev.evidence_id,
        source_sha=ev.source_sha,
        is_verified=False,
        digest_verified=False,
        signature_verified=False,
        provenance_verified=False,
        verifier_identity="Gate3AuthoritativeVerifier",
        timestamp="2026-08-20T00:00:00Z",
        certificate_hash="0" * 64,
        authority_signature=dummy_sig,
    )
    res = evaluate_relevance(claim, ev, expected_source_sha=DEFAULT_TEST_SHA, trust_certificate=unverified_cert)
    assert res.is_relevant is False
    assert res.trust_verified is False
    assert "Verified trust requirement failed" in res.rejection_reason


# ============================================================================
# 2. Multi-Dimensional Aspect Coverage Calculus Tests (§7.3, CORE-21)
# ============================================================================

def test_coverage_full_aspect_set():
    """Aspects A(C) is a subset of Union(A(E_i)) -> FULL coverage."""
    claim = make_test_claim(aspects=("boundary_zero", "boundary_max", "null_handling"))
    ev1 = make_test_evidence(ev_id="EV-1", aspects_covered=("boundary_zero", "boundary_max"))
    ev2 = make_test_evidence(ev_id="EV-2", aspects_covered=("null_handling", "extra_aspect"))

    cov = evaluate_coverage(claim, [ev1, ev2])
    assert cov.status == CoverageStatus.FULL
    assert cov.missing_aspects == ()


def test_coverage_partial_aspect_set():
    """Partial aspect overlap -> PARTIAL coverage (missing aspects identified)."""
    claim = make_test_claim(aspects=("boundary_zero", "boundary_max", "null_handling"))
    ev1 = make_test_evidence(ev_id="EV-1", aspects_covered=("boundary_zero",))

    cov = evaluate_coverage(claim, [ev1])
    assert cov.status == CoverageStatus.PARTIAL
    assert set(cov.missing_aspects) == {"boundary_max", "null_handling"}


def test_coverage_disjoint_aspect_set():
    """Zero aspect overlap -> NONE coverage."""
    claim = make_test_claim(aspects=("boundary_zero", "boundary_max"))
    ev1 = make_test_evidence(ev_id="EV-1", aspects_covered=("irrelevant_aspect_x",))

    cov = evaluate_coverage(claim, [ev1])
    assert cov.status == CoverageStatus.NONE
    assert set(cov.missing_aspects) == {"boundary_zero", "boundary_max"}


def test_coverage_empty_aspects_helpers():
    """Helper extractors handle None or missing contexts."""
    assert extract_claim_aspects(None) == set()
    assert extract_evidence_aspects([]) == set()
    claim_no_aspects = make_test_claim(aspects=())
    cov = evaluate_coverage(claim_no_aspects, [])
    assert cov.status == CoverageStatus.NONE


# ============================================================================
# 3. Deterministic Claim Epistemic Reducer & Anti-Majority Voting (§4.2, §5.4, CORE-20)
# ============================================================================

def test_reducer_single_valid_support_grants_supported():
    """Single valid supporting evidence with full coverage -> SUPPORTED."""
    claim = make_test_claim()
    ev = make_test_evidence(polarity=EvidencePolarity.SUPPORTS)
    reduced = reduce_claim(claim, [ev], repository_sha=DEFAULT_TEST_SHA)
    assert reduced.epistemic_state == ClaimEpistemicState.SUPPORTED
    assert reduced.supporting_evidence_ids == (ev.evidence_id,)


def test_reducer_single_refute_grants_contradicted():
    """Single valid refuting evidence -> CONTRADICTED."""
    claim = make_test_claim()
    ev = make_test_evidence(polarity=EvidencePolarity.REFUTES)
    reduced = reduce_claim(claim, [ev], repository_sha=DEFAULT_TEST_SHA)
    assert reduced.epistemic_state == ClaimEpistemicState.CONTRADICTED
    assert reduced.refuting_evidence_ids == (ev.evidence_id,)


def test_reducer_adversarial_n_support_vs_1_refute_forces_conflicted():
    """Adversarial vector: 100 SUPPORTS vs 1 REFUTES -> CONFLICTED (No majority voting!)."""
    claim = make_test_claim()
    supports = [
        make_test_evidence(ev_id=f"EV-SUP-{i:03d}", polarity=EvidencePolarity.SUPPORTS)
        for i in range(100)
    ]
    refute = make_test_evidence(ev_id="EV-REF-001", polarity=EvidencePolarity.REFUTES)

    reduced = reduce_claim(claim, supports + [refute], repository_sha=DEFAULT_TEST_SHA)
    assert reduced.epistemic_state == ClaimEpistemicState.CONFLICTED
    assert len(reduced.supporting_evidence_ids) == 100
    assert len(reduced.refuting_evidence_ids) == 1
    assert len(reduced.conflicts) == 1


def test_reducer_partial_coverage_never_grants_supported():
    """Evidence with PARTIAL aspect coverage -> UNSUPPORTED (cannot close)."""
    claim = make_test_claim(aspects=("asp1", "asp2"))
    ev = make_test_evidence(polarity=EvidencePolarity.SUPPORTS, aspects_covered=("asp1",))
    reduced = reduce_claim(claim, [ev], repository_sha=DEFAULT_TEST_SHA)
    assert reduced.epistemic_state == ClaimEpistemicState.UNSUPPORTED
    assert reduced.coverage_status == CoverageStatus.PARTIAL


def test_reducer_stale_evidence_sets_stale():
    """Evidence from old commit SHA -> STALE."""
    claim = make_test_claim()
    ev = make_test_evidence(polarity=EvidencePolarity.SUPPORTS, source_sha=ALT_TEST_SHA)
    reduced = reduce_claim(claim, [ev], repository_sha=DEFAULT_TEST_SHA)
    assert reduced.epistemic_state == ClaimEpistemicState.STALE
    assert ev.evidence_id in reduced.stale_evidence_ids


def test_reducer_duplicate_evidence_deterministic():
    """Submitting duplicate identical evidence items produces deterministic deduplicated reduction."""
    claim = make_test_claim()
    ev1 = make_test_evidence(ev_id="EV-DUP-1")
    reduced1 = reduce_claim(claim, [ev1], repository_sha=DEFAULT_TEST_SHA)
    reduced2 = reduce_claim(claim, [ev1, ev1, ev1], repository_sha=DEFAULT_TEST_SHA)
    assert reduced1.epistemic_state == reduced2.epistemic_state
    assert reduced1.supporting_evidence_ids == reduced2.supporting_evidence_ids


def test_reducer_pure_replay_identity():
    """Folding identical claim and evidence sets produces bit-for-bit identical state."""
    claims = {
        "CLM-1": make_test_claim(claim_id="CLM-1"),
        "CLM-2": make_test_claim(claim_id="CLM-2"),
    }
    catalog = {
        "EV-1": make_test_evidence(ev_id="EV-1", claim_id="CLM-1", polarity=EvidencePolarity.SUPPORTS),
        "EV-2": make_test_evidence(ev_id="EV-2", claim_id="CLM-2", polarity=EvidencePolarity.REFUTES),
    }

    state1 = fold_claim_evidence_state(claims, catalog, DEFAULT_TEST_SHA)
    state2 = fold_claim_evidence_state(claims, catalog, DEFAULT_TEST_SHA)

    assert state1 == state2
    assert state1.claims["CLM-1"].epistemic_state == ClaimEpistemicState.SUPPORTED
    assert state1.claims["CLM-2"].epistemic_state == ClaimEpistemicState.CONTRADICTED


def test_reducer_conflicted_preserved_in_claim_status():
    """CONFLICTED epistemic state maps to ClaimStatus.CONFLICTED without lossy down-mapping."""
    assert ClaimEpistemicState.SUPPORTED.to_domain_status() == ClaimStatus.SUPPORTED
    assert ClaimEpistemicState.CONTRADICTED.to_domain_status() == ClaimStatus.CONTRADICTED
    assert ClaimEpistemicState.CONFLICTED.to_domain_status() == ClaimStatus.CONFLICTED
    assert ClaimEpistemicState.STALE.to_domain_status() == ClaimStatus.STALE
    assert ClaimEpistemicState.UNSUPPORTED.to_domain_status() == ClaimStatus.UNSUPPORTED


# ============================================================================
# 4. Convergence & Drift Analysis Tests (§7.6, CORE-24)
# ============================================================================

def test_convergence_converged_state():
    """All claims supported, zero drift -> is_converged is True, drift_count is 0."""
    claims = {"CLM-1": make_test_claim(claim_id="CLM-1")}
    catalog = {"EV-1": make_test_evidence(ev_id="EV-1", claim_id="CLM-1", polarity=EvidencePolarity.SUPPORTS)}
    state = fold_claim_evidence_state(claims, catalog, DEFAULT_TEST_SHA)

    report = ConvergenceEngine.analyze_convergence(
        task_id="TASK-001",
        repository_sha=DEFAULT_TEST_SHA,
        intended_claims=claims,
        claim_states=state.claims,
        evidence_catalog=catalog,
        evaluated_at=EVAL_TIMESTAMP,
    )
    assert report.is_converged is True
    assert report.drift_count == 0
    assert len(report.findings) == 0


def test_convergence_detects_all_drift_types():
    """Detects MISSING, PARTIAL, CONTRADICTORY, UNREQUESTED, and STALE drift."""
    claims = {
        "CLM-MISSING": make_test_claim(claim_id="CLM-MISSING"),
        "CLM-PARTIAL": make_test_claim(claim_id="CLM-PARTIAL", aspects=("asp1", "asp2")),
        "CLM-CONTRADICT": make_test_claim(claim_id="CLM-CONTRADICT"),
        "CLM-STALE": make_test_claim(claim_id="CLM-STALE"),
    }
    catalog = {
        "EV-PARTIAL": make_test_evidence(ev_id="EV-PARTIAL", claim_id="CLM-PARTIAL", aspects_covered=("asp1",)),
        "EV-CONTRADICT": make_test_evidence(ev_id="EV-CONTRADICT", claim_id="CLM-CONTRADICT", polarity=EvidencePolarity.REFUTES),
        "EV-UNREQUESTED": make_test_evidence(ev_id="EV-UNREQUESTED", claim_id="CLM-UNTRACKED"),
        "EV-STALE": make_test_evidence(ev_id="EV-STALE", claim_id="CLM-STALE", source_sha=ALT_TEST_SHA),
    }
    state = fold_claim_evidence_state(claims, catalog, DEFAULT_TEST_SHA)

    report = ConvergenceEngine.analyze_convergence(
        task_id="TASK-001",
        repository_sha=DEFAULT_TEST_SHA,
        intended_claims=claims,
        claim_states=state.claims,
        evidence_catalog=catalog,
        evaluated_at=EVAL_TIMESTAMP,
    )
    assert report.is_converged is False
    drift_types = {f.finding_type for f in report.findings}
    assert DriftType.MISSING in drift_types
    assert DriftType.PARTIAL in drift_types
    assert DriftType.CONTRADICTORY in drift_types
    assert DriftType.UNREQUESTED in drift_types
    assert DriftType.STALE in drift_types


def test_convergence_missing_timestamp_rejected():
    """Missing or empty evaluated_at timestamp raises ValueError."""
    claims = {"CLM-1": make_test_claim()}
    with pytest.raises(ValueError, match="evaluated_at timestamp is required"):
        ConvergenceEngine.analyze_convergence(
            task_id="TASK-001",
            repository_sha=DEFAULT_TEST_SHA,
            intended_claims=claims,
            claim_states={},
            evidence_catalog={},
            evaluated_at="",
        )


def test_convergence_non_authorization_invariant():
    """CORE-24 Invariant: ConvergenceReport is purely diagnostic; cannot execute tools or issue tokens."""
    claims = {"CLM-1": make_test_claim()}
    catalog = {}
    state = fold_claim_evidence_state(claims, catalog, DEFAULT_TEST_SHA)
    report = ConvergenceEngine.analyze_convergence(
        task_id="TASK-001",
        repository_sha=DEFAULT_TEST_SHA,
        intended_claims=claims,
        claim_states=state.claims,
        evidence_catalog=catalog,
        evaluated_at=EVAL_TIMESTAMP,
    )
    assert not hasattr(report, "authorize")
    assert not hasattr(report, "issue_token")
    assert not hasattr(report, "execute")


# ============================================================================
# 5. Assessment Receipt Minting & Ed25519 Verification Tests (§3.10, §7.5)
# ============================================================================

def test_mint_assessment_receipt_and_verify_signature():
    """Mints Ed25519-signed AssessmentReceipt and verifies cryptographic authenticity."""
    claims = {
        "CLM-1": make_test_claim(claim_id="CLM-1"),
        "CLM-2": make_test_claim(claim_id="CLM-2"),
    }
    catalog = {
        "EV-1": make_test_evidence(ev_id="EV-1", claim_id="CLM-1", polarity=EvidencePolarity.SUPPORTS),
        "EV-2": make_test_evidence(ev_id="EV-2", claim_id="CLM-2", polarity=EvidencePolarity.SUPPORTS),
    }
    state = fold_claim_evidence_state(claims, catalog, DEFAULT_TEST_SHA)

    receipt = mint_assessment_receipt(
        receipt_id="RCPT-OBL-001-001",
        obligation_id="OBL-001",
        policy_version=1,
        repository_sha=DEFAULT_TEST_SHA,
        claim_states=state.claims,
        intended_claims=claims,
        evaluated_at=EVAL_TIMESTAMP,
    )
    assert receipt.verdict == AssessmentVerdict.SATISFIED
    assert len(receipt.claim_assessments) == 2
    assert verify_assessment_receipt_signature(receipt) is True


def test_conflicted_claim_in_assessment_receipt():
    """CONFLICTED claim is recorded with ClaimStatus.CONFLICTED and preserved in AssessmentReceipt."""
    claims = {"CLM-1": make_test_claim(claim_id="CLM-1")}
    catalog = {
        "EV-1": make_test_evidence(ev_id="EV-1", claim_id="CLM-1", polarity=EvidencePolarity.SUPPORTS),
        "EV-2": make_test_evidence(ev_id="EV-2", claim_id="CLM-1", polarity=EvidencePolarity.REFUTES),
    }
    state = fold_claim_evidence_state(claims, catalog, DEFAULT_TEST_SHA)
    assert state.claims["CLM-1"].epistemic_state == ClaimEpistemicState.CONFLICTED

    receipt = mint_assessment_receipt(
        receipt_id="RCPT-OBL-003-001",
        obligation_id="OBL-003",
        policy_version=1,
        repository_sha=DEFAULT_TEST_SHA,
        claim_states=state.claims,
        intended_claims=claims,
        evaluated_at=EVAL_TIMESTAMP,
    )
    assert receipt.verdict == AssessmentVerdict.REJECTED
    assert len(receipt.claim_assessments) == 1
    # Check that status is strictly CONFLICTED, not CONTRADICTED
    assert receipt.claim_assessments[0].status == ClaimStatus.CONFLICTED
    assert len(receipt.conflicts) == 1
    assert verify_assessment_receipt_signature(receipt) is True


def test_missing_evaluation_timestamp_rejected():
    """Minting receipt with empty evaluated_at raises ValueError."""
    claims = {"CLM-1": make_test_claim(claim_id="CLM-1")}
    with pytest.raises(ValueError, match="evaluated_at timestamp is required"):
        mint_assessment_receipt(
            receipt_id="RCPT-OBL-001-001",
            obligation_id="OBL-001",
            policy_version=1,
            repository_sha=DEFAULT_TEST_SHA,
            claim_states={},
            intended_claims=claims,
            evaluated_at="",
        )


def test_tampered_assessment_receipt_signature_rejected():
    """Adversarial vector: Modifying verdict or claim assessment breaks Ed25519 signature."""
    claims = {"CLM-1": make_test_claim(claim_id="CLM-1")}
    catalog = {"EV-1": make_test_evidence(ev_id="EV-1", claim_id="CLM-1", polarity=EvidencePolarity.REFUTES)}
    state = fold_claim_evidence_state(claims, catalog, DEFAULT_TEST_SHA)

    receipt = mint_assessment_receipt(
        receipt_id="RCPT-OBL-002-001",
        obligation_id="OBL-002",
        policy_version=1,
        repository_sha=DEFAULT_TEST_SHA,
        claim_states=state.claims,
        intended_claims=claims,
        evaluated_at=EVAL_TIMESTAMP,
    )
    assert receipt.verdict == AssessmentVerdict.REJECTED
    assert verify_assessment_receipt_signature(receipt) is True

    # Tamper with receipt verdict (forging SATISFIED)
    tampered_receipt = AssessmentReceipt(
        receipt_id=receipt.receipt_id,
        obligation_id=receipt.obligation_id,
        policy_version=receipt.policy_version,
        repository_sha=receipt.repository_sha,
        verdict=AssessmentVerdict.SATISFIED,  # Forged!
        claim_assessments=receipt.claim_assessments,
        signature=receipt.signature,
        conflicts=receipt.conflicts,
        stale_evidence=receipt.stale_evidence,
        evaluated_at=receipt.evaluated_at,
    )
    assert verify_assessment_receipt_signature(tampered_receipt) is False


def test_fabricated_d4_authority_object_rejected():
    """Fabricated / untrusted authority signer produces invalid signatures that fail verification."""
    class UntrustedAuthoritySigner:
        def sign_payload(self, canonical_bytes: bytes, verifier_identity: str, timestamp_iso: str):
            priv = ed25519.Ed25519PrivateKey.generate()
            sig_bytes = priv.sign(canonical_bytes)
            return AsymmetricAuthoritySignature(
                algorithm="ED25519",
                signer_identity="UntrustedActor",
                public_key_fingerprint="0" * 64,
                payload_digest=hashlib.sha256(canonical_bytes).hexdigest(),
                signature_hex=sig_bytes.hex(),
                timestamp=timestamp_iso,
            )

    claims = {"CLM-1": make_test_claim(claim_id="CLM-1")}
    state = fold_claim_evidence_state(claims, {}, DEFAULT_TEST_SHA)

    receipt = mint_assessment_receipt(
        receipt_id="RCPT-OBL-UNTRUSTED-001",
        obligation_id="OBL-001",
        policy_version=1,
        repository_sha=DEFAULT_TEST_SHA,
        claim_states=state.claims,
        intended_claims=claims,
        evaluated_at=EVAL_TIMESTAMP,
        authority_signer=UntrustedAuthoritySigner(),
    )
    # Verification against genuine authority fails closed
    assert verify_assessment_receipt_signature(receipt) is False


def test_d4_cannot_access_private_key_directly():
    """D4 claim modules do not expose or contain direct access to Gate3AuthorityKeyStore private keys."""
    import claim.receipts as cr
    import claim.reducer as cred
    import claim.convergence as cconv
    import claim.relevance as crel
    import claim.coverage as ccov

    # Check that none of the claim modules import Gate3AuthorityKeyStore
    for mod in (cr, cred, cconv, crel, ccov):
        assert not hasattr(mod, "Gate3AuthorityKeyStore")
        assert not hasattr(mod, "_private_key")
        assert not hasattr(mod, "get_private_key")


# ============================================================================
# 6. Property-Based Testing (Hypothesis)
# ============================================================================

@settings(max_examples=50)
@given(
    num_supports=st.integers(min_value=1, max_value=20),
    num_refutes=st.integers(min_value=0, max_value=20),
)
def test_hypothesis_contradiction_supremacy_property(num_supports, num_refutes):
    """Property: Any non-zero count of refuting evidence strictly forces CONTRADICTED or CONFLICTED."""
    claim = make_test_claim()
    ev_list = []
    for i in range(num_supports):
        ev_list.append(make_test_evidence(ev_id=f"EV-S-{i}", polarity=EvidencePolarity.SUPPORTS))
    for j in range(num_refutes):
        ev_list.append(make_test_evidence(ev_id=f"EV-R-{j}", polarity=EvidencePolarity.REFUTES))

    reduced = reduce_claim(claim, ev_list, DEFAULT_TEST_SHA)

    if num_refutes > 0 and num_supports > 0:
        assert reduced.epistemic_state == ClaimEpistemicState.CONFLICTED
    elif num_refutes > 0:
        assert reduced.epistemic_state == ClaimEpistemicState.CONTRADICTED
    elif num_supports > 0:
        assert reduced.epistemic_state == ClaimEpistemicState.SUPPORTED
