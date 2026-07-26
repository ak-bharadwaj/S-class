# S-Class V7.0: Engineering Operating System (EOS)

S-Class is an **Engineering Operating System (EOS)** designed to provide deterministic, verifiable, and strategy-aware software development for AI agent platforms. Rather than relying on unstructured LLM prompt loops, S-Class enforces an **atomic 11-state Finite-State Machine (FSM)** equipped with hard evidence gates, real-time parallel multi-agent debate, continuous self-evaluation, and deterministic replay audit logs.

---

## The 7-Layer EOS Architecture

```
User Goal / NLP Request
   │
   ▼
Meta-Planner (`planner.py` & `strategy.py`)
   │  └─ Strategy Engine: Infers risk (LOW..CRITICAL), scale (MICRO..ENTERPRISE), urgency, & evidence contracts.
   ▼
Execution Strategy & Intent Contract (`intent_contract.py`)
   │  └─ Locks acceptance criteria & scope boundaries; resets to TRIAGE if requirements shift mid-flight.
   ▼
Workflow Profile (`workflow.json`)
   │  └─ Selects execution shortcut (FULL, BUG_FIX, RESEARCH, REFACTOR, HOTFIX).
   ▼
Deterministic 11-State FSM Core (`runtime.py`)
   │  └─ TRIAGE ➔ ANALYSIS ➔ CLARIFICATION ➔ DESIGN ➔ DEBATE ➔ TASK_COMPILATION ➔ CODING ➔ INTEGRATION ➔ QA ➔ RECOVERY ➔ RELEASE
   ▼
Parallel Multi-Agent Layer
   │  ├─ DEBATE Phase: 8 Domain Experts in Parallel (UI/UX, Frontend, Backend, DB, Security, Governance, Reviewer, Proxy User)
   │  └─ QA Phase: 6 Specialized QA Agents in Parallel (Frontend QA, Backend QA, Security, Reviewer, Proxy User, QA Lead)
   ▼
Verifiable Execution Gate (`verifier.py`)
   │  └─ Hard-blocks state transitions unless physical disk diffs, test receipts (exit code 0), & scan reports exist.
   ▼
Learning, Evaluation & Replay Engine (`evaluation.py` & `replay.py`)
      ├─ Evaluates agent confidence mid-flight & auto-pivots profiles if scope expands.
      └─ Records immutable `transitionHistory` audit trail log for 100% deterministic replayability.
```

---

## The 6 Core Guarantees of S-Class EOS

| # | Guarantee | Core Module | Technical Rationale & Impact |
| :--- | :--- | :--- | :--- |
| **1** | **Strategy-Aware Planning** | `strategy.py` | Analyzes task risk, urgency, project scale, and evidence contracts *before* code generation begins. |
| **2** | **Verifiable Execution Gate** | `verifier.py` | State transitions require physical evidence artifacts on disk (diffs, test receipts with exit code 0, security scans). |
| **3** | **Continuous Self-Evaluation** | `evaluation.py` | Evaluates agent confidence at phase boundaries. Auto-resets to `TRIAGE` if requirements shift mid-flight. |
| **4** | **Anti-Looping Recovery** | `error_recovery.py` | Enforces regex error matching, exponential backoff ($base \times mult^{attempt}$), & strict stop bounds. |
| **5** | **Zero-Regression Memory** | `runtime.py` | Shadow-first test suite execution validates bug fixes against the full test suite before memory promotion. |
| **6** | **Deterministic Replay** | `replay.py` | Records an immutable `transitionHistory` audit trail log allowing 100% trajectory replayability and compliance auditing. |

---

## Specialized Parallel Swarm Squads

S-Class EOS forbids collapsing complex phases into single-agent execution. Subagents execute concurrently in parallel background threads via `invoke_subagent`:

### 1. The 8-Agent Domain Planning Squad (`DEBATE` Phase)
When designing blueprints, S-Class spawns **8 specialized domain experts in parallel** to cross-examine proposals and resolve cross-domain ripple effects before code is written:
*   `dss_governor` — System Architecture Lead & Moderator
*   `dss_ui_ux` — UI/UX Ergonomics & Accessibility Specialist
*   `dss_frontend_dev` — React / Next.js Client Component & Rendering Expert
*   `dss_backend_dev` — API DTO, Route Signature, & Controller Specialist
*   `dss_db_architect` — SQL Model, Foreign Key, & ORM Migration Expert
*   `dss_cso_v2` — Auth Bounds, RBAC, & Security Auditor
*   `dss_reviewer_v2` — Code Quality & Maintainability Auditor
*   `dss_user_alias_v2` — Proxy User Acceptance Advocate

