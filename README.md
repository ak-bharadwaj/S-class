# S-Class: Flagship Engineering Workflow Plugin for Antigravity

S-Class is the official engineering workflow plugin for the Antigravity platform. It defines and executes a strict 11-state Finite-State Machine (FSM) to coordinate multi-agent engineering workflows, leveraging Antigravity's native capabilities.

---

## Why S-Class? (Value Proposition)

| Question | S-Class Workflow Engine | Standard LLM Tools / Claude Code |
| :--- | :--- | :--- |
| **What problem does it solve?** | Prevents architectural drift, parameter leaks, and logic regressions on complex codebases. | Single-agent chat interfaces struggle with multi-file scaling and structural logic. |
| **Why use a Finite-State Machine?** | Forces development through explicit, auditable states (`DEBATE`, `RECOVERY`, etc.) with defined transition rules. | Conversational models skip steps, run tools out of order, or introduce logical stubs. |
| **Why event-driven routing?** | Supports adaptive loops (e.g. `Database Modified` event triggers migration checks; `QA Failed` routes to Recovery). | Rigid linear scripts break when encountering errors and cannot easily self-correct. |
| **What is Goal Convergence Mode?** | An autonomous closed-loop that builds, tests, reviews, and patches code until all quality checks are 100% satisfied. | Requires constant human prompt-interruptions to review code outputs and fix errors. |
| **Why a plugin over prompts?** | Registers capability permissions, executes parallel groups, and commits state updates programmatically. | Prompt templates rely entirely on the LLM remembering instructions without system enforcement. |

---

## 1. Supported Antigravity Capabilities

S-Class integrates directly with the Antigravity environment to support:
*   **Task Memory:** Utilizes the memory agent to index previous decisions, architectural changes, and bug tracking databases.
*   **Antigravity Sessions:** Integrates subagents directly into active workspace sessions without state duplication.
*   **Agent Debate Loops:** Schedules parallel subagent execution to debate designs and code quality.
*   **Goal Convergence Mode:** Executes closed-loop iterations to satisfy user objectives autonomously.
*   **Shared State Database:** Regulates task status updates inside `orchestration_state.json`.
*   **Skill Auto-Discovery:** Leverages the `find-skills` module to locate and install missing capability plugins dynamically.
*   **Plugin API:** Serves as the reference architecture for building pluggable Antigravity workflows.

---

## 2. Quick Start

### Installation

#### Windows (PowerShell):
```powershell
iex (irm -useb https://raw.githubusercontent.com/ak-bharadwaj/sclass-v5/master/install.ps1)
```

#### Linux/macOS (Shell):
```bash
curl -fsSL https://raw.githubusercontent.com/ak-bharadwaj/sclass-v5/master/install.sh | bash
```

### Usage

#### 1. Zero-Config Workspace Initialization
Developers do not need to create configuration files manually. Running S-Class initialization creates both the orchestration state file and a default config preset named `sclass.config.json` in the root of the project:
```json
{
  "pipeline": "sclass-v5",
  "executionMode": "Human-in-the-Loop Mode",
  "loopMode": "closed-loop",
  "projectType": "web-application",
  "commands": {
    "devServer": "npm run dev",
    "test": "npm test",
    "dbMigration": ""
  }
}
```

#### 2. Broad NLP Input Decomposition
S-Class is designed to handle high-level natural language (NLP) requests (e.g. *"Build a dashboard website with active fire tracking and authentication"*). 

The ingestion agents handle system-level decomposition automatically:
1.  **Requirements Analyst (`dss_analyst`):** Maps the broad user prompt into explicit database models, API signatures, views, and data contracts.
2.  **System Architect (`dss_architect_v2`):** Designs the complete blueprints (SQL columns, entity relationships, route schemas).
3.  **Response Aggregator (`dss_aggregator`):** Commits the specification details and compiles them into structured tasks (T1, T2, T3) mapped with dependencies and acceptance criteria for the builder to implement.

#### 3. Importing the FSM Runtime Library API
S-Class runs as an internal Python library inside the host environment. Subagents and managers import and call state functions directly:

```python
from sclass-v5 import runtime

# Initialize the workspace state file
runtime.initialize_state()

# Load the current validated State object
state = runtime.get_state()
print(f"Current State: {state.currentPhase}")

# Dispatch an event to transition states
runtime.dispatch_event("triage_done")

# Update a task status
runtime.update_task("T1", "IN_PROGRESS")

# Record a durable decision log
runtime.log_decision(
    decision="Use SQLite",
    reason="No concurrent connections needed in operational state",
    agent="dss_architect_v2",
    confidence=0.90,
    alts=["PostgreSQL", "JSON storage"]
)
```

---

## 3. Directory Layout

*   [plugin.json](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/plugin.json) — Registers pipeline metadata, loop modes, and capabilities.
*   [state_schema.json](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/state_schema.json) — JSON Schema for shared FSM execution state validation.
*   [events.json](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/events.json) — Transition events catalog.
*   [capabilities.json](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/capabilities.json) — Subagent permission boundary matrix.
*   [workflow.json](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/workflow.json) — States and parallel groups declaration.
*   `prompts/` — System prompts for the 11 subagents.

---

## 4. Documentation Index

*   [docs/runtime.md](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/docs/runtime.md) — Engine loops, state ownership, and timeout safety.
*   [docs/workflow.md](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/docs/workflow.md) — FSM States definition and event routing.
*   [docs/plugin-api.md](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/docs/plugin-api.md) — Schemas and capabilities specifications.
*   [docs/recovery.md](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/docs/recovery.md) — Self-healing RECOVERY loops and patch strategies.
*   [docs/sdk.md](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/docs/sdk.md) — Blueprint for building other Antigravity plugins.
*   [docs/roadmap.md](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/docs/roadmap.md) — S-Class context management & knowledge indexing roadmap.

---

## 5. License
S-Class is released under the [MIT License](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/LICENSE).
