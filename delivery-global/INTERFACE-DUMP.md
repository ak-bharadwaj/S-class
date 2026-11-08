# INTERFACE DUMP: Blocks 3 through 9 Public Evaluators (Task G6)

Machine-generated AST interface sheet for CL and GPT audit review.

## Block 3 (Lanes F4, E, P11, P0A, P0B, P1P4, P3A, P3B, P3C, P5, P6, P7)

### Module `f4_lane_selection.py`

#### `resolve_effective_depth` (line 148)
```python
def resolve_effective_depth(profile_derived_depth: Union[str, DepthLevel], policy_floor: Union[str, DepthLevel]) -> Tuple[str, str]
```
- **Authority Parameter**: `None`
- **Description**: Resolves effective depth honoring policy floor precedence (PD-F4-006).

#### `get_depth_budget` (line 161)
```python
def get_depth_budget(depth: Union[str, DepthLevel]) -> BudgetTriple
```
- **Authority Parameter**: `None`
- **Description**: Looks up declared assignment budget triple by depth level (PD-F4-004).

#### `compute_lane` (line 171)
```python
def compute_lane(payload: Mapping[str, Any], policy_floor: Optional[str] = None) -> Lane
```
- **Authority Parameter**: `None`
- **Description**: Computes deterministic lane from canonical inputs (PD-F4-001, PD-F4-002, PD-F4-006).

#### `record_lane_escalation` (line 260)
```python
def record_lane_escalation(canonical_profile_revision: int, prior_lane: str, escalated_lane: str, reason: str, authorized_decision: Optional[str] = None) -> EscalationRecord
```
- **Authority Parameter**: `None`
- **Description**: Stores lane escalation as a canonical profile revision (PD-F4-005).

#### `replay_lane` (line 277)
```python
def replay_lane(replayed_profile_revision: int, escalations: Sequence[EscalationRecord], default_lane: Lane = Lane.STANDARD) -> Lane
```
- **Authority Parameter**: `None`
- **Description**: Reproduces escalated lane deterministically on replay (PD-F4-005).

