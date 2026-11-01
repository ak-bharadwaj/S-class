# Design Draft 3: P4 Additions (Planning and Decomposition)

**Document Reference:** `delivery-1-design-drafts/3_p4_additions_draft.md`  
**Base Commit:** `3ed415e67e15e6aedc7d456445c3c193146ae606`  
**Master Source:** `FREEZE-CANDIDATE-v6.0.2/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md` (§2.10 P4, L2140 bytes)  
**Status:** PROPOSAL / DESIGN DRAFT (Not an accepted normative change; for GPT review and onward gating by CL)

---

## 1. Executive Summary & Context

Phase 4 (P4) governs Planning and Decomposition. It translates confirmed requirements, architecture specifications, and lane policies into a bounded, dependency-aware task graph (`WorkGraph`) and verification plan (`VerificationPlan`). P4 acts as a strict structural filter, ensuring tasks do not exceed policy-prescribed complexity limits, contain cycles, hide concurrency hazards through undeclared write sets, or leave requirements without verifier coverage.

This proposal specifies the design of the S-Class P4 Additions adhering strictly to Section 2.10 of the R30 Master Product Design.

---

## 2. Direct Master Quotes & Normative Anchors

### 2.1 Trace Statement & Purpose (§2.10.1, §2.10.2)
> **Master Quote:**  
> *"P4 emits a bounded dependency-aware plan and verifier coverage using kernel WorkGraph, WorkNode, and VerificationPlan, without creating another work state machine."*
>
> *"Frozen bindings: `WorkNode` is `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §7 L2170-L2186 'class WorkNode:'; `WorkGraph` is §7 L2189-L2202 'class WorkGraph:'; `VerificationPlan` is §5.2 L2050-L2056 'class VerificationPlan:'. The frozen revision events are `VERIFICATION_PLAN_REVISED` at §12.1 L3528-L3528 'VERIFICATION_PLAN_REVISED = \"VerificationPlanRevised\"' and `WORKGRAPH_REVISED` at §12.1 L3529-L3529 'WORKGRAPH_REVISED = \"WorkGraphRevised\"'."*

### 2.2 Entry Predicate & Inputs (§2.10.1, §2.10.3)
> **Master Quote:**  
> *"P3's product-layer applicability projection is explicit and permits planning; it is not a frozen kernel applicability result. Confirmed requirements, objective revision, canonical Policy, target snapshot, F4-computed lane, and current ArchitectureRecord/DomainModel references are bound."*
>
> *"Inputs: Confirmed obligations, current objective/target, kernel WorkGraph/WorkNode and VerificationPlan, policy-derived lane, profile ChangeSurface, available qualified verifiers, canonical write sets, and current P3 outputs."*

### 2.3 Agent Instructions & Initial Policy Defaults (§2.10.4)
> **Master Quote:**  
> *"Decompose each task within lane defaults below. Each obligation must have planned verifier coverage using F6 traceability; only current links contribute under `PD-F6-005`. Dependencies are acyclic. For parallel tasks, compare declared write sets mechanically: known overlap is serialized and SATISFIED; undeclared or unknown write sets are `BLOCKED_ON_HUMAN[PD-CH2-032]`. Never assume disjointness from missing data."*
>
> *"Initial policy defaults (tunable only by canonical Policy revision): a task unit is one distinct canonical mutation target (file, symbol, API, schema, database object, or explicit external-effect target); repeated references to the same target count once. These are stopping limits, not measured performance claims."*
>
> | Lane | Max tasks/graph | Max units/task | Max total graph units | Max verification reruns/test |
> |---|---:|---:|---:|---:|
> | MICRO | 4 | 4 | 8 | 1 |
> | STANDARD | 16 | 12 | 64 | 2 |
> | CRITICAL | 64 | 32 | 512 | 3 |
>
> *"Rerun caps count verification reruns after the initial invocation. F10's execution count (default 4 per target and input digest) therefore covers the initial invocation plus the CRITICAL-lane maximum of 3 reruns; a lane cap is always the stricter bound. Each invocation is bounded by the F10 hard stop (120 s), so worst-case wall time per test is (reruns + 1) × 120 s: MICRO 240 s, STANDARD 360 s, CRITICAL 480 s."*

### 2.4 Artifacts + Schemas (§2.10.5)
> **Master Quote:**  
> | Payload | Required fields | Binding / authority |
> |---|---|---|
> | `Plan` | `plan_id`, `objective_revision`, `lane`, `task_nodes`, `dependency_edges`, `obligation_coverage`, `verifier_assignments`, `overlap_map`, `scope_digest`, `content_digest` | product proposal; evaluator recomputes caps, acyclicity and coverage |
> | `WorkGraphBinding` | `workgraph_ref`, `workgraph_revision`, `node_refs`, `dependency_refs`, `parallel_group`, `overlap_map_ref` | reference to kernel WorkGraph/WorkNode; never writes them |
> | `VerificationPlanBinding` | `verification_plan_ref`, `step_refs`, `obligation_refs`, `verifier_ids`, `freshness_policy_ref` | reference to frozen VerificationPlan and current contracts |

