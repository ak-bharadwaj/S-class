# S-Class v6.0.2: Block 1 Verification Coverage Audit
**Audit Reference:** `delivery-1-audit/coverage_audit.md`  
**Integration Base Commit:** `3ed415e67e15e6aedc7d456445c3c193146ae606`  
**Audit Scope:** Block 1 Packets (1-00 CI Guards, 1-01 Artifact Model, 1-02/1-02b Predicate Evaluator, 1-03/1-03f Trust Model)  
**Date:** 2026-11-01  
**Author:** Antigravity (Lane D Coverage Auditor)  
**Status:** Authoritative Reference Document (No implementation changes, no MUST status alterations)

---

## 1. Executive Summary

This document establishes the comprehensive verification coverage audit across all delivered and accepted implementation packets comprising **Block 1** of the S-Class v6.0.2 product layer. The baseline for this audit is the unified integration commit `3ed415e67e15e6aedc7d456445c3c193146ae606`.

The audit verifies that every normative obligation allocated to Block 1 (`PD-F1-001` through `PD-F1-005`, `PD-F2-001` through `PD-F2-007`, `PD-F3-001` through `PD-F3-006`, and foundational pre-flight guards) has:
1. Exact traceability to implementation code symbols in `src/sclass/product/`.
2. Both positive validation coverage and fail-closed negative/adversarial coverage.
3. Formal binding to the authoritative test fixtures defined in the R30 Master Product Design (`FREEZE-CANDIDATE-v6.0.2`).
4. Strict determinism and 100% mutation kill rates across all delivered mutation batteries.
5. Full compliance with the immutable boundaries of the frozen v6.0.1 kernel packages (`00-SPEC/`, `10-CONFORMANCE/`, `20-RUNTIME/`).

```
+--------------------------------------------------------------------------------------------------+
|                                    BLOCK 1 AUDIT SUMMARY                                         |
+-------------------+----------------+-------------+------------+------------+---------------------+
| Packet            | Normative Scope| Unit Tests  | Fixtures   | Mutants    | Gate Outputs        |
+-------------------+----------------+-------------+------------+------------+---------------------+
| 1-00 CI Guards    | CI/Kernel/Spec | 2 guards    | N/A        | N/A        | PASS / FAIL (Exit)  |
| 1-01 Artifacts    | PD-F1-001..005 | 28 tests*   | F1-T1..T11 | 4/4 killed | SATISFIED, MISSING, |
|                   |                | (44 items)  |            | (100%)     | BLOCKED_ON_HUMAN    |
| 1-02b Predicates  | PD-F2-001..007 | 45 tests    | F2-T1..T14 |24/24 killed| SATISFIED, UNSAT,   |
|                   |                | (45 items)  |            | (100%)     | INCONCLUSIVE, MISS. |
| 1-03f Trust Model | PD-F3-001..006 | 72 tests    | F3-T1..T7  |34/34 killed| SATISFIED, MISSING, |
|                   |                | (72 items)  |            | (100%)     | BLOCKED, UNVERIFIED |
+-------------------+----------------+-------------+------------+------------+---------------------+
| TOTAL PRODUCT     | 18 MUST IDs    | 145 tests   | 32 fixtures|62/62 killed| Deterministic Gate  |
|                   |                | (161 items) |            | (100%)     | Semantics           |
+-------------------+----------------+-------------+------------+------------+---------------------+
* Note: test_artifact_schemas.py includes parameterized tests expanding to 44 execution items.
```

---

## 2. Packet 1-00: Pre-Flight CI Guards & Frozen Integrity

### 2.1 Scope and Normative Basis
Block 1-00 enforces kernel and specification immutability. No product-level implementation is permitted to modify, weaken, or shadow the frozen v6.0.1 artifacts:
- `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md`
- `10-CONFORMANCE/sclass_semantics_v6_0_1.py`
- `10-CONFORMANCE/test_sclass_v6_0_1_conformance.py`
- `20-RUNTIME/sclass_runtime_v6_0_1.py`
- `20-RUNTIME/test_sclass_runtime_v6_0_1.py`

### 2.2 Implementation & Guard Infrastructure
- **Files:**
  - `tests/guards/test_frozen_integrity_guard.py`
  - `tests/guards/test_kernel_registry_guard.py`
  - `.github/workflows/ci.yml`
  - `requirements-linux.txt`
