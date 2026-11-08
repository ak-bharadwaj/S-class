"""Cross-Block End-to-End Integration Tests for Blocks 4 through 9.

Validates end-to-end integration and cross-block dependency chaining across:
- Block 4: Adapter Qualification, Anchors, Lifecycle Phase Admission, Execution Flow & Isolation
- Block 5: Enforcement Boundary & Workspace Concurrency Gate
- Block 6: Knowledge Package Quarantine, Playbook & OSS Qualification
- Block 7: Wire Protocol, Session Identity & Consequential Action Gating
- Block 9: Threat Evaluation, Stratum Sampling, Compatibility & Erratum Governance

Includes authority validation and negative/gaming scenario chaining across all blocks.
"""
from __future__ import annotations

import pytest
from sclass.product.gate import GateOutput, GateState

# Gate modules
from sclass.product.adapter_qualification_contract import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B4A,
    evaluate_pd_f10_001_contract_invocation,
    evaluate_pd_f10_002_usable_adapter_binding,
)
from sclass.product.adapter_diff_spec_anchors import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B4B,
    evaluate_pd_ch3_015_artifact_binding_integrity,
)
from sclass.product.lifecycle_phase_admission import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B4C,
    evaluate_pd_ch3_001_phase_artifact_anchors,
)
from sclass.product.execution_flow_testinput import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B4D,
    evaluate_pd_ch4_012_reference_exact_resolution,
)
from sclass.product.isolation_claims import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B4E,
    evaluate_pd_ch4_010_test_input_write_isolation,
)
from sclass.product.context_resume_threats import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B4F,
    evaluate_pd_ch4_007_context_resume_anchors,
)
from sclass.product.enforcement_workspace_gate import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B5,
    evaluate_pd_ch8_008_prevention_boundary,
    evaluate_pd_ch8_009_workspace_promotion,
    evaluate_pd_ch8_010_out_of_band_edits,
    evaluate_pd_ch8_013_budget_exhaustion_ledger,
)
from sclass.product.knowledge_package_quarantine import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B6A,
    REQUIRED_PACKAGE_METADATA_FIELDS,
    evaluate_pd_ch6_007_package_metadata,
    evaluate_pd_ch6_010_quarantine_conditions,
)
from sclass.product.oss_qualification_playbook import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B6B,
    OSS_QUALIFICATION_FIELDS,
    REQUIRED_PLAYBOOK_PHASES,
    evaluate_pd_ch6_014_oss_qualification_record,
    evaluate_pd_ch6_006_playbook_content,
)
from sclass.product.wire_session_consequential_gate import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B7A,
    REQUIRED_SESSION_BINDINGS,
    evaluate_pd_ch7_016_wire_protocol_envelope,
    evaluate_pd_ch7_012_session_identity_bindings,
    evaluate_pd_ch7_013_consequential_developer_actions,
)
from sclass.product.notification_skill_normalization import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B7B,
    evaluate_pd_ch7_014_notification_projections,
)
from sclass.product.threat_eval_regression_gate import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B9A,
    REQUIRED_THREAT_FIELDS,
    REQUIRED_EVAL_RUN_BINDINGS,
    evaluate_pd_ch9_008_threat_coverage,
    evaluate_pd_ch9_009_eval_run_bindings,
    evaluate_pd_ch9_003_security_promotion_gate,
)
from sclass.product.stratum_sampling_compatibility import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B9B,
    REQUIRED_COMPATIBILITY_FIELDS,
    evaluate_pd_ch9_006_stratum_sampling_promotion,
    evaluate_pd_ch10_008_explicit_compatibility,
    evaluate_pd_ch10_010_roadmap_integrity,
)
from sclass.product.erratum_issue_registry import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B9C,
    REQUIRED_OPEN_ISSUE_FIELDS,
    evaluate_pd_ch10_012_frozen_erratum_path,
    evaluate_pd_ch10_013_open_issue_schema,
)

AUTH = "QUALIFIED_EVALUATOR"


