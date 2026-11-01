# S-Class v6.0.2: Block 1 Normative MUST Tracker
**Tracking Reference:** `delivery-1-audit/must_tracker.md`  
**Integration Base Commit:** `3ed415e67e15e6aedc7d456445c3c193146ae606`  
**Scope:** Authoritative Tracking of Block 1 Normative Obligations (`PD-F1`, `PD-F2`, `PD-F3`) with Forward Mapping (`PD-F6`, `PD-F7`)  
**Date:** 2026-11-01  
**Author:** Antigravity (Lane D Coverage Auditor)  
**Status:** Reference-only tracker. Per coordinator directive, this document alters no MUST statuses and respects CL's normative decisions.

---

## 1. Tracker Overview & Namespace Classification

This tracker monitors all Product Design MUST obligations allocated in the R30 Master Product Design (`FREEZE-CANDIDATE-v6.0.2`) across Block 1. Obligations are categorized under the non-reusing `PD-` namespace and classified by evaluation tier:
- **Mechanical (M):** Deterministically verifiable by static analysis, schema validation, AST evaluation, or digest matching without runtime telemetry.
- **Evaluator (E):** Verified via dynamic execution, adapter invocation, or external check records produced by an independent evaluator.
- **Judgment (J):** Requires authoritative human sign-off, governance escalation, or cryptographic policy assertion.

---

## 2. Section F1: Content Model of Design/Spec Artifacts

| Field | Detail |
|---|---|
| **MUST ID** | `PD-F1-001` |
| **Section** | F1 (Content Model) |
| **Class** | Mechanical (M) |
| **Normative Requirement** | Descriptive prose alone cannot satisfy a mechanical representation obligation. |
| **Authoritative Fixture** | `F1-T11` (prose-only variation preserves gate result) |
| **Implementation Symbol** | `sclass.product.artifacts.evaluate_f1_representation` (`src/sclass/product/artifacts.py#L421-L507`) |
| **Positive Tests** | `tests/product/test_artifact_schemas.py::test_pd_f1_001_prose_variation_preserves_gate_output` |
| **Negative Tests** | `tests/product/test_artifact_schemas.py::test_pd_f1_003_missing_executable_representation_negative` |
| **Expected Gate Outputs** | `SATISFIED` when structured representation is valid; varying prose does not alter outcome. |
| **CL Authoritative Status** | **ACCEPTED** (Block 1-01) |
| **Gaps / Unverified Claims**| None. Purely mechanical schema validation. |

---

| Field | Detail |
|---|---|
| **MUST ID** | `PD-F1-002` |
| **Section** | F1 (Content Model) |
| **Class** | Evaluator (E) |
| **Normative Requirement** | Agent-authored executable claims require an independent verifier; F1 establishes the non-self-verification floor. |
| **Authoritative Fixture** | `F1-T7` (agent self-report contradicted by independent verifier) |
| **Implementation Symbol** | `sclass.product.artifacts.evaluate_f1_representation` (`src/sclass/product/artifacts.py#L450-L465`) |
| **Positive Tests** | `tests/product/test_artifact_schemas.py::test_pd_f1_002_non_self_verification_floor_positive` |
| **Negative Tests** | `tests/product/test_artifact_schemas.py::test_pd_f1_002_non_self_verification_floor_negative` |
| **Expected Gate Outputs** | `SATISFIED` (verified by independent source) / `UNSAT` or `UNVERIFIED` (agent self-assertion rejected). |
| **CL Authoritative Status** | **ACCEPTED** (Block 1-01) |
| **Gaps / Unverified Claims**| Relies on caller-injected evaluator check record; agent self-assertion rejected. |

---

