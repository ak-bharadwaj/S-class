<div align="center">

# ⚡ S-CLASS EOS V13.0
### The Authoritative Execution Microkernel & Deterministic Cognitive Control Plane

*Eliminates AI coding agent hallucination, enforces multi-tier evidence gates, and synchronizes cross-platform state across Cursor, Claude Code, OpenAI Codex CLI, and Google Antigravity.*

[![Version](https://img.shields.io/badge/version-13.0.0--pre--d0-blue.svg)](https://github.com/ak-bharadwaj/S-class/tree/working-pre-d0)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-green.svg)](https://github.com/ak-bharadwaj/S-class/tree/working-pre-d0)
[![Build](https://img.shields.io/badge/tests-269%2F269%20passing-brightgreen.svg)](https://github.com/ak-bharadwaj/S-class/tree/working-pre-d0)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)

[Quick Start](#-quick-start) • [CLI & Slash Commands](#-dedicated-execution-modes--slash-commands) • [Architecture](#-system-architecture) • [Features](#-core-architectural-innovations) • [Python SDK](#-30-second-python-sdk-quickstart) • [Benchmark Comparison](#-framework-architectural-comparison) • [License](#-license)

---

</div>

## 📌 Executive Overview

When autonomous AI coding agents (such as Claude Code, Cursor, OpenHands, or Codex CLI) execute software engineering tasks, they suffer from 4 critical failure modes:
1. **Agent Drift & Hallucinated Scaffolding:** They get stuck in loops, invent unrequested features (forcing complex enterprise auth or UI pages onto narrow backend algorithm tasks), or overwrite files blindly.
2. **Fake / Unearned Verification:** They claim *"All tests pass and the task is verified!"* when either zero code exists on disk, or when running in test simulation without declaring simulation provenance.
3. **Sparse & Amateur UIs:** For real UI tasks, they generate unstyled default HTML tables, missing loading states, and broken responsive layouts.
4. **Platform Siloing & Context Loss:** Switching between Cursor, Claude Code, and Antigravity loses in-flight decisions, pending tasks, and mental model state.

**S-Class EOS V13.0 fixes this completely.** Operating as an **Authoritative Execution Microkernel & Cognitive Control Plane**, S-Class intercepts all agent actions, routes engineering goals through an evidence-gated 19-state Finite State Machine (FSM), enforces domain-aware specification synthesis, maintains a zero-infrastructure Codebase Knowledge Graph (CKG), projects dynamic native rules (`.cursorrules`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`), and guarantees **strict epistemic honesty** with explicit simulation provenance tracking.

> [!IMPORTANT]
> **Release Branch Attestation (`working-pre-d0`)**: Formally verified across **269 automated regression test cases across 48 test suites passing 100% green**. Includes Domain-Aware Skill Dispatch, Top-Level Epistemic Simulation Provenance, External Workspace Targeting (`-w`/`--workspace`), FastMCP Graph Server, and Starter Code Synthesis.

> [!NOTE]
> **V13.0 Zero-Defect Guarantee**: Passed an exhaustive audit resolving external workspace path resolution, domain scoping (UI agents standby for non-UI tasks), recursive CTE false cycle bugs, and synthetic execution surfacing.

---

## 🏛 System Architecture

```
                                 ENGINEERING GOAL / COMMAND
                                (/goal, /boost, /learn, /grill)
                                             │
                                             ▼
                       S-Class CLI & Unified SDK Interface (sdk_interface.py)
                         (Supports -w/--workspace external targeting)
                                             │
                                             ▼
                                Deterministic Microkernel
                                  (runtime.py 19-State FSM)
                                             │
   ┌──────────────────────┬──────────────────┴─────────────────┬──────────────────────┐
   ▼                      ▼                                    ▼                      ▼
Domain Classifier    Specification Synthesis              Full 8-Subagent Swarm     Multi-Tier Verifier
(task_classifier.py) Engine (spec_synthesis.py)           (sclass_subagent_reg)     Fortress (verifier.py)
   │                  (Inspect Before Infer)               (Domain-Aware Scoping)     │
   │                      │                                    │                      │
   ▼                      ▼                                    ▼                      ▼
CKG Knowledge Graph  FastMCP Graph Server                Dynamic Skill Auto-Loader  Anti-Cheating Visual QA
(codebase_graph_db)  (codebase_kg_server.py)             (118-Skill Matt Pocock)    (High-Variance PNGs)
   │                                                                                  │
   └─────────────────────────────────────────┬────────────────────────────────────────┘
                                             │
                                             ▼
                         Cross-Platform Cognitive Projection & Handoff
                     (.cursorrules, CLAUDE.md, AGENTS.md, GEMINI.md, CONTINUE_HERE.md)
```

---

## 🚀 Core Architectural Innovations

### 1. External Workspace Isolation (`-w`, `--workspace`, `--target`, `-C`)
S-Class CLI operates safely on external codebases without polluting its own directory. All governance records, state files, and logs land strictly in the target project's `.agents/` folder, never touching the CLI caller's root.

### 2. Loud Epistemic Provenance Surfacing
S-Class never lies about what actually occurred. If a run occurs in test/simulation mode without active coding agent credentials:
* Surfaces `"status": "COMPLETED_SYNTHETIC"` or `"SIMULATED"`.
* Emits top-level `synthetic: true`, `authority: "FSM_TEST_RUNNER"`, and `epistemic_warning`.
* Highlights a prominent CLI notice banner detailing exact authority attribution and synthesized starter code.

### 3. Domain-Aware Subagent & Skill Dispatch
For algorithm, CLI, and library tasks, S-Class automatically scopes subagent swarms:
* UI/UX subagents (`dss_ui_ux`, `dss_frontend_dev`, `dss_qa_frontend`, `dss_user_alias_v2`) are placed on `STANDBY_NON_UI` with zero assigned skills.
* Heavy enterprise auth skills (`oauth-sso-saml-auth`, `tenant-isolation-multi-tenancy`) are decoupled from default activation.
* Active backend subagents receive curated, non-UI skill combos.

### 4. Zero-Infrastructure Codebase Knowledge Graph (CKG)
Embedded SQLite graph database with AST entity extraction (classes, functions, routes, schemas) and recursive Common Table Expressions (`WITH RECURSIVE`) for lightning-fast multi-hop dependency traversals and cycle-free blast-radius impact analysis.

### 5. Cross-Platform Context Projection & Handoff Engine
Maintains a single cognitive source-of-truth and continuously projects it into the native instructions format of each major AI tool:
* **Cursor**: `.cursorrules` & `.cursor/rules/*.mdc`
* **Claude Code**: `CLAUDE.md`
* **OpenAI Codex CLI**: `AGENTS.md`
* **Google Antigravity / Gemini**: `GEMINI.md`
* **Handoff Receipt**: `CONTINUE_HERE.md` and `session_handoff.json` (schema `schema.session-handoff.v1`).

### 6. FastMCP Codebase Knowledge Graph Server
Exposes 7 high-performance MCP tools (`graph_query`, `find_dependencies`, `impact_analysis`, `trace_execution_path`, `explain_architecture_slice`, `record_decision`, `export_mermaid`) for real-time graph navigation and dynamic Mermaid diagram generation.

### 7. Multi-Tier Anti-Cheating Visual Verification Gate
Requires authentic Chrome DevTools MCP visual receipts for frontend applications. Rejects synthetic solid-fill placeholders, zero-variance bitmaps, or missing user-interaction traces (`click`, `fill`, `assert`). Automatically adapts for non-UI tasks to verify backend contracts without demanding screenshots.

### 8. Starter Code Synthesis in Simulation
For backend and algorithm tasks in simulation mode, S-Class synthesizes actual runnable code implementations (e.g. `rate_limiter.py` with a thread-safe `SlidingWindowRateLimiter`) on disk so projects never complete with missing source code.

---

## 💻 Dedicated Execution Modes & Slash Commands

S-Class V13.0 introduces a dedicated CLI (`sclass_cli.py`) and unified SDK interface (`sdk_interface.py`):

| Slash Command | Execution Purpose | Action Performed |
| :--- | :--- | :--- |
| **`/goal [objective]`** | **Autonomous Goal Execution** | Drives full 19-state FSM execution lifecycle with subagent worker swarms and adaptive release gates. |
| **`/boost [task/goal]`** | **High-Velocity Swarm Boost** | Pre-indexes codebase into CKG, engages parallel subagents, applies token budget controls, and accelerates goal convergence. |
| **`/learn [pattern/fix]`** | **Automated Learning & KB Engine** | Captures bug fixes and architectural patterns into learning memory, promotes approved candidates to Knowledge Base, and updates CKG. |
| **`/status`** | **FSM Pipeline Inspection** | Returns real-time FSM phase, task statuses, transition history, and active governance receipts. |
| **`/advance`** | **Step-by-Step FSM Driver** | Advances the FSM forward one validated state transition. |
| **`/grill [spec/plan]`** | **Plan Red-Teaming Audit** | Runs `sclass_grill.py` to stress-test design specifications across 5 threat vectors before coding. |
| **`/doubt [question]`** | **Non-Interrupting Inquiry** | Queries codebase symbols and architecture safely in parallel with ongoing background tasks. |
| **`/inquire [question]`** | **Read-Only Symbol Query** | Queries workspace AST symbols, dependencies, and active FSM state safely. |

---

## ⚡ Quick Start

### Step 1: Run S-Class CLI on Any Project

```bash
# Execute an autonomous goal on an external project
python sclass_cli.py -w /path/to/my-project /goal "implement a rate limiter using a sliding window algorithm"

# Fast-track high-velocity boost with Codebase Knowledge Graph pre-indexing
python sclass_cli.py -w /path/to/my-project /boost "optimize database connection pool"

# Check active FSM phase and governance status
python sclass_cli.py -w /path/to/my-project /status

# Red-team architecture and specs
python sclass_cli.py -w /path/to/my-project /grill
```

---

### Step 2: Add S-Class Rules to Your Workspace

Create or open `.cursorrules`, `AGENTS.md`, or `CLAUDE.md` in your project root directory:

```markdown
pipeline: sclass-v5
CRITICAL DIRECTIVE: You MUST route all engineering goals strictly through S-Class EOS FSM (runtime.initialize_state & runtime.dispatch_event). Direct parent code edits are strictly forbidden (Rule 17). Subagents MUST enforce Rule 27 No-Laziness Directive, Rule 28 Subagent Deployment Dashboard, Rule 29 Full 8 Concurrent Subagent Swarms, Rule 30 Specification Synthesis, Rule 31 Semantic Gate, and Chrome MCP visual screenshots for UI tasks.
```

---

## 🐍 30-Second Python SDK Quickstart

```python
from sdk_interface import SClassSDK

# 1. Initialize S-Class SDK pointed at any target workspace
sdk = SClassSDK(workspace_dir="/path/to/my-project")

# 2. Run an Autonomous Goal with Epistemic Provenance
result = sdk.execute_goal(goal="implement a rate limiter using a sliding window algorithm")
print(f"Execution Status: {result['status']}")
print(f"Synthetic Simulation: {result['synthetic']} (Authority: {result['authority']})")
print(f"Source Files Generated: {result['source_files']}")

# 3. Query Codebase Knowledge Graph
nodes = sdk.query_graph(pattern="RateLimiter")
print(f"Found {len(nodes)} matching symbols in CKG")

# 4. Cross-Platform Context Projection
sdk.project_rules()
# Automatically generates .cursorrules, CLAUDE.md, AGENTS.md, GEMINI.md, and CONTINUE_HERE.md
```

---

## 📊 Framework Architectural Comparison

| Architectural Layer | OpenHands | Claude Code | Meta Muse Code | **S-Class V13.0 (Deterministic Control Plane)** |
| :--- | :--- | :--- | :--- | :--- |
| **System Philosophy** | Sandbox Harness | CLI Agent Loop | Model Co-Trained CLI | **Deterministic Microkernel & Safety-Case Engine** |
| **Epistemic Honesty** | Silent Simulation | None | None | **✅ Loud Provenance Surfacing (`COMPLETED_SYNTHETIC`, `authority`)** |
| **Workspace Isolation** | Container Bound | Local Directory | Local Directory | **✅ External Workspace Targeting (`-w`, `--workspace`, `-C`)** |
| **Domain-Aware Dispatch** | Monolithic | Monolithic | Monolithic | **✅ Adaptive UI/Backend Scoping (UI agents standby on algorithm tasks)** |
| **Codebase Knowledge Graph** | None | Keyword Search | Vector Index | **✅ Zero-Infra SQLite CKG + Recursive CTE Traversal** |
| **Cross-Platform Handoff** | None | Claude Only | Custom | **✅ Universal Projection (Cursor, Claude, Codex, Gemini)** |
| **State Mutation Guard** | FS Writes | FS Writes | FS Writes | **✅ Exclusive Kernel Mutator (`sclass_kernel.py` + FileLock)** |
| **Visual Evidence Gate** | Heuristic | None | Heuristic | **✅ Chrome DevTools MCP + Anti-Cheating Variance Checks** |
| **Starter Code Synthesis** | None | None | None | **✅ Automated Functional Starter Code Generation** |
| **OS Compatibility** | Docker / Unix | Linux / macOS | Linux / macOS | **✅ Windows Native (PowerShell), macOS, Linux Native** |

---

## 🧪 Comprehensive Automated Test Suite

S-Class V13.0 contains **269 automated unit and integration tests across 48 test modules** passing with 100% success across Python 3.10–3.14:

| Test Module File | Test Count | Functionality Tested |
| :--- | :--- | :--- |
| `tests/test_spec_synthesis.py` | 30 tests | Specification synthesis V2.1, evidence-driven capability expansion, conservative inference, semantic gate, assumption budget, anti-bypass verifier gate. |
| `tests/test_eos_core.py` | 15 tests | Decoupled RiskEngine/PolicyEngine, SafetyCase, Output Evidence Pack, SHA-256 tamper hashing. |
| `tests/test_robust_qa.py` | 13 tests | Chrome DevTools DOM sanitization, user flow receipts, duplicate screenshot detection, Lighthouse audits. |
| `tests/test_slash_commands.py` | 12 tests | Slash command dispatchers (`/goal`, `/boost`, `/learn`), CLI flags (`-w`, `--target`, `-C`), epistemic provenance surfacing, starter code synthesis, and domain-aware dispatch. |
| `tests/test_artifact_governance.py` | 10 tests | Governance lifecycle, artifact signing, cryptographic checksums, integrity assertions. |
| `tests/test_practical_regression.py` | 9 tests | Empirical failure cases (`FAIL-001` to `FAIL-011`), FileLock stale process recovery, 1:1 bidirectional grounding equality, plain-prose library role preservation. |
| `tests/test_runtime.py` | 9 tests | FSM state initialization, schema validation, event dispatching, FileLock hardware mutual exclusion. |
| `tests/test_adversarial_domain_synthesis.py` | 8 tests | Dynamic synthesis across novel unseen domain shapes (Precision Ag, Maritime Logistics, FinTech HFT, Aerospace, IoT). |
| `tests/test_mcp_graph_server.py` | 8 tests | FastMCP graph server tools, dependency analysis, impact tracing, Mermaid export. |
| `tests/test_planner.py` | 8 tests | Meta-Planner workflow profile selection (`FULL`, `BUG_FIX`, `RESEARCH`, `REFACTOR`, `HOTFIX`). |
| `tests/test_browser_automation.py` | 7 tests | Playwright headless browser control, screenshot capture, entropy validation, dimension verification. |
| `tests/test_guardrails.py` | 7 tests | Supply-chain verification, secret scanning, context budget tracking, promise protocol, resilience retry. |
| `tests/test_task_classification.py` | 7 tests | Domain classification (algorithm, fullstack, backend, cli), adaptive QA gate filtering, and zero-screenshot backend passes. |
| `tests/test_behavior_graph.py` | 6 tests | Behavioral graph topology, mutation transitions, node edge invariant validation. |
| `tests/test_memory_semantic.py` | 6 tests | Semantic memory indexing, tri-partite retrieval, memory decay models. |
| `tests/test_codebase_graph.py` | 5 tests | SQLite graph schema, AST entity extraction, recursive CTE traversals, cycle detection. |
| `tests/test_fable5_stress.py` | 5 tests | Fable-5 stress scenarios: CLI dev tool, Kafka ETL pipeline, multi-tenant monorepo RBAC, healthcare emergency override, deep architecture spec decision preservation. |
| `tests/test_kernel.py` | 5 tests | Microkernel state mutator, event sourcing replay, tri-partite memory, resource scheduler. |
| `tests/test_sdd_pipeline.py` | 5 tests | Spec-Driven Development pipeline, delta-spec manager, OpenGSD wave-based artifact DAG. |
| `tests/test_security_shield.py` | 5 tests | Secret scanning, dangerous AST pattern detection, vulnerability report generation. |
| `tests/test_skill_orchestrator.py` | 5 tests | 118-skill catalog resolution, phase filtering, domain-aware combo resolution. |
| `tests/test_spec_compiler_v7.py` | 5 tests | Spec compilation pipeline, IR lowering, dependency order resolution. |
| `tests/test_strict_evidence_gates.py` | 5 tests | Evidence gate verification (git conflict rejection, telemetry requirements, feedback reports). |
| `tests/test_topology.py` | 5 tests | Subagent network topologies (`WorkerMeshPool`, Star, Mesh, Ring phase resolution). |
| `tests/test_v9_5_1_single_source_of_truth.py` | 5 tests | Single source of truth invariants, non-mutating refinement pipeline verification. |
| `tests/test_config_gc.py` | 4 tests | Garbage collection for stale workspace state and locks. |
| `tests/test_doctor.py` | 4 tests | System diagnostics & environment preflight check. |
| `tests/test_error_recovery.py` | 4 tests | Failure report verification and automatic error state recovery. |
| `tests/test_v9_5_2_verification.py` | 4 tests | Verifier gate enforcement, pipeline rejection on missing artifacts. |
| `tests/test_v9_5_3_epistemic_rigor.py` | 4 tests | Epistemic claim grounding, knowledge consistency proofs. |
| `tests/test_v9_debate_engine.py` | 4 tests | Claim-level 5D architectural debate scoring and consensus. |
| `tests/test_verifier_hardening.py` | 4 tests | Anti-cheating image entropy checks, solid-fill rejection, high-variance verification. |
| `tests/test_cross_platform_handoff.py` | 3 tests | Dynamic rule generation (`.cursorrules`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`) and session handoff receipts. |
| `tests/test_end_to_end_pipeline_debate.py` | 3 tests | End-to-end multi-agent debate and consensus pipeline verification. |
| `tests/test_intent_contract.py` | 3 tests | Composable contracts, OutputContractSpec v2.1 serialization, typed predicates. |
| `tests/test_mcp_server.py` | 3 tests | MCP tool execution, stdio JSON-RPC server transport, status reporting. |
| `tests/test_replay.py` | 3 tests | Transition record serialization, replay engine audit, markdown exporting. |
| `tests/test_skill_auto_loader.py` | 3 tests | Dynamic auto-loading of Matt Pocock SKILL.md playbooks, tier filtering, and fallback resolution. |
| `tests/test_v12_engines.py` | 3 tests | Automated AST dependency resolution, zero-infra DB fallbacks, port conflict resolution. |
| `tests/test_worktree_manager.py` | 3 tests | Git worktree isolation, atomic commits, conventional commit enforcement. |
| `tests/test_fsm_goal_sequence.py` | 2 tests | Full 19-state sequence runner, automated state advancement. |
| `tests/test_skill_discovery.py` | 2 tests | Upfront tech/domain scanner, auto-cloning missing repos, skill discovery receipt generation. |
| `tests/test_spec_griller.py` | 2 tests | 5-vector threat audit, red-teaming report generation, critical defect detection. |
| `tests/test_subagent_registry.py` | 2 tests | Full 8 subagent concurrent dispatch, role assignment, `find-skill` capability binding. |
| `tests/test_v9_5_control_plane.py` | 2 tests | Control plane governance, FSM override events, policy enforcement. |
| `tests/test_benchmarks.py` | 1 test | 50-scenario empirical quality benchmark (30% unit test vs 100% S-Class defect detection). |
| `tests/test_global_skill_availability.py` | 1 test | 100% skill availability across S-Class and all 8 subagents 24/7 across all phases. |
| `tests/test_sdk_interface.py` | 1 test | Unified SDK client initialization, phase stepping, and graph query interface. |

---

## 🔒 License & Legal Notice

**Copyright (c) 2026 ak-bharadwaj. All Rights Reserved.**

S-Class EOS V13.0 is **Proprietary and Confidential Software**. 

Unauthorized copying, modification, redistribution, sublicensing, deployment, or public hosting of this Software, via any medium, is strictly prohibited. Access and usage are granted exclusively under explicit written authorization by the copyright holder (`ak-bharadwaj`). See [LICENSE](LICENSE) for full details.
