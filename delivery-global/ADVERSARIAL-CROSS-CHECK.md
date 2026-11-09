# ADVERSARIAL CROSS-CHECK REPORT (Task G5 / Round 11 / Round 12 E2)

Machine-generated verification feeding 21 hostile adversarial vectors to every public evaluator.

## 1. Executive Summary

- **Total Public Evaluators Tested**: 172
- **Total Adversarial Checks Run**: 3612 (172 × 21 vectors)
- **Total Flaws Found**: 0
- **Legitimate Happy Paths Verified (Vector 17)**: 8
- **Exceptions Escaping**: 0
- **Verdict**: `PASS`

## 2. Tested Hostile Vectors (21 Vectors)

- `1. None`
- `2. Wrong Type (int)`
- `3. Empty Dict`
- `4. Huge Int`
- `5. NaN`
- `6. Payload Claiming Authority`
- `7. authority='AGENT'`
- `8. Authority Omitted`
- `9. Exception-Raising Dependency`
- `10. Dict with Extra Keys`
- `11. Recursive Structure`
- `12. Unicode Edge`
- `13. Valid Authority + Evidence Omitted`
- `14. Valid Authority + Each Evidence Param None`
- `15. Valid Authority + Wrong Types (str 'False', 0, 1, list)`
- `16. Valid Authority + Payload Keys Missing`
- `17. Valid Authority + Evidence True/False Mixed`
- `18. Valid Authority + Deep Chain 5000 Nodes`
- `19. Valid Authority + Huge Int (10**100)`
- `20. Valid Authority + 1e6-Element List`
- `21. Valid Authority + String-Instead-Of-List`

## 3. Vector 17 Legitimate Happy Path Classifications

| Evaluator | Vector | Master Line & Justification |
|---|---|---|
| `evaluate_pd_ch10_007_master_cross_links` | `17. Valid Authority + Evidence True/False Mixed` | Master L4594/L10726 (CH10-T7): cross_linked_to_master=True, unknown_references_present=False |
| `evaluate_pd_ch6_008_precedence_and_conflicts` | `17. Valid Authority + Evidence True/False Mixed` | Master L3693/L11870 (CH6-T10): precedence_order_respected=True, conflicting_override_present=False |
| `evaluate_pd_ch6_009_lifecycle_projection` | `17. Valid Authority + Evidence True/False Mixed` | Master L3717/L11911 (CH6-T12): is_evidence_projection=True, independent_state_machine=False |
| `evaluate_pd_ch2_048_test_input_set_exclusion_check` | `17. Valid Authority + Evidence True/False Mixed` | Master L2076/L10323 (CH2-T48): p6_tests_frozen_invoked=True, p6_modifies_test_input_set=False |
| `evaluate_pd_ch7_014_notification_projections` | `17. Valid Authority + Evidence True/False Mixed` | Master L4041/L12327 (CH7-T21): derived_from_gate_projection=True, implies_approval_on_model_message=False |
| `evaluate_pd_ch7_015_external_skill_normalization` | `17. Valid Authority + Evidence True/False Mixed` | Master L4244/L12374 (CH7-T23): normalized_into_sclass_owned_checks=True, creates_alternate_lifecycle_or_loop=False |
| `evaluate_pd_ch6_003_pack_activation` | `17. Valid Authority + Evidence True/False Mixed` | Master L3862/L10585 (CH6-T3): scope_specific_qualification=True, effective_revocation_present=False |
| `evaluate_pd_ch9_007_secret_egress_claims` | `17. Valid Authority + Evidence True/False Mixed` | Master L4402/L12881 (CH9-T24): qualified_receipt_on_launched_worker=True, unqualified_scanner_or_native_host_write=False |

## 4. Results Matrix

