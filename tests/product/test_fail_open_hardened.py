import pytest
from sclass.product.gate import GateState, GateOutput

from sclass.product.threat_eval_regression_gate import (
    evaluate_pd_ch9_003_security_promotion_gate,
    evaluate_pd_ch9_010_promotion_blockers,
    evaluate_pd_ch9_005_data_retention_policy,
    evaluate_b9_a_gate,
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B9,
)
from sclass.product.knowledge_package_quarantine import (
    evaluate_pd_ch6_010_quarantine_conditions,
    evaluate_b6_a_gate,
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B6,
)
from sclass.product.trust_model import check_structured_conflict
from sclass.product.artifacts import evaluate_f1_representation
from sclass.product.f4_lane_selection import evaluate_f4_lane_selection
from sclass.product.adapter_qualification_contract import (
    evaluate_pd_f10_006_independent_verification,
    evaluate_b4_a_gate,
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B4A,
)
from sclass.product.adapter_diff_spec_anchors import (
    evaluate_pd_f10_007_differential_detection,
    evaluate_b4_b_gate,
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B4B,
)
from sclass.product.enforcement_workspace_gate import (
    evaluate_pd_ch8_008_prevention_boundary,
    evaluate_pd_ch8_010_out_of_band_edits,
    evaluate_pd_ch8_013_budget_exhaustion_ledger,
    evaluate_b5_gate,
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B5,
)
from sclass.product.execution_flow_testinput import (
    evaluate_pd_ch3_010_flow_baseline_binding,
    evaluate_pd_ch3_011_adapter_qualification_disclosure,
    evaluate_pd_ch3_012_ux_interruption_budget_authority,
    evaluate_b4_d_gate,
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B4D,
)
from sclass.product.isolation_claims import (
    evaluate_pd_ch4_010_test_input_write_isolation,
    evaluate_pd_ch4_006_canonical_closure_vs_prose,
    evaluate_b4_e_gate,
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B4E,
)
from sclass.product.lifecycle_phase_admission import (
    evaluate_pd_ch3_003_clarification_scope_entry,
    evaluate_pd_ch3_006_external_tool_candidate_trust,
    evaluate_b4_c_gate,
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B4C,
)
from sclass.product.lifecycle_p0a import evaluate_p0a_gate, QUALIFIED_EVALUATOR_BOUNDARY as AUTH_P0A
from sclass.product.lifecycle_p0b import evaluate_p0b_gate, QUALIFIED_EVALUATOR_BOUNDARY as AUTH_P0B
from sclass.product.lifecycle_p11 import evaluate_p11_gate, QUALIFIED_EVALUATOR_BOUNDARY as AUTH_P11
from sclass.product.lifecycle_p1_p4 import evaluate_p1_p4_gate, QUALIFIED_EVALUATOR_BOUNDARY as AUTH_P1P4
from sclass.product.lifecycle_p3b import evaluate_p3b_gate, QUALIFIED_EVALUATOR_BOUNDARY as AUTH_P3B
from sclass.product.lifecycle_p3c_p8_p10 import evaluate_p3c_p8_p10_gate, QUALIFIED_EVALUATOR_BOUNDARY as AUTH_P3C
from sclass.product.lifecycle_p5 import evaluate_p5_gate, QUALIFIED_EVALUATOR_BOUNDARY as AUTH_P5
from sclass.product.lifecycle_p6 import evaluate_p6_gate, QUALIFIED_EVALUATOR_BOUNDARY as AUTH_P6
from sclass.product.lifecycle_p7 import evaluate_p7_gate, QUALIFIED_EVALUATOR_BOUNDARY as AUTH_P7


INVALID_VALUES = [None, "False", 0, 1, [], {}]


# -----------------------------------------------------------------------------
# 1. Block 9 Evaluators
# -----------------------------------------------------------------------------
def test_pd_ch9_003_fail_closed_omitted_and_invalid():
    res = evaluate_pd_ch9_003_security_promotion_gate(authority=AUTH_B9)
    assert res.state == GateState.MISSING

    for val in INVALID_VALUES:
        res = evaluate_pd_ch9_003_security_promotion_gate(failed_security_scan=val, authority=AUTH_B9)
        assert res.state == GateState.MISSING
        res = evaluate_pd_ch9_003_security_promotion_gate(environment_mismatch=val, authority=AUTH_B9)
        assert res.state == GateState.MISSING
        res = evaluate_pd_ch9_003_security_promotion_gate(sandbox_trust_root_failure=val, authority=AUTH_B9)
        assert res.state == GateState.MISSING


