# S-Class SDK: Pluggable workflow runtime engine for multi-agent execution

S-Class SDK is a portable, technology-agnostic framework for defining and executing multi-agent workflows. It maps development, research, and audit stages into a strict 11-state Finite-State Machine (FSM) governed by first-class transition events, capabilities constraints, and parallel execution groups.

---

## 1. Quick Start

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
Inherit this pipeline in any project by adding the following metadata to your local `CLAUDE.md`:
```markdown
pipeline: sclass-v5
executionMode: Human-in-the-Loop Mode
```

---

## 2. Directory Layout

*   [plugin.json](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/plugin.json) — Registers pipeline metadata, loop modes, and capabilities.
*   [state_schema.json](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/state_schema.json) — JSON Schema for shared FSM execution state validation.
*   [events.json](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/events.json) — Transition events catalog.
*   [capabilities.json](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/capabilities.json) — Subagent permission boundary matrix.
*   [workflow.json](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/workflow.json) — States and parallel groups declaration.
*   `prompts/` — System prompts for the 11 subagents.

---

## 3. Documentation Index

*   [docs/runtime.md](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/docs/runtime.md) — Engine loops, state ownership, and timeout safety.
*   [docs/workflow.md](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/docs/workflow.md) — FSM States definition and event routing.
*   [docs/plugin-api.md](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/docs/plugin-api.md) — Schemas and capabilities specifications.
*   [docs/recovery.md](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/docs/recovery.md) — Self-healing RECOVERY loops and patch strategies.
*   [docs/sdk.md](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/docs/sdk.md) — Creating custom pipelines (Research, GameDev, etc.).

---

## 4. License
S-Class SDK is released under the [MIT License](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/LICENSE).
