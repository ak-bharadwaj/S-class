"""Unit tests for Chapter 1 Architecture Governance & Subordination Evaluators (F4).

Covers:
- PD-CH1-001: Control-plane thesis
- PD-CH1-002: Subordination to frozen v6.0.1 package
- PD-CH1-004: Concept classification & kernel type exclusion
- PD-CH1-005: Artifact authority class declaration
- PD-CH1-006: Namespace authority isolation
- PD-CH1-007: v1 authority floor preservation
- Public gate path: evaluate_architecture_governance_gate / evaluate_ch1_gate
"""
import pytest

from sclass.product.gate import GateState
from sclass.product.architecture_governance import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch1_001_control_plane_thesis,
    evaluate_pd_ch1_002_frozen_package_subordination,
    evaluate_pd_ch1_004_concept_classification,
    evaluate_pd_ch1_005_authority_class_declaration,
    evaluate_pd_ch1_006_namespace_authority_isolation,
    evaluate_pd_ch1_007_v1_authority_floor_preservation,
    evaluate_architecture_governance_gate,
    evaluate_ch1_gate,
)


# =============================================================================
# PD-CH1-001: Control-plane thesis
# =============================================================================

def test_ch1_001_valid_evidence_accepted():
    valid = {
        "must_id": "PD-CH1-001",
        "component_role": "control_plane",
        "responsibilities": ["engineering_gates", "authorization", "evidence_admissibility"],
    }
    out = evaluate_pd_ch1_001_control_plane_thesis(valid, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH1-001"


def test_ch1_001_unauthorized_caller_rejected():
    valid = {"must_id": "PD-CH1-001", "component_role": "control_plane"}
    out = evaluate_pd_ch1_001_control_plane_thesis(valid, authority="UNAUTHORIZED")
    assert out.state == GateState.MISSING
    out_none = evaluate_pd_ch1_001_control_plane_thesis(valid, authority=None)
    assert out_none.state == GateState.MISSING


def test_ch1_001_forbidden_roles_rejected():
    for forbidden in ["ide", "model", "agent_loop", "workflow_engine", "replacement_parser"]:
        bad = {"must_id": "PD-CH1-001", "component_role": forbidden}
        out = evaluate_pd_ch1_001_control_plane_thesis(bad, authority=QUALIFIED_EVALUATOR_BOUNDARY)
        assert out.state == GateState.MISSING, f"Role {forbidden} should be rejected"


def test_ch1_001_forbidden_ide_semantics_rejected():
    bad = {"must_id": "PD-CH1-001", "owns_ide_semantics": True}
    out = evaluate_pd_ch1_001_control_plane_thesis(bad, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.MISSING


def test_ch1_001_missing_evidence_rejected():
    assert evaluate_pd_ch1_001_control_plane_thesis(None, authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING
    assert evaluate_pd_ch1_001_control_plane_thesis({}, authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING


def test_ch1_001_invalid_input_safe():
    assert evaluate_pd_ch1_001_control_plane_thesis("bad-input", authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING


# =============================================================================
# PD-CH1-002: Subordination to frozen v6.0.1 package
# =============================================================================

def test_ch1_002_valid_evidence_accepted():
    valid = {
        "must_id": "PD-CH1-002",
        "subordinate_to_frozen_package": True,
        "conflicts_with_kernel": False,
        "overrides_kernel_predicate": False,
    }
    out = evaluate_pd_ch1_002_frozen_package_subordination(valid, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.SATISFIED


def test_ch1_002_unauthorized_caller_rejected():
    valid = {"must_id": "PD-CH1-002", "subordinate_to_frozen_package": True}
    assert evaluate_pd_ch1_002_frozen_package_subordination(valid, authority=None).state == GateState.MISSING


def test_ch1_002_contradictory_kernel_predicate_rejected():
    conflicting = {
        "must_id": "PD-CH1-002",
        "subordinate_to_frozen_package": True,
        "conflicts_with_kernel": True,  # Overrides/conflicts!
    }
    out = evaluate_pd_ch1_002_frozen_package_subordination(conflicting, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.MISSING


def test_ch1_002_missing_subordination_rejected():
    missing = {"must_id": "PD-CH1-002"}
    assert evaluate_pd_ch1_002_frozen_package_subordination(missing, authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING


# =============================================================================
# PD-CH1-004: Concept classification & kernel type exclusion
# =============================================================================

def test_ch1_004_valid_evidence_accepted():
    valid = {
        "must_id": "PD-CH1-004",
        "concept_name": "WorkType",
        "classifications": ["PROCESS_ARTIFACT"],
        "presented_as_kernel_type": False,
    }
    out = evaluate_pd_ch1_004_concept_classification(valid, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.SATISFIED


def test_ch1_004_unauthorized_caller_rejected():
    valid = {"must_id": "PD-CH1-004", "concept_name": "WorkType", "classifications": ["PROCESS_ARTIFACT"]}
    assert evaluate_pd_ch1_004_concept_classification(valid, authority=None).state == GateState.MISSING


def test_ch1_004_presented_as_kernel_type_rejected():
    bad = {
        "must_id": "PD-CH1-004",
        "concept_name": "Playbook",
        "classifications": ["GUIDANCE"],
        "presented_as_kernel_type": True,  # Forbidden presentation as kernel type
    }
    out = evaluate_pd_ch1_004_concept_classification(bad, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.MISSING


def test_ch1_004_multiple_classifications_rejected():
    bad = {
        "must_id": "PD-CH1-004",
        "concept_name": "MultiConcept",
        "classifications": ["PROCESS_ARTIFACT", "GUIDANCE"],  # Must belong to exactly one
    }
    out = evaluate_pd_ch1_004_concept_classification(bad, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.MISSING


def test_ch1_004_unregistered_classification_rejected():
    bad = {
        "must_id": "PD-CH1-004",
        "concept_name": "Custom",
        "classifications": ["UNKNOWN_CLASS"],
    }
    out = evaluate_pd_ch1_004_concept_classification(bad, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.MISSING


# =============================================================================
# PD-CH1-005: Artifact authority class declaration
# =============================================================================

def test_ch1_005_valid_evidence_accepted():
    for auth_class in ["PROCESS_ARTIFACT", "DOCUMENTATION", "PROJECTION", "GUIDANCE", "IMPLEMENTATION_METADATA"]:
        valid = {"must_id": "PD-CH1-005", "authority_class": auth_class}
        out = evaluate_pd_ch1_005_authority_class_declaration(valid, authority=QUALIFIED_EVALUATOR_BOUNDARY)
        assert out.state == GateState.SATISFIED


def test_ch1_005_unauthorized_caller_rejected():
    valid = {"must_id": "PD-CH1-005", "authority_class": "GUIDANCE"}
    assert evaluate_pd_ch1_005_authority_class_declaration(valid, authority=None).state == GateState.MISSING


def test_ch1_005_omitted_authority_class_rejected():
    bad = {"must_id": "PD-CH1-005"}
    assert evaluate_pd_ch1_005_authority_class_declaration(bad, authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING


def test_ch1_005_unregistered_authority_class_rejected():
    bad = {"must_id": "PD-CH1-005", "authority_class": "KERNEL_AUTHORITY"}
    assert evaluate_pd_ch1_005_authority_class_declaration(bad, authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING


def test_ch1_005_self_asserted_trust_verdict_rejected():
    bad = {"must_id": "PD-CH1-005", "authority_class": "GUIDANCE", "self_asserted_trust": True}
    assert evaluate_pd_ch1_005_authority_class_declaration(bad, authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING


# =============================================================================
# PD-CH1-006: Namespace authority isolation
# =============================================================================

def test_ch1_006_valid_evidence_accepted():
    valid = {
        "must_id": "PD-CH1-006",
        "source_namespace": "sclass.product",
        "target_namespace": "sclass.product",
        "defines_cross_namespace_authority": False,
        "isolation_enforced": True,
    }
    out = evaluate_pd_ch1_006_namespace_authority_isolation(valid, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.SATISFIED


def test_ch1_006_unauthorized_caller_rejected():
    valid = {"must_id": "PD-CH1-006", "isolation_enforced": True}
    assert evaluate_pd_ch1_006_namespace_authority_isolation(valid, authority=None).state == GateState.MISSING


def test_ch1_006_cross_namespace_authority_rejected():
    bad = {
        "must_id": "PD-CH1-006",
        "source_namespace": "sclass.product",
        "target_namespace": "sclass_semantics_v6_0_1",
        "defines_cross_namespace_authority": True,
    }
    out = evaluate_pd_ch1_006_namespace_authority_isolation(bad, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.MISSING


# =============================================================================
# PD-CH1-007: v1 authority floor preservation
# =============================================================================

def test_ch1_007_valid_evidence_accepted():
    valid = {
        "must_id": "PD-CH1-007",
        "work_type": "FEATURE",
        "domain": "Backend",
        "mandatory_controls_preserved": True,
        "removes_mandatory_control": False,
    }
    out = evaluate_pd_ch1_007_v1_authority_floor_preservation(valid, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.SATISFIED


def test_ch1_007_unauthorized_caller_rejected():
    valid = {"must_id": "PD-CH1-007", "mandatory_controls_preserved": True}
    assert evaluate_pd_ch1_007_v1_authority_floor_preservation(valid, authority=None).state == GateState.MISSING


def test_ch1_007_relaxed_security_or_evidence_floor_rejected():
    bad = {
        "must_id": "PD-CH1-007",
        "work_type": "FEATURE",
        "mandatory_controls_preserved": True,
        "lowers_security_floor": True,
    }
    out = evaluate_pd_ch1_007_v1_authority_floor_preservation(bad, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.MISSING


def test_ch1_007_unsupported_work_type_rejected():
    bad = {
        "must_id": "PD-CH1-007",
        "work_type": "REFACTOR_MASSIVE",
        "mandatory_controls_preserved": True,
    }
    assert evaluate_pd_ch1_007_v1_authority_floor_preservation(bad, authority=QUALIFIED_EVALUATOR_BOUNDARY).state == GateState.MISSING


# =============================================================================
# Public Gate Path: evaluate_architecture_governance_gate
# =============================================================================

def test_architecture_governance_public_gate_path():
    all_valid = [
        {"must_id": "PD-CH1-001", "component_role": "control_plane"},
        {"must_id": "PD-CH1-002", "subordinate_to_frozen_package": True},
        {"must_id": "PD-CH1-004", "concept_name": "WorkType", "classifications": ["PROCESS_ARTIFACT"]},
        {"must_id": "PD-CH1-005", "authority_class": "PROCESS_ARTIFACT"},
        {"must_id": "PD-CH1-006", "isolation_enforced": True},
        {"must_id": "PD-CH1-007", "mandatory_controls_preserved": True},
    ]
    gate_out = evaluate_architecture_governance_gate(all_valid, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert gate_out.state == GateState.SATISFIED

    # Alias check
    alias_out = evaluate_ch1_gate(all_valid, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert alias_out.state == GateState.SATISFIED


def test_architecture_governance_public_gate_unauthorized_fails():
    gate_out = evaluate_architecture_governance_gate([{"must_id": "PD-CH1-001"}], authority=None)
    assert gate_out.state == GateState.MISSING


def test_architecture_governance_public_gate_rejects_on_single_violation():
    items = [
        {"must_id": "PD-CH1-001", "component_role": "control_plane"},
        {"must_id": "PD-CH1-002", "subordinate_to_frozen_package": False},  # Violation!
    ]
    gate_out = evaluate_architecture_governance_gate(items, authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert gate_out.state == GateState.MISSING
    assert gate_out.must_id == "PD-CH1-002"
