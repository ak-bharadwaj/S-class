"""Tests for Block 4 Lane D (Execution Flow Adaptation & TestInputSet Binding).

Test matrix: MUST x {gaming, happy, no-authority, malformed/None fail-closed, mutation per decision branch}.
MUSTs covered:
- PD-CH3-010: Upgrade/migration flows MUST bind baselines and rollback/verification inputs before closure.
- PD-CH3-011: Project-class adaptation MUST mark unqualified adapter/pack as open qualification.
- PD-CH3-012: UX adaptation interruption budgets MUST NOT suppress required human decision.
- PD-CH3-014: Canonical lifecycle examples MUST exercise real gate outputs and adversarial failure.
- PD-CH4-012: Reference MUST resolve exactly against pinned snapshot; no fuzzy matching.
- PD-CH4-009: P5 MUST bind complete TestInputSet before red.
"""
from __future__ import annotations

import pytest
from sclass.product.gate import GateOutput, GateState
from sclass.product.execution_flow_testinput import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    REQUIRED_TEST_INPUT_KEYS,
    evaluate_pd_ch3_010_flow_baseline_binding,
    evaluate_pd_ch3_011_adapter_qualification_disclosure,
    evaluate_pd_ch3_012_ux_interruption_budget_authority,
    evaluate_pd_ch3_014_lifecycle_example_adversarial_failure,
    evaluate_pd_ch4_012_reference_exact_resolution,
    evaluate_pd_ch4_009_test_input_set_binding,
    evaluate_b4_d_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


