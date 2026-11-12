"""Tests for Lifecycle P6 Implementation Governance Invariants (PD-CH2-037, 038, 039, 040, 048)."""
from __future__ import annotations

import pytest

from sclass.product.gate import GateOutput, GateState
from sclass.product.lifecycle_p6 import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch2_037_execution_gate_authorization,
    evaluate_pd_ch2_038_scope_growth_stop,
    evaluate_pd_ch2_039_implementation_claims,
    evaluate_pd_ch2_040_canonical_delta_kernel_receipt,
    evaluate_pd_ch2_048_test_input_set_exclusion_check,
    evaluate_p6_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


# -------------------------------------------------------------------------
# PD-CH2-037: ExecutionGate Authorization
# -------------------------------------------------------------------------

def test_pd_ch2_037_happy():
    res = evaluate_pd_ch2_037_execution_gate_authorization(
        has_execution_gate_auth=True,
        task_id="T1",
        scope="src",
        target="src/core.py",
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_037_gaming_fixture_ch2_t37():
    # CH2-T37: no authorization
    res = evaluate_pd_ch2_037_execution_gate_authorization(
        has_execution_gate_auth=False,
        task_id="T1",
        scope="src",
        target="src/core.py",
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-037"
    assert str(res) == "MISSING[PD-CH2-037]"


def test_pd_ch2_037_no_authority():
    res = evaluate_pd_ch2_037_execution_gate_authorization(
        has_execution_gate_auth=True,
        task_id="T1",
        scope="src",
        target="src/core.py",
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-037]"


# -------------------------------------------------------------------------
# PD-CH2-038: Scope Growth Stop
# -------------------------------------------------------------------------

def test_pd_ch2_038_happy():
    res = evaluate_pd_ch2_038_scope_growth_stop(
        is_out_of_scope=False,
        delta_files=["src/auth.py"],
        declared_scope={"src/auth.py", "src/user.py"},
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_038_gaming_fixture_ch2_t38():
    # CH2-T38: out-of-scope delta
    res = evaluate_pd_ch2_038_scope_growth_stop(
        is_out_of_scope=True,
        delta_files=["src/other.py"],
        declared_scope={"src/auth.py"},
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-038"
    assert str(res) == "MISSING[PD-CH2-038]"


def test_pd_ch2_038_out_of_scope_flag_isolated():
    """Mutant kill test: is_out_of_scope=True with files matching declared_scope."""
    res = evaluate_pd_ch2_038_scope_growth_stop(
        is_out_of_scope=True,
        delta_files=["src/auth.py"],
        declared_scope={"src/auth.py"},
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-038"
    assert "Out-of-scope delta detected" in res.detail


def test_pd_ch2_038_file_not_in_scope():
    res = evaluate_pd_ch2_038_scope_growth_stop(
        is_out_of_scope=False,
        delta_files=["src/unapproved.py"],
        declared_scope={"src/auth.py"},
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-038]"


def test_pd_ch2_038_no_authority():
    res = evaluate_pd_ch2_038_scope_growth_stop(
        is_out_of_scope=False,
        delta_files=["src/auth.py"],
        declared_scope={"src/auth.py"},
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-038]"


# -------------------------------------------------------------------------
# PD-CH2-039: Implementation Claims (PD-F7-006 Delegation)
# -------------------------------------------------------------------------

def test_pd_ch2_039_happy():
    res = evaluate_pd_ch2_039_implementation_claims(
        claimed_symbols=["UserValidator"],
        post_delta_symbols={"UserValidator", "Other"},
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_039_gaming_fixture_ch2_t39():
    # CH2-T39: symbol absent post-delta -> MISSING[PD-F7-006]
    res = evaluate_pd_ch2_039_implementation_claims(
        claimed_symbols=["MissingSymbol"],
        post_delta_symbols={"ExistingSymbol"},
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-006"
    assert str(res) == "MISSING[PD-F7-006]"


def test_pd_ch2_039_no_authority():
    res = evaluate_pd_ch2_039_implementation_claims(
        claimed_symbols=["UserValidator"],
        post_delta_symbols={"UserValidator"},
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F7-006"
    assert str(res) == "MISSING[PD-F7-006]"


# -------------------------------------------------------------------------
# PD-CH2-040: Canonical Delta Kernel Receipt
# -------------------------------------------------------------------------

def test_pd_ch2_040_happy():
    res = evaluate_pd_ch2_040_canonical_delta_kernel_receipt(
        has_kernel_receipt=True,
        kernel_receipt_digest="sha256:kernel123",
        kernel_denied=False,
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_040_gaming_fixture_ch2_t40():
    # CH2-T40: no kernel receipt
    res = evaluate_pd_ch2_040_canonical_delta_kernel_receipt(
        has_kernel_receipt=False,
        kernel_receipt_digest=None,
        kernel_denied=False,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-040"
    assert str(res) == "MISSING[PD-CH2-040]"


def test_pd_ch2_040_kernel_denied():
    res = evaluate_pd_ch2_040_canonical_delta_kernel_receipt(
        has_kernel_receipt=True,
        kernel_receipt_digest="sha256:123",
        kernel_denied=True,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-040]"


def test_pd_ch2_040_no_authority():
    res = evaluate_pd_ch2_040_canonical_delta_kernel_receipt(
        has_kernel_receipt=True,
        kernel_receipt_digest="sha256:123",
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-040]"


# -------------------------------------------------------------------------
# PD-CH2-048: TestInputSet Exclusion Check
# -------------------------------------------------------------------------

def test_pd_ch2_048_happy():
    res = evaluate_pd_ch2_048_test_input_set_exclusion_check(
        p6_tests_frozen_invoked=True,
        p6_modifies_test_input_set=False,
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_048_gaming_fixture_ch2_t48():
    # CH2-T48: P6 composition omits P6-TESTS-FROZEN
    res = evaluate_pd_ch2_048_test_input_set_exclusion_check(
        p6_tests_frozen_invoked=False,
        p6_modifies_test_input_set=False,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-048"
    assert str(res) == "MISSING[PD-CH2-048]"


def test_pd_ch2_048_modifies_test_input_set():
    res = evaluate_pd_ch2_048_test_input_set_exclusion_check(
        p6_tests_frozen_invoked=True,
        p6_modifies_test_input_set=True,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-048]"


def test_pd_ch2_048_no_authority():
    res = evaluate_pd_ch2_048_test_input_set_exclusion_check(
        p6_tests_frozen_invoked=True,
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-048]"


# -------------------------------------------------------------------------
# Composite Gate Evaluator
# -------------------------------------------------------------------------

def test_p6_composite_gate_happy():
    manifest = {
        "has_execution_gate_auth": True,
        "task_id": "T1",
        "scope": "src",
        "target": "src/core.py",
        "is_out_of_scope": False,
        "delta_files": ["src/core.py"],
        "declared_scope": {"src/core.py"},
        "claimed_symbols": ["CoreFunc"],
        "post_delta_symbols": {"CoreFunc"},
        "has_kernel_receipt": True,
        "kernel_receipt_digest": "sha256:receipt1",
        "kernel_denied": False,
        "p6_tests_frozen_invoked": True,
        "p6_modifies_test_input_set": False,
    }
    res = evaluate_p6_gate(manifest, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_p6_composite_gate_fail_closed_no_authority():
    manifest = {}
    res = evaluate_p6_gate(manifest, authority=None)
    assert res.state == GateState.MISSING
    assert len(res.failures) == 5
