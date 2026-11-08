# STATIC LPC AUDIT REPORT (S1 - S8)

Machine-generated AST audit of all public evaluators across Blocks 1-9 on integration tip.

## 1. Executive Summary

- **Total Public Evaluators Audited**: 171
- **Total Product Modules**: 40
- **S1 Authority Parameter**: 138 / 171 pass
- **S2 Authority First Statement**: 143 / 171 pass
- **S3 Closed Vocabulary Return**: 138 / 171 pass
- **S4 Safe Exception Handling**: 171 / 171 pass
- **S5 Forbidden Imports (I/O, network, etc.)**: 2 violations
- **S6 Mutable State / Defaults**: 171 / 171 pass
- **S7 Import Direction (tests/tools in product)**: 1 violations
- **S8 Tested with Authority Omitted**: 170 evaluators covered in test suite

## 2. Module Sizing and Waivers

| Module | Line Count | Status / Waiver |
|---|---|---|
| `predicate_evaluator.py` | 1405 | W-B2-1 (Block 2 CAP waiver, authorized by CL) |
| `trust_model.py` | 1233 | W-B2-1 (Block 2 CAP waiver, authorized by CL) |
| `metrics.py` | 845 | W-B2-1 (Block 2 CAP waiver, authorized by CL) |
| `traceability.py` | 674 | W-B2-1 (Block 2 CAP waiver, authorized by CL) |
| `claim_ledger.py` | 653 | W-B2-1 (Block 2 CAP waiver, authorized by CL) |
| `artifacts.py` | 611 | W-B2-1 (Block 2 CAP waiver, authorized by CL) |
| `fixture_bindings.py` | 532 | W-B2-1 (Block 2 CAP waiver, authorized by CL) |
| `gate_evaluator.py` | 524 | PASSED (<= 600) |
| `fixture_runner.py` | 464 | PASSED (<= 600) |
| `f4_lane_selection.py` | 390 | PASSED (<= 600) |
| `lifecycle_p0a.py` | 390 | PASSED (<= 600) |
| `adapter_qualification_contract.py` | 362 | PASSED (<= 600) |
| `lifecycle_p11.py` | 359 | PASSED (<= 600) |
| `adapter_diff_spec_anchors.py` | 355 | PASSED (<= 600) |
| `stratum_sampling_compatibility.py` | 335 | PASSED (<= 600) |
| `lifecycle_phase_admission.py` | 333 | PASSED (<= 600) |
| `lifecycle_p0b.py` | 317 | PASSED (<= 600) |
| `lifecycle_p5.py` | 317 | PASSED (<= 600) |
| `threat_eval_regression_gate.py` | 317 | PASSED (<= 600) |
| `lifecycle_p3a.py` | 309 | PASSED (<= 600) |
| `lifecycle_p1_p4.py` | 307 | PASSED (<= 600) |
| `wire_session_consequential_gate.py` | 307 | PASSED (<= 600) |
| `gate_cache.py` | 305 | PASSED (<= 600) |
| `execution_flow_testinput.py` | 302 | PASSED (<= 600) |
| `lifecycle_p3b.py` | 296 | PASSED (<= 600) |
| `isolation_claims.py` | 285 | PASSED (<= 600) |
| `lifecycle_p3c_p8_p10.py` | 285 | PASSED (<= 600) |
| `lifecycle_p7.py` | 284 | PASSED (<= 600) |
| `knowledge_package_quarantine.py` | 279 | PASSED (<= 600) |
| `performance_claims.py` | 277 | PASSED (<= 600) |
| `enforcement_workspace_gate.py` | 272 | PASSED (<= 600) |
| `check_registry.py` | 264 | PASSED (<= 600) |
| `oss_qualification_playbook.py` | 256 | PASSED (<= 600) |
| `lifecycle_p6.py` | 254 | PASSED (<= 600) |
| `f8_step_pack.py` | 231 | PASSED (<= 600) |
| `replay.py` | 173 | PASSED (<= 600) |
| `erratum_issue_registry.py` | 168 | PASSED (<= 600) |
| `context_resume_threats.py` | 117 | PASSED (<= 600) |
| `notification_skill_normalization.py` | 99 | PASSED (<= 600) |
| `gate.py` | 62 | PASSED (<= 600) |

