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
