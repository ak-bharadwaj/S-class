"""Tests verifying that every aggregator gate fails closed when authority is omitted (Task E3)."""

import pytest
from sclass.product.gate import GateState, GateOutput

from sclass.product.adapter_qualification_contract import evaluate_b4_a_gate
from sclass.product.adapter_diff_spec_anchors import evaluate_b4_b_gate
from sclass.product.lifecycle_phase_admission import evaluate_b4_c_gate
from sclass.product.execution_flow_testinput import evaluate_b4_d_gate
from sclass.product.isolation_claims import evaluate_b4_e_gate
from sclass.product.context_resume_threats import evaluate_b4_f_gate
from sclass.product.enforcement_workspace_gate import evaluate_b5_gate
from sclass.product.knowledge_package_quarantine import evaluate_b6_a_gate
from sclass.product.oss_qualification_playbook import evaluate_b6_b_gate
from sclass.product.wire_session_consequential_gate import evaluate_b7_a_gate
from sclass.product.notification_skill_normalization import evaluate_b7_b_gate
from sclass.product.threat_eval_regression_gate import evaluate_b9_a_gate
from sclass.product.stratum_sampling_compatibility import evaluate_b9_b_gate
from sclass.product.erratum_issue_registry import evaluate_b9_c_gate
from sclass.product.lifecycle_p0a import evaluate_p0a_gate
from sclass.product.lifecycle_p0b import evaluate_p0b_gate
from sclass.product.lifecycle_p1_p4 import evaluate_p1_p4_gate
from sclass.product.lifecycle_p3a import evaluate_p3a_gate
from sclass.product.lifecycle_p3b import evaluate_p3b_gate
from sclass.product.lifecycle_p3c_p8_p10 import evaluate_p3c_p8_p10_gate
from sclass.product.lifecycle_p5 import evaluate_p5_gate
from sclass.product.lifecycle_p6 import evaluate_p6_gate
from sclass.product.lifecycle_p7 import evaluate_p7_gate
from sclass.product.lifecycle_p11 import evaluate_p11_gate
from sclass.product.f4_lane_selection import evaluate_f4_lane_selection
from sclass.product.gate_evaluator import evaluate_f5_gate


def _assert_all_non_satisfied(res):
    """Helper asserting every MUST result is strictly non-SATISFIED."""
    if isinstance(res, dict):
        assert len(res) > 0, "Aggregator returned empty dictionary"
        for must_id, val in res.items():
            if isinstance(val, GateOutput):
                assert val.state != GateState.SATISFIED, f"{must_id} returned SATISFIED without authority: {val}"
            elif isinstance(val, str):
                assert "SATISFIED" not in val, f"{must_id} returned SATISFIED string without authority: {val}"
            elif hasattr(val, "status"):
                assert val.status != "SATISFIED", f"{must_id} returned SATISFIED status without authority: {val}"
    elif isinstance(res, GateOutput):
        assert res.state != GateState.SATISFIED, f"Aggregator returned SATISFIED without authority: {res}"
    elif hasattr(res, "product_gate"):
        assert res.product_gate.state != GateState.SATISFIED, f"F5Result returned SATISFIED without authority: {res.product_gate}"
    elif hasattr(res, "status"):
        assert res.status != "SATISFIED", f"Aggregator returned SATISFIED status without authority: {res}"
    else:
        pytest.fail(f"Unrecognized aggregator return type: {type(res)}")


def test_aggregator_evaluate_b4_a_gate_authority_omitted():
    res = evaluate_b4_a_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_b4_b_gate_authority_omitted():
    res = evaluate_b4_b_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_b4_c_gate_authority_omitted():
    res = evaluate_b4_c_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_b4_d_gate_authority_omitted():
    res = evaluate_b4_d_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_b4_e_gate_authority_omitted():
    res = evaluate_b4_e_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_b4_f_gate_authority_omitted():
    res = evaluate_b4_f_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_b5_gate_authority_omitted():
    res = evaluate_b5_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_b6_a_gate_authority_omitted():
    res = evaluate_b6_a_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_b6_b_gate_authority_omitted():
    res = evaluate_b6_b_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_b7_a_gate_authority_omitted():
    res = evaluate_b7_a_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_b7_b_gate_authority_omitted():
    res = evaluate_b7_b_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_b9_a_gate_authority_omitted():
    res = evaluate_b9_a_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_b9_b_gate_authority_omitted():
    res = evaluate_b9_b_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_b9_c_gate_authority_omitted():
    res = evaluate_b9_c_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_p0a_gate_authority_omitted():
    res = evaluate_p0a_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_p0b_gate_authority_omitted():
    res = evaluate_p0b_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_p1_p4_gate_authority_omitted():
    res = evaluate_p1_p4_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_p3a_gate_authority_omitted():
    res = evaluate_p3a_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_p3b_gate_authority_omitted():
    res = evaluate_p3b_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_p3c_p8_p10_gate_authority_omitted():
    res = evaluate_p3c_p8_p10_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_p5_gate_authority_omitted():
    res = evaluate_p5_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_p6_gate_authority_omitted():
    res = evaluate_p6_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_p7_gate_authority_omitted():
    res = evaluate_p7_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_p11_gate_authority_omitted():
    res = evaluate_p11_gate({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_f4_lane_selection_authority_omitted():
    res = evaluate_f4_lane_selection({}, authority=None)
    _assert_all_non_satisfied(res)


def test_aggregator_evaluate_f5_gate_authority_omitted():
    res = evaluate_f5_gate(
        phase="P1",
        canonical_state_binding={"state": "valid"},
        pinned_guidance={"guidance": "valid"},
        policy_version="1.0",
        evaluator_version="1.0",
        evaluation_instant="2026-11-09T00:00:00Z",
        caller_authority=None,
    )
    _assert_all_non_satisfied(res)
