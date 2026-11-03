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

from typing import Any
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
    VALID_REFERENCE_KINDS,
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
    repo = InMemoryRepositoryIntelligenceIndex(pre_delta_symbols={"pkg.rate_limiter:Limiter"})
    fixture = {
        "claim_id": "CL-1",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.rate_limiter:Limiter",
        "evidence_refs": [],
        "target_snapshot": "TS-1",
        "evaluator_resolution": "RESOLVED",
    }
    result = evaluate_f7_claim(fixture, repo_index=repo)
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
    repo = InMemoryRepositoryIntelligenceIndex(pre_delta_symbols={"pkg.rate_limiter:Limiter"})
    ev_resolver = InMemoryKernelEvidenceResolver(valid_refs=["EV-B1"])
    obl_resolver = InMemoryObligationClosureResolver(closed_obligations=set())
    results = evaluate_f7_claim_ledger(
        fixture,
        repo_index=repo,
        evidence_resolver=ev_resolver,
        obligation_resolver=obl_resolver,
    )
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
    repo = InMemoryRepositoryIntelligenceIndex(
        pre_delta_symbols=set(fixture["pre_delta_index"]),
        post_delta_overlay=set(fixture["post_delta_overlay"]),
    )
    results = evaluate_f7_claim_ledger(fixture, repo_index=repo)
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
    # 1. Without resolver injected
    res = evaluate_f7_claim(claim)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-002"

    # 2. With resolver injected: empty evidence_refs must still fail closed under PD-F7-002
    resolver = InMemoryKernelEvidenceResolver(valid_refs=["EV-1"])
    res_with_res = evaluate_f7_claim(claim, evidence_resolver=resolver)
    assert res_with_res.state == GateState.MISSING
    assert res_with_res.must_id == "PD-F7-002"
    assert "lacks required evidence_refs" in (res_with_res.detail or "")


def test_pd_f7_002_behavioral_claim_kernel_evidence_resolves_false() -> None:
    """PD-F7-002: Behavioral claim without resolvable evidence fails closed."""
    claim = {
        "claim_id": "CL-BEH-RESOLVES-FALSE",
        "type": "behavioral",
        "subject": "run_benchmark",
        "evidence_refs": ["EV-1"],
        "kernel_evidence_resolves": False,
    }
    res_no_res = evaluate_f7_claim(claim)
    assert res_no_res.state == GateState.MISSING
    assert res_no_res.must_id == "PD-F7-002"

    resolver = InMemoryKernelEvidenceResolver(valid_refs=[])
    res = evaluate_f7_claim(claim, evidence_resolver=resolver)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-002"
    assert "not found in kernel evidence store" in (res.detail or "")


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
    """PD-F7-002: Reference claims do NOT require agent evidence_refs; repo_index resolution suffices."""
    repo = InMemoryRepositoryIntelligenceIndex(pre_delta_symbols={"pkg.auth:login"})
    claim = {
        "claim_id": "CL-REF-OPT",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.auth:login",
        "evidence_refs": [],
    }
    res = evaluate_f7_claim(claim, repo_index=repo)
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
    resolver = InMemoryCanonicalDependencyResolver({
        "ratelimit-core": "sha256:canonical-digest-1234",
    })
    claim = {
        "claim_id": "CL-DEP-NAME-ONLY",
        "type": "reference",
        "reference_kind": "package",
        "subject": "ratelimit-core",
        # No expected_dependency_digest provided
    }
    # 1. With resolver injected: fails because name alone without digest verification
    res_with_res = evaluate_f7_claim(claim, dependency_resolver=resolver)
    assert res_with_res.state == GateState.MISSING
    assert res_with_res.must_id == "PD-F7-003"
    assert "name alone" in (res_with_res.detail or "")

    # 2. Without resolver injected: fails because dependency_resolver required
    res_no_res = evaluate_f7_claim(claim)
    assert res_no_res.state == GateState.MISSING
    assert res_no_res.must_id == "PD-F7-003"


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
    ev_resolver = InMemoryKernelEvidenceResolver(valid_refs=["EV-1"])
    claim = {
        "claim_id": "CL-COMP-OPEN",
        "type": "completion",
        "subject": "OBL-2",
        "obligation_ref": "OBL-2",
        "evidence_refs": ["EV-1"],
    }
    res = evaluate_f7_claim(claim, obligation_resolver=obl_resolver, evidence_resolver=ev_resolver)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-005"
    assert "not closed by admissible evidence" in (res.detail or "")