| Field | Detail |
|---|---|
| **MUST ID** | `PD-F1-003` |
| **Section** | F1 (Content Model) |
| **Class** | Mechanical (M) |
| **Normative Requirement** | Applicable artifact kind MUST use the required executable representation or explicitly enter the defined J fallback. |
| **Authoritative Fixture** | `F1-T1` (prose-only API design) |
| **Implementation Symbol** | `sclass.product.artifacts.evaluate_f1_representation` (`src/sclass/product/artifacts.py#L430-L445`) |
| **Positive Tests** | `tests/product/test_artifact_schemas.py::test_pd_f1_003_executable_representation_positive` |
| **Negative Tests** | `tests/product/test_artifact_schemas.py::test_pd_f1_003_missing_executable_representation_negative` |
| **Expected Gate Outputs** | `SATISFIED` / `MISSING[PD-F1-003]` (when executable representation is absent without J fallback). |
| **CL Authoritative Status** | **ACCEPTED** (Block 1-01) |
| **Gaps / Unverified Claims**| J fallback routing requires explicit governance record. |

---

| Field | Detail |
|---|---|
| **MUST ID** | `PD-F1-004` |
| **Section** | F1 (Content Model) |
| **Class** | Mechanical / Evaluator (M/E) |
| **Normative Requirement** | Every executable spec MUST satisfy the generic positive/negative adequacy rule through its qualified adapter. |
| **Authoritative Fixture** | `F1-T3` (positive example only), `F1-T4` (negative example accepted), `F1-T9` (accept-all), `F1-T10` (unsatisfiable) |
| **Implementation Symbol** | `sclass.product.artifacts.evaluate_f1_representation` (`src/sclass/product/artifacts.py#L466-L485`) |
| **Positive Tests** | `tests/product/test_artifact_schemas.py::test_pd_f1_003_executable_representation_positive` |
| **Negative Tests** | `tests/product/test_artifact_schemas.py::test_pd_f1_004_adequacy_positive_only_negative`<br>`tests/product/test_artifact_schemas.py::test_pd_f1_004_adequacy_negative_observed_accepted`<br>`tests/product/test_artifact_schemas.py::test_pd_f1_004_adequacy_accept_all_predicate`<br>`tests/product/test_artifact_schemas.py::test_pd_f1_004_adequacy_unsatisfiable_predicate` |
| **Expected Gate Outputs** | `SATISFIED` / `UNSAT` (adequacy failure: positive-only or negative example accepted). |
| **CL Authoritative Status** | **ACCEPTED** (Block 1-01) |
| **Gaps / Unverified Claims**| Full qualification matrix across external engines deferred to F10 adapter stage. |

---

| Field | Detail |
|---|---|
| **MUST ID** | `PD-F1-005` |
| **Section** | F1 (Content Model) |
| **Class** | M / E / J |
| **Normative Requirement** | Changes to confirmed executable constraints MUST be treated as potentially weakening when no structural-diff procedure exists, and weakening MUST follow the authoritative change/approval path. |
| **Authoritative Fixture** | `F1-T5` (weakening without approval), `F1-T6` (weakening with approval), `F1-T8` (no structural diff) |
| **Implementation Symbol** | `sclass.product.artifacts._detect_predicate_weakening` (`src/sclass/product/artifacts.py#L509-L558`) |
| **Positive Tests** | `tests/product/test_artifact_schemas.py::test_pd_f1_005_weakening_with_approval_satisfied` |
| **Negative Tests** | `tests/product/test_artifact_schemas.py::test_pd_f1_005_weakening_without_approval_blocked`<br>`tests/product/test_artifact_schemas.py::test_pd_f1_005_no_structural_diff_blocked` |
| **Expected Gate Outputs** | `SATISFIED` (weakening with approval) / `BLOCKED_ON_HUMAN` (weakening without approval or absent diff). |
| **CL Authoritative Status** | **ACCEPTED** (Block 1-01) |
| **Gaps / Unverified Claims**| None. Strict fallback to `BLOCKED_ON_HUMAN` enforced. |

---

## 3. Section F2: Predicate & Invariant Language (Decidable Fragment)