def test_pd_ch9_010_fail_closed_omitted_and_invalid():
    res = evaluate_pd_ch9_010_promotion_blockers(authority=AUTH_B9)
    assert res.state == GateState.MISSING

    for val in INVALID_VALUES:
        res = evaluate_pd_ch9_010_promotion_blockers(critical_regression=val, unqualified_data_handling=False, authority=AUTH_B9)
        assert res.state == GateState.MISSING
        res = evaluate_pd_ch9_010_promotion_blockers(critical_regression=False, unqualified_data_handling=val, authority=AUTH_B9)
        assert res.state == GateState.MISSING


def test_pd_ch9_005_fail_closed_omitted_and_invalid():
    res = evaluate_pd_ch9_005_data_retention_policy(authority=AUTH_B9)
    assert res.state == GateState.MISSING

    for val in INVALID_VALUES:
        res = evaluate_pd_ch9_005_data_retention_policy(within_retention_limit=val, has_policy_reference=True, authority=AUTH_B9)
        assert res.state == GateState.MISSING
        res = evaluate_pd_ch9_005_data_retention_policy(within_retention_limit=True, has_policy_reference=val, authority=AUTH_B9)
        assert res.state == GateState.MISSING


def test_b9_a_gate_empty():
    res = evaluate_b9_a_gate({}, authority=AUTH_B9)
    assert len(res) == 6
    assert all(out.state == GateState.MISSING for out in res.values())


# -----------------------------------------------------------------------------
# 2. Block 6 Quarantine Evaluators
# -----------------------------------------------------------------------------
def test_pd_ch6_010_fail_closed_omitted_and_invalid():
    res = evaluate_pd_ch6_010_quarantine_conditions(authority=AUTH_B6)
    assert res.state == GateState.MISSING

    for val in INVALID_VALUES:
        res = evaluate_pd_ch6_010_quarantine_conditions(unknown_checks=val, authority=AUTH_B6)
        assert res.state == GateState.MISSING
        res = evaluate_pd_ch6_010_quarantine_conditions(weakened_floors=val, authority=AUTH_B6)
        assert res.state == GateState.MISSING
        res = evaluate_pd_ch6_010_quarantine_conditions(invalid_signature=val, authority=AUTH_B6)
        assert res.state == GateState.MISSING
        res = evaluate_pd_ch6_010_quarantine_conditions(unsupported_compatibility=val, authority=AUTH_B6)
        assert res.state == GateState.MISSING


def test_b6_a_gate_empty():
    res = evaluate_b6_a_gate({}, authority=AUTH_B6)
    assert len(res) == 6
    assert all(out.state == GateState.MISSING for out in res.values())


# -----------------------------------------------------------------------------
# 3. Trust Model Structured Conflict
# -----------------------------------------------------------------------------
def test_check_structured_conflict_hostile_and_invalid():
    for val in [None, 0, 1, 42, "", "pass", {}, [], ["a"]]:
        out = check_structured_conflict(val, val)
        assert out.state in (GateState.MISSING, GateState.BLOCKED_ON_HUMAN)

    out = check_structured_conflict({"__proto__": "admin"}, {"__proto__": "admin"})
    assert out.state in (GateState.MISSING, GateState.BLOCKED_ON_HUMAN)

    out = check_structured_conflict({"$where": "true"}, {"$where": "true"})
    assert out.state in (GateState.MISSING, GateState.BLOCKED_ON_HUMAN)

    out = check_structured_conflict({"admin": True, "authority": "root"}, {"admin": True, "authority": "root"})
    assert out.state in (GateState.MISSING, GateState.BLOCKED_ON_HUMAN)


# -----------------------------------------------------------------------------
# 4. Artifacts F1 Representation
# -----------------------------------------------------------------------------
def test_evaluate_f1_representation_hostile_and_empty():
    for val in [None, "", {}, {"random_key": 123}, {"hostile": True}]:
        out = evaluate_f1_representation(val)
        assert out.state == GateState.MISSING


# -----------------------------------------------------------------------------
# 5. F4 Lane Selection
# -----------------------------------------------------------------------------
def test_evaluate_f4_lane_selection_hostile_and_empty():
    for val in [None, "", 0, 1, {}, {"irrelevant": True}]:
        out = evaluate_f4_lane_selection(val)
        assert out.state == GateState.MISSING


# -----------------------------------------------------------------------------
# 6. Block 4 Lane A Evaluators
# -----------------------------------------------------------------------------
def test_pd_f10_006_fail_closed_omitted_and_invalid():
    res = evaluate_pd_f10_006_independent_verification(authority=AUTH_B4A)
    assert res.state == GateState.MISSING

    for val in INVALID_VALUES:
        res = evaluate_pd_f10_006_independent_verification(is_critical_lane=val, authority=AUTH_B4A)
        assert res.state == GateState.MISSING


