# S-Class v6.0.2 Block 1 Consolidated Design Proposals

**Document Identifier:** `delivery-1-design-drafts/S-CLASS-v6.0.2-BLOCK-1-DESIGN-DRAFTS-COMBINED.md`  
**Repository:** `ak-bharadwaj/S-class`  
**Branch:** `lane-c-design-drafts`  
**Base Parent Commit:** `3ed415e67e15e6aedc7d456445c3c193146ae606`  
**Normative Authority:** `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` (Frozen Kernel v6.0.1)  
**Master Source:** `FREEZE-CANDIDATE-v6.0.2/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md` (Candidate R30)  
**Companion Research Sources:**  
- `FREEZE-CANDIDATE-v6.0.2/product/r29-companion/RESEARCH-NOTES-R29.md`  
- `FREEZE-CANDIDATE-v6.0.2/product/r29-companion/FREEZE-DECISION-R28.md`  
**Status:** PROPOSAL / DESIGN DRAFT ONLY  
*Notice: This document is an unaccepted engineering proposal submitted for GPT coordinator review and subsequent single-pass gating by CL. It does NOT constitute an accepted normative change, does not alter MUST statuses, and introduces zero kernel modifications.*

---

## Document Architecture & Compliance Summary

This consolidated design document unites three core product-layer proposals for S-Class v6.0.2 Block 1:
1. **Section 1: Chapter 8 Operational Category** (Workspace, Enforcement Boundary, Parallelism, Brownfield, Budget, and Repair)
2. **Section 2: Phase 9 (P9) Review Engine** (Review, Hardening, and Non-Self-Waiver Floor)
3. **Section 3: Phase 4 (P4) Additions** (Planning, Bounded Decomposition, Mechanical Overlap Serialization, and Traceability Binding)

Every proposed MUST requirement across all three sections is subjected to and evaluated against CL's Six Mandatory Design Gates:
- **Gate 1 (IDs & Registries):** Strict adherence to reserved non-reusing ranges (`PD-CH8-014+` for Chapter 8, `PD-CH2-066+` for Chapter 2); zero reuse of retired IDs; full registry and test-registry rows provided.
- **Gate 2 (Complete MUST Structure):** Complete 8-part specification for every requirement (ID, Class, Decidable Requirement, Gaming Fixture, Happy Fixture, Expected Gate Outputs [SATISFIED, MISSING, BLOCKED_ON_HUMAN], Failure Route, Who may write, NEVER rule).
- **Gate 3 (No Kernel Expansion):** Zero additions of kernel events, states, enums, state machines, or agent-writable trust fields. All kernel bindings remain read-only references to frozen v6.0.1.
- **Gate 4 (Authority & Coverage):** Elimination of model-approves-own-output paths; strict prohibition of zero-finding completion without declared full coverage; prevention claims contingent on host probe verification.
- **Gate 5 (Evidence & Research Grounding):** Traceability to cited research files (`RESEARCH-NOTES-R29.md`, `FREEZE-DECISION-R28.md`); explicit identification of unverified claims; strict handling of command-analyzer bypass corpus.
- **Gate 6 (Unresolved Decisions):** Formalization of all open design ambiguities as `BLOCKED — AK DECISION REQUIRED` with explicit questions and discrete options.

---

## Consolidated Design Gates Checklist

| Section / Proposal | Gate 1: IDs & Registries | Gate 2: MUST Structure | Gate 3: No Kernel Expansion | Gate 4: Authority & Coverage | Gate 5: Evidence Grounding | Gate 6: Unresolved Decisions | Overall Status |
|---|---|---|---|---|---|---|---|
| **Section 1: Chapter 8 Category** | **PASS** (`PD-CH8-014..017`, `CH8-T20..T27`) | **PASS** (Full 8-part structure) | **PASS** (Zero kernel mutations) | **PASS** (Host probe required for prevention) | **PASS** (Cited `RESEARCH-NOTES-R29` §C; unverified corpus marked) | **BLOCKED** (4 open items require AK decision) | **SUBMITTED FOR GATING** |
| **Section 2: P9 Review Engine** | **PASS** (`PD-CH2-066..067`, `CH2-T77..T80`) | **PASS** (Full 8-part structure) | **PASS** (Projection only, zero kernel expansion) | **PASS** (Zero findings requires full coverage; non-self-waiver) | **PASS** (Cited `RESEARCH-NOTES-R29` §A, §B) | **BLOCKED** (3 open items require AK decision) | **SUBMITTED FOR GATING** |
| **Section 3: P4 Additions** | **PASS** (`PD-CH2-068..069`, `CH2-T81..T84`) | **PASS** (Full 8-part structure) | **PASS** (Read-only WorkGraph/Plan bindings) | **PASS** (Deterministic tie-break; no inferred verifiers) | **PASS** (Cited `RESEARCH-NOTES-R29` §B) | **BLOCKED** (3 open items require AK decision) | **SUBMITTED FOR GATING** |

---

# SECTION 1: Chapter 8 Operational Category Proposal
*(Workspace, Enforcement, Parallelism, Brownfield, Budget, and Repair)*

## 1.1 Normative Master Context & Direct Citations

