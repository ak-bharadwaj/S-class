"""Authoritative Test Suite for R30 Section F7 Claim Ledger & Reference Verification.

Normative Reference:
    R30 Master Product Design (FREEZE-CANDIDATE-v6.0.2), Section F7.
    Obligations: PD-F7-001 through PD-F7-006.
    Authoritative Fixtures: F7-T1 through F7-T6.

Coverage:
    - Master Fixture F7-T1: Reference symbol claim -> SATISFIED.
    - Master Fixture F7-T2: Behavioral claim without evidence -> MISSING[PD-F7-002].
    - Master Fixture F7-T3: Hallucinated reference absent pre-delta -> MISSING[PD-F7-004].
    - Master Fixture F7-T4: Dependency digest mismatch -> MISSING[PD-F7-003].
    - Master Fixture F7-T5: Claim-type evidence rules -> SATISFIED, SATISFIED, MISSING[PD-F7-005].
    - Master Fixture F7-T6: Post-delta symbol resolution & precedence -> SATISFIED, MISSING[PD-F7-006], MISSING[PD-F7-004].
    - Positive and negative tests for every PD ID (PD-F7-001 through PD-F7-006).
    - Fail-closed behavior at every trust boundary and anti-gaming protection.
"""

from __future__ import annotations

import pytest

from sclass.product.claim_ledger import (
    CanonicalDependencyResolver,
    ClaimRecord,
    ClaimType,
    EvaluatorResolution,
    InMemoryCanonicalDependencyResolver,
    InMemoryKernelEvidenceResolver,
    InMemoryObligationClosureResolver,
    InMemoryRepositoryIntelligenceIndex,
    KernelEvidenceResolver,
    ObligationClosureResolver,
    ReferenceKind,
    RepositoryIntelligenceIndex,
    evaluate_f7_claim,
    evaluate_f7_claim_ledger,
    evaluate_f7_claims,
)
from sclass.product.trust_model import GateState


# =============================================================================
# PART 1: Authoritative Master Fixture Verification (F7-T1 through F7-T6)
# =============================================================================

def test_f7_t1_reference_symbol_claim() -> None:
    """Fixture F7-T1 / F7-FT1: Reference symbol claim with successful resolution.
    
    Fixture YAML:
        claim_id: CL-1
        type: reference
        reference_kind: symbol
        subject: "pkg.rate_limiter:Limiter"
        evidence_refs: []
        target_snapshot: TS-1
        evaluator_resolution: RESOLVED
        expected_gate_output: SATISFIED
    """
    fixture = {
        "claim_id": "CL-1",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.rate_limiter:Limiter",
        "evidence_refs": [],
        "target_snapshot": "TS-1",
        "evaluator_resolution": "RESOLVED",
    }
    result = evaluate_f7_claim(fixture)
    assert result.state == GateState.SATISFIED
    assert str(result) == "SATISFIED"
    assert result == "SATISFIED"


def test_f7_t2_behavioral_claim_without_evidence() -> None:
    """Fixture F7-T2 / F7-FT2: Behavioral claim with empty evidence_refs.
    
    Fixture YAML:
        claim_id: CL-2
        type: behavioral
        subject: "POST /rate-limit"
        evidence_refs: []
        target_snapshot: TS-1
        expected_gate_output: MISSING[PD-F7-002]
    """
    fixture = {
        "claim_id": "CL-2",
        "type": "behavioral",
        "subject": "POST /rate-limit",
        "evidence_refs": [],
        "target_snapshot": "TS-1",
    }
    result = evaluate_f7_claim(fixture)
    assert result.state == GateState.MISSING
    assert result.must_id == "PD-F7-002"
    assert str(result) == "MISSING[PD-F7-002]"
    assert result == "MISSING[PD-F7-002]"


