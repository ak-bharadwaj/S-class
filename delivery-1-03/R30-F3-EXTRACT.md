# Normative Extract: R30 Section F3 Trust Model for Agent-Authored Content

## Document Provenance & Verification
- **Source Archive:** `FREEZE-CANDIDATE-v6.0.2-R30.zip`
- **Source File:** `FREEZE-CANDIDATE-v6.0.2/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`
- **Expected SHA-256:** `340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff`
- **Verified SHA-256:** `340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff`
- **Integrity Status:** `MATCH - VERIFIED`

---

## Section F3 Normative Text

<!-- SECTION F3 | status: ACCEPTED -->
## F3 — Trust model for agent-authored content

**Status:** ACCEPTED.

**Known defects:** none.

### Context

Agent-authored artifacts are candidate content and provenance, not proof. The canonical structured representation is the gate-relevant object. Prose is explanatory and is not mechanically compared. Trust is established only by evaluator checks or by an authorized human/policy confirmation bound to the canonical structured content.

### Decision

1. The **canonical structured form is authoritative for gates**.
2. Requirement confirmation follows the frozen path: `REQUIREMENT_CONFIRMED` is the USER/POLICY event and `Requirement.source_provenance` is the digest of the canonical structured form. Design confirmations are `Decision` outcomes. `ApprovalRecord` and product-layer `ConfirmationScope` are used only for governance approvals such as weakening, adapter changes and waivers.
3. A human confirmation is admissible only when S-Class renders the canonical structured form on an S-Class-controlled or host-native surface. Text relayed by an agent is not admissible. An approval is admissible only when signed by a principal key never reachable from the agent; no agent-callable tool may create or forward an approval.
4. Prose is explanatory. A semantic conflict check is performed only between two structured representations; prose is never a mechanical comparison operand.
5. A changed canonical description/rendering requires reconfirmation because the confirmation is bound to the canonical content digest.

The artifact envelope is defined in **§2.5**, not F1. Gate states are defined by the gate function in **F5 / Chapter 5**, not by F1. F3 consumes those definitions and does not redefine them.

### MUST requirements

| ID | Class | Requirement | Test |
|---|---|---|---|
| PD-F3-001 | M | Agent-authored content MUST remain a claim/provenance input and MUST NOT self-authenticate. | F3-T1 agent marks `verified=true` with no evaluator record → `MISSING[PD-F3-001]`; F3-T7 evaluator-backed record present → `SATISFIED`. |
| PD-F3-002 | M | Gate authority MUST come from evaluator-produced check records bound to the canonical object and target. | F3-T2 agent-written PASS record with no evaluator provenance → `MISSING[PD-F3-002]`. |
| PD-F3-003 | M | Conflicting structured representations MUST be detected without using explanatory prose as a mechanical comparison operand. | F3-T3 two structured fields disagree while prose differs only explanatorily → `BLOCKED_ON_HUMAN[PD-F3-003]`. |
| PD-F3-004 | E | Requirement confirmation MUST be a `REQUIREMENT_CONFIRMED` USER/POLICY event whose `Requirement.source_provenance` equals the digest of the canonical structured form; design confirmations MUST be Decision outcomes; ApprovalRecord/ConfirmationScope MUST be reserved for governance approvals. | F3-T4 reconfirmation after canonical digest change requires a human → `BLOCKED_ON_HUMAN[PD-F3-004]`. |
| PD-F3-005 | E | The evaluator MUST recompute `content_digest`; a claimed digest that differs from the recomputed digest is invalid. | F3-T5 claimed D1, recomputed D2 → `MISSING[PD-F3-005]`. |
| PD-F3-006 | M | Human confirmation is admissible only from an S-Class-controlled or host-native rendering surface; agent-relayed confirmation text is inadmissible; the signing principal key MUST be unreachable from the agent, no agent-callable tool may create or forward an approval, and this control assumes the key resides in a separate OS principal or hardware-backed store requiring user presence. | F3-T6 approval submitted through an agent-facing tool → `BLOCKED_ON_HUMAN[PD-F3-006]`. |

### Tests / fixtures

| Test | Concrete input summary | Exact expected result |
|---|---|---|
| F3-T1 | candidate has `producer=agent`, `verified=true`, evaluator checks empty | `MISSING[PD-F3-001]` |
| F3-T2 | agent supplies `check_records:[{status:PASS,producer:agent}]`, evaluator record absent | `MISSING[PD-F3-002]` |
| F3-T3 | structured A predicate `rate <= 100`; structured B predicate `rate <= 1000`; prose present but excluded from comparison | `BLOCKED_ON_HUMAN[PD-F3-003]` |
| F3-T4 | `REQUIREMENT_CONFIRMED` has `Requirement.source_provenance=D1`, canonical structured form recomputes to D2 and no human reconfirmation is present | `BLOCKED_ON_HUMAN[PD-F3-004]` |
| F3-T5 | envelope claims `content_digest=D1`; evaluator recomputes D2 | `MISSING[PD-F3-005]` |
| F3-T6 | governance approval submitted through an agent-facing tool; principal key is agent-reachable | `BLOCKED_ON_HUMAN[PD-F3-006]` |
| F3-T7 | happy: agent claims verified, evaluator check record bound to canonical object and target is present | `SATISFIED`; the claim itself carries no authority |

### KERNEL BINDING

The frozen event vocabulary includes `REQUIREMENT_CONFIRMED`: `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §12.1 L3517-L3521 "class EventType(Enum):". `Requirement.source_provenance` is a digest of the source artifact/message and USER/POLICY authority makes the requirement binding: `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §3 L1273-L1286 "@dataclass(frozen=True)".