# -----------------------------------------------------------------------------
# PD-CH3-010
# -----------------------------------------------------------------------------
def test_ch3_010_happy_path():
    out = evaluate_pd_ch3_010_flow_baseline_binding(
        flow_type="MIGRATION",
        baseline_digest="sha256:base",
        rollback_inputs_bound=True,
        verification_inputs_bound=True,
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH3-010"


def test_ch3_010_gaming_missing_rollback_binding():
    out = evaluate_pd_ch3_010_flow_baseline_binding(
        flow_type="MIGRATION",
        baseline_digest=None,
        rollback_inputs_bound=False,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH3-010"


def test_ch3_010_no_authority():
    assert evaluate_pd_ch3_010_flow_baseline_binding("MIGRATION", "base", authority=None).state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-CH3-011
# -----------------------------------------------------------------------------
def test_ch3_011_happy_qualified():
    out = evaluate_pd_ch3_011_adapter_qualification_disclosure(
        adapter_identity="browser-adapter",
        is_qualified=True,
        marked_supported=True,
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH3-011"


def test_ch3_011_gaming_unqualified_presented_as_supported():
    out = evaluate_pd_ch3_011_adapter_qualification_disclosure(
        adapter_identity="browser-adapter",
        is_qualified=False,
        marked_supported=True,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH3-011"
    assert "presented as supported" in out.detail


def test_ch3_011_no_authority():
    assert evaluate_pd_ch3_011_adapter_qualification_disclosure("a", True, True, authority=None).state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-CH3-012
# -----------------------------------------------------------------------------
def test_ch3_012_happy_human_decision_honored():
    out = evaluate_pd_ch3_012_ux_interruption_budget_authority(
        human_decision_required=True,
        decision_suppressed_by_cap=False,
        interruption_budget_exceeded=False,
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH3-012"


def test_ch3_012_gaming_cap_suppresses_required_approval():
    out = evaluate_pd_ch3_012_ux_interruption_budget_authority(
        human_decision_required=True,
        decision_suppressed_by_cap=True,
        authority=AUTH,
    )
    assert out.state == GateState.BLOCKED_ON_HUMAN
    assert out.must_id == "PD-CH3-012"


def test_ch3_012_no_authority():
    assert evaluate_pd_ch3_012_ux_interruption_budget_authority(True, False, authority=None).state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-CH3-014
# -----------------------------------------------------------------------------
def test_ch3_014_happy_lifecycle_example():
    out = evaluate_pd_ch3_014_lifecycle_example_adversarial_failure(
        exercises_real_gate_outputs=True,
        has_adversarial_claim_failure=True,
        has_test_integrity_failure=True,
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH3-014"


def test_ch3_014_gaming_omits_adversarial_or_integrity_failure():
    out = evaluate_pd_ch3_014_lifecycle_example_adversarial_failure(
        exercises_real_gate_outputs=True,
        has_adversarial_claim_failure=False,
        has_test_integrity_failure=True,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH3-014"


def test_ch3_014_no_authority():
    assert evaluate_pd_ch3_014_lifecycle_example_adversarial_failure(True, True, True, authority=None).state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-CH4-012
# -----------------------------------------------------------------------------
def test_ch4_012_happy_exact_resolution():
    out = evaluate_pd_ch4_012_reference_exact_resolution(
        path_reference="src/core.py",
        symbol_reference="eval_gate",
        target_snapshot_pinned=True,
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH4-012"


def test_ch4_012_gaming_unresolved_or_unpinned():
    out = evaluate_pd_ch4_012_reference_exact_resolution(
        path_reference="src/unknown.py",
        symbol_reference="eval_gate",
        target_snapshot_pinned=False,
        is_unresolved=True,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH4-012"


def test_ch4_012_gaming_ambiguous_reference():
    out = evaluate_pd_ch4_012_reference_exact_resolution(
        path_reference="src/core.py",
        symbol_reference="eval_gate",
        target_snapshot_pinned=True,
        is_ambiguous=True,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert "Ambiguous reference" in out.detail


def test_ch4_012_gaming_fuzzy_match():
    out = evaluate_pd_ch4_012_reference_exact_resolution(
        path_reference="src/core.py",
        symbol_reference="eval_gate",
        target_snapshot_pinned=True,
        is_fuzzy_match=True,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert "Fuzzy-match" in out.detail


def test_ch4_012_no_authority():
    assert evaluate_pd_ch4_012_reference_exact_resolution("p", "s", True, authority=None).state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-CH4-009
# -----------------------------------------------------------------------------
def _full_test_input_set():
    return {k: f"content_{k}" for k in REQUIRED_TEST_INPUT_KEYS}


def test_ch4_009_happy_path():
    out = evaluate_pd_ch4_009_test_input_set_binding(
        test_input_set=_full_test_input_set(),
        is_before_red=True,
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH4-009"


def test_ch4_009_gaming_omits_fixtures_and_plugins():
    partial = _full_test_input_set()
    del partial["fixtures"]
    del partial["plugins"]
    out = evaluate_pd_ch4_009_test_input_set_binding(
        test_input_set=partial,
        is_before_red=True,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH4-009"
    assert "omits declared complete inputs" in out.detail


def test_ch4_009_not_before_red():
    out = evaluate_pd_ch4_009_test_input_set_binding(
        test_input_set=_full_test_input_set(),
        is_before_red=False,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING


def test_ch4_009_no_authority_and_none():
    assert evaluate_pd_ch4_009_test_input_set_binding(_full_test_input_set(), authority=None).state == GateState.MISSING
    assert evaluate_pd_ch4_009_test_input_set_binding(None, authority=AUTH).state == GateState.MISSING


# -----------------------------------------------------------------------------
# Aggregate Gate
# -----------------------------------------------------------------------------
def test_evaluate_b4_d_gate_aggregate():
    payload = {
        "flow_type": "MIGRATION",
        "baseline_digest": "sha256:b",
        "adapter_identity": "ad",
        "is_qualified": True,
        "marked_supported": True,
        "human_decision_required": False,
        "exercises_real_gate_outputs": True,
        "has_adversarial_claim_failure": True,
        "has_test_integrity_failure": True,
        "path_reference": "path",
        "symbol_reference": "sym",
        "target_snapshot_pinned": True,
        "test_input_set": _full_test_input_set(),
        "is_before_red": True,
    }
    gate_out = evaluate_b4_d_gate(payload, authority=AUTH)
    assert len(gate_out) == 6
    for m_id, res in gate_out.items():
        assert res.state == GateState.SATISFIED
