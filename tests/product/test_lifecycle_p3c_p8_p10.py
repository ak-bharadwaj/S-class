"""Tests for Lifecycle P3C, P8, P9 & P10 Invariants (PD-CH2-026, 028, 051, 052, 053)."""
from __future__ import annotations

import pytest

from sclass.product.gate import GateOutput, GateState
from sclass.product.lifecycle_p3c_p8_p10 import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    ReleaseEvaluationOutput,
    evaluate_pd_ch2_026_adr_design_digest_binding,
    evaluate_pd_ch2_028_unique_must_ids,
    evaluate_pd_ch2_051_p8_retry_budget_exhaustion,
    evaluate_pd_ch2_052_p9_task_aggregation_findings_closure,
    evaluate_pd_ch2_053_p10_kernel_release_evaluation,
    evaluate_p3c_p8_p10_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


# -------------------------------------------------------------------------
# PD-CH2-026: ADR & Design Digest Binding
# -------------------------------------------------------------------------

def test_pd_ch2_026_happy():
    adrs = [{"id": "ADR-001", "digest": "sha256:111", "lint_passed": True, "is_stale": False}]
    res = evaluate_pd_ch2_026_adr_design_digest_binding(adrs, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_026_gaming_fixture_ch2_t26():
    # CH2-T26: stale/unresolved
    adrs = [{"id": "ADR-001", "digest": "sha256:111", "lint_passed": False, "is_stale": True}]
    res = evaluate_pd_ch2_026_adr_design_digest_binding(adrs, authority=AUTH)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-026"
    assert str(res) == "MISSING[PD-CH2-026]"


def test_pd_ch2_026_no_authority():
    adrs = [{"id": "ADR-001", "digest": "sha256:111", "lint_passed": True}]
    res = evaluate_pd_ch2_026_adr_design_digest_binding(adrs, authority=None)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-026]"


# -------------------------------------------------------------------------
# PD-CH2-028: Unique MUST IDs
# -------------------------------------------------------------------------

def test_pd_ch2_028_happy():
    mids = ["PD-CH2-001", "PD-CH2-002", "PD-CH2-003"]
    res = evaluate_pd_ch2_028_unique_must_ids(mids, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_028_gaming_fixture_ch2_t28():
    # CH2-T28: duplicate ID
    mids = ["PD-CH2-001", "PD-CH2-002", "PD-CH2-001"]
    res = evaluate_pd_ch2_028_unique_must_ids(mids, authority=AUTH)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-028"
    assert str(res) == "MISSING[PD-CH2-028]"


def test_pd_ch2_028_no_authority():
    mids = ["PD-CH2-001", "PD-CH2-002"]
    res = evaluate_pd_ch2_028_unique_must_ids(mids, authority=None)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-028]"


# -------------------------------------------------------------------------
# PD-CH2-051: P8 Retry Budget Exhaustion
# -------------------------------------------------------------------------