- **Mechanism:**
  - Exact LF-normalized SHA-256 byte comparison against pinned checksums.
  - Runtime inspection of kernel registries ensuring zero monkey-patching, namespace pollution, or unauthorized subclassing by product layers.
  - Hash-pinned pip installation (`--require-hashes`) ensuring deterministic Linux dependencies.

### 2.3 Test Coverage Inventory
- **Guard Tests:**
  - `test_frozen_files_sha256_integrity`: Parameterized across all 5 frozen files; asserts exact match with canonical SHA-256 digests.
  - `test_kernel_registry_no_product_pollution`: Verifies that `sclass.kernel` namespaces retain strictly frozen class registries.
- **Fail-Closed Behavior:**
  - Any byte modification, newline conversion, or attribute injection causes immediate process exit with non-zero status.

---

## 3. Packet 1-01: Artifact Content Model & Schema Validation (Section F1)

### 3.1 Scope and Normative Obligations
Section F1 governs the structured, machine-checkable representation of design, spec, and plan artifacts, abolishing unverified descriptive prose as an engineering proof.

| MUST ID | Normative Statement (Excerpt) | Classification | Authoritative Fixture |
|---|---|---|---|
| `PD-F1-001` | Descriptive prose alone cannot satisfy a mechanical representation obligation. | Mechanical (M) | `F1-T11` |
| `PD-F1-002` | Agent-authored executable claims require an independent verifier; F1 establishes the non-self-verification floor. | Evaluator (E) | `F1-T7` |
| `PD-F1-003` | Applicable artifact kind MUST use the required executable representation or explicitly enter the defined J fallback. | Mechanical (M) | `F1-T1` |
| `PD-F1-004` | Every executable spec MUST satisfy the generic positive/negative adequacy rule through its qualified adapter. | Mechanical/Evaluator (M/E) | `F1-T3`, `F1-T4`, `F1-T9`, `F1-T10` |
| `PD-F1-005` | Changes to confirmed executable constraints MUST be treated as potentially weakening when no structural-diff procedure exists, and weakening MUST follow the authoritative change/approval path. | M/E/J | `F1-T5`, `F1-T6`, `F1-T8` |

### 3.2 Implementation Architecture
- **Module:** `src/sclass/product/artifacts.py`
- **Key Symbols:**
  - `CommonPhaseArtifact` (L327): The canonical envelope binding `artifact_id`, `phase`, `work_type`, `artifact_class`, `artifact_type`, `version`, `created_at`, `source_provenance`, `content_digest`, and `payload`.
  - `JSONSchema202012Validator` (L219): Standalone JSON Schema Draft 2020-12 engine enforcing strict unknown-field rejection (`additionalProperties: false`).
  - `SchemaRegistry` (L245): Catalog resolving Appendix A schemas: `CommonPhaseArtifact`, `ChangeSurfaceAnalysis`, `ClarificationRecord`, `DomainModel`, `ArchitectureRecord`, `Plan`, `TestDesignRecord`, `ImplementationRecord`, `VerificationEvidenceSet`, `ReviewRecord`.
  - `c1_canonical_encode` & `compute_content_digest` (L152, L157): Deterministic RFC 8785 C1 canonical JSON serialization and SHA-256 digest computation.
  - `evaluate_f1_representation` (L421): Core evaluator executing F1 gate checks and weakening classification.
  - `_detect_predicate_weakening` (L509): Syntactic and semantic differential evaluator comparing old and new constraint sets.

### 3.3 Test Coverage Breakdown
- **Test Suite:** `tests/product/test_artifact_schemas.py` (28 test definitions, 44 pytest items)
- **Positive Test Coverage:**
  - `test_common_phase_artifact_positive`: Validates compliant envelope against schema.
  - `test_all_9_payload_schemas_positive`: Parameterized across all 9 phase payload schemas.
  - `test_canonical_c1_golden_vectors_reproduced`: Exact C1 JSON serialization matches RFC 8785 test vectors.
  - `test_pd_f1_001_prose_variation_preserves_gate_output`: Confirms varying prose descriptions leaves mechanical validation digest and gate verdict identical.
  - `test_pd_f1_002_non_self_verification_floor_positive`: Validates acceptance when claim is paired with independent verifier check record.
  - `test_pd_f1_003_executable_representation_positive`: Validates compliant structured spec representation.
  - `test_pd_f1_005_weakening_with_approval_satisfied`: Proves weakening constraint with authoritative human/policy approval record succeeds (`SATISFIED`).
