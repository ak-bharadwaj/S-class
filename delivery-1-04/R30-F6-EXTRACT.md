# R30 Master Product Design Extract: Section F6 Traceability Links

**Source Document:** `FREEZE-CANDIDATE-v6.0.2/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`  
**Section:** `## F6 — Traceability links` & `### F6 fixtures`  
**Status:** ACCEPTED

---

## F6 — Traceability links

**Status:** ACCEPTED.

**Known defects:** none.

### Context

P3-2 requires real typed traceability rather than name matching or asserted coverage. F6 defines links derived only from kernel objects referenced through product-layer `source_refs`.

### Decision

The normative typed chain is:

`Requirement -> AcceptanceCriterion -> VerificationStep -> Test -> Evidence -> Obligation`.

Each link has a type, source canonical object identity, destination canonical object identity and source provenance. Product-layer artifacts may propose `source_refs`; the evaluator resolves those references to existing kernel objects before a link becomes part of computed coverage. An `AcceptanceContract` defines an acceptance criterion through its `required_evidence`, `composition`, `waiver_rules`, and `authored_by` fields; F6 does not invent an alternate acceptance object. A product-layer criterion node identity is `(contract_id, RequiredEvidence.requirement_key)` and is bound to the frozen `RequiredEvidence` fields; a product-layer `Test` node identity is `(path, content_digest)` and is verified against the frozen `TargetSnapshot`.

Coverage is computed, never asserted. Planned coverage is the typed chain resolved through `VerificationStep` before evidence exists; realized coverage requires the same chain plus admissible evidence. A link is valid only when both endpoint content digests are current under the frozen freshness predicate. Required coverage is complete when every required obligation has a valid typed path from its governing Requirement through the applicable acceptance criterion, verification step, test and admissible evidence. An object referenced but not connected by the expected incoming/outgoing relation is an orphan and cannot contribute coverage.

`link_id = digest(C1(link_type, source_stable_id, destination_stable_id))`. Revision numbers and rendering text are not part of link identity, so the same logical endpoints retain the same link ID across revisions. A changed endpoint creates a new link identity and invalidates the old path for coverage purposes.

### MUSTs

| ID | Class | Requirement | Test |
|---|---|---|---|
| PD-F6-001 | M | Trace links MUST be typed and derived only from resolved kernel objects reached through `source_refs`. | F6-T1 complete typed chain → `SATISFIED`. |
| PD-F6-002 | M | Coverage MUST be computed from valid links and MUST detect orphan nodes rather than accepting asserted coverage. | F6-T2 orphan verification step → `MISSING[PD-F6-002]`. |
| PD-F6-003 | M | Link identity MUST be stable across revisions when source/destination stable IDs and link type remain unchanged. | F6-T3 revision 2 with same endpoints → same `link_id`. |
| PD-F6-004 | E | Agent assertions about coverage MUST NOT substitute for evaluator-computed coverage. | F6-T4 claimed 100% coverage with a missing typed link → `MISSING[PD-F6-004]`. |
| PD-F6-005 | E | Both endpoints of a trace link MUST be current under the frozen freshness predicate before the link contributes to coverage. | F6-T5 stale evidence endpoint → `MISSING[PD-F6-005]`. |
| PD-F6-006 | M | Planned coverage MUST be computed through VerificationStep without requiring realized evidence; realized coverage MUST require admissible evidence. | F6-T6 planned chain with no evidence → planned coverage present but realized coverage absent; realized case adds admissible evidence |

### Tests

| Test | Fixture | Exact expected output |
|---|---|---|
| F6-T1 | F6-FT1 resolves Requirement R1, AC1, VS1, TEST1, EV1, OBL1 with typed links in order | `SATISFIED` |
| F6-T2 | F6-FT2 resolves VS2 but it has no valid incoming AC link | `MISSING[PD-F6-002]` |
| F6-T3 | F6-FT3 revision changes description only; stable endpoint IDs and link type unchanged | same `link_id`; `SATISFIED` |
| F6-T4 | F6-FT4 artifact claims `coverage=100%` but misses `Test -> Evidence` link | `MISSING[PD-F6-004]` |
| F6-T5 | F6-FT5 destination evidence digest is stale under the frozen freshness predicate | `MISSING[PD-F6-005]` |
| F6-T6 | F6-FT6 planned chain has Requirement/AcceptanceCriterion/VerificationStep/Test but no evidence; realized case adds admissible evidence | planned coverage computed, realized coverage absent; realized case `SATISFIED` |

### Kernel binding