def test_f7_t3_hallucinated_reference() -> None:
    """Fixture F7-T3 / F7-FT3: Hallucinated reference absent from pre-delta view.
    
    Fixture YAML:
        claim_id: CL-3
        type: reference
        reference_kind: symbol
        subject: "pkg.hallucinated:MissingClass"
        evidence_refs: []
        created_by_delta: false
        target_snapshot: TS-1
        evaluator_resolution: MISSING
        expected_gate_output: MISSING[PD-F7-004]
    """
    fixture = {
        "claim_id": "CL-3",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.hallucinated:MissingClass",
        "evidence_refs": [],
        "created_by_delta": False,
        "target_snapshot": "TS-1",
        "evaluator_resolution": "MISSING",
    }
    result = evaluate_f7_claim(fixture)
    assert result.state == GateState.MISSING
    assert result.must_id == "PD-F7-004"
    assert str(result) == "MISSING[PD-F7-004]"
    assert result == "MISSING[PD-F7-004]"


def test_f7_t4_dependency_digest_mismatch() -> None:
    """Fixture F7-T4 / F7-FT4: Package dependency digest mismatch.
    
    Fixture YAML:
        claim_id: CL-4
        type: reference
        reference_kind: package
        subject: "ratelimit-core"
        evidence_refs: []
        target_snapshot: TS-1
        expected_dependency_digest: D1
        canonical_dependency_set_digest: D2
        expected_gate_output: MISSING[PD-F7-003]
    """
    fixture = {
        "claim_id": "CL-4",
        "type": "reference",
        "reference_kind": "package",
        "subject": "ratelimit-core",
        "evidence_refs": [],
        "target_snapshot": "TS-1",
        "expected_dependency_digest": "D1",
        "canonical_dependency_set_digest": "D2",
    }
    result = evaluate_f7_claim(fixture)
    assert result.state == GateState.MISSING
    assert result.must_id == "PD-F7-003"
    assert str(result) == "MISSING[PD-F7-003]"
    assert result == "MISSING[PD-F7-003]"


def test_f7_t5_claim_type_evidence_rules() -> None:
    """Fixture F7-T5 / F7-FT5: Closed claim-type evidence rules.
    
    Fixture YAML:
        reference_claim:
          type: reference
          subject: "pkg.rate_limiter:Limiter"
          evaluator_resolution: RESOLVED
        behavioral_claim:
          type: behavioral
          evidence_refs: [EV-B1]
          kernel_evidence_resolves: true
        completion_claim:
          type: completion
          evidence_refs: []
          obligation_closed: false
        expected_reference_result: SATISFIED
        expected_behavioral_result: SATISFIED
        expected_completion_result: MISSING[PD-F7-005]
    """
    fixture = {
        "reference_claim": {
            "claim_id": "CL-T5-REF",
            "type": "reference",
            "subject": "pkg.rate_limiter:Limiter",
            "evaluator_resolution": "RESOLVED",
        },
        "behavioral_claim": {
            "claim_id": "CL-T5-BEH",
            "type": "behavioral",
            "subject": "Execute tests",
            "evidence_refs": ["EV-B1"],
            "kernel_evidence_resolves": True,
        },
        "completion_claim": {
            "claim_id": "CL-T5-COMP",
            "type": "completion",
            "subject": "Obligation closure",
            "evidence_refs": [],
            "obligation_closed": False,
        },
    }
    results = evaluate_f7_claim_ledger(fixture)
    assert isinstance(results, dict)
    assert results["reference"].state == GateState.SATISFIED
    assert str(results["reference"]) == "SATISFIED"
    assert results["behavioral"].state == GateState.SATISFIED
    assert str(results["behavioral"]) == "SATISFIED"
    assert results["completion"].state == GateState.MISSING
    assert results["completion"].must_id == "PD-F7-005"
    assert str(results["completion"]) == "MISSING[PD-F7-005]"


