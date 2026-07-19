# Antigravity Plugin Lifecycle & Runtime

The S-Class plugin coordinates execution processes by binding directly to the Antigravity runtime environment. It implements the standard lifecycle protocols defined for Antigravity workflow extensions.

---

## 1. The Antigravity Plugin Lifecycle

S-Class execution follows a six-stage lifecycle:

```
 [ Install ] ──> [ Load ] ──> [ Initialize ] ──> [ Register Events ]
                                                         │
                                                         ▼
 [ Shutdown ] <──────────────── [ Execute ] <────────────┘
```

1.  **Install:** Developer clones or runs the installation script, placing the plugin folder in `~/.gemini/config/plugins/`.
2.  **Load:** Antigravity boots up in a workspace, scans `CLAUDE.md`, and imports the `sclass-v5` plugin structure.
3.  **Initialize:** The State Manager instantiates the FSM session and creates the local `.agents/orchestration_state.json` file.
4.  **Register Events:** The event router registers the event transition schemas from `events.json`.
5.  **Execute:** The subagent pipeline processes user objectives through transitions, audits, and code patches.
6.  **Shutdown:** Cleans up temporary code structures, commits final decision logs, and outputs execution results.

---

## 2. Antigravity Sessions & Memory Integration
S-Class runs subagents inside the active Antigravity session workspace:
*   **Context Injection:** The memory agent queries Antigravity's indexed knowledge bases to populate design blueprints.
*   **State Locking:** Workspace file operations are synchronized to ensure that only `dss_builder_v2` writes code, preventing merge conflicts.
*   **Global Rule Matching:** Workspaces automatically inherit the FSM rules from the global configuration directories without folder clutter.
