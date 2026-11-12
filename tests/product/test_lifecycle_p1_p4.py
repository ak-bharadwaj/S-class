"""Tests for Lifecycle P1 and P4 Foundations & Decomposition Engine."""
from __future__ import annotations

import pytest

from sclass.product.gate import GateOutput, GateState
from sclass.product.lifecycle_p1_p4 import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    DEFAULT_POLICY_CAPS,
    evaluate_pd_ch2_056_discovery_completeness,
    evaluate_pd_ch2_057_skill_depth_precedence,
    evaluate_pd_ch2_029_task_caps,
    evaluate_pd_ch2_031_work_graph_acyclic,
    evaluate_pd_ch2_032_write_set_overlap,
    evaluate_p1_p4_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


# -------------------------------------------------------------------------
# PD-CH2-056: P1 Discovery Completeness
# -------------------------------------------------------------------------

def test_pd_ch2_056_happy_fixture_ch2_t58():
    res = evaluate_pd_ch2_056_discovery_completeness(
        target_snapshot_resolved=True,
        index_coverage_ratio=1.0,
        high_impact_unknowns_resolved=True,
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_056_gaming_fixture_ch2_t57():
    # CH2-T57: unresolvable snapshot / incomplete coverage
    res = evaluate_pd_ch2_056_discovery_completeness(
        target_snapshot_resolved=False,
        index_coverage_ratio=0.75,
        high_impact_unknowns_resolved=True,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-056"
    assert str(res) == "MISSING[PD-CH2-056]"


def test_pd_ch2_056_unresolvable_snapshot_isolated():
    """Mutant kill test: unresolvable snapshot with 100% coverage and resolved unknowns."""
    res = evaluate_pd_ch2_056_discovery_completeness(
        target_snapshot_resolved=False,
        index_coverage_ratio=1.0,
        high_impact_unknowns_resolved=True,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-056"
    assert "Unresolvable target snapshot" in res.detail


def test_pd_ch2_056_incomplete_coverage_isolated():
    """Mutant kill test: resolved snapshot with incomplete coverage ratio."""
    res = evaluate_pd_ch2_056_discovery_completeness(
        target_snapshot_resolved=True,
        index_coverage_ratio=0.85,
        high_impact_unknowns_resolved=True,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-056"
    assert "Incomplete index coverage" in res.detail


def test_pd_ch2_056_missing_unknown_resolution():
    res = evaluate_pd_ch2_056_discovery_completeness(
        target_snapshot_resolved=True,
        index_coverage_ratio=1.0,
        high_impact_unknowns_resolved=False,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-056]"


def test_pd_ch2_056_no_authority():
    res = evaluate_pd_ch2_056_discovery_completeness(
        target_snapshot_resolved=True,
        index_coverage_ratio=1.0,
        high_impact_unknowns_resolved=True,
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-056]"


# -------------------------------------------------------------------------
# PD-CH2-057: P1 Skill Resolution & Digest Pinning
# -------------------------------------------------------------------------

def test_pd_ch2_057_happy_fixture_ch2_t60():
    res = evaluate_pd_ch2_057_skill_depth_precedence(
        skills_resolved=True,
        pinned_skill_digests=["sha256:abc1234"],
        policy_floor_respected=True,
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_057_gaming_fixture_ch2_t59():
    # CH2-T59: pinned_skill_digests omitted
    res = evaluate_pd_ch2_057_skill_depth_precedence(
        skills_resolved=True,
        pinned_skill_digests=[],
        policy_floor_respected=True,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-057"
    assert str(res) == "MISSING[PD-CH2-057]"


def test_pd_ch2_057_policy_floor_violated():
    res = evaluate_pd_ch2_057_skill_depth_precedence(
        skills_resolved=True,
        pinned_skill_digests=["sha256:abc1234"],
        policy_floor_respected=False,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-057]"


def test_pd_ch2_057_no_authority():
    res = evaluate_pd_ch2_057_skill_depth_precedence(
        skills_resolved=True,
        pinned_skill_digests=["sha256:abc1234"],
        policy_floor_respected=True,
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-057]"


# -------------------------------------------------------------------------
# PD-CH2-029: P4 Task-Unit and Task-Count Caps
# -------------------------------------------------------------------------

def test_pd_ch2_029_happy_in_cap():
    res = evaluate_pd_ch2_029_task_caps(
        lane_type="MICRO",
        task_units=4,
        task_count=2,
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_029_gaming_fixture_ch2_t29():
    # CH2-T29: MICRO task of 7 units exceeds 4-unit cap
    res = evaluate_pd_ch2_029_task_caps(
        lane_type="MICRO",
        task_units=7,
        task_count=1,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-029"
    assert str(res) == "MISSING[PD-CH2-029]"


def test_pd_ch2_029_task_count_exceeded():
    res = evaluate_pd_ch2_029_task_caps(
        lane_type="MICRO",
        task_units=2,
        task_count=15,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-029]"


def test_pd_ch2_029_no_authority():
    res = evaluate_pd_ch2_029_task_caps(
        lane_type="MICRO",
        task_units=2,
        task_count=1,
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-029]"


# -------------------------------------------------------------------------
# PD-CH2-031: WorkGraph Acyclic
# -------------------------------------------------------------------------

def test_pd_ch2_031_happy_acyclic():
    res = evaluate_pd_ch2_031_work_graph_acyclic(
        graph_edges={"T1": ["T2"], "T2": ["T3"], "T3": []},
        authority=AUTH,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_031_gaming_fixture_ch2_t31():
    # CH2-T31: cycle
    res = evaluate_pd_ch2_031_work_graph_acyclic(
        graph_edges={"T1": ["T2"], "T2": ["T3"], "T3": ["T1"]},
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-031"
    assert str(res) == "MISSING[PD-CH2-031]"


def test_pd_ch2_031_self_cycle():
    res = evaluate_pd_ch2_031_work_graph_acyclic(
        graph_edges={"T1": ["T1"]},
        authority=AUTH,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-031]"


def test_pd_ch2_031_no_authority():
    res = evaluate_pd_ch2_031_work_graph_acyclic(
        graph_edges={"T1": ["T2"]},
        authority=None,
    )
    assert res.state == GateState.MISSING
    assert str(res) == "MISSING[PD-CH2-031]"


# -------------------------------------------------------------------------
# PD-CH2-032: Write-Set Overlap & Unknown Handling
# -------------------------------------------------------------------------

def test_pd_ch2_032_happy_fixture_ch2_t32_known_overlap():
    tasks = [
        {"task_id": "T1", "declared_write_set": {"fileA.py"}, "serialized": True},
        {"task_id": "T2", "declared_write_set": {"fileA.py"}, "serialized": True},
    ]
    res = evaluate_pd_ch2_032_write_set_overlap(tasks=tasks, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_032_happy_disjoint():
    tasks = [
        {"task_id": "T1", "declared_write_set": {"fileA.py"}, "serialized": False},
        {"task_id": "T2", "declared_write_set": {"fileB.py"}, "serialized": False},
    ]
    res = evaluate_pd_ch2_032_write_set_overlap(tasks=tasks, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_032_gaming_fixture_ch2_t32b_unknown_write_set():
    # Unknown/undeclared write set blocks for human
    tasks = [
        {"task_id": "T1", "declared_write_set": None},
    ]
    res = evaluate_pd_ch2_032_write_set_overlap(tasks=tasks, authority=AUTH)
    assert res.state == GateState.BLOCKED_ON_HUMAN
    assert res.must_id == "PD-CH2-032"
    assert str(res) == "BLOCKED_ON_HUMAN[PD-CH2-032]"


def test_pd_ch2_032_no_authority():
    tasks = [
        {"task_id": "T1", "declared_write_set": {"fileA.py"}},
    ]
    res = evaluate_pd_ch2_032_write_set_overlap(tasks=tasks, authority=None)
    assert res.state == GateState.BLOCKED_ON_HUMAN
    assert res.must_id == "PD-CH2-032"
    assert str(res) == "BLOCKED_ON_HUMAN[PD-CH2-032]"


# -------------------------------------------------------------------------
# Composite Gate Evaluator
# -------------------------------------------------------------------------

def test_p1_p4_composite_gate_happy():
    manifest = {
        "target_snapshot_resolved": True,
        "index_coverage_ratio": 1.0,
        "high_impact_unknowns_resolved": True,
        "skills_resolved": True,
        "pinned_skill_digests": ["sha256:123"],
        "policy_floor_respected": True,
        "lane_type": "MICRO",
        "task_units": 3,
        "task_count": 2,
        "graph_edges": {"T1": ["T2"], "T2": []},
        "tasks": [{"task_id": "T1", "declared_write_set": {"fileA.py"}}],
    }
    res = evaluate_p1_p4_gate(manifest, authority=AUTH)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_p1_p4_composite_gate_fail_closed_no_authority():
    manifest = {}
    res = evaluate_p1_p4_gate(manifest, authority=None)
    assert res.state == GateState.MISSING
    assert len(res.failures) == 5