def test_f7_t6_post_delta_symbol_resolution() -> None:
    """Fixture F7-T6 / F7-FT6: Post-delta symbol resolution & precedence.
    
    Fixture YAML:
        reference_kind: symbol
        pre_delta_index: []
        post_delta_overlay: [pkg.rate_limit.check]
        claim_subject: pkg.rate_limit.check
        created_by_delta: true
        expected_gate_output: SATISFIED
        absent_case_subject: pkg.missing.check
        absent_case_created_by_delta: true
        absent_case_post_delta_present: false
        expected_absent_case: MISSING[PD-F7-006]
        pre_existing_absent_subject: pkg.legacy.missing
        pre_existing_created_by_delta: false
        expected_pre_existing_absent: MISSING[PD-F7-004]
    """
    fixture = {
        "reference_kind": "symbol",
        "pre_delta_index": [],
        "post_delta_overlay": ["pkg.rate_limit.check"],
        "claim_subject": "pkg.rate_limit.check",
        "created_by_delta": True,
        "absent_case_subject": "pkg.missing.check",
        "absent_case_created_by_delta": True,
        "absent_case_post_delta_present": False,
        "pre_existing_absent_subject": "pkg.legacy.missing",
        "pre_existing_created_by_delta": False,
    }
    results = evaluate_f7_claim_ledger(fixture)
    assert isinstance(results, dict)
    # Case 1: Delta-created present post-delta -> SATISFIED
    assert results["delta_created_present"].state == GateState.SATISFIED
    assert str(results["delta_created_present"]) == "SATISFIED"
    # Case 2: Delta-created absent post-delta -> MISSING[PD-F7-006]
    assert results["delta_created_absent"].state == GateState.MISSING
    assert results["delta_created_absent"].must_id == "PD-F7-006"
    assert str(results["delta_created_absent"]) == "MISSING[PD-F7-006]"
    # Case 3: Pre-existing absent pre-delta -> MISSING[PD-F7-004]
    assert results["pre_existing_absent"].state == GateState.MISSING
    assert results["pre_existing_absent"].must_id == "PD-F7-004"
    assert str(results["pre_existing_absent"]) == "MISSING[PD-F7-004]"


# =============================================================================
# PART 2: Normative Obligation Unit Tests (PD-F7-001 through PD-F7-006)
# =============================================================================

# --- PD-F7-001: Structured Claim Requirement & Prose Rejection ---

def test_pd_f7_001_prose_alone_fails_closed() -> None:
    """PD-F7-001: Raw prose string cannot create a claim; fails closed."""
    prose_input = "We claim that the system now achieves 100% throughput and rate limits correctly."
    res = evaluate_f7_claim(prose_input)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-001"
    assert "Prose alone MUST NOT create a claim" in (res.detail or "")


def test_pd_f7_001_missing_required_fields_fails_closed() -> None:
    """PD-F7-001: Claim missing claim_id, type, or subject fails closed."""
    # Missing claim_id
    res1 = evaluate_f7_claim({"type": "reference", "subject": "pkg.foo"})
    assert res1.state == GateState.MISSING
    assert res1.must_id == "PD-F7-001"

    # Missing type
    res2 = evaluate_f7_claim({"claim_id": "C-1", "subject": "pkg.foo"})
    assert res2.state == GateState.MISSING
    assert res2.must_id == "PD-F7-001"

    # Missing subject
    res3 = evaluate_f7_claim({"claim_id": "C-1", "type": "reference"})
    assert res3.state == GateState.MISSING
    assert res3.must_id == "PD-F7-001"


def test_pd_f7_001_empty_mapping_fails_closed() -> None:
    """PD-F7-001: Empty claim mapping fails closed."""
    res = evaluate_f7_claim({})
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-001"


def test_pd_f7_001_anti_gaming_embedded_resolver_ignored() -> None:
    """PD-F7-001 / Anti-Gaming: Candidate-embedded resolver in claim dict is ignored."""
    class FakeResolver:
        def resolve_reference(self, *args, **kwargs) -> bool:
            return True

    # Candidate attempts to inject its own resolver inside claim dictionary
    claim = {
        "claim_id": "CL-HACK",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.fake:Symbol",
        "created_by_delta": False,
        "evaluator_resolution": "MISSING",
        "resolver": FakeResolver(),
    }
    # Evaluator must ignore 'resolver' in claim dict and fail closed under PD-F7-004
    res = evaluate_f7_claim(claim)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-004"


# --- PD-F7-002: Evidence References for Behavioral and Completion Claims ---

