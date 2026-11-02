# R30 Master Product Design Extract: Section F7 Claim Ledger and Reference Verification

**Source Document:** `FREEZE-CANDIDATE-v6.0.2/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`  
**Section:** `## F7 — Claim ledger and reference verification` & `### F7 fixtures`  
**Status:** ACCEPTED  

---

## F7 — Claim ledger and reference verification

**Status:** ACCEPTED.

**Known defects:** none.

### Context

Agent claims are structured records, not prose assertions. S-Class verifies proposed engineering references against the immutable TargetSnapshot and dependency identity before a claim can satisfy a gate.

### Decision

Every agent claim MUST be represented as `{claim_id, type, subject, evidence_refs}`. The claim-type registry is closed for v1: `reference`, `behavioral`, `completion`. `reference` claims require successful TargetSnapshot/dependency resolution; `behavioral` claims require kernel evidence refs whose receipts resolve and are current; `completion` claims require the governing obligation/evidence closure. For reference claims the evaluator's own symbol/import/API resolution is the evidence; agent `evidence_refs` are optional. For behavioral claims `evidence_refs` MUST resolve to kernel evidence. Completion claims cannot rely on agent self-report.

S-Class never parses prose to discover claims. Reference claims may rely on evaluator resolution without agent evidence references; behavioral and completion claims require their declared admissible evidence.

Reference verification resolves proposed symbols, imports, packages and APIs against the frozen repository-intelligence pipeline: `04-INTELLIGENCE/S-CLASS-ENGINEERING-INTELLIGENCE-SPEC.md` §4 L64-L76 "## 4. Repository intelligence pipeline" and the `TargetSnapshot` plus its dependency identity. The F10 adapter category `repository-intelligence / symbol resolution` is bound by the same adapter contract and qualification rules. Symbols created by the proposed delta are resolved against the post-delta overlay before the claim can close. Package/dependency resolution is anchored to the frozen `CanonicalDependencySet` entries `(namespace, identity, digest)`. Reference absence is `MISSING` for the relevant claim MUST. Precedence is determined by the canonical claim attribute `created_by_delta`: `PD-F7-006` applies when the claim asserts a delta-created symbol and that symbol is absent from the post-delta overlay; `PD-F7-004` applies to a pre-existing reference absent from the pre-delta view. A delta-created claim that remains absent post-delta fails under `PD-F7-006`.

### Claim-type registry

| Claim type | Required/valid evidence |
|---|---|
| `reference` | evaluator-resolved symbol/import/package/API identity in the repository-intelligence index; agent `evidence_refs` optional |
| `behavioral` | kernel evidence bound to the executed test/verification result |
| `completion` | admissible kernel evidence showing the applicable obligation is satisfied |

For reference claims, the evaluator's own repository-intelligence resolution is the evidence. For behavioral and completion claims, `evidence_refs` MUST resolve to kernel evidence.

### MUSTs

| ID | Class | Requirement | Test |
|---|---|---|---|
| PD-F7-001 | M | Every agent claim MUST be a structured record with `claim_id`, `type`, `subject` and optional `evidence_refs`; prose alone MUST NOT create a claim. | F7-T1 structured claim with evidence refs → `SATISFIED`. |
| PD-F7-002 | M | Behavioral and completion claims without resolvable evidence references MUST remain unverified and MUST NOT satisfy a gate; reference claims use evaluator-owned repository-intelligence resolution as their evidence. | F7-T2 no evidence refs → `MISSING[PD-F7-002]`. |
| PD-F7-003 | E | Proposed symbols, imports, packages and APIs MUST resolve against the TargetSnapshot and the canonical dependency identity before verification. | F7-T4 package digest mismatch → `MISSING[PD-F7-003]`. |
| PD-F7-004 | E | A pre-existing symbol/import/package/API reference (`created_by_delta=false`) absent from the pre-delta repository view MUST yield a missing claim result. | F7-T3 pre-existing symbol absent from pre-delta view → `MISSING[PD-F7-004]`. |
| PD-F7-005 | M | Claim types MUST use the closed v1 registry and each type MUST use its declared evidence rule. | F7-T5 reference claim resolved by evaluator, behavioral claim with kernel evidence, completion claim without closure → `SATISFIED`, `SATISFIED`, `MISSING[PD-F7-005]`. |
| PD-F7-006 | E | When `created_by_delta=true`, the claimed symbol MUST resolve in the post-delta repository overlay; absence post-delta is missing regardless of pre-delta presence. | F7-T6 delta-created symbol resolves post-delta → `SATISFIED`; delta-created symbol absent post-delta → `MISSING[PD-F7-006]`. |

### Tests

