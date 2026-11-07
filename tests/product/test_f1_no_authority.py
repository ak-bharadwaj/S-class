"""Permanent regression tests for F1 authority model hardening (Task 2 / F1-FIX).

Verifies that authority for independent verification (PD-F1-002) and weakening approval /
structural diff procedures (PD-F1-005) derives strictly from caller-injected keyword arguments,
never from untrusted specification payloads or candidate self-assertions.
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
# 1. Six Required Permanent Probes (Probes A through F)
# =============================================================================

def test_probe_a_empty_artifact_fails_closed():
    """Probe A: Empty artifact with no injected arguments must fail closed to MISSING."""
    empty_artifact: Dict[str, Any] = {}
    result = evaluate_f1_representation(empty_artifact)
    assert result != GateState.SATISFIED
    assert result.state == GateState.MISSING
    assert str(result).startswith("MISSING")
    assert result.must_id == "PD-F1-003"


def test_probe_b_agent_pass_without_verifier_fails_closed():
    """Probe B: Agent self-report PASS without independent verifier fails closed to MISSING[PD-F1-002]."""
    spec_agent_pass = {
        "agent_result": "PASS",
        "claim_ref": "PROBE-B-CLAIM",
    }
    result = evaluate_f1_representation(spec_agent_pass)
    assert result != GateState.SATISFIED
    assert result == "MISSING[PD-F1-002]"
    assert result.state == GateState.MISSING
    assert result.must_id == "PD-F1-002"


def test_probe_c_agent_pass_plus_payload_verifier_pass_fails_closed():
    """Probe C: Agent self-report PASS with payload verifier PASS fails closed to MISSING[PD-F1-002].
    
    Payload independent_verifier_result cannot grant authority.
    """
    spec_payload_verifier = {
        "agent_result": "PASS",
        "independent_verifier_result": "PASS",
        "claim_ref": "PROBE-C-ATTACK",
    }
    result = evaluate_f1_representation(spec_payload_verifier)
    assert result != GateState.SATISFIED
    assert result == "MISSING[PD-F1-002]"
    assert result.state == GateState.MISSING
    assert result.must_id == "PD-F1-002"


def test_probe_d_weakening_plus_payload_procedure_and_approval_fails_closed():
    """Probe D: Weakening 10->20 with payload procedure and approval fails closed to BLOCKED_ON_HUMAN[PD-F1-005].
    
    Payload procedure and approval cannot grant authority.
    """
    spec_weakening_payload_auth = {
        "confirmed": {"predicate": "x LESS_OR_EQUAL 10"},
        "proposed": {"predicate": "x LESS_OR_EQUAL 20"},
        "structural_diff_procedure": "numeric_range_diff",
        "authoritative_approval": "DECISION-42",
    }
    result = evaluate_f1_representation(spec_weakening_payload_auth)
    assert result != GateState.SATISFIED
    assert result == "BLOCKED_ON_HUMAN[PD-F1-005]"
    assert result.state == GateState.BLOCKED_ON_HUMAN
    assert result.must_id == "PD-F1-005"


def test_probe_e_constraint_removed_no_injected_approval_fails_closed():
    """Probe E: Constraint removed plus payload procedure without injected approval fails closed to BLOCKED_ON_HUMAN[PD-F1-005]."""
    spec_removed = {
        "confirmed": {"predicate": "x LESS_OR_EQUAL 10"},
        "proposed": None,
        "structural_diff_procedure": lambda c, p: True,
    }
    result = evaluate_f1_representation(spec_removed)
    assert result != GateState.SATISFIED
    assert result == "BLOCKED_ON_HUMAN[PD-F1-005]"
    assert result.state == GateState.BLOCKED_ON_HUMAN
    assert result.must_id == "PD-F1-005"


def test_probe_f_changed_constraint_no_procedure_payload_approval_fails_closed():
    """Probe F: Changed constraint without injected procedure, payload approval fails closed to BLOCKED_ON_HUMAN[PD-F1-005]."""
    spec_changed = {
        "confirmed": {"predicate": "x LESS_OR_EQUAL 10"},
        "proposed": {"predicate": "x LESS_OR_EQUAL 20"},
        "authoritative_approval": "DECISION-42",
    }
    result = evaluate_f1_representation(spec_changed)
    assert result != GateState.SATISFIED
    assert result == "BLOCKED_ON_HUMAN[PD-F1-005]"
    assert result.state == GateState.BLOCKED_ON_HUMAN
    assert result.must_id == "PD-F1-005"


# =============================================================================
# 2. Additional Permanent Tests
# =============================================================================

def test_approval_whitespace_only_rejected():
    """Approval containing only whitespace is rejected and blocked on human."""
    spec = {
        "proposed": {"predicate": "x LESS_OR_EQUAL 20"},
    }
    result = evaluate_f1_representation(
        spec,
        confirmed_artifact={"predicate": "x LESS_OR_EQUAL 10"},
        structural_diff_procedure=lambda c, p: True,
        authoritative_approval="   \t\n  ",
    )
    assert result == "BLOCKED_ON_HUMAN[PD-F1-005]"
    assert result.state == GateState.BLOCKED_ON_HUMAN
    assert result.must_id == "PD-F1-005"


def test_procedure_raising_exception_fails_closed():
    """Structural diff procedure raising an exception fails closed to BLOCKED_ON_HUMAN[PD-F1-005]."""
    def raising_proc(c: Any, p: Any) -> Any:
        raise RuntimeError("Structural diff engine internal failure")

    spec = {
        "proposed": {"predicate": "status_beta"},
    }
    result = evaluate_f1_representation(
        spec,
        confirmed_artifact={"predicate": "status_alpha"},
        structural_diff_procedure=raising_proc,
        authoritative_approval="DECISION-42",
    )
    assert result == "BLOCKED_ON_HUMAN[PD-F1-005]"
    assert result.state == GateState.BLOCKED_ON_HUMAN
    assert result.must_id == "PD-F1-005"


def test_procedure_returning_truthy_non_true_fails_closed():
    """Structural diff procedure returning truthy non-True values (1, 'True', dict) fails closed."""
    for truthy_val in [1, "True", {"weakening": True}, [True]]:
        result = evaluate_f1_representation(
            {"proposed": {"predicate": "x LESS_OR_EQUAL 20"}},
            confirmed_artifact={"predicate": "x LESS_OR_EQUAL 10"},
            structural_diff_procedure=lambda c, p: truthy_val,
            authoritative_approval="DECISION-42",
        )
        assert result == "BLOCKED_ON_HUMAN[PD-F1-005]", f"Expected BLOCKED_ON_HUMAN for {truthy_val!r}"
        assert result.state == GateState.BLOCKED_ON_HUMAN
        assert result.must_id == "PD-F1-005"


def test_procedure_returning_falsy_non_false_fails_closed():
    """Structural diff procedure returning falsy non-False values (0, '', None, []) fails closed."""
    for falsy_val in [0, "", None, []]:
        result = evaluate_f1_representation(
            {"proposed": {"predicate": "status_beta"}},
            confirmed_artifact={"predicate": "status_alpha"},
            structural_diff_procedure=lambda c, p: falsy_val,
        )
        assert result == "BLOCKED_ON_HUMAN[PD-F1-005]", f"Expected BLOCKED_ON_HUMAN for {falsy_val!r}"
        assert result.state == GateState.BLOCKED_ON_HUMAN


def test_agent_authored_approval_rejected():
    """Agent-authored claim attempting to supply its own approval fails closed."""
    spec_agent_claim = {
        "proposed": {"predicate": "x LESS_OR_EQUAL 20"},
        "confirmed": {"predicate": "x LESS_OR_EQUAL 10"},
        "authoritative_approval": "AGENT-SELF-APPROVED-001",
        "agent_authored": True,
        "agent_claim_of_completion": True,
    }
    result = evaluate_f1_representation(spec_agent_claim)
    assert result == "BLOCKED_ON_HUMAN[PD-F1-005]"
    assert result.state == GateState.BLOCKED_ON_HUMAN


def test_injected_authority_valid_produces_satisfied():
    """Valid injected authority dependencies satisfy evaluation."""
    # 1. Independent verifier PASS satisfies PD-F1-002
    res_verifier = evaluate_f1_representation(
        {"agent_result": "PASS"},
        independent_verifier_result="PASS",
    )
    assert res_verifier == GateState.SATISFIED
    assert res_verifier.state == GateState.SATISFIED

    # 2. Structural diff exact False (not weakening) satisfies PD-F1-005
    res_not_weakening = evaluate_f1_representation(
        {"proposed": {"predicate": "x LESS_OR_EQUAL 10"}},
        confirmed_artifact={"predicate": "x LESS_OR_EQUAL 10"},
        structural_diff_procedure=lambda c, p: False,
    )
    assert res_not_weakening == GateState.SATISFIED
    assert res_not_weakening.state == GateState.SATISFIED

    # 3. Structural diff exact True (weakening) with injected non-empty approval satisfies PD-F1-005
    res_weakening_approved = evaluate_f1_representation(
        {"proposed": {"predicate": "x LESS_OR_EQUAL 20"}},
        confirmed_artifact={"predicate": "x LESS_OR_EQUAL 10"},
        structural_diff_procedure=lambda c, p: True,
        authoritative_approval="DECISION-AUDIT-2026-11-07",
    )
    assert res_weakening_approved == GateState.SATISFIED
    assert res_weakening_approved.state == GateState.SATISFIED


def test_payload_verifier_fail_makes_result_stricter():
    """Per Rule 1, payload facts may make result stricter, never more permissive.
    
    If payload contains verifier FAIL, even if injected is PASS, it fails closed.
    """
    spec_payload_fail = {
        "agent_result": "PASS",
        "independent_verifier_result": "FAIL",
    }
    result = evaluate_f1_representation(
        spec_payload_fail,
        independent_verifier_result="PASS",
    )
    assert result == "MISSING[PD-F1-002]"
    assert result.state == GateState.MISSING


def test_absent_or_unknown_artifact_class_fails_closed():
    """PD-F1-003: absent or unknown artifact_class fails closed to MISSING[PD-F1-003].
    
    'applicable' is a real class requiring executable representation, not an exemption.
    """
    # Unknown class
    res_unknown = evaluate_f1_representation({
        "artifact": {
            "artifact_class": "unknown_unregistered_kind",
        }
    })
    assert res_unknown == "MISSING[PD-F1-003]"
    assert res_unknown.state == GateState.MISSING
    assert res_unknown.must_id == "PD-F1-003"

    # 'applicable' class without executable spec
    res_applicable_missing = evaluate_f1_representation({
        "artifact": {
            "artifact_class": "applicable",
            "prose": "Applicable artifact kind without contract",
        }
    })
    assert res_applicable_missing == "MISSING[PD-F1-003]"
    assert res_applicable_missing.state == GateState.MISSING
    assert res_applicable_missing.must_id == "PD-F1-003"

    # 'applicable' class with valid executable contract
    res_applicable_satisfied = evaluate_f1_representation({
        "artifact": {
            "artifact_class": "applicable",
            "contract": {"method": "GET", "path": "/api/v1/health"},
        }
    })
    assert res_applicable_satisfied == GateState.SATISFIED
    assert res_applicable_satisfied.state == GateState.SATISFIED


def test_caller_authority_closed_set_enforcement():
    """Enforces closed set {QUALIFIED_EVALUATOR_BOUNDARY} for caller_authority."""
    # Identity / equality with QUALIFIED_EVALUATOR_BOUNDARY succeeds
    res_valid = evaluate_f1_representation(
        {"artifact": {"artifact_class": "code", "prose": "Trusted eval"}},
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert res_valid == GateState.SATISFIED

    # Unrecognized authority fails closed
    for bad_auth in ["AGENT", "UNTRUSTED", "CALLER", "DELEGATE", ""]:
        res_bad = evaluate_f1_representation(
            {"artifact": {"artifact_class": "code", "prose": "Untrusted eval"}},
            caller_authority=bad_auth,
        )
        assert res_bad == "MISSING[PD-F1-001]", f"Expected MISSING for authority '{bad_auth}'"
        assert res_bad.state == GateState.MISSING
        assert res_bad.must_id == "PD-F1-001"