Chapter 8 of `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md` governs the operational boundary between S-Class and the host operating system, filesystem, and external processes. 

Authoritative Master Quotes:
> **§ 8.1 Trace Statement & Enforcement Tiers:**  
> *"S-Class prevents unauthorized writes only for workers it launches inside its enforcement boundary; host-native activity is detected from observed deltas."*  
> *"Enforcement Tiers: E0 advisory: display gate results and proposed patches; no write-prevention promise. E1 mediated worker: S-Class-launched worker writes pass through ExecutionGate and its configured isolation boundary; preventive claim is limited to qualified OS/runtime support. E2 controlled promotion: authorized worker changes are staged against a bound baseline and promoted only after kernel and product gates close; does not mean IDE-native writes were prevented."*  
> *"Current documented enforcement is Linux worker isolation with Bubblewrap/cgroup v2; other hosts/remote workers need qualification."*

> **§ 8.2 Workspace and Promotion:**  
> *"Baseline is a TargetSnapshot plus content/dependency digests and a declared worktree root. Patch proposal is compared to canonical allowed write set before worker writes; promotion is separate from worktree mutation. Promotion requires F5-gated current evidence, kernel ReleaseEvaluation and authorization. A host-native workspace watcher compares observed tree to baseline and reports out-of-band mutations; detection may be delayed, so do not claim prevention."*

> **§ 8.3 Out-of-band and Concurrent Edits:**  
> *"Out-of-band/concurrent edits MUST trigger re-snapshot and digest comparison before continuing; invalidation is owned by `PD-CH2-055`."*

> **§ 8.4 Parallelism and Merging:**  
> *"Parallel work MUST follow dependencies and canonical delta order, serialize overlapping write sets and merge only when target identity and each task verification pass."*

> **§ 8.5 Repository Intelligence & Brownfield:**  
> *"Repository intelligence MUST disclose index coverage/freshness and unresolved symbols remain MISSING."*

> **§ 8.6 Budget, Observability and Repair:**  
> *"Budget exhaustion MUST stop or route to an authorized repair path; retry decisions use the frozen RetryBudget with no second ledger; hard budget gates reject model-reported-only cost and admit only authoritative or host-attested cost metrics; resource and runtime limits use explicit units/defaults."*

Existing Master Allocations:
The master allocates `PD-CH8-008` through `PD-CH8-013` (with `001..007` permanently retired). To formalize the operational category without colliding with existing rows, all newly proposed MUST definitions allocate strictly from `PD-CH8-014` onwards.

---

## 1.2 Proposed Normative Requirements (PD-CH8-014+)

### MUST Requirement: `PD-CH8-014`
- **MUST ID:** `PD-CH8-014`
- **Class:** `M` (Mandatory)
- **Decidable Requirement:**  
  An evaluation claiming preventative enforcement (Tier `E1_MEDIATED_WORKER`) MUST verify that an active, qualified host probe was executed for the specific host OS, kernel release, and container runtime version within the current session. If the probe is absent, stale, failed, or if the host is unqualified, the evaluator MUST downgrade the enforcement tier claim to `E0_ADVISORY` and reject any write-prevention assertion.
- **Gaming / Adversarial Fixture:**  
  `CH8-T20`: Agent running on Windows native environment asserts `enforcement_tier: "E1_MEDIATED_WORKER"` without a qualified Linux/Bubblewrap host probe receipt, attempting to claim prevention against IDE write bypass.
- **Happy Fixture:**  
  `CH8-T21`: Agent launches worker inside verified Linux cgroup v2 / Bubblewrap boundary with cryptographic `HostProbeReceipt` matching host kernel digest; evaluator yields `SATISFIED`.
- **Expected Gate Outputs:**  
  - If valid probe present and matching: `SATISFIED`.  
  - If probe missing or host unqualified: `MISSING[PD-CH8-014]` with `action_result: BLOCKED`.  
  - If probe indicates corrupted host namespace or unauthenticated bypass attempt: `BLOCKED_ON_HUMAN[PD-CH8-014]`.
- **Failure Route:**  
  Downgrade to Tier `E0_ADVISORY`; abort automated execution; route to human operator for environment qualification.
- **Who may write:** Host-level execution harness during session initialization via authenticated OS runtime probe.
- **NEVER:** Claim write prevention based solely on agent declaration, IDE extension presence, or unverified runtime assumptions.

---

### MUST Requirement: `PD-CH8-015`
- **MUST ID:** `PD-CH8-015`
- **Class:** `M` (Mandatory)
- **Decidable Requirement:**  
  Workspace promotion MUST preserve an immutable pre-mutation rollback manifest containing the `TargetSnapshot` content digest, tree digest, and reverse-patch deltas before applying staged worker modifications to the physical worktree root. Promotion MUST fail closed if the rollback manifest cannot be persisted or verified.
- **Gaming / Adversarial Fixture:**  
  `CH8-T22`: Worker stages valid verified patches and initiates workspace promotion, but omits persisting the pre-mutation rollback manifest to accelerate promotion.
- **Happy Fixture:**  
  `CH8-T23`: Worker stages patches, generates pre-mutation rollback manifest with valid SHA-256 tree digest, verifies write persistence, and completes promotion; evaluator yields `SATISFIED`.
