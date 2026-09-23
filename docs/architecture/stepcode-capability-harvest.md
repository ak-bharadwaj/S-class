# Step-Code Capability Harvest & Assurance-Plane Consolidation

## 1. Executive Summary

This document establishes the authoritative inventory, classification, and absorption strategy of **Step-Code** capabilities into **S-Class**.

The guiding principle of this refactor is:
> **Step-Code execution state != S-Class project truth.**
> S-Class exploits Step-Code's mature execution harness primitives while maintaining absolute independent authority over technical obligations, evidence verification, mutation invalidation, recovery, and completion adjudication.

---

## 2. Capability Classification Taxonomy

Every analyzed capability from Step-Code is classified into exactly one of five architectural tiers:

*   **A — Adopt directly**: The primitive is generic, mature, and directly usable by S-Class without semantic distortion.
*   **B — Adapt**: The architectural pattern or model is valuable, but S-Class requires stronger epistemic, security, or provenance semantics.
*   **C — Wrap**: The runtime subsystem remains external and encapsulated behind a stable S-Class adapter interface.
*   **D — Consume only**: S-Class ingests runtime events and output candidate data as untrusted signals, never as authority.
*   **E — Do not adopt**: The capability conflicts with S-Class's architecture, creates competing sources of truth, or duplicates solved product features.

---

## 3. Comprehensive Step-Code Subsystem Inventory

| Subsystem Area | Step-Code Location / Primitive | S-Class Status Prior | Decision | S-Class Target Ownership |
| :--- | :--- | :--- | :--- | :--- |
| **Durable Operation Model** | `packages/agent-core` (operation state, pending effect, settlement, terminal result) | Partially solved | **B — Adapt** | Adapted into `ExecutionLedger` and `DurableOperation`. S-Class adds Intent -> Authorization gate and separates execution truth from project truth. |
| **Effect Lifecycle** | Intent -> Effect Pending -> Effect Executed -> Runtime Settlement | Solved in parts | **B — Adapt** | Extended into: Action Intent -> S-Class Authorization -> Runtime Effect -> Independent Observation -> Evidence Receipt -> Claim Assessment -> Canonical Project State. |
| **Replay Semantics** | Tool-level execution retry | Missing explicit replay contract | **B — Adapt** | Explicit `ReplayClass` (`SAFE`, `IDEMPOTENT`, `NEVER`). Unsafe effects fail closed and are never automatically replayed. |
| **Command Permission Analysis** | `docs/command-permissions.md` (pattern allowlists, prompt gates, sandboxing) | Solved at policy level | **B — Adapt** | Retained as lower runtime safety layer. Forms dual-layer gate: S-Class Authorization + Runtime Permission. |
| **Session Trees & Forking** | `packages/agent-core` (session trees, checkpointing, branching) | Partially solved | **C — Wrap** | Wrapped under `RuntimeHarness.inspect_session()` and `SessionState`. Managed in `ExecutionLedger`. |
| **Tool Execution Engine** | `packages/coding-agent` (file editing, shell execution, diffing) | Solved in native | **C — Wrap** | Kept in runtime harness. S-Class does not duplicate file-editing tool implementations. |
| **Model Provider Adapters** | `packages/providers` (LLM streaming, rate limiting, auth) | Externalized | **C — Wrap** | External to S-Class. Governed via `RuntimeHarness`. |
| **Goal Lifecycle** | `docs/goal-lifecycle.md` (goal decomposition, goal complete state) | Solved via TaskState | **D — Consume only** | Runtime goal completion is treated as an untrusted proposal. Final task completion is adjudicated independently by S-Class `CompletionEvaluator`. |
| **Tool Results & Stdio** | `packages/agent-core` (tool output, terminal exit code) | Solved in observation | **D — Consume only** | Ingested as candidate signals for independent observation, never directly promoted to verified truth. |
| **Subagent Concurrency** | `packages/agent-core` (background lanes, parallel workers, worktree isolation) | Fleet coordinator | **B — Adapt** | Runtime manages concurrency/lanes; S-Class enforces `SubagentAuthorityScope`, symbol leases, and claim scopes. |
| **Full Coding Agent Loop** | Conversational prompt loop, multi-turn LLM agent loop | S-Class is not an agent | **E — Do not adopt** | S-Class is an assurance plane, not a conversational LLM coding agent. |
| **Plugin Marketplace** | Plugin manifests, MCP registry | MCP Gateway | **C — Wrap** | Wrap MCP plugin discovery behind unified action gateway. Do not build competing marketplace. |

---

## 4. Architectural Separation: Two Distinct Planes

```text
                        USER / IDE
                            |
                            v
               +---------------------------+
               |      EXECUTION PLANE      |
               |                           |
               | Step-Code / Claude Code / |
               | Codex / Custom Runtimes   |
               |                           |
               | Sessions, Tools, Retries, |
               | Worktrees, Subagents      |
               +-------------+-------------+
                             |
                      runtime events
                      intents/actions
                      observations
                             |
                             v
               +---------------------------+
               |       S-CLASS CORE        |
               |     (ASSURANCE PLANE)     |
               |                           |
               | Tasks, Obligations,       |
               | Claims, Authorizations,   |
               | Observations, Evidence,   |
               | Invalidation, Frontier,   |
               | Recovery, Completion      |
               +-------------+-------------+
                             |
                             v
                  CANONICAL PROJECT TRUTH
```

### The Two Ledgers
1. **Execution Ledger**: Owned by the runtime harness. Tracks execution truth (operations, sessions, retries, tool exit codes).
2. **Assurance Ledger**: Owned by S-Class. Tracks project truth (obligations, claims, evidence receipts, verification decisions, frontier).

Direct mutation from Execution Ledger to Assurance Ledger is strictly forbidden. All state promotions must proceed through independent observation and verifier evaluation.
