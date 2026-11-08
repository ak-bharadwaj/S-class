"""Cross-lane Integration Test Suite for Block 3 (P3 -> P11 + Replay after Invalidation).

Tests at least 12 cross-lane lifecycle chaining scenarios:
  1. P3 Solution Strategy (P3A) -> P4 Work Graph (P1P4)
  2. P4 Task Caps (P1P4) -> P5 Implementation Red-Run (P5)
  3. P5 Implementation Spec (P5) -> P6 Execution Authorization (P6)
  4. P6 Scope Growth Stop (P6) -> P7 Evidence Binding (P7)
  5. P7 Independence Floor (P7) -> P7 Freshness Predicate (P7)
  6. P7 Closure Ownership (P7) -> Negative Result Block
  7. P7 Deterministic Re-run (P7) -> P8 Retry Budget Exhaustion (P3C)
  8. P8 Telemetry (P3C) -> P9 Task Aggregation Findings Closure (P3C)
  9. P9 Findings Closure (P3C) -> P10 Kernel Release Evaluation (P3C)
 10. P10 Release Evaluation (P3C) -> P11 Lifecycle Delivery Flow (P11)
 11. Full End-to-End Linear Lifecycle Pipeline: P3 -> P4 -> P5 -> P6 -> P7 -> P8 -> P9 -> P10 -> P11
 12. Strategy Invalidation and Replay Protocol (Contradiction handling -> ADR invalidation -> Replay)

Every scenario includes a strict no-authority variant that verifies fail-closed gate semantics.
"""
from __future__ import annotations

import pytest

from sclass.product.gate import GateOutput, GateState
from sclass.product.lifecycle_p1_p4 import (
    QUALIFIED_EVALUATOR_BOUNDARY as BOUNDARY_P1P4,
    evaluate_pd_ch2_029_task_caps,
    evaluate_pd_ch2_031_work_graph_acyclic,
)
from sclass.product.lifecycle_p3a import (
    QUALIFIED_EVALUATOR_BOUNDARY as BOUNDARY_P3A,
    evaluate_pd_ch2_013_requirement_coverage,
)
from sclass.product.lifecycle_p3b import (
    QUALIFIED_EVALUATOR_BOUNDARY as BOUNDARY_P3B,
    evaluate_pd_ch2_025_unknown_contradiction_handling,
)
from sclass.product.lifecycle_p3c_p8_p10 import (
    QUALIFIED_EVALUATOR_BOUNDARY as BOUNDARY_P3C,
    evaluate_pd_ch2_026_adr_design_digest_binding,
    evaluate_pd_ch2_051_p8_retry_budget_exhaustion,
    evaluate_pd_ch2_052_p9_task_aggregation_findings_closure,
    evaluate_pd_ch2_053_p10_kernel_release_evaluation,
)
from sclass.product.lifecycle_p5 import (
    QUALIFIED_EVALUATOR_BOUNDARY as BOUNDARY_P5,
    evaluate_pd_ch2_034_red_run_validity,
    evaluate_pd_ch2_035_executable_spec_constraints,
)
from sclass.product.lifecycle_p6 import (
    QUALIFIED_EVALUATOR_BOUNDARY as BOUNDARY_P6,
    evaluate_pd_ch2_037_execution_gate_authorization,
    evaluate_pd_ch2_038_scope_growth_stop,
)
from sclass.product.lifecycle_p7 import (
    QUALIFIED_EVALUATOR_BOUNDARY as BOUNDARY_P7,
    evaluate_pd_ch2_041_evidence_binding,
    evaluate_pd_ch2_043_independence_floor,
    evaluate_pd_ch2_044_freshness_predicate,
    evaluate_pd_ch2_045_closure_ownership,
    evaluate_pd_ch2_050_deterministic_rerun,
)
from sclass.product.lifecycle_p11 import (
    QUALIFIED_EVALUATOR_BOUNDARY as BOUNDARY_P11,
    evaluate_pd_ch2_061_delivery_flow,
)


# ==============================================================================
# Scenario 1: P3 Solution Strategy (P3A) -> P4 Work Graph (P1P4)
# ==============================================================================
def test_scenario_01_p3_to_p4_happy():
    reqs = [{"id": "REQ-1", "semantic_coverage": True, "explicit_applicability": False}]
    r3 = evaluate_pd_ch2_013_requirement_coverage(reqs, authority=BOUNDARY_P3A)
    assert r3.state == GateState.SATISFIED

    graph = {"A": ["B"], "B": ["C"], "C": []}
    r4 = evaluate_pd_ch2_031_work_graph_acyclic(graph, authority=BOUNDARY_P1P4)
    assert r4.state == GateState.SATISFIED


