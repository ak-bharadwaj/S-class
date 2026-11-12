"""Tests for Lifecycle P7 Verification Governance Invariants (PD-CH2-041, 042, 043, 044, 045, 050)."""
from __future__ import annotations

import pytest

from sclass.product.gate import GateOutput, GateState
from sclass.product.lifecycle_p7 import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch2_041_evidence_binding,
    evaluate_pd_ch2_042_adapter_qualification,
    evaluate_pd_ch2_043_independence_floor,
    evaluate_pd_ch2_044_freshness_predicate,
    evaluate_pd_ch2_045_closure_ownership,
    evaluate_pd_ch2_050_deterministic_rerun,
    evaluate_p7_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


# -------------------------------------------------------------------------
# PD-CH2-041: Verification Evidence Binding
# -------------------------------------------------------------------------

def test_pd_ch2_041_happy():
    res = evaluate_pd_ch2_041_evidence_binding(
        evidence_identity_bound=True,
        current_target_bound=True,
        current_step_bound=True,
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_041_gaming_fixture_ch2_t41():
    # CH2-T41: missing target/step
    res = evaluate_pd_ch2_041_evidence_binding(
        evidence_identity_bound=True,
        current_target_bound=False,
        current_step_bound=False,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-041"
    assert str(res) == "MISSING[PD-CH2-041]"


def test_pd_ch2_041_no_authority():
    res = evaluate_pd_ch2_041_evidence_binding(
        evidence_identity_bound=True,
        current_target_bound=True,
        current_step_bound=True,
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-041]"


# -------------------------------------------------------------------------
# PD-CH2-042: Adapter Qualification
# -------------------------------------------------------------------------

def test_pd_ch2_042_happy():
    res = evaluate_pd_ch2_042_adapter_qualification(
        adapter_name="pytest-sclass",
        is_f10_qualified=True,
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_042_gaming_fixture_ch2_t42():
    # CH2-T42: unqualified adapter
    res = evaluate_pd_ch2_042_adapter_qualification(
        adapter_name="unverified-adapter",
        is_f10_qualified=False,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-042"
    assert str(res) == "MISSING[PD-CH2-042]"


def test_pd_ch2_042_no_authority():
    res = evaluate_pd_ch2_042_adapter_qualification(
        adapter_name="pytest-sclass",
        is_f10_qualified=True,
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-042]"


# -------------------------------------------------------------------------
# PD-CH2-043: Independence Floor
# -------------------------------------------------------------------------

def test_pd_ch2_043_happy():
    res = evaluate_pd_ch2_043_independence_floor(
        independence_level=3,
        required_floor=2,
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_043_gaming_fixture_ch2_t43():
    # CH2-T43: floor not met
    res = evaluate_pd_ch2_043_independence_floor(
        independence_level=1,
        required_floor=3,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-043"
    assert str(res) == "MISSING[PD-CH2-043]"


def test_pd_ch2_043_no_authority():
    res = evaluate_pd_ch2_043_independence_floor(
        independence_level=3,
        required_floor=2,
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-043]"


# -------------------------------------------------------------------------
# PD-CH2-044: Freshness Predicate
# -------------------------------------------------------------------------

def test_pd_ch2_044_happy():
    res = evaluate_pd_ch2_044_freshness_predicate(
        evidence_digest="sha256:target100",
        current_code_digest="sha256:target100",
        is_stale=False,
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_044_gaming_fixture_ch2_t44():
    # CH2-T44: stale digest
    res = evaluate_pd_ch2_044_freshness_predicate(
        evidence_digest="sha256:old_stale_digest",
        current_code_digest="sha256:new_code_digest",
        is_stale=True,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-044"
    assert str(res) == "MISSING[PD-CH2-044]"


def test_pd_ch2_044_no_authority():
    res = evaluate_pd_ch2_044_freshness_predicate(
        evidence_digest="sha256:target100",
        current_code_digest="sha256:target100",
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-044]"


# -------------------------------------------------------------------------
# PD-CH2-045: Closure Ownership
# -------------------------------------------------------------------------

def test_pd_ch2_045_happy():
    res = evaluate_pd_ch2_045_closure_ownership(
        kernel_closure_result="CLOSED",
        agent_asserts_closure=False,
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_045_gaming_fixture_ch2_t45():
    # CH2-T45: agent asserts closure without kernel result
    res = evaluate_pd_ch2_045_closure_ownership(
        kernel_closure_result=None,
        agent_asserts_closure=True,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-045"
    assert str(res) == "MISSING[PD-CH2-045]"


def test_pd_ch2_045_no_authority():
    res = evaluate_pd_ch2_045_closure_ownership(
        kernel_closure_result="CLOSED",
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-045]"


# -------------------------------------------------------------------------
# PD-CH2-050: Deterministic Reruns
# -------------------------------------------------------------------------

def test_pd_ch2_050_happy():
    res = evaluate_pd_ch2_050_deterministic_rerun(
        rerun_results=["PASS", "PASS", "PASS"],
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_050_gaming_fixture_ch2_t50():
    # CH2-T50: same inputs with rerun results [PASS, FAIL] -> non-SATISFIED
    res = evaluate_pd_ch2_050_deterministic_rerun(
        rerun_results=["PASS", "FAIL"],
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-050"
    assert str(res) == "MISSING[PD-CH2-050]"
    assert str(res) != "SATISFIED"
    assert "Nondeterministic rerun results across identical inputs" in res.detail


def test_pd_ch2_050_no_authority():
    res = evaluate_pd_ch2_050_deterministic_rerun(
        rerun_results=["PASS", "PASS"],
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-050]"


# -------------------------------------------------------------------------
# Composite Gate Evaluator
# -------------------------------------------------------------------------

def test_p7_composite_gate_happy():
    manifest = {
        "evidence_identity_bound": True,
        "current_target_bound": True,
        "current_step_bound": True,
        "adapter_name": "pytest-sclass",
        "is_f10_qualified": True,
        "independence_level": 3,
        "required_floor": 2,
        "evidence_digest": "sha256:1",
        "current_code_digest": "sha256:1",
        "is_stale": False,
        "kernel_closure_result": "CLOSED",
        "agent_asserts_closure": False,
        "rerun_results": ["PASS", "PASS"],
    }
    res = evaluate_p7_gate(manifest, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_p7_composite_gate_fail_closed_no_authority():
    manifest = {}
    res = evaluate_p7_gate(manifest, authority=None)
    assert res.state == GateState.MISSING
    assert len(res.failures) == 6