def test_b4_a_gate_empty():
    res = evaluate_b4_a_gate({}, authority=AUTH_B4A)
    assert len(res) == 6
    assert all(out.state == GateState.MISSING for out in res.values())


# -----------------------------------------------------------------------------
# 7. Block 4 Lane B Evaluators
# -----------------------------------------------------------------------------
def test_pd_f10_007_fail_closed_omitted_and_invalid():
    res = evaluate_pd_f10_007_differential_detection(authority=AUTH_B4B)
    assert res.state == GateState.MISSING

    res = evaluate_pd_f10_007_differential_detection(None, None, authority=AUTH_B4B)
    assert res.state == GateState.MISSING


def test_b4_b_gate_empty():
    res = evaluate_b4_b_gate({}, authority=AUTH_B4B)
    assert len(res) == 6
    assert all(out.state == GateState.MISSING for out in res.values())


# -----------------------------------------------------------------------------
# 8. Block 5 Evaluators
# -----------------------------------------------------------------------------
def test_b5_evaluators_fail_closed_omitted_and_invalid():
    for val in INVALID_VALUES:
        assert evaluate_pd_ch8_008_prevention_boundary(prevention_claimed=val, authority=AUTH_B5).state == GateState.MISSING
        assert evaluate_pd_ch8_010_out_of_band_edits(out_of_band_edits_detected=val, authority=AUTH_B5).state == GateState.MISSING
        assert evaluate_pd_ch8_013_budget_exhaustion_ledger(budget_exhausted=val, authority=AUTH_B5).state == GateState.MISSING


def test_b5_gate_empty():
    res = evaluate_b5_gate({}, authority=AUTH_B5)
    assert len(res) == 6
    assert all(out.state == GateState.MISSING for out in res.values())


# -----------------------------------------------------------------------------
# 9. Block 4 Lane D Evaluators
# -----------------------------------------------------------------------------
def test_b4_d_evaluators_fail_closed_omitted_and_invalid():
    # flow_type omitted or not str
    for val in [None, 0, 1, [], {}]:
        assert evaluate_pd_ch3_010_flow_baseline_binding(flow_type=val, authority=AUTH_B4D).state == GateState.MISSING

    # flow requiring baseline with omitted or invalid baseline
    for val in [None, "", 0, 1, [], {}]:
        assert evaluate_pd_ch3_010_flow_baseline_binding(flow_type="MIGRATION", baseline_digest=val, authority=AUTH_B4D).state == GateState.MISSING

    for val in INVALID_VALUES:
        assert evaluate_pd_ch3_010_flow_baseline_binding(flow_type="MIGRATION", baseline_digest="sha256:abc", rollback_inputs_bound=val, authority=AUTH_B4D).state == GateState.MISSING
        assert evaluate_pd_ch3_010_flow_baseline_binding(flow_type="MIGRATION", baseline_digest="sha256:abc", verification_inputs_bound=val, authority=AUTH_B4D).state == GateState.MISSING

    # adapter disclosure
    for val in [None, "", 0, 1, [], {}]:
        assert evaluate_pd_ch3_011_adapter_qualification_disclosure(adapter_identity=val, is_qualified=True, marked_supported=True, authority=AUTH_B4D).state == GateState.MISSING

    for val in INVALID_VALUES:
        assert evaluate_pd_ch3_011_adapter_qualification_disclosure(adapter_identity="tool", is_qualified=val, marked_supported=True, authority=AUTH_B4D).state == GateState.MISSING
        assert evaluate_pd_ch3_011_adapter_qualification_disclosure(adapter_identity="tool", is_qualified=True, marked_supported=val, authority=AUTH_B4D).state == GateState.MISSING

    # ux interruption budget
    for val in INVALID_VALUES:
        assert evaluate_pd_ch3_012_ux_interruption_budget_authority(human_decision_required=val, authority=AUTH_B4D).state == GateState.MISSING


def test_b4_d_gate_empty():
    res = evaluate_b4_d_gate({}, authority=AUTH_B4D)
    assert len(res) == 6
    assert all(out.state == GateState.MISSING for out in res.values())


# -----------------------------------------------------------------------------
# 10. Block 4 Lane E Evaluators
# -----------------------------------------------------------------------------
def test_b4_e_evaluators_fail_closed_omitted_and_invalid():
    assert evaluate_pd_ch4_010_test_input_write_isolation(authority=AUTH_B4E).state == GateState.MISSING
    assert evaluate_pd_ch4_010_test_input_write_isolation(None, None, authority=AUTH_B4E).state == GateState.MISSING

    for val in INVALID_VALUES:
        assert evaluate_pd_ch4_006_canonical_closure_vs_prose(agent_prose_done_claim=val, authority=AUTH_B4E).state == GateState.MISSING


