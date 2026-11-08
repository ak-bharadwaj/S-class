"""Tests for F4 Lane Selection Engine (PD-F4-001 through PD-F4-006).

Verifies:
- PD-F4-001: Deterministic lane computation over canonical dimensions.
- PD-F4-002: Critical lane rules, Micro eligibility rules, lower requested lane rejection.
- PD-F4-003: Retention of depth floor and F1 representation obligations.
- PD-F4-004: Assignment budget lookup and exhaustion behavior.
- PD-F4-005: Replayable escalation via profile revision or authorized Decision.
- PD-F4-006: Adaptive-depth precedence (policy floor override) and independence mapping.
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
# 1. Traceability & Conformance Tests (PD-F4-001..PD-F4-006)
# =============================================================================

def test_pd_f4_001_micro_eligible_happy_fixture_f4_t1():
    """F4-T1: Micro profile with requested MICRO -> computed MICRO, SATISFIED."""
    payload = {
        "depth_dimensions": {
            "planning": "D1", "discovery": "D1", "context": "D1", "domain_model": "D0",
            "data_model": "D0", "architecture": "D0", "testing": "D1", "verification": "D1",
            "recovery": "D0", "independence": "D0",
        },
        "risk_tier": "LOW",
        "failure_impact": "LOW",
        "regulatory_sensitivity": "NONE",
        "required_independence": "NONE",
        "irreversibility": False,
        "rollback_capability": True,
        "estimated_files": 2,
        "modules": 1,
        "change_surface": {
            "databases": 0, "external_integrations": 0, "deployment_surfaces": 0,
            "apis": 0, "schemas": 0,
        },
        "security_sensitivity": "NONE",
        "external_effects": {
            "external_systems": 0, "user_visible_effects": False,
            "financial_effects": False, "security_effects": False,
        },
        "critical_flag": False,
        "requested_lane": "MICRO",
    }
    lane = compute_lane(payload)
    assert lane == Lane.MICRO

    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_f4_001_critical_by_depth_happy_fixture_f4_t2():
    """F4-T2: Verification depth D4 -> computed CRITICAL, SATISFIED."""
    payload = {
        "depth_dimensions": {
            "planning": "D2", "discovery": "D2", "context": "D2", "domain_model": "D3",
            "data_model": "D3", "architecture": "D3", "testing": "D3", "verification": "D4",
            "recovery": "D3", "independence": "D3",
        },
        "critical_flag": False,
        "requested_lane": "CRITICAL",
    }
    lane = compute_lane(payload)
    assert lane == Lane.CRITICAL

    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_f4_002_lower_requested_lane_rejection_gaming_fixture_f4_t3():
    """F4-T3: Computed STANDARD, requested MICRO -> MISSING[PD-F4-002]."""
    payload = {
        "depth_dimensions": {
            "planning": "D1", "discovery": "D1", "context": "D1", "domain_model": "D1",
            "data_model": "D0", "architecture": "D1", "testing": "D1", "verification": "D1",
            "recovery": "D1", "independence": "D0",
        },
        "risk_tier": "LOW",
        "failure_impact": "LOW",
        "change_surface": {
            "apis": 1, "databases": 0, "schemas": 0,
            "external_integrations": 0, "deployment_surfaces": 0,
        },
        "external_effects": {
            "external_systems": 0, "user_visible_effects": False,
            "financial_effects": False, "security_effects": False,
        },
        "security_sensitivity": "NONE",
        "critical_flag": False,
        "requested_lane": "MICRO",
    }
    lane = compute_lane(payload)
    assert lane == Lane.STANDARD

    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F4-002"
    assert str(res) == "MISSING[PD-F4-002]"


def test_pd_f4_003_f1_obligation_retention_happy_fixture_f4_t4():
    """F4-T4 Happy: Required DDL present -> SATISFIED."""
    payload = {
        "depth_dimensions": {
            "planning": "D1", "discovery": "D1", "context": "D1", "domain_model": "D1",
            "data_model": "D1", "architecture": "D1", "testing": "D1", "verification": "D1",
            "recovery": "D1", "independence": "D0",
        },
        "risk_tier": "LOW",
        "failure_impact": "LOW",
        "change_surface": {
            "databases": 1, "apis": 0, "schemas": 0,
            "external_integrations": 0, "deployment_surfaces": 0,
        },
        "external_effects": {
            "external_systems": 0, "user_visible_effects": False,
            "financial_effects": False, "security_effects": False,
        },
        "security_sensitivity": "NONE",
        "critical_flag": False,
        "f1_artifact_class": "data",
        "f1_required_representation": "DDL",
        "requested_lane": "STANDARD",
        "ddl_present": True,
    }
    lane = compute_lane(payload)
    assert lane == Lane.STANDARD

    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_f4_003_f1_obligation_missing_ddl_gaming_fixture_f4_t4():
    """F4-T4 Gaming: Required DDL absent -> MISSING[PD-F1-003]."""
    payload = {
        "depth_dimensions": {
            "planning": "D1", "discovery": "D1", "context": "D1", "domain_model": "D1",
            "data_model": "D1", "architecture": "D1", "testing": "D1", "verification": "D1",
            "recovery": "D1", "independence": "D0",
        },
        "risk_tier": "LOW",
        "failure_impact": "LOW",
        "change_surface": {
            "databases": 1, "apis": 0, "schemas": 0,
            "external_integrations": 0, "deployment_surfaces": 0,
        },
        "external_effects": {
            "external_systems": 0, "user_visible_effects": False,
            "financial_effects": False, "security_effects": False,
        },
        "security_sensitivity": "NONE",
        "critical_flag": False,
        "f1_artifact_class": "data",
        "f1_required_representation": "DDL",
        "requested_lane": "STANDARD",
        "ddl_present": False,
    }
    lane = compute_lane(payload)
    assert lane == Lane.STANDARD

    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F1-003"
    assert str(res) == "MISSING[PD-F1-003]"


def test_pd_f4_004_depth_budget_table_fixture_f4_t7():
    """F4-T7: D3 budget table lookup -> 8192, EVAL-LARGE, 2."""
    budget = get_depth_budget("D3")
    assert budget.max_assignments == 8192
    assert budget.adapter_resource_limits_class == "EVAL-LARGE"
    assert budget.interruption_budget == 2

    # All depths in table
    assert BUDGET_TABLE["D0"].max_assignments == 32
    assert BUDGET_TABLE["D1"].max_assignments == 128
    assert BUDGET_TABLE["D2"].max_assignments == 1024
    assert BUDGET_TABLE["D3"].max_assignments == 8192
    assert BUDGET_TABLE["D4"].max_assignments == 65536
    assert BUDGET_TABLE["D5"].max_assignments == 262144

    # Budget exhaustion yields INCONCLUSIVE / MISSING[PD-F4-004]
    payload = {
        "depth_dimensions": {"planning": "D3"},
        "requested_lane": "STANDARD",
        "budget_exhausted": True,
    }
    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F4-004"


def test_pd_f4_005_replayable_escalation_fixture_f4_t6():
    """F4-T6: Replayable escalation via profile revision 8 records CRITICAL."""
    record = record_lane_escalation(
        canonical_profile_revision=8,
        prior_lane="STANDARD",
        escalated_lane="CRITICAL",
        reason="security-sensitive change causes policy critical flag",
        authorized_decision="DECISION-SEC-01",
    )
    assert record.canonical_profile_revision == 8
    assert record.escalated_lane == "CRITICAL"

    replayed = replay_lane(replayed_profile_revision=8, escalations=[record])
    assert replayed == Lane.CRITICAL

    # Gate evaluation replay
    payload = {
        "canonical_profile_revision": 8,
        "replayed_profile_revision": 8,
        "recorded_lane": "CRITICAL",
        "requested_lane": "CRITICAL",
    }
    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED


def test_pd_f4_006_policy_floor_override_fixture_f4_t5():
    """F4-T5: Profile derived depth D1, policy floor D3 -> effective depth D3."""
    eff_depth, ind_floor = resolve_effective_depth(profile_derived_depth="D1", policy_floor="D3")
    assert eff_depth == "D3"
    assert "execution-environment separation" in ind_floor

    payload = {
        "profile_derived_depth": "D1",
        "policy_floor": "D3",
        "requested_lane": "STANDARD",
    }
    res = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED


# =============================================================================
# 2. Security & Authority Hardening Tests
# =============================================================================

def test_unauthorized_caller_rejected():
    """Fails closed when caller_authority is omitted or incorrect."""
    payload = {"requested_lane": "STANDARD"}
    res_none = evaluate_f4_lane_selection(payload, caller_authority=None)
    assert res_none.state == GateState.MISSING
    assert res_none.must_id == "PD-F4-001"

    res_agent = evaluate_f4_lane_selection(payload, caller_authority="AGENT")
    assert res_agent.state == GateState.MISSING
    assert res_agent.must_id == "PD-F4-001"


def test_missing_or_malformed_requested_lane():
    """Fails closed when requested_lane is missing or invalid."""
    res_missing = evaluate_f4_lane_selection({}, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res_missing.state == GateState.MISSING
    assert res_missing.must_id == "PD-F4-002"

    res_bad = evaluate_f4_lane_selection({"requested_lane": "SUPER_LANE"}, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res_bad.state == GateState.MISSING
    assert res_bad.must_id == "PD-F4-002"


# =============================================================================
# 3. Mutation & Branch Coverage Tests
# =============================================================================

def test_mutations_micro_eligibility_branches():
    """Tests all individual Micro disqualification branches."""
    base = {
        "depth_dimensions": {"planning": "D1"},
        "risk_tier": "LOW",
        "failure_impact": "LOW",
        "regulatory_sensitivity": "NONE",
        "required_independence": "NONE",
        "irreversibility": False,
        "rollback_capability": True,
        "estimated_files": 1,
        "modules": 1,
        "security_sensitivity": "NONE",
        "change_surface": {},
        "external_effects": {},
        "critical_flag": False,
    }
    assert compute_lane(base) == Lane.MICRO

    # Mutate risk_tier
    m = dict(base, risk_tier="HIGH")
    assert compute_lane(m) == Lane.STANDARD

    # Mutate failure_impact
    m = dict(base, failure_impact="MEDIUM")
    assert compute_lane(m) == Lane.STANDARD

    # Mutate regulatory_sensitivity
    m = dict(base, regulatory_sensitivity="HIGH")
    assert compute_lane(m) == Lane.STANDARD

    # Mutate required_independence
    m = dict(base, required_independence="SEPARATE_MODEL")
    assert compute_lane(m) == Lane.STANDARD

    # Mutate irreversibility
    m = dict(base, irreversibility=True)
    assert compute_lane(m) == Lane.STANDARD

    # Mutate rollback_capability
    m = dict(base, rollback_capability=False)
    assert compute_lane(m) == Lane.STANDARD

    # Mutate estimated_files (> 2)
    m = dict(base, estimated_files=3)
    assert compute_lane(m) == Lane.STANDARD

    # Mutate modules (> 1)
    m = dict(base, modules=2)
    assert compute_lane(m) == Lane.STANDARD

    # Mutate security_sensitivity
    m = dict(base, security_sensitivity="CRITICAL")
    assert compute_lane(m) == Lane.STANDARD

    # Mutate change_surface: databases
    m = dict(base, change_surface={"databases": 1})
    assert compute_lane(m) == Lane.STANDARD

    # Mutate external_effects: external_systems
    m = dict(base, external_effects={"external_systems": 1})
    assert compute_lane(m) == Lane.STANDARD


def test_mutations_critical_branches():
    """Tests all critical escalation branches."""
    base = {"depth_dimensions": {"planning": "D2"}, "requested_lane": "CRITICAL"}

    # Dimension >= D4 triggers CRITICAL
    assert compute_lane({"depth_dimensions": {"verification": "D4"}}) == Lane.CRITICAL
    assert compute_lane({"depth_dimensions": {"testing": "D5"}}) == Lane.CRITICAL

    # critical_flag triggers CRITICAL
    assert compute_lane({"depth_dimensions": {"planning": "D1"}, "critical_flag": True}) == Lane.CRITICAL

    # security_change triggers CRITICAL
    assert compute_lane({"depth_dimensions": {"planning": "D1"}, "security_change": True}) == Lane.CRITICAL

    # policy_critical_predicate triggers CRITICAL
    assert compute_lane({"depth_dimensions": {"planning": "D1"}, "policy_critical_predicate": True}) == Lane.CRITICAL