The frozen `AcceptanceContract` defines the acceptance criterion through `contract_id`, `obligation_id`, `revision`, `required_evidence`, `composition`, `waiver_rules`, and `authored_by`: `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §5.2 L2021-L2030 "@dataclass(frozen=True)". The frozen `RequiredEvidence` fields are `requirement_key`, `evidence_kind`, `verifier_id`, `min_independence`, `freshness`, `mandatory`, and `min_receipts`: `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §5.2 L1925-L1932 "class RequiredEvidence:". The frozen `Requirement` carries `derived_obligations` and authority: `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §3 L1273-L1286 "@dataclass(frozen=True)". The frozen `Obligation` carries its acceptance-contract and satisfied-evidence relationships: `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §5 L1813-L1826 "@dataclass(frozen=True)". `VerificationStep` is a canonical verification-plan object: `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §5.2 L2039-L2047 "@dataclass(frozen=True)". Evidence identity is bound to obligation(s), target snapshot, verification step and tool/result identities: `05-VERIFICATION/S-CLASS-VERIFICATION-AND-EVIDENCE-SPEC.md` §4 L60-L78 "## 4. Evidence identity".

**Who may write:** agents may propose `source_refs` in candidate artifacts; the evaluator resolves and writes computed link/coverage projections; canonical kernel objects and their authority remain writable only through existing authorized transition paths. F6 adds no canonical state field or event.

### NEVER

F6 MUST NEVER infer links from similar names, accept agent-asserted coverage, attach evidence without resolved source identity, or create a second traceability authority.

### Cost bound

Link construction is `O(L log L)` for `L` links after canonicalization. Orphan detection is linear in canonical node/link counts. Coverage traversal is bounded by the typed chain depth and number of obligations. Digest computation is linear in stable endpoint encoding.

---

### F6 fixtures

### F6-T1 / F6-FT1 — complete typed chain
```yaml
nodes: [REQ-1, AC-1, VS-1, TEST-1, EV-1, OBL-1]
links:
  - {type: REQUIREMENT_TO_ACCEPTANCE, source: REQ-1, destination: AC-1}
  - {type: ACCEPTANCE_TO_VERIFICATION, source: AC-1, destination: VS-1}
  - {type: VERIFICATION_TO_TEST, source: VS-1, destination: TEST-1}
  - {type: TEST_TO_EVIDENCE, source: TEST-1, destination: EV-1}
  - {type: EVIDENCE_TO_OBLIGATION, source: EV-1, destination: OBL-1}
source_refs_resolve: true
expected_gate_output: SATISFIED
```

### F6-T2 / F6-FT2 — orphan verification step
```yaml
nodes: [REQ-2, AC-2, VS-2, TEST-2, EV-2, OBL-2]
links:
  - {type: REQUIREMENT_TO_ACCEPTANCE, source: REQ-2, destination: AC-2}
  - {type: VERIFICATION_TO_TEST, source: VS-2, destination: TEST-2}
  - {type: TEST_TO_EVIDENCE, source: TEST-2, destination: EV-2}
  - {type: EVIDENCE_TO_OBLIGATION, source: EV-2, destination: OBL-2}
source_refs_resolve: true
orphan_nodes: [VS-2]
expected_gate_output: MISSING[PD-F6-002]
```

### F6-T3 / F6-FT3 — stable link identity across revision
```yaml
link_type: ACCEPTANCE_TO_VERIFICATION
source_stable_id: AC-3
destination_stable_id: VS-3
revision_1: 1
revision_2: 2
revision_1_description: "Rate limit accepted."
revision_2_description: "Rate limit accepted with clarified wording."
expected_link_id_revision_1: SHA256(C1(ACCEPTANCE_TO_VERIFICATION|AC-3|VS-3))
expected_link_id_revision_2: SHA256(C1(ACCEPTANCE_TO_VERIFICATION|AC-3|VS-3))
expected_gate_output: SATISFIED
```

### F6-T4 / F6-FT4 — asserted coverage ignored
```yaml
agent_claimed_coverage_percent: 100
resolved_links:
  - {type: REQUIREMENT_TO_ACCEPTANCE, source: REQ-4, destination: AC-4}
  - {type: ACCEPTANCE_TO_VERIFICATION, source: AC-4, destination: VS-4}
  - {type: VERIFICATION_TO_TEST, source: VS-4, destination: TEST-4}
  - {type: EVIDENCE_TO_OBLIGATION, source: EV-4, destination: OBL-4}
missing_link: {type: TEST_TO_EVIDENCE, source: TEST-4, destination: EV-4}
expected_gate_output: MISSING[PD-F6-004]
```

### F6-T5 / F6-FT5 — stale endpoint freshness
```yaml
source_digest: VS-5
destination_digest: EV-5
source_fresh: true
destination_fresh: false
expected_gate_output: MISSING[PD-F6-005]
```

### F6-T6 / F6-FT6 — planned versus realized coverage
```yaml
planned:
  nodes: [REQ-1, AC-1, VS-1, TEST-1]
  evidence: []
  expected_planned_coverage: 1.0
  expected_realized_coverage: 0.0
realized:
  evidence: [EV-1]
  expected_realized_coverage: 1.0
```