def test_pd_f7_002_behavioral_claim_missing_evidence_fails_closed() -> None:
    """PD-F7-002: Behavioral claim with empty or absent evidence_refs fails closed."""
    claim = {
        "claim_id": "CL-BEH-EMPTY",
        "type": "behavioral",
        "subject": "run_benchmark",
        "evidence_refs": [],
    }
    res = evaluate_f7_claim(claim)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-002"


def test_pd_f7_002_behavioral_claim_kernel_evidence_resolves_false() -> None:
    """PD-F7-002: Behavioral claim with kernel_evidence_resolves=False fails closed."""
    claim = {
        "claim_id": "CL-BEH-RESOLVES-FALSE",
        "type": "behavioral",
        "subject": "run_benchmark",
        "evidence_refs": ["EV-1"],
        "kernel_evidence_resolves": False,
    }
    res = evaluate_f7_claim(claim)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-002"
    assert "does not resolve to kernel evidence" in (res.detail or "")


def test_pd_f7_002_behavioral_claim_unresolvable_evidence_fails_closed() -> None:
    """PD-F7-002: Behavioral claim with unresolvable kernel evidence fails closed."""
    resolver = InMemoryKernelEvidenceResolver(valid_refs=["EV-VALID-1"])
    claim = {
        "claim_id": "CL-BEH-UNRES",
        "type": "behavioral",
        "subject": "run_benchmark",
        "evidence_refs": ["EV-UNKNOWN-99"],
    }
    res = evaluate_f7_claim(claim, evidence_resolver=resolver)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-002"
    assert "not found in kernel evidence store" in (res.detail or "")


def test_pd_f7_002_behavioral_claim_valid_evidence_satisfied() -> None:
    """PD-F7-002: Behavioral claim with valid resolved kernel evidence satisfies gate."""
    resolver = InMemoryKernelEvidenceResolver(valid_refs=["EV-VALID-1", "EV-VALID-2"])
    claim = {
        "claim_id": "CL-BEH-OK",
        "type": "behavioral",
        "subject": "run_benchmark",
        "evidence_refs": ["EV-VALID-1", "EV-VALID-2"],
    }
    res = evaluate_f7_claim(claim, evidence_resolver=resolver)
    assert res.state == GateState.SATISFIED


def test_pd_f7_002_reference_claim_optional_evidence_refs() -> None:
    """PD-F7-002: Reference claims do NOT require agent evidence_refs; evaluator resolution suffices."""
    claim = {
        "claim_id": "CL-REF-OPT",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.auth:login",
        "evidence_refs": [],
        "evaluator_resolution": "RESOLVED",
    }
    res = evaluate_f7_claim(claim)
    assert res.state == GateState.SATISFIED


# --- PD-F7-003: Proposed Packages and TargetSnapshot / Dependency Identity ---

def test_pd_f7_003_package_digest_mismatch_fails_closed() -> None:
    """PD-F7-003: Package dependency expected digest vs canonical set digest mismatch fails closed."""
    resolver = InMemoryCanonicalDependencyResolver({
        "ratelimit-core": "sha256:canonical-digest-2222",
    })
    claim = {
        "claim_id": "CL-DEP-MISMATCH",
        "type": "reference",
        "reference_kind": "package",
        "subject": "ratelimit-core",
        "expected_dependency_digest": "sha256:claimed-digest-1111",
    }
    res = evaluate_f7_claim(claim, dependency_resolver=resolver)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-003"
    assert "digest mismatch" in (res.detail or "")


def test_pd_f7_003_package_absent_from_canonical_set_fails_closed() -> None:
    """PD-F7-003: Package absent from CanonicalDependencySet fails closed."""
    resolver = InMemoryCanonicalDependencyResolver({
        "ratelimit-core": "sha256:canonical-digest-2222",
    })
    claim = {
        "claim_id": "CL-DEP-ABSENT",
        "type": "reference",
        "reference_kind": "package",
        "subject": "unknown-lib",
        "expected_dependency_digest": "sha256:any",
    }
    res = evaluate_f7_claim(claim, dependency_resolver=resolver)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-003"
    assert "absent from CanonicalDependencySet" in (res.detail or "")


