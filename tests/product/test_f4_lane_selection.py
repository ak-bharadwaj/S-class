"""Tests for F4 Lane Selection Engine (PD-F4-001 through PD-F4-006).

Verifies complete MUST x test-kind matrix (24 tests: 6 MUSTs x 4 test-kinds: happy, gaming, no_authority, malformed).
Includes distinct tests for:
- F4-T6: Canonical EngineeringProfile revision 8 replay output.
- F4-T7: Exact assignment budget triple (8192, EVAL-LARGE, 2).
"""
from __future__ import annotations

import pytest

from sclass.product.f4_lane_selection import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    Lane,
    DepthLevel,
    BudgetTriple,
    EscalationRecord,
    BUDGET_TABLE,
    INDEPENDENCE_FLOOR_TABLE,
    compute_lane,
    resolve_effective_depth,
    get_depth_budget,
    record_lane_escalation,
    replay_lane,
    evaluate_f4_lane_selection,
)
from sclass.product.gate import GateOutput, GateState


# =============================================================================
# 1. MUST x TEST-KIND MATRIX TESTS (6 MUSTs x 4 test kinds = 24 tests)
# =============================================================================

# --- PD-F4-001: Deterministic Lane Selection ---

def test_must_matrix_pd_f4_001_happy():
    """PD-F4-001 happy: Micro-eligible inputs deterministically compute MICRO lane."""
    payload = {
        "depth_dimensions": {"planning": "D1", "discovery": "D1", "context": "D1", "verification": "D1"},
        "risk_tier": "LOW", "failure_impact": "LOW", "estimated_files": 2, "modules": 1,
        "rollback_capability": True, "critical_flag": False, "requested_lane": "MICRO",
    }
    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert res.explain["computed_lane"] == "MICRO"


def test_must_matrix_pd_f4_001_gaming():
    """PD-F4-001 gaming: Agent requests MICRO while hiding 5 estimated files; computed lane escalates to STANDARD."""
    payload = {
        "depth_dimensions": {"planning": "D1", "verification": "D1"},
        "risk_tier": "LOW", "failure_impact": "LOW", "estimated_files": 5, "modules": 1,
        "rollback_capability": True, "critical_flag": False, "requested_lane": "MICRO",
    }
    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-F4-002]"


def test_must_matrix_pd_f4_001_no_authority():
    """PD-F4-001 no_authority: Call without caller_authority fails closed with MISSING[PD-F4-001]."""
    payload = {"depth_dimensions": {"planning": "D1"}, "requested_lane": "STANDARD"}
    res = evaluate_f4_lane_selection(payload, caller_authority=None)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F4-001"


def test_must_matrix_pd_f4_001_malformed():
    """PD-F4-001 malformed: Depth dimensions is not a dictionary; safely falls back to defaults."""
    payload = {"depth_dimensions": "invalid_structure", "requested_lane": "STANDARD"}
    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert res.explain["computed_lane"] == "MICRO"


# --- PD-F4-002: Critical Application & Micro Eligibility ---

def test_must_matrix_pd_f4_002_happy():
    """PD-F4-002 happy: D4 verification depth computes CRITICAL; requested CRITICAL matches."""
    payload = {
        "depth_dimensions": {"verification": "D4"},
        "requested_lane": "CRITICAL",
    }
    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert res.explain["computed_lane"] == "CRITICAL"


def test_must_matrix_pd_f4_002_gaming():
    """PD-F4-002 gaming: Computed STANDARD with API change but agent requests MICRO -> MISSING[PD-F4-002]."""
    payload = {
        "depth_dimensions": {"planning": "D1"},
        "api_change": True,
        "requested_lane": "MICRO",
    }
    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-F4-002]"


def test_must_matrix_pd_f4_002_no_authority():
    """PD-F4-002 no_authority: Invalid caller_authority fails closed."""
    payload = {"requested_lane": "CRITICAL"}
    res = evaluate_f4_lane_selection(payload, caller_authority="AGENT_UNVERIFIED")
    assert res.state == GateState.MISSING


def test_must_matrix_pd_f4_002_malformed():
    """PD-F4-002 malformed: Missing requested_lane or unknown lane string fails closed with MISSING[PD-F4-002]."""
    payload = {"depth_dimensions": {"planning": "D1"}}
    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F4-002"


# --- PD-F4-003: Non-reduction of Floor & F1 Obligations ---

def test_must_matrix_pd_f4_003_happy():
    """PD-F4-003 happy: Data model change in STANDARD lane fulfills F1 DDL representation -> SATISFIED."""
    payload = {
        "change_surface": {"databases": 1},
        "f1_artifact_class": "data",
        "f1_required_representation": "DDL",
        "ddl_present": True,
        "requested_lane": "STANDARD",
    }
    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED


def test_must_matrix_pd_f4_003_gaming():
    """PD-F4-003 gaming: Data model change in STANDARD lane with missing DDL fails with MISSING[PD-F1-003]."""
    payload = {
        "change_surface": {"databases": 1},
        "f1_artifact_class": "data",
        "f1_required_representation": "DDL",
        "ddl_present": False,
        "requested_lane": "STANDARD",
    }
    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-F1-003]"


def test_must_matrix_pd_f4_003_no_authority():
    """PD-F4-003 no_authority: Non-qualified caller fails closed."""
    payload = {"f1_artifact_class": "data", "requested_lane": "STANDARD"}
    res = evaluate_f4_lane_selection(payload, caller_authority="UNQUALIFIED")
    assert res.state == GateState.MISSING


def test_must_matrix_pd_f4_003_malformed():
    """PD-F4-003 malformed: DDL absent with missing artifact class still fails closed."""
    payload = {"f1_required_representation": "DDL", "ddl_present": False, "requested_lane": "STANDARD"}
    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING


