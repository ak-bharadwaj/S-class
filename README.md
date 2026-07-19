# S-Class V5.2 Engineering Pipeline Plugin

This directory contains the pluggable S-Class Engineering Pipeline configuration for Antigravity. It implements a generic 11-state Finite-State Machine (FSM) governed by first-class events, parallel execution groups, an agent capabilities matrix, and multi-variable goal convergence exit gates.

---

## 1. Directory Structure

```
C:\Users\dorni\.gemini\config\plugins\sclass-v5/
├── plugin.json          # Plugin metadata & compatibility declaration
├── README.md            # This documentation file
├── state_schema.json    # JSON schema defining the FSM shared execution state
├── events.json          # Register for first-class transition events
└── prompts/             # Isolated system prompts for the 11 subagents
     ├── analyst.md
     ├── memory.md
     ├── architect.md
     ├── governor.md
     ├── aggregator.md
     ├── builder.md
     ├── integrator.md
     ├── cso.md
     ├── reviewer.md
     ├── qa.md
     ├── user_alias.md
     └── release_manager.md
```

---

## 2. Dynamic Integration Instructions

To bind a project workspace to this plugin:
1. Ensure your local `CLAUDE.md` specifies:
   ```markdown
   pipeline: sclass-v5
   executionMode: Human-in-the-Loop | Goal Convergence Mode
   ```
2. The orchestrator automatically loads rules from this plugin directory and configures all 11 subagents with their corresponding prompt markdown files.
3. Only workspace-specific parameters and mathematical formulas are left in the project's local `.agents/orchestration.md`.
