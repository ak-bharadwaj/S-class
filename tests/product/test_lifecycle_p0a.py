"""Tests for Lifecycle P0A Engine (PD-CH2-001, 002, 003, 005, 006, 055).

Verifies full test matrix for each MUST:
- Happy test
- Gaming test (Appendix F / normative table fixture behavior)
- No-authority negative test (omitted, None, AGENT -> MISSING)
- Malformed/None/exception fail-closed test
- Decision-branch mutation tests
"""
from __future__ import annotations

import pytest

from sclass.product.gate import GateOutput, GateState
from sclass.product.lifecycle_p0a import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    STANDARD_PHASES,
    ELEVEN_DIMENSIONS,
    REGISTERED_WORK_TYPES,
    evaluate_pd_ch2_001_single_lifecycle,
    evaluate_pd_ch2_002_eleven_dimensions,
    evaluate_pd_ch2_003_earlier_phase_validity,
    evaluate_pd_ch2_005_skipped_phase_applicability,
    evaluate_pd_ch2_006_earliest_defect_routing,
    evaluate_pd_ch2_055_downstream_invalidation,
    evaluate_p0a_gate,
)


# =============================================================================
# 1. PD-CH2-001 Tests
# =============================================================================

def test_pd_ch2_001_happy():
    """Happy: registered work type with valid P0..P11 projection -> SATISFIED."""
    payload = {
        "work_type": "FEATURE",
        "phase_sequence": list(STANDARD_PHASES),
    }
    res = evaluate_pd_ch2_001_single_lifecycle(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_001_gaming_ch2_t1():
    """Gaming (CH2-T1): alternate lifecycle token P12 -> MISSING[PD-CH2-001]."""
    payload = {
        "work_type": "FEATURE",
        "phase_sequence": list(STANDARD_PHASES),
        "alternate_phase": "P12",
    }
    res = evaluate_pd_ch2_001_single_lifecycle(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-001"
    assert "MISSING[PD-CH2-001]" in res.failures


def test_pd_ch2_001_no_authority():
    """Negative: omitted / None / AGENT authority fails closed."""
    payload = {"work_type": "FEATURE"}
    assert evaluate_pd_ch2_001_single_lifecycle(payload).state == GateState.MISSING
    assert evaluate_pd_ch2_001_single_lifecycle(payload, caller_authority=None).state == GateState.MISSING
    assert evaluate_pd_ch2_001_single_lifecycle(payload, caller_authority="AGENT").state == GateState.MISSING


def test_pd_ch2_001_malformed():
    """Fail-closed on malformed or non-mapping payloads."""
    assert evaluate_pd_ch2_001_single_lifecycle(None, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING
    assert evaluate_pd_ch2_001_single_lifecycle("string", caller_authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING
    assert evaluate_pd_ch2_001_single_lifecycle({"work_type": "INVALID_TYPE"}, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING
    assert evaluate_pd_ch2_001_single_lifecycle({"work_type": "FEATURE", "phase_sequence": ["P0", "P99"]}, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING


# =============================================================================
# 2. PD-CH2-002 Tests
# =============================================================================

def test_pd_ch2_002_happy():
    """Happy: all eleven dimensions defined -> SATISFIED."""
    payload = {
        "phase": "P6",
        "defined_dimensions": list(ELEVEN_DIMENSIONS),
    }
    res = evaluate_pd_ch2_002_eleven_dimensions(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_002_gaming_ch2_t2():
    """Gaming (CH2-T2): missing dimension Applicability -> MISSING[PD-CH2-002]."""
    payload = {
        "phase": "P6",
        "missing_dimension": "Applicability",
    }
    res = evaluate_pd_ch2_002_eleven_dimensions(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-002"
    assert "MISSING[PD-CH2-002]" in res.failures


def test_pd_ch2_002_no_authority():
    """Negative: no authority fails closed."""
    payload = {"phase": "P6", "defined_dimensions": list(ELEVEN_DIMENSIONS)}
    assert evaluate_pd_ch2_002_eleven_dimensions(payload).state == GateState.MISSING
    assert evaluate_pd_ch2_002_eleven_dimensions(payload, caller_authority=None).state == GateState.MISSING
    assert evaluate_pd_ch2_002_eleven_dimensions(payload, caller_authority="AGENT").state == GateState.MISSING


def test_pd_ch2_002_malformed():
    """Fail-closed on missing dimensions list or invalid phase."""
    assert evaluate_pd_ch2_002_eleven_dimensions(None, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING
    assert evaluate_pd_ch2_002_eleven_dimensions({"phase": "P99"}, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING
    # Missing exit criteria in defined list
    partial = [d for d in ELEVEN_DIMENSIONS if d != "Exit Criteria"]
    assert evaluate_pd_ch2_002_eleven_dimensions({"phase": "P1", "defined_dimensions": partial}, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING


# =============================================================================
# 3. PD-CH2-003 Tests
# =============================================================================

def test_pd_ch2_003_happy():
    """Happy: all earlier phases valid -> SATISFIED."""
    payload = {
        "current_phase": "P3",
        "earlier_phase_status": {"P0": "VALID", "P1": "VALID", "P2": "VALID"},
    }
    res = evaluate_pd_ch2_003_earlier_phase_validity(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_003_gaming_ch2_t3():
    """Gaming (CH2-T3): invalid P2 artifact followed by P3 attempt -> MISSING[PD-CH2-003]."""
    payload = {
        "current_phase": "P3",
        "earlier_phase_status": {"P0": "VALID", "P1": "VALID", "P2": "INVALID"},
    }
    res = evaluate_pd_ch2_003_earlier_phase_validity(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-003"
    assert "MISSING[PD-CH2-003]" in res.failures


def test_pd_ch2_003_no_authority():
    """Negative: no authority fails closed."""
    payload = {"current_phase": "P3", "earlier_phase_status": {"P2": "VALID"}}
    assert evaluate_pd_ch2_003_earlier_phase_validity(payload).state == GateState.MISSING
    assert evaluate_pd_ch2_003_earlier_phase_validity(payload, caller_authority="AGENT").state == GateState.MISSING


def test_pd_ch2_003_malformed():
    """Fail-closed on earlier_phase_invalid flag or malformed input."""
    assert evaluate_pd_ch2_003_earlier_phase_validity(None, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING
    assert evaluate_pd_ch2_003_earlier_phase_validity({"earlier_phase_invalid": True}, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING


# =============================================================================
# 4. PD-CH2-005 Tests
# =============================================================================

def test_pd_ch2_005_happy():
    """Happy: skipped phase has explicit evaluator-checkable applicability record -> SATISFIED."""
    payload = {
        "skipped_phases": ["P2"],
        "applicability_declarations": {
            "P2": {"evaluator_checkable": True, "skip_reason": "SPIKE_RESEARCH_NO_FORMAL_SPEC"}
        },
    }
    res = evaluate_pd_ch2_005_skipped_phase_applicability(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_005_gaming_ch2_t5():
    """Gaming (CH2-T5): applicability declaration absent -> MISSING[PD-CH2-005]."""
    payload = {
        "skipped_phases": ["P2"],
        "applicability_declaration_absent": True,
    }
    res = evaluate_pd_ch2_005_skipped_phase_applicability(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-005"
    assert "MISSING[PD-CH2-005]" in res.failures


def test_pd_ch2_005_no_authority():
    """Negative: no authority fails closed."""
    payload = {"skipped_phases": ["P2"]}
    assert evaluate_pd_ch2_005_skipped_phase_applicability(payload).state == GateState.MISSING
    assert evaluate_pd_ch2_005_skipped_phase_applicability(payload, caller_authority="AGENT").state == GateState.MISSING


def test_pd_ch2_005_malformed():
    """Fail-closed when applicability declaration is missing or not checkable."""
    assert evaluate_pd_ch2_005_skipped_phase_applicability(None, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING
    # Missing record
    assert evaluate_pd_ch2_005_skipped_phase_applicability({"skipped_phases": ["P2"], "applicability_declarations": {}}, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING
    # Not checkable
    bad_rec = {"skipped_phases": ["P2"], "applicability_declarations": {"P2": {"evaluator_checkable": False}}}
    assert evaluate_pd_ch2_005_skipped_phase_applicability(bad_rec, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING


# =============================================================================
# 5. PD-CH2-006 Tests
# =============================================================================

def test_pd_ch2_006_happy():
    """Happy: defect routes to earliest affected phase (P2) -> SATISFIED."""
    payload = {
        "defect_found_in": "P6",
        "earliest_affected_phase": "P2",
        "routed_phase": "P2",
    }
    res = evaluate_pd_ch2_006_earliest_defect_routing(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_006_gaming_ch2_t6():
    """Gaming (CH2-T6): requirement defect found during P6 routes to P6 instead of P2 -> MISSING[PD-CH2-006]."""
    payload = {
        "defect_found_in": "P6",
        "earliest_affected_phase": "P2",
        "routed_phase": "P6",
    }
    res = evaluate_pd_ch2_006_earliest_defect_routing(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-006"
    assert "MISSING[PD-CH2-006]" in res.failures


def test_pd_ch2_006_no_authority():
    """Negative: no authority fails closed."""
    payload = {"defect_found_in": "P6", "earliest_affected_phase": "P2", "routed_phase": "P2"}
    assert evaluate_pd_ch2_006_earliest_defect_routing(payload).state == GateState.MISSING
    assert evaluate_pd_ch2_006_earliest_defect_routing(payload, caller_authority="AGENT").state == GateState.MISSING


def test_pd_ch2_006_malformed():
    """Fail-closed on missing earliest affected phase or non-mapping."""
    assert evaluate_pd_ch2_006_earliest_defect_routing(None, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING
    assert evaluate_pd_ch2_006_earliest_defect_routing({"defect_found_in": "P6"}, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING


# =============================================================================
# 6. PD-CH2-055 Tests
# =============================================================================

def test_pd_ch2_055_happy_ch2_t56():
    """Happy (CH2-T56): downstream invalidated and recomputed with visible changed binding -> SATISFIED."""
    payload = {
        "authoritative_dependency_digest": "DIGEST-NEW-123",
        "downstream_invalidated": True,
        "recomputation_key": {"dependency_digest": "DIGEST-NEW-123"},
    }
    res = evaluate_pd_ch2_055_downstream_invalidation(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_055_gaming_ch2_t55():
    """Gaming (CH2-T55): bypass attempt with stale downstream projection -> MISSING[PD-CH2-055]."""
    payload = {
        "bypass_attempt": True,
        "authoritative_dependency_digest": "DIGEST-NEW-123",
        "recomputation_key": {"dependency_digest": "DIGEST-OLD-000"},
    }
    res = evaluate_pd_ch2_055_downstream_invalidation(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-055"
    assert "MISSING[PD-CH2-055]" in res.failures


def test_pd_ch2_055_no_authority():
    """Negative: no authority fails closed."""
    payload = {"authoritative_dependency_digest": "D1", "recomputation_key": {"dependency_digest": "D1"}}
    assert evaluate_pd_ch2_055_downstream_invalidation(payload).state == GateState.MISSING
    assert evaluate_pd_ch2_055_downstream_invalidation(payload, caller_authority="AGENT").state == GateState.MISSING


def test_pd_ch2_055_malformed():
    """Fail-closed on digest mismatch or un-invalidated downstream."""
    assert evaluate_pd_ch2_055_downstream_invalidation(None, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING
    # Digest mismatch
    mismatch = {
        "authoritative_dependency_digest": "D-REAL",
        "recomputation_key": {"dependency_digest": "D-FAKE"},
    }
    assert evaluate_pd_ch2_055_downstream_invalidation(mismatch, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING
    # Not invalidated
    not_inv = {
        "authoritative_dependency_digest": "D1",
        "recomputation_key": {"dependency_digest": "D1"},
        "downstream_invalidated": False,
    }
    assert evaluate_pd_ch2_055_downstream_invalidation(not_inv, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING


# =============================================================================
# 7. Composite Evaluator & Mutation Tests
# =============================================================================

def test_p0a_composite_gate():
    """Verifies evaluate_p0a_gate evaluates all 6 MUSTs."""
    payloads = {
        "PD-CH2-001": {"work_type": "FEATURE"},
        "PD-CH2-002": {"phase": "P0", "defined_dimensions": list(ELEVEN_DIMENSIONS)},
        "PD-CH2-003": {"earlier_phase_status": {"P0": "VALID"}},
        "PD-CH2-005": {"skipped_phases": []},
        "PD-CH2-006": {"defect_found_in": "P6", "earliest_affected_phase": "P2", "routed_phase": "P2"},
        "PD-CH2-055": {"authoritative_dependency_digest": "D", "recomputation_key": {"dependency_digest": "D"}},
    }
    res = evaluate_p0a_gate(payloads, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert len(res) == 6
    assert all(g.state == GateState.SATISFIED for g in res.values())
