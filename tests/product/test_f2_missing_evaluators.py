"""Unit tests for F2 missing evaluators (F4): PD-F2-003, PD-F2-004, PD-F2-006.

Covers:
- PD-F2-003: Reference evaluator budget (SAT only on satisfying, UNSAT only on complete, INCONCLUSIVE on budget expiration)
- PD-F2-004: Predicate classification domains (TAUTOLOGY, CONTRADICTORY, EQUIVALENT, TIGHTENING, WEAKENING over declared domain)
- PD-F2-006: F2 adapter differential match and budget exhaustion
- Public gate path: evaluate_predicate_gate / evaluate_f2_gate
"""
import pytest

from sclass.product.gate import GateState
from sclass.product.predicate_evaluator import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_f2_003_reference_evaluator_budget,
    evaluate_pd_f2_004_predicate_classification_domains,
    evaluate_pd_f2_006_f2_adapter_differential_match,
    evaluate_predicate_gate,
    evaluate_f2_gate,
)


# =============================================================================
# PD-F2-003: Reference evaluator budget
# =============================================================================

def test_f2_003_valid_sat_accepted():
    valid_sat = {
        "must_id": "PD-F2-003",
        "base_result": "SAT",
        "satisfying_assignment_found": True,
        "valid_satisfying_assignment": True,
    }
    out = evaluate_pd_f2_003_reference_evaluator_budget(valid_sat, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-F2-003"


def test_f2_003_valid_unsat_accepted():
    valid_unsat = {
        "must_id": "PD-F2-003",
        "base_result": "UNSAT",
        "complete_search": True,
        "complete_bounded_evaluation": True,
    }
    out = evaluate_pd_f2_003_reference_evaluator_budget(valid_unsat, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.SATISFIED


def test_f2_003_valid_inconclusive_on_budget_expired():
    inconclusive = {
        "must_id": "PD-F2-003",
        "base_result": "INCONCLUSIVE",
        "budget_expired": True,
        "assignments_evaluated": 1000,
        "budget_limit": 1000,
    }
    out = evaluate_pd_f2_003_reference_evaluator_budget(inconclusive, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.SATISFIED


def test_f2_003_unauthorized_caller_rejected():
    valid = {"must_id": "PD-F2-003", "base_result": "SAT", "satisfying_assignment_found": True}
    assert evaluate_pd_f2_003_reference_evaluator_budget(valid, authority=None).state == GateState.MISSING
    assert evaluate_pd_f2_003_reference_evaluator_budget(valid, authority="FORGED").state == GateState.MISSING


def test_f2_003_budget_expired_returning_sat_or_unsat_rejected():
    bad_sat = {
        "must_id": "PD-F2-003",
        "base_result": "SAT",
        "budget_expired": True,  # Cannot return SAT if budget expired without finding solution!
        "assignments_evaluated": 500,
        "budget_limit": 500,
    }
    out = evaluate_pd_f2_003_reference_evaluator_budget(bad_sat, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.MISSING

    bad_unsat = {
        "must_id": "PD-F2-003",
        "base_result": "UNSAT",
        "budget_expired": True,
    }
    out = evaluate_pd_f2_003_reference_evaluator_budget(bad_unsat, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.MISSING


def test_f2_003_incomplete_search_returning_unsat_rejected():
    bad = {
        "must_id": "PD-F2-003",
        "base_result": "UNSAT",
        "complete_search": False,
        "complete_bounded_evaluation": False,
    }
    out = evaluate_pd_f2_003_reference_evaluator_budget(bad, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.MISSING


def test_f2_003_missing_evidence_rejected():
    assert evaluate_pd_f2_003_reference_evaluator_budget(None, authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING
    assert evaluate_pd_f2_003_reference_evaluator_budget({}, authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING


# =============================================================================
# PD-F2-004: Predicate classification domains
# =============================================================================

def test_f2_004_valid_classifications_accepted():
    for cl in ["TAUTOLOGY", "CONTRADICTORY", "EQUIVALENT", "TIGHTENING", "WEAKENING"]:
        valid = {
            "must_id": "PD-F2-004",
            "classification": cl,
            "domain_bounds_matched": True,
        }
        out = evaluate_pd_f2_004_predicate_classification_domains(valid, authority=QUALIFIED_EVALUATOR_BOUNDARY)
        assert out.state == GateState.SATISFIED


def test_f2_004_unauthorized_caller_rejected():
    valid = {"must_id": "PD-F2-004", "classification": "EQUIVALENT", "domain_bounds_matched": True}
    assert evaluate_pd_f2_004_predicate_classification_domains(valid, authority=None).state == GateState.MISSING


def test_f2_004_mismatched_domain_bounds_rejected():
    bad = {
        "must_id": "PD-F2-004",
        "classification": "EQUIVALENT",
        "domain_bounds_matched": False,  # Mismatched bounds
    }
    out = evaluate_pd_f2_004_predicate_classification_domains(bad, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.MISSING


def test_f2_004_unregistered_classification_rejected():
    bad = {
        "must_id": "PD-F2-004",
        "classification": "ARBITRARY_CLASS",
        "domain_bounds_matched": True,
    }
    out = evaluate_pd_f2_004_predicate_classification_domains(bad, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.MISSING


def test_f2_004_missing_evidence_rejected():
    assert evaluate_pd_f2_004_predicate_classification_domains(None, authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING


# =============================================================================
# PD-F2-006: F2 adapter differential match
# =============================================================================

def test_f2_006_matching_outputs_accepted():
    valid = {
        "must_id": "PD-F2-006",
        "adapter_outputs": ["SAT", "UNSAT", "INCONCLUSIVE"],
        "reference_outputs": ["SAT", "UNSAT", "INCONCLUSIVE"],
        "uses_applicable_f4_budget": True,
    }
    out = evaluate_pd_f2_006_f2_adapter_differential_match(valid, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.SATISFIED


def test_f2_006_unauthorized_caller_rejected():
    valid = {
        "must_id": "PD-F2-006",
        "adapter_outputs": ["SAT"],
        "reference_outputs": ["SAT"],
    }
    assert evaluate_pd_f2_006_f2_adapter_differential_match(valid, authority=None).state == GateState.MISSING


def test_f2_006_disagreeing_outputs_rejected():
    bad = {
        "must_id": "PD-F2-006",
        "adapter_outputs": ["SAT", "SAT"],
        "reference_outputs": ["SAT", "UNSAT"],  # Disagreement!
    }
    out = evaluate_pd_f2_006_f2_adapter_differential_match(bad, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.MISSING


def test_f2_006_budget_exhaustion_must_return_inconclusive():
    valid_exhausted = {
        "must_id": "PD-F2-006",
        "budget_exhausted": True,
        "adapter_budget_result": "INCONCLUSIVE",
    }
    out = evaluate_pd_f2_006_f2_adapter_differential_match(valid_exhausted, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.SATISFIED

    bad_exhausted = {
        "must_id": "PD-F2-006",
        "budget_exhausted": True,
        "adapter_budget_result": "SAT",  # Cannot return SAT on budget exhaustion!
    }
    out = evaluate_pd_f2_006_f2_adapter_differential_match(bad_exhausted, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.MISSING


# =============================================================================
# Public Gate Path: evaluate_predicate_gate / evaluate_f2_gate
# =============================================================================

def test_predicate_public_gate_path():
    all_valid = [
        {
            "must_id": "PD-F2-003",
            "base_result": "SAT",
            "satisfying_assignment_found": True,
            "valid_satisfying_assignment": True,
        },
        {
            "must_id": "PD-F2-004",
            "classification": "EQUIVALENT",
            "domain_bounds_matched": True,
        },
        {
            "must_id": "PD-F2-006",
            "adapter_outputs": ["SAT"],
            "reference_outputs": ["SAT"],
            "uses_applicable_f4_budget": True,
        },
    ]
    gate_out = evaluate_predicate_gate(all_valid, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert gate_out.state == GateState.SATISFIED

    alias_out = evaluate_f2_gate(all_valid, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert alias_out.state == GateState.SATISFIED


def test_predicate_public_gate_unauthorized_fails():
    gate_out = evaluate_predicate_gate([{"must_id": "PD-F2-003"}], authority=None)
    assert gate_out.state == GateState.MISSING


def test_predicate_public_gate_rejects_on_single_violation():
    items = [
        {
            "must_id": "PD-F2-003",
            "base_result": "SAT",
            "satisfying_assignment_found": True,
            "valid_satisfying_assignment": True,
        },
        {
            "must_id": "PD-F2-004",
            "classification": "EQUIVALENT",
            "domain_bounds_matched": False,  # Violation!
        },
    ]
    gate_out = evaluate_predicate_gate(items, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert gate_out.state == GateState.MISSING
    assert gate_out.must_id == "PD-F2-004"