| Field | Detail |
|---|---|
| **MUST ID** | `PD-F2-001` |
| **Section** | F2 (Decidable Fragment) |
| **Class** | Mechanical (M) |
| **Normative Requirement** | F2 predicates MUST conform to the closed grammar, finite types, precedence, associativity and canonical surface mapping. |
| **Authoritative Fixture** | `F2-T1` (valid token stream), `F2-T2` (malformed token / forbidden construct) |
| **Implementation Symbol** | `sclass.product.predicate_evaluator.tokenize`, `Parser` (`src/sclass/product/predicate_evaluator.py#L625-L933`) |
| **Positive Tests** | `tests/product/test_predicate_evaluator.py::test_f2_t1_valid_token_stream_and_bounded_predicate`<br>`tests/product/test_predicate_evaluator.py::test_canonical_surface_mapping_deterministic` |
| **Negative Tests** | `tests/product/test_predicate_evaluator.py::test_f2_t2_malformed_token_and_forbidden_construct` |
| **Expected Gate Outputs** | `SATISFIED` / `UNSAT` (syntax error / forbidden construct). |
| **CL Authoritative Status** | **ACCEPTED** (Block 1-02b) |
| **Gaps / Unverified Claims**| None. Closed grammar strictly enforced. |

---

| Field | Detail |
|---|---|
| **MUST ID** | `PD-F2-002` |
| **Section** | F2 (Decidable Fragment) |
| **Class** | Mechanical (M) |
| **Normative Requirement** | Every mechanically decided scalar or collection variable MUST have an explicit finite domain; interval/set reduction MUST preserve the bounded model set. |
| **Authoritative Fixture** | `F2-T3` (unbounded integer), `F2-T11` (false-UNSAT guard) |
| **Implementation Symbol** | `sclass.product.predicate_evaluator.PredicateEvaluator` (`src/sclass/product/predicate_evaluator.py#L934-L1050`) |
| **Positive Tests** | `tests/product/test_predicate_evaluator.py::test_f2_t11_false_unsat_guard` |
| **Negative Tests** | `tests/product/test_predicate_evaluator.py::test_f2_t3_unbounded_integer` |
| **Expected Gate Outputs** | `SATISFIED` / `UNSAT` (unbounded variable rejected). |
| **CL Authoritative Status** | **ACCEPTED** (Block 1-02b) |
| **Gaps / Unverified Claims**| None. Unbounded variables fail closed. |

---

| Field | Detail |
|---|---|
| **MUST ID** | `PD-F2-003` |
| **Section** | F2 (Decidable Fragment) |
| **Class** | Mechanical / Evaluator (M/E) |
| **Normative Requirement** | The reference evaluator MUST return SAT only for a satisfying bounded assignment, UNSAT only after complete bounded evaluation, and INCONCLUSIVE when the evaluation budget expires first. |
| **Authoritative Fixture** | `F2-T4` (truncated residual search) |
| **Implementation Symbol** | `sclass.product.predicate_evaluator.PredicateEvaluator.evaluate` (`src/sclass/product/predicate_evaluator.py#L1051-L1120`) |
| **Positive Tests** | `tests/product/test_predicate_evaluator.py::test_f2_t1_valid_token_stream_and_bounded_predicate` |
| **Negative Tests** | `tests/product/test_predicate_evaluator.py::test_f2_t4_truncated_residual_search_budget` |
| **Expected Gate Outputs** | `SATISFIED` (SAT) / `UNSAT` (complete search unsat) / `INCONCLUSIVE` (budget exhausted). |
| **CL Authoritative Status** | **ACCEPTED** (Block 1-02b) |
| **Gaps / Unverified Claims**| Evaluation step budget pinned to constant; dynamic budget scaling reserved for F4. |

---

| Field | Detail |
|---|---|
| **MUST ID** | `PD-F2-004` |
| **Section** | F2 (Decidable Fragment) |
| **Class** | Mechanical / Evaluator (M/E) |
| **Normative Requirement** | Tautology, contradiction and old/new classification MUST use the same declared bounded model domain, with EQUIVALENT, TIGHTENING and WEAKENING defined as stated. |
| **Authoritative Fixture** | `F2-T5` (tautology & contradiction), `F2-T6` (classification), `F2-T14` (widening) |
| **Implementation Symbol** | `sclass.product.predicate_evaluator.PredicateEvaluator.classify` (`src/sclass/product/predicate_evaluator.py#L1121-L1190`) |
| **Positive Tests** | `tests/product/test_predicate_evaluator.py::test_f2_t5_tautology_and_contradiction`<br>`tests/product/test_predicate_evaluator.py::test_f2_t6_weakening_classifications`<br>`tests/product/test_predicate_evaluator.py::test_f2_t14_widening_requires_weakening_classification` |
| **Negative Tests** | `tests/product/test_predicate_evaluator.py::test_f2_t6_weakening_without_approval_fails` |
| **Expected Gate Outputs** | Classification results: `EQUIVALENT`, `TIGHTENING`, `WEAKENING`; unauthorized weakening yields `BLOCKED_ON_POLICY`. |
| **CL Authoritative Status** | **ACCEPTED** (Block 1-02b) |
| **Gaps / Unverified Claims**| None. Domain matching strictly verified. |