# --- PD-F4-004: Assignment Budget & Resources ---

def test_must_matrix_pd_f4_004_happy():
    """PD-F4-004 happy: D3 depth budget returns declared triple (8192, EVAL-LARGE, 2)."""
    b = get_depth_budget("D3")
    assert b.max_assignments == 8192
    assert b.adapter_resource_limits_class == "EVAL-LARGE"
    assert b.interruption_budget == 2


def test_must_matrix_pd_f4_004_gaming():
    """PD-F4-004 gaming: Evaluator budget exhausted returns INCONCLUSIVE (MISSING[PD-F4-004])."""
    payload = {"budget_exhausted": True, "requested_lane": "STANDARD"}
    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-F4-004]"


def test_must_matrix_pd_f4_004_no_authority():
    """PD-F4-004 no_authority: Missing caller authority fails closed."""
    payload = {"depth": "D3", "requested_lane": "STANDARD"}
    res = evaluate_f4_lane_selection(payload, caller_authority=None)
    assert res.state == GateState.MISSING


def test_must_matrix_pd_f4_004_malformed():
    """PD-F4-004 malformed: Out of range depth string clamps safely to valid range."""
    b = get_depth_budget("D999")
    assert b.depth == "D5"


# --- PD-F4-005: Escalation Storage & Replay ---

def test_must_matrix_pd_f4_005_happy():
    """PD-F4-005 happy: Replay EngineeringProfile rev 8 reproduces CRITICAL lane."""
    payload = {
        "prior_lane": "STANDARD", "security_change": True, "policy_critical_predicate": True,
        "canonical_profile_revision": 8, "recorded_lane": "CRITICAL",
        "replayed_profile_revision": 8, "requested_lane": "CRITICAL",
    }
    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert res.explain["computed_lane"] == "CRITICAL"
    assert res.explain["replayed_profile_revision"] == 8


def test_must_matrix_pd_f4_005_gaming():
    """PD-F4-005 gaming: Attempting unrecorded escalation without canonical profile revision."""
    payload = {
        "depth_dimensions": {"planning": "D2"},
        "prior_lane": "STANDARD",
        "recorded_lane": "CRITICAL",
        "requested_lane": "STANDARD",
    }
    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert res.explain["computed_lane"] == "STANDARD"


def test_must_matrix_pd_f4_005_no_authority():
    """PD-F4-005 no_authority: Call without authority fails closed."""
    payload = {"canonical_profile_revision": 8, "requested_lane": "CRITICAL"}
    res = evaluate_f4_lane_selection(payload, caller_authority=None)
    assert res.state == GateState.MISSING


def test_must_matrix_pd_f4_005_malformed():
    """PD-F4-005 malformed: Replay function with empty escalations list falls back to default."""
    replayed = replay_lane(8, [], default_lane=Lane.STANDARD)
    assert replayed == Lane.STANDARD


# --- PD-F4-006: Adaptive-depth Precedence & Independence ---

def test_must_matrix_pd_f4_006_happy():
    """PD-F4-006 happy: Policy floor D3 overrides profile-derived D1 -> effective D3."""
    eff_depth, ind_floor = resolve_effective_depth("D1", "D3")
    assert eff_depth == "D3"
    assert "execution-environment separation" in ind_floor


def test_must_matrix_pd_f4_006_gaming():
    """PD-F4-006 gaming: Agent attempts to set policy floor lower than profile-derived depth -> max applies."""
    eff_depth, _ = resolve_effective_depth("D4", "D1")
    assert eff_depth == "D4"


def test_must_matrix_pd_f4_006_no_authority():
    """PD-F4-006 no_authority: Missing caller authority fails closed."""
    payload = {"profile_derived_depth": "D1", "policy_floor": "D3", "requested_lane": "STANDARD"}
    res = evaluate_f4_lane_selection(payload, caller_authority=None)
    assert res.state == GateState.MISSING


def test_must_matrix_pd_f4_006_malformed():
    """PD-F4-006 malformed: Invalid non-numeric depth string defaults to D0 gracefully."""
    eff_depth, _ = resolve_effective_depth("NON_EXISTENT", "INVALID")
    assert eff_depth == "D0"


# =============================================================================
# 2. DISTINCT TESTS FOR F4-T6 REPLAY AND F4-T7 BUDGET TRIPLE (R7-5)
# =============================================================================

def test_f4_t6_engineering_profile_rev8_replay():
    """R7-5 Distinct Test: EngineeringProfile rev 8 replay reproduces CRITICAL output."""
    payload = {
        "prior_lane": "STANDARD", "security_change": True, "policy_critical_predicate": True,
        "canonical_profile_revision": 8, "recorded_lane": "CRITICAL",
        "replayed_profile_revision": 8, "requested_lane": "CRITICAL",
    }
    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert res.explain["replayed_profile_revision"] == 8
    assert res.explain["canonical_profile_revision"] == 8
    assert res.explain["computed_lane"] == "CRITICAL"


def test_f4_t7_exact_budget_triple():
    """R7-5 Distinct Test: Evaluator returns exact budget triple for D3."""
    payload = {
        "depth": "D3", "max_assignments": 8192, "adapter_resource_limits_class": "EVAL-LARGE",
        "interruption_budget": 2, "requested_lane": "STANDARD",
    }
    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    bt = res.explain["budget_triple"]
    assert bt["depth"] == "D3"
    assert bt["max_assignments"] == 8192
    assert bt["adapter_resource_limits_class"] == "EVAL-LARGE"
    assert bt["interruption_budget"] == 2
