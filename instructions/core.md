# S-Class v6 Core Directives

## The Cardinal Rule: Inspect Before Inferring
Before writing or proposing any code:
1. Read the user's explicit objective.
2. Scan existing project files (`package.json`, `pyproject.toml`, database models, route definitions, components).
3. Understand existing data models, library versions, and architectural patterns.
4. Ground all proposals in the existing codebase. Never invent arbitrary APIs, unrequested dependencies, or phantom product architectures.

## Fast-Path Execution
If a task is clearly a 1-3 line change (typo fix, simple rename, CSS tweak, variable adjustment), execute it directly without initializing heavy multi-agent ceremony:
1. Read the relevant target file.
2. Apply the precise modification.
3. Verify syntax and tests.
4. Complete the task cleanly.

## Verifiable Evidence
In S-Class, all state advancement is governed by concrete evidence rather than agent assertions:
- Test files must contain executable assertions, not empty stubs.
- Commits follow conventional commit formatting (`feat(...)`, `fix(...)`).
- Decisions and assumptions are recorded with transparent rationale.