---

| Field | Detail |
|---|---|
| **MUST ID** | `PD-F2-005` |
| **Section** | F2 (Decidable Fragment) |
| **Class** | Evaluator / Judgment (E/J) |
| **Normative Requirement** | Temporal, unbounded or otherwise out-of-fragment predicates MUST route to a qualified property/stateful test or J. |
| **Authoritative Fixture** | `F2-T7` (temporal property routed out of v1) |
| **Implementation Symbol** | `sclass.product.predicate_evaluator.tokenize` (`src/sclass/product/predicate_evaluator.py#L650-L680`) |
| **Positive Tests** | N/A (v1 decider rejects temporal operators) |
| **Negative Tests** | `tests/product/test_predicate_evaluator.py::test_f2_t7_temporal_property_routed_out_of_v1` |
| **Expected Gate Outputs** | `UNSAT` / `INCONCLUSIVE` (routing out of v1 decidable fragment). |
| **CL Authoritative Status** | **ACCEPTED** (Block 1-02b) |
| **Gaps / Unverified Claims**| External temporal test harness integration deferred to Phase 2. |

---

| Field | Detail |
|---|---|
| **MUST ID** | `PD-F2-006` |
| **Section** | F2 (Decidable Fragment) |
| **Class** | Mechanical / Evaluator (M/E) |
| **Normative Requirement** | Every qualified F2 adapter MUST match the reference evaluator on small conformance fixtures, MUST use the applicable F4 evaluation budget, and MUST return INCONCLUSIVE on budget exhaustion. |
| **Authoritative Fixture** | `F2-T8` (reference enumerator differential) |
| **Implementation Symbol** | `sclass.product.predicate_evaluator.PredicateEvaluator` (`src/sclass/product/predicate_evaluator.py#L934-L1190`) |
| **Positive Tests** | `tests/product/test_predicate_evaluator.py::test_f2_t8_reference_enumerator_differential` |
| **Negative Tests** | `tests/product/test_predicate_evaluator.py::test_f2_t8_divergence_fails` |
| **Expected Gate Outputs** | `SATISFIED` when matching reference solver; mismatch fails. |
| **CL Authoritative Status** | **ACCEPTED** (Block 1-02b) |
| **Gaps / Unverified Claims**| Multi-adapter qualification matrix deferred to F10. |

---

| Field | Detail |
|---|---|
| **MUST ID** | `PD-F2-007` |
| **Section** | F2 (Decidable Fragment) |
| **Class** | Mechanical (M) |
| **Normative Requirement** | F2 canonical bindings MUST resolve to frozen Requirement, Constraint, AcceptanceContract and VerificationStep objects; digest-bound confirmation is governed by F3. |
| **Authoritative Fixture** | `F2-T9` (frozen bindings), `F2-T10` (token-level parser and large-domain compound formula) |
| **Implementation Symbol** | `sclass.product.predicate_evaluator.resolve_frozen_bindings`, `evaluate_predicate_input` (`src/sclass/product/predicate_evaluator.py#L132-L195, L1281-L1350`) |
| **Positive Tests** | `tests/product/test_predicate_evaluator.py::test_f2_t9_frozen_bindings`<br>`tests/product/test_predicate_evaluator.py::test_f2_t10_token_level_parser_and_large_domain` |
| **Negative Tests** | `tests/product/test_predicate_evaluator.py::test_brief_1_02b_embedded_resolver_ignored_returns_missing_pd_f2_007`<br>`tests/product/test_predicate_evaluator.py::test_brief_1_02b_missing_resolver_fails_closed_missing_pd_f2_007`<br>`tests/product/test_predicate_evaluator.py::test_unresolved_frozen_binding_fails_closed` |
| **Expected Gate Outputs** | `SATISFIED` / `MISSING[PD-F2-007]` (unresolvable ref, candidate-embedded resolver, or absent resolver). |
| **CL Authoritative Status** | **ACCEPTED** (Block 1-02b) |
| **Gaps / Unverified Claims**| Resolver strictly caller-injected; no candidate self-resolution permitted. |