#### `evaluate_f4_lane_selection` (line 289)
```python
def evaluate_f4_lane_selection(payload: Mapping[str, Any], caller_authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `None`
- **Description**: Evaluates lane selection gate conformance (PD-F4-001..PD-F4-006).

### Module `f8_step_pack.py`

#### `truncate_context_items` (line 56)
```python
def truncate_context_items(items: Sequence[str], item_bytes: Mapping[str, int], precedence: Sequence[str], budget_bytes: int) -> Tuple[str, ...]
```
- **Authority Parameter**: `None`
- **Description**: Deterministically orders and truncates context items by precedence (PD-F8-002).

#### `compile_step_pack` (line 86)
```python
def compile_step_pack(phase: str, task_ref: str, canonical_state_binding: str, pinned_skills: Sequence[str], context_budget_bytes: int, compiler_version: str = DEFAULT_COMPILER_VERSION, context_items: Optional[Sequence[str]] = None, item_bytes: Optional[Mapping[str, int]] = None, precedence: Optional[Sequence[str]] = None, anchors: Optional[Sequence[str]] = None) -> StepPack
```
- **Authority Parameter**: `None`
- **Description**: Pure compilation function emitting canonical bytes and digest (PD-F8-001, PD-F8-004).

#### `resume_step_pack` (line 144)
```python
def resume_step_pack(canonical_state_binding: str, anchors: Sequence[str], transcript_present: bool = True, pinned_skills: Sequence[str] = ('SK-1', 'SK-2'), context_budget_bytes: int = 4096, compiler_version: str = DEFAULT_COMPILER_VERSION) -> Tuple[Tuple[str, ...], str]
```
- **Authority Parameter**: `None`
- **Description**: Resumes step-pack state from canonical binding & anchors, ignoring transcript (PD-F8-003).

#### `evaluate_f8_step_pack` (line 166)
```python
def evaluate_f8_step_pack(payload: Mapping[str, Any], caller_authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `None`
- **Description**: Evaluates F8 step-pack conformance (PD-F8-001..PD-F8-004).

### Module `lifecycle_p11.py`

#### `evaluate_pd_ch2_054_signal` (line 48)
```python
def evaluate_pd_ch2_054_signal(payload: Mapping[str, Any], caller_authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `None`
- **Description**: Evaluates P11 monitoring signals (PD-CH2-054).

#### `evaluate_pd_ch2_058_applicability` (line 84)
```python
def evaluate_pd_ch2_058_applicability(payload: Mapping[str, Any], caller_authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `None`
- **Description**: Evaluates work type phase applicability matrix coverage (PD-CH2-058).

#### `evaluate_pd_ch2_060_flow_order` (line 149)
```python
def evaluate_pd_ch2_060_flow_order(payload: Mapping[str, Any], caller_authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `None`
- **Description**: Evaluates user-facing default flow order preservation (PD-CH2-060).

#### `evaluate_pd_ch2_061_delivery_flow` (line 199)
```python
def evaluate_pd_ch2_061_delivery_flow(payload: Mapping[str, Any], caller_authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `None`
- **Description**: Evaluates operations/delivery flow binding (PD-CH2-061).

#### `evaluate_pd_ch2_062_project_class` (line 245)
```python
def evaluate_pd_ch2_062_project_class(payload: Mapping[str, Any], caller_authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `None`
- **Description**: Evaluates project-class qualification (PD-CH2-062).

#### `evaluate_pd_ch2_063_question_budget` (line 288)
```python
def evaluate_pd_ch2_063_question_budget(payload: Mapping[str, Any], caller_authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `None`
- **Description**: Evaluates human question budget and open blocker enforcement (PD-CH2-063).

#### `evaluate_p11_gate` (line 337)
```python
def evaluate_p11_gate(payload: Mapping[str, Any], caller_authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `None`
- **Description**: Unified entry point for P11 Lifecycle & Operations Gate.

### Module `lifecycle_p0a.py`

#### `evaluate_pd_ch2_001_single_lifecycle` (line 59)
```python
def evaluate_pd_ch2_001_single_lifecycle(payload: Mapping[str, Any], caller_authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `None`
- **Description**: Every work type MUST execute as a projection of the same P0-P11 lifecycle (PD-CH2-001).

#### `evaluate_pd_ch2_002_eleven_dimensions` (line 120)
```python
def evaluate_pd_ch2_002_eleven_dimensions(payload: Mapping[str, Any], caller_authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `None`
- **Description**: Every P-phase MUST define all eleven dimensions (PD-CH2-002).

#### `evaluate_pd_ch2_003_earlier_phase_validity` (line 175)
```python
def evaluate_pd_ch2_003_earlier_phase_validity(payload: Mapping[str, Any], caller_authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `None`
- **Description**: A later phase MUST NOT make an invalid earlier phase valid (PD-CH2-003).

#### `evaluate_pd_ch2_005_skipped_phase_applicability` (line 219)
```python
def evaluate_pd_ch2_005_skipped_phase_applicability(payload: Mapping[str, Any], caller_authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `None`
- **Description**: Every skipped phase MUST have an explicit evaluator-checkable applicability result (PD-CH2-005).

#### `evaluate_pd_ch2_006_earliest_defect_routing` (line 275)
```python
def evaluate_pd_ch2_006_earliest_defect_routing(payload: Mapping[str, Any], caller_authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `None`
- **Description**: A discovered defect MUST route to the earliest affected phase (PD-CH2-006).

#### `evaluate_pd_ch2_055_downstream_invalidation` (line 319)
```python
def evaluate_pd_ch2_055_downstream_invalidation(payload: Mapping[str, Any], caller_authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `None`
- **Description**: The lifecycle gate MUST invalidate every downstream projection whose dependency digest changes (PD-CH2-055).

#### `evaluate_p0a_gate` (line 373)
```python
def evaluate_p0a_gate(payloads: Mapping[str, Mapping[str, Any]], caller_authority: Optional[str] = None) -> Dict[str, GateOutput]
```
- **Authority Parameter**: `None`
- **Description**: Composite gate evaluator for all P0A invariants.

### Module `lifecycle_p0b.py`

#### `evaluate_pd_ch2_007_p8_retry_budget` (line 37)
```python
def evaluate_pd_ch2_007_p8_retry_budget(retry_budget_allocated: int, retry_budget_consumed: int, alternate_retry_path_active: bool = False, is_p8_repair: bool = True, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-007: P8 repair MUST consume the frozen RetryBudget and MUST NOT create an alternate retry path.

#### `evaluate_pd_ch2_008_p11_non_terminal_reentry` (line 80)
```python
def evaluate_pd_ch2_008_p11_non_terminal_reentry(trigger_type: str, target_phase: str, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-008: P11 MUST be non-terminal; new work MUST re-enter at P0.

#### `evaluate_pd_ch2_009_done_claim_evidence_closure` (line 116)
```python
def evaluate_pd_ch2_009_done_claim_evidence_closure(model_done_claimed: bool, admissible_evidence_present: bool, kernel_evaluated_closure: bool, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-009: A model DONE claim MUST NOT close work without admissible evidence and kernel-evaluated closure.

#### `evaluate_pd_ch2_010_green_external_run_evidence` (line 151)
```python
def evaluate_pd_ch2_010_green_external_run_evidence(external_run_green: bool, bound_to_obligation_inputs: bool, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-010: A green external run MUST be treated only as run evidence bound to its inputs, not as completion by itself.

#### `evaluate_pd_ch2_011_stack_pack_phase_topology` (line 185)
```python
def evaluate_pd_ch2_011_stack_pack_phase_topology(stack_pack_topology: Sequence[str], standard_phases: Sequence[str] = STANDARD_LIFECYCLE_PHASES, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-011: Stack/skill changes MUST NOT create a lifecycle fork or remove core phases.

#### `evaluate_pd_ch2_012_mandatory_floor_human_waiver` (line 213)
```python
def evaluate_pd_ch2_012_mandatory_floor_human_waiver(waiver_requested: bool, has_authorized_waiver_path: bool = False, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-012: Human judgment MUST NOT waive mandatory mechanical/evidence floors except through existing authorized waiver paths.

#### `evaluate_p0b_gate` (line 241)
```python
def evaluate_p0b_gate(manifest: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Composite gate evaluator for Lifecycle P0B obligations (PD-CH2-007..012).

### Module `lifecycle_p1_p4.py`

#### `evaluate_pd_ch2_056_discovery_completeness` (line 37)
```python
def evaluate_pd_ch2_056_discovery_completeness(target_snapshot_resolved: bool, index_coverage_ratio: float, high_impact_unknowns_resolved: bool, min_index_coverage: float = 1.0, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-056: P1 discovery completeness classification.

#### `evaluate_pd_ch2_057_skill_depth_precedence` (line 80)
```python
def evaluate_pd_ch2_057_skill_depth_precedence(skills_resolved: bool, pinned_skill_digests: Sequence[str] | Mapping[str, str], policy_floor_respected: bool, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-057: P1 skill resolution & digest pinning before downstream progression.

#### `evaluate_pd_ch2_029_task_caps` (line 108)
```python
def evaluate_pd_ch2_029_task_caps(lane_type: str, task_units: int, task_count: int = 1, *, custom_caps: Optional[Mapping[str, Mapping[str, int]]] = None, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-029: P4 task-count and task-unit caps enforcement from policy defaults.

#### `evaluate_pd_ch2_031_work_graph_acyclic` (line 150)
```python
def evaluate_pd_ch2_031_work_graph_acyclic(graph_edges: Mapping[str, Sequence[str]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-031: WorkGraph dependency edges MUST be acyclic.

#### `evaluate_pd_ch2_032_write_set_overlap` (line 196)
```python
def evaluate_pd_ch2_032_write_set_overlap(tasks: Sequence[Mapping[str, Any]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-032: Known write-set overlap MUST serialize mechanically; unknown write sets block for human.

#### `evaluate_p1_p4_gate` (line 241)
```python
def evaluate_p1_p4_gate(manifest: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Composite gate evaluator for Lifecycle P1 and P4 obligations.

### Module `lifecycle_p3a.py`

#### `evaluate_pd_ch2_013_requirement_coverage` (line 32)
```python
def evaluate_pd_ch2_013_requirement_coverage(requirements: Sequence[Mapping[str, Any]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-013: Every applicable requirement has semantic coverage or explicit applicability.

#### `evaluate_pd_ch2_014_domain_invariants` (line 62)
```python
def evaluate_pd_ch2_014_domain_invariants(domain_entities: Sequence[Mapping[str, Any]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-014: Required domain/data invariants are represented.

#### `evaluate_pd_ch2_015_architecture_provenance` (line 91)
```python
def evaluate_pd_ch2_015_architecture_provenance(architecture_elements: Sequence[Mapping[str, Any]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-015: Every required architecture element has attributable provenance.

#### `evaluate_pd_ch2_016_dependency_relationships` (line 130)
```python
def evaluate_pd_ch2_016_dependency_relationships(material_dependencies: Sequence[Mapping[str, Any]], represented_edges: Sequence[Tuple[str, str]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-016: Materially affected dependency relationships are represented.

#### `evaluate_pd_ch2_017_domain_model_substance` (line 161)
```python
def evaluate_pd_ch2_017_domain_model_substance(domain_model: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-017: DomainModel satisfies the measurable substance predicate.

#### `evaluate_pd_ch2_018_architecture_record_substance` (line 201)
```python
def evaluate_pd_ch2_018_architecture_record_substance(architecture_record: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-018: ArchitectureRecord satisfies the measurable substance predicate.

#### `evaluate_p3a_gate` (line 240)
```python
def evaluate_p3a_gate(manifest: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Composite gate evaluator for Lifecycle P3A obligations (PD-CH2-013..018).

### Module `lifecycle_p3b.py`

#### `evaluate_pd_ch2_020_decidable_invariants` (line 38)
```python
def evaluate_pd_ch2_020_decidable_invariants(invariants: Sequence[Mapping[str, Any]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-020: Invariants use F2's decidable fragment; unsupported/undecidable cases cannot PASS.

#### `evaluate_pd_ch2_021_cross_entity_constraints` (line 71)
```python
def evaluate_pd_ch2_021_cross_entity_constraints(constraints: Sequence[Mapping[str, Any]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-021: Cross-entity constraints include explicit relationships and cardinalities.

#### `evaluate_pd_ch2_022_change_surface_boundary_closure` (line 101)
```python
def evaluate_pd_ch2_022_change_surface_boundary_closure(change_surface_boundaries: Sequence[str], dependency_edges: Sequence[Tuple[str, str]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-022: Architecture dependency edges cover ChangeSurfaceAnalysis boundary closure.

#### `evaluate_pd_ch2_023_boundary_data_flow_contracts` (line 134)
```python
def evaluate_pd_ch2_023_boundary_data_flow_contracts(data_flows: Sequence[Mapping[str, Any]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-023: Each boundary-crossing data flow binds source, destination, contract and transformation.

#### `evaluate_pd_ch2_024_interface_signatures_typed_contracts` (line 167)
```python
def evaluate_pd_ch2_024_interface_signatures_typed_contracts(interfaces: Sequence[Mapping[str, Any]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-024: Interface signatures agree with typed domain contracts and requirement predicates.

#### `evaluate_pd_ch2_025_unknown_contradiction_handling` (line 199)
```python
def evaluate_pd_ch2_025_unknown_contradiction_handling(has_unknown_contradiction: bool, human_waiver_attempted: bool = False, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-025: Every unknown/undecidable contradiction returns MISSING; waivers cannot bypass absent analysis.

#### `evaluate_p3b_gate` (line 226)
```python
def evaluate_p3b_gate(manifest: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Composite gate evaluator for Lifecycle P3B obligations (PD-CH2-020..025).

### Module `lifecycle_p3c_p8_p10.py`

#### `evaluate_pd_ch2_026_adr_design_digest_binding` (line 47)
```python
def evaluate_pd_ch2_026_adr_design_digest_binding(adr_sources: Sequence[Mapping[str, Any]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-026: Existing ADR/design sources are digest-bound and pass structure/reference lint.

#### `evaluate_pd_ch2_028_unique_must_ids` (line 79)
```python
def evaluate_pd_ch2_028_unique_must_ids(must_ids: Sequence[str], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-028: MUST IDs are unique, reserved and never reassigned.

#### `evaluate_pd_ch2_051_p8_retry_budget_exhaustion` (line 108)
```python
def evaluate_pd_ch2_051_p8_retry_budget_exhaustion(retry_budget_remaining: int, earliest_affected_phase: str = 'P2', routed_phase: str = 'P2', *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-051: P8 MUST route failure to earliest affected phase and stop when RetryBudget exhausted.

#### `evaluate_pd_ch2_052_p9_task_aggregation_findings_closure` (line 143)
```python
def evaluate_pd_ch2_052_p9_task_aggregation_findings_closure(required_p7_tasks: Sequence[str], aggregated_p7_tasks: Sequence[str], open_mandatory_findings: Sequence[str], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-052: P9 MUST aggregate all required P7 task results and close each mandatory finding.

#### `evaluate_pd_ch2_053_p10_kernel_release_evaluation` (line 180)
```python
def evaluate_pd_ch2_053_p10_kernel_release_evaluation(kernel_release_evaluation: str, product_checks_pass: bool = True, *, authority: Optional[str] = None) -> ReleaseEvaluationOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-053: P10 MUST require frozen kernel ReleaseEvaluation and MUST NOT override kernel denial.

#### `evaluate_p3c_p8_p10_gate` (line 220)
```python
def evaluate_p3c_p8_p10_gate(manifest: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput | ReleaseEvaluationOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Composite gate evaluator for P3C, P8, P9, P10 obligations.

### Module `lifecycle_p5.py`

#### `evaluate_pd_ch2_033_delta_sequence` (line 37)
```python
def evaluate_pd_ch2_033_delta_sequence(test_delta_seq: int, impl_delta_seq: int, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-033: Test-carrying canonical delta MUST precede implementation delta by sequence.

#### `evaluate_pd_ch2_034_red_run_validity` (line 64)
```python
def evaluate_pd_ch2_034_red_run_validity(adapter_qualified: bool, run_failed_designed_test: bool, failure_class: str, designed_class: str, harness_error: bool = False, skipped_or_xfail: bool = False, timeout: bool = False, unstable_flaky: bool = False, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-034: Valid red run from qualified adapter failing designed test.

#### `evaluate_pd_ch2_035_executable_spec_constraints` (line 119)
```python
def evaluate_pd_ch2_035_executable_spec_constraints(is_executable_f1_f2: bool, finite_domain: bool, is_prose_only: bool = False, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-035: Executable specifications MUST satisfy F1/F2 finite-domain constraints.

#### `evaluate_pd_ch2_036_adapter_qualification` (line 147)
```python
def evaluate_pd_ch2_036_adapter_qualification(adapter_name: str, *, qualified_adapters: Set[str] = DEFAULT_QUALIFIED_ADAPTERS, is_f10_qualified: bool = True, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-036: Required test adapters MUST be qualified under F10.

#### `evaluate_pd_ch2_046_test_input_set_binding` (line 175)
```python
def evaluate_pd_ch2_046_test_input_set_binding(primary_test_digest: Optional[str], bound_test_input_set: Mapping[str, str], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-046: Primary test digest MUST be present in TestInputSet before authorizing red run.

#### `evaluate_pd_ch2_047_red_classification_source` (line 202)
```python
def evaluate_pd_ch2_047_red_classification_source(adapter_structured_result: Mapping[str, Any], designed_test_tuple: Tuple[str, str], agent_assertion_used: bool = False, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-047: Red classification MUST use adapter structured result, never agent assertions.

#### `evaluate_p5_gate` (line 240)
```python
def evaluate_p5_gate(manifest: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Composite gate evaluator for Lifecycle P5 obligations.

### Module `lifecycle_p6.py`

#### `evaluate_pd_ch2_037_execution_gate_authorization` (line 30)
```python
def evaluate_pd_ch2_037_execution_gate_authorization(has_execution_gate_auth: bool, task_id: str, scope: str, target: str, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-037: Implementation writes MUST be ExecutionGate-authorized for exact task/scope/target.

#### `evaluate_pd_ch2_038_scope_growth_stop` (line 59)
```python
def evaluate_pd_ch2_038_scope_growth_stop(is_out_of_scope: bool, delta_files: Sequence[str], declared_scope: Set[str], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-038: Scope growth MUST stop and route to P4.

#### `evaluate_pd_ch2_039_implementation_claims` (line 95)
```python
def evaluate_pd_ch2_039_implementation_claims(claimed_symbols: Sequence[str], post_delta_symbols: Set[str], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-039: Implementation claims MUST use F7 rules; symbol absent post-delta -> MISSING[PD-F7-006].

#### `evaluate_pd_ch2_040_canonical_delta_kernel_receipt` (line 123)
```python
def evaluate_pd_ch2_040_canonical_delta_kernel_receipt(has_kernel_receipt: bool, kernel_receipt_digest: Optional[str], kernel_denied: bool = False, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-040: Product records MUST NOT create canonical delta authority or override kernel denial.

#### `evaluate_pd_ch2_048_test_input_set_exclusion_check` (line 151)
```python
def evaluate_pd_ch2_048_test_input_set_exclusion_check(p6_tests_frozen_invoked: bool, p6_modifies_test_input_set: bool = False, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-048: P6 gate MUST invoke complete TestInputSet exclusion check owned by PD-CH4-010.

#### `evaluate_p6_gate` (line 185)
```python
def evaluate_p6_gate(manifest: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Composite gate evaluator for Lifecycle P6 implementation obligations.

### Module `lifecycle_p7.py`

#### `evaluate_pd_ch2_041_evidence_binding` (line 37)
```python
def evaluate_pd_ch2_041_evidence_binding(evidence_identity_bound: bool, current_target_bound: bool, current_step_bound: bool, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-041: Verification evidence MUST bind frozen evidence identity and current target/step.

#### `evaluate_pd_ch2_042_adapter_qualification` (line 65)
```python
def evaluate_pd_ch2_042_adapter_qualification(adapter_name: str, is_f10_qualified: bool, *, qualified_adapters: Set[str] = DEFAULT_QUALIFIED_ADAPTERS, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-042: Required adapter results MUST come from qualified F10 adapters.

#### `evaluate_pd_ch2_043_independence_floor` (line 93)
```python
def evaluate_pd_ch2_043_independence_floor(independence_level: int, required_floor: int, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-043: Independence MUST meet F4 depth-derived floor.

#### `evaluate_pd_ch2_044_freshness_predicate` (line 120)
```python
def evaluate_pd_ch2_044_freshness_predicate(evidence_digest: str, current_code_digest: str, is_stale: bool = False, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-044: Freshness MUST use frozen predicate at recorded evaluation instant.

#### `evaluate_pd_ch2_045_closure_ownership` (line 148)
```python
def evaluate_pd_ch2_045_closure_ownership(kernel_closure_result: Optional[str], agent_asserts_closure: bool = False, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-045: Closure MUST be kernel-owned; agent assertions without kernel closure rejected.

#### `evaluate_pd_ch2_050_deterministic_rerun` (line 175)
```python
def evaluate_pd_ch2_050_deterministic_rerun(rerun_results: Sequence[str], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH2-050: P7 MUST reject nondeterministic test reruns; [PASS, FAIL] -> non-SATISFIED.

#### `evaluate_p7_gate` (line 209)
```python
def evaluate_p7_gate(manifest: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Composite gate evaluator for Lifecycle P7 verification obligations.

### Module `replay.py`

#### `evaluate_ch2_064_replay_invalidation` (line 27)
```python
def evaluate_ch2_064_replay_invalidation(payload: Mapping[str, Any], caller_authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `None`
- **Description**: Evaluates invalidation and replay restart conformance (PD-CH2-064).

#### `evaluate_ch2_065_lifecycle_proof` (line 80)
```python
def evaluate_ch2_065_lifecycle_proof(payload: Mapping[str, Any], caller_authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `None`
- **Description**: Evaluates lifecycle worked proof examples (PD-CH2-065).

#### `evaluate_replay_gate` (line 152)
```python
def evaluate_replay_gate(payload: Mapping[str, Any], caller_authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `None`
- **Description**: Unified entry point for Chapter 2 Replay Gate (PD-CH2-064, PD-CH2-065).

## Block 4 (Lanes B4-A to B4-F)

### Module `adapter_qualification_contract.py`

#### `evaluate_pd_f10_001_contract_invocation` (line 77)
```python
def evaluate_pd_f10_001_contract_invocation(tool_call: Optional[Mapping[str, Any]], adapter_record: Optional[Mapping[str, Any]] = None, category: Optional[str] = None, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-F10-001 (Line 1020): Executable-spec tooling MUST be invoked only through declared F10 contract.

#### `evaluate_pd_f10_002_usable_adapter_binding` (line 113)
```python
def evaluate_pd_f10_002_usable_adapter_binding(adapter: Optional[Mapping[str, Any]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-F10-002 (Line 1021): A usable adapter MUST bind immutable identity, schemas, qualification and evidence fields.

#### `evaluate_pd_f10_003_adapter_registration_authority` (line 156)
```python
def evaluate_pd_f10_003_adapter_registration_authority(actor: str, operation: str, canonical_write_authorized: bool, *, evidence_adapter_digest: Optional[str] = None, current_adapter_digest: Optional[str] = None, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-F10-003 (Line 1022): Only authorized non-agent authority may register/change adapters; changed identity stales evidence.

#### `evaluate_pd_f10_004_execution_gate_enforcement` (line 194)
```python
def evaluate_pd_f10_004_execution_gate_enforcement(authorized_request: Optional[Any], execution_lease: Optional[Any], budget_reservation: Optional[Any], fence: Optional[Any], worker_execute_attempt: bool = False, execution_timeout: bool = False, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-F10-004 (Line 1023): Adapter execution MUST pass through ExecutionGate with lease, budget, and fence.

#### `evaluate_pd_f10_005_qualification_matrix` (line 233)
```python
def evaluate_pd_f10_005_qualification_matrix(frozen_required_tests: Optional[Mapping[str, Mapping[str, str]]], additional_product_tests: Optional[Mapping[str, Mapping[str, str]]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-F10-005 (Line 1024): Qualification MUST pass all 14 frozen adapter tests, A1, A2, and A3.

#### `evaluate_pd_f10_006_independent_verification` (line 279)
```python
def evaluate_pd_f10_006_independent_verification(is_critical_lane: bool, qualified_independent_verifier: Optional[str] = None, primary_result: Optional[str] = None, independent_result: Optional[str] = None, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-F10-006 (Line 1025): CRITICAL-lane independent verification MUST use qualified independent verifier.

#### `evaluate_b4_a_gate` (line 316)
```python
def evaluate_b4_a_gate(payload: Mapping[str, Any], *, authority: Optional[str] = None) -> Dict[str, GateOutput]
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Aggregate gate evaluator for Block 4 Lane A (PD-F10-001..006).

### Module `adapter_diff_spec_anchors.py`

#### `evaluate_pd_f10_007_differential_detection` (line 45)
```python
def evaluate_pd_f10_007_differential_detection(canonical_semantics_primary: Any, canonical_semantics_secondary: Any, evidence_bindings_primary: Optional[Mapping[str, Any]] = None, evidence_bindings_secondary: Optional[Mapping[str, Any]] = None, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-F10-007 (Line 1026): Differential detection MUST compare canonicalized semantics and evidence bindings.

#### `evaluate_pd_ch3_015_artifact_binding_integrity` (line 83)
```python
def evaluate_pd_ch3_015_artifact_binding_integrity(objective_revision: Optional[str], source_digest: Optional[str], artifact_type: Optional[str], owning_authority: Optional[str], *, shadows_canonical_object: bool = False, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH3-015 (Line 2916): Every product artifact MUST bind objective revision, source digest, artifact type and owning authority.

#### `evaluate_pd_ch3_016_spec_anchor_resolution` (line 121)
```python
def evaluate_pd_ch3_016_spec_anchor_resolution(spec_path: Optional[str], symbol_or_heading: Optional[str], line_range: Optional[Tuple[int, int]], anchor_digest: Optional[str], *, expected_anchor_digest: Optional[str] = None, is_fuzzy_match: bool = False, file_length_lines: int = 1000, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH3-016 (Line 2966): Every normative requirement MUST resolve to an exact spec path, symbol/heading and line range.

#### `evaluate_pd_ch3_017_predicate_measurable_thresholds` (line 169)
```python
def evaluate_pd_ch3_017_predicate_measurable_thresholds(predicate: Optional[str], threshold_value: Optional[float], threshold_unit: Optional[str], policy_digest: Optional[str], policy_revision: Optional[str], *, is_undecidable: bool = False, expected_policy_digest: Optional[str] = None, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH3-017 (Line 3024): Mechanical spec-quality predicates MUST use explicit measurable thresholds bound to policy digest.

#### `evaluate_pd_ch3_018_clarification_authorized_outcome` (line 216)
```python
def evaluate_pd_ch3_018_clarification_authorized_outcome(clarification_id: Optional[str], authorized_outcome_digest: Optional[str], resolver_identity: Optional[str], *, is_model_inference: bool = False, is_silent: bool = False, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH3-018 (Line 3074): A blocking clarification MUST have an authorized outcome or remain MISSING/BLOCKED_ON_HUMAN.

#### `evaluate_pd_ch3_020_spec_change_replay_point` (line 254)
```python
def evaluate_pd_ch3_020_spec_change_replay_point(spec_anchor_digest: Optional[str], affected_evidence_digests: Optional[Sequence[str]], earliest_replay_phase: Optional[str], *, invalidated_evidence: bool = True, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH3-020 (Line 3117): Spec change MUST identify earliest replay point and invalidate affected evidence.

#### `evaluate_b4_b_gate` (line 298)
```python
def evaluate_b4_b_gate(payload: Mapping[str, Any], *, authority: Optional[str] = None) -> Dict[str, GateOutput]
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Aggregate gate evaluator for Block 4 Lane B (PD-F10-007, PD-CH3-015..018, PD-CH3-020).

### Module `stratum_sampling_compatibility.py`

#### `evaluate_pd_ch9_006_stratum_sampling_promotion` (line 64)
```python
def evaluate_pd_ch9_006_stratum_sampling_promotion(false_completion_worsened: bool, stratum_counts: Mapping[str, int], *, minimum_per_stratum: int = 100, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH9-006 (Line 4401): Promotion blocked if false-completion worsens or stratum below minimum (100).

#### `evaluate_pd_ch9_007_secret_egress_claims` (line 108)
```python
def evaluate_pd_ch9_007_secret_egress_claims(qualified_receipt_on_launched_worker: bool, *, unqualified_scanner_or_native_host_write: bool = False, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH9-007 (Line 4402): Secret-egress claims require qualified evidence on launched worker; no host-native.

#### `evaluate_pd_ch10_008_explicit_compatibility` (line 136)
```python
def evaluate_pd_ch10_008_explicit_compatibility(compatibility_matrix: Optional[Mapping[str, Any]], *, unsupported_pair_present: bool = False, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH10-008 (Line 4426): Explicit compatibility across kernel, protocol, schema, adapter, pack.

#### `evaluate_pd_ch10_009_audit_export_bindings` (line 172)
```python
def evaluate_pd_ch10_009_audit_export_bindings(audit_export: Optional[Mapping[str, Any]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH10-009 (Line 4450): Audit export binds sequence range, digests, gate I/O, truncation declarations.

#### `evaluate_pd_ch10_010_roadmap_integrity` (line 208)
```python
def evaluate_pd_ch10_010_roadmap_integrity(capabilities: Sequence[Mapping[str, Any]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH10-010 (Line 4485): Roadmap uses only H0-H7, assigns dependencies and exit tests, no planning as implemented.

#### `evaluate_pd_ch10_011_fact_classification` (line 256)
```python
def evaluate_pd_ch10_011_fact_classification(facts: Sequence[Mapping[str, Any]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH10-011 (Line 4519): Implementation facts classified as keep/replace/retire/qualify and evidence-backed or UNVERIFIED.

#### `evaluate_b9_b_gate` (line 300)
```python
def evaluate_b9_b_gate(payload: Mapping[str, Any], *, authority: Optional[str] = None) -> Dict[str, GateOutput]
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Aggregate gate evaluator for Block 9 Lane B (PD-CH9-006..007, PD-CH10-008..011).

### Module `execution_flow_testinput.py`

#### `evaluate_pd_ch3_010_flow_baseline_binding` (line 54)
```python
def evaluate_pd_ch3_010_flow_baseline_binding(flow_type: str, baseline_digest: Optional[str], *, rollback_inputs_bound: bool = True, verification_inputs_bound: bool = True, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH3-010 (Line 3185): Upgrade/migration flows MUST bind baselines and rollback/verification inputs.

#### `evaluate_pd_ch3_011_adapter_qualification_disclosure` (line 86)
```python
def evaluate_pd_ch3_011_adapter_qualification_disclosure(adapter_identity: str, is_qualified: bool, marked_supported: bool, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH3-011 (Line 3186): Project-class adaptation MUST mark unqualified adapter as open qualification.

#### `evaluate_pd_ch3_012_ux_interruption_budget_authority` (line 115)
```python
def evaluate_pd_ch3_012_ux_interruption_budget_authority(human_decision_required: bool, decision_suppressed_by_cap: bool = False, interruption_budget_exceeded: bool = False, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH3-012 (Line 3187): UX adaptation interruption budgets MUST NOT suppress required human decision.

#### `evaluate_pd_ch3_014_lifecycle_example_adversarial_failure` (line 145)
```python
def evaluate_pd_ch3_014_lifecycle_example_adversarial_failure(exercises_real_gate_outputs: bool, has_adversarial_claim_failure: bool, has_test_integrity_failure: bool, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH3-014 (Line 3188): Canonical lifecycle examples MUST exercise real gate outputs and adversarial failure.

#### `evaluate_pd_ch4_012_reference_exact_resolution` (line 174)
```python
def evaluate_pd_ch4_012_reference_exact_resolution(path_reference: Optional[str], symbol_reference: Optional[str], target_snapshot_pinned: bool, *, is_unresolved: bool = False, is_ambiguous: bool = False, is_fuzzy_match: bool = False, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH4-012 (Line 3257): Path/symbol/line reference MUST resolve exactly against pinned snapshot.

#### `evaluate_pd_ch4_009_test_input_set_binding` (line 220)
```python
def evaluate_pd_ch4_009_test_input_set_binding(test_input_set: Optional[Mapping[str, Any]], *, is_before_red: bool = True, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH4-009 (Line 3288): P5 MUST bind qualified adapter-declared complete TestInputSet before red.

#### `evaluate_b4_d_gate` (line 256)
```python
def evaluate_b4_d_gate(payload: Mapping[str, Any], *, authority: Optional[str] = None) -> Dict[str, GateOutput]
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Aggregate gate evaluator for Block 4 Lane D (PD-CH3-010..012, PD-CH3-014, PD-CH4-012, PD-CH4-009).

### Module `context_resume_threats.py`

#### `evaluate_pd_ch4_007_context_resume_anchors` (line 32)
```python
def evaluate_pd_ch4_007_context_resume_anchors(canonical_anchors_present: bool, pinned_guidance_digests: Optional[Sequence[str]], step_pack_digest: Optional[str], *, transcript_only_authority: bool = False, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH4-007 (Line 3467): Context resume MUST rebuild anchors from canonical state and reject transcript-only authority.

#### `evaluate_pd_ch4_008_threat_matrix_containment` (line 62)
```python
def evaluate_pd_ch4_008_threat_matrix_containment(threat_matrix_rows: Optional[Sequence[Mapping[str, Any]]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH4-008 (Line 3468): All listed threat classes MUST map to a detection, gate, containment, and fixture.

#### `evaluate_b4_f_gate` (line 99)
```python
def evaluate_b4_f_gate(payload: Mapping[str, Any], *, authority: Optional[str] = None) -> Dict[str, GateOutput]
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Aggregate gate evaluator for Block 4 Lane F (PD-CH4-007, PD-CH4-008).

## Block 5 (Lane B5)

### Module `enforcement_workspace_gate.py`

#### `evaluate_pd_ch8_008_prevention_boundary` (line 32)
```python
def evaluate_pd_ch8_008_prevention_boundary(prevention_claimed: bool, inside_qualified_enforcement_boundary: bool, *, is_native_ide_activity: bool = False, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH8-008 (Line 4102): Prevention MUST be claimed only inside a launched and qualified enforcement boundary.

#### `evaluate_pd_ch8_009_workspace_promotion` (line 62)
```python
def evaluate_pd_ch8_009_workspace_promotion(target_verified: bool, kernel_release_authority: bool, rollback_evidence_preserved: bool, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH8-009 (Line 4126): Workspace promotion MUST require target, kernel release authority, and rollback evidence.

#### `evaluate_pd_ch8_010_out_of_band_edits` (line 91)
```python
def evaluate_pd_ch8_010_out_of_band_edits(out_of_band_edits_detected: bool, re_snapshot_taken: bool, digest_comparison_passed: bool, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH8-010 (Line 4150): Out-of-band edits MUST trigger re-snapshot and digest comparison before continuing.

#### `evaluate_pd_ch8_011_parallel_work_serialization` (line 121)
```python
def evaluate_pd_ch8_011_parallel_work_serialization(dependencies_satisfied: bool, canonical_delta_order: bool, overlapping_writes_serialized: bool, target_identity_match: bool, all_task_verification_pass: bool, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH8-011 (Line 4174): Parallel work MUST follow dependencies/delta order, serialize writes, and verify tasks.

#### `evaluate_pd_ch8_012_repository_intelligence` (line 158)
```python
def evaluate_pd_ch8_012_repository_intelligence(discloses_coverage: bool, discloses_freshness: bool, *, unresolved_symbol_present: bool = False, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH8-012 (Line 4198): Repository intelligence MUST disclose index coverage/freshness; unresolved symbols remain MISSING.

#### `evaluate_pd_ch8_013_budget_exhaustion_ledger` (line 187)
```python
def evaluate_pd_ch8_013_budget_exhaustion_ledger(budget_exhausted: bool, routed_to_authorized_repair: bool, *, second_ledger_active: bool = False, model_reported_only_cost: bool = False, authoritative_host_cost: bool = True, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH8-013 (Line 4222): Budget exhaustion MUST stop/route to repair; retry uses frozen RetryBudget with no second ledger.

#### `evaluate_b5_gate` (line 225)
```python
def evaluate_b5_gate(payload: Mapping[str, Any], *, authority: Optional[str] = None) -> Dict[str, GateOutput]
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Aggregate gate evaluator for Block 5 (PD-CH8-008..013).

## Block 6 (Lanes B6-A & B6-B)

### Module `wire_session_consequential_gate.py`

#### `evaluate_pd_ch7_016_wire_protocol_envelope` (line 52)
```python
def evaluate_pd_ch7_016_wire_protocol_envelope(request: Optional[Mapping[str, Any]], response: Optional[Mapping[str, Any]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH7-016 (Line 3892): Wire protocol request/response envelope conformance.

#### `evaluate_pd_ch7_008_guidance_resources` (line 103)
```python
def evaluate_pd_ch7_008_guidance_resources(versioned: bool, bounded: bool, subordinate_to_policy_and_kernel: bool, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH7-008 (Line 3909): Guidance resources versioned, bounded, subordinate to policy/kernel.

#### `evaluate_pd_ch7_009_protocol_idempotent_retries` (line 132)
```python
def evaluate_pd_ch7_009_protocol_idempotent_retries(idempotent_under_request_identity: bool, version_conflict_typed_error: bool = True, *, conflict_detected: bool = False, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH7-009 (Line 3933): Protocol retries idempotent under identity; version conflicts return typed error.

#### `evaluate_pd_ch7_011_ide_mode_capabilities` (line 168)
```python
def evaluate_pd_ch7_011_ide_mode_capabilities(host_qualified: bool, declared_tier: Optional[str], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH7-011 (Line 3969): IDE mode declares E0/E1/E2 capabilities per qualified host/version.

#### `evaluate_pd_ch7_012_session_identity_bindings` (line 196)
```python
def evaluate_pd_ch7_012_session_identity_bindings(session_bindings: Optional[Mapping[str, Any]], *, transport_claims_canonical_authority: bool = False, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH7-012 (Line 3993): Session identity binds task, snapshot, revision, and pins; no transport authority.

#### `evaluate_pd_ch7_013_consequential_developer_actions` (line 240)
```python
def evaluate_pd_ch7_013_consequential_developer_actions(authorization_scope_gate_passed: bool, admissible_observation_emitted: bool, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH7-013 (Line 4017): Consequential developer actions pass authorization/scope gates and emit observation.

#### `evaluate_b7_a_gate` (line 268)
```python
def evaluate_b7_a_gate(payload: Mapping[str, Any], *, authority: Optional[str] = None) -> Dict[str, GateOutput]
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Aggregate gate evaluator for Block 7 Lane A (PD-CH7-016, 008, 009, 011, 012, 013).

### Module `lifecycle_phase_admission.py`

#### `evaluate_pd_ch3_001_phase_artifact_anchors` (line 50)
```python
def evaluate_pd_ch3_001_phase_artifact_anchors(objective_revision: Optional[str], spec_anchor_digests: Optional[Sequence[str]], *, expected_objective_revision: Optional[str] = None, expected_anchor_digests: Optional[Sequence[str]] = None, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH3-001 (Line 3179): Every phase artifact MUST bind objective revision and canonical SpecAnchor digests.

#### `evaluate_pd_ch3_002_normative_requirements_completeness` (line 94)
```python
def evaluate_pd_ch3_002_normative_requirements_completeness(requirements: Optional[Sequence[Mapping[str, Any]]], non_goals: Optional[Sequence[str]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH3-002 (Line 3180): Normative requirements MUST have testable acceptance links, non-goals, and no placeholders.

#### `evaluate_pd_ch3_003_clarification_scope_entry` (line 137)
```python
def evaluate_pd_ch3_003_clarification_scope_entry(scope_changed: bool, canonical_decision_recorded: bool, human_confirmed: bool, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH3-003 (Line 3181): Clarification answers changing scope MUST enter canonical mechanisms; absent human blocks.

#### `evaluate_pd_ch3_006_external_tool_candidate_trust` (line 173)
```python
def evaluate_pd_ch3_006_external_tool_candidate_trust(tool_identity: str, qualification_recorded: bool, claimed_authoritative: bool, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH3-006 (Line 3182): External process tools MUST remain untrusted candidates until qualification is recorded.

#### `evaluate_pd_ch3_007_work_type_decision_projection` (line 202)
```python
def evaluate_pd_ch3_007_work_type_decision_projection(canonical_decision_outcome: Optional[str], projected_work_type: Optional[str], agent_override_attempted: bool = False, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH3-007 (Line 3183): Work type MUST be projected from canonical Decision outcome without product state machine.

#### `evaluate_pd_ch3_009_flow_gates_and_lane_computation` (line 245)
```python
def evaluate_pd_ch3_009_flow_gates_and_lane_computation(flow_identity: str, contract_tests_present: bool, computed_lane: Optional[str], agent_selected_lane: bool = False, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH3-009 (Line 3184): Default user-facing flow MUST preserve required gates/evidence and compute lane from policy.

#### `evaluate_b4_c_gate` (line 289)
```python
def evaluate_b4_c_gate(payload: Mapping[str, Any], *, authority: Optional[str] = None) -> Dict[str, GateOutput]
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Aggregate gate evaluator for Block 4 Lane C (PD-CH3-001..003, PD-CH3-006..007, PD-CH3-009).

## Block 7 (Lanes B7-A & B7-B)

### Module `threat_eval_regression_gate.py`

#### `evaluate_pd_ch9_008_threat_coverage` (line 64)
```python
def evaluate_pd_ch9_008_threat_coverage(threat_record: Optional[Mapping[str, Any]], *, absence_of_findings_as_pass: bool = False, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH9-008 (Line 4321): Threat coverage: attack, boundary, prevention/detection, containment, mapped fixture.

#### `evaluate_pd_ch9_009_eval_run_bindings` (line 101)
```python
def evaluate_pd_ch9_009_eval_run_bindings(eval_run: Optional[Mapping[str, Any]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH9-009 (Line 4347): Evaluation run binds benchmark, target, policy, runtime, and audit label.

#### `evaluate_pd_ch9_010_promotion_blockers` (line 137)
```python
def evaluate_pd_ch9_010_promotion_blockers(critical_regression: bool, unqualified_data_handling: bool, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH9-010 (Line 4371): Promotion blocks on critical regression or unqualified data handling.

#### `evaluate_pd_ch9_003_security_promotion_gate` (line 165)
```python
def evaluate_pd_ch9_003_security_promotion_gate(failed_security_scan: bool = False, environment_mismatch: bool = False, sandbox_trust_root_failure: bool = False, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH9-003 (Line 4398): Security scan failure, environment mismatch, or sandbox/trust-root failure blocks promotion.

#### `evaluate_pd_ch9_004_metric_reporting_integrity` (line 208)
```python
def evaluate_pd_ch9_004_metric_reporting_integrity(metric_report: Optional[Mapping[str, Any]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH9-004 (Line 4399): Metric reports MUST include denominator, observation window, stratum, exclusions, uncertainty.

#### `evaluate_pd_ch9_005_data_retention_policy` (line 251)
```python
def evaluate_pd_ch9_005_data_retention_policy(within_retention_limit: bool, has_policy_reference: bool, *, recorded_action: bool = True, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH9-005 (Line 4400): Retention and data access MUST follow policy values with explicit units and version.

#### `evaluate_b9_a_gate` (line 280)
```python
def evaluate_b9_a_gate(payload: Mapping[str, Any], *, authority: Optional[str] = None) -> Dict[str, GateOutput]
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Aggregate gate evaluator for Block 9 Lane A (PD-CH9-008..010, PD-CH9-003..005).

### Module `knowledge_package_quarantine.py`

#### `evaluate_pd_ch6_007_package_metadata` (line 48)
```python
def evaluate_pd_ch6_007_package_metadata(package_metadata: Optional[Mapping[str, Any]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH6-007 (Line 3669): Closed schema, content digest, provenance, license, capabilities, signature.

#### `evaluate_pd_ch6_008_precedence_and_conflicts` (line 84)
```python
def evaluate_pd_ch6_008_precedence_and_conflicts(precedence_deterministic: bool, lower_tier_removes_mandatory: bool = False, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH6-008 (Line 3693): Deterministic precedence and conflict resolution without removing mandatory checks.

#### `evaluate_pd_ch6_009_lifecycle_projection` (line 112)
```python
def evaluate_pd_ch6_009_lifecycle_projection(is_evidence_projection: bool, *, independent_state_machine: bool = False, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH6-009 (Line 3717): Pack lifecycle labels MUST be projections of qualification/revocation evidence.

#### `evaluate_pd_ch6_010_quarantine_conditions` (line 140)
```python
def evaluate_pd_ch6_010_quarantine_conditions(unknown_checks: bool = False, weakened_floors: bool = False, invalid_signature: bool = False, unsupported_compatibility: bool = False, *, quarantined: bool = False, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH6-010 (Line 3741): Unknown checks, weakened floors, invalid signatures, unsupported compatibility.

#### `evaluate_pd_ch6_011_license_provenance_verification` (line 179)
```python
def evaluate_pd_ch6_011_license_provenance_verification(license_verified: bool, provenance_verified: bool, *, public_url_only: bool = False, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH6-011 (Line 3765): Unclear license/provenance MUST remain UNVERIFIED and block promotion.

#### `evaluate_pd_ch6_012_steppack_digest_pinning` (line 208)
```python
def evaluate_pd_ch6_012_steppack_digest_pinning(in_flight: bool, content_digest_pinned: bool, compiler_digest_pinned: bool, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH6-012 (Line 3789): Every in-flight StepPack MUST pin selected content/compiler digests.

#### `evaluate_b6_a_gate` (line 238)
```python
def evaluate_b6_a_gate(payload: Mapping[str, Any], *, authority: Optional[str] = None) -> Dict[str, GateOutput]
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Aggregate gate evaluator for Block 6 Lane A (PD-CH6-007..012).

## Block 8 (Lane B8)

### Module `notification_skill_normalization.py`

#### `evaluate_pd_ch7_014_notification_projections` (line 26)
```python
def evaluate_pd_ch7_014_notification_projections(derived_from_gate_projection: bool, *, implies_approval_on_model_message: bool = False, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH7-014 (Line 4041): Notifications MUST be derived from gate projections and not imply approval on model message.

#### `evaluate_pd_ch7_015_external_skill_normalization` (line 54)
```python
def evaluate_pd_ch7_015_external_skill_normalization(normalized_into_sclass_owned_checks: bool, *, creates_alternate_lifecycle_or_loop: bool = False, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH7-015 (Line 4244): External skill content normalized into S-Class-owned checks; no alternate lifecycle.

#### `evaluate_b7_b_gate` (line 82)
```python
def evaluate_b7_b_gate(payload: Mapping[str, Any], *, authority: Optional[str] = None) -> Dict[str, GateOutput]
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Aggregate gate evaluator for Block 7 Lane B (PD-CH7-014, 015).

## Block 9 (Lanes B9-A, B9-B, B9-C)

### Module `oss_qualification_playbook.py`

#### `evaluate_pd_ch6_013_stack_pack_adapters` (line 58)
```python
def evaluate_pd_ch6_013_stack_pack_adapters(stack_pack: Optional[Mapping[str, Any]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH6-013 (Line 3813): Stack pack references qualified adapter families or explicitly blocks checks.

#### `evaluate_pd_ch6_014_oss_qualification_record` (line 107)
```python
def evaluate_pd_ch6_014_oss_qualification_record(record: Optional[Mapping[str, Any]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH6-014 (Line 3835): OSS qualification record must contain all 16 fields and each must remain UNVERIFIED until evidence.

#### `evaluate_pd_ch6_003_pack_activation` (line 160)
```python
def evaluate_pd_ch6_003_pack_activation(scope_specific_qualification: bool, effective_revocation_present: bool = False, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH6-003 (Line 3862): Activation MUST require scope-specific qualification and absence of effective revocation.

#### `evaluate_pd_ch6_006_playbook_content` (line 188)
```python
def evaluate_pd_ch6_006_playbook_content(playbook_content: Optional[Mapping[str, Any]], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH6-006 (Line 3863): v1 Python Feature/Bug Fix playbook content MUST provide phase checklists and refer to qualified adapter families.

#### `evaluate_b6_b_gate` (line 232)
```python
def evaluate_b6_b_gate(payload: Mapping[str, Any], *, authority: Optional[str] = None) -> Dict[str, GateOutput]
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Aggregate gate evaluator for Block 6 Lane B (PD-CH6-013, 014, 003, 006).

### Module `erratum_issue_registry.py`

#### `evaluate_pd_ch10_012_frozen_erratum_path` (line 38)
```python
def evaluate_pd_ch10_012_frozen_erratum_path(formal_erratum_path: bool, insufficiency_analysis_present: bool, replay_analysis_present: bool, *, ad_hoc_source_edit: bool = False, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH10-012 (Line 4543): Frozen change requires formal erratum path, insufficiency and replay analysis.

#### `evaluate_pd_ch10_013_open_issue_schema` (line 68)
```python
def evaluate_pd_ch10_013_open_issue_schema(issue: Optional[Mapping[str, Any]], *, oi_008_owner_reviews_count: int = 0, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH10-013 (Line 4567): Open issues name impact, owner, evidence, phase, status; OI-008 requires 2 raw fresh-chat reviews.

#### `evaluate_pd_ch10_007_master_cross_links` (line 116)
```python
def evaluate_pd_ch10_007_master_cross_links(cross_linked_to_master: bool, *, unknown_references_present: bool = False, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH10-007 (Line 4594): Version/qualification and issue/claim registries internally cross-linked to master.

#### `evaluate_b9_c_gate` (line 144)
```python
def evaluate_b9_c_gate(payload: Mapping[str, Any], *, authority: Optional[str] = None) -> Dict[str, GateOutput]
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Aggregate gate evaluator for Block 9 Lane C (PD-CH10-012..013, PD-CH10-007).

### Module `isolation_claims.py`

#### `evaluate_pd_ch4_010_test_input_write_isolation` (line 32)
```python
def evaluate_pd_ch4_010_test_input_write_isolation(implementation_write_paths: Sequence[str], test_input_paths: Sequence[str], *, manifest_unchanged: bool = True, environment_digest_match: bool = True, test_is_green: bool = True, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH4-010 (Line 3289): P6 MUST exclude every path in bound TestInputSet from writes; P7 evidence uses same manifest.

#### `evaluate_pd_ch4_014_authorized_delta_scope` (line 71)
```python
def evaluate_pd_ch4_014_authorized_delta_scope(observed_delta_paths: Sequence[str], authorized_write_paths: Sequence[str], *, green_test_run: bool = True, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH4-014 (Line 3327): Observed delta outside authorized scope returns BLOCKED; cannot be accepted by green test.

#### `evaluate_pd_ch4_016_independent_evidence_producers` (line 101)
```python
def evaluate_pd_ch4_016_independent_evidence_producers(primary_producer: Optional[str], independent_producer: Optional[str], *, is_self_review: bool = False, shared_unqualified_adapter: bool = False, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH4-016 (Line 3408): Independence claims MUST name distinct evidence producers; self-review prohibited.

#### `evaluate_pd_ch4_002_execution_claim_receipt` (line 145)
```python
def evaluate_pd_ch4_002_execution_claim_receipt(has_execution_claim: bool, has_structured_results: bool, raw_result_digest: Optional[str], *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH4-002 (Line 3464): Claims of execution MUST bind qualified adapter structured results and raw result identity.

#### `evaluate_pd_ch4_005_evidence_freshness_identity` (line 174)
```python
def evaluate_pd_ch4_005_evidence_freshness_identity(requirement_revision_digest: Optional[str], evidence_requirement_digest: Optional[str], *, target_identity_match: bool = True, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH4-005 (Line 3465): Evidence freshness and independence MUST be evaluated from bound identity.

#### `evaluate_pd_ch4_006_canonical_closure_vs_prose` (line 210)
```python
def evaluate_pd_ch4_006_canonical_closure_vs_prose(agent_prose_done_claim: bool, kernel_obligation_closure: bool, has_admissible_evidence: bool, *, authority: Optional[str] = None) -> GateOutput
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: PD-CH4-006 (Line 3466): False-completion MUST be recorded from canonical events; agent prose has no closure authority.

#### `evaluate_b4_e_gate` (line 239)
```python
def evaluate_b4_e_gate(payload: Mapping[str, Any], *, authority: Optional[str] = None) -> Dict[str, GateOutput]
```
- **Authority Parameter**: `Keyword-only `authority=None``
- **Description**: Aggregate gate evaluator for Block 4 Lane E (PD-CH4-010, PD-CH4-014, PD-CH4-016, PD-CH4-002, 005, 006).

