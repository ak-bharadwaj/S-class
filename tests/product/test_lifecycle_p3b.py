"""Tests for Lifecycle P3B Architecture & Constraint Invariants (PD-CH2-020..025)."""
from __future__ import annotations

import pytest

from sclass.product.gate import GateOutput, GateState
from sclass.product.lifecycle_p3b import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    DECIDABLE_FRAGMENTS,
    evaluate_pd_ch2_020_decidable_invariants,
    evaluate_pd_ch2_021_cross_entity_constraints,
    evaluate_pd_ch2_022_change_surface_boundary_closure,
    evaluate_pd_ch2_023_boundary_data_flow_contracts,
    evaluate_pd_ch2_024_interface_signatures_typed_contracts,
    evaluate_pd_ch2_025_unknown_contradiction_handling,
    evaluate_p3b_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


# -------------------------------------------------------------------------
# PD-CH2-020: Decidable Invariants
# -------------------------------------------------------------------------

def test_pd_ch2_020_happy():
    invs = [{"name": "BalanceEq", "fragment": "EQUATIONAL_EQUALITY", "supported": True, "claimed_pass": True}]
    res = evaluate_pd_ch2_020_decidable_invariants(invs, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_020_gaming_fixture_ch2_t20():
    # CH2-T20: unsupported PASS
    invs = [{"name": "HaltingProblemInv", "fragment": "UNDECIDABLE_FOL", "supported": False, "claimed_pass": True}]
    res = evaluate_pd_ch2_020_decidable_invariants(invs, authority=AUTH)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-020"
    assert str(res) == "MISSING[PD-CH2-020]"


def test_pd_ch2_020_no_authority():
    invs = [{"name": "BalanceEq", "fragment": "EQUATIONAL_EQUALITY", "supported": True}]
    res = evaluate_pd_ch2_020_decidable_invariants(invs, authority=None)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-020]"


# -------------------------------------------------------------------------
# PD-CH2-021: Cross-Entity Constraints
# -------------------------------------------------------------------------

def test_pd_ch2_021_happy():
    constraints = [{"id": "C-1", "relationship": "ONE_TO_MANY", "cardinality": "1..*"}]
    res = evaluate_pd_ch2_021_cross_entity_constraints(constraints, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_021_gaming_fixture_ch2_t21():
    # CH2-T21: no relation
    constraints = [{"id": "C-1", "relationship": None, "cardinality": "1..*"}]
    res = evaluate_pd_ch2_021_cross_entity_constraints(constraints, authority=AUTH)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-021"
    assert str(res) == "MISSING[PD-CH2-021]"


def test_pd_ch2_021_no_authority():
    constraints = [{"id": "C-1", "relationship": "ONE_TO_ONE", "cardinality": "1"}]
    res = evaluate_pd_ch2_021_cross_entity_constraints(constraints, authority=None)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-021]"


# -------------------------------------------------------------------------
# PD-CH2-022: Change Surface Boundary Closure
# -------------------------------------------------------------------------

def test_pd_ch2_022_happy():
    boundaries = ["ServiceA", "Database"]
    edges = [("ServiceA", "Database")]
    res = evaluate_pd_ch2_022_change_surface_boundary_closure(boundaries, edges, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_022_gaming_fixture_ch2_t22():
    # CH2-T22: edge absent
    boundaries = ["ServiceA", "Database", "UncoveredBoundary"]
    edges = [("ServiceA", "Database")]
    res = evaluate_pd_ch2_022_change_surface_boundary_closure(boundaries, edges, authority=AUTH)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-022"
    assert str(res) == "MISSING[PD-CH2-022]"


def test_pd_ch2_022_no_authority():
    boundaries = ["ServiceA"]
    edges = [("ServiceA", "ServiceB")]
    res = evaluate_pd_ch2_022_change_surface_boundary_closure(boundaries, edges, authority=None)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-022]"


# -------------------------------------------------------------------------
# PD-CH2-023: Boundary-Crossing Data Flow Contracts
# -------------------------------------------------------------------------

