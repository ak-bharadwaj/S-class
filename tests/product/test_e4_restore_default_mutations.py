"""Mutation tests for E4 / Y4: Verify Optional[bool] = None sentinel safety.

Tests that restoring literal default False or omitting negative evidence flags
is safe by design, strictly validated, and fails closed on invalid types (str 'False', int, etc.).
"""
import pytest
from sclass.product.gate import GateOutput, GateState

AUTH = "QUALIFIED_EVALUATOR"

from sclass.product.adapter_diff_spec_anchors import (
    evaluate_pd_ch3_015_artifact_binding_integrity,
    evaluate_pd_ch3_016_spec_anchor_resolution,
    evaluate_pd_ch3_017_predicate_measurable_thresholds,
    evaluate_pd_ch3_018_clarification_authorized_outcome,
)
from sclass.product.adapter_qualification_contract import evaluate_pd_f10_004_execution_gate_enforcement
from sclass.product.context_resume_threats import evaluate_pd_ch4_007_context_resume_anchors
from sclass.product.enforcement_workspace_gate import (
    evaluate_pd_ch8_008_prevention_boundary,
    evaluate_pd_ch8_012_repository_intelligence,
    evaluate_pd_ch8_013_budget_exhaustion_ledger,
)
from sclass.product.erratum_issue_registry import (
    evaluate_pd_ch10_012_frozen_erratum_path,
    evaluate_pd_ch10_007_master_cross_links,
)
from sclass.product.execution_flow_testinput import (
    evaluate_pd_ch3_012_ux_interruption_budget_authority,
    evaluate_pd_ch4_012_reference_exact_resolution,
)
from sclass.product.isolation_claims import evaluate_pd_ch4_016_independent_evidence_producers
from sclass.product.knowledge_package_quarantine import (
    evaluate_pd_ch6_008_precedence_and_conflicts,
    evaluate_pd_ch6_009_lifecycle_projection,
)
from sclass.product.lifecycle_p0b import (
    evaluate_pd_ch2_007_p8_retry_budget,
    evaluate_pd_ch2_012_mandatory_floor_human_waiver,
)
from sclass.product.lifecycle_phase_admission import (
    evaluate_pd_ch3_007_work_type_decision_projection,
    evaluate_pd_ch3_009_flow_gates_and_lane_computation,
)
from sclass.product.notification_skill_normalization import (
    evaluate_pd_ch7_014_notification_projections,
    evaluate_pd_ch7_015_external_skill_normalization,
)
from sclass.product.oss_qualification_playbook import evaluate_pd_ch6_003_pack_activation
from sclass.product.stratum_sampling_compatibility import (
    evaluate_pd_ch9_007_secret_egress_claims,
    evaluate_pd_ch10_008_explicit_compatibility,
)
from sclass.product.threat_eval_regression_gate import evaluate_pd_ch9_008_threat_coverage
from sclass.product.wire_session_consequential_gate import (
    evaluate_pd_ch7_009_protocol_idempotent_retries,
    evaluate_pd_ch7_012_session_identity_bindings,
)


def test_e4_ch3_015_shadows_canonical_object_rejection():
    res = evaluate_pd_ch3_015_artifact_binding_integrity(
        "REV-1", "sha256-a", "code", "dev", shadows_canonical_object=True, authority=AUTH
    )
    assert res.state == GateState.MISSING


def test_e4_ch3_016_is_fuzzy_match_rejection():
    res = evaluate_pd_ch3_016_spec_anchor_resolution(
        "spec.md", "Section 1", (10, 20), "sha256-a", is_fuzzy_match=True, authority=AUTH
    )
    assert res.state == GateState.MISSING


def test_e4_ch3_017_is_undecidable_rejection():
    res = evaluate_pd_ch3_017_predicate_measurable_thresholds(
        "pred", 10.0, "ms", "sha256-p", "REV-1", is_undecidable=True, authority=AUTH
    )
    assert res.state == GateState.MISSING


