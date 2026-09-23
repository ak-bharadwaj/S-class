# Step-Code Capability Harvest & Assurance-Plane Consolidation

## 1. Executive Summary & Foundational Axiom

This document establishes the authoritative inventory, classification, and absorption strategy of **Step-Code** capabilities into **S-Class**.

The foundational axiom of this refactor is:
> **Step-Code execution state != S-Class project truth.**
> **Step-Code provides the execution substrate. S-Class provides the independent assurance substrate.**

S-Class exploits Step-Code's mature execution harness primitives (subprocess management, tool executors, session trees, worker lanes, command permission heuristics, durable operation lifecycles) while maintaining absolute independent authority over:
1. Cryptographic dual-layer authorization
2. Independent sensory observation (filesystem, git tree, subprocesses)
3. Formal typed evidence verification
4. Canonical state reduction
5. Mutation invalidation & regression frontiers
6. Bounded crash recovery
7. Independent completion adjudication

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

| Subsystem Area | Step-Code Location / Primitive | Decision | S-Class Target Ownership & Architectural Handling |
| :--- | :--- | :--- | :--- |
| **Durable Operation Model** | `packages/agent-core` (operation state, pending effect, settlement, terminal result) | **B — Adapt** | Adapted into `ExecutionLedger`, `DurableOperation`, and `CrossRuntimeOperation`. S-Class adds Intent -> Authorization gate and separates execution truth from project truth. Persisted via `CanonicalOperationStore`. |
| **Effect Lifecycle** | Intent -> Effect Pending -> Effect Executed -> Runtime Settlement | **B — Adapt** | Extended into: Action Intent -> S-Class Authorization -> Runtime Effect -> Independent Observation -> Evidence Receipt -> Claim Assessment -> Canonical Project State. |
| **Replay Semantics** | Tool-level execution retry | **B — Adapt** | Explicit `ReplayClass` (`SAFE`, `IDEMPOTENT`, `NEVER`). Destructive or stateful operations fail closed and are never automatically replayed during recovery. |
| **Command Permission Analysis** | `docs/command-permissions.md` (pattern allowlists, prompt gates, sandboxing) | **B — Adapt** | Retained as lower runtime safety layer (`StepCodeCommandAnalyzer`). Integrated into `DualLayerAuthorizer` (S-Class Policy + Runtime Permission). |
| **Session Trees & Forking** | `packages/agent-core` (session trees, checkpointing, branching) | **C — Wrap** | Wrapped under `RuntimeHarness.inspect_session()` and `SessionState`. Managed in lower `ExecutionLedger`. |
| **Tool Execution Engine** | `packages/coding-agent` (file editing, shell execution, diffing) | **C — Wrap** | Kept in external runtime engine (`tools/step_rpc_server.js` or CLI). S-Class does not duplicate file-editing tool implementations. |
| **Model Provider Adapters** | `packages/providers` (LLM streaming, rate limiting, auth) | **C — Wrap** | External to S-Class. Governed via `RuntimeHarness` RPC interface (`prompt`, `steer`, `follow_up`). |
| **Subagent Concurrency & Lanes** | `packages/agent-core` (background lanes, parallel workers, worktree isolation) | **B — Adapt** | External runtime manages physical lanes; S-Class enforces `SubagentAuthorityScope`, symbol leases, and claim scopes. |
| **Goal Lifecycle** | `docs/goal-lifecycle.md` (goal decomposition, goal complete state) | **D — Consume only** | Runtime goal completion is treated as an untrusted proposal. Final task completion is adjudicated independently by S-Class `CompletionEvaluator`. |
| **Tool Results & Stdio** | `packages/agent-core` (tool output, terminal exit code) | **D — Consume only** | Ingested as candidate signals (`untrusted_candidate=True`) for independent observation, never directly promoted to verified truth. |
| **Full Coding Agent Loop** | Conversational prompt loop, multi-turn LLM agent loop | **E — Do not adopt** | S-Class is an assurance plane, not a conversational LLM coding agent. Adopting the agent loop into S-Class would violate separation of concerns. |
| **Plugin Marketplace** | Plugin manifests, MCP registry | **C — Wrap** | Wrap MCP plugin discovery behind unified action gateway. Do not build competing marketplace. |

---

## 4. Architectural Separation: Two Distinct Planes

```text
                        USER / CLI / IDE
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
1. **Execution Ledger (`.sclass/trust/cross_runtime_operations.jsonl` + SQLite `cross_runtime_operations`)**:
   - Owned by the runtime harness.
   - Tracks operational execution truth (lower runtime operations, session trees, tool retries, raw exit codes).
2. **Assurance Ledger (`.sclass/trust/assurance_ledger.jsonl`)**:
   - Owned exclusively by S-Class.
   - Tracks canonical project truth (technical obligations, claims, independent evidence receipts, verifier assessments, regression frontiers).

Direct promotion or mutation from Execution Ledger to Assurance Ledger is strictly forbidden. All state promotions must proceed through independent observation and typed verifier evaluation.

---

## 5. MIT License & Attribution Notice

The architectural harvest, durable operation state lifecycle, session tree concepts, and command permission analysis patterns incorporated in this consolidation are adapted from **Step-Code**.

```text
Portions of this software and architectural patterns are derived from Step-Code:
Copyright (c) Step-Code Contributors.
Licensed under the MIT License:

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