def test_pd_f7_005_completion_claim_closed_obligation_satisfied() -> None:
    """PD-F7-005: Completion claim with closed governing obligation satisfies gate."""
    obl_resolver = InMemoryObligationClosureResolver(closed_obligations=["OBL-1"])
    ev_resolver = InMemoryKernelEvidenceResolver(valid_refs=["EV-1"])
    claim = {
        "claim_id": "CL-COMP-CLOSED",
        "type": "completion",
        "subject": "OBL-1",
        "obligation_ref": "OBL-1",
        "obligation_closed": True,
        "evidence_refs": ["EV-1"],
    }
    res = evaluate_f7_claim(claim, obligation_resolver=obl_resolver, evidence_resolver=ev_resolver)
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
    """PD-F7-006: Delta-created symbol absent from post-delta overlay or missing repo index fails closed."""
    claim = {
        "claim_id": "CL-DELTA-ABSENT-NO-INDEX",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.new_feature:Handler",
        "created_by_delta": True,
        "post_delta_present": False,
    }
    res_no_idx = evaluate_f7_claim(claim)
    assert res_no_idx.state == GateState.MISSING
    assert res_no_idx.must_id == "PD-F7-006"
    assert "requires a caller-injected RepositoryIntelligenceIndex" in (res_no_idx.detail or "")

    repo = InMemoryRepositoryIntelligenceIndex(post_delta_overlay=[])
    res_with_idx = evaluate_f7_claim(claim, repo_index=repo)
    assert res_with_idx.state == GateState.MISSING
    assert res_with_idx.must_id == "PD-F7-006"
    assert "absent from post-delta overlay" in (res_with_idx.detail or "")


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


# =============================================================================
# PART 4: No-Resolver Negative Test Matrix (CL Probes 1-4 & Resolver Omission)
# =============================================================================

def test_cl_probe_1_behavioral_invented_evidence_no_resolver() -> None:
    """CL Probe 1: Behavioral claim with invented evidence reference and NO resolvers injected.
    
    Must fail closed with MISSING[PD-F7-002].
    Non-empty evidence_refs is NOT proof without caller-injected KernelEvidenceResolver.
    """
    claim = {
        "claim_id": "CL-PROBE-1",
        "type": "behavioral",
        "subject": "Execute security benchmark",
        "evidence_refs": ["EV-INVENTED-FAKE-999"],
        "kernel_evidence_resolves": True,  # Candidate asserted flag must be disregarded
    }
    res = evaluate_f7_claim(claim)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-002"
    assert "KernelEvidenceResolver" in (res.detail or "")


def test_cl_probe_2_completion_payload_obligation_closed_no_resolver() -> None:
    """CL Probe 2: Completion claim with payload obligation_closed: true and NO resolvers injected.
    
    Must fail closed with MISSING[PD-F7-005].
    Candidate payload obligation_closed: true must NEVER confer closure.
    """
    claim = {
        "claim_id": "CL-PROBE-2",
        "type": "completion",
        "subject": "Close audit obligation",
        "obligation_ref": "OBL-AUDIT-1",
        "obligation_closed": True,  # Candidate-asserted closure must be disregarded
        "evidence_refs": ["EV-INVENTED-1"],
    }
    res = evaluate_f7_claim(claim)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-005"
    assert "ObligationClosureResolver" in (res.detail or "")


def test_cl_probe_3_package_matching_payload_digests_no_resolver() -> None:
    """CL Probe 3: Package claim with payload-supplied matching digests and NO resolvers injected.
    
    Must fail closed with MISSING[PD-F7-003].
    Never satisfy a package claim using matching payload-supplied digests alone.
    """
    claim = {
        "claim_id": "CL-PROBE-3",
        "type": "reference",
        "reference_kind": "package",
        "subject": "untrusted-crypto-pkg",
        "expected_dependency_digest": "sha256:same-hash-12345",
        "canonical_dependency_set_digest": "sha256:same-hash-12345",
    }
    res = evaluate_f7_claim(claim)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-003"
    assert "CanonicalDependencyResolver" in (res.detail or "")


def test_cl_probe_4_nonexistent_symbol_no_repo_index() -> None:
    """CL Probe 4: Nonexistent symbol with no repository index injected.
    
    Pre-existing reference without repo index -> MISSING[PD-F7-004].
    Delta-created reference without repo index -> MISSING[PD-F7-006].
    """
    # Pre-existing reference
    claim_pre = {
        "claim_id": "CL-PROBE-4-PRE",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.nonexistent:MissingClass",
        "created_by_delta": False,
        "evaluator_resolution": "RESOLVED",  # Candidate asserted flag must be disregarded
    }
    res_pre = evaluate_f7_claim(claim_pre)
    assert res_pre.state == GateState.MISSING
    assert res_pre.must_id == "PD-F7-004"
    assert "RepositoryIntelligenceIndex" in (res_pre.detail or "")

    # Delta-created reference
    claim_delta = {
        "claim_id": "CL-PROBE-4-DELTA",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.nonexistent:NewClass",
        "created_by_delta": True,
        "evaluator_resolution": "RESOLVED",  # Candidate asserted flag must be disregarded
    }
    res_delta = evaluate_f7_claim(claim_delta)
    assert res_delta.state == GateState.MISSING
    assert res_delta.must_id == "PD-F7-006"
    assert "RepositoryIntelligenceIndex" in (res_delta.detail or "")