### 2.5 Sub-Check Table (§2.10.6)
> **Master Quote:**  
> | check | class M/E/J | decision procedure | inputs | failure route | cost bound |
> |---|---|---|---|---|---|
> | `P4-ENTRY-APPLICABILITY` | M | require current P3 product-layer applicability projection | P3 applicability projection, objective/target/policy bindings | return to P3 or MISSING when absent/stale | bounded binding checks |
> | `P4-SCOPE` | M | compute task count, units/task and total units against lane policy defaults | lane, task graph, canonical target IDs | split/replan P4; `MISSING[PD-CH2-029]` | O(tasks + targets), stopped at lane caps |
> | `P4-COVERAGE` | M | require each applicable obligation mapped to a planned verifier via F6 trace links | obligation IDs, verifier links, endpoint freshness | P4 repair; cites `PD-F6-005` for stale links | O(obligations + links) |
> | `P4-ACYCLIC` | M | cycle check of dependency edges | WorkGraph projection | repair graph; no execution | O(V+E), graph cap applies |
> | `P4-OVERLAP` | M/E/J | known write-set intersection forces serialization; unknown/missing write set blocks for human | every parallel task's declared write set | known overlap: serialize/SATISFIED; unknown: `BLOCKED_ON_HUMAN[PD-CH2-032]` | O(declared targets), lane-bounded |
> | `P4-VERIFIER-QUAL` | E | verifier resolves to qualified F10 adapter or authorized kernel verifier | verifier registry | P5 planning repair; no assumed coverage | O(verifiers), registry-bounded |

### 2.6 Formal Gate & Normative Closure (§2.10.7, §2.10.12)
> **Master Quote:**  
> `G_P4 = P3_APPLICABILITY_CURRENT AND LANE_CAPS_PASS AND OBLIGATION_PLANNED_COVERAGE_COMPLETE AND WORKGRAPH_ACYCLIC AND OVERLAP_RESOLVED_OR_SERIALIZED AND VERIFIERS_QUALIFIED AND BINDINGS_CURRENT`  
>
> | ID | Class | Requirement | Test |
> |---|---|---|---|
> | `PD-CH2-029` | M | P4 MUST enforce task-count and task-unit caps from the F4 lane's canonical Policy defaults. | CH2-T29 MICRO task of 7 units exceeds 4-unit cap → `MISSING[PD-CH2-029]`; in-cap payload → `SATISFIED`. |
> | `PD-CH2-031` | M | WorkGraph dependency edges MUST be acyclic. | CH2-T31 cycle → `MISSING[PD-CH2-031]`. |
> | `PD-CH2-032` | M/E/J | Known write-set overlap MUST serialize mechanically; unknown/undeclared write sets MUST block for human resolution. | CH2-T32 known overlap → serialized / `SATISFIED`; CH2-T32b unknown write set → `BLOCKED_ON_HUMAN[PD-CH2-032]`. |
>
> **NEVER Rule:**  
> *"Run undeclared-overlap tasks in parallel, infer a verifier, exceed a lane cap, or write kernel graph/plan state from product code."*

---

## 3. P4 Additions Architecture Proposal

### 3.1 Plan Evaluator Component (`sclass.product.planning`)
The P4 Plan Evaluator validates candidate `Plan` payloads generated by planning agents:

```
+-------------------------------------------------------------------------+
|                           P4 PLAN EVALUATOR                             |
+-------------------------------------------------------------------------+
|                                                                         |
|  1. Scope & Lane Cap Validator (PD-CH2-029)                             |
|     - Inspects F4 lane: MICRO, STANDARD, or CRITICAL.                  |
|     - Verifies:                                                         |
|         len(task_nodes) <= MaxTasksPerGraph                             |
|         for each task: len(distinct_units) <= MaxUnitsPerTask           |
|         len(all_distinct_units) <= MaxTotalGraphUnits                   |
|     - If cap breached: returns MISSING[PD-CH2-029].                     |
|                                                                         |
|  2. Acyclicity Checker (PD-CH2-031)                                     |
|     - Implements Tarjan's or Kahn's algorithm over dependency edges.    |
|     - Detects direct or indirect cycles; yields topological order.      |
|     - If cycle detected: returns MISSING[PD-CH2-031].                   |
|                                                                         |
|  3. Concurrency & Overlap Arbitrator (PD-CH2-032)                       |
|     - For every pair of parallel (unconnected) tasks (T_A, T_B):        |
|       * Case 1: Write sets declared and disjoint -> Valid Parallel.     |
|       * Case 2: Write sets declared with intersection -> Serialize      |
|                 (add dependency edge T_A -> T_B) -> SATISFIED.          |
|       * Case 3: Either task has undeclared/unknown write set:           |
|                 Fail closed -> BLOCKED_ON_HUMAN[PD-CH2-032].            |
|                                                                         |
|  4. Planned Coverage Validator (PD-F6-006 / PD-F6-005)                  |
|     - Verifies each confirmed obligation maps to at least one           |
|       VerificationStep via valid F6 trace links.                        |
|                                                                         |
+-------------------------------------------------------------------------+
```

---

## 4. Explicitly Identified Unresolved Ambiguities

Per directive, the following items are unresolved ambiguities in the R30 Master that must NOT be invented in implementation:

1. **Dynamic / Runtime-Generated Write Target Representation:**
   - A task unit is defined as *"one distinct canonical mutation target (file, symbol, API, schema, database object, or explicit external-effect target)"*. If a build script generates intermediate files whose names are non-deterministic or resolved at compile time, the master does not define how such targets must be declared to avoid triggering `BLOCKED_ON_HUMAN[PD-CH2-032]`.
2. **Deterministic Serialization Tie-Breaker:**
   - When two overlapping tasks `T_A` and `T_B` must be serialized under `PD-CH2-032`, the master requires that they *"serialize mechanically"*, but does not specify the exact canonical ordering rule (e.g. lexicographical by `task_id`, or by index in `task_nodes`).
3. **Database Table / Schema Unit Granularity:**
   - For database mutations, it remains ambiguous whether a single DDL migration script altering 5 columns across 2 tables counts as 1 unit (1 migration file) or 7 units (2 tables + 5 columns).
