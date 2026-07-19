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

#### 1. Configuration Preset
Inherit this pipeline in any project by adding the following metadata to your local `CLAUDE.md`:
```markdown
pipeline: sclass-v5
executionMode: Human-in-the-Loop Mode
```

#### 2. Executing the FSM State Machine CLI
The plugin includes an executable Python runtime engine (`runtime.py`) that acts as the single-writer state manager and event router. Run it inside your project directory to coordinate steps:

*   **Initialize Workspace State:**
    ```bash
    python ~/.gemini/config/plugins/sclass-v5/runtime.py init
    ```
*   **Check Active Phase & Tasks:**
    ```bash
    python ~/.gemini/config/plugins/sclass-v5/runtime.py status
    ```
*   **Dispatch Event Trigger (State Transition):**
    ```bash
    python ~/.gemini/config/plugins/sclass-v5/runtime.py dispatch triage_done
    ```
*   **Audit Subagent Capabilities Matrix:**
    ```bash
    python ~/.gemini/config/plugins/sclass-v5/runtime.py capabilities dss_builder_v2
    ```
*   **Update Task Execution Status:**
    ```bash
    python ~/.gemini/config/plugins/sclass-v5/runtime.py task T1 IN_PROGRESS
    ```
*   **Record Durable Decision Log:**
    ```bash
    python ~/.gemini/config/plugins/sclass-v5/runtime.py decision "Use SQLite" "No concurrency required" dss_architect_v2 0.90
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
