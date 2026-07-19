# S-Class SDK: Context Management & Knowledge Indexing Roadmap (V6.0)

This roadmap details the future architectural transitions of the S-Class SDK. While FSM states, event-driven transitions, task compilation, and decision logging solve **80-90%** of conversational memory constraints, scaling to unlimited repository sizes requires moving from basic text retrieval to a structured **Knowledge & Retrieval Layer**.

---

## 1. The Context Bottleneck

On large repositories (100+ files), even with task-level decomposition, a coder subagent still needs to understand:
*   The API signatures of related services.
*   Schema definitions of linked database entities.
*   Cross-module dependencies.

Loading all related code files overflows context windows, leading to degradation of logic, stubs injection, and regression errors.

---

## 2. Structured Knowledge & Retrieval Architecture (V6.0)

To resolve repository-scale context bottlenecks, S-Class is transitioning to a **Selective Context Manager**:

```
                       [ Task Request ]
                              │
                              ▼
                  [ Knowledge Retriever ]
                              │
       ┌──────────────────────┼──────────────────────┐
       ▼                      ▼                      ▼
 [ Module Summaries ]   [ Dependency Graph ]   [ Global Maps ]
       │                      │                      │
       └──────────────────────┼──────────────────────┘
                              │ (Load only delta)
                              ▼
                    [ Builder Context Window ]
```

### A. Hierarchical Memory Layers
Instead of passing the entire codebase or conversation history, context is scoped hierarchically:
1.  **Global Layer:** High-level system architecture and database layouts.
2.  **Module Layer:** Living summaries of specific folders/subsystems (e.g. `auth/` public interfaces).
3.  **Task Layer:** Acceptance criteria and target file delta.
4.  **Execution Layer:** Stdin/Stdout logs of the active compiler/test check.
*   *Rule:* Only the lowest layer (Execution + Task + relevant Module metadata) is loaded into the model's active window.

### B. Architectural Module Summaries
Modules will maintain living architectural summaries (stored in `.agents/knowledge/` or directly in code docstrings):
*   **Purpose:** What the module is responsible for.
*   **Public APIs:** Exposed signatures and constructors.
*   **Dependencies:** Modules this code imports.
*   **Constraints:** Known limits and physics boundaries.
*   *Outcome:* The builder reads the module summary to call APIs correctly, without opening the raw implementation code of the module.

### C. Codebase Dependency Graphs
S-Class will build and query a dependency graph of the codebase:
*   **Query:** *"What depends on `auth_service.py`?"*
*   **Outcome:** Returns the list of files (e.g. `router.py`, `middleware.py`). Only these files are monitored for changes or loaded for diff audits, preventing regression checks from overflowing context.
