# Design Draft 1: Chapter 8 Category (Workspace, Enforcement, Parallelism, Brownfield, Budget, and Repair)

**Document Reference:** `delivery-1-design-drafts/1_chapter_8_category_draft.md`  
**Base Commit:** `3ed415e67e15e6aedc7d456445c3c193146ae606`  
**Master Source:** `FREEZE-CANDIDATE-v6.0.2/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md` (Chapter 8, L22822 bytes)  
**Status:** PROPOSAL / DESIGN DRAFT (Not an accepted normative change; for GPT review and onward gating by CL)

---

## 1. Executive Summary & Context

Chapter 8 defines the operational execution boundary of S-Class: how the product layer interfaces with the physical workspace, isolates worker processes, handles out-of-band developer edits, coordinates parallel mutations, surfaces repository intelligence, and stops runaway execution through hard budget gates.

This draft formalizes the Chapter 8 category proposals while preserving exact master terminology and quoting authoritative definitions.

---

## 2. Direct Master Quotes & Normative Anchors

### 2.1 Trace Statement & Enforcement Tiers (§8.1)
> **Master Quote:**  
> *"S-Class prevents unauthorized writes only for workers it launches inside its enforcement boundary; host-native activity is detected from observed deltas."*
>
> **Enforcement Tiers:**  
> - **E0 advisory:** display gate results and proposed patches; no write-prevention promise.  
> - **E1 mediated worker:** S-Class-launched worker writes pass through ExecutionGate and its configured isolation boundary; preventive claim is limited to qualified OS/runtime support.  
> - **E2 controlled promotion:** authorized worker changes are staged against a bound baseline and promoted only after kernel and product gates close; does not mean IDE-native writes were prevented.  
>
> *"Current documented enforcement is Linux worker isolation with Bubblewrap/cgroup v2; other hosts/remote workers need qualification. See `03-RUNTIME/S-CLASS-WORKER-RUNTIME-AND-HARNESS-CONTRACT.md` §2 L13-L24 '## 2. Worker model' and `01-ARCHITECTURE/S-CLASS-OSS-FIRST-ARCHITECTURE.md` §5 L71-L88 '## 5. Runtime zones'. These are design inputs, not a production claim."*

### 2.2 Workspace and Promotion (§8.2)
> **Master Quote:**  
> *"Baseline is a TargetSnapshot plus content/dependency digests and a declared worktree root. Patch proposal is compared to canonical allowed write set before worker writes; promotion is separate from worktree mutation. Promotion requires F5-gated current evidence, kernel ReleaseEvaluation and authorization. A host-native workspace watcher compares observed tree to baseline and reports out-of-band mutations; detection may be delayed, so do not claim prevention."*

### 2.3 Out-of-band and Concurrent Edits (§8.3)
> **Master Quote:**  
> *"Out-of-band/concurrent edits MUST trigger re-snapshot and digest comparison before continuing; invalidation is owned by `PD-CH2-055`."*

### 2.4 Parallelism and Merging (§8.4)
> **Master Quote:**  
> *"Parallel work MUST follow dependencies and canonical delta order, serialize overlapping write sets and merge only when target identity and each task verification pass."*

### 2.5 Repository Intelligence & Brownfield (§8.5)
> **Master Quote:**  
> *"Repository intelligence MUST disclose index coverage/freshness and unresolved symbols remain MISSING."*

### 2.6 Budget, Observability and Repair (§8.6)
> **Master Quote:**  
> *"Budget exhaustion MUST stop or route to an authorized repair path; retry decisions use the frozen RetryBudget with no second ledger; hard budget gates reject model-reported-only cost and admit only authoritative or host-attested cost metrics; resource and runtime limits use explicit units/defaults."*

---

## 3. Normative Requirements Allocation (PD-CH8)

The R30 Master defines six active MUST obligations in the Chapter 8 reserved range (`PD-CH8-008..013`):

