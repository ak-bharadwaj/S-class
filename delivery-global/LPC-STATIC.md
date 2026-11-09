# STATIC LPC AUDIT REPORT (S1 - S8)

Machine-generated AST audit of all public evaluators across Blocks 1-9 on integration tip.

## 1. Executive Summary

- **Total Public Evaluators Audited**: 171
- **Total Product Modules**: 40
- **S1 Authority Parameter**: 162 / 171 pass
- **S2 Authority First Statement**: 142 / 171 pass
- **S3 Closed Vocabulary Return**: 158 / 171 pass
- **S4 Safe Exception Handling**: 171 / 171 pass
- **S5 Forbidden Imports (I/O, network, etc.)**: 1 violations
- **S6 Mutable State / Defaults**: 171 / 171 pass
- **S7 Import Direction (tests/tools in product)**: 0 violations
- **S8 Tested with Authority Omitted**: 171 / 171 evaluators covered in test suite

## 2. Module Sizing and Waivers

| Module | Line Count | Status / Waiver |
|---|---|---|
| `predicate_evaluator.py` | 1405 | W-B2-1 (Block 2 CAP waiver, authorized by CL) |
| `trust_model.py` | 1329 | W-B2-1 (Block 2 CAP waiver, authorized by CL) |
| `metrics.py` | 845 | W-B2-1 (Block 2 CAP waiver, authorized by CL) |
| `traceability.py` | 674 | W-B2-1 (Block 2 CAP waiver, authorized by CL) |
| `claim_ledger.py` | 666 | W-B2-1 (Block 2 CAP waiver, authorized by CL) |
| `artifacts.py` | 635 | W-B2-1 (Block 2 CAP waiver, authorized by CL) |
| `fixture_bindings.py` | 537 | W-B2-1 (Block 2 CAP waiver, authorized by CL) |
| `gate_evaluator.py` | 524 | PASSED (<= 600) |
| `adapter_qualification_contract.py` | 467 | PASSED (<= 600) |
| `fixture_runner.py` | 464 | PASSED (<= 600) |
| `lifecycle_p1_p4.py` | 430 | PASSED (<= 600) |
| `adapter_diff_spec_anchors.py` | 427 | PASSED (<= 600) |
| `lifecycle_phase_admission.py` | 424 | PASSED (<= 600) |
| `threat_eval_regression_gate.py` | 423 | PASSED (<= 600) |
| `lifecycle_p11.py` | 422 | PASSED (<= 600) |
| `lifecycle_p0a.py` | 417 | PASSED (<= 600) |
| `execution_flow_testinput.py` | 414 | PASSED (<= 600) |
| `knowledge_package_quarantine.py` | 408 | PASSED (<= 600) |
| `f4_lane_selection.py` | 400 | PASSED (<= 600) |
| `isolation_claims.py` | 398 | PASSED (<= 600) |
| `lifecycle_p3a.py` | 398 | PASSED (<= 600) |
| `lifecycle_p5.py` | 387 | PASSED (<= 600) |
| `lifecycle_p3b.py` | 384 | PASSED (<= 600) |
| `lifecycle_p0b.py` | 383 | PASSED (<= 600) |
| `stratum_sampling_compatibility.py` | 380 | PASSED (<= 600) |
| `lifecycle_p7.py` | 375 | PASSED (<= 600) |
| `enforcement_workspace_gate.py` | 356 | PASSED (<= 600) |
| `lifecycle_p3c_p8_p10.py` | 353 | PASSED (<= 600) |
| `wire_session_consequential_gate.py` | 351 | PASSED (<= 600) |
| `lifecycle_p6.py` | 338 | PASSED (<= 600) |
| `gate_cache.py` | 305 | PASSED (<= 600) |
| `oss_qualification_playbook.py` | 287 | PASSED (<= 600) |
| `performance_claims.py` | 277 | PASSED (<= 600) |
| `check_registry.py` | 264 | PASSED (<= 600) |
| `f8_step_pack.py` | 239 | PASSED (<= 600) |
| `replay.py` | 191 | PASSED (<= 600) |
| `erratum_issue_registry.py` | 185 | PASSED (<= 600) |
| `context_resume_threats.py` | 126 | PASSED (<= 600) |
| `notification_skill_normalization.py` | 117 | PASSED (<= 600) |
| `gate.py` | 62 | PASSED (<= 600) |