def test_resolver_omission_repo_index_independently() -> None:
    """Independent omission of repo_index while other resolvers are supplied fails closed."""
    dep_res = InMemoryCanonicalDependencyResolver({"pkg": "sha256:1"})
    ev_res = InMemoryKernelEvidenceResolver(["EV-1"])
    obl_res = InMemoryObligationClosureResolver(["OBL-1"])

    # Pre-existing symbol without repo_index
    claim_pre = {
        "claim_id": "CL-OMIT-REPO-PRE",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.core:Limiter",
        "created_by_delta": False,
    }
    res_pre = evaluate_f7_claim(
        claim_pre,
        repo_index=None,
        dependency_resolver=dep_res,
        evidence_resolver=ev_res,
        obligation_resolver=obl_res,
    )
    assert res_pre.state == GateState.MISSING
    assert res_pre.must_id == "PD-F7-004"

    # Delta-created symbol without repo_index
    claim_delta = {
        "claim_id": "CL-OMIT-REPO-DELTA",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.core:Limiter",
        "created_by_delta": True,
    }
    res_delta = evaluate_f7_claim(
        claim_delta,
        repo_index=None,
        dependency_resolver=dep_res,
        evidence_resolver=ev_res,
        obligation_resolver=obl_res,
    )
    assert res_delta.state == GateState.MISSING
    assert res_delta.must_id == "PD-F7-006"


