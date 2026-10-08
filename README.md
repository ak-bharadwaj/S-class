<div align="center">

# ⚡ S-CLASS EOS v6
### Adaptive Engineering Guard & Deterministic Cognitive Control Plane

*Detects and gates AI coding agent hallucination with deterministic verification, dynamically selects the right FSM path and subagents, enforces evidence verification gates, and synchronizes cross-platform state across Cursor, GitHub Copilot, Claude Code, OpenAI Codex CLI, Windsurf, and Google Antigravity.*

[![Version](https://img.shields.io/badge/version-6.0.0-blue.svg)](https://github.com/ak-bharadwaj/S-class/tree/working-pre-d0)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-green.svg)](https://github.com/ak-bharadwaj/S-class/tree/working-pre-d0)
[![Tests](https://img.shields.io/badge/tests-385%20passing-brightgreen.svg)](https://github.com/ak-bharadwaj/S-class/tree/working-pre-d0)
[![License](https://img.shields.io/badge/license-Source--Available-green.svg)](LICENSE)

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
- **Deterministic Evidence Verification:** Content-addressed SHA-256 verification receipts and automated test execution assert that claims reflect verifiable reality.

---

## 🎯 Adaptive Workflow Profiles

S-Class dynamically classifies tasks into tailored workflows using multi-signal scoring:

| Profile | Target Tasks | State Sequence | Subagents | Typical Duration |
| :--- | :--- | :--- | :--- | :--- |
| **`QUESTION`** | Informational queries, architecture questions | *Direct answer (Bypasses FSM)* | 0 | Instant |
| **`MICRO`** | Typos, renames, single-line/CSS tweaks | `TRIAGE` → `CODING` → `DONE` | 0 (direct) | < 30 sec |
| **`SMALL_FIX`** | Targeted bug fixes, minor components | `TRIAGE` → `ANALYSIS` → `CODING` → `TASK_VERIFICATION` → `DONE` | 0 | 1–3 min |
| **`CORE`** | Pure algorithms, libraries, CLI utilities | `TRIAGE` → `ANALYSIS` → `SPEC_SYNTHESIS` → `CODING` → `TASK_VERIFICATION` → `QA` → `DONE` | 2 (builder + QA) | 3–5 min |
| **`RESEARCH`** | Architecture research, audits, exploration | `TRIAGE` → `ANALYSIS` → `SPEC_SYNTHESIS` → `DESIGN` → `DEBATE` → `DONE` | 2–3 | 5–10 min |
| **`HOTFIX`** | Emergency crash repairs | `TRIAGE` → `CODING` → `TASK_VERIFICATION` → `MERGE` → `INTEGRATION` → `QA` → `RELEASE` → `MONITORING` → `DONE` | 2 (builder + QA) | 2–5 min |
| **`BUG_FIX`** | Functional bug fixes, regression repairs | `TRIAGE` → `ANALYSIS` → `SPEC_SYNTHESIS` → `CODING` → `TASK_VERIFICATION` → `MERGE` → `INTEGRATION` → `QA` → `RELEASE` → `MONITORING` → `DONE` | 2–3 (builder + QA ± security) | 3–8 min |
| **`FAST`** | Accelerated feature convergence (`/boost`) | `TRIAGE` → `ANALYSIS` → `SPEC_SYNTHESIS` → `CODING` → `TASK_VERIFICATION` → `MERGE` → `INTEGRATION` → `QA` → `RELEASE` → `MONITORING` → `DONE` | 2–3 | 5–10 min |
| **`REFACTOR`** | Structural code refactoring | `TRIAGE` → `ANALYSIS` → `SPEC_SYNTHESIS` → `DESIGN` → `CODING` → `TASK_VERIFICATION` → `MERGE` → `INTEGRATION` → `QA` → `RELEASE` → `MONITORING` → `DONE` | 2–3 | 5–12 min |
| **`FULL`** | Greenfield products, multi-feature systems | Full 15-state pipeline with multi-agent debate and governance | 3–5 | Thorough |

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

### 1. Adaptive Subagent Selector (0 to 5 per task, not 24)
Rather than spawning 8–24 rigid personas for every task, `subagent_selector.py` dynamically composes 8 specialist roles (`architect`, `builder`, `frontend`, `database`, `qa`, `security`, `reviewer`, `analyst`) based on detected domains (`frontend`, `backend`, `database`, `security`). Simple and micro tasks spawn **zero** subagents, completely removing overhead. For code-writing tasks, the engine strictly enforces the single Lead Writer constraint (only 1 subagent holds write authority, preventing conflicting code diffs).

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

### 6. Cross-Platform Context Projection & MCP Integration
Synchronizes a single verified state and native MCP server plugins across all 6 supported developer platforms:
- **Cursor**: `.cursorrules`, `.cursor/rules/sclass-governance.mdc`, and `.cursor/mcp.json`
- **Claude Code**: `CLAUDE.md`, `.claude/mcp.json`, and `.claude/hooks`
- **OpenAI Codex CLI**: `AGENTS.md`, `.codex/mcp.json`, and `.codex/hooks`
- **Google Antigravity / Gemini**: `GEMINI.md`, `.agents/mcp.json`, and `.gemini/mcp_config.json`
- **GitHub Copilot**: `.github/copilot-instructions.md` and `.github/hooks`
- **Windsurf**: `.windsurfrules` and `.windsurf/hooks`
- **Handoff Receipts**: `CONTINUE_HERE.md` and `session_handoff.json`

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

### 1. Environment Setup (Isolated Virtual Environment)
```bash
# Clone and enter the repository
git clone https://github.com/ak-bharadwaj/S-class.git
cd S-class

# Create and activate an isolated virtual environment
python -m venv .venv
source .venv/bin/activate       # On Linux/macOS
# .venv\Scripts\activate       # On Windows PowerShell

# Install dependencies and S-Class in editable mode (registers `sclass` executable)
pip install -e .
```

### 2. Goal Execution & Real-Time Monitoring
```bash
# Classify an engineering goal
sclass classify "fix typo in navigation button"
# Or run directly via Python: python sclass_cli.py classify "fix typo in navigation button"

# Fast-track high-velocity boost with Codebase Knowledge Graph pre-indexing
sclass /boost "optimize database connection pool"

# Check active FSM phase and governance status
sclass /status

# Launch live monitoring dashboard
sclass watch
```

### 3. Deploy Zero-Bypass Hooks (Cursor, Antigravity, Copilot, Claude Code, Codex, Windsurf)
```bash
sclass install --platform all --strict --git-hook
```

---

## 🐍 30-Second Python SDK Quickstart

```python
from sdk_interface import SClassSDK

# 1. Initialize S-Class SDK pointed at any target workspace
sdk = SClassSDK(workspace_dir="/path/to/my-project")

# 2. Run an Adaptive Goal Pipeline (Governance & FSM State Driver)
result = sdk.execute_goal(goal="fix button color styling in navbar")
print(f"Execution Status: {result['status']}")  # Returns COMPLETED (live agent) or SIMULATED (headless test runner)
print(f"FSM State Transitions: {len(result.get('history', []))}")

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

## 🔒 License & Intellectual Property

**Copyright (c) 2026 ak-bharadwaj. All Rights Reserved.**

S-Class EOS v6 is released under the **Source-Available Community & Evaluation License**. 
Public inspection, non-commercial research, prospective investor evaluation, and architectural testing are permitted. Commercial production use, SaaS hosting, or redistributing requires an explicit enterprise commercial license from the copyright holder (`ak-bharadwaj`). See [LICENSE](LICENSE) for full terms.


## 🎪 Expo Quick Start (60-Second Investor Demo)
1. **Goal Classification**: `sclass classify "Add unit tests for pricing module"` (shows Profile: CORE, 7 states, 2 subagents).
2. **Micro Speed**: `sclass classify "Fix typo in README"` (shows Profile: MICRO, 3 states, 0 subagents).
3. **Live Interception**: `python -m pytest tests/integration/test_hook_interception_live.py -v` (proves zero-trust blocking of leaked secrets & fake completion trapping).
4. **Interactive Dashboard**: `sclass watch` (terminal dashboard).
5. **Cross-Platform Install**: `sclass install --platform all --strict --git-hook` (registers hooks across Cursor, Antigravity, Copilot, Claude, Codex, Windsurf).