def test_pd_f7_003_package_matching_canonical_digest_satisfied() -> None:
    """PD-F7-003: Package matching canonical dependency set digest satisfies gate."""
    resolver = InMemoryCanonicalDependencyResolver({
        "ratelimit-core": "sha256:match-digest-3333",
    })
    claim = {
        "claim_id": "CL-DEP-OK",
        "type": "reference",
        "reference_kind": "package",
        "subject": "ratelimit-core",
        "expected_dependency_digest": "sha256:match-digest-3333",
    }
    res = evaluate_f7_claim(claim, dependency_resolver=resolver)
    assert res.state == GateState.SATISFIED


def test_pd_f7_003_anti_gaming_package_name_alone_forbidden() -> None:
    """PD-F7-003 / NEVER: Package resolution by name alone without digest verification is forbidden."""
    claim = {
        "claim_id": "CL-DEP-NAME-ONLY",
        "type": "reference",
        "reference_kind": "package",
        "subject": "ratelimit-core",
        # No expected_dependency_digest or canonical_dependency_set_digest provided
    }
    res = evaluate_f7_claim(claim)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-003"
    assert "name alone" in (res.detail or "")


# --- PD-F7-004: Pre-Existing Reference Absence from Pre-Delta View ---

def test_pd_f7_004_pre_existing_symbol_absent_fails_closed() -> None:
    """PD-F7-004: Pre-existing reference absent from pre-delta view yields MISSING[PD-F7-004]."""
    repo = InMemoryRepositoryIntelligenceIndex(
        pre_delta_symbols=["pkg.core:OldClass"],
        post_delta_overlay=[],
    )
    claim = {
        "claim_id": "CL-PRE-ABSENT",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.core:NonExistent",
        "created_by_delta": False,
    }
    res = evaluate_f7_claim(claim, repo_index=repo)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-004"


def test_pd_f7_004_pre_existing_symbol_present_satisfied() -> None:
    """PD-F7-004: Pre-existing reference present in pre-delta view satisfies gate."""
    repo = InMemoryRepositoryIntelligenceIndex(
        pre_delta_symbols=["pkg.core:OldClass"],
        post_delta_overlay=[],
    )
    claim = {
        "claim_id": "CL-PRE-OK",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.core:OldClass",
        "created_by_delta": False,
    }
    res = evaluate_f7_claim(claim, repo_index=repo)
    assert res.state == GateState.SATISFIED


def test_pd_f7_004_pre_existing_import_absent_fails_closed() -> None:
    """PD-F7-004: Pre-existing import reference absent pre-delta yields MISSING[PD-F7-004]."""
    repo = InMemoryRepositoryIntelligenceIndex(
        pre_delta_symbols=["os", "sys"],
        post_delta_overlay=[],
    )
    claim = {
        "claim_id": "CL-IMP-ABSENT",
        "type": "reference",
        "reference_kind": "import",
        "subject": "math_advanced",
        "created_by_delta": False,
    }
    res = evaluate_f7_claim(claim, repo_index=repo)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-004"


# --- PD-F7-005: Closed Claim-Type Registry & Declared Evidence Rules ---

def test_pd_f7_005_invalid_claim_type_fails_closed() -> None:
    """PD-F7-005: Unregistered claim type outside {reference, behavioral, completion} fails closed."""
    claim = {
        "claim_id": "CL-BAD-TYPE",
        "type": "speculative",
        "subject": "AI will pass benchmark",
    }
    res = evaluate_f7_claim(claim)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-005"
    assert "Invalid claim type" in (res.detail or "")


def test_pd_f7_005_completion_claim_unclosed_obligation_fails_closed() -> None:
    """PD-F7-005: Completion claim without governing obligation closure fails closed."""
    obl_resolver = InMemoryObligationClosureResolver(closed_obligations=["OBL-1"])
    claim = {
        "claim_id": "CL-COMP-OPEN",
        "type": "completion",
        "subject": "OBL-2",
        "obligation_ref": "OBL-2",
        "evidence_refs": ["EV-1"],
    }
    res = evaluate_f7_claim(claim, obligation_resolver=obl_resolver)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-005"
    assert "not closed by admissible evidence" in (res.detail or "")


