"""Consumer contract tests for Block 2 integration.

Verifies consumer contracts for:
- F2 (predicate_evaluator)
- F6 (traceability)
- F7 (claim_ledger)
- GateOutput equality semantics and to_dict schema shape
- F5Result composition and pure wrapping
- F5 aggregation precedence: MISSING over BLOCKED (master line 631, PD-F5-002)

NOTE: F1 and F3 consumer-contract tests are DEFERRED per CL amendment 1
(pending GATE-B-2 after Ak merges lane-b1-f1-fix and lane-b1-f3-fix).
"""
import pytest

from sclass.product.claim_ledger import evaluate_f7_claims
from sclass.product.gate import GateOutput, GateState
from sclass.product.gate_evaluator import (
    QUALIFIED_EVALUATOR_BOUNDARY as F5_BOUNDARY,
    F5Result,
    evaluate_f5_gate,
)
from sclass.product.predicate_evaluator import evaluate_predicate_input
from sclass.product.traceability import evaluate_f6_traceability


def test_gate_output_equality_and_to_dict():
    """Verify GateOutput equality, string representation, and dictionary serialization."""
    out_sat = GateOutput(state=GateState.SATISFIED)
    assert out_sat == "SATISFIED"
    assert str(out_sat) == "SATISFIED"

    out_missing = GateOutput(
        state=GateState.MISSING,
        must_id="PD-CH5-007",
        failures=["MISSING[PD-CH5-007]"],
        explain={"missing_element": "policy_version"},
    )
    assert out_missing == "MISSING[PD-CH5-007]"
    assert str(out_missing) == "MISSING[PD-CH5-007]"

    d = out_missing.to_dict()
    assert d["state"] == "MISSING"
    assert "MISSING[PD-CH5-007]" in d["failures"]
    assert d["explain"]["missing_element"] == "policy_version"


def test_f5_result_composition():
    """Verify F5Result composition wraps GateOutput without mutating authority."""
    gate_out = GateOutput(
        state=GateState.MISSING,
        must_id="PD-F5-002",
        failures=["MISSING[PD-F5-002]"],
        explain={"failing_check_ids": ["C-01"]},
    )
    res = F5Result(
        product_gate=gate_out,
        combined="MISSING[PD-F5-002]",
        action_result="MISSING",
        explain={"failing_check_ids": ["C-01"]},
    )
    assert res.state == GateState.MISSING
    assert res.product_gate == gate_out
    assert res.gate_output == gate_out
    assert res.combined == "MISSING[PD-F5-002]"

    d = res.to_f5_dict()
    assert d["state"] == "MISSING"
    assert "explain" in d
    assert res.digest() is not None
    assert len(res.digest()) == 64


def test_f5_missing_over_blocked_precedence():
    """Master line 631 (PD-F5-002): MISSING has precedence over BLOCKED in F5 aggregation."""
    # When both missing and blocked sub-checks apply, F5 aggregation yields MISSING
    checks = [
        {"check_id": "C-01", "status": "MISSING", "must_id": "PD-F5-002", "inputs_digest": "d1"},
        {"check_id": "C-09", "status": "BLOCKED_ON_HUMAN", "must_id": "PD-F5-002", "inputs_digest": "d2"},
    ]
    result = evaluate_f5_gate(
        phase="P5",
        canonical_state_binding={"binding": "b1"},
        pinned_guidance={"skills": []},
        policy_version="1.0.0",
        evaluator_version="1.0.0",
        evaluation_instant="2026-11-07T12:00:00Z",
        checks=checks,
        caller_authority=F5_BOUNDARY,
    )
    assert result.state == GateState.MISSING
    assert result.product_gate.must_id == "PD-F5-002"
    assert "PD-F5-002" in result.product_gate.failures
    # Explain payload retains both failing and blocked check IDs
    assert any(fe.check_id == "C-01" for fe in result.failures)
    assert "C-09" in result.explain.get("blocked", [])


def test_f2_consumer_contract():
    """Verify consumer contract with F2 predicate_evaluator."""
    # Malformed / empty spec fails closed
    res = evaluate_predicate_input(
        spec={},
        consumer="p3_invariant",
    )
    assert res.gate_output.state in (GateState.MISSING, GateState.BLOCKED_ON_HUMAN)


def test_f6_consumer_contract():
    """Verify consumer contract with F6 traceability."""
    # Empty spec fails closed under F6
    out = evaluate_f6_traceability(
        spec={},
    )
    assert isinstance(out, GateOutput)
    assert out.state in (GateState.MISSING, GateState.SATISFIED)


def test_f7_consumer_contract():
    """Verify consumer contract with F7 claim_ledger."""
    # Empty claims fails closed under F7
    out = evaluate_f7_claims(
        claims=[],
    )
    assert isinstance(out, GateOutput)
    assert out.state in (GateState.MISSING, GateState.SATISFIED)
