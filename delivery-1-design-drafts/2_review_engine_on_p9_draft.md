# Design Draft 2: Review Engine on P9 (Review and Hardening)

**Document Reference:** `delivery-1-design-drafts/2_review_engine_on_p9_draft.md`  
**Base Commit:** `3ed415e67e15e6aedc7d456445c3c193146ae606`  
**Master Source:** `FREEZE-CANDIDATE-v6.0.2/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md` (§2.15 P9, L1880 bytes)  
**Status:** PROPOSAL / DESIGN DRAFT (Not an accepted normative change; for GPT review and onward gating by CL)

---

## 1. Executive Summary & Context

Phase 9 (P9) governs Review and Hardening. Operating downstream of per-task verification (P7) and repair (P8), P9 serves as the aggregate gatekeeper before delivery readiness (P10). It evaluates whether all planned tasks executed to completion, resolves open defect findings, enforces regression hardening, and binds to kernel release authority without inventing an independent workflow state machine.

This proposal specifies the design of the S-Class P9 Review Engine adhering strictly to Section 2.15 of the R30 Master Product Design.

---

## 2. Direct Master Quotes & Normative Anchors

### 2.1 Trace Statement & Purpose (§2.15.1, §2.15.2)
> **Master Quote:**  
> *"P9 reviews the aggregate evidence, resolves findings and hardens against relevant regression without inventing a state machine."*
>
> *"F5 owns phase composition: P5-P8 are `ENTRY AND TASK_LOOPS AND PRODUCT_ADDED_BLOCKS`; P9/P10 aggregate per-task P7 outputs through their phase sub-check tables; kernel authority and product block are conjoined."*

### 2.2 Entry Predicate & Inputs (§2.15.1, §2.15.3)
> **Master Quote:**  
> *"P7 per-task results, P8 repair results where applicable, current target/obligation snapshots and F5 sub-check outputs are replayable at a common evaluation instant."*
>
> *"Inputs: Per-task TaskGateResult, canonical Decision/approval, findings, evidence and freshness results, regression/security/dependency reports, target and policy versions."*

### 2.3 Agent Instructions & Dispositions (§2.15.4)
> **Master Quote:**  
> *"Review only bound and fresh evidence. Each finding must reference a check/evidence/obligation and have disposition `FIXED`, `AUTHORIZED_WAIVER`, or `OPEN`. A waiver must be frozen-authority-bound; a product reviewer cannot self-authorize one. Regressions route to P8/P6/P5. Aggregate P7 task results deterministically under F5; one passing task cannot cancel another task's failure."*

### 2.4 Artifacts + Schemas (§2.15.5)
> **Master Quote:**  
> | Payload | Required fields | Binding / authority |
> |---|---|---|
> | `ReviewRecord` | `review_id`, `target_snapshot_ref`, `task_result_refs`, `finding_refs`, `policy_version`, `evaluation_instant`, `content_digest` | projection, not release authority |
> | `FindingDisposition` | `finding_ref`, `disposition`, `repair_ref`, `decision_ref`, `evidence_refs`, `content_digest` | decision/waiver links required for authorized exception |

### 2.5 Sub-Check Table (§2.15.6)
> **Master Quote:**  
> | check | class M/E/J | decision procedure | inputs | failure route | cost bound |
> |---|---|---|---|---|---|
> | `P9-COMPLETENESS` | M | aggregate every required per-task P7 result via F5 | task results, sub-check tables | missing task result → MISSING | O(tasks + findings) |
> | `P9-FRESHNESS` | M | recompute frozen freshness at recorded instant | target/policy/evidence digests | invalidate and rerun P7 | O(declared dependencies) |
> | `P9-FINDINGS` | M/E | every finding has current disposition plus evidence or authorized Decision | finding graph, links | open finding blocks | O(findings + links) |
> | `P9-HARDENING` | E | run applicable qualified F10 adapter checks, including security/dependency regressions from policy | adapter registry, check plans | repair P8/P6/P5 or BLOCKED | adapter time/output caps |