- **Negative & Adversarial Test Coverage:**
  - `test_common_phase_artifact_missing_required_fields`: Fails closed when envelope fields are omitted.
  - `test_common_phase_artifact_invalid_types`: Fails closed on malformed datatypes.
  - `test_common_phase_artifact_strict_unknown_fields_rejection`: Fails closed on unauthorized injected fields.
  - `test_common_phase_artifact_digest_mismatch_fails`: Tamper test; changing 1 bit in payload invalidates `content_digest`.
  - `test_all_9_payload_schemas_negative_unknown_field`: Parameterized; rejects arbitrary keys across all 9 payloads.
  - `test_pd_f1_002_non_self_verification_floor_negative` (`F1-T7`): Agent self-assertion without independent verification is rejected.
  - `test_pd_f1_003_missing_executable_representation_negative` (`F1-T1`): Prose-only artifact rejected with `MISSING[PD-F1-003]`.
  - `test_pd_f1_004_adequacy_positive_only_negative` (`F1-T3`): Executable spec lacking negative counter-examples is rejected (`UNSAT`).
  - `test_pd_f1_004_adequacy_negative_observed_accepted` (`F1-T4`): Negative example erroneously accepted by candidate spec fails adequacy check.
  - `test_pd_f1_004_adequacy_accept_all_predicate` (`F1-T9`): Vacuous accept-all spec fails closed.
  - `test_pd_f1_004_adequacy_unsatisfiable_predicate` (`F1-T10`): Vacuous contradictive spec fails closed.
  - `test_pd_f1_005_weakening_without_approval_blocked` (`F1-T5`): Constraint weakening lacking approval is `BLOCKED_ON_HUMAN`.
  - `test_pd_f1_005_no_structural_diff_blocked` (`F1-T8`): Missing structural diff algorithm defaults to potential weakening and blocks.
  - `test_agent_cannot_self_grant_authority_or_trust`: Rejects agent self-delegation attempts.
- **Mutation Verification:** 4/4 mutants killed (100% kill rate).

---

## 4. Packet 1-02 / 1-02b: Predicate & Invariant Language (Section F2)

### 4.1 Scope and Normative Obligations
Section F2 establishes the decidable fragment for specification predicates and invariants. Evaluation must be mechanically decidable, terminate within a strict bounded model domain, and resolve bindings strictly through caller-injected resolvers.

| MUST ID | Normative Statement (Excerpt) | Classification | Authoritative Fixture |
|---|---|---|---|
| `PD-F2-001` | F2 predicates MUST conform to the closed grammar, finite types, precedence, associativity and canonical surface mapping. | Mechanical (M) | `F2-T1`, `F2-T2` |
| `PD-F2-002` | Every mechanically decided scalar or collection variable MUST have an explicit finite domain; interval/set reduction MUST preserve bounded model set. | Mechanical (M) | `F2-T3`, `F2-T11` |
| `PD-F2-003` | Evaluator MUST return SAT only for satisfying assignment, UNSAT only after complete bounded evaluation, and INCONCLUSIVE when budget expires. | Mechanical/Evaluator (M/E) | `F2-T4` |
| `PD-F2-004` | Tautology, contradiction and old/new classification MUST use declared bounded domain, with EQUIVALENT, TIGHTENING, WEAKENING defined as stated. | Mechanical/Evaluator (M/E) | `F2-T5`, `F2-T6`, `F2-T14` |
| `PD-F2-005` | Temporal, unbounded or otherwise out-of-fragment predicates MUST route to a qualified property/stateful test or J. | Evaluator/Judgment (E/J) | `F2-T7` |
| `PD-F2-006` | Qualified F2 adapter MUST match reference evaluator, use applicable F4 budget, and return INCONCLUSIVE on exhaustion. | Mechanical/Evaluator (M/E) | `F2-T8` |
| `PD-F2-007` | F2 canonical bindings MUST resolve to frozen Requirement, Constraint, AcceptanceContract and VerificationStep objects. | Mechanical (M) | `F2-T9`, `F2-T10` |

