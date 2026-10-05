# Phase: ANALYSIS

Objectives:
- Read existing codebase files and query the Codebase Knowledge Graph (CKG).
- Trace symbol dependencies, imports, and downstream blast radius.
- Identify existing conventions, data transfer objects, and error handling patterns.
- Do not modify source files during this phase.
- Once context is loaded, transition forward via `dispatch_event("context_loaded")` or `dispatch_event("analysis_done")`.
