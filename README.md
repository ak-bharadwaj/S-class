# S-Class V9.2.0: Event-Sourced Cognitive Memory Microkernel Engine

S-Class is an **Event-Sourced Cognitive Memory Microkernel Engine** designed to provide deterministic, verifiable, and strategy-aware software development for AI agent platforms. 

Rather than treating LLMs as trusted state editors or running unstructured prompt loops, S-Class treats LLMs and subagents as **untrusted decision proposers**, placing all state mutations behind a lean, policy-driven **Deterministic Microkernel (`sclass_kernel.py`)** with **Event Sourcing**, **Tri-Partite Cognitive Memory**, and an **Event-Driven Asynchronous Graph**.

---

## Master Architecture Map (V9.2.0)

```
                            User Goal Prompt
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              PRE-PLANNING KNOWLEDGE BASE (`knowledge_base.py`)           │
│  Profile-Driven Selective Retrieval Policies:                           │
│  - BUG_FIX Profile   ➔ Loads `failed_approaches` + `reusable_fixes`     │
│  - RESEARCH Profile  ➔ Loads `architecture_patterns` + `standards`       │
│  - HOTFIX Profile    ➔ Loads `recent_incidents` + `regressions`         │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ Injects Organizational Context
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│            DECOUPLED PLANNING PIPELINE (`sclass_planner.py`)            │
│  1. IntentExtractor  ➔ Extracts goals, scope boundaries, & constraints  │
│  2. RiskAnalyzer     ➔ Assesses risk level, review depth, & KB context  │
│  3. WorkflowSelector ➔ Selects workflow profile (FULL, BUG_FIX, etc.)   │
│  4. ExecutionPlanner ➔ Assembles task DAG & capability squad           │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ Proposes Execution Plan
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              DETERMINISTIC MICROKERNEL (`sclass_kernel.py`)             │
│  Formally Enforces:                                                    │
│  Initial Design ➔ DEBATE ➔ DESIGN_REVISION ➔ TASK_COMPILATION ➔         │
│  CODING ➔ TASK_VERIFICATION ➔ MERGE ➔ INTEGRATION ➔ QA ➔ RELEASE ➔     │
│  MONITORING ➔ FEEDBACK ➔ ISSUE_DETECTION ➔ HOTFIX / RECOVERY Loop      │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ├──────────────────────────────────────┐
                                   ▼                                      ▼
┌────────────────────────────────────────┐ ┌──────────────────────────────┐
│  TRI-PARTITE COGNITIVE MEMORY          │ │ ACTIVE MULTI-STREAM MONITOR │
│  (`context_compressor.py`)             │ │ (`monitoring.py`)            │
│  - Episodic Memory ("What happened?")  │ │ Ingests 6 Telemetry Streams: │
│  - Semantic Memory ("What we learned") │ │ Logs, Metrics, User Reports, │
│  - Working Memory ("Current context")  │ │ Crash, Perf, Security        │
└────────────────────────────────────────┘ └──────────────┬───────────────┘
                                                          │
                                                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│           AUTOMATED LEARNING ENGINE & PROMOTION (`learning_engine.py`)  │
│  Execution ➔ Evaluation ➔ Candidate Capture ➔ Approval ➔ KB Update      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## The 8 Core Subsystems of S-Class V9.2.0

| # | Subsystem | Module | Technical Rationale & Impact |
| :--- | :--- | :--- | :--- |
| **1** | **Deterministic Microkernel** | `sclass_kernel.py` | Exclusive authoritative state mutator exposing formal Kernel API (`request_transition`, `request_merge`, etc.). |
| **2** | **Event Sourcing Store** | `.agents/event_store.jsonl` | Append-only event log serves as canonical truth. State can be reconstructed via event replay. |
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

## Formal Kernel API (`sclass_kernel.py`)

Untrusted LLMs, builders, and subagents cannot mutate state directly. All state updates pass through formal, policy-driven Kernel API methods:

```python
kernel.request_transition(from_state, event_name, workspace_dir)
kernel.request_task_verification(task_id, workspace_dir)
kernel.request_merge(task_id, sandbox_branch, workspace_dir)
kernel.request_recovery(error_log, workspace_dir)
kernel.request_release(workspace_dir)
kernel.reconstruct_state_from_event_store(workspace_dir)
```

---

## Declarative Verification Policies (`policies.json`)

Verification requirements are declared as clean policy definitions:

```json
{
  "verification_policies": {
    "ui": { "requires": ["build_check", "screenshot"], "min_strength": 3.0 },
    "backend": { "requires": ["build_check", "unit_test"], "min_strength": 3.0 },
    "auth": { "requires": ["build_check", "unit_test", "security_scan", "integration_test"], "min_strength": 5.0 }
  }
}
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
