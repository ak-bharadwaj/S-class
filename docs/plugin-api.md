# S-Class Plugin Integration & API

This document details the configuration files, manifest variables, and state schemas used to integrate S-Class into the Antigravity environment.

---

## 1. Antigravity Manifest Schema (`plugin.json`)
The manifest configures how Antigravity registers and runs the workflow:
*   `id`: Unique identifier (e.g. `sclass-v5`).
*   `name`: Display name.
*   `version`: Semantic versioning (e.g. `5.2.0`).
*   `author`: Author name.
*   `supports`: Lists compatible frameworks.
*   `executionModes`: Declares support for Human-in-the-loop and Goal Convergence modes.

---

## 2. Shared State Model (`state_schema.json`)
The State Manager commits task parameters and history to the local workspace file `.agents/orchestration_state.json`:
*   `taskId`: Current session ID.
*   `currentPhase`: Active FSM state.
*   `retryCount`: Failure recovery attempts.
*   `tasks`: Array of tasks containing `dependsOn` dependency locks.
*   `decisionLog`: Logs choices, alternatives, confidence metrics, and timestamps.

---

## 3. Agent Capabilities (`capabilities.json`)
Restricts subagent actions inside the active Antigravity workspace:
*   `can_read`: Permission to read files.
*   `can_write`: Permission to write or patch source files.
*   `can_dispatch_events`: Permission to trigger event transitions.
*   `can_vote`: Permission to issue confidence scores during debate rounds.