def test_pd_ch2_023_happy():
    flows = [{
        "id": "F-1", "source": "API", "destination": "Queue",
        "contract": "AvroOrderPayload", "transformation": "SerializeToAvro"
    }]
    res = evaluate_pd_ch2_023_boundary_data_flow_contracts(flows, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_023_gaming_fixture_ch2_t23():
    # CH2-T23: no transform
    flows = [{
        "id": "F-1", "source": "API", "destination": "Queue",
        "contract": "AvroOrderPayload", "transformation": None
    }]
    res = evaluate_pd_ch2_023_boundary_data_flow_contracts(flows, authority=AUTH)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-023"
    assert str(res) == "MISSING[PD-CH2-023]"


def test_pd_ch2_023_no_authority():
    flows = [{"id": "F-1", "source": "A", "destination": "B", "contract": "C", "transformation": "T"}]
    res = evaluate_pd_ch2_023_boundary_data_flow_contracts(flows, authority=None)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-023]"


# -------------------------------------------------------------------------
# PD-CH2-024: Interface Signatures Agree with Typed Contracts
# -------------------------------------------------------------------------

def test_pd_ch2_024_happy():
    ifaces = [{
        "name": "GetUser", "signature_type": "UserResponseDTO",
        "domain_contract_type": "UserResponseDTO", "requirement_predicate_type": "UserResponseDTO"
    }]
    res = evaluate_pd_ch2_024_interface_signatures_typed_contracts(ifaces, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_024_gaming_fixture_ch2_t24():
    # CH2-T24: mismatch
    ifaces = [{
        "name": "GetUser", "signature_type": "Dict[str, Any]",
        "domain_contract_type": "UserResponseDTO", "requirement_predicate_type": "UserResponseDTO"
    }]
    res = evaluate_pd_ch2_024_interface_signatures_typed_contracts(ifaces, authority=AUTH)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-024"
    assert str(res) == "MISSING[PD-CH2-024]"


def test_pd_ch2_024_no_authority():
    ifaces = [{"name": "GetUser", "signature_type": "DTO", "domain_contract_type": "DTO"}]
    res = evaluate_pd_ch2_024_interface_signatures_typed_contracts(ifaces, authority=None)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-024]"


# -------------------------------------------------------------------------
# PD-CH2-025: Unknown / Undecidable Contradiction Handling
# -------------------------------------------------------------------------

def test_pd_ch2_025_happy():
    res = evaluate_pd_ch2_025_unknown_contradiction_handling(has_unknown_contradiction=False, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_025_gaming_fixture_ch2_t25():
    # CH2-T25: unknown result
    res = evaluate_pd_ch2_025_unknown_contradiction_handling(has_unknown_contradiction=True, authority=AUTH)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-025"
    assert str(res) == "MISSING[PD-CH2-025]"


def test_pd_ch2_025_human_waiver_fails():
    res = evaluate_pd_ch2_025_unknown_contradiction_handling(
        has_unknown_contradiction=True,
        human_waiver_attempted=True,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-025]"


def test_pd_ch2_025_no_authority():
    res = evaluate_pd_ch2_025_unknown_contradiction_handling(has_unknown_contradiction=False, authority=None)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-025]"


# -------------------------------------------------------------------------
# Composite Gate Evaluator
# -------------------------------------------------------------------------

def test_p3b_composite_gate_happy():
    manifest = {
        "invariants": [{"name": "I1", "fragment": "EQUATIONAL_EQUALITY", "supported": True}],
        "constraints": [{"id": "C1", "relationship": "R", "cardinality": "1"}],
        "change_surface_boundaries": ["B1"],
        "dependency_edges": [("B1", "B2")],
        "data_flows": [{"id": "F1", "source": "S", "destination": "D", "contract": "K", "transformation": "T"}],
        "interfaces": [{"name": "If1", "signature_type": "T1", "domain_contract_type": "T1"}],
        "has_unknown_contradiction": False,
    }
    res = evaluate_p3b_gate(manifest, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_p3b_composite_gate_fail_closed_no_authority():
    manifest = {}
    res = evaluate_p3b_gate(manifest, authority=None)
    assert res.state == GateState.MISSING
    assert len(res.failures) == 6