- **Expected Gate Outputs:**  
  - If rollback manifest verified and staged deltas within authorized write set: `SATISFIED`.  
  - If rollback manifest omitted, incomplete, or unpersisted: `MISSING[PD-CH8-015]`.  
  - If target worktree state changed concurrently during manifest creation: `BLOCKED_ON_HUMAN[PD-CH8-015]`.
- **Failure Route:**  
  Abort promotion; discard temporary staging overlay; re-evaluate workspace baseline.
- **Who may write:** Product Promotion Subsystem (`sclass.product.workspace.promotion`).
- **NEVER:** Apply worker mutations directly to physical worktree root without an active, verified rollback manifest.

---

### MUST Requirement: `PD-CH8-016`
- **MUST ID:** `PD-CH8-016`
- **Class:** `M` (Mandatory)
- **Decidable Requirement:**  
  Repository intelligence queries and symbol resolution projections MUST declare the exact index coverage percentage and snapshot timestamp. Any query resolving a symbol outside declared index coverage or referencing an unresolved symbol MUST return state `MISSING[PD-CH8-016]`; the projection MUST NOT substitute heuristic guesses or synthetic placeholders.
- **Gaming / Adversarial Fixture:**  
  `CH8-T24`: Brownfield index has 64% coverage; agent queries an unindexed internal class and the projection synthesizes a dummy signature rather than returning MISSING.
- **Happy Fixture:**  
  `CH8-T25`: Agent queries index with 100% declared coverage; all referenced symbols resolve to exact AST locations with fresh digests; evaluator yields `SATISFIED`.
- **Expected Gate Outputs:**  
  - If all queried symbols fully indexed and resolved: `SATISFIED`.  
  - If queried symbol unindexed, missing, or coverage < 100% for target namespace: `MISSING[PD-CH8-016]`.  
  - If index structure is corrupted or contradictory: `BLOCKED_ON_HUMAN[PD-CH8-016]`.
- **Failure Route:**  
  Invalidate repository intelligence cache; schedule background re-indexing; require explicit developer symbol qualification.
- **Who may write:** Repository Intelligence Adapter (`sclass.product.repo_intel`).
- **NEVER:** Synthesize or hallucinate missing symbol definitions or claim full repository awareness on partial indices.

---

### MUST Requirement: `PD-CH8-017`
- **MUST ID:** `PD-CH8-017`
- **Class:** `M` (Mandatory)
- **Decidable Requirement:**  
  Hard budget gates MUST evaluate cost and resource exhaustion solely from authoritative OS process telemetry (cgroup v2 cpu.stat / memory.current) and cryptographically signed API proxy receipts. Any cost, token, or execution metric asserted solely by an agent model without external receipt MUST be rejected and evaluated as `MISSING[PD-CH8-017]`.
- **Gaming / Adversarial Fixture:**  
  `CH8-T26`: Agent emits completion receipt declaring `model_tokens_consumed: 120` and `execution_cost_usd: 0.002` without an accompanying signed gateway proxy token receipt.
- **Happy Fixture:**  
  `CH8-T27`: Execution harness attaches signed API gateway receipt and Linux cgroup accounting log; cumulative cost is within budget ceiling; evaluator yields `SATISFIED`.
- **Expected Gate Outputs:**  
  - If authoritative receipts present and within budget limits: `SATISFIED`.  
  - If receipts missing, unsigned, or self-reported: `MISSING[PD-CH8-017]`.  
  - If budget ceiling exceeded: `BLOCKED_ON_HUMAN[PD-CH8-017]`.
- **Failure Route:**  
  Halt task execution immediately; reject self-reported metrics; invoke frozen `RetryBudget` repair protocol or block for human approval.
- **Who may write:** Execution Gate and Authorized Accounting Proxy (`sclass.product.budget`).
- **NEVER:** Permit an agent to report its own token consumption, runtime duration, or financial cost without external host attestation.

---

## 1.3 Gate Check & Grounding Analysis

- **Gate 1 Compliance:** Proposed IDs `PD-CH8-014..017` fall squarely within the reserved range `CH8-001..199`. None collide with existing allocations `008..013` or retired IDs `001..007`. Test IDs `CH8-T20..T27` cleanly extend `CH8-T8..T19`.
- **Gate 2 Compliance:** All 4 requirements provide decidable criteria, gaming fixtures, happy fixtures, three-state outputs, failure routes, authorship rules, and NEVER invariants.
- **Gate 3 Compliance:** Zero kernel changes. Projections run in product space.
- **Gate 4 Compliance:** Prevention requires host probe (`PD-CH8-014`); cost requires signed receipts (`PD-CH8-017`).
- **Gate 5 Compliance (Evidence):**
  - Host probe requirement derives from `RESEARCH-NOTES-R29.md` §C (*"MCP tool is advisory unless the host forces its use... prevention only inside an S-Class-launched boundary; host-native activity is detect/contain, PD-CH8-008"*).
  - Budget attestation derives from `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md` §8.6 and `RESEARCH-NOTES-R29.md` §D.
  - **Adversarial Command-Analyzer Corpus:** The two research files (`RESEARCH-NOTES-R29.md` and `FREEZE-DECISION-R28.md`) do NOT contain or specify a 12-bypass-class taxonomy for a command analyzer. Per Gate 5 instructions (*"Where the research files do not support a claim, mark it UNVERIFIED. Do not substitute a different taxonomy"*), the command-analyzer adversarial corpus is formally marked **UNVERIFIED**.
