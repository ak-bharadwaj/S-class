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

---

## 3. Separation of Concerns (Workflow vs. Execution)

To keep responsibilities clean and decouple logic:
*   **S-Class (Workflow Engine):** Responsible for tracking the active state, registering valid transition event matrices, enforcing capabilities/permissions, executing metadata side-effects (like version increments), and committing changes atomically. *It never decides what agent to call next or runs the LLM model directly.*
*   **Antigravity (Execution Engine):** Responsible for reading the current phase from the state file, loading the corresponding prompt/agent role from the plugin, running the LLM model, validating outputs, and dispatching transition events back to S-Class.

---

## 4. Host Loop Execution Protocols

The host runs a continuous execution loop determined by the selected mode:

### A. Goal Convergence Mode Loop
```python
while state.currentPhase != "DONE":
    # 1. Fetch current phase and task parameters from state
    phase = runtime.get_state().currentPhase
    
    # 2. Load the prompt template for the phase
    prompt = load_prompt_file(phase)
    
    # 3. Invoke the model & collect output
    result = host.run_model(prompt)
    
    # 4. Assess transition event
    event = parse_transition_event(result)
    
    # 5. Dispatch transition back to state
    runtime.dispatch_event(event)
```

### B. Human-in-the-Loop Mode
Works identically to the Goal Convergence loop but halts for manual human override permissions at selected checkpoints before continuing:
```
Current Phase -> Await Output -> Validate & Dispatch -> WAIT (Await User Continue) -> Next Phase
```