def test_scenario_01_p3_to_p4_no_authority():
    reqs = [{"id": "REQ-1", "semantic_coverage": True, "explicit_applicability": False}]
    r3 = evaluate_pd_ch2_013_requirement_coverage(reqs, authority=None)
    assert r3.state != GateState.SATISFIED
    assert r3.must_id == "PD-CH2-013"

    graph = {"A": ["B"], "B": ["C"], "C": []}
    r4 = evaluate_pd_ch2_031_work_graph_acyclic(graph, authority="AGENT")
    assert r4.state != GateState.SATISFIED
    assert r4.must_id == "PD-CH2-031"


# ==============================================================================
# Scenario 2: P4 Task Caps (P1P4) -> P5 Implementation Red-Run (P5)
# ==============================================================================
def test_scenario_02_p4_to_p5_happy():
    r4 = evaluate_pd_ch2_029_task_caps(lane_type="STANDARD", task_units=4, task_count=2, authority=BOUNDARY_P1P4)
    assert r4.state == GateState.SATISFIED

    r5 = evaluate_pd_ch2_034_red_run_validity(
        adapter_qualified=True,
        run_failed_designed_test=True,
        failure_class="AssertionError",
        designed_class="AssertionError",
        authority=BOUNDARY_P5,
    )
    assert r5.state == GateState.SATISFIED


def test_scenario_02_p4_to_p5_no_authority():
    r4 = evaluate_pd_ch2_029_task_caps(lane_type="STANDARD", task_units=4, task_count=2, authority=None)
    assert r4.state != GateState.SATISFIED
    assert r4.must_id == "PD-CH2-029"

    r5 = evaluate_pd_ch2_034_red_run_validity(
        adapter_qualified=True,
        run_failed_designed_test=True,
        failure_class="AssertionError",
        designed_class="AssertionError",
        authority="INVALID",
    )
    assert r5.state != GateState.SATISFIED
    assert r5.must_id == "PD-CH2-034"


# ==============================================================================
# Scenario 3: P5 Implementation Spec (P5) -> P6 Execution Authorization (P6)
# ==============================================================================
def test_scenario_03_p5_to_p6_happy():
    r5 = evaluate_pd_ch2_035_executable_spec_constraints(
        is_executable_f1_f2=True,
        finite_domain=True,
        is_prose_only=False,
        authority=BOUNDARY_P5,
    )
    assert r5.state == GateState.SATISFIED

    r6 = evaluate_pd_ch2_037_execution_gate_authorization(
        has_execution_gate_auth=True,
        task_id="TSK-1",
        scope="mod1",
        target="mod1.py",
        authority=BOUNDARY_P6,
    )
    assert r6.state == GateState.SATISFIED


def test_scenario_03_p5_to_p6_no_authority():
    r5 = evaluate_pd_ch2_035_executable_spec_constraints(
        is_executable_f1_f2=True,
        finite_domain=True,
        is_prose_only=False,
        authority=None,
    )
    assert r5.state != GateState.SATISFIED
    assert r5.must_id == "PD-CH2-035"

    r6 = evaluate_pd_ch2_037_execution_gate_authorization(
        has_execution_gate_auth=True,
        task_id="TSK-1",
        scope="mod1",
        target="mod1.py",
        authority="UNAUTHORIZED",
    )
    assert r6.state != GateState.SATISFIED
    assert r6.must_id == "PD-CH2-037"


# ==============================================================================
# Scenario 4: P6 Scope Growth Stop (P6) -> P7 Evidence Binding (P7)
# ==============================================================================
def test_scenario_04_p6_to_p7_happy():
    r6 = evaluate_pd_ch2_038_scope_growth_stop(
        is_out_of_scope=False,
        delta_files=["a.py"],
        declared_scope={"a.py"},
        authority=BOUNDARY_P6,
    )
    assert r6.state == GateState.SATISFIED

    r7 = evaluate_pd_ch2_041_evidence_binding(
        evidence_identity_bound=True,
        current_target_bound=True,
        current_step_bound=True,
        authority=BOUNDARY_P7,
    )
    assert r7.state == GateState.SATISFIED


def test_scenario_04_p6_to_p7_no_authority():
    r6 = evaluate_pd_ch2_038_scope_growth_stop(
        is_out_of_scope=False,
        delta_files=["a.py"],
        declared_scope={"a.py"},
        authority=None,
    )
    assert r6.state != GateState.SATISFIED
    assert r6.must_id == "PD-CH2-038"

    r7 = evaluate_pd_ch2_041_evidence_binding(
        evidence_identity_bound=True,
        current_target_bound=True,
        current_step_bound=True,
        authority="AGENT",
    )
    assert r7.state != GateState.SATISFIED
    assert r7.must_id == "PD-CH2-041"


