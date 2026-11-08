"""Tests for Lifecycle P0B Execution & Completion Invariants (PD-CH2-007..012)."""
from __future__ import annotations

import pytest

from sclass.product.gate import GateOutput, GateState
from sclass.product.lifecycle_p0b import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    STANDARD_LIFECYCLE_PHASES,
    evaluate_pd_ch2_007_p8_retry_budget,
    evaluate_pd_ch2_008_p11_non_terminal_reentry,
    evaluate_pd_ch2_009_done_claim_evidence_closure,
    evaluate_pd_ch2_010_green_external_run_evidence,
    evaluate_pd_ch2_011_stack_pack_phase_topology,
    evaluate_pd_ch2_012_mandatory_floor_human_waiver,
    evaluate_p0b_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


# -------------------------------------------------------------------------
# PD-CH2-007: P8 Retry Budget & Alternate Retry Paths
# -------------------------------------------------------------------------

def test_pd_ch2_007_happy():
    res = evaluate_pd_ch2_007_p8_retry_budget(
        retry_budget_allocated=3,
        retry_budget_consumed=1,
        alternate_retry_path_active=False,
        is_p8_repair=True,
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_007_gaming_fixture_ch2_t7():
    # CH2-T7: RetryBudget exhausted but alternate retry continues
    res = evaluate_pd_ch2_007_p8_retry_budget(
        retry_budget_allocated=3,
        retry_budget_consumed=3,
        alternate_retry_path_active=True,
        is_p8_repair=True,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-007"
    assert str(res) == "MISSING[PD-CH2-007]"


def test_pd_ch2_007_over_budget():
    res = evaluate_pd_ch2_007_p8_retry_budget(
        retry_budget_allocated=3,
        retry_budget_consumed=4,
        alternate_retry_path_active=False,
        is_p8_repair=True,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-007]"


def test_pd_ch2_007_zero_consumed_in_repair():
    res = evaluate_pd_ch2_007_p8_retry_budget(
        retry_budget_allocated=3,
        retry_budget_consumed=0,
        alternate_retry_path_active=False,
        is_p8_repair=True,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-007]"


def test_pd_ch2_007_no_authority():
    res = evaluate_pd_ch2_007_p8_retry_budget(
        retry_budget_allocated=3,
        retry_budget_consumed=1,
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-007]"


# -------------------------------------------------------------------------
# PD-CH2-008: P11 Non-Terminal & Re-entry at P0
# -------------------------------------------------------------------------

def test_pd_ch2_008_happy():
    res = evaluate_pd_ch2_008_p11_non_terminal_reentry(
        trigger_type="post_release_regression",
        target_phase="P0",
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_008_gaming_fixture_ch2_t8():
    # CH2-T8: post-release regression re-enters at P7 instead of P0
    res = evaluate_pd_ch2_008_p11_non_terminal_reentry(
        trigger_type="post_release_regression",
        target_phase="P7",
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-008"
    assert str(res) == "MISSING[PD-CH2-008]"


def test_pd_ch2_008_new_work_wrong_phase():
    res = evaluate_pd_ch2_008_p11_non_terminal_reentry(
        trigger_type="new_work",
        target_phase="P2",
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-008]"


def test_pd_ch2_008_no_authority():
    res = evaluate_pd_ch2_008_p11_non_terminal_reentry(
        trigger_type="post_release_regression",
        target_phase="P0",
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-008]"


# -------------------------------------------------------------------------
# PD-CH2-009: Model DONE Claim Evidence & Closure
# -------------------------------------------------------------------------

def test_pd_ch2_009_happy():
    res = evaluate_pd_ch2_009_done_claim_evidence_closure(
        model_done_claimed=True,
        admissible_evidence_present=True,
        kernel_evaluated_closure=True,
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_009_gaming_fixture_ch2_t9():
    # CH2-T9: agent submits DONE without evidence
    res = evaluate_pd_ch2_009_done_claim_evidence_closure(
        model_done_claimed=True,
        admissible_evidence_present=False,
        kernel_evaluated_closure=True,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-009"
    assert str(res) == "MISSING[PD-CH2-009]"


def test_pd_ch2_009_no_kernel_closure():
    res = evaluate_pd_ch2_009_done_claim_evidence_closure(
        model_done_claimed=True,
        admissible_evidence_present=True,
        kernel_evaluated_closure=False,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-009]"


def test_pd_ch2_009_no_authority():
    res = evaluate_pd_ch2_009_done_claim_evidence_closure(
        model_done_claimed=True,
        admissible_evidence_present=True,
        kernel_evaluated_closure=True,
        authority="UNAUTHORIZED",
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-009]"


# -------------------------------------------------------------------------
# PD-CH2-010: Green External Run Evidence
# -------------------------------------------------------------------------

def test_pd_ch2_010_happy():
    res = evaluate_pd_ch2_010_green_external_run_evidence(
        external_run_green=True,
        bound_to_obligation_inputs=True,
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_010_gaming_fixture_ch2_t10():
    # CH2-T10: unrelated green suite submitted for this obligation
    res = evaluate_pd_ch2_010_green_external_run_evidence(
        external_run_green=True,
        bound_to_obligation_inputs=False,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-010"
    assert str(res) == "MISSING[PD-CH2-010]"


def test_pd_ch2_010_failed_run():
    res = evaluate_pd_ch2_010_green_external_run_evidence(
        external_run_green=False,
        bound_to_obligation_inputs=True,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-010]"


def test_pd_ch2_010_no_authority():
    res = evaluate_pd_ch2_010_green_external_run_evidence(
        external_run_green=True,
        bound_to_obligation_inputs=True,
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-010]"


# -------------------------------------------------------------------------
# PD-CH2-011: Stack Pack Phase Topology
# -------------------------------------------------------------------------

def test_pd_ch2_011_happy():
    res = evaluate_pd_ch2_011_stack_pack_phase_topology(
        stack_pack_topology=STANDARD_LIFECYCLE_PHASES,
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_011_gaming_fixture_ch2_t11():
    # CH2-T11: stack pack introduces alternate phase topology
    alternate_topology = ("P0", "P1", "P2", "P3_CUSTOM", "P4", "P5", "P6", "P7", "P8", "P9", "P10", "P11")
    res = evaluate_pd_ch2_011_stack_pack_phase_topology(
        stack_pack_topology=alternate_topology,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-011"
    assert str(res) == "MISSING[PD-CH2-011]"


def test_pd_ch2_011_missing_core_phase():
    short_topology = ("P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7")
    res = evaluate_pd_ch2_011_stack_pack_phase_topology(
        stack_pack_topology=short_topology,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-011]"


def test_pd_ch2_011_no_authority():
    res = evaluate_pd_ch2_011_stack_pack_phase_topology(
        stack_pack_topology=STANDARD_LIFECYCLE_PHASES,
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-011]"


# -------------------------------------------------------------------------
# PD-CH2-012: Mandatory Floor Human Waiver
# -------------------------------------------------------------------------

def test_pd_ch2_012_happy_no_waiver():
    res = evaluate_pd_ch2_012_mandatory_floor_human_waiver(
        waiver_requested=False,
        has_authorized_waiver_path=False,
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_012_happy_authorized_waiver():
    res = evaluate_pd_ch2_012_mandatory_floor_human_waiver(
        waiver_requested=True,
        has_authorized_waiver_path=True,
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_012_gaming_fixture_ch2_t12():
    # CH2-T12: unsupported override with no frozen authorization
    res = evaluate_pd_ch2_012_mandatory_floor_human_waiver(
        waiver_requested=True,
        has_authorized_waiver_path=False,
        authority=AUTH,
    )
    assert res.state == GateState.BLOCKED_ON_HUMAN
    assert res.must_id == "PD-CH2-012"
    assert str(res) == "BLOCKED_ON_HUMAN[PD-CH2-012]"


def test_pd_ch2_012_no_authority():
    res = evaluate_pd_ch2_012_mandatory_floor_human_waiver(
        waiver_requested=False,
        has_authorized_waiver_path=False,
        authority=None,
    )
    assert res.state == GateState.BLOCKED_ON_HUMAN
    assert res.must_id == "PD-CH2-012"
    assert str(res) == "BLOCKED_ON_HUMAN[PD-CH2-012]"


# -------------------------------------------------------------------------
# Composite Gate Evaluator: evaluate_p0b_gate
# -------------------------------------------------------------------------

def test_p0b_composite_gate_happy():
    manifest = {
        "retry_budget_allocated": 3,
        "retry_budget_consumed": 1,
        "alternate_retry_path_active": False,
        "is_p8_repair": False,
        "trigger_type": "standard_progress",
        "target_phase": "P0",
        "model_done_claimed": False,
        "admissible_evidence_present": True,
        "kernel_evaluated_closure": True,
        "external_run_green": True,
        "bound_to_obligation_inputs": True,
        "stack_pack_topology": STANDARD_LIFECYCLE_PHASES,
        "waiver_requested": False,
        "has_authorized_waiver_path": False,
    }
    res = evaluate_p0b_gate(manifest, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_p0b_composite_gate_fail_closed_no_authority():
    manifest = {}
    res = evaluate_p0b_gate(manifest, authority=None)
    assert res.state == GateState.MISSING
    assert len(res.failures) == 6
