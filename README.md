<div align="center">

# ⚡ S-CLASS EOS V12.1
### The Deterministic AI Systems Runtime & Safety-Case Engine

*Enterprise-grade execution microkernel that eliminates AI agent drift, blocks broken UI releases, and enforces multi-page visual evidence verification.*

[![Version](https://img.shields.io/badge/version-12.0.0-blue.svg)](https://github.com/ak-bharadwaj/S-class)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-green.svg)](https://github.com/ak-bharadwaj/S-class)
[![Build](https://img.shields.io/badge/tests-91%2F91%20passing-brightgreen.svg)](https://github.com/ak-bharadwaj/S-class)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)

[Quick Start](#-quick-start) • [Architecture](#-system-architecture) • [Features](#-core-architectural-innovations) • [Python SDK](#-30-second-python-sdk-quickstart) • [Benchmark Comparison](#-framework-architectural-comparison) • [License](#-license)

---

</div>

## 📌 Executive Overview

When autonomous AI coding agents (such as Claude Code, Cursor, or OpenHands) execute software engineering tasks, they suffer from 3 critical failure modes:
1. **Agent Drift:** They get stuck in repetitive loops, forget requirements mid-flight, or perform unverified direct file edits.
2. **Fake Verification:** They claim *"Everything works cleanly!"* based on unit tests or build logs, while the actual web interface renders broken components, `undefined`/`NaN` text, or HTTP 500 errors.
3. **Sparse & Amateur UIs:** They build unstyled HTML templates with default browser fonts and empty 1-row data tables.

**S-Class EOS V12.0 fixes this completely.** Operating as an **Authoritative Execution Microkernel**, S-Class intercepts all agent actions, routes engineering goals through a strict 11-state Finite State Machine (FSM), red-teams plans before writing code, and verifies live web applications visually using Chrome DevTools MCP before release is allowed.

---

## 🏛 System Architecture

```
                                RELEASE CANDIDATE
                                        │
                                        ▼
                           Deterministic Microkernel
                            (sclass_kernel.py FSM)
                                        │
      ┌────────────────────────┬────────┴────────┬────────────────────────┐
      ▼                        ▼                 ▼                        ▼
Workspace Pre-Flight    Spec Griller      Subagent Swarm           Safety-Case Engine
 Scanner                Engine            Worker Pool               (verifier.py)
 (workspace_digest)     (sclass_grill)    (dss_builder_v2)                │
      │                        │                 │                        │
      └────────────────────────┴────────┬────────┴────────────────────────┘
                                        │
                                        ▼
                    Chrome MCP Multi-Page Visual Verification
                       (100% PNG & User Flow Receipts)
```

---

## 🚀 Core Architectural Innovations

### 1. Pre-Flight Spec Griller Engine (`sclass_grill.py`)
Inspired by Meta AI's plan stress-testing workflows, `sclass_grill.py` automatically evaluates design specifications against **5 heavy benchmark threat vectors** during the `DEBATE` phase:
* **Concurrency & Race Conditions:** Audits async submit triggers, button loading/disabled states, and atomic DB transactions.
* **Database Schema Integrity:** Verifies foreign key constraints, migration boundaries, and relational indexing.
* **UI Null & Undefined Safety:** Audits component error boundaries, empty-state fallbacks, and checks for raw `[object Object]` / `NaN` placeholders.
* **API Signature Completeness:** Verifies explicit HTTP verbs, request/response DTO schemas, and controller signatures.
* **Security & Auth Guarding:** Verifies Zod/Pydantic input validation and authentication route guards.

### 2. Live Input-to-Output User Flow Verification (`user_flow_receipts.json`)
The User Proxy agent (`dss_user_alias_v2`) is strictly forbidden from signing off on QA or Release based on static screenshots alone. It MUST execute live form submissions using Chrome DevTools MCP tools (`fill`, `click`, `submit`) and verify that submitted data **actually renders visually on the screen output view**.

### 3. Visual DOM Error Token Sanitization
S-Class automatically scans rendered HTML and DOM Accessibility trees for visual error indicators (`500 Internal Server Error`, `404 Not Found`, `TypeError:`, `Failed to fetch`, `Unhandled Runtime Error`, `Connection Refused`). If any error token is detected on screen, release is **HARD-BLOCKED**.

### 4. AST Dependency Resolver (`ast_dependency_resolver.py`)
Scans generated JavaScript, TypeScript, and Python code for imported packages (`lucide-react`, `framer-motion`, `zod`, `axios`, `express`, `cors`) and automatically syncs missing dependencies into `package.json` and `requirements.txt` upfront.

### 5. Zero-Infrastructure Database Fallback Guard (`zero_infra_db.py`)
Tests host database port reachability (PostgreSQL 5432, MongoDB 27017, Redis 6379). If host databases are not running on the user's computer, it automatically injects an **In-Memory SQLite** (`file:./dev.db`) driver so applications build and run out of the box with zero manual DB setup.

### 6. Full Workspace Pre-Flight Scanner (`workspace_preflight_scanner.py`)
Performs a 100% workspace file scan upfront, extracting AST symbol trees, exported functions, environment variable keys, and package dependencies into `.agents/workspace_digest.json` to eliminate AI context blind spots.

---

## 💻 Dedicated Execution Modes & Slash Commands

S-Class V12.0 introduces dedicated command execution modes for developer workflows:

| Slash Command / Mode | Execution Purpose | Action Performed |
| :--- | :--- | :--- |
| **`/goal [objective]`** | **Autonomous Goal Execution** | Launches full 11-state FSM execution lifecycle with subagent worker swarms and visual release gates. |
| **`/grill [spec/plan]`** | **Plan Red-Teaming Audit** | Runs `sclass_grill.py` to stress-test design specifications across 5 threat vectors before coding. |
| **`/doubt [question]`** | **Non-Interrupting Inquiry** | Answers user questions about code or architecture using read-only tools **without pausing or resetting the main task**. |
| **`/inquire [question]`** | **Read-Only Code Audit** | Queries workspace AST symbols and active FSM state safely in parallel with ongoing background tasks. |

---

## ⚡ Quick Start

### Step 1: Install or Update S-Class V12.0 (One-Line Command)

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
CRITICAL DIRECTIVE: You MUST route all engineering goals strictly through S-Class EOS FSM (runtime.initialize_state & runtime.dispatch_event). Direct parent code edits are strictly forbidden (Rule 17). Subagents MUST enforce Rule 16 UI/UX design tokens and Chrome MCP multi-page visual screenshots (Rule 14 & 15).
```

---

### Step 3: Run S-Class in Chat

Simply enter your goal or command in your AI assistant prompt:

```bash
# Example 1: Full Application Project
"Build a Driving Academy Portal with student booking, instructor scheduling, and admin analytics following sclass"

# Example 2: Plan Red-Teaming Audit
"/grill Verify authentication route guards and database migration boundaries"

# Example 3: Non-Interrupting Doubt Inquiry (Main task continues in background)
"/doubt What database schema are we using for instructor schedules?"
```

---

## 🐍 30-Second Python SDK Quickstart

```python
import runtime
from sclass_kernel import kernel_instance
from sclass_grill import SpecGrillerEngine
from ast_dependency_resolver import ASTDependencyResolver
from zero_infra_db import ZeroInfraDbEngine
from verifier import OutputContractVerifier

# 1. Initialize S-Class FSM State
state = runtime.initialize_state(goal="Build Driving Academy Portal", workspace_dir="./")
print(f"FSM State Initialized: Phase='{state.currentPhase}', Profile='{state.workflowProfile}'")

# 2. Run Pre-Flight Spec Grilling Red-Teaming Engine
grill_report = SpecGrillerEngine.grill_specification(workspace_dir="./")
print(f"Plan Red-Teaming Result: Passed={grill_report.overall_passed} (Critical Defects={grill_report.critical_defects_found})")

# 3. Auto-Resolve Missing Package Dependencies & DB Drivers
dep_res = ASTDependencyResolver.resolve_workspace_dependencies(workspace_dir="./")
db_res = ZeroInfraDbEngine.audit_and_fallback_database(workspace_dir="./")
print(f"Auto-Injected Packages: {dep_res['npm_packages_injected']}")
print(f"Zero-Infra DB Driver: {db_res['fallbacks_applied']}")

# 4. Dispatch FSM Transition via Deterministic Microkernel
res = kernel_instance.request_transition(from_state="TRIAGE", event_name="triage_complete", workspace_dir="./")
print(f"Kernel Approved Mutation: '{res['previousPhase']}' ➔ '{res['currentPhase']}'")
```

---

## 📊 Framework Architectural Comparison

| Architectural Layer | OpenHands | Claude Code | Meta Muse Code | **S-Class V12.0 (Deterministic Runtime)** |
| :--- | :--- | :--- | :--- | :--- |
| **System Philosophy** | Sandbox Harness | CLI Agent Loop | Model Co-Trained CLI | **Deterministic Microkernel & Safety-Case Engine** |
| **State Mutation Guard** | File System Writes | File System Writes | File System Writes | **✅ Exclusive Kernel Mutator (`sclass_kernel.py`)** |
| **Pre-Flight Plan Red-Teaming** | None | None | Interactive `/grill` | **✅ Automated 5-Vector `SpecGrillerEngine`** |
| **Visual Evidence Gate** | Heuristic | None | Heuristic | **✅ Chrome DevTools MCP + PNG Magic Header + User Flow Receipts** |
| **Visual DOM Error Parsing** | None | None | None | **✅ Sanitizes `500 Server Error`, `TypeError`, `Failed to fetch`** |
| **Missing Package Resolution** | Manual Error Retry | Manual Error Retry | Manual Error Retry | **✅ Automated `ASTDependencyResolver` (`package.json` Sync)** |
| **Zero-Infra DB Fallback** | Host DB Dependent | Host DB Dependent | Host DB Dependent | **✅ Automated `ZeroInfraDbEngine` (SQLite File Driver)** |
| **Model Independence** | Provider Dependent | Locked to Anthropic | Locked to Meta API | **✅ 100% Model Agnostic (Gemini, Claude, GPT, DeepSeek)** |
| **OS Compatibility** | Docker / Unix | Linux / macOS | Linux / macOS | **✅ Windows PowerShell, macOS, Linux Native** |

---

## 🧪 Comprehensive Automated Test Suite

S-Class V12.0 contains **91 automated unit and integration tests** passing with 100% success across Python 3.10–3.14:

| Test Module File | Test Count | Functionality Tested |
| :--- | :--- | :--- |
| `tests/test_v12_engines.py` | 3 tests | Automated AST dependency resolution, zero-infra DB fallbacks, port conflict resolution. |
| `tests/test_spec_griller.py` | 2 tests | 5-vector threat audit, red-teaming report generation, critical defect detection. |
| `tests/test_robust_qa.py` | 13 tests | Chrome DevTools DOM sanitization, user flow receipts, duplicate screenshot detection, Lighthouse audits. |
| `tests/test_benchmarks.py` | 1 test | 50-scenario empirical quality benchmark (30% unit test vs 100% S-Class defect detection). |
| `tests/test_eos_core.py` | 15 tests | Decoupled RiskEngine/PolicyEngine, SafetyCase, Output Evidence Pack, SHA-256 tamper hashing. |
| `tests/test_kernel.py` | 6 tests | Microkernel state mutator, event sourcing replay, tri-partite memory, resource scheduler. |
| `tests/test_intent_contract.py` | 4 tests | Composable contracts, OutputContractSpec v2.1 serialization, typed predicates. |
| `tests/test_planner.py` | 9 tests | Meta-Planner workflow profile selection (`FULL`, `BUG_FIX`, `RESEARCH`, `REFACTOR`, `HOTFIX`). |
| `tests/test_runtime.py` | 9 tests | FSM state initialization, schema validation, event dispatching, FileLock hardware mutual exclusion. |
| `tests/test_memory_semantic.py` | 6 tests | Semantic TF-IDF vector similarity search, memory schema v2 auto-migration. |
| `tests/test_security_shield.py` | 4 tests | Secret scanning, dangerous AST pattern detection, vulnerability report generation. |
| `tests/test_topology.py` | 5 tests | Subagent network topologies (`WorkerMeshPool`, Star, Mesh, Ring phase resolution). |

---

## 🔒 License & Legal Notice

**Copyright (c) 2026 ak-bharadwaj. All Rights Reserved.**

S-Class EOS V12.0 is **Proprietary and Confidential Software**. 

Unauthorized copying, modification, redistribution, sublicensing, deployment, or public hosting of this Software, via any medium, is strictly prohibited. Access and usage are granted exclusively under explicit written authorization by the copyright holder (`ak-bharadwaj`). See [LICENSE](LICENSE) for full details.