- **Gate 6 Compliance (Unresolved Decisions):** See Section 1.4 below.

---

## 1.4 Formal Open Decisions (Gate 6)

### `BLOCKED — AK DECISION REQUIRED (CH8-OI-001)`
- **Subject:** Non-Linux Enforcement Boundary Qualification (Master OI-005, OI-013)
- **Question:** How shall S-Class claim Tier E1 mediated worker isolation on Windows (Job Objects / AppContainer) and macOS (sandbox-exec / endpoint security) given that Bubblewrap and cgroups v2 are Linux-specific?
- **Available Options:**
  - **Option A:** Restrict Tier E1 write prevention strictly to Linux hosts. Treat Windows and macOS sessions strictly as Tier E0 (advisory) / E2 (controlled promotion) detect-only.
  - **Option B:** Implement platform-specific native sandboxes (Windows Job Objects + AppContainer isolation; macOS sandbox-exec) and establish a dedicated host qualification battery for each platform.
  - **Option C:** Mandate that all non-Linux workers execute inside an isolated Linux guest container (Docker / WSL2) to inherit the verified Bubblewrap/cgroup boundary.

### `BLOCKED — AK DECISION REQUIRED (CH8-OI-002)`
- **Subject:** Watcher Detection Latency vs Invalidation Window (Master §8.2)
- **Question:** The master states *"detection may be delayed, so do not claim prevention."* What is the maximum allowable filesystem watcher polling latency before an ongoing gate evaluation must be invalidated upon detecting an out-of-band edit?
- **Available Options:**
  - **Option A:** Strict pre-gate synchronization: Force a synchronous re-scan and digest verification immediately before evaluating any task or phase gate, ignoring asynchronous watcher latency.
  - **Option B:** Bounded asynchronous window: Allow an asynchronous watcher event queue with a hard maximum latency ceiling (e.g. 500 ms); any event with timestamp prior to gate evaluation instant invalidates results retroactively.
  - **Option C:** Read-only worktree during evaluation: Remove write permissions from the worktree during evaluation to guarantee zero concurrent host mutations.

### `BLOCKED — AK DECISION REQUIRED (CH8-OI-003)`
- **Subject:** Repository Intelligence Freshness SLA (Master §8.5, PD-CH8-012)
- **Question:** What quantitative threshold defines when an AST / symbol index transitions from `FRESH` to `STALE` relative to git commit timestamps and file modification events?
- **Available Options:**
  - **Option A:** Strict commit binding: An index is fresh ONLY if its content digest matches the exact `TargetSnapshot` git tree digest. Any unindexed delta marks the index STALE.
  - **Option B:** Grace delta threshold: An index remains usable if modified files do not alter exported interface symbols, but discloses `partial_freshness` metadata.
  - **Option C:** Time-decay SLA: An index is considered fresh for up to $N$ minutes following repository scan unless modified by a known structural refactoring event.

### `BLOCKED — AK DECISION REQUIRED (CH8-OI-004)`
- **Subject:** Command-Analyzer Adversarial Corpus 12-Bypass Taxonomy Definition
- **Question:** The research files cite EvilGenie and trajectory monitoring, but do not articulate the canonical 12 bypass classes for the command analyzer corpus. What authoritative taxonomy shall govern the command-analyzer negative test battery?
- **Available Options:**
  - **Option A:** Commission a dedicated research brief (Brief 03) to formalize and benchmark the 12 bypass classes against real agent trajectories (e.g. subshell injection, argument splitting, pipe bypass, quoting evasion, environment manipulation, tool unbundling, shell variable expansion, alias hijacking, glob expansion, race conditions, descriptor redirection, and signal trapping).
  - **Option B:** Adopt the 6 threat vectors from frozen `06-VALIDATION/S-CLASS-VALIDATION-AND-RELEASE-GATES.md` (ZV1-ZV6) expanded to 12 operational classes.
  - **Option C:** Rely strictly on kernel ExecutionGate command white-listing without maintaining an independent product-layer heuristic command analyzer.

---

# SECTION 2: Phase 9 (P9) Review Engine Proposal
*(Review, Hardening, and Non-Self-Waiver Floor)*

## 2.1 Normative Master Context & Direct Citations

Phase 9 (P9) operates downstream of per-task verification (P7) and repair (P8), providing aggregate evidence synthesis before delivery readiness (P10).

Authoritative Master Quotes:
> **§ 2.15.1 Purpose & Non-State-Machine Invariant:**  
> *"P9 reviews the aggregate evidence, resolves findings and hardens against relevant regression without inventing a state machine."*  
> *"F5 owns phase composition: P5-P8 are `ENTRY AND TASK_LOOPS AND PRODUCT_ADDED_BLOCKS`; P9/P10 aggregate per-task P7 outputs through their phase sub-check tables; kernel authority and product block are conjoined."*