### 2. The 6-Agent Specialized QA Squad (`QA` Phase)
During system verification, S-Class spawns **6 specialized QA agents in parallel**:
*   `dss_qa_frontend` — UI / Playwright / Chrome MCP Visual Screenshot QA
*   `dss_qa_backend` — API Endpoint Routing / DB Migration / Server Log QA
*   `dss_reviewer_v2` — Code Quality Auditor
*   `dss_cso_v2` — Security & Secret Vulnerability Scanner (`security_shield.py`)
*   `dss_user_alias_v2` — Proxy User UX & Acceptance Criteria Auditor
*   `dss_qa_v2` — System QA Lead (Synthesizes results & issues final release decision)

---

## Dual Integration Modes

S-Class EOS operates natively across both plugin and MCP client ecosystems:

### Mode A: Native Antigravity Plugin
Registered as an active workspace plugin inside `.gemini/config/plugins/sclass-v5/`. Equips Antigravity with governance system prompts (`instructions.md`), capabilities (`capabilities.json`), and FSM transition rules (`workflow.json`).

### Mode B: Model Context Protocol (MCP) Server (`mcp_server.py`)
Connects S-Class EOS seamlessly to **Claude Desktop**, **Cursor**, **VS Code**, **Codex**, or **Gemini CLI** over stdio JSON-RPC:

```json
{
  "mcpServers": {
    "sclass": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "C:/Users/dorni/.gemini/config/plugins/sclass-v5"
    }
  }
}
```

#### Standard MCP Tools Exposed:
*   `sclass_initialize`: Ingests NLP goals & initializes FSM state + strategy
*   `sclass_get_state`: Queries active FSM phase, task queue, and decision log
*   `sclass_dispatch`: Dispatches state transition events with evidence validation
*   `sclass_reset_to_triage`: Resets workflow back to `TRIAGE` if user modifies requirements mid-flight
*   `sclass_memory_search`: Performs TF-IDF semantic vector search over past bug fixes
*   `sclass_doctor`: Runs environment health check (`run_doctor`)
*   `sclass_gc`: Cleans up stale lock files and expired FSM state caches
*   `sclass_audit_replay`: Audits execution trajectory and exports Markdown audit logs
*   `sclass_security_scan`: Scans source files for secrets and vulnerability patterns

---

## Competitive Architectural Analysis

| Feature | Ruflo (`ruvnet/ruflo`) | ECC (`affaan-m/ECC`) | **S-Class EOS V7.0** |
| :--- | :--- | :--- | :--- |
| **System Philosophy** | Swarm Meta-Harness | Harness Adapter Rules | **Deterministic Engineering OS** |
| **Strategy-Aware Planning** | ❌ None | ❌ None | **✅ `strategy.py`**: Risk, scale, urgency, & evidence inference |
| **State Evidence Gate** | ❌ Self-reported completion | ⚠️ Exit code checks | **✅ `verifier.py`**: Hard-blocks transitions unless disk evidence exists |
| **Parallel Domain Debate** | Generic workers | Generic planner | **✅ 8 Parallel Domain Experts** (UI, Frontend, Backend, DB, Security) |
| **Specialized QA Squad** | Generic tester | Command test hooks | **✅ 6 Parallel QA Agents** (Frontend UI, Backend API/DB, Proxy User, Lead) |
| **Mid-Flight Requirement Reset** | ❌ None | ❌ None | **✅ `reset_to_triage`**: Restarts strategy & planning on goal updates |
| **Deterministic Replay Log** | ⚠️ Execution receipts | ❌ None | **✅ Guarantee #6 (`replay.py`)**: Immutable `transitionHistory` audit trail |
| **Semantic Memory Search** | ✅ HNSW Index | ⚠️ Flat JSON | **✅ `MemoryManager.semantic_search()`**: TF-IDF vector similarity |
| **Vulnerability Scanning** | ❌ None | ✅ AgentShield | **✅ `security_shield.py`**: Secret detection & AST pattern scanner |
| **Environment Doctor & GC** | ✅ `doctor --fix` | ✅ `config-gc` | **✅ `doctor.py` + `config_gc.py`**: Lock cleanup & health verification |

---

## Test Suite & Verification

S-Class EOS contains **60 automated unit tests** passing cleanly with 100% success across Python 3.10, 3.11, 3.12, 3.13, and 3.14:

```bash
python -m pytest tests/ -v
# Output: 60 passed in 0.38s
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
