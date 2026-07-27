# S-Class V9.2.0: Event-Sourced Cognitive Memory Microkernel Engine

S-Class is an **Event-Sourced Cognitive Memory Microkernel Engine** built for AI agent platforms. Rather than allowing AI agents to mutate project state directly or drift during long coding sessions, S-Class places all code generation, planning, and state transitions behind a deterministic, policy-driven microkernel.

---

## Why S-Class EOS? (The Core Advantage)

| Without S-Class | With S-Class EOS V9.2.0 |
| :--- | :--- |
| **Direct State Mutation:** Agents edit files and state without formal validation, causing silent corruption. | **Exclusive Kernel Mutator:** Only the deterministic `sclass_kernel` can write state changes to disk. |
| **Context Window Overflow:** Long-running coding sessions crash or drift as context bloats. | **Tri-Partite Cognitive Memory:** Automatically compresses context into Episodic, Semantic, and Working Memory. |
| **Speculative Verification:** Completion is self-reported by LLM prompts ("I fixed it!"). | **Policy-Driven Evidence Gates:** Hard-blocks state transitions unless physical test receipts & diffs exist on disk. |
| **Irreproducible Execution:** Failures cannot be audited or replayed when things go wrong. | **Canonical Event Sourcing & Replay:** Immutable event store (`event_store.jsonl`) enables 100% mathematical replayability. |
| **Static Memory:** Systems relearn the same architectural lessons and mistakes on every run. | **Selective KB & Automated Learning:** Pre-planning knowledge retrieval + automatic candidate learning loop. |

---

## How S-Class Compares to Other Frameworks

| Feature | OpenHands | Claude Code | Codex / Generic Agents | **S-Class EOS V9.2.0** |
| :--- | :--- | :--- | :--- | :--- |
| **Architecture** | Sandbox Harness | CLI Agent Loop | Prompt Loop | **Deterministic Microkernel** |
| **State Mutation Guard** | ❌ Direct File Edits | ❌ Direct File Edits | ❌ Direct File Edits | **✅ Exclusive Kernel Mutator** |
| **Evidence Validation** | ⚠️ Self-Reported | ⚠️ Command Exit Codes | ❌ None | **✅ Policy-Driven Evidence Gates** |
| **Event Sourcing** | ❌ None | ❌ None | ❌ None | **✅ Append-Only `event_store.jsonl`** |
| **Cognitive Memory** | ❌ Flat History | ❌ Flat History | ❌ Flat History | **✅ Tri-Partite Memory (Episodic/Semantic/Working)** |
| **Post-Release Loop** | ❌ Terminal State | ❌ Terminal State | ❌ Terminal State | **✅ Continuous Multi-Stream Telemetry Loop** |

---

## End-to-End Execution Data Flow

```
   User Request / Prompt
           │
           ▼
┌──────────────────────┐
│   Planning Engine    │ ◄── Ingests Organizational Knowledge Base (`knowledge_base.py`)
│  (`sclass_planner`)  │
└──────────┬───────────┘
           │ Proposes Execution Plan
           ▼
┌──────────────────────┐
│ Deterministic Kernel │ ◄── Enforces FSM State Graph & Schema Validation (`sclass_kernel.py`)
└──────────┬───────────┘
           │ Dispatches Task
           ▼
┌──────────────────────┐
│ Resource OS Scheduler│ ◄── Checks CPU, RAM, & Concurrency Bounds (`ResourceAwareScheduler`)
└──────────┬───────────┘
           │ Spawns Ephemeral Builders
           ▼
┌──────────────────────┐
│ Sandboxed Builders   │ ◄── Build isolated code changes in `sandbox/T1`, `sandbox/T2`
└──────────┬───────────┘
           │ Submits Code Outputs
           ▼
┌──────────────────────┐
│ Verifier Evidence    │ ◄── Audits physical diffs, test receipts, & visual screenshots (`verifier.py`)
└──────────┬───────────┘
           │ Approves Mutation
           ▼
┌──────────────────────┐
│ Canonical EventStore │ ◄── Appends immutable event to `.agents/event_store.jsonl`
└──────────┬───────────┘
           │
           ├──────────────────────────┐
           ▼                          ▼
┌──────────────────────┐   ┌──────────────────────┐
│ Replay Engine        │   │ Learning Engine      │
│ (`replay.py`)        │   │ (`learning_engine`)  │
│ 100% Audit Replay    │   │ Promotes KB Lessons  │
└──────────────────────┘   └──────────────────────┘
```

---

## The 8 Core Subsystems of S-Class V9.2.0

| # | Subsystem | Module | Technical Rationale & Impact |
| :--- | :--- | :--- | :--- |
| **1** | **Deterministic Microkernel** | `sclass_kernel.py` | Exclusive authoritative state mutator exposing formal Kernel API (`request_transition`, `request_merge`, etc.). |
| **2** | **Event Sourcing Store** | `.agents/event_store.jsonl` | Append-only event log serves as canonical truth. State can be reconstructed at any time via event replay. |
| **3** | **Pre-Planning Knowledge Base** | `knowledge_base.py` | Profile-driven selective retrieval loads organizational memory upfront before drafting plans. |
| **4** | **Decoupled 4-Stage Planner** | `sclass_planner.py` | Single-responsibility pipeline: `IntentExtractor` ➔ `RiskAnalyzer` ➔ `WorkflowSelector` ➔ `ExecutionPlanner`. |
| **5** | **Tri-Partite Cognitive Memory** | `context_compressor.py` | Separates context into Episodic ("What happened"), Semantic ("What we learned"), & Working Memory ("Current context"). |
| **6** | **Event-Driven Asynchronous Graph**| `event_graph.py` | Pub/sub event broker (`TASK_STARTED`, `TASK_COMPLETED`, `QA_FAILED`, `RECOVERY_REQUIRED`, `RELEASE_CREATED`, `MONITORING_ALERT`). |
| **7** | **Multi-Stream Active Monitoring** | `monitoring.py` | Active ingestion across 6 streams: Logs, Metrics, User Reports, Crash Reports, Performance, & Security Events. |
| **8** | **Automated Learning & KB Promotion**| `learning_engine.py` | Captures knowledge candidates during execution and promotes approved candidates to permanent KB files. |

---

## Tri-Partite Cognitive Memory Science

S-Class avoids context window overflow by structuring memory into three distinct cognitive layers:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. EPISODIC MEMORY ("What happened?")                                  │
│    - Past sequential FSM state events & transitions                     │
│    - Execution failures & retry histories                               │
│    - Milestone phases completed                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ 2. SEMANTIC MEMORY ("What did we learn?")                              │
│    - Generalized architectural principles & learned rules               │
│    - Organizational standards & invariant constraints                   │
├─────────────────────────────────────────────────────────────────────────┤
│ 3. WORKING MEMORY ("Current execution context")                        │
│    - Active FSM state phase                                             │
│    - Target file paths & active sandbox branch                          │
│    - Active boundary risks & review depth                               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Test Suite & Verification

S-Class contains **64 automated unit tests** passing cleanly with 100% success across Python 3.10, 3.11, 3.12, 3.13, and 3.14:

```bash
python -m pytest tests/ -v
# Output: 64 passed in 0.40s
```

---

## Quick Start & Installation

### Installation

#### Windows (PowerShell):
```powershell
iex (irm -useb https://raw.githubusercontent.com/ak-bharadwaj/S-class/master/install.ps1)
```

#### Linux / macOS (Shell):
```bash
curl -fsSL https://raw.githubusercontent.com/ak-bharadwaj/S-class/master/install.sh | bash
```

---

## License
S-Class is released under the [MIT License](LICENSE).
