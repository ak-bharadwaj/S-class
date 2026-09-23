# Architecture: Step-Code External Runtime Integration

## 1. Executive Summary & Epistemic Separation

S-Class establishes an uncompromising architectural boundary between execution and assurance:
> **Step-Code provides the execution substrate. S-Class provides the independent assurance substrate.**
> **Step-Code execution state != S-Class project truth.**

Step-Code is an external, decoupled execution engine operating as a separate process or daemon. It manages the LLM conversation loop, tool invocations, session branching, subagent worker lanes, command permission heuristics, and execution retries.

S-Class sits above the execution plane as the independent epistemic authority. It governs cryptographic authorization, independent sensory observation, formal evidence verification, canonical state reduction, mutation invalidation, regression frontiers, bounded crash recovery, and task completion adjudication.

**Under no circumstances can an external runtime signal (such as `status: "SETTLED"`, `result: "SUCCESS"`, or `goal_complete: true`) ever establish S-Class project truth.** All candidate outputs emitted by Step-Code are strictly classified as `untrusted_candidate` until independently verified by S-Class observers and typed verifiers.

---

## 2. Concrete Primitive Mapping

| Step-Code Primitive | S-Class Equivalent | Role in S-Class Assurance Plane |
| :--- | :--- | :--- |
| **Session / Tree Node** | `session_id` / `HandoffContext` | Execution session boundary; scoped worktree context |
| **Operation Lifecycle** | `DurableOperation` / `CrossRuntimeOperation` | Tracks runtime effect lifecycle across `PLANNED` -> `AUTHORIZED` -> `EFFECT_PENDING` -> `EFFECT_EXECUTED` -> `SETTLED` |
| **Tool Execution** | `ActionRequest` / `RuntimeEvent` | Candidate action input evaluated by S-Class authorizers before execution |
| **Effect Pending Signal** | `OperationState.EFFECT_PENDING` | Pending effect fence preventing concurrent or untracked workspace mutations |
| **Runtime Settlement** | `OperationState.SETTLED` | Untrusted candidate execution output requiring observation and verification |
| **Tool Result / Stdio** | `untrusted_candidate` | Candidate evidence signal; never promoted directly to verified claim |
| **Goal Completion** | Untrusted Proposed Completion | Candidate proposal submitted to `CompletionEvaluator.adjudicate()` |
| **Subagent Workers** | `SubagentAuthorityScope` | Bounded child execution context constrained by symbol leases and claim boundaries |
| **Command Permission** | `StepCodeCommandAnalyzer` | Lower-tier execution safety heuristic (part of Dual-Layer Authorization) |

---

## 3. Stdio LF Protocol & Communication Invariant

Communication between S-Class (`StepCodeRpcHarness`) and the external Step-Code runtime (`step --mode rpc` / `tools/step_rpc_server.js`) occurs over standard I/O using strict single-byte LF (`0x0A`, `\n`) framed JSON lines:

### Protocol Invariants:
1. **Strict LF Framing (`0x0A`)**:
   Standard JSONL requires single-byte `\n` framing. Payloads containing Unicode line terminators (such as `\u2028` Line Separator or `\u2029` Paragraph Separator) MUST NOT cause line-splitting or buffer corruption. Python's default text streams and `splitlines()` split on Unicode separators; therefore, S-Class uses raw byte buffer slicing on `b'\n'` (`0x0A`).
2. **Synchronous Request-Response Correlation**:
   Every RPC request carries an integer `id` and `action`. Responses mirror `id` and return `status` ("ok" or "SETTLED") and `result`.
3. **Fail-Closed Subprocess Lifecycle**:
   If the external Step-Code process terminates unexpectedly, hangs, or emits corrupt JSON, `StepCodeRpcHarness` immediately fails closed, marks the runtime as `UNAVAILABLE`, transitions in-flight operations to `FAILED`, and blocks all subsequent unverified effects until cleanly restarted.
4. **Standard Commands**:
   - `prompt`: Ingests agent instruction, drives LLM turn, returns untrusted response candidate.
   - `tool_call`: Submits an authorized action for execution in the target workspace.
   - `abort`: Cancels an in-flight operation in the runtime process.
   - `state`: Queries runtime session tree and active lanes.
   - `health`: Returns runtime process liveness and ready state.

---

## 4. Dual-Layer Authorization Gate

Before any action reaches the Step-Code execution engine, it must pass both layers of the dual authorization gate:

```text
ActionRequest
     |
     v
[ Layer 1: S-Class DualLayerAuthorizer ]
  - Evaluates cryptographic integrity, active obligations, claim scopes,
    and capability registry policies.
  - Generates immutable AuthorizationDecision with action_hash binding.
     | (ALLOW)
     v
[ Layer 2: StepCodeCommandAnalyzer ]
  - Analyzes shell commands, path boundaries, destructive patterns
    (rm -rf, mkfs, format, fork bombs).
     | (ALLOWED)
     v
[ External Step-Code RPC Execution ]
```

If either layer denies or detects tampering (`action_hash` mismatch), execution is aborted immediately and recorded in the audit trail.

---

## 5. Dual-Ledger Architecture

Execution truth and project truth are partitioned into two strictly decoupled ledgers:

1. **Execution Ledger (`.sclass/trust/cross_runtime_operations.jsonl` + SQLite `cross_runtime_operations`)**:
   - Owned by the runtime harness.
   - Records operational execution history: lower runtime IDs, timestamps, replay classes, raw exit codes, and settlements.
   - Used for crash recovery and audit trails.
2. **Assurance Ledger (`.sclass/trust/assurance_ledger.jsonl`)**:
   - Owned exclusively by S-Class.
   - Records canonical project truth: technical obligations, independent claims, evidence receipts, verifier decisions, and regression frontiers.
   - Directly ingested by `CanonicalStateReducer` and `CompletionEvaluator`.

Direct mutation from the Execution Ledger to the Assurance Ledger is cryptographically and architecturally forbidden.

---

## 6. Open-Source Harvest & Attribution Notice

The durable operation lifecycle, session tree isolation patterns, and command permission analysis integrated into this architecture were harvested and adapted from **Step-Code**.

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
