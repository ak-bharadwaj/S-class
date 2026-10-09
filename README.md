<div align="center">

# ⚡ S-CLASS EOS v6
### Adaptive Engineering Guard & Deterministic Cognitive Control Plane

*Detects and gates AI coding agent hallucination with deterministic verification, dynamically selects the right FSM path and subagents, enforces evidence verification gates, and synchronizes cross-platform state across VS Code, Cursor, GitHub Copilot, Claude Code, OpenAI Codex CLI, Windsurf, and Google Antigravity.*

[![Version](https://img.shields.io/badge/version-6.0.0-blue.svg)](https://github.com/ak-bharadwaj/S-class/tree/working-pre-d0)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-green.svg)](https://github.com/ak-bharadwaj/S-class/tree/working-pre-d0)
[![CI](https://github.com/ak-bharadwaj/S-class/actions/workflows/ci.yml/badge.svg?branch=working-pre-d0)](https://github.com/ak-bharadwaj/S-class/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-409%20passing-brightgreen.svg)](https://github.com/ak-bharadwaj/S-class/tree/working-pre-d0)
[![VS Code Extension](https://img.shields.io/badge/VS%20Code-v1.0.0%20VSIX-purple.svg)](editors/vscode/)
[![License](https://img.shields.io/badge/license-Source--Available-green.svg)](LICENSE)

[Quick Start](#-quick-start) • [Live Verification](#-60-second-live-verification-walkthrough) • [Adaptive Profiles](#-adaptive-workflow-profiles) • [VS Code Extension](#-vs-code-native-control-plane) • [Architecture](#-system-architecture) • [Features](#-core-architectural-innovations) • [Python SDK](#-30-second-python-sdk-quickstart) • [License](#-license)

---

</div>

## 📌 Executive Overview

When autonomous AI coding agents execute enterprise software engineering tasks, they consistently suffer from 4 critical failure modes:

1. **Agent Drift & Hallucinated Scaffolding:** Inventing unrequested features, ignoring existing project conventions, and hallucinating external npm/PyPI dependencies.
2. **Fake / Unearned Verification:** Declaring *"All tests pass and the task is verified!"* when either zero assertions exist on disk, tests were bypassed with `@pytest.mark.skip`, or code was never run.
3. **One-Size-Fits-All Overhead:** Treating a 1-line typo fix with the same heavy ceremony, 15 states, and 8 subagents as building a full-stack database-backed application.
4. **Context Window Exhaustion:** Bloating every agent turn with 400+ lines of monolithic shouting rules instead of loading phase-relevant, concise instructions.

**S-Class v6 solves this through Adaptive Intelligence & Deterministic Governance:**
- **Dynamic FSM Path Selection:** 1-line typo fixes execute in 3 states and 0 subagents (<30s). Complex architecture changes get a thorough 15-state pipeline with multi-agent debate and governance.
- **Spec-Grounded Coding & Diff Auditing:** Enforces *Inspect Before Infer* and scans diffs for scope creep, weakened test assertions, and secret leaks.
- **Phase-Specific Context Diet:** Injects only 40–80 lines of targeted instructions per turn instead of massive rule dumps, reducing context consumption by 85%.
- **Deterministic Evidence Verification:** Content-addressed SHA-256 verification receipts and automated test execution assert that all completion claims reflect verifiable disk reality.

---

## ⚡ 60-Second Live Verification Walkthrough

Experience the core capabilities of S-Class in under 60 seconds using these reproduction commands:

### 1. Zero-Trust Live Security & Anti-Cheating Interception
Run the live interception test suite to observe S-Class blocking an agent attempting to leak API keys and trapping an agent attempting fake completion:
```bash
python -m pytest tests/integration/test_hook_interception_live.py -v
```
> **Expected Result:** `PASS` across all cases. Verifies that `hook_runner` strictly denies pre-tool execution on secrets and forces `decision: continue` on unverified completion claims.

### 2. Adaptive Profiling & Dynamic Fast-Path Routing
Test how S-Class classifies tasks into optimal workflow profiles:
```bash
# Micro Task: 3 states, 0 subagents, instant execution
python -m sclass_cli classify "Fix typo in navigation button"

# High-Risk Architecture Task: Escapes to FULL profile, 15 states, multi-agent debate
python -m sclass_cli classify "Refactor OAuth authentication layer and migrate postgres schema"
```

### 3. VS Code Live Control Plane & Sidebar
Install and load the native VS Code extension:
```bash
code --install-extension editors/vscode/sclass-governor-1.0.0.vsix
```
> **Expected Result:** Activity Bar displays the S-Class **Shield icon**, offering a live FSM stepper, subagent tree, and zero-polling state synchronization.

### 4. Interactive Terminal Watch Monitor
Launch the real-time TUI dashboard:
```bash
python -m sclass_cli watch
```

### 5. Pre-Commit Verification Gate
Audit staged git changes for entropy leaks, deleted assertions, and unauthorized edits:
```bash
python -m sclass_cli audit --staged
```

---

## 🎯 Adaptive Workflow Profiles

S-Class dynamically classifies goals into tailored workflows using multi-signal scoring:

| Profile | Target Tasks | State Sequence | Subagents | Typical Duration |
| :--- | :--- | :--- | :--- | :--- |
| **`QUESTION`** | Informational queries, architecture questions | Direct response *(Bypasses FSM)* | 0 | Instant |
| **`MICRO`** | Typos, string changes, single-line CSS | `TRIAGE` → `CODING` → `DONE` | 0 *(Direct)* | < 30 sec |
| **`SMALL_FIX`** | Targeted bug fixes, minor components | `TRIAGE` → `ANALYSIS` → `CODING` → `TASK_VERIFICATION` → `DONE` | 0 *(Direct)* | 1–3 min |
| **`CORE`** | Pure algorithms, utilities, CLI packages | `TRIAGE` → `ANALYSIS` → `SPECIFICATION_SYNTHESIS` → `CODING` → `TASK_VERIFICATION` → `QA` → `DONE` | 2 *(builder + QA)* | 3–5 min |
| **`RESEARCH`** | Architecture research, audits, exploration | `TRIAGE` → `ANALYSIS` → `SPECIFICATION_SYNTHESIS` → `DESIGN` → `DEBATE` → `DONE` | 2–3 | 5–10 min |
| **`HOTFIX`** | Emergency crash repairs | `TRIAGE` → `CODING` → `TASK_VERIFICATION` → `MERGE` → `INTEGRATION` → `QA` → `RELEASE` → `MONITORING` → `DONE` | 2 *(builder + QA)* | 2–5 min |
| **`FAST`** | Accelerated feature convergence (`/boost`) | `TRIAGE` → `ANALYSIS` → `SPECIFICATION_SYNTHESIS` → `CODING` → `TASK_VERIFICATION` → `MERGE` → `INTEGRATION` → `QA` → `RELEASE` → `MONITORING` → `DONE` | 2–3 | 5–10 min |
| **`BUG_FIX`** | Functional bug fixes, regression repairs | `TRIAGE` → `ANALYSIS` → `SPECIFICATION_SYNTHESIS` → `CODING` → `TASK_VERIFICATION` → `MERGE` → `INTEGRATION` → `QA` → `RELEASE` → `MONITORING` → `DONE` | 2–3 *(builder + QA ± security)* | 3–8 min |
| **`REFACTOR`** | Structural refactoring, API revisions | `TRIAGE` → `ANALYSIS` → `SPECIFICATION_SYNTHESIS` → `DESIGN` → `CODING` → `TASK_VERIFICATION` → `MERGE` → `INTEGRATION` → `QA` → `RELEASE` → `MONITORING` → `DONE` | 2–3 | 5–12 min |
| **`FULL`** | Greenfield products, multi-service systems | Full 15-state pipeline with multi-agent debate and governance | 3–5 | Thorough |

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

## 🖥 VS Code Native Control Plane

S-Class includes a native VS Code extension located in [`editors/vscode/`](editors/vscode/):

- **Activity Bar Shield Icon**: Quick one-click access in VS Code's sidebar.
- **Live Control Plane (Webview)**: Interactive visual FSM stepper displaying current phase, objective, epistemic mode (<span style="background:#238636;color:white;padding:1px 5px;border-radius:3px;">GROUNDED</span> vs <span style="background:#d29922;color:black;padding:1px 5px;border-radius:3px;">SYNTHETIC</span>), and quick action buttons.
- **FSM State & Gates (Tree View)**: Shows phase milestones, the 8-agent specialist swarm, and evidence gate verification status.
- **Zero-Polling Reactivity**: Uses a native `FileSystemWatcher` on `**/.agents/**` to update views instantly without latency or background polling loops.

```bash
# Package into VSIX:
cd editors/vscode && npx --yes @vscode/vsce package --no-git-tag-version

# Install in VS Code:
code --install-extension sclass-governor-1.0.0.vsix
```

---

## 🚀 Core Architectural Innovations

### 1. Dynamic Subagent Selector (0 to 5 per task, not 24)
Rather than spawning 8–24 rigid personas for every task, `subagent_selector.py` dynamically composes specialist roles (`architect`, `builder`, `frontend`, `database`, `qa`, `security`, `reviewer`, `analyst`) based on detected domains (`frontend`, `backend`, `database`, `security`). Simple and micro tasks spawn **zero** subagents, completely removing overhead. For code-writing tasks, the engine strictly enforces the **Single Lead Writer constraint** (only 1 subagent holds write authority, preventing conflicting code diffs).

### 2. Diff-Audit Verification Gate (`diff_auditor.py`)
After each coding pass, diffs are automatically audited against the intent contract:
- **Scope Creep Detection:** Flags edits outside authorized target files.
- **Weakened Test Detection:** Forbids deleting or commenting out existing assertions.
- **Secret Hygiene:** Detects leaked API keys, tokens, and hardcoded credentials using Shannon entropy and regex signatures.

### 3. Modular Phase-Specific Instructions (`instructions/`)
Monolithic shouting rules are replaced with modular, concise instructions loaded strictly when their phase is active:
- `instructions/core.md` (Cardinal Rule: Inspect Before Infer, Fast-Path bypass)
- `instructions/triage.md`, `analysis.md`, `spec_synthesis.md`, `design.md`, `debate.md`
- `instructions/coding.md`, `qa.md`, `release.md`, `micro.md`
Saves 80–90% of token context on simple turns.

### 4. Incremental Verification Engine
Instead of re-verifying the entire repository from scratch on every iteration, `IncrementalVerifier` tracks workspace snapshots and targets only modified source and test files.

### 5. Codebase Knowledge Graph (CKG)
Embedded SQLite graph database with AST entity extraction (classes, functions, routes, schemas) and recursive Common Table Expressions (`WITH RECURSIVE`) for multi-hop dependency traversals and cycle-free blast-radius impact analysis.

### 6. Cross-Platform Context Projection & Hook Matrix
Synchronizes a single verified state and native MCP server plugins across all supported developer platforms:

| Platform | System Instructions | Hook Enforcement Configuration |
|---|---|---|
| **Google Antigravity** | `GEMINI.md` | `.agents/hooks.json` |
| **VS Code** | Extension Sidebar + `.github/copilot-instructions.md` | `.github/hooks/sclass.json` |
| **Cursor** | `.cursorrules`, `.cursor/rules/*.mdc` | `.cursor/hooks.json` |
| **GitHub Copilot** | `.github/copilot-instructions.md` | `.github/hooks/sclass.json` |
| **Claude Code** | `CLAUDE.md` | `.claude/settings.json`, `.claude/hooks` |
| **Windsurf** | `.windsurfrules` | `.windsurf/hooks.json` |
| **OpenAI Codex CLI** | `AGENTS.md` | `.codex/hooks.json` |

---

## 💻 Dedicated Execution Modes & Slash Commands

| Slash Command | Execution Purpose | Action Performed |
| :--- | :--- | :--- |
| **`/goal [objective]`** | **Adaptive Goal Execution** | Selects optimal profile, executes FSM lifecycle, and verifies evidence receipts. |
| **`/boost [task/goal]`** | **High-Velocity Swarm Boost** | Pre-indexes codebase into CKG, applies token budget controls, and accelerates goal convergence. |
| **`/learn [pattern/fix]`** | **Automated Learning & KB Engine** | Captures bug fixes and architectural patterns into learning memory. |
| **`/status`** | **FSM Pipeline Inspection** | Returns real-time FSM phase, task statuses, transition history, and active governance receipts. |
| **`/advance`** | **Step-by-Step FSM Driver** | Advances the FSM forward one validated state transition. |
| **`/grill [spec/plan]`** | **Plan Red-Teaming Audit** | Runs `sclass_grill.py` to stress-test design specifications across 5 threat vectors before coding. |
| **`/doubt [question]`** | **Non-Interrupting Inquiry** | Queries codebase symbols and architecture safely in parallel with ongoing background tasks. |
| **`/inquire [question]`** | **Read-Only Symbol Query** | Queries workspace AST symbols, dependencies, and active FSM state safely. |

---

## ⚡ Quick Start

### 1. Environment Setup
```bash
# Clone the repository with submodules
git clone --recurse-submodules https://github.com/ak-bharadwaj/S-class.git
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
# Or run directly via Python module: python -m sclass_cli classify "fix typo in navigation button"

# Fast-track high-velocity boost with Codebase Knowledge Graph pre-indexing
sclass /boost "optimize database connection pool"

# Check active FSM phase and governance status
sclass /status

# Launch live monitoring dashboard
sclass watch
```

### 3. Deploy Zero-Bypass Hooks (All Platforms)
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

The following enterprise isolation and policy backends are scheduled for upcoming releases:
- **gVisor / Kernel Virtualization (`runsc`)**: Container sandboxing for arbitrary untrusted code execution.
- **Open Policy Agent (OPA / Rego)**: External declarative policy enforcement for enterprise compliance.
- **OCI Container Runtimes**: Direct Docker/Podman isolation wrappers for agent execution sandboxes.
- **Dagger Pipelines**: Declarative containerized CI/CD verification workflows.

---

## 🔒 License & Intellectual Property

**Copyright (c) 2026 ak-bharadwaj. All Rights Reserved.**

S-Class EOS v6 is released under the **Source-Available Community & Evaluation License**. 
Public inspection, non-commercial research, prospective investor evaluation, and architectural testing are permitted. Commercial production deployment, SaaS hosting, or redistributing as a commercial product requires an explicit enterprise commercial license from the copyright holder (`ak-bharadwaj`). See [LICENSE](LICENSE) for full terms.