Frozen `Authority.USER` and `Authority.POLICY` are binding authority classes: `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §2.4 L1172-L1178 "class Authority(Enum):". Frozen `Requirement` carries that authority and binds only USER/POLICY requirements: `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §3 L1273-L1286 "@dataclass(frozen=True)".

Frozen approval kinds include `DUAL_AUTHORIZATION`, `POLICY_RELAXATION`, `BREAK_GLASS_USE`, `WAIVER`, `RELEASE`: `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §4 L1601-L1606 "class ApprovalKind(Enum):". F3 uses `DUAL_AUTHORIZATION` only where a governance approval requires dual approval; it is not a Requirement confirmation kind.

The frozen `ApprovalRecord` has `target_digest` and `scope_digest` only for target/scope binding among its digest fields: `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §4 L1609-L1620 "class ApprovalRecord:". F3 defines a product-layer `ConfirmationScope` object with exactly `objective_revision`, `obligation_ref` or `decision_ref`, and `artifact_type`; its C1 digest is stored in `ApprovalRecord.scope_digest`. `objective_revision`, `obligation_ref` and `artifact_type` are not added to `ApprovalRecord`.

The frozen `Decision` object is bound separately: `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §3 L1306-L1313 "@dataclass(frozen=True)". Evidence is not acceptance and independent verification is separate: `05-VERIFICATION/S-CLASS-VERIFICATION-AND-EVIDENCE-SPEC.md` §5 L80-L93 "## 5. Evidence is not acceptance" and §10 L149-L151 "## 10. Independent verification". Freshness remains a pure use-time predicate: `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §11.4 L3325-L3335 "### 11.4 Freshness — a pure".

**Who may write:** agents write candidate artifacts and candidate claims; evaluators write `check_records`; humans or governing policy write confirmations. Key-custody admissibility assumes the principal key is held by a separate OS principal or hardware-backed store requiring user presence; an agent running as the same OS user is therefore not an admissible separation boundary. Canonical approval records are written only through the existing authorized approval path; F3 creates no new event or approval store.

### NEVER

F3 MUST NEVER treat prose, model confidence, producer identity or agent-written PASS text as gate authority; compare prose mechanically; accept agent-relayed confirmation text; carry confirmation across a changed canonical digest without reconfirmation; or create a parallel approval/trust store.

### Cost bound

Digest recomputation is `O(size(content))`; structured conflict checking is bounded by the compared structured-object size; ConfirmationScope digesting is linear in canonical scope size; evaluator lookup is bounded by referenced canonical records. Human confirmation adds interruption cost only when policy requires it. No unbounded model reasoning is a gate requirement.

**State:** DESIGNED; not VERIFIED.



---

## Authoritative F3 Test Fixtures (F3-T1 through F3-T7)

### F3 fixtures

### F3-T1 / F3-FT1 — agent claim is not proof
```yaml
must_id: PD-F3-001
fixture_role: gaming
input_binding: candidate claim vs evaluator check records
bound_inputs: [candidate_digest, evaluator_check_records]
mutates: [evaluator_check_records]
op: omit
candidate:
  producer: agent
  verified: true
evaluator_check_records: []
expected_gate_output: MISSING[PD-F3-001]
execution_evidence: UNVERIFIED
```

### F3-T2 / F3-FT2 — agent-written PASS has no authority
```yaml
candidate:
  check_records:
    - check_id: C1
      status: PASS
      producer: agent
evaluator_check_records: []
expected_gate_output: MISSING[PD-F3-002]
```

### F3-T3 / F3-FT3 — structured conflict only
```yaml
structured_a:
  acceptance:
    predicate: "rate LESS_OR_EQUAL 100"
structured_b:
  acceptance:
    predicate: "rate LESS_OR_EQUAL 1000"
prose:
  text: "The endpoint has a rate limit."
  mechanically_compared: false
expected_gate_output: BLOCKED_ON_HUMAN[PD-F3-003]
```

### F3-T4 / F3-FT4 — requirement confirmation digest mismatch and governance approval
```yaml
requirement_confirmation:
  event_type: REQUIREMENT_CONFIRMED
  authority: USER
  source_provenance: D1
  canonical_structured_form_digest: D2
  expected_gate_output: BLOCKED_ON_HUMAN[PD-F3-004]
governance_approval:
  approval_id: APR-7
  kind: WAIVER
  principal_id: human-17
  principal_role: owner
  workspace_id: WS-1
  target_digest: D1
  policy_version: P7
  scope_digest: S1
  issued_at: 2026-10-06T09:00:00Z
  expires_at: 2026-10-06T18:00:00Z
  signature: SIG-7
```

### F3-T5 / F3-FT5 — content digest mismatch
```yaml
claimed_content_digest: D1
recomputed_content_digest: D2
expected_gate_output: MISSING[PD-F3-005]
```

### F3-T6 / F3-FT6 — host-native confirmation surface and key custody
```yaml
confirmation_surface: agent_facing_tool
principal_key_accessible_to_agent: true
approval_forwarding_tool_available: true
user_presence_required: false
expected_gate_output: BLOCKED_ON_HUMAN[PD-F3-006]
```

### F4 fixtures

### F3-T7 / F3-FT7 — evaluator-backed record accepted, claim ignored
```yaml
must_id: PD-F3-001
fixture_role: happy
input_binding: every named input present and digest-equal to the authorized baseline
bound_inputs: [candidate_digest, evaluator_check_records]
baseline: authorized baseline digests pinned by the F5 gate tuple; no variant mutates any bound input
candidate:
  producer: agent
  verified: true
evaluator_check_records: [{check_id: C-01, object_digest: D-1, target_digest: T-1, producer: evaluator}]
expected_gate_output: SATISFIED
```


