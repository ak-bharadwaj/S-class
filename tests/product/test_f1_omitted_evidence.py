"""Dedicated Omitted-Evidence Test Suite for F1 Evaluator (evaluate_f1_representation).

Verifies fail-closed behavior across all input parameters and authority facts per
CL Builder Rules (Rule 3 & Rule 6) and R3-3 (Finding F-10).
Every omission of required evidence must produce MISSING or BLOCKED_ON_HUMAN, never SATISFIED.
"""

from __future__ import annotations

import pytest
from typing import Any, Dict, Optional

from sclass.product.artifacts import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_f1_representation,
)
from sclass.product.gate import GateOutput, GateState


# =============================================================================
# 1. Entire Artifact Omission Tests
# =============================================================================

def test_f1_omitted_entire_artifact():
    """Omission of artifact (None or empty dict) fails closed to MISSING[PD-F1-003]."""
    for empty in [None, {}, ""]:
        res = evaluate_f1_representation(empty)  # type: ignore
        assert res != GateState.SATISFIED
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-F1-003"
        assert str(res) == "MISSING[PD-F1-003]"


def test_f1_omitted_artifact_non_dict():
    """Non-mapping artifact (integer, list, boolean) fails closed to MISSING[PD-F1-003]."""
    for non_map in [123, True, False, ["list"], ("tuple",)]:
        res = evaluate_f1_representation(non_map)  # type: ignore
        assert res != GateState.SATISFIED
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-F1-003"


# =============================================================================
# 2. PD-F1-002: Omitted Independent Verifier Tests
# =============================================================================

def test_f1_omitted_independent_verifier_when_agent_pass():
    """Agent reports PASS but independent_verifier_result argument is omitted (None) -> MISSING[PD-F1-002]."""
    artifact = {
        "artifact_class": "interface",
        "contract": "def api(): pass",
        "positive": "p",
        "negative": "n",
        "agent_result": "PASS",
    }
    # Injected verifier omitted
    res = evaluate_f1_representation(artifact, independent_verifier_result=None)
    assert res != GateState.SATISFIED
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F1-002"
    assert str(res) == "MISSING[PD-F1-002]"


def test_f1_omitted_injected_verifier_with_payload_claim_007():
    """Payload carries claim_ref='CLAIM-007' and independent_verifier_result='PASS',
    but injected argument is omitted -> MISSING[PD-F1-002] (F-8 / R3-2 hardening)."""
    artifact = {
        "claim_ref": "CLAIM-007",
        "agent_result": "PASS",
        "independent_verifier_result": "PASS",
        "artifact_class": "interface",
        "contract": "def api(): pass",
    }
    # Injected verifier omitted
    res = evaluate_f1_representation(artifact, independent_verifier_result=None)
    assert res != GateState.SATISFIED
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F1-002"
    assert str(res) == "MISSING[PD-F1-002]"


# =============================================================================
# 3. PD-F1-003: Omitted Executable Specification / Contract Tests
# =============================================================================

def test_f1_omitted_contract_and_fallback():
    """Applicable artifact kind with contract and J fallback omitted fails closed to MISSING[PD-F1-003]."""
    for kind in ["data", "interface", "invariant", "state/concurrency", "applicable"]:
        artifact = {"artifact_class": kind}
        res = evaluate_f1_representation(artifact)
        assert res != GateState.SATISFIED
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-F1-003"
        assert str(res) == "MISSING[PD-F1-003]"


def test_f1_omitted_artifact_class():
    """Artifact omitting artifact_class fails closed to MISSING[PD-F1-003]."""
    artifact = {"contract": "def api(): pass", "positive": "p", "negative": "n"}
    res = evaluate_f1_representation(artifact)
    assert res != GateState.SATISFIED
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F1-003"


# =============================================================================
# 4. PD-F1-004: Omitted Adequacy Example Tests
# =============================================================================