# ==============================================================================
# Scenario 5: P7 Independence Floor (P7) -> P7 Freshness Predicate (P7)
# ==============================================================================
def test_scenario_05_p7_independence_and_freshness_happy():
    r_ind = evaluate_pd_ch2_043_independence_floor(
        independence_level=2,
        required_floor=1,
        authority=BOUNDARY_P7,
    )
    assert r_ind.state == GateState.SATISFIED

    r_fresh = evaluate_pd_ch2_044_freshness_predicate(
        evidence_digest="h1",
        current_code_digest="h1",
        is_stale=False,
        authority=BOUNDARY_P7,
    )
    assert r_fresh.state == GateState.SATISFIED


def test_scenario_05_p7_independence_and_freshness_no_authority():
    r_ind = evaluate_pd_ch2_043_independence_floor(
        independence_level=2,
        required_floor=1,
        authority=None,
    )
    assert r_ind.state != GateState.SATISFIED
    assert r_ind.must_id == "PD-CH2-043"

    r_fresh = evaluate_pd_ch2_044_freshness_predicate(
        evidence_digest="h1",
        current_code_digest="h1",
        is_stale=False,
        authority="AGENT",
    )
    assert r_fresh.state != GateState.SATISFIED
    assert r_fresh.must_id == "PD-CH2-044"


# ==============================================================================
# Scenario 6: P7 Closure Ownership (P7) -> Negative Result Block
# ==============================================================================
def test_scenario_06_p7_closure_ownership_happy_and_negative():
    r_pass = evaluate_pd_ch2_045_closure_ownership(
        kernel_closure_result="CLOSED",
        agent_asserts_closure=False,
        authority=BOUNDARY_P7,
    )
    assert r_pass.state == GateState.SATISFIED

    r_fail = evaluate_pd_ch2_045_closure_ownership(
        kernel_closure_result="FAILED",
        agent_asserts_closure=False,
        authority=BOUNDARY_P7,
    )
    assert r_fail.state == GateState.MISSING
    assert r_fail.must_id == "PD-CH2-045"


def test_scenario_06_p7_closure_ownership_no_authority():
    r = evaluate_pd_ch2_045_closure_ownership(
        kernel_closure_result="CLOSED",
        agent_asserts_closure=False,
        authority=None,
    )
    assert r.state != GateState.SATISFIED
    assert r.must_id == "PD-CH2-045"


# ==============================================================================
# Scenario 7: P7 Deterministic Re-run (P7) -> P8 Retry Budget Exhaustion (P3C)
# ==============================================================================
def test_scenario_07_p7_to_p8_happy():
    r7 = evaluate_pd_ch2_050_deterministic_rerun(
        rerun_results=["PASS", "PASS"],
        authority=BOUNDARY_P7,
    )
    assert r7.state == GateState.SATISFIED

    r8 = evaluate_pd_ch2_051_p8_retry_budget_exhaustion(
        retry_budget_remaining=3,
        earliest_affected_phase="P2",
        routed_phase="P2",
        authority=BOUNDARY_P3C,
    )
    assert r8.state == GateState.SATISFIED


def test_scenario_07_p7_to_p8_no_authority():
    r7 = evaluate_pd_ch2_050_deterministic_rerun(
        rerun_results=["PASS", "PASS"],
        authority=None,
    )
    assert r7.state != GateState.SATISFIED
    assert r7.must_id == "PD-CH2-050"

    r8 = evaluate_pd_ch2_051_p8_retry_budget_exhaustion(
        retry_budget_remaining=3,
        earliest_affected_phase="P2",
        routed_phase="P2",
        authority="INVALID",
    )
    assert r8.state != GateState.SATISFIED
    assert r8.must_id == "PD-CH2-051"


# ==============================================================================
# Scenario 8: P8 Telemetry (P3C) -> P9 Findings Closure (P3C)
# ==============================================================================
def test_scenario_08_p8_to_p9_happy():
    r8 = evaluate_pd_ch2_051_p8_retry_budget_exhaustion(
        retry_budget_remaining=5,
        earliest_affected_phase="P2",
        routed_phase="P2",
        authority=BOUNDARY_P3C,
    )
    assert r8.state == GateState.SATISFIED

    r9 = evaluate_pd_ch2_052_p9_task_aggregation_findings_closure(
        required_p7_tasks=["T1"],
        aggregated_p7_tasks=["T1"],
        open_mandatory_findings=[],
        authority=BOUNDARY_P3C,
    )
    assert r9.state == GateState.SATISFIED