| Test | Fixture | Exact expected output |
|---|---|---|
| F7-T1 | F7-FT1 claim `CL-1` type `reference`, reference_kind `symbol`, subject `pkg.rate_limiter:Limiter`, evaluator resolution succeeds | `SATISFIED` |
| F7-T2 | F7-FT2 claim `CL-2` type `behavioral`, empty `evidence_refs` | `MISSING[PD-F7-002]` |
| F7-T3 | F7-FT3 claim `CL-3` subject `pkg.hallucinated:MissingClass`; snapshot contains no such symbol | `MISSING[PD-F7-004]` |
| F7-T4 | F7-FT4 package `ratelimit-core` expected digest D1 but CanonicalDependencySet resolves D2 | `MISSING[PD-F7-003]` |
| F7-T5 | F7-FT5 reference claim resolved by evaluator, behavioral claim with kernel evidence, completion claim without closure | `SATISFIED`, `SATISFIED`, `MISSING[PD-F7-005]` |
| F7-T6 | F7-FT6 applies `created_by_delta=true` to delta-created symbols and false to pre-existing references | `SATISFIED` when delta-created symbol resolves post-delta; `MISSING[PD-F7-006]` when delta-created symbol is absent post-delta; `MISSING[PD-F7-004]` when a pre-existing reference is absent pre-delta |

### Kernel binding

The frozen `TargetSnapshot` is the immutable target identity used for verification: `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §2.2.1 L835-L848 "@dataclass(frozen=True)". The frozen `CanonicalDependencySet` records `(namespace, identity, digest)` entries and rejects duplicate identities: `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §2.3 L498-L508 "### `CanonicalDependencySet`". Dependency identity can be derived deterministically from the target dependency map: `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §11.4 L3353-L3357 "def dependency_map_digest(deps: FrozenMap) -> Digest:".

The frozen Requirement retains source provenance and authority for claims tied to user/policy requirements: `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §3 L1273-L1286 "@dataclass(frozen=True)". Evidence identity binds input/artifact identity and freshness dependencies: `05-VERIFICATION/S-CLASS-VERIFICATION-AND-EVIDENCE-SPEC.md` §4 L60-L78 "## 4. Evidence identity".

**Who may write:** agents write candidate structured claims; evaluators write verification results and claim-ledger projections; canonical target/dependency objects are changed only through existing authorized paths. F7 adds no prose parser and no canonical event type.

### NEVER

F7 MUST NEVER parse prose to manufacture claims, accept an evidence-free claim, resolve a package by name alone, treat a stale dependency identity as current, or convert an unresolvable reference into SATISFIED.

### Cost bound

Structured claim validation is linear in claim size. Symbol/API lookup is bounded by the repository-intelligence index. Dependency identity checks are `O(log D)` after canonical sorting of `D` dependency entries. Evidence lookup is bounded by referenced receipt count. No prose parsing is required.

---

### F7 fixtures

### F7-T1 / F7-FT1 — reference symbol claim
```yaml
claim_id: CL-1
type: reference
reference_kind: symbol
subject: "pkg.rate_limiter:Limiter"
evidence_refs: []
target_snapshot: TS-1
evaluator_resolution: RESOLVED
expected_gate_output: SATISFIED
```

### F7-T2 / F7-FT2 — behavioral claim without evidence
```yaml
claim_id: CL-2
type: behavioral
subject: "POST /rate-limit"
evidence_refs: []
target_snapshot: TS-1
expected_gate_output: MISSING[PD-F7-002]
```

### F7-T3 / F7-FT3 — hallucinated reference
```yaml
claim_id: CL-3
type: reference
reference_kind: symbol
subject: "pkg.hallucinated:MissingClass"
evidence_refs: []
created_by_delta: false
target_snapshot: TS-1
evaluator_resolution: MISSING
expected_gate_output: MISSING[PD-F7-004]
```

### F7-T4 / F7-FT4 — dependency digest mismatch
```yaml
claim_id: CL-4
type: reference
reference_kind: package
subject: "ratelimit-core"
evidence_refs: []
target_snapshot: TS-1
expected_dependency_digest: D1
canonical_dependency_set_digest: D2
expected_gate_output: MISSING[PD-F7-003]
```

### F7-T5 / F7-FT5 — claim-type evidence rules
```yaml
reference_claim:
  type: reference
  subject: "pkg.rate_limiter:Limiter"
  evaluator_resolution: RESOLVED
behavioral_claim:
  type: behavioral
  evidence_refs: [EV-B1]
  kernel_evidence_resolves: true
completion_claim:
  type: completion
  evidence_refs: []
  obligation_closed: false
expected_reference_result: SATISFIED
expected_behavioral_result: SATISFIED
expected_completion_result: MISSING[PD-F7-005]
```

### F7-T6 / F7-FT6 — post-delta symbol resolution
```yaml
reference_kind: symbol
pre_delta_index: []
post_delta_overlay: [pkg.rate_limit.check]
claim_subject: pkg.rate_limit.check
created_by_delta: true
expected_gate_output: SATISFIED
absent_case_subject: pkg.missing.check
absent_case_created_by_delta: true
absent_case_post_delta_present: false
expected_absent_case: MISSING[PD-F7-006]
pre_existing_absent_subject: pkg.legacy.missing
pre_existing_created_by_delta: false
expected_pre_existing_absent: MISSING[PD-F7-004]
```