### 4.2 Implementation Architecture
- **Module:** `src/sclass/product/predicate_evaluator.py`
- **Key Symbols:**
  - `tokenize` (L625) & `Parser` (L800): Strict recursive-descent lexer and parser enforcing operator precedence, associativity, and forbidden syntax rejection.
  - `PredicateEvaluator` (L934): Decidable fragment solver over finite integer and enum domains, implementing interval propagation, residual search, tautology/contradiction checks, and classification.
  - `resolve_frozen_bindings` (L132): Resolves binding refs against caller-injected resolver, checking target kinds (`Requirement`, `Constraint`, `AcceptanceContract`, `VerificationStep`).
  - `evaluate_predicate_input` (L1281): Top-level dispatcher enforcing caller-controlled injection and fail-closed gate outputs.
  - `GateState` & `GateOutput` (L78, L86): Structured gate result contract.
- **Brief 1-02b Remediation:**
  - Completely eliminated caller-spec fallback to `spec.get("resolver")` or `spec.get("binding_resolver")`.
  - Evaluator strictly requires the `resolver` parameter injected by the caller. If omitted or `None`, evaluation immediately fails closed with `UNVERIFIED` and `MISSING[PD-F2-007]`.

### 4.3 Test Coverage Breakdown
- **Test Suite:** `tests/product/test_predicate_evaluator.py` (45 tests)
- **Positive Test Coverage:**
  - `test_f2_t1_valid_token_stream_and_bounded_predicate`: Tokenization and evaluation of valid boolean, comparison, and set-membership expressions.
  - `test_f2_t5_tautology_and_contradiction`: Validates detection of `P or not P` (Tautology) and `P and not P` (Contradiction).
  - `test_f2_t6_weakening_classifications`: Validates exact classification: `EQUIVALENT`, `TIGHTENING`, `WEAKENING`.
  - `test_f2_t9_frozen_bindings`: Validates correct resolution against frozen kernel mock fixtures.
  - `test_f2_t10_token_level_parser_and_large_domain`: Stress tests parser over large conjunctions/disjunctions.
  - `test_f2_t11_false_unsat_guard`: Proves interval reduction does not produce false UNSAT on satisfiable bounds.
  - `test_f2_t12_compound_or_alternatives_not_conjunctive`: Verifies disjunction handling across disjunct domains.
  - `test_f2_t13_residual_cross_variable_atom`: Validates residual enumeration over multi-variable constraints.
  - `test_f2_t14_widening_requires_weakening_classification`: Proves domain enlargement triggers `WEAKENING`.
  - `test_canonical_surface_mapping_deterministic`: Verifies deterministic AST-to-surface roundtripping.
- **Negative & Adversarial Test Coverage:**
  - `test_f2_t2_malformed_token_and_forbidden_construct`: Rejects syntax errors, bitwise operators, and unquoted strings.
  - `test_f2_t3_unbounded_integer`: Rejects unbounded variable declarations without finite ranges.
  - `test_f2_t4_truncated_residual_search_budget`: Enforces `INCONCLUSIVE` when evaluation step budget is exceeded.
  - `test_f2_t7_temporal_property_routed_out_of_v1`: Rejects LTL/CTL temporal operators (`always`, `eventually`, `until`).
  - `test_f2_t8_reference_enumerator_differential`: Detects divergence against brute-force reference enumerator.
  - `test_brief_1_02b_embedded_resolver_ignored_returns_missing_pd_f2_007`: Proves that candidate-embedded resolvers cannot confer authority.
  - `test_brief_1_02b_missing_resolver_fails_closed_missing_pd_f2_007`: Caller omitting resolver yields `MISSING[PD-F2-007]`.
  - `test_unresolved_frozen_binding_fails_closed`: Unresolvable symbol fails closed.
  - `test_invalid_frozen_object_type_fails_closed`: Non-F2 kernel types fail closed.
- **Mutation Verification:** 24/24 mutants killed (100% kill rate).

---

## 5. Packet 1-03 / 1-03f: Trust Model for Agent-Authored Content (Section F3)

### 5.1 Scope and Normative Obligations
Section F3 establishes the core trust architecture: agent-authored content is untrusted telemetry that cannot self-authenticate. Gate authority derives exclusively from evaluator check records produced by caller-injected `CheckRecordSource` dependencies.