### 2.6 Formal Gate & Normative Closure (§2.15.7, §2.15.12)
> **Master Quote:**  
> `G_P9 = ALL_REQUIRED_TASK_RESULTS_PRESENT AND FRESHNESS_CURRENT AND FINDINGS_CLOSED_OR_AUTHORIZEDLY_WAIVED AND HARDENING_CHECKS_PASS AND KERNEL_AUTHORITY_VALID`  
>
> `PD-CH2-052 | M/E/J | P9 MUST aggregate all required P7 task results and close each mandatory finding only by evidence or canonical authority. | CH2-T52 one required P7 result omitted or one mandatory finding open → MISSING[PD-CH2-052]; unauthorized waiver → BLOCKED_ON_HUMAN[PD-CH2-052].`
>
> **NEVER Rule:**  
> *"Average away a failed task, accept stale evidence, or let a product-layer review create a waiver."*

---

## 3. Review Engine Architecture Proposal

### 3.1 Review Engine Core Component (`sclass.product.review_engine`)
The Review Engine operates as a deterministic functional evaluator over `P7` outputs:

```
+-------------------------------------------------------------------------+
|                         P9 REVIEW ENGINE                                |
+-------------------------------------------------------------------------+
|                                                                         |
|  1. Completeness Evaluator (P9-COMPLETENESS)                            |
|     - Verifies every WorkNode in WorkGraph has a corresponding P7       |
|       TaskGateResult.                                                   |
|     - Fails closed with MISSING[PD-CH2-052] if any task is missing.     |
|     - Rejects any averaging, majority voting, or failure masking.       |
|                                                                         |
|  2. Freshness Verifier (P9-FRESHNESS)                                   |
|     - Validates that TargetSnapshot, Policy, and Evidence digests       |
|       are identical between P7 evaluation and P9 evaluation instant.    |
|     - Invalidation forces re-execution of affected P7 tasks.            |
|                                                                         |
|  3. Finding Disposition Tracker (P9-FINDINGS)                           |
|     - Inspects all declared findings in FindingGraph.                   |
|     - DISPOSITION = FIXED: Requires valid fresh EvidenceSet link.       |
|     - DISPOSITION = AUTHORIZED_WAIVER: Requires signed Decision record  |
|       from canonical Kernel Authority (BLOCKED_ON_HUMAN if absent).     |
|     - DISPOSITION = OPEN: Immediately blocks P9 gate progression.       |
|                                                                         |
|  4. Hardening Verifier (P9-HARDENING)                                   |
|     - Invokes declared policy-mandated security and regression checks   |
|       via qualified F10 ExecutionGate adapters.                         |
|     - Enforces time/resource fence (F10 budget bounds).                 |
|                                                                         |
+-------------------------------------------------------------------------+
```

### 3.2 Immutability of Findings & Non-Self-Waiver Floor
1. Findings are immutable content-addressed projections (`FindingDisposition`).
2. An agent or reviewer cannot author an `AUTHORIZED_WAIVER` without a cryptographic link to a canonical kernel `Decision` or `ApprovalRecord`.
3. An evaluator detecting a missing or self-asserted waiver record returns:
   `GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-CH2-052", detail="Unauthorized finding waiver")`

---

## 4. Explicitly Identified Unresolved Ambiguities

Per directive, the following items are unresolved ambiguities in the R30 Master that must NOT be invented in implementation:

1. **Adapter Registry Binding for Hardening Checks (OI-003, OI-010):**
   - Section 2.15 specifies running *"applicable qualified F10 adapter checks, including security/dependency regressions from policy"*. However, the precise policy mapping schema determining which adapters are triggered for which file extensions remains open under F10 qualification.
2. **Multi-Task Finding Span & Granularity:**
   - The master does not specify whether a finding discovered during aggregate P9 review must be attributed back to a specific individual task `work_node_id` or whether it may remain an aggregate finding attached directly to the `ReviewRecord`.
3. **Hardening Failure Routing Priority:**
   - Section 2.15 lists `repair P8/P6/P5 or BLOCKED` as the failure route for `P9-HARDENING`. It does not specify the deterministic arbitration logic for deciding whether an aggregate hardening failure routes backwards to P8 (repair), P6 (re-implementation), or P5 (test design).