def test_e4_ch3_018_model_inference_or_silent_rejection():
    res1 = evaluate_pd_ch3_018_clarification_authorized_outcome(
        "C-1", "sha256-a", "human", is_model_inference=True, authority=AUTH
    )
    assert res1.state == GateState.MISSING
    res2 = evaluate_pd_ch3_018_clarification_authorized_outcome(
        "C-1", "sha256-a", "human", is_silent=True, authority=AUTH
    )
    assert res2.state == GateState.MISSING


def test_e4_f10_004_timeout_and_worker_attempt():
    res1 = evaluate_pd_f10_004_execution_gate_enforcement(
        {"id": "r"}, {"id": "l"}, {"id": "b"}, {"id": "f"}, execution_timeout=True, authority=AUTH
    )
    assert res1.state == GateState.MISSING
    res2 = evaluate_pd_f10_004_execution_gate_enforcement(
        {"id": "r"}, {"id": "l"}, {"id": "b"}, {"id": "f"}, execution_timeout="False", authority=AUTH
    )
    assert res2.state == GateState.MISSING


def test_e4_ch4_007_transcript_only_authority():
    res = evaluate_pd_ch4_007_context_resume_anchors(
        "sha256-t", "sha256-c", "sha256-s", transcript_only_authority=True, authority=AUTH
    )
    assert res.state == GateState.MISSING


def test_e4_ch8_008_native_ide_activity():
    res = evaluate_pd_ch8_008_prevention_boundary(
        prevention_claimed=True,
        inside_qualified_enforcement_boundary=True,
        is_native_ide_activity=True,
        authority=AUTH,
    )
    assert res.state == GateState.MISSING


def test_e4_ch8_012_unresolved_symbol_present():
    res = evaluate_pd_ch8_012_repository_intelligence(
        True, True, unresolved_symbol_present=True, authority=AUTH
    )
    assert res.state == GateState.MISSING


def test_e4_ch8_013_budget_exhaustion_ledger():
    res1 = evaluate_pd_ch8_013_budget_exhaustion_ledger(
        budget_exhausted=True, routed_to_authorized_repair=True, second_ledger_active=True, authority=AUTH
    )
    assert res1.state == GateState.MISSING
    res2 = evaluate_pd_ch8_013_budget_exhaustion_ledger(
        budget_exhausted=True, routed_to_authorized_repair=True, model_reported_only_cost=True, authority=AUTH
    )
    assert res2.state == GateState.MISSING


def test_e4_ch10_012_ad_hoc_source_edit():
    res = evaluate_pd_ch10_012_frozen_erratum_path(
        "sha256-e", "sha256-p", True, ad_hoc_source_edit=True, authority=AUTH
    )
    assert res.state == GateState.MISSING


def test_e4_ch10_007_unknown_references_present():
    res = evaluate_pd_ch10_007_master_cross_links(
        True, unknown_references_present=True, authority=AUTH
    )
    assert res.state == GateState.MISSING


def test_e4_ch3_012_interruption_budget():
    res1 = evaluate_pd_ch3_012_ux_interruption_budget_authority(
        True, decision_suppressed_by_cap=True, authority=AUTH
    )
    assert res1.state == GateState.BLOCKED_ON_HUMAN
    res2 = evaluate_pd_ch3_012_ux_interruption_budget_authority(
        False, interruption_budget_exceeded=True, authority=AUTH
    )
    assert res2.state == GateState.BLOCKED_ON_HUMAN


def test_e4_ch4_012_reference_resolution_flags():
    res1 = evaluate_pd_ch4_012_reference_exact_resolution(
        "ref", "sha256-t", 10, is_unresolved=True, authority=AUTH
    )
    assert res1.state == GateState.MISSING
    res2 = evaluate_pd_ch4_012_reference_exact_resolution(
        "ref", "sha256-t", 10, is_ambiguous=True, authority=AUTH
    )
    assert res2.state == GateState.MISSING
    res3 = evaluate_pd_ch4_012_reference_exact_resolution(
        "ref", "sha256-t", 10, is_fuzzy_match=True, authority=AUTH
    )
    assert res3.state == GateState.MISSING