| MUST ID | Normative Statement (Excerpt) | Classification | Authoritative Fixture |
|---|---|---|---|
| `PD-F3-001` | Agent-authored content MUST remain a claim/provenance input and MUST NOT self-authenticate. | Mechanical (M) | `F3-T1` |
| `PD-F3-002` | Gate authority MUST come from evaluator-produced check records bound to the canonical object and target. | Mechanical (M) | `F3-T2`, `F3-T7` |
| `PD-F3-003` | Conflicting structured representations MUST be detected without using explanatory prose as comparison operand. | Mechanical (M) | `F3-T3` |
| `PD-F3-004` | Requirement confirmation MUST be a REQUIREMENT_CONFIRMED USER/POLICY event whose Requirement.source_provenance equals digest of canonical structured form. | Evaluator (E) | `F3-T4` |
| `PD-F3-005` | Evaluator MUST recompute content_digest; claimed digest that differs from recomputed digest is invalid. | Evaluator (E) | `F3-T5` |
| `PD-F3-006` | Human confirmation is admissible only from S-Class-controlled or host-native surface; agent-relayed text inadmissible; signing key unreachable from agent. | Mechanical (M) | `F3-T6` |

### 5.2 Implementation Architecture
- **Module:** `src/sclass/product/trust_model.py`
- **Key Symbols:**
  - `CheckRecordSource` (L131): Formal abstract protocol defining `get_check_records(object_digest: str, target_digest: str) -> Sequence[CheckRecord]`.
  - `query_check_record_source` (L173): Validates that injected source implements the protocol; rejects callable-only sources with `MISSING[PD-F3-002]`.
  - `evaluate_claim` (L221): Evaluates candidate claims against injected check record source. Zero caller-asserted identity parameters.
  - `check_structured_conflict` (L435): Semantic AST comparison ignoring prose narrative fields.
  - `evaluate_requirement_confirmation` (L467): Validates user/policy confirmation events against recomputed canonical C1 digests.
  - `verify_content_digest` (L608): Independent recomputation of SHA-256 digests.
  - `evaluate_confirmation_admissibility` (L676): Validates surface provenance (`HOST_NATIVE`, `SCLASS_CONTROLLED`), user presence, and key custody isolation.
  - `evaluate_f3_trust` (L767): Unified entry point executing all Section F3 verifications.
- **Directive 1-03e/1-03f Remediation:**
  - Total elimination of `evaluator_identity` parameter across product, dispatcher, tests, and fixtures.
  - Strict protocol enforcement: rejected callable fallbacks.
  - Removed producer-conferred authority: check record `producer` cannot confer authority; missing producer on valid bound record succeeds.

### 5.3 Test Coverage Breakdown
- **Test Suite:** `tests/product/test_trust_model.py` (72 tests)
- **Positive Test Coverage:**
  - `test_f3_t7_evaluator_backed_record_accepted`: Injected source returning valid `CheckRecord` produces `SATISFIED`.
  - `test_pd_f3_003_identical_structured_different_prose_is_satisfied`: Confirms identical structured logic with radically different prose produces `SATISFIED`.
  - `test_pd_f3_004_valid_requirement_confirmed_user`: USER confirmation event produces `SATISFIED`.
  - `test_pd_f3_004_valid_requirement_confirmed_policy`: POLICY confirmation event produces `SATISFIED`.
  - `test_pd_f3_005_matching_digest_satisfied`: Matching recomputed digest produces `SATISFIED`.
  - `test_pd_f3_006_host_native_surface_with_key_custody_is_satisfied`: Host-native surface with full custody isolation produces `SATISFIED`.
  - `test_pd_f3_006_sclass_controlled_surface_is_satisfied`: S-Class controlled surface produces `SATISFIED`.