> **§ 2.15.4 Agent Instructions & Waiver Rules:**  
> *"Review only bound and fresh evidence. Each finding must reference a check/evidence/obligation and have disposition `FIXED`, `AUTHORIZED_WAIVER`, or `OPEN`. A waiver must be frozen-authority-bound; a product reviewer cannot self-authorize one. Regressions route to P8/P6/P5. Aggregate P7 task results deterministically under F5; one passing task cannot cancel another task's failure."*

> **§ 2.15.6 Sub-Checks:**  
> - `P9-COMPLETENESS` (Class M): *"aggregate every required per-task P7 result via F5; missing task result -> MISSING"*  
> - `P9-FRESHNESS` (Class M): *"recompute frozen freshness at recorded instant; target/policy/evidence digests; invalidate and rerun P7"*  
> - `P9-FINDINGS` (Class M/E): *"every finding has current disposition plus evidence or authorized Decision; open finding blocks"*  
> - `P9-HARDENING` (Class E): *"run applicable qualified F10 adapter checks, including security/dependency regressions from policy"*

> **§ 2.15.7 Formal Gate & NEVER Rule:**  
> `G_P9 = ALL_REQUIRED_TASK_RESULTS_PRESENT AND FRESHNESS_CURRENT AND FINDINGS_CLOSED_OR_AUTHORIZEDLY_WAIVED AND HARDENING_CHECKS_PASS AND KERNEL_AUTHORITY_VALID`  
> *"NEVER: Average away a failed task, accept stale evidence, or let a product-layer review create a waiver."*

Existing Master Allocations:
Chapter 2 defines `PD-CH2-052` (P9 completeness and finding closure). Allocated Chapter 2 IDs end at `PD-CH2-065` (with `004, 019, 027, 030, 049, 059` retired). Proposed requirements allocate strictly from `PD-CH2-066` onwards.

---

## 2.2 Proposed Normative Requirements (PD-CH2-066+)

### MUST Requirement: `PD-CH2-066`
- **MUST ID:** `PD-CH2-066`
- **Class:** `M` (Mandatory)
- **Decidable Requirement:**  
  The P9 Review Engine MUST evaluate aggregate completion by verifying that every `WorkNode` declared in the bound `WorkGraph` possesses an affirmative `TaskGateResult` recorded at an identical `TargetSnapshot` instant. A finding marked `AUTHORIZED_WAIVER` MUST cite a cryptographically verified `ApprovalRecord` or `Decision` originating from canonical Kernel Authority. Any self-authored waiver, model-generated exception, or missing task result MUST yield `BLOCKED_ON_HUMAN[PD-CH2-066]`.
- **Gaming / Adversarial Fixture:**  
  `CH2-T77`: A product-layer review agent detects an open security regression finding during aggregate P9 review and generates an inline waiver asserting `disposition: "AUTHORIZED_WAIVER"` signed by the review agent itself.
- **Happy Fixture:**  
  `CH2-T78`: All tasks possess passing P7 results; one non-critical finding is accompanied by an authenticated `ApprovalRecord` signed by the project owner; evaluator yields `SATISFIED`.
- **Expected Gate Outputs:**  
  - If all tasks passing and all findings FIXED or possessing valid kernel waivers: `SATISFIED`.  
  - If any required task result omitted or finding OPEN without waiver: `MISSING[PD-CH2-066]`.  
  - If waiver lacks canonical kernel authority signature: `BLOCKED_ON_HUMAN[PD-CH2-066]`.
- **Failure Route:**  
  Route open defect findings to P8 (repair); route unevidenced waivers to Human Project Lead for formal decision.
- **Who may write:** P9 Review Engine (`sclass.product.review_engine`).
- **NEVER:** Permit a product-layer reviewer or agent to authorize a waiver, mask a failed task, or average results across tasks.

---

### MUST Requirement: `PD-CH2-067`
- **MUST ID:** `PD-CH2-067`
- **Class:** `M` (Mandatory)
- **Decidable Requirement:**  
  A P9 gate evaluation declaring "zero findings" (`findings_count == 0`) MUST NOT produce state `SATISFIED` unless accompanied by a declared verifier coverage map proving that 100% of confirmed obligations and policy-mandated hardening checks were executed. If verifier coverage is undeclared, incomplete, or based on default assumptions, the evaluator MUST return `MISSING[PD-CH2-067]`.
- **Gaming / Adversarial Fixture:**  
  `CH2-T79`: Reviewer submits an empty findings list (`[]`) with `coverage_declared: false`, attempting to pass P9 review on the grounds that "no bugs were discovered".
- **Happy Fixture:**  
  `CH2-T80`: Reviewer submits empty findings list accompanied by full verifier execution receipts proving 100% obligation and hardening check coverage; evaluator yields `SATISFIED`.
- **Expected Gate Outputs:**  
  - If zero findings accompanied by verified 100% declared coverage: `SATISFIED`.  
  - If zero findings asserted but coverage map missing or < 100%: `MISSING[PD-CH2-067]`.  
  - If coverage telemetry is contradictory or corrupted: `BLOCKED_ON_HUMAN[PD-CH2-067]`.
