# GPT Review Decisions Log: Block 1-05 (Lane A: Section F7 Fail-Closed Remediation)

**Lane:** Lane A (`lane-a-f7-fix`)  
**Authority:** CL's BPC failure decision & remediation directive  
**Starting HEAD:** `78389f9a46d105197221b4bb17f988b3f9739d6e` (from `integration-r30-b1`)  
**Implementation Commit C:** `de4cd7a833e64c005143a70775c31ba974efe611`  
**Status Standard:** All status labels use `SOURCED (file, section)` or `UNVERIFIED`.

---

## 1. Normative Register & Decisions

| MUST ID | Obligation Title | Status Label | Normative Authority & Source | Architectural Disposition |
|---|---|---|---|---|
| `PD-F7-001` | Structured Claim Representation & Prose Rejection | `SOURCED (S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md, §F7)` | R30 Master Product Design §F7 | Every agent claim MUST be a structured record with `claim_id`, `type`, `subject`, and optional `evidence_refs`. Prose alone rejected. Candidate-embedded resolvers in candidate specs strictly ignored. |
| `PD-F7-002` | Evidence Requirements for Behavioral and Completion Claims | `SOURCED (S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md, §F7)` | R30 Master Product Design §F7 | Behavioral claims require caller-injected `KernelEvidenceResolver`; non-empty `evidence_refs` without resolver is not proof. Completion claims require caller-injected evidence resolution. Missing resolver yields `MISSING[PD-F7-002]`. |
| `PD-F7-003` | TargetSnapshot & Canonical Dependency Identity Resolution | `SOURCED (S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md, §F7)` | R30 Master Product Design §F7 | Proposed packages require caller-injected `CanonicalDependencyResolver`. Canonical digest MUST come from resolver, not candidate payload. Missing resolver yields `MISSING[PD-F7-003]`. Packages MUST NEVER be resolved by name alone. |
| `PD-F7-004` | Pre-Existing Reference Absence from Pre-Delta View | `SOURCED (S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md, §F7)` | R30 Master Product Design §F7 | Pre-existing references (`created_by_delta=false`) require caller-injected `RepositoryIntelligenceIndex`. Absence pre-delta or missing index yields `MISSING[PD-F7-004]`. Candidate flags ignored. |
| `PD-F7-005` | Closed Claim-Type Registry & Declared Evidence Rules | `SOURCED (S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md, §F7)` | R30 Master Product Design §F7 | Claim types MUST use the closed v1 registry: `reference`, `behavioral`, `completion`. Completion claims require caller-injected `ObligationClosureResolver`. Payload `obligation_closed: true` NEVER confers closure. Missing resolver yields `MISSING[PD-F7-005]`. |
| `PD-F7-006` | Post-Delta Symbol Resolution & Precedence | `SOURCED (S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md, §F7)` | R30 Master Product Design §F7 | Delta-created references (`created_by_delta=true`) require caller-injected `RepositoryIntelligenceIndex`. Absence post-delta or missing index yields `MISSING[PD-F7-006]`. Precedence over PD-F7-004 enforced. |

---

## 2. Gating & Remediation Constraints

1. **Candidate Authority Stripped:** All candidate-supplied evaluator authority removed. In `src/sclass/product/claim_ledger.py`, candidate flags (`evaluator_resolution`, `pre_delta_present`, `post_delta_present`, `kernel_evidence_resolves`, `obligation_closed`, `absent_case_post_delta_present`) and embedded resolvers are completely disregarded.
2. **Auto-Manufacturing Path Removed:** Removed composite F7-T6 path manufacturing `InMemoryRepositoryIntelligenceIndex` from candidate `pre_delta_index` and `post_delta_overlay`. Callers must supply `repo_index`.
3. **Commit C Scope Boundary:** Commit C (`de4cd7a833e64c005143a70775c31ba974efe611`) contains only implementation in `src/sclass/product/claim_ledger.py` and authoritative test suite in `tests/product/test_claim_ledger.py`. Zero modifications to frozen directories (`00-SPEC/`, `10-CONFORMANCE/`, `20-RUNTIME/`).
4. **Commit E Scope Boundary:** Commit E contains only delivery materials within `delivery-1-05/`.
5. **Merge Authority:** In strict adherence to governance instructions, Ak retains exclusive merge authority after CL gate acceptance. No self-pass or QUALIFIED status is claimed.
