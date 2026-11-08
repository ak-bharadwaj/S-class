"""Tests for Lifecycle P5 Test Construction & Red Run Governance (PD-CH2-033, 034, 035, 036, 046, 047)."""
from __future__ import annotations

import pytest

from sclass.product.gate import GateOutput, GateState
from sclass.product.lifecycle_p5 import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch2_033_delta_sequence,
    evaluate_pd_ch2_034_red_run_validity,
    evaluate_pd_ch2_035_executable_spec_constraints,
    evaluate_pd_ch2_036_adapter_qualification,
    evaluate_pd_ch2_046_test_input_set_binding,
    evaluate_pd_ch2_047_red_classification_source,
    evaluate_p5_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


# -------------------------------------------------------------------------
# PD-CH2-033: Delta Sequence (Test-First)
# -------------------------------------------------------------------------

def test_pd_ch2_033_happy():
    res = evaluate_pd_ch2_033_delta_sequence(test_delta_seq=1, impl_delta_seq=2, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_033_gaming_fixture_ch2_t33():
    # CH2-T33: implementation delta ordered first
    res = evaluate_pd_ch2_033_delta_sequence(test_delta_seq=5, impl_delta_seq=3, authority=AUTH)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-033"
    assert str(res) == "MISSING[PD-CH2-033]"


def test_pd_ch2_033_same_sequence():
    res = evaluate_pd_ch2_033_delta_sequence(test_delta_seq=2, impl_delta_seq=2, authority=AUTH)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-033]"


def test_pd_ch2_033_no_authority():
    res = evaluate_pd_ch2_033_delta_sequence(test_delta_seq=1, impl_delta_seq=2, authority=None)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-033]"


# -------------------------------------------------------------------------
# PD-CH2-034: Red Run Validity
# -------------------------------------------------------------------------