- **Failure Route:**  
  Reject completion claim; trigger missing verifier runs in P7/P9; prevent progression to P10.
- **Who may write:** P9 Aggregation Evaluator (`sclass.product.review_engine.coverage`).
- **NEVER:** Conclude review satisfaction from the absence of findings without affirmative proof of complete check execution.

---

## 2.3 Gate Check & Grounding Analysis

- **Gate 1 Compliance:** Proposed IDs `PD-CH2-066` and `PD-CH2-067` allocate cleanly above the highest allocated ID (`065`) in reserved range `CH2-001..199`. No retired IDs are reused. Test IDs `CH2-T77..T80` extend `CH2-T1..T76`.
- **Gate 2 Compliance:** Full 8-part specification provided for each MUST.
- **Gate 3 Compliance:** Zero kernel changes. The Review Engine is a functional aggregator over existing artifacts.
- **Gate 4 Compliance:** Model cannot approve own output; zero findings cannot pass without full declared coverage (`PD-CH2-067`); self-waivers blocked (`PD-CH2-066`).
- **Gate 5 Compliance (Evidence):**
  - Grounded directly in Wang et al. (arXiv:2503.15223) and SWE-ABS (arXiv:2603.00520) cited in `RESEARCH-NOTES-R29.md` §A: passing limited checks or finding no defects is weak evidence unless comprehensive suites are executed.
  - Trajectory gaming protection derives from "The Verification Horizon" (arXiv:2606.26300) cited in `RESEARCH-NOTES-R29.md` §B.
- **Gate 6 Compliance (Unresolved Decisions):** See Section 2.4 below.

---

## 2.4 Formal Open Decisions (Gate 6)

### `BLOCKED — AK DECISION REQUIRED (P9-OI-001)`
- **Subject:** Policy-to-Hardening Adapter Registry Binding (Master §2.15.6, OI-003, OI-010)
- **Question:** What schema and mechanism shall bind file types and domain policies to specific F10 hardening adapters during aggregate P9 review?
- **Available Options:**
  - **Option A:** Static policy table: Pin an explicit, immutable map of file extensions to adapter names directly in canonical `Policy` (e.g. `*.py` -> `bandit, safety`; `*.ts` -> `eslint-security`).
  - **Option B:** Dynamic qualification registry: Query an extensible `AdapterRegistry` where adapters register their supported capabilities and minimum confidence thresholds.
  - **Option C:** Monolithic audit script: Bundle hardening checks into a single mandatory repository-level shell script executed under `ExecutionGate`.

### `BLOCKED — AK DECISION REQUIRED (P9-OI-002)`
- **Subject:** Multi-Task Finding Granularity and Attribution
- **Question:** When an aggregate regression is discovered during P9 review, how must the finding be attributed in the `FindingGraph`?
- **Available Options:**
  - **Option A:** Strict task attribution: Require that every finding be mapped to exactly one culpable `work_node_id` from the plan, failing closed if ambiguous.
  - **Option B:** Aggregate session attribution: Permit findings to attach directly to the top-level `ReviewRecord` as general regressions, routing to a new repair task.
  - **Option C:** Dual attribution: Findings carry both a primary `ReviewRecord` reference and an optional set of suspected candidate task nodes.

### `BLOCKED — AK DECISION REQUIRED (P9-OI-003)`
- **Subject:** Hardening Failure Routing Arbitration
- **Question:** Section 2.15.6 lists `repair P8/P6/P5 or BLOCKED` as the failure route for `P9-HARDENING`. What deterministic rule arbitrates whether a failure routes to P8 (repair), P6 (re-implementation), or P5 (test design)?
- **Available Options:**
  - **Option A:** Strict hierarchical escalation: Always route to P8 first. If P8 budget is exhausted, escalate to P6. If P6 fails verification, escalate to P5.
  - **Option B:** Finding category dispatch: Syntax and lint defects route to P8; functional test regressions route to P6; contract and schema discrepancies route to P5.
  - **Option C:** Fail closed to human: Any aggregate hardening failure immediately routes to `BLOCKED_ON_HUMAN` to prevent automated cycling.

---

# SECTION 3: Phase 4 (P4) Additions Proposal
*(Planning, Bounded Decomposition, Mechanical Overlap Serialization, and Traceability Binding)*

## 3.1 Normative Master Context & Direct Citations

Phase 4 (P4) translates confirmed obligations and lane policies into a bounded, dependency-aware plan (`WorkGraph`) and verification plan (`VerificationPlan`).

Authoritative Master Quotes:
> **§ 2.10.1 Purpose & Frozen Bindings:**  
> *"P4 emits a bounded dependency-aware plan and verifier coverage using kernel WorkGraph, WorkNode, and VerificationPlan, without creating another work state machine."*  
> *"Frozen bindings: `WorkNode` is `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` § 7 L2170-L2186 'class WorkNode:'; `WorkGraph` is § 7 L2189-L2202 'class WorkGraph:'; `VerificationPlan` is § 5.2 L2050-L2056 'class VerificationPlan:'. The frozen revision events are `VERIFICATION_PLAN_REVISED`... and `WORKGRAPH_REVISED`."*