def test_pd_f7_005_completion_claim_closed_obligation_satisfied() -> None:
    """PD-F7-005: Completion claim with closed governing obligation satisfies gate."""
    obl_resolver = InMemoryObligationClosureResolver(closed_obligations=["OBL-1"])
    claim = {
        "claim_id": "CL-COMP-CLOSED",
        "type": "completion",
        "subject": "OBL-1",
        "obligation_ref": "OBL-1",
        "obligation_closed": True,
        "evidence_refs": ["EV-1"],
    }
    res = evaluate_f7_claim(claim, obligation_resolver=obl_resolver)
    assert res.state == GateState.SATISFIED


def test_pd_f7_005_anti_gaming_agent_self_report_completion_rejected() -> None:
    """PD-F7-005 / Anti-Gaming: Completion claims cannot rely on agent self-report alone."""
    claim = {
        "claim_id": "CL-COMP-SELF-REPORT",
        "type": "completion",
        "subject": "Requirement R1 fully satisfied by candidate",
        "agent_asserted_status": "PASS",
        "obligation_closed": False,
        "evidence_refs": [],
    }
    res = evaluate_f7_claim(claim)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-005"


# --- PD-F7-006: Post-Delta Overlay Resolution & Precedence ---

def test_pd_f7_006_delta_created_symbol_present_post_delta_satisfied() -> None:
    """PD-F7-006: Delta-created symbol resolving in post-delta overlay satisfies gate."""
    repo = InMemoryRepositoryIntelligenceIndex(
        pre_delta_symbols=[],
        post_delta_overlay=["pkg.new_feature:Handler"],
    )
    claim = {
        "claim_id": "CL-DELTA-OK",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.new_feature:Handler",
        "created_by_delta": True,
    }
    res = evaluate_f7_claim(claim, repo_index=repo)
    assert res.state == GateState.SATISFIED


def test_pd_f7_006_delta_created_symbol_absent_post_delta_fails_closed() -> None:
    """PD-F7-006: Delta-created symbol absent from post-delta overlay yields MISSING[PD-F7-006]."""
    repo = InMemoryRepositoryIntelligenceIndex(
        pre_delta_symbols=[],
        post_delta_overlay=["pkg.new_feature:OtherClass"],
    )
    claim = {
        "claim_id": "CL-DELTA-ABSENT",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.new_feature:Handler",
        "created_by_delta": True,
    }
    res = evaluate_f7_claim(claim, repo_index=repo)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-006"


def test_pd_f7_006_delta_created_symbol_post_delta_present_false_without_repo_index() -> None:
    """PD-F7-006: Delta-created symbol with post_delta_present=False fails closed."""
    claim = {
        "claim_id": "CL-DELTA-ABSENT-NO-INDEX",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.new_feature:Handler",
        "created_by_delta": True,
        "post_delta_present": False,
    }
    res = evaluate_f7_claim(claim)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-006"
    assert "absent from post-delta repository overlay" in (res.detail or "")


def test_pd_f7_006_precedence_delta_created_governed_by_post_delta_overlay() -> None:
    """PD-F7-006 / Precedence: When created_by_delta=True, absence post-delta fails under PD-F7-006,
    even if the symbol coincidentally existed pre-delta."""
    repo = InMemoryRepositoryIntelligenceIndex(
        pre_delta_symbols=["pkg.coincidental:Symbol"],
        post_delta_overlay=[],  # Deleted or absent in post-delta overlay
    )
    claim = {
        "claim_id": "CL-PRECEDENCE",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.coincidental:Symbol",
        "created_by_delta": True,  # Asserts delta creation
    }
    res = evaluate_f7_claim(claim, repo_index=repo)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-006"  # Must fail under PD-F7-006, NOT PD-F7-004!


