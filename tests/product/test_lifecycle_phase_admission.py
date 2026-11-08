"""Tests for Block 4 Lane C (Objective Lifecycle Phase Flow & Admission).

Test matrix: MUST x {gaming, happy, no-authority, malformed/None fail-closed, mutation per decision branch}.
MUSTs covered:
- PD-CH3-001: Every phase artifact MUST bind objective revision and canonical SpecAnchor digests.
- PD-CH3-002: Normative requirements MUST have testable acceptance links, explicit non-goals, and no placeholders.
- PD-CH3-003: Clarification answers changing scope MUST enter canonical mechanisms; absent human blocks.
- PD-CH3-006: External process tools MUST remain untrusted candidates until qualification is recorded.
- PD-CH3-007: Work type MUST be projected from canonical Decision outcome without product state machine.
- PD-CH3-009: Default user-facing flow MUST preserve required gates/evidence and compute lane from policy.
"""
from __future__ import annotations

import pytest
from sclass.product.gate import GateOutput, GateState
from sclass.product.lifecycle_phase_admission import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    VALID_WORK_TYPES,
    CANONICAL_LANES,
    evaluate_pd_ch3_001_phase_artifact_anchors,
    evaluate_pd_ch3_002_normative_requirements_completeness,
    evaluate_pd_ch3_003_clarification_scope_entry,
    evaluate_pd_ch3_006_external_tool_candidate_trust,
    evaluate_pd_ch3_007_work_type_decision_projection,
    evaluate_pd_ch3_009_flow_gates_and_lane_computation,
    evaluate_b4_c_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


