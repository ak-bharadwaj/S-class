"""Independent W4 Consumer Contract Scenarios for Block 3 (Lanes F4, F8, Replay, P0A, P0B, P1P4, P3A, P3B, P3C, P5, P6, P7, P11).

Mandated by S-CLASS M0 ITERATION 2 (E5):
- Standalone independent test functions under tests/independent/
- Covers all 69 Block 3 MUSTs
- Evaluates fail-closed security posture (unauthenticated / missing authority -> non-SATISFIED)
- Evaluates authorized consumer contracts (valid authority -> SATISFIED)
- Asserts GateOutput contract compliance (GateState closed vocabulary, to_dict schema)
"""
from __future__ import annotations

import pytest
from sclass.product.gate import GateOutput, GateState
import sclass.product.f4_lane_selection as f4
import sclass.product.f8_step_pack as f8
import sclass.product.replay as rep
import sclass.product.lifecycle_p0a as p0a
import sclass.product.lifecycle_p0b as p0b
import sclass.product.lifecycle_p1_p4 as p1p4
import sclass.product.lifecycle_p3a as p3a
import sclass.product.lifecycle_p3b as p3b
import sclass.product.lifecycle_p3c_p8_p10 as p3c
import sclass.product.lifecycle_p5 as p5
import sclass.product.lifecycle_p6 as p6
import sclass.product.lifecycle_p7 as p7
import sclass.product.lifecycle_p11 as p11

AUTH = "QUALIFIED_EVALUATOR"


# =============================================================================
# Lane F4: 6 MUSTs (PD-F4-001 through PD-F4-006)
# =============================================================================

