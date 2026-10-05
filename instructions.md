# S-Class v6 Adaptive Engineering Guard

S-Class EOS v6 provides deterministic, evidence-backed workflow management and verification for autonomous AI software engineering. It dynamically selects the shortest safe FSM path and minimal subagent count for each task.

## The Cardinal Rule: Inspect Before Inferring
Before writing or proposing any code:
1. Read the user's objective.
2. Scan existing project files (`package.json`, `pyproject.toml`, database schemas, routes, and models).
3. Understand existing data models, typing conventions, and architectural patterns.
4. Ground all proposals in the existing codebase. Never invent arbitrary APIs, unrequested dependencies, or phantom architectures.

## Fast-Path Execution (Bypass Heavy Ceremony)
For 1-3 line changes (typos, renames, simple values, color/CSS tweaks):
- Read the target file.
- Apply the targeted change.
- Verify syntax and tests.
- Complete immediately without state overhead or subagent spawning.

## Adaptive FSM Execution
When a task involves multi-file changes or structural logic:
1. Initialize state with `runtime.initialize_state(goal="...")`.
2. S-Class classifies the task into a tailored profile:
   - `MICRO`: 3 states (`TRIAGE` → `CODING` → `DONE`), 0 subagents.
   - `SMALL_FIX`: 5 states (`TRIAGE` → `ANALYSIS` → `CODING` → `TASK_VERIFICATION` → `DONE`), 0 subagents.
   - `BUG_FIX`: 11 states, targeted builder + QA subagents.
   - `CORE`: 7 states for algorithms, CLI, and libraries without frontend overhead.
   - `FULL`: 15 states with multi-agent architecture and debate for greenfield products.
3. Advance states using `runtime.dispatch_event(event_name)`.

## Phase Guidelines

### CODING
- Implement minimal required changes adhering to existing codebase patterns.
- Every new test file must include real executable assertions (`assert`, `expect`). Empty mock stubs are rejected.
- Audit diffs using `diff_auditor.py` to prevent scope creep, test weakening, and exposed secrets.

### QA & Verification
- Run automated unit and integration tests; require green exit codes.
- For UI tasks, capture authentic Chrome DevTools MCP screenshots and DOM layouts.
- Zero uncaught exceptions or HTTP 500 errors in console logs.

### Evidence & Release
- Verify tamper-evident SHA-256 state hashes against the evidence log before release.
- Commit all modifications using conventional commit formatting (`feat(...)`, `fix(...)`).