- **Negative & Adversarial Test Coverage:**
  - `test_f3_t1_agent_claim_is_not_proof`: Agent claim without evaluator source produces `UNVERIFIED`.
  - `test_f3_t2_agent_written_pass_has_no_authority`: Agent asserting `status: "PASS"` in payload produces `UNVERIFIED`.
  - `test_pd_f3_002_adversarial_callable_only_source_fails_closed`: Callable without `get_check_records()` fails closed with `MISSING[PD-F3-002]`.
  - `test_pd_f3_002_adversarial_record_producer_field_cannot_independently_confer_authority`: `producer: "evaluator"` label without valid source cannot confer authority.
  - `test_pd_f3_003_differing_structured_identical_prose_is_blocked_on_human`: Conflicting structured forms with identical prose triggers `BLOCKED_ON_HUMAN`.
  - `test_pd_f3_003_adversarial_prose_injection_has_zero_effect`: Injection in prose description does not affect structural conflict detector.
  - `test_pd_f3_004_agent_authority_rejected`: Agent-emitted confirmation event rejected with `BLOCKED_ON_POLICY`.
  - `test_pd_f3_004_llm_derived_authority_rejected`: LLM confirmation event rejected with `BLOCKED_ON_POLICY`.
  - `test_pd_f3_004_wrong_event_type_rejected`: Non-`REQUIREMENT_CONFIRMED` event rejected.
  - `test_pd_f3_004_missing_or_empty_source_provenance_fails_closed`: Omission of canonical digest fails closed.
  - `test_pd_f3_005_mismatch_yields_missing` (`F3-T5`): Claimed digest != recomputed digest yields `MISSING[PD-F3-005]`.
  - `test_pd_f3_005_conflicting_claimed_digest_keys_fail_closed`: Spec providing conflicting digest keys fails closed.
  - `test_pd_f3_006_unknown_surfaces_fail_closed`: Unrecognized surface fails closed.
  - `test_pd_f3_006_principal_key_accessible_to_agent_blocked`: Agent access to signing key yields `BLOCKED_ON_POLICY`.
  - `test_pd_f3_006_approval_forwarding_tool_available_blocked`: Agent forwarding tool present yields `BLOCKED_ON_POLICY`.
  - `test_pd_f3_006_user_presence_not_required_blocked`: User presence check absent yields `BLOCKED_ON_POLICY`.
  - `test_pd_f3_no_evaluator_identity_in_api`: Verifies `evaluator_identity` parameter is absent from all signatures.
- **Mutation Verification:** 34/34 mutants killed (100% kill rate).

---

## 6. Shared Gate Vocabulary Alignment (Lane B Bridge)

During Block 1 development, Section F2 and Section F3 introduced independent definitions of `GateState` and `GateOutput`. While Lane B (`lane-b-shared-gate`) has unified these in `src/sclass/product/gate.py`, the integration baseline `3ed415e67e15e6aedc7d456445c3c193146ae606` preserves backward compatibility:
- `sclass.product.predicate_evaluator.GateOutput`
- `sclass.product.trust_model.GateOutput`

Both implementations exhibit identical string representation (`str(out)`), value equality (`==`), hashability, and serialization contracts (`to_dict()`). Lane A will temporarily import from `trust_model` until Lane B is merged, after which all consumers will bind directly to `sclass.product.gate`.

---

## 7. Identified Gaps, Open Directives & Future Gating

1. **CL Reserved Directive for Block 2:**
   - In accordance with CL's formal acceptance of Block 1-03, the first real-source gate evaluator implemented in Block 2 must reject source-returned check records declaring `producer: "agent"`. A dedicated negative test proving this cannot produce `SATISFIED` must be authored in Block 2. This check was deliberately excluded from F3 to preserve F3's pure dependency injection semantics.
2. **Hardware Security Module (HSM) / WebAuthn Custody Integration:**
   - Packet 1-03 enforces the cryptographic custody contract (`PD-F3-006`) via explicit custody assertion records. Integration with live OS-native WebAuthn / FIDO2 tokens or platform TPMs belongs to Phase 2 runtime integration.
3. **Traceability (F6) and Claim Ledger (F7):**
   - Packets F6 and F7 remain open on Lane A. F6 implementation will enforce typed links, orphan detection, and caller-injected source ref resolution.

---

## 8. Audit Verdict

**Block 1 Verification Status: VERIFIED & ACCEPTED**  
- Normative Coverage: 100% across `PD-F1-001..005`, `PD-F2-001..007`, `PD-F3-001..006`.
- Test Suite: 145 tests (161 pytest items) in `tests/product/` passing with zero regressions.
- Mutation Resistance: 62/62 mutants killed across Packets 1-01, 1-02b, and 1-03f (100% overall kill rate).
- Boundary Integrity: 5/5 frozen files verified against canonical SHA-256 hashes.