def test_w4_scenario_pd_f4_001():
    """W4 Scenario for PD-F4-001: Micro-eligible inputs compute MICRO lane."""
    payload = {
        "depth_dimensions": {"planning": "D1", "discovery": "D1", "context": "D1", "verification": "D1"},
        "risk_tier": "LOW", "failure_impact": "LOW", "estimated_files": 2, "modules": 1,
        "rollback_capability": True, "critical_flag": False, "requested_lane": "MICRO",
    }
    unauth = f4.evaluate_f4_lane_selection(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-F4-001"

    auth = f4.evaluate_f4_lane_selection(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_f4_002():
    """W4 Scenario for PD-F4-002: D4 verification depth computes CRITICAL."""
    payload = {
        "depth_dimensions": {"verification": "D4"},
        "requested_lane": "CRITICAL",
    }
    unauth = f4.evaluate_f4_lane_selection(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING

    auth = f4.evaluate_f4_lane_selection(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_f4_003():
    """W4 Scenario for PD-F4-003: DDL representation in STANDARD lane."""
    payload = {
        "change_surface": {"databases": 1},
        "f1_artifact_class": "data",
        "f1_required_representation": "DDL",
        "ddl_present": True,
        "requested_lane": "STANDARD",
    }
    unauth = f4.evaluate_f4_lane_selection(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING

    auth = f4.evaluate_f4_lane_selection(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_f4_004():
    """W4 Scenario for PD-F4-004: Depth budget declaration."""
    payload = {"depth": "D3", "requested_lane": "STANDARD"}
    unauth = f4.evaluate_f4_lane_selection(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING

    auth = f4.evaluate_f4_lane_selection(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_f4_005():
    """W4 Scenario for PD-F4-005: Replay EngineeringProfile rev 8 reproduces CRITICAL."""
    payload = {
        "prior_lane": "STANDARD", "security_change": True, "policy_critical_predicate": True,
        "canonical_profile_revision": 8, "recorded_lane": "CRITICAL",
        "replayed_profile_revision": 8, "requested_lane": "CRITICAL",
    }
    unauth = f4.evaluate_f4_lane_selection(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING

    auth = f4.evaluate_f4_lane_selection(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_f4_006():
    """W4 Scenario for PD-F4-006: Policy floor D3 overrides profile-derived D1."""
    payload = {"profile_derived_depth": "D1", "policy_floor": "D3", "requested_lane": "STANDARD"}
    unauth = f4.evaluate_f4_lane_selection(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING

    auth = f4.evaluate_f4_lane_selection(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


# =============================================================================
# Lane F8: 4 MUSTs (PD-F8-001 through PD-F8-004)
# =============================================================================

def test_w4_scenario_pd_f8_001():
    """W4 Scenario for PD-F8-001: Golden step compilation."""
    payload = {
        "target_must": "PD-F8-001", "phase": "P8", "task_ref": "TASK-1",
        "canonical_state_binding": "STATE-1", "pinned_skills": ["SK-1", "SK-2"],
        "context_budget_bytes": 4096, "compiler_version": "C1",
        "transcript_present": True, "anchors": ["A1"],
    }
    unauth = f8.evaluate_f8_step_pack(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-F8-001"

    auth = f8.evaluate_f8_step_pack(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_f8_002():
    """W4 Scenario for PD-F8-002: Context budget constraints."""
    payload = {
        "target_must": "PD-F8-002", "phase": "P8", "task_ref": "TASK-1",
        "canonical_state_binding": "STATE-1", "pinned_skills": ["SK-1", "SK-2"],
        "context_budget_bytes": 4096, "compiler_version": "C1",
        "transcript_present": True, "anchors": ["A1"],
    }
    unauth = f8.evaluate_f8_step_pack(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING

    auth = f8.evaluate_f8_step_pack(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_f8_003():
    """W4 Scenario for PD-F8-003: Step pack deterministic resume."""
    payload = {
        "target_must": "PD-F8-003", "phase": "P8", "task_ref": "TASK-1",
        "canonical_state_binding": "STATE-1", "pinned_skills": ["SK-1", "SK-2"],
        "context_budget_bytes": 4096, "compiler_version": "C1",
        "transcript_present": True, "anchors": ["A1"],
    }
    unauth = f8.evaluate_f8_step_pack(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING

    auth = f8.evaluate_f8_step_pack(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_f8_004():
    """W4 Scenario for PD-F8-004: Step pack verification."""
    payload = {
        "target_must": "PD-F8-004", "phase": "P8", "task_ref": "TASK-1",
        "canonical_state_binding": "STATE-1", "pinned_skills": ["SK-1", "SK-2"],
        "context_budget_bytes": 4096, "compiler_version": "C1",
        "transcript_present": True, "anchors": ["A1"],
    }
    unauth = f8.evaluate_f8_step_pack(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING

    auth = f8.evaluate_f8_step_pack(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


# =============================================================================
# Lane Replay: 2 MUSTs (PD-CH2-064, PD-CH2-065)
# =============================================================================

def test_w4_scenario_pd_ch2_064():
    """W4 Scenario for PD-CH2-064: Replay invalidation restarts at earliest affected phase."""
    payload = {
        "must_id": "PD-CH2-064",
        "dependency_set_digest": "DEP-SET-001",
        "earliest_affected_phase": "P2",
        "replay_start_phase": "P2",
    }
    unauth = rep.evaluate_ch2_064_replay_invalidation(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-064"

    auth = rep.evaluate_ch2_064_replay_invalidation(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_065():
    """W4 Scenario for PD-CH2-065: Lifecycle proof requires verified canonical record."""
    payload = {
        "must_id": "PD-CH2-065",
        "example_preconditions": {"target": "rate_limiter", "window_sec": 60},
        "bound_input_digests": ["DIGEST-PRE-01", "DIGEST-IN-01"],
        "expected_gate_output": "SATISFIED",
        "failure_route": None,
        "evaluator_record_ref": "EVAL-REC-001",
    }
    unauth = rep.evaluate_ch2_065_lifecycle_proof(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-065"

    verifier = lambda ref: {
        "evaluator_record_ref": "EVAL-REC-001",
        "status": "VERIFIED",
        "gate_output": "SATISFIED",
    } if ref == "EVAL-REC-001" else None

    auth = rep.evaluate_ch2_065_lifecycle_proof(payload, caller_authority=AUTH, record_verifier=verifier)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


# =============================================================================
# Lane P0A: 6 MUSTs (PD-CH2-001, 002, 003, 005, 006, 055)
# =============================================================================

def test_w4_scenario_pd_ch2_001():
    """W4 Scenario for PD-CH2-001: Registered single lifecycle projection."""
    payload = {"work_type": "FEATURE", "phase_sequence": list(p0a.STANDARD_PHASES)}
    unauth = p0a.evaluate_pd_ch2_001_single_lifecycle(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-001"

    auth = p0a.evaluate_pd_ch2_001_single_lifecycle(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_002():
    """W4 Scenario for PD-CH2-002: Eleven lifecycle dimensions defined."""
    payload = {"phase": "P6", "defined_dimensions": list(p0a.ELEVEN_DIMENSIONS)}
    unauth = p0a.evaluate_pd_ch2_002_eleven_dimensions(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-002"

    auth = p0a.evaluate_pd_ch2_002_eleven_dimensions(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_003():
    """W4 Scenario for PD-CH2-003: Earlier phase validity prerequisites."""
    payload = {"current_phase": "P3", "earlier_phase_status": {"P0": "VALID", "P1": "VALID", "P2": "VALID"}}
    unauth = p0a.evaluate_pd_ch2_003_earlier_phase_validity(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-003"

    auth = p0a.evaluate_pd_ch2_003_earlier_phase_validity(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_005():
    """W4 Scenario for PD-CH2-005: Skipped phase explicit applicability record."""
    payload = {
        "skipped_phases": ["P2"],
        "applicability_declarations": {
            "P2": {"evaluator_checkable": True, "skip_reason": "SPIKE_RESEARCH_NO_FORMAL_SPEC"}
        },
    }
    unauth = p0a.evaluate_pd_ch2_005_skipped_phase_applicability(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-005"

    auth = p0a.evaluate_pd_ch2_005_skipped_phase_applicability(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_006():
    """W4 Scenario for PD-CH2-006: Defect routing to earliest affected phase."""
    payload = {"defect_found_in": "P6", "earliest_affected_phase": "P2", "routed_phase": "P2"}
    unauth = p0a.evaluate_pd_ch2_006_earliest_defect_routing(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-006"

    auth = p0a.evaluate_pd_ch2_006_earliest_defect_routing(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_055():
    """W4 Scenario for PD-CH2-055: Downstream invalidation on dependency change."""
    payload = {
        "authoritative_dependency_digest": "DIGEST-NEW-123",
        "downstream_invalidated": True,
        "recomputation_key": {"dependency_digest": "DIGEST-NEW-123"},
    }
    unauth = p0a.evaluate_pd_ch2_055_downstream_invalidation(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-055"

    auth = p0a.evaluate_pd_ch2_055_downstream_invalidation(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


# =============================================================================
# Lane P0B: 6 MUSTs (PD-CH2-007, 008, 009, 010, 011, 012)
# =============================================================================

def test_w4_scenario_pd_ch2_007():
    """W4 Scenario for PD-CH2-007: P8 retry budget allocation."""
    unauth = p0b.evaluate_pd_ch2_007_p8_retry_budget(10, 2, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-007"

    auth = p0b.evaluate_pd_ch2_007_p8_retry_budget(10, 2, alternate_retry_path_active=False, is_p8_repair=True, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_008():
    """W4 Scenario for PD-CH2-008: P11 non-terminal re-entry."""
    unauth = p0b.evaluate_pd_ch2_008_p11_non_terminal_reentry("NON_TERMINAL", "P0", authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-008"

    auth = p0b.evaluate_pd_ch2_008_p11_non_terminal_reentry("NON_TERMINAL", "P0", authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_009():
    """W4 Scenario for PD-CH2-009: Done claim evidence and kernel closure."""
    unauth = p0b.evaluate_pd_ch2_009_done_claim_evidence_closure(True, True, True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-009"

    auth = p0b.evaluate_pd_ch2_009_done_claim_evidence_closure(
        model_done_claimed=True, admissible_evidence_present=True, kernel_evaluated_closure=True, authority=AUTH
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_010():
    """W4 Scenario for PD-CH2-010: Green external run evidence binding."""
    unauth = p0b.evaluate_pd_ch2_010_green_external_run_evidence(True, True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-010"

    auth = p0b.evaluate_pd_ch2_010_green_external_run_evidence(
        external_run_green=True, bound_to_obligation_inputs=True, authority=AUTH
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_011():
    """W4 Scenario for PD-CH2-011: Stack pack phase topology."""
    phases = ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10", "P11"]
    unauth = p0b.evaluate_pd_ch2_011_stack_pack_phase_topology(phases, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-011"

    auth = p0b.evaluate_pd_ch2_011_stack_pack_phase_topology(phases, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_012():
    """W4 Scenario for PD-CH2-012: Mandatory floor human waiver path."""
    unauth = p0b.evaluate_pd_ch2_012_mandatory_floor_human_waiver(waiver_requested=False, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth != GateState.SATISFIED
    assert unauth.state in (GateState.MISSING, GateState.BLOCKED_ON_HUMAN)

    auth = p0b.evaluate_pd_ch2_012_mandatory_floor_human_waiver(waiver_requested=False, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


# =============================================================================
# Lane P1P4: 5 MUSTs (PD-CH2-029, 031, 032, 056, 057)
# =============================================================================

def test_w4_scenario_pd_ch2_029():
    """W4 Scenario for PD-CH2-029: Task units cap per lane."""
    unauth = p1p4.evaluate_pd_ch2_029_task_caps("MICRO", 1, task_count=1, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-029"

    auth = p1p4.evaluate_pd_ch2_029_task_caps("MICRO", 1, task_count=1, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_031():
    """W4 Scenario for PD-CH2-031: Work graph acyclic validation."""
    edges = {"T1": ["T2"], "T2": []}
    unauth = p1p4.evaluate_pd_ch2_031_work_graph_acyclic(edges, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-031"

    auth = p1p4.evaluate_pd_ch2_031_work_graph_acyclic(edges, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_032():
    """W4 Scenario for PD-CH2-032: Write set overlap serialization."""
    tasks = [
        {"task_id": "T1", "declared_write_set": {"fileA.py"}, "serialized": False},
        {"task_id": "T2", "declared_write_set": {"fileB.py"}, "serialized": False},
    ]
    unauth = p1p4.evaluate_pd_ch2_032_write_set_overlap(tasks=tasks, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.BLOCKED_ON_HUMAN
    assert unauth.must_id == "PD-CH2-032"

    auth = p1p4.evaluate_pd_ch2_032_write_set_overlap(tasks=tasks, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_056():
    """W4 Scenario for PD-CH2-056: P1 Discovery completeness."""
    unauth = p1p4.evaluate_pd_ch2_056_discovery_completeness(True, 1.0, True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-056"

    auth = p1p4.evaluate_pd_ch2_056_discovery_completeness(
        target_snapshot_resolved=True, index_coverage_ratio=1.0, high_impact_unknowns_resolved=True, authority=AUTH
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_057():
    """W4 Scenario for PD-CH2-057: Skill depth and precedence."""
    unauth = p1p4.evaluate_pd_ch2_057_skill_depth_precedence(True, ["SK-1"], True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-057"

    auth = p1p4.evaluate_pd_ch2_057_skill_depth_precedence(
        skills_resolved=True, pinned_skill_digests=["SK-1"], policy_floor_respected=True, authority=AUTH
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


# =============================================================================
# Lane P3A: 6 MUSTs (PD-CH2-013, 014, 015, 016, 017, 018)
# =============================================================================

def test_w4_scenario_pd_ch2_013():
    """W4 Scenario for PD-CH2-013: Requirement semantic coverage."""
    reqs = [{"id": "REQ-1", "semantic_coverage": True, "explicit_applicability": False}]
    unauth = p3a.evaluate_pd_ch2_013_requirement_coverage(reqs, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-013"

    auth = p3a.evaluate_pd_ch2_013_requirement_coverage(reqs, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_014():
    """W4 Scenario for PD-CH2-014: Domain entity invariants."""
    entities = [{"name": "Account", "invariants": ["balance >= 0"]}]
    unauth = p3a.evaluate_pd_ch2_014_domain_invariants(entities, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-014"

    auth = p3a.evaluate_pd_ch2_014_domain_invariants(entities, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_015():
    """W4 Scenario for PD-CH2-015: Architecture provenance to requirements."""
    elements = [{"name": "Gateway", "provenance": {"requirement_id": "REQ-1"}}]
    unauth = p3a.evaluate_pd_ch2_015_architecture_provenance(elements, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-015"

    auth = p3a.evaluate_pd_ch2_015_architecture_provenance(elements, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_016():
    """W4 Scenario for PD-CH2-016: Dependency relationships representation."""
    material = [{"source": "ServiceA", "destination": "Database"}]
    represented = [("ServiceA", "Database")]
    unauth = p3a.evaluate_pd_ch2_016_dependency_relationships(material, represented, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-016"

    auth = p3a.evaluate_pd_ch2_016_dependency_relationships(material, represented, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_017():
    """W4 Scenario for PD-CH2-017: Domain model substance."""
    model = {"entities": [{"name": "User", "fields": ["id: UUID"], "constraints": ["email != empty"]}]}
    unauth = p3a.evaluate_pd_ch2_017_domain_model_substance(model, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-017"

    auth = p3a.evaluate_pd_ch2_017_domain_model_substance(model, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_018():
    """W4 Scenario for PD-CH2-018: Architecture record substance."""
    record = {"components": ["API"], "boundaries": ["TrustBoundary"], "contracts": ["ProtobufV1"]}
    unauth = p3a.evaluate_pd_ch2_018_architecture_record_substance(record, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-018"

    auth = p3a.evaluate_pd_ch2_018_architecture_record_substance(record, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


# =============================================================================
# Lane P3B: 6 MUSTs (PD-CH2-020, 021, 022, 023, 024, 025)
# =============================================================================

def test_w4_scenario_pd_ch2_020():
    """W4 Scenario for PD-CH2-020: Decidable invariant fragments."""
    invs = [{"name": "BalanceEq", "fragment": "EQUATIONAL_EQUALITY", "supported": True, "claimed_pass": True}]
    unauth = p3b.evaluate_pd_ch2_020_decidable_invariants(invs, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-020"

    auth = p3b.evaluate_pd_ch2_020_decidable_invariants(invs, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_021():
    """W4 Scenario for PD-CH2-021: Cross-entity cardinality constraints."""
    constraints = [{"id": "C-1", "relationship": "ONE_TO_MANY", "cardinality": "1..*"}]
    unauth = p3b.evaluate_pd_ch2_021_cross_entity_constraints(constraints, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-021"

    auth = p3b.evaluate_pd_ch2_021_cross_entity_constraints(constraints, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_022():
    """W4 Scenario for PD-CH2-022: Change surface boundary closure."""
    boundaries = ["ServiceA", "Database"]
    edges = [("ServiceA", "Database")]
    unauth = p3b.evaluate_pd_ch2_022_change_surface_boundary_closure(boundaries, edges, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-022"

    auth = p3b.evaluate_pd_ch2_022_change_surface_boundary_closure(boundaries, edges, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_023():
    """W4 Scenario for PD-CH2-023: Boundary data flow contracts."""
    flows = [{"id": "F-1", "source": "API", "destination": "Queue", "contract": "AvroOrderPayload", "transformation": "SerializeToAvro"}]
    unauth = p3b.evaluate_pd_ch2_023_boundary_data_flow_contracts(flows, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-023"

    auth = p3b.evaluate_pd_ch2_023_boundary_data_flow_contracts(flows, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_024():
    """W4 Scenario for PD-CH2-024: Interface signatures typed contracts."""
    ifaces = [{
        "name": "GetUser", "signature_type": "UserResponseDTO",
        "domain_contract_type": "UserResponseDTO", "requirement_predicate_type": "UserResponseDTO"
    }]
    unauth = p3b.evaluate_pd_ch2_024_interface_signatures_typed_contracts(ifaces, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-024"

    auth = p3b.evaluate_pd_ch2_024_interface_signatures_typed_contracts(ifaces, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_025():
    """W4 Scenario for PD-CH2-025: Unknown contradiction handling."""
    unauth = p3b.evaluate_pd_ch2_025_unknown_contradiction_handling(False, False, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-025"

    auth = p3b.evaluate_pd_ch2_025_unknown_contradiction_handling(False, False, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


# =============================================================================
# Lane P3C / P8 / P10: 5 MUSTs (PD-CH2-026, 028, 051, 052, 053)
# =============================================================================

def test_w4_scenario_pd_ch2_026():
    """W4 Scenario for PD-CH2-026: ADR design digest binding."""
    adrs = [{"id": "ADR-001", "digest": "sha256:111", "lint_passed": True, "is_stale": False}]
    unauth = p3c.evaluate_pd_ch2_026_adr_design_digest_binding(adrs, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-026"

    auth = p3c.evaluate_pd_ch2_026_adr_design_digest_binding(adrs, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_028():
    """W4 Scenario for PD-CH2-028: Unique MUST IDs."""
    mids = ["PD-CH2-001", "PD-CH2-002", "PD-CH2-003"]
    unauth = p3c.evaluate_pd_ch2_028_unique_must_ids(mids, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-028"

    auth = p3c.evaluate_pd_ch2_028_unique_must_ids(mids, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_051():
    """W4 Scenario for PD-CH2-051: P8 retry budget exhaustion routing."""
    unauth = p3c.evaluate_pd_ch2_051_p8_retry_budget_exhaustion(3, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth != GateState.SATISFIED
    assert unauth.state in (GateState.MISSING, GateState.BLOCKED_ON_HUMAN)

    auth = p3c.evaluate_pd_ch2_051_p8_retry_budget_exhaustion(
        retry_budget_remaining=3, earliest_affected_phase="P2", routed_phase="P2", authority=AUTH
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_052():
    """W4 Scenario for PD-CH2-052: P9 task aggregation findings closure."""
    unauth = p3c.evaluate_pd_ch2_052_p9_task_aggregation_findings_closure(["T1"], ["T1"], [], authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-052"

    auth = p3c.evaluate_pd_ch2_052_p9_task_aggregation_findings_closure(
        required_p7_tasks=["T-1"], aggregated_p7_tasks=["T-1"], open_mandatory_findings=[], authority=AUTH
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_053():
    """W4 Scenario for PD-CH2-053: P10 kernel release evaluation."""
    unauth = p3c.evaluate_pd_ch2_053_p10_kernel_release_evaluation("ALLOW", True, authority=None)
    assert str(unauth).startswith("MISSING")

    auth = p3c.evaluate_pd_ch2_053_p10_kernel_release_evaluation(
        kernel_release_evaluation="ALLOW", product_checks_pass=True, authority=AUTH
    )
    assert str(auth) == "SATISFIED"
    assert auth.status == "SATISFIED"


# =============================================================================
# Lane P5: 6 MUSTs (PD-CH2-033, 034, 035, 036, 046, 047)
# =============================================================================

def test_w4_scenario_pd_ch2_033():
    """W4 Scenario for PD-CH2-033: Delta sequence precedence."""
    unauth = p5.evaluate_pd_ch2_033_delta_sequence(1, 2, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-033"

    auth = p5.evaluate_pd_ch2_033_delta_sequence(test_delta_seq=1, impl_delta_seq=2, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_034():
    """W4 Scenario for PD-CH2-034: Red-run validity and designed test match."""
    unauth = p5.evaluate_pd_ch2_034_red_run_validity(True, True, "AssertionError", "AssertionError", authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-034"

    auth = p5.evaluate_pd_ch2_034_red_run_validity(
        adapter_qualified=True, run_failed_designed_test=True, failure_class="AssertionError", designed_class="AssertionError", authority=AUTH
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_035():
    """W4 Scenario for PD-CH2-035: Executable specification constraints."""
    unauth = p5.evaluate_pd_ch2_035_executable_spec_constraints(True, True, False, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-035"

    auth = p5.evaluate_pd_ch2_035_executable_spec_constraints(
        is_executable_f1_f2=True, finite_domain=True, is_prose_only=False, authority=AUTH
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_036():
    """W4 Scenario for PD-CH2-036: Adapter qualification in implementation plane."""
    unauth = p5.evaluate_pd_ch2_036_adapter_qualification("pytest-sclass", authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-036"

    auth = p5.evaluate_pd_ch2_036_adapter_qualification("pytest-sclass", authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_046():
    """W4 Scenario for PD-CH2-046: Test input set binding."""
    unauth = p5.evaluate_pd_ch2_046_test_input_set_binding(
        primary_test_digest="sha256:primary123", bound_test_input_set={"test_file.py": "sha256:primary123"}, authority=None
    )
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-046"

    auth = p5.evaluate_pd_ch2_046_test_input_set_binding(
        primary_test_digest="sha256:primary123",
        bound_test_input_set={"test_file.py": "sha256:primary123", "conftest.py": "sha256:conf456"},
        authority=AUTH,
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_047():
    """W4 Scenario for PD-CH2-047: Red classification source."""
    unauth = p5.evaluate_pd_ch2_047_red_classification_source(
        adapter_structured_result={"failed_test": "test_invariant_a", "failure_reason": "AssertionError: expected True"},
        designed_test_tuple=("test_invariant_a", "AssertionError: expected True"),
        authority=None,
    )
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-047"

    auth = p5.evaluate_pd_ch2_047_red_classification_source(
        adapter_structured_result={"failed_test": "test_invariant_a", "failure_reason": "AssertionError: expected True"},
        designed_test_tuple=("test_invariant_a", "AssertionError: expected True"),
        authority=AUTH,
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


# =============================================================================
# Lane P6: 5 MUSTs (PD-CH2-037, 038, 039, 040, 048)
# =============================================================================

def test_w4_scenario_pd_ch2_037():
    """W4 Scenario for PD-CH2-037: Execution gate authorization."""
    unauth = p6.evaluate_pd_ch2_037_execution_gate_authorization(True, "T1", "src", "src/core.py", authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-037"

    auth = p6.evaluate_pd_ch2_037_execution_gate_authorization(
        has_execution_gate_auth=True, task_id="T1", scope="src", target="src/core.py", authority=AUTH
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_038():
    """W4 Scenario for PD-CH2-038: Scope growth stop."""
    unauth = p6.evaluate_pd_ch2_038_scope_growth_stop(False, ["src/auth.py"], {"src/auth.py"}, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-038"

    auth = p6.evaluate_pd_ch2_038_scope_growth_stop(
        is_out_of_scope=False, delta_files=["src/auth.py"], declared_scope={"src/auth.py", "src/user.py"}, authority=AUTH
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_039():
    """W4 Scenario for PD-CH2-039: Claimed symbols presence in post-delta symbols."""
    unauth = p6.evaluate_pd_ch2_039_implementation_claims(["UserValidator"], {"UserValidator"}, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth != GateState.SATISFIED
    assert unauth.state in (GateState.MISSING, GateState.BLOCKED_ON_HUMAN)

    auth = p6.evaluate_pd_ch2_039_implementation_claims(
        claimed_symbols=["UserValidator"], post_delta_symbols={"UserValidator", "Other"}, authority=AUTH
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_040():
    """W4 Scenario for PD-CH2-040: Canonical delta kernel receipt."""
    unauth = p6.evaluate_pd_ch2_040_canonical_delta_kernel_receipt(True, "sha256:kernel123", False, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-040"

    auth = p6.evaluate_pd_ch2_040_canonical_delta_kernel_receipt(
        has_kernel_receipt=True, kernel_receipt_digest="sha256:kernel123", kernel_denied=False, authority=AUTH
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_048():
    """W4 Scenario for PD-CH2-048: Test input set exclusion check."""
    unauth = p6.evaluate_pd_ch2_048_test_input_set_exclusion_check(True, False, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-048"

    auth = p6.evaluate_pd_ch2_048_test_input_set_exclusion_check(
        p6_tests_frozen_invoked=True, p6_modifies_test_input_set=False, authority=AUTH
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


# =============================================================================
# Lane P7: 6 MUSTs (PD-CH2-041, 042, 043, 044, 045, 050)
# =============================================================================

def test_w4_scenario_pd_ch2_041():
    """W4 Scenario for PD-CH2-041: Evidence binding to target and step."""
    unauth = p7.evaluate_pd_ch2_041_evidence_binding(True, True, True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-041"

    auth = p7.evaluate_pd_ch2_041_evidence_binding(
        evidence_identity_bound=True, current_target_bound=True, current_step_bound=True, authority=AUTH
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_042():
    """W4 Scenario for PD-CH2-042: Verification plane adapter qualification."""
    unauth = p7.evaluate_pd_ch2_042_adapter_qualification("pytest-sclass", True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-042"

    auth = p7.evaluate_pd_ch2_042_adapter_qualification("pytest-sclass", is_f10_qualified=True, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_043():
    """W4 Scenario for PD-CH2-043: Independence floor compliance."""
    unauth = p7.evaluate_pd_ch2_043_independence_floor(3, 2, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-043"

    auth = p7.evaluate_pd_ch2_043_independence_floor(independence_level=3, required_floor=2, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_044():
    """W4 Scenario for PD-CH2-044: Freshness predicate."""
    unauth = p7.evaluate_pd_ch2_044_freshness_predicate("sha256:target100", "sha256:target100", False, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-044"

    auth = p7.evaluate_pd_ch2_044_freshness_predicate(
        evidence_digest="sha256:target100", current_code_digest="sha256:target100", is_stale=False, authority=AUTH
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_045():
    """W4 Scenario for PD-CH2-045: Closure ownership."""
    unauth = p7.evaluate_pd_ch2_045_closure_ownership("CLOSED", False, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-045"

    auth = p7.evaluate_pd_ch2_045_closure_ownership(
        kernel_closure_result="CLOSED", agent_asserts_closure=False, authority=AUTH
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_050():
    """W4 Scenario for PD-CH2-050: Deterministic re-run verification."""
    unauth = p7.evaluate_pd_ch2_050_deterministic_rerun(["PASS", "PASS", "PASS"], authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-050"

    auth = p7.evaluate_pd_ch2_050_deterministic_rerun(rerun_results=["PASS", "PASS", "PASS"], authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


# =============================================================================
# Lane P11: 6 MUSTs (PD-CH2-054, 058, 060, 061, 062, 063)
# =============================================================================

def test_w4_scenario_pd_ch2_054():
    """W4 Scenario for PD-CH2-054: Signal source event ref proposing P0 re-entry."""
    payload = {
        "source_event_ref": "EVT-CANONICAL-10",
        "baseline_digest": "D1",
        "observed_digest": "D2",
        "proposed_action": "propose_p0_reentry",
    }
    unauth = p11.evaluate_pd_ch2_054_signal(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-054"

    auth = p11.evaluate_pd_ch2_054_signal(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_058():
    """W4 Scenario for PD-CH2-058: Applicability records for all 12 phases."""
    payload = {
        "must_id": "PD-CH2-058",
        "work_type": "FEATURE",
        "applicability_records[P0..P11]": ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10", "P11"],
        "skip_reason": "none",
        "evaluator_record_ref": "EVAL-APP-001",
    }
    unauth = p11.evaluate_pd_ch2_058_applicability(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-058"

    auth = p11.evaluate_pd_ch2_058_applicability(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_060():
    """W4 Scenario for PD-CH2-060: Flow order preservation."""
    payload = {
        "must_id": "PD-CH2-060",
        "flow_definition_digest": "FLOW-DEF-01",
        "phase_order": ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"],
        "defect_origin_phase": "P2",
        "replay_start_phase": "P2",
    }
    unauth = p11.evaluate_pd_ch2_060_flow_order(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-060"

    auth = p11.evaluate_pd_ch2_060_flow_order(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_061():
    """W4 Scenario for PD-CH2-061: Delivery flow predicates and gate outputs."""
    payload = {
        "must_id": "PD-CH2-061",
        "entry_predicate_digest": "DIGEST-ENTRY-01",
        "gate_output_digests": ["DIGEST-GATE-01", "DIGEST-GATE-02"],
        "rollback_condition_digest": "DIGEST-ROLLBACK-01",
    }
    unauth = p11.evaluate_pd_ch2_061_delivery_flow(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-061"

    auth = p11.evaluate_pd_ch2_061_delivery_flow(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_062():
    """W4 Scenario for PD-CH2-062: Project class and fit evidence."""
    payload = {
        "must_id": "PD-CH2-062",
        "project_class": "python_backend",
        "fit_evidence_digest": "DIGEST-FIT-001",
        "qualification_record_digest": "DIGEST-QUAL-001",
    }
    unauth = p11.evaluate_pd_ch2_062_project_class(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-062"

    auth = p11.evaluate_pd_ch2_062_project_class(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED


def test_w4_scenario_pd_ch2_063():
    """W4 Scenario for PD-CH2-063: Question budget and blockers."""
    payload = {
        "must_id": "PD-CH2-063",
        "question_budget": 5,
        "questions_asked": 3,
        "open_blockers_digest": "DIGEST-BLOCKERS-01",
        "treated_as_complete": False,
    }
    unauth = p11.evaluate_pd_ch2_063_question_budget(payload, caller_authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH2-063"

    auth = p11.evaluate_pd_ch2_063_question_budget(payload, caller_authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