def test_b4_e_gate_empty():
    res = evaluate_b4_e_gate({}, authority=AUTH_B4E)
    assert len(res) == 6
    assert all(out.state == GateState.MISSING for out in res.values())


# -----------------------------------------------------------------------------
# 11. Block 4 Lane C Evaluators
# -----------------------------------------------------------------------------
def test_b4_c_evaluators_fail_closed_omitted_and_invalid():
    for val in INVALID_VALUES:
        assert evaluate_pd_ch3_003_clarification_scope_entry(scope_changed=val, authority=AUTH_B4C).state == GateState.MISSING

    # tool identity invalid
    for val in [None, 0, 1, [], {}]:
        assert evaluate_pd_ch3_006_external_tool_candidate_trust(tool_identity=val, qualification_recorded=True, claimed_authoritative=False, authority=AUTH_B4C).state == GateState.MISSING

    # claimed authoritative without qualification
    assert evaluate_pd_ch3_006_external_tool_candidate_trust(tool_identity="tool", qualification_recorded=False, claimed_authoritative=True, authority=AUTH_B4C).state == GateState.MISSING


def test_b4_c_gate_empty():
    res = evaluate_b4_c_gate({}, authority=AUTH_B4C)
    assert len(res) == 6
    assert all(out.state == GateState.MISSING for out in res.values())


# -----------------------------------------------------------------------------
# 12. Lifecycle Composite Gates
# -----------------------------------------------------------------------------
def test_all_lifecycle_composite_gates_empty():
    # P0A
    res_p0a = evaluate_p0a_gate({}, authority=AUTH_P0A)
    assert all(out.state == GateState.MISSING for out in res_p0a.values())

    # P11
    res_p11 = evaluate_p11_gate({}, authority=AUTH_P11)
    assert res_p11.state == GateState.MISSING

    # P0B, P1_P4, P3B, P3C, P5, P6, P7
    assert evaluate_p0b_gate({}, authority=AUTH_P0B).state == GateState.MISSING
    assert evaluate_p1_p4_gate({}, authority=AUTH_P1P4).state == GateState.MISSING
    assert evaluate_p3b_gate({}, authority=AUTH_P3B).state == GateState.MISSING
    assert evaluate_p3c_p8_p10_gate({}, authority=AUTH_P3C).state == GateState.MISSING
    assert evaluate_p5_gate({}, authority=AUTH_P5).state == GateState.MISSING
    assert evaluate_p6_gate({}, authority=AUTH_P6).state == GateState.MISSING
    assert evaluate_p7_gate({}, authority=AUTH_P7).state == GateState.MISSING


# -----------------------------------------------------------------------------
# 13. Mutation Tests Killing "restore default False"
# -----------------------------------------------------------------------------
def test_mutation_killing_restore_default_false():
    evaluators_with_no_args = [
        (evaluate_pd_ch9_003_security_promotion_gate, {"authority": AUTH_B9}),
        (evaluate_pd_ch9_010_promotion_blockers, {"authority": AUTH_B9}),
        (evaluate_pd_ch9_005_data_retention_policy, {"authority": AUTH_B9}),
        (evaluate_pd_ch6_010_quarantine_conditions, {"authority": AUTH_B6}),
        (evaluate_pd_f10_006_independent_verification, {"authority": AUTH_B4A}),
        (evaluate_pd_f10_007_differential_detection, {"authority": AUTH_B4B}),
        (evaluate_pd_ch8_008_prevention_boundary, {"authority": AUTH_B5}),
        (evaluate_pd_ch8_010_out_of_band_edits, {"authority": AUTH_B5}),
        (evaluate_pd_ch8_013_budget_exhaustion_ledger, {"authority": AUTH_B5}),
        (evaluate_pd_ch3_010_flow_baseline_binding, {"authority": AUTH_B4D}),
        (evaluate_pd_ch3_011_adapter_qualification_disclosure, {"authority": AUTH_B4D}),
        (evaluate_pd_ch3_012_ux_interruption_budget_authority, {"authority": AUTH_B4D}),
        (evaluate_pd_ch4_010_test_input_write_isolation, {"authority": AUTH_B4E}),
        (evaluate_pd_ch4_006_canonical_closure_vs_prose, {"authority": AUTH_B4E}),
        (evaluate_pd_ch3_003_clarification_scope_entry, {"authority": AUTH_B4C}),
        (evaluate_pd_ch3_006_external_tool_candidate_trust, {"authority": AUTH_B4C}),
    ]

    for fn, kwargs in evaluators_with_no_args:
        out = fn(**kwargs)
        assert out.state in (GateState.MISSING, GateState.BLOCKED_ON_HUMAN), (
            f"MUTATION SURVIVED: {fn.__name__} returned {out.state} with no evidence args! Must be MISSING/BLOCKED."
        )