## 3. Forbidden Imports (S5) & Import Direction (S7)

### S5 Forbidden Imports Detected:

- `fixture_bindings.py:15`: imported `os`
- `predicate_evaluator.py:19`: imported `sys`
### S7 Import Direction Violations Detected:

- `fixture_bindings.py:504`: imported `tools.master_fixtures` from tests/tools
## 4. Evaluator LPC Audit Table (All Public Evaluators)

| Evaluator | File:Line | S1 (Auth Param) | S2 (Auth Check) | S3 (Closed Vocab) | S4 (Safe Except) | S6 (No Mut Defaults) | S8 (Tested Auth Omitted) |
|---|---|---|---|---|---|---|---|
| `evaluate_pd_f10_007_differential_detection` | `adapter_diff_spec_anchors.py:45` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_015_artifact_binding_integrity` | `adapter_diff_spec_anchors.py:83` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_016_spec_anchor_resolution` | `adapter_diff_spec_anchors.py:121` | PASS | PASS | PASS | PASS | PASS | NO_TEST |
| `evaluate_pd_ch3_017_predicate_measurable_thresholds` | `adapter_diff_spec_anchors.py:169` | PASS | PASS | PASS | PASS | PASS | NO_TEST |
| `evaluate_pd_ch3_018_clarification_authorized_outcome` | `adapter_diff_spec_anchors.py:216` | PASS | PASS | PASS | PASS | PASS | NO_TEST |
| `evaluate_pd_ch3_020_spec_change_replay_point` | `adapter_diff_spec_anchors.py:254` | PASS | PASS | PASS | PASS | PASS | NO_TEST |
| `evaluate_b4_b_gate` | `adapter_diff_spec_anchors.py:298` | PASS | FAIL | FAIL | PASS | PASS | NO_TEST |
| `evaluate_pd_f10_001_contract_invocation` | `adapter_qualification_contract.py:77` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_f10_002_usable_adapter_binding` | `adapter_qualification_contract.py:113` | PASS | PASS | PASS | PASS | PASS | NO_TEST |
| `evaluate_pd_f10_003_adapter_registration_authority` | `adapter_qualification_contract.py:156` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_f10_004_execution_gate_enforcement` | `adapter_qualification_contract.py:194` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_f10_005_qualification_matrix` | `adapter_qualification_contract.py:233` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_f10_006_independent_verification` | `adapter_qualification_contract.py:279` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b4_a_gate` | `adapter_qualification_contract.py:316` | PASS | FAIL | FAIL | PASS | PASS | NO_TEST |
| `evaluate_f1_representation` | `artifacts.py:426` | FAIL | PASS | PASS | PASS | PASS | PASS |
| `evaluate_f7_claim` | `claim_ledger.py:282` | FAIL | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_f7_claim_ledger` | `claim_ledger.py:529` | FAIL | FAIL | FAIL | PASS | PASS | PASS |
| `evaluate_f7_claims` | `claim_ledger.py:628` | FAIL | FAIL | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch4_007_context_resume_anchors` | `context_resume_threats.py:32` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch4_008_threat_matrix_containment` | `context_resume_threats.py:62` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b4_f_gate` | `context_resume_threats.py:99` | PASS | FAIL | FAIL | PASS | PASS | NO_TEST |
| `evaluate_pd_ch8_008_prevention_boundary` | `enforcement_workspace_gate.py:32` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch8_009_workspace_promotion` | `enforcement_workspace_gate.py:62` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch8_010_out_of_band_edits` | `enforcement_workspace_gate.py:91` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch8_011_parallel_work_serialization` | `enforcement_workspace_gate.py:121` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch8_012_repository_intelligence` | `enforcement_workspace_gate.py:158` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch8_013_budget_exhaustion_ledger` | `enforcement_workspace_gate.py:187` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b5_gate` | `enforcement_workspace_gate.py:225` | PASS | FAIL | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch10_012_frozen_erratum_path` | `erratum_issue_registry.py:38` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch10_013_open_issue_schema` | `erratum_issue_registry.py:68` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch10_007_master_cross_links` | `erratum_issue_registry.py:116` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b9_c_gate` | `erratum_issue_registry.py:144` | PASS | FAIL | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch3_010_flow_baseline_binding` | `execution_flow_testinput.py:54` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_011_adapter_qualification_disclosure` | `execution_flow_testinput.py:86` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_012_ux_interruption_budget_authority` | `execution_flow_testinput.py:115` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_014_lifecycle_example_adversarial_failure` | `execution_flow_testinput.py:145` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch4_012_reference_exact_resolution` | `execution_flow_testinput.py:174` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch4_009_test_input_set_binding` | `execution_flow_testinput.py:220` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b4_d_gate` | `execution_flow_testinput.py:256` | PASS | FAIL | FAIL | PASS | PASS | NO_TEST |
| `evaluate_f4_lane_selection` | `f4_lane_selection.py:289` | FAIL | PASS | FAIL | PASS | PASS | PASS |
| `evaluate_f8_step_pack` | `f8_step_pack.py:166` | FAIL | PASS | PASS | PASS | PASS | PASS |
| `evaluate_f5_gate` | `gate_evaluator.py:139` | FAIL | FAIL | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch4_010_test_input_write_isolation` | `isolation_claims.py:32` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch4_014_authorized_delta_scope` | `isolation_claims.py:71` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch4_016_independent_evidence_producers` | `isolation_claims.py:101` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch4_002_execution_claim_receipt` | `isolation_claims.py:145` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch4_005_evidence_freshness_identity` | `isolation_claims.py:174` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch4_006_canonical_closure_vs_prose` | `isolation_claims.py:210` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b4_e_gate` | `isolation_claims.py:239` | PASS | FAIL | FAIL | PASS | PASS | NO_TEST |
| `evaluate_pd_ch6_007_package_metadata` | `knowledge_package_quarantine.py:48` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch6_008_precedence_and_conflicts` | `knowledge_package_quarantine.py:84` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch6_009_lifecycle_projection` | `knowledge_package_quarantine.py:112` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch6_010_quarantine_conditions` | `knowledge_package_quarantine.py:140` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch6_011_license_provenance_verification` | `knowledge_package_quarantine.py:179` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch6_012_steppack_digest_pinning` | `knowledge_package_quarantine.py:208` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b6_a_gate` | `knowledge_package_quarantine.py:238` | PASS | FAIL | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch2_001_single_lifecycle` | `lifecycle_p0a.py:59` | FAIL | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_002_eleven_dimensions` | `lifecycle_p0a.py:120` | FAIL | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_003_earlier_phase_validity` | `lifecycle_p0a.py:175` | FAIL | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_005_skipped_phase_applicability` | `lifecycle_p0a.py:219` | FAIL | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_006_earliest_defect_routing` | `lifecycle_p0a.py:275` | FAIL | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_055_downstream_invalidation` | `lifecycle_p0a.py:319` | FAIL | PASS | PASS | PASS | PASS | PASS |
| `evaluate_p0a_gate` | `lifecycle_p0a.py:373` | FAIL | FAIL | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch2_007_p8_retry_budget` | `lifecycle_p0b.py:37` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_008_p11_non_terminal_reentry` | `lifecycle_p0b.py:80` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_009_done_claim_evidence_closure` | `lifecycle_p0b.py:116` | PASS | PASS | PASS | PASS | PASS | NO_TEST |
| `evaluate_pd_ch2_010_green_external_run_evidence` | `lifecycle_p0b.py:151` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_011_stack_pack_phase_topology` | `lifecycle_p0b.py:185` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_012_mandatory_floor_human_waiver` | `lifecycle_p0b.py:213` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_p0b_gate` | `lifecycle_p0b.py:241` | PASS | PASS | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch2_054_signal` | `lifecycle_p11.py:48` | FAIL | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_058_applicability` | `lifecycle_p11.py:84` | FAIL | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_060_flow_order` | `lifecycle_p11.py:149` | FAIL | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_061_delivery_flow` | `lifecycle_p11.py:199` | FAIL | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_062_project_class` | `lifecycle_p11.py:245` | FAIL | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_063_question_budget` | `lifecycle_p11.py:288` | FAIL | PASS | PASS | PASS | PASS | PASS |
| `evaluate_p11_gate` | `lifecycle_p11.py:337` | FAIL | FAIL | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch2_056_discovery_completeness` | `lifecycle_p1_p4.py:37` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_057_skill_depth_precedence` | `lifecycle_p1_p4.py:80` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_029_task_caps` | `lifecycle_p1_p4.py:108` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_031_work_graph_acyclic` | `lifecycle_p1_p4.py:150` | PASS | PASS | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch2_032_write_set_overlap` | `lifecycle_p1_p4.py:196` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_p1_p4_gate` | `lifecycle_p1_p4.py:241` | PASS | PASS | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch2_013_requirement_coverage` | `lifecycle_p3a.py:32` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_014_domain_invariants` | `lifecycle_p3a.py:62` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_015_architecture_provenance` | `lifecycle_p3a.py:91` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_016_dependency_relationships` | `lifecycle_p3a.py:130` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_017_domain_model_substance` | `lifecycle_p3a.py:161` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_018_architecture_record_substance` | `lifecycle_p3a.py:201` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_p3a_gate` | `lifecycle_p3a.py:240` | PASS | PASS | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch2_020_decidable_invariants` | `lifecycle_p3b.py:38` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_021_cross_entity_constraints` | `lifecycle_p3b.py:71` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_022_change_surface_boundary_closure` | `lifecycle_p3b.py:101` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_023_boundary_data_flow_contracts` | `lifecycle_p3b.py:134` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_024_interface_signatures_typed_contracts` | `lifecycle_p3b.py:167` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_025_unknown_contradiction_handling` | `lifecycle_p3b.py:199` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_p3b_gate` | `lifecycle_p3b.py:226` | PASS | PASS | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch2_026_adr_design_digest_binding` | `lifecycle_p3c_p8_p10.py:47` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_028_unique_must_ids` | `lifecycle_p3c_p8_p10.py:79` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_051_p8_retry_budget_exhaustion` | `lifecycle_p3c_p8_p10.py:108` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_052_p9_task_aggregation_findings_closure` | `lifecycle_p3c_p8_p10.py:143` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_053_p10_kernel_release_evaluation` | `lifecycle_p3c_p8_p10.py:180` | PASS | PASS | FAIL | PASS | PASS | PASS |
| `evaluate_p3c_p8_p10_gate` | `lifecycle_p3c_p8_p10.py:220` | PASS | PASS | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch2_033_delta_sequence` | `lifecycle_p5.py:37` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_034_red_run_validity` | `lifecycle_p5.py:64` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_035_executable_spec_constraints` | `lifecycle_p5.py:119` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_036_adapter_qualification` | `lifecycle_p5.py:147` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_046_test_input_set_binding` | `lifecycle_p5.py:175` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_047_red_classification_source` | `lifecycle_p5.py:202` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_p5_gate` | `lifecycle_p5.py:240` | PASS | PASS | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch2_037_execution_gate_authorization` | `lifecycle_p6.py:30` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_038_scope_growth_stop` | `lifecycle_p6.py:59` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_039_implementation_claims` | `lifecycle_p6.py:95` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_040_canonical_delta_kernel_receipt` | `lifecycle_p6.py:123` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_048_test_input_set_exclusion_check` | `lifecycle_p6.py:151` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_p6_gate` | `lifecycle_p6.py:185` | PASS | PASS | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch2_041_evidence_binding` | `lifecycle_p7.py:37` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_042_adapter_qualification` | `lifecycle_p7.py:65` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_043_independence_floor` | `lifecycle_p7.py:93` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_044_freshness_predicate` | `lifecycle_p7.py:120` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_045_closure_ownership` | `lifecycle_p7.py:148` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_050_deterministic_rerun` | `lifecycle_p7.py:175` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_p7_gate` | `lifecycle_p7.py:209` | PASS | PASS | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch3_001_phase_artifact_anchors` | `lifecycle_phase_admission.py:50` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_002_normative_requirements_completeness` | `lifecycle_phase_admission.py:94` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_003_clarification_scope_entry` | `lifecycle_phase_admission.py:137` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_006_external_tool_candidate_trust` | `lifecycle_phase_admission.py:173` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_007_work_type_decision_projection` | `lifecycle_phase_admission.py:202` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_009_flow_gates_and_lane_computation` | `lifecycle_phase_admission.py:245` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b4_c_gate` | `lifecycle_phase_admission.py:289` | PASS | FAIL | FAIL | PASS | PASS | NO_TEST |
| `evaluate_f9_metric` | `metrics.py:472` | FAIL | PASS | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch7_014_notification_projections` | `notification_skill_normalization.py:26` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch7_015_external_skill_normalization` | `notification_skill_normalization.py:54` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b7_b_gate` | `notification_skill_normalization.py:82` | PASS | FAIL | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch6_013_stack_pack_adapters` | `oss_qualification_playbook.py:58` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch6_014_oss_qualification_record` | `oss_qualification_playbook.py:107` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch6_003_pack_activation` | `oss_qualification_playbook.py:160` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch6_006_playbook_content` | `oss_qualification_playbook.py:188` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b6_b_gate` | `oss_qualification_playbook.py:232` | PASS | FAIL | FAIL | PASS | PASS | PASS |
| `evaluate_performance_claim` | `performance_claims.py:78` | FAIL | PASS | PASS | PASS | PASS | PASS |
| `evaluate_predicate_input` | `predicate_evaluator.py:1262` | FAIL | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_ch2_064_replay_invalidation` | `replay.py:27` | FAIL | PASS | PASS | PASS | PASS | PASS |
| `evaluate_ch2_065_lifecycle_proof` | `replay.py:80` | FAIL | PASS | PASS | PASS | PASS | PASS |
| `evaluate_replay_gate` | `replay.py:152` | FAIL | FAIL | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch9_006_stratum_sampling_promotion` | `stratum_sampling_compatibility.py:64` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch9_007_secret_egress_claims` | `stratum_sampling_compatibility.py:108` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch10_008_explicit_compatibility` | `stratum_sampling_compatibility.py:136` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch10_009_audit_export_bindings` | `stratum_sampling_compatibility.py:172` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch10_010_roadmap_integrity` | `stratum_sampling_compatibility.py:208` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch10_011_fact_classification` | `stratum_sampling_compatibility.py:256` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b9_b_gate` | `stratum_sampling_compatibility.py:300` | PASS | FAIL | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch9_008_threat_coverage` | `threat_eval_regression_gate.py:64` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch9_009_eval_run_bindings` | `threat_eval_regression_gate.py:101` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch9_010_promotion_blockers` | `threat_eval_regression_gate.py:137` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch9_003_security_promotion_gate` | `threat_eval_regression_gate.py:165` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch9_004_metric_reporting_integrity` | `threat_eval_regression_gate.py:208` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch9_005_data_retention_policy` | `threat_eval_regression_gate.py:251` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b9_a_gate` | `threat_eval_regression_gate.py:280` | PASS | FAIL | FAIL | PASS | PASS | PASS |
| `evaluate_f6_traceability` | `traceability.py:405` | FAIL | FAIL | FAIL | PASS | PASS | PASS |
| `evaluate_claim` | `trust_model.py:258` | FAIL | FAIL | PASS | PASS | PASS | PASS |
| `check_structured_conflict` | `trust_model.py:472` | FAIL | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_requirement_confirmation` | `trust_model.py:504` | FAIL | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_confirmation_admissibility` | `trust_model.py:713` | FAIL | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_f3_trust` | `trust_model.py:804` | FAIL | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch7_016_wire_protocol_envelope` | `wire_session_consequential_gate.py:52` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch7_008_guidance_resources` | `wire_session_consequential_gate.py:103` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch7_009_protocol_idempotent_retries` | `wire_session_consequential_gate.py:132` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch7_011_ide_mode_capabilities` | `wire_session_consequential_gate.py:168` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch7_012_session_identity_bindings` | `wire_session_consequential_gate.py:196` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch7_013_consequential_developer_actions` | `wire_session_consequential_gate.py:240` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b7_a_gate` | `wire_session_consequential_gate.py:268` | PASS | FAIL | FAIL | PASS | PASS | PASS |