---

## 4. Section F3: Trust Model for Agent-Authored Content

| Field | Detail |
|---|---|
| **MUST ID** | `PD-F3-001` |
| **Section** | F3 (Trust Model) |
| **Class** | Mechanical (M) |
| **Normative Requirement** | Agent-authored content MUST remain a claim/provenance input and MUST NOT self-authenticate. |
| **Authoritative Fixture** | `F3-T1` (agent claim is not proof) |
| **Implementation Symbol** | `sclass.product.trust_model.evaluate_claim` (`src/sclass/product/trust_model.py#L221-L320`) |
| **Positive Tests** | `tests/product/test_trust_model.py::test_f3_t7_evaluator_backed_record_accepted` |
| **Negative Tests** | `tests/product/test_trust_model.py::test_f3_t1_agent_claim_is_not_proof` |
| **Expected Gate Outputs** | `UNVERIFIED` (agent-authored claim without independent evaluator record). |
| **CL Authoritative Status** | **ACCEPTED** (Block 1-03f) |
| **Gaps / Unverified Claims**| None. Pure agent claim cannot satisfy a gate. |

---

| Field | Detail |
|---|---|
| **MUST ID** | `PD-F3-002` |
| **Section** | F3 (Trust Model) |
| **Class** | Mechanical (M) |
| **Normative Requirement** | Gate authority MUST come from evaluator-produced check records bound to the canonical object and target. |
| **Authoritative Fixture** | `F3-T2` (agent-written PASS has no authority), `F3-T7` (evaluator-backed record accepted) |
| **Implementation Symbol** | `sclass.product.trust_model.query_check_record_source`, `evaluate_claim` (`src/sclass/product/trust_model.py#L173-L220, L221-L380`) |
| **Positive Tests** | `tests/product/test_trust_model.py::test_f3_t7_evaluator_backed_record_accepted` |
| **Negative Tests** | `tests/product/test_trust_model.py::test_f3_t2_agent_written_pass_has_no_authority`<br>`tests/product/test_trust_model.py::test_pd_f3_002_adversarial_callable_only_source_fails_closed`<br>`tests/product/test_trust_model.py::test_pd_f3_adversarial_record_producer_field_cannot_independently_confer_authority`<br>`tests/product/test_trust_model.py::test_pd_f3_adversarial_no_source_returns_missing_pd_f3_002` |
| **Expected Gate Outputs** | `SATISFIED` (evaluator record from valid source) / `MISSING[PD-F3-002]` (missing source, callable-only source, or unbound record). |
| **CL Authoritative Status** | **ACCEPTED** (Block 1-03f) |
| **Gaps / Unverified Claims**| **Mandatory Block 2 Condition:** In the first real-source gate evaluator, source-returned records declaring `producer: "agent"` must be rejected. |

---

| Field | Detail |
|---|---|
| **MUST ID** | `PD-F3-003` |
| **Section** | F3 (Trust Model) |
| **Class** | Mechanical (M) |
| **Normative Requirement** | Conflicting structured representations MUST be detected without using explanatory prose as a mechanical comparison operand. |
| **Authoritative Fixture** | `F3-T3` (structured conflict only) |
| **Implementation Symbol** | `sclass.product.trust_model.check_structured_conflict` (`src/sclass/product/trust_model.py#L435-L466`) |
| **Positive Tests** | `tests/product/test_trust_model.py::test_pd_f3_003_identical_structured_different_prose_is_satisfied` |
| **Negative Tests** | `tests/product/test_trust_model.py::test_pd_f3_003_differing_structured_identical_prose_is_blocked_on_human`<br>`tests/product/test_trust_model.py::test_pd_f3_003_adversarial_prose_injection_has_zero_effect` |
| **Expected Gate Outputs** | `SATISFIED` (identical AST, differing prose) / `BLOCKED_ON_HUMAN` (differing AST, identical prose). |
| **CL Authoritative Status** | **ACCEPTED** (Block 1-03f) |
| **Gaps / Unverified Claims**| None. Prose fields completely excluded from AST comparison. |