# =============================================================================
# PART 3: Schema Serialization, Canonical Identity, and Claim Sequences
# =============================================================================

def test_claim_record_dataclass_validation() -> None:
    """ClaimRecord validates string types and required non-empty fields."""
    with pytest.raises(ValueError, match="non-empty string 'claim_id'"):
        ClaimRecord(claim_id="", type="reference", subject="foo")

    with pytest.raises(ValueError, match="non-empty string 'type'"):
        ClaimRecord(claim_id="C1", type="", subject="foo")

    with pytest.raises(ValueError, match="non-empty string 'subject'"):
        ClaimRecord(claim_id="C1", type="reference", subject="")


def test_claim_record_to_dict_and_from_dict() -> None:
    """ClaimRecord supports round-trip dictionary serialization matching schema."""
    rec = ClaimRecord(
        claim_id="CL-TEST-ROUNDTRIP",
        type="reference",
        reference_kind="symbol",
        subject="pkg.module:Class",
        created_by_delta=True,
        evidence_refs=("EV-1", "EV-2"),
        target_snapshot_ref="TS-GOLDEN",
        dependency_digest="sha256:dep-digest-1",
        expected_dependency_digest="sha256:dep-digest-1",
        canonical_dependency_set_digest="sha256:dep-digest-1",
    )
    d = rec.to_dict()
    assert d["claim_id"] == "CL-TEST-ROUNDTRIP"
    assert d["type"] == "reference"
    assert d["reference_kind"] == "symbol"
    assert d["created_by_delta"] is True
    assert d["evidence_refs"] == ["EV-1", "EV-2"]
    assert d["content_digest"] == rec.content_digest

    rec2 = ClaimRecord.from_dict(d)
    assert rec2.claim_id == rec.claim_id
    assert rec2.type == rec.type
    assert rec2.reference_kind == rec.reference_kind
    assert rec2.subject == rec.subject
    assert rec2.created_by_delta == rec.created_by_delta
    assert rec2.evidence_refs == rec.evidence_refs
    assert rec2.content_digest == rec.content_digest


def test_claim_record_canonical_c1_content_digest_stability() -> None:
    """ClaimRecord computes deterministic C1 canonical content digests."""
    rec1 = ClaimRecord(
        claim_id="CL-HASH-TEST",
        type="reference",
        reference_kind="symbol",
        subject="pkg.rate_limit:check",
        created_by_delta=False,
        evidence_refs=(),
    )
    rec2 = ClaimRecord(
        claim_id="CL-HASH-TEST",
        type="reference",
        reference_kind="symbol",
        subject="pkg.rate_limit:check",
        created_by_delta=False,
        evidence_refs=(),
    )
    assert rec1.content_digest is not None
    assert rec1.content_digest == rec2.content_digest
    assert len(rec1.content_digest) == 64


def test_evaluate_f7_claims_sequence_handling() -> None:
    """evaluate_f7_claims evaluates a sequence of claims and fails closed on first missing."""
    repo = InMemoryRepositoryIntelligenceIndex(
        pre_delta_symbols=["pkg.core:A", "pkg.core:B"],
    )
    valid_claims = [
        ClaimRecord(claim_id="C1", type="reference", reference_kind="symbol", subject="pkg.core:A"),
        ClaimRecord(claim_id="C2", type="reference", reference_kind="symbol", subject="pkg.core:B"),
    ]
    res_ok = evaluate_f7_claims(valid_claims, repo_index=repo)
    assert res_ok.state == GateState.SATISFIED

    failing_claims = [
        ClaimRecord(claim_id="C1", type="reference", reference_kind="symbol", subject="pkg.core:A"),
        ClaimRecord(claim_id="C2_FAIL", type="reference", reference_kind="symbol", subject="pkg.missing:C"),
    ]
    res_fail = evaluate_f7_claims(failing_claims, repo_index=repo)
    assert res_fail.state == GateState.MISSING
    assert res_fail.must_id == "PD-F7-004"

    res_empty = evaluate_f7_claims([])
    assert res_empty.state == GateState.MISSING
    assert res_empty.must_id == "PD-F7-001"
