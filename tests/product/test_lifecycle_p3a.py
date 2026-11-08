"""Tests for Lifecycle P3A Architecture & Domain Modeling Invariants (PD-CH2-013..018)."""
from __future__ import annotations

import pytest

from sclass.product.gate import GateOutput, GateState
from sclass.product.lifecycle_p3a import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch2_013_requirement_coverage,
    evaluate_pd_ch2_014_domain_invariants,
    evaluate_pd_ch2_015_architecture_provenance,
    evaluate_pd_ch2_016_dependency_relationships,
    evaluate_pd_ch2_017_domain_model_substance,
    evaluate_pd_ch2_018_architecture_record_substance,
    evaluate_p3a_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


# -------------------------------------------------------------------------
# PD-CH2-013: Requirement Coverage
# -------------------------------------------------------------------------

def test_pd_ch2_013_happy():
    reqs = [{"id": "REQ-1", "semantic_coverage": True, "explicit_applicability": False}]
    res = evaluate_pd_ch2_013_requirement_coverage(reqs, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_013_gaming_fixture_ch2_t13():
    # CH2-T13: unmapped
    reqs = [{"id": "REQ-1", "semantic_coverage": False, "explicit_applicability": False}]
    res = evaluate_pd_ch2_013_requirement_coverage(reqs, authority=AUTH)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-013"
    assert str(res) == "MISSING[PD-CH2-013]"


def test_pd_ch2_013_no_authority():
    reqs = [{"id": "REQ-1", "semantic_coverage": True}]
    res = evaluate_pd_ch2_013_requirement_coverage(reqs, authority=None)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-013]"


# -------------------------------------------------------------------------
# PD-CH2-014: Domain Invariants
# -------------------------------------------------------------------------

def test_pd_ch2_014_happy():
    entities = [{"name": "Account", "invariants": ["balance >= 0"]}]
    res = evaluate_pd_ch2_014_domain_invariants(entities, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_014_gaming_fixture_ch2_t14():
    # CH2-T14: no invariant
    entities = [{"name": "Account", "invariants": []}]
    res = evaluate_pd_ch2_014_domain_invariants(entities, authority=AUTH)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-014"
    assert str(res) == "MISSING[PD-CH2-014]"


def test_pd_ch2_014_no_authority():
    entities = [{"name": "Account", "invariants": ["balance >= 0"]}]
    res = evaluate_pd_ch2_014_domain_invariants(entities, authority=None)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-014]"


# -------------------------------------------------------------------------
# PD-CH2-015: Architecture Element Provenance
# -------------------------------------------------------------------------

def test_pd_ch2_015_happy():
    elements = [{"name": "Gateway", "provenance": {"requirement_id": "REQ-1"}}]
    res = evaluate_pd_ch2_015_architecture_provenance(elements, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_015_gaming_fixture_ch2_t15():
    # CH2-T15: provenance absent
    elements = [{"name": "Gateway", "provenance": None}]
    res = evaluate_pd_ch2_015_architecture_provenance(elements, authority=AUTH)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-015"
    assert str(res) == "MISSING[PD-CH2-015]"


def test_pd_ch2_015_empty_provenance():
    elements = [{"name": "Gateway", "provenance": {}}]
    res = evaluate_pd_ch2_015_architecture_provenance(elements, authority=AUTH)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-015]"


def test_pd_ch2_015_no_authority():
    elements = [{"name": "Gateway", "provenance": {"requirement_id": "REQ-1"}}]
    res = evaluate_pd_ch2_015_architecture_provenance(elements, authority=None)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-015]"


# -------------------------------------------------------------------------
# PD-CH2-016: Material Dependency Relationships
# -------------------------------------------------------------------------

def test_pd_ch2_016_happy():
    material = [{"source": "ServiceA", "destination": "Database"}]
    represented = [("ServiceA", "Database")]
    res = evaluate_pd_ch2_016_dependency_relationships(material, represented, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_016_gaming_fixture_ch2_t16():
    # CH2-T16: edge absent
    material = [{"source": "ServiceA", "destination": "Database"}]
    represented = [("ServiceA", "OtherService")]
    res = evaluate_pd_ch2_016_dependency_relationships(material, represented, authority=AUTH)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-016"
    assert str(res) == "MISSING[PD-CH2-016]"


def test_pd_ch2_016_no_authority():
    material = [{"source": "ServiceA", "destination": "Database"}]
    represented = [("ServiceA", "Database")]
    res = evaluate_pd_ch2_016_dependency_relationships(material, represented, authority=None)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-016]"


# -------------------------------------------------------------------------
# PD-CH2-017: DomainModel Measurable Substance
# -------------------------------------------------------------------------

def test_pd_ch2_017_happy():
    model = {"entities": [{"name": "User", "fields": ["id: UUID", "email: str"], "constraints": ["email != empty"]}]}
    res = evaluate_pd_ch2_017_domain_model_substance(model, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_017_gaming_fixture_ch2_t17():
    # CH2-T17: names only
    model = {"entities": [{"name": "User", "fields": [], "constraints": []}]}
    res = evaluate_pd_ch2_017_domain_model_substance(model, authority=AUTH)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-017"
    assert str(res) == "MISSING[PD-CH2-017]"


def test_pd_ch2_017_no_authority():
    model = {"entities": [{"name": "User", "fields": ["id: UUID"]}]}
    res = evaluate_pd_ch2_017_domain_model_substance(model, authority=None)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-017]"


# -------------------------------------------------------------------------
# PD-CH2-018: ArchitectureRecord Measurable Substance
# -------------------------------------------------------------------------

def test_pd_ch2_018_happy():
    record = {
        "components": ["API", "Worker"],
        "boundaries": ["TrustBoundary_VPC"],
        "contracts": ["ProtobufV1"],
    }
    res = evaluate_pd_ch2_018_architecture_record_substance(record, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_018_gaming_fixture_ch2_t18():
    # CH2-T18: components only
    record = {
        "components": ["API", "Worker"],
        "interactions": [],
        "boundaries": [],
        "contracts": [],
    }
    res = evaluate_pd_ch2_018_architecture_record_substance(record, authority=AUTH)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-018"
    assert str(res) == "MISSING[PD-CH2-018]"


def test_pd_ch2_018_no_authority():
    record = {"components": ["API"], "boundaries": ["VPC"]}
    res = evaluate_pd_ch2_018_architecture_record_substance(record, authority=None)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-018]"


# -------------------------------------------------------------------------
# Composite Gate Evaluator
# -------------------------------------------------------------------------

def test_p3a_composite_gate_happy():
    manifest = {
        "requirements": [{"id": "R1", "semantic_coverage": True}],
        "domain_entities": [{"name": "Account", "invariants": ["x > 0"]}],
        "architecture_elements": [{"name": "Svc", "provenance": {"requirement_id": "R1"}}],
        "material_dependencies": [{"source": "A", "destination": "B"}],
        "represented_edges": [("A", "B")],
        "domain_model": {"entities": [{"name": "E", "fields": ["f1: str"]}]},
        "architecture_record": {"components": ["C1"], "contracts": ["K1"]},
    }
    res = evaluate_p3a_gate(manifest, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_p3a_composite_gate_fail_closed_no_authority():
    manifest = {}
    res = evaluate_p3a_gate(manifest, authority=None)
    assert res.state == GateState.MISSING
    assert len(res.failures) == 6