---

| Field | Detail |
|---|---|
| **MUST ID** | `PD-F3-004` |
| **Section** | F3 (Trust Model) |
| **Class** | Evaluator (E) |
| **Normative Requirement** | Requirement confirmation MUST be a REQUIREMENT_CONFIRMED USER/POLICY event whose Requirement.source_provenance equals the digest of the canonical structured form; design confirmations MUST be Decision outcomes. |
| **Authoritative Fixture** | `F3-T4` (requirement confirmation digest mismatch and governance approval) |
| **Implementation Symbol** | `sclass.product.trust_model.evaluate_requirement_confirmation` (`src/sclass/product/trust_model.py#L467-L607`) |
| **Positive Tests** | `tests/product/test_trust_model.py::test_pd_f3_004_valid_requirement_confirmed_user`<br>`tests/product/test_trust_model.py::test_pd_f3_004_valid_requirement_confirmed_policy` |
| **Negative Tests** | `tests/product/test_trust_model.py::test_pd_f3_004_agent_authority_rejected`<br>`tests/product/test_trust_model.py::test_pd_f3_004_llm_derived_authority_rejected`<br>`tests/product/test_trust_model.py::test_pd_f3_004_wrong_event_type_rejected`<br>`tests/product/test_trust_model.py::test_pd_f3_004_missing_or_empty_source_provenance_fails_closed` |
| **Expected Gate Outputs** | `SATISFIED` / `BLOCKED_ON_POLICY` (agent/LLM confirmation) / `MISSING[PD-F3-004]` (digest mismatch). |
| **CL Authoritative Status** | **ACCEPTED** (Block 1-03f) |
| **Gaps / Unverified Claims**| None. Full canonical recomputation enforced. |

---

| Field | Detail |
|---|---|
| **MUST ID** | `PD-F3-005` |
| **Section** | F3 (Trust Model) |
| **Class** | Evaluator (E) |
| **Normative Requirement** | The evaluator MUST recompute content_digest; a claimed digest that differs from the recomputed digest is invalid. |
| **Authoritative Fixture** | `F3-T5` (content digest mismatch) |
| **Implementation Symbol** | `sclass.product.trust_model.verify_content_digest` (`src/sclass/product/trust_model.py#L608-L675`) |
| **Positive Tests** | `tests/product/test_trust_model.py::test_pd_f3_005_matching_digest_satisfied`<br>`tests/product/test_trust_model.py::test_pd_f3_005_conformance_against_c1_vectors` |
| **Negative Tests** | `tests/product/test_trust_model.py::test_pd_f3_005_mismatch_yields_missing`<br>`tests/product/test_trust_model.py::test_pd_f3_005_caller_supplied_digest_string_rejected`<br>`tests/product/test_trust_model.py::test_pd_f3_005_conflicting_claimed_digest_keys_fail_closed` |
| **Expected Gate Outputs** | `SATISFIED` / `MISSING[PD-F3-005]` (claimed digest != recomputed digest). |
| **CL Authoritative Status** | **ACCEPTED** (Block 1-03f) |
| **Gaps / Unverified Claims**| None. Always recomputes from RFC 8785 canonical bytes. |

---