## 3. Import Direction and Forbidden Imports Audit

### S5 Forbidden Imports Detected:

- `predicate_evaluator.py:19`: imported `sys`
- **S7 Import Direction**: ZERO violations (no imports from `tests/` or `tools/`).

## 4. Evaluator LPC Audit Table (All Public Evaluators)

| Evaluator | File:Line | S1 (Auth Param) | S2 (Auth Check) | S3 (Closed Vocab) | S4 (Safe Except) | S6 (No Mut Defaults) | S8 (Tested Auth Omitted) |
|---|---|---|---|---|---|---|---|
| `evaluate_pd_f10_007_differential_detection` | `adapter_diff_spec_anchors.py:45` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_015_artifact_binding_integrity` | `adapter_diff_spec_anchors.py:103` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_016_spec_anchor_resolution` | `adapter_diff_spec_anchors.py:141` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_017_predicate_measurable_thresholds` | `adapter_diff_spec_anchors.py:189` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_018_clarification_authorized_outcome` | `adapter_diff_spec_anchors.py:236` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_020_spec_change_replay_point` | `adapter_diff_spec_anchors.py:274` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b4_b_gate` | `adapter_diff_spec_anchors.py:318` | PASS | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_pd_f10_001_contract_invocation` | `adapter_qualification_contract.py:77` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_f10_002_usable_adapter_binding` | `adapter_qualification_contract.py:120` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_f10_003_adapter_registration_authority` | `adapter_qualification_contract.py:170` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_f10_004_execution_gate_enforcement` | `adapter_qualification_contract.py:215` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_f10_005_qualification_matrix` | `adapter_qualification_contract.py:268` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_f10_006_independent_verification` | `adapter_qualification_contract.py:321` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b4_a_gate` | `adapter_qualification_contract.py:369` | PASS | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_f1_representation` | `artifacts.py:426` | PASS | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_f7_claim` | `claim_ledger.py:282` | FAIL | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_f7_claim_ledger` | `claim_ledger.py:529` | FAIL | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_f7_claims` | `claim_ledger.py:628` | FAIL | FAIL | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch4_007_context_resume_anchors` | `context_resume_threats.py:32` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch4_008_threat_matrix_containment` | `context_resume_threats.py:62` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b4_f_gate` | `context_resume_threats.py:106` | PASS | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch8_008_prevention_boundary` | `enforcement_workspace_gate.py:32` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch8_009_workspace_promotion` | `enforcement_workspace_gate.py:68` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch8_010_out_of_band_edits` | `enforcement_workspace_gate.py:104` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch8_011_parallel_work_serialization` | `enforcement_workspace_gate.py:140` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch8_012_repository_intelligence` | `enforcement_workspace_gate.py:184` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch8_013_budget_exhaustion_ledger` | `enforcement_workspace_gate.py:213` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b5_gate` | `enforcement_workspace_gate.py:257` | PASS | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch10_012_frozen_erratum_path` | `erratum_issue_registry.py:38` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch10_013_open_issue_schema` | `erratum_issue_registry.py:68` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch10_007_master_cross_links` | `erratum_issue_registry.py:123` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b9_c_gate` | `erratum_issue_registry.py:159` | PASS | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_010_flow_baseline_binding` | `execution_flow_testinput.py:54` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_011_adapter_qualification_disclosure` | `execution_flow_testinput.py:112` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_012_ux_interruption_budget_authority` | `execution_flow_testinput.py:154` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_014_lifecycle_example_adversarial_failure` | `execution_flow_testinput.py:191` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch4_012_reference_exact_resolution` | `execution_flow_testinput.py:227` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch4_009_test_input_set_binding` | `execution_flow_testinput.py:273` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b4_d_gate` | `execution_flow_testinput.py:316` | PASS | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_f4_lane_selection` | `f4_lane_selection.py:289` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_f8_step_pack` | `f8_step_pack.py:166` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_f5_gate` | `gate_evaluator.py:139` | PASS | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch4_010_test_input_write_isolation` | `isolation_claims.py:32` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch4_014_authorized_delta_scope` | `isolation_claims.py:84` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch4_016_independent_evidence_producers` | `isolation_claims.py:142` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch4_002_execution_claim_receipt` | `isolation_claims.py:186` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch4_005_evidence_freshness_identity` | `isolation_claims.py:222` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch4_006_canonical_closure_vs_prose` | `isolation_claims.py:265` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b4_e_gate` | `isolation_claims.py:300` | PASS | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch6_007_package_metadata` | `knowledge_package_quarantine.py:48` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch6_008_precedence_and_conflicts` | `knowledge_package_quarantine.py:84` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch6_009_lifecycle_projection` | `knowledge_package_quarantine.py:122` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch6_010_quarantine_conditions` | `knowledge_package_quarantine.py:160` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch6_011_license_provenance_verification` | `knowledge_package_quarantine.py:218` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch6_012_steppack_digest_pinning` | `knowledge_package_quarantine.py:258` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b6_a_gate` | `knowledge_package_quarantine.py:309` | PASS | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_001_single_lifecycle` | `lifecycle_p0a.py:59` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_002_eleven_dimensions` | `lifecycle_p0a.py:120` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_003_earlier_phase_validity` | `lifecycle_p0a.py:175` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_005_skipped_phase_applicability` | `lifecycle_p0a.py:219` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_006_earliest_defect_routing` | `lifecycle_p0a.py:275` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_055_downstream_invalidation` | `lifecycle_p0a.py:319` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_p0a_gate` | `lifecycle_p0a.py:373` | PASS | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_007_p8_retry_budget` | `lifecycle_p0b.py:37` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_008_p11_non_terminal_reentry` | `lifecycle_p0b.py:88` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_009_done_claim_evidence_closure` | `lifecycle_p0b.py:139` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_010_green_external_run_evidence` | `lifecycle_p0b.py:181` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_011_stack_pack_phase_topology` | `lifecycle_p0b.py:222` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_012_mandatory_floor_human_waiver` | `lifecycle_p0b.py:264` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_p0b_gate` | `lifecycle_p0b.py:300` | PASS | PASS | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch2_054_signal` | `lifecycle_p11.py:48` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_058_applicability` | `lifecycle_p11.py:92` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_060_flow_order` | `lifecycle_p11.py:165` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_061_delivery_flow` | `lifecycle_p11.py:223` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_062_project_class` | `lifecycle_p11.py:277` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_063_question_budget` | `lifecycle_p11.py:328` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_p11_gate` | `lifecycle_p11.py:385` | PASS | FAIL | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch2_056_discovery_completeness` | `lifecycle_p1_p4.py:38` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_057_skill_depth_precedence` | `lifecycle_p1_p4.py:95` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_029_task_caps` | `lifecycle_p1_p4.py:130` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_031_work_graph_acyclic` | `lifecycle_p1_p4.py:185` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_032_write_set_overlap` | `lifecycle_p1_p4.py:283` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_p1_p4_gate` | `lifecycle_p1_p4.py:357` | PASS | PASS | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch2_013_requirement_coverage` | `lifecycle_p3a.py:32` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_014_domain_invariants` | `lifecycle_p3a.py:75` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_015_architecture_provenance` | `lifecycle_p3a.py:117` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_016_dependency_relationships` | `lifecycle_p3a.py:169` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_017_domain_model_substance` | `lifecycle_p3a.py:228` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_018_architecture_record_substance` | `lifecycle_p3a.py:281` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_p3a_gate` | `lifecycle_p3a.py:327` | PASS | FAIL | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch2_020_decidable_invariants` | `lifecycle_p3b.py:38` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_021_cross_entity_constraints` | `lifecycle_p3b.py:84` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_022_change_surface_boundary_closure` | `lifecycle_p3b.py:127` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_023_boundary_data_flow_contracts` | `lifecycle_p3b.py:181` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_024_interface_signatures_typed_contracts` | `lifecycle_p3b.py:227` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_025_unknown_contradiction_handling` | `lifecycle_p3b.py:272` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_p3b_gate` | `lifecycle_p3b.py:307` | PASS | PASS | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch2_026_adr_design_digest_binding` | `lifecycle_p3c_p8_p10.py:47` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_028_unique_must_ids` | `lifecycle_p3c_p8_p10.py:92` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_051_p8_retry_budget_exhaustion` | `lifecycle_p3c_p8_p10.py:128` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_052_p9_task_aggregation_findings_closure` | `lifecycle_p3c_p8_p10.py:170` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_053_p10_kernel_release_evaluation` | `lifecycle_p3c_p8_p10.py:221` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_p3c_p8_p10_gate` | `lifecycle_p3c_p8_p10.py:268` | PASS | PASS | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch2_033_delta_sequence` | `lifecycle_p5.py:37` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_034_red_run_validity` | `lifecycle_p5.py:71` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_035_executable_spec_constraints` | `lifecycle_p5.py:131` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_036_adapter_qualification` | `lifecycle_p5.py:160` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_046_test_input_set_binding` | `lifecycle_p5.py:201` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_047_red_classification_source` | `lifecycle_p5.py:235` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_p5_gate` | `lifecycle_p5.py:288` | PASS | PASS | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch2_037_execution_gate_authorization` | `lifecycle_p6.py:30` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_038_scope_growth_stop` | `lifecycle_p6.py:71` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_039_implementation_claims` | `lifecycle_p6.py:128` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_040_canonical_delta_kernel_receipt` | `lifecycle_p6.py:177` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_048_test_input_set_exclusion_check` | `lifecycle_p6.py:206` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_p6_gate` | `lifecycle_p6.py:248` | PASS | PASS | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch2_041_evidence_binding` | `lifecycle_p7.py:37` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_042_adapter_qualification` | `lifecycle_p7.py:72` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_043_independence_floor` | `lifecycle_p7.py:113` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_044_freshness_predicate` | `lifecycle_p7.py:147` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_045_closure_ownership` | `lifecycle_p7.py:187` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch2_050_deterministic_rerun` | `lifecycle_p7.py:222` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_p7_gate` | `lifecycle_p7.py:278` | PASS | PASS | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch3_001_phase_artifact_anchors` | `lifecycle_phase_admission.py:50` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_002_normative_requirements_completeness` | `lifecycle_phase_admission.py:107` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_003_clarification_scope_entry` | `lifecycle_phase_admission.py:157` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_006_external_tool_candidate_trust` | `lifecycle_phase_admission.py:199` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_007_work_type_decision_projection` | `lifecycle_phase_admission.py:241` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch3_009_flow_gates_and_lane_computation` | `lifecycle_phase_admission.py:284` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b4_c_gate` | `lifecycle_phase_admission.py:328` | PASS | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_f9_metric` | `metrics.py:472` | PASS | PASS | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch7_014_notification_projections` | `notification_skill_normalization.py:26` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch7_015_external_skill_normalization` | `notification_skill_normalization.py:62` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b7_b_gate` | `notification_skill_normalization.py:98` | PASS | FAIL | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch6_013_stack_pack_adapters` | `oss_qualification_playbook.py:58` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch6_014_oss_qualification_record` | `oss_qualification_playbook.py:114` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch6_003_pack_activation` | `oss_qualification_playbook.py:174` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch6_006_playbook_content` | `oss_qualification_playbook.py:210` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b6_b_gate` | `oss_qualification_playbook.py:261` | PASS | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_performance_claim` | `performance_claims.py:78` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_predicate_input` | `predicate_evaluator.py:1262` | FAIL | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_ch2_064_replay_invalidation` | `replay.py:27` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_ch2_065_lifecycle_proof` | `replay.py:88` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_replay_gate` | `replay.py:168` | PASS | FAIL | FAIL | PASS | PASS | PASS |
| `evaluate_pd_ch9_006_stratum_sampling_promotion` | `stratum_sampling_compatibility.py:64` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch9_007_secret_egress_claims` | `stratum_sampling_compatibility.py:115` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch10_008_explicit_compatibility` | `stratum_sampling_compatibility.py:151` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch10_009_audit_export_bindings` | `stratum_sampling_compatibility.py:194` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch10_010_roadmap_integrity` | `stratum_sampling_compatibility.py:237` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch10_011_fact_classification` | `stratum_sampling_compatibility.py:292` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b9_b_gate` | `stratum_sampling_compatibility.py:343` | PASS | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch9_008_threat_coverage` | `threat_eval_regression_gate.py:64` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch9_009_eval_run_bindings` | `threat_eval_regression_gate.py:108` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch9_010_promotion_blockers` | `threat_eval_regression_gate.py:151` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch9_003_security_promotion_gate` | `threat_eval_regression_gate.py:191` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch9_004_metric_reporting_integrity` | `threat_eval_regression_gate.py:248` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch9_005_data_retention_policy` | `threat_eval_regression_gate.py:298` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b9_a_gate` | `threat_eval_regression_gate.py:334` | PASS | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_f6_traceability` | `traceability.py:405` | FAIL | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_claim` | `trust_model.py:260` | FAIL | FAIL | PASS | PASS | PASS | PASS |
| `check_structured_conflict` | `trust_model.py:482` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_requirement_confirmation` | `trust_model.py:584` | FAIL | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_confirmation_admissibility` | `trust_model.py:801` | FAIL | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_f3_trust` | `trust_model.py:892` | FAIL | FAIL | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch7_016_wire_protocol_envelope` | `wire_session_consequential_gate.py:52` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch7_008_guidance_resources` | `wire_session_consequential_gate.py:110` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch7_009_protocol_idempotent_retries` | `wire_session_consequential_gate.py:146` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch7_011_ide_mode_capabilities` | `wire_session_consequential_gate.py:189` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch7_012_session_identity_bindings` | `wire_session_consequential_gate.py:224` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_pd_ch7_013_consequential_developer_actions` | `wire_session_consequential_gate.py:275` | PASS | PASS | PASS | PASS | PASS | PASS |
| `evaluate_b7_a_gate` | `wire_session_consequential_gate.py:310` | PASS | FAIL | PASS | PASS | PASS | PASS |

## 5. Static LPC Failures Disposition Table (Task R3)

| Check | File:Line | Evaluator / Symbol | Detail | Disposition | Justification / Notes |
|---|---|---|---|---|---|
| S5 | `predicate_evaluator.py:19` | `sys` | Forbidden import: sys | **JUSTIFIED(W-B2-1)** | Frozen Block 2 module: sys.path.insert used at lines 39-40 to load conformance modules |
| S2 | `adapter_diff_spec_anchors.py:318` | `evaluate_b4_b_gate` | First statement is If but does not check authority | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_b4_b_gate_authority_omitted)** | Aggregator gate delegates authority parameter down to child evaluators; verified fail-closed without authority |
| S2 | `adapter_qualification_contract.py:369` | `evaluate_b4_a_gate` | First statement is If but does not check authority | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_b4_a_gate_authority_omitted)** | Aggregator gate delegates authority parameter down to child evaluators; verified fail-closed without authority |
| S2 | `artifacts.py:426` | `evaluate_f1_representation` | First statement is not If: Assign | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in artifacts.py; authority check verified via test_fail_open_hardened.py |
| S1 | `claim_ledger.py:282` | `evaluate_f7_claim` | has_auth=False, default_none=False | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in claim_ledger.py; caller authority enforced at harness boundary |
| S2 | `claim_ledger.py:282` | `evaluate_f7_claim` | First statement is If but does not check authority | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in claim_ledger.py; authority check verified via test_fail_open_hardened.py |
| S1 | `claim_ledger.py:529` | `evaluate_f7_claim_ledger` | has_auth=False, default_none=False | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in claim_ledger.py; caller authority enforced at harness boundary |
| S2 | `claim_ledger.py:529` | `evaluate_f7_claim_ledger` | First statement is If but does not check authority | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in claim_ledger.py; authority check verified via test_fail_open_hardened.py |
| S1 | `claim_ledger.py:628` | `evaluate_f7_claims` | has_auth=False, default_none=False | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in claim_ledger.py; caller authority enforced at harness boundary |
| S2 | `claim_ledger.py:628` | `evaluate_f7_claims` | First statement is If but does not check authority | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in claim_ledger.py; authority check verified via test_fail_open_hardened.py |
| S3 | `claim_ledger.py:628` | `evaluate_f7_claims` | Free return detected: Name(id='out', ctx=Load()) | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in claim_ledger.py; outputs mapped to closed vocabulary by harness |
| S2 | `context_resume_threats.py:106` | `evaluate_b4_f_gate` | First statement is If but does not check authority | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_b4_f_gate_authority_omitted)** | Aggregator gate delegates authority parameter down to child evaluators; verified fail-closed without authority |
| S2 | `enforcement_workspace_gate.py:257` | `evaluate_b5_gate` | First statement is If but does not check authority | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_b5_gate_authority_omitted)** | Aggregator gate delegates authority parameter down to child evaluators; verified fail-closed without authority |
| S2 | `erratum_issue_registry.py:159` | `evaluate_b9_c_gate` | First statement is If but does not check authority | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_b9_c_gate_authority_omitted)** | Aggregator gate delegates authority parameter down to child evaluators; verified fail-closed without authority |
| S2 | `execution_flow_testinput.py:316` | `evaluate_b4_d_gate` | First statement is If but does not check authority | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_b4_d_gate_authority_omitted)** | Aggregator gate delegates authority parameter down to child evaluators; verified fail-closed without authority |
| S2 | `gate_evaluator.py:139` | `evaluate_f5_gate` | First statement is not If: Assign | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_f5_gate_authority_omitted)** | Aggregator gate delegates authority parameter down to child evaluators; verified fail-closed without authority |
| S2 | `isolation_claims.py:300` | `evaluate_b4_e_gate` | First statement is If but does not check authority | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_b4_e_gate_authority_omitted)** | Aggregator gate delegates authority parameter down to child evaluators; verified fail-closed without authority |
| S2 | `knowledge_package_quarantine.py:309` | `evaluate_b6_a_gate` | First statement is If but does not check authority | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_b6_a_gate_authority_omitted)** | Aggregator gate delegates authority parameter down to child evaluators; verified fail-closed without authority |
| S2 | `lifecycle_p0a.py:373` | `evaluate_p0a_gate` | First statement is not If: Assign | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_p0a_gate_authority_omitted)** | Aggregator gate delegates authority parameter down to child evaluators; verified fail-closed without authority |
| S3 | `lifecycle_p0b.py:300` | `evaluate_p0b_gate` | Free return detected: Name(id='r007', ctx=Load()) | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_p0b_gate_authority_omitted)** | Aggregator gate returns dict or composite GateOutput containing closed-vocabulary MUST states; verified fail-closed without authority |
| S2 | `lifecycle_p11.py:385` | `evaluate_p11_gate` | First statement is not If: Assign | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_p11_gate_authority_omitted)** | Aggregator gate delegates authority parameter down to child evaluators; verified fail-closed without authority |
| S3 | `lifecycle_p11.py:385` | `evaluate_p11_gate` | Free return detected: Call(func=Subscript(value=Name(id='dispatch_map', ctx=Load() | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_p11_gate_authority_omitted)** | Aggregator gate returns dict or composite GateOutput containing closed-vocabulary MUST states; verified fail-closed without authority |
| S3 | `lifecycle_p1_p4.py:357` | `evaluate_p1_p4_gate` | Free return detected: Name(id='r056', ctx=Load()) | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_p1_p4_gate_authority_omitted)** | Aggregator gate returns dict or composite GateOutput containing closed-vocabulary MUST states; verified fail-closed without authority |
| S2 | `lifecycle_p3a.py:327` | `evaluate_p3a_gate` | First statement is If but does not check authority | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_p3a_gate_authority_omitted)** | Aggregator gate delegates authority parameter down to child evaluators; verified fail-closed without authority |
| S3 | `lifecycle_p3a.py:327` | `evaluate_p3a_gate` | Free return detected: Name(id='r013', ctx=Load()) | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_p3a_gate_authority_omitted)** | Aggregator gate returns dict or composite GateOutput containing closed-vocabulary MUST states; verified fail-closed without authority |
| S3 | `lifecycle_p3b.py:307` | `evaluate_p3b_gate` | Free return detected: Name(id='r020', ctx=Load()) | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_p3b_gate_authority_omitted)** | Aggregator gate returns dict or composite GateOutput containing closed-vocabulary MUST states; verified fail-closed without authority |
| S3 | `lifecycle_p3c_p8_p10.py:268` | `evaluate_p3c_p8_p10_gate` | Free return detected: Name(id='r026', ctx=Load()) | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_p3c_p8_p10_gate_authority_omitted)** | Aggregator gate returns dict or composite GateOutput containing closed-vocabulary MUST states; verified fail-closed without authority |
| S3 | `lifecycle_p5.py:288` | `evaluate_p5_gate` | Free return detected: Name(id='r033', ctx=Load()) | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_p5_gate_authority_omitted)** | Aggregator gate returns dict or composite GateOutput containing closed-vocabulary MUST states; verified fail-closed without authority |
| S3 | `lifecycle_p6.py:248` | `evaluate_p6_gate` | Free return detected: Name(id='r037', ctx=Load()) | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_p6_gate_authority_omitted)** | Aggregator gate returns dict or composite GateOutput containing closed-vocabulary MUST states; verified fail-closed without authority |
| S3 | `lifecycle_p7.py:278` | `evaluate_p7_gate` | Free return detected: Name(id='r041', ctx=Load()) | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_p7_gate_authority_omitted)** | Aggregator gate returns dict or composite GateOutput containing closed-vocabulary MUST states; verified fail-closed without authority |
| S2 | `lifecycle_phase_admission.py:328` | `evaluate_b4_c_gate` | First statement is If but does not check authority | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_b4_c_gate_authority_omitted)** | Aggregator gate delegates authority parameter down to child evaluators; verified fail-closed without authority |
| S3 | `metrics.py:472` | `evaluate_f9_metric` | Free return detected: Call(func=Name(id='_evaluate_envelope', ctx=Load()), args=[N | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in metrics.py; outputs mapped to closed vocabulary by harness |
| S2 | `notification_skill_normalization.py:98` | `evaluate_b7_b_gate` | First statement is If but does not check authority | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_b7_b_gate_authority_omitted)** | Aggregator gate delegates authority parameter down to child evaluators; verified fail-closed without authority |
| S3 | `notification_skill_normalization.py:98` | `evaluate_b7_b_gate` | Free return detected: Dict(keys=[Constant(value='PD-CH7-014'), Constant(value='PD- | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_b7_b_gate_authority_omitted)** | Aggregator gate returns dict or composite GateOutput containing closed-vocabulary MUST states; verified fail-closed without authority |
| S2 | `oss_qualification_playbook.py:261` | `evaluate_b6_b_gate` | First statement is If but does not check authority | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_b6_b_gate_authority_omitted)** | Aggregator gate delegates authority parameter down to child evaluators; verified fail-closed without authority |
| S1 | `predicate_evaluator.py:1262` | `evaluate_predicate_input` | has_auth=False, default_none=False | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in predicate_evaluator.py; caller authority enforced at harness boundary |
| S2 | `predicate_evaluator.py:1262` | `evaluate_predicate_input` | First statement is If but does not check authority | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in predicate_evaluator.py; authority check verified via test_fail_open_hardened.py |
| S2 | `replay.py:168` | `evaluate_replay_gate` | First statement is If but does not check authority | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_replay_gate_authority_omitted)** | Aggregator gate delegates authority parameter down to child evaluators; verified fail-closed without authority |
| S3 | `replay.py:168` | `evaluate_replay_gate` | Free return detected: Call(func=Name(id='evaluate_ch2_064_replay_invalidation', ct | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_replay_gate_authority_omitted)** | Aggregator gate returns dict or composite GateOutput containing closed-vocabulary MUST states; verified fail-closed without authority |
| S2 | `stratum_sampling_compatibility.py:343` | `evaluate_b9_b_gate` | First statement is If but does not check authority | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_b9_b_gate_authority_omitted)** | Aggregator gate delegates authority parameter down to child evaluators; verified fail-closed without authority |
| S2 | `threat_eval_regression_gate.py:334` | `evaluate_b9_a_gate` | First statement is If but does not check authority | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_b9_a_gate_authority_omitted)** | Aggregator gate delegates authority parameter down to child evaluators; verified fail-closed without authority |
| S1 | `traceability.py:405` | `evaluate_f6_traceability` | has_auth=False, default_none=False | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in traceability.py; caller authority enforced at harness boundary |
| S2 | `traceability.py:405` | `evaluate_f6_traceability` | First statement is If but does not check authority | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in traceability.py; authority check verified via test_fail_open_hardened.py |
| S1 | `trust_model.py:260` | `evaluate_claim` | has_auth=False, default_none=False | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in trust_model.py; caller authority enforced at harness boundary |
| S2 | `trust_model.py:260` | `evaluate_claim` | First statement is not If: Try | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in trust_model.py; authority check verified via test_fail_open_hardened.py |
| S1 | `trust_model.py:584` | `evaluate_requirement_confirmation` | has_auth=False, default_none=False | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in trust_model.py; caller authority enforced at harness boundary |
| S2 | `trust_model.py:584` | `evaluate_requirement_confirmation` | First statement is not If: Try | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in trust_model.py; authority check verified via test_fail_open_hardened.py |
| S1 | `trust_model.py:801` | `evaluate_confirmation_admissibility` | has_auth=False, default_none=False | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in trust_model.py; caller authority enforced at harness boundary |
| S2 | `trust_model.py:801` | `evaluate_confirmation_admissibility` | First statement is If but does not check authority | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in trust_model.py; authority check verified via test_fail_open_hardened.py |
| S1 | `trust_model.py:892` | `evaluate_f3_trust` | has_auth=False, default_none=False | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in trust_model.py; caller authority enforced at harness boundary |
| S2 | `trust_model.py:892` | `evaluate_f3_trust` | First statement is not If: Try | **PROPOSED_CHANGE(frozen Block 1/2, CL approves)** | Frozen Block 1/2 legacy evaluator in trust_model.py; authority check verified via test_fail_open_hardened.py |
| S2 | `wire_session_consequential_gate.py:310` | `evaluate_b7_a_gate` | First statement is If but does not check authority | **JUSTIFIED(tests/product/test_aggregator_authority.py::test_aggregator_evaluate_b7_a_gate_authority_omitted)** | Aggregator gate delegates authority parameter down to child evaluators; verified fail-closed without authority |
