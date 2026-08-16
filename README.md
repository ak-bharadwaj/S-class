<div align="center">

# ⚡ S-CLASS EOS V11.2
### The Deterministic AI Systems Runtime & Safety-Case Engine

*Enterprise-grade central deterministic orchestration kernel that eliminates AI agent drift, blocks broken UI releases, and enforces cryptographic verification evidence.*

[![Version](https://img.shields.io/badge/version-11.2.0--frozen-blue.svg)](https://github.com/ak-bharadwaj/S-class)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-green.svg)](https://github.com/ak-bharadwaj/S-class)
[![Build](https://img.shields.io/badge/tests-397%2F397%20passing-brightgreen.svg)](https://github.com/ak-bharadwaj/S-class)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)

[Quick Start](#-quick-start) • [Architecture](#-system-architecture) • [Features](#-core-architectural-innovations) • [Python SDK](#-30-second-python-sdk-quickstart) • [Benchmark Comparison](#-framework-architectural-comparison) • [License](#-license)

---

</div>

## 📌 Executive Overview

When autonomous AI coding agents execute software engineering tasks, they suffer from 3 critical failure modes:
1. **Agent Drift & Invention:** They get stuck in repetitive loops, invent unrequested features, or perform unverified direct file edits.
2. **Fake Verification:** They claim *"Everything works cleanly!"* based on superficial unit tests or build logs, while the actual runtime state or interface renders errors.
3. **Sparse & Amateur Implementation:** Unstructured mutations without epistemic grounding or verified ChangeSets.

**S-Class EOS V11.2 fixes this completely.** Operating as a **Central Deterministic Orchestration Kernel**, S-Class intercepts all agent actions, routes engineering goals through a strict Finite State Machine (FSM), enforces evidence-driven Specification Synthesis before design/coding, red-teams plans before writing code, and verifies execution authenticity through sovereign test runners and cryptographic evidence receipts before release is allowed.

> [!NOTE]
> **V11.2 LTS Release Attestation**: Formally verified across 397 product regression tests (49 test suites) covering:
> 1. Single-authority Layer-0 `FileLock` with kernel advisory locks, persistent inode identity validation, and empirical subprocess crash resilience.
> 2. Fail-closed `ArtifactGovernor` security configuration handling and non-destructive GC stale lock reclamation.
> 3. Multi-step semantic event log replay and natural runtime checkpoint equivalence.
> 4. Static AST dependency Directed Acyclic Graph (DAG) with zero circular imports across all core modules.
> 5. Sovereign `SClassTestRunner` subprocess authorization, path-traversal prevention, and shell injection blocking.
> 6. Frozen supply-chain plugin boundaries and formal `HARD_CONSTRAINT` vs. `PREFERENCE` separation.

---

## 🏛 System Architecture

```
                                RELEASE CANDIDATE
                                        │
                                        ▼
                   Central Deterministic Orchestration Kernel
                             (sclass_kernel.py FSM)
                                        │
  ┌───────────────────────┬─────────────┴────────────┬───────────────────────┐
  ▼                       ▼                          ▼                       ▼
Specification Synthesis  Spec Griller      8-Subagent Dispatch      Safety-Case Engine
 Engine (spec_synthesis) Engine            Registry                  (verifier.py)
 (Inspect Before Infer)  (sclass_grill)    (sclass_subagent_reg)             │
  │                       │                          │                       │
  └───────────────────────┴─────────────┬────────────┴───────────────────────┘
                                        │
                                        ▼
                     Sovereign Cryptographic Verification
                         (100% Authentic Execution Proofs)
```

---

## 🚀 Core Architectural Innovations

### 1. Canonical Single-Authority FileLock (`file_lock.py` - Layer 0)
Hardware-level and OS-native kernel advisory mutual exclusion file lock (`msvcrt.locking` on Windows, `fcntl.flock` on POSIX) serving as the SOLE authoritative gate for cross-process synchronization. Process crash resilience is guaranteed natively by the OS kernel automatically releasing file descriptors upon process termination. Emits atomic diagnostic owner metadata (PID, UUID token, hostname, timestamp) for audit trails and monitoring without creating unsafe secondary bypass authorities.

### 2. Strict Central Orchestration Kernel (`sclass_kernel.py` - Layer 5)
Exclusive state mutator enforcing the deterministic FSM state graph under OS `FileLock`. Enforces strict API contract invariants:
* `request_transition(event_name="triage_done")` $\to$ Valid (derives current state authoritatively from disk).
* `request_transition(event_name="triage_done", from_state="TRIAGE")` $\to$ Valid if state matches; blocks with `ValueError` on state mismatch.
* `request_transition(from_state="TRIAGE")` or empty `event_name` $\to$ **Strictly blocks with `ValueError`**. Never reinterprets `from_state` as an event name.

### 3. Multi-Step Semantic Event Replay & Natural Checkpoint Equivalence (`event_store.py`)
Append-only immutable event sourcing using canonical `EventRecord` schema. Evaluated by replaying multi-transition sequences from scratch and verifying reconstructed `currentPhase` matches live runtime state. Proves that snapshots captured naturally from disk at event offsets reconstruct identical system states to full log replays.

### 4. Specification Synthesis Engine & Anti-Bypass Gate (`spec_synthesis.py` - Layer 3)
Mandatory FSM state sitting between `ANALYSIS` and `DESIGN`. Performs multi-stage requirement expansion (`EXPLICIT`, `SUPPORTED`, `DERIVED`, `OPTIONAL`, `UNKNOWN`, `CONFLICT`, `REUSE`), runs evidence-driven capability expansion (`Role → Capability → Entity → Action → Page → UX`), enforces conservative derived rules, calculates a weighted assumption budget, and enforces an unbypassable hard gate in `verifier.py`.

### 5. Modular Production Skill Catalog & Orchestrator (`sclass_skill_orchestrator.py`)
S-Class organizes modular skill capabilities across integrated suites (Impeccable UI craft, Taste aesthetic engines, Emil animation guidelines, enterprise backend architecture, database modeling, and domain workflows), providing structured playbooks for specialized subagents.

### 6. Rule-Based Skill Discovery & Supply-Chain Boundary (`sclass_skill_discovery.py`)
Analyzes project goals and domain keywords upfront to bind approved local capability plugins. Enforces strict supply-chain boundaries by freezing arbitrary runtime cloning or external network execution.

### 7. 8-Subagent Dispatch Registry (`sclass_subagent_registry.py`)
Provides cataloged subagent profiles (`dss_governor`, `dss_ui_ux`, `dss_frontend_dev`, `dss_backend_dev`, `dss_db_architect`, `dss_cso_v2`, `dss_qa_frontend`, `dss_user_alias_v2`) equipped with specialized skill stacks and scoped role capabilities.

### 8. Zero-Infrastructure Database Fallback Guard (`zero_infra_db.py`)
Tests host database port reachability (PostgreSQL 5432, MongoDB 27017, Redis 6379). If host databases are not running on the user's computer, it automatically injects an **In-Memory SQLite** (`file:./dev.db`) driver so applications build and run out of the box with zero manual DB setup.

---

## 💻 Dedicated Execution Modes & Slash Commands

S-Class V11.2 introduces dedicated command execution modes for developer workflows:

| Slash Command / Mode | Execution Purpose | Action Performed |
| :--- | :--- | :--- |
| **`/goal [objective]`** | **Autonomous Goal Execution** | Launches full 19-state FSM execution lifecycle with subagent worker swarms and visual release gates. |
| **`/grill [spec/plan]`** | **Plan Red-Teaming Audit** | Runs `sclass_grill.py` to stress-test design specifications across 5 threat vectors before coding. |
| **`/doubt [question]`** | **Non-Interrupting Inquiry** | Answers user questions about code or architecture using read-only tools **without pausing or resetting the main task**. |
| **`/inquire [question]`** | **Read-Only Code Audit** | Queries workspace AST symbols and active FSM state safely in parallel with ongoing background tasks. |

---

## ⚡ Quick Start

### Step 1: Install or Update S-Class V11.2 (One-Line Command)

#### Windows (PowerShell):
```powershell
iex (irm -useb https://raw.githubusercontent.com/ak-bharadwaj/S-class/master/install.ps1)
```

#### Linux / macOS (Terminal):
```bash
curl -fsSL https://raw.githubusercontent.com/ak-bharadwaj/S-class/master/install.sh | bash
```

---

### Step 2: Add S-Class Configuration to Your Workspace

Create or open `.cursorrules`, `AGENTS.md`, or `CLAUDE.md` in your project root directory:

```markdown
pipeline: sclass-v5
CRITICAL DIRECTIVE: You MUST route all engineering goals strictly through S-Class EOS FSM (runtime.initialize_state & sclass_kernel.kernel_instance.request_transition). Direct parent code edits are strictly forbidden (Rule 17). Subagents MUST enforce Rule 27 No-Laziness Directive, Rule 28 Subagent Deployment Dashboard, Rule 29 Full 8 Concurrent Subagent Swarms, Rule 30 Specification Synthesis, Rule 31 Semantic Gate, and Chrome MCP multi-page visual screenshots (Rule 14 & 15).
```

---

## 🐍 30-Second Python SDK Quickstart

```python
import runtime
from sclass_kernel import kernel_instance
from sclass_grill import SpecGrillerEngine
from sclass_skill_orchestrator import SClassSkillOrchestrator
from sclass_skill_discovery import SkillDiscoveryEngine
from sclass_subagent_registry import SubagentRegistry
from spec_synthesis import SpecSynthesisEngine

# 1. Initialize S-Class FSM State
state = runtime.initialize_state(goal="Build Enterprise Application", workspace_dir="./")

# 2. Execute Specification Synthesis Engine (Inspect Before Inferring)
synth_engine = SpecSynthesisEngine()
synthesized_spec = synth_engine.run_synthesis("Build student dashboard with profile", workspace_dir="./")
print(f"Synthesized Spec Gate Result: {synthesized_spec.gate_result} (Assumption Weight: {synthesized_spec.total_assumption_weight}/10)")

# 3. Run Upfront Skill Discovery & Auto-Bind Skill Catalog
discovery = SkillDiscoveryEngine.find_and_bind_required_skills(goal_text="Build Enterprise Application", workspace_dir="./")
print(f"Bound Skills: Discovered={discovery['discovered_skills_count']}, Active={discovery['total_active_skills_bound']}")

# 4. Dispatch Full 8 Concurrent Subagent Matrix with find-skill Capability
dispatch = SubagentRegistry.prepare_full_8_subagent_dispatch(goal_text="Build Enterprise Application", fsm_phase="DEBATE", workspace_dir="./")
print(f"Dispatched {dispatch['total_subagents_dispatched']} Subagents Concurrently (Skill Discovery Active={dispatch['skill_discovery_active']})")

# 5. Dispatch FSM Transition via Central Deterministic Orchestration Kernel
res = kernel_instance.request_transition(event_name="triage_done", from_state="TRIAGE", workspace_dir="./")
print(f"Kernel Approved Mutation: '{res['previousPhase']}' ➔ '{res['currentPhase']}'")
```

---

## 📊 Framework Architectural Comparison

| Architectural Layer | OpenHands | Claude Code | Meta Muse Code | **S-Class EOS V11.2 (Deterministic Runtime)** |
| :--- | :--- | :--- | :--- | :--- |
| **System Philosophy** | Sandbox Harness | CLI Agent Loop | Model Co-Trained CLI | **Central Orchestration Kernel & Safety-Case Engine** |
| **State Mutation Guard** | File System Writes | File System Writes | File System Writes | **✅ Exclusive Kernel Mutator under OS `FileLock`** |
| **Specification Synthesis** | Generic Prompting | Generic Prompting | Generic Prompting | **✅ `SpecSynthesisEngine` + `SemanticGate` Anti-Bypass (`spec_synthesis.py`)** |
| **Modular Skill Stack** | Single Prompt Dump | Single Prompt Dump | Single Prompt Dump | **✅ Modular Skill Catalog (`sclass_skill_orchestrator.py`)** |
| **Skill Discovery Engine** | None | None | None | **✅ `SkillDiscoveryEngine` (Rule-Based Discovery)** |
| **Subagent Dispatch** | Single Worker | Single Worker | Single Worker | **✅ 8-Subagent Dispatch Registry (`SubagentRegistry`)** |
| **Verification Gate** | Heuristic | None | Heuristic | **✅ Sovereign Crypto Authority & Subprocess Runner** |
| **Zero-Infra DB Fallback** | Host DB Dependent | Host DB Dependent | Host DB Dependent | **✅ Automated `ZeroInfraDbEngine` (SQLite File Driver)** |
| **Model Independence** | Provider Dependent | Locked to Anthropic | Locked to Meta API | **✅ 100% Model Agnostic (Gemini, Claude, GPT, DeepSeek)** |
| **OS Compatibility** | Docker / Unix | Linux / macOS | Linux / macOS | **✅ Windows PowerShell, macOS, Linux Native** |

---

## 🧪 Comprehensive Automated Test Suite

S-Class EOS V11.2 contains **407 product regression test cases across 52 test suites** passing with 100% success across Python 3.10–3.14 (historical and research benchmarks isolated in `benchmark/v0/`):

| Test Module Category | Test Count | Functionality Tested |
| :--- | :--- | :--- |
| **Property & Invariant Testing** | 4 tests | Hypothesis property testing adapter verifying SPIFFE URI authority, PHI/PII redaction, and double-entry ledger zero-sum conservation (`tests/test_property_verifier.py`). |
| **API Contract Verification** | 3 tests | Schemathesis OpenAPI contract verification and behavioral fuzzing campaigns (`tests/test_api_contract_verifier.py`). |
| **Static & Type Verification** | 3 tests | Ruff static analysis quality receipts & Python type checking evidence generation (`tests/test_static_and_type_providers.py`). |
| **Audit Hardening & Concurrency** | 10 tests | Portalocker cross-platform locking, live planner/MCP dispatch, fail-closed governor security, multi-process GC lock reclamation race safety (`tests/test_audit_hardening_verification.py`). |
| **V11.2 Stabilization Pass** | 12 tests | Canonical event replay, LibCST AST dependency DAG, kernel API contract strictness, subprocess crash resilience, SClassTestRunner boundaries, supply-chain freeze (`tests/test_v11_stabilization.py`). |
| **Master Production Closure** | 6 tests | Whole-system V9.6 $\to$ V11.2 master closure: task compiler, execution planner, repository snapshot, ChangeSet reconciliation, implementation/verification evidence (`tests/test_v11_master_closure.py`). |
| **World Model & Adapters** | 33 tests | Sovereign PromotionEngine, LanguageAdapters (Python, JS/TS, Fallback), GroundedSpecWeaver, Evidence Verification (`tests/test_v11_world_model.py`). |
| **ChangeSet Governance** | 28 tests | Sovereign ChangeSet issuance, boundary enforcement, atomic diff reconciliation (`tests/test_v11_changeset_governance.py`). |
| **Repository Snapshot** | 18 tests | Deterministic tree hashing, file classification, language discovery, ChangeSet diffing (`tests/test_v11_repository_snapshot.py`). |
| **Execution Planner (V10)** | 26 tests | Topological task ordering, concurrency barriers, resource locking, batch compilation (`tests/test_v10_execution_planner.py`). |
| **Epistemic & Adversarial Matrix** | 45 tests | Red-team audits, adversarial FSM transitions, metamorphic debate, failure injection (`tests/test_v9_6_*.py`). |
| **Specification Synthesis** | 30 tests | Evidence-driven expansion, conservative inference, semantic gate, assumption budget (`tests/test_spec_synthesis.py`). |
| **Kernel & Event Sourcing** | 15 tests | Central deterministic kernel state mutator, event sourcing replay, natural snapshot checkpointing (`tests/test_kernel.py`, `tests/test_replay.py`, `tests/test_eos_core.py`). |
| **Core Architecture & QA** | 44 tests | Multi-subagent dispatch, skill orchestrator, Chrome QA, security shield, runtime FSM (`tests/test_runtime.py`, `tests/test_subagent_registry.py`, `tests/test_robust_qa.py`). |

---

## 🔒 License & Legal Notice

**Copyright (c) 2026 ak-bharadwaj. All Rights Reserved.**

S-Class EOS V11.2 is **Proprietary and Confidential Software**. 

Unauthorized copying, modification, redistribution, sublicensing, deployment, or public hosting of this Software, via any medium, is strictly prohibited. Access and usage are granted exclusively under explicit written authorization by the copyright holder (`ak-bharadwaj`). See [LICENSE](LICENSE) for full details.
