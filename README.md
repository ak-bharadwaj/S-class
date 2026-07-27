# S-Class V9.2: The Deterministic AI Runtime

> **Event-Sourced Cognitive Memory Microkernel Engine for AI Agent Platforms**

S-Class is a **Deterministic AI Runtime**. Rather than allowing AI agents to mutate project state directly or drift during long coding sessions, S-Class places all code generation, planning, and state transitions behind a deterministic, policy-driven microkernel running on your host operating system.

---

## 30-Second Quick Start Example

```python
import runtime
from sclass_kernel import kernel_instance
from sclass_planner import ExecutionPlanner

# 1. Initialize deterministic FSM state for your engineering goal
state = runtime.initialize_state(goal="Fix user authentication JWT token validation bug")

# 2. Planning Engine creates an Execution Strategy with domain matching & KB rules
plan = ExecutionPlanner.create_plan(state.planRationale)

# 3. Formally request Kernel State Transition (Exclusive Authoritative State Mutator)
res = kernel_instance.request_transition("TRIAGE", "triage_done")
print(f"Kernel Approved Transition: {res['previousPhase']} ➔ {res['currentPhase']}")

# 4. Request Per-Task Verification on isolated builder sandbox
ver_res = kernel_instance.request_task_verification(task_id="T1")
print(f"Sandbox Task Verified: {ver_res['status']}")

# 5. Cleanly merge verified task into primary branch
merge_res = kernel_instance.request_merge(task_id="T1", sandbox_branch="sandbox/T1")
print(f"Merged Sandbox: {merge_res['currentPhase']}")
```

---

## Why S-Class EOS? (The Core Advantage)

| Without S-Class | With S-Class V9.2 |
| :--- | :--- |
| **Direct State Mutation:** Agents edit files and state without formal validation, causing silent corruption. | **Exclusive Kernel Mutator:** Only the deterministic `sclass_kernel.py` can write state changes to disk. |
| **Context Window Overflow:** Long-running coding sessions crash or drift as context bloats. | **Tri-Partite Cognitive Memory:** Automatically compresses context into Episodic, Semantic, and Working Memory. |
| **Prompt-Dependent Verification:** Completion is self-reported by LLM prompts ("I fixed it!"). | **Policy-Driven Evidence Gates:** Hard-blocks state transitions unless physical test receipts & diffs exist on disk. |
| **Irreproducible Execution Logs:** Failures cannot be audited or replayed when things go wrong. | **Deterministic Event Replay:** Immutable event store (`event_store.jsonl`) records execution events. |
| **Static Memory:** Systems relearn the same architectural lessons and mistakes on every run. | **Selective KB & Automated Learning:** Pre-planning knowledge retrieval + automatic candidate learning loop. |

---

## Framework Architectural Comparison

| Architectural Layer | OpenHands | Claude Code | Codex / Generic Agents | **S-Class V9.2 (Deterministic AI Runtime)** |
| :--- | :--- | :--- | :--- | :--- |
| **System Philosophy** | Sandbox Harness | CLI Agent Loop | Prompt Execution Loop | **Deterministic Microkernel Engine** |
| **State Mutation Guard** | File System Writes | File System Writes | File System Writes | **✅ Exclusive Kernel Mutator (`sclass_kernel.py`)** |
| **Evidence Validation** | Self-Reported Prompt | Command Exit Codes | Unchecked Prompts | **✅ Policy-Driven Evidence Gates (`policies.json`)** |
| **Event Sourcing** | Flat Execution Log | Command Line Log | Conversation Log | **✅ Append-Only `event_store.jsonl` Canonical Log** |
| **Cognitive Memory** | Flat Context Window | Flat Context Window | Flat Context Window | **✅ Tri-Partite Memory (`Episodic`, `Semantic`, `Working`)** |
| **Task Concurrency** | Single Thread Loop | Single Thread Loop | Single Thread Loop | **✅ OS Resource Scheduler (`resource_scheduler.py`)** |
| **Post-Release Loop** | Terminal State | Terminal State | Terminal State | **✅ Multi-Stream Active Telemetry Loop (`monitoring.py`)** |

---

## End-to-End Execution Data Flow