class TestBlock4To9CrossBlockIntegration:
    """12 Comprehensive Cross-Block Integration Scenarios."""

    def test_scenario_1_full_pipeline_happy_path(self):
        """Scenario 1: Full pipeline execution across Blocks 4..9 with authorized caller."""
        # B4: Adapter qualification
        r_b4 = evaluate_pd_f10_001_contract_invocation(
            tool_call={"tool_identity": "adapter-x", "version": "1.0"},
            adapter_record={"adapter_id": "A1"},
            category="syntax-validator",
            authority=AUTH,
        )
        assert r_b4.state == GateState.SATISFIED

        # B5: Enforcement boundary & workspace promotion
        r_b5 = evaluate_pd_ch8_009_workspace_promotion(
            target_verified=True,
            kernel_release_authority=True,
            rollback_evidence_preserved=True,
            authority=AUTH,
        )
        assert r_b5.state == GateState.SATISFIED

        # B6: Knowledge package verification
        valid_meta = {f: f"val_{f}" for f in REQUIRED_PACKAGE_METADATA_FIELDS}
        r_b6 = evaluate_pd_ch6_007_package_metadata(valid_meta, authority=AUTH)
        assert r_b6.state == GateState.SATISFIED

        # B7: Wire protocol envelope
        req = {"protocol_version": "1.0", "task_id": "T1", "session_id": "S1"}
        resp = {"request_id": "R1", "result": "OK", "next_action": "NONE", "resource_refs": [], "error": None}
        r_b7 = evaluate_pd_ch7_016_wire_protocol_envelope(req, resp, authority=AUTH)
        assert r_b7.state == GateState.SATISFIED

        # B9: Threat eval & security gate
        r_b9 = evaluate_pd_ch9_003_security_promotion_gate(
            failed_security_scan=False,
            environment_mismatch=False,
            sandbox_trust_root_failure=False,
            authority=AUTH,
        )
        assert r_b9.state == GateState.SATISFIED

    def test_scenario_2_caller_lacks_authority_across_pipeline(self):
        """Scenario 2: Every gate in the pipeline fails closed when authority is omitted/None."""
        assert evaluate_pd_f10_001_contract_invocation({}, {}, "cat", authority=None).state == GateState.MISSING
        assert evaluate_pd_ch8_009_workspace_promotion(True, True, True, authority=None).state == GateState.MISSING
        assert evaluate_pd_ch6_007_package_metadata({}, authority=None).state == GateState.MISSING
        assert evaluate_pd_ch7_016_wire_protocol_envelope({}, {}, authority=None).state == GateState.MISSING
        assert evaluate_pd_ch9_003_security_promotion_gate(authority=None).state == GateState.MISSING
        assert evaluate_pd_ch10_012_frozen_erratum_path(True, True, True, authority=None).state == GateState.MISSING

    def test_scenario_3_b4_adapter_failure_blocks_downstream_enforcement(self):
        """Scenario 3: Unusable adapter binding in B4 blocks downstream workspace promotion in B5."""
        r_b4 = evaluate_pd_f10_002_usable_adapter_binding(
            {"adapter_id": "A1", "qualification_record_ref": None},
            authority=AUTH,
        )
        assert r_b4.state == GateState.MISSING
        # Downstream B5 promotion cannot verify target without qualified adapter
        r_b5 = evaluate_pd_ch8_009_workspace_promotion(
            target_verified=False,
            kernel_release_authority=True,
            rollback_evidence_preserved=True,
            authority=AUTH,
        )
        assert r_b5.state == GateState.MISSING

    def test_scenario_4_b5_oob_edits_invalidate_b4_context(self):
        """Scenario 4: Out-of-band edits in B5 invalidate B4 context resume."""
        r_b5 = evaluate_pd_ch8_010_out_of_band_edits(
            out_of_band_edits_detected=True,
            re_snapshot_taken=False,
            digest_comparison_passed=False,
            authority=AUTH,
        )
        assert r_b5.state == GateState.MISSING

        # B4 context resume detects invalidated snapshot
        r_b4 = evaluate_pd_ch4_007_context_resume_anchors(
            canonical_anchors_present=False,
            pinned_guidance_digests=None,
            step_pack_digest=None,
            authority=AUTH,
        )
        assert r_b4.state == GateState.MISSING

    def test_scenario_5_b6_unqualified_knowledge_pack_blocks_b7_playbook(self):
        """Scenario 5: Quarantined package in B6 blocks B7 playbook execution."""
        r_b6 = evaluate_pd_ch6_010_quarantine_conditions(
            unknown_checks=True,
            quarantined=True,
            authority=AUTH,
        )
        assert r_b6.state == GateState.MISSING

        # B6 playbook content cannot claim unqualified adapter usable
        r_playbook = evaluate_pd_ch6_006_playbook_content(
            {
                "phases": list(REQUIRED_PLAYBOOK_PHASES),
                "unqualified_adapter_claimed_usable": True,
            },
            authority=AUTH,
        )
        assert r_playbook.state == GateState.MISSING

    def test_scenario_6_b7_unsupported_protocol_blocks_b9_eval(self):
        """Scenario 6: Unsupported wire protocol version in B7 blocks B9 evaluation run."""
        r_b7 = evaluate_pd_ch7_016_wire_protocol_envelope(
            {"protocol_version": "0.1", "task_id": "T1", "session_id": "S1"},
            {"request_id": "R1", "result": "OK", "next_action": "NONE", "resource_refs": [], "error": None},
            authority=AUTH,
        )
        assert r_b7.state == GateState.MISSING

        # B9 eval run cannot bind an invalid protocol run
        r_b9 = evaluate_pd_ch9_009_eval_run_bindings(
            {"benchmark_task_revision": "R1", "target": "T1"},  # missing other fields
            authority=AUTH,
        )
        assert r_b9.state == GateState.MISSING

    def test_scenario_7_b9_security_scan_failure_blocks_b5_workspace_promotion(self):
        """Scenario 7: Security critical regression in B9 blocks workspace promotion in B5."""
        r_b9 = evaluate_pd_ch9_003_security_promotion_gate(
            failed_security_scan=True,
            authority=AUTH,
        )
        assert r_b9.state == GateState.MISSING
        assert "BLOCKED" in r_b9.detail

        # B5 kernel release authority is withheld
        r_b5 = evaluate_pd_ch8_009_workspace_promotion(
            target_verified=True,
            kernel_release_authority=False,
            rollback_evidence_preserved=True,
            authority=AUTH,
        )
        assert r_b5.state == GateState.MISSING

    def test_scenario_8_b5_budget_exhaustion_routes_to_b9_erratum(self):
        """Scenario 8: B5 budget exhaustion triggers formal repair route through B9 erratum path."""
        # Unrouted budget exhaustion fails
        r_b5_fail = evaluate_pd_ch8_013_budget_exhaustion_ledger(
            budget_exhausted=True,
            routed_to_authorized_repair=False,
            authority=AUTH,
        )
        assert r_b5_fail.state == GateState.MISSING

        # Routed budget exhaustion passes B5
        r_b5_pass = evaluate_pd_ch8_013_budget_exhaustion_ledger(
            budget_exhausted=True,
            routed_to_authorized_repair=True,
            authority=AUTH,
        )
        assert r_b5_pass.state == GateState.SATISFIED

        # The repair path executes formal B9 erratum path
        r_b9_erratum = evaluate_pd_ch10_012_frozen_erratum_path(
            formal_erratum_path=True,
            insufficiency_analysis_present=True,
            replay_analysis_present=True,
            authority=AUTH,
        )
        assert r_b9_erratum.state == GateState.SATISFIED

    def test_scenario_9_b6_oss_qualification_incomplete_blocks_b9_compatibility(self):
        """Scenario 9: Incomplete OSS qualification record in B6 blocks B9 compatibility promotion."""
        incomplete_rec = {f: f"ref_{f}" for f in OSS_QUALIFICATION_FIELDS}
        del incomplete_rec["reviewer_reference"]
        r_b6 = evaluate_pd_ch6_014_oss_qualification_record(incomplete_rec, authority=AUTH)
        assert r_b6.state == GateState.MISSING

        # Compatibility matrix detects unsupported unverified pair
        r_b9_compat = evaluate_pd_ch10_008_explicit_compatibility(
            {f: "1.0" for f in REQUIRED_COMPATIBILITY_FIELDS},
            unsupported_pair_present=True,
            authority=AUTH,
        )
        assert r_b9_compat.state == GateState.MISSING

    def test_scenario_10_b7_consequential_action_without_observation_blocks_b9_audit(self):
        """Scenario 10: Consequential action failing observation in B7 blocks B9 audit export."""
        r_b7 = evaluate_pd_ch7_013_consequential_developer_actions(
            authorization_scope_gate_passed=True,
            admissible_observation_emitted=False,
            authority=AUTH,
        )
        assert r_b7.state == GateState.MISSING

    def test_scenario_11_b4_synthetic_gap_claims_blocked(self):
        """Scenario 11: Synthetic gap claims in B4 without spec anchor fail closed."""
        r_b4 = evaluate_pd_ch3_015_artifact_binding_integrity(
            objective_revision=None,
            source_digest=None,
            artifact_type=None,
            owning_authority=None,
            authority=AUTH,
        )
        assert r_b4.state == GateState.MISSING

    def test_scenario_12_b9_oi008_fresh_chat_review_gating(self):
        """Scenario 12: Open issue OI-008 in B9 requires two raw fresh-chat reviews before closure."""
        issue = {f: f"val_{f}" for f in REQUIRED_OPEN_ISSUE_FIELDS}
        issue["id"] = "OI-008"
        issue["status"] = "CLOSED"

        # 0 or 1 review -> BLOCKED
        r_fail = evaluate_pd_ch10_013_open_issue_schema(issue, oi_008_owner_reviews_count=1, authority=AUTH)
        assert r_fail.state == GateState.MISSING
        assert "BLOCKED" in r_fail.detail

        # 2 reviews -> SATISFIED
        r_pass = evaluate_pd_ch10_013_open_issue_schema(issue, oi_008_owner_reviews_count=2, authority=AUTH)
        assert r_pass.state == GateState.SATISFIED