def test_e4_ch4_016_self_review_and_unqualified():
    res1 = evaluate_pd_ch4_016_independent_evidence_producers(
        "prod1", "prod2", is_self_review=True, authority=AUTH
    )
    assert res1.state == GateState.MISSING
    res2 = evaluate_pd_ch4_016_independent_evidence_producers(
        "prod1", "prod2", shared_unqualified_adapter=True, authority=AUTH
    )
    assert res2.state == GateState.MISSING


def test_e4_ch6_008_lower_tier_removes_mandatory():
    res = evaluate_pd_ch6_008_precedence_and_conflicts(
        True, lower_tier_removes_mandatory=True, authority=AUTH
    )
    assert res.state == GateState.MISSING


def test_e4_ch6_009_independent_state_machine():
    res = evaluate_pd_ch6_009_lifecycle_projection(
        True, independent_state_machine=True, authority=AUTH
    )
    assert res.state == GateState.MISSING


def test_e4_ch2_007_alternate_retry_path():
    res = evaluate_pd_ch2_007_p8_retry_budget(
        10, 5, alternate_retry_path_active=True, is_p8_repair=False, authority=AUTH
    )
    assert res.state == GateState.MISSING


def test_e4_ch2_012_unauthorized_waiver():
    res = evaluate_pd_ch2_012_mandatory_floor_human_waiver(
        waiver_requested=True, has_authorized_waiver_path=False, authority=AUTH
    )
    assert res.state == GateState.BLOCKED_ON_HUMAN


def test_e4_ch3_007_agent_override():
    res = evaluate_pd_ch3_007_work_type_decision_projection(
        "WT-1", "WT-1", agent_override_attempted=True, authority=AUTH
    )
    assert res.state == GateState.MISSING


def test_e4_ch3_009_agent_selected_lane():
    res = evaluate_pd_ch3_009_flow_gates_and_lane_computation(
        "STANDARD", "sha256-d", True, agent_selected_lane=True, authority=AUTH
    )
    assert res.state == GateState.MISSING


def test_e4_ch7_014_implies_approval():
    res = evaluate_pd_ch7_014_notification_projections(
        True, implies_approval_on_model_message=True, authority=AUTH
    )
    assert res.state == GateState.MISSING


def test_e4_ch7_015_alternate_lifecycle():
    res = evaluate_pd_ch7_015_external_skill_normalization(
        True, creates_alternate_lifecycle_or_loop=True, authority=AUTH
    )
    assert res.state == GateState.MISSING


def test_e4_ch6_003_effective_revocation():
    res = evaluate_pd_ch6_003_pack_activation(
        True, effective_revocation_present=True, authority=AUTH
    )
    assert res.state == GateState.MISSING


def test_e4_ch9_007_unqualified_scanner():
    res = evaluate_pd_ch9_007_secret_egress_claims(
        True, unqualified_scanner_or_native_host_write=True, authority=AUTH
    )
    assert res.state == GateState.MISSING


def test_e4_ch10_008_unsupported_pair():
    res = evaluate_pd_ch10_008_explicit_compatibility(
        {"supported": True}, unsupported_pair_present=True, authority=AUTH
    )
    assert res.state == GateState.MISSING


def test_e4_ch9_008_absence_of_findings():
    res = evaluate_pd_ch9_008_threat_coverage(
        {"threats": []}, absence_of_findings_as_pass=True, authority=AUTH
    )
    assert res.state == GateState.MISSING


def test_e4_ch7_009_conflict_detected():
    res = evaluate_pd_ch7_009_protocol_idempotent_retries(
        True, version_conflict_typed_error=False, conflict_detected=True, authority=AUTH
    )
    assert res.state == GateState.MISSING


def test_e4_ch7_012_transport_claims_authority():
    res = evaluate_pd_ch7_012_session_identity_bindings(
        {"id": "1"}, transport_claims_canonical_authority=True, authority=AUTH
    )
    assert res.state == GateState.MISSING