```
   User Request / Prompt
           │
           ▼
┌──────────────────────────────┐
│       Planning Engine        │ ◄── Pre-Planning KB Query (`knowledge_base.py`)
│     (`sclass_planner.py`)    │
└──────────────┬───────────────┘
               │ Proposes Execution Plan
               ▼
┌──────────────────────────────┐
│    Deterministic Kernel      │ ◄── Enforces FSM State Graph & Schema (`sclass_kernel.py`)
│    (`sclass_kernel.py`)      │
└──────────────┬───────────────┘
               │ Dispatches Task
               ▼
┌──────────────────────────────┐
│  Resource OS Task Scheduler  │ ◄── Checks CPU, RAM, & Concurrency Bounds (`resource_scheduler.py`)
│  (`resource_scheduler.py`)   │
└──────────────┬───────────────┘
               │ Spawns Ephemeral Tech Builders
               ▼
┌──────────────────────────────┐
│  Sandboxed Tech Builders    │ ◄── Build isolated code changes in `sandbox/T1`, `sandbox/T2`
└──────────────┬───────────────┘
               │ Submits Code Outputs
               ▼
┌──────────────────────────────┐
│   Verifier Evidence Gate     │ ◄── Audits physical diffs, test receipts, & screenshots (`verifier.py`)
│       (`verifier.py`)        │
└──────────────┬───────────────┘
               │ Approves Mutation
               ▼
┌──────────────────────────────┐
│  Canonical Event Sourcing    │ ◄── Appends immutable event to `.agents/event_store.jsonl`
└──────────────┬───────────────┘
               │
               ├──────────────────────────────┐
               ▼                              ▼
┌──────────────────────────────┐   ┌──────────────────────────────┐
│   Event Replay Engine        │   │   Automated Learning Engine  │
│       (`replay.py`)          │   │    (`learning_engine.py`)     │
│   Deterministic Audit Log    │   │    Promotes KB Lessons       │
└──────────────────────────────┘   └──────────────────────────────┘
```

---

## 1:1 Architecture-to-Module Mapping

| Architecture Box | Dedicated Module File | Key Responsibilities |
| :--- | :--- | :--- |
| **Deterministic Microkernel** | `sclass_kernel.py` | Authoritative state mutator, formal Kernel API, FSM graph validation. |
| **Planning Engine** | `sclass_planner.py` | 4-stage pipeline: Intent, Risk, Workflow selection, Execution Plan assembly. |
| **Resource OS Scheduler** | `resource_scheduler.py` | Checks host CPU, RAM, context budget, and builder concurrency limits ($\le 4$). |
| **Pre-Planning Knowledge Base** | `knowledge_base.py` | Profile-driven selective retrieval (`bug_fix`, `research`, `hotfix`, `full`). |
| **Context Compression Engine** | `context_compressor.py` | Structuring memory into Episodic, Semantic, and Working Memory layers. |
| **Event-Driven Graph Broker** | `event_graph.py` | Asynchronous pub/sub topic broker (`TASK_STARTED`, `QA_FAILED`, etc.). |
| **Multi-Stream Monitor** | `monitoring.py` | Active telemetry ingestion across 6 streams (Logs, Metrics, Crash, Perf, Security). |
| **Automated Learning Engine** | `learning_engine.py` | Captures knowledge candidates and promotes approved fixes to permanent KB. |
| **Verifier Evidence Gate** | `verifier.py` | Hard-blocks state transitions unless physical disk evidence and test receipts exist. |
| **Event Replay Engine** | `replay.py` | Deterministic event replay and Markdown trajectory audit report generation. |
| **Smart Recovery Dispatcher** | `error_recovery.py` | Categorized error recovery routing (Syntax ➔ Coding, Import ➔ Integration, etc.). |

---

## Comprehensive Test Suite Coverage

S-Class contains **65 automated unit tests** passing with 100% success across Python 3.10–3.14:

| Test Module File | Test Count | System Functionality Tested |
| :--- | :--- | :--- |
| `tests/test_kernel.py` | 6 tests | Kernel formal API, Event Sourcing replay, Tri-Partite Memory, Resource Scheduler, Event Graph. |
| `tests/test_eos_core.py` | 10 tests | Strategy Engine, Domain Classification, Capability Matching, Self-Evaluator, Evidence Verifier. |
| `tests/test_error_recovery.py` | 4 tests | Regex error matching, exponential backoff, stop conditions, Smart Multi-Tier Recovery. |
| `tests/test_planner.py` | 9 tests | Meta-Planner profile selection (`BUG_FIX`, `RESEARCH`, `REFACTOR`, `HOTFIX`), profile shortcuts. |
| `tests/test_replay.py` | 3 tests | TransitionRecord serialization, ReplayEngine trajectory audit, Markdown export. |
| `tests/test_runtime.py` | 9 tests | FSM state initialization, schema type validation, event dispatching, FileLock recovery. |
| `tests/test_memory_semantic.py` | 6 tests | Semantic TF-IDF vector similarity search, memory schema v2, auto-migration. |
| `tests/test_security_shield.py` | 4 tests | Secret scanning, dangerous AST pattern detection, vulnerability report generation. |
| `tests/test_topology.py` | 5 tests | Subagent network topologies (Hierarchical, Mesh, Star, Ring phase resolution). |
| `tests/test_doctor.py` | 4 tests | Environment health verification, corrupt file detection, stale lock recovery. |
| `tests/test_config_gc.py` | 4 tests | Lock GC, state expiration cleanup, memory pruning, orphaned screenshot GC. |
| `tests/test_intent_contract.py` | 3 tests | Intent Contract validation, scope boundary enforcement, serialization. |

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
