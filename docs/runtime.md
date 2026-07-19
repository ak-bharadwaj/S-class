# S-Class Runtime Architecture

The S-Class Runtime is a portable, technology-agnostic workflow execution engine. It coordinates agent tasks based on a strict Finite-State Machine (FSM) schema.

---

## 1. Engine Core Flow
The core runtime separates execution orchestration from prompt management. It executes the FSM states based on dispatched events:
*   **State Machine Execution:** Evaluates FSM configurations and checks exit criteria dynamically.
*   **Event Dispatcher:** Intercepts and routes JSON events, shifting states accordingly.
*   **State Ownership:** The runtime is the *only* writer to `orchestration_state.json`. Subagents output structured messages only.

---

## 2. Host Adapters
S-Class defines standard interfaces allowing clean integration with host development environments:
*   **Antigravity Adapter:** Binds subagents to the Antigravity local workspace CLI.
*   **VS Code / IDE Adapter:** Connects build events and lint checks directly to editors.
*   **API-driven Host (Claude/OpenAI):** Routes subagent tasks via standard HTTP API calls.

---

## 3. Parallel Scheduling
To maximize processing performance, the runtime triggers concurrent groups:
1.  **Group #1 (Debate):** Invokes Governor, CSO, Reviewer, and User Proxy in parallel.
2.  **Group #2 (Verification):** Invokes Reviewer, CSO, and QA in parallel.

---

## 4. Timeout Safety Controls
Parallel agents have a wait limit (e.g. 5 minutes). If a timeout occurs:
*   **Retry:** Re-invokes the stalled agent once.
*   **Fallback:** If failed, proceeds with the remaining agent votes and logs low confidence.