> **§ 2.10.4 Agent Instructions & Initial Policy Defaults:**  
> *"Decompose each task within lane defaults below. Each obligation must have planned verifier coverage using F6 traceability; only current links contribute under `PD-F6-005`. Dependencies are acyclic. For parallel tasks, compare declared write sets mechanically: known overlap is serialized and SATISFIED; undeclared or unknown write sets are `BLOCKED_ON_HUMAN[PD-CH2-032]`. Never assume disjointness from missing data."*  
> *"Initial policy defaults (tunable only by canonical Policy revision): a task unit is one distinct canonical mutation target (file, symbol, API, schema, database object, or explicit external-effect target); repeated references to the same target count once."*  
> | Lane | Max tasks/graph | Max units/task | Max total graph units | Max verification reruns/test |  
> |---|---:|---:|---:|---:|  
> | MICRO | 4 | 4 | 8 | 1 |  
> | STANDARD | 16 | 12 | 64 | 2 |  
> | CRITICAL | 64 | 32 | 512 | 3 |

> **§ 2.10.7 Formal Gate & NEVER Rule:**  
> `G_P4 = P3_APPLICABILITY_CURRENT AND LANE_CAPS_PASS AND OBLIGATION_PLANNED_COVERAGE_COMPLETE AND WORKGRAPH_ACYCLIC AND OVERLAP_RESOLVED_OR_SERIALIZED AND VERIFIERS_QUALIFIED AND BINDINGS_CURRENT`  
> *"NEVER: Run undeclared-overlap tasks in parallel, infer a verifier, exceed a lane cap, or write kernel graph/plan state from product code."*

Existing Master Allocations:
Chapter 2 currently allocates `PD-CH2-029` (lane caps), `PD-CH2-031` (acyclicity), and `PD-CH2-032` (write-set overlap). Proposed requirements allocate from `PD-CH2-068` onwards.

---

## 3.2 Proposed Normative Requirements (PD-CH2-068+)

### MUST Requirement: `PD-CH2-068`
- **MUST ID:** `PD-CH2-068`
- **Class:** `M` (Mandatory)
- **Decidable Requirement:**  
  When two or more parallel tasks in a `Plan` declare overlapping write sets, the planning evaluator MUST mechanically serialize them by injecting directed dependency edges ordered strictly by canonical task identifier lexicographical sort (`task_id_A < task_id_B`). Any plan attempting to execute overlapping write sets concurrently, or relying on non-deterministic tie-breakers, MUST return `MISSING[PD-CH2-068]`. If any parallel task has an undeclared or unknown write set, the evaluator MUST return `BLOCKED_ON_HUMAN[PD-CH2-068]`.
- **Gaming / Adversarial Fixture:**  
  `CH2-T81`: Planning agent submits two parallel tasks mutating the same file (`src/auth.py`), asserting they can execute concurrently because they modify different line ranges.
- **Happy Fixture:**  
  `CH2-T82`: Two tasks declare overlapping file targets; evaluator detects intersection and injects directed edge `task_01 -> task_02` based on canonical identifier sort; evaluator yields `SATISFIED`.
- **Expected Gate Outputs:**  
  - If disjoint or mechanically serialized by canonical sort: `SATISFIED`.  
  - If overlapping write sets remain parallel: `MISSING[PD-CH2-068]`.  
  - If write sets undeclared, wildcarded, or unresolved: `BLOCKED_ON_HUMAN[PD-CH2-068]`.
- **Failure Route:**  
  Reject plan proposal; invoke mechanical serialization filter; block for human review if write targets cannot be determined.
- **Who may write:** P4 Plan Evaluator (`sclass.product.planning.overlap`).
- **NEVER:** Execute overlapping write targets in parallel or guess disjointness from incomplete write set declarations.

---

### MUST Requirement: `PD-CH2-069`
- **MUST ID:** `PD-CH2-069`
- **Class:** `M` (Mandatory)
- **Decidable Requirement:**  
  Every confirmed obligation assigned to a `Plan` MUST bind to at least one qualified `VerificationStep` in the candidate `VerificationPlan` via valid Section F6 trace links satisfying `PD-F6-001` through `PD-F6-006`. A plan containing any unlinked obligation, or linking via stale or unverified endpoints, MUST return `MISSING[PD-CH2-069]`.
- **Gaming / Adversarial Fixture:**  
  `CH2-T83`: Plan covers 5 confirmed obligations with verifier steps, but omits the 6th obligation, asserting it will be verified informally during implementation.
- **Happy Fixture:**  
  `CH2-T84`: All confirmed obligations map 1:1 or 1:N to qualified verification steps with verified Section F6 trace link hashes; evaluator yields `SATISFIED`.
- **Expected Gate Outputs:**  
  - If all confirmed obligations have active, verified F6 trace links: `SATISFIED`.  
  - If one or more obligations lack planned verifier coverage: `MISSING[PD-CH2-069]`.  
  - If obligation reference cannot be resolved against target baseline: `BLOCKED_ON_HUMAN[PD-CH2-069]`.