def test_pd_ch2_051_happy():
    res = evaluate_pd_ch2_051_p8_retry_budget_exhaustion(
        retry_budget_remaining=2,
        earliest_affected_phase="P2",
        routed_phase="P2",
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_051_gaming_fixture_ch2_t51():
    # CH2-T51: exhausted budget
    res = evaluate_pd_ch2_051_p8_retry_budget_exhaustion(
        retry_budget_remaining=0,
        earliest_affected_phase="P2",
        routed_phase="P2",
        authority=AUTH,
    )
    assert res.state == GateState.BLOCKED_ON_HUMAN
    assert res.must_id == "PD-CH2-051"
    assert str(res) == "BLOCKED_ON_HUMAN[PD-CH2-051]"


def test_pd_ch2_051_wrong_routing():
    res = evaluate_pd_ch2_051_p8_retry_budget_exhaustion(
        retry_budget_remaining=2,
        earliest_affected_phase="P2",
        routed_phase="P6",
        authority=AUTH,
    )
    assert res.state == GateState.BLOCKED_ON_HUMAN
    assert res.must_id == "PD-CH2-051"
    assert str(res) == "BLOCKED_ON_HUMAN[PD-CH2-051]"


def test_pd_ch2_051_no_authority():
    res = evaluate_pd_ch2_051_p8_retry_budget_exhaustion(
        retry_budget_remaining=2,
        authority=None,
    )
    assert res.state == GateState.BLOCKED_ON_HUMAN
    assert res.must_id == "PD-CH2-051"
    assert str(res) == "BLOCKED_ON_HUMAN[PD-CH2-051]"


# -------------------------------------------------------------------------
# PD-CH2-052: P9 Task Aggregation & Findings Closure
# -------------------------------------------------------------------------

def test_pd_ch2_052_happy():
    res = evaluate_pd_ch2_052_p9_task_aggregation_findings_closure(
        required_p7_tasks=["T-1", "T-2"],
        aggregated_p7_tasks=["T-1", "T-2", "T-3"],
        open_mandatory_findings=[],
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_052_gaming_fixture_ch2_t52_omitted_task():
    # CH2-T52: one required P7 result omitted
    res = evaluate_pd_ch2_052_p9_task_aggregation_findings_closure(
        required_p7_tasks=["T-1", "T-2"],
        aggregated_p7_tasks=["T-1"],
        open_mandatory_findings=[],
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-052"
    assert str(res) == "MISSING[PD-CH2-052]"


def test_pd_ch2_052_open_finding():
    res = evaluate_pd_ch2_052_p9_task_aggregation_findings_closure(
        required_p7_tasks=["T-1"],
        aggregated_p7_tasks=["T-1"],
        open_mandatory_findings=["SECURITY-VULN-001"],
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-052"
    assert str(res) == "MISSING[PD-CH2-052]"


def test_pd_ch2_052_no_authority():
    res = evaluate_pd_ch2_052_p9_task_aggregation_findings_closure(
        required_p7_tasks=["T-1"],
        aggregated_p7_tasks=["T-1"],
        open_mandatory_findings=[],
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-052]"


# -------------------------------------------------------------------------
# PD-CH2-053: P10 Kernel ReleaseEvaluation & Denial Preservation
# -------------------------------------------------------------------------

def test_pd_ch2_053_happy():
    res = evaluate_pd_ch2_053_p10_kernel_release_evaluation(
        kernel_release_evaluation="ALLOW",
        product_checks_pass=True,
        authority=AUTH,
    )
    assert res.status == "SATISFIED"
    assert str(res) == "SATISFIED"


def test_pd_ch2_053_gaming_fixture_ch2_t53_denied():
    # CH2-T53: kernel ReleaseEvaluation=DENIED and product checks pass -> combined DENIED
    res = evaluate_pd_ch2_053_p10_kernel_release_evaluation(
        kernel_release_evaluation="DENIED",
        product_checks_pass=True,
        authority=AUTH,
    )
    assert res.status == "DENIED"
    assert str(res) == "DENIED"


def test_pd_ch2_053_product_checks_fail():
    res = evaluate_pd_ch2_053_p10_kernel_release_evaluation(
        kernel_release_evaluation="ALLOW",
        product_checks_pass=False,
        authority=AUTH,
    )
    assert res.status == "MISSING[PD-CH2-053]"
    assert str(res) == "MISSING[PD-CH2-053]"


def test_pd_ch2_053_no_authority():
    res = evaluate_pd_ch2_053_p10_kernel_release_evaluation(
        kernel_release_evaluation="ALLOW",
        product_checks_pass=True,
        authority=None,
    )
    assert res.status == "MISSING[PD-CH2-053]"
    assert str(res) == "MISSING[PD-CH2-053]"


# -------------------------------------------------------------------------
# Composite Gate Evaluator
# -------------------------------------------------------------------------

def test_p3c_p8_p10_composite_gate_happy():
    manifest = {
        "adr_sources": [{"id": "A1", "digest": "sha256:1", "lint_passed": True, "is_stale": False}],
        "must_ids": ["MID-1", "MID-2"],
        "retry_budget_remaining": 3,
        "earliest_affected_phase": "P2",
        "routed_phase": "P2",
        "required_p7_tasks": ["P7-1"],
        "aggregated_p7_tasks": ["P7-1"],
        "open_mandatory_findings": [],
        "kernel_release_evaluation": "ALLOW",
        "product_checks_pass": True,
    }
    res = evaluate_p3c_p8_p10_gate(manifest, authority=AUTH)
    assert res.state == "SATISFIED" or getattr(res, "state", None) == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_p3c_p8_p10_composite_gate_fail_closed_no_authority():
    manifest = {}
    res = evaluate_p3c_p8_p10_gate(manifest, authority=None)
    assert str(res) == "MISSING[PD-CH2-026]"