| MUST ID | Class | Master Statement | Failure Route | Happy Fixture / Gaming Fixture |
|---|---|---|---|---|
| `PD-CH8-008` | M | Prevention MUST be claimed only inside a launched and qualified enforcement boundary; native IDE activity is detection/containment, not prevention. | `MISSING[PD-CH8-008]` with separate `action_result: BLOCKED` | CH8-T9 (`SATISFIED`) / CH8-T8 |
| `PD-CH8-009` | M | Workspace promotion MUST require the current target and kernel release authority after verification and preserve rollback evidence; comparison of the observed write set with authorized scope is owned by `PD-CH4-014`. | `MISSING[PD-CH8-009]` | CH8-T11 (`SATISFIED`) / CH8-T10 |
| `PD-CH8-010` | M | Out-of-band/concurrent edits MUST trigger re-snapshot and digest comparison before continuing; invalidation is owned by `PD-CH2-055`. | `MISSING[PD-CH8-010]` | CH8-T13 (`SATISFIED`) / CH8-T12 |
| `PD-CH8-011` | M | Parallel work MUST follow dependencies and canonical delta order, serialize overlapping write sets and merge only when target identity and each task verification pass. | `MISSING[PD-CH8-011]` | CH8-T15 (`SATISFIED`) / CH8-T14 |
| `PD-CH8-012` | M | Repository intelligence MUST disclose index coverage/freshness and unresolved symbols remain MISSING. | `MISSING[PD-CH8-012]` | CH8-T17 (`SATISFIED`) / CH8-T16 |
| `PD-CH8-013` | M | Budget exhaustion MUST stop or route to an authorized repair path; retry decisions use the frozen RetryBudget with no second ledger; hard budget gates reject model-reported-only cost and admit only authoritative or host-attested cost metrics; resource and runtime limits use explicit units/defaults. | `MISSING[PD-CH8-013]` | CH8-T19 (`SATISFIED`) / CH8-T18 |

---

## 4. Architectural Proposals for Category Implementation

### 4.1 Enforcement Boundary Adapter Architecture
To implement `PD-CH8-008` without polluting frozen kernel registries:
1. Define an `EnforcementContext` abstraction in `sclass.product.workspace`:
   - Properties: `boundary_tier` (`E0_ADVISORY`, `E1_MEDIATED_WORKER`, `E2_CONTROLLED_PROMOTION`), `isolation_provider` (e.g. `BubblewrapLinuxCgroupV2`), `qualified_status` (`bool`).
   - If worker write prevention is claimed when `boundary_tier != E1_MEDIATED_WORKER` or `qualified_status is False`, the evaluator returns `MISSING[PD-CH8-008]` with `action_result: BLOCKED`.
2. Prohibit claiming prevention for IDE-native edits:
   - Mark all filesystem watcher detections as `CONTAINMENT_OBSERVED_DELTA` rather than `PREVENTATIVE_BLOCK`.

### 4.2 Workspace Promotion Engine
To implement `PD-CH8-009`:
1. Promotion is strictly decoupled from worktree generation. Staged patches reside in isolated temporary overlays.
2. Promotion evaluator queries kernel `ReleaseEvaluation`. If release authority is absent or stale relative to `TargetSnapshot`, gate outputs `MISSING[PD-CH8-009]`.
3. Rollback record containing pre-promotion directory state digest and inverse patch must be stored prior to write-set application.

### 4.3 Concurrent Edit Reconciliation
To implement `PD-CH8-010`:
1. Prior to evaluating any task gate, re-poll the host-native watcher.
2. If working directory digest != baseline `TargetSnapshot` digest, trigger `PD-CH2-055` invalidation, invalidate downstream F5 cache entries, and demand fresh snapshot before proceeding.

### 4.4 Hard Budget Gating & Stop Mechanics
To implement `PD-CH8-013`:
1. Hard rejection of agent-self-reported token counts or execution costs.
2. Metric derivation reads only:
   - Process runtime metrics from OS cgroup accounting or process execution receipts.
   - Authoritative proxy/API gateway signed receipts for model invocation tokens.
3. If cost metric > budget ceiling or elapsed time > timeout, execution halts immediately with `MISSING[PD-CH8-013]`. No automatic retry ledger may be created; retry relies exclusively on frozen `RetryBudget`.

---

## 5. Explicitly Identified Unresolved Ambiguities

Per directive, the following items are unresolved ambiguities in the R30 Master that must NOT be invented in implementation:

1. **Non-Linux Enforcement Boundaries (OI-005, OI-013):**
   - The master specifies Bubblewrap and cgroups v2 on Linux as the sole documented E1 boundary. Windows (AppContainer/Job Objects) and macOS (sandbox-exec) enforcement mechanisms are unqualified. How S-Class claims E1 on non-Linux platforms remains an open qualification issue (OI-005).
2. **Watcher Polling Latency vs Event-Driven Invalidation:**
   - The master notes: *"detection may be delayed, so do not claim prevention."* It does not specify the maximum allowable watcher detection latency before an out-of-band edit invalidates an ongoing evaluation.
3. **Repository Intelligence Freshness SLA:**
   - `PD-CH8-012` requires disclosing index freshness, but does not define a universal numerical threshold for when an index transitions from `FRESH` to `STALE` across varying repository sizes.
4. **Repair Path Escalation Protocol:**
   - `PD-CH8-013` specifies that budget exhaustion *"routes to an authorized repair path"*, but the exact handoff contract between Phase 8 (Repair) and external human operators is unspecified when the `RetryBudget` is depleted.