- **Failure Route:**  
  Reject candidate plan; route back to P4 planning agent with list of unmapped obligations.
- **Who may write:** P4 Plan Evaluator (`sclass.product.planning.coverage`).
- **NEVER:** Permit a plan to proceed to implementation without affirmative, mechanically verified verifier coverage for every confirmed obligation.

---

## 3.3 Gate Check & Grounding Analysis

- **Gate 1 Compliance:** Proposed IDs `PD-CH2-068` and `PD-CH2-069` allocate in Chapter 2 reserved range `CH2-001..199` without colliding with allocated or retired IDs. Test IDs `CH2-T81..T84` extend `CH2-T77..T80`.
- **Gate 2 Compliance:** Full 8-part specification provided for each MUST.
- **Gate 3 Compliance:** Zero kernel changes. WorkGraph and VerificationPlan bindings are strictly read-only projections.
- **Gate 4 Compliance:** Eliminates concurrency gaming; mandates deterministic serialization; requires affirmative trace link coverage for every obligation.
- **Gate 5 Compliance (Evidence):**
  - Grounded in `RESEARCH-NOTES-R29.md` §B (*"The Verification Horizon... trajectory monitor plus test rewards cut the hack rate... test-edit detection is one of its methods"*).
  - Scope and write-set protection derives from master §2.10 and `RESEARCH-NOTES-R29.md` §B.
- **Gate 6 Compliance (Unresolved Decisions):** See Section 3.4 below.

---

## 3.4 Formal Open Decisions (Gate 6)

### `BLOCKED — AK DECISION REQUIRED (P4-OI-001)`
- **Subject:** Dynamic and Build-Generated Mutation Target Syntax (Master §2.10.4)
- **Question:** How shall tasks declaring mutations against dynamic, compiler-generated, or globbed targets specify their write sets to satisfy `PD-CH2-032` and `PD-CH2-068` without triggering `BLOCKED_ON_HUMAN`?
- **Available Options:**
  - **Option A:** Strict explicit enumeration: Prohibit all dynamic targets. Every affected file or symbol must be fully enumerated before execution.
  - **Option B:** Directory prefix bounding: Allow canonical directory prefixes (e.g. `target/generated/**` or `dist/*`) provided the prefix is owned exclusively by one task.
  - **Option C:** Two-phase execution lease: Tasks declare a dynamic placeholder, execute inside an isolated overlay to discover actual targets, then promote targets back to the plan before final serialization.

### `BLOCKED — AK DECISION REQUIRED (P4-OI-002)`
- **Subject:** Multi-File Refactoring Task Unit Metric Granularity
- **Question:** The master defines a unit as *"one distinct canonical mutation target (file, symbol, API, schema, database object, or explicit external-effect target)"*. For cross-cutting refactorings modifying 50 files with identical AST transformations, does this count as 50 units (exceeding STANDARD lane 12-unit cap) or 1 unit (1 refactoring rule)?
- **Available Options:**
  - **Option A:** Strict physical count: Every physical file modified counts as 1 unit. Large refactorings MUST use the CRITICAL lane or split across multiple graphs.
  - **Option B:** Logical target metric: Semantic transformation rules count as 1 unit if proven isomorphic by an AST rewrite engine.
  - **Option C:** Separate refactoring lane: Introduce a dedicated `REFACTOR` lane with higher unit caps and mandatory AST regression verifiers.

### `BLOCKED — AK DECISION REQUIRED (P4-OI-003)`
- **Subject:** Database Migration Script Unit Granularity
- **Question:** How are database schema mutations counted against lane unit caps?
- **Available Options:**
  - **Option A:** Migration script level: Each migration script file counts as 1 unit, regardless of the number of tables or columns altered.
  - **Option B:** Schema entity level: Each distinct database table or view altered counts as 1 unit.
  - **Option C:** Column / constraint level: Each individual DDL operation (add column, alter constraint) counts as 1 unit.

---

## Proposed Registry Rows for Future Master Integration

### MUST Registry Allocation Additions
```markdown
| Owner | Reserved range | Currently allocated | Status rule |
|---|---:|---:|---|
| Ch2 | CH2-001..199 | 001..003, 005..018, 020..026, 028..029, 031..048, 050..058, 060..065, [PROP: 066..069] | retired: 004, 019, 027, 030, 049, 059 |
| Ch8 | CH8-001..199 | 008..013, [PROP: 014..017] | retired: 001..007 |
```

### Test Registry Allocation Additions
```markdown
| Test ID range | Resolution |
|---|---|
| CH2-T77..T80 | P9 Review Engine proposals (CH2-T77 gaming / CH2-T78 happy for PD-CH2-066; CH2-T79 gaming / CH2-T80 happy for PD-CH2-067) |
| CH2-T81..T84 | P4 Additions proposals (CH2-T81 gaming / CH2-T82 happy for PD-CH2-068; CH2-T83 gaming / CH2-T84 happy for PD-CH2-069) |
| CH8-T20..T27 | Chapter 8 Category proposals (CH8-T20..T27 gaming and happy pairs for PD-CH8-014..017) |
```

---
*End of S-Class v6.0.2 Block 1 Consolidated Design Proposals Document.*