def test_scenario_08_p8_to_p9_no_authority():
    r9 = evaluate_pd_ch2_052_p9_task_aggregation_findings_closure(
        required_p7_tasks=["T1"],
        aggregated_p7_tasks=["T1"],
        open_mandatory_findings=[],
        authority=None,
    )
    assert r9.state != GateState.SATISFIED
    assert r9.must_id == "PD-CH2-052"


# ==============================================================================
# Scenario 9: P9 Findings Closure (P3C) -> P10 Kernel Release Evaluation (P3C)
# ==============================================================================
def test_scenario_09_p9_to_p10_happy():
    r9 = evaluate_pd_ch2_052_p9_task_aggregation_findings_closure(
        required_p7_tasks=["T2"],
        aggregated_p7_tasks=["T2"],
        open_mandatory_findings=[],
        authority=BOUNDARY_P3C,
    )
    assert r9.state == GateState.SATISFIED

    r10 = evaluate_pd_ch2_053_p10_kernel_release_evaluation(
        kernel_release_evaluation="ALLOW",
        product_checks_pass=True,
        authority=BOUNDARY_P3C,
    )
    assert r10.status == "SATISFIED"


def test_scenario_09_p9_to_p10_no_authority():
    r10 = evaluate_pd_ch2_053_p10_kernel_release_evaluation(
        kernel_release_evaluation="ALLOW",
        product_checks_pass=True,
        authority="AGENT",
    )
    assert r10.status != "SATISFIED"
    assert "PD-CH2-053" in r10.status


# ==============================================================================
# Scenario 10: P10 Release Evaluation (P3C) -> P11 Lifecycle Delivery Flow (P11)
# ==============================================================================
def test_scenario_10_p10_to_p11_happy():
    r10 = evaluate_pd_ch2_053_p10_kernel_release_evaluation(
        kernel_release_evaluation="ALLOW",
        product_checks_pass=True,
        authority=BOUNDARY_P3C,
    )
    assert r10.status == "SATISFIED"

    r11 = evaluate_pd_ch2_061_delivery_flow(
        payload={
            "rollback_condition_digest": "rb_valid_digest",
            "entry_predicate_digest": "ep_valid_digest",
            "entry_predicate_stale": False,
            "gate_output_digests": ["gd1"],
            "predecessor_phase_proof_present": True,
        },
        caller_authority=BOUNDARY_P11,
    )
    assert r11.state == GateState.SATISFIED


def test_scenario_10_p10_to_p11_no_authority():
    r11 = evaluate_pd_ch2_061_delivery_flow(
        payload={
            "rollback_condition_digest": "rb_valid_digest",
            "entry_predicate_digest": "ep_valid_digest",
            "entry_predicate_stale": False,
            "gate_output_digests": ["gd1"],
            "predecessor_phase_proof_present": True,
        },
        caller_authority=None,
    )
    assert r11.state != GateState.SATISFIED
    assert r11.must_id == "PD-CH2-061"