| Evaluator | Module | 21 Adversarial Vectors Status | Classification / Flaws |
|---|---|---|---|
| `evaluate_b4_b_gate` | `adapter_diff_spec_anchors.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch3_015_artifact_binding_integrity` | `adapter_diff_spec_anchors.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch3_016_spec_anchor_resolution` | `adapter_diff_spec_anchors.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch3_017_predicate_measurable_thresholds` | `adapter_diff_spec_anchors.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch3_018_clarification_authorized_outcome` | `adapter_diff_spec_anchors.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch3_020_spec_change_replay_point` | `adapter_diff_spec_anchors.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_f10_007_differential_detection` | `adapter_diff_spec_anchors.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_b4_a_gate` | `adapter_qualification_contract.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_f10_001_contract_invocation` | `adapter_qualification_contract.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_f10_002_usable_adapter_binding` | `adapter_qualification_contract.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_f10_003_adapter_registration_authority` | `adapter_qualification_contract.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_f10_004_execution_gate_enforcement` | `adapter_qualification_contract.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_f10_005_qualification_matrix` | `adapter_qualification_contract.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_f10_006_independent_verification` | `adapter_qualification_contract.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_f1_representation` | `artifacts.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_f7_claim` | `claim_ledger.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_f7_claim_ledger` | `claim_ledger.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_f7_claims` | `claim_ledger.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_b4_f_gate` | `context_resume_threats.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch4_007_context_resume_anchors` | `context_resume_threats.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch4_008_threat_matrix_containment` | `context_resume_threats.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_b5_gate` | `enforcement_workspace_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch8_008_prevention_boundary` | `enforcement_workspace_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch8_009_workspace_promotion` | `enforcement_workspace_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch8_010_out_of_band_edits` | `enforcement_workspace_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch8_011_parallel_work_serialization` | `enforcement_workspace_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch8_012_repository_intelligence` | `enforcement_workspace_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch8_013_budget_exhaustion_ledger` | `enforcement_workspace_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_b9_c_gate` | `erratum_issue_registry.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch10_007_master_cross_links` | `erratum_issue_registry.py` | **PASS (LEGIT_HAPPY)** | 17. Valid Authority + Evidence True/False Mixed: LEGIT_HAPPY (Master L4594/L10726 (CH10-T7): cross_linked_to_master=True, unknown_references_present=False) |
| `evaluate_pd_ch10_012_frozen_erratum_path` | `erratum_issue_registry.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch10_013_open_issue_schema` | `erratum_issue_registry.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_b4_d_gate` | `execution_flow_testinput.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch3_010_flow_baseline_binding` | `execution_flow_testinput.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch3_011_adapter_qualification_disclosure` | `execution_flow_testinput.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch3_012_ux_interruption_budget_authority` | `execution_flow_testinput.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch3_014_lifecycle_example_adversarial_failure` | `execution_flow_testinput.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch4_009_test_input_set_binding` | `execution_flow_testinput.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch4_012_reference_exact_resolution` | `execution_flow_testinput.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_f1_representation` | `f4_lane_selection.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_f4_lane_selection` | `f4_lane_selection.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_f8_step_pack` | `f8_step_pack.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_f5_gate` | `gate_evaluator.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_b4_e_gate` | `isolation_claims.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch4_002_execution_claim_receipt` | `isolation_claims.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch4_005_evidence_freshness_identity` | `isolation_claims.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch4_006_canonical_closure_vs_prose` | `isolation_claims.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch4_010_test_input_write_isolation` | `isolation_claims.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch4_014_authorized_delta_scope` | `isolation_claims.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch4_016_independent_evidence_producers` | `isolation_claims.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_b6_a_gate` | `knowledge_package_quarantine.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch6_007_package_metadata` | `knowledge_package_quarantine.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch6_008_precedence_and_conflicts` | `knowledge_package_quarantine.py` | **PASS (LEGIT_HAPPY)** | 17. Valid Authority + Evidence True/False Mixed: LEGIT_HAPPY (Master L3693/L11870 (CH6-T10): precedence_order_respected=True, conflicting_override_present=False) |
| `evaluate_pd_ch6_009_lifecycle_projection` | `knowledge_package_quarantine.py` | **PASS (LEGIT_HAPPY)** | 17. Valid Authority + Evidence True/False Mixed: LEGIT_HAPPY (Master L3717/L11911 (CH6-T12): is_evidence_projection=True, independent_state_machine=False) |
| `evaluate_pd_ch6_010_quarantine_conditions` | `knowledge_package_quarantine.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch6_011_license_provenance_verification` | `knowledge_package_quarantine.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch6_012_steppack_digest_pinning` | `knowledge_package_quarantine.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_p0a_gate` | `lifecycle_p0a.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_001_single_lifecycle` | `lifecycle_p0a.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_002_eleven_dimensions` | `lifecycle_p0a.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_003_earlier_phase_validity` | `lifecycle_p0a.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_005_skipped_phase_applicability` | `lifecycle_p0a.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_006_earliest_defect_routing` | `lifecycle_p0a.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_055_downstream_invalidation` | `lifecycle_p0a.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_p0b_gate` | `lifecycle_p0b.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_007_p8_retry_budget` | `lifecycle_p0b.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_008_p11_non_terminal_reentry` | `lifecycle_p0b.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_009_done_claim_evidence_closure` | `lifecycle_p0b.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_010_green_external_run_evidence` | `lifecycle_p0b.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_011_stack_pack_phase_topology` | `lifecycle_p0b.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_012_mandatory_floor_human_waiver` | `lifecycle_p0b.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_p11_gate` | `lifecycle_p11.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_054_signal` | `lifecycle_p11.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_058_applicability` | `lifecycle_p11.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_060_flow_order` | `lifecycle_p11.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_061_delivery_flow` | `lifecycle_p11.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_062_project_class` | `lifecycle_p11.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_063_question_budget` | `lifecycle_p11.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_p1_p4_gate` | `lifecycle_p1_p4.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_029_task_caps` | `lifecycle_p1_p4.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_031_work_graph_acyclic` | `lifecycle_p1_p4.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_032_write_set_overlap` | `lifecycle_p1_p4.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_056_discovery_completeness` | `lifecycle_p1_p4.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_057_skill_depth_precedence` | `lifecycle_p1_p4.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_p3a_gate` | `lifecycle_p3a.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_013_requirement_coverage` | `lifecycle_p3a.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_014_domain_invariants` | `lifecycle_p3a.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_015_architecture_provenance` | `lifecycle_p3a.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_016_dependency_relationships` | `lifecycle_p3a.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_017_domain_model_substance` | `lifecycle_p3a.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_018_architecture_record_substance` | `lifecycle_p3a.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_p3b_gate` | `lifecycle_p3b.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_020_decidable_invariants` | `lifecycle_p3b.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_021_cross_entity_constraints` | `lifecycle_p3b.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_022_change_surface_boundary_closure` | `lifecycle_p3b.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_023_boundary_data_flow_contracts` | `lifecycle_p3b.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_024_interface_signatures_typed_contracts` | `lifecycle_p3b.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_025_unknown_contradiction_handling` | `lifecycle_p3b.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_p3c_p8_p10_gate` | `lifecycle_p3c_p8_p10.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_026_adr_design_digest_binding` | `lifecycle_p3c_p8_p10.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_028_unique_must_ids` | `lifecycle_p3c_p8_p10.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_051_p8_retry_budget_exhaustion` | `lifecycle_p3c_p8_p10.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_052_p9_task_aggregation_findings_closure` | `lifecycle_p3c_p8_p10.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_053_p10_kernel_release_evaluation` | `lifecycle_p3c_p8_p10.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_p5_gate` | `lifecycle_p5.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_033_delta_sequence` | `lifecycle_p5.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_034_red_run_validity` | `lifecycle_p5.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_035_executable_spec_constraints` | `lifecycle_p5.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_036_adapter_qualification` | `lifecycle_p5.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_046_test_input_set_binding` | `lifecycle_p5.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_047_red_classification_source` | `lifecycle_p5.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_p6_gate` | `lifecycle_p6.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_037_execution_gate_authorization` | `lifecycle_p6.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_038_scope_growth_stop` | `lifecycle_p6.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_039_implementation_claims` | `lifecycle_p6.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_040_canonical_delta_kernel_receipt` | `lifecycle_p6.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_048_test_input_set_exclusion_check` | `lifecycle_p6.py` | **PASS (LEGIT_HAPPY)** | 17. Valid Authority + Evidence True/False Mixed: LEGIT_HAPPY (Master L2076/L10323 (CH2-T48): p6_tests_frozen_invoked=True, p6_modifies_test_input_set=False) |
| `evaluate_p7_gate` | `lifecycle_p7.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_041_evidence_binding` | `lifecycle_p7.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_042_adapter_qualification` | `lifecycle_p7.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_043_independence_floor` | `lifecycle_p7.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_044_freshness_predicate` | `lifecycle_p7.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_045_closure_ownership` | `lifecycle_p7.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch2_050_deterministic_rerun` | `lifecycle_p7.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_b4_c_gate` | `lifecycle_phase_admission.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch3_001_phase_artifact_anchors` | `lifecycle_phase_admission.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch3_002_normative_requirements_completeness` | `lifecycle_phase_admission.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch3_003_clarification_scope_entry` | `lifecycle_phase_admission.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch3_006_external_tool_candidate_trust` | `lifecycle_phase_admission.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch3_007_work_type_decision_projection` | `lifecycle_phase_admission.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch3_009_flow_gates_and_lane_computation` | `lifecycle_phase_admission.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_f9_metric` | `metrics.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_b7_b_gate` | `notification_skill_normalization.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch7_014_notification_projections` | `notification_skill_normalization.py` | **PASS (LEGIT_HAPPY)** | 17. Valid Authority + Evidence True/False Mixed: LEGIT_HAPPY (Master L4041/L12327 (CH7-T21): derived_from_gate_projection=True, implies_approval_on_model_message=False) |
| `evaluate_pd_ch7_015_external_skill_normalization` | `notification_skill_normalization.py` | **PASS (LEGIT_HAPPY)** | 17. Valid Authority + Evidence True/False Mixed: LEGIT_HAPPY (Master L4244/L12374 (CH7-T23): normalized_into_sclass_owned_checks=True, creates_alternate_lifecycle_or_loop=False) |
| `evaluate_b6_b_gate` | `oss_qualification_playbook.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch6_003_pack_activation` | `oss_qualification_playbook.py` | **PASS (LEGIT_HAPPY)** | 17. Valid Authority + Evidence True/False Mixed: LEGIT_HAPPY (Master L3862/L10585 (CH6-T3): scope_specific_qualification=True, effective_revocation_present=False) |
| `evaluate_pd_ch6_006_playbook_content` | `oss_qualification_playbook.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch6_013_stack_pack_adapters` | `oss_qualification_playbook.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch6_014_oss_qualification_record` | `oss_qualification_playbook.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_performance_claim` | `performance_claims.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_predicate_input` | `predicate_evaluator.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_ch2_064_replay_invalidation` | `replay.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_ch2_065_lifecycle_proof` | `replay.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_replay_gate` | `replay.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_b9_b_gate` | `stratum_sampling_compatibility.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch10_008_explicit_compatibility` | `stratum_sampling_compatibility.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch10_009_audit_export_bindings` | `stratum_sampling_compatibility.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch10_010_roadmap_integrity` | `stratum_sampling_compatibility.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch10_011_fact_classification` | `stratum_sampling_compatibility.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch9_006_stratum_sampling_promotion` | `stratum_sampling_compatibility.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch9_007_secret_egress_claims` | `stratum_sampling_compatibility.py` | **PASS (LEGIT_HAPPY)** | 17. Valid Authority + Evidence True/False Mixed: LEGIT_HAPPY (Master L4402/L12881 (CH9-T24): qualified_receipt_on_launched_worker=True, unqualified_scanner_or_native_host_write=False) |
| `evaluate_b9_a_gate` | `threat_eval_regression_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch9_003_security_promotion_gate` | `threat_eval_regression_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch9_004_metric_reporting_integrity` | `threat_eval_regression_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch9_005_data_retention_policy` | `threat_eval_regression_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch9_008_threat_coverage` | `threat_eval_regression_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch9_009_eval_run_bindings` | `threat_eval_regression_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch9_010_promotion_blockers` | `threat_eval_regression_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_f6_traceability` | `traceability.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `check_structured_conflict` | `trust_model.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_claim` | `trust_model.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_confirmation_admissibility` | `trust_model.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_f3_trust` | `trust_model.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_requirement_confirmation` | `trust_model.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_b7_a_gate` | `wire_session_consequential_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch7_008_guidance_resources` | `wire_session_consequential_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch7_009_protocol_idempotent_retries` | `wire_session_consequential_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch7_011_ide_mode_capabilities` | `wire_session_consequential_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch7_012_session_identity_bindings` | `wire_session_consequential_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch7_013_consequential_developer_actions` | `wire_session_consequential_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
| `evaluate_pd_ch7_016_wire_protocol_envelope` | `wire_session_consequential_gate.py` | **PASS (ALL 21 REJECTED)** | None (fail-closed) |