| Field | Detail |
|---|---|
| **MUST ID** | `PD-F3-006` |
| **Section** | F3 (Trust Model) |
| **Class** | Mechanical (M) |
| **Normative Requirement** | Human confirmation is admissible only from an S-Class-controlled or host-native rendering surface; agent-relayed confirmation text is inadmissible; the signing principal key MUST be unreachable from the agent environment. |
| **Authoritative Fixture** | `F3-T6` (host-native confirmation surface and key custody) |
| **Implementation Symbol** | `sclass.product.trust_model.evaluate_confirmation_admissibility` (`src/sclass/product/trust_model.py#L676-L766`) |
| **Positive Tests** | `tests/product/test_trust_model.py::test_pd_f3_006_host_native_surface_with_key_custody_is_satisfied`<br>`tests/product/test_trust_model.py::test_pd_f3_006_sclass_controlled_surface_is_satisfied` |
| **Negative Tests** | `tests/product/test_trust_model.py::test_pd_f3_006_unknown_surfaces_fail_closed`<br>`tests/product/test_trust_model.py::test_pd_f3_006_principal_key_accessible_to_agent_blocked`<br>`tests/product/test_trust_model.py::test_pd_f3_006_approval_forwarding_tool_available_blocked`<br>`tests/product/test_trust_model.py::test_pd_f3_006_user_presence_not_required_blocked` |
| **Expected Gate Outputs** | `SATISFIED` / `BLOCKED_ON_POLICY` (agent accessibility, missing user presence, or unverified surface). |
| **CL Authoritative Status** | **ACCEPTED** (Block 1-03f) |
| **Gaps / Unverified Claims**| Live TPM/FIDO2 hardware binding evaluated against verified assertion schema; OS driver execution deferred to Phase 2. |

---

## 5. Forward Tracking: Section F6 & F7 (Lane A Scope)

The following requirements are assigned to Lane A (`lane-a-f6-f7`) for sequential implementation and verification:

| MUST ID | Section | Class | Normative Requirement Summary | Expected Fixtures | Planned Implementation | Status |
|---|---|---|---|---|---|---|
| `PD-F6-001` | F6 | M | Trace links MUST be typed and derived only from resolved kernel objects reached through source_refs. | `F6-T1` | `sclass.product.traceability` | **IN PROGRESS** (Lane A) |
| `PD-F6-002` | F6 | M | Coverage MUST be computed from valid links and MUST detect orphan nodes rather than accepting asserted coverage. | `F6-T2` | `sclass.product.traceability` | **IN PROGRESS** (Lane A) |
| `PD-F6-003` | F6 | M | Link identity MUST be stable across revisions when source/destination stable IDs and link type remain unchanged. | `F6-T3` | `sclass.product.traceability` | **IN PROGRESS** (Lane A) |
| `PD-F6-004` | F6 | E | Agent assertions about coverage MUST NOT substitute for evaluator-computed coverage. | `F6-T4` | `sclass.product.traceability` | **IN PROGRESS** (Lane A) |
| `PD-F6-005` | F6 | E | Both endpoints of a trace link MUST be current under the frozen freshness predicate before contributing to coverage. | `F6-T5` | `sclass.product.traceability` | **IN PROGRESS** (Lane A) |
| `PD-F6-006` | F6 | M | Planned coverage MUST be computed through VerificationStep without requiring realized evidence; realized coverage requires evidence. | `F6-T6` | `sclass.product.traceability` | **IN PROGRESS** (Lane A) |
| `PD-F7-001` | F7 | M | Every agent claim MUST be a structured record with claim_id, type, subject and optional evidence_refs. | `F7-T1` | `sclass.product.claim_ledger` | **QUEUED** (Post-F6) |
| `PD-F7-002` | F7 | M | Behavioral/completion claims without evidence remain unverified; reference claims use evaluator repository-intelligence. | `F7-T2` | `sclass.product.claim_ledger` | **QUEUED** (Post-F6) |
| `PD-F7-003` | F7 | E | Symbols/imports/APIs MUST resolve against TargetSnapshot and canonical dependency identity. | `F7-T4` | `sclass.product.claim_ledger` | **QUEUED** (Post-F6) |
| `PD-F7-004` | F7 | E | Pre-existing symbol absent from pre-delta repository view yields missing claim result. | `F7-T3` | `sclass.product.claim_ledger` | **QUEUED** (Post-F6) |
| `PD-F7-005` | F7 | M | Claim types MUST use closed v1 registry; each type uses declared evidence rule. | `F7-T5` | `sclass.product.claim_ledger` | **QUEUED** (Post-F6) |
| `PD-F7-006` | F7 | E | When created_by_delta=true, claimed symbol MUST resolve in post-delta repository overlay. | `F7-T6` | `sclass.product.claim_ledger` | **QUEUED** (Post-F6) |