def test_f1_omitted_negative_example():
    """Contract provides positive example but omits negative example -> MISSING[PD-F1-004]."""
    artifact = {
        "artifact_class": "interface",
        "contract": "def api(): pass",
        "positive": "example_input_valid",
        # negative omitted
    }
    res = evaluate_f1_representation(artifact)
    assert res != GateState.SATISFIED
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F1-004"
    assert str(res) == "MISSING[PD-F1-004]"


def test_f1_omitted_positive_example():
    """Contract provides negative example but omits positive example -> MISSING[PD-F1-004]."""
    artifact = {
        "artifact_class": "interface",
        "contract": "def api(): pass",
        # positive omitted
        "negative": "example_input_invalid",
    }
    res = evaluate_f1_representation(artifact)
    assert res != GateState.SATISFIED
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F1-004"
    assert str(res) == "MISSING[PD-F1-004]"


# =============================================================================
# 5. PD-F1-005: Omitted Procedure and Approval Tests
# =============================================================================

def test_f1_omitted_structural_diff_procedure_when_constraints_differ():
    """Confirmed and proposed constraints differ, but structural_diff_procedure is omitted -> BLOCKED_ON_HUMAN[PD-F1-005]."""
    artifact = {
        "confirmed": {"predicate": "x LESS_OR_EQUAL 10"},
        "proposed": {"predicate": "x LESS_OR_EQUAL 20"},
    }
    # structural_diff_procedure omitted
    res = evaluate_f1_representation(artifact, structural_diff_procedure=None)
    assert res != GateState.SATISFIED
    assert res.state == GateState.BLOCKED_ON_HUMAN
    assert res.must_id == "PD-F1-005"
    assert str(res) == "BLOCKED_ON_HUMAN[PD-F1-005]"


def test_f1_omitted_authoritative_approval_when_weakening():
    """Weakening detected (diff procedure returns True), but authoritative_approval is omitted -> BLOCKED_ON_HUMAN[PD-F1-005]."""
    artifact = {
        "confirmed": {"predicate": "x LESS_OR_EQUAL 10"},
        "proposed": {"predicate": "x LESS_OR_EQUAL 20"},
    }
    # diff procedure indicates weakening, but approval omitted
    res = evaluate_f1_representation(
        artifact,
        structural_diff_procedure=lambda c, p: True,
        authoritative_approval=None,
    )
    assert res != GateState.SATISFIED
    assert res.state == GateState.BLOCKED_ON_HUMAN
    assert res.must_id == "PD-F1-005"
    assert str(res) == "BLOCKED_ON_HUMAN[PD-F1-005]"


def test_f1_omitted_approval_whitespace_only():
    """Approval containing only whitespace is equivalent to omitted approval -> BLOCKED_ON_HUMAN[PD-F1-005]."""
    artifact = {
        "confirmed": {"predicate": "x LESS_OR_EQUAL 10"},
        "proposed": {"predicate": "x LESS_OR_EQUAL 20"},
    }
    for ws in ["", "   ", "\t\t", "\n"]:
        res = evaluate_f1_representation(
            artifact,
            structural_diff_procedure=lambda c, p: True,
            authoritative_approval=ws,
        )
        assert res != GateState.SATISFIED
        assert res.state == GateState.BLOCKED_ON_HUMAN
        assert res.must_id == "PD-F1-005"


# =============================================================================
# 6. Caller Authority Closed-Set Omission Tests
# =============================================================================

def test_f1_omitted_caller_authority_closed_set():
    """When non-closed-set authority is passed, evaluator rejects with MISSING[PD-F1-001]."""
    artifact = {
        "artifact_class": "code",
        "prose": "valid spec",
    }
    # Closed set valid
    res_valid = evaluate_f1_representation(artifact, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res_valid.state == GateState.SATISFIED

    # Unauthorized authority
    for unauth in ["AGENT", "CALLER", "DELEGATE", "USER"]:
        res_unauth = evaluate_f1_representation(artifact, caller_authority=unauth)
        assert res_unauth.state == GateState.MISSING
        assert res_unauth.must_id == "PD-F1-001"