# ==============================================================================
# Scenario 11: Full End-to-End Linear Lifecycle Pipeline: P3 -> P11
# ==============================================================================
def test_scenario_11_full_lifecycle_chain_happy():
    # P3: Solution Strategy (P3A)
    reqs = [{"id": "REQ-ALL", "semantic_coverage": True, "explicit_applicability": False}]
    r3 = evaluate_pd_ch2_013_requirement_coverage(reqs, authority=BOUNDARY_P3A)
    assert r3.state == GateState.SATISFIED

    # P4: Decomposition (P1P4)
    r4 = evaluate_pd_ch2_029_task_caps(lane_type="STANDARD", task_units=4, task_count=2, authority=BOUNDARY_P1P4)
    assert r4.state == GateState.SATISFIED

    # P5: Implementation Spec (P5)
    r5 = evaluate_pd_ch2_035_executable_spec_constraints(
        is_executable_f1_f2=True,
        finite_domain=True,
        is_prose_only=False,
        authority=BOUNDARY_P5,
    )
    assert r5.state == GateState.SATISFIED

    # P6: Execution Authorization (P6)
    r6 = evaluate_pd_ch2_037_execution_gate_authorization(
        has_execution_gate_auth=True,
        task_id="TSK-CHAIN",
        scope="mod1",
        target="mod1.py",
        authority=BOUNDARY_P6,
    )
    assert r6.state == GateState.SATISFIED

    # P7: Evidence Binding (P7)
    r7 = evaluate_pd_ch2_041_evidence_binding(
        evidence_identity_bound=True,
        current_target_bound=True,
        current_step_bound=True,
        authority=BOUNDARY_P7,
    )
    assert r7.state == GateState.SATISFIED

    # P8: Monitoring Floor (P3C)
    r8 = evaluate_pd_ch2_051_p8_retry_budget_exhaustion(
        retry_budget_remaining=3,
        earliest_affected_phase="P2",
        routed_phase="P2",
        authority=BOUNDARY_P3C,
    )
    assert r8.state == GateState.SATISFIED

    # P9: Findings Closure (P3C)
    r9 = evaluate_pd_ch2_052_p9_task_aggregation_findings_closure(
        required_p7_tasks=["T_ALL"],
        aggregated_p7_tasks=["T_ALL"],
        open_mandatory_findings=[],
        authority=BOUNDARY_P3C,
    )
    assert r9.state == GateState.SATISFIED

    # P10: Kernel Release Evaluation (P3C)
    r10 = evaluate_pd_ch2_053_p10_kernel_release_evaluation(
        kernel_release_evaluation="ALLOW",
        product_checks_pass=True,
        authority=BOUNDARY_P3C,
    )
    assert r10.status == "SATISFIED"

    # P11: Delivery Flow (P11)
    r11 = evaluate_pd_ch2_061_delivery_flow(
        payload={
            "rollback_condition_digest": "rb_all",
            "entry_predicate_digest": "ep_all",
            "entry_predicate_stale": False,
            "gate_output_digests": ["gd_all"],
            "predecessor_phase_proof_present": True,
        },
        caller_authority=BOUNDARY_P11,
    )
    assert r11.state == GateState.SATISFIED


def test_scenario_11_full_lifecycle_chain_intermediate_authority_break():
    # Intermediate authority break at P6 halts execution fail-closed
    reqs = [{"id": "REQ-ALL", "semantic_coverage": True, "explicit_applicability": False}]
    r3 = evaluate_pd_ch2_013_requirement_coverage(reqs, authority=BOUNDARY_P3A)
    assert r3.state == GateState.SATISFIED

    r6_unauth = evaluate_pd_ch2_037_execution_gate_authorization(
        has_execution_gate_auth=True,
        task_id="TSK-CHAIN",
        scope="mod1",
        target="mod1.py",
        authority=None,
    )
    assert r6_unauth.state != GateState.SATISFIED
    assert r6_unauth.must_id == "PD-CH2-037"


# ==============================================================================
# Scenario 12: Strategy Invalidation Protocol and Replay Re-evaluation
# ==============================================================================
def test_scenario_12_invalidation_and_replay_happy():
    # 1. Contradiction detected -> triggers invalidation protocol
    inv_res = evaluate_pd_ch2_025_unknown_contradiction_handling(
        has_unknown_contradiction=True,
        human_waiver_attempted=False,
        authority=BOUNDARY_P3B,
    )
    assert inv_res.state == GateState.MISSING
    assert inv_res.must_id == "PD-CH2-025"

    # 2. Downstream ADR check detects stale invalidated artifact -> returns MISSING
    stale_adrs = [{"id": "ADR-001", "digest": "sha256:111", "lint_passed": True, "is_stale": True}]
    r_stale = evaluate_pd_ch2_026_adr_design_digest_binding(stale_adrs, authority=BOUNDARY_P3C)
    assert r_stale.state == GateState.MISSING
    assert r_stale.must_id == "PD-CH2-026"

    # 3. Replay with fresh re-evaluated ADR and resolved contradiction restores SATISFIED
    inv_resolved = evaluate_pd_ch2_025_unknown_contradiction_handling(
        has_unknown_contradiction=False,
        human_waiver_attempted=False,
        authority=BOUNDARY_P3B,
    )
    assert inv_resolved.state == GateState.SATISFIED

    fresh_adrs = [{"id": "ADR-002", "digest": "sha256:222", "lint_passed": True, "is_stale": False}]
    r_fresh = evaluate_pd_ch2_026_adr_design_digest_binding(fresh_adrs, authority=BOUNDARY_P3C)
    assert r_fresh.state == GateState.SATISFIED


def test_scenario_12_invalidation_protocol_no_authority():
    # Invalidation evaluation without authority fails closed
    inv_res = evaluate_pd_ch2_025_unknown_contradiction_handling(
        has_unknown_contradiction=False,
        human_waiver_attempted=False,
        authority=None,
    )
    assert inv_res.state != GateState.SATISFIED
    assert inv_res.must_id == "PD-CH2-025"
