# S-Class Runtime Plane Architecture

## 1. Executive Summary & Epistemic Boundary

The **Runtime Plane** is the operational execution substrate of S-Class.
It incorporates the deep, battle-tested execution mechanics of **Step-Code** (MIT License, StepFun):
- Multi-lane execution isolation (main, parallel, subagent, workflow, background)
- Durable effect sandwich (`INTENT -> EFFECT_PENDING -> EXTERNAL EFFECT -> SETTLEMENT`)
- 5-Way conjunction permission engine
- First-class tool call and tool result lifecycle interception
- Resilient session tree checkpointing and non-destructive context compaction
- Bounded recovery ladders

### Foundational Invariant
> **Runtime execution state != S-Class project truth.**
> All runtime results, process exit codes, tool outputs, and task completion proposals remain **untrusted candidates** until independently observed, receipted, and verified by the S-Class Assurance Plane.

---

## 2. The Consolidated RuntimeProvider Hierarchy

Rather than maintaining fragmented runtime abstractions, S-Class unifies all external execution engines under `src/sclass/runtime/provider.py`:

```text
                  RuntimeProvider (Abstract Base)
                   ├── StepCodeProvider (src/sclass/runtime/stepcode.py)
                   ├── NativeProvider
                   ├── CodexProvider
                   └── ClaudeProvider
```

### Core Provider Lifecycle
1. `health_check()`: Verifies process health, pipe framing, and connectivity.
2. `start_operation(intent)`: Initializes a cross-runtime operation in canonical storage.
3. `execute_action(action, authorization)`: Executes an authorized action through the 5-way permission engine and durable effect sandwich.
4. `observe_operation(operation_id)`: Fetches durable operation state from canonical storage.
5. `cancel_operation(operation_id, reason)`: Transitions in-flight operation to `CANCELLED`.

---

## 3. The Durable Effect Sandwich

All mutating or external actions pass through the two-phase transaction boundary (`src/sclass/execution/effect_boundary.py`):

```text
       TX1: Persist Operation Intent & Identity (EFFECT_PENDING)
                            ↓
       EFFECT: Invoke External Runtime Substrate (Out-of-process)
                            ↓
       TX2: Persist Runtime Settlement & Hashes (SETTLED / FAILED)
```

- **TX1**: Persists `intent_hash`, `action_hash`, `replay_class`, and operation identity.
- **EFFECT**: Executes out-of-process tool call.
- **TX2**: Persists exit code, execution duration, and stdio hashes.
- **Rules**:
  - Never infer effect completion from process termination.
  - Never infer effect completion from missing state.
  - Never infer effect completion from model narrative.

---

## 4. 5-Way Permission Conjunction Engine

Step-Code permissions are governed by `src/sclass/runtime/permissions.py`:
- 4 Presets: `Ask`, `Read-only`, `Bypass`, `Autopilot`.
- Conjunction Model:
  $$\text{Can Execute} = \text{S-Class Auth} \land \text{Step-Code Perm} \land \text{Capability} \land \text{Workspace Policy} \land \text{Operation State}$$
- **Fail-Closed Rule**: A Step-Code `ALLOW` cannot override an S-Class `DENY`. An S-Class `ALLOW` cannot override a Step-Code `DENY`.

---

## 5. Execution Lanes & Bounded Subagent Delegation

Execution concurrency is organized into isolated lanes (`src/sclass/runtime/lanes.py`):
- `MAIN`: Primary orchestration lane.
- `PARALLEL`: Concurrent worker lane.
- `SUBAGENT`: Dedicated child agent lane.
- `WORKFLOW`: Phased pipeline execution lane.
- `BACKGROUND`: Long-running asynchronous monitoring lane.

### Delegation Invariant
A child agent receives:
- Delegated task scope
- Delegated workspace boundary
- Delegated token/time budget
- Delegated tool set

**NEVER parent authority.** Child agents may generate candidate evidence, but **can never certify their own evidence**.

---

## 6. Context Management & Telemetry

- **Context Compaction** (`src/sclass/runtime/sessions.py`): Compresses prior turns into structured branch summaries for LLM token budgets. Preserves 100% of durable session history and canonical evidence on disk.
- **Typed Telemetry** (`src/sclass/runtime/telemetry.py`): Emits structured events (`tool_call_completed`, `permission_decision`, `workflow_started`, etc.) into append-only JSONL. Telemetry provides observability only and cannot establish completion.

---

## 7. Plan & Task System Distinction (Directive Section 12)

S-Class strictly separates operational planning from canonical truth:
- **Step plan** $\rightarrow$ `ExecutionPlanCandidate` (`src/sclass/runtime/plans.py`): Operational sequence proposed by the model.
- **Step task** $\rightarrow$ `RuntimeTask` (`src/sclass/runtime/plans.py`): Individual execution unit updated by runtime.
- **S-Class obligation** $\rightarrow$ `TechnicalObligation` (`src/sclass/domain/obligations.py`): Canonical acceptance requirement.

> **Absolute Rule**: The model or Step-Code engine may update runtime tasks, but runtime task completion **cannot mark an S-Class obligation satisfied**. Only canonical S-Class state reduction through independent verifiers establishes obligation satisfaction.

---

## 8. Subsystem Migration Registry (Directive Section 41)

In accordance with Directive Section 41, all subsystems are strictly categorized with zero duplicate authority paths:

| Subsystem ID | Canonical Path | Status | Superseded By | Epistemic / Authority Note |
|---|---|---|---|---|
| `runtime_provider` | `src/sclass/runtime/provider.py` | `ACTIVE` | - | Unified abstraction for Step-Code, Native, Codex, Claude |
| `stepcode_provider` | `src/sclass/runtime/stepcode.py` | `ACTIVE` | - | Out-of-process subprocess execution with 5-way permission |
| `stepcode_rpc_harness` | `src/sclass/execution/harness.py` | `COMPATIBILITY` | `stepcode.py` | Low-level JSONL RPC framing layer |
| `legacy_regex_cmd_analyzer` | `src/sclass/execution/isolated.py` | `DEPRECATED` | `permissions.py` | Replaced by 5-way permission engine |
| `evolution_engine` | `src/sclass/evolution/engine.py` | `ACTIVE` | - | RRSI Pareto frontier, calibration, readjudication |
| `effect_boundary` | `src/sclass/execution/effect_boundary.py` | `ACTIVE` | - | TX1 -> EFFECT -> TX2 two-phase transactional sandwich |
| `dual_ledgers` | `src/sclass/trust/two_ledgers.py` | `ACTIVE` | - | Runtime execution ledger separated from assurance ledger |
| `step_extension_bridge` | `src/sclass/adapters/step_extension.js` | `ACTIVE` | - | `pi.on("tool_call")` and `pi.on("tool_result")` extension hooks |
| `legacy_mock_harness` | `tests/doubles/mock_harness.py` | `REFERENCE` | - | Preserved for isolated offline unit tests |
| `unverified_agent_proposals` | `src/sclass/assurance/authority.py` | `DEAD` | `completion.py` | Unverified agent claims cannot establish project truth |

