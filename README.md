<div align="center">

# ⚡ S-CLASS EOS v6
### Adaptive Engineering Guard & Deterministic Cognitive Control Plane

*Eliminates AI coding agent hallucination, dynamically selects the right FSM path and subagents, enforces evidence verification gates, and synchronizes cross-platform state across Cursor, Claude Code, OpenAI Codex CLI, and Google Antigravity.*

[![Version](https://img.shields.io/badge/version-6.0.0-blue.svg)](https://github.com/ak-bharadwaj/S-class/tree/working-pre-d0)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-green.svg)](https://github.com/ak-bharadwaj/S-class/tree/working-pre-d0)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](https://github.com/ak-bharadwaj/S-class/tree/working-pre-d0)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)

[Quick Start](#-quick-start) • [Adaptive Workflows](#-adaptive-workflow-profiles) • [Architecture](#-system-architecture) • [Features](#-core-architectural-innovations) • [Python SDK](#-30-second-python-sdk-quickstart) • [Roadmap](#-roadmap) • [License](#-license)

---

</div>

## 📌 Executive Overview

When autonomous AI coding agents execute software engineering tasks, they suffer from 4 critical failure modes:
1. **Agent Drift & Hallucinated Scaffolding:** Inventing unrequested features, ignoring existing project patterns, and hallucinating external dependencies.
2. **Fake / Unearned Verification:** Claiming *"All tests pass and the task is verified!"* when either zero assertions exist on disk or code was never run.
3. **One-Size-Fits-All Overhead:** Treating a 1-line typo fix with the same heavy ceremony, 15 states, and 8 subagents as building a full-stack SaaS platform.
4. **Context Window Exhaustion:** Bloating every turn with massive rule dumps instead of loading phase-relevant instructions.

**S-Class v6 fixes this through Adaptive Intelligence:**
- **Dynamic FSM Path Selection:** 1-line typo fixes take 3 states and 0 subagents (<30s). Complex products get thorough 15-state architecture and debate.
- **Spec-Grounded Coding & Diff Auditing:** Enforces *Inspect Before Infer* and scans diffs for scope creep, weakened tests, and secrets.
- **Phase-Specific Context Diet:** Injects only 40–80 lines of relevant instructions per turn instead of 400 lines of shouting.
- **Tamper-Evident Evidence Verification:** SHA-256 hashing and deterministic assertions guarantee that claims reflect verifiable reality.

---

## 🎯 Adaptive Workflow Profiles

S-Class dynamically classifies tasks into tailored workflows using multi-signal scoring:

| Profile | Target Tasks | State Sequence | Subagents | Typical Duration |
| :--- | :--- | :--- | :--- | :--- |
| **`QUESTION`** | Informational queries, architecture questions | *Direct answer (Bypasses FSM)* | 0 | Instant |
| **`MICRO`** | Typos, renames, single-line/CSS tweaks | `TRIAGE` → `CODING` → `DONE` | 0 (direct) | < 30 sec |
| **`SMALL_FIX`** | Targeted bug fixes, minor components | `TRIAGE` → `ANALYSIS` → `CODING` → `TASK_VERIFICATION` → `DONE` | 0 | 1–3 min |
| **`BUG_FIX`** | Functional bug fixes, regression repairs | `TRIAGE` → `ANALYSIS` → `SPEC` → `CODING` → `VERIFICATION` → `QA` → `RELEASE` → `DONE` | 2 (builder + QA) | 3–8 min |
| **`CORE`** | Pure algorithms, libraries, CLI utilities | `TRIAGE` → `ANALYSIS` → `SPEC` → `CODING` → `VERIFICATION` → `QA` → `DONE` | 1–2 | 3–5 min |
| **`HOTFIX`** | Emergency production crash repairs | `TRIAGE` → `CODING` → `VERIFICATION` → `QA` → `RELEASE` → `DONE` | 2 | 2–5 min |
| **`FAST`** | Accelerated feature convergence (`/boost`) | Accelerated bypass pipeline | 2–3 | 5–10 min |
| **`REFACTOR`** | Structural code refactoring | `TRIAGE` → `ANALYSIS` → `DESIGN` → `CODING` → `VERIFICATION` → `QA` → `DONE` | 2–3 | 5–12 min |
| **`FULL`** | Complex multi-feature greenfield products | Full 15-state pipeline with multi-agent debate | 3–5 | Thorough |

---

## 🏛 System Architecture

```
                                 ENGINEERING GOAL / COMMAND
                                (/goal, /boost, /learn, /grill)
                                             │
                                             ▼
                       TaskSignals Classifier & MetaPlanner (planner.py)
                       (Determines Profile: MICRO, SMALL_FIX, FULL...)
                                             │
                                             ▼
                                Deterministic Microkernel
                                  (runtime.py State Engine)
                                             │
   ┌──────────────────────┬──────────────────┴─────────────────┬──────────────────────┐
   ▼                      ▼                                    ▼                      ▼
Dynamic Subagents     Specification Synthesis              Diff Auditor           Multi-Tier Verifier
(subagent_selector)   Engine (spec_synthesis.py)           (diff_auditor.py)      Fortress (verifier.py)
(0 to 5 per domain)   (Inspect Before Infer)               (Scope & Test Checks)  (Incremental & Visual)
   │                      │                                    │                      │
   ▼                      ▼                                    ▼                      ▼
Token Budget Guard    FastMCP Graph Server                Modular Instructions   Anti-Cheating Visual QA
(token_budget.py)     (codebase_kg_server.py)             (instructions/*.md)    (Real DOM & Variance)
   │                                                                                  │
   └─────────────────────────────────────────┬────────────────────────────────────────┘
                                             │
                                             ▼
                         Cross-Platform Context Projection & Handoff
                     (.cursorrules, CLAUDE.md, AGENTS.md, GEMINI.md, CONTINUE_HERE.md)
```

---

## 🚀 Core Architectural Innovations

### 1. Adaptive Subagent Selector (3–5 per task, not 24)
Rather than spawning 8–24 rigid personas for every task, `subagent_selector.py` composes 6 core roles (`architect`, `builder`, `qa`, `security`, `reviewer`, `analyst`) dynamically based on detected domains (`frontend`, `backend`, `database`, `security`). Simple and micro tasks spawn **zero** subagents, completely removing overhead.

### 2. Diff-Audit Verification Gate (`diff_auditor.py`)
After each coding pass, diffs are automatically checked against the intent contract:
- **Scope Creep Detection:** Flags edits outside authorized target files.
- **Weakened Test Detection:** Forbids deleting or commenting out existing assertions.
- **Secret Hygiene:** Detects leaked API keys, tokens, and hardcoded credentials.

### 3. Modular Phase-Specific Instructions (`instructions/`)
monolithic shouting rules are replaced with modular, concise instructions loaded strictly when their phase is active:
- `instructions/core.md` (Cardinal Rule: Inspect Before Infer, Fast-Path bypass)
- `instructions/triage.md`, `analysis.md`, `spec_synthesis.md`, `design.md`, `debate.md`
- `instructions/coding.md`, `qa.md`, `release.md`, `micro.md`
Saves 80–90% of token context on simple turns.

### 4. Incremental Verification Engine
Instead of re-verifying the entire repository from scratch on every iteration, `IncrementalVerifier` tracks workspace snapshots and targets only modified source and test files.

### 5. Codebase Knowledge Graph (CKG)
Embedded SQLite graph database with AST entity extraction (classes, functions, routes, schemas) and recursive Common Table Expressions (`WITH RECURSIVE`) for multi-hop dependency traversals and cycle-free blast-radius impact analysis.

### 6. Cross-Platform Context Projection
Synchronizes a single verified state into the native formats of each major AI tool:
- **Cursor**: `.cursorrules` & `.cursor/rules/*.mdc`
- **Claude Code**: `CLAUDE.md`
- **OpenAI Codex CLI**: `AGENTS.md`
- **Google Antigravity / Gemini**: `GEMINI.md`
- **Handoff Receipt**: `CONTINUE_HERE.md` and `session_handoff.json`

---

## 💻 Dedicated Execution Modes & Slash Commands

| Slash Command | Execution Purpose | Action Performed |
| :--- | :--- | :--- |
| **`/goal [objective]`** | **Adaptive Goal Execution** | Selects optimal profile, executes FSM lifecycle, and verifies evidence. |
| **`/boost [task/goal]`** | **High-Velocity Swarm Boost** | Pre-indexes codebase into CKG, applies token budget controls, and accelerates goal convergence. |
| **`/learn [pattern/fix]`** | **Automated Learning & KB Engine** | Captures bug fixes and architectural patterns into learning memory. |
| **`/status`** | **FSM Pipeline Inspection** | Returns real-time FSM phase, task statuses, transition history, and active governance receipts. |
| **`/advance`** | **Step-by-Step FSM Driver** | Advances the FSM forward one validated state transition. |
| **`/grill [spec/plan]`** | **Plan Red-Teaming Audit** | Runs `sclass_grill.py` to stress-test design specifications across 5 threat vectors before coding. |
| **`/doubt [question]`** | **Non-Interrupting Inquiry** | Queries codebase symbols and architecture safely in parallel with ongoing background tasks. |
| **`/inquire [question]`** | **Read-Only Symbol Query** | Queries workspace AST symbols, dependencies, and active FSM state safely. |

---

## ⚡ Quick Start

```bash
# 1. Execute an adaptive goal on any project
python sclass_cli.py -w /path/to/my-project /goal "fix typo in navigation button"

# 2. Fast-track high-velocity boost with Codebase Knowledge Graph pre-indexing
python sclass_cli.py -w /path/to/my-project /boost "optimize database connection pool"

# 3. Check active FSM phase and governance status
python sclass_cli.py -w /path/to/my-project /status
```

---

## 🐍 30-Second Python SDK Quickstart

```python
from sdk_interface import SClassSDK

# 1. Initialize S-Class SDK pointed at any target workspace
sdk = SClassSDK(workspace_dir="/path/to/my-project")

# 2. Run an Adaptive Goal
result = sdk.execute_goal(goal="fix button color styling in navbar")
print(f"Execution Status: {result['status']}")
print(f"Source Files Generated/Modified: {result.get('source_files', [])}")

# 3. Cross-Platform Context Projection
sdk.project_rules()
```

---

## 🗺 Roadmap

The following enterprise isolation and policy backends are on the roadmap for future releases:
- **gVisor / Kernel Virtualization (`runsc`)**: Container sandboxing for arbitrary untrusted code execution.
- **Open Policy Agent (OPA / Rego)**: External declarative policy enforcement for enterprise compliance.
- **OCI Container Runtimes**: Direct Docker/Podman isolation wrappers for agent execution sandboxes.
- **Dagger Pipelines**: Declarative containerized CI/CD verification workflows.

---

## 🔒 License & Legal Notice

**Copyright (c) 2026 ak-bharadwaj. All Rights Reserved.**

S-Class EOS v6 is **Proprietary and Confidential Software**. 
Unauthorized copying, modification, redistribution, sublicensing, deployment, or public hosting of this Software, via any medium, is strictly prohibited. Access and usage are granted exclusively under explicit written authorization by the copyright holder (`ak-bharadwaj`). See [LICENSE](LICENSE) for full details.