def test_pd_ch2_034_happy_fixture_ch2_t34_valid_red():
    # CH2-T34: valid red
    res = evaluate_pd_ch2_034_red_run_validity(
        adapter_qualified=True,
        run_failed_designed_test=True,
        failure_class="AssertionError",
        designed_class="AssertionError",
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_034_gaming_fixture_ch2_t34_wrong_reason():
    res = evaluate_pd_ch2_034_red_run_validity(
        adapter_qualified=True,
        run_failed_designed_test=True,
        failure_class="HarnessError",
        designed_class="AssertionError",
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-034"
    assert str(res) == "MISSING[PD-CH2-034]"


def test_pd_ch2_034_skip_or_timeout():
    res = evaluate_pd_ch2_034_red_run_validity(
        adapter_qualified=True,
        run_failed_designed_test=True,
        failure_class="AssertionError",
        designed_class="AssertionError",
        timeout=True,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-034]"


def test_pd_ch2_034_no_authority():
    res = evaluate_pd_ch2_034_red_run_validity(
        adapter_qualified=True,
        run_failed_designed_test=True,
        failure_class="AssertionError",
        designed_class="AssertionError",
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-034]"


# -------------------------------------------------------------------------
# PD-CH2-035: Executable Specifications & Finite Domain
# -------------------------------------------------------------------------

def test_pd_ch2_035_happy():
    res = evaluate_pd_ch2_035_executable_spec_constraints(
        is_executable_f1_f2=True,
        finite_domain=True,
        is_prose_only=False,
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_035_gaming_fixture_ch2_t35():
    # CH2-T35: prose-only/unbounded predicate
    res = evaluate_pd_ch2_035_executable_spec_constraints(
        is_executable_f1_f2=False,
        finite_domain=False,
        is_prose_only=True,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-035"
    assert str(res) == "MISSING[PD-CH2-035]"


def test_pd_ch2_035_no_authority():
    res = evaluate_pd_ch2_035_executable_spec_constraints(
        is_executable_f1_f2=True,
        finite_domain=True,
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-035]"


# -------------------------------------------------------------------------
# PD-CH2-036: Test Adapter Qualification
# -------------------------------------------------------------------------

def test_pd_ch2_036_happy():
    res = evaluate_pd_ch2_036_adapter_qualification(
        adapter_name="pytest-sclass",
        is_f10_qualified=True,
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_036_gaming_fixture_ch2_t36():
    # CH2-T36: unqualified adapter
    res = evaluate_pd_ch2_036_adapter_qualification(
        adapter_name="unverified-custom-adapter",
        is_f10_qualified=False,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-036"
    assert str(res) == "MISSING[PD-CH2-036]"


def test_pd_ch2_036_no_authority():
    res = evaluate_pd_ch2_036_adapter_qualification(
        adapter_name="pytest-sclass",
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-036]"


# -------------------------------------------------------------------------
# PD-CH2-046: Primary Test Digest in Complete TestInputSet
# -------------------------------------------------------------------------

def test_pd_ch2_046_happy():
    res = evaluate_pd_ch2_046_test_input_set_binding(
        primary_test_digest="sha256:primary123",
        bound_test_input_set={"test_file.py": "sha256:primary123", "conftest.py": "sha256:conf456"},
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_046_gaming_fixture_ch2_t46():
    # CH2-T46: red run requested before primary test digest is bound
    res = evaluate_pd_ch2_046_test_input_set_binding(
        primary_test_digest="sha256:unbound789",
        bound_test_input_set={"conftest.py": "sha256:conf456"},
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-046"
    assert str(res) == "MISSING[PD-CH2-046]"


def test_pd_ch2_046_no_authority():
    res = evaluate_pd_ch2_046_test_input_set_binding(
        primary_test_digest="sha256:primary123",
        bound_test_input_set={"test_file.py": "sha256:primary123"},
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-046]"


# -------------------------------------------------------------------------
# PD-CH2-047: Red Classification Source
# -------------------------------------------------------------------------

def test_pd_ch2_047_happy():
    res = evaluate_pd_ch2_047_red_classification_source(
        adapter_structured_result={"failed_test": "test_invariant_a", "failure_reason": "AssertionError: expected True"},
        designed_test_tuple=("test_invariant_a", "AssertionError: expected True"),
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_047_gaming_fixture_ch2_t47():
    # CH2-T47: agent says right reason but adapter result targets wrong behavior
    res = evaluate_pd_ch2_047_red_classification_source(
        adapter_structured_result={"failed_test": "test_different_b", "failure_reason": "ZeroDivisionError"},
        designed_test_tuple=("test_invariant_a", "AssertionError: expected True"),
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-047"
    assert str(res) == "MISSING[PD-CH2-047]"


def test_pd_ch2_047_agent_assertion_bypass():
    res = evaluate_pd_ch2_047_red_classification_source(
        adapter_structured_result={"failed_test": "test_invariant_a", "failure_reason": "AssertionError: expected True"},
        designed_test_tuple=("test_invariant_a", "AssertionError: expected True"),
        agent_assertion_used=True,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-047]"


def test_pd_ch2_047_no_authority():
    res = evaluate_pd_ch2_047_red_classification_source(
        adapter_structured_result={"failed_test": "test_invariant_a", "failure_reason": "fail"},
        designed_test_tuple=("test_invariant_a", "fail"),
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-047]"


# -------------------------------------------------------------------------
# Composite Gate Evaluator
# -------------------------------------------------------------------------

def test_p5_composite_gate_happy():
    manifest = {
        "test_delta_seq": 1,
        "impl_delta_seq": 2,
        "adapter_qualified": True,
        "run_failed_designed_test": True,
        "failure_class": "AssertionError",
        "designed_class": "AssertionError",
        "is_executable_f1_f2": True,
        "finite_domain": True,
        "is_prose_only": False,
        "adapter_name": "pytest-sclass",
        "primary_test_digest": "sha256:t1",
        "bound_test_input_set": {"t1.py": "sha256:t1"},
        "adapter_structured_result": {"failed_test": "t", "failure_reason": "f"},
        "designed_test_tuple": ("t", "f"),
    }
    res = evaluate_p5_gate(manifest, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_p5_composite_gate_fail_closed_no_authority():
    manifest = {}
    res = evaluate_p5_gate(manifest, authority=None)
    assert res.state == GateState.MISSING
    assert len(res.failures) == 6