# -----------------------------------------------------------------------------
# PD-CH3-001
# -----------------------------------------------------------------------------
def test_ch3_001_happy_path():
    out = evaluate_pd_ch3_001_phase_artifact_anchors(
        objective_revision="rev-01",
        spec_anchor_digests=["sha256:anchor1", "sha256:anchor2"],
        expected_objective_revision="rev-01",
        expected_anchor_digests=["sha256:anchor1", "sha256:anchor2"],
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH3-001"


def test_ch3_001_gaming_mismatched_objective_or_anchor_digest():
    out_rev = evaluate_pd_ch3_001_phase_artifact_anchors(
        objective_revision="rev-02",
        spec_anchor_digests=["sha256:anchor1"],
        expected_objective_revision="rev-01",
        authority=AUTH,
    )
    assert out_rev.state == GateState.MISSING
    assert out_rev.must_id == "PD-CH3-001"

    out_anc = evaluate_pd_ch3_001_phase_artifact_anchors(
        objective_revision="rev-01",
        spec_anchor_digests=["sha256:stale"],
        expected_anchor_digests=["sha256:fresh"],
        authority=AUTH,
    )
    assert out_anc.state == GateState.MISSING


def test_ch3_001_no_authority_and_empty():
    assert evaluate_pd_ch3_001_phase_artifact_anchors("r", ["a"], authority=None).state == GateState.MISSING
    assert evaluate_pd_ch3_001_phase_artifact_anchors(None, None, authority=AUTH).state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-CH3-002
# -----------------------------------------------------------------------------
def test_ch3_002_happy_path():
    out = evaluate_pd_ch3_002_normative_requirements_completeness(
        requirements=[
            {"id": "REQ-1", "text": "The engine shall validate", "acceptance_links": ["test_1"]},
            {"id": "REQ-2", "text": "The engine shall fail-closed", "acceptance_links": ["test_2"]},
        ],
        non_goals=["Out of scope: UI rendering"],
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH3-002"


def test_ch3_002_gaming_unlinked_criterion():
    out = evaluate_pd_ch3_002_normative_requirements_completeness(
        requirements=[{"id": "REQ-1", "text": "No acceptance link", "acceptance_links": []}],
        non_goals=["non-goal-1"],
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH3-002"
    assert "missing testable acceptance links" in out.detail


def test_ch3_002_gaming_normative_placeholder():
    out = evaluate_pd_ch3_002_normative_requirements_completeness(
        requirements=[{"id": "REQ-1", "text": "Behavior is TODO later", "acceptance_links": ["t1"]}],
        non_goals=["non-goal-1"],
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert "normative placeholder" in out.detail


def test_ch3_002_missing_non_goals_and_no_authority():
    out_ng = evaluate_pd_ch3_002_normative_requirements_completeness(
        requirements=[{"id": "1", "acceptance_links": ["t"]}], non_goals=None, authority=AUTH
    )
    assert out_ng.state == GateState.MISSING
    out_na = evaluate_pd_ch3_002_normative_requirements_completeness([{"id": "1"}], ["ng"], authority=None)
    assert out_na.state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-CH3-003
# -----------------------------------------------------------------------------
def test_ch3_003_happy_path_confirmed():
    out = evaluate_pd_ch3_003_clarification_scope_entry(
        scope_changed=True,
        canonical_decision_recorded=True,
        human_confirmed=True,
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH3-003"


def test_ch3_003_happy_no_scope_change():
    out = evaluate_pd_ch3_003_clarification_scope_entry(
        scope_changed=False,
        canonical_decision_recorded=False,
        human_confirmed=False,
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED


def test_ch3_003_gaming_agent_claims_confirmation_no_human():
    out = evaluate_pd_ch3_003_clarification_scope_entry(
        scope_changed=True,
        canonical_decision_recorded=True,
        human_confirmed=False,
        authority=AUTH,
    )
    assert out.state == GateState.BLOCKED_ON_HUMAN
    assert out.must_id == "PD-CH3-003"


def test_ch3_003_gaming_human_confirmed_but_not_recorded():
    out = evaluate_pd_ch3_003_clarification_scope_entry(
        scope_changed=True,
        canonical_decision_recorded=False,
        human_confirmed=True,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert "not entered in canonical Decision" in out.detail


def test_ch3_003_no_authority():
    assert evaluate_pd_ch3_003_clarification_scope_entry(True, True, True, authority=None).state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-CH3-006
# -----------------------------------------------------------------------------
def test_ch3_006_happy_qualified_tool():
    out = evaluate_pd_ch3_006_external_tool_candidate_trust(
        tool_identity="external-linter",
        qualification_recorded=True,
        claimed_authoritative=True,
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH3-006"


def test_ch3_006_happy_unqualified_candidate():
    out = evaluate_pd_ch3_006_external_tool_candidate_trust(
        tool_identity="candidate-tool",
        qualification_recorded=False,
        claimed_authoritative=False,
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED


def test_ch3_006_gaming_unqualified_claimed_authoritative():
    out = evaluate_pd_ch3_006_external_tool_candidate_trust(
        tool_identity="shadow-tool",
        qualification_recorded=False,
        claimed_authoritative=True,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH3-006"
    assert "claimed authoritative without recorded qualification" in out.detail


def test_ch3_006_no_authority():
    assert evaluate_pd_ch3_006_external_tool_candidate_trust("t", True, True, authority=None).state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-CH3-007
# -----------------------------------------------------------------------------
def test_ch3_007_happy_path():
    out = evaluate_pd_ch3_007_work_type_decision_projection(
        canonical_decision_outcome="DEC-FEATURE-01",
        projected_work_type="FEATURE",
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH3-007"


def test_ch3_007_gaming_agent_only_override():
    out = evaluate_pd_ch3_007_work_type_decision_projection(
        canonical_decision_outcome="DEC-BUGFIX-01",
        projected_work_type="FEATURE",
        agent_override_attempted=True,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH3-007"
    assert "Agent-only work-type label change rejected" in out.detail


def test_ch3_007_invalid_work_type():
    out = evaluate_pd_ch3_007_work_type_decision_projection(
        canonical_decision_outcome="DEC-01",
        projected_work_type="UNKNOWN_ARBITRARY_TYPE",
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert "Invalid projected work type" in out.detail


def test_ch3_007_no_authority_and_none():
    assert evaluate_pd_ch3_007_work_type_decision_projection("D", "FEATURE", authority=None).state == GateState.MISSING
    assert evaluate_pd_ch3_007_work_type_decision_projection(None, None, authority=AUTH).state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-CH3-009
# -----------------------------------------------------------------------------
def test_ch3_009_happy_path():
    out = evaluate_pd_ch3_009_flow_gates_and_lane_computation(
        flow_identity="user_registration_flow",
        contract_tests_present=True,
        computed_lane="STANDARD_LANE",
        agent_selected_lane=False,
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH3-009"


def test_ch3_009_gaming_omits_contract_test():
    out = evaluate_pd_ch3_009_flow_gates_and_lane_computation(
        flow_identity="endpoint_flow",
        contract_tests_present=False,
        computed_lane="STANDARD_LANE",
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH3-009"
    assert "omits required contract test" in out.detail


def test_ch3_009_gaming_agent_selected_lane():
    out = evaluate_pd_ch3_009_flow_gates_and_lane_computation(
        flow_identity="endpoint_flow",
        contract_tests_present=True,
        computed_lane="FAST_LANE",
        agent_selected_lane=True,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH3-009"
    assert "agent-selected lane" in out.detail


def test_ch3_009_invalid_lane_and_no_authority():
    assert evaluate_pd_ch3_009_flow_gates_and_lane_computation("f", True, "INVALID", authority=AUTH).state == GateState.MISSING
    assert evaluate_pd_ch3_009_flow_gates_and_lane_computation("f", True, "FAST_LANE", authority=None).state == GateState.MISSING


# -----------------------------------------------------------------------------
# Aggregate Gate
# -----------------------------------------------------------------------------
def test_evaluate_b4_c_gate_aggregate():
    payload = {
        "objective_revision": "rev-1",
        "spec_anchor_digests": ["sha256:1"],
        "requirements": [{"id": "R1", "acceptance_links": ["t1"]}],
        "non_goals": ["ng1"],
        "scope_changed": False,
        "tool_identity": "tool1",
        "qualification_recorded": True,
        "claimed_authoritative": True,
        "canonical_decision_outcome": "DEC-1",
        "projected_work_type": "FEATURE",
        "flow_identity": "flow1",
        "contract_tests_present": True,
        "computed_lane": "STANDARD_LANE",
    }
    gate_out = evaluate_b4_c_gate(payload, authority=AUTH)
    assert len(gate_out) == 6
    for m_id, res in gate_out.items():
        assert res.state == GateState.SATISFIED