def test_resolver_omission_dependency_resolver_independently() -> None:
    """Independent omission of dependency_resolver while other resolvers are supplied fails closed."""
    repo = InMemoryRepositoryIntelligenceIndex(pre_delta_symbols=["pkg.core:Limiter"])
    ev_res = InMemoryKernelEvidenceResolver(["EV-1"])
    obl_res = InMemoryObligationClosureResolver(["OBL-1"])

    claim_pkg = {
        "claim_id": "CL-OMIT-DEP",
        "type": "reference",
        "reference_kind": "package",
        "subject": "ratelimit-core",
        "expected_dependency_digest": "sha256:match",
        "canonical_dependency_set_digest": "sha256:match",
    }
    res = evaluate_f7_claim(
        claim_pkg,
        repo_index=repo,
        dependency_resolver=None,
        evidence_resolver=ev_res,
        obligation_resolver=obl_res,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-003"


def test_resolver_omission_evidence_resolver_independently() -> None:
    """Independent omission of evidence_resolver while other resolvers are supplied fails closed."""
    repo = InMemoryRepositoryIntelligenceIndex(pre_delta_symbols=["pkg.core:Limiter"])
    dep_res = InMemoryCanonicalDependencyResolver({"pkg": "sha256:1"})
    obl_res = InMemoryObligationClosureResolver(["OBL-1"])

    # Behavioral claim
    claim_beh = {
        "claim_id": "CL-OMIT-EV-BEH",
        "type": "behavioral",
        "subject": "benchmark",
        "evidence_refs": ["EV-1"],
    }
    res_beh = evaluate_f7_claim(
        claim_beh,
        repo_index=repo,
        dependency_resolver=dep_res,
        evidence_resolver=None,
        obligation_resolver=obl_res,
    )
    assert res_beh.state == GateState.MISSING
    assert res_beh.must_id == "PD-F7-002"

    # Completion claim (obligation closed, but evidence_resolver missing)
    claim_comp = {
        "claim_id": "CL-OMIT-EV-COMP",
        "type": "completion",
        "subject": "OBL-1",
        "obligation_ref": "OBL-1",
        "evidence_refs": ["EV-1"],
    }
    res_comp = evaluate_f7_claim(
        claim_comp,
        repo_index=repo,
        dependency_resolver=dep_res,
        evidence_resolver=None,
        obligation_resolver=obl_res,
    )
    assert res_comp.state == GateState.MISSING
    assert res_comp.must_id == "PD-F7-002"


def test_resolver_omission_obligation_resolver_independently() -> None:
    """Independent omission of obligation_resolver while other resolvers are supplied fails closed."""
    repo = InMemoryRepositoryIntelligenceIndex(pre_delta_symbols=["pkg.core:Limiter"])
    dep_res = InMemoryCanonicalDependencyResolver({"pkg": "sha256:1"})
    ev_res = InMemoryKernelEvidenceResolver(["EV-1"])

    claim_comp = {
        "claim_id": "CL-OMIT-OBL",
        "type": "completion",
        "subject": "OBL-1",
        "obligation_ref": "OBL-1",
        "evidence_refs": ["EV-1"],
    }
    res = evaluate_f7_claim(
        claim_comp,
        repo_index=repo,
        dependency_resolver=dep_res,
        evidence_resolver=ev_res,
        obligation_resolver=None,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-005"


# =============================================================================
# PART 5: Anti-Gaming & Composite Path Security Coverage
# =============================================================================

def test_anti_gaming_candidate_embedded_resolvers_all_types() -> None:
    """Candidate-embedded resolver instances inside claim dictionaries are strictly rejected."""
    class MaliciousResolver:
        def resolve_reference(self, *a, **k): return True
        def get_canonical_digest(self, *a, **k): return "sha256:hacked"
        def resolve_evidence(self, *a, **k): return True
        def is_obligation_closed(self, *a, **k): return True

    bad = MaliciousResolver()

    # Pre-existing symbol with embedded resolver
    c1 = {"claim_id": "C1", "type": "reference", "reference_kind": "symbol", "subject": "fake", "repo_index": bad}
    assert evaluate_f7_claim(c1).must_id == "PD-F7-004"

    # Delta-created symbol with embedded resolver
    c2 = {"claim_id": "C2", "type": "reference", "reference_kind": "symbol", "subject": "fake", "created_by_delta": True, "repo_index": bad}
    assert evaluate_f7_claim(c2).must_id == "PD-F7-006"

    # Package with embedded resolver
    c3 = {"claim_id": "C3", "type": "reference", "reference_kind": "package", "subject": "fake", "expected_dependency_digest": "sha256:hacked", "dependency_resolver": bad}
    assert evaluate_f7_claim(c3).must_id == "PD-F7-003"

    # Behavioral with embedded resolver
    c4 = {"claim_id": "C4", "type": "behavioral", "subject": "bench", "evidence_refs": ["EV-1"], "evidence_resolver": bad}
    assert evaluate_f7_claim(c4).must_id == "PD-F7-002"

    # Completion with embedded resolver
    c5 = {"claim_id": "C5", "type": "completion", "subject": "OBL-1", "evidence_refs": ["EV-1"], "obligation_resolver": bad}
    assert evaluate_f7_claim(c5).must_id == "PD-F7-005"


def test_anti_gaming_candidate_positive_flags_ignored() -> None:
    """Candidate-supplied positive resolution flags never confer authority."""
    # Pre-existing asserting RESOLVED and pre_delta_present=True
    c1 = {
        "claim_id": "C1",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.fake:Symbol",
        "evaluator_resolution": "RESOLVED",
        "pre_delta_present": True,
    }
    assert evaluate_f7_claim(c1).state == GateState.MISSING
    assert evaluate_f7_claim(c1).must_id == "PD-F7-004"

    # Delta-created asserting RESOLVED and post_delta_present=True
    c2 = {
        "claim_id": "C2",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.fake:DeltaSymbol",
        "created_by_delta": True,
        "evaluator_resolution": "RESOLVED",
        "post_delta_present": True,
    }
    assert evaluate_f7_claim(c2).state == GateState.MISSING
    assert evaluate_f7_claim(c2).must_id == "PD-F7-006"

    # Behavioral asserting kernel_evidence_resolves=True
    c3 = {
        "claim_id": "C3",
        "type": "behavioral",
        "subject": "bench",
        "evidence_refs": ["EV-1"],
        "kernel_evidence_resolves": True,
    }
    assert evaluate_f7_claim(c3).state == GateState.MISSING
    assert evaluate_f7_claim(c3).must_id == "PD-F7-002"

    # Completion asserting obligation_closed=True
    c4 = {
        "claim_id": "C4",
        "type": "completion",
        "subject": "OBL-1",
        "obligation_ref": "OBL-1",
        "evidence_refs": ["EV-1"],
        "obligation_closed": True,
    }
    assert evaluate_f7_claim(c4).state == GateState.MISSING
    assert evaluate_f7_claim(c4).must_id == "PD-F7-005"


def test_composite_f7_t6_path_without_injected_repo_index_fails_closed() -> None:
    """Composite F7-T6 path does not manufacture InMemoryRepositoryIntelligenceIndex; fails closed."""
    spec = {
        "reference_kind": "symbol",
        "pre_delta_index": ["pkg.legacy:OldSymbol"],
        "post_delta_overlay": ["pkg.new:NewSymbol"],
        "claim_subject": "pkg.new:NewSymbol",
        "created_by_delta": True,
        "absent_case_subject": "pkg.missing:AbsentSymbol",
        "absent_case_created_by_delta": True,
        "pre_existing_absent_subject": "pkg.legacy:MissingOldSymbol",
        "pre_existing_created_by_delta": False,
    }
    # No repo_index injected: must NOT auto-manufacture from spec['pre_delta_index']
    results = evaluate_f7_claim_ledger(spec, repo_index=None)
    assert isinstance(results, dict)
    assert results["delta_created_present"].state == GateState.MISSING
    assert results["delta_created_present"].must_id == "PD-F7-006"
    assert results["delta_created_absent"].state == GateState.MISSING
    assert results["delta_created_absent"].must_id == "PD-F7-006"
    assert results["pre_existing_absent"].state == GateState.MISSING
    assert results["pre_existing_absent"].must_id == "PD-F7-004"


def test_composite_f7_t5_path_without_injected_resolvers_fails_closed() -> None:
    """Composite F7-T5 path without injected resolvers fails closed for all sub-claims."""
    spec = {
        "reference_claim": {
            "claim_id": "CL-REF",
            "type": "reference",
            "subject": "pkg:Foo",
            "evaluator_resolution": "RESOLVED",
        },
        "behavioral_claim": {
            "claim_id": "CL-BEH",
            "type": "behavioral",
            "subject": "bench",
            "evidence_refs": ["EV-1"],
            "kernel_evidence_resolves": True,
        },
        "completion_claim": {
            "claim_id": "CL-COMP",
            "type": "completion",
            "subject": "OBL-1",
            "obligation_closed": True,
            "evidence_refs": ["EV-1"],
        },
    }
    results = evaluate_f7_claim_ledger(spec)
    assert isinstance(results, dict)
    assert results["reference"].state == GateState.MISSING
    assert results["reference"].must_id == "PD-F7-004"
    assert results["behavioral"].state == GateState.MISSING
    assert results["behavioral"].must_id == "PD-F7-002"
    assert results["completion"].state == GateState.MISSING
    assert results["completion"].must_id == "PD-F7-005"


# =============================================================================
# PART 6: Positive and Negative Resolver Controls (All Claim Types)
# =============================================================================

def test_controls_pre_existing_reference_symbol() -> None:
    """Controls for pre-existing reference symbol: valid, absent, missing resolver."""
    claim = {
        "claim_id": "CL-CTRL-PRE",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.ctrl:TargetClass",
        "created_by_delta": False,
    }
    # 1. Valid injected resolver -> SATISFIED
    repo_ok = InMemoryRepositoryIntelligenceIndex(pre_delta_symbols=["pkg.ctrl:TargetClass"])
    assert evaluate_f7_claim(claim, repo_index=repo_ok).state == GateState.SATISFIED

    # 2. Injected resolver returning absent -> MISSING[PD-F7-004]
    repo_absent = InMemoryRepositoryIntelligenceIndex(pre_delta_symbols=[])
    res_absent = evaluate_f7_claim(claim, repo_index=repo_absent)
    assert res_absent.state == GateState.MISSING
    assert res_absent.must_id == "PD-F7-004"

    # 3. Missing resolver -> MISSING[PD-F7-004]
    res_missing = evaluate_f7_claim(claim, repo_index=None)
    assert res_missing.state == GateState.MISSING
    assert res_missing.must_id == "PD-F7-004"


def test_controls_delta_created_reference_symbol() -> None:
    """Controls for delta-created reference symbol: valid, absent, missing resolver."""
    claim = {
        "claim_id": "CL-CTRL-DELTA",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.ctrl:NewClass",
        "created_by_delta": True,
    }
    # 1. Valid injected resolver -> SATISFIED
    repo_ok = InMemoryRepositoryIntelligenceIndex(post_delta_overlay=["pkg.ctrl:NewClass"])
    assert evaluate_f7_claim(claim, repo_index=repo_ok).state == GateState.SATISFIED

    # 2. Injected resolver returning absent -> MISSING[PD-F7-006]
    repo_absent = InMemoryRepositoryIntelligenceIndex(post_delta_overlay=[])
    res_absent = evaluate_f7_claim(claim, repo_index=repo_absent)
    assert res_absent.state == GateState.MISSING
    assert res_absent.must_id == "PD-F7-006"

    # 3. Missing resolver -> MISSING[PD-F7-006]
    res_missing = evaluate_f7_claim(claim, repo_index=None)
    assert res_missing.state == GateState.MISSING
    assert res_missing.must_id == "PD-F7-006"


def test_controls_package_reference() -> None:
    """Controls for package reference: valid, mismatch/absent, missing resolver."""
    claim = {
        "claim_id": "CL-CTRL-PKG",
        "type": "reference",
        "reference_kind": "package",
        "subject": "pkg-core",
        "expected_dependency_digest": "sha256:golden-hash",
    }
    # 1. Valid matching resolver -> SATISFIED
    dep_ok = InMemoryCanonicalDependencyResolver({"pkg-core": "sha256:golden-hash"})
    assert evaluate_f7_claim(claim, dependency_resolver=dep_ok).state == GateState.SATISFIED

    # 2. Injected resolver mismatch -> MISSING[PD-F7-003]
    dep_mismatch = InMemoryCanonicalDependencyResolver({"pkg-core": "sha256:different-hash"})
    res_mis = evaluate_f7_claim(claim, dependency_resolver=dep_mismatch)
    assert res_mis.state == GateState.MISSING
    assert res_mis.must_id == "PD-F7-003"

    # 3. Injected resolver absent package -> MISSING[PD-F7-003]
    dep_absent = InMemoryCanonicalDependencyResolver({})
    res_abs = evaluate_f7_claim(claim, dependency_resolver=dep_absent)
    assert res_abs.state == GateState.MISSING
    assert res_abs.must_id == "PD-F7-003"

    # 4. Missing resolver -> MISSING[PD-F7-003]
    res_missing = evaluate_f7_claim(claim, dependency_resolver=None)
    assert res_missing.state == GateState.MISSING
    assert res_missing.must_id == "PD-F7-003"


def test_controls_behavioral_claim() -> None:
    """Controls for behavioral claim: valid, unresolvable evidence, missing resolver."""
    claim = {
        "claim_id": "CL-CTRL-BEH",
        "type": "behavioral",
        "subject": "run_benchmark",
        "evidence_refs": ["EV-CTRL-1"],
    }
    # 1. Valid resolving resolver -> SATISFIED
    ev_ok = InMemoryKernelEvidenceResolver(["EV-CTRL-1"])
    assert evaluate_f7_claim(claim, evidence_resolver=ev_ok).state == GateState.SATISFIED

    # 2. Injected resolver returning false -> MISSING[PD-F7-002]
    ev_absent = InMemoryKernelEvidenceResolver([])
    res_abs = evaluate_f7_claim(claim, evidence_resolver=ev_absent)
    assert res_abs.state == GateState.MISSING
    assert res_abs.must_id == "PD-F7-002"

    # 3. Missing resolver -> MISSING[PD-F7-002]
    res_missing = evaluate_f7_claim(claim, evidence_resolver=None)
    assert res_missing.state == GateState.MISSING
    assert res_missing.must_id == "PD-F7-002"


def test_controls_completion_claim() -> None:
    """Controls for completion claim: valid, unclosed, unresolvable evidence, missing resolvers."""
    claim = {
        "claim_id": "CL-CTRL-COMP",
        "type": "completion",
        "subject": "OBL-FINAL",
        "obligation_ref": "OBL-FINAL",
        "evidence_refs": ["EV-COMP-1"],
    }
    ev_ok = InMemoryKernelEvidenceResolver(["EV-COMP-1"])
    obl_ok = InMemoryObligationClosureResolver(["OBL-FINAL"])

    # 1. Valid resolvers -> SATISFIED
    assert evaluate_f7_claim(claim, obligation_resolver=obl_ok, evidence_resolver=ev_ok).state == GateState.SATISFIED

    # 2. Injected obligation resolver returning false -> MISSING[PD-F7-005]
    obl_open = InMemoryObligationClosureResolver([])
    res_unclosed = evaluate_f7_claim(claim, obligation_resolver=obl_open, evidence_resolver=ev_ok)
    assert res_unclosed.state == GateState.MISSING
    assert res_unclosed.must_id == "PD-F7-005"

    # 3. Injected evidence resolver returning false -> MISSING[PD-F7-002]
    ev_unres = InMemoryKernelEvidenceResolver([])
    res_unres = evaluate_f7_claim(claim, obligation_resolver=obl_ok, evidence_resolver=ev_unres)
    assert res_unres.state == GateState.MISSING
    assert res_unres.must_id == "PD-F7-002"

    # 4. Missing obligation resolver -> MISSING[PD-F7-005]
    res_no_obl = evaluate_f7_claim(claim, obligation_resolver=None, evidence_resolver=ev_ok)
    assert res_no_obl.state == GateState.MISSING
    assert res_no_obl.must_id == "PD-F7-005"

    # 5. Missing evidence resolver -> MISSING[PD-F7-002]
    res_no_ev = evaluate_f7_claim(claim, obligation_resolver=obl_ok, evidence_resolver=None)
    assert res_no_ev.state == GateState.MISSING
    assert res_no_ev.must_id == "PD-F7-002"


# =============================================================================
# PART 8: Additional L8 Strict Validation: ReferenceKind & created_by_delta
# =============================================================================

# --- Finding A: ReferenceKind strict validation ---

def test_reference_kind_unknown_with_subject_in_pre_delta_index_fails_closed() -> None:
    """Finding A: Unknown reference_kind with subject present in pre-delta index fails closed under PD-F7-003."""
    repo = InMemoryRepositoryIntelligenceIndex(pre_delta_symbols=["pkg.core:Limiter"])
    claim = {
        "claim_id": "CL-UNK-PRE",
        "type": "reference",
        "reference_kind": "unsupported_macro",
        "subject": "pkg.core:Limiter",
        "created_by_delta": False,
    }
    res = evaluate_f7_claim(claim, repo_index=repo)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-003"
    assert res != GateState.SATISFIED
    assert "Invalid reference_kind 'unsupported_macro'" in (res.detail or "")


def test_reference_kind_unknown_with_subject_in_post_delta_overlay_fails_closed() -> None:
    """Finding A: Unknown reference_kind with subject present in post-delta overlay fails closed under PD-F7-003."""
    repo = InMemoryRepositoryIntelligenceIndex(post_delta_overlay=["pkg.core:NewLimiter"])
    claim = {
        "claim_id": "CL-UNK-POST",
        "type": "reference",
        "reference_kind": "unsupported_type",
        "subject": "pkg.core:NewLimiter",
        "created_by_delta": True,
    }
    res = evaluate_f7_claim(claim, repo_index=repo)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-003"
    assert res != GateState.SATISFIED
    assert "Invalid reference_kind 'unsupported_type'" in (res.detail or "")


@pytest.mark.parametrize("bad_kind", ["macro", "type", "var", "function", "class", "module", "INVALID", "123", ""])
def test_every_unsupported_reference_kind_returns_missing_never_satisfied(bad_kind: str) -> None:
    """Finding A: Every unsupported reference kind returns MISSING (never SATISFIED) regardless of delta."""
    repo = InMemoryRepositoryIntelligenceIndex(
        pre_delta_symbols=["pkg.core:Target"],
        post_delta_overlay=["pkg.core:Target"],
    )
    for delta in (False, True):
        claim = {
            "claim_id": f"CL-UNSUPP-{bad_kind}-{delta}",
            "type": "reference",
            "reference_kind": bad_kind,
            "subject": "pkg.core:Target",
            "created_by_delta": delta,
        }
        res = evaluate_f7_claim(claim, repo_index=repo)
        assert res.state == GateState.MISSING
        assert res != GateState.SATISFIED
        assert res.must_id == "PD-F7-003"
        assert f"Invalid reference_kind '{bad_kind}'" in (res.detail or "")


def test_reference_kind_omitted_defaults_to_symbol_normatively() -> None:
    """Finding A: Omitted reference_kind preserves normative default ('symbol')."""
    repo = InMemoryRepositoryIntelligenceIndex(pre_delta_symbols=["pkg.core:Target"])
    claim = {
        "claim_id": "CL-OMITTED-KIND",
        "type": "reference",
        "subject": "pkg.core:Target",
        "created_by_delta": False,
    }
    res = evaluate_f7_claim(claim, repo_index=repo)
    assert res.state == GateState.SATISFIED


def test_claim_record_rejects_unsupported_reference_kind() -> None:
    """Finding A: ClaimRecord direct construction and from_dict reject unknown reference_kind."""
    with pytest.raises(ValueError, match="reference_kind"):
        ClaimRecord(
            claim_id="CL-BAD-KIND",
            type="reference",
            subject="pkg.core:Target",
            reference_kind="invalid_kind",
        )
    with pytest.raises(ValueError, match="reference_kind"):
        ClaimRecord.from_dict({
            "claim_id": "CL-BAD-KIND",
            "type": "reference",
            "subject": "pkg.core:Target",
            "reference_kind": "invalid_kind",
        })


# --- Finding B: Strict boolean validation for created_by_delta ---

@pytest.mark.parametrize("malformed", ["false", "true", 0, 1, None, [], {}, 3.14])
def test_evaluate_f7_claim_rejects_malformed_created_by_delta_before_resolver(malformed: Any) -> None:
    """Finding B: Untrusted non-bool created_by_delta fails closed under PD-F7-001 before resolver selection."""
    repo = InMemoryRepositoryIntelligenceIndex(
        pre_delta_symbols=["pkg.core:Target"],
        post_delta_overlay=["pkg.core:Target"],
    )
    claim = {
        "claim_id": "CL-BAD-DELTA",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.core:Target",
        "created_by_delta": malformed,
    }
    res = evaluate_f7_claim(claim, repo_index=repo)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-001"
    assert res != GateState.SATISFIED
    assert "strict boolean" in (res.detail or "")


@pytest.mark.parametrize("malformed", ["false", "true", 0, 1, None, [], {}, 3.14])
def test_claim_record_direct_rejects_malformed_created_by_delta(malformed: Any) -> None:
    """Finding B: ClaimRecord direct construction rejects non-bool created_by_delta."""
    with pytest.raises(ValueError, match="created_by_delta"):
        ClaimRecord(
            claim_id="CL-BAD-DELTA",
            type="reference",
            subject="pkg.core:Target",
            created_by_delta=malformed,
        )


@pytest.mark.parametrize("malformed", ["false", "true", 0, 1, None, [], {}, 3.14])
def test_claim_record_from_dict_rejects_malformed_created_by_delta(malformed: Any) -> None:
    """Finding B: ClaimRecord.from_dict rejects non-bool created_by_delta (no truthiness coercion)."""
    with pytest.raises(ValueError, match="created_by_delta"):
        ClaimRecord.from_dict({
            "claim_id": "CL-BAD-DELTA",
            "type": "reference",
            "subject": "pkg.core:Target",
            "created_by_delta": malformed,
        })


def test_valid_booleans_for_created_by_delta_preserved() -> None:
    """Finding B: Valid boolean True and False values are preserved across all paths."""
    repo = InMemoryRepositoryIntelligenceIndex(
        pre_delta_symbols=["pkg.core:Pre"],
        post_delta_overlay=["pkg.core:Post"],
    )

    # False -> pre-delta
    c_false = {"claim_id": "C-F", "type": "reference", "subject": "pkg.core:Pre", "created_by_delta": False}
    assert evaluate_f7_claim(c_false, repo_index=repo).state == GateState.SATISFIED

    # True -> post-delta
    c_true = {"claim_id": "C-T", "type": "reference", "subject": "pkg.core:Post", "created_by_delta": True}
    assert evaluate_f7_claim(c_true, repo_index=repo).state == GateState.SATISFIED

    # ClaimRecord direct
    rec_f = ClaimRecord(claim_id="C-F", type="reference", subject="pkg.core:Pre", created_by_delta=False)
    assert rec_f.created_by_delta is False
    rec_t = ClaimRecord(claim_id="C-T", type="reference", subject="pkg.core:Post", created_by_delta=True)
    assert rec_t.created_by_delta is True

    # ClaimRecord from_dict
    from_dict_f = ClaimRecord.from_dict(c_false)
    assert from_dict_f.created_by_delta is False
    from_dict_t = ClaimRecord.from_dict(c_true)
    assert from_dict_t.created_by_delta is True


# --- Regression Tests: Unhashable ReferenceKind Inputs (Lists & Dicts) ---

@pytest.mark.parametrize("unhashable_kind", [[], {}, ["symbol"], {"kind": "symbol"}])
def test_evaluate_f7_claim_unhashable_reference_kind_fails_closed(unhashable_kind: Any) -> None:
    """Unhashable reference_kind (list, dict) returns MISSING[PD-F7-003] without TypeError or SATISFIED."""
    repo = InMemoryRepositoryIntelligenceIndex(
        pre_delta_symbols=["pkg.core:Target"],
        post_delta_overlay=["pkg.core:Target"],
    )
    for delta in (False, True):
        claim = {
            "claim_id": "CL-UNHASHABLE-KIND",
            "type": "reference",
            "reference_kind": unhashable_kind,
            "subject": "pkg.core:Target",
            "created_by_delta": delta,
        }
        res = evaluate_f7_claim(claim, repo_index=repo)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-F7-003"
        assert res != GateState.SATISFIED
        assert "Invalid reference_kind" in (res.detail or "")


@pytest.mark.parametrize("unhashable_kind", [[], {}, ["symbol"], {"kind": "symbol"}])
def test_claim_record_direct_rejects_unhashable_reference_kind(unhashable_kind: Any) -> None:
    """ClaimRecord direct construction raises ValueError (not TypeError) on unhashable reference_kind."""
    with pytest.raises(ValueError, match="reference_kind"):
        ClaimRecord(
            claim_id="CL-UNHASHABLE-KIND",
            type="reference",
            subject="pkg.core:Target",
            reference_kind=unhashable_kind,
        )


@pytest.mark.parametrize("unhashable_kind", [[], {}, ["symbol"], {"kind": "symbol"}])
def test_claim_record_from_dict_rejects_unhashable_reference_kind(unhashable_kind: Any) -> None:
    """ClaimRecord.from_dict raises ValueError (not TypeError) on unhashable reference_kind."""
    with pytest.raises(ValueError, match="reference_kind"):
        ClaimRecord.from_dict({
            "claim_id": "CL-UNHASHABLE-KIND",
            "type": "reference",
            "subject": "pkg.core:Target",
            "reference_kind": unhashable_kind,
        })


@pytest.mark.parametrize("unhashable_kind", [[], {}, ["symbol"], {"kind": "symbol"}])
def test_repo_index_resolve_reference_unhashable_kind(unhashable_kind: Any) -> None:
    """InMemoryRepositoryIntelligenceIndex.resolve_reference returns False on unhashable kind without TypeError."""
    repo = InMemoryRepositoryIntelligenceIndex(
        pre_delta_symbols=["pkg.core:Target"],
        post_delta_overlay=["pkg.core:Target"],
    )
    assert repo.resolve_reference(unhashable_kind, "pkg.core:Target", post_delta=False) is False
    assert repo.resolve_reference(unhashable_kind, "pkg.core:Target", post_delta=True) is False


